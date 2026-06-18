from __future__ import annotations

import json
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


def _run_validation_script(*args: str) -> subprocess.CompletedProcess[str]:
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
    assert payload["governance"]["read_only"] is True
    assert payload["governance"]["starts_process"] is False
    assert payload["governance"]["opens_public_tunnel"] is False
    assert payload["governance"]["calls_remote_voice_provider"] is False
    assert payload["governance"]["live_desktop_action"] is False


def test_orb_voice_overlay_lens_validation_classifies_chatgpt_source_receipt_without_transcript(
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
    assert payload["chatgpt_voice_receipts"]["count"] == 1
    assert payload["chatgpt_voice_receipts"]["clean_chatgpt_source_count"] == 1
    latest = payload["chatgpt_voice_receipts"]["latest_chatgpt_source"]
    assert latest["receipt_id"] == "chatgpt-voice-recorded-test"
    assert latest["source_claims_chatgpt_voice"] is True
    assert latest["transcript_char_count"] == 48
    assert latest["transcript_redacted_from_summary"] is True
    assert latest["reply_present"] is True
    summary = json.dumps(payload["chatgpt_voice_receipts"])
    assert "this text should not appear" not in summary
    assert payload["next_smallest_truthful_gap"] in {
        "record_current_https_mcp_connector_url_or_replace_tunnel_with_persistent_ingress",
        "restore_or_create_read_only_mona_lisa_sandbox_replay_artifact",
    }
