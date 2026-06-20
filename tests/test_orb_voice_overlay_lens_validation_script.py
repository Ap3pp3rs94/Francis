from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
from pathlib import Path

import pytest


def _powershell() -> str:
    exe = shutil.which("powershell") or shutil.which("pwsh")
    if not exe:
        pytest.skip("PowerShell is not available")
    return exe


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _unused_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _mcp_server_voice_provenance() -> dict[str, str]:
    return {
        "ingress_transport": "mcp_gateway_tool",
        "mcp_gateway_tool": "francis.chatgpt_voice.ingress",
        "mcp_server_tool": "francis_chatgpt_voice_ingress",
        "mcp_server_transport": "streamable-http",
    }


def _run_validation_script(
    *args: str,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    run_env = os.environ.copy()
    run_env.pop("FRANCIS_CHATGPT_VOICE_CONNECTOR_URL", None)
    if env:
        run_env.update(env)
    return subprocess.run(
        [
            _powershell(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(_repo_root() / "scripts" / "orb-voice-overlay-lens-validation.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
        timeout=60,
        env=run_env,
    )


def test_orb_voice_overlay_lens_validation_reports_missing_chatgpt_source_receipt(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    port = _unused_local_port()

    proc = _run_validation_script(
        "-DataDir",
        str(data_dir),
        "-ConnectorPort",
        str(port),
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "francis.orb_voice_overlay_lens.validation"
    assert payload["status"] == "proof_blocked_no_chatgpt_app_source_receipt"
    assert payload["ok"] is False
    assert payload["chatgpt_voice_receipts"]["count"] == 0
    assert payload["chatgpt_voice_receipts"]["clean_chatgpt_source_count"] == 0
    assert payload["chatgpt_voice_receipts"]["usable_chatgpt_source_count"] == 0
    assert payload["chatgpt_voice_receipts"]["fresh_chatgpt_source_count"] == 0
    assert payload["chatgpt_voice_receipts"]["fresh_usable_chatgpt_source_count"] == 0
    assert payload["chatgpt_voice_receipts"]["stale_chatgpt_source_count"] == 0
    assert payload["chatgpt_voice_receipts"]["transcript_unavailable_count"] == 0
    assert payload["chatgpt_voice_receipts"]["mcp_server_chatgpt_source_count"] == 0
    assert payload["chatgpt_voice_receipts"]["fresh_mcp_server_chatgpt_source_count"] == 0
    assert payload["chatgpt_voice_receipts"]["fresh_usable_mcp_server_chatgpt_source_count"] == 0
    assert payload["chatgpt_voice_receipts"]["fresh_streamable_http_mcp_server_chatgpt_source_count"] == 0
    assert payload["chatgpt_voice_receipts"]["fresh_usable_streamable_http_mcp_server_chatgpt_source_count"] == 0
    assert payload["persistent_ingress_plan"]["kind"] == "francis.chatgpt_voice.persistent_ingress_plan"
    assert payload["persistent_ingress_plan"]["status"] == "persistent_ingress_url_needed"
    assert payload["persistent_ingress_plan"]["governance"]["read_only"] is True
    assert payload["persistent_ingress_plan"]["governance"]["starts_process"] is False
    assert payload["persistent_ingress_plan"]["governance"]["opens_public_tunnel"] is False
    assert payload["persistent_ingress_plan"]["installer_readiness"]["winget"]["name"] == "winget"
    assert payload["persistent_ingress_plan"]["install_command_hints"]["cloudflared_winget"] == (
        "winget install --id Cloudflare.cloudflared --exact"
    )
    handoff = payload["persistent_ingress_plan"]["operator_handoff"]
    assert handoff["read_only_plan"] is True
    assert handoff["installs_provider"] is False
    assert handoff["opens_tunnel"] is False
    assert handoff["writes_state"] is False
    assert handoff["stable_url_placeholder"] == "https://YOUR-STABLE-HOST/mcp"
    assert handoff["install_commands"]["cloudflared_winget"].endswith(
        "--accept-source-agreements --accept-package-agreements"
    )
    assert "RecordUrl" in handoff["governed_handoff_commands"]["record_url"]
    assert payload["governance"]["read_only"] is True
    assert payload["governance"]["starts_process"] is False
    assert payload["governance"]["opens_public_tunnel"] is False
    assert payload["governance"]["calls_remote_voice_provider"] is False
    assert payload["governance"]["live_desktop_action"] is False


def test_orb_voice_overlay_lens_validation_resolves_cross_platform_powershell_host() -> None:
    script = (_repo_root() / "scripts" / "orb-voice-overlay-lens-validation.ps1").read_text(encoding="utf-8")

    assert "function Resolve-PowerShellHost" in script
    assert "Get-Command powershell -ErrorAction SilentlyContinue" in script
    assert "Get-Command pwsh -ErrorAction SilentlyContinue" in script
    assert "$Output = & $PowerShellHost -NoProfile -ExecutionPolicy Bypass -File $ScriptPath @ScriptArgs 2>&1" in script
    assert "$Output = & powershell -NoProfile -ExecutionPolicy Bypass -File $ScriptPath @ScriptArgs 2>&1" not in script


def test_orb_voice_overlay_lens_validation_requires_mcp_tool_provenance_for_source_receipt(
    tmp_path: Path,
) -> None:
    data_dir = tmp_path / "data"
    receipt_dir = data_dir / "integrations" / "chatgpt_voice" / "receipts"
    receipt_dir.mkdir(parents=True)
    receipt = {
        "kind": "francis.chatgpt_voice.bridge.receipt",
        "receipt_id": "chatgpt-voice-recorded-test",
        "actor": "chatgpt.voice",
        "source": "chatgpt.voice",
        "decision": "recorded",
        "chat_forward_status": "forwarded",
        "chat_forwarded": True,
        "transcript": "this text should not appear in the proof summary",
        "transcript_char_count": 48,
        "reply": "I can hear you. Voice input is reaching Francis.",
        "reply_source": "chat_forward.response",
        "governance": {
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
    }
    (receipt_dir / "chatgpt-voice-recorded-test.json").write_text(json.dumps(receipt), encoding="utf-8")
    port = _unused_local_port()

    proc = _run_validation_script(
        "-DataDir",
        str(data_dir),
        "-ConnectorPort",
        str(port),
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["status"] == "proof_blocked_no_chatgpt_app_mcp_tool_receipt"
    assert payload["next_smallest_truthful_gap"] == (
        "trigger_fresh_chatgpt_app_mcp_tool_call_and_confirm_server_tool_receipt"
    )
    assert payload["chatgpt_voice_receipts"]["count"] == 1
    assert payload["chatgpt_voice_receipts"]["clean_chatgpt_source_count"] == 1
    assert payload["chatgpt_voice_receipts"]["usable_chatgpt_source_count"] == 1
    assert payload["chatgpt_voice_receipts"]["fresh_chatgpt_source_count"] == 1
    assert payload["chatgpt_voice_receipts"]["fresh_usable_chatgpt_source_count"] == 1
    assert payload["chatgpt_voice_receipts"]["mcp_server_chatgpt_source_count"] == 0
    assert payload["chatgpt_voice_receipts"]["fresh_mcp_server_chatgpt_source_count"] == 0
    assert payload["chatgpt_voice_receipts"]["fresh_usable_mcp_server_chatgpt_source_count"] == 0
    assert payload["chatgpt_voice_receipts"]["stale_chatgpt_source_count"] == 0
    assert payload["chatgpt_voice_receipts"]["transcript_unavailable_count"] == 0
    latest = payload["chatgpt_voice_receipts"]["latest_chatgpt_source"]
    assert latest["receipt_id"] == "chatgpt-voice-recorded-test"
    assert latest["source_claims_chatgpt_voice"] is True
    assert latest["source_claims_mcp_gateway_tool"] is False
    assert latest["source_claims_mcp_server_tool"] is False
    assert latest["source_claims_mcp_server_transport"] is False
    assert latest["source_claims_streamable_http_mcp_server"] is False
    assert latest["usable_chatgpt_transcript"] is True
    assert latest["usable_mcp_server_chatgpt_transcript"] is False
    assert latest["usable_streamable_http_mcp_server_chatgpt_transcript"] is False
    assert latest["fresh_for_live_proof"] is True
    assert latest["created_ts_present"] is False
    assert latest["observed_ts_source"] == "file_mtime"
    assert latest["transcript_unavailable_detected"] is False
    assert latest["transcript_char_count"] == 48
    assert latest["transcript_redacted_from_summary"] is True
    assert latest["reply_present"] is True
    latest_usable = payload["chatgpt_voice_receipts"]["latest_usable_chatgpt_source"]
    assert latest_usable["receipt_id"] == "chatgpt-voice-recorded-test"
    latest_fresh_usable = payload["chatgpt_voice_receipts"]["latest_fresh_usable_chatgpt_source"]
    assert latest_fresh_usable["receipt_id"] == "chatgpt-voice-recorded-test"
    assert payload["persistent_ingress_plan"]["status"] == "persistent_ingress_url_needed"
    assert payload["persistent_ingress_plan"]["provider_config_hints"]["ngrok_reserved_domain"].endswith(
        "then record https://<reserved-domain>/mcp."
    )
    checks = {check["id"]: check for check in payload["checks"]}
    assert checks["persistent_ingress_plan_readback"]["passed"] is True
    assert checks["chatgpt_app_mcp_tool_receipt_observed"]["status"] == "missing"
    assert checks["chatgpt_app_mcp_tool_receipt_observed"]["passed"] is False
    assert checks["chatgpt_app_public_mcp_transport_observed"]["status"] == "missing"
    assert checks["chatgpt_app_public_mcp_transport_observed"]["passed"] is False
    summary = json.dumps(payload["chatgpt_voice_receipts"])
    assert "this text should not appear" not in summary


def test_orb_voice_overlay_lens_validation_blocks_mcp_server_receipt_without_public_transport(
    tmp_path: Path,
) -> None:
    data_dir = tmp_path / "data"
    receipt_dir = data_dir / "integrations" / "chatgpt_voice" / "receipts"
    receipt_dir.mkdir(parents=True)
    receipt = {
        "kind": "francis.chatgpt_voice.bridge.receipt",
        "receipt_id": "chatgpt-voice-recorded-internal-mcp-test",
        "actor": "chatgpt.voice",
        "source": "chatgpt.voice",
        "ingress_transport": "mcp_gateway_tool",
        "mcp_gateway_tool": "francis.chatgpt_voice.ingress",
        "mcp_server_tool": "francis_chatgpt_voice_ingress",
        "decision": "recorded",
        "chat_forward_status": "forwarded",
        "chat_forwarded": True,
        "transcript": "internal MCP transport proof should redact this transcript",
        "transcript_char_count": 57,
        "reply": "I can hear you. Voice input is reaching Francis.",
        "reply_source": "chat_forward.response",
        "governance": {
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
    }
    (receipt_dir / "chatgpt-voice-recorded-internal-mcp-test.json").write_text(
        json.dumps(receipt),
        encoding="utf-8",
    )
    port = _unused_local_port()

    proc = _run_validation_script(
        "-DataDir",
        str(data_dir),
        "-ConnectorPort",
        str(port),
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["status"] == "proof_blocked_chatgpt_app_public_mcp_transport_unverified"
    assert payload["next_smallest_truthful_gap"] == (
        "trigger_fresh_chatgpt_app_public_mcp_tool_call_and_confirm_streamable_http_transport"
    )
    assert payload["chatgpt_voice_receipts"]["fresh_mcp_server_chatgpt_source_count"] == 1
    assert payload["chatgpt_voice_receipts"]["fresh_mcp_server_transport_verified_count"] == 0
    assert payload["chatgpt_voice_receipts"]["fresh_streamable_http_mcp_server_chatgpt_source_count"] == 0
    assert payload["chatgpt_voice_receipts"]["fresh_usable_streamable_http_mcp_server_chatgpt_source_count"] == 0
    latest_mcp = payload["chatgpt_voice_receipts"]["latest_fresh_mcp_server_chatgpt_source"]
    assert latest_mcp["receipt_id"] == "chatgpt-voice-recorded-internal-mcp-test"
    assert latest_mcp["source_claims_mcp_server_tool"] is True
    assert latest_mcp["mcp_server_transport"] == ""
    assert latest_mcp["source_claims_mcp_server_transport"] is False
    assert latest_mcp["source_claims_streamable_http_mcp_server"] is False
    assert latest_mcp["usable_mcp_server_chatgpt_transcript"] is True
    assert latest_mcp["usable_streamable_http_mcp_server_chatgpt_transcript"] is False
    checks = {check["id"]: check for check in payload["checks"]}
    assert checks["chatgpt_app_mcp_tool_receipt_observed"]["passed"] is True
    assert checks["chatgpt_app_public_mcp_transport_observed"]["status"] == "transport_unverified"
    assert checks["chatgpt_app_public_mcp_transport_observed"]["passed"] is False
    summary = json.dumps(payload["chatgpt_voice_receipts"])
    assert "internal MCP transport proof should redact" not in summary


def test_orb_voice_overlay_lens_validation_uses_environment_connector_url(
    tmp_path: Path,
) -> None:
    data_dir = tmp_path / "data"
    receipt_dir = data_dir / "integrations" / "chatgpt_voice" / "receipts"
    receipt_dir.mkdir(parents=True)
    receipt = {
        "kind": "francis.chatgpt_voice.bridge.receipt",
        "receipt_id": "chatgpt-voice-recorded-env-test",
        "actor": "chatgpt.voice",
        "source": "chatgpt.voice",
        **_mcp_server_voice_provenance(),
        "decision": "recorded",
        "chat_forward_status": "forwarded",
        "chat_forwarded": True,
        "transcript": "environment URL proof should redact this transcript",
        "transcript_char_count": 52,
        "reply": "I can hear you. Voice input is reaching Francis.",
        "reply_source": "chat_forward.response",
        "governance": {
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
    }
    (receipt_dir / "chatgpt-voice-recorded-env-test.json").write_text(json.dumps(receipt), encoding="utf-8")
    port = _unused_local_port()

    proc = _run_validation_script(
        "-DataDir",
        str(data_dir),
        "-ConnectorPort",
        str(port),
        env={"FRANCIS_CHATGPT_VOICE_CONNECTOR_URL": "https://francis-env.example.test/mcp"},
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["status"] == "proof_partial_connector_reachability_unverified"
    assert payload["next_smallest_truthful_gap"] == (
        "verify_current_https_mcp_connector_reachability_or_trigger_fresh_chatgpt_tool_call"
    )
    assert payload["chatgpt_voice_connector"]["connector_url_provided"] is True
    assert payload["chatgpt_voice_connector"]["connector_url_shape_valid"] is True
    assert (
        payload["chatgpt_voice_connector"]["connector_url_source"] == "environment:FRANCIS_CHATGPT_VOICE_CONNECTOR_URL"
    )
    assert payload["chatgpt_voice_connector"]["connector_url_reason"] == (
        "connector_url_shape_valid_reachability_not_verified"
    )
    assert payload["chatgpt_voice_connector"]["connector_reachability_verified"] is False
    assert payload["chatgpt_voice_connector"]["connector_usable_for_chatgpt"] is False
    assert payload["chatgpt_voice_connector"]["connector_reachability_status"] == "verification_not_requested"
    assert payload["chatgpt_voice_connector"]["connector_reachability_probe_requested"] is False
    assert payload["chatgpt_voice_connector"]["connector_probe_timeout_seconds"] == 5
    assert payload["chatgpt_voice_receipts"]["mcp_server_chatgpt_source_count"] == 1
    assert payload["chatgpt_voice_receipts"]["fresh_mcp_server_chatgpt_source_count"] == 1
    assert payload["chatgpt_voice_receipts"]["fresh_usable_mcp_server_chatgpt_source_count"] == 1
    assert payload["chatgpt_voice_receipts"]["fresh_mcp_server_transport_verified_count"] == 1
    assert payload["chatgpt_voice_receipts"]["fresh_streamable_http_mcp_server_chatgpt_source_count"] == 1
    assert payload["chatgpt_voice_receipts"]["fresh_usable_streamable_http_mcp_server_chatgpt_source_count"] == 1
    latest_mcp = payload["chatgpt_voice_receipts"]["latest_fresh_mcp_server_chatgpt_source"]
    assert latest_mcp["receipt_id"] == "chatgpt-voice-recorded-env-test"
    assert latest_mcp["source_claims_mcp_server_tool"] is True
    assert latest_mcp["mcp_server_tool"] == "francis_chatgpt_voice_ingress"
    assert latest_mcp["mcp_server_transport"] == "streamable-http"
    assert latest_mcp["source_claims_mcp_server_transport"] is True
    assert latest_mcp["source_claims_streamable_http_mcp_server"] is True
    assert latest_mcp["usable_streamable_http_mcp_server_chatgpt_transcript"] is True
    latest_public_mcp = payload["chatgpt_voice_receipts"]["latest_fresh_streamable_http_mcp_server_chatgpt_source"]
    assert latest_public_mcp["receipt_id"] == "chatgpt-voice-recorded-env-test"
    checks = {check["id"]: check for check in payload["checks"]}
    assert checks["chatgpt_app_public_mcp_transport_observed"]["passed"] is True
    assert checks["chatgpt_app_public_mcp_transport_observed"]["status"] == "fresh_observed"
    assert payload["persistent_ingress_plan"]["status"] == "connector_url_shape_valid_record_ready"
    assert payload["persistent_ingress_plan"]["connector_url"]["source"] == (
        "environment:FRANCIS_CHATGPT_VOICE_CONNECTOR_URL"
    )
    assert payload["persistent_ingress_plan"]["governance"]["starts_process"] is False
    assert payload["persistent_ingress_plan"]["governance"]["opens_public_tunnel"] is False
    assert payload["persistent_ingress_plan"]["governance"]["writes_data"] is False
    summary = json.dumps(payload["chatgpt_voice_receipts"])
    assert "environment URL proof should redact" not in summary


def test_orb_voice_overlay_lens_validation_requires_same_public_mcp_receipt_for_usable_transcript(
    tmp_path: Path,
) -> None:
    data_dir = tmp_path / "data"
    receipt_dir = data_dir / "integrations" / "chatgpt_voice" / "receipts"
    receipt_dir.mkdir(parents=True)
    public_unavailable_receipt = {
        "kind": "francis.chatgpt_voice.bridge.receipt",
        "receipt_id": "chatgpt-voice-rejected-public-unavailable-test",
        "actor": "chatgpt.voice",
        "source": "chatgpt.voice",
        **_mcp_server_voice_provenance(),
        "decision": "rejected",
        "reason": "transcript_unavailable",
        "chat_forward_status": "rejected",
        "chat_forwarded": False,
        "transcript": "Transcript Unavailable",
        "transcript_char_count": 22,
        "reply": "ChatGPT reported that the transcript was unavailable.",
        "reply_source": "bridge.transcript_guard",
        "governance": {
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
    }
    internal_usable_receipt = {
        "kind": "francis.chatgpt_voice.bridge.receipt",
        "receipt_id": "chatgpt-voice-recorded-internal-usable-test",
        "actor": "chatgpt.voice",
        "source": "chatgpt.voice",
        "ingress_transport": "mcp_gateway_tool",
        "mcp_gateway_tool": "francis.chatgpt_voice.ingress",
        "mcp_server_tool": "francis_chatgpt_voice_ingress",
        "mcp_server_transport": "",
        "decision": "recorded",
        "chat_forward_status": "forwarded",
        "chat_forwarded": True,
        "transcript": "internal usable MCP transcript should not satisfy public MCP proof",
        "transcript_char_count": 64,
        "reply": "I can hear you. Voice input is reaching Francis.",
        "reply_source": "chat_forward.response",
        "governance": {
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
    }
    (receipt_dir / "chatgpt-voice-rejected-public-unavailable-test.json").write_text(
        json.dumps(public_unavailable_receipt),
        encoding="utf-8",
    )
    (receipt_dir / "chatgpt-voice-recorded-internal-usable-test.json").write_text(
        json.dumps(internal_usable_receipt),
        encoding="utf-8",
    )
    port = _unused_local_port()

    proc = _run_validation_script(
        "-DataDir",
        str(data_dir),
        "-ConnectorPort",
        str(port),
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["status"] == "proof_blocked_no_usable_chatgpt_app_public_mcp_transcript"
    assert payload["next_smallest_truthful_gap"] == (
        "trigger_fresh_chatgpt_app_public_mcp_tool_call_with_usable_transcript"
    )
    receipts = payload["chatgpt_voice_receipts"]
    assert receipts["fresh_streamable_http_mcp_server_chatgpt_source_count"] == 1
    assert receipts["fresh_usable_mcp_server_chatgpt_source_count"] == 1
    assert receipts["fresh_usable_streamable_http_mcp_server_chatgpt_source_count"] == 0
    latest_public_mcp = receipts["latest_fresh_streamable_http_mcp_server_chatgpt_source"]
    assert latest_public_mcp["receipt_id"] == "chatgpt-voice-rejected-public-unavailable-test"
    assert latest_public_mcp["transcript_unavailable_detected"] is True
    latest_usable_mcp = receipts["latest_fresh_usable_mcp_server_chatgpt_source"]
    assert latest_usable_mcp["receipt_id"] == "chatgpt-voice-recorded-internal-usable-test"
    assert latest_usable_mcp["source_claims_streamable_http_mcp_server"] is False
    checks = {check["id"]: check for check in payload["checks"]}
    assert checks["chatgpt_app_public_mcp_transport_observed"]["passed"] is True
    assert checks["chatgpt_app_mcp_tool_usable_transcript_observed"]["passed"] is True
    assert checks["chatgpt_app_public_mcp_usable_transcript_observed"]["passed"] is False
    assert checks["chatgpt_app_public_mcp_usable_transcript_observed"]["status"] == "transcript_unavailable"
    assert checks["chatgpt_app_public_mcp_usable_transcript_observed"]["reason"] == (
        "latest_streamable_http_mcp_tool_receipt_has_unavailable_transcript"
    )
    summary = json.dumps(receipts)
    assert "internal usable MCP transcript should not satisfy" not in summary


def test_orb_voice_overlay_lens_validation_reports_mcp_probe_connection_proof(
    tmp_path: Path,
) -> None:
    data_dir = tmp_path / "data"
    receipt_dir = data_dir / "integrations" / "chatgpt_voice" / "receipts"
    receipt_dir.mkdir(parents=True)
    receipt = {
        "kind": "francis.chatgpt_voice.bridge.receipt",
        "receipt_id": "chatgpt-voice-recorded-probe-test",
        "actor": "chatgpt.voice",
        "source": "chatgpt.voice",
        "client_origin": "chatgpt_app_voice",
        "ingress_transport": "mcp_gateway_tool",
        "mcp_gateway_tool": "francis.chatgpt_voice.mcp_probe",
        "mcp_server_tool": "francis_chatgpt_voice_mcp_probe",
        "proof_kind": "mcp_connection",
        "decision": "recorded",
        "chat_forward_status": "not_requested",
        "chat_forwarded": False,
        "transcript": "",
        "transcript_char_count": 0,
        "reply": "Francis MCP voice bridge is reachable. No transcript was recorded.",
        "reply_source": "bridge.mcp_connection_proof",
        "governance": {
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
    }
    (receipt_dir / "chatgpt-voice-recorded-probe-test.json").write_text(json.dumps(receipt), encoding="utf-8")
    port = _unused_local_port()

    proc = _run_validation_script(
        "-DataDir",
        str(data_dir),
        "-ConnectorPort",
        str(port),
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["status"] == "proof_blocked_no_usable_chatgpt_app_transcript"
    assert payload["next_smallest_truthful_gap"] == "trigger_fresh_chatgpt_app_voice_tool_call_with_usable_transcript"
    assert payload["chatgpt_voice_receipts"]["fresh_mcp_probe_chatgpt_source_count"] == 1
    assert payload["chatgpt_voice_receipts"]["fresh_mcp_connection_proof_chatgpt_source_count"] == 1
    assert payload["chatgpt_voice_receipts"]["fresh_usable_mcp_server_chatgpt_source_count"] == 0
    latest_probe = payload["chatgpt_voice_receipts"]["latest_mcp_probe_chatgpt_source"]
    assert latest_probe["receipt_id"] == "chatgpt-voice-recorded-probe-test"
    assert latest_probe["source_claims_mcp_probe_tool"] is True
    assert latest_probe["source_claims_mcp_connection_proof"] is True
    checks = {check["id"]: check for check in payload["checks"]}
    assert checks["chatgpt_app_mcp_connection_proof_observed"]["passed"] is True
    assert checks["chatgpt_app_mcp_connection_proof_observed"]["status"] == "fresh_observed"
    assert checks["chatgpt_app_usable_transcript_observed"]["passed"] is False
    assert payload["chatgpt_app_origin"]["connector_mcp_connection_proof_observed"] is True
    summary = json.dumps(payload["chatgpt_voice_receipts"])
    assert "No transcript was recorded" not in summary


def test_orb_voice_overlay_lens_validation_blocks_stale_chatgpt_source_receipt(
    tmp_path: Path,
) -> None:
    data_dir = tmp_path / "data"
    receipt_dir = data_dir / "integrations" / "chatgpt_voice" / "receipts"
    receipt_dir.mkdir(parents=True)
    receipt = {
        "kind": "francis.chatgpt_voice.bridge.receipt",
        "receipt_id": "chatgpt-voice-recorded-stale-test",
        "created_ts": 1,
        "actor": "chatgpt.voice",
        "source": "chatgpt.voice",
        "decision": "recorded",
        "chat_forward_status": "forwarded",
        "chat_forwarded": True,
        "transcript": "stale transcript should not satisfy live proof",
        "transcript_char_count": 46,
        "reply": "I can hear you. Voice input is reaching Francis.",
        "reply_source": "chat_forward.response",
        "governance": {
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
    }
    (receipt_dir / "chatgpt-voice-recorded-stale-test.json").write_text(json.dumps(receipt), encoding="utf-8")
    port = _unused_local_port()

    proc = _run_validation_script(
        "-DataDir",
        str(data_dir),
        "-ConnectorPort",
        str(port),
        "-ChatGptReceiptFreshnessSeconds",
        "60",
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["status"] == "proof_blocked_stale_chatgpt_app_source_receipt"
    assert (
        payload["next_smallest_truthful_gap"] == "trigger_fresh_chatgpt_app_voice_tool_call_and_confirm_source_receipt"
    )
    assert payload["chatgpt_voice_receipts"]["clean_chatgpt_source_count"] == 1
    assert payload["chatgpt_voice_receipts"]["usable_chatgpt_source_count"] == 1
    assert payload["chatgpt_voice_receipts"]["fresh_chatgpt_source_count"] == 0
    assert payload["chatgpt_voice_receipts"]["fresh_usable_chatgpt_source_count"] == 0
    assert payload["chatgpt_voice_receipts"]["stale_chatgpt_source_count"] == 1
    assert payload["chatgpt_voice_receipts"]["freshness_window_seconds"] == 60
    latest = payload["chatgpt_voice_receipts"]["latest_chatgpt_source"]
    assert latest["receipt_id"] == "chatgpt-voice-recorded-stale-test"
    assert latest["usable_chatgpt_transcript"] is True
    assert latest["fresh_for_live_proof"] is False
    assert latest["created_ts_present"] is True
    assert latest["observed_ts_source"] == "created_ts"
    assert latest["receipt_age_seconds"] > 60
    assert payload["chatgpt_voice_receipts"]["latest_fresh_chatgpt_source"] is None
    assert payload["chatgpt_voice_receipts"]["latest_fresh_usable_chatgpt_source"] is None
    checks = {check["id"]: check for check in payload["checks"]}
    assert checks["chatgpt_app_source_receipt_observed"]["status"] == "stale_only"
    assert checks["chatgpt_app_source_receipt_observed"]["passed"] is False
    summary = json.dumps(payload["chatgpt_voice_receipts"])
    assert "stale transcript should not satisfy" not in summary


def test_orb_voice_overlay_lens_validation_blocks_unavailable_chatgpt_source_receipt(
    tmp_path: Path,
) -> None:
    data_dir = tmp_path / "data"
    receipt_dir = data_dir / "integrations" / "chatgpt_voice" / "receipts"
    receipt_dir.mkdir(parents=True)
    receipt = {
        "kind": "francis.chatgpt_voice.bridge.receipt",
        "receipt_id": "chatgpt-voice-rejected-unavailable-test",
        "actor": "chatgpt.voice",
        "source": "chatgpt.voice",
        **_mcp_server_voice_provenance(),
        "decision": "rejected",
        "reason": "transcript_unavailable",
        "chat_forward_status": "rejected",
        "chat_forwarded": False,
        "transcript": "Transcript Unavailable\n\nAll right, filler should not count as a user message.",
        "transcript_char_count": 78,
        "reply": "ChatGPT reported that the transcript was unavailable.",
        "reply_source": "bridge.transcript_guard",
        "governance": {
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
    }
    (receipt_dir / "chatgpt-voice-rejected-unavailable-test.json").write_text(
        json.dumps(receipt),
        encoding="utf-8",
    )
    port = _unused_local_port()

    proc = _run_validation_script(
        "-DataDir",
        str(data_dir),
        "-ConnectorPort",
        str(port),
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["status"] == "proof_blocked_no_usable_chatgpt_app_transcript"
    assert payload["ok"] is False
    assert payload["next_smallest_truthful_gap"] == "trigger_fresh_chatgpt_app_voice_tool_call_with_usable_transcript"
    assert payload["chatgpt_voice_receipts"]["count"] == 1
    assert payload["chatgpt_voice_receipts"]["clean_chatgpt_source_count"] == 1
    assert payload["chatgpt_voice_receipts"]["usable_chatgpt_source_count"] == 0
    assert payload["chatgpt_voice_receipts"]["fresh_chatgpt_source_count"] == 1
    assert payload["chatgpt_voice_receipts"]["fresh_usable_chatgpt_source_count"] == 0
    assert payload["chatgpt_voice_receipts"]["mcp_server_chatgpt_source_count"] == 1
    assert payload["chatgpt_voice_receipts"]["fresh_mcp_server_chatgpt_source_count"] == 1
    assert payload["chatgpt_voice_receipts"]["fresh_usable_mcp_server_chatgpt_source_count"] == 0
    assert payload["chatgpt_voice_receipts"]["transcript_unavailable_count"] == 1
    latest = payload["chatgpt_voice_receipts"]["latest_chatgpt_source"]
    assert latest["source_claims_chatgpt_voice"] is True
    assert latest["source_claims_mcp_server_tool"] is True
    assert latest["usable_chatgpt_transcript"] is False
    assert latest["usable_mcp_server_chatgpt_transcript"] is False
    assert latest["transcript_unavailable_detected"] is True
    assert payload["chatgpt_voice_receipts"]["latest_usable_chatgpt_source"] is None
    checks = {check["id"]: check for check in payload["checks"]}
    assert checks["chatgpt_app_source_receipt_observed"]["passed"] is True
    assert checks["chatgpt_app_mcp_tool_receipt_observed"]["passed"] is True
    assert checks["chatgpt_app_usable_transcript_observed"]["passed"] is False
    assert checks["chatgpt_app_usable_transcript_observed"]["status"] == "transcript_unavailable"
    assert checks["chatgpt_app_mcp_tool_usable_transcript_observed"]["passed"] is False
    assert checks["chatgpt_app_mcp_tool_usable_transcript_observed"]["status"] == "transcript_unavailable"
    assert checks["persistent_ingress_plan_readback"]["passed"] is True
    assert payload["persistent_ingress_plan"]["governance"]["writes_data"] is False
    summary = json.dumps(payload["chatgpt_voice_receipts"])
    assert "filler should not count" not in summary
