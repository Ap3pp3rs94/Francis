from __future__ import annotations

import json
import platform
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


def _run_script(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            _powershell(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(_repo_root() / "scripts" / "lens-resident-host-plan-consumption-proof.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
        timeout=180,
    )


def test_lens_resident_host_plan_consumption_proof_moves_handoff_to_tray_presence() -> None:
    if platform.system() != "Windows":
        pytest.skip("Live resident host plan-consumption proof is Windows-hosted.")

    proc = _run_script("-Mode", "Status")

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.resident_host.plan_consumption_proof"
    assert payload["status"] == "proof_passed"
    assert payload["ok"] is True
    assert payload["stage_state"] == "active"
    assert payload["ready_to_close"] is False
    assert payload["data_root_removed"] is True
    assert payload["live_resident_host_observed"] is True
    assert payload["persistent_supervision_plan_consumed_live_resident_host"] is True
    assert payload["resident_dependency_ready"] is True
    assert payload["first_missing_required_before_enable"] == "tray_presence"
    assert payload["missing_required_before_enable"] == [
        "tray_presence",
        "global_hotkey_binding",
        "overlay_window",
        "summon_binding",
    ]
    assert payload["next_smallest_truthful_gap"] == "tray_presence"
    assert payload["recommended_next_slice"] == "resolve_tray_presence_before_persistent_supervision_enablement"
    assert payload["stop_observed"] is True
    assert payload["side_effects_bounded"] is True

    start = payload["start_resident"]
    assert start["exit_code"] == 0
    assert start["status"] == "resident_supervision_started"
    assert start["resident_host_process"] is True
    assert start["resident_supervised_runtime"] is True
    assert start["supervisor_pid"] > 0
    assert start["host_pid"] > 0
    assert start["next_smallest_truthful_gap"] == "summon_tray_presence_blocker_boundary"
    assert start["parse_error"] == ""
    assert start["stderr"] == ""

    plan = payload["persistent_supervision_plan"]
    assert plan["exit_code"] == 0
    assert plan["status"] == "blocked"
    assert plan["required_before_enable_ready"] is False
    assert plan["first_missing_required_before_enable"] == "tray_presence"
    assert plan["next_smallest_truthful_gap"] == "persistent_supervision_required_prerequisites_missing"
    assert plan["parse_error"] == ""
    assert plan["stderr"] == ""

    resident = payload["resident_dependency"]
    assert resident["id"] == "resident_host_process"
    assert resident["ready"] is True
    assert resident["status"] == "ready"
    assert resident["blocker"] == ""
    assert resident["requirement_state"] == "ready"
    assert resident["process_alive"] is True
    assert resident["runtime_status"] == "resident_running"
    assert resident["resident_supervised_runtime"] is True
    assert resident["proof_script"] == ""
    assert resident["read_only_contract"] is True
    assert resident["diagnostic_only"] is True
    assert resident["would_execute"] is False
    assert resident["would_mutate"] is False

    handoff = payload["plan_first_missing_requirement_handoff"]
    assert handoff["id"] == "tray_presence"
    assert handoff["blocker"] == "tray_host_missing"
    assert handoff["requirement_state"] == "tray_host_disabled"
    assert handoff["tray_registration_authority"] is False

    stop = payload["stop_resident"]
    assert stop["exit_code"] == 0
    assert stop["status"] == "resident_supervision_stopped"
    assert stop["resident_host_process"] is False
    assert stop["resident_supervised_runtime"] is False
    assert stop["parse_error"] == ""
    assert stop["stderr"] == ""

    governance = payload["governance"]
    assert governance == {
        "diagnostic_only": False,
        "read_only_contract": False,
        "temporary_runtime_state_write": True,
        "product_execution_authority": False,
        "execution_authority": False,
        "approval_decision_authority": False,
        "memory_write": False,
        "local_process_launch_authority": True,
        "process_supervision_authority": True,
        "process_restart_authority": False,
        "service_install_authority": False,
        "service_control_authority": False,
        "tray_registration_authority": False,
        "hotkey_registration_authority": False,
        "overlay_control_authority": False,
        "window_management_authority": False,
        "summon_authority": False,
        "receipt_write_authority": False,
        "resident_claim_authority": False,
        "capture_authority": False,
        "new_sensing_authority": False,
        "mutation_authority_granted": False,
    }
