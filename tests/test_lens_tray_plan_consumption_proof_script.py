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
            str(_repo_root() / "scripts" / "lens-tray-plan-consumption-proof.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
        timeout=180,
    )


def test_lens_tray_plan_consumption_proof_moves_handoff_to_global_hotkey() -> None:
    if platform.system() != "Windows":
        pytest.skip("Live resident host tray plan-consumption proof is Windows-hosted.")

    proc = _run_script("-Mode", "Status")

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.tray_runtime.plan_consumption_proof"
    assert payload["status"] == "proof_passed"
    assert payload["ok"] is True
    assert payload["stage_state"] == "active"
    assert payload["ready_to_close"] is False
    assert payload["data_root_removed"] is True
    assert payload["live_resident_host_observed"] is True
    assert payload["synthetic_tray_runtime_readback_observed"] is True
    assert payload["persistent_supervision_plan_consumed_tray_runtime"] is True
    assert payload["resident_dependency_ready"] is True
    assert payload["tray_dependency_ready"] is True
    assert payload["first_missing_required_before_enable"] == "global_hotkey_binding"
    assert payload["missing_required_before_enable"] == [
        "global_hotkey_binding",
        "overlay_window",
        "summon_binding",
    ]
    assert payload["next_smallest_truthful_gap"] == "global_hotkey_binding"
    assert payload["recommended_next_slice"] == "resolve_global_hotkey_binding_before_persistent_supervision_enablement"
    assert payload["stop_observed"] is True
    assert payload["side_effects_bounded"] is True

    scope = payload["proof_scope"]
    assert scope == {
        "synthetic_tray_runtime_readback": True,
        "os_tray_registered": False,
        "tray_icon_claim_source": "proof_runtime_readback",
        "persistent_supervision_enabled": False,
        "global_hotkey_registered": False,
        "overlay_opened": False,
        "summon_binding_enabled": False,
    }

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

    tray_state = payload["tray_runtime_state"]
    assert tray_state["kind"] == "lens.tray.runtime_state"
    assert tray_state["status"] == "tray_running"
    assert tray_state["pid"] > 0
    assert tray_state["tray_icon_visible"] is True
    assert tray_state["proof_only"] is True
    assert tray_state["os_tray_registered"] is False

    tray_presence = payload["tray_presence"]
    assert tray_presence["exit_code"] == 0
    assert tray_presence["status"] == "running"
    assert tray_presence["ready"] is True
    assert tray_presence["tray_presence"] is True
    assert tray_presence["parse_error"] == ""
    assert tray_presence["stderr"] == ""

    plan = payload["persistent_supervision_plan"]
    assert plan["exit_code"] == 0
    assert plan["status"] == "blocked"
    assert plan["required_before_enable_ready"] is False
    assert plan["first_missing_required_before_enable"] == "global_hotkey_binding"
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

    tray = payload["tray_dependency"]
    assert tray["id"] == "tray_presence"
    assert tray["ready"] is True
    assert tray["status"] == "ready"
    assert tray["blocker"] == ""
    assert tray["requirement_state"] == "ready"
    assert tray["blocked_reason"] == ""
    assert tray["tray_presence_source"] == "live_runtime_readback"
    assert tray["tray_runtime_ready"] is True
    assert tray["tray_runtime_process_alive"] is True
    assert tray["tray_runtime_icon_visible"] is True
    assert tray["tray_runtime_pid"] > 0
    assert tray["tray_runtime_status"] == "tray_running"
    assert tray["tray_runtime_status_kind"] == "lens.tray.runtime_state"
    assert tray["tray_runtime_state_exists"] is True
    assert tray["tray_runtime_status_pid_matches_pid_file"] is True
    assert tray["tray_registration_authority"] is False
    assert tray["tray_icon_authority"] is False

    handoff = payload["plan_first_missing_requirement_handoff"]
    assert handoff["id"] == "global_hotkey_binding"
    assert handoff["blocker"] == "global_hotkey_binding_missing"
    assert handoff["requirement_state"] == "binding_disabled"
    assert handoff["proof_script"] == "scripts/lens-summon-global-hotkey-binding-blocker-proof.ps1 -Mode Status"
    assert handoff["os_binding_readiness_route"] == "/lens/os-binding/readiness"
    assert handoff["os_binding_authority_route"] == "/lens/os-binding/authority"
    assert handoff["approval_action"] == "lens.os_binding.command_palette_binding_authority"
    assert handoff["authority_scope"] == "system.write"
    assert handoff["read_only_contract"] is True
    assert handoff["diagnostic_only"] is True
    assert handoff["would_execute"] is False
    assert handoff["would_mutate"] is False

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
        "tray_icon_authority": False,
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
