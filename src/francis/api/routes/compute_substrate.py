from __future__ import annotations

import re
import uuid
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from francis.api.errors import api_error_code, log_api_exception
from francis.compute_substrate import (
    CancellationToken,
    CapabilityReceipt,
    ComputeSubstrateService,
    ComputeSubmission,
    ComputeSubmissionResult,
    ComputeTaskRecord,
    ComputeTaskStatus,
    ExecutionContext,
    ExecutionDeadline,
    LocalJsonComputeApprovalStore,
    LocalJsonComputeReceiptStore,
    LocalJsonComputeStatusStore,
    ResourceBudget,
    TaskEnvelope,
)
from francis.governance.api_permission_gate import ApiPermissionDecision, ApiPermissionGate

router = APIRouter()

_COMPUTE_SUBMIT_SCOPE = "compute:submit"
_COMPUTE_STATUS_READ_SCOPE = "compute:status:read"
_COMPUTE_RECEIPT_READ_SCOPE = "compute:receipt:read"
_SAFE_API_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,120}$")
_SAFE_CAPABILITY_RE = re.compile(r"^[A-Za-z0-9_.-]{1,120}$")
_SUPPORTED_CAPABILITIES = {
    "echo",
    "health_check",
    "compute_test",
    "cooperative_delay_test",
    "summarize_status",
}


class ComputeResourceBudgetIn(BaseModel):
    max_runtime_ms: int = 1000
    max_memory_mb: int = 128
    cpu_weight: int = 25
    priority: str = "normal"
    allow_network: bool = False
    filesystem_scope: list[str] = Field(default_factory=lambda: ["none"])
    allow_gpu: bool = False
    cancel_requested: bool = False
    approval_required: bool = False
    max_compute_units: int = 1000

    def to_budget(self, *, approval_required: bool) -> ResourceBudget:
        return ResourceBudget(
            max_runtime_ms=self.max_runtime_ms,
            max_memory_mb=self.max_memory_mb,
            cpu_weight=self.cpu_weight,
            priority=self.priority,
            allow_network=self.allow_network,
            filesystem_scope=tuple(self.filesystem_scope or ["none"]),
            allow_gpu=self.allow_gpu,
            cancel_requested=self.cancel_requested,
            approval_required=approval_required or self.approval_required,
            max_compute_units=self.max_compute_units,
        )


class ComputeDeadlineIn(BaseModel):
    deadline_at_ms: int = 0
    source: str = "api"


class ComputeSubmitIn(BaseModel):
    request_id: Any = ""
    actor_id: Any = ""
    requested_capability: Any = ""
    task_type: Any = "direct_compute_request"
    intent_summary: Any = ""
    payload: Any = Field(default_factory=dict)
    payload_summary: Any = ""
    resource_budget: Any = Field(default_factory=dict)
    risk_level: Any = "low"
    approval_required: Any = False
    approval_id: Any = ""
    correlation_id: Any = ""
    trace_id: Any = ""
    deadline: Any = None
    cancel_requested: Any = False
    cancellation_reason: Any = ""


def _compute_substrate_service() -> ComputeSubstrateService:
    return ComputeSubstrateService(
        approval_store=LocalJsonComputeApprovalStore(),
        receipt_store=LocalJsonComputeReceiptStore(),
        status_store=LocalJsonComputeStatusStore(),
    )


def _compute_receipt_store() -> LocalJsonComputeReceiptStore | None:
    return LocalJsonComputeReceiptStore()


def _safe_text(value: Any, *, limit: int = 240) -> str:
    if value is None:
        return ""
    try:
        text = str(value).strip()
    except Exception:
        return ""
    return text[:limit]


def _safe_id(value: Any) -> str:
    text = _safe_text(value, limit=160)
    return text if _SAFE_API_ID_RE.fullmatch(text) else ""


def _safe_capability(value: Any) -> str:
    text = _safe_text(value, limit=160)
    return text if _SAFE_CAPABILITY_RE.fullmatch(text) else ""


def _budget_input(value: Any) -> ComputeResourceBudgetIn | None:
    if isinstance(value, ComputeResourceBudgetIn):
        return value
    if not isinstance(value, dict):
        return None
    try:
        return ComputeResourceBudgetIn(**value)
    except Exception:
        return None


def _deadline_input(value: Any) -> ComputeDeadlineIn | None:
    if value is None:
        return None
    if isinstance(value, ComputeDeadlineIn):
        return value
    if not isinstance(value, dict):
        return None
    try:
        return ComputeDeadlineIn(**value)
    except Exception:
        return None


def _bool_input(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def _route_permission(
    *,
    actor: Any,
    required_scope: str,
    route: str,
    method: str,
) -> ApiPermissionDecision:
    return ApiPermissionGate.from_env().check(
        actor_id=actor,
        required_scopes=[required_scope],
        route=route,
        method=method,
    )


def _permission_denied(
    decision: ApiPermissionDecision,
    *,
    required_scope: str,
    next_step: str,
) -> dict[str, Any]:
    return {
        "ok": False,
        "accepted": False,
        "status": "denied",
        "error": "api_permission_denied",
        "denial_reason": decision.reason,
        "governance": {
            "gate": "permission_gate",
            "reason": decision.reason,
            "required_scope": required_scope,
            "next_step": next_step,
            "evidence": decision.evidence,
            "uses_compute_substrate_service": False,
            "calls_backend_directly": False,
            "calls_governor_directly": False,
            "grants_execution_authority": False,
            "writes_memory": False,
            "runs_shell": False,
            "starts_processes": False,
            "uses_network": False,
            "uses_gpu": False,
            "async_execution": False,
            "task_recovery": False,
        },
    }


def _malformed_request(reason: str) -> dict[str, Any]:
    return {
        "ok": False,
        "accepted": False,
        "status": "denied",
        "error": "malformed_request",
        "denial_reason": reason,
        "governance": _route_governance(
            service_touched=False,
            extra={
                "reason": reason,
                "grants_execution_authority": False,
            },
        ),
    }


def _route_governance(
    *,
    service_touched: bool,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    governance: dict[str, Any] = {
        "api_permission_gate": True,
        "uses_compute_substrate_service": service_touched,
        "calls_backend_directly": False,
        "calls_governor_directly": False,
        "mutates_receipts_directly": False,
        "mutates_approvals_directly": False,
        "mutates_status_directly": False,
        "internal_local_dev_only": True,
        "stores_payload": False,
        "stores_output": False,
        "returns_raw_execution_output": False,
        "writes_memory": False,
        "long_term_memory_persistence": False,
        "live_learning_persistence": False,
        "model_training": False,
        "async_execution": False,
        "background_execution": False,
        "task_recovery": False,
        "task_resumability": False,
        "shell": False,
        "subprocess": False,
        "network_client": False,
        "gpu_execution": False,
        "daemon": False,
        "os_level_cpu_memory_enforcement": False,
    }
    if extra:
        governance.update(extra)
    return governance


def _request_id(raw_request_id: str) -> str:
    request_id = _safe_id(raw_request_id)
    return request_id or f"api_compute_{uuid.uuid4().hex[:12]}"


def _validate_submit_request(payload: ComputeSubmitIn) -> str:
    if payload.request_id and not _safe_id(payload.request_id):
        return "invalid_request_id"
    if payload.correlation_id and not _safe_id(payload.correlation_id):
        return "invalid_correlation_id"
    if payload.trace_id and not _safe_id(payload.trace_id):
        return "invalid_trace_id"
    if payload.approval_id and not _safe_id(payload.approval_id):
        return "invalid_approval_id"
    capability = _safe_capability(payload.requested_capability)
    if not capability:
        return "missing_requested_capability"
    if capability not in _SUPPORTED_CAPABILITIES:
        return "unsupported_capability"
    if not isinstance(payload.payload, dict):
        return "invalid_payload"
    if _budget_input(payload.resource_budget) is None:
        return "invalid_resource_budget"
    if payload.deadline is not None and _deadline_input(payload.deadline) is None:
        return "invalid_deadline"
    if _bool_input(payload.approval_required) is None:
        return "invalid_approval_required"
    if _bool_input(payload.cancel_requested) is None:
        return "invalid_cancel_requested"
    return ""


def _submission_from_request(payload: ComputeSubmitIn) -> ComputeSubmission:
    request_id = _request_id(payload.request_id)
    correlation_id = _safe_id(payload.trace_id) or _safe_id(payload.correlation_id) or request_id
    budget_input = _budget_input(payload.resource_budget) or ComputeResourceBudgetIn()
    request_approval_required = bool(_bool_input(payload.approval_required))
    approval_required = bool(
        request_approval_required or budget_input.approval_required or _safe_id(payload.approval_id)
    )
    budget = budget_input.to_budget(approval_required=approval_required)
    request_payload = payload.payload if isinstance(payload.payload, dict) else {}
    envelope = TaskEnvelope(
        task_id=request_id,
        function_name=_safe_capability(payload.requested_capability),
        payload={**dict(request_payload), "risk_level": _safe_text(payload.risk_level, limit=40) or "low"},
        budget=budget,
        actor=_safe_text(payload.actor_id, limit=120) or "api.compute_substrate",
        trace_id=correlation_id,
        approval_id=_safe_id(payload.approval_id),
    )
    deadline_input = _deadline_input(payload.deadline)
    cancel_requested = bool(_bool_input(payload.cancel_requested))
    context = None
    if deadline_input is not None or cancel_requested:
        context = ExecutionContext(
            deadline=ExecutionDeadline(
                deadline_at_ms=max(0, int(deadline_input.deadline_at_ms)),
                source=_safe_text(deadline_input.source, limit=80) or "api",
            )
            if deadline_input is not None
            else ExecutionDeadline(),
            cancellation_token=CancellationToken(
                cancel_requested=cancel_requested,
                reason=_safe_text(payload.cancellation_reason, limit=120) or "api_cancel_requested",
            ),
        )
    return ComputeSubmission(envelope=envelope, context=context)


def _bounded_record_payload(record: ComputeTaskRecord, *, found: bool = True) -> dict[str, Any]:
    return {
        "found": found,
        "task_id": record.task_id,
        "correlation_id": record.correlation_id,
        "capability": record.capability,
        "worker_id": record.worker_id,
        "status": record.status,
        "denial_reason": record.denial_reason,
        "approval_required": record.approval_required,
        "approval_id": record.approval_id,
        "approval_satisfied": record.approval_satisfied,
        "approval_consumed": record.approval_consumed,
        "cancellation_requested": record.cancellation_requested,
        "cancellation_reason": record.cancellation_reason,
        "timed_out": record.timed_out,
        "timeout_stage": record.timeout_stage,
        "execution_started": record.execution_started,
        "execution_finished": record.execution_finished,
        "receipt_id": record.receipt_id,
        "receipt_persisted": record.receipt_persisted,
        "receipt_persistence_status": record.receipt_persistence_status,
        "receipt_persistence_failed": record.receipt_persistence_status == "persistence_failed",
        "started_at_ms": record.started_at_ms,
        "finished_at_ms": record.finished_at_ms,
        "duration_ms": record.duration_ms,
        "created_at_ms": record.created_at_ms,
        "updated_at_ms": record.updated_at_ms,
        "durable_status_persistence": record.durable_status_persistence,
        "status_write_attempted": record.status_write_attempted,
        "status_write_succeeded": record.status_write_succeeded,
        "status_persisted": record.status_persisted,
        "status_persistence_failed": record.status_persistence_failed,
        "status_persistence_error": record.status_persistence_error,
        "stores_payload": False,
        "stores_output": False,
        "background_execution": False,
        "async_execution": False,
    }


def _receipt_budget_summary(budget: dict[str, Any]) -> dict[str, Any]:
    filesystem_scope = budget.get("filesystem_scope")
    filesystem_summary = ["none"] if filesystem_scope == ["none"] else ["non_default_scope_requested"]
    return {
        "max_runtime_ms": budget.get("max_runtime_ms") if isinstance(budget.get("max_runtime_ms"), int) else 0,
        "max_memory_mb": budget.get("max_memory_mb") if isinstance(budget.get("max_memory_mb"), int) else 0,
        "cpu_weight": budget.get("cpu_weight") if isinstance(budget.get("cpu_weight"), int) else 0,
        "priority": _safe_text(budget.get("priority"), limit=40) or "normal",
        "allow_network": bool(budget.get("allow_network", False)),
        "filesystem_scope": filesystem_summary,
        "allow_gpu": bool(budget.get("allow_gpu", False)),
        "approval_required": bool(budget.get("approval_required", False)),
        "max_compute_units": budget.get("max_compute_units") if isinstance(budget.get("max_compute_units"), int) else 0,
    }


def _receipt_approval_scope_summary(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    ceiling = value.get("resource_budget_ceiling")
    ceiling_summary: dict[str, int | None] = {}
    if isinstance(ceiling, dict):
        for key in ("max_runtime_ms", "max_memory_mb", "max_cpu_weight", "max_compute_units"):
            raw = ceiling.get(key)
            ceiling_summary[key] = raw if isinstance(raw, int) else None
    return {
        "task_id_bound": bool(value.get("task_id_bound", False)),
        "correlation_id_bound": bool(value.get("correlation_id_bound", False)),
        "allowed_capabilities": [
            capability
            for capability in (_safe_capability(item) for item in value.get("allowed_capabilities", ()))
            if capability
        ][:20],
        "allowed_worker_ids": [
            worker_id for worker_id in (_safe_id(item) for item in value.get("allowed_worker_ids", ())) if worker_id
        ][:20],
        "max_risk_level": _safe_text(value.get("max_risk_level"), limit=40) or "low",
        "resource_budget_ceiling": ceiling_summary,
    }


def _receipt_record_payload(receipt: CapabilityReceipt, *, found: bool = True) -> dict[str, Any]:
    governance = receipt.governance
    return {
        "found": found,
        "receipt_id": receipt.receipt_id,
        "task_id": receipt.task_id,
        "correlation_id": receipt.trace_id,
        "capability": receipt.function_name,
        "worker_id": receipt.worker_id,
        "backend_name": receipt.backend_name,
        "execution_status": receipt.status,
        "reason": _safe_text(receipt.reason, limit=120),
        "approval_required": bool(governance.get("approval_required", False)),
        "approval_id": receipt.approval_id,
        "approval_satisfied": bool(governance.get("approval_satisfied", False)),
        "approval_decision": _safe_text(governance.get("approval_decision"), limit=120),
        "approval_denial_reason": _safe_text(governance.get("approval_denial_reason"), limit=120),
        "approval_consumed": bool(governance.get("approval_consumed", False)),
        "approval_persistence": _safe_text(governance.get("approval_persistence"), limit=120),
        "durable_approval_persistence": bool(governance.get("durable_approval_persistence", False)),
        "approval_scope_summary": _receipt_approval_scope_summary(governance.get("approval_scope_summary")),
        "receipt_persisted": bool(receipt.persisted),
        "receipt_persistence_status": _safe_text(governance.get("receipt_persistence"), limit=120),
        "durable_compute_receipt_persistence": bool(governance.get("durable_compute_receipt", False)),
        "resource_budget": _receipt_budget_summary(dict(receipt.budget)),
        "cancellation_requested": bool(governance.get("cancellation_requested", False)),
        "cancellation_reason": _safe_text(governance.get("cancellation_reason"), limit=120),
        "deadline_configured": bool(governance.get("deadline_configured", False)),
        "deadline_expired": bool(governance.get("deadline_expired", False)),
        "timed_out": bool(governance.get("timed_out", False)),
        "timeout_stage": _safe_text(governance.get("timeout_stage"), limit=80),
        "execution_started": bool(governance.get("execution_started", False)),
        "execution_finished": bool(governance.get("execution_finished", False)),
        "duration_ms": governance.get("duration_ms") if isinstance(governance.get("duration_ms"), int) else 0,
        "created_at_ms": receipt.created_at_ms,
        "stores_payload": False,
        "stores_output": False,
        "returns_raw_execution_output": False,
        "stores_receipt_path": False,
        "background_execution": False,
        "async_execution": False,
    }


def _receipt_response(receipt: CapabilityReceipt) -> dict[str, Any]:
    record = _receipt_record_payload(receipt)
    return {
        "ok": True,
        "status": "found",
        "error": "",
        "found": True,
        "receipt_id": receipt.receipt_id,
        "task_id": receipt.task_id,
        "correlation_id": receipt.trace_id,
        "record": record,
        "governance": _route_governance(
            service_touched=False,
            extra={
                "receipt_readback_only": True,
                "grants_execution_authority": False,
                "does_not_trigger_execution": True,
                "does_not_consume_approval": True,
                "receipt_store_read_only": True,
                "durable_compute_receipt_readback": True,
                "mutates_receipts_directly": False,
                "mutates_approvals_directly": False,
                "mutates_status_directly": False,
            },
        ),
    }


def _receipt_unavailable_response(*, error: str, reason: str, receipt_id: str) -> dict[str, Any]:
    return {
        "ok": False,
        "status": "unavailable" if error != "receipt_not_found" else "unknown",
        "error": error,
        "denial_reason": reason,
        "found": False,
        "receipt_id": receipt_id,
        "record": {
            "found": False,
            "receipt_id": receipt_id,
            "stores_payload": False,
            "stores_output": False,
            "returns_raw_execution_output": False,
            "stores_receipt_path": False,
        },
        "governance": _route_governance(
            service_touched=False,
            extra={
                "receipt_readback_only": True,
                "grants_execution_authority": False,
                "does_not_trigger_execution": True,
                "does_not_consume_approval": True,
                "receipt_store_read_only": True,
                "receipt_store_error_redacted": error
                in {
                    "receipt_store_read_failed",
                    "receipt_decode_failed",
                    "receipt_schema_unsupported",
                    "receipt_redaction_failed",
                },
            },
        ),
    }


def _submission_response(
    result: ComputeSubmissionResult,
    *,
    request_id: str,
) -> dict[str, Any]:
    record = result.record
    receipt_persistence_failed = record.receipt_persistence_status == "persistence_failed"
    return {
        "ok": result.ok,
        "accepted": record.status != ComputeTaskStatus.UNKNOWN,
        "denied": record.status == ComputeTaskStatus.DENIED,
        "status": record.status,
        "error": _submission_error(result),
        "denial_reason": record.denial_reason,
        "request_id": request_id,
        "task_id": result.task_id,
        "correlation_id": result.correlation_id,
        "approval_required": record.approval_required,
        "approval_satisfied": record.approval_satisfied,
        "approval_id": record.approval_id,
        "approval_consumed": record.approval_consumed,
        "receipt_id": record.receipt_id,
        "receipt_persisted": record.receipt_persisted,
        "receipt_persistence_status": record.receipt_persistence_status,
        "receipt_persistence_failed": receipt_persistence_failed,
        "durable_status_persistence": record.durable_status_persistence,
        "status_write_attempted": record.status_write_attempted,
        "status_write_succeeded": record.status_write_succeeded,
        "status_persisted": record.status_persisted,
        "status_persistence_failed": record.status_persistence_failed,
        "status_persistence_error": record.status_persistence_error,
        "cancellation_requested": record.cancellation_requested,
        "timed_out": record.timed_out,
        "timeout_stage": record.timeout_stage,
        "started_at_ms": record.started_at_ms,
        "finished_at_ms": record.finished_at_ms,
        "duration_ms": record.duration_ms,
        "record": _bounded_record_payload(record),
        "governance": _route_governance(
            service_touched=True,
            extra={
                "approval_grants_do_not_authorize_api_access": True,
                "api_permission_does_not_bypass_substrate_approval": True,
                "durable_approval_persistence": True,
                "durable_compute_receipt_persistence": record.receipt_persisted,
                "durable_status_persistence": record.durable_status_persistence,
            },
        ),
    }


def _submission_error(result: ComputeSubmissionResult) -> str:
    record = result.record
    if record.denial_reason:
        return record.denial_reason
    if record.receipt_persistence_status == "persistence_failed":
        return "receipt_persistence_failed"
    if record.status_persistence_failed:
        return "status_persistence_failed"
    if result.result_status == "error":
        return "backend_execution_failed"
    if result.result_error:
        return _safe_text(result.result_status, limit=80) or "compute_execution_failed"
    return ""


def _status_response(record: ComputeTaskRecord, *, found: bool) -> dict[str, Any]:
    return {
        "ok": found,
        "status": record.status,
        "error": "" if found else "status_not_found",
        "found": found,
        "task_id": record.task_id,
        "correlation_id": record.correlation_id,
        "record": _bounded_record_payload(record, found=found),
        "governance": _route_governance(
            service_touched=True,
            extra={
                "status_readback_only": True,
                "grants_execution_authority": False,
            },
        ),
    }


@router.post("/submit")
def submit_compute_task(request: Request, payload: ComputeSubmitIn) -> dict[str, Any]:
    permission = _route_permission(
        actor=payload.actor_id,
        required_scope=_COMPUTE_SUBMIT_SCOPE,
        route=request.url.path,
        method=request.method,
    )
    if not permission.allowed:
        return _permission_denied(
            permission,
            required_scope=_COMPUTE_SUBMIT_SCOPE,
            next_step="configure_actor_scope_before_compute_submission",
        )

    validation_error = _validate_submit_request(payload)
    if validation_error:
        return _malformed_request(validation_error)

    submission = _submission_from_request(payload)
    try:
        result = _compute_substrate_service().submit(submission)
    except Exception as exc:
        log_api_exception(exc, route="compute_substrate.submit")
        return {
            "ok": False,
            "accepted": False,
            "status": "failed",
            "error": api_error_code(),
            "denial_reason": "service_submission_failed",
            "request_id": submission.envelope.task_id,
            "governance": _route_governance(
                service_touched=True,
                extra={"exception_redacted": True},
            ),
        }
    return _submission_response(result, request_id=submission.envelope.task_id)


@router.get("/receipts/{receipt_id}")
def get_compute_receipt(request: Request, receipt_id: str, actor: str = "") -> dict[str, Any]:
    permission = _route_permission(
        actor=actor,
        required_scope=_COMPUTE_RECEIPT_READ_SCOPE,
        route=request.url.path,
        method=request.method,
    )
    if not permission.allowed:
        return _permission_denied(
            permission,
            required_scope=_COMPUTE_RECEIPT_READ_SCOPE,
            next_step="configure_actor_scope_before_compute_receipt_readback",
        )
    clean_id = _safe_id(receipt_id)
    if not clean_id:
        return _malformed_request("invalid_receipt_id")

    store = _compute_receipt_store()
    if store is None:
        return _receipt_unavailable_response(
            error="receipt_store_unavailable",
            reason="receipt_store_unavailable",
            receipt_id=clean_id,
        )
    try:
        read_result = store.read_receipt_result(clean_id)
    except Exception:
        return _receipt_unavailable_response(
            error="receipt_store_read_failed",
            reason="receipt_store_read_failed",
            receipt_id=clean_id,
        )
    if read_result.status == "receipt_not_found":
        return _receipt_unavailable_response(
            error="receipt_not_found",
            reason="receipt_not_found",
            receipt_id=clean_id,
        )
    if not read_result.found or read_result.receipt is None:
        error = _safe_text(read_result.error or read_result.status, limit=80) or "receipt_store_read_failed"
        return _receipt_unavailable_response(
            error=error,
            reason=error,
            receipt_id=clean_id,
        )
    try:
        return _receipt_response(read_result.receipt)
    except Exception:
        return _receipt_unavailable_response(
            error="receipt_redaction_failed",
            reason="receipt_redaction_failed",
            receipt_id=clean_id,
        )


@router.get("/status/by-correlation/{correlation_id}")
def get_compute_status_by_correlation(request: Request, correlation_id: str, actor: str = "") -> dict[str, Any]:
    permission = _route_permission(
        actor=actor,
        required_scope=_COMPUTE_STATUS_READ_SCOPE,
        route=request.url.path,
        method=request.method,
    )
    if not permission.allowed:
        return _permission_denied(
            permission,
            required_scope=_COMPUTE_STATUS_READ_SCOPE,
            next_step="configure_actor_scope_before_compute_status_readback",
        )
    clean_id = _safe_id(correlation_id)
    if not clean_id:
        return _malformed_request("invalid_correlation_id")
    record = _compute_substrate_service().status_for_correlation(clean_id)
    return _status_response(record, found=record.status != ComputeTaskStatus.UNKNOWN)


@router.get("/status/{task_id}")
def get_compute_status(request: Request, task_id: str, actor: str = "") -> dict[str, Any]:
    permission = _route_permission(
        actor=actor,
        required_scope=_COMPUTE_STATUS_READ_SCOPE,
        route=request.url.path,
        method=request.method,
    )
    if not permission.allowed:
        return _permission_denied(
            permission,
            required_scope=_COMPUTE_STATUS_READ_SCOPE,
            next_step="configure_actor_scope_before_compute_status_readback",
        )
    clean_id = _safe_id(task_id)
    if not clean_id:
        return _malformed_request("invalid_task_id")
    record = _compute_substrate_service().status_for_task(clean_id)
    return _status_response(record, found=record.status != ComputeTaskStatus.UNKNOWN)
