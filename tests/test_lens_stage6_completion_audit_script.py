from __future__ import annotations

import json
import os
import shutil
import subprocess
from collections.abc import Mapping
from pathlib import Path

import pytest

from powershell_script_runner import run_powershell_script

_AUDIT_CHILD_PROOF_TIMEOUT_SECONDS = 120
_AUDIT_EXPECTED_SERIAL_CHILD_PROOFS = 18
_AUDIT_TRANSITION_PLAN_SERIAL_CHILD_PROOFS = 4
_AUDIT_TRANSITION_PLAN_WRAPPER_OVERHEAD_SECONDS = 60
_FULL_AUDIT_ENV = "FRANCIS_RUN_STAGE6_FULL_COMPLETION_AUDIT_TEST"
_FULL_AUDIT_TIMEOUT_ENV = "FRANCIS_STAGE6_FULL_COMPLETION_AUDIT_TIMEOUT_SECONDS"


def _powershell() -> str:
    exe = shutil.which("powershell") or shutil.which("pwsh")
    if not exe:
        pytest.skip("PowerShell is not available")
    return exe


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _full_audit_timeout_seconds(environ: Mapping[str, str] | None = None) -> int:
    values = os.environ if environ is None else environ
    configured = values.get(_FULL_AUDIT_TIMEOUT_ENV, "").strip()
    if configured:
        return int(configured)
    serial_child_budget = _AUDIT_CHILD_PROOF_TIMEOUT_SECONDS * _AUDIT_EXPECTED_SERIAL_CHILD_PROOFS
    return serial_child_budget + 180


def _transition_plan_wrapper_timeout_seconds(child_timeout_seconds: int) -> int:
    return (
        child_timeout_seconds * _AUDIT_TRANSITION_PLAN_SERIAL_CHILD_PROOFS
    ) + _AUDIT_TRANSITION_PLAN_WRAPPER_OVERHEAD_SECONDS


def _arm_full_audit_faulthandler_timeout() -> None:
    import faulthandler

    faulthandler.cancel_dump_traceback_later()
    faulthandler.dump_traceback_later(_full_audit_timeout_seconds() + 120, exit=True)


def _run_audit(*args: str) -> subprocess.CompletedProcess[str]:
    return run_powershell_script(
        _powershell(),
        _repo_root() / "scripts" / "lens-stage6-completion-audit.ps1",
        args,
        cwd=_repo_root(),
        timeout_seconds=_full_audit_timeout_seconds(),
    )


def test_lens_stage6_completion_audit_child_capture_does_not_set_invalid_encodings() -> None:
    script = (_repo_root() / "scripts" / "lens-stage6-completion-audit.ps1").read_text(encoding="utf-8")

    assert "$StartInfo.RedirectStandardOutput = $false" in script
    assert "$StartInfo.RedirectStandardError = $false" in script
    assert "$StdoutPath" in script
    assert "$StderrPath" in script
    assert "StandardOutputEncoding" not in script
    assert "StandardErrorEncoding" not in script


def test_lens_stage6_completion_audit_projects_recommended_authority_grant_state() -> None:
    script = (_repo_root() / "scripts" / "lens-stage6-completion-audit.ps1").read_text(encoding="utf-8")
    authority_grant_projection = "$RecommendedAuthorityGranted = [bool]$RecommendedHandoff.authority_granted"

    assert authority_grant_projection in script
    assert "authority_granted = $RecommendedAuthorityGranted" in script
    assert script.index(authority_grant_projection) < script.index("authority_granted = $RecommendedAuthorityGranted")


def test_lens_stage6_completion_audit_outer_timeout_covers_serial_child_budget() -> None:
    expected_minimum = _AUDIT_CHILD_PROOF_TIMEOUT_SECONDS * _AUDIT_EXPECTED_SERIAL_CHILD_PROOFS

    assert _full_audit_timeout_seconds({}) >= expected_minimum
    assert _full_audit_timeout_seconds({_FULL_AUDIT_TIMEOUT_ENV: "777"}) == 777


def test_lens_stage6_completion_audit_budgets_transition_plan_wrapper() -> None:
    script = (_repo_root() / "scripts" / "lens-stage6-completion-audit.ps1").read_text(encoding="utf-8")

    assert "$PersistentSupervisionEnablementTransitionPlanProofChildProofCount = 4" in script
    assert "$ChildProofTimeoutSeconds * $PersistentSupervisionEnablementTransitionPlanProofChildProofCount" in script
    assert "'-ChildProofTimeoutSeconds', [string]$ChildProofTimeoutSeconds" in script
    assert "-TimeoutSeconds $PersistentSupervisionEnablementTransitionPlanProofTimeoutSeconds" in script


def test_lens_stage6_completion_audit_projects_persistent_prerequisite_first_missing_readback() -> None:
    script = (_repo_root() / "scripts" / "lens-stage6-completion-audit.ps1").read_text(encoding="utf-8")
    first_missing_projection = (
        "$PersistentSupervisionPrerequisitesFirstMissingRequiredBeforeEnable = "
        "[string]$PersistentSupervisionPrerequisitesProof.first_missing_required_before_enable"
    )

    assert first_missing_projection in script
    assert (
        "$PersistentSupervisionPrerequisitesFirstMissingRequirementHandoff = "
        "$PersistentSupervisionPrerequisitesProof.first_missing_requirement_handoff"
    ) in script
    assert (
        "persistent_supervision_first_missing_required_before_enable = "
        "$PersistentSupervisionPrerequisitesFirstMissingRequiredBeforeEnable"
    ) in script
    assert (
        "persistent_supervision_first_missing_requirement_handoff = "
        "$PersistentSupervisionPrerequisitesFirstMissingRequirementHandoff"
    ) in script
    assert (
        "first_missing_required_before_enable = $PersistentSupervisionPrerequisitesFirstMissingRequiredBeforeEnable"
        in script
    )
    assert (
        "first_missing_requirement_handoff = $PersistentSupervisionPrerequisitesFirstMissingRequirementHandoff"
        in script
    )
    assert "authority_required = [string]$PersistentSupervisionPrerequisitesProof.authority_required" in script
    assert "authority_granted = [bool]$PersistentSupervisionPrerequisitesProof.authority_granted" in script
    assert "-not [bool]$PersistentSupervisionPrerequisitesProof.authority_granted" in script


def test_lens_stage6_completion_audit_preserves_persistent_authority_child_readbacks() -> None:
    script = (_repo_root() / "scripts" / "lens-stage6-completion-audit.ps1").read_text(encoding="utf-8")

    assert "authority_required = [string]$ResidentSupervisionPersistenceBoundaryProof.authority_required" in script
    assert "authority_granted = [bool]$ResidentSupervisionPersistenceBoundaryProof.authority_granted" in script
    assert "-not [bool]$ResidentSupervisionPersistenceBoundaryProof.authority_granted" in script
    assert "authority_required = [string]$PersistentSupervisionEnablementAuthorityProof.authority_required" in script
    assert "authority_granted = [bool]$PersistentSupervisionEnablementAuthorityProof.authority_granted" in script
    assert "authority_required = [string]$PersistentSupervisionExecutionAuthorityProof.authority_required" in script
    assert "authority_granted = [bool]$PersistentSupervisionExecutionAuthorityProof.authority_granted" in script
    assert "authority_required = [string]$PersistentSupervisionResidentClaimBoundaryProof.authority_required" in script
    assert "authority_granted = [bool]$PersistentSupervisionResidentClaimBoundaryProof.authority_granted" in script
    assert "authority_required = [string]$PersistentSupervisionServiceInstallPlanProof.authority_required" in script
    assert "authority_granted = [bool]$PersistentSupervisionServiceInstallPlanProof.authority_granted" in script
    assert "-not [bool]$PersistentSupervisionServiceInstallPlanProof.authority_granted" in script


def test_lens_stage6_completion_audit_preserves_checkpoint_enablement_denial_authority_readback() -> None:
    script = (_repo_root() / "scripts" / "lens-stage6-completion-audit.ps1").read_text(encoding="utf-8")

    assert (
        "[string]$PersistentSupervisionEnablementDenial.authority_required -eq "
        "'persistent_supervision_enablement_authority'"
    ) in script
    assert "authority_required = [string]$PersistentSupervisionEnablementDenial.authority_required" in script
    assert "-not [bool]$PersistentSupervisionEnablementDenial.authority_granted" in script


def test_lens_stage6_completion_audit_preserves_checkpoint_enablement_execution_denial_authority_readback() -> None:
    script = (_repo_root() / "scripts" / "lens-stage6-completion-audit.ps1").read_text(encoding="utf-8")

    assert (
        "[string]$PersistentSupervisionEnablementExecutionDenial.enablement_authority_required -eq "
        "'persistent_supervision_enablement_authority'"
    ) in script
    assert (
        "enablement_authority_required = "
        "[string]$PersistentSupervisionEnablementExecutionDenial.enablement_authority_required"
    ) in script
    assert "-not [bool]$PersistentSupervisionEnablementExecutionDenial.enablement_authority_granted" in script


def test_lens_stage6_completion_audit_preserves_checkpoint_execution_authority_denial_readback() -> None:
    script = (_repo_root() / "scripts" / "lens-stage6-completion-audit.ps1").read_text(encoding="utf-8")

    assert (
        "[string]$PersistentSupervisionEnablementExecutionDenial."
        "persistent_supervision_execution_authority_required -eq "
        "'persistent_supervision_execution_authority'"
    ) in script
    assert (
        "persistent_supervision_execution_authority_required = "
        "[string]$PersistentSupervisionEnablementExecutionDenial."
        "persistent_supervision_execution_authority_required"
    ) in script
    assert "persistent_supervision_execution_authority = $false" in script


def test_lens_stage6_completion_audit_preserves_checkpoint_enablement_service_config_authority_readback() -> None:
    script = (_repo_root() / "scripts" / "lens-stage6-completion-audit.ps1").read_text(encoding="utf-8")

    assert (
        "[string]$PersistentSupervisionEnablementDenial.service_config_write_authority_required -eq "
        "'service_config_write_authority'"
    ) in script
    assert (
        "service_config_write_authority_required = "
        "[string]$PersistentSupervisionEnablementDenial.service_config_write_authority_required"
    ) in script
    assert "service_config_write_authority = $false" in script


def test_lens_stage6_completion_audit_preserves_checkpoint_execution_service_config_authority_readback() -> None:
    script = (_repo_root() / "scripts" / "lens-stage6-completion-audit.ps1").read_text(encoding="utf-8")

    assert (
        "[string]$PersistentSupervisionEnablementExecutionDenial."
        "service_config_write_authority_required -eq 'service_config_write_authority'"
    ) in script
    assert (
        "service_config_write_authority_required = "
        "[string]$PersistentSupervisionEnablementExecutionDenial."
        "service_config_write_authority_required"
    ) in script
    assert "service_config_write_authority = $false" in script


def test_lens_stage6_completion_audit_preserves_resident_runtime_local_process_authority_readback() -> None:
    script = (_repo_root() / "scripts" / "lens-stage6-completion-audit.ps1").read_text(encoding="utf-8")

    assert (
        "[string]$ResidentRuntimeBoundary.local_process_launch_authority_required -eq 'local_process_launch_authority'"
    ) in script
    assert (
        "local_process_launch_authority_required = "
        "[string]$ResidentRuntimeBoundary.local_process_launch_authority_required"
    ) in script
    assert "local_process_launch_authority = $false" in script


def test_lens_stage6_completion_audit_preserves_resident_runtime_authority_child_readback() -> None:
    script = (_repo_root() / "scripts" / "lens-stage6-completion-audit.ps1").read_text(encoding="utf-8")

    assert "authority_required = [string]$ResidentRuntimeAuthorityBlockersProof.authority_required" in script
    assert "authority_granted = [bool]$ResidentRuntimeAuthorityBlockersProof.authority_granted" in script
    assert "authority_required = [string]$ResidentRuntimeProcessSupervisionBoundaryProof.authority_required" in script
    assert "authority_granted = [bool]$ResidentRuntimeProcessSupervisionBoundaryProof.authority_granted" in script
    assert "authority_required = [string]$ResidentRuntimeServiceControlBoundaryProof.authority_required" in script
    assert "authority_granted = [bool]$ResidentRuntimeServiceControlBoundaryProof.authority_granted" in script
    assert "authority_required = [string]$ResidentRuntimeTrayPresenceBoundaryProof.authority_required" in script
    assert "authority_granted = [bool]$ResidentRuntimeTrayPresenceBoundaryProof.authority_granted" in script
    assert "authority_required = [string]$ResidentRuntimeHotkeySummonBoundaryProof.authority_required" in script
    assert "authority_granted = [bool]$ResidentRuntimeHotkeySummonBoundaryProof.authority_granted" in script
    assert "authority_required = [string]$ResidentRuntimeOverlayWindowBoundaryProof.authority_required" in script
    assert "authority_granted = [bool]$ResidentRuntimeOverlayWindowBoundaryProof.authority_granted" in script
    assert "authority_required = [string]$ResidentRuntimeResidentClaimBoundaryProof.authority_required" in script
    assert "authority_granted = [bool]$ResidentRuntimeResidentClaimBoundaryProof.authority_granted" in script


def test_lens_stage6_completion_audit_preserves_process_supervision_handoff_authority_readback() -> None:
    script = (_repo_root() / "scripts" / "lens-stage6-completion-audit.ps1").read_text(encoding="utf-8")

    assert "authority_required = [string]$ResidentHostRuntimeBoundaryProof.authority_required" in script
    assert "authority_granted = [bool]$ResidentHostRuntimeBoundaryProof.authority_granted" in script
    assert "authority_required = [string]$ResidentHostProcessSupervisionBlockerProof.authority_required" in script
    assert "authority_granted = [bool]$ResidentHostProcessSupervisionBlockerProof.authority_granted" in script


def test_lens_stage6_completion_audit_preserves_summon_authority_handoff_readback() -> None:
    script = (_repo_root() / "scripts" / "lens-stage6-completion-audit.ps1").read_text(encoding="utf-8")

    assert "authority_required = [string]$SummonAuthorityBlockerProof.authority_required" in script
    assert "authority_granted = [bool]$SummonAuthorityBlockerProof.authority_granted" in script
    assert "authority_required = [string]$SummonAnywhereFamilyChainProof.authority_required" in script
    assert "authority_granted = [bool]$SummonAnywhereFamilyChainProof.authority_granted" in script
    assert "authority_required = [string]$SummonAnywhereFamilyChainProofResidentHost.authority_required" in script
    assert "authority_granted = [bool]$SummonAnywhereFamilyChainProofResidentHost.authority_granted" in script
    assert "authority_required = [string]$SummonAnywhereFamilyChainProofFinalAuthority.authority_required" in script
    assert "authority_granted = [bool]$SummonAnywhereFamilyChainProofFinalAuthority.authority_granted" in script


@pytest.mark.skipif(
    os.environ.get(_FULL_AUDIT_ENV) != "1",
    reason=(
        f"Full Stage 6 completion audit runs nested live diagnostics; set {_FULL_AUDIT_ENV}=1 to run it explicitly."
    ),
)
def test_lens_stage6_completion_audit_blocks_transition_without_authority() -> None:
    _arm_full_audit_faulthandler_timeout()

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
        "-ChildProofTimeoutSeconds",
        str(_AUDIT_CHILD_PROOF_TIMEOUT_SECONDS),
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
    assert payload["requested_startup_timeout_seconds"] == 5
    assert payload["child_startup_timeout_seconds"] >= 30
    assert payload["requested_child_host_launch_run_seconds"] == 2
    assert payload["child_host_launch_run_seconds"] >= 5
    assert payload["child_proof_timeout_seconds"] == _AUDIT_CHILD_PROOF_TIMEOUT_SECONDS
    assert payload["child_proof_timeouts"] == []
    child_proof_runs = {item["name"]: item for item in payload["child_proof_runs"]}
    assert set(child_proof_runs) == {
        "summon_anywhere_blockers",
        "summon_authority_blocker",
        "summon_anywhere_family_chain",
        "resident_host_runtime_boundary",
        "process_supervision_boundary",
        "resident_host_process_supervision_blocker",
        "resident_supervision_persistence_boundary",
        "host_supervision_authority_request",
        "persistent_supervision_plan",
        "persistent_supervision_prerequisites",
        "persistent_supervision_service_install_plan",
        "persistent_supervision_enablement_authority",
        "persistent_supervision_execution_authority",
        "persistent_supervision_resident_claim_boundary",
        "persistent_supervision_enablement_transition_plan",
    }
    expected_child_proof_timeouts = {name: _AUDIT_CHILD_PROOF_TIMEOUT_SECONDS for name in child_proof_runs} | {
        "resident_supervision_persistence_boundary": min(_AUDIT_CHILD_PROOF_TIMEOUT_SECONDS, 240),
        "persistent_supervision_prerequisites": min(_AUDIT_CHILD_PROOF_TIMEOUT_SECONDS, 240),
        "persistent_supervision_enablement_transition_plan": _transition_plan_wrapper_timeout_seconds(
            _AUDIT_CHILD_PROOF_TIMEOUT_SECONDS
        ),
    }
    for name, run in child_proof_runs.items():
        assert run["timed_out"] is False
        assert run["timeout_seconds"] == expected_child_proof_timeouts[name]
        assert isinstance(run["duration_ms"], int)
        assert run["duration_ms"] >= 0
    # The nested checkpoint is a live diagnostic and can stop at an earlier
    # known resident-runtime boundary on slower Windows runners; the completion
    # audit decision below remains strict.
    assert payload["checkpoint_next_smallest_truthful_gap"] in {
        "resident_overlay_activation_or_process_supervision_authority_boundary",
        "live_operator_experience_proof",
        "stage6_lens_completion_audit",
    }
    assert payload["stage6_completion_reviewed"] is True
    assert payload["next_smallest_truthful_gap"] == "persistent_supervision_required_prerequisites_missing"
    assert payload["recommended_handoff_source"] == "resident_host_process_supervision_handoff_consumed"
    assert (
        payload["recommended_next_slice"] == "resolve_persistent_supervision_required_prerequisites_before_enablement"
    )
    assert (
        payload["recommended_proof_script"]
        == "scripts/lens-persistent-supervision-prerequisites-proof.ps1 -Mode Status"
    )
    assert payload["authority_required"] == "resident_host_process_tray_hotkey_overlay_and_summon_prerequisites"
    assert payload["authority_granted"] is False
    assert payload["persistent_supervision_first_missing_required_before_enable"] == "resident_host_process"
    first_missing_handoff = payload["persistent_supervision_first_missing_requirement_handoff"]
    assert first_missing_handoff["id"] == "resident_host_process"
    assert first_missing_handoff["next_smallest_truthful_gap"] == "resident_host_process_not_supervised"
    assert first_missing_handoff["read_only_contract"] is True
    assert first_missing_handoff["diagnostic_only"] is True
    assert first_missing_handoff["would_execute"] is False
    assert first_missing_handoff["would_mutate"] is False
    recommended_handoff = payload["recommended_handoff"]
    assert recommended_handoff["status"] == "blocked"
    assert recommended_handoff["next_smallest_truthful_gap"] == "persistent_supervision_required_prerequisites_missing"
    assert recommended_handoff["next_step"] == "resolve_persistent_supervision_required_prerequisites_before_enablement"
    assert (
        recommended_handoff["proof_script"]
        == "scripts/lens-persistent-supervision-prerequisites-proof.ps1 -Mode Status"
    )
    assert recommended_handoff["route"] == "/lens/host/persistent-supervision"
    assert recommended_handoff["readiness_route"] == "/lens/host/persistent-supervision/enablement"
    assert (
        recommended_handoff["authority_required"]
        == "resident_host_process_tray_hotkey_overlay_and_summon_prerequisites"
    )
    assert recommended_handoff["authority_granted"] is False
    assert recommended_handoff["process_supervision_boundary_observed"] is True
    assert recommended_handoff["process_supervision_handoff_consumed"] is True
    assert recommended_handoff["process_supervision_ready"] is False
    assert recommended_handoff["service_activation_ready"] is False
    assert recommended_handoff["supervision_ready"] is False
    assert recommended_handoff["resident_host_supervised"] is False
    assert recommended_handoff["service_installed"] is False
    assert recommended_handoff["service_managed"] is False
    assert recommended_handoff["first_missing_required_before_enable"] == "resident_host_process"
    assert recommended_handoff["first_missing_requirement_handoff"] == first_missing_handoff
    assert recommended_handoff["read_only_contract"] is True
    assert recommended_handoff["diagnostic_only"] is True
    assert recommended_handoff["would_execute"] is False
    assert recommended_handoff["would_mutate"] is False
    assert recommended_handoff["would_supervise_process"] is False
    assert recommended_handoff["would_restart_process"] is False
    assert recommended_handoff["would_install_service"] is False
    assert recommended_handoff["would_start_service"] is False
    assert recommended_handoff["would_write_memory"] is False
    assert recommended_handoff["would_decide_approval"] is False
    assert "resident_host_process_not_supervised" in recommended_handoff["blockers"]
    assert (
        "Persistent supervision remains blocked because resident-host process, tray, global hotkey, overlay, and summon-binding prerequisites are still missing"
        in (payload["next_smallest_truthful_gap_basis"])
    )
    assert (
        "No runtime launch, service-config mutation, memory write, or resident claim is made"
        in (payload["next_smallest_truthful_gap_basis"])
    )
    assert payload["remaining_stage6_acceptance_blockers"] == [
        "summon_anywhere",
        "helpful_not_noisy",
        "system_resident_presence",
    ]
    if not payload["stage6_completion_reviewed"]:
        return

    expected_summon_family_ids = [
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
        "blockers": ["local_process_launch_authority_not_granted"],
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
    assert payload["summon_anywhere_blocked_families"] == expected_summon_family_ids
    assert payload["summon_anywhere_first_blocker_family"] == "resident_host"
    assert payload["summon_anywhere_first_blocker_family_handoff_observed"] is True
    assert payload["summon_anywhere_first_blocker_family_handoff"] == expected_first_summon_handoff
    assert payload["summon_anywhere_first_blocker_family_runtime_boundary_observed"] is True
    assert (
        payload["summon_anywhere_first_blocker_family_runtime_boundary_next_smallest_truthful_gap"]
        == "resident_host_process_not_supervised"
    )
    assert [item["id"] for item in payload["summon_anywhere_blocker_family_handoffs"]] == expected_summon_family_ids
    expected_checkpoint_first_summon_handoff = {
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
    expected_checkpoint_runtime_blockers = {
        "lens_host_persistent_supervision_prerequisites_pending",
        "lens_host_persistent_supervision_prerequisites_pending",
    }
    expected_checkpoint_required_blockers = {"local_process_launch_authority_not_granted"}
    expected_checkpoint_allowed_blockers = (
        expected_checkpoint_required_blockers | expected_checkpoint_runtime_blockers | {"resident_host_process_missing"}
    )
    assert payload["checkpoint_summon_enablement_gate_handoff_observed"] is True
    checkpoint_summon_handoff = payload["checkpoint_summon_enablement_gate_handoff"]
    assert checkpoint_summon_handoff["status"] == "blocked"
    assert checkpoint_summon_handoff["ok"] is True
    assert checkpoint_summon_handoff["ready"] is False
    assert checkpoint_summon_handoff["summon_anywhere"] is False
    assert checkpoint_summon_handoff["operator_surface_readback_ready"] is True
    assert checkpoint_summon_handoff["handoff_observed"] is True
    assert checkpoint_summon_handoff["first_blocker_family"] == "resident_host"
    assert checkpoint_summon_handoff["blocked_families"] == expected_summon_family_ids
    assert [item["id"] for item in checkpoint_summon_handoff["blocked_family_handoffs"]] == expected_summon_family_ids
    checkpoint_first_summon_handoff = checkpoint_summon_handoff["first_blocker_family_handoff"]
    assert {key: value for key, value in checkpoint_first_summon_handoff.items() if key != "blockers"} == (
        expected_checkpoint_first_summon_handoff
    )
    checkpoint_first_summon_handoff_blockers = set(checkpoint_first_summon_handoff["blockers"])
    assert expected_checkpoint_required_blockers <= checkpoint_first_summon_handoff_blockers
    assert checkpoint_first_summon_handoff_blockers & expected_checkpoint_runtime_blockers
    assert checkpoint_first_summon_handoff_blockers <= expected_checkpoint_allowed_blockers
    assert checkpoint_summon_handoff["next_smallest_truthful_gap"] == "summon_anywhere_blockers"
    assert "/lens/status" in checkpoint_summon_handoff["evidence"]
    assert "summon_authority_not_granted" in checkpoint_summon_handoff["blockers"]
    assert checkpoint_summon_handoff["execution_authority"] is False
    assert checkpoint_summon_handoff["approval_decision_authority"] is False
    assert checkpoint_summon_handoff["local_process_launch_authority"] is False
    assert checkpoint_summon_handoff["hotkey_registration_authority"] is False
    assert checkpoint_summon_handoff["tray_registration_authority"] is False
    assert checkpoint_summon_handoff["overlay_control_authority"] is False
    assert checkpoint_summon_handoff["summon_authority"] is False
    assert checkpoint_summon_handoff["memory_write"] is False
    assert checkpoint_summon_handoff["receipt_write_authority"] is False
    assert checkpoint_summon_handoff["resident_claim_authority"] is False
    summon_blocker_groups = payload["summon_anywhere_blocker_groups"]
    assert set(summon_blocker_groups["resident_host"]) & expected_checkpoint_runtime_blockers
    assert "local_process_launch_authority_not_granted" in summon_blocker_groups["resident_host"]
    assert "tray_host_missing" in summon_blocker_groups["tray_presence"]
    assert "overlay_window_missing" in summon_blocker_groups["overlay_window"]
    assert "global_hotkey_binding_missing" in summon_blocker_groups["global_hotkey_binding"]
    assert "summon_binding_missing" in summon_blocker_groups["summon_binding"]
    assert "summon_authority_not_granted" in summon_blocker_groups["authority"]

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
    helpful_not_noisy_blockers = set(blocked["helpful_not_noisy"]["blockers"])
    resident_surface_blockers = {
        "resident_surface_not_resident",
        "resident_surface_runtime_not_supervised",
    }
    early_live_readback_blockers = {
        "operator_experience_proof_missing",
        "resident_surface_runtime_missing",
    }
    assert (
        resident_surface_blockers <= helpful_not_noisy_blockers
        or early_live_readback_blockers <= helpful_not_noisy_blockers
    )
    assert helpful_not_noisy_blockers <= resident_surface_blockers | early_live_readback_blockers
    assert "global_hotkey_binding_missing" in blocked["summon_anywhere"]["blockers"]
    assert "os_level_command_palette_missing" in payload["closure_blockers"]["command_palette"]
    assert "summon_anywhere_missing" in payload["closure_blockers"]["command_palette"]
    assert "global_hotkey_binding_missing" in payload["closure_blockers"]["command_palette"]
    assert "os_level_command_palette_missing" in payload["closure_blockers"]["command_palette_os_binding"]
    assert "global_hotkey_binding_disabled" in payload["closure_blockers"]["command_palette_os_binding"]
    assert "lens_summon_binding_disabled_pending_authority" in payload["closure_blockers"]["command_palette_os_binding"]
    assert "tray_host_disabled" in payload["closure_blockers"]["command_palette_os_binding"]
    assert "overlay_window_disabled" in payload["closure_blockers"]["command_palette_os_binding"]
    assert "summon_authority_not_granted" in payload["closure_blockers"]["command_palette_os_binding"]
    assert "resident_overlay_runtime_missing" in blocked["system_resident_presence"]["blockers"]
    if early_live_readback_blockers <= helpful_not_noisy_blockers:
        assert "resident_surface_runtime_missing" in payload["closure_blockers"]["resident_surface"]
    else:
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
    assert (
        "resident_host_process_not_supervised"
        in payload["closure_blockers"]["resident_host_process_supervision_handoff"]
    )
    assert (
        "process_supervision_authority_not_granted"
        in payload["closure_blockers"]["resident_host_process_supervision_handoff"]
    )
    assert (
        "process_restart_authority_not_granted"
        in payload["closure_blockers"]["resident_host_process_supervision_handoff"]
    )
    assert (
        "resident_supervision_not_persistent"
        in payload["closure_blockers"]["resident_supervision_persistence_boundary"]
    )
    assert (
        "persistent_supervision_authority_not_granted"
        in payload["closure_blockers"]["resident_supervision_persistence_boundary"]
    )
    assert (
        "persistent_process_supervision_authority_required"
        in payload["closure_blockers"]["resident_supervision_persistence_boundary"]
    )
    assert payload["resident_supervision_persistence_boundary_proof_observed"] is True
    resident_persistence_boundary = payload["resident_supervision_persistence_boundary_proof"]
    assert resident_persistence_boundary["status"] == "proof_passed"
    assert resident_persistence_boundary["ok"] is True
    assert resident_persistence_boundary["exit_code"] == 0
    assert resident_persistence_boundary["acceptance_criterion"] == "system_resident_presence"
    assert (
        resident_persistence_boundary["previous_next_smallest_truthful_gap"] == "resident_host_process_not_supervised"
    )
    assert (
        resident_persistence_boundary["consumed_resident_candidate_next_smallest_truthful_gap"]
        == "resident_supervision_not_persistent"
    )
    assert resident_persistence_boundary["route_next_smallest_truthful_gap"] == (
        "persistent_supervision_authority_not_granted"
    )
    assert resident_persistence_boundary["next_smallest_truthful_gap"] == (
        "persistent_supervision_authority_not_granted"
    )
    assert resident_persistence_boundary["recommended_next_slice"] == (
        "prove_persistent_supervision_enablement_authority_after_candidate_handoff"
    )
    assert resident_persistence_boundary["recommended_proof_script"] == (
        "scripts/lens-persistent-supervision-enablement-authority-proof.ps1 -Mode Status"
    )
    assert resident_persistence_boundary["recommended_route"] == (
        "/lens/host/persistent-supervision/enablement/authority"
    )
    assert resident_persistence_boundary["recommended_readiness_route"] == (
        "/lens/host/persistent-supervision/enablement/authority/readiness"
    )
    assert resident_persistence_boundary["resident_candidate_boundary_proof_observed"] is True
    assert resident_persistence_boundary["persistent_supervision_plan_candidate_readback_observed"] is True
    assert resident_persistence_boundary["persistent_supervision_enablement_candidate_readback_observed"] is True
    assert resident_persistence_boundary["resident_dependency_candidate_readback_observed"] is True
    assert resident_persistence_boundary["route_blocking_preserved"] is True
    assert resident_persistence_boundary["side_effects_bounded"] is True
    assert resident_persistence_boundary["resident_runtime_candidate_supervised"] is True
    assert resident_persistence_boundary["resident_supervised_runtime"] is False
    assert resident_persistence_boundary["resident_host_process_requirement_state"] == (
        "resident_candidate_observed_not_persistent"
    )
    assert resident_persistence_boundary["resident_host_process_blocker"] == "resident_supervision_not_persistent"
    assert resident_persistence_boundary["authority_required"] == "persistent_process_supervision_authority"
    assert resident_persistence_boundary["authority_granted"] is False
    assert resident_persistence_boundary["plan_route"] == "/lens/host/persistent-supervision"
    assert resident_persistence_boundary["enablement_route"] == "/lens/host/persistent-supervision/enablement"
    assert all(item["passed"] for item in resident_persistence_boundary["checks"])
    assert resident_persistence_boundary["governance"]["diagnostic_only"] is True
    assert resident_persistence_boundary["governance"]["route_readback_contract"] is True
    assert resident_persistence_boundary["governance"]["wraps_resident_host_runtime_boundary_proof"] is True
    assert resident_persistence_boundary["governance"]["wraps_persistent_supervision_plan_route"] is True
    assert resident_persistence_boundary["governance"]["wraps_persistent_supervision_enablement_route"] is True
    assert resident_persistence_boundary["governance"]["execution_authority"] is False
    assert resident_persistence_boundary["governance"]["approval_decision_authority"] is False
    assert resident_persistence_boundary["governance"]["api_local_process_launch_authority"] is False
    assert resident_persistence_boundary["governance"]["process_supervision_authority"] is False
    assert resident_persistence_boundary["governance"]["memory_write"] is False
    assert resident_persistence_boundary["governance"]["receipt_write_authority"] is False
    assert resident_persistence_boundary["governance"]["resident_claim_authority"] is False
    assert resident_persistence_boundary["governance"]["mutation_authority_granted"] is False
    host_authority_handoff = payload["resident_host_supervision_authority_readiness_handoff"]
    assert host_authority_handoff["status"] == "blocked"
    assert host_authority_handoff["audit_status"] == "complete"
    assert host_authority_handoff["ok"] is True
    assert host_authority_handoff["ready"] is False
    assert host_authority_handoff["readback_ready"] is True
    assert host_authority_handoff["request_readback_ready"] is True
    assert host_authority_handoff["handoff_observed"] is True
    assert host_authority_handoff["first_blocked_requirement"] == "exact_supervision_authority_approval"
    assert [item["id"] for item in host_authority_handoff["blocked_requirement_handoffs"]] == (
        host_authority_handoff["blocked_requirements"]
    )
    assert host_authority_handoff["first_blocked_requirement_handoff"] == {
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
    assert host_authority_handoff["next_smallest_truthful_gap"] == ("host_supervision_authority_exact_approval_request")
    assert host_authority_handoff["execution_authority"] is False
    assert host_authority_handoff["approval_decision_authority"] is False
    assert host_authority_handoff["local_process_launch_authority"] is False
    assert host_authority_handoff["process_supervision_authority"] is False
    assert host_authority_handoff["process_restart_authority"] is False
    assert host_authority_handoff["service_install_authority"] is False
    assert host_authority_handoff["service_control_authority"] is False
    assert host_authority_handoff["memory_write"] is False
    assert host_authority_handoff["resident_claim_authority"] is False
    assert (
        "exact_supervision_authority_approval"
        in (payload["closure_blockers"]["host_supervision_authority_readiness_handoff"])
    )
    host_authority_request_proof = payload["host_supervision_authority_request_proof"]
    assert host_authority_request_proof["status"] == "proof_passed"
    assert host_authority_request_proof["ok"] is True
    assert host_authority_request_proof["exit_code"] == 0
    assert (
        "scripts/lens-host-supervision-authority-request-proof.ps1 -Mode Status"
        in host_authority_request_proof["evidence"]
    )
    assert "/lens/host/supervision/authority/request" in host_authority_request_proof["evidence"]
    assert "/lens/host/persistent-supervision/enablement" in host_authority_request_proof["evidence"]
    assert host_authority_request_proof["host_supervision_authority_approval_id"]
    assert host_authority_request_proof["host_supervision_authority_grant_receipt_id"]
    assert host_authority_request_proof["authority_granted"] is True
    assert host_authority_request_proof["grant_applied"] is True
    assert host_authority_request_proof["executed"] is False
    assert host_authority_request_proof["supervision_ready"] is False
    assert host_authority_request_proof["resident_claim_allowed"] is False
    assert host_authority_request_proof["process_supervision_authority"] is True
    assert host_authority_request_proof["process_restart_authority"] is True
    assert host_authority_request_proof["service_install_authority"] is True
    assert host_authority_request_proof["service_control_authority"] is True
    assert host_authority_request_proof["receipt_write_authority"] is True
    assert host_authority_request_proof["resident_claim_authority"] is True
    assert host_authority_request_proof["memory_write"] is False
    assert host_authority_request_proof["runtime_files"] == {
        "lens_host_status": False,
        "lens_host_pid": False,
        "lens_host_supervisor_status": False,
    }
    assert "persistent_supervision_required_prerequisites_missing" in host_authority_request_proof["blockers"]
    assert "process_supervision_disabled" not in host_authority_request_proof["blockers"]
    assert host_authority_request_proof["next_smallest_truthful_gap"] == (
        "persistent_supervision_required_prerequisites_missing"
    )
    assert (
        "persistent_supervision_required_prerequisites_missing"
        in (payload["closure_blockers"]["host_supervision_authority_request_proof"])
    )
    assert (
        "process_supervision_disabled" not in (payload["closure_blockers"]["host_supervision_authority_request_proof"])
    )
    helpful_authority_handoff = payload["helpful_not_noisy_runtime_authority_readiness_handoff"]
    assert helpful_authority_handoff["status"] == "blocked"
    assert helpful_authority_handoff["audit_status"] == "complete"
    assert helpful_authority_handoff["ok"] is True
    assert helpful_authority_handoff["ready"] is False
    assert helpful_authority_handoff["readback_ready"] is True
    assert helpful_authority_handoff["handoff_observed"] is True
    assert (
        helpful_authority_handoff["first_blocked_requirement"] == "exact_resident_runtime_execution_authority_approval"
    )
    assert [item["id"] for item in helpful_authority_handoff["blocked_requirement_handoffs"]] == (
        helpful_authority_handoff["blocked_requirements"]
    )
    assert helpful_authority_handoff["first_blocked_requirement_handoff"] == {
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
        helpful_authority_handoff["next_smallest_truthful_gap"]
        == "approve_resident_runtime_execution_authority_grant_receipt"
    )
    assert helpful_authority_handoff["execution_authority"] is False
    assert helpful_authority_handoff["approval_decision_authority"] is False
    assert helpful_authority_handoff["local_process_launch_authority"] is False
    assert helpful_authority_handoff["process_supervision_authority"] is False
    assert helpful_authority_handoff["service_control_authority"] is False
    assert helpful_authority_handoff["tray_registration_authority"] is False
    assert helpful_authority_handoff["hotkey_registration_authority"] is False
    assert helpful_authority_handoff["overlay_control_authority"] is False
    assert helpful_authority_handoff["memory_write"] is False
    assert helpful_authority_handoff["resident_claim_authority"] is False
    assert (
        "exact_resident_runtime_execution_authority_approval"
        in (payload["closure_blockers"]["helpful_not_noisy_runtime_authority_readiness_handoff"])
    )
    assert (
        "resident_runtime_execution_authority"
        in (payload["closure_blockers"]["helpful_not_noisy_runtime_authority_readiness_handoff"])
    )
    assert "service_control_authority_not_granted" in payload["closure_blockers"]["service_activation"]
    assert (
        "persistent_supervision_required_prerequisites_missing" in payload["closure_blockers"]["persistent_supervision"]
    )
    assert "receipt_write_authority_not_granted" in payload["closure_blockers"]["persistent_supervision"]
    assert "resident_claim_authority_not_granted" in payload["closure_blockers"]["persistent_supervision"]
    if os.name == "nt":
        assert payload["closure_blockers"]["persistent_supervision_service_install_plan"] == [
            "install_authority_false",
            "installable_false",
            "service_control_authority_false",
            "service_install_authority_false",
        ]
    else:
        assert payload["closure_blockers"]["persistent_supervision_service_install_plan"] == []
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
        "persistent_supervision_required_prerequisites_missing"
        in payload["closure_blockers"]["persistent_supervision_resident_claim_boundary"]
    )
    assert (
        "process_supervision_disabled"
        not in payload["closure_blockers"]["persistent_supervision_resident_claim_boundary"]
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
    assert resident_runtime_boundary["local_process_launch_authority_required"] == "local_process_launch_authority"
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
    assert (
        persistent_enablement_authority["authority_required"]
        == "persistent_supervision_execution_authority_and_resident_claim_authority"
    )
    assert persistent_enablement_authority["authority_granted"] is False
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
    assert persistent_execution_authority["authority_required"] == "resident_claim_authority"
    assert persistent_execution_authority["authority_granted"] is False
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
    assert persistent_resident_claim_boundary["authority_required"] == "none_new_stage6_completion_audit"
    assert persistent_resident_claim_boundary["authority_granted"] is False
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
    assert "persistent_supervision_required_prerequisites_missing" in persistent_resident_claim_boundary["blockers"]
    assert "process_supervision_disabled" not in persistent_resident_claim_boundary["blockers"]
    assert "resident_claim_authority_not_granted" in persistent_resident_claim_boundary["blockers"]
    assert persistent_resident_claim_boundary["remaining_authority_families_after_this_boundary"] == []
    assert persistent_resident_claim_boundary["next_smallest_truthful_gap"] == "stage6_lens_completion_audit"

    transition_plan = payload["persistent_supervision_enablement_transition_plan_proof"]
    assert transition_plan["status"] == "proof_passed"
    assert transition_plan["ok"] is True
    assert transition_plan["exit_code"] == 0
    assert (
        "scripts/lens-persistent-supervision-enablement-transition-plan-proof.ps1 -Mode Status"
        in transition_plan["evidence"]
    )
    assert transition_plan["transition_plan_observed"] is True
    assert transition_plan["transition_plan_ready"] is False
    assert transition_plan["persistent_supervision_config_gate_enabled"] is True
    assert transition_plan["persistent_supervision_enablement_disabled"] is False
    assert transition_plan["persistent_supervision_prerequisites_proof_observed"] is True
    assert transition_plan["persistent_supervision_required_prerequisites_guard_observed"] is True
    assert transition_plan["persistent_supervision_service_install_plan_proof_observed"] is True
    assert transition_plan["persistent_supervision_resident_claim_boundary_observed"] is True
    assert transition_plan["persistent_supervision_plan_observed"] is True
    assert transition_plan["windows_service_supported"] is (os.name == "nt")
    assert transition_plan["service_install_plan_supported"] is (os.name == "nt")
    assert transition_plan["service_plan_status"] == ("blocked" if os.name == "nt" else "unsupported_platform")
    if os.name == "nt":
        assert set(transition_plan["service_plan_blocked_by"]) == {
            "installable_false",
            "install_authority_false",
            "service_install_authority_false",
            "service_control_authority_false",
        }
    else:
        assert transition_plan["service_plan_blocked_by"] == ["unsupported_platform"]
    assert transition_plan["required_before_enable"] == [
        "resident_host_process",
        "tray_presence",
        "global_hotkey_binding",
        "overlay_window",
        "summon_binding",
    ]
    assert transition_plan["enabled_config_toggles"] == [
        "process_supervision_enabled",
        "persistent_supervision_enabled",
    ]
    assert transition_plan["disabled_config_toggles"] == []
    transition_authority_chain = transition_plan["authority_chain"]
    assert transition_authority_chain["host_supervision_authority"] is True
    assert transition_authority_chain["persistent_supervision_enablement_authority"] is True
    assert transition_authority_chain["service_config_write_authority"] is True
    assert transition_authority_chain["persistent_supervision_execution_authority"] is True
    assert transition_authority_chain["receipt_write_authority"] is True
    assert transition_authority_chain["resident_claim_authority"] is False
    assert transition_authority_chain["final_authority_family_consumed"] is True
    assert transition_plan["side_effects_denied"] is True
    assert transition_plan["applied"] is False
    assert transition_plan["executed"] is False
    assert transition_plan["service_config_updated"] is False
    assert transition_plan["would_update_service_config"] is False
    assert transition_plan["would_enable_process_supervision"] is False
    assert transition_plan["would_enable_persistent_supervision"] is False
    assert transition_plan["would_install_service"] is False
    assert transition_plan["would_start_service"] is False
    assert transition_plan["would_supervise_process"] is False
    assert transition_plan["would_restart_process"] is False
    assert transition_plan["would_write_receipt"] is False
    assert transition_plan["would_write_memory"] is False
    assert transition_plan["would_claim_resident"] is False
    assert [item["id"] for item in transition_plan["transition_plan"]] == [
        "read_required_prerequisites",
        "verify_service_install_plan_boundary",
        "consume_persistent_supervision_authority_chain",
        "verify_required_prerequisite_guard",
        "keep_runtime_mutation_denied",
    ]
    assert all(item["passed"] for item in transition_plan["checks"])
    assert "persistent_supervision_required_prerequisites_missing" in transition_plan["blockers"]
    assert "process_supervision_disabled" not in transition_plan["blockers"]
    assert "resident_claim_authority_not_granted" in transition_plan["blockers"]
    assert transition_plan["next_smallest_truthful_gap"] == "persistent_supervision_required_prerequisites_missing"
    transition_governance = transition_plan["governance"]
    assert transition_governance["diagnostic_only"] is True
    assert transition_governance["read_only_transition_plan"] is True
    assert transition_governance["wraps_existing_prerequisite_proof"] is True
    assert transition_governance["wraps_existing_service_install_plan_proof"] is True
    assert transition_governance["wraps_existing_resident_claim_boundary_proof"] is True
    assert transition_governance["product_execution_authority"] is False
    assert transition_governance["execution_authority"] is False
    assert transition_governance["approval_decision_authority"] is False
    assert transition_governance["local_process_launch_authority"] is False
    assert transition_governance["process_supervision_authority"] is False
    assert transition_governance["process_restart_authority"] is False
    assert transition_governance["service_install_authority"] is False
    assert transition_governance["service_control_authority"] is False
    assert transition_governance["persistent_supervision_enablement_authority"] is False
    assert transition_governance["persistent_supervision_execution_authority"] is False
    assert transition_governance["service_config_write_authority"] is False
    assert transition_governance["receipt_write_authority"] is False
    assert transition_governance["memory_write"] is False
    assert transition_governance["resident_claim_authority"] is False
    assert transition_governance["mutation_authority_granted"] is False

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

    command_palette_shell_bridge = payload["command_palette_shell_bridge"]
    assert command_palette_shell_bridge["status"] == "blocked"
    assert command_palette_shell_bridge["ok"] is True
    assert command_palette_shell_bridge["exit_code"] == 0
    assert "scripts/lens-command-palette.ps1" in command_palette_shell_bridge["evidence"][0]
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
    assert "scripts/lens-command-palette-os-binding-proof.ps1" in command_palette_os_binding["evidence"][0]
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
    os_binding_groups = command_palette_os_binding["blocker_groups"]
    assert "os_level_command_palette_missing" in os_binding_groups["palette_binding"]
    assert "global_hotkey_binding_disabled" in os_binding_groups["global_hotkey_binding"]
    assert "global_hotkey_registration_disabled" in os_binding_groups["global_hotkey_binding"]
    assert "hotkey_registration_authority_not_granted" in os_binding_groups["global_hotkey_binding"]
    assert "lens_summon_binding_disabled_pending_authority" in os_binding_groups["summon_binding"]
    assert "summon_authority_not_granted" in os_binding_groups["summon_binding"]
    assert "tray_host_disabled" in os_binding_groups["tray_presence"]
    assert "tray_registration_authority_not_granted" in os_binding_groups["tray_presence"]
    assert "overlay_window_disabled" in os_binding_groups["overlay_window"]
    assert "overlay_control_authority_not_granted" in os_binding_groups["overlay_window"]
    assert "summon_authority_not_granted" in os_binding_groups["authority"]
    assert "local_process_launch_authority_not_granted" in os_binding_groups["authority"]
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
    assert "palette_binding" in os_binding_candidate["required_preflight_families"]
    assert "global_hotkey_binding" in os_binding_candidate["required_preflight_families"]
    assert "summon_binding" in os_binding_candidate["required_preflight_families"]
    assert "authority" in os_binding_candidate["required_preflight_families"]
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

    summon_anywhere_blockers_proof = payload["summon_anywhere_blockers_proof"]
    assert summon_anywhere_blockers_proof["status"] == "proof_passed"
    assert summon_anywhere_blockers_proof["ok"] is True
    assert summon_anywhere_blockers_proof["exit_code"] == 0
    assert "scripts/lens-summon-preflight.ps1 -Mode Status" in summon_anywhere_blockers_proof["evidence"]
    assert summon_anywhere_blockers_proof["acceptance_criterion"] == "summon_anywhere"
    assert summon_anywhere_blockers_proof["next_smallest_truthful_gap"] == "summon_anywhere_blockers"
    assert summon_anywhere_blockers_proof["summon_preflight_observed"] is True
    assert summon_anywhere_blockers_proof["stage6_family_projection_observed"] is True
    assert summon_anywhere_blockers_proof["side_effects_denied"] is True
    assert summon_anywhere_blockers_proof["os_binding_authority_request_readback_observed"] is True
    assert summon_anywhere_blockers_proof["first_blocker_family_handoff_observed"] is True
    assert summon_anywhere_blockers_proof["first_blocker_family"] == "resident_host"
    assert summon_anywhere_blockers_proof["first_blocker_family_handoff"] == expected_first_summon_handoff
    assert summon_anywhere_blockers_proof["blocked_families"] == expected_summon_family_ids
    assert [item["id"] for item in summon_anywhere_blockers_proof["blocked_family_handoffs"]] == (
        expected_summon_family_ids
    )
    summon_anywhere_groups = summon_anywhere_blockers_proof["blocker_groups"]
    assert "local_process_launch_authority_not_granted" in summon_anywhere_groups["resident_host"]
    assert "tray_host_missing" in summon_anywhere_groups["tray_presence"]
    assert "overlay_window_missing" in summon_anywhere_groups["overlay_window"]
    assert "global_hotkey_binding_disabled" in summon_anywhere_groups["global_hotkey_binding"]
    assert "global_hotkey_registration_disabled" in summon_anywhere_groups["global_hotkey_binding"]
    assert "hotkey_registration_authority_not_granted" in summon_anywhere_groups["global_hotkey_binding"]
    assert "lens_summon_binding_disabled_pending_authority" in summon_anywhere_groups["summon_binding"]
    assert "summon_authority_not_granted" in summon_anywhere_groups["summon_binding"]
    assert "summon_authority_not_granted" in summon_anywhere_groups["authority"]
    assert "hotkey_registration_authority_not_granted" in summon_anywhere_groups["authority"]
    assert "overlay_control_authority_not_granted" in summon_anywhere_groups["authority"]
    assert "local_process_launch_authority_not_granted" in summon_anywhere_groups["authority"]
    assert summon_anywhere_blockers_proof["lens_status_readback"]["ok"] is True
    assert summon_anywhere_blockers_proof["os_binding_authority_request_readback"]["ok"] is True
    assert summon_anywhere_blockers_proof["summon_preflight"]["global_hotkey"] == "Ctrl+Alt+Space"
    assert summon_anywhere_blockers_proof["governance"]["diagnostic_only"] is True
    assert summon_anywhere_blockers_proof["governance"]["wraps_summon_preflight"] is True
    assert summon_anywhere_blockers_proof["governance"]["wraps_lens_status"] is True
    assert summon_anywhere_blockers_proof["governance"]["read_only_contract"] is True
    assert summon_anywhere_blockers_proof["governance"]["os_binding_authority_request_readback"] is True
    assert summon_anywhere_blockers_proof["governance"]["first_blocker_family_handoff_readback"] is True
    assert summon_anywhere_blockers_proof["governance"]["approval_request_write"] is False
    assert summon_anywhere_blockers_proof["governance"]["product_execution_authority"] is False
    assert summon_anywhere_blockers_proof["governance"]["execution_authority"] is False
    assert summon_anywhere_blockers_proof["governance"]["approval_decision_authority"] is False
    assert summon_anywhere_blockers_proof["governance"]["memory_write"] is False
    assert summon_anywhere_blockers_proof["governance"]["overlay_control_authority"] is False
    assert summon_anywhere_blockers_proof["governance"]["summon_authority"] is False
    assert summon_anywhere_blockers_proof["governance"]["capture_authority"] is False
    assert summon_anywhere_blockers_proof["governance"]["new_sensing_authority"] is False
    assert summon_anywhere_blockers_proof["governance"]["local_process_launch_authority"] is False
    assert summon_anywhere_blockers_proof["governance"]["hotkey_registration_authority"] is False
    assert summon_anywhere_blockers_proof["governance"]["resident_claim_authority"] is False
    assert summon_anywhere_blockers_proof["governance"]["mutation_authority_granted"] is False

    summon_authority_blocker_proof = payload["summon_authority_blocker_proof"]
    assert summon_authority_blocker_proof["status"] == "proof_passed"
    assert summon_authority_blocker_proof["ok"] is True
    assert summon_authority_blocker_proof["exit_code"] == 0
    assert (
        "scripts/lens-summon-anywhere-blockers-proof.ps1 -Mode Status" in (summon_authority_blocker_proof["evidence"])
    )
    assert "scripts/lens-summon-binding-blocker-proof.ps1 -Mode Status" in (summon_authority_blocker_proof["evidence"])
    assert "scripts/lens-summon-preflight.ps1 -Mode Status" in summon_authority_blocker_proof["evidence"]
    assert summon_authority_blocker_proof["acceptance_criterion"] == "summon_anywhere"
    assert summon_authority_blocker_proof["previous_summon_blocker_family"] == "summon_binding"
    assert summon_authority_blocker_proof["summon_authority_blocker_family"] == "authority"
    assert summon_authority_blocker_proof["sixth_summon_blocker_family"] == "authority"
    assert summon_authority_blocker_proof["next_summon_blocker_family"] == "stage6_lens_completion_audit"
    assert summon_authority_blocker_proof["summon_next_smallest_truthful_gap"] == "summon_anywhere_blockers"
    assert summon_authority_blocker_proof["previous_binding_next_smallest_truthful_gap"] == (
        "summon_authority_blocker_boundary"
    )
    assert summon_authority_blocker_proof["direct_summon_preflight_next_smallest_truthful_gap"] == (
        "summon_anywhere_blockers"
    )
    assert summon_authority_blocker_proof["next_smallest_truthful_gap"] == "stage6_lens_completion_audit"
    assert summon_authority_blocker_proof["authority_required"] == "summon_hotkey_overlay_and_process_authority"
    assert summon_authority_blocker_proof["authority_granted"] is False
    assert summon_authority_blocker_proof["summon_authority_family_observed"] is True
    assert summon_authority_blocker_proof["previous_summon_binding_bridge_observed"] is True
    assert summon_authority_blocker_proof["summon_preflight_authority_observed"] is True
    assert summon_authority_blocker_proof["all_summon_blocker_families_consumed"] is True
    assert summon_authority_blocker_proof["handoff_aligned"] is True
    assert summon_authority_blocker_proof["side_effects_denied"] is True
    assert summon_authority_blocker_proof["summon_authority_blockers"] == [
        "summon_authority_not_granted",
        "hotkey_registration_authority_not_granted",
        "overlay_control_authority_not_granted",
        "local_process_launch_authority_not_granted",
    ]
    assert (
        summon_authority_blocker_proof["direct_summon_preflight_authority_blockers"]
        == summon_authority_blocker_proof["summon_authority_blockers"]
    )
    assert summon_authority_blocker_proof["direct_summon_preflight_binding_blockers"] == [
        "lens_summon_binding_disabled_pending_authority",
        "summon_authority_not_granted",
    ]

    summon_authority_boundary = summon_authority_blocker_proof["summon_authority_boundary"]
    assert summon_authority_boundary["status"] == "blocked"
    assert summon_authority_boundary["ready"] is False
    assert summon_authority_boundary["summon_name"] == "Francis Lens Summon"
    assert summon_authority_boundary["config_path"] == "config/runtime/lens/summon.json"
    assert summon_authority_boundary["global_hotkey"] == "Ctrl+Alt+Space"
    assert summon_authority_boundary["binding_scope"] == "global"
    assert summon_authority_boundary["palette_route"] == "/lens/status"
    assert summon_authority_boundary["required_before_enable"] == [
        "resident_host_process",
        "tray_presence",
        "overlay_window",
        "global_hotkey_binding",
        "summon_binding",
    ]
    assert summon_authority_boundary["binding_enabled"] is False
    assert summon_authority_boundary["register_hotkey"] is False
    assert summon_authority_boundary["startup_register"] is False
    assert "summon_authority_not_granted" in summon_authority_boundary["blockers"]
    assert "hotkey_registration_authority_not_granted" in summon_authority_boundary["blockers"]
    assert "overlay_control_authority_not_granted" in summon_authority_boundary["blockers"]
    assert "local_process_launch_authority_not_granted" in summon_authority_boundary["blockers"]
    assert (
        summon_authority_boundary["summon_binding_blockers"]
        == (summon_authority_blocker_proof["direct_summon_preflight_binding_blockers"])
    )
    assert (
        summon_authority_boundary["authority_blockers"]
        == (summon_authority_blocker_proof["direct_summon_preflight_authority_blockers"])
    )

    summon_authority_governance = summon_authority_blocker_proof["governance"]
    assert summon_authority_governance["diagnostic_only"] is True
    assert summon_authority_governance["wraps_summon_anywhere_blockers_proof"] is True
    assert summon_authority_governance["wraps_summon_binding_blocker_proof"] is True
    assert summon_authority_governance["wraps_summon_preflight"] is True
    assert summon_authority_governance["read_only_contract"] is True
    assert summon_authority_governance["approval_request_write"] is False
    assert summon_authority_governance["resident_runtime_execution_authority"] is False
    assert summon_authority_governance["product_execution_authority"] is False
    assert summon_authority_governance["execution_authority"] is False
    assert summon_authority_governance["approval_decision_authority"] is False
    assert summon_authority_governance["local_process_launch_authority"] is False
    assert summon_authority_governance["process_supervision_authority"] is False
    assert summon_authority_governance["process_restart_authority"] is False
    assert summon_authority_governance["service_install_authority"] is False
    assert summon_authority_governance["service_control_authority"] is False
    assert summon_authority_governance["tray_registration_authority"] is False
    assert summon_authority_governance["tray_icon_authority"] is False
    assert summon_authority_governance["notification_authority"] is False
    assert summon_authority_governance["hotkey_registration_authority"] is False
    assert summon_authority_governance["overlay_control_authority"] is False
    assert summon_authority_governance["window_management_authority"] is False
    assert summon_authority_governance["capture_authority"] is False
    assert summon_authority_governance["new_sensing_authority"] is False
    assert summon_authority_governance["summon_authority"] is False
    assert summon_authority_governance["memory_write"] is False
    assert summon_authority_governance["receipt_write_authority"] is False
    assert summon_authority_governance["resident_claim_authority"] is False
    assert summon_authority_governance["mutation_authority_granted"] is False

    summon_anywhere_family_chain_proof = payload["summon_anywhere_family_chain_proof"]
    assert summon_anywhere_family_chain_proof["status"] == "proof_passed"
    assert summon_anywhere_family_chain_proof["ok"] is True
    assert summon_anywhere_family_chain_proof["exit_code"] == 0
    assert (
        "scripts/lens-summon-anywhere-family-chain-proof.ps1 -Mode Status"
        in (summon_anywhere_family_chain_proof["evidence"])
    )
    assert summon_anywhere_family_chain_proof["acceptance_criterion"] == "summon_anywhere"
    assert summon_anywhere_family_chain_proof["summon_next_smallest_truthful_gap"] == "summon_anywhere_blockers"
    assert summon_anywhere_family_chain_proof["next_smallest_truthful_gap"] == "stage6_lens_completion_audit"
    assert summon_anywhere_family_chain_proof["authority_required"] == "summon_hotkey_overlay_and_process_authority"
    assert summon_anywhere_family_chain_proof["authority_granted"] is False
    assert summon_anywhere_family_chain_proof["family_chain_observed"] is True
    assert summon_anywhere_family_chain_proof["resident_host_family_handoff_observed"] is True
    assert summon_anywhere_family_chain_proof["final_summon_authority_handoff_observed"] is True
    assert summon_anywhere_family_chain_proof["all_summon_blocker_families_consumed"] is True
    assert summon_anywhere_family_chain_proof["handoff_aligned"] is True
    assert summon_anywhere_family_chain_proof["side_effects_denied"] is True
    assert summon_anywhere_family_chain_proof["child_proof_timeout_seconds"] == _AUDIT_CHILD_PROOF_TIMEOUT_SECONDS
    assert summon_anywhere_family_chain_proof["child_proof_timeouts"] == []
    family_child_proof_runs = {item["name"]: item for item in summon_anywhere_family_chain_proof["child_proof_runs"]}
    assert set(family_child_proof_runs) == {
        "summon_anywhere_blockers",
        "summon_resident_host_blocker",
        "summon_authority_blocker",
    }
    for run in family_child_proof_runs.values():
        assert run["timed_out"] is False
        assert run["timeout_seconds"] == _AUDIT_CHILD_PROOF_TIMEOUT_SECONDS
        assert isinstance(run["duration_ms"], int)
        assert run["duration_ms"] >= 0
    assert summon_anywhere_family_chain_proof["blocked_families"] == expected_summon_family_ids
    assert [item["id"] for item in summon_anywhere_family_chain_proof["blocked_family_handoffs"]] == (
        expected_summon_family_ids
    )
    assert summon_anywhere_family_chain_proof["first_blocker_family"] == "resident_host"
    assert summon_anywhere_family_chain_proof["first_blocker_family_handoff"] == expected_first_summon_handoff
    family_chain_resident_host = summon_anywhere_family_chain_proof["resident_host"]
    assert family_chain_resident_host["next_smallest_truthful_gap"] == "resident_host_runtime_blocker_boundary"
    assert (
        family_chain_resident_host["lifecycle_next_smallest_truthful_gap"] == "resident_host_runtime_blocker_boundary"
    )
    assert family_chain_resident_host["authority_required"] == "process_supervision_authority"
    assert family_chain_resident_host["authority_granted"] is False
    assert "lens_host_persistent_supervision_prerequisites_pending" in family_chain_resident_host["runtime_blockers"]
    assert "tray_host_missing" in family_chain_resident_host["surface_blockers"]
    assert "overlay_window_missing" in family_chain_resident_host["surface_blockers"]
    assert "global_hotkey_binding_missing" in family_chain_resident_host["surface_blockers"]
    assert "summon_binding_missing" in family_chain_resident_host["surface_blockers"]
    family_chain_final_authority = summon_anywhere_family_chain_proof["final_authority"]
    assert family_chain_final_authority["previous_summon_blocker_family"] == "summon_binding"
    assert family_chain_final_authority["summon_authority_blocker_family"] == "authority"
    assert family_chain_final_authority["next_summon_blocker_family"] == "stage6_lens_completion_audit"
    assert family_chain_final_authority["next_smallest_truthful_gap"] == "stage6_lens_completion_audit"
    assert family_chain_final_authority["authority_required"] == "summon_hotkey_overlay_and_process_authority"
    assert family_chain_final_authority["authority_granted"] is False
    assert family_chain_final_authority["all_summon_blocker_families_consumed"] is True
    assert "summon_authority_not_granted" in family_chain_final_authority["blockers"]
    family_chain_governance = summon_anywhere_family_chain_proof["governance"]
    assert family_chain_governance["diagnostic_only"] is True
    assert family_chain_governance["wraps_summon_anywhere_blockers_proof"] is True
    assert family_chain_governance["wraps_summon_resident_host_blocker_proof"] is True
    assert family_chain_governance["wraps_summon_authority_blocker_proof"] is True
    assert family_chain_governance["read_only_contract"] is True
    assert family_chain_governance["bounded_local_process_launch"] is False
    assert family_chain_governance["temporary_runtime_state_write"] is False
    assert family_chain_governance["product_execution_authority"] is False
    assert family_chain_governance["execution_authority"] is False
    assert family_chain_governance["approval_decision_authority"] is False
    assert family_chain_governance["local_process_launch_authority"] is False
    assert family_chain_governance["process_supervision_authority"] is False
    assert family_chain_governance["service_control_authority"] is False
    assert family_chain_governance["hotkey_registration_authority"] is False
    assert family_chain_governance["overlay_control_authority"] is False
    assert family_chain_governance["summon_authority"] is False
    assert family_chain_governance["memory_write"] is False
    assert family_chain_governance["receipt_write_authority"] is False
    assert family_chain_governance["resident_claim_authority"] is False
    assert family_chain_governance["mutation_authority_granted"] is False

    process_boundary = payload["process_supervision_authority_boundary_proof"]
    assert process_boundary["status"] == "proof_passed"
    assert process_boundary["ok"] is True
    assert process_boundary["stage6_checkpoint_observed"] is False
    assert process_boundary["resident_overlay_activation_boundary_observed"] is True
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

    runtime_boundary = payload["resident_host_runtime_boundary_proof"]
    assert runtime_boundary["status"] == "proof_passed"
    assert runtime_boundary["ok"] is True
    assert runtime_boundary["exit_code"] == 0
    assert runtime_boundary["previous_next_smallest_truthful_gap"] == "resident_host_runtime_blocker_boundary"
    assert runtime_boundary["next_smallest_truthful_gap"] == "resident_host_process_not_supervised"
    assert runtime_boundary["authority_required"] == "process_supervision_authority"
    assert runtime_boundary["authority_granted"] is False
    assert runtime_boundary["runtime_handoff_observed"] is True
    assert runtime_boundary["bounded_runtime_observed"] is True
    assert runtime_boundary["runtime_heartbeat_observed"] is True
    assert runtime_boundary["heartbeat_count"] >= 1
    assert runtime_boundary["runtime_boundary_blocked"] is True
    assert runtime_boundary["process_supervision_handoff_observed"] is True
    assert runtime_boundary["side_effects_bounded"] is True
    assert runtime_boundary["resident_host_process_state"] == "foreground_observed_not_supervised"
    assert runtime_boundary["resident_host_process_blocker"] == "resident_host_process_not_supervised"
    assert runtime_boundary["resident_runtime_ready"] is False
    assert runtime_boundary["supervision_ready"] is False
    assert runtime_boundary["ready_for_resident_claim"] is False
    assert runtime_boundary["resident_claim_allowed"] is False
    assert runtime_boundary["resident_host_supervised"] is False
    assert runtime_boundary["service_managed"] is False
    assert runtime_boundary["tray_presence"] is False
    assert runtime_boundary["global_hotkey"] is False
    assert runtime_boundary["overlay_window"] is False
    assert runtime_boundary["summon_anywhere"] is False
    assert "resident_host_runtime_blocker_boundary_consumed" in runtime_boundary["blockers"]
    assert "lens_host_persistent_supervision_prerequisites_pending" in runtime_boundary["blockers"]
    assert "resident_host_process_not_supervised" in runtime_boundary["blockers"]
    assert "process_supervision_authority_not_granted" in runtime_boundary["blockers"]
    assert "process_restart_authority_not_granted" in runtime_boundary["blockers"]
    assert "scripts/lens-resident-host-runtime-boundary-proof.ps1 -Mode Status" in runtime_boundary["evidence"]
    runtime_governance = runtime_boundary["governance"]
    assert runtime_governance["diagnostic_only"] is True
    assert runtime_governance["wraps_summon_resident_host_blocker_proof"] is True
    assert runtime_governance["wraps_host_supervision_proof"] is True
    assert runtime_governance["bounded_local_process_launch"] is True
    assert runtime_governance["temporary_runtime_state_write"] is True
    assert runtime_governance["product_execution_authority"] is False
    assert runtime_governance["execution_authority"] is False
    assert runtime_governance["approval_decision_authority"] is False
    assert runtime_governance["memory_write"] is False
    assert runtime_governance["api_local_process_launch_authority"] is False
    assert runtime_governance["process_supervision_authority"] is False
    assert runtime_governance["process_restart_authority"] is False
    assert runtime_governance["service_install_authority"] is False
    assert runtime_governance["service_control_authority"] is False
    assert runtime_governance["hotkey_registration_authority"] is False
    assert runtime_governance["tray_registration_authority"] is False
    assert runtime_governance["overlay_control_authority"] is False
    assert runtime_governance["summon_authority"] is False
    assert runtime_governance["resident_claim_authority"] is False
    assert runtime_governance["mutation_authority_granted"] is False

    process_handoff = payload["resident_host_process_supervision_blocker_proof"]
    assert process_handoff["status"] == "proof_passed"
    assert process_handoff["ok"] is True
    assert process_handoff["exit_code"] == 0
    assert process_handoff["previous_next_smallest_truthful_gap"] == "resident_host_process_not_supervised"
    assert process_handoff["next_smallest_truthful_gap"] == "stage6_lens_completion_audit"
    assert process_handoff["resident_host_process_handoff_observed"] is True
    assert process_handoff["process_supervision_boundary_observed"] is True
    assert process_handoff["handoff_consumed"] is True
    assert process_handoff["authority_denied"] is True
    assert process_handoff["authority_required"] == "none_new_stage6_completion_audit"
    assert process_handoff["authority_granted"] is False
    assert process_handoff["resident_host_process_state"] == "foreground_observed_not_supervised"
    assert process_handoff["resident_host_process_blocker"] == "resident_host_process_not_supervised"
    assert process_handoff["supervision_ready"] is False
    assert process_handoff["ready_for_resident_claim"] is False
    assert process_handoff["resident_claim_allowed"] is False
    assert process_handoff["resident_host_supervised"] is False
    assert process_handoff["service_installed"] is False
    assert process_handoff["service_managed"] is False
    assert process_handoff["process_supervision_ready"] is False
    assert process_handoff["service_activation_ready"] is False
    assert process_handoff["would_supervise_process"] is False
    assert process_handoff["would_restart_process"] is False
    assert process_handoff["would_install_service"] is False
    assert process_handoff["would_start_service"] is False
    assert process_handoff["would_write_memory"] is False
    assert process_handoff["would_decide_approval"] is False
    assert "resident_host_process_not_supervised" in process_handoff["blockers"]
    assert "process_supervision_authority_not_granted" in process_handoff["blockers"]
    assert "process_restart_authority_not_granted" in process_handoff["blockers"]
    assert "service_install_authority_not_granted" in process_handoff["blockers"]
    assert "service_control_authority_not_granted" in process_handoff["blockers"]
    assert (
        "scripts/lens-resident-host-process-supervision-blocker-proof.ps1 -Mode Status" in process_handoff["evidence"]
    )

    persistent_plan = payload["persistent_supervision_plan"]
    assert persistent_plan["status"] == "blocked"
    assert persistent_plan["ok"] is True
    assert persistent_plan["plan_available"] is True
    assert persistent_plan["persistent_supervision_ready"] is False
    assert persistent_plan["resident_claim_allowed"] is False
    assert persistent_plan["requirements_total"] >= 10
    assert persistent_plan["requirements_blocked_total"] >= 5
    assert "persistent_supervision_enabled" not in persistent_plan["blocked_requirements"]
    assert "receipt_write_authority" in persistent_plan["blocked_requirements"]
    assert "resident_claim_authority" in persistent_plan["blocked_requirements"]
    assert "persistent_supervision_required_prerequisites_missing" in persistent_plan["blockers"]
    assert "receipt_write_authority_not_granted" in persistent_plan["blockers"]
    assert persistent_plan["would_install_service"] is False
    assert persistent_plan["would_start_service"] is False
    assert persistent_plan["would_restart_process"] is False
    assert persistent_plan["would_supervise_process"] is False
    assert persistent_plan["would_write_receipt"] is False
    assert persistent_plan["would_write_memory"] is False
    assert persistent_plan["would_claim_resident"] is False
    assert "scripts/lens-persistent-supervision-plan.ps1 -Mode Status" in persistent_plan["evidence"]

    prerequisites_proof = payload["persistent_supervision_prerequisites_proof"]
    assert prerequisites_proof["status"] == "proof_passed"
    assert prerequisites_proof["ok"] is True
    assert prerequisites_proof["exit_code"] == 0
    assert prerequisites_proof["acceptance_criterion"] == "system_resident_presence"
    assert prerequisites_proof["plan_route"] == "/lens/host/persistent-supervision"
    assert prerequisites_proof["enablement_route"] == "/lens/host/persistent-supervision/enablement"
    assert prerequisites_proof["route_next_smallest_truthful_gap"] == "persistent_supervision_authority_not_granted"
    assert prerequisites_proof["guard_next_smallest_truthful_gap"] == (
        "persistent_supervision_required_prerequisites_missing"
    )
    assert prerequisites_proof["family_chain_next_smallest_truthful_gap"] == "stage6_lens_completion_audit"
    assert prerequisites_proof["next_smallest_truthful_gap"] == "persistent_supervision_required_prerequisites_missing"
    assert prerequisites_proof["authority_required"] == (
        "resident_host_process_tray_hotkey_overlay_and_summon_prerequisites"
    )
    assert prerequisites_proof["authority_granted"] is False
    assert prerequisites_proof["persistent_supervision_plan_readback_observed"] is True
    assert prerequisites_proof["persistent_supervision_enablement_readback_observed"] is True
    assert prerequisites_proof["required_before_enable_observed"] is True
    assert prerequisites_proof["missing_required_before_enable_observed"] is True
    assert prerequisites_proof["required_before_enable_guard_observed"] is True
    assert prerequisites_proof["dependency_readback_observed"] is True
    assert prerequisites_proof["family_chain_observed"] is True
    assert prerequisites_proof["prerequisites_mapped_to_family_chain"] is True
    assert prerequisites_proof["first_missing_requirement_proof_observed"] is True
    assert prerequisites_proof["first_missing_requirement_side_effects_bounded"] is True
    assert prerequisites_proof["lens_status_operator_readback_observed"] is True
    assert prerequisites_proof["side_effects_denied"] is True
    assert prerequisites_proof["side_effects_bounded"] is True
    expected_persistent_prerequisites = [
        "resident_host_process",
        "tray_presence",
        "global_hotkey_binding",
        "overlay_window",
        "summon_binding",
    ]
    assert prerequisites_proof["required_before_enable"] == expected_persistent_prerequisites
    assert prerequisites_proof["missing_required_before_enable"] == expected_persistent_prerequisites
    assert prerequisites_proof["first_missing_required_before_enable"] == "resident_host_process"
    assert prerequisites_proof["first_missing_requirement_handoff"] == first_missing_handoff
    assert prerequisites_proof["guard_readback"]["observed"] is True
    assert prerequisites_proof["guard_readback"]["blocked_requirements"] == ["required_before_enable"]
    assert prerequisites_proof["guard_readback"]["blockers"] == [
        "persistent_supervision_required_prerequisites_missing"
    ]
    prerequisite_dependency_readback = {item["id"]: item for item in prerequisites_proof["dependency_readback"]}
    assert set(prerequisite_dependency_readback) == set(expected_persistent_prerequisites)
    assert prerequisite_dependency_readback["resident_host_process"]["family"] == "resident_host"
    assert prerequisite_dependency_readback["tray_presence"]["route"] == "/lens/tray"
    assert prerequisite_dependency_readback["global_hotkey_binding"]["blocker"] == "global_hotkey_binding_missing"
    assert prerequisite_dependency_readback["overlay_window"]["blocker"] == "overlay_window_missing"
    assert prerequisite_dependency_readback["summon_binding"]["route"] == "/lens/summon"
    prerequisites_family_chain = prerequisites_proof["family_chain"]
    assert prerequisites_family_chain["status"] == "proof_passed"
    assert prerequisites_family_chain["timed_out"] is False
    assert prerequisites_family_chain["blocked_families"] == expected_summon_family_ids
    assert prerequisites_family_chain["handoff_count"] == 6
    assert prerequisites_family_chain["next_smallest_truthful_gap"] == "stage6_lens_completion_audit"
    assert prerequisites_family_chain["side_effects_denied"] is True
    prerequisites_first_missing_proof = prerequisites_proof["first_missing_requirement_proof"]
    assert prerequisites_first_missing_proof["status"] == "proof_passed"
    assert prerequisites_first_missing_proof["next_smallest_truthful_gap"] == "resident_host_process_not_supervised"
    assert prerequisites_first_missing_proof["resident_host_process_blocker"] == "resident_host_process_not_supervised"
    assert prerequisites_first_missing_proof["bounded_runtime_observed"] is True
    assert prerequisites_first_missing_proof["process_supervision_handoff_observed"] is True
    assert prerequisites_first_missing_proof["side_effects_bounded"] is True
    prerequisites_route_readback = prerequisites_proof["route_readback"]
    assert prerequisites_route_readback["status"] == "readback_ready"
    assert prerequisites_route_readback["plan_status"] == "blocked"
    assert prerequisites_route_readback["enablement_status"] == "blocked"
    assert all(item["passed"] for item in prerequisites_proof["checks"])
    prerequisites_governance = prerequisites_proof["governance"]
    assert prerequisites_governance["diagnostic_only"] is True
    assert prerequisites_governance["read_only_contract"] is False
    assert prerequisites_governance["route_readback_contract"] is True
    assert prerequisites_governance["wraps_persistent_supervision_plan_route"] is True
    assert prerequisites_governance["wraps_persistent_supervision_enablement_route"] is True
    assert prerequisites_governance["wraps_lens_status"] is True
    assert prerequisites_governance["wraps_summon_anywhere_family_chain_proof"] is True
    assert prerequisites_governance["wraps_first_missing_requirement_proof"] is True
    assert prerequisites_governance["bounded_local_process_launch"] is True
    assert prerequisites_governance["bounded_process_launch"] is True
    assert prerequisites_governance["temporary_runtime_state_write"] is True
    assert prerequisites_governance["execution_authority"] is False
    assert prerequisites_governance["approval_decision_authority"] is False
    assert prerequisites_governance["local_process_launch_authority"] is True
    assert prerequisites_governance["api_local_process_launch_authority"] is False
    assert prerequisites_governance["process_supervision_authority"] is False
    assert prerequisites_governance["service_config_write_authority"] is False
    assert prerequisites_governance["summon_authority"] is False
    assert prerequisites_governance["memory_write"] is False
    assert prerequisites_governance["resident_claim_authority"] is False
    assert prerequisites_governance["mutation_authority_granted"] is False

    service_install_plan = payload["persistent_supervision_service_install_plan_proof"]
    assert service_install_plan["status"] == "proof_passed"
    assert service_install_plan["ok"] is True
    assert service_install_plan["exit_code"] == 0
    assert (
        "scripts/lens-persistent-supervision-service-install-plan-proof.ps1 -Mode Status"
        in (service_install_plan["evidence"])
    )
    assert (
        "scripts/service-install.ps1 -Mode Plan -ConfigPath config/runtime/services/lens-host.json"
        in service_install_plan["evidence"]
    )
    assert service_install_plan["service_config"] == "config/runtime/services/lens-host.json"
    assert service_install_plan["service_install_script"] == "scripts/service-install.ps1"
    assert service_install_plan["windows_service_supported"] is (os.name == "nt")
    assert service_install_plan["service_install_plan_supported"] is (os.name == "nt")
    if os.name == "nt":
        assert service_install_plan["service_install_report"]
    else:
        assert service_install_plan["service_install_report"] == ""
    assert service_install_plan["service_name"] == "Francis-LensHost"
    expected_service_plan_status = "blocked" if os.name == "nt" else "unsupported_platform"
    assert service_install_plan["service_plan_status"] == expected_service_plan_status
    assert service_install_plan["service_plan_ready"] is False
    assert service_install_plan["service_plan_would_install"] is False
    assert service_install_plan["service_plan_would_start"] is False
    assert service_install_plan["process_supervision_enabled"] is True
    assert service_install_plan["persistent_supervision_enabled"] is True
    assert service_install_plan["persistent_supervision_config_gate_enabled"] is True
    assert service_install_plan["persistent_supervision_enablement_disabled"] is False
    assert service_install_plan["installable"] is False
    assert service_install_plan["install_authority"] is False
    assert service_install_plan["service_install_authority"] is False
    assert service_install_plan["service_control_authority"] is False
    assert service_install_plan["authority_required"] == "install_service_install_and_service_control_authority"
    assert service_install_plan["authority_granted"] is False
    assert service_install_plan["wrapper_created_by_proof"] is False
    assert service_install_plan["required_before_enable"] == expected_persistent_prerequisites
    if os.name == "nt":
        assert set(service_install_plan["blocked_by"]) == {
            "installable_false",
            "install_authority_false",
            "service_install_authority_false",
            "service_control_authority_false",
        }
    else:
        assert service_install_plan["blocked_by"] == ["unsupported_platform"]
    assert all(item["passed"] for item in service_install_plan["checks"])
    assert service_install_plan["next_smallest_truthful_gap"] == "persistent_supervision_required_prerequisites_missing"
    service_install_governance = service_install_plan["governance"]
    assert service_install_governance["diagnostic_only"] is True
    assert service_install_governance["read_only_contract"] is True
    assert service_install_governance["wraps_service_install_plan"] is (os.name == "nt")
    assert service_install_governance["windows_service_supported"] is (os.name == "nt")
    assert service_install_governance["service_install_plan_supported"] is (os.name == "nt")
    assert service_install_governance["service_config_readback"] is True
    assert service_install_governance["execution_authority"] is False
    assert service_install_governance["approval_decision_authority"] is False
    assert service_install_governance["local_process_launch_authority"] is False
    assert service_install_governance["process_supervision_authority"] is False
    assert service_install_governance["service_install_authority"] is False
    assert service_install_governance["service_control_authority"] is False
    assert service_install_governance["service_config_write_authority"] is False
    assert service_install_governance["memory_write"] is False
    assert service_install_governance["resident_claim_authority"] is False
    assert service_install_governance["mutation_authority_granted"] is False

    enablement_denial = payload["persistent_supervision_enablement_denial_boundary"]
    assert enablement_denial["status"] == "blocked"
    assert enablement_denial["ok"] is True
    assert "/lens/host/persistent-supervision/enablement" in enablement_denial["evidence"]
    assert enablement_denial["boundary_ready"] is True
    assert enablement_denial["applied"] is False
    assert enablement_denial["executed"] is False
    assert enablement_denial["authority_required"] == "persistent_supervision_enablement_authority"
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
    assert enablement_denial["service_config_write_authority_required"] == "service_config_write_authority"
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

    assert "docs/canonical/ROADMAP.md#4.12" in payload["evidence"]
    assert "scripts/lens-stage6-checkpoint.ps1 -Mode Status" in payload["evidence"]
    assert "scripts/lens-command-palette.ps1 -Mode Status -StatusPath <checkpoint-lens-status>" in payload["evidence"]
    assert "scripts/lens-resident-runtime-boundary-proof.ps1 -Mode Status" in payload["evidence"]
    assert "scripts/lens-resident-runtime-authority-blockers-proof.ps1 -Mode Status" in payload["evidence"]
    assert "scripts/lens-resident-runtime-resident-claim-boundary-proof.ps1 -Mode Status" in payload["evidence"]
    assert "scripts/lens-process-supervision-authority-boundary-proof.ps1 -Mode Status" in payload["evidence"]
    assert "scripts/lens-resident-host-process-supervision-blocker-proof.ps1 -Mode Status" in payload["evidence"]
    assert "scripts/lens-host-supervision-authority-request-proof.ps1 -Mode Status" in payload["evidence"]
    assert "scripts/lens-persistent-supervision-plan.ps1 -Mode Status" in payload["evidence"]
    assert "scripts/lens-persistent-supervision-prerequisites-proof.ps1 -Mode Status" in payload["evidence"]
    assert "scripts/lens-persistent-supervision-service-install-plan-proof.ps1 -Mode Status" in payload["evidence"]
    assert "scripts/lens-persistent-supervision-execution-authority-proof.ps1 -Mode Status" in payload["evidence"]
    assert "scripts/lens-persistent-supervision-resident-claim-boundary-proof.ps1 -Mode Status" in payload["evidence"]
    assert (
        "scripts/lens-persistent-supervision-enablement-transition-plan-proof.ps1 -Mode Status" in payload["evidence"]
    )
    assert (
        "scripts/lens-command-palette-os-binding-proof.ps1 -Mode Status -StatusPath <checkpoint-lens-status>"
        in (payload["evidence"])
    )
    assert "scripts/lens-summon-anywhere-blockers-proof.ps1 -Mode Status" in payload["evidence"]
    assert "scripts/lens-summon-authority-blocker-proof.ps1 -Mode Status" in payload["evidence"]
    assert "/lens/os-binding/authority/requests" in payload["evidence"]
    assert "/lens/os-binding/authority/request" in payload["evidence"]
    assert "/lens/host/persistent-supervision/enablement" in payload["evidence"]
    assert "/lens/host/persistent-supervision/enablement/execution" in payload["evidence"]
    assert "/lens/host/persistent-supervision/enablement/execution/readiness" in payload["evidence"]
    assert "/lens/resident-surface" in payload["evidence"]
    governance = payload["governance"]
    assert governance["read_only_contract"] is True
    assert governance["diagnostic_only"] is True
    assert governance["checkpoint_readback"] is True
    assert governance["child_proof_timeout_readback"] is True
    assert governance["process_supervision_authority_boundary_readback"] is True
    assert governance["resident_host_process_supervision_blocker_proof_readback"] is True
    assert governance["resident_host_process_handoff_consumed"] is True
    assert governance["resident_host_supervision_authority_readiness_handoff_readback"] is True
    assert governance["host_supervision_authority_request_proof_readback"] is True
    assert governance["helpful_not_noisy_runtime_authority_readiness_handoff_readback"] is True
    assert governance["persistent_supervision_plan_readback"] is True
    assert governance["persistent_supervision_prerequisites_proof_readback"] is True
    assert governance["persistent_supervision_service_install_plan_proof_readback"] is True
    assert governance["persistent_supervision_enablement_authority_proof_readback"] is True
    assert governance["persistent_supervision_execution_authority_proof_readback"] is True
    assert governance["persistent_supervision_resident_claim_boundary_proof_readback"] is True
    assert governance["persistent_supervision_enablement_transition_plan_proof_readback"] is True
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
    assert governance["command_palette_shell_bridge_readback"] is True
    assert governance["command_palette_os_binding_blockers_proof_readback"] is True
    assert governance["command_palette_os_binding_candidate_readback"] is True
    assert governance["os_binding_authority_request_readback"] is True
    assert governance["summon_anywhere_blockers_proof_readback"] is True
    assert governance["summon_anywhere_first_blocker_family_handoff_readback"] is True
    assert governance["resident_host_runtime_boundary_proof_readback"] is True
    assert governance["checkpoint_summon_enablement_gate_handoff_readback"] is True
    assert governance["summon_authority_blocker_proof_readback"] is True
    assert governance["summon_anywhere_family_chain_proof_readback"] is True
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
