from __future__ import annotations

import json
import os
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


def _write_cached_process_boundary_proof(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "kind": "lens.process_supervision_authority_boundary.proof",
                "status": "proof_passed",
                "ok": True,
                "authority_required": "process_supervision_and_service_control",
                "authority_granted": False,
                "process_supervision_authority_required": "process_supervision_authority",
                "process_supervision_authority_granted": False,
                "process_restart_authority_required": "process_restart_authority",
                "process_restart_authority_granted": False,
                "service_install_authority_required": "service_install_authority",
                "service_install_authority_granted": False,
                "service_control_authority_required": "service_control_authority",
                "service_control_authority_granted": False,
                "process_supervision_boundary_observed": True,
                "service_activation_plan_observed": True,
                "bounded_local_process_launch_observed": True,
                "process_supervision_ready": False,
                "service_activation_ready": False,
                "cached_host_supervision_proof": True,
                "next_smallest_truthful_gap": "stage6_lens_completion_audit",
                "blockers": [
                    "resident_host_process_not_supervised",
                    "process_supervision_authority_not_granted",
                    "process_restart_authority_not_granted",
                    "service_install_authority_not_granted",
                    "service_control_authority_not_granted",
                ],
                "governance": {
                    "diagnostic_only": True,
                    "bounded_host_launch": True,
                    "bounded_process_launch": True,
                    "execution_authority": False,
                    "approval_decision_authority": False,
                    "memory_write": False,
                    "process_supervision_authority": False,
                    "process_restart_authority": False,
                    "service_install_authority": False,
                    "service_control_authority": False,
                    "overlay_control_authority": False,
                    "summon_authority": False,
                    "capture_authority": False,
                    "new_sensing_authority": False,
                    "mutation_authority_granted": False,
                },
            }
        ),
        encoding="utf-8",
    )


def _run_proof(*args: str, data_dir: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    if data_dir is not None:
        env["FRANCIS_DATA_DIR"] = str(data_dir)
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
        env=env,
    )


def test_lens_resident_host_process_supervision_blocker_consumes_handoff(tmp_path: Path) -> None:
    cached_process_boundary = tmp_path / "process-boundary-proof.json"
    _write_cached_process_boundary_proof(cached_process_boundary)

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
        "-ChildProofTimeoutSeconds",
        "180",
        "-CachedProcessBoundaryProofPath",
        str(cached_process_boundary),
        data_dir=tmp_path / "data",
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
    assert payload["blocked_authority_required"] == "process_supervision_and_service_control"
    assert payload["blocked_authority_granted"] is False
    assert payload["process_supervision_authority_required"] == "process_supervision_authority"
    assert payload["process_supervision_authority_granted"] is False
    assert payload["process_restart_authority_required"] == "process_restart_authority"
    assert payload["process_restart_authority_granted"] is False
    assert payload["service_install_authority_required"] == "service_install_authority"
    assert payload["service_install_authority_granted"] is False
    assert payload["service_control_authority_required"] == "service_control_authority"
    assert payload["service_control_authority_granted"] is False
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
    assert payload["host_supervision_cache_observed"] is True
    assert payload["runtime_boundary_cached_host_supervision_proof"] is True
    assert payload["process_boundary_cached_host_supervision_proof"] is True
    assert payload["cached_process_boundary_proof"] is True
    assert payload["startup_timeout_seconds"] == 20
    assert payload["foreground_run_seconds"] == 2
    assert payload["host_launch_run_seconds"] == 3
    assert payload["supervisor_run_seconds"] == 3
    assert payload["child_proof_timeout_seconds"] == 180
    assert payload["child_proof_timeouts"] == []
    child_proof_runs = {item["name"]: item for item in payload["child_proof_runs"]}
    assert set(child_proof_runs) == {
        "host_supervision_cache",
        "resident_host_runtime_boundary",
        "process_supervision_boundary",
    }
    for run in child_proof_runs.values():
        assert run["timed_out"] is False
        assert isinstance(run["duration_ms"], int)
        assert run["duration_ms"] >= 0
        assert isinstance(run["cached"], bool)
    assert child_proof_runs["host_supervision_cache"]["timeout_seconds"] == 180
    assert child_proof_runs["resident_host_runtime_boundary"]["timeout_seconds"] == 180
    assert child_proof_runs["process_supervision_boundary"]["timeout_seconds"] == 180
    assert child_proof_runs["process_supervision_boundary"]["duration_ms"] == 0
    assert child_proof_runs["process_supervision_boundary"]["cached"] is True
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
    assert checks["host_supervision_cache"]["status"] == "cache_written"
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
    assert proof["host_supervision_cache_status"] == "proof_passed"
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
        "cached_host_supervision_proof": True,
        "child_proof_timeout_seconds": 180,
        "cached_process_boundary_proof": True,
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


def test_lens_resident_host_process_supervision_blocker_accepts_delegated_authority_contract() -> None:
    script = (_repo_root() / "scripts" / "lens-resident-host-process-supervision-blocker-proof.ps1").read_text(
        encoding="utf-8"
    )

    assert "$ProcessBoundaryDelegatedAuthorityObserved" in script
    assert "CachedProcessBoundaryProofPath" in script
    assert "Read-CachedJsonScriptResult -Path $CachedProcessBoundaryProofPath" in script
    assert "'resident_runtime_execution_and_host_supervision_authority'" in script
    assert "process_supervision_delegated_authority_observed = $ProcessBoundaryDelegatedAuthorityObserved" in script
    assert "whether process supervision is still denied or delegated authority is already present" in script
    assert "read delegated process-supervision authority" in script
