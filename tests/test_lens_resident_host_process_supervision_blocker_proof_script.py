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
            str(_repo_root() / "scripts" / "lens-resident-host-process-supervision-blocker-proof.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
        timeout=420,
    )


def test_lens_resident_host_process_supervision_blocker_consumes_handoff() -> None:
    proc = _run_proof(
        "-Mode",
        "Status",
        "-StartupTimeoutSeconds",
        "20",
        "-ForegroundRunSeconds",
        "2",
        "-HostLaunchRunSeconds",
        "3",
        "-SupervisorRunSeconds",
        "20",
        "-ChildProofTimeoutSeconds",
        "180",
    )

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.resident_host.process_supervision_blocker.proof"
    assert payload["status"] == "proof_passed"
    assert payload["ok"] is True
    assert payload["stage"] == "Stage 6 / Lens MVP"
    assert payload["stage_state"] == "active"
    assert payload["acceptance_criterion"] == "summon_anywhere"
    assert payload["previous_next_smallest_truthful_gap"] == "resident_host_process_not_supervised"
    assert payload["next_smallest_truthful_gap"] == "stage6_lens_completion_audit"
    assert payload["recommended_handoff_source"] == "process_supervision_boundary_completion_audit_handoff"
    assert (
        payload["recommended_next_slice"]
        == "run_stage6_lens_completion_audit_after_process_supervision_handoff_readback"
    )
    assert payload["recommended_proof_script"] == ("scripts/lens-stage6-completion-audit.ps1 -Mode Status")
    assert payload["authority_required"] == "none_new_stage6_completion_audit"
    assert payload["authority_granted"] is False
    recommended_handoff = payload["recommended_handoff"]
    assert recommended_handoff["id"] == "stage6_lens_completion_audit"
    assert recommended_handoff["status"] == "audit_needed"
    assert recommended_handoff["previous_next_smallest_truthful_gap"] == ("resident_host_process_not_supervised")
    assert recommended_handoff["next_smallest_truthful_gap"] == "stage6_lens_completion_audit"
    assert recommended_handoff["next_step"] == (
        "run_stage6_lens_completion_audit_after_process_supervision_handoff_readback"
    )
    assert recommended_handoff["proof_script"] == ("scripts/lens-stage6-completion-audit.ps1 -Mode Status")
    assert recommended_handoff["route"] == "/lens/status"
    assert recommended_handoff["readiness_route"] == "/lens/status"
    assert recommended_handoff["acceptance_criterion"] == "summon_anywhere"
    assert recommended_handoff["blocker"] == "process_supervision_authority_not_granted"
    assert recommended_handoff["requirement_state"] == ("process_supervision_boundary_observed_without_authority")
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
    assert payload["resident_host_process_handoff_observed"] is True
    assert payload["process_supervision_boundary_observed"] is True
    assert payload["handoff_consumed"] is True
    assert payload["authority_denied"] is True
    assert payload["startup_timeout_seconds"] == 20
    assert payload["foreground_run_seconds"] == 2
    assert payload["host_launch_run_seconds"] == 3
    assert payload["supervisor_run_seconds"] == 20
    assert payload["child_proof_timeout_seconds"] == 180
    assert payload["child_proof_timeouts"] == []
    child_proof_runs = {item["name"]: item for item in payload["child_proof_runs"]}
    assert set(child_proof_runs) == {
        "resident_host_runtime_boundary",
        "process_supervision_boundary",
    }
    for run in child_proof_runs.values():
        assert run["timed_out"] is False
        assert run["timeout_seconds"] == 180
        assert isinstance(run["duration_ms"], int)
        assert run["duration_ms"] >= 0
    assert payload["resident_host_process_state"] == "foreground_observed_not_supervised"
    assert payload["resident_host_process_blocker"] == "resident_host_process_not_supervised"
    assert payload["supervision_ready"] is False
    assert payload["ready_for_resident_claim"] is False
    assert payload["resident_claim_allowed"] is False
    assert payload["resident_host_supervised"] is False
    assert payload["service_installed"] is False
    assert payload["service_managed"] is False
    assert payload["process_supervision_ready"] is False
    assert payload["service_activation_ready"] is False
    assert payload["would_supervise_process"] is False
    assert payload["would_restart_process"] is False
    assert payload["would_install_service"] is False
    assert payload["would_start_service"] is False
    assert payload["would_write_memory"] is False
    assert payload["would_decide_approval"] is False

    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["resident_host_process_handoff"]["status"] == "process_blocker_handoff_observed"
    assert checks["process_supervision_boundary"]["status"] == "process_supervision_blocked"
    assert checks["handoff_consumed"]["status"] == "blocker_consumed"
    assert checks["authority_denied"]["status"] == "diagnostic_bounded"
    assert all(item["passed"] for item in payload["checks"])

    assert "resident_host_process_not_supervised" in payload["blockers"]
    assert "process_supervision_authority_not_granted" in payload["blockers"]
    assert "process_restart_authority_not_granted" in payload["blockers"]
    assert "service_install_authority_not_granted" in payload["blockers"]
    assert "service_control_authority_not_granted" in payload["blockers"]

    proof = payload["proof"]
    assert proof["runtime_boundary_status"] == "proof_passed"
    assert proof["runtime_boundary_next_gap"] == "resident_host_process_not_supervised"
    assert proof["runtime_boundary_process_state"] == "foreground_observed_not_supervised"
    assert proof["process_boundary_status"] == "proof_passed"
    assert proof["process_boundary_next_gap"] == "stage6_lens_completion_audit"
    assert proof["process_boundary_authority_required"] == "process_supervision_and_service_control"
    assert proof["process_boundary_authority_granted"] is False
    assert proof["process_supervision_authority_required"] == "process_supervision_authority"
    assert proof["process_supervision_authority_granted"] is False
    assert proof["process_restart_authority_required"] == "process_restart_authority"
    assert proof["process_restart_authority_granted"] is False
    assert proof["service_install_authority_required"] == "service_install_authority"
    assert proof["service_install_authority_granted"] is False
    assert proof["service_control_authority_required"] == "service_control_authority"
    assert proof["service_control_authority_granted"] is False
    assert proof["process_boundary_observed"] is True
    assert proof["service_activation_plan_observed"] is True
    assert proof["bounded_local_process_launch_observed"] is True
    assert proof["process_supervision_ready"] is False
    assert proof["service_activation_ready"] is False

    assert payload["governance"] == {
        "diagnostic_only": True,
        "wraps_resident_host_runtime_boundary_proof": True,
        "wraps_process_supervision_authority_boundary_proof": True,
        "child_proof_timeout_seconds": 180,
        "bounded_local_process_launch": True,
        "temporary_runtime_state_write": True,
        "local_process_launch_authority": True,
        "api_local_process_launch_authority": False,
        "product_execution_authority": False,
        "execution_authority": False,
        "approval_decision_authority": False,
        "memory_write": False,
        "process_supervision_authority": False,
        "process_restart_authority": False,
        "service_install_authority": False,
        "service_control_authority": False,
        "hotkey_registration_authority": False,
        "tray_registration_authority": False,
        "overlay_control_authority": False,
        "summon_authority": False,
        "capture_authority": False,
        "new_sensing_authority": False,
        "receipt_write_authority": False,
        "resident_claim_authority": False,
        "mutation_authority_granted": False,
    }
