from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from francis.missions import store as mission_store
from francis.missions.store import MissionCreateRequest

router = APIRouter()
_AUTO_ADVANCE_ACTIONS = {"create_first_operation", "run_linked_operation"}


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""


def _serialize_mission(record: mission_store.MissionRecord | None) -> dict[str, Any]:
    if record is None:
        return {}
    return {
        "id": record.mission_id,
        "status": record.status.value,
        "objective": record.objective,
        "summary": record.summary,
        "next_step": record.next_step,
        "requester_id": record.requester_id,
        "priority": record.priority,
        "risk_tier": record.risk_tier,
        "linked_task_ids": list(record.linked_task_ids),
        "linked_task_count": len(record.linked_task_ids),
        "deadletter_reason": record.deadletter_reason,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
        "meta": dict(record.meta),
    }


class MissionCreateIn(BaseModel):
    objective: str
    summary: str = ""
    next_step: str = ""
    requester_id: str = "api"
    priority: int = 5
    risk_tier: str = "medium"
    status: str = "queued"
    linked_task_ids: list[str] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)


class MissionPatchIn(BaseModel):
    status: str | None = None
    summary: str | None = None
    next_step: str | None = None
    add_task_ids: list[str] = Field(default_factory=list)
    remove_task_ids: list[str] = Field(default_factory=list)
    deadletter_reason: str | None = None
    actor: str | None = None
    note: str | None = None
    meta: dict[str, Any] | None = None


class MissionTickIn(BaseModel):
    actor: str | None = None
    note: str | None = None


class MissionTickManyIn(MissionTickIn):
    limit: int = 200


class MissionRunOnceIn(MissionTickIn):
    limit: int = 50


class MissionAdvanceIn(MissionTickIn):
    worker_id: str | None = None


class MissionDeadletterIn(BaseModel):
    reason: str = "manual_deadletter"
    actor: str | None = None
    note: str | None = None


@router.post("/create")
def create_mission(payload: MissionCreateIn) -> dict[str, object]:
    try:
        record, err = mission_store.create_mission(
            MissionCreateRequest(
                objective=payload.objective,
                summary=payload.summary,
                next_step=payload.next_step,
                requester_id=payload.requester_id,
                priority=max(1, min(int(payload.priority), 9)),
                risk_tier=payload.risk_tier,
                status=payload.status.strip().lower(),
                linked_task_ids=payload.linked_task_ids,
                meta=dict(payload.meta or {}),
            )
        )
        if not record:
            return {"ok": False, "error": err or "create_failed"}
        return {
            "ok": True,
            "mission_id": record.mission_id,
            "status": record.status.value,
            "mission": _serialize_mission(record),
            "message": "created",
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.get("/list")
def list_missions(limit: int = 200, status: str | None = None) -> dict[str, object]:
    try:
        safe_limit = max(1, min(int(limit), 5000))
        records = mission_store.list_missions(limit=safe_limit, status=status.strip().lower() if status else None)
        return {"items": [_serialize_mission(record) for record in records], "total": len(records), "limit": safe_limit}
    except Exception as exc:
        return {"items": [], "total": 0, "limit": 0, "error": str(exc)}


@router.get("/queue")
def mission_queue(limit: int = 50, include_terminal: bool = False) -> dict[str, object]:
    try:
        safe_limit = max(1, min(int(limit), 5000))
        items = mission_store.mission_queue_items(limit=safe_limit, include_terminal=include_terminal)
        deadletter = mission_store.deadletter_queue_items(limit=min(safe_limit, 20))
        return {
            "ok": True,
            "items": items,
            "total": len(items),
            "deadletter": deadletter,
        }
    except Exception as exc:
        return {"ok": False, "items": [], "total": 0, "deadletter": [], "error": str(exc)}


@router.post("/tick")
def tick_missions(payload: MissionTickManyIn) -> dict[str, object]:
    try:
        safe_limit = max(1, min(int(payload.limit), 5000))
        records, applied, errors = mission_store.tick_all_missions(
            limit=safe_limit,
            actor=_safe_str(payload.actor).strip() or None,
            note=_safe_str(payload.note).strip() or None,
        )
        return {
            "ok": not errors,
            "items": [_serialize_mission(record) for record in records],
            "total": len(records),
            "applied": applied,
            "errors": errors,
        }
    except Exception as exc:
        return {"ok": False, "items": [], "total": 0, "applied": 0, "errors": [{"error": str(exc)}]}


@router.post("/run_once")
def run_queue_once(payload: MissionRunOnceIn) -> dict[str, object]:
    try:
        safe_limit = max(1, min(int(payload.limit), 5000))
        actor = _safe_str(payload.actor).strip() or "missions.runner"
        note = _safe_str(payload.note).strip() or "mission_queue_run_once"

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
            if action not in _AUTO_ADVANCE_ACTIONS:
                results.append(
                    {
                        "mission_id": mission_id,
                        "ok": True,
                        "applied": False,
                        "action": action,
                        "status": _safe_str(item.get("status")).strip(),
                        "operation_id": _safe_str(item.get("action_target_id")).strip() or None,
                        "message": _safe_str(item.get("operator_hint")).strip() or "Mission requires operator intervention.",
                    }
                )
                continue

            outcome = _advance_mission_impl(
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
                }
            )
            if bool(outcome.get("applied")):
                advanced += 1
            elif outcome.get("ok") is False:
                errors.append({"mission_id": mission_id, "error": _safe_str(outcome.get("error")).strip() or "advance_failed"})

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
    except Exception as exc:
        return {
            "ok": False,
            "items": [],
            "deadletter": [],
            "total": 0,
            "applied": 0,
            "advanced": 0,
            "results": [],
            "processed": 0,
            "errors": [{"error": str(exc)}],
            "counts": {},
        }


@router.get("/{mission_id}")
def get_mission(mission_id: str) -> dict[str, object]:
    try:
        record, err = mission_store.read_mission(mission_id)
        if not record:
            return {"ok": False, "error": err or "not_found"}
        return {
            "ok": True,
            "mission": _serialize_mission(record),
            "history": mission_store.read_history(mission_id),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.patch("/{mission_id}")
def patch_mission(mission_id: str, payload: MissionPatchIn) -> dict[str, object]:
    try:
        record, err = mission_store.update_mission(
            mission_id,
            status=payload.status.strip().lower() if payload.status else None,
            summary=payload.summary,
            next_step=payload.next_step,
            add_task_ids=payload.add_task_ids,
            remove_task_ids=payload.remove_task_ids,
            deadletter_reason=payload.deadletter_reason,
            meta_updates=dict(payload.meta or {}) if payload.meta is not None else None,
            actor=_safe_str(payload.actor).strip() or None,
            note=_safe_str(payload.note).strip() or None,
        )
        if not record:
            return {"ok": False, "error": err or "update_failed"}
        return {
            "ok": True,
            "status": record.status.value,
            "mission": _serialize_mission(record),
            "history": mission_store.read_history(mission_id),
            "message": "updated",
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.post("/{mission_id}/tick")
def tick_mission(mission_id: str, payload: MissionTickIn) -> dict[str, object]:
    try:
        record, applied, err = mission_store.tick_mission(
            mission_id,
            actor=_safe_str(payload.actor).strip() or None,
            note=_safe_str(payload.note).strip() or None,
        )
        if not record:
            return {"ok": False, "applied": False, "error": err or "tick_failed"}
        return {
            "ok": True,
            "applied": applied,
            "mission": _serialize_mission(record),
            "history": mission_store.read_history(mission_id),
            "message": "ticked" if applied else "no_change",
        }
    except Exception as exc:
        return {"ok": False, "applied": False, "error": str(exc)}


@router.post("/{mission_id}/deadletter")
def deadletter_mission(mission_id: str, payload: MissionDeadletterIn) -> dict[str, object]:
    try:
        record, err = mission_store.deadletter_mission(
            mission_id,
            payload.reason,
            actor=_safe_str(payload.actor).strip() or None,
            note=_safe_str(payload.note).strip() or None,
        )
        if not record:
            return {"ok": False, "error": err or "deadletter_failed"}
        return {
            "ok": True,
            "status": record.status.value,
            "mission": _serialize_mission(record),
            "history": mission_store.read_history(mission_id),
            "message": "deadlettered",
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _advance_mission_impl(
    mission_id: str,
    *,
    actor: str,
    note: str,
    worker_id: str,
    record_operator_receipt: bool,
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
        from francis.api.routes import operations as operations_routes

        created = operations_routes.create_operation(
            operations_routes.OperationCreateIn(
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
            "mission": _serialize_mission(updated_record),
            "operation": created.get("operation"),
            "operation_id": operation_id or None,
            "status": operation_status or updated_record.status.value,
            "message": message,
        }

    if action == "run_linked_operation" and action_target_id:
        from francis.api.routes import operations as operations_routes

        run_result = operations_routes.run_operation(
            action_target_id,
            operations_routes.OperationRunIn(worker_id=worker_id),
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
            "mission": _serialize_mission(updated_record),
            "operation": run_result.get("operation"),
            "operation_id": action_target_id,
            "status": operation_status or updated_record.status.value,
            "message": message,
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
            "mission": _serialize_mission(updated_record),
            "operation_id": action_target_id or None,
            "status": updated_record.status.value,
            "message": operator_hint or "Mission requires operator intervention.",
        }

    return {
        "ok": True,
        "applied": False,
        "action": action,
        "mission": _serialize_mission(record),
        "operation_id": action_target_id or None,
        "status": record.status.value,
        "message": operator_hint or "Mission requires operator intervention.",
    }


@router.post("/{mission_id}/advance")
def advance_mission(mission_id: str, payload: MissionAdvanceIn) -> dict[str, object]:
    try:
        actor = _safe_str(payload.actor).strip() or "missions.runner"
        note = _safe_str(payload.note).strip() or "mission_advance"
        worker_id = _safe_str(payload.worker_id).strip() or actor
        return _advance_mission_impl(
            mission_id,
            actor=actor,
            note=note,
            worker_id=worker_id,
            record_operator_receipt=True,
        )
    except Exception as exc:
        return {"ok": False, "applied": False, "error": str(exc)}
