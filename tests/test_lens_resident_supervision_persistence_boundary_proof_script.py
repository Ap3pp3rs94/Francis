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
            str(_repo_root() / "scripts" / "lens-resident-supervision-persistence-boundary-proof.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
        timeout=210,
    )


def test_lens_resident_supervision_persistence_boundary_promotes_candidate_readback(
    tmp_path: Path,
) -> None:
    data_dir = tmp_path / "data"
    proc = _run_proof(
        "-Mode",
        "Status",
        "-DataDir",
        str(data_dir),
        "-ChildProofTimeoutSeconds",
        "180",
    )

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.resident_supervision.persistence_boundary.proof"
    assert payload["status"] == "proof_passed"
    assert payload["ok"] is True
    assert payload["stage"] == "Stage 6 / Lens MVP"
    assert payload["stage_state"] == "active"
    assert payload["acceptance_criterion"] == "system_resident_presence"
    assert payload["previous_next_smallest_truthful_gap"] == "resident_host_process_not_supervised"
    assert payload["consumed_resident_candidate_next_smallest_truthful_gap"] == ("resident_supervision_not_persistent")
    assert payload["route_next_smallest_truthful_gap"] == "persistent_supervision_authority_not_granted"
    assert payload["next_smallest_truthful_gap"] == "persistent_supervision_authority_not_granted"
    assert payload["recommended_handoff_source"] == "resident_supervision_persistence_boundary_handoff"
    assert payload["recommended_next_slice"] == (
        "prove_persistent_supervision_enablement_authority_after_candidate_handoff"
    )
    assert payload["recommended_proof_script"] == (
        "scripts/lens-persistent-supervision-enablement-authority-proof.ps1 -Mode Status"
    )
    assert payload["recommended_route"] == "/lens/host/persistent-supervision/enablement/authority"
    assert payload["recommended_readiness_route"] == (
        "/lens/host/persistent-supervision/enablement/authority/readiness"
    )
    assert payload["resident_candidate_boundary_proof_observed"] is True
    assert payload["persistent_supervision_plan_candidate_readback_observed"] is True
    assert payload["persistent_supervision_enablement_candidate_readback_observed"] is True
    assert payload["resident_dependency_candidate_readback_observed"] is True
    assert payload["route_blocking_preserved"] is True
    assert payload["side_effects_bounded"] is True
    assert payload["resident_runtime_candidate_supervised"] is True
    assert payload["resident_supervised_runtime"] is False
    assert payload["supervisor_freshness_status"] == "fresh"
    assert payload["resident_host_process_requirement_state"] == "resident_candidate_observed_not_persistent"
    assert payload["resident_host_process_blocker"] == "resident_supervision_not_persistent"
    assert payload["authority_required"] == "persistent_process_supervision_authority"
    assert payload["authority_granted"] is False
    assert payload["plan_route"] == "/lens/host/persistent-supervision"
    assert payload["enablement_route"] == "/lens/host/persistent-supervision/enablement"

    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["resident_candidate_boundary_proof"]["status"] == ("resident_candidate_observed_not_persistent")
    assert checks["persistent_supervision_plan_candidate_readback"]["status"] == "candidate_handoff_promoted"
    assert checks["persistent_supervision_enablement_candidate_readback"]["status"] == ("candidate_handoff_promoted")
    assert checks["resident_dependency_candidate_readback"]["status"] == "dependency_readback_promoted"
    assert checks["route_blocking_preserved"]["status"] == "blocked_without_authority"
    assert checks["side_effects_bounded"]["status"] == "diagnostic_bounded"
    assert all(item["passed"] for item in payload["checks"])

    assert "resident_supervision_not_persistent" in payload["blockers"]
    assert "persistent_supervision_authority_not_granted" in payload["blockers"]
    assert "persistent_process_supervision_authority_required" in payload["blockers"]

    proof = payload["proof"]
    assert proof["resident_boundary_status"] == "proof_passed"
    assert proof["resident_boundary_next_gap"] == "resident_host_process_not_supervised"
    assert proof["resident_candidate_next_gap"] == "resident_supervision_not_persistent"
    assert proof["resident_candidate_persistence_blocker"] == "resident_supervision_not_persistent"
    assert proof["resident_candidate_supervised"] is True
    assert proof["resident_candidate_persistent"] is False
    assert proof["plan_status"] == "blocked"
    assert proof["plan_next_smallest_truthful_gap"] == "persistent_supervision_authority_not_granted"
    assert proof["plan_handoff_next_smallest_truthful_gap"] == "resident_supervision_not_persistent"
    assert proof["plan_handoff_requirement_state"] == "resident_candidate_observed_not_persistent"
    assert proof["enablement_status"] == "blocked"
    assert proof["enablement_next_smallest_truthful_gap"] == "persistent_supervision_authority_not_granted"
    assert proof["enablement_handoff_next_smallest_truthful_gap"] == "resident_supervision_not_persistent"
    assert proof["enablement_handoff_requirement_state"] == "resident_candidate_observed_not_persistent"

    child_runs = {item["name"]: item for item in payload["child_proof_runs"]}
    assert set(child_runs) == {"resident_host_runtime_boundary", "route_readback"}
    assert child_runs["resident_host_runtime_boundary"]["timeout_seconds"] == 180
    assert child_runs["route_readback"]["timeout_seconds"] == 60
    for run in child_runs.values():
        assert run["exit_code"] == 0
        assert run["timed_out"] is False
        assert isinstance(run["duration_ms"], int)
        assert run["duration_ms"] >= 0

    handoff = payload["handoff"]
    assert handoff == {
        "previous_next_smallest_truthful_gap": "resident_host_process_not_supervised",
        "consumed_resident_candidate_next_smallest_truthful_gap": "resident_supervision_not_persistent",
        "route_next_smallest_truthful_gap": "persistent_supervision_authority_not_granted",
        "next_smallest_truthful_gap": "persistent_supervision_authority_not_granted",
        "recommended_handoff_source": "resident_supervision_persistence_boundary_handoff",
        "recommended_next_slice": "prove_persistent_supervision_enablement_authority_after_candidate_handoff",
        "recommended_proof_script": ("scripts/lens-persistent-supervision-enablement-authority-proof.ps1 -Mode Status"),
        "recommended_route": "/lens/host/persistent-supervision/enablement/authority",
        "recommended_readiness_route": "/lens/host/persistent-supervision/enablement/authority/readiness",
        "authority_required": "persistent_process_supervision_authority",
        "read_only_contract": True,
        "diagnostic_only": True,
        "would_execute": False,
        "would_mutate": False,
        "authority_granted": False,
    }
    assert payload["governance"] == {
        "diagnostic_only": True,
        "route_readback_contract": True,
        "wraps_resident_host_runtime_boundary_proof": True,
        "wraps_persistent_supervision_plan_route": True,
        "wraps_persistent_supervision_enablement_route": True,
        "child_proof_timeout_seconds": 180,
        "bounded_local_process_launch": True,
        "bounded_process_launch": True,
        "temporary_runtime_state_write": True,
        "product_execution_authority": False,
        "execution_authority": False,
        "approval_decision_authority": False,
        "local_process_launch_authority": True,
        "api_local_process_launch_authority": False,
        "process_supervision_authority": False,
        "process_restart_authority": False,
        "service_install_authority": False,
        "service_control_authority": False,
        "persistent_supervision_enablement_authority": False,
        "persistent_supervision_execution_authority": False,
        "service_config_write_authority": False,
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
