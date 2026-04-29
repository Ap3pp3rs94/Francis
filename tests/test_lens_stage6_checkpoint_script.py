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


def _run_checkpoint(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            _powershell(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(_repo_root() / "scripts" / "lens-stage6-checkpoint.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
    )


def test_lens_stage6_checkpoint_reports_blocked_done_criteria_without_authority() -> None:
    proc = _run_checkpoint("-Mode", "Status")

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.stage6.checkpoint"
    assert payload["status"] == "blocked"
    assert payload["stage"] == "Stage 6 / Lens MVP"
    assert payload["stage_state"] == "active"
    assert payload["stage_claim"] == "backend_readback_contract_only"
    assert payload["ready_to_close"] is False
    assert payload["summary"] == {
        "criteria_total": 5,
        "ready_total": 2,
        "blocked_total": 3,
        "blocker_total": len(payload["blockers"]),
    }
    criteria = {item["id"]: item for item in payload["criteria"]}
    assert criteria["summon_anywhere"]["status"] == "not_implemented"
    assert criteria["summon_anywhere"]["ready"] is False
    assert "resident_host_process_missing" in criteria["summon_anywhere"]["blockers"]
    assert "global_hotkey_binding_missing" in criteria["summon_anywhere"]["blockers"]
    assert "summon_binding_missing" in criteria["summon_anywhere"]["blockers"]
    assert criteria["helpful_not_noisy"]["status"] == "operator_readback_proof_ready"
    assert criteria["helpful_not_noisy"]["ready"] is False
    assert criteria["helpful_not_noisy"]["blockers"] == ["resident_surface_missing"]
    assert "scripts/lens-live-operator-proof.ps1" in criteria["helpful_not_noisy"]["evidence"]
    assert criteria["mode_visibility"]["status"] == "readback_ready"
    assert criteria["mode_visibility"]["ready"] is True
    assert criteria["pilot_visibility_groundwork"]["status"] == "readback_ready"
    assert criteria["pilot_visibility_groundwork"]["ready"] is True
    assert criteria["system_resident_presence"]["status"] == "bounded_host_launch_observed"
    assert criteria["system_resident_presence"]["ready"] is False
    assert "resident_host_process_missing" not in criteria["system_resident_presence"]["blockers"]
    assert "resident_host_process_not_supervised" in criteria["system_resident_presence"]["blockers"]
    assert "resident_overlay_runtime_missing" in criteria["system_resident_presence"]["blockers"]
    assert "tray_host_missing" in payload["blockers"]
    assert "overlay_window_missing" in payload["blockers"]
    assert "scripts/lens-host-foreground-proof.ps1" in criteria["system_resident_presence"]["evidence"]
    assert "scripts/lens-host-launch-proof.ps1" in criteria["system_resident_presence"]["evidence"]
    assert "scripts/lens-host-supervision-proof.ps1" in criteria["system_resident_presence"]["evidence"]
    assert "scripts/lens-resident-surface-proof.ps1" in criteria["system_resident_presence"]["evidence"]
    assert "/lens/resident-surface/activation" in criteria["system_resident_presence"]["evidence"]
    assert "operator_experience_proof_missing" not in payload["blockers"]
    assert payload["live_operator_experience_proof"]["status"] == "proof_passed"
    assert payload["live_operator_experience_proof"]["ok"] is True
    assert payload["live_operator_experience_proof"]["exit_code"] == 0
    assert payload["live_operator_experience_proof"]["live_http_status_readback"] is True
    assert payload["live_operator_experience_proof"]["helpful_not_noisy_readback"] is True
    assert payload["live_operator_experience_proof"]["operator_experience_proof"] is True
    assert payload["live_operator_experience_proof"]["live_operator_experience_ready"] is False
    assert payload["live_operator_experience_proof"]["ready_for_stage6_closure"] is False
    assert "resident_surface_missing" in payload["live_operator_experience_proof"]["blockers"]
    assert payload["host_launch_proof"]["status"] == "proof_passed"
    assert payload["host_launch_proof"]["ok"] is True
    assert payload["host_launch_proof"]["exit_code"] == 0
    assert payload["host_launch_proof"]["bounded_host_launch_observed"] is True
    assert payload["host_launch_proof"]["launch_authority_boundary"] is True
    assert payload["host_launch_proof"]["launch_completed"] is True
    assert payload["host_launch_proof"]["ready_for_resident_claim"] is False
    assert "resident_host_process_not_supervised" in payload["host_launch_proof"]["blockers"]
    assert payload["next_smallest_truthful_gap"] == "resident_host_supervision_or_resident_overlay_runtime"
    assert payload["governance"] == {
        "read_only_contract": True,
        "diagnostic_only": True,
        "live_http_readback": True,
        "temporary_api_process": True,
        "bounded_host_launch": True,
        "temporary_runtime_state_write": True,
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
