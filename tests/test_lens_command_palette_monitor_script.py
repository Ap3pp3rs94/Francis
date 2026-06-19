from __future__ import annotations

import json
import os
import shutil
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from powershell_script_runner import run_powershell_script


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "lens-command-palette-monitor.ps1"


def _powershell() -> str:
    exe = shutil.which("powershell") or shutil.which("pwsh")
    assert exe is not None, "PowerShell is required for script tests"
    return exe


def _run_monitor(*args: str):
    return run_powershell_script(
        _powershell(),
        SCRIPT,
        list(args),
        cwd=ROOT,
        timeout_seconds=45,
    )


def _lens_status(*, command_total: int = 2) -> dict[str, object]:
    commands = [
        {"id": "voice_status", "label": "Voice status"},
        {"id": "open_lens", "label": "Open Lens"},
    ][:command_total]
    return {
        "ok": True,
        "kind": "lens.status",
        "command_palette": {
            "status": "readback_ready",
            "availability": "local_ui",
            "route": "/lens/status",
            "local_surface": "lens.status.command_palette",
            "url_entrypoint_ready": True,
            "url_entrypoint": {
                "kind": "lens.command_palette.url_entrypoint",
                "status": "ready",
                "route": "/?francis_lens=command_palette",
                "local_surface": "chat_ui.command_palette",
                "opens_palette_in_chat_ui": True,
                "requires_running_chat_ui": True,
                "os_level_command_palette": False,
                "summon_anywhere": False,
                "global_hotkey": False,
            },
            "commands": commands,
            "command_total": command_total,
            "summon_anywhere": False,
        },
    }


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_overlay_voice_runtime(data_dir: Path, *, selected_voice: str = "Emma", voice_label: str = "Emma") -> None:
    runtime_dir = data_dir / "runtime" / "lens-overlay"
    runtime_dir.mkdir(parents=True)
    pid = os.getpid()
    (runtime_dir / "lens-overlay.pid").write_text(str(pid), encoding="utf-8")
    _write_json(
        runtime_dir / "status.json",
        {
            "kind": "lens.overlay.runtime_state",
            "status": "overlay_running",
            "pid": pid,
            "overlay_name": "Francis Lens Overlay",
            "overlay_scope": "user_session",
            "overlay_window_visible": True,
            "always_on_top": True,
            "overlay_voice": {
                "kind": "lens.overlay.voice.runtime",
                "status": "listening",
                "ok": True,
                "voice_provider": "ElevenLabs",
                "selected_voice": selected_voice,
                "voice_lens_orb_identity": "Francis",
                "voice_lens_orb_are_francis_surfaces": True,
                "voice_lens_orb_are_separate_identities": False,
                "microphone_capture": True,
                "microphone_input_effective": True,
                "microphone_signal_status": "signal_observed",
                "wake_listening": True,
                "wake_phrase": "hey francis",
                "continuous_voice_chat": True,
                "continuous_voice_chat_mode": "enabled_no_wake_phrase_required",
                "continuous_voice_chat_self_trigger_guard": (
                    "suppress_all_except_francis_stop_while_owned_speech_process_active"
                ),
                "microphone_gate_while_speaking": "francis_stop_only",
                "conversation_forwarding_while_speaking": False,
            },
            "voice": {
                "kind": "lens.overlay.voice.runtime",
                "status": "spoken",
                "ok": True,
                "voice_provider": "ElevenLabs",
                "selected_voice": selected_voice,
            },
            "voice_provider_readiness": {
                "kind": "lens.overlay.voice.provider_readiness",
                "selected_provider": "ElevenLabs",
                "active_provider_configured": True,
                "elevenlabs": {
                    "configured": True,
                    "api_key_present": True,
                    "voice_id_present": True,
                    "voice_label": voice_label,
                    "credential_values_redacted": True,
                    "missing_configuration": [],
                },
                "stores_secret": False,
                "logs_text_payload": False,
            },
            "overlay_position": {
                "status": "visible_position_observed",
                "left": 1268.0,
                "top": 644.0,
                "operator_position_anchor": "",
                "voice_position_command_active": False,
                "grants_execution_authority": False,
                "grants_mutation_authority": False,
            },
        },
    )


def _json_stdout(stdout: str) -> dict[str, object]:
    return json.loads(stdout)


def test_lens_command_palette_monitor_bounds_connector_child_readbacks() -> None:
    script = SCRIPT.read_text(encoding="utf-8")

    assert "function Invoke-PowerShellJsonChild" in script
    assert "$Process.WaitForExit($BoundedTimeoutSeconds * 1000)" in script
    assert "Stop-Process -Id $Process.Id -Force" in script
    assert "connector_status_readback_timeout" in script
    assert "persistent_ingress_plan_readback_timeout" in script
    assert "timed_out = [bool](Get-PropertyValue -Payload $Readback -Name 'timed_out'" in script


class _CommandPaletteHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        body = b'<!doctype html><html><body><div id="root"></div></body></html>'
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return None


class _LocalCommandPaletteServer:
    def __enter__(self) -> str:
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), _CommandPaletteHandler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        port = self._server.server_address[1]
        return f"http://127.0.0.1:{port}/?francis_lens=command_palette"

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self._server.shutdown()
        self._thread.join(timeout=5)
        self._server.server_close()


def test_lens_command_palette_monitor_probe_records_healthy_status(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    status_path = tmp_path / "lens-status.json"
    _write_json(status_path, _lens_status())

    with _LocalCommandPaletteServer() as url:
        proc = _run_monitor(
            "-Mode",
            "Probe",
            "-DataDir",
            str(data_dir),
            "-CommandPaletteUrl",
            url,
            "-LensStatusPath",
            str(status_path),
            "-TimeoutSeconds",
            "3",
        )

    assert proc.returncode == 0, proc.stderr
    payload = _json_stdout(proc.stdout)
    assert payload["ok"] is True
    assert payload["status"] == "healthy"
    assert payload["anomaly_count"] == 0
    assert payload["bridge"]["readback_ready"] is True
    assert payload["bridge"]["route"] == "/?francis_lens=command_palette"
    assert payload["bridge"]["local_surface"] == "chat_ui.command_palette"
    assert payload["bridge"]["command_total"] == 2
    assert payload["governance"]["read_only_contract"] is True
    assert payload["governance"]["execution_authority"] is False
    assert payload["governance"]["mutation_authority_granted"] is False

    recorded_status = data_dir / "runtime" / "lens-command-palette-monitor" / "status.json"
    assert recorded_status.exists()
    assert json.loads(recorded_status.read_text(encoding="utf-8"))["status"] == "healthy"
    anomaly_log = data_dir / "runtime" / "lens-command-palette-monitor" / "anomalies.jsonl"
    assert not anomaly_log.exists()


def test_lens_command_palette_monitor_reports_chatgpt_connector_localtunnel_fallback(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    status_path = tmp_path / "lens-status.json"
    _write_json(status_path, _lens_status())

    with _LocalCommandPaletteServer() as url:
        proc = _run_monitor(
            "-Mode",
            "Probe",
            "-DataDir",
            str(data_dir),
            "-CommandPaletteUrl",
            url,
            "-LensStatusPath",
            str(status_path),
            "-EnableChatGptConnectorChecks",
            "-ChatGptConnectorUrl",
            "https://francis-voice-178175.loca.lt/mcp",
            "-TimeoutSeconds",
            "3",
        )

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = _json_stdout(proc.stdout)
    connector = payload["chatgpt_connector_monitor"]
    assert connector["enabled"] is True
    assert connector["known_localtunnel"] is True
    assert connector["timed_out"] is False
    assert connector["timeout_seconds"] >= 8
    assert connector["persistent_candidate"] is False
    assert connector["persistent_ingress_status"] == "localtunnel_fallback_replace_needed"
    assert connector["next_operator_step"] == "replace_localtunnel_with_persistent_https_mcp_ingress"
    plan = payload["chatgpt_persistent_ingress_plan_monitor"]
    assert plan["enabled"] is True
    assert plan["timed_out"] is False
    assert plan["timeout_seconds"] >= 8
    assert plan["status"] == "localtunnel_fallback_replace_needed"
    assert plan["blockers"] == ["localtunnel_url_is_not_persistent_ingress"]
    assert plan["recommended_provider_order"][0] == "cloudflared_named_tunnel"
    assert plan["next_operator_steps"] == [
        "choose_or_install_a_persistent_https_ingress_provider",
        "point_provider_to_local_endpoint",
        "record_the_stable_https_mcp_url_with_recordurl",
        "rerun_orb_voice_overlay_lens_validation",
    ]
    handoff = plan["operator_handoff"]
    assert handoff["preferred_provider"] == "cloudflared_named_tunnel"
    assert handoff["stable_url_placeholder"] == "https://YOUR-STABLE-HOST/mcp"
    assert handoff["install_commands"]["cloudflared_winget"].endswith(
        "--accept-source-agreements --accept-package-agreements"
    )
    assert "StartPersistent" in handoff["governed_handoff_commands"]["start_persistent_mcp"]
    assert isinstance(plan["providers"]["winget_available"], bool)
    assert isinstance(plan["providers"]["cloudflared_named_tunnel_path"], str)
    assert isinstance(plan["providers"]["cloudflared_named_tunnel_origin_cert_present"], bool)
    assert plan["providers"]["cloudflared_named_tunnel_origin_cert_content_read"] is False
    assert isinstance(plan["providers"]["cloudflared_named_tunnel_login_required"], bool)
    assert plan["providers"]["cloudflared_named_tunnel_requested"] is False
    assert plan["providers"]["cloudflared_named_tunnel_requested_name"] == ""
    assert plan["providers"]["cloudflared_named_tunnel_requested_hostname"] == ""
    assert plan["providers"]["cloudflared_named_tunnel_preflight_checked"] is False
    assert plan["providers"]["cloudflared_named_tunnel_preflight_output_discarded"] is True
    assert plan["providers"]["cloudflared_named_tunnel_operator_provider_setup_commands"] == []
    assert plan["providers"]["cloudflared_named_tunnel_next_operator_step"] in {
        "run_cloudflared_tunnel_login",
        "create_or_start_cloudflared_named_tunnel",
    }
    assert plan["localtunnel_replacement"]["persistent_ingress_required_for_stable_chatgpt_connector"] is True
    assert plan["governance_safe"] is True
    assert plan["governance"]["read_only_contract"] is True
    assert plan["governance"]["starts_process"] is False
    assert plan["governance"]["opens_public_tunnel"] is False
    assert plan["governance"]["writes_data"] is False
    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["chatgpt_voice_persistent_ingress_plan"]["passed"] is True
    assert "chatgpt_voice_persistent_ingress" not in checks


def test_lens_command_palette_monitor_reports_chatgpt_connector_cloudflared_quick_fallback(
    tmp_path: Path,
) -> None:
    data_dir = tmp_path / "data"
    status_path = tmp_path / "lens-status.json"
    _write_json(status_path, _lens_status())
    _write_json(
        data_dir / "runtime" / "chatgpt-voice-connector" / "status.json",
        {
            "kind": "francis.chatgpt_voice.connector_control.state",
            "status": "cloudflared_login_started",
            "connector_url": "https://example.trycloudflare.com/mcp",
            "connector_url_source": "cloudflared_quick",
            "connector_host": "example.trycloudflare.com",
            "local_endpoint": "http://127.0.0.1:8787/mcp",
            "mcp_launcher_pid": 0,
            "tunnel_pid": 0,
            "cloudflared_login": {
                "status": "cloudflared_login_started",
                "process_id": 0,
                "process_alive": False,
                "provider_login_started": True,
                "provider_login_browser_may_open": True,
                "provider_login_writes_origin_cert": True,
                "origin_cert_present": False,
                "origin_cert_content_read": False,
                "public_tunnel_started": False,
                "connector_url_recorded": False,
            },
            "updated_at": "2026-06-19T00:00:00Z",
        },
    )

    with _LocalCommandPaletteServer() as url:
        proc = _run_monitor(
            "-Mode",
            "Probe",
            "-DataDir",
            str(data_dir),
            "-CommandPaletteUrl",
            url,
            "-LensStatusPath",
            str(status_path),
            "-EnableChatGptConnectorChecks",
            "-ChatGptConnectorUrl",
            "https://example.trycloudflare.com/mcp",
            "-TimeoutSeconds",
            "3",
        )

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = _json_stdout(proc.stdout)
    connector = payload["chatgpt_connector_monitor"]
    assert connector["enabled"] is True
    assert connector["known_localtunnel"] is False
    assert connector["known_cloudflared_quick_tunnel"] is True
    assert connector["timed_out"] is False
    assert connector["timeout_seconds"] >= 8
    assert connector["persistent_candidate"] is False
    assert connector["persistent_ingress_status"] == "cloudflared_quick_tunnel_replace_needed"
    assert connector["next_operator_step"] == "replace_cloudflared_quick_tunnel_with_persistent_https_mcp_ingress"
    assert connector["blockers"] == ["cloudflared_quick_url_is_not_persistent_ingress"]
    plan = payload["chatgpt_persistent_ingress_plan_monitor"]
    assert plan["enabled"] is True
    assert plan["timed_out"] is False
    assert plan["timeout_seconds"] >= 8
    assert plan["status"] == "cloudflared_quick_tunnel_replace_needed"
    assert plan["blockers"] == ["cloudflared_quick_url_is_not_persistent_ingress"]
    providers = plan["providers"]
    assert isinstance(providers["cloudflared_named_tunnel_available"], bool)
    assert isinstance(providers["cloudflared_named_tunnel_path"], str)
    assert isinstance(providers["cloudflared_named_tunnel_origin_cert_present"], bool)
    assert providers["cloudflared_named_tunnel_origin_cert_content_read"] is False
    assert isinstance(providers["cloudflared_named_tunnel_login_required"], bool)
    assert providers["cloudflared_named_tunnel_requested"] is False
    assert providers["cloudflared_named_tunnel_requested_name"] == ""
    assert providers["cloudflared_named_tunnel_requested_hostname"] == ""
    assert providers["cloudflared_named_tunnel_preflight_checked"] is False
    assert providers["cloudflared_named_tunnel_preflight_output_discarded"] is True
    assert providers["cloudflared_named_tunnel_operator_provider_setup_commands"] == []
    assert providers["cloudflared_named_tunnel_next_operator_step"] in {
        "run_cloudflared_tunnel_login",
        "create_or_start_cloudflared_named_tunnel",
    }
    assert providers["cloudflared_login_status"] == "cloudflared_login_started"
    assert providers["cloudflared_login_process_id"] == 0
    assert providers["cloudflared_login_process_alive"] is False
    assert providers["cloudflared_login_provider_started"] is True
    assert providers["cloudflared_login_browser_may_open"] is True
    assert providers["cloudflared_login_writes_origin_cert"] is True
    assert providers["cloudflared_login_origin_cert_present"] is False
    assert providers["cloudflared_login_origin_cert_content_read"] is False
    assert providers["cloudflared_login_public_tunnel_started"] is False
    assert providers["cloudflared_login_connector_url_recorded"] is False
    assert plan["governance_safe"] is True
    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["chatgpt_voice_persistent_ingress_plan"]["passed"] is True
    assert "chatgpt_voice_persistent_ingress" not in checks


def test_lens_command_palette_monitor_passes_cloudflared_named_request_to_plan(
    tmp_path: Path,
) -> None:
    data_dir = tmp_path / "data"
    status_path = tmp_path / "lens-status.json"
    _write_json(status_path, _lens_status())

    with _LocalCommandPaletteServer() as url:
        proc = _run_monitor(
            "-Mode",
            "Probe",
            "-DataDir",
            str(data_dir),
            "-CommandPaletteUrl",
            url,
            "-LensStatusPath",
            str(status_path),
            "-EnableChatGptConnectorChecks",
            "-ChatGptConnectorUrl",
            "https://example.trycloudflare.com/mcp",
            "-CloudflaredTunnelName",
            "francis",
            "-CloudflaredHostname",
            "francis.example.test",
            "-TimeoutSeconds",
            "3",
        )

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = _json_stdout(proc.stdout)
    plan = payload["chatgpt_persistent_ingress_plan_monitor"]
    assert plan["enabled"] is True
    assert plan["governance_safe"] is True
    providers = plan["providers"]
    assert providers["cloudflared_named_tunnel_requested"] is True
    assert providers["cloudflared_named_tunnel_requested_name"] == "francis"
    assert providers["cloudflared_named_tunnel_requested_hostname"] == "francis.example.test"
    assert isinstance(providers["cloudflared_named_tunnel_exists"], bool)
    assert isinstance(providers["cloudflared_named_tunnel_preflight_checked"], bool)
    assert isinstance(providers["cloudflared_named_tunnel_preflight_exists"], bool)
    assert providers["cloudflared_named_tunnel_preflight_output_discarded"] is True
    assert isinstance(providers["cloudflared_named_tunnel_operator_provider_setup_commands"], list)
    assert providers["cloudflared_named_tunnel_next_operator_step"] in {
        "run_cloudflared_tunnel_login",
        "create_cloudflared_named_tunnel_and_route_hostname",
        "start_cloudflared_named_tunnel",
    }


def test_lens_command_palette_monitor_can_require_persistent_chatgpt_ingress(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    status_path = tmp_path / "lens-status.json"
    _write_json(status_path, _lens_status())

    with _LocalCommandPaletteServer() as url:
        proc = _run_monitor(
            "-Mode",
            "Probe",
            "-DataDir",
            str(data_dir),
            "-CommandPaletteUrl",
            url,
            "-LensStatusPath",
            str(status_path),
            "-EnableChatGptConnectorChecks",
            "-ChatGptConnectorUrl",
            "https://francis-voice-178175.loca.lt/mcp",
            "-RequirePersistentChatGptIngress",
            "-TimeoutSeconds",
            "3",
        )

    assert proc.returncode == 1
    payload = _json_stdout(proc.stdout)
    assert payload["status"] == "anomaly"
    connector = payload["chatgpt_connector_monitor"]
    assert connector["persistent_ingress_status"] == "localtunnel_fallback_replace_needed"
    assert connector["blockers"] == ["localtunnel_url_is_not_persistent_ingress"]
    plan = payload["chatgpt_persistent_ingress_plan_monitor"]
    assert plan["status"] == "localtunnel_fallback_replace_needed"
    assert plan["governance_safe"] is True
    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["chatgpt_voice_persistent_ingress_plan"]["passed"] is True
    assert checks["chatgpt_voice_persistent_ingress"]["passed"] is False
    assert checks["chatgpt_voice_persistent_ingress"]["status"] == "localtunnel_fallback_replace_needed"
    assert "chatgpt_voice_persistent_ingress" in {item["id"] for item in payload["anomalies"]}


def test_lens_command_palette_monitor_can_require_persistent_chatgpt_ingress_for_cloudflared_quick(
    tmp_path: Path,
) -> None:
    data_dir = tmp_path / "data"
    status_path = tmp_path / "lens-status.json"
    _write_json(status_path, _lens_status())

    with _LocalCommandPaletteServer() as url:
        proc = _run_monitor(
            "-Mode",
            "Probe",
            "-DataDir",
            str(data_dir),
            "-CommandPaletteUrl",
            url,
            "-LensStatusPath",
            str(status_path),
            "-EnableChatGptConnectorChecks",
            "-ChatGptConnectorUrl",
            "https://example.trycloudflare.com/mcp",
            "-RequirePersistentChatGptIngress",
            "-TimeoutSeconds",
            "3",
        )

    assert proc.returncode == 1
    payload = _json_stdout(proc.stdout)
    assert payload["status"] == "anomaly"
    connector = payload["chatgpt_connector_monitor"]
    assert connector["persistent_ingress_status"] == "cloudflared_quick_tunnel_replace_needed"
    assert connector["blockers"] == ["cloudflared_quick_url_is_not_persistent_ingress"]
    plan = payload["chatgpt_persistent_ingress_plan_monitor"]
    assert plan["status"] == "cloudflared_quick_tunnel_replace_needed"
    assert plan["governance_safe"] is True
    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["chatgpt_voice_persistent_ingress_plan"]["passed"] is True
    assert checks["chatgpt_voice_persistent_ingress"]["passed"] is False
    assert checks["chatgpt_voice_persistent_ingress"]["status"] == "cloudflared_quick_tunnel_replace_needed"
    assert "chatgpt_voice_persistent_ingress" in {item["id"] for item in payload["anomalies"]}


def test_lens_command_palette_monitor_probe_records_voice_health(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    status_path = tmp_path / "lens-status.json"
    _write_json(status_path, _lens_status())
    runtime_dir = data_dir / "runtime" / "lens-overlay"
    runtime_dir.mkdir(parents=True)
    pid = os.getpid()
    (runtime_dir / "lens-overlay.pid").write_text(str(pid), encoding="utf-8")
    _write_json(
        runtime_dir / "status.json",
        {
            "kind": "lens.overlay.runtime_state",
            "status": "overlay_running",
            "pid": pid,
            "overlay_name": "Francis Lens Overlay",
            "overlay_scope": "user_session",
            "overlay_window_visible": True,
            "always_on_top": True,
            "overlay_voice": {
                "kind": "lens.overlay.voice.runtime",
                "status": "listening",
                "ok": True,
                "voice_provider": "ElevenLabs",
                "selected_voice": "Emma",
                "voice_lens_orb_identity": "Francis",
                "voice_lens_orb_are_francis_surfaces": True,
                "voice_lens_orb_are_separate_identities": False,
                "microphone_capture": True,
                "microphone_input_effective": True,
                "microphone_signal_status": "signal_observed",
                "wake_listening": True,
                "wake_phrase": "hey francis",
                "continuous_voice_chat": True,
                "continuous_voice_chat_mode": "enabled_no_wake_phrase_required",
                "continuous_voice_chat_self_trigger_guard": (
                    "suppress_all_except_francis_stop_while_owned_speech_process_active"
                ),
                "microphone_gate_while_speaking": "francis_stop_only",
                "conversation_forwarding_while_speaking": False,
            },
            "voice": {
                "kind": "lens.overlay.voice.runtime",
                "status": "spoken",
                "ok": True,
                "voice_provider": "ElevenLabs",
                "selected_voice": "Emma",
            },
            "voice_provider_readiness": {
                "kind": "lens.overlay.voice.provider_readiness",
                "selected_provider": "ElevenLabs",
                "active_provider_configured": True,
                "elevenlabs": {
                    "configured": True,
                    "api_key_present": True,
                    "voice_id_present": True,
                    "voice_label": "Emma",
                    "credential_values_redacted": True,
                    "missing_configuration": [],
                },
                "stores_secret": False,
                "logs_text_payload": False,
            },
            "overlay_position": {
                "status": "visible_position_observed",
                "left": 1268.0,
                "top": 644.0,
                "operator_position_anchor": "",
                "voice_position_command_active": False,
                "grants_execution_authority": False,
                "grants_mutation_authority": False,
            },
        },
    )

    with _LocalCommandPaletteServer() as url:
        proc = _run_monitor(
            "-Mode",
            "Probe",
            "-DataDir",
            str(data_dir),
            "-CommandPaletteUrl",
            url,
            "-LensStatusPath",
            str(status_path),
            "-EnableVoiceChecks",
            "-VoiceProvider",
            "ElevenLabs",
            "-ElevenLabsVoiceId",
            "56bWURjYFHyYyVf490Dp",
            "-TimeoutSeconds",
            "3",
        )

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = _json_stdout(proc.stdout)
    assert payload["status"] == "healthy"
    assert payload["voice_monitor"]["enabled"] is True
    assert payload["voice_monitor"]["selected_provider"] == "ElevenLabs"
    assert payload["voice_monitor"]["selected_voice"] == "Emma"
    assert payload["voice_monitor"]["voice_label"] == "Emma"
    assert payload["voice_monitor"]["generic_voice_label_observed"] is False
    assert payload["voice_monitor"]["orb_position_command_ready"] is True
    assert payload["voice_monitor"]["orb_position_command_targets"] == ["left", "right"]
    assert payload["voice_monitor"]["orb_position_command_requires_orb_reference"] is True
    assert payload["voice_monitor"]["orb_position_command_requires_direction"] is True
    assert payload["voice_monitor"]["orb_position_command_conversation_forwarding_suppressed"] is True
    assert payload["voice_monitor"]["orb_position_command_authority_scope"] == "runtime_overlay_position_only"
    assert payload["voice_monitor"]["overlay_position_anchor"] == ""
    assert payload["voice_monitor"]["overlay_left"] == 1268
    assert payload["voice_monitor"]["overlay_top"] == 644
    assert payload["voice_monitor"]["voice_position_command_active"] is False
    assert payload["voice_monitor"]["latest_orb_position_command_applied"] is False
    assert payload["voice_monitor"]["wake_listening"] is True
    assert payload["voice_monitor"]["wake_phrase"] == "hey francis"
    assert payload["voice_monitor"]["passive_listen_contract"] == "passive_transcript_awareness_only_until_wake_phrase"
    assert payload["voice_monitor"]["microphone_gate_while_speaking"] == "francis_stop_only"
    assert payload["voice_monitor"]["conversation_forwarding_while_speaking"] is False
    assert payload["voice_monitor"]["interrupt_phrase"] == "francis stop"
    assert payload["voice_monitor"]["api_permission_denied_observed"] is False
    assert payload["voice_monitor"]["denied_recent_receipt_count"] == 0
    assert payload["voice_monitor"]["latest_receipt_denied"] is False
    assert payload["voice_monitor"]["chatgpt_mcp_proof"]["status"] == "awaiting_chatgpt_mcp_tool_call"
    assert payload["voice_monitor"]["chatgpt_mcp_proof"]["proof_observed"] is False
    assert payload["voice_monitor"]["chatgpt_mcp_proof"]["transcript_redacted_from_summary"] is True
    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["voice_overlay_readback"]["status"] == "readback_ready"
    assert checks["voice_overlay_runtime"]["status"] == "visible"
    assert checks["voice_francis_identity"]["status"] == "francis_voice_identity_ready"
    assert checks["voice_passive_listen_contract"]["status"] == "passive_until_wake"
    assert checks["voice_mic_gate_while_speaking"]["status"] == "francis_stop_only"
    assert checks["voice_chat_bridge_denials"]["status"] == "latest_receipt_clean"
    assert "voice_chatgpt_mcp_tool_proof" not in checks
    assert payload["governance"]["captures_audio"] is False


def test_lens_command_palette_monitor_reports_applied_orb_voice_command(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    status_path = tmp_path / "lens-status.json"
    _write_json(status_path, _lens_status())
    _write_overlay_voice_runtime(data_dir)
    runtime_dir = data_dir / "runtime" / "lens-overlay"
    status_payload = json.loads((runtime_dir / "status.json").read_text(encoding="utf-8"))
    status_payload["voice"] = {
        "kind": "lens.overlay.voice.runtime",
        "status": "orb_voice_command_applied",
        "ok": True,
        "local_overlay_command": True,
        "voice_orb_command": True,
        "orb_command": "move_orb_left_side",
        "chat_bridge_status": "not_called",
        "conversation_forwarding_suppressed": True,
        "speech_output_suppressed": True,
        "bounded_overlay_position_mutation": True,
        "mutation_authority_scope": "runtime_overlay_position_only",
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
    }
    status_payload["overlay_position"]["left"] = 48.0
    status_payload["overlay_position"]["operator_position_anchor"] = "voice_command_left_side"
    status_payload["overlay_position"]["voice_position_command_active"] = True
    _write_json(runtime_dir / "status.json", status_payload)

    with _LocalCommandPaletteServer() as url:
        proc = _run_monitor(
            "-Mode",
            "Probe",
            "-DataDir",
            str(data_dir),
            "-CommandPaletteUrl",
            url,
            "-LensStatusPath",
            str(status_path),
            "-EnableVoiceChecks",
            "-VoiceProvider",
            "ElevenLabs",
            "-ElevenLabsVoiceId",
            "56bWURjYFHyYyVf490Dp",
            "-TimeoutSeconds",
            "3",
        )

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = _json_stdout(proc.stdout)
    voice_monitor = payload["voice_monitor"]
    assert voice_monitor["voice_position_command_active"] is True
    assert voice_monitor["overlay_position_anchor"] == "voice_command_left_side"
    assert voice_monitor["latest_orb_position_command"] == "move_orb_left_side"
    assert voice_monitor["latest_orb_position_command_status"] == "orb_voice_command_applied"
    assert voice_monitor["latest_orb_position_command_applied"] is True
    assert voice_monitor["overlay_left"] == 48


def test_lens_command_palette_monitor_can_require_chatgpt_mcp_proof(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    status_path = tmp_path / "lens-status.json"
    _write_json(status_path, _lens_status())
    _write_overlay_voice_runtime(data_dir)

    with _LocalCommandPaletteServer() as url:
        proc = _run_monitor(
            "-Mode",
            "Probe",
            "-DataDir",
            str(data_dir),
            "-CommandPaletteUrl",
            url,
            "-LensStatusPath",
            str(status_path),
            "-EnableVoiceChecks",
            "-VoiceProvider",
            "ElevenLabs",
            "-RequireChatGptMcpProof",
            "-TimeoutSeconds",
            "3",
        )

    assert proc.returncode == 1
    payload = _json_stdout(proc.stdout)
    assert payload["status"] == "anomaly"
    assert payload["voice_monitor"]["chatgpt_mcp_proof"]["status"] == "awaiting_chatgpt_mcp_tool_call"
    assert payload["voice_monitor"]["chatgpt_mcp_proof"]["proof_observed"] is False
    assert payload["voice_monitor"]["chatgpt_mcp_proof"]["mcp_connection_proof_observed"] is False
    assert "voice_chatgpt_mcp_tool_proof" in {item["id"] for item in payload["anomalies"]}
    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["voice_chatgpt_mcp_tool_proof"]["status"] == "missing"
    assert checks["voice_chatgpt_mcp_tool_proof"]["evidence"] == "no_fresh_mcp_connection_receipt"


def test_lens_command_palette_monitor_counts_chatgpt_mcp_probe_as_connection_proof(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    status_path = tmp_path / "lens-status.json"
    _write_json(status_path, _lens_status())
    _write_overlay_voice_runtime(data_dir)
    receipt_dir = data_dir / "integrations" / "chatgpt_voice" / "receipts"
    _write_json(
        receipt_dir / "chatgpt-voice-recorded-probe.json",
        {
            "kind": "francis.chatgpt_voice.bridge.receipt",
            "receipt_id": "chatgpt-voice-recorded-probe",
            "actor": "chatgpt.voice",
            "source": "chatgpt.voice",
            "client_origin": "chatgpt_app_voice",
            "ingress_transport": "mcp_gateway_tool",
            "mcp_gateway_tool": "francis.chatgpt_voice.mcp_probe",
            "mcp_server_tool": "francis_chatgpt_voice_mcp_probe",
            "proof_kind": "mcp_connection",
            "decision": "recorded",
            "chat_forward_status": "not_requested",
            "chat_forward_error": "",
            "chat_forwarded": False,
            "transcript": "",
            "transcript_char_count": 0,
            "reply": "Francis MCP voice bridge is reachable. No transcript was recorded.",
            "reply_source": "bridge.mcp_connection_proof",
        },
    )

    with _LocalCommandPaletteServer() as url:
        proc = _run_monitor(
            "-Mode",
            "Probe",
            "-DataDir",
            str(data_dir),
            "-CommandPaletteUrl",
            url,
            "-LensStatusPath",
            str(status_path),
            "-EnableVoiceChecks",
            "-VoiceProvider",
            "ElevenLabs",
            "-RequireChatGptMcpProof",
            "-TimeoutSeconds",
            "3",
        )

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = _json_stdout(proc.stdout)
    assert payload["status"] == "healthy"
    proof = payload["voice_monitor"]["chatgpt_mcp_proof"]
    assert proof["status"] == "fresh_mcp_connection_proof_observed"
    assert proof["proof_observed"] is False
    assert proof["mcp_connection_proof_observed"] is True
    assert proof["mcp_probe_receipt_count"] == 1
    assert proof["fresh_mcp_probe_receipt_count"] == 1
    assert proof["latest_mcp_connection_proof_receipt_id"] == "chatgpt-voice-recorded-probe"
    assert proof["latest_mcp_connection_proof_tool"] == "francis_chatgpt_voice_mcp_probe"
    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["voice_chatgpt_mcp_tool_proof"]["passed"] is True
    assert checks["voice_chatgpt_mcp_tool_proof"]["status"] == "fresh_observed"
    summary = json.dumps(proof)
    assert "No transcript was recorded" not in summary


def test_lens_command_palette_monitor_flags_missing_overlay_runtime(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    status_path = tmp_path / "lens-status.json"
    _write_json(status_path, _lens_status())

    with _LocalCommandPaletteServer() as url:
        proc = _run_monitor(
            "-Mode",
            "Probe",
            "-DataDir",
            str(data_dir),
            "-CommandPaletteUrl",
            url,
            "-LensStatusPath",
            str(status_path),
            "-EnableVoiceChecks",
            "-VoiceProvider",
            "ElevenLabs",
            "-TimeoutSeconds",
            "3",
        )

    assert proc.returncode == 1
    payload = _json_stdout(proc.stdout)
    assert payload["status"] == "anomaly"
    assert payload["voice_monitor"]["overlay_ready"] is False
    assert "voice_overlay_runtime" in {item["id"] for item in payload["anomalies"]}
    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["voice_overlay_readback"]["status"] == "readback_ready"
    assert checks["voice_overlay_runtime"]["status"] == "overlay_not_ready"


def test_lens_command_palette_monitor_reports_non_chatgpt_mcp_receipt_without_proof(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    status_path = tmp_path / "lens-status.json"
    _write_json(status_path, _lens_status())
    _write_overlay_voice_runtime(data_dir)
    receipt_dir = data_dir / "integrations" / "chatgpt_voice" / "receipts"
    _write_json(
        receipt_dir / "chatgpt-voice-recorded-selftest.json",
        {
            "kind": "francis.chatgpt_voice.bridge.receipt",
            "receipt_id": "chatgpt-voice-recorded-selftest",
            "actor": "chatgpt.voice",
            "source": "local.mcp.selftest",
            "client_origin": "codex_live_mcp_selftest",
            "ingress_transport": "mcp_gateway_tool",
            "mcp_gateway_tool": "francis.chatgpt_voice.ingress",
            "mcp_server_tool": "francis_chatgpt_voice_ingress",
            "decision": "recorded",
            "chat_forward_status": "not_requested",
            "chat_forward_error": "",
            "chat_forwarded": False,
            "transcript": "this local self-test transcript must stay out of monitor summaries",
            "transcript_char_count": 58,
            "reply": "I recorded the transcript for Francis. Chat forwarding was not requested.",
            "reply_source": "bridge.recorded_only",
        },
    )

    with _LocalCommandPaletteServer() as url:
        proc = _run_monitor(
            "-Mode",
            "Probe",
            "-DataDir",
            str(data_dir),
            "-CommandPaletteUrl",
            url,
            "-LensStatusPath",
            str(status_path),
            "-EnableVoiceChecks",
            "-VoiceProvider",
            "ElevenLabs",
            "-RequireChatGptMcpProof",
            "-TimeoutSeconds",
            "3",
        )

    assert proc.returncode == 1
    payload = _json_stdout(proc.stdout)
    assert payload["status"] == "anomaly"
    proof = payload["voice_monitor"]["chatgpt_mcp_proof"]
    assert proof["status"] == "awaiting_chatgpt_mcp_tool_call"
    assert proof["proof_observed"] is False
    assert proof["mcp_connection_proof_observed"] is False
    assert proof["chatgpt_source_receipt_count"] == 0
    assert proof["mcp_server_receipt_count"] == 0
    assert proof["any_mcp_server_receipt_count"] == 1
    assert proof["fresh_any_mcp_server_receipt_count"] == 1
    assert proof["latest_any_mcp_server_receipt_id"] == "chatgpt-voice-recorded-selftest"
    assert proof["latest_any_mcp_server_receipt_source"] == "local.mcp.selftest"
    assert proof["latest_any_mcp_server_receipt_client_origin"] == "codex_live_mcp_selftest"
    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["voice_chatgpt_mcp_tool_proof"]["status"] == "missing"
    assert checks["voice_chatgpt_mcp_tool_proof"]["evidence"] == "no_fresh_mcp_connection_receipt"
    summary = json.dumps(payload["voice_monitor"]["chatgpt_mcp_proof"])
    assert "self-test transcript must stay out" not in summary


def test_lens_command_palette_monitor_records_fresh_chatgpt_mcp_proof(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    status_path = tmp_path / "lens-status.json"
    _write_json(status_path, _lens_status())
    _write_overlay_voice_runtime(data_dir)
    receipt_dir = data_dir / "integrations" / "chatgpt_voice" / "receipts"
    _write_json(
        receipt_dir / "chatgpt-voice-recorded-mcp-test.json",
        {
            "kind": "francis.chatgpt_voice.bridge.receipt",
            "receipt_id": "chatgpt-voice-recorded-mcp-test",
            "actor": "chatgpt.voice",
            "source": "chatgpt.voice",
            "client_origin": "chatgpt_app_voice",
            "ingress_transport": "mcp_gateway_tool",
            "mcp_gateway_tool": "francis.chatgpt_voice.ingress",
            "mcp_server_tool": "francis_chatgpt_voice_ingress",
            "decision": "recorded",
            "chat_forward_status": "forwarded",
            "chat_forward_error": "",
            "chat_forwarded": True,
            "transcript": "this proof transcript must stay out of monitor summaries",
            "transcript_char_count": 57,
            "reply": "I can hear you. Voice input is reaching Francis.",
            "reply_source": "chat_forward.response",
        },
    )

    with _LocalCommandPaletteServer() as url:
        proc = _run_monitor(
            "-Mode",
            "Probe",
            "-DataDir",
            str(data_dir),
            "-CommandPaletteUrl",
            url,
            "-LensStatusPath",
            str(status_path),
            "-EnableVoiceChecks",
            "-VoiceProvider",
            "ElevenLabs",
            "-RequireChatGptMcpProof",
            "-TimeoutSeconds",
            "3",
        )

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = _json_stdout(proc.stdout)
    assert payload["status"] == "healthy"
    proof = payload["voice_monitor"]["chatgpt_mcp_proof"]
    assert proof["status"] == "fresh_usable_mcp_tool_receipt_observed"
    assert proof["proof_observed"] is True
    assert proof["chatgpt_source_receipt_count"] == 1
    assert proof["any_mcp_server_receipt_count"] == 1
    assert proof["fresh_any_mcp_server_receipt_count"] == 1
    assert proof["latest_any_mcp_server_receipt_id"] == "chatgpt-voice-recorded-mcp-test"
    assert proof["latest_any_mcp_server_receipt_source"] == "chatgpt.voice"
    assert proof["mcp_server_receipt_count"] == 1
    assert proof["fresh_usable_mcp_server_receipt_count"] == 1
    assert proof["latest_fresh_usable_mcp_server_receipt_id"] == "chatgpt-voice-recorded-mcp-test"
    assert proof["required_mcp_server_tool"] == "francis_chatgpt_voice_ingress"
    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["voice_chatgpt_mcp_tool_proof"]["status"] == "fresh_observed"
    summary = json.dumps(payload["voice_monitor"]["chatgpt_mcp_proof"])
    assert "proof transcript must stay out" not in summary


def test_lens_command_palette_monitor_probe_writes_anomaly_receipt(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    status_path = tmp_path / "lens-status.json"
    _write_json(status_path, _lens_status(command_total=0))

    with _LocalCommandPaletteServer() as url:
        proc = _run_monitor(
            "-Mode",
            "Probe",
            "-DataDir",
            str(data_dir),
            "-CommandPaletteUrl",
            url,
            "-LensStatusPath",
            str(status_path),
            "-TimeoutSeconds",
            "3",
        )

    assert proc.returncode == 1
    payload = _json_stdout(proc.stdout)
    assert payload["ok"] is False
    assert payload["status"] == "anomaly"
    assert payload["anomaly_count"] >= 1
    assert "command_palette_commands" in {item["id"] for item in payload["anomalies"]}

    anomaly_log = data_dir / "runtime" / "lens-command-palette-monitor" / "anomalies.jsonl"
    assert anomaly_log.exists()
    logged = [json.loads(line) for line in anomaly_log.read_text(encoding="utf-8").splitlines()]
    assert logged[-1]["status"] == "anomaly"


def test_lens_command_palette_monitor_probe_flags_voice_denial(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    status_path = tmp_path / "lens-status.json"
    _write_json(status_path, _lens_status())
    receipt_dir = data_dir / "integrations" / "chatgpt_voice" / "receipts"
    _write_json(
        receipt_dir / "denied.json",
        {
            "kind": "francis.chatgpt_voice.bridge.receipt",
            "status": "recorded_not_forwarded",
            "chat_forward_status": "denied",
            "chat_forward_error": "api_permission_denied",
        },
    )
    runtime_dir = data_dir / "runtime" / "lens-overlay"
    runtime_dir.mkdir(parents=True)
    pid = os.getpid()
    (runtime_dir / "lens-overlay.pid").write_text(str(pid), encoding="utf-8")
    _write_json(
        runtime_dir / "status.json",
        {
            "kind": "lens.overlay.runtime_state",
            "status": "overlay_running",
            "pid": pid,
            "overlay_name": "Francis Lens Overlay",
            "overlay_scope": "user_session",
            "overlay_window_visible": True,
            "always_on_top": True,
            "overlay_voice": {
                "kind": "lens.overlay.voice.runtime",
                "status": "listening",
                "ok": True,
                "voice_provider": "ElevenLabs",
                "selected_voice": "elevenlabs",
                "voice_lens_orb_identity": "Francis",
            },
            "voice": {
                "kind": "lens.overlay.voice.runtime",
                "status": "failed",
                "ok": False,
                "voice_provider": "ElevenLabs",
                "selected_voice": "elevenlabs",
                "chat_error": "api_permission_denied",
            },
            "voice_provider_readiness": {
                "kind": "lens.overlay.voice.provider_readiness",
                "selected_provider": "ElevenLabs",
                "active_provider_configured": True,
                "elevenlabs": {
                    "configured": True,
                    "api_key_present": True,
                    "voice_id_present": True,
                    "voice_label": "elevenlabs",
                    "credential_values_redacted": True,
                    "missing_configuration": [],
                },
            },
        },
    )

    with _LocalCommandPaletteServer() as url:
        proc = _run_monitor(
            "-Mode",
            "Probe",
            "-DataDir",
            str(data_dir),
            "-CommandPaletteUrl",
            url,
            "-LensStatusPath",
            str(status_path),
            "-EnableVoiceChecks",
            "-VoiceProvider",
            "ElevenLabs",
            "-TimeoutSeconds",
            "3",
        )

    assert proc.returncode == 1
    payload = _json_stdout(proc.stdout)
    assert payload["status"] == "anomaly"
    assert "voice_francis_identity" in {item["id"] for item in payload["anomalies"]}
    assert "voice_chat_bridge_denials" in {item["id"] for item in payload["anomalies"]}
    assert payload["voice_monitor"]["api_permission_denied_observed"] is True
    assert payload["voice_monitor"]["denied_recent_receipt_count"] == 1
    assert payload["voice_monitor"]["latest_receipt_denied"] is True


def test_lens_command_palette_monitor_uses_latest_voice_receipt_for_denial_health(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    status_path = tmp_path / "lens-status.json"
    _write_json(status_path, _lens_status())
    receipt_dir = data_dir / "integrations" / "chatgpt_voice" / "receipts"
    denied = receipt_dir / "older-denied.json"
    success = receipt_dir / "latest-success.json"
    _write_json(
        denied,
        {
            "kind": "francis.chatgpt_voice.bridge.receipt",
            "status": "recorded_not_forwarded",
            "chat_forward_status": "denied",
            "chat_forward_error": "api_permission_denied",
        },
    )
    _write_json(
        success,
        {
            "kind": "francis.chatgpt_voice.bridge.receipt",
            "status": "forwarded",
            "chat_forward_status": "sent",
            "chat_forward_error": "",
        },
    )
    old_time = 1_781_800_000
    new_time = old_time + 60
    os.utime(denied, (old_time, old_time))
    os.utime(success, (new_time, new_time))
    runtime_dir = data_dir / "runtime" / "lens-overlay"
    runtime_dir.mkdir(parents=True)
    pid = os.getpid()
    (runtime_dir / "lens-overlay.pid").write_text(str(pid), encoding="utf-8")
    _write_json(
        runtime_dir / "status.json",
        {
            "kind": "lens.overlay.runtime_state",
            "status": "overlay_running",
            "pid": pid,
            "overlay_name": "Francis Lens Overlay",
            "overlay_scope": "user_session",
            "overlay_window_visible": True,
            "always_on_top": True,
            "overlay_voice": {
                "kind": "lens.overlay.voice.runtime",
                "status": "listening",
                "ok": True,
                "voice_provider": "ElevenLabs",
                "selected_voice": "Emma",
                "voice_lens_orb_identity": "Francis",
                "wake_listening": True,
                "wake_phrase": "hey francis",
                "continuous_voice_chat": True,
                "continuous_voice_chat_mode": "enabled_no_wake_phrase_required",
                "continuous_voice_chat_self_trigger_guard": (
                    "suppress_all_except_francis_stop_while_owned_speech_process_active"
                ),
                "microphone_gate_while_speaking": "francis_stop_only",
                "conversation_forwarding_while_speaking": False,
            },
            "voice": {
                "kind": "lens.overlay.voice.runtime",
                "status": "idle",
                "ok": True,
                "voice_provider": "ElevenLabs",
                "selected_voice": "Emma",
            },
            "voice_provider_readiness": {
                "kind": "lens.overlay.voice.provider_readiness",
                "selected_provider": "ElevenLabs",
                "active_provider_configured": True,
                "elevenlabs": {
                    "configured": True,
                    "api_key_present": True,
                    "voice_id_present": True,
                    "voice_label": "Emma",
                    "credential_values_redacted": True,
                    "missing_configuration": [],
                },
            },
        },
    )

    with _LocalCommandPaletteServer() as url:
        proc = _run_monitor(
            "-Mode",
            "Probe",
            "-DataDir",
            str(data_dir),
            "-CommandPaletteUrl",
            url,
            "-LensStatusPath",
            str(status_path),
            "-EnableVoiceChecks",
            "-VoiceProvider",
            "ElevenLabs",
            "-TimeoutSeconds",
            "3",
        )

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = _json_stdout(proc.stdout)
    assert payload["status"] == "healthy"
    assert payload["voice_monitor"]["denied_recent_receipt_count"] == 1
    assert payload["voice_monitor"]["latest_receipt_denied"] is False
    assert payload["voice_monitor"]["latest_receipt_id"] == "latest-success"
    assert payload["voice_monitor"]["latest_receipt_actor"] == ""
    assert payload["voice_monitor"]["latest_receipt_ingress_transport"] == ""
    assert payload["voice_monitor"]["latest_receipt_counts_as_chatgpt_mcp_proof"] is False
    assert (
        payload["voice_monitor"]["latest_receipt_proof_rejection_reason"] == "latest_receipt_not_chatgpt_voice_origin"
    )
    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["voice_chat_bridge_denials"]["status"] == "latest_receipt_clean"
