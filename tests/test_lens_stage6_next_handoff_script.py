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
            str(_repo_root() / "scripts" / "lens-stage6-next-handoff.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
        timeout=60,
    )


def test_lens_stage6_next_handoff_distills_closure_readback_without_authority() -> None:
    proc = _run_proof("-Mode", "Status")

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.stage6.next_handoff.proof"
    assert payload["status"] == "proof_passed"
    assert payload["ok"] is True
    assert payload["mode"] == "status"
    assert payload["stage"] == "Stage 6 / Lens MVP"
    assert payload["stage_state"] == "active"
    assert payload["ready_to_close"] is False
    assert payload["stage_next_smallest_truthful_gap"] == "summon_anywhere_blockers"
    assert payload["acceptance_criterion"] == "summon_anywhere"
    assert payload["acceptance_criterion_status"] == "blocked"
    assert payload["criterion_next_smallest_truthful_gap"] == "summon_anywhere_blockers"
    assert payload["first_blocker_family"] == "resident_host"
    assert payload["first_blocker_family_next_smallest_truthful_gap"] == "resident_host_runtime_blocker_boundary"
    assert payload["next_smallest_truthful_gap"] == "stage6_lens_completion_audit"
    assert (
        payload["recommended_next_slice"] == "consume_resident_host_process_supervision_handoff_before_stage6_closure"
    )
    assert payload["recommended_handoff_source"] == "first_blocker_family_completion_audit_handoff"
    assert (
        payload["recommended_proof_script"]
        == "scripts/lens-summon-resident-host-blocker-proof.ps1 -Mode Status -ConsumeProcessSupervisionHandoff"
    )
    assert payload["recommended_route"] == "/lens/host"
    assert payload["recommended_readiness_route"] == "/lens/host/runtime-loop/readiness"
    assert payload["authority_required"] == "process_supervision_authority"
    assert payload["blocked_criteria"] == [
        "summon_anywhere",
        "helpful_not_noisy",
        "system_resident_presence",
    ]
    assert payload["ready_criteria"] == ["mode_visibility", "pilot_visibility_groundwork"]

    first_handoff = payload["first_blocker_family_handoff"]
    assert first_handoff["id"] == "resident_host"
    assert first_handoff["status"] == "blocked"
    assert first_handoff["read_only_contract"] is True
    assert first_handoff["diagnostic_only"] is True
    assert first_handoff["would_execute"] is False
    assert first_handoff["would_mutate"] is False

    process_handoff = payload["first_blocker_family_completion_audit_handoff"]
    assert process_handoff["authority_required"] == "process_supervision_authority"
    assert process_handoff["read_only_contract"] is True
    assert process_handoff["diagnostic_only"] is True
    assert process_handoff["would_execute"] is False
    assert process_handoff["would_mutate"] is False

    family_chain_handoff = payload["summon_anywhere_family_chain_completion_audit_handoff"]
    assert family_chain_handoff["authority_required"] == "resident_runtime_execution_authority"
    assert family_chain_handoff["blocked_families"] == [
        "resident_host",
        "tray_presence",
        "overlay_window",
        "global_hotkey_binding",
        "summon_binding",
        "authority",
    ]
    assert family_chain_handoff["read_only_contract"] is True
    assert family_chain_handoff["diagnostic_only"] is True
    assert family_chain_handoff["would_execute"] is False
    assert family_chain_handoff["would_mutate"] is False

    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["closure_readback"]["status"] == "blocked_closure_readback_observed"
    assert checks["stage_boundary"]["status"] == "stage6_active"
    assert checks["first_blocked_criterion"]["status"] == "summon_anywhere_blocked"
    assert checks["first_blocker_family_handoff"]["status"] == "resident_host_handoff_ready"
    assert checks["completion_audit_handoff"]["status"] == "process_supervision_audit_handoff_ready"
    assert checks["family_chain_handoff"]["status"] == "summon_family_chain_handoff_ready"
    assert checks["side_effects_denied"]["status"] == "readback_only"
    assert all(item["passed"] for item in payload["checks"])

    assert payload["governance"] == {
        "diagnostic_only": True,
        "read_only_contract": True,
        "uses_lens_status_readback": True,
        "proof_script": "scripts/lens-stage6-next-handoff.ps1 -Mode Status",
        "would_execute": False,
        "would_mutate": False,
        "product_execution_authority": False,
        "execution_authority": False,
        "approval_decision_authority": False,
        "approval_request_write": False,
        "local_process_launch_authority": False,
        "process_supervision_authority": False,
        "process_restart_authority": False,
        "service_install_authority": False,
        "service_control_authority": False,
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
