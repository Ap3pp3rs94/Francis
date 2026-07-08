from __future__ import annotations

import json
import os
import uuid
from collections.abc import Iterable
from dataclasses import replace
from pathlib import Path
from typing import Any
from typing import Protocol

from francis.compute_substrate_types import (
    _int_or_default,
    _now_ms,
    _risk_rank,
    _safe_text,
    _strict_approval_id,
    ApprovalConsumptionResult,
    ApprovalGrant,
    ApprovalScope,
    TaskEnvelope,
    WorkerDescriptor,
)
from francis.governance.redaction import redact_secret_text
from francis.kernel.paths import data_dir

_APPROVAL_SCHEMA_VERSION = 1


def _safe_approval_id(value: Any) -> str:
    return _strict_approval_id(value)


class ApprovalStore(Protocol):
    def authorize(self, envelope: TaskEnvelope, descriptor: WorkerDescriptor) -> ApprovalConsumptionResult: ...

    def consume(self, envelope: TaskEnvelope, descriptor: WorkerDescriptor) -> ApprovalConsumptionResult: ...

    def get(self, approval_id: str) -> ApprovalGrant | None: ...


class InMemoryApprovalStore:
    """Process-local approval grants for internal compute substrate execution."""

    def __init__(self, grants: Iterable[ApprovalGrant] = ()) -> None:
        self._grants: dict[str, ApprovalGrant] = {}
        for grant in grants:
            self.add(grant)

    def add(self, grant: ApprovalGrant) -> ApprovalGrant:
        self._grants[grant.approval_id] = grant
        return grant

    def get(self, approval_id: str) -> ApprovalGrant | None:
        return self._grants.get(_safe_text(approval_id))

    def authorize(self, envelope: TaskEnvelope, descriptor: WorkerDescriptor) -> ApprovalConsumptionResult:
        approval_id = _safe_text(envelope.approval_id)
        if not approval_id:
            return _denied("missing_approval")

        grant = self.get(approval_id)
        if grant is None:
            return _denied("missing_approval", approval_id=approval_id)

        return _evaluate_grant(envelope, descriptor, grant)

    def consume(self, envelope: TaskEnvelope, descriptor: WorkerDescriptor) -> ApprovalConsumptionResult:
        approval_id = _safe_text(envelope.approval_id)
        decision = self.authorize(envelope, descriptor)
        if not decision.allowed:
            return decision

        grant = self.get(approval_id)
        if grant is None:
            return _denied("missing_approval", approval_id=approval_id)

        decision = _evaluate_grant(envelope, descriptor, grant)
        if not decision.allowed:
            return decision

        if grant.single_use:
            if grant.consumed_at_ms > 0:
                return _denied("already_consumed_approval", grant=grant)
            consumed = replace(
                grant,
                consumed_at_ms=_now_ms(),
                consumed_by_task_id=envelope.task_id,
            )
            self._grants[grant.approval_id] = consumed
            return _allowed(consumed, consumed=True)

        return _allowed(grant, consumed=False)

    def describe(self) -> dict[str, Any]:
        return {
            "kind": "francis.compute_substrate.in_memory_approval_store",
            "stored_approval_count": len(self._grants),
            "durable": False,
            "stores_raw_task_payload": False,
            "stores_raw_execution_output": False,
            "stores_raw_approval_notes": False,
            "writes_memory": False,
        }


class LocalJsonComputeApprovalStore:
    """Local JSON persistence for compute approval grants.

    This store provides durable local readback and sequential single-use
    consumption. It does not implement cross-process atomic reservation.
    """

    def __init__(self, approval_root: Path | str | None = None) -> None:
        root = (
            Path(approval_root)
            if approval_root is not None
            else data_dir() / "artifacts" / "compute_substrate" / "approval_grants"
        )
        self.approval_root = root.expanduser().resolve()

    def describe(self) -> dict[str, Any]:
        return {
            "kind": "francis.compute_substrate.local_json_approval_store",
            "approval_root": str(self.approval_root),
            "schema_version": _APPROVAL_SCHEMA_VERSION,
            "durable": True,
            "bounded_local_json": True,
            "single_process_sequential_semantics": True,
            "cross_process_atomic_reservation": False,
            "stores_raw_task_payload": False,
            "stores_raw_execution_output": False,
            "stores_raw_approval_notes": False,
            "writes_memory": False,
            "network": False,
            "gpu": False,
            "shell": False,
            "daemon": False,
            "arbitrary_filesystem_access": False,
        }

    def add(self, grant: ApprovalGrant) -> ApprovalGrant:
        self._write_grant(grant)
        return grant

    def get(self, approval_id: str) -> ApprovalGrant | None:
        path = self._approval_path(approval_id)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return _approval_grant_from_payload(payload)

    def authorize(self, envelope: TaskEnvelope, descriptor: WorkerDescriptor) -> ApprovalConsumptionResult:
        approval_id = _safe_text(envelope.approval_id)
        if not approval_id:
            return _durable_result(_denied("missing_approval"))

        try:
            grant = self.get(approval_id)
        except ValueError:
            return _durable_result(_denied("unsafe_approval_id", evidence={"approval_id_rejected": True}))
        if grant is None:
            return _durable_result(_denied("missing_approval", approval_id=approval_id))

        return _durable_result(_evaluate_grant(envelope, descriptor, grant))

    def consume(self, envelope: TaskEnvelope, descriptor: WorkerDescriptor) -> ApprovalConsumptionResult:
        approval_id = _safe_text(envelope.approval_id)
        if not approval_id:
            return _durable_result(_denied("missing_approval"))

        try:
            grant = self.get(approval_id)
        except ValueError:
            return _durable_result(_denied("unsafe_approval_id", evidence={"approval_id_rejected": True}))
        if grant is None:
            return _durable_result(_denied("missing_approval", approval_id=approval_id))

        decision = _evaluate_grant(envelope, descriptor, grant)
        if not decision.allowed:
            return _durable_result(decision)

        if grant.single_use:
            consumed = replace(
                grant,
                consumed_at_ms=_now_ms(),
                consumed_by_task_id=envelope.task_id,
            )
            try:
                self._write_grant(consumed)
            except Exception as exc:
                return ApprovalConsumptionResult(
                    allowed=False,
                    reason="approval_persistence_failed",
                    approval_id=grant.approval_id,
                    consumed=False,
                    scope_summary=grant.scope.to_summary(),
                    evidence={
                        **_durable_evidence(),
                        "approval_persistence": "persistence_failed",
                        "approval_write_failed": True,
                        "error_type": type(exc).__name__,
                        "error": _safe_text(exc)[:160],
                    },
                )
            return _durable_result(_allowed(consumed, consumed=True))

        return _durable_result(_allowed(grant, consumed=False))

    def _write_grant(self, grant: ApprovalGrant) -> None:
        path = self._approval_path(grant.approval_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = _approval_grant_payload(grant)
        tmp = path.with_name(f".{path.stem}.{os.getpid()}.{uuid.uuid4().hex[:12]}.tmp")
        try:
            tmp.write_text(
                json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, default=str),
                encoding="utf-8",
            )
            os.replace(tmp, path)
        finally:
            try:
                if tmp.exists():
                    tmp.unlink()
            except OSError:
                pass

    def _approval_path(self, approval_id: str) -> Path:
        clean_id = _safe_approval_id(approval_id)
        root = self.approval_root
        path = (root / f"{clean_id}.json").resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise ValueError("approval_path_outside_root") from exc
        return path


def _denied(
    reason: str,
    *,
    approval_id: str = "",
    grant: ApprovalGrant | None = None,
    evidence: dict[str, object] | None = None,
) -> ApprovalConsumptionResult:
    return ApprovalConsumptionResult(
        allowed=False,
        reason=reason,
        approval_id=approval_id or (grant.approval_id if grant else ""),
        consumed=False,
        scope_summary=grant.scope.to_summary() if grant else {},
        evidence=evidence or {},
    )


def _allowed(grant: ApprovalGrant, *, consumed: bool) -> ApprovalConsumptionResult:
    summary = grant.scope.to_summary()
    return ApprovalConsumptionResult(
        allowed=True,
        reason="approval_consumed" if consumed else "approval_satisfied_reusable",
        approval_id=grant.approval_id,
        consumed=consumed,
        scope_summary=summary,
        evidence={
            "approval_source": grant.source,
            "approval_subject": grant.subject,
            "single_use": grant.single_use,
            "scope_checked": True,
            "approval_note_persisted": False,
        },
    )


def _evaluate_grant(
    envelope: TaskEnvelope,
    descriptor: WorkerDescriptor,
    grant: ApprovalGrant,
) -> ApprovalConsumptionResult:
    if grant.revoked:
        return _denied("revoked_approval", grant=grant)

    if grant.expires_at_ms is not None and grant.expires_at_ms <= _now_ms():
        return _denied("expired_approval", grant=grant)

    if grant.single_use and grant.consumed_at_ms > 0:
        return _denied("already_consumed_approval", grant=grant)

    scope = grant.scope
    if not scope.allowed_capabilities:
        return _denied("approval_scope_missing_capability", grant=grant)

    if scope.task_id and scope.task_id != envelope.task_id:
        return _denied(
            "task_id_mismatch",
            grant=grant,
            evidence={"expected_task_bound": True},
        )

    expected_correlation = scope.correlation_id or grant.correlation_id
    if expected_correlation and expected_correlation != envelope.trace_id:
        return _denied(
            "correlation_id_mismatch",
            grant=grant,
            evidence={"expected_correlation_bound": True},
        )

    if scope.allowed_capabilities and envelope.function_name not in scope.allowed_capabilities:
        return _denied(
            "capability_mismatch",
            grant=grant,
            evidence={"allowed_capability_count": len(scope.allowed_capabilities)},
        )

    if scope.allowed_worker_ids and descriptor.worker_id not in scope.allowed_worker_ids:
        return _denied(
            "worker_mismatch",
            grant=grant,
            evidence={"allowed_worker_count": len(scope.allowed_worker_ids)},
        )

    task_risk = _safe_text(envelope.payload.get("risk_level", "low")).lower() or "low"
    if _risk_rank(task_risk) > _risk_rank(scope.max_risk_level):
        return _denied(
            "risk_exceeds_approval",
            grant=grant,
            evidence={"task_risk_level": task_risk, "max_risk_level": scope.max_risk_level},
        )

    budget = envelope.budget
    ceiling_checks = {
        "max_runtime_ms": (scope.max_runtime_ms, budget.max_runtime_ms),
        "max_memory_mb": (scope.max_memory_mb, budget.max_memory_mb),
        "max_cpu_weight": (scope.max_cpu_weight, budget.cpu_weight),
        "max_compute_units": (scope.max_compute_units, budget.max_compute_units),
    }
    exceeded = [
        name
        for name, (approved_limit, requested) in ceiling_checks.items()
        if approved_limit is not None and _int_or_default(requested, default=0) > approved_limit
    ]
    if exceeded:
        return _denied("resource_budget_exceeds_approval", grant=grant, evidence={"exceeded": exceeded})

    return ApprovalConsumptionResult(
        allowed=True,
        reason="approval_scope_valid",
        approval_id=grant.approval_id,
        consumed=False,
        scope_summary=scope.to_summary(),
        evidence={
            "approval_source": grant.source,
            "approval_subject": grant.subject,
            "single_use": grant.single_use,
            "scope_checked": True,
            "approval_note_persisted": False,
        },
    )


def _durable_result(result: ApprovalConsumptionResult) -> ApprovalConsumptionResult:
    grant_read = result.reason not in {"missing_approval", "unsafe_approval_id"}
    if grant_read:
        persistence = "persisted_local_json"
    elif result.reason == "unsafe_approval_id":
        persistence = "approval_id_rejected_before_read"
    else:
        persistence = "local_json_store_configured_no_matching_grant"
    return replace(
        result,
        evidence={
            **result.evidence,
            **_durable_evidence(),
            "approval_persistence": persistence,
            "approval_grant_read_from_store": grant_read,
        },
    )


def _durable_evidence() -> dict[str, Any]:
    return {
        "approval_store": "local_json_compute_approval_store",
        "approval_store_kind": "francis.compute_substrate.local_json_approval_store",
        "approval_schema_version": _APPROVAL_SCHEMA_VERSION,
        "durable_approval_persistence": True,
        "approval_persistence": "persisted_local_json",
        "approval_note_persisted": False,
        "cross_process_atomic_reservation": False,
        "single_process_sequential_semantics": True,
    }


def _approval_grant_payload(grant: ApprovalGrant) -> dict[str, Any]:
    return {
        "schema_version": _APPROVAL_SCHEMA_VERSION,
        "kind": "francis.compute_substrate.local_json_approval_grant",
        "approval": {
            "approval_id": _safe_approval_id(grant.approval_id),
            "subject": _bounded_text(grant.subject, limit=120),
            "approved_by": _bounded_text(grant.approved_by, limit=120),
            "source": _bounded_text(grant.source, limit=120),
            "reason_summary": _bounded_redacted_text(grant.reason),
            "approval_note_summary": _bounded_redacted_text(grant.approval_note),
            "approval_note_present": bool(grant.approval_note),
            "correlation_id": _bounded_id(grant.correlation_id),
            "trace_id": _bounded_id(grant.trace_id),
            "expires_at_ms": grant.expires_at_ms,
            "single_use": grant.single_use,
            "consumed_at_ms": grant.consumed_at_ms,
            "consumed_by_task_id": _bounded_id(grant.consumed_by_task_id),
            "revoked": grant.revoked,
            "created_at_ms": grant.created_at_ms,
            "scope": {
                "task_id": _bounded_id(grant.scope.task_id),
                "correlation_id": _bounded_id(grant.scope.correlation_id),
                "allowed_capabilities": list(grant.scope.allowed_capabilities),
                "allowed_worker_ids": list(grant.scope.allowed_worker_ids),
                "max_risk_level": grant.scope.max_risk_level,
                "max_runtime_ms": grant.scope.max_runtime_ms,
                "max_memory_mb": grant.scope.max_memory_mb,
                "max_cpu_weight": grant.scope.max_cpu_weight,
                "max_compute_units": grant.scope.max_compute_units,
            },
        },
        "governance": {
            "bounded_local_json": True,
            "approval_grant_only": True,
            "does_not_persist_task_payload": True,
            "does_not_persist_execution_output": True,
            "does_not_persist_raw_approval_note": True,
            "does_not_persist_raw_model_prompt": True,
            "does_not_write_memory": True,
            "does_not_grant_execution_authority": True,
            "does_not_use_network": True,
            "does_not_use_gpu": True,
            "does_not_run_shell": True,
            "does_not_start_daemon": True,
            "cross_process_atomic_reservation": False,
            "schema_version": _APPROVAL_SCHEMA_VERSION,
        },
    }


def _approval_grant_from_payload(payload: Any) -> ApprovalGrant | None:
    if not isinstance(payload, dict):
        return None
    if _int_or_default(payload.get("schema_version"), default=0) != _APPROVAL_SCHEMA_VERSION:
        return None
    approval = payload.get("approval")
    if not isinstance(approval, dict):
        return None
    scope_payload = approval.get("scope")
    if not isinstance(scope_payload, dict):
        scope_payload = {}
    approval_id = _safe_approval_id(approval.get("approval_id"))
    return ApprovalGrant(
        approval_id=approval_id,
        scope=ApprovalScope(
            task_id=_safe_text(scope_payload.get("task_id")),
            correlation_id=_safe_text(scope_payload.get("correlation_id")),
            allowed_capabilities=_tuple_text(scope_payload.get("allowed_capabilities")),
            allowed_worker_ids=_tuple_text(scope_payload.get("allowed_worker_ids")),
            max_risk_level=_safe_text(scope_payload.get("max_risk_level")) or "low",
            max_runtime_ms=_optional_int(scope_payload.get("max_runtime_ms")),
            max_memory_mb=_optional_int(scope_payload.get("max_memory_mb")),
            max_cpu_weight=_optional_int(scope_payload.get("max_cpu_weight")),
            max_compute_units=_optional_int(scope_payload.get("max_compute_units")),
        ),
        subject=_safe_text(approval.get("subject")) or "compute_substrate_task",
        approved_by=_safe_text(approval.get("approved_by")) or "local.operator",
        source=_safe_text(approval.get("source")) or "local_json_compute_approval_store",
        reason=_safe_text(approval.get("reason_summary")),
        approval_note=_safe_text(approval.get("approval_note_summary")),
        correlation_id=_safe_text(approval.get("correlation_id")),
        trace_id=_safe_text(approval.get("trace_id")),
        expires_at_ms=_optional_int(approval.get("expires_at_ms")),
        single_use=bool(approval.get("single_use", True)),
        consumed_at_ms=_int_or_default(approval.get("consumed_at_ms"), default=0),
        consumed_by_task_id=_safe_text(approval.get("consumed_by_task_id")),
        revoked=bool(approval.get("revoked", False)),
        created_at_ms=_int_or_default(approval.get("created_at_ms"), default=_now_ms()),
    )


def _tuple_text(value: Any) -> tuple[str, ...]:
    try:
        items = list(value)
    except TypeError:
        return ()
    return tuple(_safe_text(item) for item in items if _safe_text(item))


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    parsed = _int_or_default(value, default=0)
    return parsed if parsed > 0 else None


def _bounded_id(value: Any) -> str:
    text = _safe_text(value)
    if not text:
        return ""
    if all(ch.isalnum() or ch in ("-", "_", ".") for ch in text):
        return text[:160]
    return ""


def _bounded_text(value: Any, *, limit: int = 240) -> str:
    return _safe_text(value)[:limit]


def _bounded_redacted_text(value: Any, *, limit: int = 240) -> str:
    return redact_secret_text(_safe_text(value))[:limit]
