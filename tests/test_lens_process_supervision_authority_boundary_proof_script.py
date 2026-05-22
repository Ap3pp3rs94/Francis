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


def _write_cached_resident_surface_proof(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "kind": "lens.resident_surface.readiness_proof",
                "status": "proof_passed",
                "ok": True,
                "resident_surface_content_readback": True,
                "resident_surface_foreground_runtime_readback": True,
                "resident_surface_foreground_runtime_observed": True,
                "resident_surface_runtime_status": "foreground_runtime_observed",
                "foreground_host_process_observed": True,
                "foreground_host_runtime_completed": True,
                "resident_surface_ready": False,
                "resident_claim_allowed": False,
                "resident_host_process": False,
                "next_smallest_truthful_gap": "resident_surface_runtime_not_supervised",
                "blockers": [
                    "resident_surface_runtime_not_supervised",
                    "resident_surface_not_resident",
                ],
                "recommended_handoff_source": "resident_surface_runtime_supervision_handoff",
                "recommended_next_slice": (
                    "resolve_resident_surface_runtime_supervision_before_helpful_not_noisy_claim"
                ),
                "recommended_proof_script": "scripts/lens-resident-surface-proof.ps1 -Mode Status",
                "authority_required": "process_supervision_authority",
                "authority_granted": False,
                "recommended_handoff": {
                    "id": "resident_surface_runtime_supervision",
                    "next_smallest_truthful_gap": "resident_surface_runtime_not_supervised",
                    "readiness_route": "/lens/resident-runtime/authority-grant/readiness",
                    "authority_required": "process_supervision_authority",
                    "authority_granted": False,
                    "read_only_contract": True,
                    "diagnostic_only": True,
                    "would_execute": False,
                    "would_mutate": False,
                    "would_supervise_process": False,
                    "would_restart_process": False,
                    "would_claim_resident": False,
                },
                "proof": {
                    "resident_surface_foreground_runtime_blockers": [
                        "resident_surface_runtime_not_supervised",
                        "resident_surface_not_resident",
                    ],
                },
            }
        ),
        encoding="utf-8",
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
        "-ResidentSurfaceForegroundRunSeconds",
        "3",
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.process_supervision_authority_boundary.proof"
    assert payload["status"] == "proof_passed"
    assert payload["ok"] is True
    assert payload["mode"] == "status"
    assert payload["activation_boundary_mode"] == "direct_resident_surface_activation_boundary"
    assert payload["effective_resident_surface_foreground_run_seconds"] == 3
    assert payload["child_proof_timeout_seconds"] == 360
    assert payload["child_proof_timeouts"] == []
    assert payload["cached_resident_surface_proof"] is False
    assert payload["cached_host_supervision_proof"] is False
    child_proof_runs = {item["name"]: item for item in payload["child_proof_runs"]}
    assert set(child_proof_runs) == {
        "resident_surface_activation_boundary",
        "resident_surface_foreground_runtime",
        "host_supervision",
    }
    for run in child_proof_runs.values():
        assert run["timed_out"] is False
        assert isinstance(run["duration_ms"], int)
        assert run["duration_ms"] >= 0
    assert child_proof_runs["resident_surface_activation_boundary"]["timeout_seconds"] == 60
    assert child_proof_runs["resident_surface_foreground_runtime"]["timeout_seconds"] == 360
    assert child_proof_runs["host_supervision"]["timeout_seconds"] == 360
    assert payload["authority_required"] == "process_supervision_and_service_control"
    assert payload["authority_granted"] is False
    assert payload["resident_surface_foreground_runtime_proof_observed"] is True
    assert payload["resident_surface_runtime_supervision_handoff_observed"] is True
    assert payload["resident_surface_next_smallest_truthful_gap"] == "resident_surface_runtime_not_supervised"
    assert payload["resident_surface_authority_required"] == "process_supervision_authority"
    assert payload["resident_surface_authority_granted"] is False
    assert payload["resident_surface_recommended_handoff_source"] == "resident_surface_runtime_supervision_handoff"
    assert payload["resident_surface_recommended_next_slice"] == (
        "resolve_resident_surface_runtime_supervision_before_helpful_not_noisy_claim"
    )
    assert payload["resident_surface_recommended_proof_script"] == (
        "scripts/lens-resident-surface-proof.ps1 -Mode Status"
    )
    assert payload["recommended_handoff_source"] == "resident_surface_runtime_supervision_handoff"
    assert payload["recommended_next_slice"] == (
        "resolve_resident_surface_runtime_supervision_before_helpful_not_noisy_claim"
    )
    assert payload["recommended_proof_script"] == "scripts/lens-resident-surface-proof.ps1 -Mode Status"
    resident_surface_handoff = payload["resident_surface_runtime_supervision_handoff"]
    assert payload["recommended_handoff"] == resident_surface_handoff
    assert resident_surface_handoff["id"] == "resident_surface_runtime_supervision"
    assert resident_surface_handoff["next_smallest_truthful_gap"] == "resident_surface_runtime_not_supervised"
    assert resident_surface_handoff["readiness_route"] == "/lens/resident-runtime/authority-grant/readiness"
    assert resident_surface_handoff["authority_required"] == "process_supervision_authority"
    assert resident_surface_handoff["authority_granted"] is False
    assert resident_surface_handoff["read_only_contract"] is True
    assert resident_surface_handoff["diagnostic_only"] is True
    assert resident_surface_handoff["would_execute"] is False
    assert resident_surface_handoff["would_mutate"] is False
    assert resident_surface_handoff["would_supervise_process"] is False
    assert resident_surface_handoff["would_restart_process"] is False
    assert resident_surface_handoff["would_claim_resident"] is False
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
    assert checks["resident_surface_foreground_runtime_proof"]["status"] == "foreground_runtime_observed"
    assert checks["resident_surface_runtime_supervision_handoff"]["status"] == "handoff_observed"
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
    assert proof["resident_surface_foreground_runtime_proof_status"] == "proof_passed"
    assert proof["resident_surface_foreground_runtime_proof_observed"] is True
    assert proof["resident_surface_runtime_supervision_handoff_observed"] is True
    assert proof["resident_surface_next_smallest_truthful_gap"] == "resident_surface_runtime_not_supervised"
    assert proof["resident_surface_authority_required"] == "process_supervision_authority"
    assert proof["resident_surface_runtime_status"] == "foreground_runtime_observed"
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
    assert governance["cached_resident_surface_proof"] is False
    assert governance["cached_host_supervision_proof"] is False
    assert governance["live_http_readback"] is False
    assert governance["temporary_api_process"] is False
    assert governance["bounded_host_launch"] is True
    assert governance["bounded_process_launch"] is True
    assert governance["bounded_supervisor_observation"] is True
    assert governance["resident_surface_activation_boundary_observed"] is True
    assert governance["resident_overlay_activation_boundary_observed"] is True
    assert governance["resident_surface_foreground_runtime_readback"] is True
    assert governance["resident_surface_runtime_supervision_handoff_readback"] is True
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


def test_lens_process_supervision_boundary_consumes_cached_resident_surface_proof(tmp_path: Path) -> None:
    cached_resident_surface = tmp_path / "resident-surface-proof.json"
    _write_cached_resident_surface_proof(cached_resident_surface)

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
        "-CachedResidentSurfaceProofPath",
        str(cached_resident_surface),
    )

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["status"] == "proof_passed"
    assert payload["cached_resident_surface_proof"] is True
    assert payload["effective_resident_surface_foreground_run_seconds"] == 0
    assert payload["resident_surface_foreground_runtime_proof_observed"] is True
    assert payload["resident_surface_runtime_supervision_handoff_observed"] is True
    assert payload["resident_surface_next_smallest_truthful_gap"] == "resident_surface_runtime_not_supervised"
    assert payload["resident_surface_authority_required"] == "process_supervision_authority"
    assert payload["resident_surface_authority_granted"] is False
    child_proof_runs = {item["name"]: item for item in payload["child_proof_runs"]}
    assert child_proof_runs["resident_surface_foreground_runtime"]["duration_ms"] == 0
    assert child_proof_runs["resident_surface_foreground_runtime"]["timed_out"] is False
    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["resident_surface_foreground_runtime_proof"]["status"] == "foreground_runtime_observed"
    assert checks["resident_surface_runtime_supervision_handoff"]["status"] == "handoff_observed"
    assert payload["next_smallest_truthful_gap"] == "stage6_lens_completion_audit"
