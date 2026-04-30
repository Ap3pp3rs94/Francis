from __future__ import annotations

import json
import os
import platform
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


def _run_script(script_name: str, *args: str, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            _powershell(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(_repo_root() / "scripts" / script_name),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
        timeout=timeout,
    )


def test_lens_host_supervisor_status_is_observation_only(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    proc = _run_script(
        "lens-host-supervisor.ps1",
        "-Mode",
        "Status",
        "-DataDir",
        str(data_dir),
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.host.supervisor_runner"
    assert payload["status"] == "blocked"
    assert payload["mode"] == "status"
    assert payload["observer_ready"] is True
    assert payload["bounded_supervisor_observed"] is False
    assert payload["supervisor_observed_running_state"] is False
    assert payload["supervisor_observed_stopped_state"] is False
    assert payload["supervisor_restarted_process"] is False
    assert payload["supervisor_managed_service"] is False
    assert payload["ready_for_resident_claim"] is False
    assert payload["resident_claim_allowed"] is False
    assert payload["resident_host_process"] is False
    assert payload["supervised"] is False
    assert "resident_host_process_missing" in payload["blockers"]
    assert "process_supervision_authority_not_granted" in payload["blockers"]
    assert payload["next_smallest_truthful_gap"] == "resident_host_process_supervision_authority_boundary"
    assert payload["host_readback"]["state_exists"] is False
    assert payload["host_readback"]["process_alive"] is False
    assert not (data_dir / "runtime" / "lens-host-supervisor" / "status.json").exists()
    assert payload["governance"] == {
        "diagnostic_only": True,
        "read_only_contract": True,
        "bounded_supervisor_observation": False,
        "temporary_runtime_state_write": False,
        "product_execution_authority": False,
        "execution_authority": False,
        "approval_decision_authority": False,
        "memory_write": False,
        "local_process_launch_authority": False,
        "api_local_process_launch_authority": False,
        "process_supervision_authority": False,
        "process_restart_authority": False,
        "service_install_authority": False,
        "service_control_authority": False,
        "overlay_control_authority": False,
        "window_management_authority": False,
        "summon_authority": False,
        "capture_authority": False,
        "new_sensing_authority": False,
        "hotkey_registration_authority": False,
        "tray_registration_authority": False,
        "mutation_authority_granted": False,
    }


def test_lens_host_supervisor_observes_existing_bounded_host_without_restart(tmp_path: Path) -> None:
    if platform.system() != "Windows":
        pytest.skip("Live Lens host lifecycle process-exit proof is Windows-hosted.")

    data_dir = tmp_path / "data"
    host = subprocess.Popen(
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
            "4",
        ],
        cwd=_repo_root(),
        env={**os.environ, "FRANCIS_DATA_DIR": str(data_dir)},
        text=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )

    observed = _run_script(
        "lens-host-supervisor.ps1",
        "-Mode",
        "Observe",
        "-RunSeconds",
        "10",
        "-DataDir",
        str(data_dir),
        timeout=60,
    )
    _, host_stderr = host.communicate(timeout=30)

    assert host.returncode == 0, host_stderr

    assert observed.returncode == 0, observed.stderr
    payload = json.loads(observed.stdout)
    assert payload["kind"] == "lens.host.supervisor_runner"
    assert payload["status"] == "observation_completed"
    assert payload["mode"] == "observe"
    assert payload["ok"] is True
    assert payload["bounded_supervisor_observed"] is True
    assert payload["supervisor_observed_running_state"] is True
    assert payload["supervisor_observed_stopped_state"] is True
    assert payload["supervisor_restarted_process"] is False
    assert payload["supervisor_managed_service"] is False
    assert payload["resident_host_process"] is False
    assert payload["supervised"] is False
    assert payload["ready_for_resident_claim"] is False
    assert payload["resident_claim_allowed"] is False
    assert "resident_host_process_not_supervised" in payload["blockers"]
    assert "process_restart_authority_not_granted" in payload["blockers"]
    assert "service_control_authority_not_granted" in payload["blockers"]

    proof = payload["proof"]
    assert proof["running_state_status"] == "foreground_running"
    assert proof["running_pid"] > 0
    assert proof["running_process_alive"] is True
    assert proof["stopped_state_status"] == "foreground_stopped"
    assert proof["stopped_pid"] == proof["running_pid"]
    assert proof["stopped_process_alive"] is False
    assert proof["same_process_observed"] is True
    assert proof["pid_file_present_after_stop"] is False

    assert payload["governance"] == {
        "diagnostic_only": True,
        "read_only_contract": False,
        "bounded_supervisor_observation": True,
        "temporary_runtime_state_write": True,
        "product_execution_authority": False,
        "execution_authority": False,
        "approval_decision_authority": False,
        "memory_write": False,
        "local_process_launch_authority": False,
        "api_local_process_launch_authority": False,
        "process_supervision_authority": False,
        "process_restart_authority": False,
        "service_install_authority": False,
        "service_control_authority": False,
        "overlay_control_authority": False,
        "window_management_authority": False,
        "summon_authority": False,
        "capture_authority": False,
        "new_sensing_authority": False,
        "hotkey_registration_authority": False,
        "tray_registration_authority": False,
        "mutation_authority_granted": False,
    }
    assert (data_dir / "runtime" / "lens-host-supervisor" / "status.json").is_file()
    assert not (data_dir / "runtime" / "lens-host" / "lens-host.pid").exists()


def test_lens_host_supervisor_supervises_one_bounded_host_without_resident_claim(tmp_path: Path) -> None:
    if platform.system() != "Windows":
        pytest.skip("Live Lens host lifecycle process-exit proof is Windows-hosted.")

    data_dir = tmp_path / "data"
    proc = _run_script(
        "lens-host-supervisor.ps1",
        "-Mode",
        "SuperviseOnce",
        "-RunSeconds",
        "5",
        "-DataDir",
        str(data_dir),
        timeout=90,
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.host.supervisor_runner"
    assert payload["status"] == "supervised_session_completed"
    assert payload["mode"] == "superviseonce"
    assert payload["ok"] is True
    assert payload["supervisor_started_process"] is True
    assert payload["bounded_supervised_session"] is True
    assert payload["bounded_supervisor_observed"] is True
    assert payload["supervisor_observed_running_state"] is True
    assert payload["supervisor_observed_stopped_state"] is True
    assert payload["temporary_host_process_observed"] is True
    assert payload["supervisor_restarted_process"] is False
    assert payload["supervisor_managed_service"] is False
    assert payload["ready_for_resident_claim"] is False
    assert payload["resident_claim_allowed"] is False
    assert payload["resident_host_process"] is False
    assert payload["resident_supervised_runtime"] is False
    assert payload["supervised"] is False
    assert payload["next_smallest_truthful_gap"] == "resident_supervised_session_checkpoint_readback"
    assert "resident_host_process_missing" not in payload["blockers"]
    assert "resident_host_process_not_resident" in payload["blockers"]
    assert "resident_supervision_not_persistent" in payload["blockers"]
    assert "process_supervision_authority_not_granted" in payload["blockers"]
    assert "process_restart_authority_not_granted" in payload["blockers"]
    assert "service_control_authority_not_granted" in payload["blockers"]

    proof = payload["proof"]
    assert proof["running_state_status"] == "foreground_running"
    assert proof["running_pid"] > 0
    assert proof["running_process_alive"] is True
    assert proof["stopped_state_status"] == "foreground_stopped"
    assert proof["stopped_pid"] == proof["running_pid"]
    assert proof["stopped_process_alive"] is False
    assert proof["same_process_observed"] is True
    assert proof["pid_file_present_after_stop"] is False
    assert proof["supervisor_owned_launch"] is True
    assert proof["host_exit_code"] == 0

    assert payload["governance"] == {
        "diagnostic_only": True,
        "read_only_contract": False,
        "bounded_supervisor_observation": True,
        "temporary_runtime_state_write": True,
        "product_execution_authority": False,
        "execution_authority": False,
        "approval_decision_authority": False,
        "memory_write": False,
        "local_process_launch_authority": True,
        "api_local_process_launch_authority": False,
        "process_supervision_authority": False,
        "process_restart_authority": False,
        "service_install_authority": False,
        "service_control_authority": False,
        "overlay_control_authority": False,
        "window_management_authority": False,
        "summon_authority": False,
        "capture_authority": False,
        "new_sensing_authority": False,
        "hotkey_registration_authority": False,
        "tray_registration_authority": False,
        "mutation_authority_granted": False,
    }
    assert (data_dir / "runtime" / "lens-host-supervisor" / "status.json").is_file()
    assert (data_dir / "runtime" / "lens-host" / "status.json").is_file()
    assert not (data_dir / "runtime" / "lens-host" / "lens-host.pid").exists()
