from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
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
    with tempfile.TemporaryDirectory(prefix="francis-lens-stage6-checkpoint-test-") as data_dir:
        env = os.environ.copy()
        env["FRANCIS_DATA_DIR"] = data_dir
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
            env=env,
            check=False,
            text=True,
            capture_output=True,
            timeout=540,
        )


def test_lens_stage6_checkpoint_honors_explicit_observation_windows_without_changing_defaults() -> None:
    script = (_repo_root() / "scripts" / "lens-stage6-checkpoint.ps1").read_text(encoding="utf-8")

    assert (
        "$ResidentSurfaceForegroundMinimumSeconds = if "
        "($PSBoundParameters.ContainsKey('ResidentSurfaceForegroundRunSeconds')) { 2 } else { 25 }"
    ) in script
    assert (
        "$SupervisorObservationMinimumSeconds = if ($PSBoundParameters.ContainsKey('SupervisorRunSeconds')) "
        "{ 3 } else { 12 }"
    ) in script
    assert (
        "$ResidentOverlayActivationStartupMinimumSeconds = if "
        "($PSBoundParameters.ContainsKey('StartupTimeoutSeconds')) { 5 } else { 20 }"
    ) in script
    assert (
        "$ResidentOverlayActivationSupervisorMinimumSeconds = if "
        "($PSBoundParameters.ContainsKey('SupervisorRunSeconds')) { 3 } else { 25 }"
    ) in script
    assert (
        "$ResidentOverlayActivationResidentSurfaceForegroundMinimumSeconds = if "
        "($PSBoundParameters.ContainsKey('ResidentSurfaceForegroundRunSeconds')) { 2 } else { 25 }"
    ) in script
    assert "$ResidentOverlayRuntimeProofCachePath = Write-ProofPayloadCache" in script
    assert "'-CachedResidentOverlayRuntimeProofPath', $ResidentOverlayRuntimeProofCachePath" in script
    assert "$ResidentRuntimeAuthorityBlockersProofCachePath = Write-ProofPayloadCache" in script
    assert "'-CachedAuthorityBlockersProofPath', $ResidentRuntimeAuthorityBlockersProofCachePath" in script
    assert "$ResidentRuntimeTrayPresenceBoundaryProofCachePath = Write-ProofPayloadCache" in script
    assert "'-CachedTrayPresenceBoundaryProofPath', $ResidentRuntimeTrayPresenceBoundaryProofCachePath" in script
    assert "$SummonPreflightProofCachePath = Write-ProofPayloadCache" in script
    assert "'-CachedSummonPreflightProofPath', $SummonPreflightProofCachePath" in script
    assert "$ResidentRuntimeHotkeySummonBoundaryProofCachePath = Write-ProofPayloadCache" in script
    assert "'-CachedHotkeySummonBoundaryProofPath', $ResidentRuntimeHotkeySummonBoundaryProofCachePath" in script
    assert "$ResidentRuntimeOverlayWindowBoundaryProofCachePath = Write-ProofPayloadCache" in script
    assert "'-CachedOverlayWindowBoundaryProofPath', $ResidentRuntimeOverlayWindowBoundaryProofCachePath" in script


def test_lens_stage6_checkpoint_accepts_summon_runtime_readback_handoff() -> None:
    script = (_repo_root() / "scripts" / "lens-stage6-checkpoint.ps1").read_text(encoding="utf-8")

    assert "$SummonEnablementGateSummonBindingBlockerObserved = (" in script
    assert "$SummonEnablementGateSummonRuntimeReadbackObserved = (" in script
    assert "$SummonEnablementGateBlockers -contains 'summon_anywhere_runtime_readback'" in script
    assert "@($SummonEnablementGateAuthorityBlockers).Count -gt 0" in script
    assert (
        "($SummonEnablementGateSummonBindingBlockerObserved -or $SummonEnablementGateSummonRuntimeReadbackObserved)"
    ) in script


def test_lens_stage6_checkpoint_reports_blocked_done_criteria_without_authority() -> None:
    proc = _run_checkpoint(
        "-Mode",
        "Status",
        "-StartupTimeoutSeconds",
        "5",
        "-HostLaunchRunSeconds",
        "2",
        "-ResidentSurfaceForegroundRunSeconds",
        "5",
        "-SupervisorRunSeconds",
        "3",
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.stage6.checkpoint"
    assert payload["status"] == "blocked"
    assert payload["stage"] == "Stage 6 / Lens MVP"
    assert payload["stage_state"] == "active"
    assert payload["stage_claim"] == "backend_readback_contract_only"
    assert payload["ready_to_close"] is False
    assert payload["observation_windows"] == {
        "resident_surface_foreground_requested_seconds": 5,
        "resident_surface_foreground_effective_seconds": 5,
        "resident_surface_foreground_minimum_seconds": 2,
        "supervisor_requested_seconds": 3,
        "supervisor_effective_seconds": 3,
        "supervisor_minimum_seconds": 3,
        "resident_overlay_activation_startup_requested_seconds": 5,
        "resident_overlay_activation_startup_effective_seconds": 5,
        "resident_overlay_activation_startup_minimum_seconds": 5,
        "resident_overlay_activation_supervisor_requested_seconds": 3,
        "resident_overlay_activation_supervisor_effective_seconds": 3,
        "resident_overlay_activation_supervisor_minimum_seconds": 3,
        "resident_overlay_activation_resident_surface_foreground_requested_seconds": 5,
        "resident_overlay_activation_resident_surface_foreground_effective_seconds": 5,
        "resident_overlay_activation_resident_surface_foreground_minimum_seconds": 2,
    }
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
    assert "resident_host_process_missing" in enablement_gates["resident_supervision_enablement_gate"]["blockers"]
    assert "service_control_authority_false" in enablement_gates["resident_supervision_enablement_gate"]["blockers"]
    assert "/lens/host/supervision" in enablement_gates["resident_supervision_enablement_gate"]["evidence"]
    resident_supervision_gate = enablement_gates["resident_supervision_enablement_gate"]
    assert resident_supervision_gate["supervisor_readback_ready"] is True
    assert resident_supervision_gate["supervisor_freshness_status"] in {
        "missing",
        "fresh",
        "stale",
        "unknown",
    }
    assert isinstance(resident_supervision_gate["supervisor_state_stale"], bool)
    assert isinstance(resident_supervision_gate["fresh_supervisor_readback"], bool)
    if resident_supervision_gate["supervisor_freshness_status"] == "stale":
        assert "host_supervisor_readback_stale" in resident_supervision_gate["blockers"]
    assert enablement_gates["summon_enablement_gate"]["status"] == "blocked"
    assert enablement_gates["summon_enablement_gate"]["ready"] is False
    assert enablement_gates["summon_enablement_gate"]["summon_anywhere"] is False
    assert enablement_gates["summon_enablement_gate"]["global_hotkey"] == "Ctrl+Alt+Space"
    assert "summon_binding_missing" in enablement_gates["summon_enablement_gate"]["blockers"]
    summon_gate_groups = enablement_gates["summon_enablement_gate"]["blocker_groups"]
    assert "lens_host_persistent_supervision_prerequisites_pending" in summon_gate_groups["resident_host"]
    assert "local_process_launch_authority_not_granted" in summon_gate_groups["resident_host"]
    assert "global_hotkey_binding_missing" in summon_gate_groups["global_hotkey_binding"]
    assert "summon_binding_missing" in summon_gate_groups["summon_binding"]
    expected_summon_blocked_families = [
        "resident_host",
        "tray_presence",
        "overlay_window",
        "global_hotkey_binding",
        "summon_binding",
        "authority",
    ]
    expected_first_summon_handoff = {
        "id": "resident_host",
        "label": "Resident host",
        "status": "blocked",
        "proof_script": "scripts/lens-summon-resident-host-blocker-proof.ps1 -Mode Status",
        "route": "/lens/host",
        "readiness_route": "/lens/host/runtime-loop/readiness",
        "next_step": "run_resident_host_blocker_proof",
        "next_smallest_truthful_gap": "resident_host_runtime_blocker_boundary",
        "authority_required": "resident_runtime_execution_authority",
        "authority_granted": False,
        "read_only_contract": True,
        "diagnostic_only": True,
        "would_execute": False,
        "would_mutate": False,
    }
    expected_first_summon_handoff_required_blockers = {
        "lens_host_persistent_supervision_prerequisites_pending",
        "local_process_launch_authority_not_granted",
    }
    expected_first_summon_handoff_allowed_blockers = expected_first_summon_handoff_required_blockers | {
        "resident_host_process_missing"
    }
    assert enablement_gates["summon_enablement_gate"]["operator_surface_readback_ready"] is True
    assert enablement_gates["summon_enablement_gate"]["first_blocker_family"] == "resident_host"
    assert enablement_gates["summon_enablement_gate"]["blocked_families"] == expected_summon_blocked_families
    assert enablement_gates["summon_enablement_gate"]["first_blocker_family_handoff_observed"] is True
    summon_gate_first_handoff = enablement_gates["summon_enablement_gate"]["first_blocker_family_handoff"]
    assert {key: value for key, value in summon_gate_first_handoff.items() if key != "blockers"} == (
        expected_first_summon_handoff
    )
    assert expected_first_summon_handoff_required_blockers <= set(summon_gate_first_handoff["blockers"])
    assert set(summon_gate_first_handoff["blockers"]) <= expected_first_summon_handoff_allowed_blockers
    assert [item["id"] for item in enablement_gates["summon_enablement_gate"]["blocked_family_handoffs"]] == (
        expected_summon_blocked_families
    )
    summon_handoff = payload["summon_enablement_gate_handoff"]
    assert summon_handoff["status"] == "blocked"
    assert summon_handoff["ok"] is True
    assert summon_handoff["ready"] is False
    assert summon_handoff["summon_anywhere"] is False
    assert summon_handoff["operator_surface_readback_ready"] is True
    assert summon_handoff["handoff_observed"] is True
    assert summon_handoff["first_blocker_family"] == "resident_host"
    assert summon_handoff["blocked_families"] == expected_summon_blocked_families
    checkpoint_first_handoff = summon_handoff["first_blocker_family_handoff"]
    assert {key: value for key, value in checkpoint_first_handoff.items() if key != "blockers"} == (
        expected_first_summon_handoff
    )
    assert expected_first_summon_handoff_required_blockers <= set(checkpoint_first_handoff["blockers"])
    assert set(checkpoint_first_handoff["blockers"]) <= expected_first_summon_handoff_allowed_blockers
    assert [item["id"] for item in summon_handoff["blocked_family_handoffs"]] == expected_summon_blocked_families
    assert summon_handoff["next_smallest_truthful_gap"] == "summon_anywhere_blockers"
    assert "/lens/status" in summon_handoff["evidence"]
    assert "summon_authority_not_granted" in summon_handoff["blockers"]
    assert summon_handoff["execution_authority"] is False
    assert summon_handoff["approval_decision_authority"] is False
    assert summon_handoff["local_process_launch_authority"] is False
    assert summon_handoff["hotkey_registration_authority"] is False
    assert summon_handoff["tray_registration_authority"] is False
    assert summon_handoff["overlay_control_authority"] is False
    assert summon_handoff["summon_authority"] is False
    assert summon_handoff["memory_write"] is False
    assert summon_handoff["receipt_write_authority"] is False
    assert summon_handoff["resident_claim_authority"] is False
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
    helpful_blockers = set(criteria["helpful_not_noisy"]["blockers"])
    assert {"resident_surface_not_resident", "resident_surface_runtime_not_supervised"} <= helpful_blockers
    assert helpful_blockers <= {
        "operator_experience_proof_missing",
        "resident_surface_not_resident",
        "resident_surface_runtime_not_supervised",
    }
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
    host_supervisor_readback = payload["host_supervisor_readback"]
    assert host_supervisor_readback["readback_ready"] is True
    assert host_supervisor_readback["runtime_state_path"] == "data/runtime/lens-host-supervisor/status.json"
    assert host_supervisor_readback["freshness_window_seconds"] == 900
    assert host_supervisor_readback["freshness_status"] in {"missing", "fresh", "stale", "unknown"}
    assert isinstance(host_supervisor_readback["state_stale"], bool)
    assert isinstance(host_supervisor_readback["fresh_readback"], bool)
    assert isinstance(host_supervisor_readback["fresh_bounded_supervisor_observed"], bool)
    assert isinstance(host_supervisor_readback["fresh_supervised_session_completed"], bool)
    assert isinstance(host_supervisor_readback["supervisor_process_alive"], bool)
    assert isinstance(host_supervisor_readback["observed_process_alive"], bool)
    assert isinstance(host_supervisor_readback["observed_pid_matches_host_process"], bool)
    assert isinstance(host_supervisor_readback["resident_supervised_runtime"], bool)
    assert host_supervisor_readback["resident_claim_allowed"] is False
    assert host_supervisor_readback["execution_authority"] is False
    assert host_supervisor_readback["approval_decision_authority"] is False
    assert host_supervisor_readback["memory_write"] is False
    assert host_supervisor_readback["process_supervision_authority"] is False
    assert host_supervisor_readback["process_restart_authority"] is False
    assert host_supervisor_readback["service_control_authority"] is False
    assert host_supervisor_readback["resident_claim_authority"] is False
    if host_supervisor_readback["freshness_status"] == "stale":
        assert host_supervisor_readback["state_stale"] is True
        assert host_supervisor_readback["fresh_readback"] is False
        assert "host_supervisor_readback_stale" in host_supervisor_readback["blockers"]
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
        not in payload["resident_runtime_authority_grant_preflight"]["blockers"]
    )
    assert (
        "resident_runtime_execution_authority_not_granted"
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
        not in payload["resident_runtime_execution_policy_contract"]["blockers"]
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
        "/lens/resident-runtime/authority-grant/grants"
        in payload["resident_runtime_execution_authority_grant_boundary"]["evidence"]
    )
    assert "approval_id_required" in payload["resident_runtime_execution_authority_grant_boundary"]["blockers"]
    assert (
        "resident_runtime_authority_grant_not_implemented"
        not in payload["resident_runtime_execution_authority_grant_boundary"]["blockers"]
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
    assert payload["resident_runtime_authority_grant_receipts"]["status"] == "empty"
    assert payload["resident_runtime_authority_grant_receipts"]["ok"] is True
    assert payload["resident_runtime_authority_grant_receipts"]["receipt_count"] == 0
    assert payload["resident_runtime_authority_grant_receipts"]["latest_receipt_id"] == ""
    assert payload["resident_runtime_authority_grant_receipts"]["active_receipt_id"] == ""
    assert payload["resident_runtime_authority_grant_receipts"]["authority_granted"] is False
    assert payload["resident_runtime_authority_grant_receipts"]["resident_runtime_execution_authority"] is False
    assert (
        "/lens/resident-runtime/authority-grant/grants"
        in payload["resident_runtime_authority_grant_receipts"]["evidence"]
    )
    assert payload["resident_runtime_authority_grant_receipts"]["execution_authority"] is False
    assert payload["resident_runtime_authority_grant_receipts"]["approval_decision_authority"] is False
    assert payload["resident_runtime_authority_grant_receipts"]["process_supervision_authority"] is False
    assert payload["resident_runtime_authority_grant_receipts"]["service_control_authority"] is False
    assert payload["resident_runtime_authority_grant_receipts"]["memory_write"] is False
    assert payload["resident_runtime_authority_grant_receipts"]["receipt_write_authority"] is False
    assert payload["resident_runtime_authority_grant_receipts"]["denial_receipt_write_authority"] is False
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
    assert payload["resident_runtime_authority_grant_readiness_audit"]["authority_granted"] is False
    assert payload["resident_runtime_authority_grant_readiness_audit"]["resident_runtime_execution_authority"] is False
    assert payload["resident_runtime_authority_grant_readiness_audit"]["grant_receipt_readback_ready"] is True
    assert payload["resident_runtime_authority_grant_readiness_audit"]["denial_receipt_readback_ready"] is True
    assert payload["resident_runtime_authority_grant_readiness_audit"]["requirements_total"] >= 10
    assert payload["resident_runtime_authority_grant_readiness_audit"]["requirements_blocked_total"] >= 5
    assert (
        "authority_grant_implementation"
        not in (payload["resident_runtime_authority_grant_readiness_audit"]["blocked_requirements"])
    )
    assert (
        "exact_resident_runtime_execution_authority_approval"
        in (payload["resident_runtime_authority_grant_readiness_audit"]["blocked_requirements"])
    )
    assert (
        "resident_runtime_execution_authority"
        in (payload["resident_runtime_authority_grant_readiness_audit"]["blocked_requirements"])
    )
    assert payload["resident_runtime_authority_grant_readiness_audit"]["operator_surface_readback_ready"] is True
    assert (
        payload["resident_runtime_authority_grant_readiness_audit"]["first_blocked_requirement"]
        == "exact_resident_runtime_execution_authority_approval"
    )
    assert [
        item["id"]
        for item in payload["resident_runtime_authority_grant_readiness_audit"]["blocked_requirement_handoffs"]
    ] == payload["resident_runtime_authority_grant_readiness_audit"]["blocked_requirements"]
    assert payload["resident_runtime_authority_grant_readiness_audit"]["first_blocked_requirement_handoff"] == {
        "id": "exact_resident_runtime_execution_authority_approval",
        "label": "Exact approved resident runtime execution authority request",
        "status": "blocked",
        "route": "/lens/resident-runtime/authority-grant/requests",
        "readiness_route": "/lens/resident-runtime/authority-grant/readiness",
        "request_route": "/lens/resident-runtime/authority-grant/request",
        "requests_route": "/lens/resident-runtime/authority-grant/requests",
        "grant_route": "/lens/resident-runtime/authority-grant",
        "grants_route": "/lens/resident-runtime/authority-grant/grants",
        "denials_route": "/lens/resident-runtime/authority-grant/denials",
        "approval_action": "lens.resident_runtime.execution_authority",
        "next_step": "create_or_select_exact_approved_resident_runtime_execution_authority_request",
        "authority_required": "operator_approval",
        "authority_granted": False,
        "blockers": ["approval_id_required"],
        "would_execute": False,
        "would_mutate": False,
    }
    assert (
        payload["resident_runtime_authority_grant_readiness_audit"]["next_smallest_truthful_gap"]
        == "approve_resident_runtime_execution_authority_grant_receipt"
    )
    assert (
        "resident_runtime_authority_grant_not_implemented"
        not in (payload["resident_runtime_authority_grant_readiness_audit"]["blockers"])
    )
    assert (
        "resident_runtime_execution_authority_not_granted"
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
    assert payload["resident_host_supervision_authority_preflight"]["requirements_blocked_total"] >= 1
    assert "service_plan_ready" in payload["resident_host_supervision_authority_preflight"]["blocked_requirements"]
    assert (
        "resident_host_supervision_authority_not_granted"
        in payload["resident_host_supervision_authority_preflight"]["blockers"]
    )
    assert (
        "lens_host_persistent_supervision_prerequisites_pending"
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
    assert (
        "/lens/host/supervision/authority/requests"
        in payload["resident_host_supervision_authority_readiness_audit"]["evidence"]
    )
    assert payload["resident_host_supervision_authority_readiness_audit"]["ready"] is False
    assert payload["resident_host_supervision_authority_readiness_audit"]["preflight_ready"] is True
    assert payload["resident_host_supervision_authority_readiness_audit"]["authority_ready"] is False
    assert payload["resident_host_supervision_authority_readiness_audit"]["supervision_ready"] is False
    assert payload["resident_host_supervision_authority_readiness_audit"]["resident_claim_allowed"] is False
    assert payload["resident_host_supervision_authority_readiness_audit"]["boundary_observed"] is True
    assert payload["resident_host_supervision_authority_readiness_audit"]["request_readback_ready"] is True
    assert payload["resident_host_supervision_authority_readiness_audit"]["request_pending_count"] == 0
    assert payload["resident_host_supervision_authority_readiness_audit"]["request_approved_count"] == 0
    assert payload["resident_host_supervision_authority_readiness_audit"]["request_total_count"] == 0
    assert payload["resident_host_supervision_authority_readiness_audit"]["latest_request_approval_id"] == ""
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
        "host_supervision_authority_request_readback"
        not in payload["resident_host_supervision_authority_readiness_audit"]["blocked_requirements"]
    )
    assert payload["resident_host_supervision_authority_readiness_audit"]["operator_surface_readback_ready"] is True
    assert (
        payload["resident_host_supervision_authority_readiness_audit"]["first_blocked_requirement"]
        == "exact_supervision_authority_approval"
    )
    assert [
        item["id"]
        for item in payload["resident_host_supervision_authority_readiness_audit"]["blocked_requirement_handoffs"]
    ] == payload["resident_host_supervision_authority_readiness_audit"]["blocked_requirements"]
    assert payload["resident_host_supervision_authority_readiness_audit"]["first_blocked_requirement_handoff"] == {
        "id": "exact_supervision_authority_approval",
        "label": "Exact approved host supervision authority request",
        "status": "blocked",
        "route": "/lens/host/supervision/authority/requests",
        "readiness_route": "/lens/host/supervision/authority/readiness",
        "request_route": "/lens/host/supervision/authority/request",
        "requests_route": "/lens/host/supervision/authority/requests",
        "grant_route": "/lens/host/supervision/authority",
        "grants_route": "/lens/host/supervision/authority/grants",
        "denials_route": "/lens/host/supervision/authority/denials",
        "approval_action": "lens.host.supervision_authority",
        "next_step": "create_or_select_exact_approved_host_supervision_authority_request",
        "authority_required": "operator_approval",
        "authority_granted": False,
        "blockers": ["approval_id_required"],
        "would_execute": False,
        "would_mutate": False,
    }
    assert (
        payload["resident_host_supervision_authority_readiness_audit"]["next_smallest_truthful_gap"]
        == "host_supervision_authority_exact_approval_request"
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
    assert payload["persistent_supervision_enablement_denial_boundary"]["authority_required"] == (
        "persistent_supervision_enablement_authority"
    )
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
    assert payload["persistent_supervision_enablement_denial_boundary"]["service_config_write_authority_required"] == (
        "service_config_write_authority"
    )
    assert payload["persistent_supervision_enablement_denial_boundary"]["service_config_write_authority"] is False
    assert payload["persistent_supervision_enablement_denial_boundary"]["service_control_authority"] is False
    assert payload["persistent_supervision_enablement_denial_boundary"]["memory_write"] is False
    assert payload["persistent_supervision_enablement_denial_boundary"]["receipt_write_authority"] is False
    assert payload["persistent_supervision_enablement_denial_boundary"]["denial_receipt_write_authority"] is False
    execution_denial = payload["persistent_supervision_enablement_execution_denial_boundary"]
    assert execution_denial["status"] == "blocked"
    assert execution_denial["ok"] is True
    assert "/lens/host/persistent-supervision/enablement/execution" in execution_denial["evidence"]
    assert "/lens/host/persistent-supervision/enablement/execution/readiness" in execution_denial["evidence"]
    assert execution_denial["boundary_ready"] is True
    assert execution_denial["applied"] is False
    assert execution_denial["executed"] is False
    assert execution_denial["ready"] is False
    assert execution_denial["approval_ready"] is False
    assert execution_denial["enablement_authority_required"] == "persistent_supervision_enablement_authority"
    assert execution_denial["enablement_authority_granted"] is False
    assert execution_denial["persistent_supervision_enablement_allowed"] is False
    assert execution_denial["service_config_updated"] is False
    assert execution_denial["resident_claim_allowed"] is False
    assert "approval_id_required" in execution_denial["blockers"]
    assert "persistent_supervision_enablement_authority_not_granted" in execution_denial["blockers"]
    assert "service_config_write_authority_not_granted" in execution_denial["blockers"]
    assert "persistent_supervision_execution_authority_not_granted" in execution_denial["blockers"]
    assert execution_denial["execution_authority"] is False
    assert execution_denial["approval_decision_authority"] is False
    assert execution_denial["local_process_launch_authority"] is False
    assert execution_denial["process_supervision_authority"] is False
    assert execution_denial["process_restart_authority"] is False
    assert execution_denial["persistent_supervision_enablement_authority"] is False
    assert execution_denial["service_config_write_authority_required"] == "service_config_write_authority"
    assert execution_denial["service_config_write_authority"] is False
    assert execution_denial["persistent_supervision_execution_authority_required"] == (
        "persistent_supervision_execution_authority"
    )
    assert execution_denial["persistent_supervision_execution_authority"] is False
    assert execution_denial["service_control_authority"] is False
    assert execution_denial["memory_write"] is False
    assert execution_denial["receipt_write_authority"] is False
    assert execution_denial["denial_receipt_write_authority"] is False
    assert execution_denial["resident_claim_authority"] is False
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
    assert payload["resident_runtime_authority_boundary"]["resident_runtime_execution_authority_required"] == (
        "resident_runtime_execution_authority"
    )
    assert payload["resident_runtime_authority_boundary"]["resident_runtime_execution_authority"] is False
    assert payload["resident_runtime_authority_boundary"]["execution_authority"] is False
    assert payload["resident_runtime_authority_boundary"]["approval_decision_authority"] is False
    assert payload["resident_runtime_authority_boundary"]["local_process_launch_authority_required"] == (
        "local_process_launch_authority"
    )
    assert payload["resident_runtime_authority_boundary"]["local_process_launch_authority"] is False
    assert payload["resident_runtime_authority_boundary"]["process_supervision_authority_required"] == (
        "process_supervision_authority"
    )
    assert payload["resident_runtime_authority_boundary"]["process_supervision_authority"] is False
    assert payload["resident_runtime_authority_boundary"]["service_install_authority"] is False
    assert payload["resident_runtime_authority_boundary"]["service_control_authority_required"] == (
        "service_control_authority"
    )
    assert payload["resident_runtime_authority_boundary"]["service_control_authority"] is False
    assert payload["resident_runtime_authority_boundary"]["hotkey_registration_authority"] is False
    assert payload["resident_runtime_authority_boundary"]["tray_registration_authority_required"] == (
        "tray_registration_authority"
    )
    assert payload["resident_runtime_authority_boundary"]["tray_registration_authority"] is False
    assert payload["resident_runtime_authority_boundary"]["overlay_control_authority_required"] == (
        "overlay_control_authority"
    )
    assert payload["resident_runtime_authority_boundary"]["overlay_control_authority"] is False
    assert payload["resident_runtime_authority_boundary"]["memory_write"] is False
    assert payload["resident_runtime_authority_boundary"]["receipt_write_authority"] is False
    assert payload["resident_runtime_authority_boundary"]["resident_claim_authority_required"] == (
        "resident_claim_authority"
    )
    assert payload["resident_runtime_authority_boundary"]["resident_claim_authority"] is False
    assert payload["resident_runtime_granted_boundary_proof"]["status"] == "proof_passed"
    assert payload["resident_runtime_granted_boundary_proof"]["ok"] is True
    assert payload["resident_runtime_granted_boundary_proof"]["exit_code"] == 0
    assert (
        "scripts/lens-resident-runtime-boundary-proof.ps1"
        in payload["resident_runtime_granted_boundary_proof"]["evidence"]
    )
    assert (
        payload["resident_runtime_granted_boundary_proof"]["authority_required"]
        == "resident_runtime_execution_authority"
    )
    assert payload["resident_runtime_granted_boundary_proof"]["authority_granted"] is True
    assert payload["resident_runtime_granted_boundary_proof"]["resident_runtime_execution_authority"] is True
    assert payload["resident_runtime_granted_boundary_proof"]["runtime_ready"] is False
    assert payload["resident_runtime_granted_boundary_proof"]["resident_claim_allowed"] is False
    assert payload["resident_runtime_granted_boundary_proof"]["applied"] is False
    assert payload["resident_runtime_granted_boundary_proof"]["executed"] is False
    assert payload["resident_runtime_granted_boundary_proof"]["would_launch_process"] is False
    assert payload["resident_runtime_granted_boundary_proof"]["would_supervise_process"] is False
    assert payload["resident_runtime_granted_boundary_proof"]["would_start_service"] is False
    assert payload["resident_runtime_granted_boundary_proof"]["would_register_tray"] is False
    assert payload["resident_runtime_granted_boundary_proof"]["would_register_hotkey"] is False
    assert payload["resident_runtime_granted_boundary_proof"]["would_open_overlay"] is False
    assert payload["resident_runtime_granted_boundary_proof"]["would_write_memory"] is False
    assert payload["resident_runtime_granted_boundary_proof"]["would_claim_resident"] is False
    assert (
        "resident_runtime_execution_authority_not_granted"
        not in payload["resident_runtime_granted_boundary_proof"]["blockers"]
    )
    assert "process_supervision_authority_not_granted" in payload["resident_runtime_granted_boundary_proof"]["blockers"]
    assert "service_control_authority_not_granted" in payload["resident_runtime_granted_boundary_proof"]["blockers"]
    assert "tray_registration_authority_not_granted" in payload["resident_runtime_granted_boundary_proof"]["blockers"]
    assert "hotkey_registration_authority_not_granted" in payload["resident_runtime_granted_boundary_proof"]["blockers"]
    assert "overlay_control_authority_not_granted" in payload["resident_runtime_granted_boundary_proof"]["blockers"]
    assert "resident_claim_authority_not_granted" in payload["resident_runtime_granted_boundary_proof"]["blockers"]
    assert (
        payload["resident_runtime_granted_boundary_proof"]["next_smallest_truthful_gap"]
        == "supervised_resident_runtime_process_service_tray_hotkey_overlay_authority"
    )
    runtime_authority_blockers = payload["resident_runtime_authority_blockers_proof"]
    assert runtime_authority_blockers["status"] == "proof_passed"
    assert runtime_authority_blockers["ok"] is True
    assert runtime_authority_blockers["exit_code"] == 0
    assert "scripts/lens-resident-runtime-authority-blockers-proof.ps1" in runtime_authority_blockers["evidence"]
    assert "scripts/lens-resident-runtime-boundary-proof.ps1" in runtime_authority_blockers["evidence"]
    assert runtime_authority_blockers["next_smallest_truthful_gap"] == (
        "resident_runtime_process_supervision_authority_boundary"
    )
    assert runtime_authority_blockers["authority_required"] == "process_supervision_authority"
    assert runtime_authority_blockers["authority_granted"] is False
    assert runtime_authority_blockers["remaining_authority_families"] == [
        "process_supervision",
        "service_control",
        "tray_presence",
        "hotkey_summon",
        "overlay_window",
        "resident_claim",
    ]
    assert runtime_authority_blockers["summary"]["authority_family_total"] == 6
    assert runtime_authority_blockers["summary"]["blocked_authority_family_total"] == 6
    assert runtime_authority_blockers["summary"]["combined_gap_split"] is True
    authority_groups = runtime_authority_blockers["authority_blocker_groups"]
    assert authority_groups["process_supervision"]["status"] == "blocked"
    assert authority_groups["process_supervision"]["route"] == "/lens/host/supervision/authority/readiness"
    assert "local_process_launch_authority_not_granted" in authority_groups["process_supervision"]["blockers"]
    assert "process_supervision_authority_not_granted" in authority_groups["process_supervision"]["blockers"]
    assert authority_groups["service_control"]["status"] == "blocked"
    assert "service_control_authority_not_granted" in authority_groups["service_control"]["blockers"]
    assert authority_groups["tray_presence"]["status"] == "blocked"
    assert "tray_registration_authority_not_granted" in authority_groups["tray_presence"]["blockers"]
    assert authority_groups["hotkey_summon"]["status"] == "blocked"
    assert "hotkey_registration_authority_not_granted" in authority_groups["hotkey_summon"]["blockers"]
    assert authority_groups["overlay_window"]["status"] == "blocked"
    assert "overlay_control_authority_not_granted" in authority_groups["overlay_window"]["blockers"]
    assert authority_groups["resident_claim"]["status"] == "blocked"
    assert "resident_claim_authority_not_granted" in authority_groups["resident_claim"]["blockers"]
    assert runtime_authority_blockers["governance"]["diagnostic_only"] is True
    assert runtime_authority_blockers["governance"]["execution_authority"] is False
    assert runtime_authority_blockers["governance"]["process_supervision_authority"] is False
    assert runtime_authority_blockers["governance"]["service_control_authority"] is False
    assert runtime_authority_blockers["governance"]["resident_claim_authority"] is False
    runtime_process_boundary = payload["resident_runtime_process_supervision_boundary_proof"]
    assert runtime_process_boundary["status"] == "proof_passed"
    assert runtime_process_boundary["ok"] is True
    assert runtime_process_boundary["exit_code"] == 0
    assert "scripts/lens-resident-runtime-authority-blockers-proof.ps1" in runtime_process_boundary["evidence"]
    assert runtime_process_boundary["authority_family"] == "process_supervision"
    assert runtime_process_boundary["next_authority_family"] == "service_control"
    assert runtime_process_boundary["process_supervision_boundary_observed"] is True
    assert runtime_process_boundary["authority_blockers_proof_observed"] is True
    assert runtime_process_boundary["side_effects_denied"] is True
    assert runtime_process_boundary["first_authority_family_consumed"] is True
    assert runtime_process_boundary["authority_required"] == "process_supervision_authority"
    assert runtime_process_boundary["authority_granted"] is False
    assert runtime_process_boundary["resident_runtime_execution_authority"] is True
    assert runtime_process_boundary["local_process_launch_authority"] is False
    assert runtime_process_boundary["process_supervision_authority"] is False
    assert runtime_process_boundary["process_restart_authority"] is False
    assert runtime_process_boundary["service_control_authority"] is False
    assert runtime_process_boundary["resident_claim_authority"] is False
    assert runtime_process_boundary["would_launch_process"] is False
    assert runtime_process_boundary["would_supervise_process"] is False
    assert runtime_process_boundary["would_restart_process"] is False
    assert runtime_process_boundary["would_start_service"] is False
    assert runtime_process_boundary["would_register_tray"] is False
    assert runtime_process_boundary["would_register_hotkey"] is False
    assert runtime_process_boundary["would_open_overlay"] is False
    assert runtime_process_boundary["would_write_memory"] is False
    assert runtime_process_boundary["would_claim_resident"] is False
    assert runtime_process_boundary["process_supervision"]["status"] == "blocked"
    assert "process_supervision_authority_not_granted" in runtime_process_boundary["blockers"]
    assert runtime_process_boundary["next_smallest_truthful_gap"] == (
        "resident_runtime_service_control_authority_boundary"
    )
    assert runtime_process_boundary["governance"]["diagnostic_only"] is True
    assert runtime_process_boundary["governance"]["process_supervision_authority"] is False
    assert runtime_process_boundary["governance"]["service_control_authority"] is False
    runtime_service_boundary = payload["resident_runtime_service_control_boundary_proof"]
    assert runtime_service_boundary["status"] == "proof_passed"
    assert runtime_service_boundary["ok"] is True
    assert runtime_service_boundary["exit_code"] == 0
    assert "scripts/lens-resident-runtime-authority-blockers-proof.ps1" in runtime_service_boundary["evidence"]
    assert runtime_service_boundary["authority_family"] == "service_control"
    assert runtime_service_boundary["previous_authority_family"] == "process_supervision"
    assert runtime_service_boundary["next_authority_family"] == "tray_presence"
    assert runtime_service_boundary["service_control_boundary_observed"] is True
    assert runtime_service_boundary["previous_process_supervision_family_observed"] is True
    assert runtime_service_boundary["authority_blockers_proof_observed"] is True
    assert runtime_service_boundary["side_effects_denied"] is True
    assert runtime_service_boundary["second_authority_family_consumed"] is True
    assert runtime_service_boundary["authority_required"] == "service_control_authority"
    assert runtime_service_boundary["authority_granted"] is False
    assert runtime_service_boundary["resident_runtime_execution_authority"] is True
    assert runtime_service_boundary["local_process_launch_authority"] is False
    assert runtime_service_boundary["process_supervision_authority"] is False
    assert runtime_service_boundary["process_restart_authority"] is False
    assert runtime_service_boundary["service_install_authority"] is False
    assert runtime_service_boundary["service_control_authority"] is False
    assert runtime_service_boundary["resident_claim_authority"] is False
    assert runtime_service_boundary["would_launch_process"] is False
    assert runtime_service_boundary["would_supervise_process"] is False
    assert runtime_service_boundary["would_restart_process"] is False
    assert runtime_service_boundary["would_install_service"] is False
    assert runtime_service_boundary["would_start_service"] is False
    assert runtime_service_boundary["would_register_tray"] is False
    assert runtime_service_boundary["would_register_hotkey"] is False
    assert runtime_service_boundary["would_open_overlay"] is False
    assert runtime_service_boundary["would_write_memory"] is False
    assert runtime_service_boundary["would_claim_resident"] is False
    assert runtime_service_boundary["service_control"]["status"] == "blocked"
    assert "service_install_authority_not_granted" in runtime_service_boundary["blockers"]
    assert "service_control_authority_not_granted" in runtime_service_boundary["blockers"]
    assert runtime_service_boundary["remaining_authority_families_after_this_boundary"] == [
        "tray_presence",
        "hotkey_summon",
        "overlay_window",
        "resident_claim",
    ]
    assert runtime_service_boundary["next_smallest_truthful_gap"] == (
        "resident_runtime_tray_presence_authority_boundary"
    )
    assert runtime_service_boundary["governance"]["diagnostic_only"] is True
    assert runtime_service_boundary["governance"]["service_install_authority"] is False
    assert runtime_service_boundary["governance"]["service_control_authority"] is False
    runtime_tray_boundary = payload["resident_runtime_tray_presence_boundary_proof"]
    assert runtime_tray_boundary["status"] == "proof_passed"
    assert runtime_tray_boundary["ok"] is True
    assert runtime_tray_boundary["exit_code"] == 0
    assert "scripts/lens-resident-runtime-authority-blockers-proof.ps1" in runtime_tray_boundary["evidence"]
    assert "scripts/lens-tray-preflight.ps1" in runtime_tray_boundary["evidence"]
    assert runtime_tray_boundary["authority_family"] == "tray_presence"
    assert runtime_tray_boundary["previous_authority_family"] == "service_control"
    assert runtime_tray_boundary["next_authority_family"] == "hotkey_summon"
    assert runtime_tray_boundary["tray_presence_boundary_observed"] is True
    assert runtime_tray_boundary["previous_service_control_family_observed"] is True
    assert runtime_tray_boundary["tray_preflight_observed"] is True
    assert runtime_tray_boundary["authority_blockers_proof_observed"] is True
    assert runtime_tray_boundary["side_effects_denied"] is True
    assert runtime_tray_boundary["third_authority_family_consumed"] is True
    assert runtime_tray_boundary["authority_required"] == "tray_presence_authority"
    assert runtime_tray_boundary["authority_granted"] is False
    assert runtime_tray_boundary["resident_runtime_execution_authority"] is True
    assert runtime_tray_boundary["local_process_launch_authority"] is False
    assert runtime_tray_boundary["process_supervision_authority"] is False
    assert runtime_tray_boundary["process_restart_authority"] is False
    assert runtime_tray_boundary["service_install_authority"] is False
    assert runtime_tray_boundary["service_control_authority"] is False
    assert runtime_tray_boundary["tray_registration_authority"] is False
    assert runtime_tray_boundary["tray_icon_authority"] is False
    assert runtime_tray_boundary["notification_authority"] is False
    assert runtime_tray_boundary["resident_claim_authority"] is False
    assert runtime_tray_boundary["would_launch_process"] is False
    assert runtime_tray_boundary["would_supervise_process"] is False
    assert runtime_tray_boundary["would_restart_process"] is False
    assert runtime_tray_boundary["would_install_service"] is False
    assert runtime_tray_boundary["would_start_service"] is False
    assert runtime_tray_boundary["would_register_tray"] is False
    assert runtime_tray_boundary["would_register_hotkey"] is False
    assert runtime_tray_boundary["would_open_overlay"] is False
    assert runtime_tray_boundary["would_write_memory"] is False
    assert runtime_tray_boundary["would_claim_resident"] is False
    assert runtime_tray_boundary["tray_presence"]["status"] == "blocked"
    assert "tray_registration_authority_not_granted" in runtime_tray_boundary["blockers"]
    assert "tray_icon_authority_not_granted" in runtime_tray_boundary["blockers"]
    assert "notification_authority_not_granted" in runtime_tray_boundary["blockers"]
    assert runtime_tray_boundary["tray_preflight"]["status"] == "blocked"
    assert runtime_tray_boundary["tray_preflight"]["presence_name"] == "Francis Lens Tray Presence"
    assert runtime_tray_boundary["remaining_authority_families_after_this_boundary"] == [
        "hotkey_summon",
        "overlay_window",
        "resident_claim",
    ]
    assert runtime_tray_boundary["next_smallest_truthful_gap"] == ("resident_runtime_hotkey_summon_authority_boundary")
    assert runtime_tray_boundary["governance"]["diagnostic_only"] is True
    assert runtime_tray_boundary["governance"]["tray_preflight_readback"] is True
    assert runtime_tray_boundary["governance"]["tray_registration_authority"] is False
    assert runtime_tray_boundary["governance"]["tray_icon_authority"] is False
    assert runtime_tray_boundary["governance"]["notification_authority"] is False

    runtime_hotkey_boundary = payload["resident_runtime_hotkey_summon_boundary_proof"]
    assert runtime_hotkey_boundary["status"] == "proof_passed"
    assert runtime_hotkey_boundary["ok"] is True
    assert runtime_hotkey_boundary["exit_code"] == 0
    assert runtime_hotkey_boundary["authority_family"] == "hotkey_summon"
    assert runtime_hotkey_boundary["previous_authority_family"] == "tray_presence"
    assert runtime_hotkey_boundary["next_authority_family"] == "overlay_window"
    assert runtime_hotkey_boundary["hotkey_summon_boundary_observed"] is True
    assert runtime_hotkey_boundary["previous_tray_presence_family_observed"] is True
    assert runtime_hotkey_boundary["summon_preflight_observed"] is True
    assert runtime_hotkey_boundary["authority_blockers_proof_observed"] is True
    assert runtime_hotkey_boundary["side_effects_denied"] is True
    assert runtime_hotkey_boundary["fourth_authority_family_consumed"] is True
    assert runtime_hotkey_boundary["authority_required"] == "hotkey_registration_and_summon_authority"
    assert runtime_hotkey_boundary["authority_granted"] is False
    assert runtime_hotkey_boundary["resident_runtime_execution_authority"] is True
    assert runtime_hotkey_boundary["local_process_launch_authority"] is False
    assert runtime_hotkey_boundary["process_supervision_authority"] is False
    assert runtime_hotkey_boundary["process_restart_authority"] is False
    assert runtime_hotkey_boundary["service_install_authority"] is False
    assert runtime_hotkey_boundary["service_control_authority"] is False
    assert runtime_hotkey_boundary["tray_registration_authority"] is False
    assert runtime_hotkey_boundary["tray_icon_authority"] is False
    assert runtime_hotkey_boundary["notification_authority"] is False
    assert runtime_hotkey_boundary["summon_authority"] is False
    assert runtime_hotkey_boundary["hotkey_registration_authority"] is False
    assert runtime_hotkey_boundary["overlay_control_authority"] is False
    assert runtime_hotkey_boundary["resident_claim_authority"] is False
    assert runtime_hotkey_boundary["would_launch_process"] is False
    assert runtime_hotkey_boundary["would_supervise_process"] is False
    assert runtime_hotkey_boundary["would_restart_process"] is False
    assert runtime_hotkey_boundary["would_install_service"] is False
    assert runtime_hotkey_boundary["would_start_service"] is False
    assert runtime_hotkey_boundary["would_register_tray"] is False
    assert runtime_hotkey_boundary["would_register_hotkey"] is False
    assert runtime_hotkey_boundary["would_open_overlay"] is False
    assert runtime_hotkey_boundary["would_write_memory"] is False
    assert runtime_hotkey_boundary["would_claim_resident"] is False
    assert runtime_hotkey_boundary["hotkey_summon"]["status"] == "blocked"
    assert runtime_hotkey_boundary["summon_preflight"]["status"] == "blocked"
    assert "global_hotkey_binding_disabled" in runtime_hotkey_boundary["blockers"]
    assert "global_hotkey_registration_disabled" in runtime_hotkey_boundary["blockers"]
    assert "hotkey_registration_authority_not_granted" in runtime_hotkey_boundary["blockers"]
    assert "summon_authority_not_granted" in runtime_hotkey_boundary["blockers"]
    assert runtime_hotkey_boundary["remaining_authority_families_after_this_boundary"] == [
        "overlay_window",
        "resident_claim",
    ]
    assert runtime_hotkey_boundary["next_smallest_truthful_gap"] == (
        "resident_runtime_overlay_window_authority_boundary"
    )
    assert runtime_hotkey_boundary["governance"]["diagnostic_only"] is True
    assert runtime_hotkey_boundary["governance"]["summon_preflight_readback"] is True
    assert runtime_hotkey_boundary["governance"]["summon_authority"] is False
    assert runtime_hotkey_boundary["governance"]["hotkey_registration_authority"] is False
    runtime_overlay_boundary = payload["resident_runtime_overlay_window_boundary_proof"]
    assert runtime_overlay_boundary["status"] == "proof_passed"
    assert runtime_overlay_boundary["ok"] is True
    assert runtime_overlay_boundary["exit_code"] == 0
    assert runtime_overlay_boundary["authority_family"] == "overlay_window"
    assert runtime_overlay_boundary["previous_authority_family"] == "hotkey_summon"
    assert runtime_overlay_boundary["next_authority_family"] == "resident_claim"
    assert runtime_overlay_boundary["overlay_window_boundary_observed"] is True
    assert runtime_overlay_boundary["previous_hotkey_summon_family_observed"] is True
    assert runtime_overlay_boundary["overlay_preflight_observed"] is True
    assert runtime_overlay_boundary["authority_blockers_proof_observed"] is True
    assert runtime_overlay_boundary["side_effects_denied"] is True
    assert runtime_overlay_boundary["fifth_authority_family_consumed"] is True
    assert runtime_overlay_boundary["authority_required"] == "overlay_control_window_management_capture_authority"
    assert runtime_overlay_boundary["authority_granted"] is False
    assert runtime_overlay_boundary["local_process_launch_authority"] is False
    assert runtime_overlay_boundary["process_supervision_authority"] is False
    assert runtime_overlay_boundary["process_restart_authority"] is False
    assert runtime_overlay_boundary["service_install_authority"] is False
    assert runtime_overlay_boundary["service_control_authority"] is False
    assert runtime_overlay_boundary["tray_registration_authority"] is False
    assert runtime_overlay_boundary["tray_icon_authority"] is False
    assert runtime_overlay_boundary["notification_authority"] is False
    assert runtime_overlay_boundary["summon_authority"] is False
    assert runtime_overlay_boundary["hotkey_registration_authority"] is False
    assert runtime_overlay_boundary["overlay_control_authority"] is False
    assert runtime_overlay_boundary["window_management_authority"] is False
    assert runtime_overlay_boundary["capture_authority"] is False
    assert runtime_overlay_boundary["new_sensing_authority"] is False
    assert runtime_overlay_boundary["resident_claim_authority"] is False
    assert runtime_overlay_boundary["would_launch_process"] is False
    assert runtime_overlay_boundary["would_supervise_process"] is False
    assert runtime_overlay_boundary["would_restart_process"] is False
    assert runtime_overlay_boundary["would_install_service"] is False
    assert runtime_overlay_boundary["would_start_service"] is False
    assert runtime_overlay_boundary["would_register_tray"] is False
    assert runtime_overlay_boundary["would_register_hotkey"] is False
    assert runtime_overlay_boundary["would_open_overlay"] is False
    assert runtime_overlay_boundary["would_write_memory"] is False
    assert runtime_overlay_boundary["would_claim_resident"] is False
    assert runtime_overlay_boundary["overlay_window"]["status"] == "blocked"
    assert runtime_overlay_boundary["overlay_preflight"]["status"] == "blocked"
    assert "overlay_window_disabled" in runtime_overlay_boundary["blockers"]
    assert "overlay_control_authority_not_granted" in runtime_overlay_boundary["blockers"]
    assert "window_management_authority_not_granted" in runtime_overlay_boundary["blockers"]
    assert "capture_authority_not_granted" in runtime_overlay_boundary["blockers"]
    assert runtime_overlay_boundary["remaining_authority_families_after_this_boundary"] == ["resident_claim"]
    assert runtime_overlay_boundary["next_smallest_truthful_gap"] == (
        "resident_runtime_resident_claim_authority_boundary"
    )
    assert runtime_overlay_boundary["governance"]["diagnostic_only"] is True
    assert runtime_overlay_boundary["governance"]["overlay_preflight_readback"] is True
    assert runtime_overlay_boundary["governance"]["overlay_control_authority"] is False
    assert runtime_overlay_boundary["governance"]["window_management_authority"] is False
    assert runtime_overlay_boundary["governance"]["capture_authority"] is False
    assert runtime_overlay_boundary["governance"]["new_sensing_authority"] is False
    runtime_resident_claim_boundary = payload["resident_runtime_resident_claim_boundary_proof"]
    assert runtime_resident_claim_boundary["status"] == "proof_passed"
    assert runtime_resident_claim_boundary["ok"] is True
    assert runtime_resident_claim_boundary["exit_code"] == 0
    assert runtime_resident_claim_boundary["authority_family"] == "resident_claim"
    assert runtime_resident_claim_boundary["previous_authority_family"] == "overlay_window"
    assert runtime_resident_claim_boundary["next_authority_family"] == ""
    assert runtime_resident_claim_boundary["resident_claim_boundary_observed"] is True
    assert runtime_resident_claim_boundary["previous_overlay_window_family_observed"] is True
    assert runtime_resident_claim_boundary["authority_blockers_proof_observed"] is True
    assert runtime_resident_claim_boundary["side_effects_denied"] is True
    assert runtime_resident_claim_boundary["sixth_authority_family_consumed"] is True
    assert runtime_resident_claim_boundary["authority_required"] == "resident_claim_authority"
    assert runtime_resident_claim_boundary["authority_granted"] is False
    assert runtime_resident_claim_boundary["local_process_launch_authority"] is False
    assert runtime_resident_claim_boundary["process_supervision_authority"] is False
    assert runtime_resident_claim_boundary["process_restart_authority"] is False
    assert runtime_resident_claim_boundary["service_install_authority"] is False
    assert runtime_resident_claim_boundary["service_control_authority"] is False
    assert runtime_resident_claim_boundary["tray_registration_authority"] is False
    assert runtime_resident_claim_boundary["tray_icon_authority"] is False
    assert runtime_resident_claim_boundary["notification_authority"] is False
    assert runtime_resident_claim_boundary["summon_authority"] is False
    assert runtime_resident_claim_boundary["hotkey_registration_authority"] is False
    assert runtime_resident_claim_boundary["overlay_control_authority"] is False
    assert runtime_resident_claim_boundary["window_management_authority"] is False
    assert runtime_resident_claim_boundary["capture_authority"] is False
    assert runtime_resident_claim_boundary["new_sensing_authority"] is False
    assert runtime_resident_claim_boundary["resident_claim_authority"] is False
    assert runtime_resident_claim_boundary["would_launch_process"] is False
    assert runtime_resident_claim_boundary["would_supervise_process"] is False
    assert runtime_resident_claim_boundary["would_restart_process"] is False
    assert runtime_resident_claim_boundary["would_install_service"] is False
    assert runtime_resident_claim_boundary["would_start_service"] is False
    assert runtime_resident_claim_boundary["would_register_tray"] is False
    assert runtime_resident_claim_boundary["would_register_hotkey"] is False
    assert runtime_resident_claim_boundary["would_open_overlay"] is False
    assert runtime_resident_claim_boundary["would_write_memory"] is False
    assert runtime_resident_claim_boundary["would_claim_resident"] is False
    assert runtime_resident_claim_boundary["resident_claim"]["status"] == "blocked"
    assert "resident_claim_authority_not_granted" in runtime_resident_claim_boundary["blockers"]
    assert "resident_surface_runtime_missing" in runtime_resident_claim_boundary["blockers"]
    assert runtime_resident_claim_boundary["remaining_authority_families_after_this_boundary"] == []
    assert runtime_resident_claim_boundary["next_smallest_truthful_gap"] == "stage6_lens_completion_audit"
    assert runtime_resident_claim_boundary["governance"]["diagnostic_only"] is True
    assert runtime_resident_claim_boundary["governance"]["overlay_window_boundary_readback"] is True
    assert runtime_resident_claim_boundary["governance"]["resident_claim_authority"] is False
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
    assert (
        payload["resident_surface_foreground_runtime_proof"]["recommended_handoff_source"]
        == "resident_surface_runtime_supervision_handoff"
    )
    assert (
        payload["resident_surface_foreground_runtime_proof"]["recommended_next_slice"]
        == "resolve_resident_surface_runtime_supervision_before_helpful_not_noisy_claim"
    )
    assert (
        payload["resident_surface_foreground_runtime_proof"]["recommended_proof_script"]
        == "scripts/lens-resident-surface-proof.ps1 -Mode Status"
    )
    assert payload["resident_surface_foreground_runtime_proof"]["authority_required"] == "process_supervision_authority"
    assert payload["resident_surface_foreground_runtime_proof"]["authority_granted"] is False
    assert (
        payload["resident_surface_foreground_runtime_proof"]["resident_surface_runtime_supervision_handoff_observed"]
        is True
    )
    assert (
        payload["resident_surface_foreground_runtime_proof"]["resident_runtime_authority_grant_handoff_observed"]
        is True
    )
    resident_surface_runtime_supervision_handoff = payload["resident_surface_foreground_runtime_proof"][
        "resident_surface_runtime_supervision_handoff"
    ]
    assert (
        resident_surface_runtime_supervision_handoff
        == payload["resident_surface_foreground_runtime_proof"]["recommended_handoff"]
    )
    assert resident_surface_runtime_supervision_handoff["id"] == "resident_surface_runtime_supervision"
    assert (
        resident_surface_runtime_supervision_handoff["next_smallest_truthful_gap"]
        == "resident_surface_runtime_not_supervised"
    )
    assert (
        resident_surface_runtime_supervision_handoff["next_step"]
        == "resolve_resident_surface_runtime_supervision_before_helpful_not_noisy_claim"
    )
    assert (
        resident_surface_runtime_supervision_handoff["proof_script"]
        == "scripts/lens-resident-surface-proof.ps1 -Mode Status"
    )
    assert resident_surface_runtime_supervision_handoff["readiness_route"] == (
        "/lens/resident-runtime/authority-grant/readiness"
    )
    assert resident_surface_runtime_supervision_handoff["authority_required"] == "process_supervision_authority"
    assert resident_surface_runtime_supervision_handoff["authority_granted"] is False
    assert resident_surface_runtime_supervision_handoff["read_only_contract"] is True
    assert resident_surface_runtime_supervision_handoff["diagnostic_only"] is True
    assert resident_surface_runtime_supervision_handoff["would_execute"] is False
    assert resident_surface_runtime_supervision_handoff["would_mutate"] is False
    assert resident_surface_runtime_supervision_handoff["would_supervise_process"] is False
    assert resident_surface_runtime_supervision_handoff["would_restart_process"] is False
    assert resident_surface_runtime_supervision_handoff["would_claim_resident"] is False
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
    live_operator_proof = payload["live_operator_experience_proof"]
    assert live_operator_proof["status"] in {"proof_passed", "missing"}
    assert isinstance(live_operator_proof["ok"], bool)
    assert isinstance(live_operator_proof["exit_code"], int)
    assert isinstance(live_operator_proof["live_http_status_readback"], bool)
    assert isinstance(live_operator_proof["helpful_not_noisy_readback"], bool)
    assert isinstance(live_operator_proof["operator_experience_proof"], bool)
    if live_operator_proof["ok"]:
        assert live_operator_proof["status"] == "proof_passed"
        assert live_operator_proof["exit_code"] == 0
        assert live_operator_proof["live_http_status_readback"] is True
        assert live_operator_proof["helpful_not_noisy_readback"] is True
        assert live_operator_proof["operator_experience_proof"] is True
        assert "operator_experience_proof_missing" not in payload["blockers"]
    else:
        assert "operator_experience_proof_missing" in payload["blockers"]
    assert payload["live_operator_experience_proof"]["live_operator_experience_ready"] is False
    assert payload["live_operator_experience_proof"]["ready_for_stage6_closure"] is False
    if live_operator_proof["ok"]:
        assert "resident_surface_runtime_missing" in live_operator_proof["blockers"]
    assert "resident_surface_missing" not in live_operator_proof["blockers"]
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
    assert payload["resident_overlay_runtime_proof"]["requested_resident_surface_foreground_run_seconds"] == 5
    assert payload["resident_overlay_runtime_proof"]["resident_surface_foreground_run_seconds"] == 5
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
    assert payload["resident_overlay_activation_boundary_proof"]["startup_timeout_seconds"] == 5
    assert payload["resident_overlay_activation_boundary_proof"]["supervisor_run_seconds"] == 3
    assert payload["resident_overlay_activation_boundary_proof"]["resident_surface_foreground_run_seconds"] == 5
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
        payload["resident_overlay_activation_boundary_proof"]["overlay_runtime_source"] == "checkpoint_cached_payload"
    )
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
    command_palette_shell_bridge = payload["command_palette_shell_bridge"]
    assert command_palette_shell_bridge["status"] == "blocked"
    assert command_palette_shell_bridge["ok"] is True
    assert command_palette_shell_bridge["exit_code"] == 0
    assert command_palette_shell_bridge["readback_ready"] is True
    assert command_palette_shell_bridge["os_level_command_palette"] is False
    assert command_palette_shell_bridge["summon_anywhere"] is False
    assert command_palette_shell_bridge["availability"] == "chat_ui_only"
    assert command_palette_shell_bridge["route"] == "/lens/status"
    assert command_palette_shell_bridge["command_total"] > 0
    assert "os_level_command_palette_missing" in command_palette_shell_bridge["blockers"]
    assert "summon_anywhere_missing" in command_palette_shell_bridge["blockers"]
    assert "global_hotkey_binding_missing" in command_palette_shell_bridge["blockers"]
    assert command_palette_shell_bridge["next_smallest_truthful_gap"] == "os_level_command_palette_binding"
    assert "scripts/lens-command-palette.ps1" in command_palette_shell_bridge["evidence"][0]
    assert command_palette_shell_bridge["governance"]["read_only_contract"] is True
    assert command_palette_shell_bridge["governance"]["opens_palette"] is False
    assert command_palette_shell_bridge["governance"]["execution_authority"] is False
    assert command_palette_shell_bridge["governance"]["approval_decision_authority"] is False
    assert command_palette_shell_bridge["governance"]["memory_write"] is False
    assert command_palette_shell_bridge["governance"]["overlay_control_authority"] is False
    assert command_palette_shell_bridge["governance"]["summon_authority"] is False
    assert command_palette_shell_bridge["governance"]["hotkey_registration_authority"] is False
    assert command_palette_shell_bridge["governance"]["tray_registration_authority"] is False
    assert command_palette_shell_bridge["governance"]["local_process_launch_authority"] is False
    assert command_palette_shell_bridge["governance"]["mutation_authority_granted"] is False
    command_palette_os_binding = payload["command_palette_os_binding_blockers_proof"]
    assert command_palette_os_binding["status"] == "proof_passed"
    assert command_palette_os_binding["ok"] is True
    assert command_palette_os_binding["exit_code"] == 0
    assert command_palette_os_binding["acceptance_criterion"] == "summon_anywhere"
    assert command_palette_os_binding["os_level_command_palette_binding_observed"] is True
    assert command_palette_os_binding["summon_preflight_observed"] is True
    assert command_palette_os_binding["tray_preflight_observed"] is True
    assert command_palette_os_binding["overlay_preflight_observed"] is True
    assert command_palette_os_binding["os_binding_candidate_observed"] is True
    assert command_palette_os_binding["side_effects_denied"] is True
    assert command_palette_os_binding["blocked_families"] == [
        "palette_binding",
        "global_hotkey_binding",
        "summon_binding",
        "tray_presence",
        "overlay_window",
        "authority",
    ]
    assert command_palette_os_binding["first_blocker_family"] == "palette_binding"
    assert command_palette_os_binding["next_smallest_truthful_gap"] == "os_level_command_palette_binding"
    assert "scripts/lens-command-palette-os-binding-proof.ps1" in command_palette_os_binding["evidence"][0]
    os_binding_groups = command_palette_os_binding["blocker_groups"]
    assert "os_level_command_palette_missing" in os_binding_groups["palette_binding"]
    assert "global_hotkey_binding_disabled" in os_binding_groups["global_hotkey_binding"]
    assert "lens_summon_binding_disabled_pending_authority" in os_binding_groups["summon_binding"]
    assert "tray_host_disabled" in os_binding_groups["tray_presence"]
    assert "overlay_window_disabled" in os_binding_groups["overlay_window"]
    assert "summon_authority_not_granted" in os_binding_groups["authority"]
    assert command_palette_os_binding["command_palette"]["availability"] == "chat_ui_only"
    assert command_palette_os_binding["command_palette"]["os_level_command_palette"] is False
    os_binding_candidate = command_palette_os_binding["os_binding_candidate"]
    assert os_binding_candidate["kind"] == "lens.command_palette.os_binding_candidate"
    assert os_binding_candidate["status"] == "blocked"
    assert os_binding_candidate["candidate"] == "global_hotkey_to_lens_command_palette_bridge"
    assert os_binding_candidate["trigger"] == "Ctrl+Alt+Space"
    assert os_binding_candidate["binding_scope"] == "global"
    assert os_binding_candidate["route"] == "/lens/status"
    assert os_binding_candidate["local_surface"] == "chat_ui.command_palette"
    assert os_binding_candidate["bridge_script"] == "scripts/lens-command-palette.ps1"
    assert os_binding_candidate["proof_script"] == "scripts/lens-command-palette-os-binding-proof.ps1"
    assert os_binding_candidate["requires_approval_kind"] == "lens.os_binding.command_palette_binding_authority"
    assert "lens.os_binding.command_palette_binding_authority" in os_binding_candidate["required_authority"]
    assert "hotkey_registration_authority" in os_binding_candidate["required_authority"]
    assert "summon_authority" in os_binding_candidate["required_authority"]
    assert "local_process_launch_authority" in os_binding_candidate["required_authority"]
    assert os_binding_candidate["required_preflight_families"] == [
        "palette_binding",
        "global_hotkey_binding",
        "summon_binding",
        "authority",
    ]
    assert "os_level_command_palette_missing" in os_binding_candidate["blocked_by"]
    assert "global_hotkey_binding_disabled" in os_binding_candidate["blocked_by"]
    assert "lens_summon_binding_disabled_pending_authority" in os_binding_candidate["blocked_by"]
    assert "summon_authority_not_granted" in os_binding_candidate["blocked_by"]
    assert "hotkey_registration_authority_not_granted" in os_binding_candidate["blocked_by"]
    assert "local_process_launch_authority_not_granted" in os_binding_candidate["blocked_by"]
    assert os_binding_candidate["current_authorized_effect"] == "readback_only_status"
    assert os_binding_candidate["candidate_effect_if_authorized"] == (
        "open_lens_command_palette_from_governed_os_binding"
    )
    assert os_binding_candidate["open_mode_authorized"] is False
    assert os_binding_candidate["open_mode_refusal"] == "lens_command_palette_open_not_authorized"
    assert os_binding_candidate["would_register_hotkey_now"] is False
    assert os_binding_candidate["would_open_palette_now"] is False
    assert os_binding_candidate["would_summon_anywhere_now"] is False
    assert os_binding_candidate["would_launch_process_now"] is False
    assert os_binding_candidate["would_write_memory_now"] is False
    assert os_binding_candidate["next_smallest_truthful_gap"] == "os_level_command_palette_binding"
    assert command_palette_os_binding["summon_preflight"]["global_hotkey"] == "Ctrl+Alt+Space"
    assert command_palette_os_binding["tray_preflight"]["ready"] is False
    assert command_palette_os_binding["overlay_preflight"]["ready"] is False
    assert command_palette_os_binding["governance"]["read_only_contract"] is True
    assert command_palette_os_binding["governance"]["diagnostic_only"] is True
    assert command_palette_os_binding["governance"]["os_binding_candidate_boundary_readback"] is True
    assert command_palette_os_binding["governance"]["opens_palette"] is False
    assert command_palette_os_binding["governance"]["execution_authority"] is False
    assert command_palette_os_binding["governance"]["approval_decision_authority"] is False
    assert command_palette_os_binding["governance"]["memory_write"] is False
    assert command_palette_os_binding["governance"]["overlay_control_authority"] is False
    assert command_palette_os_binding["governance"]["window_management_authority"] is False
    assert command_palette_os_binding["governance"]["summon_authority"] is False
    assert command_palette_os_binding["governance"]["hotkey_registration_authority"] is False
    assert command_palette_os_binding["governance"]["tray_registration_authority"] is False
    assert command_palette_os_binding["governance"]["local_process_launch_authority"] is False
    assert command_palette_os_binding["governance"]["service_control_authority"] is False
    assert command_palette_os_binding["governance"]["capture_authority"] is False
    assert command_palette_os_binding["governance"]["new_sensing_authority"] is False
    assert command_palette_os_binding["governance"]["mutation_authority_granted"] is False
    authority_request_readback = payload["os_binding_authority_request_readback"]
    assert authority_request_readback["status"] == "none"
    assert authority_request_readback["ok"] is True
    assert authority_request_readback["kind"] == "lens.os_binding.command_palette_binding_authority.request_readback"
    assert authority_request_readback["route"] == "/lens/os-binding/authority/requests"
    assert authority_request_readback["authority_route"] == "/lens/os-binding/authority"
    assert authority_request_readback["request_route"] == "/lens/os-binding/authority/request"
    assert authority_request_readback["readiness_route"] == "/lens/os-binding/readiness"
    assert authority_request_readback["plan_route"] == "/lens/os-binding/plan"
    assert authority_request_readback["stage6_criterion_status"] == "none"
    assert authority_request_readback["stage6_criterion_readback_ready"] is True
    assert authority_request_readback["authority_required"] == "os_level_command_palette_binding_authority"
    assert authority_request_readback["pending_count"] == 0
    assert authority_request_readback["approved_count"] == 0
    assert authority_request_readback["total_count"] == 0
    assert authority_request_readback["authority_granted"] is False
    assert authority_request_readback["os_level_command_palette_binding_authority"] is False
    assert authority_request_readback["os_level_command_palette"] is False
    assert authority_request_readback["summon_anywhere"] is False
    assert authority_request_readback["opens_palette"] is False
    assert authority_request_readback["registers_hotkey"] is False
    assert authority_request_readback["launches_process"] is False
    assert authority_request_readback["controls_overlay"] is False
    assert authority_request_readback["governance"]["read_only_contract"] is True
    assert authority_request_readback["governance"]["approval_request_write"] is False
    assert authority_request_readback["governance"]["execution_authority"] is False
    assert authority_request_readback["governance"]["approval_decision_authority"] is False
    assert authority_request_readback["governance"]["memory_write"] is False
    assert authority_request_readback["governance"]["resident_claim_authority"] is False
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
        "resident_surface_runtime_proof_observed": True,
        "resident_surface_resident_runtime_proof_observed": False,
        "resident_runtime_authority_boundary_observed": True,
        "resident_runtime_authority_grant_preflight_observed": True,
        "resident_runtime_execution_policy_contract_observed": True,
        "resident_runtime_execution_authority_grant_boundary_observed": True,
        "resident_runtime_execution_authority_grant_receipt_readback_observed": True,
        "resident_runtime_execution_authority_grant_denial_receipt_readback_observed": True,
        "resident_runtime_execution_authority_grant_readiness_audit_observed": True,
        "resident_runtime_granted_boundary_proof_observed": True,
        "resident_runtime_authority_blockers_proof_observed": True,
        "resident_runtime_process_supervision_boundary_proof_observed": True,
        "resident_runtime_service_control_boundary_proof_observed": True,
        "resident_runtime_tray_presence_boundary_proof_observed": True,
        "resident_runtime_hotkey_summon_boundary_proof_observed": True,
        "resident_runtime_overlay_window_boundary_proof_observed": True,
        "resident_runtime_resident_claim_boundary_proof_observed": True,
        "command_palette_shell_bridge_observed": True,
        "command_palette_os_binding_blockers_proof_observed": True,
        "command_palette_os_binding_candidate_readback": True,
        "os_binding_authority_request_readback_observed": True,
        "resident_host_supervision_authority_preflight_observed": True,
        "resident_host_supervision_authority_denial_boundary_observed": True,
        "resident_host_supervision_authority_denial_receipt_readback_observed": True,
        "resident_host_supervision_authority_grant_receipt_readback_observed": True,
        "resident_host_supervision_authority_readiness_audit_observed": True,
        "summon_enablement_gate_handoff_readback": True,
        "persistent_supervision_enablement_denial_boundary_observed": True,
        "persistent_supervision_enablement_execution_denial_boundary_observed": True,
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
