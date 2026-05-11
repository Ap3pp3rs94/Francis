from __future__ import annotations

import json
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


def _run_session(data_dir: Path, *args: str, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            _powershell(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(_repo_root() / "scripts" / "lens-resident-session.ps1"),
            *args,
            "-DataDir",
            str(data_dir),
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
        timeout=timeout,
    )


def test_lens_resident_session_starts_and_stops_leased_host(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"

    status_before = _run_session(data_dir, "-Mode", "Status")
    assert status_before.returncode == 0, status_before.stderr
    before = json.loads(status_before.stdout)
    assert before["kind"] == "lens.host.resident_session"
    assert before["status"] == "missing"
    assert before["resident_session_active"] is False
    assert before["governance"]["read_only_contract"] is True
    assert before["governance"]["local_process_launch_authority"] is False
    assert before["governance"]["process_stop_authority"] is False
    assert "resident_host_process_missing" in before["blockers"]

    start = _run_session(
        data_dir,
        "-Mode",
        "Start",
        "-LeaseSeconds",
        "30",
        "-StartupTimeoutSeconds",
        "15",
    )
    try:
        assert start.returncode == 0, start.stderr or start.stdout
        started = json.loads(start.stdout)
        assert started["status"] == "resident_session_started"
        assert started["resident_session_active"] is True
        assert started["resident_runtime_candidate"] is True
        assert started["resident_supervised_runtime"] is False
        assert started["resident_claim_allowed"] is False
        assert started["next_smallest_truthful_gap"] == "resident_supervision_not_persistent"
        assert started["governance"]["read_only_contract"] is False
        assert started["governance"]["local_process_launch_authority"] is True
        assert started["governance"]["process_stop_authority"] is False
        assert started["governance"]["service_control_authority"] is False
        assert started["governance"]["tray_registration_authority"] is False
        assert started["governance"]["hotkey_registration_authority"] is False
        assert started["governance"]["overlay_control_authority"] is False
        assert started["governance"]["summon_authority"] is False
        assert started["governance"]["resident_claim_authority"] is False
        process = started["process_readback"]
        assert process["state_kind"] == "lens.host.runtime_state"
        assert process["state_status"] == "resident_running"
        assert process["state_mode"] == "resident"
        assert process["pid_present"] is True
        assert process["pid"] > 0
        assert process["process_alive"] is True
        assert process["resident_session_active"] is True
        assert (data_dir / "runtime" / "lens-host" / "status.json").is_file()
        assert (data_dir / "runtime" / "lens-host-resident-session" / "status.json").is_file()

        status_after_start = _run_session(data_dir, "-Mode", "Status")
        assert status_after_start.returncode == 0, status_after_start.stderr
        after_start = json.loads(status_after_start.stdout)
        assert after_start["kind"] == "lens.host.resident_session"
        assert after_start["status"] in {"resident_session_active", "resident_session_stopped"}
        if after_start["status"] == "resident_session_active":
            assert after_start["resident_session_active"] is True
            assert after_start["process_readback"]["pid"] == process["pid"]
            assert after_start["next_smallest_truthful_gap"] == "resident_supervision_not_persistent"
        else:
            assert after_start["resident_session_active"] is False
            assert after_start["process_readback"]["state_exists"] is True
            assert after_start["process_readback"]["state_status"] == "resident_stopped"
            assert after_start["next_smallest_truthful_gap"] == "resident_host_process_missing"
    finally:
        stop = _run_session(data_dir, "-Mode", "Stop")
        assert stop.returncode == 0, stop.stderr or stop.stdout

    stopped = json.loads(stop.stdout)
    assert stopped["status"] in {"resident_session_stopped", "resident_session_not_running"}
    assert stopped["resident_session_active"] is False
    assert stopped["governance"]["process_stop_authority"] is True
    assert stopped["governance"]["local_process_launch_authority"] is False
    if stopped["status"] == "resident_session_stopped":
        assert stopped["stopped"] is True
        assert stopped["process_readback"]["state_status"] == "resident_stopped"
    assert not (data_dir / "runtime" / "lens-host" / "lens-host.pid").exists()
