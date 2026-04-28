from __future__ import annotations

from typing import Any

from francis.governance.api_permission_gate import ApiPermissionGate
from francis.governance.redaction import redact_governed_value
from francis.operations import runtime as operations_runtime
from francis.world_state.operator_mode import snapshot as operator_mode_snapshot

_OPERATIONS_RUN_SCOPE = "operations.run"


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _redacted_dict(value: dict[str, Any]) -> dict[str, Any]:
    redacted = redact_governed_value(value)
    return redacted if isinstance(redacted, dict) else {}


def _operation_run_permission(actor: str) -> tuple[bool, dict[str, Any]]:
    decision = ApiPermissionGate.from_env().check(
        actor_id=actor,
        required_scopes=[_OPERATIONS_RUN_SCOPE],
        route="/reactor/events/dispatch_attempt",
        method="POST",
    )
    return decision.allowed, {"reason": decision.reason, "evidence": decision.evidence}


def _posture_block(action_label: str) -> str:
    try:
        operator_state = operator_mode_snapshot()
    except Exception as exc:
        return f"Execution is blocked until operator posture can be verified: {exc}"

    if not bool(operator_state.get("ok")):
        return "Execution is blocked until operator posture can be verified."

    control_mode = _as_dict(operator_state.get("control_mode"))
    posture = _as_dict(operator_state.get("posture"))
    control_mode_id = _safe_str(control_mode.get("id")).strip().lower()
    control_writes = _safe_str(control_mode.get("writes")).strip().lower()
    posture_writes = _safe_str(posture.get("writes")).strip().lower()

    if control_mode_id == "observe" or control_writes == "blocked":
        return f"Observe mode keeps execution read-only. Switch posture before {action_label}."
    if posture_writes == "blocked":
        return f"Current operator posture blocks writes. Adjust the environment before {action_label}."
    return ""


def _operation_identity(result: dict[str, Any]) -> dict[str, Any]:
    operation = _as_dict(result.get("operation"))
    output = _as_dict(operation.get("output"))
    memory_receipt = _as_dict(result.get("memory_receipt")) or _as_dict(operation.get("latest_memory_receipt"))
    return {
        "operation_id": _safe_str(operation.get("id") or operation.get("operation_id")).strip(),
        "operation_status": _safe_str(result.get("status") or operation.get("status")).strip(),
        "trace_id": _safe_str(operation.get("trace_id") or output.get("trace_id")).strip(),
        "run_id": _safe_str(operation.get("run_id") or output.get("run_id")).strip(),
        "memory_receipt_id": _safe_str(memory_receipt.get("receipt_id") or memory_receipt.get("id")).strip(),
        "memory_write": bool(memory_receipt),
    }


def _blocked_receipt(
    *,
    event_id: str,
    actor: str,
    reason: str,
    attempt_count: int,
    ts: int,
    gate: str,
    outcome: str,
    next_step: str,
    operation_id: str = "",
    permission: dict[str, Any] | None = None,
    message: str = "",
) -> dict[str, Any]:
    return _redacted_dict(
        {
            "kind": "reactor.dispatch.execution.receipt",
            "receipt_id": f"{event_id}_dispatch_execution_{attempt_count}",
            "event_id": event_id,
            "status": "blocked",
            "outcome": outcome,
            "route": "operation_run",
            "gate": gate,
            "stable_state": outcome,
            "next_step": next_step,
            "actor": actor,
            "reason": reason,
            "operation_id": operation_id,
            "attempt_count": attempt_count,
            "ts": ts,
            "message": message,
            "permission": permission or {},
            "execution_started": False,
            "dispatch_applied": False,
            "verified": False,
            "completion_claim_allowed": False,
            "memory_write": False,
            "governance": {
                "gate": gate,
                "execution_authority": False,
                "dispatch_authority": False,
                "approval_authority": False,
                "memory_write": False,
            },
        }
    )


def dispatch_event(
    event: dict[str, Any],
    *,
    actor: str,
    reason: str,
    attempt_count: int,
    ts: int,
) -> dict[str, Any]:
    """Run the first bounded Reactor dispatch engine path.

    Only `operation_run` events are handled here. Unsupported action classes
    deliberately fall back to the existing non-executing dispatch-attempt path.
    """

    classification = _as_dict(event.get("classification"))
    action_class = _safe_str(classification.get("action_class")).strip().lower()
    if action_class != "operation_run":
        return {"handled": False}

    event_id = _safe_str(event.get("event_id") or event.get("id")).strip()
    trigger = _as_dict(event.get("trigger"))
    operation_id = _safe_str(trigger.get("operation_id")).strip()
    if not operation_id:
        receipt = _blocked_receipt(
            event_id=event_id,
            actor=actor,
            reason=reason,
            attempt_count=attempt_count,
            ts=ts,
            gate="reactor_operation_run_requires_operation_id",
            outcome="operation_id_required",
            next_step="link_operation_id_before_reactor_dispatch",
        )
        return {
            "handled": True,
            "applied": False,
            "blocked": True,
            "status": "dispatch_blocked",
            "outcome": "operation_id_required",
            "stable_state": "operation_id_required",
            "next_step": "link_operation_id_before_reactor_dispatch",
            "receipt": receipt,
        }

    allowed, permission = _operation_run_permission(actor)
    if not allowed:
        receipt = _blocked_receipt(
            event_id=event_id,
            actor=actor,
            reason=reason,
            attempt_count=attempt_count,
            ts=ts,
            gate="operations_run_permission_gate",
            outcome="operation_run_permission_denied",
            next_step="configure_operations_run_scope_before_reactor_dispatch",
            operation_id=operation_id,
            permission=permission,
        )
        return {
            "handled": True,
            "applied": False,
            "blocked": True,
            "status": "dispatch_blocked",
            "outcome": "operation_run_permission_denied",
            "stable_state": "operation_run_permission_denied",
            "next_step": "configure_operations_run_scope_before_reactor_dispatch",
            "receipt": receipt,
        }

    posture_block = _posture_block("reactor operation dispatch")
    if posture_block:
        receipt = _blocked_receipt(
            event_id=event_id,
            actor=actor,
            reason=reason,
            attempt_count=attempt_count,
            ts=ts,
            gate="operator_posture",
            outcome="operator_posture_blocks_execution",
            next_step="switch_operator_posture_before_reactor_dispatch",
            operation_id=operation_id,
            message=posture_block,
        )
        return {
            "handled": True,
            "applied": False,
            "blocked": True,
            "status": "dispatch_blocked",
            "outcome": "operator_posture_blocks_execution",
            "stable_state": "operator_posture_blocks_execution",
            "next_step": "switch_operator_posture_before_reactor_dispatch",
            "receipt": receipt,
        }

    result = operations_runtime.run_operation(
        operation_id,
        worker_id=f"reactor.dispatch.{actor or 'system'}",
        advance_action="reactor_dispatch",
    )
    result_data = result if isinstance(result, dict) else {"ok": False, "error": "unexpected_operation_result"}
    identity = _operation_identity(result_data)
    ok = bool(result_data.get("ok"))
    operation_status = identity.get("operation_status") or "unknown"
    status = "dispatch_completed" if ok else "dispatch_failed"
    outcome = "operation_succeeded" if ok else f"operation_{operation_status or 'failed'}"
    stable_state = "dispatch_succeeded" if ok else "dispatch_failed"
    next_step = (
        "return_to_stable_state_with_operation_receipts" if ok else "review_failed_operation_before_retry_or_deadletter"
    )
    receipt = _redacted_dict(
        {
            "kind": "reactor.dispatch.execution.receipt",
            "receipt_id": f"{event_id}_dispatch_execution_{attempt_count}",
            "event_id": event_id,
            "status": "completed" if ok else "failed",
            "outcome": outcome,
            "route": "operation_run",
            "gate": "reactor_dispatch_engine",
            "stable_state": stable_state,
            "next_step": next_step,
            "actor": actor,
            "reason": reason,
            "operation_id": operation_id,
            "operation_status": operation_status,
            "trace_id": identity.get("trace_id"),
            "run_id": identity.get("run_id"),
            "memory_receipt_id": identity.get("memory_receipt_id"),
            "attempt_count": attempt_count,
            "ts": ts,
            "execution_started": True,
            "dispatch_applied": True,
            "verified": ok,
            "completion_claim_allowed": ok,
            "memory_write": identity.get("memory_write"),
            "governance": {
                "gate": "reactor_dispatch_engine",
                "execution_authority": True,
                "dispatch_authority": True,
                "approval_authority": False,
                "memory_write": bool(identity.get("memory_write")),
                "authority_source": "operations.run",
            },
        }
    )
    return {
        "handled": True,
        "applied": True,
        "blocked": False,
        "status": status,
        "outcome": outcome,
        "stable_state": stable_state,
        "next_step": next_step,
        "receipt": receipt,
        "operation_result": result_data,
    }
