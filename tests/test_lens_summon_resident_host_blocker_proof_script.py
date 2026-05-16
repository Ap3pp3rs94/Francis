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
            str(_repo_root() / "scripts" / "lens-summon-resident-host-blocker-proof.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
    )


def test_lens_summon_resident_host_blocker_proof_aligns_handoff(tmp_path: Path) -> None:
    proc = _run_proof(
        "-Mode",
        "Status",
        "-DataDir",
        str(tmp_path / "data"),
        "-ConsumeProcessSupervisionHandoff",
        "-StartupTimeoutSeconds",
        "20",
        "-ForegroundRunSeconds",
        "2",
        "-HostLaunchRunSeconds",
        "3",
        "-SupervisorRunSeconds",
        "3",
    )

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.summon_resident_host_blocker.proof"
    assert payload["status"] == "proof_passed"
    assert payload["ok"] is True
    assert payload["stage"] == "Stage 6 / Lens MVP"
    assert payload["stage_state"] == "active"
    assert payload["acceptance_criterion"] == "summon_anywhere"
    assert payload["service_plan_runtime_mode"] == "Resident"
    assert payload["resident_runtime_candidate_available"] is True
    assert payload["resident_runtime_candidate_supervised"] is False
    assert payload["resident_candidate_supervision_gap"] == "resident_candidate_not_supervised"
    assert payload["resident_runtime_candidate_script"] == "scripts/lens-host.ps1 -Mode Resident"
    assert payload["first_summon_blocker_family"] == "resident_host"
    assert payload["summon_next_smallest_truthful_gap"] == "summon_anywhere_blockers"
    assert payload["summon_os_binding_authority_request_readback_observed"] is True
    assert payload["resident_host_lifecycle_next_smallest_truthful_gap"] == "resident_host_runtime_blocker_boundary"
    assert payload["resident_host_process_supervision_next_smallest_truthful_gap"] == "stage6_lens_completion_audit"
    assert payload["resident_host_next_smallest_truthful_gap"] == "stage6_lens_completion_audit"
    assert payload["next_smallest_truthful_gap"] == "stage6_lens_completion_audit"
    assert payload["authority_required"] == "none_new_stage6_completion_audit"
    assert payload["authority_granted"] is False
    assert payload["summon_first_family_observed"] is True
    assert payload["resident_host_lifecycle_observed"] is True
    assert payload["consume_process_supervision_handoff"] is True
    assert payload["resident_host_process_supervision_handoff_observed"] is True
    assert payload["handoff_aligned"] is True
    assert payload["side_effects_denied"] is True

    authority_readback = payload["summon_os_binding_authority_request_readback"]
    assert authority_readback["status"] == "none"
    assert authority_readback["ok"] is True
    assert authority_readback["kind"] == "lens.os_binding.command_palette_binding_authority.request_readback"
    assert authority_readback["route"] == "/lens/os-binding/authority/requests"
    assert authority_readback["request_route"] == "/lens/os-binding/authority/request"
    assert authority_readback["readiness_route"] == "/lens/os-binding/readiness"
    assert authority_readback["plan_route"] == "/lens/os-binding/plan"
    assert authority_readback["stage6_criterion_readback_ready"] is True
    assert authority_readback["authority_granted"] is False
    assert authority_readback["os_level_command_palette_binding_authority"] is False
    assert authority_readback["os_level_command_palette"] is False
    assert authority_readback["summon_anywhere"] is False
    assert authority_readback["opens_palette"] is False
    assert authority_readback["registers_hotkey"] is False
    assert authority_readback["launches_process"] is False
    assert authority_readback["controls_overlay"] is False
    assert authority_readback["governance"]["read_only_contract"] is True
    assert authority_readback["governance"]["approval_request_write"] is False
    assert authority_readback["governance"]["execution_authority"] is False
    assert authority_readback["governance"]["approval_decision_authority"] is False
    assert authority_readback["governance"]["memory_write"] is False
    assert authority_readback["governance"]["resident_claim_authority"] is False

    assert payload["summon_resident_host_blockers"] == ["local_process_launch_authority_not_granted"]
    assert payload["resident_host_runtime_blockers"] == ["lens_host_persistent_supervision_prerequisites_pending"]
    assert isinstance(payload["resident_host_process_readback_blockers"], list)
    assert "resident_host_process_not_supervised" in payload["resident_host_process_supervision_blockers"]
    assert "process_supervision_authority_not_granted" in payload["resident_host_process_supervision_blockers"]
    assert "process_restart_authority_not_granted" in payload["resident_host_process_supervision_blockers"]
    candidate_handoff = payload["resident_runtime_candidate_handoff"]
    assert candidate_handoff["status"] == "available_not_supervised"
    assert candidate_handoff["service_config"] == "config/runtime/services/lens-host.json"
    assert candidate_handoff["service_name"] == "Francis-LensHost"
    assert candidate_handoff["service_plan_runtime_mode"] == "Resident"
    assert candidate_handoff["runtime_state_path"] == "data/runtime/lens-host/status.json"
    assert candidate_handoff["host_script"] == "scripts/lens-host.ps1 -Mode Resident"
    assert candidate_handoff["resident_runtime_candidate_available"] is True
    assert candidate_handoff["resident_runtime_candidate_supervised"] is False
    assert candidate_handoff["process_supervision_enabled"] is True
    assert candidate_handoff["service_control_authority"] is False
    assert candidate_handoff["service_install_authority"] is False
    assert candidate_handoff["resident_claim_authority"] is False
    assert candidate_handoff["authority_granted"] is False
    assert candidate_handoff["next_smallest_truthful_gap"] == "resident_host_process_not_supervised"
    process_handoff = payload["resident_host_process_supervision_handoff"]
    assert process_handoff["status"] == "proof_passed"
    assert process_handoff["previous_next_smallest_truthful_gap"] == "resident_host_process_not_supervised"
    assert process_handoff["next_smallest_truthful_gap"] == "stage6_lens_completion_audit"
    assert process_handoff["authority_required"] == "none_new_stage6_completion_audit"
    assert process_handoff["authority_granted"] is False
    assert process_handoff["resident_host_process_handoff_observed"] is True
    assert process_handoff["process_supervision_boundary_observed"] is True
    assert process_handoff["handoff_consumed"] is True
    assert process_handoff["authority_denied"] is True
    assert process_handoff["resident_host_process_state"] == "foreground_observed_not_supervised"
    assert process_handoff["resident_host_process_blocker"] == "resident_host_process_not_supervised"
    recommended_handoff = process_handoff["recommended_handoff"]
    assert recommended_handoff["id"] == "stage6_lens_completion_audit"
    assert recommended_handoff["status"] == "audit_needed"
    assert recommended_handoff["previous_next_smallest_truthful_gap"] == "resident_host_process_not_supervised"
    assert recommended_handoff["next_smallest_truthful_gap"] == "stage6_lens_completion_audit"
    assert recommended_handoff["proof_script"] == "scripts/lens-stage6-completion-audit.ps1 -Mode Status"
    assert recommended_handoff["route"] == "/lens/status"
    assert recommended_handoff["readiness_route"] == "/lens/status"
    assert recommended_handoff["acceptance_criterion"] == "summon_anywhere"
    assert recommended_handoff["blocker"] == "process_supervision_authority_not_granted"
    assert recommended_handoff["requirement_state"] == "process_supervision_boundary_observed_without_authority"
    assert recommended_handoff["authority_required"] == "none_new_stage6_completion_audit"
    assert recommended_handoff["authority_granted"] is False
    assert recommended_handoff["read_only_contract"] is True
    assert recommended_handoff["diagnostic_only"] is True
    assert recommended_handoff["would_execute"] is False
    assert recommended_handoff["would_mutate"] is False
    assert recommended_handoff["would_supervise_process"] is False
    assert recommended_handoff["would_restart_process"] is False
    assert recommended_handoff["would_install_service"] is False
    assert recommended_handoff["would_start_service"] is False
    assert recommended_handoff["would_claim_resident"] is False
    assert payload["resident_host_surface_blockers"] == [
        "tray_host_missing",
        "global_hotkey_binding_missing",
        "overlay_window_missing",
        "summon_binding_missing",
    ]

    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["summon_first_family"]["status"] == "resident_host_first"
    assert checks["summon_os_binding_authority_readback"]["status"] == "authority_readback_consumed"
    assert checks["resident_candidate_service_plan"]["status"] == "resident_candidate_planned_service_denied"
    assert checks["resident_host_lifecycle_proof"]["status"] == "runtime_blocked"
    assert checks["resident_host_process_supervision_handoff"]["status"] == "process_handoff_consumed"
    assert checks["handoff_alignment"]["status"] == "handoff_aligned"
    assert checks["side_effects_denied"]["status"] == "diagnostic_bounded"
    assert all(item["passed"] for item in payload["checks"])

    assert "scripts/lens-summon-anywhere-blockers-proof.ps1 -Mode Status" in payload["evidence"]
    assert "scripts/lens-resident-host-lifecycle-blockers-proof.ps1 -Mode Status" in payload["evidence"]
    assert "scripts/lens-resident-host-process-supervision-blocker-proof.ps1 -Mode Status" in payload["evidence"]

    assert payload["governance"] == {
        "diagnostic_only": True,
        "wraps_summon_anywhere_blockers_proof": True,
        "summon_os_binding_authority_request_readback": True,
        "wraps_resident_host_lifecycle_blockers_proof": True,
        "wraps_resident_host_process_supervision_blocker_proof": True,
        "read_only_contract": True,
        "resident_runtime_candidate_available": True,
        "resident_runtime_candidate_supervised": False,
        "resident_runtime_candidate_process_supervision_enabled": True,
        "resident_candidate_service_control_authority": False,
        "resident_candidate_service_install_authority": False,
        "resident_candidate_supervision_authority": False,
        "bounded_local_process_launch": True,
        "temporary_runtime_state_write": True,
        "api_local_process_launch_authority": False,
        "product_execution_authority": False,
        "execution_authority": False,
        "approval_decision_authority": False,
        "memory_write": False,
        "local_process_launch_authority": False,
        "process_supervision_authority": False,
        "process_restart_authority": False,
        "service_install_authority": False,
        "service_control_authority": False,
        "hotkey_registration_authority": False,
        "overlay_control_authority": False,
        "summon_authority": False,
        "capture_authority": False,
        "new_sensing_authority": False,
        "receipt_write_authority": False,
        "resident_claim_authority": False,
        "mutation_authority_granted": False,
    }


def test_lens_summon_resident_host_default_proof_keeps_checkpoint_safe_handoff() -> None:
    proc = _run_proof("-Mode", "Status")

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["status"] == "proof_passed"
    assert payload["service_plan_runtime_mode"] == "Resident"
    assert payload["resident_runtime_candidate_available"] is True
    assert payload["resident_runtime_candidate_supervised"] is False
    assert payload["resident_candidate_supervision_gap"] == "resident_candidate_not_supervised"
    assert payload["consume_process_supervision_handoff"] is False
    assert payload["resident_host_process_supervision_handoff_observed"] is False
    assert payload["resident_host_process_supervision_next_smallest_truthful_gap"] == ""
    assert payload["resident_host_next_smallest_truthful_gap"] == "resident_host_runtime_blocker_boundary"
    assert payload["next_smallest_truthful_gap"] == "resident_host_runtime_blocker_boundary"
    assert payload["authority_required"] == "process_supervision_authority"
    assert payload["authority_granted"] is False
    assert payload["handoff_aligned"] is True
    assert payload["side_effects_denied"] is True
    assert payload["summon_os_binding_authority_request_readback_observed"] is True

    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["summon_os_binding_authority_readback"]["status"] == "authority_readback_consumed"
    assert checks["resident_candidate_service_plan"]["status"] == "resident_candidate_planned_service_denied"
    assert "resident_host_process_supervision_handoff" not in checks
    assert "scripts/lens-resident-host-process-supervision-blocker-proof.ps1 -Mode Status" not in payload["evidence"]
    assert payload["governance"]["summon_os_binding_authority_request_readback"] is True
    assert payload["governance"]["wraps_resident_host_process_supervision_blocker_proof"] is False
    assert payload["governance"]["resident_runtime_candidate_available"] is True
    assert payload["governance"]["resident_runtime_candidate_supervised"] is False
    assert payload["governance"]["resident_runtime_candidate_process_supervision_enabled"] is True
    assert payload["governance"]["bounded_local_process_launch"] is False
    assert payload["governance"]["temporary_runtime_state_write"] is False
