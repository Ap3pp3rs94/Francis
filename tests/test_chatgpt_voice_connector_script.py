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


def _run_connector_script(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            _powershell(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(_repo_root() / "scripts" / "chatgpt-voice-connector.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
        timeout=30,
    )


@pytest.mark.skipif(platform.system() != "Windows", reason="connector control uses Windows process readback")
def test_chatgpt_voice_connector_status_is_read_only_without_runtime_state(tmp_path: Path) -> None:
    runtime_root = tmp_path / "connector-runtime"
    port = _unused_local_port()

    proc = _run_connector_script(
        "-Mode",
        "Status",
        "-Json",
        "-RuntimeRoot",
        str(runtime_root),
        "-Port",
        str(port),
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "francis.chatgpt_voice.connector_control"
    assert payload["ok"] is False
    assert payload["status"] == "not_started"
    assert payload["connector_url"] == ""
    assert payload["endpoint_status"]["status"] == "local_listener_missing"
    assert payload["governance"]["read_only"] is True
    assert payload["governance"]["starts_process"] is False
    assert payload["governance"]["opens_public_tunnel"] is False
    assert payload["governance"]["writes_data"] is False
    assert payload["governance"]["grants_execution_authority"] is False
    assert not runtime_root.exists()


@pytest.mark.skipif(platform.system() != "Windows", reason="connector control uses Windows process readback")
def test_chatgpt_voice_connector_start_requires_explicit_public_tunnel_authorization(tmp_path: Path) -> None:
    runtime_root = tmp_path / "connector-runtime"
    port = _unused_local_port()

    proc = _run_connector_script(
        "-Mode",
        "Start",
        "-Json",
        "-RuntimeRoot",
        str(runtime_root),
        "-Port",
        str(port),
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "francis.chatgpt_voice.connector_control"
    assert payload["ok"] is False
    assert payload["status"] == "operator_public_tunnel_authorization_required"
    assert payload["blockers"] == ["expose_public_tunnel_flag_required"]
    assert payload["governance"]["read_only"] is False
    assert payload["governance"]["starts_process"] is False
    assert payload["governance"]["opens_public_tunnel"] is False
    assert payload["governance"]["writes_data"] is False
    assert payload["governance"]["grants_execution_authority"] is False
    assert not runtime_root.exists()


@pytest.mark.skipif(platform.system() != "Windows", reason="connector control uses Windows process readback")
def test_chatgpt_voice_connector_status_accepts_manual_connector_url(tmp_path: Path) -> None:
    runtime_root = tmp_path / "connector-runtime"
    port = _unused_local_port()

    proc = _run_connector_script(
        "-Mode",
        "Status",
        "-Json",
        "-RuntimeRoot",
        str(runtime_root),
        "-Port",
        str(port),
        "-ConnectorUrl",
        "https://francis.example.test/mcp",
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["status"] == "not_started"
    assert payload["connector_url"] == "https://francis.example.test/mcp"
    assert payload["endpoint_status"]["chatgpt_connector"]["connector_url"]["shape_valid"] is True
    assert payload["governance"]["read_only"] is True
    assert payload["governance"]["starts_process"] is False
    assert payload["governance"]["opens_public_tunnel"] is False
    assert payload["governance"]["writes_data"] is False
    assert not runtime_root.exists()
