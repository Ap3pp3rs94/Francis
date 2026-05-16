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
            str(_repo_root() / "scripts" / "lens-summon-anywhere-family-chain-proof.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
        timeout=240,
    )


def test_lens_summon_anywhere_family_chain_consumes_handoffs(tmp_path: Path) -> None:
    proc = _run_proof(
        "-Mode",
        "Status",
        "-DataDir",
        str(tmp_path / "data"),
        "-ChildProofTimeoutSeconds",
        "120",
    )

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.summon_anywhere_family_chain.proof"
    assert payload["status"] == "proof_passed"
    assert payload["ok"] is True
    assert payload["stage"] == "Stage 6 / Lens MVP"
    assert payload["stage_state"] == "active"
    assert payload["acceptance_criterion"] == "summon_anywhere"
    assert payload["summon_next_smallest_truthful_gap"] == "summon_anywhere_blockers"
    assert payload["next_smallest_truthful_gap"] == "stage6_lens_completion_audit"
    assert payload["authority_required"] == "summon_hotkey_overlay_and_process_authority"
    assert payload["authority_granted"] is False
    assert payload["family_chain_observed"] is True
    assert payload["resident_host_family_handoff_observed"] is True
    assert payload["final_summon_authority_handoff_observed"] is True
    assert payload["all_summon_blocker_families_consumed"] is True
    assert payload["handoff_aligned"] is True
    assert payload["side_effects_denied"] is True
    assert payload["child_proof_timeout_seconds"] == 120
    assert payload["child_proof_timeouts"] == []
    child_proof_runs = {item["name"]: item for item in payload["child_proof_runs"]}
    assert set(child_proof_runs) == {
        "summon_anywhere_blockers",
        "summon_resident_host_blocker",
        "summon_authority_blocker",
    }
    for run in child_proof_runs.values():
        assert run["timed_out"] is False
        assert run["timeout_seconds"] == 120
        assert isinstance(run["duration_ms"], int)
        assert run["duration_ms"] >= 0

    assert payload["blocked_families"] == [
        "resident_host",
        "tray_presence",
        "overlay_window",
        "global_hotkey_binding",
        "summon_binding",
        "authority",
    ]
    assert [item["id"] for item in payload["blocked_family_handoffs"]] == payload["blocked_families"]
    assert payload["first_blocker_family"] == "resident_host"
    assert payload["first_blocker_family_handoff"]["next_smallest_truthful_gap"] == (
        "resident_host_runtime_blocker_boundary"
    )

    resident_host = payload["resident_host"]
    assert resident_host["next_smallest_truthful_gap"] == "resident_host_runtime_blocker_boundary"
    assert resident_host["lifecycle_next_smallest_truthful_gap"] == "resident_host_runtime_blocker_boundary"
    assert resident_host["runtime_blockers"] == ["lens_host_persistent_supervision_prerequisites_pending"]
    assert resident_host["surface_blockers"] == [
        "tray_host_missing",
        "global_hotkey_binding_missing",
        "overlay_window_missing",
        "summon_binding_missing",
    ]

    final_authority = payload["final_authority"]
    assert final_authority["previous_summon_blocker_family"] == "summon_binding"
    assert final_authority["summon_authority_blocker_family"] == "authority"
    assert final_authority["next_summon_blocker_family"] == "stage6_lens_completion_audit"
    assert final_authority["next_smallest_truthful_gap"] == "stage6_lens_completion_audit"
    assert final_authority["authority_required"] == "summon_hotkey_overlay_and_process_authority"
    assert final_authority["authority_granted"] is False
    assert final_authority["all_summon_blocker_families_consumed"] is True
    assert final_authority["blockers"] == [
        "summon_authority_not_granted",
        "hotkey_registration_authority_not_granted",
        "overlay_control_authority_not_granted",
        "local_process_launch_authority_not_granted",
    ]

    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["summon_anywhere_family_chain"]["status"] == "family_chain_projected"
    assert checks["resident_host_family_handoff"]["status"] == "resident_host_handoff_ready"
    assert checks["final_summon_authority_handoff"]["status"] == "final_family_consumed"
    assert checks["handoff_alignment"]["status"] == "handoff_aligned"
    assert checks["side_effects_denied"]["status"] == "diagnostic_bounded"
    assert all(item["passed"] for item in payload["checks"])

    assert payload["governance"] == {
        "diagnostic_only": True,
        "wraps_summon_anywhere_blockers_proof": True,
        "wraps_summon_resident_host_blocker_proof": True,
        "wraps_summon_authority_blocker_proof": True,
        "read_only_contract": True,
        "bounded_local_process_launch": False,
        "temporary_runtime_state_write": False,
        "product_execution_authority": False,
        "execution_authority": False,
        "approval_decision_authority": False,
        "local_process_launch_authority": False,
        "process_supervision_authority": False,
        "process_restart_authority": False,
        "service_install_authority": False,
        "service_control_authority": False,
        "tray_registration_authority": False,
        "tray_icon_authority": False,
        "notification_authority": False,
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
