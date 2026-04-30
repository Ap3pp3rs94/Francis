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
            str(_repo_root() / "scripts" / "lens-resident-overlay-runtime-proof.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
    )


def test_lens_resident_overlay_runtime_proof_observes_boundary_without_authority(
    tmp_path: Path,
) -> None:
    data_dir = tmp_path / "data"
    proc = _run_proof(
        "-Mode",
        "Status",
        "-SupervisorRunSeconds",
        "20",
        "-DataDir",
        str(data_dir),
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.resident_overlay_runtime.proof"
    assert payload["status"] == "proof_passed"
    assert payload["ok"] is True
    assert payload["supervisor_run_seconds"] == 20
    assert payload["resident_overlay_runtime_ready"] is False
    assert payload["ready_for_lens_resident_claim"] is False
    assert payload["resident_claim_allowed"] is False
    assert payload["bounded_supervisor_observed"] is True
    assert payload["supervisor_observed_running_state"] is True
    assert payload["supervisor_observed_stopped_state"] is True
    assert payload["temporary_host_process_observed"] is True
    assert payload["resident_overlay_runtime"] is False
    assert payload["resident_host_process"] is False
    assert payload["supervised"] is False
    assert payload["service_managed"] is False
    assert payload["overlay_window"] is False
    assert payload["tray_presence"] is False
    assert payload["global_hotkey_bound"] is False
    assert payload["summon_anywhere"] is False
    assert (
        payload["next_smallest_truthful_gap"] == "resident_overlay_activation_or_process_supervision_authority_boundary"
    )

    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["resident_surface_boundary"]["status"] == "surface_blocked_readback_ready"
    assert checks["bounded_supervisor_observation"]["status"] == "bounded_supervisor_observed"
    assert checks["overlay_window_boundary"]["status"] == "blocked_disabled"
    assert checks["tray_presence_boundary"]["status"] == "blocked_disabled"
    assert checks["summon_binding_boundary"]["status"] == "blocked_disabled"
    assert checks["authority_boundary"]["status"] == "diagnostic_bounded"
    assert checks["resident_runtime_claim_boundary"]["status"] == "blocked"
    assert all(item["passed"] for item in payload["checks"])

    proof = payload["proof"]
    assert proof["resident_surface_status"] == "proof_passed"
    assert proof["supervisor_observation_status"] == "proof_passed"
    assert proof["host_running_state_status"] == "foreground_running"
    assert proof["host_stopped_state_status"] == "foreground_stopped"
    assert proof["host_final_status_readback"] == "state_present_process_not_running"
    assert proof["same_process_observed"] is True
    assert proof["overlay_status"] == "blocked"
    assert proof["overlay_window_enabled"] is False
    assert proof["overlay_focus_supported"] is False
    assert proof["tray_status"] == "blocked"
    assert proof["tray_host_enabled"] is False
    assert proof["tray_icon_enabled"] is False
    assert proof["summon_status"] == "blocked"
    assert proof["global_hotkey"] == "Ctrl+Alt+Space"
    assert proof["summon_binding_enabled"] is False
    assert proof["hotkey_registration_enabled"] is False
    assert "resident_overlay_runtime_missing" in payload["blockers"]
    assert "resident_host_process_not_supervised" in payload["blockers"]
    assert "overlay_window_missing" in payload["blockers"]
    assert "tray_presence_missing" in payload["blockers"]
    assert "global_hotkey_binding_missing" in payload["blockers"]
    assert "summon_anywhere_missing" in payload["blockers"]

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
        "window_management_authority": False,
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
        "tray_icon_authority": False,
        "notification_authority": False,
        "mutation_authority_granted": False,
    }

    assert (data_dir / "runtime" / "lens-host" / "status.json").is_file()
