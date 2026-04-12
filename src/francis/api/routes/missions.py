from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from francis.missions import runtime as mission_runtime
from francis.missions import store as mission_store
from francis.missions.store import MissionCreateRequest

router = APIRouter()


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
        return mission_runtime.run_queue_once(limit=safe_limit, actor=actor, note=note)
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


@router.post("/{mission_id}/advance")
def advance_mission(mission_id: str, payload: MissionAdvanceIn) -> dict[str, object]:
    try:
        actor = _safe_str(payload.actor).strip() or "missions.runner"
        note = _safe_str(payload.note).strip() or "mission_advance"
        worker_id = _safe_str(payload.worker_id).strip() or actor
        result = mission_runtime.advance_mission(
            mission_id,
            actor=actor,
            note=note,
            worker_id=worker_id,
            record_operator_receipt=True,
        )
        mission_record = result.pop("mission_record", None)
        if isinstance(mission_record, mission_store.MissionRecord):
            result["mission"] = _serialize_mission(mission_record)
        return result
    except Exception as exc:
        return {"ok": False, "applied": False, "error": str(exc)}
