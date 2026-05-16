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
            str(_repo_root() / "scripts" / "lens-summon-binding-blocker-proof.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
    )


def test_lens_summon_binding_blocker_proof_is_readback_only(tmp_path: Path) -> None:
    proc = _run_proof("-Mode", "Status", "-DataDir", str(tmp_path / "data"))

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.summon_binding_blocker.proof"
    assert payload["status"] == "proof_passed"
    assert payload["ok"] is True
    assert payload["stage"] == "Stage 6 / Lens MVP"
    assert payload["stage_state"] == "active"
    assert payload["acceptance_criterion"] == "summon_anywhere"
    assert payload["previous_summon_blocker_family"] == "global_hotkey_binding"
    assert payload["summon_binding_blocker_family"] == "summon_binding"
    assert payload["fifth_summon_blocker_family"] == "summon_binding"
    assert payload["next_summon_blocker_family"] == "authority"
    assert payload["summon_next_smallest_truthful_gap"] == "summon_anywhere_blockers"
    assert payload["direct_summon_preflight_next_smallest_truthful_gap"] == ("summon_anywhere_blockers")
    assert payload["next_smallest_truthful_gap"] == "summon_authority_blocker_boundary"
    assert payload["summon_binding_family_observed"] is True
    assert payload["previous_global_hotkey_bridge_observed"] is True
    assert payload["previous_global_hotkey_bridge_handoff_readback_observed"] is True
    previous_global_hotkey_bridge = payload["previous_global_hotkey_bridge"]
    assert previous_global_hotkey_bridge["status"] == "proof_passed"
    assert previous_global_hotkey_bridge["next_summon_blocker_family"] == "summon_binding"
    assert previous_global_hotkey_bridge["next_smallest_truthful_gap"] == "summon_binding_blocker_boundary"
    assert previous_global_hotkey_bridge["previous_overlay_window_bridge_handoff_readback_observed"] is True
    previous_overlay_bridge = previous_global_hotkey_bridge["previous_overlay_window_bridge"]
    assert previous_overlay_bridge["status"] == "proof_passed"
    assert previous_overlay_bridge["next_summon_blocker_family"] == "global_hotkey_binding"
    assert previous_overlay_bridge["next_smallest_truthful_gap"] == ("summon_global_hotkey_binding_blocker_boundary")
    assert previous_overlay_bridge["previous_tray_presence_bridge_resident_host_readback_observed"] is True
    previous_tray_bridge = previous_overlay_bridge["previous_tray_presence_bridge"]
    assert previous_tray_bridge["status"] == "proof_passed"
    assert previous_tray_bridge["next_summon_blocker_family"] == "overlay_window"
    assert previous_tray_bridge["next_smallest_truthful_gap"] == "summon_overlay_window_blocker_boundary"
    assert previous_tray_bridge["previous_resident_host_bridge_observed"] is True
    previous_resident_host_bridge = previous_tray_bridge["previous_resident_host_bridge"]
    assert previous_resident_host_bridge["status"] == "proof_passed"
    assert previous_resident_host_bridge["first_summon_blocker_family"] == "resident_host"
    assert previous_resident_host_bridge["summon_next_smallest_truthful_gap"] == "summon_anywhere_blockers"
    assert previous_resident_host_bridge["next_smallest_truthful_gap"] == "stage6_lens_completion_audit"
    assert previous_resident_host_bridge["authority_required"] == "none_new_stage6_completion_audit"
    assert previous_resident_host_bridge["authority_granted"] is False
    assert previous_resident_host_bridge["process_supervision_handoff_observed"] is True
    process_handoff = previous_resident_host_bridge["process_supervision_handoff"]
    assert process_handoff["status"] == "proof_passed"
    assert process_handoff["next_smallest_truthful_gap"] == "stage6_lens_completion_audit"
    assert process_handoff["authority_required"] == "none_new_stage6_completion_audit"
    assert process_handoff["authority_granted"] is False
    recommended_handoff = process_handoff["recommended_handoff"]
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
    assert payload["summon_preflight_observed"] is True
    assert payload["handoff_aligned"] is True
    assert payload["side_effects_denied"] is True
    assert payload["summon_binding_blockers"] == [
        "lens_summon_binding_disabled_pending_authority",
        "summon_authority_not_granted",
    ]
    assert payload["direct_summon_preflight_binding_blockers"] == [
        "lens_summon_binding_disabled_pending_authority",
        "summon_authority_not_granted",
    ]
    assert "summon_authority_not_granted" in payload["direct_summon_preflight_authority_blockers"]
    assert "hotkey_registration_authority_not_granted" in (payload["direct_summon_preflight_authority_blockers"])

    boundary = payload["summon_preflight_boundary"]
    assert boundary["status"] == "blocked"
    assert boundary["ready"] is False
    assert boundary["summon_name"] == "Francis Lens Summon"
    assert boundary["config_path"] == "config/runtime/lens/summon.json"
    assert boundary["global_hotkey"] == "Ctrl+Alt+Space"
    assert boundary["binding_scope"] == "global"
    assert boundary["palette_route"] == "/lens/status"
    assert boundary["required_before_enable"] == [
        "resident_host_process",
        "tray_presence",
        "overlay_window",
        "global_hotkey_binding",
        "summon_binding",
    ]
    assert boundary["binding_enabled"] is False
    assert boundary["register_hotkey"] is False
    assert boundary["startup_register"] is False
    assert "lens_summon_binding_disabled_pending_authority" in boundary["blockers"]
    assert "summon_authority_not_granted" in boundary["blockers"]
    assert boundary["summon_binding_blockers"] == payload["direct_summon_preflight_binding_blockers"]
    assert boundary["authority_blockers"] == payload["direct_summon_preflight_authority_blockers"]

    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["summon_binding_family"]["status"] == "fifth_family_projected"
    assert checks["previous_global_hotkey_bridge"]["status"] == "previous_family_observed"
    assert checks["previous_global_hotkey_bridge_handoff_readback"]["status"] == "previous_handoff_observed"
    assert checks["summon_preflight_binding"]["status"] == "blocked_readback_ready"
    assert checks["handoff_alignment"]["status"] == "handoff_aligned"
    assert checks["side_effects_denied"]["status"] == "diagnostic_bounded"
    assert all(item["passed"] for item in payload["checks"])

    assert payload["governance"] == {
        "diagnostic_only": True,
        "wraps_summon_anywhere_blockers_proof": True,
        "wraps_summon_global_hotkey_binding_blocker_proof": True,
        "global_hotkey_previous_handoff_readback": True,
        "wraps_summon_preflight": True,
        "read_only_contract": True,
        "approval_request_write": False,
        "resident_runtime_execution_authority": False,
        "product_execution_authority": False,
        "execution_authority": False,
        "approval_decision_authority": False,
        "local_process_launch_authority": False,
        "process_supervision_authority": False,
        "process_restart_authority": False,
        "service_install_authority": False,
        "service_control_authority": False,
        "tray_registration_authority": False,
        "tray_icon_authority": False,
        "notification_authority": False,
        "hotkey_registration_authority": False,
        "overlay_control_authority": False,
        "window_management_authority": False,
        "capture_authority": False,
        "new_sensing_authority": False,
        "summon_authority": False,
        "memory_write": False,
        "receipt_write_authority": False,
        "resident_claim_authority": False,
        "mutation_authority_granted": False,
    }
