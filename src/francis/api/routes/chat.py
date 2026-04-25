from __future__ import annotations

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
    handoff = loop_state.get("handoff") if isinstance(loop_state.get("handoff"), dict) else {}
    action = str(handoff.get("action") or "link_operation").strip()
    reply = f"Mission {record.mission_id} declared. Next: {action}."
    append(
        "assistant",
        reply,
        {
            "mode": "mission_ingress",
            "status": record.status.value,
            "mission_id": record.mission_id,
            "handoff_action": action,
        },
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
            msg = await websocket.receive_text()
            reply = handle(msg, use_llm=False)
            await websocket.send_text(reply)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)
