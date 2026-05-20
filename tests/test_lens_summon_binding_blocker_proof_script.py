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


def test_lens_summon_binding_blocker_uses_global_hotkey_family_contract() -> None:
    script = (_repo_root() / "scripts" / "lens-summon-binding-blocker-proof.ps1").read_text(
        encoding="utf-8",
    )

    assert "GlobalHotkeyBridgeScript" not in script
    assert "GlobalHotkeyBridgeResult" not in script
    assert "uses_global_hotkey_family_contract_readback" in script
    assert "blocked_family_handoffs[global_hotkey_binding]" in script


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
    assert payload["recommended_handoff_source"] == "summon_binding_handoff"
    assert payload["recommended_next_slice"] == "run_summon_authority_blocker_proof"
    assert payload["recommended_proof_script"] == "scripts/lens-summon-authority-blocker-proof.ps1 -Mode Status"
    assert payload["recommended_route"] == "/lens/summon"
    assert payload["recommended_readiness_route"] == "/lens/summon/readiness"
    assert payload["authority_required"] == "summon_hotkey_overlay_and_process_authority"
    assert payload["authority_granted"] is False
    recommended_handoff = payload["recommended_handoff"]
    assert recommended_handoff["id"] == "authority"
    assert recommended_handoff["next_step"] == "run_summon_authority_blocker_proof"
    assert recommended_handoff["proof_script"] == "scripts/lens-summon-authority-blocker-proof.ps1 -Mode Status"
    assert recommended_handoff["next_smallest_truthful_gap"] == "summon_authority_blocker_boundary"
    assert recommended_handoff["authority_required"] == "summon_hotkey_overlay_and_process_authority"
    assert recommended_handoff["authority_granted"] is False
    assert recommended_handoff["read_only_contract"] is True
    assert recommended_handoff["diagnostic_only"] is True
    assert recommended_handoff["would_execute"] is False
    assert recommended_handoff["would_mutate"] is False
    assert payload["summon_binding_family_observed"] is True
    assert payload["previous_global_hotkey_contract_observed"] is True
    assert payload["previous_global_hotkey_contract_readback_observed"] is True
    previous_global_hotkey = payload["previous_global_hotkey_handoff"]
    assert previous_global_hotkey["source"] == "summon_anywhere_blockers.blocked_family_handoffs"
    assert previous_global_hotkey["status"] == "contract_projected"
    assert previous_global_hotkey["contract_status"] == "blocked"
    assert previous_global_hotkey["proof_script"] == (
        "scripts/lens-summon-global-hotkey-binding-blocker-proof.ps1 -Mode Status"
    )
    assert previous_global_hotkey["previous_summon_blocker_family"] == "overlay_window"
    assert previous_global_hotkey["summon_global_hotkey_binding_blocker_family"] == "global_hotkey_binding"
    assert previous_global_hotkey["next_summon_blocker_family"] == "summon_binding"
    assert previous_global_hotkey["next_smallest_truthful_gap"] == "summon_binding_blocker_boundary"
    assert previous_global_hotkey["authority_required"] == "hotkey_registration_authority"
    assert previous_global_hotkey["authority_granted"] is False
    assert previous_global_hotkey["read_only_contract"] is True
    assert previous_global_hotkey["diagnostic_only"] is True
    assert previous_global_hotkey["would_execute"] is False
    assert previous_global_hotkey["would_mutate"] is False
    assert previous_global_hotkey["handoff_aligned"] is True
    assert previous_global_hotkey["side_effects_denied"] is True
    assert previous_global_hotkey["blockers"] == [
        "global_hotkey_binding_disabled",
        "global_hotkey_registration_disabled",
        "hotkey_registration_authority_not_granted",
    ]
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
    assert checks["previous_global_hotkey_contract"]["status"] == "previous_family_contract_observed"
    assert checks["previous_global_hotkey_contract_readback"]["status"] == "previous_contract_readback_observed"
    assert checks["summon_preflight_binding"]["status"] == "blocked_readback_ready"
    assert checks["handoff_alignment"]["status"] == "handoff_aligned"
    assert checks["side_effects_denied"]["status"] == "diagnostic_bounded"
    assert all(item["passed"] for item in payload["checks"])

    assert payload["governance"] == {
        "diagnostic_only": True,
        "wraps_summon_anywhere_blockers_proof": True,
        "wraps_summon_global_hotkey_binding_blocker_proof": False,
        "uses_global_hotkey_family_contract_readback": True,
        "global_hotkey_contract_readback": True,
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
