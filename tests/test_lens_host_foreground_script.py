from __future__ import annotations

import json
import os
import shutil
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


def _run_host(*args: str, data_dir: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["FRANCIS_DATA_DIR"] = str(data_dir)
    return subprocess.run(
        [
            _powershell(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(_repo_root() / "scripts" / "lens-host.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        env=env,
        check=False,
        text=True,
        capture_output=True,
    )


def test_lens_host_foreground_writes_bounded_runtime_state(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    proc = _run_host("-Mode", "Foreground", "-RunSeconds", "0", data_dir=data_dir)

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.host.status_runner"
    assert payload["status"] == "foreground_completed"
    assert payload["foreground_supported"] is True
    assert payload["foreground_session"] is False
    assert payload["process_readback"]["state_exists"] is True
    assert payload["process_readback"]["state_status"] == "foreground_stopped"
    assert payload["process_readback"]["pid_present"] is False
    assert payload["process_readback"]["pid"] == 0
    assert payload["governance"]["runtime_state_write"] is True
    assert payload["governance"]["foreground_session_authority"] is True
    assert payload["governance"]["local_process_launch_authority"] is False
    assert payload["tray_presence"] is False
    assert payload["overlay_window"] is False
    assert payload["summon_anywhere"] is False

    state_path = data_dir / "runtime" / "lens-host" / "status.json"
    pid_path = data_dir / "runtime" / "lens-host" / "lens-host.pid"
    state = json.loads(state_path.read_text(encoding="utf-8-sig"))
    assert state["kind"] == "lens.host.runtime_state"
    assert state["status"] == "foreground_stopped"
    assert state["resident"] is False
    assert state["service_managed"] is False
    assert state["governance"]["memory_write"] is False
    assert not pid_path.exists()

    status = _run_host("-Mode", "Status", data_dir=data_dir)
    assert status.returncode == 0, status.stderr
    status_payload = json.loads(status.stdout)
    assert status_payload["process_readback"]["status"] == "state_present_process_not_running"
    assert status_payload["process_readback"]["state_status"] == "foreground_stopped"
    assert "resident_host_process_missing" in status_payload["blockers"]
