from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from francis.api.routes._operator_posture import posture_write_guard
from francis.missions import runtime as mission_runtime
from francis.missions import store as mission_store
from francis.missions.store import MissionCreateRequest
from francis.operations import runtime as operations_runtime

router = APIRouter()


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""


def _mission_write_posture_guard(action_label: str) -> str:
    return posture_write_guard(action_label)


def _stage_timestamp(value: Any) -> str:
    if isinstance(value, (int, float)):
        try:
            from datetime import datetime, timezone

            return datetime.fromtimestamp(float(value), tz=timezone.utc).isoformat().replace("+00:00", "Z")
        except Exception:
            return ""
    text = _safe_str(value).strip()
    return text


def _serialize_mission(record: mission_store.MissionRecord | None) -> dict[str, Any]:
    if record is None:
        return {}
    meta = dict(record.meta) if isinstance(record.meta, dict) else {}
    return {
        "id": record.mission_id,
        "status": record.status.value,
        "objective": record.objective,
        "summary": record.summary,
        "next_step": record.next_step,
        "requester_id": record.requester_id,
        "owner_id": record.owner_id,
        "priority": record.priority,
        "risk_tier": record.risk_tier,
        "dependency_ids": list(record.dependency_ids),
        "dependency_count": len(record.dependency_ids),
        "escalation_path": record.escalation_path,
        "linked_task_ids": list(record.linked_task_ids),
        "linked_task_count": len(record.linked_task_ids),
        "deadletter_reason": record.deadletter_reason,
        "last_task_id": _safe_str(meta.get("last_task_id")).strip(),
        "last_task_status": _safe_str(meta.get("last_task_status")).strip(),
        "last_task_result_status": _safe_str(meta.get("last_task_result_status")).strip(),
        "last_task_reason": _safe_str(meta.get("last_task_reason")).strip(),
        "last_task_gate": _safe_str(meta.get("last_task_gate")).strip(),
        "last_task_next_step": _safe_str(meta.get("last_task_next_step")).strip(),
        "last_advance_operation_id": _safe_str(meta.get("last_advance_operation_id")).strip(),
        "created_at": record.created_at,
        "updated_at": record.updated_at,
        "meta": meta,
    }


def _linked_operation_details(
    record: mission_store.MissionRecord | None, *, log_limit: int = 50
) -> list[dict[str, Any]]:
    if record is None:
        return []
    items: list[dict[str, Any]] = []
    for operation_id in record.linked_task_ids:
        detail = operations_runtime.get_operation_detail(operation_id, include_logs=True, log_limit=log_limit)
        if bool(detail.get("ok")):
            items.append(detail)
            continue
        items.append(
            {
                "ok": False,
                "operation": {"id": operation_id},
                "logs": [],
                "error": _safe_str(detail.get("error")).strip() or "not_found",
            }
        )
    return items


def _mission_run_ledger(
    mission_id: str, linked_operations: list[dict[str, Any]], *, limit: int = 200
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for detail in linked_operations:
        operation = detail.get("operation") if isinstance(detail.get("operation"), dict) else {}
        operation_id = _safe_str(operation.get("id")).strip()
        operation_name = _safe_str(operation.get("name")).strip()
        operation_status = _safe_str(operation.get("status")).strip()
        logs = detail.get("logs") if isinstance(detail.get("logs"), list) else []
        for log in logs:
            if not isinstance(log, dict):
                continue
            entry = dict(log)
            entry["mission_id"] = mission_id
            entry["operation_id"] = operation_id or None
            entry["operation_name"] = operation_name or None
            entry["operation_status"] = operation_status or None
            entries.append(entry)
    entries.sort(
        key=lambda item: (
            int(item.get("ts") or 0),
            _safe_str(item.get("id")),
        ),
        reverse=True,
    )
    return entries[: max(0, int(limit))]


def _operation_status(detail: dict[str, Any]) -> str:
    operation = detail.get("operation") if isinstance(detail.get("operation"), dict) else {}
    return _safe_str(operation.get("status")).strip().lower()


def _operation_gate(detail: dict[str, Any]) -> str:
    operation = detail.get("operation") if isinstance(detail.get("operation"), dict) else {}
    meta = operation.get("meta") if isinstance(operation.get("meta"), dict) else {}
    governance = meta.get("governance") if isinstance(meta.get("governance"), dict) else {}
    output = operation.get("output") if isinstance(operation.get("output"), dict) else {}
    output_governance = output.get("governance") if isinstance(output.get("governance"), dict) else {}
    return _safe_str(governance.get("gate")).strip() or _safe_str(output_governance.get("gate")).strip()


def _operation_approval_id(detail: dict[str, Any]) -> str:
    operation = detail.get("operation") if isinstance(detail.get("operation"), dict) else {}
    meta = operation.get("meta") if isinstance(operation.get("meta"), dict) else {}
    output = operation.get("output") if isinstance(operation.get("output"), dict) else {}
    return _safe_str(meta.get("approval_id")).strip() or _safe_str(output.get("approval_id")).strip()


def _operation_trace_id(detail: dict[str, Any]) -> str:
    operation = detail.get("operation") if isinstance(detail.get("operation"), dict) else {}
    meta = operation.get("meta") if isinstance(operation.get("meta"), dict) else {}
    return _safe_str(operation.get("trace_id")).strip() or _safe_str(meta.get("trace_id")).strip()


def _operation_next_step(detail: dict[str, Any]) -> str:
    operation = detail.get("operation") if isinstance(detail.get("operation"), dict) else {}
    meta = operation.get("meta") if isinstance(operation.get("meta"), dict) else {}
    governance = meta.get("governance") if isinstance(meta.get("governance"), dict) else {}
    output = operation.get("output") if isinstance(operation.get("output"), dict) else {}
    output_governance = output.get("governance") if isinstance(output.get("governance"), dict) else {}
    return _safe_str(governance.get("next_step")).strip() or _safe_str(output_governance.get("next_step")).strip()


def _operation_id(detail: dict[str, Any]) -> str:
    operation = detail.get("operation") if isinstance(detail.get("operation"), dict) else {}
    return _safe_str(operation.get("id")).strip()


def _operation_sort_ts(detail: dict[str, Any]) -> float:
    operation = detail.get("operation") if isinstance(detail.get("operation"), dict) else {}
    try:
        return float(operation.get("ts") or 0)
    except Exception:
        return 0.0


def _current_operation_detail(
    record: mission_store.MissionRecord,
    linked_operations: list[dict[str, Any]],
) -> dict[str, Any]:
    if not linked_operations:
        return {}

    meta = dict(record.meta) if isinstance(record.meta, dict) else {}
    last_task_id = _safe_str(meta.get("last_task_id")).strip()
    if last_task_id:
        for detail in linked_operations:
            if _operation_id(detail) == last_task_id:
                return detail

    ranked = [(_operation_sort_ts(detail), index, detail) for index, detail in enumerate(linked_operations)]
    ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return ranked[0][2]


def _loop_stage(
    status: str,
    detail: str,
    *,
    count: int | None = None,
    gate: str = "",
    approval_id: str = "",
    operation_id: str = "",
    trace_id: str = "",
    latest_event: str = "",
    latest_ts: str = "",
    next_step: str = "",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status": status,
        "detail": detail,
    }
    if count is not None:
        payload["count"] = count
    if gate:
        payload["gate"] = gate
    if approval_id:
        payload["approval_id"] = approval_id
    if operation_id:
        payload["operation_id"] = operation_id
    if trace_id:
        payload["trace_id"] = trace_id
    if latest_event:
        payload["latest_event"] = latest_event
    if latest_ts:
        payload["latest_ts"] = latest_ts
    if next_step:
        payload["next_step"] = next_step
    return payload


def _loop_handoff(
    stage: str,
    action: str,
    detail: str,
    *,
    gate: str = "",
    approval_id: str = "",
    operation_id: str = "",
    trace_id: str = "",
    latest_event: str = "",
    latest_ts: str = "",
    next_step: str = "",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "stage": stage,
        "action": action,
        "detail": detail,
    }
    if gate:
        payload["gate"] = gate
    if approval_id:
        payload["approval_id"] = approval_id
    if operation_id:
        payload["operation_id"] = operation_id
    if trace_id:
        payload["trace_id"] = trace_id
    if latest_event:
        payload["latest_event"] = latest_event
    if latest_ts:
        payload["latest_ts"] = latest_ts
    if next_step:
        payload["next_step"] = next_step
    return payload


def _mission_loop_state(
    record: mission_store.MissionRecord,
    linked_operations: list[dict[str, Any]],
    run_ledger: list[dict[str, Any]],
    history: list[dict[str, Any]],
) -> dict[str, Any]:
    latest_detail = _current_operation_detail(record, linked_operations)
    latest_operation = latest_detail.get("operation") if isinstance(latest_detail.get("operation"), dict) else {}
    latest_operation_id = _safe_str(latest_operation.get("id")).strip()
    latest_operation_status = _operation_status(latest_detail)
    latest_gate = _operation_gate(latest_detail)
    latest_approval_id = _operation_approval_id(latest_detail)
    latest_trace_id = _operation_trace_id(latest_detail)
    latest_next_step = _operation_next_step(latest_detail)

    if linked_operations:
        plan_stage = _loop_stage(
            "ready",
            f"{len(linked_operations)} linked operation(s) declared for this mission.",
            count=len(linked_operations),
            operation_id=latest_operation_id,
        )
    else:
        plan_stage = _loop_stage(
            "pending",
            "No linked operation has been declared for this mission yet.",
            count=0,
        )

    if latest_gate or latest_approval_id:
        gate_status = "needs_approval" if latest_gate == "approvals_gate" or latest_approval_id else "blocked"
        gate_bits: list[str] = []
        if latest_gate:
            gate_bits.append(f"gate {latest_gate}")
        if latest_approval_id:
            gate_bits.append(f"approval {latest_approval_id}")
        gate_stage = _loop_stage(
            gate_status,
            "Governance is actively holding the current linked operation through " + ", ".join(gate_bits) + ".",
            gate=latest_gate,
            approval_id=latest_approval_id,
            operation_id=latest_operation_id,
            next_step=latest_next_step,
        )
    elif linked_operations:
        gate_stage = _loop_stage(
            "clear",
            "No active governance gate is recorded for the current linked operation.",
            operation_id=latest_operation_id,
        )
    else:
        gate_stage = _loop_stage(
            "pending",
            "Governance has nothing to evaluate until a linked operation exists.",
        )

    execute_status = latest_operation_status or record.status.value
    if execute_status == "completed":
        execute_status = "succeeded"
    elif execute_status == "active":
        execute_status = "running"
    elif execute_status == "queued":
        execute_status = "pending"
    elif execute_status == "cancelled":
        execute_status = "canceled"
    if linked_operations:
        execute_stage = _loop_stage(
            execute_status or "unknown",
            f"The latest linked operation is currently {execute_status or 'unknown'}.",
            operation_id=latest_operation_id,
            gate=latest_gate,
            approval_id=latest_approval_id,
            next_step=latest_next_step,
        )
    else:
        execute_stage = _loop_stage(
            "pending",
            "Execution has not started because no linked operation exists yet.",
        )

    trace_count = sum(1 for detail in linked_operations if _operation_trace_id(detail))
    audit_count = sum(len(detail.get("logs")) for detail in linked_operations if isinstance(detail.get("logs"), list))
    ledger_count = len(run_ledger)
    latest_trace_receipt = run_ledger[0] if run_ledger else {}
    latest_trace_event = _safe_str(latest_trace_receipt.get("name")).strip()
    latest_trace_ts = _stage_timestamp(latest_trace_receipt.get("ts"))
    if trace_count or audit_count or ledger_count:
        trace_parts: list[str] = []
        if trace_count:
            trace_parts.append(f"{trace_count} trace id(s)")
        if ledger_count:
            trace_parts.append(f"{ledger_count} run-ledger receipt(s)")
        if audit_count:
            trace_parts.append(f"{audit_count} audit event(s)")
        trace_stage = _loop_stage(
            "recorded",
            "Trace receipts are available through " + ", ".join(trace_parts) + ".",
            count=trace_count + ledger_count + audit_count,
            operation_id=latest_operation_id,
            trace_id=latest_trace_id,
            latest_event=latest_trace_event,
            latest_ts=latest_trace_ts,
        )
    else:
        trace_stage = _loop_stage(
            "pending",
            "No trace receipts have been recorded for this mission yet.",
            count=0,
            operation_id=latest_operation_id,
        )

    history_count = len(history)
    latest_history_event = ""
    latest_history_ts = ""
    if history:
        latest_history = history[-1] if isinstance(history[-1], dict) else {}
        latest_history_event = _safe_str(latest_history.get("event")).strip()
        latest_history_ts = _stage_timestamp(latest_history.get("ts"))
    if history_count:
        memory_stage = _loop_stage(
            "recorded",
            f"{history_count} mission continuity receipt(s) are stored in local history.",
            count=history_count,
            latest_event=latest_history_event,
            latest_ts=latest_history_ts,
        )
    else:
        memory_stage = _loop_stage(
            "pending",
            "No mission continuity receipts have been stored yet.",
            count=0,
        )

    active_stage = "memory"
    summary = "Mission continuity receipts are available for review."
    handoff = _loop_handoff(
        "memory",
        "review_continuity",
        "Trace and mission continuity receipts are recorded; review local history before declaring new work.",
        operation_id=latest_operation_id,
        trace_id=latest_trace_id,
        latest_event=latest_history_event,
        latest_ts=latest_history_ts,
        next_step=record.next_step,
    )
    record_status = record.status.value
    if record_status == "deadlettered":
        active_stage = "deadletter"
        summary = "The mission is deadlettered and should be reviewed before any retry or replacement work."
        handoff = _loop_handoff(
            "deadletter",
            "review_deadletter",
            record.deadletter_reason or "Review why this mission was deadlettered before declaring follow-up work.",
            operation_id=latest_operation_id,
            trace_id=latest_trace_id,
            latest_event=latest_history_event,
            latest_ts=latest_history_ts,
            next_step=record.deadletter_reason or record.next_step,
        )
    elif record_status == "failed":
        active_stage = "deadletter"
        summary = "The mission failed and needs an explicit retry or deadletter decision."
        handoff = _loop_handoff(
            "deadletter",
            "retry_or_deadletter",
            "Review the failed mission evidence, then retry bounded work or deadletter it explicitly.",
            operation_id=latest_operation_id,
            trace_id=latest_trace_id,
            latest_event=latest_history_event,
            latest_ts=latest_history_ts,
            next_step=record.next_step,
        )
    elif latest_gate or latest_approval_id:
        active_stage = "gate"
        summary = "The mission is waiting on a governance decision before it can continue."
        handoff = _loop_handoff(
            "gate",
            latest_next_step or ("review_pending_approval" if latest_approval_id else "resolve_governance_gate"),
            "Review the active governance hold before the linked operation can continue.",
            gate=latest_gate,
            approval_id=latest_approval_id,
            operation_id=latest_operation_id,
            next_step=latest_next_step,
        )
    elif not linked_operations:
        active_stage = "plan"
        summary = "The mission still needs its first linked operation."
        handoff = _loop_handoff(
            "plan",
            "link_operation",
            "Declare or link a bounded operation before execution, trace, or memory can progress.",
            next_step=record.next_step,
        )
    elif execute_status in {"running", "pending", "queued"}:
        active_stage = "execute"
        summary = "The mission is currently in its bounded execution phase."
        action = "wait_for_execution" if execute_status == "running" else "run_linked_operation"
        handoff = _loop_handoff(
            "execute",
            action,
            "Advance or monitor the bounded linked operation before expecting trace and memory closure.",
            operation_id=latest_operation_id,
            next_step=latest_next_step or record.next_step,
        )
    elif not (trace_count or audit_count or ledger_count):
        active_stage = "trace"
        summary = "The mission has linked work, but no trace receipts are recorded yet."
        handoff = _loop_handoff(
            "trace",
            "inspect_trace_gap",
            "Linked work exists, but no run-ledger or trace receipt is available yet.",
            operation_id=latest_operation_id,
            trace_id=latest_trace_id,
            next_step=record.next_step,
        )

    return {
        "summary": summary,
        "active_stage": active_stage,
        "handoff": handoff,
        "plan": plan_stage,
        "gate": gate_stage,
        "execute": execute_stage,
        "trace": trace_stage,
        "memory": memory_stage,
    }


def _mission_detail_projection(record: mission_store.MissionRecord, *, log_limit: int = 50) -> dict[str, Any]:
    linked_operations = _linked_operation_details(record, log_limit=log_limit)
    history = mission_store.read_history(record.mission_id)
    run_ledger = _mission_run_ledger(record.mission_id, linked_operations)
    _, queue_item, _ = mission_store.mission_queue_item(record.mission_id)
    return {
        "history": history,
        "linked_operations": linked_operations,
        "run_ledger": run_ledger,
        "loop_state": _mission_loop_state(record, linked_operations, run_ledger, history),
        "queue_item": queue_item or {},
    }


def _mission_queue_result_projection(mission_id: str) -> dict[str, Any]:
    cleaned = _safe_str(mission_id).strip()
    if not cleaned:
        return {}
    record, err = mission_store.read_mission(cleaned)
    if not record:
        return {"mission_error": err or "not_found"}
    detail = _mission_detail_projection(record, log_limit=25)
    loop_state = detail.get("loop_state") if isinstance(detail.get("loop_state"), dict) else {}
    queue_item = detail.get("queue_item") if isinstance(detail.get("queue_item"), dict) else {}
    return {
        "mission": _serialize_mission(record),
        "queue_item": queue_item,
        "loop_state": loop_state,
        "handoff": loop_state.get("handoff") if isinstance(loop_state.get("handoff"), dict) else {},
        "history_count": len(detail.get("history")) if isinstance(detail.get("history"), list) else 0,
        "linked_operation_count": len(detail.get("linked_operations"))
        if isinstance(detail.get("linked_operations"), list)
        else 0,
        "run_ledger_count": len(detail.get("run_ledger")) if isinstance(detail.get("run_ledger"), list) else 0,
    }


class MissionCreateIn(BaseModel):
    objective: str
    summary: str = ""
    next_step: str = ""
    requester_id: str = "api"
    owner_id: str = ""
    priority: int = 5
    risk_tier: str = "medium"
    dependency_ids: list[str] = Field(default_factory=list)
    escalation_path: str = ""
    status: str = "queued"
    linked_task_ids: list[str] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)


class MissionPatchIn(BaseModel):
    status: str | None = None
    summary: str | None = None
    next_step: str | None = None
    owner_id: str | None = None
    dependency_ids: list[str] | None = None
    escalation_path: str | None = None
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
    blocked_reason = _mission_write_posture_guard("declaring a mission")
    if blocked_reason:
        return {"ok": False, "error": blocked_reason, "status": "blocked"}
    try:
        record, err = mission_store.create_mission(
            MissionCreateRequest(
                objective=payload.objective,
                summary=payload.summary,
                next_step=payload.next_step,
                requester_id=payload.requester_id,
                owner_id=payload.owner_id,
                priority=max(1, min(int(payload.priority), 9)),
                risk_tier=payload.risk_tier,
                dependency_ids=payload.dependency_ids,
                escalation_path=payload.escalation_path,
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
            **_mission_detail_projection(record),
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
    blocked_reason = _mission_write_posture_guard("reconciling the mission queue")
    if blocked_reason:
        return {
            "ok": False,
            "items": [],
            "total": 0,
            "applied": 0,
            "errors": [{"error": blocked_reason}],
            "status": "blocked",
        }
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
    blocked_reason = _mission_write_posture_guard("running the mission queue")
    if blocked_reason:
        return {
            "ok": False,
            "items": [],
            "deadletter": [],
            "total": 0,
            "applied": 0,
            "advanced": 0,
            "results": [],
            "processed": 0,
            "errors": [{"error": blocked_reason}],
            "counts": {},
            "status": "blocked",
        }
    try:
        safe_limit = max(1, min(int(payload.limit), 5000))
        actor = _safe_str(payload.actor).strip() or "missions.runner"
        note = _safe_str(payload.note).strip() or "mission_queue_run_once"
        result = mission_runtime.run_queue_once(limit=safe_limit, actor=actor, note=note)
        result_items = result.get("results") if isinstance(result.get("results"), list) else []
        projection_cache: dict[str, dict[str, Any]] = {}
        for item in result_items:
            if not isinstance(item, dict):
                continue
            mission_id = _safe_str(item.get("mission_id")).strip()
            if not mission_id:
                continue
            if mission_id not in projection_cache:
                projection_cache[mission_id] = _mission_queue_result_projection(mission_id)
            item.update(projection_cache[mission_id])
        return result
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
            **_mission_detail_projection(record),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.patch("/{mission_id}")
def patch_mission(mission_id: str, payload: MissionPatchIn) -> dict[str, object]:
    blocked_reason = _mission_write_posture_guard("updating a mission")
    if blocked_reason:
        return {"ok": False, "error": blocked_reason, "status": "blocked"}
    try:
        record, err = mission_store.update_mission(
            mission_id,
            status=payload.status.strip().lower() if payload.status else None,
            summary=payload.summary,
            next_step=payload.next_step,
            owner_id=payload.owner_id,
            dependency_ids=payload.dependency_ids,
            escalation_path=payload.escalation_path,
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
            **_mission_detail_projection(record),
            "message": "updated",
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.post("/{mission_id}/tick")
def tick_mission(mission_id: str, payload: MissionTickIn) -> dict[str, object]:
    blocked_reason = _mission_write_posture_guard("ticking mission continuity")
    if blocked_reason:
        return {"ok": False, "applied": False, "error": blocked_reason, "status": "blocked"}
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
            **_mission_detail_projection(record),
            "message": "ticked" if applied else "no_change",
        }
    except Exception as exc:
        return {"ok": False, "applied": False, "error": str(exc)}


@router.post("/{mission_id}/deadletter")
def deadletter_mission(mission_id: str, payload: MissionDeadletterIn) -> dict[str, object]:
    blocked_reason = _mission_write_posture_guard("deadlettering a mission")
    if blocked_reason:
        return {"ok": False, "error": blocked_reason, "status": "blocked"}
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
            **_mission_detail_projection(record),
            "message": "deadlettered",
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.post("/{mission_id}/advance")
def advance_mission(mission_id: str, payload: MissionAdvanceIn) -> dict[str, object]:
    blocked_reason = _mission_write_posture_guard("advancing a mission")
    if blocked_reason:
        return {"ok": False, "applied": False, "error": blocked_reason, "status": "blocked"}
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
            result.update(_mission_detail_projection(mission_record))
        return result
    except Exception as exc:
        return {"ok": False, "applied": False, "error": str(exc)}
