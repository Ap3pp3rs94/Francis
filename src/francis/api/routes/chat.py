from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from francis.api.websocket import ConnectionManager
from francis.chat.router import handle

router = APIRouter()
manager = ConnectionManager()


@router.get("/health")
def health() -> dict[str, object]:
    return {"ok": True, "service": "chat"}


class ChatIn(BaseModel):
    message: str
    use_llm: bool = False


@router.post("/send")
def send(payload: ChatIn) -> dict[str, object]:
    try:
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
