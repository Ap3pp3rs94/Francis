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
            str(_repo_root() / "scripts" / "federation-stage16-revocation-runtime-proof.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
        timeout=90,
        env=merged_env,
    )


def test_federation_stage16_revocation_runtime_proof_records_revoked_scope_readback(
    tmp_path: Path,
) -> None:
    data_dir = tmp_path / "data"

    proc = _run_proof("-Mode", "Status", "-DataDir", str(data_dir))

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "francis.stage16.federation.revocation_runtime_proof"
    assert payload["status"] == "proof_passed"
    assert payload["ok"] is True
    assert payload["stage"] == "Stage 16 / Federation"
    assert payload["commit_receipts"] is False
    assert payload["writes_real_project_data"] is False
    assert payload["actor"] == "stage16.federation.revoker"
    assert payload["decision_actor"] == "stage16.local.operator"
    assert payload["readback_id"] == "live_revocation_roundtrip_observed"
    assert payload["receipt_id"].startswith("fedlive_live_revocation_roundtrip_observed_")
    assert payload["active_delegation_id"].startswith("deleg-stage16-revocation-active-")
    assert payload["revoked_delegation_id"].startswith("deleg-stage16-revocation-revoked-")
    assert payload["revoked_scope"] == "pairing:stage16-revocation-loopback"
    assert payload["before_ready_count"] == 0
    assert payload["ready_count"] == 1
    assert payload["completion_eligible_readback_count"] == 1
    assert payload["required_count"] == 5
    assert payload["live_runtime_readback_ready"] is False
    assert payload["completion_review_ready"] is False
    assert payload["completion_status"] == "blocked"
    assert payload["ready_to_close"] is False
    assert payload["next_smallest_truthful_gap"] == "stage16_live_federation_runtime_readback"

    approved_path = data_dir / "approvals" / "approved" / f"{payload['approval_id']}.json"
    receipt_path = data_dir / "logs" / "federation" / "stage16_live_runtime_readbacks.jsonl"
    registry_path = data_dir / "federation" / "_registry.json"
    assert approved_path.exists()
    assert receipt_path.exists()
    assert registry_path.exists()

    approved = json.loads(approved_path.read_text(encoding="utf-8"))
    assert approved["status"] == "approved"
    assert approved["decision_actor"] == "stage16.local.operator"
    assert approved["payload"]["revoked_scope"] == payload["revoked_scope"]
    assert approved["payload"]["contains_raw_private_data"] is False
    assert approved["payload"]["contains_raw_prompt_body"] is False
    assert approved["payload"]["contains_raw_model_response"] is False
    assert approved["payload"]["grants_execution_authority"] is False
    assert approved["payload"]["grants_mutation_authority"] is False

    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    delegations = [item for item in registry["delegations"] if item["scope"] == payload["revoked_scope"]]
    assert [item["status"] for item in sorted(delegations, key=lambda item: item["ts"])] == ["active", "revoked"]
    latest = sorted(delegations, key=lambda item: item["ts"], reverse=True)[0]
    assert latest["id"] == payload["revoked_delegation_id"]
    assert latest["status"] == "revoked"
    assert latest["meta"]["operator_receipt_id"] == payload["approval_id"]
    assert latest["meta"]["remote_approval_relays_stopped"] is True
    assert latest["meta"]["sync_lanes_stopped"] is True
    assert latest["meta"]["silent_reactivation_allowed"] is False
    assert latest["meta"]["authority_expansion"] is False
    assert any(
        item["kind"] == "stage16_revocation_roundtrip"
        and item["meta"]["revoked_delegation_id"] == payload["revoked_delegation_id"]
        for item in registry["consensus_logs"]
    )

    receipts = [json.loads(line) for line in receipt_path.read_text(encoding="utf-8").splitlines()]
    assert [item["readback_id"] for item in receipts] == ["live_revocation_roundtrip_observed"]
    assert receipts[0]["proof_kind"] == "live_runtime_probe"
    assert receipts[0]["actor"] == "stage16.federation.revoker"
    assert receipts[0]["parent_receipt_id"] == payload["approval_id"]
    assert receipts[0]["readback_ready"] is True
    assert receipts[0]["governance"]["permission_scope"] == "federation.write"
    assert receipts[0]["governance"]["writes_memory"] is False
    assert receipts[0]["governance"]["grants_execution_authority"] is False
    assert receipts[0]["governance"]["grants_mutation_authority"] is False

    governance = payload["governance"]
    assert governance["operator_receipt_required"] is True
    assert governance["per_node_scope_required"] is True
    assert governance["latest_scope_event_revoked"] is True
    assert governance["remote_approval_relays_stopped"] is True
    assert governance["sync_lanes_stopped"] is True
    assert governance["silent_reactivation_allowed"] is False
    assert governance["authority_expansion_allowed"] is False
    assert governance["contains_raw_private_data"] is False
    assert governance["does_not_mark_stage16_closed"] is True
    assert governance["writes_memory"] is False
    assert governance["grants_execution_authority"] is False
    assert governance["grants_mutation_authority"] is False

    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["active_pairing_precondition_readback"]["status"] == "active"
    assert checks["operator_revocation_receipt_readback"]["status"] == "approved"
    assert checks["latest_scope_state_revoked"]["status"] == "revoked"
    assert checks["revocation_trace_written"]["status"] == "observed"
    assert checks["revocation_runtime_receipt_written"]["status"] == "observed"
    assert checks["completion_review_remains_blocked"]["status"] == "blocked"
    assert all(item["passed"] for item in payload["checks"])


def test_federation_stage16_revocation_runtime_proof_blocks_commit_in_production() -> None:
    proc = _run_proof("-Mode", "Status", "-CommitReceipts", env={"FRANCIS_ENV_PROFILE": "production"})

    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "francis.stage16.federation.revocation_runtime_proof"
    assert payload["status"] == "proof_failed"
    assert payload["ok"] is False
    assert payload["error"] == "commit_receipts_blocked_in_env_profile"
    assert payload["commit_receipts"] is True
    assert payload["writes_real_project_data"] is False
    assert payload["ready_to_close"] is False
