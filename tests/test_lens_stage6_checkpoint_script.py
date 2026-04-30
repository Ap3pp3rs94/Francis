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
    assert criteria["helpful_not_noisy"]["status"] == "resident_surface_foreground_runtime_observed"
    assert criteria["helpful_not_noisy"]["ready"] is False
    assert criteria["helpful_not_noisy"]["blockers"] == [
        "resident_surface_not_resident",
        "resident_surface_runtime_not_supervised",
    ]
    assert "/lens/resident-surface" in criteria["helpful_not_noisy"]["evidence"]
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
    assert "resident_surface_runtime_missing" not in criteria["system_resident_presence"]["blockers"]
    assert "resident_surface_not_resident" in criteria["system_resident_presence"]["blockers"]
    assert "resident_surface_runtime_not_supervised" in criteria["system_resident_presence"]["blockers"]
    assert "resident_overlay_runtime_missing" in criteria["system_resident_presence"]["blockers"]
    assert "tray_host_missing" in payload["blockers"]
    assert "overlay_window_missing" in payload["blockers"]
    assert "scripts/lens-host-foreground-proof.ps1" in criteria["system_resident_presence"]["evidence"]
    assert "scripts/lens-host-launch-proof.ps1" in criteria["system_resident_presence"]["evidence"]
    assert "scripts/lens-host-supervisor-observation-proof.ps1" in criteria["system_resident_presence"]["evidence"]
    assert "scripts/lens-host-supervision-proof.ps1" in criteria["system_resident_presence"]["evidence"]
    assert "scripts/lens-resident-surface-proof.ps1" in criteria["system_resident_presence"]["evidence"]
    assert "/lens/resident-surface" in criteria["system_resident_presence"]["evidence"]
    assert "/lens/resident-runtime/preflight" in criteria["system_resident_presence"]["evidence"]
    assert "/lens/resident-runtime/policy" in criteria["system_resident_presence"]["evidence"]
    assert "/lens/resident-runtime/authority-grant" in criteria["system_resident_presence"]["evidence"]
    assert "/lens/resident-runtime/plan" in criteria["system_resident_presence"]["evidence"]
    assert "/lens/resident-runtime/execute" in criteria["system_resident_presence"]["evidence"]
    assert "scripts/lens-resident-overlay-runtime-proof.ps1" in criteria["system_resident_presence"]["evidence"]
    assert (
        "scripts/lens-resident-overlay-activation-boundary-proof.ps1"
        in criteria["system_resident_presence"]["evidence"]
    )
    assert "/lens/resident-surface/activation" in criteria["system_resident_presence"]["evidence"]
    assert "operator_experience_proof_missing" not in payload["blockers"]
    assert "resident_surface_runtime_missing" not in payload["blockers"]
    assert "resident_surface_not_resident" in payload["blockers"]
    assert "resident_surface_runtime_not_supervised" in payload["blockers"]
    assert "resident_surface_missing" not in payload["blockers"]
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
    assert payload["resident_runtime_execution_policy_contract"]["status"] == "readback_ready"
    assert payload["resident_runtime_execution_policy_contract"]["ok"] is True
    assert payload["resident_runtime_execution_policy_contract"]["ready"] is True
    assert payload["resident_runtime_execution_policy_contract"]["policy_contract_ready"] is True
    assert payload["resident_runtime_execution_policy_contract"]["execution_policy_ready"] is True
    assert payload["resident_runtime_execution_policy_contract"]["grant_ready"] is False
    assert payload["resident_runtime_execution_policy_contract"]["authority_grant_ready"] is False
    assert payload["resident_runtime_execution_policy_contract"]["runtime_ready"] is False
    assert payload["resident_runtime_execution_policy_contract"]["resident_claim_allowed"] is False
    assert "/lens/resident-runtime/policy" in payload["resident_runtime_execution_policy_contract"]["evidence"]
    assert (
        "resident_runtime_execution_authority_not_granted"
        in payload["resident_runtime_execution_policy_contract"]["blockers"]
    )
    assert (
        "resident_runtime_authority_grant_not_implemented"
        in payload["resident_runtime_execution_policy_contract"]["blockers"]
    )
    assert payload["resident_runtime_execution_policy_contract"]["execution_authority"] is False
    assert payload["resident_runtime_execution_policy_contract"]["approval_decision_authority"] is False
    assert payload["resident_runtime_execution_policy_contract"]["local_process_launch_authority"] is False
    assert payload["resident_runtime_execution_policy_contract"]["process_supervision_authority"] is False
    assert payload["resident_runtime_execution_policy_contract"]["service_install_authority"] is False
    assert payload["resident_runtime_execution_policy_contract"]["service_control_authority"] is False
    assert payload["resident_runtime_execution_policy_contract"]["hotkey_registration_authority"] is False
    assert payload["resident_runtime_execution_policy_contract"]["tray_registration_authority"] is False
    assert payload["resident_runtime_execution_policy_contract"]["overlay_control_authority"] is False
    assert payload["resident_runtime_execution_policy_contract"]["memory_write"] is False
    assert payload["resident_runtime_execution_policy_contract"]["receipt_write_authority"] is False
    assert payload["resident_runtime_execution_policy_contract"]["resident_claim_authority"] is False
    assert payload["resident_runtime_execution_authority_grant_boundary"]["status"] == "blocked"
    assert payload["resident_runtime_execution_authority_grant_boundary"]["ok"] is True
    assert payload["resident_runtime_execution_authority_grant_boundary"]["boundary_ready"] is True
    assert payload["resident_runtime_execution_authority_grant_boundary"]["applied"] is False
    assert payload["resident_runtime_execution_authority_grant_boundary"]["executed"] is False
    assert payload["resident_runtime_execution_authority_grant_boundary"]["authority_granted"] is False
    assert payload["resident_runtime_execution_authority_grant_boundary"]["grant_ready"] is False
    assert payload["resident_runtime_execution_authority_grant_boundary"]["authority_grant_ready"] is False
    assert payload["resident_runtime_execution_authority_grant_boundary"]["runtime_ready"] is False
    assert payload["resident_runtime_execution_authority_grant_boundary"]["resident_claim_allowed"] is False
    assert (
        "/lens/resident-runtime/authority-grant"
        in payload["resident_runtime_execution_authority_grant_boundary"]["evidence"]
    )
    assert (
        "resident_runtime_authority_grant_not_implemented"
        in payload["resident_runtime_execution_authority_grant_boundary"]["blockers"]
    )
    assert (
        "resident_runtime_execution_authority_not_granted"
        in payload["resident_runtime_execution_authority_grant_boundary"]["blockers"]
    )
    assert payload["resident_runtime_execution_authority_grant_boundary"]["execution_authority"] is False
    assert payload["resident_runtime_execution_authority_grant_boundary"]["approval_decision_authority"] is False
    assert payload["resident_runtime_execution_authority_grant_boundary"]["local_process_launch_authority"] is False
    assert payload["resident_runtime_execution_authority_grant_boundary"]["process_supervision_authority"] is False
    assert payload["resident_runtime_execution_authority_grant_boundary"]["service_install_authority"] is False
    assert payload["resident_runtime_execution_authority_grant_boundary"]["service_control_authority"] is False
    assert payload["resident_runtime_execution_authority_grant_boundary"]["hotkey_registration_authority"] is False
    assert payload["resident_runtime_execution_authority_grant_boundary"]["tray_registration_authority"] is False
    assert payload["resident_runtime_execution_authority_grant_boundary"]["overlay_control_authority"] is False
    assert payload["resident_runtime_execution_authority_grant_boundary"]["memory_write"] is False
    assert payload["resident_runtime_execution_authority_grant_boundary"]["receipt_write_authority"] is False
    assert payload["resident_runtime_execution_authority_grant_boundary"]["resident_claim_authority"] is False
    assert payload["resident_runtime_authority_grant_denial_receipts"]["status"] == "empty"
    assert payload["resident_runtime_authority_grant_denial_receipts"]["ok"] is True
    assert payload["resident_runtime_authority_grant_denial_receipts"]["receipt_count"] == 0
    assert payload["resident_runtime_authority_grant_denial_receipts"]["latest_receipt_id"] == ""
    assert (
        "/lens/resident-runtime/authority-grant/denials"
        in payload["resident_runtime_authority_grant_denial_receipts"]["evidence"]
    )
    assert payload["resident_runtime_authority_grant_denial_receipts"]["execution_authority"] is False
    assert payload["resident_runtime_authority_grant_denial_receipts"]["approval_decision_authority"] is False
    assert payload["resident_runtime_authority_grant_denial_receipts"]["process_supervision_authority"] is False
    assert payload["resident_runtime_authority_grant_denial_receipts"]["service_control_authority"] is False
    assert payload["resident_runtime_authority_grant_denial_receipts"]["memory_write"] is False
    assert payload["resident_runtime_authority_grant_denial_receipts"]["receipt_write_authority"] is False
    assert payload["resident_runtime_authority_grant_denial_receipts"]["denial_receipt_write_authority"] is False
    assert payload["resident_runtime_authority_grant_readiness_audit"]["status"] == "blocked"
    assert payload["resident_runtime_authority_grant_readiness_audit"]["audit_status"] == "complete"
    assert payload["resident_runtime_authority_grant_readiness_audit"]["ok"] is True
    assert (
        "/lens/resident-runtime/authority-grant/readiness"
        in (payload["resident_runtime_authority_grant_readiness_audit"]["evidence"])
    )
    assert payload["resident_runtime_authority_grant_readiness_audit"]["ready"] is False
    assert payload["resident_runtime_authority_grant_readiness_audit"]["grant_ready"] is False
    assert payload["resident_runtime_authority_grant_readiness_audit"]["authority_grant_ready"] is False
    assert payload["resident_runtime_authority_grant_readiness_audit"]["runtime_ready"] is False
    assert payload["resident_runtime_authority_grant_readiness_audit"]["resident_claim_allowed"] is False
    assert payload["resident_runtime_authority_grant_readiness_audit"]["boundary_observed"] is True
    assert payload["resident_runtime_authority_grant_readiness_audit"]["denial_receipt_readback_ready"] is True
    assert payload["resident_runtime_authority_grant_readiness_audit"]["requirements_total"] >= 10
    assert payload["resident_runtime_authority_grant_readiness_audit"]["requirements_blocked_total"] >= 5
    assert (
        "authority_grant_implementation"
        in (payload["resident_runtime_authority_grant_readiness_audit"]["blocked_requirements"])
    )
    assert (
        "resident_runtime_authority_grant_not_implemented"
        in (payload["resident_runtime_authority_grant_readiness_audit"]["blockers"])
    )
    assert payload["resident_runtime_authority_grant_readiness_audit"]["execution_authority"] is False
    assert payload["resident_runtime_authority_grant_readiness_audit"]["approval_decision_authority"] is False
    assert payload["resident_runtime_authority_grant_readiness_audit"]["process_supervision_authority"] is False
    assert payload["resident_runtime_authority_grant_readiness_audit"]["service_control_authority"] is False
    assert payload["resident_runtime_authority_grant_readiness_audit"]["memory_write"] is False
    assert payload["resident_runtime_authority_grant_readiness_audit"]["receipt_write_authority"] is False
    assert payload["resident_host_supervision_authority_preflight"]["status"] == "blocked"
    assert payload["resident_host_supervision_authority_preflight"]["ok"] is True
    assert "/lens/host/supervision/authority" in payload["resident_host_supervision_authority_preflight"]["evidence"]
    assert payload["resident_host_supervision_authority_preflight"]["ready"] is False
    assert payload["resident_host_supervision_authority_preflight"]["preflight_ready"] is True
    assert payload["resident_host_supervision_authority_preflight"]["authority_ready"] is False
    assert payload["resident_host_supervision_authority_preflight"]["requirements_total"] >= 10
    assert payload["resident_host_supervision_authority_preflight"]["requirements_blocked_total"] >= 5
    assert (
        "process_supervision_authority"
        in payload["resident_host_supervision_authority_preflight"]["blocked_requirements"]
    )
    assert (
        "service_control_authority" in payload["resident_host_supervision_authority_preflight"]["blocked_requirements"]
    )
    assert (
        "resident_host_supervision_authority_not_granted"
        in payload["resident_host_supervision_authority_preflight"]["blockers"]
    )
    assert (
        "process_supervision_authority_not_granted"
        in payload["resident_host_supervision_authority_preflight"]["blockers"]
    )
    assert payload["resident_host_supervision_authority_preflight"]["execution_authority"] is False
    assert payload["resident_host_supervision_authority_preflight"]["approval_decision_authority"] is False
    assert payload["resident_host_supervision_authority_preflight"]["process_supervision_authority"] is False
    assert payload["resident_host_supervision_authority_preflight"]["process_restart_authority"] is False
    assert payload["resident_host_supervision_authority_preflight"]["service_install_authority"] is False
    assert payload["resident_host_supervision_authority_preflight"]["service_control_authority"] is False
    assert payload["resident_host_supervision_authority_preflight"]["memory_write"] is False
    assert payload["resident_host_supervision_authority_preflight"]["receipt_write_authority"] is False
    assert payload["resident_host_supervision_authority_denial_boundary"]["status"] == "blocked"
    assert payload["resident_host_supervision_authority_denial_boundary"]["ok"] is True
    assert (
        "/lens/host/supervision/authority" in payload["resident_host_supervision_authority_denial_boundary"]["evidence"]
    )
    assert payload["resident_host_supervision_authority_denial_boundary"]["boundary_ready"] is True
    assert payload["resident_host_supervision_authority_denial_boundary"]["applied"] is False
    assert payload["resident_host_supervision_authority_denial_boundary"]["executed"] is False
    assert payload["resident_host_supervision_authority_denial_boundary"]["authority_granted"] is False
    assert payload["resident_host_supervision_authority_denial_boundary"]["ready"] is False
    assert payload["resident_host_supervision_authority_denial_boundary"]["authority_ready"] is False
    assert (
        "host_supervision_authority_grant_not_implemented"
        not in payload["resident_host_supervision_authority_denial_boundary"]["blockers"]
    )
    assert "approval_id_required" in payload["resident_host_supervision_authority_denial_boundary"]["blockers"]
    assert (
        "process_supervision_authority_not_granted"
        in payload["resident_host_supervision_authority_denial_boundary"]["blockers"]
    )
    assert payload["resident_host_supervision_authority_denial_boundary"]["execution_authority"] is False
    assert payload["resident_host_supervision_authority_denial_boundary"]["approval_decision_authority"] is False
    assert payload["resident_host_supervision_authority_denial_boundary"]["process_supervision_authority"] is False
    assert payload["resident_host_supervision_authority_denial_boundary"]["process_restart_authority"] is False
    assert payload["resident_host_supervision_authority_denial_boundary"]["service_install_authority"] is False
    assert payload["resident_host_supervision_authority_denial_boundary"]["service_control_authority"] is False
    assert payload["resident_host_supervision_authority_denial_boundary"]["memory_write"] is False
    assert payload["resident_host_supervision_authority_denial_boundary"]["receipt_write_authority"] is False
    assert payload["resident_host_supervision_authority_denial_boundary"]["denial_receipt_write_authority"] is False
    assert payload["resident_host_supervision_authority_denial_receipts"]["status"] == "empty"
    assert payload["resident_host_supervision_authority_denial_receipts"]["ok"] is True
    assert (
        "/lens/host/supervision/authority/denials"
        in payload["resident_host_supervision_authority_denial_receipts"]["evidence"]
    )
    assert payload["resident_host_supervision_authority_denial_receipts"]["receipt_count"] == 0
    assert payload["resident_host_supervision_authority_denial_receipts"]["latest_receipt_id"] == ""
    assert payload["resident_host_supervision_authority_denial_receipts"]["execution_authority"] is False
    assert payload["resident_host_supervision_authority_denial_receipts"]["approval_decision_authority"] is False
    assert payload["resident_host_supervision_authority_denial_receipts"]["process_supervision_authority"] is False
    assert payload["resident_host_supervision_authority_denial_receipts"]["service_control_authority"] is False
    assert payload["resident_host_supervision_authority_denial_receipts"]["memory_write"] is False
    assert payload["resident_host_supervision_authority_denial_receipts"]["receipt_write_authority"] is False
    assert payload["resident_host_supervision_authority_denial_receipts"]["denial_receipt_write_authority"] is False
    assert payload["resident_host_supervision_authority_grant_receipts"]["status"] == "empty"
    assert payload["resident_host_supervision_authority_grant_receipts"]["ok"] is True
    assert (
        "/lens/host/supervision/authority/grants"
        in payload["resident_host_supervision_authority_grant_receipts"]["evidence"]
    )
    assert payload["resident_host_supervision_authority_grant_receipts"]["receipt_count"] == 0
    assert payload["resident_host_supervision_authority_grant_receipts"]["latest_receipt_id"] == ""
    assert payload["resident_host_supervision_authority_grant_receipts"]["active_receipt_id"] == ""
    assert payload["resident_host_supervision_authority_grant_receipts"]["authority_granted"] is False
    assert payload["resident_host_supervision_authority_grant_receipts"]["execution_authority"] is False
    assert payload["resident_host_supervision_authority_grant_receipts"]["approval_decision_authority"] is False
    assert payload["resident_host_supervision_authority_grant_receipts"]["process_supervision_authority"] is False
    assert payload["resident_host_supervision_authority_grant_receipts"]["service_control_authority"] is False
    assert payload["resident_host_supervision_authority_grant_receipts"]["memory_write"] is False
    assert payload["resident_host_supervision_authority_grant_receipts"]["receipt_write_authority"] is False
    assert payload["resident_host_supervision_authority_grant_receipts"]["denial_receipt_write_authority"] is False
    assert payload["resident_host_supervision_authority_readiness_audit"]["status"] == "blocked"
    assert payload["resident_host_supervision_authority_readiness_audit"]["audit_status"] == "complete"
    assert payload["resident_host_supervision_authority_readiness_audit"]["ok"] is True
    assert (
        "/lens/host/supervision/authority/readiness"
        in payload["resident_host_supervision_authority_readiness_audit"]["evidence"]
    )
    assert payload["resident_host_supervision_authority_readiness_audit"]["ready"] is False
    assert payload["resident_host_supervision_authority_readiness_audit"]["preflight_ready"] is True
    assert payload["resident_host_supervision_authority_readiness_audit"]["authority_ready"] is False
    assert payload["resident_host_supervision_authority_readiness_audit"]["supervision_ready"] is False
    assert payload["resident_host_supervision_authority_readiness_audit"]["resident_claim_allowed"] is False
    assert payload["resident_host_supervision_authority_readiness_audit"]["boundary_observed"] is True
    assert payload["resident_host_supervision_authority_readiness_audit"]["denial_receipt_readback_ready"] is True
    assert payload["resident_host_supervision_authority_readiness_audit"]["grant_receipt_readback_ready"] is True
    assert payload["resident_host_supervision_authority_readiness_audit"]["receipt_count"] == 0
    assert payload["resident_host_supervision_authority_readiness_audit"]["latest_receipt_id"] == ""
    assert payload["resident_host_supervision_authority_readiness_audit"]["grant_receipt_count"] == 0
    assert payload["resident_host_supervision_authority_readiness_audit"]["latest_grant_receipt_id"] == ""
    assert payload["resident_host_supervision_authority_readiness_audit"]["active_grant_receipt_id"] == ""
    assert payload["resident_host_supervision_authority_readiness_audit"]["requirements_total"] >= 11
    assert payload["resident_host_supervision_authority_readiness_audit"]["requirements_blocked_total"] >= 6
    assert (
        "authority_grant_implementation"
        not in payload["resident_host_supervision_authority_readiness_audit"]["blocked_requirements"]
    )
    assert (
        "process_supervision_authority"
        in payload["resident_host_supervision_authority_readiness_audit"]["blocked_requirements"]
    )
    assert (
        "host_supervision_authority_grant_not_implemented"
        not in payload["resident_host_supervision_authority_readiness_audit"]["blockers"]
    )
    assert (
        "process_supervision_authority_not_granted"
        in payload["resident_host_supervision_authority_readiness_audit"]["blockers"]
    )
    assert payload["resident_host_supervision_authority_readiness_audit"]["execution_authority"] is False
    assert payload["resident_host_supervision_authority_readiness_audit"]["approval_decision_authority"] is False
    assert payload["resident_host_supervision_authority_readiness_audit"]["process_supervision_authority"] is False
    assert payload["resident_host_supervision_authority_readiness_audit"]["process_restart_authority"] is False
    assert payload["resident_host_supervision_authority_readiness_audit"]["service_install_authority"] is False
    assert payload["resident_host_supervision_authority_readiness_audit"]["service_control_authority"] is False
    assert payload["resident_host_supervision_authority_readiness_audit"]["memory_write"] is False
    assert payload["resident_host_supervision_authority_readiness_audit"]["receipt_write_authority"] is False
    assert payload["resident_host_supervision_authority_readiness_audit"]["denial_receipt_write_authority"] is False
    assert payload["persistent_supervision_enablement_denial_boundary"]["status"] == "blocked"
    assert payload["persistent_supervision_enablement_denial_boundary"]["ok"] is True
    assert (
        "/lens/host/persistent-supervision/enablement"
        in (payload["persistent_supervision_enablement_denial_boundary"]["evidence"])
    )
    assert payload["persistent_supervision_enablement_denial_boundary"]["boundary_ready"] is True
    assert payload["persistent_supervision_enablement_denial_boundary"]["applied"] is False
    assert payload["persistent_supervision_enablement_denial_boundary"]["executed"] is False
    assert payload["persistent_supervision_enablement_denial_boundary"]["authority_granted"] is False
    assert payload["persistent_supervision_enablement_denial_boundary"]["enablement_ready"] is False
    assert payload["persistent_supervision_enablement_denial_boundary"]["resident_claim_allowed"] is False
    assert payload["persistent_supervision_enablement_denial_boundary"]["service_config_updated"] is False
    assert payload["persistent_supervision_enablement_denial_boundary"]["authority_grant_active"] is False
    assert (
        "host_supervision_authority_grant_not_active"
        in (payload["persistent_supervision_enablement_denial_boundary"]["blockers"])
    )
    assert (
        "persistent_supervision_enablement_authority_not_granted"
        in (payload["persistent_supervision_enablement_denial_boundary"]["blockers"])
    )
    assert (
        "service_config_write_authority_not_granted"
        in (payload["persistent_supervision_enablement_denial_boundary"]["blockers"])
    )
    assert payload["persistent_supervision_enablement_denial_boundary"]["execution_authority"] is False
    assert payload["persistent_supervision_enablement_denial_boundary"]["approval_decision_authority"] is False
    assert payload["persistent_supervision_enablement_denial_boundary"]["process_supervision_authority"] is False
    assert payload["persistent_supervision_enablement_denial_boundary"]["process_restart_authority"] is False
    assert payload["persistent_supervision_enablement_denial_boundary"]["service_config_write_authority"] is False
    assert payload["persistent_supervision_enablement_denial_boundary"]["service_control_authority"] is False
    assert payload["persistent_supervision_enablement_denial_boundary"]["memory_write"] is False
    assert payload["persistent_supervision_enablement_denial_boundary"]["receipt_write_authority"] is False
    assert payload["persistent_supervision_enablement_denial_boundary"]["denial_receipt_write_authority"] is False
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
    assert payload["resident_surface_content_readback"]["status"] == "blocked"
    assert payload["resident_surface_content_readback"]["ok"] is True
    assert payload["resident_surface_content_readback"]["route"] == "/lens/resident-surface"
    assert payload["resident_surface_content_readback"]["activation_route"] == "/lens/resident-surface/activation"
    assert payload["resident_surface_content_readback"]["contract_status"] == "readback_ready"
    assert payload["resident_surface_content_readback"]["content_contract_ready"] is True
    assert payload["resident_surface_content_readback"]["resident_surface_ready"] is False
    assert payload["resident_surface_content_readback"]["resident_overlay_runtime"] is False
    assert payload["resident_surface_content_readback"]["resident_claim_allowed"] is False
    assert payload["resident_surface_content_readback"]["execution_authority"] is False
    assert payload["resident_surface_content_readback"]["approval_decision_authority"] is False
    assert payload["resident_surface_content_readback"]["memory_write"] is False
    assert payload["resident_surface_content_readback"]["overlay_control_authority"] is False
    assert payload["resident_surface_content_readback"]["summon_authority"] is False
    assert payload["resident_surface_content_readback"]["resident_claim_authority"] is False
    assert "resident_surface_runtime_missing" in payload["resident_surface_content_readback"]["blockers"]
    assert "resident_surface_missing" not in payload["resident_surface_content_readback"]["blockers"]
    assert payload["resident_surface_foreground_runtime_proof"]["status"] == "proof_passed"
    assert payload["resident_surface_foreground_runtime_proof"]["ok"] is True
    assert payload["resident_surface_foreground_runtime_proof"]["exit_code"] == 0
    assert payload["resident_surface_foreground_runtime_proof"]["resident_surface_content_readback"] is True
    assert payload["resident_surface_foreground_runtime_proof"]["resident_surface_foreground_runtime_readback"] is True
    assert payload["resident_surface_foreground_runtime_proof"]["resident_surface_foreground_runtime_observed"] is True
    assert (
        payload["resident_surface_foreground_runtime_proof"]["resident_surface_runtime_status"]
        == "foreground_runtime_observed"
    )
    assert payload["resident_surface_foreground_runtime_proof"]["foreground_host_process_observed"] is True
    assert payload["resident_surface_foreground_runtime_proof"]["foreground_host_runtime_completed"] is True
    assert payload["resident_surface_foreground_runtime_proof"]["resident_surface_ready"] is False
    assert payload["resident_surface_foreground_runtime_proof"]["resident_claim_allowed"] is False
    assert payload["resident_surface_foreground_runtime_proof"]["resident_host_process"] is False
    assert payload["resident_surface_foreground_runtime_proof"]["execution_authority"] is False
    assert payload["resident_surface_foreground_runtime_proof"]["approval_decision_authority"] is False
    assert payload["resident_surface_foreground_runtime_proof"]["memory_write"] is False
    assert payload["resident_surface_foreground_runtime_proof"]["process_supervision_authority"] is False
    assert payload["resident_surface_foreground_runtime_proof"]["service_control_authority"] is False
    assert payload["resident_surface_foreground_runtime_proof"]["resident_claim_authority"] is False
    assert "resident_surface_not_resident" in payload["resident_surface_foreground_runtime_proof"]["blockers"]
    assert "resident_surface_runtime_not_supervised" in payload["resident_surface_foreground_runtime_proof"]["blockers"]
    assert "resident_surface_runtime_missing" not in payload["resident_surface_foreground_runtime_proof"]["blockers"]
    assert payload["live_operator_experience_proof"]["status"] == "proof_passed"
    assert payload["live_operator_experience_proof"]["ok"] is True
    assert payload["live_operator_experience_proof"]["exit_code"] == 0
    assert payload["live_operator_experience_proof"]["live_http_status_readback"] is True
    assert payload["live_operator_experience_proof"]["helpful_not_noisy_readback"] is True
    assert payload["live_operator_experience_proof"]["operator_experience_proof"] is True
    assert payload["live_operator_experience_proof"]["live_operator_experience_ready"] is False
    assert payload["live_operator_experience_proof"]["ready_for_stage6_closure"] is False
    assert "resident_surface_runtime_missing" in payload["live_operator_experience_proof"]["blockers"]
    assert "resident_surface_missing" not in payload["live_operator_experience_proof"]["blockers"]
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
    assert payload["host_supervisor_owned_session"]["status"] == "supervised_session_completed"
    assert payload["host_supervisor_owned_session"]["ok"] is True
    assert payload["host_supervisor_owned_session"]["exit_code"] == 0
    assert payload["host_supervisor_owned_session"]["supervisor_started_process"] is True
    assert payload["host_supervisor_owned_session"]["bounded_supervised_session"] is True
    assert payload["host_supervisor_owned_session"]["bounded_supervisor_observed"] is True
    assert payload["host_supervisor_owned_session"]["temporary_host_process_observed"] is True
    assert payload["host_supervisor_owned_session"]["supervisor_observed_running_state"] is True
    assert payload["host_supervisor_owned_session"]["supervisor_observed_stopped_state"] is True
    assert payload["host_supervisor_owned_session"]["ready_for_resident_claim"] is False
    assert payload["host_supervisor_owned_session"]["resident_host_process"] is False
    assert payload["host_supervisor_owned_session"]["resident_supervised_runtime"] is False
    assert payload["host_supervisor_owned_session"]["supervised"] is False
    assert payload["host_supervisor_owned_session"]["local_process_launch_authority"] is True
    assert payload["host_supervisor_owned_session"]["api_local_process_launch_authority"] is False
    assert payload["host_supervisor_owned_session"]["execution_authority"] is False
    assert payload["host_supervisor_owned_session"]["approval_decision_authority"] is False
    assert payload["host_supervisor_owned_session"]["memory_write"] is False
    assert payload["host_supervisor_owned_session"]["process_supervision_authority"] is False
    assert payload["host_supervisor_owned_session"]["process_restart_authority"] is False
    assert payload["host_supervisor_owned_session"]["service_control_authority"] is False
    assert payload["host_supervisor_owned_session"]["resident_claim_authority"] is False
    assert "resident_host_process_missing" not in payload["host_supervisor_owned_session"]["blockers"]
    assert "resident_host_process_not_resident" in payload["host_supervisor_owned_session"]["blockers"]
    assert "resident_supervision_not_persistent" in payload["host_supervisor_owned_session"]["blockers"]
    assert "process_supervision_authority_not_granted" in payload["host_supervisor_owned_session"]["blockers"]
    assert (
        "scripts/lens-host-supervisor.ps1 -Mode SuperviseOnce" in payload["host_supervisor_owned_session"]["evidence"]
    )
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
    assert payload["next_smallest_truthful_gap"] == "stage6_lens_completion_audit"
    assert payload["governance"] == {
        "read_only_contract": True,
        "diagnostic_only": True,
        "live_http_readback": True,
        "temporary_api_process": True,
        "bounded_host_launch": True,
        "bounded_supervisor_observation": True,
        "bounded_supervisor_owned_session": True,
        "resident_overlay_boundary_observed": True,
        "resident_overlay_activation_boundary_observed": True,
        "resident_surface_foreground_runtime_proof_observed": True,
        "resident_runtime_authority_boundary_observed": True,
        "resident_runtime_authority_grant_preflight_observed": True,
        "resident_runtime_execution_policy_contract_observed": True,
        "resident_runtime_execution_authority_grant_boundary_observed": True,
        "resident_runtime_execution_authority_grant_denial_receipt_readback_observed": True,
        "resident_runtime_execution_authority_grant_readiness_audit_observed": True,
        "resident_host_supervision_authority_preflight_observed": True,
        "resident_host_supervision_authority_denial_boundary_observed": True,
        "resident_host_supervision_authority_denial_receipt_readback_observed": True,
        "resident_host_supervision_authority_grant_receipt_readback_observed": True,
        "resident_host_supervision_authority_readiness_audit_observed": True,
        "persistent_supervision_enablement_denial_boundary_observed": True,
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
