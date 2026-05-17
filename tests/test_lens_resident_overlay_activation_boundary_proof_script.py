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
            str(_repo_root() / "scripts" / "lens-resident-overlay-activation-boundary-proof.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
        timeout=320,
    )


def test_lens_resident_overlay_activation_boundary_supports_cached_overlay_runtime() -> None:
    script = (_repo_root() / "scripts" / "lens-resident-overlay-activation-boundary-proof.ps1").read_text(
        encoding="utf-8"
    )

    assert "[string]$CachedResidentOverlayRuntimeProofPath = ''" in script
    assert "Read-CachedJsonScriptResult -Path $CachedResidentOverlayRuntimeProofPath" in script
    assert "overlay_runtime_source = if ([bool](Get-PropertyValue -Payload $OverlayResult" in script


def test_lens_resident_overlay_activation_boundary_proof_blocks_activation_without_authority(
    tmp_path: Path,
) -> None:
    data_dir = tmp_path / "data"
    proc = _run_proof(
        "-Mode",
        "Status",
        "-StartupTimeoutSeconds",
        "5",
        "-SupervisorRunSeconds",
        "3",
        "-ResidentSurfaceForegroundRunSeconds",
        "2",
        "-DataDir",
        str(data_dir),
    )

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.resident_overlay_activation_boundary.proof"
    assert payload["status"] == "proof_passed"
    assert payload["ok"] is True
    assert payload["startup_timeout_seconds"] == 5
    assert payload["supervisor_run_seconds"] == 3
    assert payload["resident_surface_foreground_run_seconds"] == 2
    assert payload["live_operator_experience_proof"] is True
    assert payload["resident_overlay_boundary_observed"] is True
    assert payload["activation_boundary_observed"] is True
    assert payload["resident_overlay_activation_ready"] is False
    assert payload["activation_ready"] is False
    assert payload["resident_surface_ready"] is False
    assert payload["resident_overlay_runtime_ready"] is False
    assert payload["ready_for_lens_resident_claim"] is False
    assert payload["resident_claim_allowed"] is False
    assert payload["execution_ready"] is False
    assert payload["executed"] is False
    assert payload["applied"] is False
    assert payload["would_launch_process"] is False
    assert payload["would_install_service"] is False
    assert payload["would_start_service"] is False
    assert payload["would_register_hotkey"] is False
    assert payload["would_open_overlay"] is False
    assert payload["would_write_memory"] is False
    assert payload["would_decide_approval"] is False
    assert (
        payload["next_smallest_truthful_gap"]
        == "resident_overlay_activation_checkpoint_consumption_or_process_supervision_authority_boundary"
    )

    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["live_operator_readback_proof"]["status"] == "proof_passed"
    assert checks["resident_overlay_runtime_boundary"]["status"] == "boundary_observed"
    assert checks["activation_boundary_blocked"]["status"] == "blocked"
    assert checks["activation_plan_denied"]["status"] == "no_activation_actions"
    assert checks["authority_boundary"]["status"] == "diagnostic_bounded"
    assert all(item["passed"] for item in payload["checks"])

    proof = payload["proof"]
    assert proof["live_operator_source"] == "script_execution"
    assert proof["overlay_runtime_source"] == "script_execution"
    assert proof["live_operator_status"] == "proof_passed"
    assert proof["live_http_status_readback"] is True
    assert proof["helpful_not_noisy_readback"] is True
    assert proof["overlay_runtime_status"] == "proof_passed"
    assert proof["bounded_supervisor_observed"] is True
    assert proof["resident_overlay_runtime"] is False
    assert proof["overlay_window"] is False
    assert proof["tray_presence"] is False
    assert proof["global_hotkey_bound"] is False
    assert proof["summon_anywhere"] is False
    assert proof["activation_boundary_status"] == "blocked"
    assert proof["activation_preflight_status"] == "blocked"
    assert proof["activation_plan_status"] == "blocked"
    assert proof["activation_denial_status"] == "blocked"
    assert proof["activation_denial_reason"] == "local_process_launch_authority_not_granted"
    assert proof["selected_approval_approved"] is False
    assert proof["surface_status"] in {"blocked", "partial"}
    assert proof["summon_status"] == "blocked"
    assert proof["tray_status"] == "blocked"
    assert proof["overlay_status"] == "blocked"

    assert "resident_overlay_activation_not_authorized" in payload["blockers"]
    assert "resident_overlay_runtime_missing" in payload["blockers"]
    assert "resident_host_process_not_supervised" in payload["blockers"]
    assert "overlay_window_missing" in payload["blockers"]
    assert "tray_presence_missing" in payload["blockers"]
    assert "global_hotkey_binding_missing" in payload["blockers"]
    assert "summon_anywhere_missing" in payload["blockers"]
    assert "operator_experience_proof_missing" not in payload["blockers"]
    assert "live_operator_experience_proof_missing" not in payload["blockers"]

    assert payload["governance"] == {
        "diagnostic_only": True,
        "live_http_readback": True,
        "temporary_api_process": True,
        "resident_overlay_boundary_observed": True,
        "activation_boundary_observed": True,
        "bounded_host_launch": True,
        "bounded_process_launch": True,
        "bounded_supervisor_observation": True,
        "temporary_runtime_state_write": True,
        "product_execution_authority": False,
        "execution_authority": False,
        "approval_decision_authority": False,
        "memory_write": False,
        "resident_overlay_activation_authority": False,
        "overlay_control_authority": False,
        "window_management_authority": False,
        "summon_authority": False,
        "capture_authority": False,
        "new_sensing_authority": False,
        "telemetry_authority": False,
        "local_process_launch_authority": True,
        "activation_local_process_launch_authority": False,
        "api_local_process_launch_authority": False,
        "process_restart_authority": False,
        "process_supervision_authority": False,
        "service_install_authority": False,
        "service_control_authority": False,
        "hotkey_registration_authority": False,
        "tray_registration_authority": False,
        "tray_icon_authority": False,
        "notification_authority": False,
        "receipt_write_authority": False,
        "denial_receipt_write_authority": False,
        "mutation_authority_granted": False,
    }

    assert (data_dir / "runtime" / "lens-host" / "status.json").is_file()
    assert not (data_dir / "runtime" / "lens-host" / "lens-host.pid").exists()
