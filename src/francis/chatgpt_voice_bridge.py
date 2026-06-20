from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from francis.governance.api_permission_gate import ApiPermissionDecision, ApiPermissionGate
from francis.governance.redaction import redact_governed_display_value, redact_secret_text
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
CHATGPT_VOICE_BRIDGE_OUTPUT_PROVIDER = "chatgpt_voice_client"
CHATGPT_VOICE_BRIDGE_OUTPUT_MODE = "client_text_reply"
CHATGPT_VOICE_BRIDGE_OUTPUT_PROVIDER_STATUS = "client_speaks_top_level_reply"
CHATGPT_VOICE_BRIDGE_PROVIDER_STATE = "client_text_reply_no_provider_call"
CHATGPT_VOICE_BRIDGE_RECEIPTS = "data/integrations/chatgpt_voice/receipts"
CHATGPT_VOICE_BRIDGE_PROVIDER_STATE_TAXONOMY = [
    CHATGPT_VOICE_BRIDGE_PROVIDER_STATE,
    "live_provider_receipt",
    "mock_provider_receipt",
    "fixture_provider_receipt",
    "replay_provider_receipt",
    "provider_unavailable",
    "provider_unconfigured",
]
CHATGPT_VOICE_BRIDGE_PROVIDER_CALL_MODES = [
    "live_provider_receipt",
    "mock_provider_receipt",
    "fixture_provider_receipt",
    "replay_provider_receipt",
]
CHATGPT_VOICE_BRIDGE_PROVIDER_STATUS_MODES = [
    "provider_unavailable",
    "provider_unconfigured",
]
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


def _bounded_redacted_text(value: Any, *, max_chars: int) -> str:
    return redact_secret_text(_bounded_text(value, max_chars=max_chars))


def _redacted_field_names(fields: dict[str, tuple[Any, str, int]]) -> list[str]:
    names: list[str] = []
    for name, (raw_value, clean_value, max_chars) in fields.items():
        bounded = _bounded_text(raw_value, max_chars=max_chars)
        if bounded and clean_value != bounded:
            names.append(name)
    return sorted(names)


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
        "voice_output_provider": CHATGPT_VOICE_BRIDGE_OUTPUT_PROVIDER,
        "voice_output_mode": CHATGPT_VOICE_BRIDGE_OUTPUT_MODE,
        "voice_output_provider_status": CHATGPT_VOICE_BRIDGE_OUTPUT_PROVIDER_STATUS,
        "voice_provider_state": CHATGPT_VOICE_BRIDGE_PROVIDER_STATE,
        "voice_provider_state_source": "chatgpt_voice_bridge_static_boundary",
        "voice_provider_receipt_mode": CHATGPT_VOICE_BRIDGE_PROVIDER_STATE,
        "voice_provider_receipt_mode_source": "chatgpt_voice_bridge_static_boundary",
        "voice_provider_receipt_mode_is_provider_call": False,
        "live_voice_provider_call": False,
        "mock_voice_provider_call": False,
        "fixture_voice_provider_call": False,
        "replay_voice_provider_call": False,
        "voice_provider_unavailable": False,
        "voice_provider_unconfigured": False,
        "elevenlabs_provider_invoked": False,
        "elevenlabs_audio_claimed": False,
        "voice_provider_receipt": _voice_provider_receipt(),
        "voice_substrate_proof": _voice_substrate_proof(),
        "raw_audio": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
    }


def _voice_provider_receipt() -> dict[str, Any]:
    mode_state = _voice_provider_mode_state()
    return {
        "state": CHATGPT_VOICE_BRIDGE_PROVIDER_STATE,
        "state_source": "chatgpt_voice_bridge_static_boundary",
        "state_basis": "bridge_returns_text_for_client_speech",
        "receipt_mode": CHATGPT_VOICE_BRIDGE_PROVIDER_STATE,
        "receipt_mode_source": "chatgpt_voice_bridge_static_boundary",
        "receipt_mode_taxonomy": CHATGPT_VOICE_BRIDGE_PROVIDER_STATE_TAXONOMY,
        "receipt_mode_is_provider_call": False,
        "client_text_reply": True,
        "provider_status_observed": False,
        "provider_status_observation_source": "not_observed_bridge_did_not_call_provider",
        "provider_boundary_evidence_location": "embedded_bridge_receipt",
        "external_provider_receipt_present": False,
        "external_provider_receipt_path": "",
        "external_provider_receipt_required_for_provider_call_modes": True,
        "live_provider_call": False,
        "mock_provider_call": False,
        "fixture_provider_call": False,
        "replay_provider_call": False,
        "provider_unavailable": False,
        "provider_unconfigured": False,
        "provider_unavailable_status_claimed": False,
        "provider_unconfigured_status_claimed": False,
        "provider_unavailable_and_unconfigured_distinct": True,
        "live_mock_fixture_replay_are_mutually_exclusive": True,
        "mode_disambiguation": mode_state,
        "elevenlabs": {
            "operator_preferred_provider": True,
            "configuration_driven": True,
            "bridge_invokes_provider": False,
            "bridge_claims_audio": False,
            "live_use_requires_provider_receipt": True,
            "direct_orb_control": False,
            "orb_animation_coupled_to_provider": False,
        },
    }


def _voice_provider_mode_state(
    mode: str = "",
    *,
    transcript_state: str = "not_applicable",
) -> dict[str, Any]:
    clean_mode = _safe_str(mode) or CHATGPT_VOICE_BRIDGE_PROVIDER_STATE
    mode_recognized = clean_mode in CHATGPT_VOICE_BRIDGE_PROVIDER_STATE_TAXONOMY
    active_modes = [clean_mode] if mode_recognized else []
    live_provider_call = clean_mode == "live_provider_receipt"
    mock_provider_call = clean_mode == "mock_provider_receipt"
    fixture_provider_call = clean_mode == "fixture_provider_receipt"
    replay_provider_call = clean_mode == "replay_provider_receipt"
    provider_unavailable = clean_mode == "provider_unavailable"
    provider_unconfigured = clean_mode == "provider_unconfigured"
    external_provider_receipt_required = clean_mode in (
        CHATGPT_VOICE_BRIDGE_PROVIDER_CALL_MODES + CHATGPT_VOICE_BRIDGE_PROVIDER_STATUS_MODES
    )
    provider_call_count = sum(
        [
            live_provider_call,
            mock_provider_call,
            fixture_provider_call,
            replay_provider_call,
        ]
    )
    return {
        "kind": "francis.voice.provider_mode_state.v1",
        "mode": clean_mode,
        "mode_recognized": mode_recognized,
        "taxonomy": CHATGPT_VOICE_BRIDGE_PROVIDER_STATE_TAXONOMY,
        "provider_call_modes": CHATGPT_VOICE_BRIDGE_PROVIDER_CALL_MODES,
        "provider_status_modes": CHATGPT_VOICE_BRIDGE_PROVIDER_STATUS_MODES,
        "active_modes": active_modes,
        "inactive_modes": [item for item in CHATGPT_VOICE_BRIDGE_PROVIDER_STATE_TAXONOMY if item not in active_modes],
        "active_mode_count": len(active_modes),
        "client_text_reply_no_provider_call": clean_mode == CHATGPT_VOICE_BRIDGE_PROVIDER_STATE,
        "provider_receipt_mode_is_provider_call": clean_mode in CHATGPT_VOICE_BRIDGE_PROVIDER_CALL_MODES,
        "live_provider_call": live_provider_call,
        "mock_provider_call": mock_provider_call,
        "fixture_provider_call": fixture_provider_call,
        "replay_provider_call": replay_provider_call,
        "provider_unavailable": provider_unavailable,
        "provider_unconfigured": provider_unconfigured,
        "provider_call_count": provider_call_count,
        "provider_modes_mutually_exclusive": len(active_modes) <= 1,
        "live_mock_fixture_replay_are_mutually_exclusive": provider_call_count <= 1,
        "provider_unavailable_and_unconfigured_distinct": True,
        "provider_unavailable_and_unconfigured_mutually_exclusive": not (
            provider_unavailable and provider_unconfigured
        ),
        "external_provider_receipt_required": external_provider_receipt_required,
        "external_provider_receipt_present": False,
        "transcript_state": transcript_state,
        "transcript_unavailable_is_not_provider_unavailable": True,
        "provider_state_inferred_from_transcript": False,
        "provider_state_inferred_from_missing_configuration": False,
        "non_client_mode_requires_external_provider_receipt": True,
    }


def _voice_output_boundary() -> dict[str, Any]:
    mode_state = _voice_provider_mode_state()
    return {
        "voice_output_provider": CHATGPT_VOICE_BRIDGE_OUTPUT_PROVIDER,
        "voice_output_mode": CHATGPT_VOICE_BRIDGE_OUTPUT_MODE,
        "voice_output_provider_status": CHATGPT_VOICE_BRIDGE_OUTPUT_PROVIDER_STATUS,
        "voice_provider_state": CHATGPT_VOICE_BRIDGE_PROVIDER_STATE,
        "voice_provider_state_source": "chatgpt_voice_bridge_static_boundary",
        "voice_provider_receipt_mode": CHATGPT_VOICE_BRIDGE_PROVIDER_STATE,
        "voice_provider_receipt_mode_source": "chatgpt_voice_bridge_static_boundary",
        "voice_provider_receipt_mode_is_provider_call": False,
        "voice_output_transport": "chatgpt_voice_client_reply",
        "client_speaks_top_level_reply": True,
        "live_voice_provider_call": False,
        "mock_voice_provider_call": False,
        "fixture_voice_provider_call": False,
        "replay_voice_provider_call": False,
        "voice_provider_unavailable": False,
        "voice_provider_unconfigured": False,
        "voice_provider_unavailable_status_claimed": False,
        "voice_provider_unconfigured_status_claimed": False,
        "elevenlabs_provider_invoked": False,
        "elevenlabs_audio_claimed": False,
        "overlay_audio_claimed": False,
        "voice_provider_receipt": _voice_provider_receipt(),
        "voice_provider_mode_disambiguation": mode_state,
        "voice_substrate_proof": _voice_substrate_proof(),
        "provider_boundary": {
            "bridge_calls_live_voice_provider": False,
            "bridge_calls_mock_voice_provider": False,
            "bridge_uses_fixture_voice_provider": False,
            "bridge_replays_voice_provider_output": False,
            "bridge_claims_provider_unavailable": False,
            "bridge_claims_provider_unconfigured": False,
            "elevenlabs_called_by_bridge": False,
            "elevenlabs_live_use_requires_provider_receipt": True,
            "provider_unavailable_and_unconfigured_distinct": True,
            "live_mock_fixture_replay_are_mutually_exclusive": True,
            "chatgpt_client_speaks_top_level_reply": True,
            "bridge_provider_receipt_mode": CHATGPT_VOICE_BRIDGE_PROVIDER_STATE,
            "bridge_provider_receipt_mode_is_provider_call": False,
            "bridge_provider_receipt_mode_taxonomy": CHATGPT_VOICE_BRIDGE_PROVIDER_STATE_TAXONOMY,
            "bridge_provider_call_modes": CHATGPT_VOICE_BRIDGE_PROVIDER_CALL_MODES,
            "bridge_provider_status_modes": CHATGPT_VOICE_BRIDGE_PROVIDER_STATUS_MODES,
            "bridge_provider_mode_disambiguation": mode_state,
        },
    }


def _transcript_state(*, decision: str, reason: str, transcript: str) -> str:
    if reason == "transcript_unavailable":
        return "transcript_unavailable_rejected"
    if reason == "transcript_required":
        return "transcript_required_rejected"
    if decision == "recorded" and transcript:
        return "redacted_transcript_recorded"
    if decision:
        return "no_transcript_recorded"
    return "not_applicable"


def _voice_substrate_proof(
    payload: dict[str, Any] | None = None,
    *,
    bridge_receipt_id: str = "",
    bridge_receipt_path: str = "",
) -> dict[str, Any]:
    payload = payload or {}
    raw_orb_voice_bridge = payload.get("orb_voice_bridge")
    orb_voice_bridge: dict[str, Any] = raw_orb_voice_bridge if isinstance(raw_orb_voice_bridge, dict) else {}
    raw_command_request = payload.get("orb_position_command_request")
    command_request: dict[str, Any] = raw_command_request if isinstance(raw_command_request, dict) else {}
    provider_receipt_mode = _safe_str(
        payload.get("voice_provider_receipt_mode"),
        CHATGPT_VOICE_BRIDGE_PROVIDER_STATE,
    )
    voice_turn_receipt_path = _safe_str(
        payload.get("voice_turn_receipt_path") or orb_voice_bridge.get("voice_turn_receipt_path")
    )
    orb_position_command_receipt_path = _safe_str(command_request.get("request_receipt_path"))
    transcript = _safe_str(payload.get("transcript"))
    decision = _safe_str(payload.get("decision"))
    reason = _safe_str(payload.get("reason"))
    bridge_receipt_present = bool(bridge_receipt_id or bridge_receipt_path)
    virtual_voice_turn_present = bool(voice_turn_receipt_path)
    orb_command_present = bool(command_request)
    transcript_state = _transcript_state(decision=decision, reason=reason, transcript=transcript)
    mode_state = _voice_provider_mode_state(provider_receipt_mode, transcript_state=transcript_state)
    return {
        "kind": "francis.voice.substrate_proof.v1",
        "bridge": CHATGPT_VOICE_BRIDGE_VERSION,
        "decision": decision,
        "reason": reason,
        "transcript_state": transcript_state,
        "transcript_redacted": True,
        "raw_audio": False,
        "accepts_audio_stream": False,
        "voice_enters_francis": True,
        "voice_turn_is_virtual": True,
        "bridge_receipt_id": bridge_receipt_id,
        "bridge_receipt_path": bridge_receipt_path,
        "voice_turn_receipt_path": voice_turn_receipt_path,
        "orb_position_command_receipt_path": orb_position_command_receipt_path,
        "structured_receipts": {
            "bridge_ingress_receipt": bridge_receipt_present,
            "virtual_voice_turn_receipt": virtual_voice_turn_present,
            "provider_boundary_receipt": True,
            "orb_position_command_request_receipt": orb_command_present,
        },
        "provider_receipt_mode": provider_receipt_mode,
        "provider_receipt_mode_taxonomy": CHATGPT_VOICE_BRIDGE_PROVIDER_STATE_TAXONOMY,
        "provider_call_modes": CHATGPT_VOICE_BRIDGE_PROVIDER_CALL_MODES,
        "provider_status_modes": CHATGPT_VOICE_BRIDGE_PROVIDER_STATUS_MODES,
        "provider_taxonomy_enforced": True,
        "provider_receipt_mode_is_provider_call": mode_state["provider_receipt_mode_is_provider_call"],
        "provider_mode_disambiguation": mode_state,
        "provider_boundary_receipt_embedded": True,
        "provider_boundary_evidence_location": "embedded_bridge_receipt",
        "external_provider_receipt_present": False,
        "external_provider_receipt_path": "",
        "external_provider_receipt_required": bool(mode_state["external_provider_receipt_required"]),
        "external_provider_receipt_required_for_provider_call_modes": True,
        "output_provider_call_claimed": False,
        "live_voice_provider_call": False,
        "mock_voice_provider_call": False,
        "fixture_voice_provider_call": False,
        "replay_voice_provider_call": False,
        "voice_provider_unavailable": False,
        "voice_provider_unconfigured": False,
        "provider_unavailable_and_unconfigured_distinct": True,
        "elevenlabs_provider_invoked": False,
        "elevenlabs_audio_claimed": False,
        "elevenlabs_live_use_requires_provider_receipt": True,
        "voice_controls_orb_directly": False,
        "bridge_queues_overlay_request": orb_command_present,
        "overlay_receipt_required_for_applied_state": orb_command_present,
        "orb_applied_state_claimed_by_bridge": False,
        "substrate_governance_bypass": False,
        "mission_governance_bypass": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
    }


def _receipt_linkage(
    payload: dict[str, Any],
    *,
    bridge_receipt_id: str,
    bridge_receipt_path: str,
) -> dict[str, Any]:
    raw_orb_voice_bridge = payload.get("orb_voice_bridge")
    orb_voice_bridge: dict[str, Any] = raw_orb_voice_bridge if isinstance(raw_orb_voice_bridge, dict) else {}
    raw_command_request = payload.get("orb_position_command_request")
    command_request: dict[str, Any] = raw_command_request if isinstance(raw_command_request, dict) else {}
    provider_receipt_mode = _safe_str(
        payload.get("voice_provider_receipt_mode"),
        CHATGPT_VOICE_BRIDGE_PROVIDER_STATE,
    )
    voice_turn_receipt_path = _safe_str(
        payload.get("voice_turn_receipt_path") or orb_voice_bridge.get("voice_turn_receipt_path")
    )
    orb_position_command_receipt_path = _safe_str(command_request.get("request_receipt_path"))
    transcript = _safe_str(payload.get("transcript"))
    decision = _safe_str(payload.get("decision"))
    reason = _safe_str(payload.get("reason"))
    transcript_state = _transcript_state(decision=decision, reason=reason, transcript=transcript)
    mode_state = _voice_provider_mode_state(provider_receipt_mode, transcript_state=transcript_state)
    return {
        "kind": "francis.voice.receipt_linkage.v1",
        "bridge_receipt": {
            "present": True,
            "id": bridge_receipt_id,
            "path": bridge_receipt_path,
        },
        "virtual_voice_turn_receipt": {
            "present": bool(voice_turn_receipt_path),
            "path": voice_turn_receipt_path,
            "virtual_voice_turn": bool(orb_voice_bridge.get("virtual_voice_turn")),
        },
        "provider_boundary_receipt": {
            "present": True,
            "embedded": True,
            "evidence_location": "embedded_bridge_receipt",
            "path": bridge_receipt_path,
            "external_provider_receipt_present": False,
            "external_provider_receipt_path": "",
            "external_provider_receipt_required": bool(mode_state["external_provider_receipt_required"]),
            "external_provider_receipt_required_for_provider_call_modes": True,
            "mode": provider_receipt_mode,
            "mode_is_provider_call": mode_state["provider_receipt_mode_is_provider_call"],
            "mode_taxonomy": CHATGPT_VOICE_BRIDGE_PROVIDER_STATE_TAXONOMY,
            "mode_disambiguation": mode_state,
            "provider_status_observed": False,
            "live_provider_call": False,
            "mock_provider_call": False,
            "fixture_provider_call": False,
            "replay_provider_call": False,
            "provider_unavailable": False,
            "provider_unconfigured": False,
            "provider_unavailable_and_unconfigured_distinct": True,
            "elevenlabs_provider_invoked": False,
            "elevenlabs_audio_claimed": False,
            "elevenlabs_live_use_requires_provider_receipt": True,
        },
        "orb_position_command_request_receipt": {
            "present": bool(orb_position_command_receipt_path),
            "path": orb_position_command_receipt_path,
            "overlay_receipt_required_for_applied_state": bool(orb_position_command_receipt_path),
            "applied_state_claimed_by_bridge": False,
            "voice_controls_orb_directly": False,
        },
        "transcript_state": transcript_state,
        "redaction": {
            "transcript_redacted": True,
            "metadata_secrets_redacted": bool(payload.get("metadata_secrets_redacted")),
            "redacted_metadata_fields": payload.get("redacted_metadata_fields") or [],
            "raw_audio": False,
        },
        "authority": {
            "voice_controls_orb_directly": False,
            "substrate_governance_bypass": False,
            "mission_governance_bypass": False,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
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


def _orb_position_substrate_boundary() -> dict[str, Any]:
    return {
        "governed_bridge_contract": "chatgpt_voice_orb_position_command_request",
        "voice_controls_orb_directly": False,
        "bridge_writes_overlay_command_request": True,
        "overlay_runtime_owns_position_mutation": True,
        "applied_state_requires_overlay_receipt": True,
        "orb_applied_state_claimed_by_bridge": False,
        "direct_desktop_control": False,
        "raw_shell": False,
        "raw_input": False,
        "orb_visual_change_allowed": False,
        "orb_visual_lock_preserved": True,
        "substrate_governance_bypass": False,
        "mission_governance_bypass": False,
        "mutation_authority_scope": "runtime_overlay_position_only",
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
    }


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
        "substrate_boundary": _orb_position_substrate_boundary(),
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
            "substrate_governance_bypass": False,
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
        "substrate_boundary": payload.get("substrate_boundary") or {},
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
            "bridge_receipt_root": CHATGPT_VOICE_BRIDGE_RECEIPTS,
            "metadata_secrets_redacted_field": "metadata_secrets_redacted",
            "redacted_metadata_fields_field": "redacted_metadata_fields",
            "receipt_readback_redacts_secret_patterns": True,
            "voice_substrate_proof_field": "voice_substrate_proof",
            "receipt_linkage_field": "receipt_linkage",
            "voice_output_provider_field": "voice_output_provider",
            "voice_output_provider_status_field": "voice_output_provider_status",
            "voice_provider_state_field": "voice_provider_state",
            "voice_provider_receipt_field": "voice_provider_receipt",
            "voice_provider_receipt_mode_field": "voice_provider_receipt_mode",
            "voice_provider_state_taxonomy": CHATGPT_VOICE_BRIDGE_PROVIDER_STATE_TAXONOMY,
            "voice_provider_receipt_mode_taxonomy": CHATGPT_VOICE_BRIDGE_PROVIDER_STATE_TAXONOMY,
            "voice_provider_call_modes": CHATGPT_VOICE_BRIDGE_PROVIDER_CALL_MODES,
            "voice_provider_status_modes": CHATGPT_VOICE_BRIDGE_PROVIDER_STATUS_MODES,
            "voice_provider_mode_disambiguation_field": "voice_provider_mode_disambiguation",
            "voice_provider_receipt_modes_are_mutually_exclusive": True,
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
            "orb_position_command_substrate_boundary": _orb_position_substrate_boundary(),
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
            "voice_output_provider": CHATGPT_VOICE_BRIDGE_OUTPUT_PROVIDER,
            "voice_output_mode": CHATGPT_VOICE_BRIDGE_OUTPUT_MODE,
            "voice_output_provider_status": CHATGPT_VOICE_BRIDGE_OUTPUT_PROVIDER_STATUS,
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
        "output_provider_boundary": {
            **_voice_output_boundary(),
            "note": "ChatGPT voice bridge returns text for the client to speak; it does not invoke ElevenLabs or overlay audio.",
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
        "speech_output_owner": CHATGPT_VOICE_BRIDGE_OUTPUT_PROVIDER,
        **_voice_output_boundary(),
        "local_overlay_speech_started": False,
        "speech_started": False,
        "speech_playback_async": False,
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
        "voice_substrate_proof": _voice_substrate_proof(
            {
                **base_payload,
                "decision": decision,
                "reason": reason,
                "chat_forwarded": chat_forwarded,
                "voice_turn_receipt_path": f"{CHATGPT_VOICE_BRIDGE_VIRTUAL_TURN_RECEIPTS}/{turn_id}.json",
            }
        ),
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
        "voice_output_provider": _safe_str(payload.get("voice_output_provider")),
        "voice_output_mode": _safe_str(payload.get("voice_output_mode")),
        "voice_output_provider_status": _safe_str(payload.get("voice_output_provider_status")),
        "voice_provider_receipt_mode": _safe_str(payload.get("voice_provider_receipt_mode")),
        "voice_substrate_proof": payload.get("voice_substrate_proof") or {},
        "live_voice_provider_call": bool(payload.get("live_voice_provider_call")),
        "mock_voice_provider_call": bool(payload.get("mock_voice_provider_call")),
        "fixture_voice_provider_call": bool(payload.get("fixture_voice_provider_call")),
        "replay_voice_provider_call": bool(payload.get("replay_voice_provider_call")),
        "voice_provider_unavailable": bool(payload.get("voice_provider_unavailable")),
        "voice_provider_unconfigured": bool(payload.get("voice_provider_unconfigured")),
        "elevenlabs_provider_invoked": bool(payload.get("elevenlabs_provider_invoked")),
        "elevenlabs_audio_claimed": bool(payload.get("elevenlabs_audio_claimed")),
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
    bridge_receipt_path = f"{CHATGPT_VOICE_BRIDGE_RECEIPTS}/{receipt_id}.json"
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
        "voice_substrate_proof": _voice_substrate_proof(
            payload,
            bridge_receipt_id=receipt_id,
            bridge_receipt_path=bridge_receipt_path,
        ),
        "receipt_linkage": _receipt_linkage(
            payload,
            bridge_receipt_id=receipt_id,
            bridge_receipt_path=bridge_receipt_path,
        ),
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
    clean_ingress_transport = (
        _bounded_redacted_text(ingress_transport, max_chars=64) or CHATGPT_VOICE_BRIDGE_HTTP_TRANSPORT
    )
    clean_mcp_gateway_tool = _bounded_redacted_text(mcp_gateway_tool, max_chars=96)
    clean_mcp_server_tool = _bounded_redacted_text(mcp_server_tool, max_chars=96)
    clean_mcp_server_transport = _bounded_redacted_text(mcp_server_transport, max_chars=64)
    clean_client_origin = _bounded_redacted_text(client_origin, max_chars=96)
    clean_source = _bounded_redacted_text(source, max_chars=96) or "chatgpt.voice"
    if not clean_client_origin:
        if clean_source == "chatgpt.voice" and clean_mcp_server_tool == CHATGPT_VOICE_BRIDGE_MCP_SERVER_TOOL:
            clean_client_origin = CHATGPT_VOICE_BRIDGE_CHATGPT_APP_VOICE_CLIENT
        elif (
            clean_ingress_transport == CHATGPT_VOICE_BRIDGE_MCP_GATEWAY_TRANSPORT
            or clean_mcp_gateway_tool
            or clean_mcp_server_tool
        ):
            clean_client_origin = CHATGPT_VOICE_BRIDGE_MCP_CLIENT_UNSPECIFIED
    clean_conversation_id = _bounded_redacted_text(conversation_id, max_chars=160)
    clean_turn_id = _bounded_redacted_text(turn_id, max_chars=160)
    clean_locale = _bounded_redacted_text(locale, max_chars=32)
    redacted_metadata_fields = _redacted_field_names(
        {
            "source": (source, clean_source, 96),
            "ingress_transport": (ingress_transport, clean_ingress_transport, 64),
            "mcp_gateway_tool": (mcp_gateway_tool, clean_mcp_gateway_tool, 96),
            "mcp_server_tool": (mcp_server_tool, clean_mcp_server_tool, 96),
            "mcp_server_transport": (mcp_server_transport, clean_mcp_server_transport, 64),
            "client_origin": (client_origin, clean_client_origin, 96),
            "conversation_id": (conversation_id, clean_conversation_id, 160),
            "turn_id": (turn_id, clean_turn_id, 160),
            "locale": (locale, clean_locale, 32),
        }
    )
    base_payload: dict[str, Any] = {
        "actor": clean_actor,
        "source": clean_source,
        "ingress_transport": clean_ingress_transport,
        "mcp_gateway_tool": clean_mcp_gateway_tool,
        "mcp_server_tool": clean_mcp_server_tool,
        "mcp_server_transport": clean_mcp_server_transport,
        "client_origin": clean_client_origin,
        "conversation_id": clean_conversation_id,
        "turn_id": clean_turn_id,
        "locale": clean_locale,
        "transcript": redacted_transcript,
        "transcript_char_count": len(redacted_transcript),
        "transcript_truncated": len(_safe_str(transcript)) > MAX_TRANSCRIPT_CHARS,
        "chat_forward_requested": bool(forward_to_chat),
        "use_llm_requested": bool(use_llm),
        "secrets_redacted": redacted_transcript != bounded_transcript or bool(redacted_metadata_fields),
        "metadata_secrets_redacted": bool(redacted_metadata_fields),
        "redacted_metadata_fields": redacted_metadata_fields,
        **_voice_output_boundary(),
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
                voice_turn_id=_bounded_text(clean_turn_id, max_chars=96),
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

    clean_source = _bounded_redacted_text(source, max_chars=96) or "chatgpt.voice"
    clean_ingress_transport = (
        _bounded_redacted_text(ingress_transport, max_chars=64) or CHATGPT_VOICE_BRIDGE_MCP_GATEWAY_TRANSPORT
    )
    clean_mcp_gateway_tool = (
        _bounded_redacted_text(mcp_gateway_tool, max_chars=96) or CHATGPT_VOICE_BRIDGE_MCP_PROOF_GATEWAY_TOOL
    )
    clean_mcp_server_tool = (
        _bounded_redacted_text(mcp_server_tool, max_chars=96) or CHATGPT_VOICE_BRIDGE_MCP_PROOF_SERVER_TOOL
    )
    clean_mcp_server_transport = _bounded_redacted_text(mcp_server_transport, max_chars=64)
    clean_client_origin = _bounded_redacted_text(client_origin, max_chars=96)
    if not clean_client_origin:
        if clean_source == "chatgpt.voice" and clean_mcp_server_tool == CHATGPT_VOICE_BRIDGE_MCP_PROOF_SERVER_TOOL:
            clean_client_origin = CHATGPT_VOICE_BRIDGE_CHATGPT_APP_VOICE_CLIENT
        elif clean_ingress_transport == CHATGPT_VOICE_BRIDGE_MCP_GATEWAY_TRANSPORT or clean_mcp_gateway_tool:
            clean_client_origin = CHATGPT_VOICE_BRIDGE_MCP_CLIENT_UNSPECIFIED

    clean_reason = _bounded_redacted_text(reason, max_chars=160)
    redacted_metadata_fields = _redacted_field_names(
        {
            "source": (source, clean_source, 96),
            "ingress_transport": (ingress_transport, clean_ingress_transport, 64),
            "mcp_gateway_tool": (mcp_gateway_tool, clean_mcp_gateway_tool, 96),
            "mcp_server_tool": (mcp_server_tool, clean_mcp_server_tool, 96),
            "mcp_server_transport": (mcp_server_transport, clean_mcp_server_transport, 64),
            "client_origin": (client_origin, clean_client_origin, 96),
            "reason": (reason, clean_reason, 160),
        }
    )
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
            "reason": clean_reason,
            "secrets_redacted": bool(redacted_metadata_fields),
            "metadata_secrets_redacted": bool(redacted_metadata_fields),
            "redacted_metadata_fields": redacted_metadata_fields,
            "transcript": "",
            "transcript_char_count": 0,
            "transcript_truncated": False,
            "chat_forward_requested": False,
            "chat_forwarded": False,
            "chat_forward_status": "not_requested",
            "chat_forward_error": "",
            "reply": reply,
            "reply_source": "bridge.mcp_connection_proof",
            **_voice_output_boundary(),
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
                redacted_item = redact_governed_display_value(item)
                if isinstance(redacted_item, dict):
                    redacted_item["receipt_path"] = str(path)
                    receipts.append(redacted_item)
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
