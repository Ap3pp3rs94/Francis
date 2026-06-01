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
            str(_repo_root() / "scripts" / "federation-stage16-live-runtime-readback-proof.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
        timeout=90,
    )


def test_federation_stage16_live_runtime_readback_proof_records_isolated_receipts(
    tmp_path: Path,
) -> None:
    data_dir = tmp_path / "data"
    proc = _run_proof("-Mode", "Status", "-DataDir", str(data_dir))

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "francis.stage16.federation.live_runtime_readback_proof"
    assert payload["status"] == "proof_passed"
    assert payload["ok"] is True
    assert payload["stage"] == "Stage 16 / Federation"
    assert payload["isolated_data_dir"] is True
    assert payload["writes_real_project_receipts"] is False
    assert payload["project_stage_closure_changed"] is False
    assert payload["denied_unscoped_write"] is True
    assert payload["before_live_runtime_readback_ready"] is False
    assert payload["before_completion_review_ready"] is False
    assert payload["readback_receipts_ready"] is True
    assert payload["live_runtime_readback_ready"] is False
    assert payload["completion_eligible_readback_count"] == 0
    assert payload["completion_review_ready"] is False
    assert (
        payload["isolated_completion_review_next_smallest_truthful_gap"] == "stage16_live_federation_runtime_readback"
    )
    assert payload["next_smallest_truthful_gap"] == "stage16_live_federation_runtime_readback"
    assert payload["recommended_next_slice"] == "collect_real_live_federation_runtime_readbacks"
    assert payload["readback_receipts_recorded"] == 5
    assert payload["receipt_line_count"] == 5
    assert payload["readback_ids"] == [
        "live_pairing_flow_observed",
        "live_selective_sync_observed",
        "live_remote_approval_roundtrip_observed",
        "live_revocation_roundtrip_observed",
        "workstation_sleep_continuity_validated",
    ]

    receipt_path = Path(payload["receipt_path"])
    assert receipt_path.exists()
    receipt_lines = receipt_path.read_text(encoding="utf-8").splitlines()
    assert len(receipt_lines) == 5
    receipts = [json.loads(line) for line in receipt_lines]
    assert {item["readback_id"] for item in receipts} == set(payload["readback_ids"])
    assert all(item["actor"] == "test.federation.write" for item in receipts)
    assert all(item["readback_ready"] is True for item in receipts)
    assert all(item["governance"]["permission_scope"] == "federation.write" for item in receipts)
    assert all(item["governance"]["readback_receipt"] is True for item in receipts)
    assert all(item["governance"]["grants_execution_authority"] is False for item in receipts)
    assert all(item["governance"]["grants_mutation_authority"] is False for item in receipts)

    governance = payload["governance"]
    assert governance["isolated_proof"] is True
    assert governance["readback_receipt_path_only"] is True
    assert governance["requires_federation_write_scope"] is True
    assert governance["writes_real_project_receipts"] is False
    assert governance["writes_registry"] is False
    assert governance["writes_memory"] is False
    assert governance["runs_tools"] is False
    assert governance["runs_shell"] is False
    assert governance["runs_git"] is False
    assert governance["launches_browser"] is False
    assert governance["captures_screen"] is False
    assert governance["grants_execution_authority"] is False
    assert governance["grants_mutation_authority"] is False

    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["isolated_data_root"]["status"] == "isolated"
    assert checks["precheck_blocks_without_live_readbacks"]["status"] == "blocked"
    assert checks["permission_gate_blocks_unscoped_write"]["status"] == "denied"
    assert checks["five_readback_receipts_written"]["status"] == "receipts_ready"
    assert checks["receipt_file_readback"]["status"] == "jsonl_ready"
    assert checks["readback_summary_consumes_receipts"]["status"] == "partial"
    assert checks["completion_review_consumes_receipts"]["status"] == "blocked"
    assert (
        checks["status_surface_reflects_isolated_readiness"]["status"] == "stage16_contracts_ready_completion_blocked"
    )
    assert all(item["passed"] for item in payload["checks"])


def test_federation_stage16_live_runtime_readback_proof_refuses_project_data_root() -> None:
    proc = _run_proof("-Mode", "Status", "-DataDir", str(_repo_root() / "data"))

    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "francis.stage16.federation.live_runtime_readback_proof"
    assert payload["status"] == "proof_failed"
    assert payload["ok"] is False
    assert payload["error"] == "refusing_to_write_project_data_receipts"
    assert payload["writes_real_project_receipts"] is False
    assert payload["next_smallest_truthful_gap"] == "stage16_live_federation_runtime_readback"
