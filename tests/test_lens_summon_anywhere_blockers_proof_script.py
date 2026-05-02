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
            str(_repo_root() / "scripts" / "lens-summon-anywhere-blockers-proof.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
    )


def test_lens_summon_anywhere_blockers_proof_is_readback_only() -> None:
    proc = _run_proof("-Mode", "Status")

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.summon_anywhere_blockers.proof"
    assert payload["status"] == "proof_passed"
    assert payload["ok"] is True
    assert payload["stage"] == "Stage 6 / Lens MVP"
    assert payload["stage_state"] == "active"
    assert payload["acceptance_criterion"] == "summon_anywhere"
    assert payload["next_smallest_truthful_gap"] == "summon_anywhere_blockers"
    assert payload["summon_preflight_observed"] is True
    assert payload["stage6_family_projection_observed"] is True
    assert payload["side_effects_denied"] is True
    assert payload["first_blocker_family"] == "resident_host"
    assert payload["blocked_families"] == [
        "resident_host",
        "tray_presence",
        "overlay_window",
        "global_hotkey_binding",
        "summon_binding",
        "authority",
    ]

    blocker_groups = payload["blocker_groups"]
    assert blocker_groups["resident_host"] == ["local_process_launch_authority_not_granted"]
    assert blocker_groups["tray_presence"] == ["tray_host_missing"]
    assert blocker_groups["overlay_window"] == ["overlay_window_missing"]
    assert blocker_groups["global_hotkey_binding"] == [
        "global_hotkey_binding_disabled",
        "global_hotkey_registration_disabled",
        "hotkey_registration_authority_not_granted",
    ]
    assert blocker_groups["summon_binding"] == [
        "lens_summon_binding_not_implemented",
        "summon_authority_not_granted",
    ]
    assert blocker_groups["authority"] == [
        "summon_authority_not_granted",
        "hotkey_registration_authority_not_granted",
        "overlay_control_authority_not_granted",
        "local_process_launch_authority_not_granted",
    ]

    summon_preflight = payload["summon_preflight"]
    assert summon_preflight["status"] == "blocked"
    assert summon_preflight["ready"] is False
    assert summon_preflight["summon_name"] == "Francis Lens Summon"
    assert summon_preflight["config_path"] == "config/runtime/lens/summon.json"
    assert summon_preflight["global_hotkey"] == "Ctrl+Alt+Space"
    assert summon_preflight["binding_scope"] == "global"
    assert summon_preflight["palette_route"] == "/lens/status"
    assert summon_preflight["required_before_enable"] == [
        "resident_host_process",
        "tray_presence",
        "overlay_window",
        "global_hotkey_binding",
        "summon_binding",
    ]

    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["summon_preflight_readback"]["status"] == "blocked_readback_ready"
    assert checks["stage6_family_projection"]["status"] == "blocked_families_projected"
    assert checks["summon_side_effects_denied"]["status"] == "diagnostic_bounded"
    assert all(item["passed"] for item in payload["checks"])

    assert payload["governance"] == {
        "diagnostic_only": True,
        "wraps_summon_preflight": True,
        "read_only_contract": True,
        "product_execution_authority": False,
        "execution_authority": False,
        "approval_decision_authority": False,
        "memory_write": False,
        "overlay_control_authority": False,
        "summon_authority": False,
        "capture_authority": False,
        "new_sensing_authority": False,
        "local_process_launch_authority": False,
        "hotkey_registration_authority": False,
        "mutation_authority_granted": False,
    }
