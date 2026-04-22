from __future__ import annotations

from typing import Any

import francis.missions.store as mission_store
from francis.operations import runtime as operations_runtime


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""


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
    if message:
        handoff["operation_message"] = message
    return handoff


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
        mission_store.tick_mission(mission_id, actor=actor, note="advance_post_create")
        updated_record, receipt_err = mission_store.record_advance_receipt(
            mission_id,
            action=action,
            outcome="applied" if bool(created.get("ok")) else "error",
            actor=actor,
            note=note,
            operation_id=operation_id,
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
        updated_record, receipt_err = mission_store.record_advance_receipt(
            mission_id,
            action=action,
            outcome=operation_status or ("applied" if bool(run_result.get("ok")) else "error"),
            actor=actor,
            note=note,
            operation_id=action_target_id,
            operation_status=operation_status,
            message=message,
            applied=bool(run_result.get("ok")),
        )
        if receipt_err:
            return {"ok": False, "applied": False, "error": receipt_err}
        return {
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
        results.append(
            {
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
            }
        )
        if bool(outcome.get("applied")):
            advanced += 1
        elif outcome.get("ok") is False:
            errors.append(
                {"mission_id": mission_id, "error": _safe_str(outcome.get("error")).strip() or "advance_failed"}
            )

    queue_items = mission_store.mission_queue_items(limit=safe_limit, include_terminal=False)
    deadletter_items = mission_store.deadletter_queue_items(limit=min(safe_limit, 20))
    counts = {
        "queued": 0,
        "active": 0,
        "blocked": 0,
        "failed": 0,
        "deadlettered": len(deadletter_items),
    }
    for item in queue_items:
        status = _safe_str(item.get("status")).strip().lower()
        if status in counts:
            counts[status] += 1

    return {
        "ok": not errors,
        "items": queue_items,
        "deadletter": deadletter_items,
        "total": len(queue_items),
        "applied": tick_applied + advanced,
        "advanced": advanced,
        "results": results,
        "processed": len(records),
        "errors": errors,
        "counts": counts,
    }
