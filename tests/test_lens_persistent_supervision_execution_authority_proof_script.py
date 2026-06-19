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
            str(_repo_root() / "scripts" / "lens-persistent-supervision-execution-authority-proof.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
        timeout=60,
    )


def test_lens_persistent_supervision_execution_authority_proof_stops_at_resident_claim(
    tmp_path: Path,
) -> None:
    data_dir = tmp_path / "data"
    proc = _run_proof("-Mode", "Status", "-DataDir", str(data_dir))

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.host.persistent_supervision_execution_authority.proof"
    assert payload["status"] == "proof_passed"
    assert payload["ok"] is True
    assert payload["host_supervision_authority_grant_receipt_id"]
    assert payload["persistent_supervision_enablement_authority_grant_receipt_id"]
    assert payload["persistent_supervision_execution_authority_grant_receipt_id"]
    assert payload["persistent_supervision_enablement_authority"] is True
    assert payload["service_config_write_authority"] is True
    assert payload["persistent_supervision_execution_authority"] is True
    assert payload["receipt_write_authority"] is True
    assert payload["persistent_supervision_enablement_allowed"] is False
    assert payload["resident_claim_allowed"] is False
    assert payload["grant_applied"] is True
    assert payload["enablement_applied"] is False
    assert payload["applied"] is False
    assert payload["executed"] is False
    assert payload["service_config_updated"] is False
    assert payload["would_update_service_config"] is False
    assert payload["would_enable_persistent_supervision"] is False
    assert payload["would_start_service"] is False
    assert payload["would_supervise_process"] is False
    assert payload["would_restart_process"] is False
    assert payload["would_write_receipt"] is False
    assert payload["would_write_memory"] is False
    assert payload["would_claim_resident"] is False
    assert (
        payload["previous_next_smallest_truthful_gap"]
        == "persistent_supervision_execution_authority_or_resident_claim_boundary"
    )
    assert payload["next_smallest_truthful_gap"] == "persistent_supervision_resident_claim_authority_boundary"
    assert (
        payload["recommended_next_slice"]
        == "review_persistent_supervision_resident_claim_boundary_without_runtime_start"
    )
    assert (
        payload["recommended_proof_script"]
        == "scripts/lens-persistent-supervision-resident-claim-boundary-proof.ps1 -Mode Status"
    )
    assert payload["recommended_handoff_source"] == "persistent_supervision_execution_authority_handoff"
    assert payload["authority_required"] == "resident_claim_authority"
    assert payload["authority_granted"] is False
    assert payload["recommended_route"] == "/lens/host/persistent-supervision/enablement/execution"
    assert payload["recommended_readiness_route"] == "/lens/host/persistent-supervision/enablement/execution/readiness"
    assert payload["persistent_supervision_execution_route"] == "/lens/host/persistent-supervision/enablement/execution"
    assert (
        payload["persistent_supervision_execution_request_route"]
        == "/lens/host/persistent-supervision/enablement/execution/request"
    )
    assert (
        payload["persistent_supervision_execution_authority_route"]
        == "/lens/host/persistent-supervision/enablement/execution/authority"
    )
    assert (
        payload["persistent_supervision_execution_authority_grants_route"]
        == "/lens/host/persistent-supervision/enablement/execution/authority/grants"
    )
    assert (
        payload["persistent_supervision_execution_readiness_route"]
        == "/lens/host/persistent-supervision/enablement/execution/readiness"
    )
    assert payload["handoff"] == {
        "recommended_handoff_source": "persistent_supervision_execution_authority_handoff",
        "status": "blocked",
        "previous_next_smallest_truthful_gap": (
            "persistent_supervision_execution_authority_or_resident_claim_boundary"
        ),
        "next_smallest_truthful_gap": "persistent_supervision_resident_claim_authority_boundary",
        "next_step": "review_persistent_supervision_resident_claim_boundary_without_runtime_start",
        "proof_script": "scripts/lens-persistent-supervision-resident-claim-boundary-proof.ps1 -Mode Status",
        "route": "/lens/host/persistent-supervision/enablement/execution",
        "readiness_route": "/lens/host/persistent-supervision/enablement/execution/readiness",
        "authority_required": "resident_claim_authority",
        "authority_granted": False,
        "read_only_contract": True,
        "diagnostic_only": True,
        "would_execute": False,
        "would_mutate": False,
    }

    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["host_supervision_authority_granted"]["status"] == "authority_granted"
    assert checks["enablement_authority_granted"]["status"] == "authority_granted"
    assert checks["execution_authority_request_ready"]["status"] == "approval_requested"
    assert checks["pending_execution_blocked"]["status"] == "blocked"
    assert checks["approved_request_without_grant_blocked"]["status"] == "denied_no_service_config_write_authority"
    assert checks["execution_authority_granted"]["status"] == "authority_granted"
    assert checks["grant_receipt_readback"]["status"] == "readback_ready"
    assert checks["execution_readiness_promoted_to_resident_claim"]["status"] == "blocked_authority_granted"
    assert checks["execution_denial_after_grant"]["status"] == "denied_no_resident_claim_authority"
    assert checks["lens_status_readback"]["status"] == "readback_ready"
    assert checks["no_runtime_started"]["status"] == "no_runtime_files"
    assert checks["authority_boundaries_intact"]["status"] == "bounded"
    assert all(item["passed"] for item in payload["checks"])

    proof = payload["proof"]
    assert proof["host_grant_status"] == "authority_granted"
    assert proof["enablement_authority_grant_status"] == "authority_granted"
    assert proof["execution_request_status"] == "approval_requested"
    assert proof["pending_denial_status"] == "blocked"
    assert proof["approved_denial_status"] == "denied_no_service_config_write_authority"
    assert proof["execution_authority_grant_status"] == "authority_granted"
    assert proof["execution_authority_grant_receipt_written"] is True
    assert proof["grant_receipts_status"] == "readback_ready"
    assert proof["grant_receipts_total"] == 1
    assert proof["readiness_status"] == "blocked"
    assert proof["readiness_execution_authority_granted"] is True
    assert proof["readiness_resident_claim_allowed"] is False
    assert proof["execution_denial_status"] == "denied_no_resident_claim_authority"
    assert proof["execution_denial_reason"] == "resident_claim_authority_not_granted"
    assert proof["status_requests_authority_granted"] is True
    assert proof["status_grants_authority_granted"] is True
    assert proof["status_readiness_execution_authority_granted"] is True
    assert proof["status_denial_boundary_status"] == "blocked"

    assert "service_config_write_authority_not_granted" not in payload["blockers"]
    assert "persistent_supervision_execution_authority_not_granted" not in payload["blockers"]
    assert "receipt_write_authority_not_granted" not in payload["blockers"]
    assert "resident_claim_authority_not_granted" in payload["blockers"]

    assert payload["governance"] == {
        "diagnostic_only": True,
        "api_route_proof": True,
        "approval_request_write": True,
        "test_fixture_approval_decisions": True,
        "approval_decision_authority": False,
        "execution_authority": False,
        "local_process_launch_authority": False,
        "process_supervision_authority": False,
        "process_restart_authority": False,
        "service_install_authority": False,
        "service_control_authority": False,
        "persistent_supervision_enablement_authority": True,
        "service_config_write_authority": True,
        "persistent_supervision_execution_authority": True,
        "receipt_write_authority": True,
        "memory_write": False,
        "resident_claim_authority": False,
        "mutation_authority_granted": False,
    }

    assert not (data_dir / "runtime" / "lens-host-supervisor" / "status.json").exists()
    assert not (data_dir / "runtime" / "lens-host" / "status.json").exists()
    assert not (data_dir / "runtime" / "lens-host" / "lens-host.pid").exists()


def test_lens_persistent_supervision_execution_authority_proof_keeps_python_stderr_out_of_json_stdout() -> None:
    script = (_repo_root() / "scripts" / "lens-persistent-supervision-execution-authority-proof.ps1").read_text(
        encoding="utf-8"
    )

    assert "$PythonStderrPath = Join-Path $ProofRuntimeDir 'python-stderr.txt'" in script
    assert "$Output = & $PythonPath $PythonScriptPath 2> $PythonStderrPath" in script
    assert "$Output = & $PythonPath $PythonScriptPath 2>&1" not in script
    assert "warnings.filterwarnings(" in script
    assert "Using `httpx` with `starlette\\.testclient` is deprecated" in script
    assert "python_proof_failed_without_json" in script
