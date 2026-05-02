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


def _run_audit(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            _powershell(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(_repo_root() / "scripts" / "lens-stage6-completion-audit.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
    )


def test_lens_stage6_completion_audit_blocks_transition_without_authority() -> None:
    proc = _run_audit(
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
    assert payload["kind"] == "lens.stage6.completion_audit"
    assert payload["status"] == "blocked"
    assert payload["audit_status"] == "complete"
    assert payload["stage"] == "Stage 6 / Lens MVP"
    assert payload["stage_state"] == "active"
    assert payload["ready_to_close"] is False
    assert payload["can_close_stage6"] is False
    assert payload["transition_allowed"] is False
    assert payload["closure_decision"] == "do_not_close_stage6"
    assert payload["next_stage"] == "Stage 7 / Telemetry"
    assert payload["checkpoint_next_smallest_truthful_gap"] == "stage6_lens_completion_audit"
    assert payload["next_smallest_truthful_gap"] == "summon_anywhere_blockers"
    assert payload["stage6_completion_reviewed"] is True
    assert (
        "Stage 6 still cannot close because summon-anywhere is blocked" in (payload["next_smallest_truthful_gap_basis"])
    )
    assert payload["remaining_stage6_acceptance_blockers"] == [
        "summon_anywhere",
        "helpful_not_noisy",
        "system_resident_presence",
    ]

    assert payload["summary"]["criteria_total"] == 5
    assert payload["summary"]["ready_total"] == 2
    assert payload["summary"]["blocked_total"] == 3
    assert payload["summary"]["ready_criteria"] == [
        "mode_visibility",
        "pilot_visibility_groundwork",
    ]
    assert payload["summary"]["blocked_criteria"] == [
        "summon_anywhere",
        "helpful_not_noisy",
        "system_resident_presence",
    ]

    blocked = {item["id"]: item for item in payload["blocked_criteria"]}
    assert blocked["helpful_not_noisy"]["blockers"] == [
        "resident_surface_not_resident",
        "resident_surface_runtime_not_supervised",
    ]
    assert "global_hotkey_binding_missing" in blocked["summon_anywhere"]["blockers"]
    assert "resident_overlay_runtime_missing" in blocked["system_resident_presence"]["blockers"]
    assert "resident_surface_runtime_missing" not in payload["closure_blockers"]["resident_surface"]
    assert "resident_surface_not_resident" in payload["closure_blockers"]["resident_surface"]
    assert "resident_surface_runtime_not_supervised" in payload["closure_blockers"]["resident_surface"]
    assert "resident_surface_missing" not in payload["closure_blockers"]["resident_surface"]
    assert "summon_binding_missing" in payload["closure_blockers"]["summon"]
    assert "tray_host_missing" in payload["closure_blockers"]["tray"]
    assert "overlay_window_missing" in payload["closure_blockers"]["overlay"]
    assert "process_supervision_authority_not_granted" in payload["closure_blockers"]["host_supervision"]
    host_supervisor_readback = payload["host_supervisor_readback"]
    assert host_supervisor_readback["readback_ready"] is True
    assert host_supervisor_readback["runtime_state_path"] == "data/runtime/lens-host-supervisor/status.json"
    assert host_supervisor_readback["freshness_window_seconds"] == 900
    assert host_supervisor_readback["freshness_status"] in {"missing", "fresh", "stale", "unknown"}
    assert isinstance(host_supervisor_readback["state_stale"], bool)
    assert isinstance(host_supervisor_readback["fresh_readback"], bool)
    assert isinstance(host_supervisor_readback["fresh_bounded_supervisor_observed"], bool)
    assert isinstance(host_supervisor_readback["fresh_supervised_session_completed"], bool)
    assert host_supervisor_readback["resident_supervised_runtime"] is False
    assert host_supervisor_readback["resident_claim_allowed"] is False
    assert host_supervisor_readback["execution_authority"] is False
    assert host_supervisor_readback["approval_decision_authority"] is False
    assert host_supervisor_readback["memory_write"] is False
    assert host_supervisor_readback["process_supervision_authority"] is False
    assert host_supervisor_readback["process_restart_authority"] is False
    assert host_supervisor_readback["service_control_authority"] is False
    assert host_supervisor_readback["resident_claim_authority"] is False
    if host_supervisor_readback["freshness_status"] == "stale":
        assert "host_supervisor_readback_stale" in host_supervisor_readback["blockers"]
        assert "host_supervisor_readback_stale" in payload["closure_blockers"]["host_supervisor_readback"]
    assert "resident_host_process_not_supervised" in payload["closure_blockers"]["process_supervision"]
    assert "process_supervision_authority_not_granted" in payload["closure_blockers"]["process_supervision"]
    assert "service_control_authority_not_granted" in payload["closure_blockers"]["service_activation"]
    assert "persistent_supervision_disabled" in payload["closure_blockers"]["persistent_supervision"]
    assert "receipt_write_authority_not_granted" in payload["closure_blockers"]["persistent_supervision"]
    assert "resident_claim_authority_not_granted" in payload["closure_blockers"]["persistent_supervision"]
    assert (
        "persistent_supervision_enablement_authority_not_granted"
        in (payload["closure_blockers"]["persistent_supervision_enablement"])
    )
    assert (
        "service_config_write_authority_not_granted"
        in (payload["closure_blockers"]["persistent_supervision_enablement"])
    )
    assert "approval_id_required" in payload["closure_blockers"]["persistent_supervision_enablement_execution"]
    assert (
        "persistent_supervision_enablement_authority_not_granted"
        in (payload["closure_blockers"]["persistent_supervision_enablement_execution"])
    )
    assert (
        "persistent_supervision_execution_authority_not_granted"
        in (payload["closure_blockers"]["persistent_supervision_enablement_execution"])
    )
    assert (
        "service_config_write_authority_not_granted"
        in (payload["closure_blockers"]["persistent_supervision_enablement_execution"])
    )
    assert (
        "persistent_supervision_enablement_authority_not_granted"
        not in payload["closure_blockers"]["persistent_supervision_enablement_authority_proof"]
    )
    assert (
        "service_config_write_authority_not_granted"
        in payload["closure_blockers"]["persistent_supervision_enablement_authority_proof"]
    )
    assert (
        "persistent_supervision_execution_authority_not_granted"
        in payload["closure_blockers"]["persistent_supervision_enablement_authority_proof"]
    )
    assert (
        "service_config_write_authority_not_granted"
        not in payload["closure_blockers"]["persistent_supervision_execution_authority_proof"]
    )
    assert (
        "persistent_supervision_execution_authority_not_granted"
        not in payload["closure_blockers"]["persistent_supervision_execution_authority_proof"]
    )
    assert (
        "receipt_write_authority_not_granted"
        not in payload["closure_blockers"]["persistent_supervision_execution_authority_proof"]
    )
    assert (
        "resident_claim_authority_not_granted"
        in payload["closure_blockers"]["persistent_supervision_execution_authority_proof"]
    )
    assert (
        "persistent_supervision_disabled"
        in payload["closure_blockers"]["persistent_supervision_resident_claim_boundary"]
    )
    assert (
        "process_supervision_disabled" in payload["closure_blockers"]["persistent_supervision_resident_claim_boundary"]
    )
    assert (
        "resident_claim_authority_not_granted"
        in payload["closure_blockers"]["persistent_supervision_resident_claim_boundary"]
    )
    assert "resident_runtime_execution_authority_not_granted" not in payload["closure_blockers"]["resident_runtime"]
    assert "local_process_launch_authority_not_granted" in payload["closure_blockers"]["resident_runtime"]
    assert "process_supervision_authority_not_granted" in payload["closure_blockers"]["resident_runtime"]
    assert "service_control_authority_not_granted" in payload["closure_blockers"]["resident_runtime"]
    assert "tray_registration_authority_not_granted" in payload["closure_blockers"]["resident_runtime"]
    assert "hotkey_registration_authority_not_granted" in payload["closure_blockers"]["resident_runtime"]
    assert "overlay_control_authority_not_granted" in payload["closure_blockers"]["resident_runtime"]
    assert "resident_claim_authority_not_granted" in payload["closure_blockers"]["resident_runtime"]
    assert payload["closure_blockers"]["resident_runtime_authority_families"] == [
        "process_supervision",
        "service_control",
        "tray_presence",
        "hotkey_summon",
        "overlay_window",
        "resident_claim",
    ]
    assert (
        "process_supervision_authority_not_granted"
        in payload["closure_blockers"]["resident_runtime_process_supervision"]
    )
    assert (
        "process_supervision_authority_not_granted"
        in payload["closure_blockers"]["resident_runtime_process_supervision_boundary"]
    )
    assert "service_control_authority_not_granted" in payload["closure_blockers"]["resident_runtime_service_control"]
    assert (
        "service_control_authority_not_granted"
        in (payload["closure_blockers"]["resident_runtime_service_control_boundary"])
    )
    assert "tray_registration_authority_not_granted" in payload["closure_blockers"]["resident_runtime_tray_presence"]
    assert (
        "tray_registration_authority_not_granted"
        in payload["closure_blockers"]["resident_runtime_tray_presence_boundary"]
    )
    assert "hotkey_registration_authority_not_granted" in payload["closure_blockers"]["resident_runtime_hotkey_summon"]
    assert (
        "hotkey_registration_authority_not_granted"
        in payload["closure_blockers"]["resident_runtime_hotkey_summon_boundary"]
    )
    assert "overlay_control_authority_not_granted" in payload["closure_blockers"]["resident_runtime_overlay_window"]
    assert (
        "overlay_control_authority_not_granted"
        in payload["closure_blockers"]["resident_runtime_overlay_window_boundary"]
    )
    assert (
        "window_management_authority_not_granted"
        in payload["closure_blockers"]["resident_runtime_overlay_window_boundary"]
    )
    assert "capture_authority_not_granted" in payload["closure_blockers"]["resident_runtime_overlay_window_boundary"]
    assert "resident_claim_authority_not_granted" in payload["closure_blockers"]["resident_runtime_resident_claim"]
    assert (
        "resident_claim_authority_not_granted"
        in payload["closure_blockers"]["resident_runtime_resident_claim_boundary"]
    )
    assert "resident_surface_runtime_missing" in payload["closure_blockers"]["resident_runtime_resident_claim_boundary"]

    resident_runtime_boundary = payload["resident_runtime_execution_boundary"]
    assert resident_runtime_boundary["status"] == "blocked"
    assert resident_runtime_boundary["ok"] is True
    assert "/lens/resident-runtime/execute" in resident_runtime_boundary["evidence"]
    assert resident_runtime_boundary["applied"] is False
    assert resident_runtime_boundary["executed"] is False
    assert resident_runtime_boundary["resident_runtime_execution_authority"] is False
    assert resident_runtime_boundary["execution_authority"] is False
    assert resident_runtime_boundary["approval_decision_authority"] is False
    assert resident_runtime_boundary["local_process_launch_authority"] is False
    assert resident_runtime_boundary["process_supervision_authority"] is False
    assert resident_runtime_boundary["service_control_authority"] is False
    assert resident_runtime_boundary["tray_registration_authority"] is False
    assert resident_runtime_boundary["hotkey_registration_authority"] is False
    assert resident_runtime_boundary["overlay_control_authority"] is False
    assert resident_runtime_boundary["memory_write"] is False
    assert resident_runtime_boundary["receipt_write_authority"] is False
    assert resident_runtime_boundary["resident_claim_authority"] is False
    assert "resident_runtime_execution_authority_not_granted" in resident_runtime_boundary["blockers"]
    assert "local_process_launch_authority_not_granted" in resident_runtime_boundary["blockers"]

    persistent_enablement_authority = payload["persistent_supervision_enablement_authority_proof"]
    assert persistent_enablement_authority["status"] == "proof_passed"
    assert persistent_enablement_authority["ok"] is True
    assert persistent_enablement_authority["exit_code"] == 0
    assert (
        "scripts/lens-persistent-supervision-enablement-authority-proof.ps1 -Mode Status"
        in (persistent_enablement_authority["evidence"])
    )
    assert "/lens/host/persistent-supervision/enablement/authority" in (persistent_enablement_authority["evidence"])
    assert persistent_enablement_authority["host_supervision_authority_grant_receipt_id"]
    assert persistent_enablement_authority["persistent_supervision_enablement_authority_grant_receipt_id"]
    assert persistent_enablement_authority["persistent_supervision_enablement_authority"] is True
    assert persistent_enablement_authority["service_config_write_authority"] is False
    assert persistent_enablement_authority["persistent_supervision_execution_authority"] is False
    assert persistent_enablement_authority["persistent_supervision_enablement_allowed"] is False
    assert persistent_enablement_authority["resident_claim_allowed"] is False
    assert persistent_enablement_authority["grant_applied"] is True
    assert persistent_enablement_authority["enablement_applied"] is False
    assert persistent_enablement_authority["executed"] is False
    assert persistent_enablement_authority["service_config_updated"] is False
    assert persistent_enablement_authority["would_update_service_config"] is False
    assert persistent_enablement_authority["would_enable_process_supervision"] is False
    assert persistent_enablement_authority["would_enable_persistent_supervision"] is False
    assert persistent_enablement_authority["would_install_service"] is False
    assert persistent_enablement_authority["would_start_service"] is False
    assert persistent_enablement_authority["would_supervise_process"] is False
    assert persistent_enablement_authority["would_restart_process"] is False
    assert persistent_enablement_authority["would_write_memory"] is False
    assert persistent_enablement_authority["would_claim_resident"] is False
    assert (
        "persistent_supervision_enablement_authority_not_granted" not in (persistent_enablement_authority["blockers"])
    )
    assert "service_config_write_authority_not_granted" in persistent_enablement_authority["blockers"]
    assert "persistent_supervision_execution_authority_not_granted" in (persistent_enablement_authority["blockers"])
    assert (
        persistent_enablement_authority["next_smallest_truthful_gap"]
        == "persistent_supervision_execution_authority_or_resident_claim_boundary"
    )

    persistent_execution_authority = payload["persistent_supervision_execution_authority_proof"]
    assert persistent_execution_authority["status"] == "proof_passed"
    assert persistent_execution_authority["ok"] is True
    assert persistent_execution_authority["exit_code"] == 0
    assert (
        "scripts/lens-persistent-supervision-execution-authority-proof.ps1 -Mode Status"
        in (persistent_execution_authority["evidence"])
    )
    assert (
        "/lens/host/persistent-supervision/enablement/execution/authority"
        in (persistent_execution_authority["evidence"])
    )
    assert persistent_execution_authority["host_supervision_authority_grant_receipt_id"]
    assert persistent_execution_authority["persistent_supervision_enablement_authority_grant_receipt_id"]
    assert persistent_execution_authority["persistent_supervision_execution_authority_grant_receipt_id"]
    assert persistent_execution_authority["persistent_supervision_enablement_authority"] is True
    assert persistent_execution_authority["service_config_write_authority"] is True
    assert persistent_execution_authority["persistent_supervision_execution_authority"] is True
    assert persistent_execution_authority["receipt_write_authority"] is True
    assert persistent_execution_authority["persistent_supervision_enablement_allowed"] is False
    assert persistent_execution_authority["resident_claim_allowed"] is False
    assert persistent_execution_authority["grant_applied"] is True
    assert persistent_execution_authority["enablement_applied"] is False
    assert persistent_execution_authority["applied"] is False
    assert persistent_execution_authority["executed"] is False
    assert persistent_execution_authority["service_config_updated"] is False
    assert persistent_execution_authority["would_update_service_config"] is False
    assert persistent_execution_authority["would_enable_persistent_supervision"] is False
    assert persistent_execution_authority["would_start_service"] is False
    assert persistent_execution_authority["would_supervise_process"] is False
    assert persistent_execution_authority["would_restart_process"] is False
    assert persistent_execution_authority["would_write_receipt"] is False
    assert persistent_execution_authority["would_write_memory"] is False
    assert persistent_execution_authority["would_claim_resident"] is False
    assert "service_config_write_authority_not_granted" not in persistent_execution_authority["blockers"]
    assert "persistent_supervision_execution_authority_not_granted" not in (persistent_execution_authority["blockers"])
    assert "receipt_write_authority_not_granted" not in persistent_execution_authority["blockers"]
    assert "resident_claim_authority_not_granted" in persistent_execution_authority["blockers"]
    assert (
        persistent_execution_authority["next_smallest_truthful_gap"]
        == "persistent_supervision_resident_claim_authority_boundary"
    )

    persistent_resident_claim_boundary = payload["persistent_supervision_resident_claim_boundary_proof"]
    assert persistent_resident_claim_boundary["status"] == "proof_passed"
    assert persistent_resident_claim_boundary["ok"] is True
    assert persistent_resident_claim_boundary["exit_code"] == 0
    assert (
        "scripts/lens-persistent-supervision-resident-claim-boundary-proof.ps1 -Mode Status"
        in persistent_resident_claim_boundary["evidence"]
    )
    assert persistent_resident_claim_boundary["authority_family"] == "resident_claim"
    assert persistent_resident_claim_boundary["previous_authority_family"] == "persistent_supervision_execution"
    assert persistent_resident_claim_boundary["next_authority_family"] == ""
    assert persistent_resident_claim_boundary["persistent_supervision_resident_claim_boundary_observed"] is True
    assert persistent_resident_claim_boundary["persistent_supervision_execution_authority_proof_observed"] is True
    assert persistent_resident_claim_boundary["persistent_supervision_plan_observed"] is True
    assert persistent_resident_claim_boundary["side_effects_denied"] is True
    assert persistent_resident_claim_boundary["final_persistent_supervision_authority_family_consumed"] is True
    assert persistent_resident_claim_boundary["persistent_supervision_enablement_authority"] is True
    assert persistent_resident_claim_boundary["service_config_write_authority"] is True
    assert persistent_resident_claim_boundary["persistent_supervision_execution_authority"] is True
    assert persistent_resident_claim_boundary["receipt_write_authority"] is True
    assert persistent_resident_claim_boundary["resident_claim_authority"] is False
    assert persistent_resident_claim_boundary["persistent_supervision_ready"] is False
    assert persistent_resident_claim_boundary["resident_claim_allowed"] is False
    assert persistent_resident_claim_boundary["applied"] is False
    assert persistent_resident_claim_boundary["executed"] is False
    assert persistent_resident_claim_boundary["service_config_updated"] is False
    assert persistent_resident_claim_boundary["would_update_service_config"] is False
    assert persistent_resident_claim_boundary["would_enable_persistent_supervision"] is False
    assert persistent_resident_claim_boundary["would_start_service"] is False
    assert persistent_resident_claim_boundary["would_supervise_process"] is False
    assert persistent_resident_claim_boundary["would_restart_process"] is False
    assert persistent_resident_claim_boundary["would_write_receipt"] is False
    assert persistent_resident_claim_boundary["would_write_memory"] is False
    assert persistent_resident_claim_boundary["would_claim_resident"] is False
    assert persistent_resident_claim_boundary["resident_claim"]["status"] == "blocked"
    assert "persistent_supervision_disabled" in persistent_resident_claim_boundary["blockers"]
    assert "process_supervision_disabled" in persistent_resident_claim_boundary["blockers"]
    assert "resident_claim_authority_not_granted" in persistent_resident_claim_boundary["blockers"]
    assert persistent_resident_claim_boundary["remaining_authority_families_after_this_boundary"] == []
    assert persistent_resident_claim_boundary["next_smallest_truthful_gap"] == "stage6_lens_completion_audit"

    granted_boundary = payload["resident_runtime_granted_boundary_proof"]
    assert granted_boundary["status"] == "proof_passed"
    assert granted_boundary["ok"] is True
    assert granted_boundary["exit_code"] == 0
    assert "scripts/lens-resident-runtime-boundary-proof.ps1" in granted_boundary["evidence"]
    assert "/lens/resident-runtime/execute" in granted_boundary["evidence"]
    assert "/lens/resident-runtime/denials" in granted_boundary["evidence"]
    assert granted_boundary["resident_runtime_execution_authority"] is True
    assert granted_boundary["runtime_ready"] is False
    assert granted_boundary["resident_claim_allowed"] is False
    assert granted_boundary["applied"] is False
    assert granted_boundary["executed"] is False
    assert granted_boundary["would_launch_process"] is False
    assert granted_boundary["would_supervise_process"] is False
    assert granted_boundary["would_start_service"] is False
    assert granted_boundary["would_register_tray"] is False
    assert granted_boundary["would_register_hotkey"] is False
    assert granted_boundary["would_open_overlay"] is False
    assert granted_boundary["would_write_memory"] is False
    assert granted_boundary["would_claim_resident"] is False
    assert granted_boundary["execution_authority"] is False
    assert granted_boundary["approval_decision_authority"] is False
    assert granted_boundary["local_process_launch_authority"] is False
    assert granted_boundary["process_supervision_authority"] is False
    assert granted_boundary["service_control_authority"] is False
    assert granted_boundary["tray_registration_authority"] is False
    assert granted_boundary["hotkey_registration_authority"] is False
    assert granted_boundary["overlay_control_authority"] is False
    assert granted_boundary["memory_write"] is False
    assert granted_boundary["receipt_write_authority"] is False
    assert granted_boundary["resident_claim_authority"] is False
    assert "resident_runtime_execution_authority_not_granted" not in granted_boundary["blockers"]
    assert "local_process_launch_authority_not_granted" in granted_boundary["blockers"]
    assert "process_supervision_authority_not_granted" in granted_boundary["blockers"]
    assert "service_control_authority_not_granted" in granted_boundary["blockers"]
    assert "tray_registration_authority_not_granted" in granted_boundary["blockers"]
    assert "hotkey_registration_authority_not_granted" in granted_boundary["blockers"]
    assert "overlay_control_authority_not_granted" in granted_boundary["blockers"]
    assert "resident_claim_authority_not_granted" in granted_boundary["blockers"]
    assert (
        granted_boundary["next_smallest_truthful_gap"]
        == "supervised_resident_runtime_process_service_tray_hotkey_overlay_authority"
    )

    runtime_authority_blockers = payload["resident_runtime_authority_blockers_proof"]
    assert runtime_authority_blockers["status"] == "proof_passed"
    assert runtime_authority_blockers["ok"] is True
    assert runtime_authority_blockers["exit_code"] == 0
    assert "scripts/lens-resident-runtime-authority-blockers-proof.ps1" in runtime_authority_blockers["evidence"]
    assert runtime_authority_blockers["next_smallest_truthful_gap"] == (
        "resident_runtime_process_supervision_authority_boundary"
    )
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
    assert runtime_authority_blockers["diagnostic_only"] is True
    assert runtime_authority_blockers["execution_authority"] is False
    assert runtime_authority_blockers["process_supervision_authority"] is False
    assert runtime_authority_blockers["service_control_authority"] is False
    assert runtime_authority_blockers["resident_claim_authority"] is False

    runtime_process_boundary = payload["resident_runtime_process_supervision_boundary_proof"]
    assert runtime_process_boundary["status"] == "proof_passed"
    assert runtime_process_boundary["ok"] is True
    assert runtime_process_boundary["exit_code"] == 0
    assert runtime_process_boundary["authority_family"] == "process_supervision"
    assert runtime_process_boundary["next_authority_family"] == "service_control"
    assert runtime_process_boundary["process_supervision_boundary_observed"] is True
    assert runtime_process_boundary["authority_blockers_proof_observed"] is True
    assert runtime_process_boundary["side_effects_denied"] is True
    assert runtime_process_boundary["first_authority_family_consumed"] is True
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

    runtime_service_boundary = payload["resident_runtime_service_control_boundary_proof"]
    assert runtime_service_boundary["status"] == "proof_passed"
    assert runtime_service_boundary["ok"] is True
    assert runtime_service_boundary["exit_code"] == 0
    assert runtime_service_boundary["authority_family"] == "service_control"
    assert runtime_service_boundary["previous_authority_family"] == "process_supervision"
    assert runtime_service_boundary["next_authority_family"] == "tray_presence"
    assert runtime_service_boundary["service_control_boundary_observed"] is True
    assert runtime_service_boundary["previous_process_supervision_family_observed"] is True
    assert runtime_service_boundary["authority_blockers_proof_observed"] is True
    assert runtime_service_boundary["side_effects_denied"] is True
    assert runtime_service_boundary["second_authority_family_consumed"] is True
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
    runtime_tray_boundary = payload["resident_runtime_tray_presence_boundary_proof"]
    assert runtime_tray_boundary["status"] == "proof_passed"
    assert runtime_tray_boundary["ok"] is True
    assert runtime_tray_boundary["exit_code"] == 0
    assert runtime_tray_boundary["authority_family"] == "tray_presence"
    assert runtime_tray_boundary["previous_authority_family"] == "service_control"
    assert runtime_tray_boundary["next_authority_family"] == "hotkey_summon"
    assert runtime_tray_boundary["tray_presence_boundary_observed"] is True
    assert runtime_tray_boundary["previous_service_control_family_observed"] is True
    assert runtime_tray_boundary["tray_preflight_observed"] is True
    assert runtime_tray_boundary["authority_blockers_proof_observed"] is True
    assert runtime_tray_boundary["side_effects_denied"] is True
    assert runtime_tray_boundary["third_authority_family_consumed"] is True
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
    assert runtime_tray_boundary["tray_preflight"]["status"] == "blocked"
    assert "tray_registration_authority_not_granted" in runtime_tray_boundary["blockers"]
    assert "tray_icon_authority_not_granted" in runtime_tray_boundary["blockers"]
    assert "notification_authority_not_granted" in runtime_tray_boundary["blockers"]
    assert runtime_tray_boundary["remaining_authority_families_after_this_boundary"] == [
        "hotkey_summon",
        "overlay_window",
        "resident_claim",
    ]
    assert runtime_tray_boundary["next_smallest_truthful_gap"] == ("resident_runtime_hotkey_summon_authority_boundary")
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
    process_boundary = payload["process_supervision_authority_boundary_proof"]
    assert process_boundary["status"] == "proof_passed"
    assert process_boundary["ok"] is True
    assert process_boundary["stage6_checkpoint_observed"] is True
    assert process_boundary["host_supervision_boundary_observed"] is True
    assert process_boundary["process_supervision_boundary_observed"] is True
    assert process_boundary["service_activation_plan_observed"] is True
    assert process_boundary["bounded_local_process_launch_observed"] is True
    assert process_boundary["supervision_ready"] is False
    assert process_boundary["ready_for_resident_claim"] is False
    assert process_boundary["resident_claim_allowed"] is False
    assert process_boundary["resident_host_supervised"] is False
    assert process_boundary["service_installed"] is False
    assert process_boundary["service_managed"] is False
    assert process_boundary["process_supervision_ready"] is False
    assert process_boundary["service_activation_ready"] is False
    assert process_boundary["would_supervise_process"] is False
    assert process_boundary["would_restart_process"] is False
    assert process_boundary["would_install_service"] is False
    assert process_boundary["would_start_service"] is False
    assert process_boundary["would_write_memory"] is False
    assert process_boundary["would_decide_approval"] is False
    assert "resident_host_process_not_supervised" in process_boundary["blockers"]
    assert "process_supervision_authority_not_granted" in process_boundary["blockers"]
    assert "scripts/lens-process-supervision-authority-boundary-proof.ps1 -Mode Status" in process_boundary["evidence"]

    persistent_plan = payload["persistent_supervision_plan"]
    assert persistent_plan["status"] == "blocked"
    assert persistent_plan["ok"] is True
    assert persistent_plan["plan_available"] is True
    assert persistent_plan["persistent_supervision_ready"] is False
    assert persistent_plan["resident_claim_allowed"] is False
    assert persistent_plan["requirements_total"] >= 10
    assert persistent_plan["requirements_blocked_total"] >= 7
    assert "persistent_supervision_enabled" in persistent_plan["blocked_requirements"]
    assert "receipt_write_authority" in persistent_plan["blocked_requirements"]
    assert "resident_claim_authority" in persistent_plan["blocked_requirements"]
    assert "persistent_supervision_disabled" in persistent_plan["blockers"]
    assert "receipt_write_authority_not_granted" in persistent_plan["blockers"]
    assert persistent_plan["would_install_service"] is False
    assert persistent_plan["would_start_service"] is False
    assert persistent_plan["would_restart_process"] is False
    assert persistent_plan["would_supervise_process"] is False
    assert persistent_plan["would_write_receipt"] is False
    assert persistent_plan["would_write_memory"] is False
    assert persistent_plan["would_claim_resident"] is False
    assert "scripts/lens-persistent-supervision-plan.ps1 -Mode Status" in persistent_plan["evidence"]

    enablement_denial = payload["persistent_supervision_enablement_denial_boundary"]
    assert enablement_denial["status"] == "blocked"
    assert enablement_denial["ok"] is True
    assert "/lens/host/persistent-supervision/enablement" in enablement_denial["evidence"]
    assert enablement_denial["boundary_ready"] is True
    assert enablement_denial["applied"] is False
    assert enablement_denial["executed"] is False
    assert enablement_denial["authority_granted"] is False
    assert enablement_denial["enablement_ready"] is False
    assert enablement_denial["resident_claim_allowed"] is False
    assert enablement_denial["service_config_updated"] is False
    assert enablement_denial["authority_grant_active"] is False
    assert "host_supervision_authority_grant_not_active" in enablement_denial["blockers"]
    assert "persistent_supervision_enablement_authority_not_granted" in enablement_denial["blockers"]
    assert "service_config_write_authority_not_granted" in enablement_denial["blockers"]
    assert enablement_denial["execution_authority"] is False
    assert enablement_denial["approval_decision_authority"] is False
    assert enablement_denial["local_process_launch_authority"] is False
    assert enablement_denial["process_supervision_authority"] is False
    assert enablement_denial["process_restart_authority"] is False
    assert enablement_denial["service_config_write_authority"] is False
    assert enablement_denial["service_control_authority"] is False
    assert enablement_denial["memory_write"] is False
    assert enablement_denial["receipt_write_authority"] is False
    assert enablement_denial["denial_receipt_write_authority"] is False
    assert enablement_denial["resident_claim_authority"] is False

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
    assert execution_denial["service_config_write_authority"] is False
    assert execution_denial["persistent_supervision_execution_authority"] is False
    assert execution_denial["service_control_authority"] is False
    assert execution_denial["memory_write"] is False
    assert execution_denial["receipt_write_authority"] is False
    assert execution_denial["denial_receipt_write_authority"] is False
    assert execution_denial["resident_claim_authority"] is False

    assert "docs/canonical/ROADMAP.md#4.12" in payload["evidence"]
    assert "scripts/lens-stage6-checkpoint.ps1 -Mode Status" in payload["evidence"]
    assert "scripts/lens-resident-runtime-boundary-proof.ps1 -Mode Status" in payload["evidence"]
    assert "scripts/lens-resident-runtime-authority-blockers-proof.ps1 -Mode Status" in payload["evidence"]
    assert "scripts/lens-resident-runtime-resident-claim-boundary-proof.ps1 -Mode Status" in payload["evidence"]
    assert "scripts/lens-process-supervision-authority-boundary-proof.ps1 -Mode Status" in payload["evidence"]
    assert "scripts/lens-persistent-supervision-plan.ps1 -Mode Status" in payload["evidence"]
    assert "scripts/lens-persistent-supervision-execution-authority-proof.ps1 -Mode Status" in payload["evidence"]
    assert "scripts/lens-persistent-supervision-resident-claim-boundary-proof.ps1 -Mode Status" in payload["evidence"]
    assert "/lens/host/persistent-supervision/enablement" in payload["evidence"]
    assert "/lens/host/persistent-supervision/enablement/execution" in payload["evidence"]
    assert "/lens/host/persistent-supervision/enablement/execution/readiness" in payload["evidence"]
    assert "/lens/resident-surface" in payload["evidence"]
    governance = payload["governance"]
    assert governance["read_only_contract"] is True
    assert governance["diagnostic_only"] is True
    assert governance["checkpoint_readback"] is True
    assert governance["process_supervision_authority_boundary_readback"] is True
    assert governance["persistent_supervision_plan_readback"] is True
    assert governance["persistent_supervision_execution_authority_proof_readback"] is True
    assert governance["persistent_supervision_resident_claim_boundary_proof_readback"] is True
    assert governance["persistent_supervision_enablement_denial_boundary_readback"] is True
    assert governance["persistent_supervision_enablement_execution_denial_boundary_readback"] is True
    assert governance["resident_runtime_granted_boundary_proof_readback"] is True
    assert governance["resident_runtime_authority_blockers_proof_readback"] is True
    assert governance["resident_runtime_process_supervision_boundary_proof_readback"] is True
    assert governance["resident_runtime_service_control_boundary_proof_readback"] is True
    assert governance["resident_runtime_tray_presence_boundary_proof_readback"] is True
    assert governance["resident_runtime_hotkey_summon_boundary_proof_readback"] is True
    assert governance["resident_runtime_overlay_window_boundary_proof_readback"] is True
    assert governance["resident_runtime_resident_claim_boundary_proof_readback"] is True
    assert governance["process_supervision_boundary_observed"] is True
    assert governance["service_activation_plan_observed"] is True
    assert governance["execution_authority"] is False
    assert governance["approval_decision_authority"] is False
    assert governance["memory_write"] is False
    assert governance["local_process_launch_authority"] is False
    assert governance["process_supervision_authority"] is False
    assert governance["service_control_authority"] is False
    assert governance["hotkey_registration_authority"] is False
    assert governance["tray_registration_authority"] is False
    assert governance["overlay_control_authority"] is False
    assert governance["summon_authority"] is False
    assert governance["telemetry_authority"] is False
