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
            str(_repo_root() / "scripts" / "lens-host-supervision-proof.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
    )


def test_lens_host_supervision_proof_composes_blocked_readiness_without_authority() -> None:
    proc = _run_proof(
        "-Mode",
        "Status",
        "-ForegroundRunSeconds",
        "2",
        "-HostLaunchRunSeconds",
        "3",
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.host.supervision_readiness_proof"
    assert payload["status"] == "proof_passed"
    assert payload["ok"] is True
    assert payload["requested_foreground_run_seconds"] == 2
    assert payload["foreground_run_seconds"] >= 5
    assert payload["host_launch_run_seconds"] == 3
    assert payload["supervision_ready"] is False
    assert payload["ready_for_resident_claim"] is False
    assert payload["resident_claim_allowed"] is False
    assert payload["bounded_host_launch_observed"] is True
    assert payload["resident_host_process"] is False
    assert payload["service_installed"] is False
    assert payload["supervised"] is False
    assert payload["service_managed"] is False
    assert payload["tray_presence"] is False
    assert payload["global_hotkey"] is False
    assert payload["overlay_window"] is False
    assert payload["summon_anywhere"] is False
    assert payload["next_smallest_truthful_gap"] == ("resident_host_supervision_or_resident_overlay_runtime")

    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["host_lifecycle_preflight"]["status"] == "blocked_readback_ready"
    assert checks["foreground_readiness_proof"]["status"] == "proof_passed"
    assert checks["bounded_launch_proof"]["status"] == "bounded_launch_observed"
    assert checks["service_plan_no_install"]["status"] == "blocked_no_install"
    assert checks["service_not_installed"]["status"] == "not_installed"
    assert checks["process_supervision_disabled"]["status"] == "blocked"
    assert checks["service_control_denied"]["status"] == "blocked"
    assert checks["install_authority_denied"]["status"] == "blocked"
    assert all(item["passed"] for item in payload["checks"])

    proof = payload["proof"]
    assert proof["lifecycle_preflight_status"] == "blocked"
    assert proof["foreground_proof_status"] == "proof_passed"
    assert proof["foreground_process_observed"] is True
    assert proof["foreground_status_readback_matched"] is True
    assert proof["foreground_completed"] is True
    assert proof["host_launch_proof_status"] == "proof_passed"
    assert proof["bounded_host_launch_observed"] is True
    assert proof["host_launch_completed"] is True
    assert proof["host_launch_authority_boundary"] is True
    assert proof["host_launch_ready_for_resident_claim"] is False
    assert proof["service_plan_status"] == "blocked"
    assert proof["service_plan_ready"] is False
    assert proof["service_plan_would_install"] is False
    assert proof["service_plan_would_start"] is False
    assert "installable_false" in proof["service_plan_blocked_by"]
    assert "service_install_authority_false" in proof["service_plan_blocked_by"]
    assert "service_control_authority_false" in proof["service_plan_blocked_by"]
    assert proof["service_status"] in {"not_installed", "unsupported_platform"}
    assert proof["process_supervision_status"] == "blocked"
    assert proof["service_control_status"] == "blocked"
    assert "resident_host_process_not_supervised" in payload["blockers"]
    assert "resident_supervision_disabled" in payload["blockers"]
    assert "resident_surface_runtime_missing" in payload["blockers"]
    assert "resident_surface_missing" not in payload["blockers"]
    assert "operator_experience_proof_missing" not in payload["blockers"]
    assert "tray_host_missing" in payload["blockers"]

    assert payload["governance"] == {
        "read_only_contract": True,
        "diagnostic_only": True,
        "bounded_foreground_session": True,
        "bounded_host_launch": True,
        "bounded_process_launch": True,
        "temporary_runtime_state_write": True,
        "product_execution_authority": False,
        "execution_authority": False,
        "approval_decision_authority": False,
        "memory_write": False,
        "overlay_control_authority": False,
        "summon_authority": False,
        "capture_authority": False,
        "new_sensing_authority": False,
        "local_process_launch_authority": True,
        "api_local_process_launch_authority": False,
        "service_install_authority": False,
        "service_control_authority": False,
        "hotkey_registration_authority": False,
        "tray_registration_authority": False,
        "mutation_authority_granted": False,
    }
