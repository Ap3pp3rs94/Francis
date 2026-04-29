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
            str(_repo_root() / "scripts" / "lens-live-operator-proof.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
        timeout=45,
    )


def test_lens_live_operator_proof_reads_status_over_http_without_authority() -> None:
    proc = _run_proof("-Mode", "Status", "-StartupTimeoutSeconds", "20")

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.live_operator_experience.proof"
    assert payload["status"] == "proof_passed"
    assert payload["ok"] is True
    assert payload["status_route"] == "/lens/status?limit=5"
    assert payload["live_http_status_readback"] is True
    assert payload["operator_experience_proof"] is True
    assert payload["helpful_not_noisy_readback"] is True
    assert payload["live_operator_experience_ready"] is False
    assert payload["ready_for_stage6_closure"] is False
    assert payload["resident_surface_ready"] is False
    assert payload["resident_claim_allowed"] is False
    assert payload["next_smallest_truthful_gap"] == "resident_host_or_resident_overlay_runtime"

    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["api_process_started"]["status"] == "started"
    assert checks["http_lens_status_readback"]["status"] == "readback_ready"
    assert checks["hud_runtime_readback"]["status"] == "readback_only"
    assert checks["command_palette_readback"]["status"] == "chat_ui_only"
    assert checks["mode_and_pilot_visibility"]["status"] == "readback_ready"
    assert checks["operator_views_readback"]["status"] == "readback_ready"
    assert checks["resident_claim_boundary"]["status"] == "blocked"
    assert checks["authority_boundary"]["status"] == "blocked"
    assert checks["helpful_not_noisy_boundary"]["status"] == "readback_ready"
    assert all(item["passed"] for item in payload["checks"])

    assert "resident_surface_missing" in payload["blockers"]
    assert "resident_host_process_missing" in payload["blockers"]
    assert "resident_overlay_runtime_missing" in payload["blockers"]
    assert "operator_experience_proof_missing" not in payload["blockers"]

    proof = payload["proof"]
    assert proof["api_pid"] > 0
    assert proof["lens_status"] in {"ready", "attention"}
    assert proof["hud_runtime_status"] == "readback_only"
    assert proof["hud_runtime_claim"] == "chat_ui_hud_readback_only"
    assert proof["command_total"] > 0
    assert proof["command_palette_availability"] == "chat_ui_only"
    assert proof["mode"]
    assert proof["pilot_status"]
    assert proof["receipt_status"] == "readback_ready"
    assert proof["resident_surface_activation_status"] == "blocked"

    assert payload["governance"] == {
        "diagnostic_only": True,
        "live_http_readback": True,
        "temporary_api_process": True,
        "temporary_runtime_state_write": True,
        "product_execution_authority": False,
        "execution_authority": False,
        "approval_decision_authority": False,
        "memory_write": False,
        "overlay_control_authority": False,
        "window_management_authority": False,
        "summon_authority": False,
        "capture_authority": False,
        "new_sensing_authority": False,
        "telemetry_authority": False,
        "local_process_launch_authority": False,
        "api_local_process_launch_authority": False,
        "service_install_authority": False,
        "service_control_authority": False,
        "hotkey_registration_authority": False,
        "tray_registration_authority": False,
        "mutation_authority_granted": False,
    }
