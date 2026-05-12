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
            str(_repo_root() / "scripts" / "lens-resident-runtime-authority-blockers-proof.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
    )


def test_lens_resident_runtime_authority_blockers_proof_splits_combined_gap(
    tmp_path: Path,
) -> None:
    data_dir = tmp_path / "data"
    proc = _run_proof("-Mode", "Status", "-DataDir", str(data_dir))

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.resident_runtime.authority_blockers_proof"
    assert payload["status"] == "proof_passed"
    assert payload["ok"] is True
    assert payload["next_smallest_truthful_gap"] == "resident_runtime_process_supervision_authority_boundary"

    boundary = payload["boundary_proof"]
    assert boundary["ok"] is True
    assert boundary["kind"] == "lens.resident_runtime.granted_boundary_proof"
    assert boundary["status"] == "proof_passed"
    assert boundary["resident_runtime_execution_authority"] is True
    assert boundary["runtime_ready"] is False
    assert boundary["resident_claim_allowed"] is False
    assert boundary["applied"] is False
    assert boundary["executed"] is False
    assert boundary["would_launch_process"] is False
    assert boundary["would_supervise_process"] is False
    assert boundary["would_start_service"] is False
    assert boundary["would_register_tray"] is False
    assert boundary["would_register_hotkey"] is False
    assert boundary["would_open_overlay"] is False
    assert boundary["would_write_memory"] is False
    assert boundary["would_claim_resident"] is False
    assert (
        boundary["combined_next_smallest_truthful_gap"]
        == "supervised_resident_runtime_process_service_tray_hotkey_overlay_authority"
    )

    families = set(payload["remaining_authority_families"])
    assert families == {
        "process_supervision",
        "service_control",
        "tray_presence",
        "hotkey_summon",
        "overlay_window",
        "resident_claim",
    }
    assert payload["summary"] == {
        "blocker_total": payload["summary"]["blocker_total"],
        "authority_family_total": 6,
        "blocked_authority_family_total": 6,
        "combined_gap_split": True,
    }
    assert payload["summary"]["blocker_total"] >= 20

    groups = payload["authority_blocker_groups"]
    assert groups["process_supervision"]["status"] == "blocked"
    assert groups["process_supervision"]["route"] == "/lens/host/supervision/authority/readiness"
    assert "local_process_launch_authority_not_granted" in groups["process_supervision"]["blockers"]
    assert "process_supervision_authority_not_granted" in groups["process_supervision"]["blockers"]
    assert "process_restart_authority_not_granted" in groups["process_supervision"]["blockers"]
    assert groups["process_supervision"]["authority_granted"] is False
    assert groups["process_supervision"]["would_execute"] is False

    assert groups["service_control"]["status"] == "blocked"
    assert groups["service_control"]["route"] == "/lens/host/persistent-supervision/enablement"
    assert "service_install_authority_not_granted" in groups["service_control"]["blockers"]
    assert "service_control_authority_not_granted" in groups["service_control"]["blockers"]
    assert groups["service_control"]["authority_granted"] is False

    assert groups["tray_presence"]["status"] == "blocked"
    assert groups["tray_presence"]["route"] == "/lens/tray"
    assert "tray_registration_authority_not_granted" in groups["tray_presence"]["blockers"]
    assert "lens_tray_presence_disabled_pending_authority" in groups["tray_presence"]["blockers"]

    assert groups["hotkey_summon"]["status"] == "blocked"
    assert groups["hotkey_summon"]["route"] == "/lens/summon"
    assert "hotkey_registration_authority_not_granted" in groups["hotkey_summon"]["blockers"]
    assert "global_hotkey_binding_missing" in groups["hotkey_summon"]["blockers"]

    assert groups["overlay_window"]["status"] == "blocked"
    assert groups["overlay_window"]["route"] == "/lens/overlay"
    assert "overlay_control_authority_not_granted" in groups["overlay_window"]["blockers"]
    assert "lens_overlay_window_not_implemented" in groups["overlay_window"]["blockers"]

    assert groups["resident_claim"]["status"] == "blocked"
    assert groups["resident_claim"]["route"] == "/lens/resident-runtime/plan"
    assert "resident_claim_authority_not_granted" in groups["resident_claim"]["blockers"]
    assert "resident_surface_runtime_missing" in groups["resident_claim"]["blockers"]

    assert payload["governance"] == {
        "diagnostic_only": True,
        "wraps_existing_boundary_proof": True,
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
        "resident_claim_authority": False,
        "mutation_authority_granted": False,
    }
