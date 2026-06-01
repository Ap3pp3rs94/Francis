from __future__ import annotations

import json
import os
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


def _run_proof(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    return subprocess.run(
        [
            _powershell(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(_repo_root() / "scripts" / "federation-stage16-remote-approval-runtime-proof.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
        timeout=90,
        env=merged_env,
    )


def test_federation_stage16_remote_approval_runtime_proof_records_roundtrip_readback(
    tmp_path: Path,
) -> None:
    data_dir = tmp_path / "data"

    proc = _run_proof("-Mode", "Status", "-DataDir", str(data_dir))

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "francis.stage16.federation.remote_approval_runtime_proof"
    assert payload["status"] == "proof_passed"
    assert payload["ok"] is True
    assert payload["stage"] == "Stage 16 / Federation"
    assert payload["commit_receipts"] is False
    assert payload["writes_real_project_data"] is False
    assert payload["actor"] == "stage16.federation.requester"
    assert payload["decision_actor"] == "stage16.local.operator"
    assert payload["readback_id"] == "live_remote_approval_roundtrip_observed"
    assert payload["receipt_id"].startswith("fedlive_live_remote_approval_roundtrip_observed_")
    assert payload["before_ready_count"] == 0
    assert payload["ready_count"] == 1
    assert payload["completion_eligible_readback_count"] == 1
    assert payload["required_count"] == 5
    assert payload["live_runtime_readback_ready"] is False
    assert payload["completion_review_ready"] is False
    assert payload["completion_status"] == "blocked"
    assert payload["ready_to_close"] is False
    assert payload["next_smallest_truthful_gap"] == "stage16_live_federation_runtime_readback"
    assert payload["recommended_next_slice"] == "collect_remaining_live_federation_runtime_readbacks"
    assert "live_remote_approval_roundtrip_observed" not in payload["missing_readbacks"]

    approved_path = data_dir / "approvals" / "approved" / f"{payload['approval_id']}.json"
    pending_path = data_dir / "approvals" / "pending" / f"{payload['approval_id']}.json"
    receipt_path = data_dir / "logs" / "federation" / "stage16_live_runtime_readbacks.jsonl"
    registry_path = data_dir / "federation" / "_registry.json"
    assert approved_path.exists()
    assert not pending_path.exists()
    assert receipt_path.exists()
    assert registry_path.exists()

    approved = json.loads(approved_path.read_text(encoding="utf-8"))
    assert approved["status"] == "approved"
    assert approved["decision_actor"] == "stage16.local.operator"
    assert approved["payload"]["contains_raw_private_data"] is False
    assert approved["payload"]["contains_raw_prompt_body"] is False
    assert approved["payload"]["contains_raw_model_response"] is False
    assert approved["payload"]["grants_execution_authority"] is False
    assert approved["payload"]["grants_mutation_authority"] is False

    receipts = [json.loads(line) for line in receipt_path.read_text(encoding="utf-8").splitlines()]
    assert [item["readback_id"] for item in receipts] == ["live_remote_approval_roundtrip_observed"]
    assert receipts[0]["proof_kind"] == "live_runtime_probe"
    assert receipts[0]["actor"] == "stage16.federation.requester"
    assert receipts[0]["parent_receipt_id"] == payload["approval_id"]
    assert receipts[0]["readback_ready"] is True
    assert receipts[0]["governance"]["permission_scope"] == "federation.write"
    assert receipts[0]["governance"]["writes_memory"] is False
    assert receipts[0]["governance"]["grants_execution_authority"] is False
    assert receipts[0]["governance"]["grants_mutation_authority"] is False

    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    assert any(
        item["kind"] == "stage16_remote_approval_roundtrip" and item["meta"]["approval_id"] == payload["approval_id"]
        for item in registry["consensus_logs"]
    )

    governance = payload["governance"]
    assert governance["local_loopback_only"] is True
    assert governance["request_metadata_only"] is True
    assert governance["decision_receipt_reference_only"] is True
    assert governance["operator_impersonation_allowed"] is False
    assert governance["scope_expansion_allowed"] is False
    assert governance["contains_raw_private_data"] is False
    assert governance["contains_raw_prompt_body"] is False
    assert governance["contains_raw_model_response"] is False
    assert governance["does_not_mark_stage16_closed"] is True
    assert governance["writes_memory"] is False
    assert governance["grants_execution_authority"] is False
    assert governance["grants_mutation_authority"] is False

    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["approval_request_written"]["status"] == "pending"
    assert checks["operator_decision_receipt_written"]["status"] == "approved"
    assert checks["federation_trace_written"]["status"] == "observed"
    assert checks["remote_approval_runtime_receipt_written"]["status"] == "observed"
    assert checks["completion_review_remains_blocked"]["status"] == "blocked"
    assert all(item["passed"] for item in payload["checks"])


def test_federation_stage16_remote_approval_runtime_proof_blocks_commit_in_production() -> None:
    proc = _run_proof("-Mode", "Status", "-CommitReceipts", env={"FRANCIS_ENV_PROFILE": "production"})

    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "francis.stage16.federation.remote_approval_runtime_proof"
    assert payload["status"] == "proof_failed"
    assert payload["ok"] is False
    assert payload["error"] == "commit_receipts_blocked_in_env_profile"
    assert payload["commit_receipts"] is True
    assert payload["writes_real_project_data"] is False
    assert payload["ready_to_close"] is False
