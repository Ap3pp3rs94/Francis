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


def _run_checkpoint(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            _powershell(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(_repo_root() / "scripts" / "lens-stage6-checkpoint.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
    )


def test_lens_stage6_checkpoint_reports_blocked_done_criteria_without_authority() -> None:
    proc = _run_checkpoint("-Mode", "Status")

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.stage6.checkpoint"
    assert payload["status"] == "blocked"
    assert payload["stage"] == "Stage 6 / Lens MVP"
    assert payload["stage_state"] == "active"
    assert payload["stage_claim"] == "backend_readback_contract_only"
    assert payload["ready_to_close"] is False
    assert payload["summary"] == {
        "criteria_total": 5,
        "ready_total": 2,
        "blocked_total": 3,
        "blocker_total": len(payload["blockers"]),
    }
    criteria = {item["id"]: item for item in payload["criteria"]}
    assert criteria["summon_anywhere"]["status"] == "not_implemented"
    assert criteria["summon_anywhere"]["ready"] is False
    assert "resident_host_process_missing" in criteria["summon_anywhere"]["blockers"]
    assert "global_hotkey_binding_missing" in criteria["summon_anywhere"]["blockers"]
    assert "summon_binding_missing" in criteria["summon_anywhere"]["blockers"]
    assert criteria["helpful_not_noisy"]["status"] == "needs_live_operator_proof"
    assert criteria["helpful_not_noisy"]["ready"] is False
    assert "operator_experience_proof_missing" in criteria["helpful_not_noisy"]["blockers"]
    assert criteria["mode_visibility"]["status"] == "readback_ready"
    assert criteria["mode_visibility"]["ready"] is True
    assert criteria["pilot_visibility_groundwork"]["status"] == "readback_ready"
    assert criteria["pilot_visibility_groundwork"]["ready"] is True
    assert criteria["system_resident_presence"]["status"] == "not_implemented"
    assert criteria["system_resident_presence"]["ready"] is False
    assert "resident_host_process_missing" in criteria["system_resident_presence"]["blockers"]
    assert "resident_overlay_runtime_missing" in criteria["system_resident_presence"]["blockers"]
    assert "tray_host_missing" in payload["blockers"]
    assert "overlay_window_missing" in payload["blockers"]
    assert payload["next_smallest_truthful_gap"] == "resident_host_process_or_supervised_foreground_readiness_proof"
    assert payload["governance"] == {
        "read_only_contract": True,
        "diagnostic_only": True,
        "execution_authority": False,
        "approval_decision_authority": False,
        "memory_write": False,
        "overlay_control_authority": False,
        "summon_authority": False,
        "capture_authority": False,
        "new_sensing_authority": False,
        "local_process_launch_authority": False,
        "service_install_authority": False,
        "service_control_authority": False,
        "hotkey_registration_authority": False,
        "tray_registration_authority": False,
        "mutation_authority_granted": False,
    }
