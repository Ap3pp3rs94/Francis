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
    proc = _run_audit("-Mode", "Status")

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
    assert payload["next_smallest_truthful_gap"] == "persistent_supervision_enablement_authority_not_granted"
    assert "enablement denial boundary" in payload["next_smallest_truthful_gap_basis"]
    assert "execution denial boundary" in payload["next_smallest_truthful_gap_basis"]

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
    assert "scripts/lens-process-supervision-authority-boundary-proof.ps1 -Mode Status" in payload["evidence"]
    assert "scripts/lens-persistent-supervision-plan.ps1 -Mode Status" in payload["evidence"]
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
    assert governance["persistent_supervision_enablement_denial_boundary_readback"] is True
    assert governance["persistent_supervision_enablement_execution_denial_boundary_readback"] is True
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
