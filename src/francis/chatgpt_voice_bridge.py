from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from francis.governance.api_permission_gate import ApiPermissionDecision, ApiPermissionGate
from francis.governance.redaction import redact_secret_text
from francis.kernel.paths import data_dir

CHATGPT_VOICE_BRIDGE_READ_SCOPE = "chatgpt.voice.bridge.read"
CHATGPT_VOICE_BRIDGE_WRITE_SCOPE = "chatgpt.voice.bridge.write"
CHATGPT_VOICE_BRIDGE_KIND = "francis.chatgpt_voice.bridge"
CHATGPT_VOICE_BRIDGE_VERSION = "chatgpt_voice_bridge_v0"
CHATGPT_VOICE_BRIDGE_HTTP_TRANSPORT = "http_api"
CHATGPT_VOICE_BRIDGE_MCP_GATEWAY_TRANSPORT = "mcp_gateway_tool"
CHATGPT_VOICE_BRIDGE_MCP_GATEWAY_TOOL = "francis.chatgpt_voice.ingress"
CHATGPT_VOICE_BRIDGE_MCP_SERVER_TOOL = "francis_chatgpt_voice_ingress"
MAX_TRANSCRIPT_CHARS = 8000
_TRANSCRIPT_UNAVAILABLE_MARKERS = {
    "transcript unavailable",
    "transcript not available",
    "unavailable transcript",
}
_TRANSCRIPT_REQUIRED_REPLY = (
    "I did not receive a transcript from ChatGPT voice, so I cannot answer that turn. "
    "Please repeat it or send the text."
)
_TRANSCRIPT_UNAVAILABLE_REPLY = (
    "ChatGPT reported that the transcript was unavailable, so I did not forward that as your message. "
    "Please repeat the request or send the text."
)


def _now() -> float:
    return time.time()


def _utc_iso_from_ts(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    try:
        return str(value).strip()
    except Exception:
        return default


def _bounded_text(value: Any, *, max_chars: int) -> str:
    text = _safe_str(value)
    if not text:
        return ""
    return text[: max(1, max_chars)]


def _transcript_rejection_reason(text: str) -> str:
    if not text:
        return "transcript_required"
    normalized = " ".join("".join(char if char.isalnum() else " " for char in text.lower()).split())
    if normalized in _TRANSCRIPT_UNAVAILABLE_MARKERS:
        return "transcript_unavailable"
    if any(normalized.startswith(f"{marker} ") for marker in _TRANSCRIPT_UNAVAILABLE_MARKERS):
        return "transcript_unavailable"
    return ""


def _voice_response(*, text: str, source: str, requires_transcript: bool = False) -> dict[str, Any]:
    return {
        "text": text,
        "source": source,
        "speakable": bool(text),
        "requires_transcript": bool(requires_transcript),
        "raw_audio": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
    }


def _receipt_root() -> Path:
    return data_dir() / "integrations" / "chatgpt_voice" / "receipts"


def _atomic_write_json(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".atomic-json-{os.getpid()}-{hashlib.sha256(str(_now()).encode()).hexdigest()[:12]}.tmp")
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=True, default=str), encoding="utf-8")
    os.replace(tmp, path)


def _digest(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:16]


def _permission(
    actor: str,
    *,
    required_scope: str,
    route: str,
    method: str,
) -> ApiPermissionDecision:
    return ApiPermissionGate.from_env().check(
        actor_id=actor,
        required_scopes=[required_scope],
        route=route,
        method=method,
    )


def _permission_denied(decision: ApiPermissionDecision, *, kind: str) -> dict[str, Any]:
    return {
        "kind": kind,
        "ok": False,
        "status": "denied",
        "error": "api_permission_denied",
        "governance": {
            "bridge": CHATGPT_VOICE_BRIDGE_VERSION,
            "gate": "permission_gate",
            "reason": decision.reason,
            "evidence": decision.evidence,
            "read_only": True,
            "writes_receipt": False,
            "forwards_to_chat": False,
            "calls_model": False,
            "raw_audio": False,
            "raw_shell": False,
            "raw_input": False,
            "screenshots": False,
            "pixels": False,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
    }


def _honesty(*, read_only: bool, writes_receipt: bool = False, forwards_to_chat: bool = False) -> dict[str, Any]:
    return {
        "bridge": CHATGPT_VOICE_BRIDGE_VERSION,
        "read_only": read_only,
        "writes_receipt": writes_receipt,
        "records_transcript": writes_receipt,
        "raw_audio": False,
        "accepts_audio_stream": False,
        "transcript_only": True,
        "forwards_to_chat": forwards_to_chat,
        "chat_forward_requires_chat_write_scope": True,
        "calls_model": False,
        "raw_shell": False,
        "raw_input": False,
        "screenshots": False,
        "pixels": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "approves_proposals": False,
        "promotes_capabilities": False,
        "creates_native_chatgpt_app": False,
        "claims_phone_localhost_access": False,
    }


def chatgpt_voice_bridge_contract(actor: str = "") -> dict[str, Any]:
    route = "/chatgpt-voice/contract"
    clean_actor = _safe_str(actor)
    decision = _permission(clean_actor, required_scope=CHATGPT_VOICE_BRIDGE_READ_SCOPE, route=route, method="GET")
    if not decision.allowed:
        return _permission_denied(decision, kind=f"{CHATGPT_VOICE_BRIDGE_KIND}.contract")

    return {
        "kind": f"{CHATGPT_VOICE_BRIDGE_KIND}.contract",
        "ok": True,
        "status": "ready",
        "surface": CHATGPT_VOICE_BRIDGE_VERSION,
        "routes": {
            "contract": route,
            "ingress": "/chatgpt-voice/ingress",
            "receipts": "/chatgpt-voice/receipts",
            "chat_forward_target": "/chat/send",
        },
        "mcp_tools": {
            "contract": "francis.chatgpt_voice.contract",
            "ingress": CHATGPT_VOICE_BRIDGE_MCP_GATEWAY_TOOL,
            "server_ingress": CHATGPT_VOICE_BRIDGE_MCP_SERVER_TOOL,
            "receipts": "francis.chatgpt_voice.receipts",
        },
        "receipt_contract": {
            "ingress_provenance_fields": ["ingress_transport", "mcp_gateway_tool", "mcp_server_tool"],
            "direct_http_transport": CHATGPT_VOICE_BRIDGE_HTTP_TRANSPORT,
            "mcp_gateway_transport": CHATGPT_VOICE_BRIDGE_MCP_GATEWAY_TRANSPORT,
            "mcp_gateway_tool": CHATGPT_VOICE_BRIDGE_MCP_GATEWAY_TOOL,
            "mcp_server_tool": CHATGPT_VOICE_BRIDGE_MCP_SERVER_TOOL,
        },
        "input_contract": {
            "transcript_required": True,
            "audio_stream_accepted": False,
            "max_transcript_chars": MAX_TRANSCRIPT_CHARS,
            "metadata_fields": ["source", "conversation_id", "turn_id", "locale"],
            "forward_to_chat_default": True,
            "use_llm_default": False,
        },
        "chatgpt_app_boundary": {
            "supported_shape": "mcp_or_https_connector_posts_transcribed_text",
            "native_phone_localhost_access_claimed": False,
            "mobile_client_requires_linked_chatgpt_app_or_connector": True,
            "local_francis_requires_reachable_https_endpoint_or_tunnel_for_mobile": True,
        },
        "governance": _honesty(read_only=True),
    }


def _write_receipt(payload: dict[str, Any]) -> dict[str, Any]:
    receipt_id = f"chatgpt-voice-{_safe_str(payload.get('decision'), 'recorded')}-{_digest(payload)}"
    created_ts = _now()
    receipt = {
        "kind": f"{CHATGPT_VOICE_BRIDGE_KIND}.receipt",
        "receipt_id": receipt_id,
        "id": receipt_id,
        "created_ts": created_ts,
        "created_at": _utc_iso_from_ts(created_ts),
        **payload,
        "governance": _honesty(
            read_only=False,
            writes_receipt=True,
            forwards_to_chat=bool(payload.get("chat_forward_requested")) and bool(payload.get("chat_forwarded")),
        ),
    }
    path = _receipt_root() / f"{receipt_id}.json"
    _atomic_write_json(path, receipt)
    receipt["receipt_path"] = str(path)
    return receipt


def record_chatgpt_voice_ingress(
    *,
    actor: str = "",
    transcript: str = "",
    source: str = "chatgpt.voice",
    conversation_id: str = "",
    turn_id: str = "",
    locale: str = "",
    forward_to_chat: bool = True,
    use_llm: bool = False,
    ingress_transport: str = CHATGPT_VOICE_BRIDGE_HTTP_TRANSPORT,
    mcp_gateway_tool: str = "",
    mcp_server_tool: str = "",
) -> dict[str, Any]:
    route = "/chatgpt-voice/ingress"
    clean_actor = _safe_str(actor) or "chatgpt.voice"
    decision = _permission(clean_actor, required_scope=CHATGPT_VOICE_BRIDGE_WRITE_SCOPE, route=route, method="POST")
    if not decision.allowed:
        return _permission_denied(decision, kind=f"{CHATGPT_VOICE_BRIDGE_KIND}.ingress")

    bounded_transcript = _bounded_text(transcript, max_chars=MAX_TRANSCRIPT_CHARS)
    redacted_transcript = redact_secret_text(bounded_transcript)
    base_payload: dict[str, Any] = {
        "actor": clean_actor,
        "source": _bounded_text(source, max_chars=96) or "chatgpt.voice",
        "ingress_transport": _bounded_text(ingress_transport, max_chars=64) or CHATGPT_VOICE_BRIDGE_HTTP_TRANSPORT,
        "mcp_gateway_tool": _bounded_text(mcp_gateway_tool, max_chars=96),
        "mcp_server_tool": _bounded_text(mcp_server_tool, max_chars=96),
        "conversation_id": _bounded_text(conversation_id, max_chars=160),
        "turn_id": _bounded_text(turn_id, max_chars=160),
        "locale": _bounded_text(locale, max_chars=32),
        "transcript": redacted_transcript,
        "transcript_char_count": len(redacted_transcript),
        "transcript_truncated": len(_safe_str(transcript)) > MAX_TRANSCRIPT_CHARS,
        "chat_forward_requested": bool(forward_to_chat),
        "use_llm_requested": bool(use_llm),
        "secrets_redacted": redacted_transcript != bounded_transcript,
    }

    transcript_rejection_reason = _transcript_rejection_reason(redacted_transcript)
    if transcript_rejection_reason:
        reply = (
            _TRANSCRIPT_UNAVAILABLE_REPLY
            if transcript_rejection_reason == "transcript_unavailable"
            else _TRANSCRIPT_REQUIRED_REPLY
        )
        receipt = _write_receipt({**base_payload, "decision": "rejected", "reason": transcript_rejection_reason})
        return {
            "kind": f"{CHATGPT_VOICE_BRIDGE_KIND}.ingress",
            "ok": False,
            "status": "rejected",
            "error": transcript_rejection_reason,
            "reply": reply,
            "voice_response": _voice_response(
                text=reply,
                source="bridge.transcript_guard",
                requires_transcript=True,
            ),
            "receipt": receipt,
            "chat_forward": {
                "requested": bool(forward_to_chat),
                "forwarded": False,
                "status": "rejected",
                "error": transcript_rejection_reason,
                "response": {},
            },
            "governance": _honesty(read_only=False, writes_receipt=True),
        }

    chat_response: dict[str, Any] = {}
    chat_forwarded = False
    chat_status = "not_requested"
    chat_error = ""
    if forward_to_chat:
        from francis.api.routes.chat import ChatIn, send

        chat_response = send(
            ChatIn(
                message=redacted_transcript,
                use_llm=bool(use_llm),
                actor=clean_actor,
                voice_turn_id=_bounded_text(turn_id, max_chars=96),
            )
        )
        chat_error = _safe_str(chat_response.get("error"))
        chat_forwarded = not chat_error and chat_response.get("status") != "denied"
        chat_status = "forwarded" if chat_forwarded else "denied"
    reply = _safe_str(chat_response.get("reply")) if chat_forwarded else ""
    reply_source = "chat_forward.response" if reply else ""
    if not reply:
        if forward_to_chat and not chat_forwarded:
            reply = "I recorded the transcript, but the Francis chat write gate did not accept forwarding."
            reply_source = "bridge.forward_denied"
        else:
            reply = "I recorded the transcript for Francis. Chat forwarding was not requested."
            reply_source = "bridge.recorded_only"

    receipt = _write_receipt(
        {
            **base_payload,
            "decision": "recorded",
            "chat_forwarded": chat_forwarded,
            "chat_forward_status": chat_status,
            "chat_forward_error": chat_error,
            "chat_response_mode": _safe_str(chat_response.get("mode")),
            "chat_response_status": _safe_str(chat_response.get("status")),
            "reply": reply,
            "reply_source": reply_source,
        }
    )
    status = "forwarded" if chat_forwarded else "recorded_not_forwarded" if forward_to_chat else "recorded"
    return {
        "kind": f"{CHATGPT_VOICE_BRIDGE_KIND}.ingress",
        "ok": chat_forwarded or not forward_to_chat,
        "status": status,
        "reply": reply,
        "voice_response": _voice_response(text=reply, source=reply_source),
        "receipt": receipt,
        "chat_forward": {
            "requested": bool(forward_to_chat),
            "forwarded": chat_forwarded,
            "status": chat_status,
            "error": chat_error,
            "response": chat_response,
        },
        "governance": _honesty(read_only=False, writes_receipt=True, forwards_to_chat=chat_forwarded),
    }


def chatgpt_voice_bridge_receipts(actor: str = "", *, limit: int = 10) -> dict[str, Any]:
    route = "/chatgpt-voice/receipts"
    clean_actor = _safe_str(actor)
    decision = _permission(clean_actor, required_scope=CHATGPT_VOICE_BRIDGE_READ_SCOPE, route=route, method="GET")
    if not decision.allowed:
        return _permission_denied(decision, kind=f"{CHATGPT_VOICE_BRIDGE_KIND}.receipts")

    root = _receipt_root()
    receipts: list[dict[str, Any]] = []
    if root.exists():
        paths = sorted(root.glob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
        for path in paths[: max(1, min(int(limit or 10), 100))]:
            try:
                item = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if isinstance(item, dict):
                item["receipt_path"] = str(path)
                receipts.append(item)
    return {
        "kind": f"{CHATGPT_VOICE_BRIDGE_KIND}.receipts",
        "ok": True,
        "status": "ready",
        "count": len(receipts),
        "receipts": receipts,
        "governance": _honesty(read_only=True),
    }


__all__ = [
    "CHATGPT_VOICE_BRIDGE_HTTP_TRANSPORT",
    "CHATGPT_VOICE_BRIDGE_MCP_GATEWAY_TOOL",
    "CHATGPT_VOICE_BRIDGE_MCP_GATEWAY_TRANSPORT",
    "CHATGPT_VOICE_BRIDGE_MCP_SERVER_TOOL",
    "CHATGPT_VOICE_BRIDGE_READ_SCOPE",
    "CHATGPT_VOICE_BRIDGE_WRITE_SCOPE",
    "chatgpt_voice_bridge_contract",
    "chatgpt_voice_bridge_receipts",
    "record_chatgpt_voice_ingress",
]
