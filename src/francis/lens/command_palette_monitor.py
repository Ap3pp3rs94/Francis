from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from francis.governance.redaction import redact_secret_text
from francis.kernel.paths import data_dir

LENS_COMMAND_PALETTE_MONITOR_STATUS_KIND = "francis.lens.command_palette.monitor_readback"

_MAX_TEXT = 512
_MAX_ITEMS = 12
_MONITOR_HEARTBEAT_FRESH_SECONDS = 120


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_str(value: Any, default: str = "", *, max_length: int = _MAX_TEXT) -> str:
    if value is None:
        return default
    try:
        text = str(value).strip()
    except Exception:
        return default
    if not text:
        return default
    redacted = redact_secret_text(text)
    return redacted[:max_length]


def _safe_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    return default


def _safe_int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            return default
    return default


def _safe_string_list(value: Any, *, limit: int = _MAX_ITEMS, max_length: int = 160) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value[:limit]:
        text = _safe_str(item, max_length=max_length)
        if text:
            out.append(text)
    return out


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        if not path.is_file():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _monitor_status_path() -> Path:
    return data_dir() / "runtime" / "lens-command-palette-monitor" / "status.json"


def _monitor_anomaly_log_path() -> Path:
    return data_dir() / "runtime" / "lens-command-palette-monitor" / "anomalies.jsonl"


def _fresh_iso_timestamp(value: Any, *, max_age_seconds: int = _MONITOR_HEARTBEAT_FRESH_SECONDS) -> bool:
    text = _safe_str(value, max_length=80)
    if not text:
        return False
    try:
        observed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return False
    if observed.tzinfo is None:
        observed = observed.replace(tzinfo=UTC)
    age = (datetime.now(UTC) - observed.astimezone(UTC)).total_seconds()
    return 0 <= age <= max_age_seconds


def _check(value: Any) -> dict[str, Any]:
    raw = _as_dict(value)
    return {
        "id": _safe_str(raw.get("id"), max_length=120),
        "passed": _safe_bool(raw.get("passed")),
        "status": _safe_str(raw.get("status"), max_length=120),
        "evidence": _safe_str(raw.get("evidence"), max_length=240),
    }


def _checks(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [_check(item) for item in value[:_MAX_ITEMS]]


def _bridge(value: Any) -> dict[str, Any]:
    raw = _as_dict(value)
    return {
        "ok": _safe_bool(raw.get("ok")),
        "readback_ready": _safe_bool(raw.get("readback_ready")),
        "local_open_available": _safe_bool(raw.get("local_open_available")),
        "route": _safe_str(raw.get("route"), max_length=160),
        "local_surface": _safe_str(raw.get("local_surface"), max_length=160),
        "command_total": _safe_int(raw.get("command_total")),
        "availability": _safe_str(raw.get("availability"), max_length=120),
        "observed_blockers": _safe_string_list(raw.get("observed_blockers")),
    }


def _mcp_proof(value: Any) -> dict[str, Any]:
    raw = _as_dict(value)
    return {
        "status": _safe_str(raw.get("status"), "not_checked", max_length=120),
        "proof_observed": _safe_bool(raw.get("proof_observed")),
        "freshness_window_seconds": _safe_int(raw.get("freshness_window_seconds")),
        "chatgpt_source_receipt_count": _safe_int(raw.get("chatgpt_source_receipt_count")),
        "any_mcp_server_receipt_count": _safe_int(raw.get("any_mcp_server_receipt_count")),
        "fresh_any_mcp_server_receipt_count": _safe_int(raw.get("fresh_any_mcp_server_receipt_count")),
        "latest_any_mcp_server_receipt_id": _safe_str(
            raw.get("latest_any_mcp_server_receipt_id"),
            max_length=160,
        ),
        "latest_any_mcp_server_receipt_source": _safe_str(
            raw.get("latest_any_mcp_server_receipt_source"),
            max_length=120,
        ),
        "latest_any_mcp_server_receipt_client_origin": _safe_str(
            raw.get("latest_any_mcp_server_receipt_client_origin"),
            max_length=160,
        ),
        "mcp_server_receipt_count": _safe_int(raw.get("mcp_server_receipt_count")),
        "usable_mcp_server_receipt_count": _safe_int(raw.get("usable_mcp_server_receipt_count")),
        "fresh_usable_mcp_server_receipt_count": _safe_int(raw.get("fresh_usable_mcp_server_receipt_count")),
        "latest_chatgpt_source_receipt_id": _safe_str(raw.get("latest_chatgpt_source_receipt_id"), max_length=160),
        "latest_mcp_server_receipt_id": _safe_str(raw.get("latest_mcp_server_receipt_id"), max_length=160),
        "latest_fresh_usable_mcp_server_receipt_id": _safe_str(
            raw.get("latest_fresh_usable_mcp_server_receipt_id"),
            max_length=160,
        ),
        "latest_mcp_transcript_unavailable": _safe_bool(raw.get("latest_mcp_transcript_unavailable")),
        "transcript_redacted_from_summary": True,
        "required_actor": _safe_str(raw.get("required_actor"), "chatgpt.voice", max_length=120),
        "required_source": _safe_str(raw.get("required_source"), "chatgpt.voice", max_length=120),
        "required_ingress_transport": _safe_str(
            raw.get("required_ingress_transport"),
            "mcp_gateway_tool",
            max_length=120,
        ),
        "required_mcp_gateway_tool": _safe_str(
            raw.get("required_mcp_gateway_tool"),
            "francis.chatgpt_voice.ingress",
            max_length=160,
        ),
        "required_mcp_server_tool": _safe_str(
            raw.get("required_mcp_server_tool"),
            "francis_chatgpt_voice_ingress",
            max_length=160,
        ),
        "next_operator_step": _safe_str(raw.get("next_operator_step"), max_length=200),
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
    }


def _voice_monitor(value: Any) -> dict[str, Any]:
    raw = _as_dict(value)
    return {
        "enabled": _safe_bool(raw.get("enabled")),
        "ok": _safe_bool(raw.get("ok")),
        "selected_provider": _safe_str(raw.get("selected_provider"), max_length=120),
        "active_provider_configured": _safe_bool(raw.get("active_provider_configured")),
        "selected_voice": _safe_str(raw.get("selected_voice"), max_length=120),
        "voice_label": _safe_str(raw.get("voice_label"), max_length=120),
        "voice_identity_ok": _safe_bool(raw.get("voice_identity_ok")),
        "generic_voice_label_observed": _safe_bool(raw.get("generic_voice_label_observed")),
        "overlay_status": _safe_str(raw.get("overlay_status"), max_length=120),
        "overlay_ready": _safe_bool(raw.get("overlay_ready")),
        "overlay_voice_status": _safe_str(raw.get("overlay_voice_status"), max_length=120),
        "voice_status": _safe_str(raw.get("voice_status"), max_length=120),
        "voice_turn_status": _safe_str(raw.get("voice_turn_status"), max_length=120),
        "api_permission_denied_observed": _safe_bool(raw.get("api_permission_denied_observed")),
        "recent_receipt_count": _safe_int(raw.get("recent_receipt_count")),
        "denied_recent_receipt_count": _safe_int(raw.get("denied_recent_receipt_count")),
        "latest_receipt_denied": _safe_bool(raw.get("latest_receipt_denied")),
        "latest_receipt_status": _safe_str(raw.get("latest_receipt_status"), max_length=120),
        "latest_receipt_chat_forward_status": _safe_str(
            raw.get("latest_receipt_chat_forward_status"),
            max_length=120,
        ),
        "latest_receipt_chat_forward_error": _safe_str(
            raw.get("latest_receipt_chat_forward_error"),
            max_length=200,
        ),
        "latest_receipt_id": _safe_str(raw.get("latest_receipt_id"), max_length=160),
        "latest_receipt_actor": _safe_str(raw.get("latest_receipt_actor"), max_length=120),
        "latest_receipt_source": _safe_str(raw.get("latest_receipt_source"), max_length=120),
        "latest_receipt_client_origin": _safe_str(raw.get("latest_receipt_client_origin"), max_length=160),
        "latest_receipt_ingress_transport": _safe_str(
            raw.get("latest_receipt_ingress_transport"),
            max_length=120,
        ),
        "latest_receipt_mcp_gateway_tool": _safe_str(
            raw.get("latest_receipt_mcp_gateway_tool"),
            max_length=160,
        ),
        "latest_receipt_mcp_server_tool": _safe_str(raw.get("latest_receipt_mcp_server_tool"), max_length=160),
        "latest_receipt_counts_as_chatgpt_mcp_proof": _safe_bool(
            raw.get("latest_receipt_counts_as_chatgpt_mcp_proof"),
        ),
        "latest_receipt_proof_rejection_reason": _safe_str(
            raw.get("latest_receipt_proof_rejection_reason"),
            max_length=180,
        ),
        "chatgpt_mcp_proof": _mcp_proof(raw.get("chatgpt_mcp_proof")),
        "status_path": "data/runtime/lens-overlay/status.json",
        "voice_status_path": "data/runtime/lens-overlay/voice-status.json",
        "voice_turn_status_path": "data/runtime/lens-overlay/voice-turn-status.json",
        "receipt_root": "data/integrations/chatgpt_voice/receipts",
        "governance": {
            "read_only_contract": True,
            "controls_overlay": False,
            "captures_audio": False,
            "captures_screen": False,
            "execution_authority": False,
            "mutation_authority_granted": False,
        },
    }


def _connector_monitor(value: Any) -> dict[str, Any]:
    raw = _as_dict(value)
    return {
        "enabled": _safe_bool(raw.get("enabled")),
        "ok": _safe_bool(raw.get("ok")),
        "status": _safe_str(raw.get("status"), max_length=120),
        "connector_url_present": _safe_bool(raw.get("connector_url_present")),
        "connector_url_host": _safe_str(raw.get("connector_url_host"), max_length=180),
        "connector_url_source": _safe_str(raw.get("connector_url_source"), max_length=120),
        "connector_shape_valid": _safe_bool(raw.get("connector_shape_valid")),
        "connector_usable_for_chatgpt": _safe_bool(raw.get("connector_usable_for_chatgpt")),
        "expected_tool_present": _safe_bool(raw.get("expected_tool_present")),
        "local_listener_ready": _safe_bool(raw.get("local_listener_ready")),
        "mcp_launcher_alive": _safe_bool(raw.get("mcp_launcher_alive")),
        "public_tunnel_process_alive": _safe_bool(raw.get("public_tunnel_process_alive")),
        "known_localtunnel": _safe_bool(raw.get("known_localtunnel")),
        "persistent_candidate": _safe_bool(raw.get("persistent_candidate")),
        "persistent_ingress_status": _safe_str(raw.get("persistent_ingress_status"), max_length=120),
        "blockers": _safe_string_list(raw.get("blockers")),
        "next_operator_step": _safe_str(raw.get("next_operator_step"), max_length=200),
        "governance": {
            "read_only_contract": True,
            "starts_process": False,
            "opens_public_tunnel": False,
            "writes_repo": False,
            "writes_data": False,
            "captures_audio": False,
            "captures_screen": False,
            "execution_authority": False,
            "mutation_authority_granted": False,
        },
    }


def _persistent_ingress_plan(value: Any) -> dict[str, Any]:
    raw = _as_dict(value)
    providers = _as_dict(raw.get("providers"))
    return {
        "enabled": _safe_bool(raw.get("enabled")),
        "ok": _safe_bool(raw.get("ok")),
        "status": _safe_str(raw.get("status"), max_length=120),
        "blockers": _safe_string_list(raw.get("blockers")),
        "recommended_provider_order": _safe_string_list(raw.get("recommended_provider_order")),
        "next_operator_steps": _safe_string_list(raw.get("next_operator_steps")),
        "providers": {
            "cloudflared_named_tunnel_available": _safe_bool(providers.get("cloudflared_named_tunnel_available")),
            "ngrok_reserved_domain_available": _safe_bool(providers.get("ngrok_reserved_domain_available")),
            "caddy_reverse_proxy_available": _safe_bool(providers.get("caddy_reverse_proxy_available")),
            "ssh_reverse_tunnel_available": _safe_bool(providers.get("ssh_reverse_tunnel_available")),
            "winget_available": _safe_bool(providers.get("winget_available")),
        },
        "governance_safe": _safe_bool(raw.get("governance_safe")),
        "governance": {
            "read_only_contract": True,
            "starts_process": False,
            "opens_public_tunnel": False,
            "writes_repo": False,
            "writes_data": False,
            "captures_audio": False,
            "captures_screen": False,
            "execution_authority": False,
            "mutation_authority_granted": False,
        },
    }


def lens_command_palette_monitor_status() -> dict[str, Any]:
    path = _monitor_status_path()
    raw = _read_json(path)
    if raw is None:
        return {
            "ok": False,
            "kind": LENS_COMMAND_PALETTE_MONITOR_STATUS_KIND,
            "status": "missing",
            "source_kind": "",
            "monitor_process_alive": False,
            "monitor_heartbeat_fresh": False,
            "anomaly_count": 0,
            "anomalies": [],
            "checks": [],
            "bridge": _bridge({}),
            "voice_monitor": _voice_monitor({}),
            "chatgpt_connector_monitor": _connector_monitor({}),
            "chatgpt_persistent_ingress_plan_monitor": _persistent_ingress_plan({}),
            "reporting": {
                "status_path": "data/runtime/lens-command-palette-monitor/status.json",
                "anomaly_log_path": "data/runtime/lens-command-palette-monitor/anomalies.jsonl",
            },
            "governance": {
                "read_only_contract": True,
                "execution_authority": False,
                "mutation_authority_granted": False,
                "captures_audio": False,
                "captures_screen": False,
            },
        }

    return {
        "ok": _safe_bool(raw.get("ok")),
        "kind": LENS_COMMAND_PALETTE_MONITOR_STATUS_KIND,
        "source_kind": _safe_str(raw.get("kind"), max_length=160),
        "status": _safe_str(raw.get("status"), "unknown", max_length=120),
        "mode": _safe_str(raw.get("mode"), max_length=80),
        "checked_at": _safe_str(raw.get("checked_at"), max_length=80),
        "monitor_pid": _safe_int(raw.get("monitor_pid")) or _safe_int(raw.get("pid")),
        "monitor_heartbeat_fresh": _fresh_iso_timestamp(raw.get("checked_at")),
        "monitor_process_alive": _safe_bool(
            raw.get("monitor_process_alive"),
            (_safe_int(raw.get("monitor_pid")) or _safe_int(raw.get("pid"))) > 0
            and _fresh_iso_timestamp(raw.get("checked_at")),
        ),
        "command_palette_url": _safe_str(raw.get("command_palette_url"), max_length=240),
        "api_base_url": _safe_str(raw.get("api_base_url"), max_length=160),
        "chat_ui_base_url": _safe_str(raw.get("chat_ui_base_url"), max_length=160),
        "anomaly_count": _safe_int(raw.get("anomaly_count")),
        "anomalies": _checks(raw.get("anomalies")),
        "checks": _checks(raw.get("checks")),
        "bridge": _bridge(raw.get("bridge")),
        "voice_monitor": _voice_monitor(raw.get("voice_monitor")),
        "chatgpt_connector_monitor": _connector_monitor(raw.get("chatgpt_connector_monitor")),
        "chatgpt_persistent_ingress_plan_monitor": _persistent_ingress_plan(
            raw.get("chatgpt_persistent_ingress_plan_monitor"),
        ),
        "reporting": {
            "status_path": "data/runtime/lens-command-palette-monitor/status.json",
            "anomaly_log_path": "data/runtime/lens-command-palette-monitor/anomalies.jsonl",
            "status_file_present": path.is_file(),
            "anomaly_log_present": _monitor_anomaly_log_path().is_file(),
        },
        "governance": {
            "read_only_contract": True,
            "opens_browser": False,
            "registers_hotkey": False,
            "controls_overlay": False,
            "execution_authority": False,
            "mutation_authority_granted": False,
            "memory_write": False,
            "captures_screen": False,
            "captures_audio": False,
            "hidden_sensing": False,
        },
    }


__all__ = ["LENS_COMMAND_PALETTE_MONITOR_STATUS_KIND", "lens_command_palette_monitor_status"]
