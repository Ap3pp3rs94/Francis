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
            str(_repo_root() / "scripts" / "lens-host-foreground-proof.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
    )


def test_lens_host_foreground_proof_observes_bounded_process_without_authority(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    proc = _run_proof("-Mode", "Status", "-RunSeconds", "8", "-DataDir", str(data_dir))

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.host.foreground_readiness_proof"
    assert payload["status"] == "proof_passed"
    assert payload["ok"] is True
    assert payload["ready_for_resident_claim"] is False
    assert payload["foreground_process_observed"] is True
    assert payload["foreground_status_readback_matched"] is True
    assert payload["foreground_completed"] is True
    assert payload["resident_host_process"] is False
    assert payload["supervised"] is False
    assert payload["service_managed"] is False
    assert payload["tray_presence"] is False
    assert payload["global_hotkey"] is False
    assert payload["overlay_window"] is False
    assert payload["summon_anywhere"] is False
    assert "resident_supervision_disabled" in payload["blockers"]
    assert "lens_host_runtime_not_implemented" in payload["blockers"]
    assert "global_hotkey_binding_missing" in payload["blockers"]

    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["powershell_runtime"]["passed"] is True
    assert checks["host_status_runner"]["passed"] is True
    assert checks["foreground_runtime_state"]["status"] == "observed"
    assert checks["host_status_readback"]["status"] == "process_observed"
    assert checks["foreground_completion"]["status"] == "completed"
    assert payload["proof"]["running_state_status"] == "foreground_running"
    assert payload["proof"]["status_readback_status"] == "process_observed"
    assert payload["proof"]["status_readback_state"] == "foreground_running"
    assert payload["proof"]["running_pid"] == payload["proof"]["status_readback_pid"]
    assert payload["proof"]["running_pid"] > 0
    assert payload["proof"]["final_payload_status"] == "foreground_completed"
    assert payload["proof"]["final_state_status"] == "foreground_stopped"
    assert (data_dir / "runtime" / "lens-host" / "status.json").is_file()
    assert not (data_dir / "runtime" / "lens-host" / "lens-host.pid").exists()

    assert payload["governance"] == {
        "diagnostic_only": True,
        "bounded_foreground_session": True,
        "temporary_runtime_state_write": True,
        "product_execution_authority": False,
        "execution_authority": False,
        "approval_decision_authority": False,
        "memory_write": False,
        "overlay_control_authority": False,
        "summon_authority": False,
        "capture_authority": False,
        "new_sensing_authority": False,
        "local_process_launch_authority": False,
        "api_local_process_launch_authority": False,
        "service_install_authority": False,
        "service_control_authority": False,
        "hotkey_registration_authority": False,
        "tray_registration_authority": False,
        "mutation_authority_granted": False,
    }
