from __future__ import annotations

import json
import platform
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


def _run_mcp_script(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            _powershell(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(_repo_root() / "scripts" / "chatgpt-voice-mcp.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
        timeout=30,
    )


@pytest.mark.skipif(platform.system() != "Windows", reason="Get-NetTCPConnection is Windows-specific")
def test_chatgpt_voice_mcp_status_json_reports_local_and_connector_readiness() -> None:
    port = _unused_local_port()

    proc = _run_mcp_script(
        "-StatusOnly",
        "-Json",
        "-Port",
        str(port),
        "-ConnectorUrl",
        "https://francis.example.test/mcp",
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "francis.chatgpt_voice.mcp.status"
    assert payload["ok"] is False
    assert payload["status"] == "local_listener_missing"
    assert payload["local_endpoint"] == f"http://127.0.0.1:{port}/mcp"
    assert payload["local_listener"]["ready"] is False
    assert payload["chatgpt_connector"]["requires_https"] is True
    assert payload["chatgpt_connector"]["requires_mcp_path"] == "/mcp"
    assert payload["chatgpt_connector"]["connector_url"]["provided"] is True
    assert payload["chatgpt_connector"]["connector_url"]["https"] is True
    assert payload["chatgpt_connector"]["connector_url"]["ends_with_mcp_path"] is True
    assert payload["chatgpt_connector"]["connector_url"]["shape_valid"] is True
    assert payload["chatgpt_connector"]["connector_url"]["reachability_verified"] is False
    assert payload["chatgpt_connector"]["connector_url"]["usable_for_chatgpt"] is False
    assert payload["chatgpt_connector"]["ready"] is False
    assert payload["chatgpt_connector"]["ready_to_attempt_link"] is False
    assert payload["chatgpt_connector"]["reachability_verified"] is False
    assert payload["chatgpt_connector"]["connector_probe_timeout_seconds"] == 5
    assert payload["chatgpt_connector"]["native_localhost_access_claimed"] is False
    assert payload["chatgpt_connector"]["opens_tunnel"] is False
    assert payload["blockers"] == ["local_mcp_listener_missing"]
    assert payload["governance"]["read_only"] is True
    assert payload["governance"]["writes_repo"] is False
    assert payload["governance"]["writes_data"] is False
    assert payload["governance"]["opens_public_tunnel"] is False
    assert payload["governance"]["starts_process"] is False
    assert payload["governance"]["grants_execution_authority"] is False
    assert payload["governance"]["grants_mutation_authority"] is False


@pytest.mark.skipif(platform.system() != "Windows", reason="Get-NetTCPConnection is Windows-specific")
def test_chatgpt_voice_mcp_status_json_rejects_non_https_connector_url() -> None:
    port = _unused_local_port()

    proc = _run_mcp_script(
        "-StatusOnly",
        "-Json",
        "-Port",
        str(port),
        "-ConnectorUrl",
        "http://127.0.0.1:8787/mcp",
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    connector = payload["chatgpt_connector"]["connector_url"]
    assert connector["https"] is False
    assert connector["shape_valid"] is False
    assert connector["usable_for_chatgpt"] is False
    assert connector["reason"] == "connector_url_must_be_https"
    assert "connector_url_must_be_https" in payload["blockers"]


@pytest.mark.skipif(platform.system() != "Windows", reason="Get-NetTCPConnection is Windows-specific")
def test_chatgpt_voice_mcp_verify_connector_skips_invalid_url_shape() -> None:
    port = _unused_local_port()

    proc = _run_mcp_script(
        "-StatusOnly",
        "-Json",
        "-VerifyConnector",
        "-Port",
        str(port),
        "-ConnectorUrl",
        "http://127.0.0.1:8787/mcp",
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    connector = payload["chatgpt_connector"]
    assert connector["connector_url"]["shape_valid"] is False
    assert connector["connector_url"]["reachability_verified"] is False
    assert connector["connector_url"]["usable_for_chatgpt"] is False
    assert connector["probe"] is None
    assert connector["ready"] is False
    assert connector["connector_probe_timeout_seconds"] == 5
    assert payload["governance"]["read_only"] is True
    assert payload["governance"]["writes_data"] is False
