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
            str(_repo_root() / "scripts" / "lens-overlay-api-execution-proof.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
        timeout=360,
    )


def test_lens_overlay_api_execution_proof_uses_governed_routes() -> None:
    script = (_repo_root() / "scripts" / "lens-overlay-api-execution-proof.ps1").read_text(encoding="utf-8")

    assert '"/lens/host/supervision/authority/request"' in script
    assert '"/lens/resident-runtime/authority-grant/request"' in script
    assert '"/lens/resident-runtime/execute"' in script
    assert '"/lens/tray/authority/request"' in script
    assert '"/lens/tray/execute"' in script
    assert '"/lens/os-binding/authority/request"' in script
    assert '"/lens/os-binding/execute"' in script
    assert '"/lens/overlay/authority/request"' in script
    assert '"/lens/overlay/authority"' in script
    assert '"/lens/overlay/execute"' in script
    assert '"/lens/overlay/executions?limit=10"' in script
    assert '"/lens/host/supervision/execute"' in script
    assert '"mode": "stop"' in script
    assert '"mode": "resident_stop"' in script
    assert '"/lens/summon/execute"' not in script
    assert '"summon_authority": False' in script
    assert '"resident_claim_authority": False' in script


def test_lens_overlay_api_execution_proof_starts_and_stops_real_overlay_runtime(
    tmp_path: Path,
) -> None:
    if platform.system() != "Windows":
        pytest.skip("Live Lens overlay API execution proof is Windows-hosted.")
    if os.environ.get("CI", "").lower() == "true":
        pytest.skip("Live overlay proof requires an interactive Windows user session.")

    data_dir = tmp_path / "data"
    proc = _run_proof(
        "-Mode",
        "Status",
        "-RunSeconds",
        "10",
        "-DataDir",
        str(data_dir),
    )

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.overlay.api_execution.proof"
    assert payload["status"] == "proof_passed"
    assert payload["ok"] is True
    assert payload["stage"] == "Stage 6 / Lens MVP"
    assert payload["stage_state"] == "active"
    assert payload["acceptance_criterion"] == "summon_anywhere"
    assert payload["previous_next_smallest_truthful_gap"] == "summon_overlay_window_blocker_boundary"
    assert payload["route_next_smallest_truthful_gap"] == "summon_anywhere_blockers"
    assert payload["next_smallest_truthful_gap"] == "summon_binding_blocker_boundary"
    assert payload["recommended_next_slice"] == "prove_governed_summon_api_execution_after_overlay_window"
    assert payload["recommended_proof_script"] == "scripts/lens-summon-api-execution-proof.ps1 -Mode Status"
    assert payload["recommended_handoff_source"] == "api_overlay_execution_summon_binding_handoff"
    assert payload["recommended_handoff"]["id"] == "summon_binding"
    assert payload["recommended_handoff"]["would_execute"] is False
    assert payload["recommended_handoff"]["would_mutate"] is False

    assert payload["host_supervision_authority_grant_receipt_id"]
    assert payload["resident_runtime_authority_grant_receipt_id"]
    assert payload["tray_authority_grant_receipt_id"]
    assert payload["os_binding_authority_grant_receipt_id"]
    assert payload["overlay_authority_grant_receipt_id"]
    assert payload["resident_runtime_execution_authority"] is True
    assert payload["host_supervision_authority"] is True
    assert payload["tray_presence_authority"] is True
    assert payload["os_binding_authority"] is True
    assert payload["overlay_authority"] is True
    assert payload["execution_applied"] is True
    assert payload["executed"] is True
    assert payload["resident_host_process_started"] is True
    assert payload["resident_supervised_runtime_started"] is True
    assert payload["tray_presence_started"] is True
    assert payload["tray_runtime_ready"] is True
    assert payload["global_hotkey_bound"] is True
    assert payload["hotkey_runtime_ready"] is True
    assert payload["overlay_window_started"] is True
    assert payload["overlay_runtime_ready"] is True
    assert payload["overlay_window_visible"] is True
    assert payload["overlay_always_on_top"] is True
    assert payload["overlay_stop_observed"] is True
    assert payload["hotkey_stop_observed"] is True
    assert payload["tray_presence_stop_observed"] is True
    assert payload["resident_supervision_stop_observed"] is True
    assert payload["overlay_pid_file_present_after_start"] is True
    assert payload["overlay_pid_file_present_after_stop"] is False
    assert payload["hotkey_pid_file_present_after_stop"] is False
    assert payload["tray_pid_file_present_after_stop"] is False
    assert payload["host_pid_file_present_after_stop"] is False
    assert payload["required_before_enable_after_overlay"] == ["summon_binding"]
    assert payload["blockers"] == ["summon_binding_missing"]
    assert payload["summon_anywhere"] is False
    assert payload["service_managed"] is False
    assert payload["resident_claim_allowed"] is False

    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["host_supervision_authority_granted"]["status"] == "authority_granted"
    assert checks["resident_runtime_started_before_overlay"]["status"] == "resident_supervision_started"
    assert checks["tray_and_hotkey_started_before_overlay"]["status"] == "ready"
    assert checks["overlay_authority_granted"]["status"] == "authority_granted"
    assert checks["api_execute_started_real_overlay_window"]["status"] == "overlay_window_started"
    assert checks["status_plan_consumed_live_overlay_runtime"]["status"] == "summon_binding"
    assert checks["overlay_receipt_readback_after_start"]["status"] == "readback_ready"
    assert checks["overlay_readiness_observed_after_start"]["status"] == "blocked"
    assert checks["api_stop_cleaned_real_overlay_window"]["status"] == "overlay_window_stopped"
    assert checks["api_stop_cleaned_real_global_hotkey"]["status"] == "global_hotkey_binding_stopped"
    assert checks["api_stop_cleaned_real_tray_presence"]["status"] == "tray_presence_stopped"
    assert checks["resident_supervision_stop_observed"]["status"] == "resident_supervision_stopped"
    assert checks["authority_boundaries_intact"]["status"] == "bounded"
    assert all(item["passed"] for item in payload["checks"])

    proof = payload["proof"]
    assert proof["resident_start_status"] == "resident_supervision_started"
    assert proof["tray_start_status"] == "tray_presence_started"
    assert proof["hotkey_start_status"] == "global_hotkey_bound"
    assert proof["overlay_start_status"] == "overlay_window_started"
    assert proof["overlay_runtime_status_after_start"] == "overlay_running"
    assert proof["overlay_runtime_pid_after_start"] > 0
    assert proof["overlay_stop_status"] == "overlay_window_stopped"
    assert proof["overlay_runtime_status_after_stop"] == "overlay_stopped"
    assert proof["hotkey_stop_status"] == "global_hotkey_binding_stopped"
    assert proof["tray_stop_status"] == "tray_presence_stopped"
    assert proof["resident_stop_status"] == "resident_supervision_stopped"
    assert proof["overlay_receipt_readback_status"] == "readback_ready"
    assert proof["overlay_receipt_readback_next_gap"] == "summon_anywhere_blockers"
    assert proof["persistent_plan_first_missing_after_overlay"] == "summon_binding"

    assert payload["start_execution"] == {
        "status": "overlay_window_started",
        "next_smallest_truthful_gap": "summon_anywhere_blockers",
        "overlay_window": True,
        "overlay_runtime_ready": True,
        "overlay_window_visible": True,
        "always_on_top": True,
        "stop_command": "scripts/lens-overlay-window.ps1 -Mode Stop",
    }
    assert payload["stop_execution"] == {
        "status": "overlay_window_stopped",
        "overlay_window": False,
        "overlay_runtime_ready": False,
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
        "overlay_control_authority": True,
        "window_management_authority": True,
        "capture_authority": False,
        "new_sensing_authority": False,
        "summon_authority": False,
        "memory_write": False,
        "resident_claim_authority": False,
        "mutation_authority_granted": True,
    }

    assert not (data_dir / "runtime" / "lens-overlay" / "lens-overlay.pid").exists()
    assert not (data_dir / "runtime" / "lens-hotkey" / "lens-hotkey.pid").exists()
    assert not (data_dir / "runtime" / "lens-tray" / "lens-tray.pid").exists()
    assert not (data_dir / "runtime" / "lens-host" / "lens-host.pid").exists()
