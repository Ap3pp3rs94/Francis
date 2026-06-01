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
            str(_repo_root() / "scripts" / "federation-stage16-local-loopback-runtime-proof.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
        timeout=90,
        env=merged_env,
    )


def test_federation_stage16_local_loopback_runtime_proof_records_partial_live_readbacks(
    tmp_path: Path,
) -> None:
    data_dir = tmp_path / "data"

    proc = _run_proof("-Mode", "Status", "-DataDir", str(data_dir))

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "francis.stage16.federation.local_loopback_runtime_proof"
    assert payload["status"] == "proof_passed"
    assert payload["ok"] is True
    assert payload["stage"] == "Stage 16 / Federation"
    assert payload["commit_receipts"] is False
    assert payload["writes_real_project_data"] is False
    assert payload["writes_registry"] is True
    assert payload["writes_live_readback_receipts"] is True
    assert payload["actor"] == "test.federation.write"
    assert payload["source_node_id"] == "stage16-local-workstation"
    assert payload["paired_node_id"] == "stage16-local-loopback-node"
    assert payload["pairing_scope"] == "pairing:stage16-local-loopback"
    assert payload["knowledge_id"] == "stage16-local-loopback-shared-metadata"
    assert payload["recorded_readback_ids"] == [
        "live_pairing_flow_observed",
        "live_selective_sync_observed",
    ]
    assert payload["remaining_readback_ids"] == [
        "live_remote_approval_roundtrip_observed",
        "live_revocation_roundtrip_observed",
        "workstation_sleep_continuity_validated",
    ]
    assert payload["missing_readbacks"] == payload["remaining_readback_ids"]
    assert payload["readback_summary_status"] == "partial"
    assert payload["receipt_ready_count"] == 2
    assert payload["ready_count"] == 2
    assert payload["completion_eligible_readback_count"] == 2
    assert payload["required_count"] == 5
    assert payload["live_runtime_readback_ready"] is False
    assert payload["completion_review_ready"] is False
    assert payload["completion_status"] == "blocked"
    assert payload["ready_to_close"] is False
    assert payload["next_smallest_truthful_gap"] == "stage16_remote_approval_runtime_readback"
    assert payload["recommended_next_slice"] == "collect_remote_approval_runtime_readback"

    registry_path = Path(payload["registry_path"])
    receipt_path = Path(payload["receipt_path"])
    assert registry_path.exists()
    assert receipt_path.exists()

    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    assert set(registry["instances"]) >= {"stage16-local-workstation", "stage16-local-loopback-node"}
    assert any(item["scope"] == "pairing:stage16-local-loopback" for item in registry["delegations"])
    assert any(item["id"] == "stage16-local-loopback-shared-metadata" for item in registry["shared_knowledge"])
    assert any(item["kind"] == "stage16_local_loopback_runtime_readback" for item in registry["consensus_logs"])

    receipts = [json.loads(line) for line in receipt_path.read_text(encoding="utf-8").splitlines()]
    assert [item["readback_id"] for item in receipts] == payload["recorded_readback_ids"]
    assert all(item["actor"] == "test.federation.write" for item in receipts)
    assert all(item["proof_kind"] == "live_runtime_probe" for item in receipts)
    assert all(item["readback_ready"] is True for item in receipts)
    assert all(item["governance"]["permission_scope"] == "federation.write" for item in receipts)
    assert all(item["governance"]["writes_memory"] is False for item in receipts)
    assert all(item["governance"]["grants_execution_authority"] is False for item in receipts)
    assert all(item["governance"]["grants_mutation_authority"] is False for item in receipts)

    governance = payload["governance"]
    assert governance["local_loopback_only"] is True
    assert governance["commit_mode_requires_dev_or_workstation_profile"] is True
    assert governance["does_not_mark_stage16_closed"] is True
    assert governance["does_not_execute_remote_approval"] is True
    assert governance["does_not_execute_revocation"] is True
    assert governance["does_not_probe_sleep_resume"] is True
    assert governance["contains_raw_private_data"] is False
    assert governance["contains_raw_prompt_body"] is False
    assert governance["contains_raw_model_response"] is False
    assert governance["writes_memory"] is False
    assert governance["grants_execution_authority"] is False
    assert governance["grants_mutation_authority"] is False

    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["pairing_flow_readback"]["status"] == "observed"
    assert checks["selective_sync_readback"]["status"] == "observed"
    assert checks["trace_readback"]["status"] == "observed"
    assert checks["completion_evidence_records_only_provable_readbacks"]["status"] == "partial"
    assert checks["completion_review_remains_blocked"]["status"] == "blocked"
    assert checks["status_surface_remains_blocked"]["status"] == "stage16_contracts_ready_completion_blocked"
    assert all(item["passed"] for item in payload["checks"])


def test_federation_stage16_local_loopback_runtime_proof_blocks_commit_in_production() -> None:
    proc = _run_proof("-Mode", "Status", "-CommitReceipts", env={"FRANCIS_ENV_PROFILE": "production"})

    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "francis.stage16.federation.local_loopback_runtime_proof"
    assert payload["status"] == "proof_failed"
    assert payload["ok"] is False
    assert payload["error"] == "commit_receipts_blocked_in_env_profile"
    assert payload["commit_receipts"] is True
    assert payload["writes_real_project_data"] is False
    assert payload["ready_to_close"] is False
