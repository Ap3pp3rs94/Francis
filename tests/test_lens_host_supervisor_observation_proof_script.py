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


def _run_proof(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            _powershell(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(_repo_root() / "scripts" / "lens-host-supervisor-observation-proof.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
        timeout=140,
    )


def test_lens_host_supervisor_observation_proof_tracks_bounded_lifecycle(
    tmp_path: Path,
) -> None:
    data_dir = tmp_path / "data"
    proc = _run_proof("-Mode", "Status", "-RunSeconds", "20", "-DataDir", str(data_dir))

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.host.supervisor_observation_proof"
    assert payload["status"] == "proof_passed"
    assert payload["ok"] is True
    assert payload["run_seconds"] == 20
    assert payload["bounded_supervisor_observed"] is True
    assert payload["supervision_observation_ready"] is True
    assert payload["supervisor_observed_running_state"] is True
    assert payload["supervisor_observed_stopped_state"] is True
    assert payload["supervisor_restarted_process"] is False
    assert payload["supervisor_managed_service"] is False
    assert payload["ready_for_resident_claim"] is False
    assert payload["temporary_host_process_observed"] is True
    assert payload["resident_host_process"] is False
    assert payload["supervised"] is False
    assert payload["service_managed"] is False
    assert payload["tray_presence"] is False
    assert payload["global_hotkey"] is False
    assert payload["overlay_window"] is False
    assert payload["summon_anywhere"] is False
    assert payload["next_smallest_truthful_gap"] == ("resident_host_process_supervision_or_resident_overlay_runtime")
    assert "resident_host_process_not_supervised" in payload["blockers"]
    assert "resident_supervision_disabled" in payload["blockers"]
    assert "service_control_authority_false" in payload["blockers"]

    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["powershell_runtime"]["passed"] is True
    assert checks["host_status_runner"]["passed"] is True
    assert checks["host_supervisor_runner"]["passed"] is True
    assert checks["bounded_launch_started"]["status"] == "launch_started_observed"
    assert checks["supervisor_runner_consumed"]["status"] == "observation_completed"
    assert checks["supervisor_observed_running_state"]["status"] == "foreground_running_observed"
    assert checks["supervisor_observed_stopped_state"]["status"] == "foreground_stopped_observed"
    assert checks["status_readback_after_stop"]["status"] == "stopped_readback_ready"
    assert checks["launch_authority_boundary"]["status"] == "diagnostic_bounded"
    assert all(item["passed"] for item in payload["checks"])

    proof = payload["proof"]
    assert proof["launch_exit_code"] == 0
    assert proof["launch_status"] == "launch_started"
    assert proof["launch_supported"] is True
    assert proof["launch_authority"] is False
    assert proof["diagnostic_launch_authority"] is True
    assert proof["supervisor_runner"] == "scripts/lens-host-supervisor.ps1"
    assert proof["supervisor_runner_exit_code"] == 0
    assert proof["supervisor_runner_status"] == "observation_completed"
    assert proof["running_state_source"] == "supervisor_runner_observe"
    assert proof["running_state_status"] == "foreground_running"
    assert proof["running_pid"] > 0
    assert proof["running_process_alive"] is True
    assert proof["stopped_state_status"] == "foreground_stopped"
    assert proof["stopped_pid"] == proof["running_pid"]
    assert proof["same_process_observed"] is True
    assert proof["final_status_readback"] == "state_present_process_not_running"
    assert proof["final_status_state"] == "foreground_stopped"
    assert proof["pid_file_present_after_stop"] is False

    assert payload["governance"] == {
        "diagnostic_only": True,
        "bounded_host_launch": True,
        "bounded_process_launch": True,
        "bounded_supervisor_observation": True,
        "temporary_runtime_state_write": True,
        "product_execution_authority": False,
        "execution_authority": False,
        "approval_decision_authority": False,
        "memory_write": False,
        "overlay_control_authority": False,
        "summon_authority": False,
        "capture_authority": False,
        "new_sensing_authority": False,
        "local_process_launch_authority": True,
        "api_local_process_launch_authority": False,
        "process_restart_authority": False,
        "process_supervision_authority": False,
        "service_install_authority": False,
        "service_control_authority": False,
        "hotkey_registration_authority": False,
        "tray_registration_authority": False,
        "mutation_authority_granted": False,
    }

    assert (data_dir / "runtime" / "lens-host" / "status.json").is_file()
    assert (data_dir / "runtime" / "lens-host-supervisor" / "status.json").is_file()
    assert not (data_dir / "runtime" / "lens-host" / "lens-host.pid").exists()
