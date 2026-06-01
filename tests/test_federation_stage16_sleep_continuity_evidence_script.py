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


def _run_evidence(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
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
            str(_repo_root() / "scripts" / "federation-stage16-sleep-continuity-evidence.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
        timeout=60,
        env=merged_env,
    )


def _run_proof(*args: str) -> subprocess.CompletedProcess[str]:
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
    )


def test_federation_stage16_sleep_continuity_evidence_status_is_read_only(tmp_path: Path) -> None:
    output_dir = tmp_path / "evidence"

    proc = _run_evidence("-Mode", "Status", "-OutputDir", str(output_dir))

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "francis.stage16.federation.sleep_continuity_evidence"
    assert payload["status"] == "ready_for_operator_evidence"
    assert payload["evidence_written"] is False
    assert payload["required_sequence"] == [
        "PreSleep",
        "operator sleep/resume",
        "PostResume",
        "runtime proof with CommitReceipts",
    ]
    assert payload["governance"]["does_not_infer_sleep_from_delay"] is True
    assert payload["governance"]["writes_runtime_readback"] is False
    assert payload["governance"]["marks_stage16_closed"] is False
    assert payload["governance"]["committed_pre_sleep_path_must_stay_under_project_evidence_root"] is True
    assert payload["governance"]["committed_pre_sleep_path_traversal_blocked"] is True
    assert not output_dir.exists()


def test_federation_stage16_sleep_continuity_evidence_writes_pre_sleep_marker(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "evidence"

    proc = _run_evidence(
        "-Mode",
        "PreSleep",
        "-OutputDir",
        str(output_dir),
        "-ContinuityRecordId",
        "stage16-sleep-continuity-test",
        "-TraceId",
        "trace-stage16-sleep-continuity-test",
        "-AuthoritySnapshotId",
        "authsnap-stage16-sleep-continuity-test",
    )

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["status"] == "pre_sleep_evidence_written"
    assert payload["evidence_written"] is True
    assert payload["commit_evidence"] is False
    assert payload["continuity_record_id"] == "stage16-sleep-continuity-test"
    assert (
        payload["operator_next_step"] == "sleep_or_suspend_workstation_then_run_postresume_with_operator_confirmation"
    )

    evidence_path = Path(payload["evidence_path"])
    assert evidence_path.exists()
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert evidence["evidence_kind"] == "stage16_sleep_continuity_pre_sleep"
    assert evidence["continuity_record_id"] == "stage16-sleep-continuity-test"
    assert evidence["freshness_state"] == "fresh"
    assert evidence["source_recorded_ts"] > 0
    assert evidence["governance"]["contains_raw_private_data"] is False
    assert evidence["governance"]["writes_runtime_readback"] is False
    assert evidence["governance"]["marks_stage16_closed"] is False


def test_federation_stage16_sleep_continuity_evidence_requires_post_resume_confirmation(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "evidence"
    pre_proc = _run_evidence(
        "-Mode",
        "PreSleep",
        "-OutputDir",
        str(output_dir),
        "-ContinuityRecordId",
        "stage16-sleep-continuity-test",
    )
    pre_payload = json.loads(pre_proc.stdout)

    proc = _run_evidence(
        "-Mode",
        "PostResume",
        "-OutputDir",
        str(output_dir),
        "-PreSleepEvidencePath",
        pre_payload["evidence_path"],
    )

    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["status"] == "blocked"
    assert payload["error"] == "operator_sleep_resume_confirmation_required"
    assert payload["evidence_written"] is False
    assert list(output_dir.glob("post_resume_*.json")) == []


def test_federation_stage16_sleep_continuity_evidence_post_resume_feeds_runtime_proof(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "evidence"
    data_dir = tmp_path / "proof_data"
    pre_proc = _run_evidence(
        "-Mode",
        "PreSleep",
        "-OutputDir",
        str(output_dir),
        "-ContinuityRecordId",
        "stage16-sleep-continuity-test",
        "-TraceId",
        "trace-stage16-sleep-continuity-test",
        "-AuthoritySnapshotId",
        "authsnap-stage16-sleep-continuity-test",
    )
    pre_payload = json.loads(pre_proc.stdout)

    post_proc = _run_evidence(
        "-Mode",
        "PostResume",
        "-OutputDir",
        str(output_dir),
        "-PreSleepEvidencePath",
        pre_payload["evidence_path"],
        "-OperatorConfirmedSleepResume",
    )

    assert post_proc.returncode == 0, post_proc.stderr or post_proc.stdout
    post_payload = json.loads(post_proc.stdout)
    assert post_payload["status"] == "post_resume_evidence_written"
    assert post_payload["operator_confirmed_sleep_resume"] is True
    assert post_payload["proof_command"].startswith(
        "scripts/federation-stage16-sleep-continuity-runtime-proof.ps1 -Mode Status -CommitReceipts"
    )

    post_evidence = json.loads(Path(post_payload["evidence_path"]).read_text(encoding="utf-8"))
    assert post_evidence["evidence_kind"] == "stage16_sleep_continuity_post_resume"
    assert post_evidence["continuity_record_id"] == "stage16-sleep-continuity-test"
    assert post_evidence["sleep_observed"] is True
    assert post_evidence["resume_observed"] is True
    assert post_evidence["continuity_available_after_resume"] is True
    assert post_evidence["revoked_links_present_current_state"] is False
    assert post_evidence["stale_state_implies_current_authority"] is False

    proof_proc = _run_proof(
        "-Mode",
        "Status",
        "-DataDir",
        str(data_dir),
        "-PreSleepEvidencePath",
        pre_payload["evidence_path"],
        "-PostResumeEvidencePath",
        post_payload["evidence_path"],
    )

    assert proof_proc.returncode == 0, proof_proc.stderr or proof_proc.stdout
    proof_payload = json.loads(proof_proc.stdout)
    assert proof_payload["status"] == "proof_passed"
    assert proof_payload["readback_id"] == "workstation_sleep_continuity_validated"
    assert proof_payload["ready_count"] == 1
    assert proof_payload["ready_to_close"] is False


def test_federation_stage16_sleep_continuity_evidence_commit_rejects_external_pre_sleep_path(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "external_evidence"
    record_id = "stage16-sleep-external-root-test"
    pre_proc = _run_evidence(
        "-Mode",
        "PreSleep",
        "-OutputDir",
        str(output_dir),
        "-ContinuityRecordId",
        record_id,
    )
    assert pre_proc.returncode == 0, pre_proc.stderr or pre_proc.stdout
    pre_payload = json.loads(pre_proc.stdout)

    proc = _run_evidence(
        "-Mode",
        "PostResume",
        "-CommitEvidence",
        "-PreSleepEvidencePath",
        pre_payload["evidence_path"],
        "-OperatorConfirmedSleepResume",
        env={"FRANCIS_ENV_PROFILE": "dev"},
    )

    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["status"] == "blocked"
    assert payload["error"] == "pre_sleep_evidence_path_outside_commit_root"
    assert payload["commit_evidence"] is True
    assert payload["evidence_written"] is False
    assert payload["writes_runtime_readback"] is False
    assert payload["marks_stage16_closed"] is False

    project_post_resume = (
        _repo_root()
        / "data"
        / "test_runs"
        / "federation-stage16-sleep-continuity-evidence"
        / f"post_resume_{record_id}.json"
    )
    assert not project_post_resume.exists()


def test_federation_stage16_sleep_continuity_evidence_blocks_commit_in_production() -> None:
    proc = _run_evidence(
        "-Mode",
        "PreSleep",
        "-CommitEvidence",
        env={"FRANCIS_ENV_PROFILE": "production"},
    )

    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "francis.stage16.federation.sleep_continuity_evidence"
    assert payload["status"] == "blocked"
    assert payload["error"] == "commit_evidence_blocked_in_env_profile"
    assert payload["commit_evidence"] is True
    assert payload["evidence_written"] is False
    assert payload["writes_runtime_readback"] is False
    assert payload["marks_stage16_closed"] is False
