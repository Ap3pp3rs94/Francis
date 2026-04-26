from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from francis.api.routes._operator_posture import posture_write_guard
from francis.api.websocket import ConnectionManager
from francis.chat.continuity.ledger import append
from francis.chat.router import handle, parse_mission_ingress
from francis.governance.redaction import redact_secret_text
from francis.missions import store as mission_store
from francis.missions.store import MissionCreateRequest

router = APIRouter()
manager = ConnectionManager()


@router.get("/health")
def health() -> dict[str, object]:
    return {"ok": True, "service": "chat"}


class ChatIn(BaseModel):
    message: str
    use_llm: bool = False


def _chat_text_from_wire(raw: str) -> str:
    if not isinstance(raw, str):
        return str(raw)

    stripped = raw.strip()
    if not stripped:
        return ""

    try:
        decoded = json.loads(stripped)
    except Exception:
        return raw
    if not isinstance(decoded, dict):
        return raw

    message = decoded.get("message") if isinstance(decoded.get("message"), dict) else decoded
    content = message.get("content") if isinstance(message, dict) else None
    if isinstance(content, str):
        return content
    return raw


def _mission_ingress_ws_event(payload: dict[str, object]) -> str:
    reply = str(payload.get("reply") or "")
    meta = {
        key: payload[key]
        for key in (
            "ok",
            "mode",
            "status",
            "error",
            "mission_id",
            "mission",
            "queue_item",
            "loop_state",
            "current_task",
            "receipt_summary",
        )
        if key in payload
    }
    return json.dumps(
        {
            "type": "message",
            "message": {
                "role": "assistant",
                "content": reply,
                "meta": meta,
            },
        },
        ensure_ascii=True,
    )


def _compact_mission_ingress_meta(
    *,
    record: mission_store.MissionRecord,
    loop_state: dict[str, object],
    current_task: dict[str, object],
    receipt_summary: dict[str, object],
) -> dict[str, object]:
    handoff = loop_state.get("handoff") if isinstance(loop_state.get("handoff"), dict) else {}
    meta: dict[str, object] = {
        "mode": "mission_ingress",
        "status": record.status.value,
        "mission_id": record.mission_id,
        "ingress_plane": "P1_INTERFACE",
        "active_stage": str(loop_state.get("active_stage") or "").strip(),
        "handoff_stage": str(handoff.get("stage") or "").strip(),
        "handoff_action": str(handoff.get("action") or "").strip(),
        "handoff_gate": str(handoff.get("gate") or "").strip(),
        "handoff_approval_id": str(handoff.get("approval_id") or "").strip(),
        "handoff_operation_id": str(handoff.get("operation_id") or "").strip(),
        "handoff_trace_id": str(handoff.get("trace_id") or "").strip(),
        "handoff_next_step": str(handoff.get("next_step") or "").strip(),
        "current_task_source": str(current_task.get("source") or "").strip(),
        "current_task_operation_id": str(current_task.get("operation_id") or "").strip(),
        "current_task_gate": str(current_task.get("gate") or "").strip(),
        "current_task_next_step": str(current_task.get("next_step") or "").strip(),
        "linked_operation_count": int(receipt_summary.get("linked_operation_count") or 0),
        "run_ledger_count": int(receipt_summary.get("run_ledger_count") or 0),
        "memory_receipt_count": int(receipt_summary.get("memory_receipt_count") or 0),
    }
    return {key: value for key, value in meta.items() if value not in {"", None}}


def _mission_ingress_reply(payload: ChatIn) -> dict[str, object] | None:
    intent = parse_mission_ingress(payload.message)
    if intent is None:
        return None

    objective = redact_secret_text(intent.objective.strip())
    append("user", f"/mission {objective}".strip(), {"mode": "mission_ingress", "redacted": True})
    if not objective:
        reply = "Mission declaration needs an objective after /mission."
        append("assistant", reply, {"mode": "mission_ingress", "status": "rejected"})
        return {
            "ok": False,
            "mode": "mission_ingress",
            "status": "rejected",
            "error": "objective_required",
            "reply": reply,
        }

    blocked_reason = posture_write_guard("declaring a mission from chat")
    if blocked_reason:
        reply = f"Mission declaration blocked: {blocked_reason}"
        append("assistant", reply, {"mode": "mission_ingress", "status": "blocked"})
        return {
            "ok": False,
            "mode": "mission_ingress",
            "status": "blocked",
            "error": blocked_reason,
            "reply": reply,
        }

    record, err = mission_store.create_mission(
        MissionCreateRequest(
            objective=objective,
            summary="Mission declared from chat ingress.",
            next_step="Declare or advance the first bounded operation for this mission.",
            requester_id="chat.send",
            owner_id="chat.send",
            status=mission_store.MissionStatus.QUEUED,
            meta={"source": "chat.send", "ingress_plane": "P1_INTERFACE"},
        )
    )
    if not record:
        error = err or "mission_create_failed"
        reply = f"Mission declaration failed: {error}"
        append("assistant", reply, {"mode": "mission_ingress", "status": "failed"})
        return {"ok": False, "mode": "mission_ingress", "status": "failed", "error": error, "reply": reply}

    from francis.api.routes import missions as mission_routes

    detail = mission_routes._mission_detail_projection(record)
    queue_item = detail.get("queue_item") if isinstance(detail.get("queue_item"), dict) else {}
    loop_state = detail.get("loop_state") if isinstance(detail.get("loop_state"), dict) else {}
    current_task = detail.get("current_task") if isinstance(detail.get("current_task"), dict) else {}
    receipt_summary = detail.get("receipt_summary") if isinstance(detail.get("receipt_summary"), dict) else {}
    handoff = loop_state.get("handoff") if isinstance(loop_state.get("handoff"), dict) else {}
    action = str(handoff.get("action") or "link_operation").strip()
    reply = f"Mission {record.mission_id} declared. Next: {action}."
    append(
        "assistant",
        reply,
        _compact_mission_ingress_meta(
            record=record,
            loop_state=loop_state,
            current_task=current_task,
            receipt_summary=receipt_summary,
        ),
    )

    response: dict[str, Any] = {
        "ok": True,
        "mode": "mission_ingress",
        "status": record.status.value,
        "reply": reply,
        "mission_id": record.mission_id,
        "mission": mission_routes._serialize_mission(record, queue_item),
    }
    response.update(detail)
    return response


@router.post("/send")
def send(payload: ChatIn) -> dict[str, object]:
    try:
        mission_reply = _mission_ingress_reply(payload)
        if mission_reply is not None:
            return mission_reply
        return {"reply": handle(payload.message, use_llm=payload.use_llm)}
    except Exception as exc:
        return {"reply": "", "error": str(exc)}


@router.websocket("/ws")
async def ws(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    try:
        while True:
            raw_msg = await websocket.receive_text()
            msg = _chat_text_from_wire(raw_msg)
            mission_reply = _mission_ingress_reply(ChatIn(message=msg, use_llm=False))
            if mission_reply is not None:
                await websocket.send_text(_mission_ingress_ws_event(mission_reply))
                continue
            reply = handle(msg, use_llm=False)
            await websocket.send_text(reply)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)
