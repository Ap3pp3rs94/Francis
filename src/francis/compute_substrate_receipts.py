from __future__ import annotations

import json
import os
import uuid
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any, Protocol

from francis.compute_substrate_types import (
    COMPUTE_RECEIPT_KIND,
    _NO_FILESYSTEM_SCOPE,
    _dict_or_empty,
    _int_or_default,
    _now_ms,
    _safe_id,
    _safe_text,
    _scope_tuple,
    ApprovalConsumptionResult,
    CapabilityReceipt,
    TaskEnvelope,
    WorkerDescriptor,
)
from francis.kernel.paths import data_dir

_RECEIPT_SCHEMA_VERSION = 1
_SAFE_RECEIPT_ID_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")


def _safe_receipt_id(value: Any) -> str:
    text = _safe_text(value)
    if not text or len(text) > 160 or any(ch not in _SAFE_RECEIPT_ID_CHARS for ch in text):
        raise ValueError("unsafe_receipt_id")
    return text


def _receipt_safe_budget(budget: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(budget)
    scopes = _scope_tuple(payload.get("filesystem_scope"))
    payload["filesystem_scope"] = ["none"] if scopes == _NO_FILESYSTEM_SCOPE else ["non_default_scope_requested"]
    return payload


class ComputeReceiptStore(Protocol):
    def write_receipt(self, receipt: CapabilityReceipt) -> CapabilityReceipt: ...

    def read_receipt(self, receipt_id: str) -> CapabilityReceipt | None: ...

    def describe(self) -> dict[str, Any]: ...


class LocalJsonComputeReceiptStore:
    def __init__(self, receipt_root: Path | str | None = None) -> None:
        root = (
            Path(receipt_root)
            if receipt_root is not None
            else data_dir() / "artifacts" / "compute_substrate" / "capability_receipts"
        )
        self.receipt_root = root.expanduser().resolve()

    def describe(self) -> dict[str, Any]:
        return {
            "kind": "francis.compute_substrate.local_json_receipt_store",
            "receipt_root": str(self.receipt_root),
            "schema_version": _RECEIPT_SCHEMA_VERSION,
            "writes_memory": False,
            "approval_consumption": "not_implemented",
            "network": False,
            "gpu": False,
            "shell": False,
            "daemon": False,
            "arbitrary_filesystem_access": False,
        }

    def write_receipt(self, receipt: CapabilityReceipt) -> CapabilityReceipt:
        path = self._receipt_path(receipt.receipt_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        persisted_receipt = replace(
            receipt,
            budget=_receipt_safe_budget(receipt.budget),
            persisted=True,
            receipt_path=str(path),
            receipt_error="",
            governance={
                **receipt.governance,
                "receipt_persistence": "persisted_local_json",
                "receipt_store": "local_json_compute_receipt_store",
                "durable_compute_receipt": True,
                "durable_audit_authority": "compute_capability_receipt_only",
                "receipt_store_configured": True,
                "writes_memory": False,
                "long_term_memory_persistence": False,
                "approval_consumption": receipt.governance.get("approval_consumption", "not_required"),
                "os_level_cpu_memory_enforcement": False,
            },
        )
        approval_consumed = bool(persisted_receipt.governance.get("approval_consumed"))
        payload = {
            "schema_version": _RECEIPT_SCHEMA_VERSION,
            "kind": "francis.compute_substrate.local_json_capability_receipt",
            "receipt": persisted_receipt.to_dict(),
            "governance": {
                "bounded_local_json": True,
                "compute_receipt_only": True,
                "does_not_persist_task_payload": True,
                "does_not_persist_task_output": True,
                "does_not_write_memory": True,
                "does_not_consume_approval": not approval_consumed,
                "approval_consumed": approval_consumed,
                "does_not_grant_execution_authority": True,
                "does_not_use_network": True,
                "does_not_use_gpu": True,
                "does_not_start_daemon": True,
                "does_not_run_shell": True,
            },
        }
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
        return persisted_receipt

    def read_receipt(self, receipt_id: str) -> CapabilityReceipt | None:
        path = self._receipt_path(receipt_id)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict):
            return None
        receipt_payload = payload.get("receipt")
        if not isinstance(receipt_payload, dict):
            return None
        return CapabilityReceipt(
            kind=_safe_text(receipt_payload.get("kind")) or COMPUTE_RECEIPT_KIND,
            receipt_id=_safe_receipt_id(receipt_payload.get("receipt_id")),
            task_id=_safe_id(receipt_payload.get("task_id"), fallback_prefix="task"),
            worker_id=_safe_id(receipt_payload.get("worker_id"), fallback_prefix="worker"),
            backend_name=_safe_text(receipt_payload.get("backend_name")),
            function_name=_safe_text(receipt_payload.get("function_name")),
            trace_id=_safe_text(receipt_payload.get("trace_id")),
            approval_id=_safe_text(receipt_payload.get("approval_id")),
            status=_safe_text(receipt_payload.get("status")),
            reason=_safe_text(receipt_payload.get("reason")),
            budget=_dict_or_empty(receipt_payload.get("budget")),
            persisted=bool(receipt_payload.get("persisted")),
            receipt_path=_safe_text(receipt_payload.get("receipt_path")),
            receipt_error=_safe_text(receipt_payload.get("receipt_error")),
            governance=_dict_or_empty(receipt_payload.get("governance")),
            created_at_ms=_int_or_default(receipt_payload.get("created_at_ms"), default=_now_ms()),
        )

    def _receipt_path(self, receipt_id: str) -> Path:
        clean_id = _safe_receipt_id(receipt_id)
        root = self.receipt_root
        path = (root / f"{clean_id}.json").resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise ValueError("receipt_path_outside_root") from exc
        return path


class CapabilityReceiptAdapter:
    """Creates the compute capability receipt object before optional persistence."""

    def create(
        self,
        *,
        envelope: TaskEnvelope,
        descriptor: WorkerDescriptor,
        status: str,
        reason: str,
        approval_result: ApprovalConsumptionResult | None = None,
    ) -> CapabilityReceipt:
        approval_governance = _approval_governance(envelope, approval_result)
        return CapabilityReceipt(
            kind=COMPUTE_RECEIPT_KIND,
            receipt_id=f"compute_capability_{uuid.uuid4().hex[:16]}",
            task_id=envelope.task_id,
            worker_id=descriptor.worker_id,
            backend_name=descriptor.backend_name,
            function_name=envelope.function_name,
            trace_id=_safe_id(envelope.trace_id, fallback_prefix="trace") if envelope.trace_id else "",
            approval_id=_safe_id(envelope.approval_id, fallback_prefix="approval") if envelope.approval_id else "",
            status=status,
            reason=reason,
            budget=envelope.budget.to_dict(),
            persisted=False,
            receipt_path="",
            receipt_error="",
            governance={
                "local_first": True,
                "registered_function_only": True,
                "arbitrary_subprocess": False,
                "shell": False,
                "unrestricted_filesystem_write": False,
                "unrestricted_network": False,
                "background_daemon": False,
                "network_requested": envelope.budget.allow_network,
                "gpu_requested": envelope.budget.allow_gpu,
                "uses_network": False,
                "uses_gpu": False,
                "starts_processes": descriptor.starts_processes,
                "worker_enabled": descriptor.enabled,
                "writes_memory": False,
                "long_term_memory_persistence": False,
                "receipt_persistence": "in_memory_only",
                "receipt_store_configured": False,
                **approval_governance,
                "os_level_cpu_memory_enforcement": False,
                "timeout_enforcement": "budget_validation_elapsed_check_and_registered_function_caps",
            },
        )


def _approval_governance(
    envelope: TaskEnvelope,
    approval_result: ApprovalConsumptionResult | None,
) -> dict[str, Any]:
    if not envelope.budget.approval_required:
        return {
            "approval_required": False,
            "approval_satisfied": False,
            "approval_id": "",
            "approval_decision": "not_required",
            "approval_denial_reason": "",
            "approval_consumed": False,
            "approval_consumption": "not_required",
            "approval_scope_summary": {},
            "approval_persistence": "not_implemented_internal_in_memory_only",
        }

    if approval_result is None:
        return {
            "approval_required": True,
            "approval_satisfied": False,
            "approval_id": _safe_text(envelope.approval_id),
            "approval_decision": "missing_approval",
            "approval_denial_reason": "missing_approval",
            "approval_consumed": False,
            "approval_consumption": "denied_not_consumed",
            "approval_scope_summary": {},
            "approval_persistence": "not_implemented_internal_in_memory_only",
        }

    if approval_result.allowed:
        consumption = "consumed" if approval_result.consumed else "satisfied_reusable"
        return {
            "approval_required": True,
            "approval_satisfied": True,
            "approval_id": approval_result.approval_id,
            "approval_decision": approval_result.reason,
            "approval_denial_reason": "",
            "approval_consumed": approval_result.consumed,
            "approval_consumption": consumption,
            "approval_scope_summary": dict(approval_result.scope_summary),
            "approval_persistence": "not_implemented_internal_in_memory_only",
        }

    return {
        "approval_required": True,
        "approval_satisfied": False,
        "approval_id": approval_result.approval_id or _safe_text(envelope.approval_id),
        "approval_decision": approval_result.reason,
        "approval_denial_reason": approval_result.reason,
        "approval_consumed": False,
        "approval_consumption": "denied_not_consumed",
        "approval_scope_summary": dict(approval_result.scope_summary),
        "approval_persistence": "not_implemented_internal_in_memory_only",
    }
