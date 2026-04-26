from __future__ import annotations

from typing import Any

from francis.governance.redaction import redact_secret_text
import francis.missions.store as mission_store
from francis.operations import runtime as operations_runtime


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""


def _queue_run_error(errors: list[dict[str, object]]) -> str:
    if not errors:
        return ""
    first = errors[0]
    return _safe_str(first.get("error") or first.get("message")).strip() or "mission_queue_run_failed"


def _queue_run_error_record(mission_id: str, action: str, outcome: dict[str, object]) -> dict[str, object]:
    record: dict[str, object] = {
        "mission_id": mission_id,
        "error": _safe_str(outcome.get("error")).strip() or "advance_failed",
    }
    fields = {
        "action": action,
        "status": outcome.get("status"),
        "operation_id": outcome.get("operation_id"),
        "approval_id": outcome.get("approval_id"),
        "gate": outcome.get("gate"),
        "next_step": outcome.get("next_step"),
        "trace_id": outcome.get("trace_id"),
        "run_id": outcome.get("run_id"),
        "artifact_dir": outcome.get("artifact_dir"),
        "message": outcome.get("message"),
    }
    for key, value in fields.items():
        text = _safe_str(value).strip()
        if text:
            record[key] = text
    return record


def _redact_free_text(value: Any) -> str:
    return redact_secret_text(_safe_str(value).strip())


def _queue_run_request(actor: Any, note: Any, limit: int) -> dict[str, object]:
    return {
        "actor": _redact_free_text(actor) or "missions.runner",
        "note": _redact_free_text(note) or "mission_queue_run_once",
        "limit": max(1, int(limit)),
    }


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _operation_handoff(operation: Any) -> dict[str, object]:
    operation_record = _as_dict(operation)
    operation_meta = _as_dict(operation_record.get("meta"))
    operation_output = _as_dict(operation_record.get("output"))
    governance = _as_dict(operation_meta.get("governance"))
    approval_id = (
        _safe_str(operation_meta.get("approval_id")).strip() or _safe_str(operation_output.get("approval_id")).strip()
    )
    gate = _safe_str(governance.get("gate")).strip()
    next_step = _safe_str(governance.get("next_step")).strip()
    trace_id = (
        _safe_str(operation_record.get("trace_id")).strip()
        or _safe_str(operation_meta.get("trace_id")).strip()
        or _safe_str(operation_output.get("trace_id")).strip()
    )
    output_receipt = operation_output.get("receipt") if isinstance(operation_output.get("receipt"), dict) else {}
    output_sandbox = (
        operation_output.get("sandbox")
        if isinstance(operation_output.get("sandbox"), dict)
        else output_receipt.get("sandbox")
        if isinstance(output_receipt.get("sandbox"), dict)
        else {}
    )
    output_audit = output_receipt.get("audit_event") if isinstance(output_receipt.get("audit_event"), dict) else {}
    output_sandbox_audit = (
        output_sandbox.get("audit_event") if isinstance(output_sandbox.get("audit_event"), dict) else {}
    )
    trace_id = (
        trace_id
        or _safe_str(operation_output.get("traceId")).strip()
        or _safe_str(output_receipt.get("trace_id")).strip()
        or _safe_str(output_sandbox.get("trace_id")).strip()
        or _safe_str(output_audit.get("trace_id")).strip()
        or _safe_str(output_sandbox_audit.get("trace_id")).strip()
    )
    run_id = (
        _safe_str(operation_record.get("run_id")).strip()
        or _safe_str(operation_meta.get("run_id")).strip()
        or _safe_str(operation_output.get("run_id")).strip()
        or _safe_str(operation_output.get("runId")).strip()
        or _safe_str(output_receipt.get("run_id")).strip()
        or _safe_str(output_sandbox.get("run_id")).strip()
        or _safe_str(output_audit.get("run_id")).strip()
        or _safe_str(output_sandbox_audit.get("run_id")).strip()
    )
    artifact_dir = (
        _safe_str(operation_record.get("artifact_dir")).strip()
        or _safe_str(operation_meta.get("artifact_dir")).strip()
        or _safe_str(operation_output.get("artifact_dir")).strip()
        or _safe_str(operation_output.get("artifact_path")).strip()
        or _safe_str(output_receipt.get("artifact_dir")).strip()
        or _safe_str(output_receipt.get("artifact_path")).strip()
        or _safe_str(output_sandbox.get("artifact_dir")).strip()
        or _safe_str(output_sandbox.get("artifact_path")).strip()
        or _safe_str(output_audit.get("artifact_dir")).strip()
        or _safe_str(output_sandbox_audit.get("artifact_dir")).strip()
    )
    message = (
        _safe_str(operation_meta.get("result_message")).strip() or _safe_str(operation_output.get("message")).strip()
    )
    handoff: dict[str, object] = {}
    if approval_id:
        handoff["approval_id"] = approval_id
    if gate:
        handoff["gate"] = gate
    if next_step:
        handoff["next_step"] = next_step
    if trace_id:
        handoff["trace_id"] = trace_id
    if run_id:
        handoff["run_id"] = run_id
    if artifact_dir:
        handoff["artifact_dir"] = artifact_dir
    if message:
        handoff["operation_message"] = message
    return handoff


def _operation_receipt_identity(operation: Any) -> dict[str, str]:
    operation_record = _as_dict(operation)
    operation_meta = _as_dict(operation_record.get("meta"))
    return {
        "operation_name": _safe_str(operation_record.get("name")).strip(),
        "operation_plane": _safe_str(operation_meta.get("orb_plane")).strip(),
    }


def advance_mission(
    mission_id: str,
    *,
    actor: str = "missions.runner",
    note: str = "mission_advance",
    worker_id: str = "missions.runner",
    record_operator_receipt: bool = True,
) -> dict[str, object]:
    record, _, tick_err = mission_store.tick_mission(
        mission_id,
        actor=actor,
        note="advance_preflight",
    )
    if not record and tick_err:
        return {"ok": False, "applied": False, "error": tick_err}

    record, queue_item, queue_err = mission_store.mission_queue_item(mission_id)
    if not record or not queue_item:
        return {"ok": False, "applied": False, "error": queue_err or "not_found"}

    action = _safe_str(queue_item.get("recommended_action")).strip() or "review_mission"
    action_target_id = _safe_str(queue_item.get("action_target_id")).strip()
    operator_hint = _safe_str(queue_item.get("operator_hint")).strip()

    if action == "create_first_operation":
        created = operations_runtime.create_operation(
            action="plan.create",
            reason=f"mission.advance:{mission_id}",
            actor=actor,
            mission_id=mission_id,
            objective=record.objective,
            input={
                "goal": record.objective,
                "constraints": {
                    "mission_id": mission_id,
                    "summary": record.summary,
                    "next_step": record.next_step,
                },
            },
        )
        operation_id = _safe_str(created.get("operation_id")).strip()
        operation_status = _safe_str(created.get("status")).strip()
        message = _safe_str(created.get("message")).strip() or "operation_created"
        operation_identity = _operation_receipt_identity(created.get("operation"))
        mission_store.tick_mission(mission_id, actor=actor, note="advance_post_create")
        updated_record, receipt_err = mission_store.record_advance_receipt(
            mission_id,
            action=action,
            outcome="applied" if bool(created.get("ok")) else "error",
            actor=actor,
            note=note,
            operation_id=operation_id,
            **operation_identity,
            operation_status=operation_status,
            message=message,
            applied=bool(created.get("ok")),
        )
        if receipt_err:
            return {"ok": False, "applied": False, "error": receipt_err}
        return {
            "ok": bool(created.get("ok")),
            "applied": bool(created.get("ok")),
            "action": action,
            "mission_record": updated_record,
            "operation": created.get("operation"),
            "operation_id": operation_id or None,
            "status": operation_status or updated_record.status.value,
            "message": message,
            **_operation_handoff(created.get("operation")),
        }

    if action == "run_linked_operation" and action_target_id:
        run_result = operations_runtime.run_operation(
            action_target_id,
            worker_id=worker_id,
        )
        mission_store.tick_mission(mission_id, actor=actor, note="advance_post_run")
        operation_status = _safe_str(run_result.get("status")).strip()
        message = _safe_str(run_result.get("message")).strip() or "operation_run"
        operation_identity = _operation_receipt_identity(run_result.get("operation"))
        updated_record, receipt_err = mission_store.record_advance_receipt(
            mission_id,
            action=action,
            outcome=operation_status or ("applied" if bool(run_result.get("ok")) else "error"),
            actor=actor,
            note=note,
            operation_id=action_target_id,
            **operation_identity,
            operation_status=operation_status,
            message=message,
            applied=bool(run_result.get("ok")),
        )
        if receipt_err:
            return {"ok": False, "applied": False, "error": receipt_err}
        response: dict[str, object] = {
            "ok": bool(run_result.get("ok")),
            "applied": bool(run_result.get("ok")),
            "action": action,
            "mission_record": updated_record,
            "operation": run_result.get("operation"),
            "operation_id": action_target_id,
            "status": operation_status or updated_record.status.value,
            "message": message,
            **_operation_handoff(run_result.get("operation")),
        }
        memory_receipt = run_result.get("memory_receipt")
        if isinstance(memory_receipt, dict):
            response["memory_receipt"] = memory_receipt
        return response

    if record_operator_receipt:
        updated_record, receipt_err = mission_store.record_advance_receipt(
            mission_id,
            action=action,
            outcome="requires_operator",
            actor=actor,
            note=note,
            operation_id=action_target_id,
            operation_status=_safe_str(queue_item.get("last_task_status")).strip(),
            message=operator_hint or "Mission cannot be advanced automatically from the current queue state.",
            applied=False,
        )
        if receipt_err:
            return {"ok": False, "applied": False, "error": receipt_err}
        if action in mission_store.RECOVERY_REVIEW_ACTIONS:
            recovery_record, recovery_err = mission_store.record_recovery_review_receipt(
                mission_id,
                action=action,
                outcome="requires_operator",
                actor=actor,
                note=note,
                target_id=action_target_id,
                message=operator_hint or "Mission requires operator intervention.",
                source_status=record.status.value,
            )
            if recovery_err:
                return {"ok": False, "applied": False, "error": recovery_err}
            if recovery_record is not None:
                updated_record = recovery_record
        return {
            "ok": True,
            "applied": False,
            "action": action,
            "mission_record": updated_record,
            "operation_id": action_target_id or None,
            "status": updated_record.status.value,
            "message": operator_hint or "Mission requires operator intervention.",
        }

    return {
        "ok": True,
        "applied": False,
        "action": action,
        "mission_record": record,
        "operation_id": action_target_id or None,
        "status": record.status.value,
        "message": operator_hint or "Mission requires operator intervention.",
    }


def run_queue_once(
    *,
    limit: int = 50,
    actor: str = "missions.runner",
    note: str = "mission_queue_run_once",
) -> dict[str, object]:
    safe_limit = max(1, int(limit))
    records, tick_applied, errors = mission_store.tick_all_missions(
        limit=max(safe_limit, 200),
        actor=actor,
        note=note,
    )
    initial_items = mission_store.mission_queue_items(limit=safe_limit, include_terminal=False)

    results: list[dict[str, object]] = []
    advanced = 0
    for item in initial_items:
        mission_id = _safe_str(item.get("id")).strip()
        if not mission_id:
            continue
        action = _safe_str(item.get("recommended_action")).strip() or "review_mission"
        if action not in mission_store.AUTO_ADVANCE_ACTIONS:
            results.append(
                {
                    "mission_id": mission_id,
                    "ok": True,
                    "applied": False,
                    "action": action,
                    "status": _safe_str(item.get("status")).strip(),
                    "operation_id": _safe_str(item.get("action_target_id")).strip() or None,
                    "message": _safe_str(item.get("operator_hint")).strip()
                    or "Mission requires operator intervention.",
                }
            )
            continue

        outcome = advance_mission(
            mission_id,
            actor=actor,
            note=note,
            worker_id=actor,
            record_operator_receipt=False,
        )
        result: dict[str, object] = {
            "mission_id": mission_id,
            "ok": bool(outcome.get("ok")),
            "applied": bool(outcome.get("applied")),
            "action": _safe_str(outcome.get("action")).strip() or action,
            "status": _safe_str(outcome.get("status")).strip(),
            "operation_id": _safe_str(outcome.get("operation_id")).strip() or None,
            "message": _safe_str(outcome.get("message")).strip(),
            "approval_id": _safe_str(outcome.get("approval_id")).strip() or None,
            "gate": _safe_str(outcome.get("gate")).strip() or None,
            "next_step": _safe_str(outcome.get("next_step")).strip() or None,
            "trace_id": _safe_str(outcome.get("trace_id")).strip() or None,
            "run_id": _safe_str(outcome.get("run_id")).strip() or None,
            "artifact_dir": _safe_str(outcome.get("artifact_dir")).strip() or None,
        }
        operation = outcome.get("operation")
        if isinstance(operation, dict):
            result["operation"] = operation
        memory_receipt = outcome.get("memory_receipt")
        if isinstance(memory_receipt, dict):
            result["memory_receipt"] = memory_receipt
        results.append(result)
        if bool(outcome.get("applied")):
            advanced += 1
        elif outcome.get("ok") is False:
            errors.append(_queue_run_error_record(mission_id, action, outcome))

    queue_items = mission_store.mission_queue_items(limit=safe_limit, include_terminal=False)
    failed_items = mission_store.failed_queue_items(limit=min(safe_limit, 20))
    deadletter_items = mission_store.deadletter_queue_items(limit=min(safe_limit, 20))
    counts = {
        "queued": 0,
        "active": 0,
        "blocked": 0,
        "failed": len(failed_items),
        "deadlettered": len(deadletter_items),
    }
    for item in queue_items:
        status = _safe_str(item.get("status")).strip().lower()
        if status in counts:
            counts[status] += 1

    status = "failed" if errors else "succeeded"
    response: dict[str, object] = {
        "ok": not errors,
        "items": queue_items,
        "failed": failed_items,
        "deadletter": deadletter_items,
        "total": len(queue_items),
        "applied": tick_applied + advanced,
        "advanced": advanced,
        "results": results,
        "processed": len(records),
        "errors": errors,
        "counts": counts,
        "status": status,
        "request": _queue_run_request(actor, note, safe_limit),
    }
    if errors:
        response["error"] = _queue_run_error(errors)
    return response
