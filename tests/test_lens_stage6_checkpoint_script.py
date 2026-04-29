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
        "enablement_gate_total": 4,
        "enablement_gate_ready_total": 0,
        "enablement_gate_blocked_total": 4,
        "blocker_total": len(payload["blockers"]),
    }
    criteria = {item["id"]: item for item in payload["criteria"]}
    enablement_gates = {item["id"]: item for item in payload["enablement_gates"]}
    assert enablement_gates["resident_supervision_enablement_gate"]["status"] == "blocked"
    assert enablement_gates["resident_supervision_enablement_gate"]["ready"] is False
    assert enablement_gates["resident_supervision_enablement_gate"]["resident_claim_allowed"] is False
    assert "process_supervision_enabled" in enablement_gates["resident_supervision_enablement_gate"]["blockers"]
    assert "service_control_authority_false" in enablement_gates["resident_supervision_enablement_gate"]["blockers"]
    assert "/lens/host/supervision" in enablement_gates["resident_supervision_enablement_gate"]["evidence"]
    assert enablement_gates["summon_enablement_gate"]["status"] == "blocked"
    assert enablement_gates["summon_enablement_gate"]["ready"] is False
    assert enablement_gates["summon_enablement_gate"]["summon_anywhere"] is False
    assert enablement_gates["summon_enablement_gate"]["global_hotkey"] == "Ctrl+Alt+Space"
    assert "summon_binding_missing" in enablement_gates["summon_enablement_gate"]["blockers"]
    assert enablement_gates["tray_enablement_gate"]["status"] == "blocked"
    assert enablement_gates["tray_enablement_gate"]["ready"] is False
    assert enablement_gates["tray_enablement_gate"]["tray_presence"] is False
    assert enablement_gates["tray_enablement_gate"]["presence_name"] == "Francis Lens Tray Presence"
    assert "tray_registration_authority_not_granted" in enablement_gates["tray_enablement_gate"]["blockers"]
    assert enablement_gates["overlay_enablement_gate"]["status"] == "blocked"
    assert enablement_gates["overlay_enablement_gate"]["ready"] is False
    assert enablement_gates["overlay_enablement_gate"]["overlay_window"] is False
    assert enablement_gates["overlay_enablement_gate"]["overlay_name"] == "Francis Lens Overlay"
    assert "overlay_control_authority_not_granted" in enablement_gates["overlay_enablement_gate"]["blockers"]
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
    assert criteria["system_resident_presence"]["status"] == "resident_overlay_activation_boundary_observed"
    assert criteria["system_resident_presence"]["ready"] is False
    assert "resident_host_process_missing" not in criteria["system_resident_presence"]["blockers"]
    assert "resident_host_process_not_supervised" in criteria["system_resident_presence"]["blockers"]
    assert "resident_supervision_disabled" in criteria["system_resident_presence"]["blockers"]
    assert "resident_overlay_runtime_missing" in criteria["system_resident_presence"]["blockers"]
    assert "tray_host_missing" in payload["blockers"]
    assert "overlay_window_missing" in payload["blockers"]
    assert "scripts/lens-host-foreground-proof.ps1" in criteria["system_resident_presence"]["evidence"]
    assert "scripts/lens-host-launch-proof.ps1" in criteria["system_resident_presence"]["evidence"]
    assert "scripts/lens-host-supervisor-observation-proof.ps1" in criteria["system_resident_presence"]["evidence"]
    assert "scripts/lens-host-supervision-proof.ps1" in criteria["system_resident_presence"]["evidence"]
    assert "scripts/lens-resident-surface-proof.ps1" in criteria["system_resident_presence"]["evidence"]
    assert "/lens/resident-runtime/preflight" in criteria["system_resident_presence"]["evidence"]
    assert "/lens/resident-runtime/plan" in criteria["system_resident_presence"]["evidence"]
    assert "/lens/resident-runtime/execute" in criteria["system_resident_presence"]["evidence"]
    assert "scripts/lens-resident-overlay-runtime-proof.ps1" in criteria["system_resident_presence"]["evidence"]
    assert (
        "scripts/lens-resident-overlay-activation-boundary-proof.ps1"
        in criteria["system_resident_presence"]["evidence"]
    )
    assert "/lens/resident-surface/activation" in criteria["system_resident_presence"]["evidence"]
    assert "operator_experience_proof_missing" not in payload["blockers"]
    assert payload["resident_runtime_authority_grant_preflight"]["status"] == "blocked"
    assert payload["resident_runtime_authority_grant_preflight"]["ok"] is True
    assert payload["resident_runtime_authority_grant_preflight"]["ready"] is False
    assert payload["resident_runtime_authority_grant_preflight"]["grant_ready"] is False
    assert payload["resident_runtime_authority_grant_preflight"]["authority_grant_ready"] is False
    assert payload["resident_runtime_authority_grant_preflight"]["runtime_ready"] is False
    assert payload["resident_runtime_authority_grant_preflight"]["resident_claim_allowed"] is False
    assert "/lens/resident-runtime/preflight" in payload["resident_runtime_authority_grant_preflight"]["evidence"]
    assert (
        "resident_runtime_authority_grant_not_implemented"
        in payload["resident_runtime_authority_grant_preflight"]["blockers"]
    )
    assert (
        "process_supervision_authority_not_granted" in payload["resident_runtime_authority_grant_preflight"]["blockers"]
    )
    assert payload["resident_runtime_authority_grant_preflight"]["execution_authority"] is False
    assert payload["resident_runtime_authority_grant_preflight"]["approval_decision_authority"] is False
    assert payload["resident_runtime_authority_grant_preflight"]["local_process_launch_authority"] is False
    assert payload["resident_runtime_authority_grant_preflight"]["process_supervision_authority"] is False
    assert payload["resident_runtime_authority_grant_preflight"]["service_install_authority"] is False
    assert payload["resident_runtime_authority_grant_preflight"]["service_control_authority"] is False
    assert payload["resident_runtime_authority_grant_preflight"]["hotkey_registration_authority"] is False
    assert payload["resident_runtime_authority_grant_preflight"]["tray_registration_authority"] is False
    assert payload["resident_runtime_authority_grant_preflight"]["overlay_control_authority"] is False
    assert payload["resident_runtime_authority_grant_preflight"]["memory_write"] is False
    assert payload["resident_runtime_authority_grant_preflight"]["receipt_write_authority"] is False
    assert payload["resident_runtime_authority_grant_preflight"]["resident_claim_authority"] is False
    assert payload["resident_runtime_activation_plan"]["status"] == "blocked"
    assert payload["resident_runtime_activation_plan"]["ok"] is True
    assert payload["resident_runtime_activation_plan"]["plan_available"] is True
    assert payload["resident_runtime_activation_plan"]["runtime_ready"] is False
    assert payload["resident_runtime_activation_plan"]["resident_claim_allowed"] is False
    assert "/lens/resident-runtime/plan" in payload["resident_runtime_activation_plan"]["evidence"]
    assert "resident_runtime_execution_authority_not_granted" in payload["resident_runtime_activation_plan"]["blockers"]
    assert "process_supervision_authority_not_granted" in payload["resident_runtime_activation_plan"]["blockers"]
    assert "tray_registration_authority_not_granted" in payload["resident_runtime_activation_plan"]["blockers"]
    assert "overlay_control_authority_not_granted" in payload["resident_runtime_activation_plan"]["blockers"]
    assert payload["resident_runtime_activation_plan"]["execution_authority"] is False
    assert payload["resident_runtime_activation_plan"]["approval_decision_authority"] is False
    assert payload["resident_runtime_activation_plan"]["local_process_launch_authority"] is False
    assert payload["resident_runtime_activation_plan"]["process_supervision_authority"] is False
    assert payload["resident_runtime_activation_plan"]["service_install_authority"] is False
    assert payload["resident_runtime_activation_plan"]["service_control_authority"] is False
    assert payload["resident_runtime_activation_plan"]["hotkey_registration_authority"] is False
    assert payload["resident_runtime_activation_plan"]["tray_registration_authority"] is False
    assert payload["resident_runtime_activation_plan"]["overlay_control_authority"] is False
    assert payload["resident_runtime_activation_plan"]["memory_write"] is False
    assert payload["resident_runtime_authority_boundary"]["status"] == "blocked"
    assert payload["resident_runtime_authority_boundary"]["ok"] is True
    assert payload["resident_runtime_authority_boundary"]["applied"] is False
    assert payload["resident_runtime_authority_boundary"]["executed"] is False
    assert "/lens/resident-runtime/execute" in payload["resident_runtime_authority_boundary"]["evidence"]
    assert (
        "resident_runtime_execution_authority_not_granted" in payload["resident_runtime_authority_boundary"]["blockers"]
    )
    assert "process_supervision_authority_not_granted" in payload["resident_runtime_authority_boundary"]["blockers"]
    assert "service_control_authority_not_granted" in payload["resident_runtime_authority_boundary"]["blockers"]
    assert "tray_registration_authority_not_granted" in payload["resident_runtime_authority_boundary"]["blockers"]
    assert "overlay_control_authority_not_granted" in payload["resident_runtime_authority_boundary"]["blockers"]
    assert payload["resident_runtime_authority_boundary"]["execution_authority"] is False
    assert payload["resident_runtime_authority_boundary"]["approval_decision_authority"] is False
    assert payload["resident_runtime_authority_boundary"]["local_process_launch_authority"] is False
    assert payload["resident_runtime_authority_boundary"]["process_supervision_authority"] is False
    assert payload["resident_runtime_authority_boundary"]["service_install_authority"] is False
    assert payload["resident_runtime_authority_boundary"]["service_control_authority"] is False
    assert payload["resident_runtime_authority_boundary"]["hotkey_registration_authority"] is False
    assert payload["resident_runtime_authority_boundary"]["tray_registration_authority"] is False
    assert payload["resident_runtime_authority_boundary"]["overlay_control_authority"] is False
    assert payload["resident_runtime_authority_boundary"]["memory_write"] is False
    assert payload["resident_runtime_authority_boundary"]["receipt_write_authority"] is False
    assert payload["resident_runtime_authority_boundary"]["resident_claim_authority"] is False
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
    assert payload["host_supervisor_observation_proof"]["status"] == "proof_passed"
    assert payload["host_supervisor_observation_proof"]["ok"] is True
    assert payload["host_supervisor_observation_proof"]["exit_code"] == 0
    assert payload["host_supervisor_observation_proof"]["bounded_supervisor_observed"] is True
    assert payload["host_supervisor_observation_proof"]["supervisor_observed_running_state"] is True
    assert payload["host_supervisor_observation_proof"]["supervisor_observed_stopped_state"] is True
    assert payload["host_supervisor_observation_proof"]["ready_for_resident_claim"] is False
    assert "resident_host_process_not_supervised" in payload["host_supervisor_observation_proof"]["blockers"]
    assert payload["resident_overlay_runtime_proof"]["status"] == "proof_passed"
    assert payload["resident_overlay_runtime_proof"]["ok"] is True
    assert payload["resident_overlay_runtime_proof"]["exit_code"] == 0
    assert payload["resident_overlay_runtime_proof"]["bounded_supervisor_observed"] is True
    assert payload["resident_overlay_runtime_proof"]["resident_overlay_runtime_ready"] is False
    assert payload["resident_overlay_runtime_proof"]["resident_overlay_runtime"] is False
    assert payload["resident_overlay_runtime_proof"]["overlay_window"] is False
    assert payload["resident_overlay_runtime_proof"]["tray_presence"] is False
    assert payload["resident_overlay_runtime_proof"]["global_hotkey_bound"] is False
    assert payload["resident_overlay_runtime_proof"]["summon_anywhere"] is False
    assert payload["resident_overlay_runtime_proof"]["ready_for_lens_resident_claim"] is False
    assert "resident_overlay_runtime_missing" in payload["resident_overlay_runtime_proof"]["blockers"]
    assert "operator_experience_proof_missing" not in payload["resident_overlay_runtime_proof"]["blockers"]
    assert "scripts/lens-resident-overlay-runtime-proof.ps1" in payload["resident_overlay_runtime_proof"]["evidence"]
    assert payload["resident_overlay_activation_boundary_proof"]["status"] == "proof_passed"
    assert payload["resident_overlay_activation_boundary_proof"]["ok"] is True
    assert payload["resident_overlay_activation_boundary_proof"]["exit_code"] == 0
    assert payload["resident_overlay_activation_boundary_proof"]["live_operator_experience_proof"] is True
    assert payload["resident_overlay_activation_boundary_proof"]["resident_overlay_boundary_observed"] is True
    assert payload["resident_overlay_activation_boundary_proof"]["activation_boundary_observed"] is True
    assert payload["resident_overlay_activation_boundary_proof"]["resident_overlay_activation_ready"] is False
    assert payload["resident_overlay_activation_boundary_proof"]["activation_ready"] is False
    assert payload["resident_overlay_activation_boundary_proof"]["execution_ready"] is False
    assert payload["resident_overlay_activation_boundary_proof"]["executed"] is False
    assert payload["resident_overlay_activation_boundary_proof"]["applied"] is False
    assert payload["resident_overlay_activation_boundary_proof"]["would_launch_process"] is False
    assert payload["resident_overlay_activation_boundary_proof"]["would_install_service"] is False
    assert payload["resident_overlay_activation_boundary_proof"]["would_start_service"] is False
    assert payload["resident_overlay_activation_boundary_proof"]["would_register_hotkey"] is False
    assert payload["resident_overlay_activation_boundary_proof"]["would_open_overlay"] is False
    assert payload["resident_overlay_activation_boundary_proof"]["would_write_memory"] is False
    assert payload["resident_overlay_activation_boundary_proof"]["would_decide_approval"] is False
    assert (
        "resident_overlay_activation_not_authorized"
        in payload["resident_overlay_activation_boundary_proof"]["blockers"]
    )
    assert "operator_experience_proof_missing" not in payload["resident_overlay_activation_boundary_proof"]["blockers"]
    assert (
        "live_operator_experience_proof_missing"
        not in payload["resident_overlay_activation_boundary_proof"]["blockers"]
    )
    assert (
        "scripts/lens-resident-overlay-activation-boundary-proof.ps1"
        in payload["resident_overlay_activation_boundary_proof"]["evidence"]
    )
    assert payload["next_smallest_truthful_gap"] == "supervised_resident_host_runtime_execution_policy_contract"
    assert payload["governance"] == {
        "read_only_contract": True,
        "diagnostic_only": True,
        "live_http_readback": True,
        "temporary_api_process": True,
        "bounded_host_launch": True,
        "bounded_supervisor_observation": True,
        "resident_overlay_boundary_observed": True,
        "resident_overlay_activation_boundary_observed": True,
        "resident_runtime_authority_boundary_observed": True,
        "resident_runtime_authority_grant_preflight_observed": True,
        "temporary_runtime_state_write": True,
        "execution_authority": False,
        "approval_decision_authority": False,
        "memory_write": False,
        "resident_overlay_activation_authority": False,
        "overlay_control_authority": False,
        "summon_authority": False,
        "capture_authority": False,
        "new_sensing_authority": False,
        "local_process_launch_authority": True,
        "api_local_process_launch_authority": False,
        "activation_local_process_launch_authority": False,
        "process_restart_authority": False,
        "process_supervision_authority": False,
        "service_install_authority": False,
        "service_control_authority": False,
        "hotkey_registration_authority": False,
        "tray_registration_authority": False,
        "receipt_write_authority": False,
        "denial_receipt_write_authority": False,
        "mutation_authority_granted": False,
    }
