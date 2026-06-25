from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
from pathlib import Path

import pytest

_PROOF_GLOBAL_HOTKEY = "Ctrl+Alt+Shift+F14"


def _powershell() -> str:
    exe = shutil.which("powershell") or shutil.which("pwsh")
    if not exe:
        pytest.skip("PowerShell is not available")
    return exe


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _run_proof(*args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["FRANCIS_PROOF_GLOBAL_HOTKEY"] = _PROOF_GLOBAL_HOTKEY
    return subprocess.run(
        [
            _powershell(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(_repo_root() / "scripts" / "lens-summon-api-execution-proof.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        env=env,
        check=False,
        text=True,
        capture_output=True,
        timeout=420,
    )


def test_lens_summon_api_execution_proof_uses_governed_routes() -> None:
    script = (_repo_root() / "scripts" / "lens-summon-api-execution-proof.ps1").read_text(encoding="utf-8")

    assert '"/lens/host/supervision/authority/request"' in script
    assert '"/lens/resident-runtime/authority-grant/request"' in script
    assert '"/lens/resident-runtime/execute"' in script
    assert '"/lens/tray/authority/request"' in script
    assert '"/lens/tray/execute"' in script
    assert '"/lens/os-binding/authority/request"' in script
    assert '"/lens/os-binding/execute"' in script
    assert '"/lens/overlay/authority/request"' in script
    assert '"/lens/overlay/execute"' in script
    assert '"/lens/summon/authority/request"' in script
    assert '"/lens/summon/authority"' in script
    assert '"/lens/summon/execute"' in script
    assert '"/lens/summon/executions?limit=10"' in script
    assert '"/lens/summon/readiness"' in script
    assert '"/lens/host/supervision/execute"' in script
    assert "$AllowLaunchOnHotkey" in script
    assert "FRANCIS_PROOF_ALLOW_LAUNCH_ON_HOTKEY" in script
    assert "dependency_run_seconds = max(run_seconds, 60)" in script
    assert '"mode": "resident_stop"' in script
    assert '"allow_launch": allow_launch_on_hotkey' in script
    assert '"summon_approval_id"' in script
    assert '"overlay_approval_id"' in script
    assert 'hotkey_execute_payload["summon_approval_id"] = summon_approval_id' in script
    assert 'hotkey_execute_payload["overlay_approval_id"] = overlay_approval_id' in script
    assert '"summon_anywhere_authority": False' in script
    assert '"resident_claim_authority": False' in script
    assert 'proof_global_hotkey = os.environ.get("FRANCIS_PROOF_GLOBAL_HOTKEY", "Ctrl+Alt+Shift+F12").strip()' in script
    assert '"global_hotkey": proof_global_hotkey' in script


def test_lens_summon_api_execution_proof_executes_bounded_summon_handoff(
    tmp_path: Path,
) -> None:
    if platform.system() != "Windows":
        pytest.skip("Live Lens summon API execution proof is Windows-hosted.")
    if os.environ.get("CI", "").lower() == "true":
        pytest.skip("Live summon proof requires an interactive Windows user session.")

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
    assert payload["kind"] == "lens.summon.api_execution.proof"
    assert payload["status"] == "proof_passed"
    assert payload["ok"] is True
    assert payload["stage"] == "Stage 6 / Lens MVP"
    assert payload["stage_state"] == "active"
    assert payload["acceptance_criterion"] == "summon_anywhere"
    assert payload["previous_next_smallest_truthful_gap"] == "summon_binding_blocker_boundary"
    assert payload["route_next_smallest_truthful_gap"] == "summon_anywhere_runtime_readback"
    assert payload["next_smallest_truthful_gap"] == "summon_anywhere_runtime_readback"
    assert (
        payload["recommended_proof_script"]
        == "scripts/lens-persistent-supervision-api-execution-proof.ps1 -Mode Status"
    )
    assert payload["dependency_run_seconds"] == 60
    assert payload["resident_dependency_run_seconds"] == 60
    assert payload["global_hotkey"] == _PROOF_GLOBAL_HOTKEY

    assert payload["host_supervision_authority_grant_receipt_id"]
    assert payload["resident_runtime_authority_grant_receipt_id"]
    assert payload["tray_authority_grant_receipt_id"]
    assert payload["os_binding_authority_grant_receipt_id"]
    assert payload["overlay_authority_grant_receipt_id"]
    assert payload["summon_authority_grant_receipt_id"]
    assert payload["resident_runtime_execution_authority"] is True
    assert payload["host_supervision_authority"] is True
    assert payload["tray_presence_authority"] is True
    assert payload["os_binding_authority"] is True
    assert payload["overlay_authority"] is True
    assert payload["summon_authority"] is True
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
    assert payload["summon_binding_observed"] is True
    assert payload["summon_runtime_ready"] is True
    assert payload["bounded_handoff_ready"] is True
    assert payload["local_open_ready"] is True
    assert payload["opened"] is False
    assert payload["no_launch"] is True
    assert payload["receipt_written"] is True
    assert payload["summon_runtime_state_observed"] is True
    assert payload["summon_config_override_present"] is True
    assert payload["overlay_stop_observed"] is True
    assert payload["hotkey_stop_observed"] is True
    assert payload["tray_presence_stop_observed"] is True
    assert payload["resident_supervision_stop_observed"] is True
    assert payload["overlay_pid_file_present_after_stop"] is False
    assert payload["hotkey_pid_file_present_after_stop"] is False
    assert payload["tray_pid_file_present_after_stop"] is False
    assert payload["host_pid_file_present_after_stop"] is False
    assert payload["required_before_enable_after_summon"] == []
    assert payload["required_before_enable_ready_after_summon"] is True
    assert payload["summon_readiness_summon_runtime_ready"] is True
    assert "summon_anywhere_runtime_readback" in payload["summon_readiness_blockers_after_execute"]
    assert payload["blockers"] == []
    assert payload["summon_anywhere"] is False
    assert payload["os_level_summon"] is False
    assert payload["service_managed"] is False
    assert payload["resident_claim_allowed"] is False

    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["host_supervision_authority_granted"]["status"] == "authority_granted"
    assert checks["resident_tray_hotkey_overlay_started_before_summon"]["status"] == "ready"
    assert checks["summon_authority_granted"]["status"] == "authority_granted"
    assert checks["api_execute_observed_bounded_summon_handoff"]["status"] == "summon_binding_observed"
    assert checks["summon_runtime_state_written"]["status"] == "summon_binding_observed"
    assert checks["status_plan_consumed_live_summon_runtime"]["status"] == "required_before_enable_clear"
    assert checks["summon_receipt_readback_after_execute"]["status"] == "readback_ready"
    assert checks["summon_readiness_consumes_runtime_without_closure"]["status"] == "blocked"
    assert checks["api_stop_cleaned_real_overlay_window"]["status"] == "overlay_window_stopped"
    assert checks["api_stop_cleaned_real_global_hotkey"]["status"] == "global_hotkey_binding_stopped"
    assert checks["api_stop_cleaned_real_tray_presence"]["status"] == "tray_presence_stopped"
    assert checks["resident_supervision_stop_observed"]["status"] == "resident_supervision_stopped"
    assert checks["authority_boundaries_intact"]["status"] == "bounded"
    assert all(item["passed"] for item in payload["checks"])

    proof = payload["proof"]
    assert proof["dependency_run_seconds"] == 60
    assert proof["resident_dependency_run_seconds"] == 60
    assert proof["global_hotkey"] == _PROOF_GLOBAL_HOTKEY
    assert proof["resident_start_status"] in {"resident_supervision_started", "resident_supervision_already_running"}
    assert proof["tray_start_status"] in {"tray_presence_started", "tray_presence_already_running"}
    assert proof["hotkey_start_status"] in {
        "global_hotkey_bound",
        "global_hotkey_already_bound",
        "global_hotkey_binding_already_running",
    }
    assert proof["overlay_start_status"] in {"overlay_window_started", "overlay_window_already_running"}
    assert proof["summon_execute_status"] == "summon_binding_observed"
    assert proof["summon_receipt_readback_status"] == "readback_ready"
    assert proof["summon_receipt_readback_next_gap"] == "summon_anywhere_runtime_readback"
    assert proof["summon_runtime_state_status"] == "summon_binding_observed"
    assert proof["summon_runtime_readback_status"] == "observed"
    assert proof["persistent_plan_first_missing_after_summon"] == ""
    assert proof["overlay_stop_status"] == "overlay_window_stopped"
    assert proof["hotkey_stop_status"] == "global_hotkey_binding_stopped"
    assert proof["tray_stop_status"] == "tray_presence_stopped"
    assert proof["resident_stop_status"] == "resident_supervision_stopped"

    assert payload["start_execution"] == {
        "status": "summon_binding_observed",
        "next_smallest_truthful_gap": "summon_anywhere_runtime_readback",
        "summon_binding": True,
        "summon_runtime_ready": True,
        "bounded_handoff_ready": True,
        "local_open_ready": True,
        "opened": False,
        "no_launch": True,
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
        "local_process_launch_authority": False,
        "process_supervision_authority": True,
        "process_restart_authority": False,
        "service_install_authority": False,
        "service_control_authority": False,
        "tray_registration_authority": True,
        "tray_icon_authority": True,
        "hotkey_registration_authority": True,
        "overlay_control_authority": True,
        "window_management_authority": True,
        "bounded_local_open_handoff_authority": True,
        "summon_authority": True,
        "summon_anywhere_authority": False,
        "os_level_summon_authority": False,
        "capture_authority": False,
        "new_sensing_authority": False,
        "memory_write": False,
        "resident_claim_authority": False,
        "mutation_authority_granted": True,
    }

    assert (data_dir / "runtime" / "lens-summon" / "status.json").exists()
    assert not (data_dir / "runtime" / "lens-overlay" / "lens-overlay.pid").exists()
    assert not (data_dir / "runtime" / "lens-hotkey" / "lens-hotkey.pid").exists()
    assert not (data_dir / "runtime" / "lens-tray" / "lens-tray.pid").exists()
    assert not (data_dir / "runtime" / "lens-host" / "lens-host.pid").exists()
