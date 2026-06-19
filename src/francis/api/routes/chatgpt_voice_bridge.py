from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel

from francis.chatgpt_voice_bridge import (
    chatgpt_voice_bridge_contract,
    chatgpt_voice_bridge_receipts,
    record_chatgpt_voice_ingress,
    record_chatgpt_voice_mcp_probe,
)

router = APIRouter()


class ChatGptVoiceIngressIn(BaseModel):
    actor: str | None = None
    transcript: str = ""
    source: str = "chatgpt.voice"
    client_origin: str = ""
    conversation_id: str = ""
    turn_id: str = ""
    locale: str = ""
    forward_to_chat: bool = True
    use_llm: bool = False


class ChatGptVoiceMcpProofIn(BaseModel):
    actor: str | None = None
    source: str = "chatgpt.voice"
    client_origin: str = ""
    reason: str = ""


@router.get("/contract")
def contract(actor: str = "") -> dict[str, Any]:
    return chatgpt_voice_bridge_contract(actor=actor)


@router.post("/mcp-proof")
def mcp_proof(payload: ChatGptVoiceMcpProofIn) -> dict[str, Any]:
    return record_chatgpt_voice_mcp_probe(
        actor=payload.actor or "",
        source=payload.source,
        client_origin=payload.client_origin,
        reason=payload.reason,
    )


@router.post("/ingress")
def ingress(payload: ChatGptVoiceIngressIn) -> dict[str, Any]:
    return record_chatgpt_voice_ingress(
        actor=payload.actor or "",
        transcript=payload.transcript,
        source=payload.source,
        client_origin=payload.client_origin,
        conversation_id=payload.conversation_id,
        turn_id=payload.turn_id,
        locale=payload.locale,
        forward_to_chat=payload.forward_to_chat,
        use_llm=payload.use_llm,
    )


@router.get("/receipts")
def receipts(actor: str = "", limit: int = Query(10, ge=1, le=100)) -> dict[str, Any]:
    return chatgpt_voice_bridge_receipts(actor=actor, limit=limit)
