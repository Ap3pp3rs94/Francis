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
            str(_repo_root() / "scripts" / "lens-host-launch-proof.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
    )


def test_lens_host_launch_proof_observes_bounded_launch_without_product_authority(
    tmp_path: Path,
) -> None:
    data_dir = tmp_path / "data"
    proc = _run_proof("-Mode", "Status", "-RunSeconds", "3", "-DataDir", str(data_dir))

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.host.launch_readiness_proof"
    assert payload["status"] == "proof_passed"
    assert payload["ok"] is True
    assert payload["run_seconds"] == 3
    assert payload["ready_for_resident_claim"] is False
    assert payload["bounded_host_launch_observed"] is True
    assert payload["launch_authority_boundary"] is True
    assert payload["launch_completed"] is True
    assert payload["runtime_heartbeat_observed"] is True
    assert payload["heartbeat_count"] >= 1
    assert payload["last_heartbeat_at"]
    assert payload["resident_host_process"] is False
    assert payload["supervised"] is False
    assert payload["service_managed"] is False
    assert payload["tray_presence"] is False
    assert payload["global_hotkey"] is False
    assert payload["overlay_window"] is False
    assert payload["summon_anywhere"] is False
    assert "resident_host_process_not_supervised" in payload["blockers"]
    assert "lens_host_runtime_not_implemented" in payload["blockers"]

    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["powershell_runtime"]["passed"] is True
    assert checks["host_status_runner"]["passed"] is True
    assert checks["bounded_launch_started"]["status"] == "launch_started_observed"
    assert checks["launch_authority_boundary"]["status"] == "diagnostic_bounded"
    assert checks["bounded_launch_completion"]["status"] == "self_stopped"
    assert checks["runtime_heartbeat_readback"]["status"] == "heartbeat_observed"
    assert all(item["passed"] for item in payload["checks"])

    proof = payload["proof"]
    assert proof["launch_exit_code"] == 0
    assert proof["launch_status"] == "launch_started"
    assert proof["launch_supported"] is True
    assert proof["launch_authority"] is False
    assert proof["diagnostic_launch_authority"] is True
    assert proof["observed_pid"] > 0
    assert proof["final_pid"] == proof["observed_pid"]
    assert proof["final_heartbeat_count"] == payload["heartbeat_count"]
    assert proof["final_heartbeat_count"] >= 1
    assert proof["final_last_heartbeat_at"] == payload["last_heartbeat_at"]
    assert proof["final_status_heartbeat_count"] == proof["final_heartbeat_count"]
    assert proof["final_status_last_heartbeat_at"] == proof["final_last_heartbeat_at"]
    assert proof["final_state_status"] == "foreground_stopped"
    assert proof["final_status_readback"] == "state_present_process_not_running"
    assert proof["final_status_state"] == "foreground_stopped"
    assert proof["pid_file_present_after_stop"] is False

    assert payload["governance"] == {
        "diagnostic_only": True,
        "bounded_host_launch": True,
        "bounded_process_launch": True,
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
        "service_install_authority": False,
        "service_control_authority": False,
        "hotkey_registration_authority": False,
        "tray_registration_authority": False,
        "mutation_authority_granted": False,
    }

    assert (data_dir / "runtime" / "lens-host" / "status.json").is_file()
    assert not (data_dir / "runtime" / "lens-host" / "lens-host.pid").exists()
