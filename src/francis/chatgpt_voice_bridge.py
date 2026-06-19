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
CHATGPT_VOICE_BRIDGE_MCP_PROOF_GATEWAY_TOOL = "francis.chatgpt_voice.mcp_probe"
CHATGPT_VOICE_BRIDGE_MCP_PROOF_SERVER_TOOL = "francis_chatgpt_voice_mcp_probe"
CHATGPT_VOICE_BRIDGE_MCP_CLIENT_UNSPECIFIED = "mcp_client_unspecified"
CHATGPT_VOICE_BRIDGE_MCP_SERVER_TRANSPORT_UNSPECIFIED = "mcp_server_transport_unspecified"
CHATGPT_VOICE_BRIDGE_PUBLIC_CONNECTOR_TRANSPORT = "streamable-http"
CHATGPT_VOICE_BRIDGE_CHATGPT_APP_VOICE_CLIENT = "chatgpt_app_voice"
CHATGPT_VOICE_BRIDGE_VIRTUAL_TURN_STATE = "data/runtime/lens-overlay/voice-turn-status.json"
CHATGPT_VOICE_BRIDGE_VIRTUAL_TURN_RECEIPTS = "data/runtime/lens-overlay/voice-turns"
CHATGPT_VOICE_BRIDGE_ORB_POSITION_COMMAND_REQUEST = "data/runtime/lens-overlay/orb-position-command-request.json"
CHATGPT_VOICE_BRIDGE_ORB_POSITION_COMMAND_RECEIPTS = "data/runtime/lens-overlay/orb-position-commands"
CHATGPT_VOICE_BRIDGE_MCP_INGRESS_DESCRIPTION = (
    "Use this as the required bridge for every ChatGPT voice turn directed at Francis, the Francis orb, "
    "or the Francis voice/lens surface. When the operator is trying to talk to Francis, always pass the exact "
    "user-visible transcript text in `transcript`, leave `forward_to_chat` true unless the operator explicitly "
    "requested receipt-only intake, and speak only the returned top-level `reply` as Francis's answer. If ChatGPT "
    "voice reports Transcript Unavailable, still call this tool with that marker so Francis can return the bounded "
    "transcript guard reply. When this call is made by ChatGPT Voice, set `client_origin` to `chatgpt_app_voice`; "
    "the MCP server adapter also defaults to that value for ChatGPT voice calls. Do not answer locally, summarize, "
    "or invent a Francis reply. The returned voice reply is sentence-aware and bounded for spoken playback."
)
CHATGPT_VOICE_BRIDGE_MCP_PROOF_DESCRIPTION = (
    "Call this first when validating that ChatGPT can reach Francis over the MCP connector, especially when "
    "ChatGPT Voice shows Transcript Unavailable. This records a connection-proof receipt only; it does not record "
    "a user transcript, does not call the model, does not update a voice turn, and does not grant execution authority."
)
MAX_TRANSCRIPT_CHARS = 8000
MAX_SPEAKABLE_REPLY_CHARS = 420
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


def _limit_speakable_reply(text: str, *, max_chars: int = MAX_SPEAKABLE_REPLY_CHARS) -> tuple[str, bool]:
    bounded = _safe_str(text).replace("\r", " ").replace("\n", " ")
    bounded = " ".join(bounded.split())
    if len(bounded) <= max_chars:
        return bounded, False
    if max_chars <= 3:
        return bounded[:max_chars], True

    candidate = bounded[:max_chars].rstrip()
    minimum_useful_boundary = min(160, int(max_chars * 0.45))
    sentence_boundary = max(candidate.rfind("."), candidate.rfind("!"), candidate.rfind("?"))
    if sentence_boundary >= minimum_useful_boundary:
        return candidate[: sentence_boundary + 1].rstrip(), True

    word_boundary = candidate.rfind(" ")
    if word_boundary >= minimum_useful_boundary:
        return f"{candidate[:word_boundary].rstrip()}...", True
    return f"{bounded[: max_chars - 3].rstrip()}...", True


def _voice_response(
    *,
    text: str,
    source: str,
    requires_transcript: bool = False,
    text_truncated: bool = False,
) -> dict[str, Any]:
    return {
        "text": text,
        "source": source,
        "speakable": bool(text),
        "requires_transcript": bool(requires_transcript),
        "max_text_chars": MAX_SPEAKABLE_REPLY_CHARS,
        "text_truncated": bool(text_truncated),
        "sentence_aware_limit": True,
        "raw_audio": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
    }


def _receipt_root() -> Path:
    return data_dir() / "integrations" / "chatgpt_voice" / "receipts"


def _virtual_voice_root() -> Path:
    return data_dir() / "runtime" / "lens-overlay"


def _virtual_voice_turn_state_path() -> Path:
    return _virtual_voice_root() / "voice-turn-status.json"


def _virtual_voice_turn_receipt_root() -> Path:
    return _virtual_voice_root() / "voice-turns"


def _orb_position_command_request_path() -> Path:
    return _virtual_voice_root() / "orb-position-command-request.json"


def _orb_position_command_receipt_root() -> Path:
    return _virtual_voice_root() / "orb-position-commands"


def _atomic_write_json(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".atomic-json-{os.getpid()}-{hashlib.sha256(str(_now()).encode()).hexdigest()[:12]}.tmp")
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=True, default=str), encoding="utf-8")
    os.replace(tmp, path)


def _digest(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:16]


def _text_digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def _safe_voice_turn_id(turn_id: Any, *, payload: dict[str, Any]) -> str:
    text = _bounded_text(turn_id, max_chars=96)
    if not text:
        text = f"chatgpt_voice_turn_{_digest(payload)}"
    safe = "".join(char if char.isalnum() or char in "_.-" else "_" for char in text)
    return safe.strip("._-") or "chatgpt_voice_turn_unknown"


def _safe_file_id(value: Any, *, default: str) -> str:
    text = _bounded_text(value, max_chars=128)
    safe = "".join(char if char.isalnum() or char in "_.-" else "_" for char in text)
    return safe.strip("._-") or default


def _resolve_orb_position_command(text: str) -> dict[str, Any]:
    normalized = " ".join("".join(char if char.isalnum() else " " for char in text.lower()).split())
    result: dict[str, Any] = {
        "recognized": False,
        "intent": "",
        "command": "",
        "target_side": "",
        "target_anchor": "",
        "normalized_text_length": len(normalized),
        "requires_explicit_orb_reference": True,
        "francis_reference_satisfies_orb_reference": True,
        "reference_type": "",
        "requires_direction": True,
        "conversation_forwarding_suppressed": True,
        "authority_scope": "runtime_overlay_position_only",
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
    }
    if not normalized:
        return result

    words = normalized.split()
    has_orb_reference = "orb" in words or "orbs" in words
    has_francis_reference = "francis" in words or "frances" in words
    has_move_verb = any(
        word in words
        for word in (
            "move",
            "put",
            "place",
            "dock",
            "shift",
            "send",
            "go",
            "come",
            "slide",
            "park",
            "anchor",
            "snap",
            "bring",
            "set",
        )
    )
    move_left = "left" in words
    move_right = "right" in words
    has_embodiment_reference = has_orb_reference or has_francis_reference
    if not has_embodiment_reference or not has_move_verb or move_left == move_right:
        return result

    target_side = "left" if move_left else "right"
    reference_type = "orb" if has_orb_reference else "francis_identity"
    result.update(
        {
            "recognized": True,
            "intent": "move_orb",
            "command": f"move_orb_{target_side}_side",
            "target_side": target_side,
            "target_anchor": f"voice_command_{target_side}_side",
            "reference_type": reference_type,
        }
    )
    return result


def _write_orb_position_command_request(
    *,
    base_payload: dict[str, Any],
    command: dict[str, Any],
    transcript_text: str,
    chat_forward_requested: bool,
) -> dict[str, Any]:
    created_ts = _now()
    request_id = _safe_file_id(
        base_payload.get("turn_id"),
        default=f"orb-position-command-{_digest({**base_payload, **command, 'created_ts': created_ts})}",
    )
    request_path = _orb_position_command_request_path()
    receipt_path = _orb_position_command_receipt_root() / f"{request_id}.json"
    payload = {
        "kind": "lens.overlay.orb_position_command.request",
        "status": "queued",
        "ok": True,
        "request_id": request_id,
        "created_ts": created_ts,
        "created_at": _utc_iso_from_ts(created_ts),
        "source": _safe_str(base_payload.get("source")),
        "actor": _safe_str(base_payload.get("actor")),
        "client_origin": _safe_str(base_payload.get("client_origin")),
        "conversation_id": _safe_str(base_payload.get("conversation_id")),
        "turn_id": _safe_str(base_payload.get("turn_id")),
        "ingress_transport": _safe_str(base_payload.get("ingress_transport")),
        "mcp_gateway_tool": _safe_str(base_payload.get("mcp_gateway_tool")),
        "mcp_server_tool": _safe_str(base_payload.get("mcp_server_tool")),
        "mcp_server_transport": _safe_str(base_payload.get("mcp_server_transport")),
        "intent": _safe_str(command.get("intent")),
        "command": _safe_str(command.get("command")),
        "reference_type": _safe_str(command.get("reference_type")),
        "target_side": _safe_str(command.get("target_side")),
        "target_anchor": _safe_str(command.get("target_anchor")),
        "transcript_length": len(transcript_text),
        "transcript_hash": _text_digest(transcript_text) if transcript_text else "",
        "transcript_redacted": True,
        "stores_transcript": False,
        "chat_forward_requested_before_command": bool(chat_forward_requested),
        "conversation_forwarding_suppressed": True,
        "speech_output_suppressed": False,
        "bounded_overlay_position_mutation": True,
        "mutation_authority_scope": "runtime_overlay_position_only",
        "overlay_runtime_owns_execution": True,
        "request_path": CHATGPT_VOICE_BRIDGE_ORB_POSITION_COMMAND_REQUEST,
        "request_full_path": str(request_path),
        "request_receipt_path": f"{CHATGPT_VOICE_BRIDGE_ORB_POSITION_COMMAND_RECEIPTS}/{request_id}.json",
        "request_receipt_full_path": str(receipt_path),
        "applied": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "governance": {
            "bridge": CHATGPT_VOICE_BRIDGE_VERSION,
            "gate": "chatgpt_voice_orb_position_command_request",
            "writes_receipt": True,
            "writes_overlay_position_command_request": True,
            "forwards_to_chat": False,
            "calls_model": False,
            "raw_audio": False,
            "raw_shell": False,
            "raw_input": False,
            "screenshots": False,
            "pixels": False,
            "overlay_runtime_owns_execution": True,
            "bounded_overlay_position_mutation": True,
            "mutation_authority_scope": "runtime_overlay_position_only",
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
    }
    _atomic_write_json(request_path, payload)
    _atomic_write_json(receipt_path, payload)
    return payload


def _orb_position_command_summary(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": _safe_str(payload.get("status")),
        "request_id": _safe_str(payload.get("request_id")),
        "command": _safe_str(payload.get("command")),
        "target_side": _safe_str(payload.get("target_side")),
        "target_anchor": _safe_str(payload.get("target_anchor")),
        "queued": _safe_str(payload.get("status")) == "queued",
        "applied": bool(payload.get("applied")),
        "conversation_forwarding_suppressed": bool(payload.get("conversation_forwarding_suppressed")),
        "overlay_runtime_owns_execution": bool(payload.get("overlay_runtime_owns_execution")),
        "authority_scope": _safe_str(payload.get("mutation_authority_scope")),
        "reference_type": _safe_str(payload.get("reference_type")),
        "request_path": _safe_str(payload.get("request_path")),
        "request_receipt_path": _safe_str(payload.get("request_receipt_path")),
        "grants_execution_authority": bool(payload.get("grants_execution_authority")),
        "grants_mutation_authority": bool(payload.get("grants_mutation_authority")),
    }


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
        "writes_lens_voice_turn": writes_receipt,
        "virtual_voice_turn_projection": writes_receipt,
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
            "mcp_proof": "/chatgpt-voice/mcp-proof",
            "ingress": "/chatgpt-voice/ingress",
            "receipts": "/chatgpt-voice/receipts",
            "chat_forward_target": "/chat/send",
        },
        "mcp_tools": {
            "contract": "francis.chatgpt_voice.contract",
            "mcp_probe": CHATGPT_VOICE_BRIDGE_MCP_PROOF_GATEWAY_TOOL,
            "server_mcp_probe": CHATGPT_VOICE_BRIDGE_MCP_PROOF_SERVER_TOOL,
            "ingress": CHATGPT_VOICE_BRIDGE_MCP_GATEWAY_TOOL,
            "server_ingress": CHATGPT_VOICE_BRIDGE_MCP_SERVER_TOOL,
            "receipts": "francis.chatgpt_voice.receipts",
        },
        "receipt_contract": {
            "ingress_provenance_fields": [
                "ingress_transport",
                "mcp_gateway_tool",
                "mcp_server_tool",
                "mcp_server_transport",
            ],
            "direct_http_transport": CHATGPT_VOICE_BRIDGE_HTTP_TRANSPORT,
            "mcp_gateway_transport": CHATGPT_VOICE_BRIDGE_MCP_GATEWAY_TRANSPORT,
            "mcp_gateway_tool": CHATGPT_VOICE_BRIDGE_MCP_GATEWAY_TOOL,
            "mcp_server_tool": CHATGPT_VOICE_BRIDGE_MCP_SERVER_TOOL,
            "mcp_connection_proof_gateway_tool": CHATGPT_VOICE_BRIDGE_MCP_PROOF_GATEWAY_TOOL,
            "mcp_connection_proof_server_tool": CHATGPT_VOICE_BRIDGE_MCP_PROOF_SERVER_TOOL,
            "mcp_server_transport_field": "mcp_server_transport",
            "mcp_server_transport_unspecified": CHATGPT_VOICE_BRIDGE_MCP_SERVER_TRANSPORT_UNSPECIFIED,
            "public_connector_transport": CHATGPT_VOICE_BRIDGE_PUBLIC_CONNECTOR_TRANSPORT,
        },
        "orb_voice_contract": {
            "francis_identity": "Francis",
            "francis_surfaces": ["voice", "lens", "orb"],
            "orb_role": "embodiment",
            "orb_is_embodiment": True,
            "voice_lens_orb_are_separate_identities": False,
            "voice_lens_orb_are_francis_surfaces": True,
            "mcp_transcript_updates_voice_turn_readback": True,
            "voice_turn_state_path": CHATGPT_VOICE_BRIDGE_VIRTUAL_TURN_STATE,
            "voice_turn_receipt_root": CHATGPT_VOICE_BRIDGE_VIRTUAL_TURN_RECEIPTS,
            "virtual_voice_turn": True,
            "microphone_capture_claimed": False,
            "raw_audio_stream_accepted": False,
            "local_overlay_speech_started_by_bridge": False,
            "client_speaks_top_level_reply": True,
            "orb_position_voice_commands": True,
            "orb_position_command_targets": ["left", "right"],
            "orb_position_command_move_verbs": [
                "move",
                "put",
                "place",
                "dock",
                "shift",
                "send",
                "go",
                "come",
                "slide",
                "park",
                "anchor",
                "snap",
                "bring",
                "set",
            ],
            "orb_position_command_requires_orb_reference": True,
            "orb_position_command_accepts_francis_identity_reference": True,
            "orb_position_command_requires_direction": True,
            "orb_position_command_request_path": CHATGPT_VOICE_BRIDGE_ORB_POSITION_COMMAND_REQUEST,
            "orb_position_command_receipt_root": CHATGPT_VOICE_BRIDGE_ORB_POSITION_COMMAND_RECEIPTS,
            "orb_position_command_overlay_runtime_owns_execution": True,
            "orb_position_command_authority_scope": "runtime_overlay_position_only",
        },
        "input_contract": {
            "transcript_required": True,
            "audio_stream_accepted": False,
            "max_transcript_chars": MAX_TRANSCRIPT_CHARS,
            "metadata_fields": ["source", "conversation_id", "turn_id", "locale"],
            "client_origin_field": "client_origin",
            "chatgpt_voice_client_origin_value": CHATGPT_VOICE_BRIDGE_CHATGPT_APP_VOICE_CLIENT,
            "forward_to_chat_default": True,
            "use_llm_default": False,
        },
        "client_speech_contract": {
            "call_mcp_probe_to_validate_connector": True,
            "call_ingress_for_every_voice_turn": True,
            "speak_only_top_level_reply": True,
            "max_reply_chars": MAX_SPEAKABLE_REPLY_CHARS,
            "sentence_aware_reply_limit": True,
            "transcript_unavailable_must_be_forwarded": True,
            "chatgpt_voice_must_set_client_origin": CHATGPT_VOICE_BRIDGE_CHATGPT_APP_VOICE_CLIENT,
            "mcp_server_default_client_origin": CHATGPT_VOICE_BRIDGE_CHATGPT_APP_VOICE_CLIENT,
            "local_fallback_answer_allowed": False,
            "mcp_probe_description": CHATGPT_VOICE_BRIDGE_MCP_PROOF_DESCRIPTION,
            "description": CHATGPT_VOICE_BRIDGE_MCP_INGRESS_DESCRIPTION,
        },
        "chatgpt_app_boundary": {
            "supported_shape": "mcp_or_https_connector_posts_transcribed_text",
            "native_phone_localhost_access_claimed": False,
            "mobile_client_requires_linked_chatgpt_app_or_connector": True,
            "local_francis_requires_reachable_https_endpoint_or_tunnel_for_mobile": True,
        },
        "governance": _honesty(read_only=True),
    }


def _is_mcp_ingress(payload: dict[str, Any]) -> bool:
    return (
        _safe_str(payload.get("ingress_transport")) == CHATGPT_VOICE_BRIDGE_MCP_GATEWAY_TRANSPORT
        or bool(_safe_str(payload.get("mcp_gateway_tool")))
        or bool(_safe_str(payload.get("mcp_server_tool")))
    )


def _virtual_voice_status(
    *,
    decision: str,
    chat_forward_requested: bool,
    chat_forwarded: bool,
) -> tuple[str, str]:
    if decision == "rejected":
        return "chatgpt_voice_transcript_rejected", "transcript_guard_reply_ready"
    if chat_forwarded:
        return "chatgpt_voice_reply_ready", "chatgpt_voice_client_speaks_reply"
    if chat_forward_requested:
        return "chatgpt_voice_forward_denied", "policy_denial_reply_ready"
    return "chatgpt_voice_transcript_recorded", "recorded_only_reply_ready"


def _write_virtual_voice_turn(
    *,
    base_payload: dict[str, Any],
    decision: str,
    reply: str,
    reply_source: str,
    chat_forwarded: bool,
    chat_status: str,
    reason: str = "",
    chat_error: str = "",
    chat_response: dict[str, Any] | None = None,
) -> dict[str, Any]:
    chat_response = chat_response or {}
    turn_id = _safe_voice_turn_id(base_payload.get("turn_id"), payload={**base_payload, "decision": decision})
    state_path = _virtual_voice_turn_state_path()
    receipt_path = _virtual_voice_turn_receipt_root() / f"{turn_id}.json"
    created_ts = _now()
    transcript = _safe_str(base_payload.get("transcript"))
    is_mcp = _is_mcp_ingress(base_payload)
    status, handback_state = _virtual_voice_status(
        decision=decision,
        chat_forward_requested=bool(base_payload.get("chat_forward_requested")),
        chat_forwarded=chat_forwarded,
    )
    transcript_source = "chatgpt_voice_mcp_transcript" if is_mcp else "chatgpt_voice_http_transcript"
    payload = {
        "kind": "lens.overlay.voice.turn_state",
        "status": status,
        "ok": decision != "rejected" and (chat_forwarded or not bool(base_payload.get("chat_forward_requested"))),
        "active_turn_id": turn_id,
        "turn_id": turn_id,
        "started_at": _utc_iso_from_ts(created_ts),
        "updated_at": _utc_iso_from_ts(created_ts),
        "voice_turn": True,
        "voice_turn_completed": True,
        "handback_ready": True,
        "handback_state": handback_state,
        "francis_identity": "Francis",
        "francis_identity_contract": "single_francis_identity",
        "francis_surfaces": ["voice", "lens", "orb"],
        "voice_role": "speech_and_transcription_channel",
        "lens_role": "desktop_overlay_view",
        "orb_role": "embodiment",
        "orb_is_embodiment": True,
        "voice_lens_orb_are_separate_identities": False,
        "voice_lens_orb_are_francis_surfaces": True,
        "voice_transport_identity": "chatgpt_voice_or_browser_speech_transport",
        "virtual_voice_turn": True,
        "virtual_voice_source": "chatgpt_voice_bridge",
        "synthetic_transcript": True,
        "synthetic_voice_turn": True,
        "synthetic_voice_turn_command": False,
        "transcript_source": transcript_source,
        "explicit_operator_text": True,
        "microphone_speech": False,
        "microphone_recognition_claimed": False,
        "microphone_capture": False,
        "raw_audio": False,
        "accepts_audio_stream": False,
        "voice_recognition": "not_used_chatgpt_voice_mcp_transcript"
        if is_mcp
        else "not_used_chatgpt_voice_http_transcript",
        "wake_phrase_detected": False,
        "continuous_voice_chat": False,
        "transcript_length": int(base_payload.get("transcript_char_count") or 0),
        "transcript_hash": _text_digest(transcript) if transcript else "",
        "transcript_redacted": True,
        "overlay_stores_transcript": False,
        "bridge_receipt_stores_redacted_transcript": True,
        "mcp_ingress": is_mcp,
        "ingress_transport": _safe_str(base_payload.get("ingress_transport")),
        "mcp_gateway_tool": _safe_str(base_payload.get("mcp_gateway_tool")),
        "mcp_server_tool": _safe_str(base_payload.get("mcp_server_tool")),
        "mcp_server_transport": _safe_str(base_payload.get("mcp_server_transport")),
        "conversation_id": _safe_str(base_payload.get("conversation_id")),
        "source": _safe_str(base_payload.get("source")),
        "actor": _safe_str(base_payload.get("actor")),
        "client_origin": _safe_str(base_payload.get("client_origin")),
        "decision": decision,
        "reason": reason,
        "chat_bridge_route": "/chat/send",
        "chat_bridge_actor": _safe_str(base_payload.get("actor")),
        "chat_bridge_status": chat_status,
        "chat_forward_requested": bool(base_payload.get("chat_forward_requested")),
        "chat_forwarded": chat_forwarded,
        "chat_error": chat_error,
        "chat_response_status": _safe_str(chat_response.get("status")),
        "chat_response_mode": _safe_str(chat_response.get("mode")),
        "chat_route_writes_conversation_ledger": chat_forwarded,
        "orb_position_command_detected": bool(base_payload.get("orb_position_command_detected")),
        "orb_position_command_request": base_payload.get("orb_position_command_request") or {},
        "orb_position_command": _safe_str(base_payload.get("orb_position_command")),
        "orb_position_command_target_side": _safe_str(base_payload.get("orb_position_command_target_side")),
        "orb_position_command_status": _safe_str(base_payload.get("orb_position_command_status")),
        "orb_position_command_authority_scope": _safe_str(base_payload.get("orb_position_command_authority_scope")),
        "orb_position_command_overlay_runtime_owns_execution": bool(
            base_payload.get("orb_position_command_overlay_runtime_owns_execution")
        ),
        "reply_source": reply_source,
        "chat_reply_length": len(reply),
        "chat_reply_max_speakable_chars": int(base_payload.get("chat_reply_max_speakable_chars") or 0),
        "chat_reply_truncated_for_voice": bool(base_payload.get("chat_reply_truncated_for_voice")),
        "chat_reply_sentence_aware_limit": bool(base_payload.get("chat_reply_sentence_aware_limit")),
        "chat_reply_redacted": True,
        "speech_output_owner": "chatgpt_voice_client",
        "client_speaks_top_level_reply": True,
        "local_overlay_speech_started": False,
        "speech_started": False,
        "speech_playback_async": False,
        "speech_output_transport": "chatgpt_voice_client_reply",
        "latest_voice_turn_wins": True,
        "stale_reply_suppression_supported": True,
        "thought_relevance_status": "current_virtual_voice_turn_recorded",
        "thought_retention_policy": "receipt_backed_virtual_turn_readback",
        "model_call_abort_requested": False,
        "model_call_abort_observed": False,
        "model_call_cancellation_supported": False,
        "thought_cancellation_supported": False,
        "arbitrary_audio_control": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "voice_turn_state_path": CHATGPT_VOICE_BRIDGE_VIRTUAL_TURN_STATE,
        "voice_turn_state_full_path": str(state_path),
        "voice_turn_receipt_path": f"{CHATGPT_VOICE_BRIDGE_VIRTUAL_TURN_RECEIPTS}/{turn_id}.json",
        "voice_turn_receipt_full_path": str(receipt_path),
        "next_smallest_truthful_gap": "confirm_chatgpt_client_calls_mcp_tool_for_each_voice_turn",
    }
    _atomic_write_json(state_path, payload)
    _atomic_write_json(receipt_path, payload)
    return payload


def _virtual_voice_summary(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": _safe_str(payload.get("status")),
        "turn_id": _safe_str(payload.get("turn_id")),
        "virtual_voice_turn": bool(payload.get("virtual_voice_turn")),
        "client_origin": _safe_str(payload.get("client_origin")),
        "mcp_ingress": bool(payload.get("mcp_ingress")),
        "mcp_server_transport": _safe_str(payload.get("mcp_server_transport")),
        "transcript_source": _safe_str(payload.get("transcript_source")),
        "chat_bridge_status": _safe_str(payload.get("chat_bridge_status")),
        "chat_forwarded": bool(payload.get("chat_forwarded")),
        "client_speaks_top_level_reply": bool(payload.get("client_speaks_top_level_reply")),
        "local_overlay_speech_started": bool(payload.get("local_overlay_speech_started")),
        "francis_identity": _safe_str(payload.get("francis_identity")),
        "francis_surfaces": payload.get("francis_surfaces", []),
        "orb_role": _safe_str(payload.get("orb_role")),
        "orb_is_embodiment": bool(payload.get("orb_is_embodiment")),
        "voice_lens_orb_are_separate_identities": bool(payload.get("voice_lens_orb_are_separate_identities")),
        "voice_lens_orb_are_francis_surfaces": bool(payload.get("voice_lens_orb_are_francis_surfaces")),
        "microphone_recognition_claimed": bool(payload.get("microphone_recognition_claimed")),
        "raw_audio": bool(payload.get("raw_audio")),
        "voice_turn_state_path": _safe_str(payload.get("voice_turn_state_path")),
        "voice_turn_receipt_path": _safe_str(payload.get("voice_turn_receipt_path")),
        "orb_position_command_detected": bool(payload.get("orb_position_command_detected")),
        "orb_position_command": _safe_str(payload.get("orb_position_command")),
        "orb_position_command_target_side": _safe_str(payload.get("orb_position_command_target_side")),
        "orb_position_command_status": _safe_str(payload.get("orb_position_command_status")),
        "orb_position_command_request": payload.get("orb_position_command_request") or {},
        "orb_position_command_overlay_runtime_owns_execution": bool(
            payload.get("orb_position_command_overlay_runtime_owns_execution")
        ),
        "grants_execution_authority": bool(payload.get("grants_execution_authority")),
        "grants_mutation_authority": bool(payload.get("grants_mutation_authority")),
    }


def _write_receipt(payload: dict[str, Any]) -> dict[str, Any]:
    receipt_id = f"chatgpt-voice-{_safe_str(payload.get('decision'), 'recorded')}-{_digest(payload)}"
    created_ts = _now()
    governance = _honesty(
        read_only=False,
        writes_receipt=True,
        forwards_to_chat=bool(payload.get("chat_forward_requested")) and bool(payload.get("chat_forwarded")),
    )
    if bool(payload.get("orb_position_command_detected")):
        governance.update(
            {
                "writes_overlay_position_command_request": True,
                "bounded_overlay_position_mutation": True,
                "mutation_authority_scope": "runtime_overlay_position_only",
                "overlay_runtime_owns_execution": True,
            }
        )
    receipt = {
        "kind": f"{CHATGPT_VOICE_BRIDGE_KIND}.receipt",
        "receipt_id": receipt_id,
        "id": receipt_id,
        "created_ts": created_ts,
        "created_at": _utc_iso_from_ts(created_ts),
        **payload,
        "governance": governance,
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
    mcp_server_transport: str = "",
    client_origin: str = "",
) -> dict[str, Any]:
    route = "/chatgpt-voice/ingress"
    clean_actor = _safe_str(actor) or "chatgpt.voice"
    decision = _permission(clean_actor, required_scope=CHATGPT_VOICE_BRIDGE_WRITE_SCOPE, route=route, method="POST")
    if not decision.allowed:
        return _permission_denied(decision, kind=f"{CHATGPT_VOICE_BRIDGE_KIND}.ingress")

    bounded_transcript = _bounded_text(transcript, max_chars=MAX_TRANSCRIPT_CHARS)
    redacted_transcript = redact_secret_text(bounded_transcript)
    clean_ingress_transport = _bounded_text(ingress_transport, max_chars=64) or CHATGPT_VOICE_BRIDGE_HTTP_TRANSPORT
    clean_mcp_gateway_tool = _bounded_text(mcp_gateway_tool, max_chars=96)
    clean_mcp_server_tool = _bounded_text(mcp_server_tool, max_chars=96)
    clean_mcp_server_transport = _bounded_text(mcp_server_transport, max_chars=64)
    clean_client_origin = _bounded_text(client_origin, max_chars=96)
    clean_source = _bounded_text(source, max_chars=96) or "chatgpt.voice"
    if not clean_client_origin:
        if clean_source == "chatgpt.voice" and clean_mcp_server_tool == CHATGPT_VOICE_BRIDGE_MCP_SERVER_TOOL:
            clean_client_origin = CHATGPT_VOICE_BRIDGE_CHATGPT_APP_VOICE_CLIENT
        elif (
            clean_ingress_transport == CHATGPT_VOICE_BRIDGE_MCP_GATEWAY_TRANSPORT
            or clean_mcp_gateway_tool
            or clean_mcp_server_tool
        ):
            clean_client_origin = CHATGPT_VOICE_BRIDGE_MCP_CLIENT_UNSPECIFIED
    base_payload: dict[str, Any] = {
        "actor": clean_actor,
        "source": clean_source,
        "ingress_transport": clean_ingress_transport,
        "mcp_gateway_tool": clean_mcp_gateway_tool,
        "mcp_server_tool": clean_mcp_server_tool,
        "mcp_server_transport": clean_mcp_server_transport,
        "client_origin": clean_client_origin,
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
        orb_voice_bridge = _write_virtual_voice_turn(
            base_payload=base_payload,
            decision="rejected",
            reason=transcript_rejection_reason,
            reply=reply,
            reply_source="bridge.transcript_guard",
            chat_forwarded=False,
            chat_status="rejected",
        )
        receipt = _write_receipt(
            {
                **base_payload,
                "decision": "rejected",
                "reason": transcript_rejection_reason,
                "orb_voice_bridge": _virtual_voice_summary(orb_voice_bridge),
            }
        )
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
            "orb_voice_bridge": orb_voice_bridge,
            "governance": _honesty(read_only=False, writes_receipt=True),
        }

    orb_position_command = _resolve_orb_position_command(redacted_transcript)
    if bool(orb_position_command.get("recognized")):
        command_request = _write_orb_position_command_request(
            base_payload=base_payload,
            command=orb_position_command,
            transcript_text=redacted_transcript,
            chat_forward_requested=bool(forward_to_chat),
        )
        command_summary = _orb_position_command_summary(command_request)
        command_payload = {
            **base_payload,
            "chat_forward_requested": False,
            "orb_position_command_detected": True,
            "orb_position_command_request": command_summary,
            "orb_position_command": _safe_str(orb_position_command.get("command")),
            "orb_position_command_target_side": _safe_str(orb_position_command.get("target_side")),
            "orb_position_command_status": "queued_for_overlay_runtime",
            "orb_position_command_authority_scope": "runtime_overlay_position_only",
            "orb_position_command_overlay_runtime_owns_execution": True,
        }
        target_side = _safe_str(orb_position_command.get("target_side"))
        reply = f"I queued the orb move to the {target_side} side."
        reply_source = "bridge.orb_position_command_queued"
        orb_voice_bridge = _write_virtual_voice_turn(
            base_payload=command_payload,
            decision="recorded",
            reply=reply,
            reply_source=reply_source,
            chat_forwarded=False,
            chat_status="suppressed_orb_position_command",
        )
        governance = {
            **_honesty(read_only=False, writes_receipt=True),
            "writes_overlay_position_command_request": True,
            "bounded_overlay_position_mutation": True,
            "mutation_authority_scope": "runtime_overlay_position_only",
            "overlay_runtime_owns_execution": True,
        }
        receipt = _write_receipt(
            {
                **command_payload,
                "decision": "recorded",
                "chat_forwarded": False,
                "chat_forward_status": "suppressed_orb_position_command",
                "chat_forward_error": "",
                "reply": reply,
                "reply_source": reply_source,
                "orb_position_command_request": command_summary,
                "orb_voice_bridge": _virtual_voice_summary(orb_voice_bridge),
            }
        )
        return {
            "kind": f"{CHATGPT_VOICE_BRIDGE_KIND}.ingress",
            "ok": True,
            "status": "orb_position_command_queued",
            "reply": reply,
            "voice_response": _voice_response(text=reply, source=reply_source),
            "receipt": receipt,
            "chat_forward": {
                "requested": bool(forward_to_chat),
                "forwarded": False,
                "status": "suppressed_orb_position_command",
                "error": "",
                "response": {},
            },
            "orb_position_command": command_summary,
            "orb_voice_bridge": orb_voice_bridge,
            "governance": governance,
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
    reply, reply_truncated = _limit_speakable_reply(reply)
    base_payload["chat_reply_max_speakable_chars"] = MAX_SPEAKABLE_REPLY_CHARS
    base_payload["chat_reply_truncated_for_voice"] = bool(reply_truncated)
    base_payload["chat_reply_sentence_aware_limit"] = True

    orb_voice_bridge = _write_virtual_voice_turn(
        base_payload=base_payload,
        decision="recorded",
        reply=reply,
        reply_source=reply_source,
        chat_forwarded=chat_forwarded,
        chat_status=chat_status,
        chat_error=chat_error,
        chat_response=chat_response,
    )
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
            "chat_reply_max_speakable_chars": MAX_SPEAKABLE_REPLY_CHARS,
            "chat_reply_truncated_for_voice": bool(reply_truncated),
            "chat_reply_sentence_aware_limit": True,
            "orb_voice_bridge": _virtual_voice_summary(orb_voice_bridge),
        }
    )
    status = "forwarded" if chat_forwarded else "recorded_not_forwarded" if forward_to_chat else "recorded"
    return {
        "kind": f"{CHATGPT_VOICE_BRIDGE_KIND}.ingress",
        "ok": chat_forwarded or not forward_to_chat,
        "status": status,
        "reply": reply,
        "voice_response": _voice_response(text=reply, source=reply_source, text_truncated=reply_truncated),
        "receipt": receipt,
        "chat_forward": {
            "requested": bool(forward_to_chat),
            "forwarded": chat_forwarded,
            "status": chat_status,
            "error": chat_error,
            "response": chat_response,
        },
        "orb_voice_bridge": orb_voice_bridge,
        "governance": _honesty(read_only=False, writes_receipt=True, forwards_to_chat=chat_forwarded),
    }


def record_chatgpt_voice_mcp_probe(
    *,
    actor: str = "",
    source: str = "chatgpt.voice",
    client_origin: str = "",
    reason: str = "",
    ingress_transport: str = CHATGPT_VOICE_BRIDGE_MCP_GATEWAY_TRANSPORT,
    mcp_gateway_tool: str = CHATGPT_VOICE_BRIDGE_MCP_PROOF_GATEWAY_TOOL,
    mcp_server_tool: str = CHATGPT_VOICE_BRIDGE_MCP_PROOF_SERVER_TOOL,
    mcp_server_transport: str = "",
) -> dict[str, Any]:
    route = "/chatgpt-voice/mcp-proof"
    clean_actor = _safe_str(actor) or "chatgpt.voice"
    decision = _permission(clean_actor, required_scope=CHATGPT_VOICE_BRIDGE_WRITE_SCOPE, route=route, method="POST")
    if not decision.allowed:
        return _permission_denied(decision, kind=f"{CHATGPT_VOICE_BRIDGE_KIND}.mcp_proof")

    clean_source = _bounded_text(source, max_chars=96) or "chatgpt.voice"
    clean_ingress_transport = (
        _bounded_text(ingress_transport, max_chars=64) or CHATGPT_VOICE_BRIDGE_MCP_GATEWAY_TRANSPORT
    )
    clean_mcp_gateway_tool = (
        _bounded_text(mcp_gateway_tool, max_chars=96) or CHATGPT_VOICE_BRIDGE_MCP_PROOF_GATEWAY_TOOL
    )
    clean_mcp_server_tool = _bounded_text(mcp_server_tool, max_chars=96) or CHATGPT_VOICE_BRIDGE_MCP_PROOF_SERVER_TOOL
    clean_mcp_server_transport = _bounded_text(mcp_server_transport, max_chars=64)
    clean_client_origin = _bounded_text(client_origin, max_chars=96)
    if not clean_client_origin:
        if clean_source == "chatgpt.voice" and clean_mcp_server_tool == CHATGPT_VOICE_BRIDGE_MCP_PROOF_SERVER_TOOL:
            clean_client_origin = CHATGPT_VOICE_BRIDGE_CHATGPT_APP_VOICE_CLIENT
        elif clean_ingress_transport == CHATGPT_VOICE_BRIDGE_MCP_GATEWAY_TRANSPORT or clean_mcp_gateway_tool:
            clean_client_origin = CHATGPT_VOICE_BRIDGE_MCP_CLIENT_UNSPECIFIED

    reply = "Francis MCP voice bridge is reachable. No transcript was recorded."
    orb_voice_bridge = {
        "status": "mcp_connection_proof_recorded",
        "virtual_voice_turn": False,
        "francis_identity": "Francis",
        "francis_surfaces": ["voice", "lens", "orb"],
        "orb_role": "embodiment",
        "orb_is_embodiment": True,
        "voice_lens_orb_are_separate_identities": False,
        "voice_lens_orb_are_francis_surfaces": True,
        "client_origin": clean_client_origin,
        "mcp_ingress": True,
        "mcp_connection_proof": True,
        "mcp_server_transport": clean_mcp_server_transport,
        "mcp_server_transport_verified": bool(clean_mcp_server_transport),
        "public_mcp_connector_transport": clean_mcp_server_transport == CHATGPT_VOICE_BRIDGE_PUBLIC_CONNECTOR_TRANSPORT,
        "local_overlay_speech_started": False,
        "microphone_recognition_claimed": False,
        "raw_audio": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
    }
    receipt = _write_receipt(
        {
            "actor": clean_actor,
            "source": clean_source,
            "client_origin": clean_client_origin,
            "ingress_transport": clean_ingress_transport,
            "mcp_gateway_tool": clean_mcp_gateway_tool,
            "mcp_server_tool": clean_mcp_server_tool,
            "mcp_server_transport": clean_mcp_server_transport,
            "decision": "recorded",
            "proof_kind": "mcp_connection",
            "reason": _bounded_text(reason, max_chars=160),
            "transcript": "",
            "transcript_char_count": 0,
            "transcript_truncated": False,
            "chat_forward_requested": False,
            "chat_forwarded": False,
            "chat_forward_status": "not_requested",
            "chat_forward_error": "",
            "reply": reply,
            "reply_source": "bridge.mcp_connection_proof",
            "orb_voice_bridge": orb_voice_bridge,
        }
    )
    return {
        "kind": f"{CHATGPT_VOICE_BRIDGE_KIND}.mcp_proof",
        "ok": True,
        "status": "recorded",
        "reply": reply,
        "voice_response": _voice_response(text=reply, source="bridge.mcp_connection_proof"),
        "receipt": receipt,
        "chat_forward": {
            "requested": False,
            "forwarded": False,
            "status": "not_requested",
            "error": "",
            "response": {},
        },
        "orb_voice_bridge": orb_voice_bridge,
        "governance": _honesty(read_only=False, writes_receipt=True),
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
    "CHATGPT_VOICE_BRIDGE_MCP_INGRESS_DESCRIPTION",
    "CHATGPT_VOICE_BRIDGE_MCP_GATEWAY_TOOL",
    "CHATGPT_VOICE_BRIDGE_MCP_GATEWAY_TRANSPORT",
    "CHATGPT_VOICE_BRIDGE_ORB_POSITION_COMMAND_RECEIPTS",
    "CHATGPT_VOICE_BRIDGE_ORB_POSITION_COMMAND_REQUEST",
    "CHATGPT_VOICE_BRIDGE_MCP_PROOF_DESCRIPTION",
    "CHATGPT_VOICE_BRIDGE_MCP_PROOF_GATEWAY_TOOL",
    "CHATGPT_VOICE_BRIDGE_MCP_PROOF_SERVER_TOOL",
    "CHATGPT_VOICE_BRIDGE_MCP_SERVER_TOOL",
    "CHATGPT_VOICE_BRIDGE_READ_SCOPE",
    "CHATGPT_VOICE_BRIDGE_WRITE_SCOPE",
    "chatgpt_voice_bridge_contract",
    "chatgpt_voice_bridge_receipts",
    "record_chatgpt_voice_ingress",
    "record_chatgpt_voice_mcp_probe",
]
