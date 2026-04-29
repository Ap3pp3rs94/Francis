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
        "4",
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.process_supervision_authority_boundary.proof"
    assert payload["status"] == "proof_passed"
    assert payload["ok"] is True
    assert payload["mode"] == "status"
    assert payload["stage6_checkpoint_observed"] is True
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
    assert checks["stage6_checkpoint_activation_boundary"]["status"] == "activation_boundary_checkpointed"
    assert checks["host_supervision_boundary"]["status"] == "supervision_blocked"
    assert checks["process_supervision_denied"]["status"] == "blocked"
    assert checks["service_activation_plan_blocked"]["status"] == "blocked_no_service_activation"
    assert checks["authority_boundary"]["status"] == "diagnostic_bounded"
    assert all(item["passed"] for item in payload["checks"])

    proof = payload["proof"]
    assert proof["checkpoint_status"] == "blocked"
    assert proof["checkpoint_stage_state"] == "active"
    assert proof["checkpoint_system_resident_status"] == "resident_overlay_activation_boundary_observed"
    assert proof["checkpoint_next_smallest_truthful_gap"] == ("resident_host_supervision_authority_readiness_audit")
    assert proof["activation_boundary_status"] == "proof_passed"
    assert proof["activation_boundary_ok"] is True
    assert proof["host_supervision_status"] == "proof_passed"
    assert proof["host_supervision_ready"] is False
    assert proof["host_ready_for_resident_claim"] is False
    assert proof["process_supervision_status"] == "blocked"
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
    assert "resident_overlay_activation_not_authorized" in payload["blockers"]
    assert "operator_experience_proof_missing" not in payload["blockers"]
    assert "live_operator_experience_proof_missing" not in payload["blockers"]
    assert payload["next_smallest_truthful_gap"] == "resident_host_supervision_authority_readiness_audit"

    assert payload["governance"] == {
        "diagnostic_only": True,
        "checkpoint_readback": True,
        "live_http_readback": True,
        "temporary_api_process": True,
        "bounded_host_launch": True,
        "bounded_process_launch": True,
        "bounded_supervisor_observation": True,
        "resident_overlay_activation_boundary_observed": True,
        "resident_host_supervision_authority_denial_boundary_observed": True,
        "resident_host_supervision_authority_denial_receipt_readback_observed": True,
        "temporary_runtime_state_write": True,
        "product_execution_authority": False,
        "execution_authority": False,
        "approval_decision_authority": False,
        "memory_write": False,
        "resident_overlay_activation_authority": False,
        "process_restart_authority": False,
        "process_supervision_authority": False,
        "service_install_authority": False,
        "service_control_authority": False,
        "overlay_control_authority": False,
        "summon_authority": False,
        "capture_authority": False,
        "new_sensing_authority": False,
        "local_process_launch_authority": True,
        "api_local_process_launch_authority": False,
        "activation_local_process_launch_authority": False,
        "hotkey_registration_authority": False,
        "tray_registration_authority": False,
        "tray_icon_authority": False,
        "receipt_write_authority": False,
        "denial_receipt_write_authority": False,
        "mutation_authority_granted": False,
    }
