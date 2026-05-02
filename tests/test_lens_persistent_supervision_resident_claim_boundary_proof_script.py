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
            str(_repo_root() / "scripts" / "lens-persistent-supervision-resident-claim-boundary-proof.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
        timeout=90,
    )


def test_lens_persistent_supervision_resident_claim_boundary_is_readback_only(
    tmp_path: Path,
) -> None:
    data_dir = tmp_path / "data"
    proc = _run_proof("-Mode", "Status", "-DataDir", str(data_dir))

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.host.persistent_supervision_resident_claim_boundary.proof"
    assert payload["status"] == "proof_passed"
    assert payload["ok"] is True
    assert payload["authority_family"] == "resident_claim"
    assert payload["previous_authority_family"] == "persistent_supervision_execution"
    assert payload["next_authority_family"] == ""
    assert payload["persistent_supervision_resident_claim_boundary_observed"] is True
    assert payload["persistent_supervision_execution_authority_proof_observed"] is True
    assert payload["persistent_supervision_plan_observed"] is True
    assert payload["side_effects_denied"] is True
    assert payload["final_persistent_supervision_authority_family_consumed"] is True
    assert payload["persistent_supervision_enablement_authority"] is True
    assert payload["service_config_write_authority"] is True
    assert payload["persistent_supervision_execution_authority"] is True
    assert payload["receipt_write_authority"] is True
    assert payload["resident_claim_authority"] is False
    assert payload["persistent_supervision_ready"] is False
    assert payload["resident_claim_allowed"] is False
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

    resident_claim = payload["resident_claim"]
    assert resident_claim["status"] == "blocked"
    assert resident_claim["ready"] is False
    assert resident_claim["authority_granted"] is False
    assert resident_claim["would_execute"] is False
    assert resident_claim["route"] == "/lens/host/persistent-supervision/enablement/execution"
    assert "/lens/host/persistent-supervision/enablement/execution" in resident_claim["evidence"]
    assert "/lens/host/persistent-supervision/enablement/execution/readiness" in resident_claim["evidence"]
    assert resident_claim["required_before"] == [
        "process_supervision_enabled",
        "persistent_supervision_enabled",
    ]
    assert "persistent_supervision_disabled" in resident_claim["blockers"]
    assert "process_supervision_disabled" in resident_claim["blockers"]
    assert "resident_claim_authority_not_granted" in resident_claim["blockers"]
    assert "service_config_write_authority_not_granted" not in resident_claim["blockers"]
    assert "persistent_supervision_execution_authority_not_granted" not in resident_claim["blockers"]
    assert "receipt_write_authority_not_granted" not in resident_claim["blockers"]

    assert "resident_claim_authority_not_granted" in payload["blockers"]
    assert payload["remaining_authority_families_after_this_boundary"] == []
    assert payload["next_smallest_truthful_gap"] == "stage6_lens_completion_audit"

    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["persistent_supervision_execution_authority_proof"]["status"] == "proof_observed"
    assert checks["persistent_supervision_plan_readback"]["status"] == "blocked"
    assert checks["resident_claim_boundary"]["status"] == "blocked"
    assert checks["resident_claim_side_effects_denied"]["status"] == "denied_no_resident_claim"
    assert checks["authority_boundary"]["status"] == "diagnostic_bounded"
    assert all(item["passed"] for item in payload["checks"])

    governance = payload["governance"]
    assert governance["diagnostic_only"] is True
    assert governance["wraps_existing_execution_authority_proof"] is True
    assert governance["persistent_supervision_plan_readback"] is True
    assert governance["test_fixture_approval_decisions"] is True
    assert governance["test_fixture_authority_receipts"] is True
    assert governance["product_execution_authority"] is False
    assert governance["execution_authority"] is False
    assert governance["approval_decision_authority"] is False
    assert governance["local_process_launch_authority"] is False
    assert governance["process_supervision_authority"] is False
    assert governance["service_control_authority"] is False
    assert governance["memory_write"] is False
    assert governance["receipt_write_authority"] is False
    assert governance["resident_claim_authority"] is False
    assert governance["mutation_authority_granted"] is False

    assert not (data_dir / "runtime" / "lens-host-supervisor" / "status.json").exists()
    assert not (data_dir / "runtime" / "lens-host" / "status.json").exists()
    assert not (data_dir / "runtime" / "lens-host" / "lens-host.pid").exists()
