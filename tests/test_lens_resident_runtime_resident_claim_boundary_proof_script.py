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
            str(_repo_root() / "scripts" / "lens-resident-runtime-resident-claim-boundary-proof.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
    )


def test_lens_resident_runtime_resident_claim_boundary_is_readback_only() -> None:
    proc = _run_proof("-Mode", "Status")

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.resident_runtime.resident_claim_boundary.proof"
    assert payload["status"] == "proof_passed"
    assert payload["ok"] is True
    assert payload["authority_family"] == "resident_claim"
    assert payload["previous_authority_family"] == "overlay_window"
    assert payload["next_authority_family"] == ""
    assert payload["resident_claim_boundary_observed"] is True
    assert payload["previous_overlay_window_family_observed"] is True
    assert payload["authority_blockers_proof_observed"] is True
    assert payload["side_effects_denied"] is True
    assert payload["sixth_authority_family_consumed"] is True
    assert payload["local_process_launch_authority"] is False
    assert payload["process_supervision_authority"] is False
    assert payload["process_restart_authority"] is False
    assert payload["service_install_authority"] is False
    assert payload["service_control_authority"] is False
    assert payload["tray_registration_authority"] is False
    assert payload["tray_icon_authority"] is False
    assert payload["notification_authority"] is False
    assert payload["summon_authority"] is False
    assert payload["hotkey_registration_authority"] is False
    assert payload["overlay_control_authority"] is False
    assert payload["window_management_authority"] is False
    assert payload["capture_authority"] is False
    assert payload["new_sensing_authority"] is False
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

    resident_claim = payload["resident_claim"]
    assert resident_claim["status"] == "blocked"
    assert resident_claim["ready"] is False
    assert resident_claim["authority_granted"] is False
    assert resident_claim["would_execute"] is False
    assert resident_claim["route"] == "/lens/resident-runtime/plan"
    assert "/lens/resident-runtime/plan" in resident_claim["evidence"]
    assert "/lens/resident-runtime/execute" in resident_claim["evidence"]
    assert resident_claim["required_before"] == []
    assert "lens_host_runtime_not_implemented" in resident_claim["blockers"]
    assert "resident_claim_authority_not_granted" in resident_claim["blockers"]
    assert "resident_surface_runtime_missing" in resident_claim["blockers"]
    assert payload["blockers"] == resident_claim["blockers"]

    assert payload["remaining_authority_families_after_this_boundary"] == []
    assert payload["next_smallest_truthful_gap"] == "stage6_lens_completion_audit"

    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["resident_runtime_authority_blockers_proof"]["status"] == "proof_observed"
    assert checks["previous_overlay_window_family"]["status"] == "blocked"
    assert checks["resident_claim_family"]["status"] == "blocked"
    assert checks["resident_claim_side_effects_denied"]["status"] == "denied_no_resident_claim"
    assert checks["authority_boundary"]["status"] == "diagnostic_bounded"
    assert all(item["passed"] for item in payload["checks"])

    governance = payload["governance"]
    assert governance["diagnostic_only"] is True
    assert governance["wraps_existing_authority_blockers_proof"] is True
    assert governance["overlay_window_boundary_readback"] is True
    assert governance["execution_authority"] is False
    assert governance["approval_decision_authority"] is False
    assert governance["local_process_launch_authority"] is False
    assert governance["process_supervision_authority"] is False
    assert governance["service_control_authority"] is False
    assert governance["overlay_control_authority"] is False
    assert governance["memory_write"] is False
    assert governance["resident_claim_authority"] is False
    assert governance["mutation_authority_granted"] is False
