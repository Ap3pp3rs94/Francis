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
            str(_repo_root() / "scripts" / "lens-resident-runtime-tray-presence-boundary-proof.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
    )


def test_lens_resident_runtime_tray_presence_boundary_is_readback_only() -> None:
    proc = _run_proof("-Mode", "Status")

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.resident_runtime.tray_presence_boundary.proof"
    assert payload["status"] == "proof_passed"
    assert payload["ok"] is True
    assert payload["authority_family"] == "tray_presence"
    assert payload["previous_authority_family"] == "service_control"
    assert payload["next_authority_family"] == "hotkey_summon"
    assert payload["tray_presence_boundary_observed"] is True
    assert payload["previous_service_control_family_observed"] is True
    assert payload["tray_preflight_observed"] is True
    assert payload["authority_blockers_proof_observed"] is True
    assert payload["side_effects_denied"] is True
    assert payload["third_authority_family_consumed"] is True
    assert payload["resident_runtime_execution_authority"] is True
    assert payload["local_process_launch_authority"] is False
    assert payload["process_supervision_authority"] is False
    assert payload["process_restart_authority"] is False
    assert payload["service_install_authority"] is False
    assert payload["service_control_authority"] is False
    assert payload["tray_registration_authority"] is False
    assert payload["tray_icon_authority"] is False
    assert payload["notification_authority"] is False
    assert payload["resident_claim_authority"] is False
    assert payload["would_launch_process"] is False
    assert payload["would_supervise_process"] is False
    assert payload["would_restart_process"] is False
    assert payload["would_install_service"] is False
    assert payload["would_start_service"] is False
    assert payload["would_register_tray"] is False
    assert payload["would_register_hotkey"] is False
    assert payload["would_open_overlay"] is False
    assert payload["would_write_memory"] is False
    assert payload["would_claim_resident"] is False

    tray_presence = payload["tray_presence"]
    assert tray_presence["status"] == "blocked"
    assert tray_presence["ready"] is False
    assert tray_presence["authority_granted"] is False
    assert tray_presence["would_execute"] is False
    assert tray_presence["route"] == "/lens/tray"
    assert "/lens/tray" in tray_presence["evidence"]
    assert tray_presence["required_before"] == ["resident_claim"]
    assert "tray_registration_authority_not_granted" in tray_presence["blockers"]
    assert "tray_icon_authority_not_granted" in tray_presence["blockers"]
    assert "notification_authority_not_granted" in tray_presence["blockers"]
    assert "tray_host_disabled" in tray_presence["blockers"]
    assert payload["blockers"] == tray_presence["blockers"]

    tray_preflight = payload["tray_preflight"]
    assert tray_preflight["status"] == "blocked"
    assert tray_preflight["ready"] is False
    assert tray_preflight["presence_name"] == "Francis Lens Tray Presence"
    assert tray_preflight["config_path"] == "config/runtime/lens/tray.json"
    assert tray_preflight["tray_scope"] == "user_session"
    assert "tray_registration_authority_not_granted" in tray_preflight["blockers"]
    assert "tray_icon_authority_not_granted" in tray_preflight["blockers"]
    assert "notification_authority_not_granted" in tray_preflight["blockers"]

    assert payload["remaining_authority_families"] == [
        "process_supervision",
        "service_control",
        "tray_presence",
        "hotkey_summon",
        "overlay_window",
        "resident_claim",
    ]
    assert payload["remaining_authority_families_after_this_boundary"] == [
        "hotkey_summon",
        "overlay_window",
        "resident_claim",
    ]
    assert payload["next_smallest_truthful_gap"] == "resident_runtime_hotkey_summon_authority_boundary"

    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["resident_runtime_authority_blockers_proof"]["status"] == "proof_observed"
    assert checks["previous_service_control_family"]["status"] == "blocked"
    assert checks["tray_preflight_readback"]["status"] == "blocked_readback_ready"
    assert checks["tray_presence_family"]["status"] == "blocked"
    assert checks["tray_presence_side_effects_denied"]["status"] == "denied_no_tray_presence"
    assert checks["authority_boundary"]["status"] == "diagnostic_bounded"
    assert all(item["passed"] for item in payload["checks"])

    assert payload["governance"] == {
        "diagnostic_only": True,
        "wraps_existing_authority_blockers_proof": True,
        "tray_preflight_readback": True,
        "approval_request_write": True,
        "resident_runtime_execution_authority": True,
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
        "memory_write": False,
        "receipt_write_authority": False,
        "resident_claim_authority": False,
        "mutation_authority_granted": False,
    }
