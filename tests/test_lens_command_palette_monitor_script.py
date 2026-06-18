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
                "wake_listening": True,
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
        },
    )


def _json_stdout(stdout: str) -> dict[str, object]:
    return json.loads(stdout)


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
    assert connector["persistent_candidate"] is False
    assert connector["persistent_ingress_status"] == "localtunnel_fallback_replace_needed"
    assert connector["next_operator_step"] == "replace_localtunnel_with_persistent_https_mcp_ingress"
    plan = payload["chatgpt_persistent_ingress_plan_monitor"]
    assert plan["enabled"] is True
    assert plan["status"] == "localtunnel_fallback_replace_needed"
    assert plan["blockers"] == ["localtunnel_url_is_not_persistent_ingress"]
    assert plan["recommended_provider_order"][0] == "cloudflared_named_tunnel"
    assert plan["next_operator_steps"] == [
        "choose_or_install_a_persistent_https_ingress_provider",
        "point_provider_to_local_endpoint",
        "record_the_stable_https_mcp_url_with_recordurl",
        "rerun_orb_voice_overlay_lens_validation",
    ]
    assert isinstance(plan["providers"]["winget_available"], bool)
    assert plan["localtunnel_replacement"]["persistent_ingress_required_for_stable_chatgpt_connector"] is True
    assert plan["governance_safe"] is True
    assert plan["governance"]["read_only_contract"] is True
    assert plan["governance"]["starts_process"] is False
    assert plan["governance"]["opens_public_tunnel"] is False
    assert plan["governance"]["writes_data"] is False
    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["chatgpt_voice_persistent_ingress_plan"]["passed"] is True
    assert "chatgpt_voice_persistent_ingress" not in checks


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
                "wake_listening": True,
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
    assert payload["voice_monitor"]["api_permission_denied_observed"] is False
    assert payload["voice_monitor"]["denied_recent_receipt_count"] == 0
    assert payload["voice_monitor"]["latest_receipt_denied"] is False
    assert payload["voice_monitor"]["chatgpt_mcp_proof"]["status"] == "awaiting_chatgpt_mcp_tool_call"
    assert payload["voice_monitor"]["chatgpt_mcp_proof"]["proof_observed"] is False
    assert payload["voice_monitor"]["chatgpt_mcp_proof"]["transcript_redacted_from_summary"] is True
    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["voice_overlay_readback"]["status"] == "readback_ready"
    assert checks["voice_francis_identity"]["status"] == "francis_voice_identity_ready"
    assert checks["voice_chat_bridge_denials"]["status"] == "latest_receipt_clean"
    assert "voice_chatgpt_mcp_tool_proof" not in checks
    assert payload["governance"]["captures_audio"] is False


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
    assert "voice_chatgpt_mcp_tool_proof" in {item["id"] for item in payload["anomalies"]}
    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["voice_chatgpt_mcp_tool_proof"]["status"] == "awaiting_chatgpt_mcp_tool_call"
    assert checks["voice_chatgpt_mcp_tool_proof"]["evidence"] == "no_fresh_usable_mcp_receipt"


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
    assert proof["mcp_server_receipt_count"] == 1
    assert proof["fresh_usable_mcp_server_receipt_count"] == 1
    assert proof["latest_fresh_usable_mcp_server_receipt_id"] == "chatgpt-voice-recorded-mcp-test"
    assert proof["required_mcp_server_tool"] == "francis_chatgpt_voice_ingress"
    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["voice_chatgpt_mcp_tool_proof"]["status"] == "fresh_usable_mcp_tool_receipt_observed"
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
    assert payload["voice_monitor"]["latest_receipt_proof_rejection_reason"] == "latest_receipt_not_chatgpt_voice_origin"
    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["voice_chat_bridge_denials"]["status"] == "latest_receipt_clean"
