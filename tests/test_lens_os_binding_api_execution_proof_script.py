from __future__ import annotations

import json
import os
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


def _run_proof(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            _powershell(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(_repo_root() / "scripts" / "lens-os-binding-api-execution-proof.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
        timeout=300,
    )


def test_lens_os_binding_api_execution_proof_uses_governed_routes() -> None:
    script = (_repo_root() / "scripts" / "lens-os-binding-api-execution-proof.ps1").read_text(encoding="utf-8")

    assert '"/lens/host/supervision/authority/request"' in script
    assert '"/lens/resident-runtime/authority-grant/request"' in script
    assert '"/lens/resident-runtime/execute"' in script
    assert '"/lens/tray/authority/request"' in script
    assert '"/lens/tray/execute"' in script
    assert '"/lens/os-binding/authority/request"' in script
    assert '"/lens/os-binding/authority"' in script
    assert '"/lens/os-binding/execute"' in script
    assert '"/lens/os-binding/executions?limit=10"' in script
    assert '"/lens/host/supervision/execute"' in script
    assert '"mode": "stop"' in script
    assert '"mode": "resident_stop"' in script
    assert '"overlay_control_authority": False' in script
    assert '"summon_authority": False' in script
    assert '"resident_claim_authority": False' in script


def test_lens_os_binding_api_execution_proof_starts_and_stops_real_hotkey_runtime(
    tmp_path: Path,
) -> None:
    if platform.system() != "Windows":
        pytest.skip("Live Lens OS-binding API execution proof is Windows-hosted.")
    if os.environ.get("CI", "").lower() == "true":
        pytest.skip("Live OS hotkey proof requires an interactive Windows user session.")

    data_dir = tmp_path / "data"
    proc = _run_proof(
        "-Mode",
        "Status",
        "-RunSeconds",
        "5",
        "-DataDir",
        str(data_dir),
    )

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.os_binding.api_execution.proof"
    assert payload["status"] == "proof_passed"
    assert payload["ok"] is True
    assert payload["stage"] == "Stage 6 / Lens MVP"
    assert payload["stage_state"] == "active"
    assert payload["acceptance_criterion"] == "summon_anywhere"
    assert payload["previous_next_smallest_truthful_gap"] == "os_level_command_palette_binding"
    assert payload["route_next_smallest_truthful_gap"] == "summon_binding"
    assert payload["next_smallest_truthful_gap"] == "summon_overlay_window_blocker_boundary"
    assert (
        payload["recommended_next_slice"] == "prove_governed_overlay_window_api_execution_after_global_hotkey_binding"
    )
    assert payload["recommended_proof_script"] == "scripts/lens-summon-overlay-window-blocker-proof.ps1 -Mode Status"
    assert payload["recommended_handoff_source"] == "api_os_binding_execution_overlay_window_handoff"
    assert payload["recommended_handoff"]["id"] == "overlay_window"
    assert payload["recommended_handoff"]["would_execute"] is False
    assert payload["recommended_handoff"]["would_mutate"] is False

    assert payload["host_supervision_authority_grant_receipt_id"]
    assert payload["resident_runtime_authority_grant_receipt_id"]
    assert payload["tray_authority_grant_receipt_id"]
    assert payload["os_binding_authority_grant_receipt_id"]
    assert payload["resident_runtime_execution_authority"] is True
    assert payload["host_supervision_authority"] is True
    assert payload["tray_presence_authority"] is True
    assert payload["os_binding_authority"] is True
    assert payload["execution_applied"] is True
    assert payload["executed"] is True
    assert payload["resident_host_process_started"] is True
    assert payload["resident_supervised_runtime_started"] is True
    assert payload["tray_presence_started"] is True
    assert payload["tray_runtime_ready"] is True
    assert payload["global_hotkey_bound"] is True
    assert payload["hotkey_runtime_ready"] is True
    assert payload["os_level_command_palette"] is True
    assert payload["hotkey_stop_observed"] is True
    assert payload["tray_presence_stop_observed"] is True
    assert payload["resident_supervision_stop_observed"] is True
    assert payload["hotkey_pid_file_present_after_start"] is True
    assert payload["hotkey_pid_file_present_after_stop"] is False
    assert payload["tray_pid_file_present_after_stop"] is False
    assert payload["host_pid_file_present_after_stop"] is False
    assert payload["required_before_enable_after_hotkey"] == ["overlay_window", "summon_binding"]
    assert payload["overlay_window"] is False
    assert payload["summon_anywhere"] is False
    assert payload["service_managed"] is False
    assert payload["resident_claim_allowed"] is False

    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["host_supervision_authority_granted"]["status"] == "authority_granted"
    assert checks["resident_runtime_authority_granted"]["status"] == "authority_granted"
    assert checks["resident_runtime_started_before_os_binding"]["status"] == "resident_supervision_started"
    assert checks["tray_presence_started_before_os_binding"]["status"] == "tray_presence_started"
    assert checks["os_binding_authority_granted"]["status"] == "authority_granted"
    assert checks["readiness_blocked_until_hotkey_runtime"]["status"] == "blocked"
    assert checks["api_execute_bound_real_global_hotkey"]["status"] == "global_hotkey_bound"
    assert checks["status_plan_consumed_live_hotkey_runtime"]["status"] == "overlay_window"
    assert checks["os_binding_receipt_readback_after_start"]["status"] == "readback_ready"
    assert checks["readiness_observed_os_level_palette_after_start"]["status"] == "ready"
    assert checks["api_stop_cleaned_real_global_hotkey"]["status"] == "global_hotkey_binding_stopped"
    assert checks["api_stop_cleaned_real_tray_presence"]["status"] == "tray_presence_stopped"
    assert checks["resident_supervision_stop_observed"]["status"] == "resident_supervision_stopped"
    assert checks["authority_boundaries_intact"]["status"] == "bounded"
    assert all(item["passed"] for item in payload["checks"])
    assert payload["blockers"] == ["overlay_window_missing", "summon_binding_missing"]

    proof = payload["proof"]
    assert proof["resident_start_status"] == "resident_supervision_started"
    assert proof["tray_start_status"] == "tray_presence_started"
    assert proof["hotkey_start_status"] == "global_hotkey_bound"
    assert proof["hotkey_runtime_status_after_start"] == "hotkey_bound"
    assert proof["hotkey_runtime_pid_after_start"] > 0
    assert proof["hotkey_stop_status"] == "global_hotkey_binding_stopped"
    assert proof["hotkey_runtime_status_after_stop"] == "hotkey_stopped"
    assert proof["tray_stop_status"] == "tray_presence_stopped"
    assert proof["resident_stop_status"] == "resident_supervision_stopped"
    assert proof["os_binding_receipt_readback_status"] == "readback_ready"
    assert proof["os_binding_receipt_readback_next_gap"] == "summon_binding"
    assert proof["persistent_plan_first_missing_after_hotkey"] == "overlay_window"

    assert payload["start_execution"] == {
        "status": "global_hotkey_bound",
        "next_smallest_truthful_gap": "summon_binding",
        "global_hotkey_binding": True,
        "hotkey_runtime_ready": True,
        "os_level_command_palette": True,
        "launch_on_hotkey": False,
        "stop_command": "scripts/lens-hotkey-binding.ps1 -Mode Stop",
    }
    assert payload["stop_execution"] == {
        "status": "global_hotkey_binding_stopped",
        "global_hotkey_binding": False,
        "hotkey_runtime_ready": False,
    }
    assert payload["governance"] == {
        "diagnostic_only": True,
        "api_route_proof": True,
        "api_execution_authority": True,
        "approval_request_write": True,
        "test_fixture_approval_decisions": True,
        "approval_decision_authority": False,
        "product_execution_authority": False,
        "execution_authority": True,
        "temporary_runtime_state_write": True,
        "local_process_launch_authority": True,
        "process_supervision_authority": True,
        "process_restart_authority": False,
        "service_install_authority": False,
        "service_control_authority": False,
        "tray_registration_authority": True,
        "tray_icon_authority": True,
        "hotkey_registration_authority": True,
        "overlay_control_authority": False,
        "summon_authority": False,
        "capture_authority": False,
        "new_sensing_authority": False,
        "memory_write": False,
        "resident_claim_authority": False,
        "mutation_authority_granted": True,
    }

    assert not (data_dir / "runtime" / "lens-hotkey" / "lens-hotkey.pid").exists()
    assert not (data_dir / "runtime" / "lens-tray" / "lens-tray.pid").exists()
    assert not (data_dir / "runtime" / "lens-host" / "lens-host.pid").exists()
