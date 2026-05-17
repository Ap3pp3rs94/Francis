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
            str(_repo_root() / "scripts" / "lens-process-supervision-authority-boundary-proof.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
    )


def test_lens_process_supervision_boundary_blocks_supervision_and_service_activation() -> None:
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
        "3",
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.process_supervision_authority_boundary.proof"
    assert payload["status"] == "proof_passed"
    assert payload["ok"] is True
    assert payload["mode"] == "status"
    assert payload["activation_boundary_mode"] == "direct_resident_surface_activation_boundary"
    assert payload["effective_resident_surface_foreground_run_seconds"] == 0
    assert payload["child_proof_timeout_seconds"] == 360
    assert payload["child_proof_timeouts"] == []
    assert payload["cached_host_supervision_proof"] is False
    child_proof_runs = {item["name"]: item for item in payload["child_proof_runs"]}
    assert set(child_proof_runs) == {"resident_surface_activation_boundary", "host_supervision"}
    for run in child_proof_runs.values():
        assert run["timed_out"] is False
        assert isinstance(run["duration_ms"], int)
        assert run["duration_ms"] >= 0
    assert child_proof_runs["resident_surface_activation_boundary"]["timeout_seconds"] == 60
    assert child_proof_runs["host_supervision"]["timeout_seconds"] == 360
    assert payload["authority_required"] == "process_supervision_and_service_control"
    assert payload["authority_granted"] is False
    assert payload["process_supervision_authority_required"] == "process_supervision_authority"
    assert payload["process_supervision_authority_granted"] is False
    assert payload["process_restart_authority_required"] == "process_restart_authority"
    assert payload["process_restart_authority_granted"] is False
    assert payload["service_install_authority_required"] == "service_install_authority"
    assert payload["service_install_authority_granted"] is False
    assert payload["service_control_authority_required"] == "service_control_authority"
    assert payload["service_control_authority_granted"] is False
    assert payload["stage6_checkpoint_observed"] is False
    assert payload["resident_surface_activation_boundary_observed"] is True
    assert payload["resident_overlay_activation_boundary_observed"] is True
    assert payload["host_supervision_boundary_observed"] is True
    assert payload["process_supervision_boundary_observed"] is True
    assert payload["service_activation_plan_observed"] is True
    assert payload["bounded_local_process_launch_observed"] is True
    assert payload["supervision_ready"] is False
    assert payload["ready_for_resident_claim"] is False
    assert payload["resident_claim_allowed"] is False
    assert payload["resident_host_process"] is False
    assert payload["resident_host_supervised"] is False
    assert payload["service_installed"] is False
    assert payload["service_managed"] is False
    assert payload["process_supervision_ready"] is False
    assert payload["service_activation_ready"] is False
    assert payload["tray_presence"] is False
    assert payload["global_hotkey_bound"] is False
    assert payload["overlay_window"] is False
    assert payload["summon_anywhere"] is False
    assert payload["would_supervise_process"] is False
    assert payload["would_restart_process"] is False
    assert payload["would_install_service"] is False
    assert payload["would_start_service"] is False
    assert payload["would_write_wrapper"] is False
    assert payload["would_write_memory"] is False
    assert payload["would_decide_approval"] is False

    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["resident_surface_activation_boundary"]["status"] == "activation_boundary_observed"
    assert checks["host_supervision_boundary"]["status"] == "supervision_blocked"
    assert checks["process_supervision_denied"]["status"] == "blocked"
    assert checks["service_activation_plan_blocked"]["status"] == "blocked_no_service_activation"
    assert checks["authority_boundary"]["status"] == "diagnostic_bounded"
    assert all(item["passed"] for item in payload["checks"])

    proof = payload["proof"]
    assert proof["checkpoint_status"] == "not_run"
    assert proof["checkpoint_stage_state"] == ""
    assert proof["checkpoint_system_resident_status"] == ""
    assert proof["checkpoint_next_smallest_truthful_gap"] == ""
    assert proof["activation_boundary_source"] == "direct_resident_surface_activation_boundary"
    assert proof["activation_boundary_status"] == "blocked"
    assert proof["activation_boundary_ok"] is True
    assert (
        proof["activation_boundary_next_smallest_truthful_gap"]
        == "approve_resident_runtime_execution_authority_grant_receipt"
    )
    assert proof["resident_surface_activation_boundary_observed"] is True
    assert proof["resident_overlay_boundary_observed"] is False
    assert proof["host_supervision_status"] == "proof_passed"
    assert proof["host_supervision_ready"] is False
    assert proof["host_ready_for_resident_claim"] is False
    assert proof["process_supervision_status"] == "enabled"
    assert proof["service_control_status"] == "blocked"
    assert proof["service_plan_status"] == "blocked"
    assert proof["service_plan_ready"] is False
    assert proof["service_plan_would_install"] is False
    assert proof["service_plan_would_start"] is False
    assert "installable_false" in proof["service_plan_blocked_by"]
    assert "service_install_authority_false" in proof["service_plan_blocked_by"]
    assert "service_control_authority_false" in proof["service_plan_blocked_by"]
    assert proof["service_status"] in {"not_installed", "unsupported_platform"}

    assert "process_supervision_authority_not_granted" in payload["blockers"]
    assert "process_restart_authority_not_granted" in payload["blockers"]
    assert "service_install_authority_not_granted" in payload["blockers"]
    assert "service_control_authority_not_granted" in payload["blockers"]
    assert "resident_host_process_not_supervised" in payload["blockers"]
    assert "resident_supervision_disabled" in payload["blockers"]
    assert "resident_runtime_execution_authority_not_granted" in payload["blockers"]
    assert "local_process_launch_authority_not_granted" in payload["blockers"]
    assert "operator_experience_proof_missing" not in payload["blockers"]
    assert "live_operator_experience_proof_missing" not in payload["blockers"]
    assert payload["next_smallest_truthful_gap"] == "stage6_lens_completion_audit"

    governance = payload["governance"]
    assert governance["diagnostic_only"] is True
    assert governance["checkpoint_readback"] is False
    assert governance["resident_surface_activation_boundary_readback"] is True
    assert governance["resident_overlay_activation_boundary_readback"] is True
    assert governance["cached_host_supervision_proof"] is False
    assert governance["live_http_readback"] is False
    assert governance["temporary_api_process"] is False
    assert governance["bounded_host_launch"] is True
    assert governance["bounded_process_launch"] is True
    assert governance["bounded_supervisor_observation"] is True
    assert governance["resident_surface_activation_boundary_observed"] is True
    assert governance["resident_overlay_activation_boundary_observed"] is True
    assert governance["resident_host_supervision_authority_denial_boundary_observed"] is False
    assert governance["resident_host_supervision_authority_denial_receipt_readback_observed"] is False
    assert governance["resident_host_supervision_authority_grant_receipt_readback_observed"] is False
    assert governance["resident_host_supervision_authority_readiness_audit_observed"] is False
    assert governance["temporary_runtime_state_write"] is True
    assert governance["local_process_launch_authority"] is True
    for denied_authority in (
        "product_execution_authority",
        "execution_authority",
        "approval_decision_authority",
        "memory_write",
        "resident_overlay_activation_authority",
        "process_restart_authority",
        "process_supervision_authority",
        "service_install_authority",
        "service_control_authority",
        "overlay_control_authority",
        "summon_authority",
        "capture_authority",
        "new_sensing_authority",
        "api_local_process_launch_authority",
        "activation_local_process_launch_authority",
        "hotkey_registration_authority",
        "tray_registration_authority",
        "tray_icon_authority",
        "receipt_write_authority",
        "denial_receipt_write_authority",
        "mutation_authority_granted",
    ):
        assert governance[denied_authority] is False
