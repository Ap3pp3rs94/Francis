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
            str(_repo_root() / "scripts" / "lens-summon-tray-presence-blocker-proof.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
    )


def test_lens_summon_tray_presence_bridge_uses_resident_host_contract_readback() -> None:
    script = (_repo_root() / "scripts" / "lens-summon-tray-presence-blocker-proof.ps1").read_text(encoding="utf-8")

    assert "blocked_family_handoffs[resident_host]" in script
    assert "$ResidentHostBridgeScript" not in script
    assert "-ConsumeProcessSupervisionHandoff" not in script
    assert "$ResidentHostBridgeForegroundRunSeconds" not in script
    assert "$ResidentHostBridgeHostLaunchRunSeconds" not in script
    assert "$ResidentHostBridgeSupervisorRunSeconds" not in script


def test_lens_summon_tray_presence_blocker_proof_is_readback_only(tmp_path: Path) -> None:
    proc = _run_proof("-Mode", "Status", "-DataDir", str(tmp_path / "data"))

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.summon_tray_presence_blocker.proof"
    assert payload["status"] == "proof_passed"
    assert payload["ok"] is True
    assert payload["stage"] == "Stage 6 / Lens MVP"
    assert payload["stage_state"] == "active"
    assert payload["acceptance_criterion"] == "summon_anywhere"
    assert payload["previous_summon_blocker_family"] == "resident_host"
    assert payload["summon_tray_presence_blocker_family"] == "tray_presence"
    assert payload["second_summon_blocker_family"] == "tray_presence"
    assert payload["next_summon_blocker_family"] == "overlay_window"
    assert payload["summon_next_smallest_truthful_gap"] == "summon_anywhere_blockers"
    assert payload["resident_runtime_next_smallest_truthful_gap"] == (
        "resident_runtime_hotkey_summon_authority_boundary"
    )
    assert payload["next_smallest_truthful_gap"] == "summon_overlay_window_blocker_boundary"
    assert payload["summon_tray_family_observed"] is True
    assert payload["previous_resident_host_contract_observed"] is True
    assert payload["previous_resident_host_contract_readback_observed"] is True
    previous_contract = payload["previous_resident_host_contract"]
    assert previous_contract["source"] == "summon_anywhere_blockers.blocked_family_handoffs"
    assert previous_contract["status"] == "contract_projected"
    assert previous_contract["contract_status"] == "blocked"
    assert previous_contract["proof_script"] == "scripts/lens-summon-resident-host-blocker-proof.ps1 -Mode Status"
    assert previous_contract["previous_summon_blocker_family"] == ""
    assert previous_contract["summon_resident_host_blocker_family"] == "resident_host"
    assert previous_contract["next_summon_blocker_family"] == "tray_presence"
    assert previous_contract["summon_next_smallest_truthful_gap"] == "summon_anywhere_blockers"
    assert previous_contract["next_smallest_truthful_gap"] == "resident_host_runtime_blocker_boundary"
    assert previous_contract["route"] == "/lens/host"
    assert previous_contract["readiness_route"] == "/lens/host/runtime-loop/readiness"
    assert previous_contract["authority_required"] == "resident_runtime_execution_authority"
    assert previous_contract["authority_granted"] is False
    assert previous_contract["read_only_contract"] is True
    assert previous_contract["diagnostic_only"] is True
    assert previous_contract["would_execute"] is False
    assert previous_contract["would_mutate"] is False
    assert previous_contract["handoff_aligned"] is True
    assert previous_contract["side_effects_denied"] is True
    assert previous_contract["blockers"] == ["local_process_launch_authority_not_granted"]
    assert payload["tray_presence_boundary_observed"] is True
    assert payload["handoff_aligned"] is True
    assert payload["side_effects_denied"] is True
    assert payload["summon_tray_presence_blockers"] == ["tray_host_missing"]

    runtime_blockers = payload["resident_runtime_tray_presence_blockers"]
    assert "lens_tray_presence_disabled_pending_authority" in runtime_blockers
    assert "tray_host_missing" in runtime_blockers
    assert "tray_host_disabled" in runtime_blockers
    assert "tray_registration_authority_not_granted" in runtime_blockers
    assert "tray_icon_authority_not_granted" in runtime_blockers
    assert "notification_authority_not_granted" in runtime_blockers

    boundary = payload["tray_presence_boundary"]
    assert boundary["status"] == "proof_passed"
    assert boundary["authority_family"] == "tray_presence"
    assert boundary["previous_authority_family"] == "service_control"
    assert boundary["next_authority_family"] == "hotkey_summon"
    assert boundary["tray_presence_boundary_observed"] is True
    assert boundary["tray_preflight_observed"] is True
    assert boundary["side_effects_denied"] is True
    assert boundary["third_authority_family_consumed"] is True
    assert boundary["route"] == "/lens/tray"
    assert boundary["tray_preflight_status"] == "blocked"
    assert boundary["tray_preflight_presence_name"] == "Francis Lens Tray Presence"
    assert boundary["tray_preflight_config_path"] == "config/runtime/lens/tray.json"
    assert boundary["blockers"] == runtime_blockers

    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["summon_tray_presence_family"]["status"] == "second_family_projected"
    assert checks["previous_resident_host_contract"]["status"] == "previous_family_contract_observed"
    assert checks["previous_resident_host_contract_readback"]["status"] == "previous_contract_readback_observed"
    assert checks["tray_presence_boundary"]["status"] == "blocked_readback_ready"
    assert checks["handoff_alignment"]["status"] == "handoff_aligned"
    assert checks["side_effects_denied"]["status"] == "diagnostic_bounded"
    assert all(item["passed"] for item in payload["checks"])

    assert payload["governance"] == {
        "diagnostic_only": True,
        "wraps_summon_anywhere_blockers_proof": True,
        "wraps_summon_resident_host_blocker_proof": False,
        "uses_resident_host_family_contract_readback": True,
        "resident_host_contract_readback": True,
        "wraps_resident_runtime_tray_presence_boundary_proof": True,
        "tray_preflight_readback": True,
        "read_only_contract": True,
        "wrapped_resident_runtime_approval_request_write": True,
        "wrapped_resident_runtime_execution_authority": True,
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
        "summon_authority": False,
        "capture_authority": False,
        "new_sensing_authority": False,
        "memory_write": False,
        "receipt_write_authority": False,
        "resident_claim_authority": False,
        "mutation_authority_granted": False,
    }
