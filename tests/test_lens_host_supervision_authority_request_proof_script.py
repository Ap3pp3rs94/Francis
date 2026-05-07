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
            str(_repo_root() / "scripts" / "lens-host-supervision-authority-request-proof.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
        timeout=60,
    )


def test_lens_host_supervision_authority_request_proof_consumes_exact_request(
    tmp_path: Path,
) -> None:
    data_dir = tmp_path / "data"
    proc = _run_proof("-Mode", "Status", "-DataDir", str(data_dir))

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.host.supervision_authority_exact_approval_request.proof"
    assert payload["status"] == "proof_passed"
    assert payload["ok"] is True
    assert payload["host_supervision_authority_approval_id"]
    assert payload["host_supervision_authority_grant_receipt_id"]
    assert payload["authority_granted"] is True
    assert payload["grant_applied"] is True
    assert payload["executed"] is False
    assert payload["supervision_ready"] is False
    assert payload["resident_claim_allowed"] is False
    assert payload["process_supervision_authority"] is True
    assert payload["process_restart_authority"] is True
    assert payload["service_install_authority"] is True
    assert payload["service_control_authority"] is True
    assert payload["receipt_write_authority"] is True
    assert payload["resident_claim_authority"] is True
    assert payload["memory_write"] is False
    assert payload["next_smallest_truthful_gap"] == "persistent_supervision_enablement_disabled"

    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["readiness_before_points_to_exact_approval_request"]["status"] == "blocked"
    assert checks["authority_request_created"]["status"] == "approval_requested"
    assert checks["request_readback"]["status"] == "pending_review"
    assert checks["pending_grant_blocked"]["status"] == "blocked"
    assert checks["approval_decision_fixture"]["status"] == "approved"
    assert checks["authority_granted"]["status"] == "authority_granted"
    assert checks["grant_receipt_readback"]["status"] == "readback_ready"
    assert checks["denial_readback_empty_after_valid_grant"]["status"] == "empty"
    assert checks["readiness_after_consumes_exact_approval"]["status"] == "blocked"
    assert checks["persistent_enablement_boundary"]["status"] == "blocked"
    assert checks["lens_status_readback"]["status"] == "readback_ready"
    assert checks["no_runtime_started"]["status"] == "no_runtime_files"
    assert checks["authority_boundaries_intact"]["status"] == "bounded"
    assert all(item["passed"] for item in payload["checks"])

    proof = payload["proof"]
    assert proof["readiness_before_status"] == "blocked"
    assert proof["readiness_before_next_gap"] == "host_supervision_authority_exact_approval_request"
    assert proof["request_status"] == "approval_requested"
    assert proof["request_readback_status"] == "pending_review"
    assert proof["pending_grant_status"] == "blocked"
    assert proof["decision_status"] == "approved"
    assert proof["grant_status"] == "authority_granted"
    assert proof["grant_receipt_kind"] == "lens.host.supervision_authority.grant.receipt"
    assert proof["grant_receipts_status"] == "readback_ready"
    assert proof["readiness_after_status"] == "blocked"
    assert proof["readiness_after_active_grant_receipt_id"] == payload["host_supervision_authority_grant_receipt_id"]
    assert proof["persistent_plan_status"] == "blocked"
    assert proof["persistent_plan_next_gap"] == "persistent_supervision_enablement_disabled"
    assert proof["enablement_status"] == "blocked"
    assert proof["enablement_next_gap"] == "persistent_supervision_enablement_disabled"
    assert proof["status_grants_authority_granted"] is True
    assert proof["status_active_grant_receipt_id"] == payload["host_supervision_authority_grant_receipt_id"]
    assert proof["status_readiness_request_readback_ready"] is True
    assert proof["status_readiness_resident_claim_allowed"] is False
    assert proof["status_stage6_requirement_ready"] is False

    assert "process_supervision_disabled" in payload["blockers"]
    assert "persistent_supervision_disabled" in payload["blockers"]
    assert payload["runtime_files"] == {
        "lens_host_status": False,
        "lens_host_pid": False,
        "lens_host_supervisor_status": False,
    }
    assert payload["governance"] == {
        "diagnostic_only": True,
        "api_route_proof": True,
        "approval_request_write": True,
        "test_fixture_approval_decisions": True,
        "approval_decision_authority": False,
        "execution_authority": False,
        "local_process_launch_authority": False,
        "process_supervision_authority": True,
        "process_restart_authority": True,
        "service_install_authority": True,
        "service_control_authority": True,
        "persistent_supervision_enablement_authority": False,
        "service_config_write_authority": False,
        "persistent_supervision_execution_authority": False,
        "receipt_write_authority": True,
        "memory_write": False,
        "resident_claim_authority": True,
        "mutation_authority_granted": False,
    }

    assert not (data_dir / "runtime" / "lens-host-supervisor" / "status.json").exists()
    assert not (data_dir / "runtime" / "lens-host" / "status.json").exists()
    assert not (data_dir / "runtime" / "lens-host" / "lens-host.pid").exists()
