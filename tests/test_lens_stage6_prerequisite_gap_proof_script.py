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
            str(_repo_root() / "scripts" / "lens-stage6-prerequisite-gap-proof.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
        timeout=60,
    )


def test_lens_stage6_prerequisite_gap_proof_reads_current_first_gap(tmp_path: Path) -> None:
    proc = _run_proof("-Mode", "Status", "-DataDir", str(tmp_path / "data"))

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.stage6.prerequisite_gap.proof"
    assert payload["status"] == "proof_passed"
    assert payload["ok"] is True
    assert payload["stage"] == "Stage 6 / Lens MVP"
    assert payload["stage_state"] == "active"
    assert payload["ready_to_close"] is False
    assert payload["acceptance_criterion"] == "system_resident_presence"
    assert payload["blocked_criteria"] == [
        "summon_anywhere",
        "helpful_not_noisy",
        "system_resident_presence",
    ]
    assert payload["closure_next_smallest_truthful_gap"] == "summon_anywhere_blockers"
    assert payload["next_smallest_truthful_gap"] == "persistent_supervision_required_prerequisites_missing"
    assert payload["missing_required_before_enable"] == [
        "resident_host_process",
        "tray_presence",
        "global_hotkey_binding",
        "overlay_window",
        "summon_binding",
    ]
    assert payload["first_missing_required_before_enable"] == "resident_host_process"

    handoff = payload["first_missing_requirement_handoff"]
    assert handoff["id"] == "resident_host_process"
    assert handoff["family"] == "resident_host"
    assert handoff["route"] == "/lens/host"
    assert handoff["readiness_route"] == "/lens/host/runtime-loop/readiness"
    assert handoff["proof_script"] == "scripts/lens-resident-host-runtime-boundary-proof.ps1 -Mode Status"
    assert handoff["acceptance_criterion"] == "system_resident_presence"
    assert handoff["read_only_contract"] is True
    assert handoff["diagnostic_only"] is True
    assert handoff["would_execute"] is False
    assert handoff["would_mutate"] is False
    assert payload["first_missing_handoff_next_smallest_truthful_gap"] in {
        "resident_host_process_not_supervised",
        "resident_supervision_not_persistent",
    }
    assert payload["recommended_proof_script"] == handoff["proof_script"]
    assert payload["recommended_route"] == "/lens/host"
    assert payload["recommended_readiness_route"] == "/lens/host/runtime-loop/readiness"

    assert payload["summon_anywhere_first_blocker_family"] == "resident_host"
    assert payload["summon_anywhere_blocked_families"] == [
        "resident_host",
        "tray_presence",
        "overlay_window",
        "global_hotkey_binding",
        "summon_binding",
        "authority",
    ]

    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["stage6_active"]["status"] == "active"
    assert checks["acceptance_blockers"]["status"] == "summon_anywhere_blockers"
    assert checks["persistent_supervision_prerequisites"]["status"] == "blocked"
    assert checks["first_missing_requirement_handoff"]["status"] in {
        "resident_host_process_not_supervised",
        "resident_supervision_not_persistent",
    }
    assert checks["summon_family_alignment"]["status"] == "resident_host"
    assert checks["side_effects_denied"]["status"] == "readback_only"
    assert all(item["passed"] for item in payload["checks"])

    assert payload["governance"] == {
        "diagnostic_only": True,
        "read_only_contract": True,
        "uses_lens_status_readback": True,
        "would_execute": False,
        "would_mutate": False,
        "product_execution_authority": False,
        "execution_authority": False,
        "approval_decision_authority": False,
        "local_process_launch_authority": False,
        "process_supervision_authority": False,
        "process_restart_authority": False,
        "service_install_authority": False,
        "service_control_authority": False,
        "tray_registration_authority": False,
        "hotkey_registration_authority": False,
        "overlay_control_authority": False,
        "summon_authority": False,
        "capture_authority": False,
        "new_sensing_authority": False,
        "memory_write": False,
        "receipt_write_authority": False,
        "resident_claim_authority": False,
        "mutation_authority_granted": False,
    }
