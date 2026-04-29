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
            str(_repo_root() / "scripts" / "lens-resident-surface-proof.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
    )


def test_lens_resident_surface_proof_composes_blocked_surface_without_authority() -> None:
    proc = _run_proof("-Mode", "Status")

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.resident_surface.readiness_proof"
    assert payload["status"] == "proof_passed"
    assert payload["ok"] is True
    assert payload["resident_surface_ready"] is False
    assert payload["ready_for_lens_resident_claim"] is False
    assert payload["resident_claim_allowed"] is False
    assert payload["resident_host_process"] is False
    assert payload["tray_presence"] is False
    assert payload["tray_icon"] is False
    assert payload["overlay_window"] is False
    assert payload["global_hotkey_bound"] is False
    assert payload["summon_anywhere"] is False
    assert payload["operator_experience_proof"] is False
    assert (
        payload["next_smallest_truthful_gap"]
        == "resident_surface_activation_boundary_or_live_operator_experience_proof"
    )

    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["host_lifecycle_boundary"]["status"] == "blocked_readback_ready"
    assert checks["supervision_proof_available"]["status"] == "available"
    assert checks["tray_presence_preflight"]["status"] == "blocked_disabled"
    assert checks["overlay_window_preflight"]["status"] == "blocked_disabled"
    assert checks["summon_binding_preflight"]["status"] == "blocked_disabled"
    assert checks["authority_boundary"]["status"] == "blocked"
    assert checks["resident_claim_boundary"]["status"] == "blocked"
    assert all(item["passed"] for item in payload["checks"])

    proof = payload["proof"]
    assert proof["host_lifecycle_status"] == "blocked"
    assert proof["supervision_proof_available"] is True
    assert proof["tray_status"] == "blocked"
    assert proof["overlay_status"] == "blocked"
    assert proof["summon_status"] == "blocked"
    assert proof["tray_host_enabled"] is False
    assert proof["tray_icon_enabled"] is False
    assert proof["overlay_window_enabled"] is False
    assert proof["overlay_focus_supported"] is False
    assert proof["global_hotkey"] == "Ctrl+Alt+Space"
    assert proof["summon_binding_enabled"] is False
    assert proof["hotkey_registration_enabled"] is False
    assert "tray_host_disabled" in proof["tray_blockers"]
    assert "overlay_window_disabled" in proof["overlay_blockers"]
    assert "global_hotkey_binding_disabled" in proof["summon_blockers"]

    assert "resident_surface_missing" in payload["blockers"]
    assert "tray_presence_missing" in payload["blockers"]
    assert "overlay_window_missing" in payload["blockers"]
    assert "summon_anywhere_missing" in payload["blockers"]
    assert "operator_experience_proof_missing" in payload["blockers"]

    assert payload["governance"] == {
        "read_only_contract": True,
        "diagnostic_only": True,
        "bounded_foreground_session": False,
        "temporary_runtime_state_write": False,
        "product_execution_authority": False,
        "execution_authority": False,
        "approval_decision_authority": False,
        "memory_write": False,
        "overlay_control_authority": False,
        "window_management_authority": False,
        "summon_authority": False,
        "capture_authority": False,
        "new_sensing_authority": False,
        "local_process_launch_authority": False,
        "api_local_process_launch_authority": False,
        "service_install_authority": False,
        "service_control_authority": False,
        "hotkey_registration_authority": False,
        "tray_registration_authority": False,
        "tray_icon_authority": False,
        "notification_authority": False,
        "mutation_authority_granted": False,
    }
