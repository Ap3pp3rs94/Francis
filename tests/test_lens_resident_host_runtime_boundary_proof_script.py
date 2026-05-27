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
            str(_repo_root() / "scripts" / "lens-resident-host-runtime-boundary-proof.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
        timeout=210,
        env=env,
    )


def test_lens_resident_host_runtime_boundary_requires_prior_authority_readback() -> None:
    script = (_repo_root() / "scripts" / "lens-resident-host-runtime-boundary-proof.ps1").read_text(encoding="utf-8")

    assert (
        "[string](Get-PropertyValue -Payload $SummonResidentHostPayload -Name 'authority_required' -Default '') "
        "-eq 'process_supervision_authority'"
    ) in script
    assert (
        "-not [bool](Get-PropertyValue -Payload $SummonResidentHostPayload -Name 'authority_granted' -Default $true)"
    ) in script


def test_lens_resident_host_runtime_boundary_accepts_existing_candidate_readback() -> None:
    script = (_repo_root() / "scripts" / "lens-resident-host-runtime-boundary-proof.ps1").read_text(encoding="utf-8")

    assert "$ExistingResidentCandidateObserved" in script
    assert "resident_candidate_already_running_observed" in script
    assert "resident_runtime_candidate_existing_process_observed" in script
    assert "resident_runtime_candidate_fresh_bounded_launch" in script
    assert "bounded_resident_candidate_launch = $FreshResidentCandidateObserved" in script


def test_lens_resident_host_runtime_boundary_accepts_lifecycle_child_handoff() -> None:
    script = (_repo_root() / "scripts" / "lens-resident-host-runtime-boundary-proof.ps1").read_text(encoding="utf-8")

    assert "[string](Get-PropertyValue -Payload $SummonResidentHostPayload -Name 'recommended_handoff_source'" in script
    assert "'resident_host_lifecycle_handoff'" in script
    assert "'run_resident_host_lifecycle_blockers_proof'" in script
    assert "'scripts/lens-resident-host-lifecycle-blockers-proof.ps1 -Mode Status'" in script


def test_lens_resident_host_runtime_boundary_consumes_handoff_without_authority(tmp_path: Path) -> None:
    proc = _run_proof(
        "-Mode",
        "Status",
        "-ForegroundRunSeconds",
        "2",
        "-HostLaunchRunSeconds",
        "3",
        "-ResidentCandidateRunSeconds",
        "2",
        "-ChildProofTimeoutSeconds",
        "180",
        data_dir=tmp_path / "data",
    )

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.resident_host.runtime_blocker_boundary.proof"
    assert payload["status"] == "proof_passed"
    assert payload["ok"] is True
    assert payload["stage"] == "Stage 6 / Lens MVP"
    assert payload["stage_state"] == "active"
    assert payload["acceptance_criterion"] == "summon_anywhere"
    assert payload["previous_next_smallest_truthful_gap"] == "resident_host_runtime_blocker_boundary"
    assert payload["next_smallest_truthful_gap"] == "resident_host_process_not_supervised"
    assert payload["recommended_handoff_source"] == "runtime_boundary_process_supervision_handoff"
    assert payload["recommended_next_slice"] == (
        "consume_resident_host_process_supervision_handoff_before_stage6_closure"
    )
    assert payload["recommended_proof_script"] == (
        "scripts/lens-resident-host-process-supervision-blocker-proof.ps1 -Mode Status"
    )
    assert payload["authority_required"] == "process_supervision_authority"
    assert payload["authority_granted"] is False
    recommended_handoff = payload["recommended_handoff"]
    assert recommended_handoff["id"] == "resident_host_process_supervision"
    assert recommended_handoff["status"] == "blocked"
    assert recommended_handoff["previous_next_smallest_truthful_gap"] == ("resident_host_runtime_blocker_boundary")
    assert recommended_handoff["next_smallest_truthful_gap"] == "resident_host_process_not_supervised"
    assert recommended_handoff["next_step"] == (
        "consume_resident_host_process_supervision_handoff_before_stage6_closure"
    )
    assert recommended_handoff["proof_script"] == (
        "scripts/lens-resident-host-process-supervision-blocker-proof.ps1 -Mode Status"
    )
    assert recommended_handoff["route"] == "/lens/host"
    assert recommended_handoff["readiness_route"] == "/lens/host/supervision"
    assert recommended_handoff["acceptance_criterion"] == "system_resident_presence"
    assert recommended_handoff["blocker"] == "resident_host_process_not_supervised"
    assert recommended_handoff["requirement_state"] == "foreground_observed_not_supervised"
    assert recommended_handoff["authority_required"] == "process_supervision_authority"
    assert recommended_handoff["authority_granted"] is False
    assert recommended_handoff["read_only_contract"] is True
    assert recommended_handoff["diagnostic_only"] is True
    assert recommended_handoff["would_execute"] is False
    assert recommended_handoff["would_mutate"] is False
    assert recommended_handoff["would_supervise_process"] is False
    assert recommended_handoff["would_restart_process"] is False
    assert recommended_handoff["would_claim_resident"] is False
    assert payload["runtime_handoff_observed"] is True
    assert payload["bounded_runtime_observed"] is True
    assert payload["runtime_heartbeat_observed"] is True
    assert payload["heartbeat_count"] >= 1
    assert payload["last_heartbeat_at"]
    assert payload["runtime_boundary_blocked"] is True
    assert payload["process_supervision_handoff_observed"] is True
    assert payload["side_effects_bounded"] is True
    assert payload["cached_host_supervision_proof"] is False
    assert payload["requested_foreground_run_seconds"] == 2
    assert payload["foreground_run_seconds"] >= 5
    assert payload["host_launch_run_seconds"] == 3
    assert payload["resident_candidate_run_seconds"] == 2
    assert payload["resident_host_process_state"] == "foreground_observed_not_supervised"
    assert payload["resident_host_process_blocker"] == "resident_host_process_not_supervised"
    assert payload["resident_runtime_candidate_observed"] is True
    assert payload["resident_runtime_candidate_supervised"] is True
    assert payload["resident_runtime_candidate_fresh_bounded_launch"] is True
    assert payload["resident_runtime_candidate_existing_process_observed"] is False
    assert payload["resident_runtime_candidate_next_smallest_truthful_gap"] == "resident_supervision_not_persistent"
    assert payload["resident_runtime_persistence_blocker"] == "resident_supervision_not_persistent"
    assert payload["resident_runtime_ready"] is False
    assert payload["resident_runtime_persistent"] is False
    assert payload["supervision_ready"] is False
    assert payload["ready_for_resident_claim"] is False
    assert payload["resident_claim_allowed"] is False
    assert payload["resident_host_process"] is False
    assert payload["resident_host_supervised"] is False
    assert payload["service_managed"] is False
    assert payload["tray_presence"] is False
    assert payload["global_hotkey"] is False
    assert payload["overlay_window"] is False
    assert payload["summon_anywhere"] is False

    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["resident_host_runtime_handoff"]["status"] == "handoff_consumed"
    assert checks["bounded_runtime_observation"]["status"] == "foreground_observed_not_supervised"
    assert checks["runtime_heartbeat_readback"]["status"] == "heartbeat_observed"
    assert checks["runtime_boundary_blocked"]["status"] == "blocked"
    assert checks["process_supervision_handoff"]["status"] == "next_blocker_identified"
    assert checks["resident_candidate_supervision"]["status"] == "resident_candidate_observed_not_persistent"
    assert checks["side_effects_bounded"]["status"] == "diagnostic_bounded"
    assert all(item["passed"] for item in payload["checks"])

    assert "resident_host_runtime_blocker_boundary_consumed" in payload["blockers"]
    assert "lens_host_persistent_supervision_prerequisites_pending" in payload["blockers"]
    assert "resident_host_process_not_supervised" in payload["blockers"]
    assert "resident_runtime_candidate_not_persistent" in payload["blockers"]
    assert "resident_supervision_not_persistent" in payload["blockers"]
    assert "process_supervision_authority_not_granted" in payload["blockers"]
    assert "process_restart_authority_not_granted" in payload["blockers"]
    assert "tray_host_missing" in payload["blockers"]
    assert "global_hotkey_binding_missing" in payload["blockers"]
    assert "overlay_window_missing" in payload["blockers"]
    assert "summon_binding_missing" in payload["blockers"]

    proof = payload["proof"]
    assert proof["summon_resident_host_status"] == "proof_passed"
    assert proof["summon_resident_host_next_gap"] == "resident_host_runtime_blocker_boundary"
    assert proof["host_supervision_status"] == "proof_passed"
    assert proof["bounded_host_launch_observed"] is True
    assert proof["foreground_process_observed"] is True
    assert proof["host_supervision_runtime_heartbeat_observed"] is True
    assert proof["host_supervision_heartbeat_count"] == payload["heartbeat_count"]
    assert proof["host_supervision_heartbeat_count"] >= 1
    assert proof["host_supervision_last_heartbeat_at"] == payload["last_heartbeat_at"]
    assert proof["host_supervision_next_gap"] == "resident_host_process_not_supervised"
    assert proof["resident_candidate_status"] == "supervised_session_completed"
    assert proof["resident_candidate_next_gap"] == "resident_supervision_not_persistent"
    assert proof["resident_candidate_supervised"] is True
    assert proof["resident_candidate_fresh_bounded_launch"] is True
    assert proof["resident_candidate_existing_process_observed"] is False
    assert proof["process_supervision_status"] == "enabled"
    assert proof["service_control_status"] == "blocked"
    assert proof["host_ready_for_resident_claim"] is False

    assert payload["governance"] == {
        "diagnostic_only": True,
        "wraps_summon_resident_host_blocker_proof": True,
        "wraps_host_supervision_proof": True,
        "cached_host_supervision_proof": False,
        "wraps_resident_candidate_supervisor_proof": True,
        "bounded_local_process_launch": True,
        "bounded_process_launch": True,
        "bounded_resident_candidate_launch": True,
        "existing_resident_candidate_observed": False,
        "child_proof_timeout_seconds": 180,
        "temporary_runtime_state_write": True,
        "product_execution_authority": False,
        "execution_authority": False,
        "approval_decision_authority": False,
        "memory_write": False,
        "local_process_launch_authority": True,
        "api_local_process_launch_authority": False,
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
        "resident_claim_authority": False,
        "mutation_authority_granted": False,
    }
