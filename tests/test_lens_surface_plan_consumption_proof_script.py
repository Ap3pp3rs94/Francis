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
            str(_repo_root() / "scripts" / "lens-surface-plan-consumption-proof.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
        timeout=180,
    )


def test_lens_surface_plan_consumption_proof_consumes_summon_handoff_readback() -> None:
    if platform.system() != "Windows":
        pytest.skip("Live resident host surface plan-consumption proof is Windows-hosted.")

    proc = _run_script("-Mode", "Status")

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.surface_runtime.plan_consumption_proof"
    assert payload["status"] == "proof_passed"
    assert payload["ok"] is True
    assert payload["stage_state"] == "active"
    assert payload["ready_to_close"] is False
    assert payload["data_root_removed"] is True
    assert payload["live_resident_host_observed"] is True
    assert payload["coordinated_surface_runtime_readback_observed"] is True
    assert payload["persistent_supervision_plan_consumed_surface_runtime"] is True
    assert payload["resident_dependency_ready"] is True
    assert payload["plan_retry_attempted"] in {True, False}
    assert isinstance(payload["plan_retry_reason"], str)
    assert isinstance(payload["initial_plan_first_missing_required_before_enable"], str)
    assert isinstance(payload["initial_plan_next_smallest_truthful_gap"], str)
    assert payload["tray_dependency_ready"] is True
    assert payload["global_hotkey_dependency_ready"] is True
    assert payload["overlay_dependency_ready"] is True
    assert payload["summon_dependency_ready"] is True
    assert payload["summon_binding_still_blocked"] is False
    assert payload["first_missing_required_before_enable"] == ""
    assert payload["missing_required_before_enable"] == []
    assert payload["next_smallest_truthful_gap"] == "persistent_supervision_authority_not_granted"
    assert payload["recommended_next_slice"] == "resolve_persistent_supervision_authority_before_enablement"
    assert payload["recommended_handoff_source"] == "surface_plan_consumption_persistent_supervision_authority_handoff"
    assert (
        payload["recommended_proof_script"]
        == "scripts/lens-persistent-supervision-enablement-authority-proof.ps1 -Mode Status"
    )
    assert payload["recommended_route"] == "/lens/host/persistent-supervision/enablement/authority"
    assert payload["recommended_readiness_route"] == "/lens/host/persistent-supervision/enablement/authority/readiness"
    assert payload["authority_required"] == "persistent_supervision_enablement_authority"
    assert payload["authority_granted"] is False
    assert payload["stop_observed"] is True
    assert payload["side_effects_bounded"] is True

    recommended_handoff = payload["recommended_handoff"]
    assert recommended_handoff["status"] == "blocked"
    assert (
        recommended_handoff["consumed_surface_runtime_next_smallest_truthful_gap"]
        == "persistent_supervision_authority_not_granted"
    )
    assert recommended_handoff["next_smallest_truthful_gap"] == "persistent_supervision_authority_not_granted"
    assert recommended_handoff["next_step"] == "resolve_persistent_supervision_authority_before_enablement"
    assert (
        recommended_handoff["proof_script"]
        == "scripts/lens-persistent-supervision-enablement-authority-proof.ps1 -Mode Status"
    )
    assert recommended_handoff["route"] == "/lens/host/persistent-supervision/enablement"
    assert recommended_handoff["authority_route"] == "/lens/host/persistent-supervision/enablement/authority"
    assert recommended_handoff["readiness_route"] == "/lens/host/persistent-supervision/enablement/authority/readiness"
    assert recommended_handoff["authority_required"] == "persistent_supervision_enablement_authority"
    assert recommended_handoff["authority_granted"] is False
    assert recommended_handoff["required_before_enable_ready"] is True
    assert recommended_handoff["first_missing_required_before_enable"] == ""
    assert recommended_handoff["missing_required_before_enable"] == []
    assert recommended_handoff["read_only_contract"] is True
    assert recommended_handoff["diagnostic_only"] is True
    assert recommended_handoff["would_execute"] is False
    assert recommended_handoff["would_mutate"] is False
    assert recommended_handoff["would_supervise_process"] is False
    assert recommended_handoff["would_restart_process"] is False
    assert recommended_handoff["would_install_service"] is False
    assert recommended_handoff["would_start_service"] is False
    assert recommended_handoff["would_write_receipt"] is False
    assert recommended_handoff["would_write_memory"] is False
    assert recommended_handoff["would_decide_approval"] is False
    assert recommended_handoff["would_claim_resident"] is False
    assert "process_restart_authority_not_granted" in recommended_handoff["blockers"]
    assert "service_install_authority_not_granted" in recommended_handoff["blockers"]
    assert "service_control_authority_not_granted" in recommended_handoff["blockers"]
    assert "receipt_write_authority_not_granted" in recommended_handoff["blockers"]
    assert "resident_claim_authority_not_granted" in recommended_handoff["blockers"]

    scope = payload["proof_scope"]
    assert scope == {
        "synthetic_tray_runtime_readback": True,
        "synthetic_hotkey_runtime_readback": True,
        "synthetic_overlay_runtime_readback": True,
        "synthetic_summon_runtime_readback": True,
        "os_tray_registered": False,
        "global_hotkey_registered": False,
        "overlay_opened": False,
        "browser_launched": False,
        "os_level_summon": False,
        "summon_anywhere": False,
        "bounded_summon_handoff_readback": True,
        "persistent_supervision_enabled": False,
    }

    start = payload["start_resident"]
    assert start["exit_code"] == 0
    assert start["status"] == "resident_supervision_started"
    assert start["resident_host_process"] is True
    assert start["resident_supervised_runtime"] is True
    assert start["supervisor_pid"] > 0
    assert start["host_pid"] > 0
    assert start["parse_error"] == ""
    assert start["stderr"] == ""

    surface = payload["surface_runtime"]
    assert surface["exit_code"] == 0
    assert surface["status"] == "running"
    assert surface["ready"] is True
    assert surface["ready_total"] == 3
    assert surface["component_total"] == 3
    assert surface["parse_error"] == ""
    assert surface["stderr"] == ""

    plan = payload["persistent_supervision_plan"]
    assert plan["exit_code"] == 0
    assert plan["status"] == "blocked"
    assert plan["required_before_enable_ready"] is True
    assert plan["first_missing_required_before_enable"] == ""
    assert plan["next_smallest_truthful_gap"] == "persistent_supervision_authority_not_granted"
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

    tray = payload["tray_dependency"]
    assert tray["id"] == "tray_presence"
    assert tray["ready"] is True
    assert tray["status"] == "ready"
    assert tray["blocker"] == ""
    assert tray["requirement_state"] == "ready"
    assert tray["tray_presence_source"] == "live_runtime_readback"
    assert tray["tray_runtime_ready"] is True
    assert tray["tray_runtime_process_alive"] is True
    assert tray["tray_runtime_icon_visible"] is True
    assert tray["tray_registration_authority"] is False
    assert tray["tray_icon_authority"] is False

    hotkey = payload["global_hotkey_dependency"]
    assert hotkey["id"] == "global_hotkey_binding"
    assert hotkey["ready"] is True
    assert hotkey["status"] == "ready"
    assert hotkey["blocker"] == ""
    assert hotkey["requirement_state"] == "ready"
    assert hotkey["global_hotkey_source"] == "live_runtime_readback"
    assert hotkey["hotkey_runtime_ready"] is True
    assert hotkey["hotkey_runtime_process_alive"] is True
    assert hotkey["hotkey_runtime_bound"] is True
    assert hotkey["hotkey_registration_authority"] is True

    overlay = payload["overlay_dependency"]
    assert overlay["id"] == "overlay_window"
    assert overlay["ready"] is True
    assert overlay["status"] == "ready"
    assert overlay["blocker"] == ""
    assert overlay["requirement_state"] == "ready"
    assert overlay["overlay_window_source"] == "live_runtime_readback"
    assert overlay["overlay_runtime_ready"] is True
    assert overlay["overlay_runtime_process_alive"] is True
    assert overlay["overlay_runtime_window_visible"] is True
    assert overlay["overlay_runtime_always_on_top"] is True
    assert overlay["overlay_control_authority"] is False
    assert overlay["window_management_authority"] is False

    summon = payload["summon_dependency"]
    assert summon["id"] == "summon_binding"
    assert summon["ready"] is True
    assert summon["status"] == "ready"
    assert summon["blocker"] == ""
    assert summon["requirement_state"] == "ready"
    assert summon["blocked_reason"] == ""
    assert summon["summon_authority"] is True
    assert summon["local_process_launch_authority"] is True
    assert summon["summon_config_ready"] is False
    assert summon["summon_runtime_ready"] is True
    assert summon["summon_presence_source"] == "live_runtime_readback"
    assert summon["summon_runtime_requirement_state"] == "bounded_handoff_observed"
    assert summon["summon_runtime_blocker"] == ""
    assert summon["summon_runtime_bounded_handoff_ready"] is True
    assert summon["summon_runtime_local_open_ready"] is True
    assert summon["summon_runtime_no_launch"] is True
    summon_runtime = summon["summon_runtime_readback"]
    assert summon_runtime["ready"] is True
    assert summon_runtime["status"] == "observed"
    assert summon_runtime["state_kind"] == "lens.summon.runtime_state"
    assert summon_runtime["state_status"] == "summon_binding_observed"
    assert summon_runtime["global_hotkey"] == "Ctrl+Alt+F"
    assert summon_runtime["expected_global_hotkey"] == "Ctrl+Alt+F"
    assert summon_runtime["binding_scope"] == "global"
    assert summon_runtime["expected_binding_scope"] == "global"
    assert summon_runtime["bounded_handoff_ready"] is True
    assert summon_runtime["local_open_ready"] is True
    assert summon_runtime["opened"] is False
    assert summon_runtime["no_launch"] is True
    assert summon_runtime["summon_anywhere"] is False
    assert summon_runtime["os_level_summon"] is False

    handoff = payload["plan_first_missing_requirement_handoff"]
    assert handoff is None

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
