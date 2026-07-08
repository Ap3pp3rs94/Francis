from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace
from typing import Protocol

from francis.compute_substrate_types import (
    _int_or_default,
    _now_ms,
    _risk_rank,
    _safe_text,
    ApprovalConsumptionResult,
    ApprovalGrant,
    TaskEnvelope,
    WorkerDescriptor,
)


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
