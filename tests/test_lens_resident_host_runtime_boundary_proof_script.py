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
            str(_repo_root() / "scripts" / "lens-resident-host-runtime-boundary-proof.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
    )


def test_lens_resident_host_runtime_boundary_consumes_handoff_without_authority() -> None:
    proc = _run_proof(
        "-Mode",
        "Status",
        "-ForegroundRunSeconds",
        "2",
        "-HostLaunchRunSeconds",
        "3",
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
    assert payload["runtime_handoff_observed"] is True
    assert payload["bounded_runtime_observed"] is True
    assert payload["runtime_heartbeat_observed"] is True
    assert payload["heartbeat_count"] >= 1
    assert payload["last_heartbeat_at"]
    assert payload["runtime_boundary_blocked"] is True
    assert payload["process_supervision_handoff_observed"] is True
    assert payload["side_effects_bounded"] is True
    assert payload["requested_foreground_run_seconds"] == 2
    assert payload["foreground_run_seconds"] >= 5
    assert payload["host_launch_run_seconds"] == 3
    assert payload["resident_host_process_state"] == "foreground_observed_not_supervised"
    assert payload["resident_host_process_blocker"] == "resident_host_process_not_supervised"
    assert payload["resident_runtime_ready"] is False
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
    assert checks["side_effects_bounded"]["status"] == "diagnostic_bounded"
    assert all(item["passed"] for item in payload["checks"])

    assert "resident_host_runtime_blocker_boundary_consumed" in payload["blockers"]
    assert "lens_host_runtime_not_implemented" in payload["blockers"]
    assert "resident_host_process_not_supervised" in payload["blockers"]
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
    assert proof["process_supervision_status"] == "blocked"
    assert proof["service_control_status"] == "blocked"
    assert proof["host_ready_for_resident_claim"] is False

    assert payload["governance"] == {
        "diagnostic_only": True,
        "wraps_summon_resident_host_blocker_proof": True,
        "wraps_host_supervision_proof": True,
        "bounded_local_process_launch": True,
        "bounded_process_launch": True,
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
