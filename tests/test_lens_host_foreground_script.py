from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
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


def _read_state(data_dir: Path) -> dict[str, object]:
    state_path = data_dir / "runtime" / "lens-host" / "status.json"
    if not state_path.is_file():
        return {}
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _wait_for_state(data_dir: Path, status: str, timeout_seconds: float = 5.0) -> dict[str, object]:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        payload = _read_state(data_dir)
        if payload.get("status") == status:
            return payload
        time.sleep(0.05)
    return _read_state(data_dir)


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


def test_lens_host_status_observes_live_foreground_session(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    env = os.environ.copy()
    env["FRANCIS_DATA_DIR"] = str(data_dir)
    proc = subprocess.Popen(
        [
            _powershell(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(_repo_root() / "scripts" / "lens-host.ps1"),
            "-Mode",
            "Foreground",
            "-RunSeconds",
            "6",
        ],
        cwd=_repo_root(),
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        running_state = _wait_for_state(data_dir, "foreground_running")
        assert running_state["process_alive"] is True
        assert running_state["resident"] is False
        assert running_state["service_managed"] is False

        status = _run_host("-Mode", "Status", data_dir=data_dir)
        assert status.returncode == 0, status.stderr
        status_payload = json.loads(status.stdout)
        assert status_payload["process_readback"]["status"] == "process_observed"
        assert status_payload["process_readback"]["state_status"] == "foreground_running"
        assert status_payload["process_readback"]["pid_present"] is True
        assert status_payload["process_readback"]["pid"] == running_state["pid"]
        assert status_payload["process_readback"]["process_alive"] is True
        assert status_payload["process_readback"]["blocked_reason"] == "resident_host_not_supervised"
        assert status_payload["foreground_session"] is True
        assert status_payload["resident"] is False
        assert status_payload["process_supervision"] is False
        assert "resident_host_process_missing" not in status_payload["blockers"]
        assert "lens_host_runtime_not_implemented" in status_payload["blockers"]

        stdout, stderr = proc.communicate(timeout=10)
        assert proc.returncode == 0, stderr
        final_payload = json.loads(stdout)
        assert final_payload["status"] == "foreground_completed"
        assert final_payload["process_readback"]["state_status"] == "foreground_stopped"
    finally:
        if proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=5)


def test_lens_host_launch_starts_bounded_background_session(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    proc = _run_host("-Mode", "Launch", "-RunSeconds", "3", data_dir=data_dir)

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.host.status_runner"
    assert payload["status"] == "launch_started"
    assert payload["mode"] == "launch"
    assert payload["launch_supported"] is True
    assert payload["launch_authority"] is False
    assert payload["diagnostic_launch_authority"] is True
    assert payload["launch"]["status"] == "started_observed"
    assert payload["launch"]["observed_pid"] > 0
    assert payload["launch"]["run_seconds"] == 3
    assert payload["launch"]["stop_mode"] == "bounded_self_stop"
    assert payload["process_readback"]["status"] == "process_observed"
    assert payload["process_readback"]["state_status"] == "foreground_running"
    assert payload["process_readback"]["pid_present"] is True
    assert payload["process_readback"]["pid"] == payload["launch"]["observed_pid"]
    assert payload["process_readback"]["process_alive"] is True
    assert payload["process_readback"]["blocked_reason"] == "resident_host_not_supervised"
    assert payload["foreground_supported"] is True
    assert payload["foreground_session"] is True
    assert payload["resident"] is False
    assert payload["process_supervision"] is False
    assert payload["tray_presence"] is False
    assert payload["overlay_window"] is False
    assert payload["summon_anywhere"] is False
    assert "resident_host_process_not_supervised" in payload["blockers"]
    assert "lens_host_runtime_not_implemented" in payload["blockers"]

    governance = payload["governance"]
    assert governance["diagnostic_only"] is True
    assert governance["bounded_process_launch"] is True
    assert governance["temporary_runtime_state_write"] is True
    assert governance["product_execution_authority"] is False
    assert governance["execution_authority"] is False
    assert governance["approval_decision_authority"] is False
    assert governance["memory_write"] is False
    assert governance["overlay_control_authority"] is False
    assert governance["summon_authority"] is False
    assert governance["local_process_launch_authority"] is True
    assert governance["api_local_process_launch_authority"] is False
    assert governance["service_install_authority"] is False
    assert governance["service_control_authority"] is False
    assert governance["mutation_authority_granted"] is False

    stopped_state = _wait_for_state(data_dir, "foreground_stopped", timeout_seconds=8)
    assert stopped_state["status"] == "foreground_stopped"
    assert stopped_state["pid"] == payload["launch"]["observed_pid"]
    assert stopped_state["process_alive"] is False
    assert stopped_state["resident"] is False
    assert stopped_state["service_managed"] is False
    assert stopped_state["governance"]["memory_write"] is False
    assert not (data_dir / "runtime" / "lens-host" / "lens-host.pid").exists()
