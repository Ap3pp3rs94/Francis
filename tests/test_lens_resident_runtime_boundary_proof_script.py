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
            str(_repo_root() / "scripts" / "lens-resident-runtime-boundary-proof.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
    )


def test_lens_resident_runtime_granted_boundary_proof_denies_execution(
    tmp_path: Path,
) -> None:
    data_dir = tmp_path / "data"
    proc = _run_proof("-Mode", "Status", "-DataDir", str(data_dir))

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.resident_runtime.granted_boundary_proof"
    assert payload["status"] == "proof_passed"
    assert payload["ok"] is True
    assert payload["resident_runtime_execution_authority"] is True
    assert payload["runtime_ready"] is False
    assert payload["resident_claim_allowed"] is False
    assert payload["applied"] is False
    assert payload["executed"] is False
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
    assert payload["authority_grant_receipt_id"]
    assert payload["runtime_denial_receipt_id"]
    assert (
        payload["next_smallest_truthful_gap"]
        == "supervised_resident_runtime_process_service_tray_hotkey_overlay_authority"
    )

    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["activation_approval_ready"]["status"] == "approved"
    assert checks["authority_grant_ready"]["status"] == "authority_granted"
    assert checks["runtime_plan_still_blocked"]["status"] == "blocked"
    assert checks["execute_denied_after_grant"]["status"] == "denied_no_resident_runtime_execution_boundary"
    assert checks["launch_supervision_boundary"]["status"] == "blocked"
    assert checks["tray_hotkey_overlay_claim_boundary"]["status"] == "blocked"
    assert checks["denial_receipt_readback"]["status"] == "readback_ready"
    assert checks["no_runtime_started"]["status"] == "no_runtime_files"
    assert checks["authority_boundaries_intact"]["status"] == "bounded"
    assert all(item["passed"] for item in payload["checks"])

    proof = payload["proof"]
    assert proof["authority_grant_status"] == "authority_granted"
    assert proof["authority_grant_receipt_written"] is True
    assert proof["runtime_plan_status"] == "blocked"
    assert proof["runtime_plan_active_authority_grant_receipt_id"] == payload["authority_grant_receipt_id"]
    assert proof["runtime_denial_status"] == "denied_no_resident_runtime_execution_boundary"
    assert proof["runtime_denial_reason"] == "local_process_launch_authority_not_granted"
    assert proof["runtime_denial_receipt_written"] is True
    assert proof["runtime_denial_receipts_status"] == "readback_ready"
    assert proof["runtime_denial_receipts_total"] == 1

    assert "resident_runtime_execution_authority_not_granted" not in payload["blockers"]
    assert "local_process_launch_authority_not_granted" in payload["blockers"]
    assert "process_supervision_authority_not_granted" in payload["blockers"]
    assert "service_control_authority_not_granted" in payload["blockers"]
    assert "tray_registration_authority_not_granted" in payload["blockers"]
    assert "hotkey_registration_authority_not_granted" in payload["blockers"]
    assert "overlay_control_authority_not_granted" in payload["blockers"]
    assert "resident_claim_authority_not_granted" in payload["blockers"]

    assert payload["governance"] == {
        "diagnostic_only": True,
        "api_route_proof": True,
        "approval_request_write": True,
        "approval_decision_authority": False,
        "resident_runtime_execution_authority": True,
        "execution_authority": False,
        "local_process_launch_authority": False,
        "process_supervision_authority": False,
        "process_restart_authority": False,
        "service_install_authority": False,
        "service_control_authority": False,
        "tray_registration_authority": False,
        "hotkey_registration_authority": False,
        "overlay_control_authority": False,
        "memory_write": False,
        "receipt_write_authority": False,
        "denial_receipt_write_authority": True,
        "resident_claim_authority": False,
        "mutation_authority_granted": False,
    }

    assert not (data_dir / "runtime" / "lens-host" / "status.json").exists()
    assert not (data_dir / "runtime" / "lens-host" / "lens-host.pid").exists()
