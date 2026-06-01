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
            str(_repo_root() / "scripts" / "federation-stage16-sleep-continuity-runtime-proof.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
        timeout=90,
        env=merged_env,
    )


def _write_sleep_evidence(root: Path, *, post_pre_sleep_path: str | None = None) -> tuple[Path, Path]:
    root.mkdir(parents=True, exist_ok=True)
    pre_path = root / "pre_sleep.json"
    post_path = root / "post_resume.json"
    pre = {
        "evidence_kind": "stage16_sleep_continuity_pre_sleep",
        "continuity_record_id": "stage16-sleep-continuity-record",
        "source_node_id": "stage16-local-workstation",
        "paired_node_id": "stage16-local-loopback-node",
        "trace_id": "trace-stage16-sleep-continuity-test",
        "authority_snapshot_id": "authsnap-stage16-sleep-test",
        "source_recorded_ts": 1_800_017_200,
        "freshness_state": "fresh",
        "governance": {
            "contains_raw_private_data": False,
            "contains_raw_prompt_body": False,
            "contains_raw_model_response": False,
        },
    }
    post = {
        "evidence_kind": "stage16_sleep_continuity_post_resume",
        "continuity_record_id": "stage16-sleep-continuity-record",
        "source_node_id": "stage16-local-workstation",
        "paired_node_id": "stage16-local-loopback-node",
        "trace_id": "trace-stage16-sleep-continuity-test",
        "authority_snapshot_id": "authsnap-stage16-sleep-test",
        "received_ts": 1_800_017_320,
        "freshness_state": "fresh",
        "redaction_summary": "metadata_only_no_private_payload",
        "sleep_observed": True,
        "resume_observed": True,
        "continuity_available_after_resume": True,
        "revoked_links_present_current_state": False,
        "stale_state_implies_current_authority": False,
        "pre_sleep_evidence_path": post_pre_sleep_path or str(pre_path.resolve()),
        "governance": {
            "contains_raw_private_data": False,
            "contains_raw_prompt_body": False,
            "contains_raw_model_response": False,
        },
    }
    pre_path.write_text(json.dumps(pre), encoding="utf-8")
    post_path.write_text(json.dumps(post), encoding="utf-8")
    return pre_path, post_path


def test_federation_stage16_sleep_continuity_runtime_proof_requires_explicit_evidence() -> None:
    proc = _run_proof("-Mode", "Status")

    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "francis.stage16.federation.sleep_continuity_runtime_proof"
    assert payload["status"] == "proof_failed"
    assert payload["ok"] is False
    assert payload["error"] == "pre_and_post_sleep_evidence_required"
    assert payload["evidence_required"] is True
    assert payload["ready_to_close"] is False
    assert payload["next_smallest_truthful_gap"] == "stage16_sleep_continuity_runtime_readback"


def test_federation_stage16_sleep_continuity_runtime_proof_records_manual_readback_with_evidence(
    tmp_path: Path,
) -> None:
    data_dir = tmp_path / "data"
    pre_path, post_path = _write_sleep_evidence(tmp_path / "evidence")

    proc = _run_proof(
        "-Mode",
        "Status",
        "-DataDir",
        str(data_dir),
        "-PreSleepEvidencePath",
        str(pre_path),
        "-PostResumeEvidencePath",
        str(post_path),
    )

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "francis.stage16.federation.sleep_continuity_runtime_proof"
    assert payload["status"] == "proof_passed"
    assert payload["ok"] is True
    assert payload["stage"] == "Stage 16 / Federation"
    assert payload["commit_receipts"] is False
    assert payload["writes_real_project_data"] is False
    assert payload["evidence_required"] is True
    assert payload["evidence_failures"] == []
    assert payload["actor"] == "stage16.federation.sleep_continuity"
    assert payload["continuity_record_id"] == "stage16-sleep-continuity-record"
    assert payload["source_node_id"] == "stage16-local-workstation"
    assert payload["paired_node_id"] == "stage16-local-loopback-node"
    assert payload["authority_snapshot_id"] == "authsnap-stage16-sleep-test"
    assert payload["readback_id"] == "workstation_sleep_continuity_validated"
    assert payload["receipt_id"].startswith("fedlive_workstation_sleep_continuity_validated_")
    assert payload["ready_count"] == 1
    assert payload["completion_eligible_readback_count"] == 1
    assert payload["required_count"] == 5
    assert payload["live_runtime_readback_ready"] is False
    assert payload["completion_review_ready"] is False
    assert payload["ready_to_close"] is False
    assert payload["recommended_next_slice"] == "collect_remaining_live_federation_runtime_readbacks"
    assert payload["next_smallest_truthful_gap"] == "stage16_pairing_runtime_readback"

    receipt_path = data_dir / "logs" / "federation" / "stage16_live_runtime_readbacks.jsonl"
    registry_path = data_dir / "federation" / "_registry.json"
    assert receipt_path.exists()
    assert registry_path.exists()

    receipt = json.loads(receipt_path.read_text(encoding="utf-8").splitlines()[0])
    assert receipt["readback_id"] == "workstation_sleep_continuity_validated"
    assert receipt["proof_kind"] == "manual_operator_runtime_readback"
    assert receipt["actor"] == "stage16.federation.sleep_continuity"
    assert receipt["parent_receipt_id"] == "stage16-sleep-continuity-record"
    assert receipt["readback_ready"] is True
    assert receipt["governance"]["permission_scope"] == "federation.write"
    assert receipt["governance"]["writes_memory"] is False
    assert receipt["governance"]["grants_execution_authority"] is False
    assert receipt["governance"]["grants_mutation_authority"] is False

    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    knowledge = next(item for item in registry["shared_knowledge"] if item["id"] == "stage16-sleep-continuity-record")
    assert knowledge["kind"] == "continuity_summary"
    assert knowledge["meta"]["freshness_state"] == "fresh"
    assert knowledge["meta"]["revoked_links_present_current_state"] is False
    assert knowledge["meta"]["stale_state_implies_current_authority"] is False
    assert knowledge["meta"]["contains_raw_private_data"] is False
    assert any(
        item["kind"] == "stage16_sleep_continuity_readback"
        and item["meta"]["continuity_record_id"] == "stage16-sleep-continuity-record"
        for item in registry["consensus_logs"]
    )

    governance = payload["governance"]
    assert governance["requires_explicit_pre_sleep_evidence"] is True
    assert governance["requires_explicit_post_resume_evidence"] is True
    assert governance["post_resume_pre_sleep_path_link_required"] is True
    assert governance["committed_evidence_paths_must_stay_under_project_evidence_root"] is True
    assert governance["committed_evidence_path_traversal_blocked"] is True
    assert governance["does_not_infer_sleep_from_delay"] is True
    assert governance["manual_operator_runtime_readback"] is True
    assert governance["redacted_continuity_summary_only"] is True
    assert governance["contains_raw_private_data"] is False
    assert governance["does_not_mark_stage16_closed"] is True
    assert governance["writes_memory"] is False
    assert governance["grants_execution_authority"] is False
    assert governance["grants_mutation_authority"] is False

    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["explicit_sleep_evidence_valid"]["status"] == "valid"
    assert checks["continuity_summary_readback"]["status"] == "observed"
    assert checks["sleep_continuity_trace_written"]["status"] == "observed"
    assert checks["sleep_continuity_runtime_receipt_written"]["status"] == "observed"
    assert all(item["passed"] for item in payload["checks"])


def test_federation_stage16_sleep_continuity_runtime_proof_rejects_mismatched_post_resume_pre_sleep_path(
    tmp_path: Path,
) -> None:
    data_dir = tmp_path / "data"
    wrong_pre_path = tmp_path / "wrong" / "pre_sleep.json"
    wrong_pre_path.parent.mkdir(parents=True, exist_ok=True)
    wrong_pre_path.write_text("{}", encoding="utf-8")
    pre_path, post_path = _write_sleep_evidence(
        tmp_path / "evidence",
        post_pre_sleep_path=str(wrong_pre_path),
    )

    proc = _run_proof(
        "-Mode",
        "Status",
        "-DataDir",
        str(data_dir),
        "-PreSleepEvidencePath",
        str(pre_path),
        "-PostResumeEvidencePath",
        str(post_path),
    )

    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "francis.stage16.federation.sleep_continuity_runtime_proof"
    assert payload["status"] == "proof_failed"
    assert payload["ok"] is False
    assert payload["evidence_failures"] == ["post_pre_sleep_evidence_path_mismatch"]
    assert payload["blockers"] == [
        "explicit_sleep_evidence_valid",
        "continuity_summary_readback",
        "sleep_continuity_trace_written",
        "sleep_continuity_runtime_receipt_written",
    ]
    assert payload["receipt_id"] == ""
    assert payload["ready_to_close"] is False
    assert payload["next_smallest_truthful_gap"] == "stage16_sleep_continuity_runtime_readback"


def test_federation_stage16_sleep_continuity_runtime_proof_commit_rejects_external_evidence_paths(
    tmp_path: Path,
) -> None:
    pre_path, post_path = _write_sleep_evidence(tmp_path / "external_evidence")

    proc = _run_proof(
        "-Mode",
        "Status",
        "-CommitReceipts",
        "-PreSleepEvidencePath",
        str(pre_path),
        "-PostResumeEvidencePath",
        str(post_path),
        env={"FRANCIS_ENV_PROFILE": "dev"},
    )

    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "francis.stage16.federation.sleep_continuity_runtime_proof"
    assert payload["status"] == "proof_failed"
    assert payload["ok"] is False
    assert payload["error"] == "sleep_evidence_path_outside_commit_root"
    assert payload["commit_receipts"] is True
    assert payload["writes_real_project_data"] is False
    assert payload["ready_to_close"] is False
    assert payload["next_smallest_truthful_gap"] == "stage16_sleep_continuity_runtime_readback"


def test_federation_stage16_sleep_continuity_runtime_proof_blocks_commit_in_production() -> None:
    proc = _run_proof("-Mode", "Status", "-CommitReceipts", env={"FRANCIS_ENV_PROFILE": "production"})

    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "francis.stage16.federation.sleep_continuity_runtime_proof"
    assert payload["status"] == "proof_failed"
    assert payload["ok"] is False
    assert payload["error"] == "commit_receipts_blocked_in_env_profile"
    assert payload["commit_receipts"] is True
    assert payload["writes_real_project_data"] is False
    assert payload["ready_to_close"] is False
