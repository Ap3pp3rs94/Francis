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


def _run_evidence(*args: str) -> subprocess.CompletedProcess[str]:
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
    )


def _run_sequence(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
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
            str(_repo_root() / "scripts" / "federation-stage16-sleep-continuity-post-resume-sequence.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
        timeout=120,
        env=merged_env,
    )


def test_federation_stage16_sleep_post_resume_sequence_status_is_read_only(tmp_path: Path) -> None:
    pre_path = tmp_path / "evidence" / "pre_sleep.json"

    proc = _run_sequence("-Mode", "Status", "-PreSleepEvidencePath", str(pre_path))

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "francis.stage16.federation.sleep_continuity_post_resume_sequence"
    assert payload["status"] == "ready_for_operator_confirmed_post_resume_sequence"
    assert payload["run_available_after_operator_confirmation"] is True
    assert payload["required_sequence"] == [
        "operator-confirmed sleep/resume",
        "PostResume evidence",
        "runtime proof receipt",
    ]
    assert "federation-stage16-sleep-continuity-post-resume-sequence.ps1" in payload["sequence_command"]
    assert "-OperatorConfirmedSleepResume" in payload["sequence_command"]
    assert payload["governance"]["status_projection_only"] is True
    assert payload["governance"]["status_runs_shell"] is False
    assert payload["governance"]["status_writes_evidence"] is False
    assert payload["governance"]["status_writes_receipts"] is False
    assert payload["governance"]["run_requires_operator_confirmed_sleep_resume"] is True
    assert payload["governance"]["marks_stage16_closed"] is False
    assert payload["writes_evidence"] is False
    assert payload["writes_receipts"] is False
    assert payload["marks_stage16_closed"] is False
    assert not pre_path.parent.exists()


def test_federation_stage16_sleep_post_resume_sequence_requires_confirmation(tmp_path: Path) -> None:
    output_dir = tmp_path / "evidence"
    pre_proc = _run_evidence(
        "-Mode",
        "PreSleep",
        "-OutputDir",
        str(output_dir),
        "-ContinuityRecordId",
        "stage16-sleep-sequence-confirmation-test",
    )
    assert pre_proc.returncode == 0, pre_proc.stderr or pre_proc.stdout
    pre_payload = json.loads(pre_proc.stdout)

    proc = _run_sequence(
        "-Mode",
        "Run",
        "-OutputDir",
        str(output_dir),
        "-PreSleepEvidencePath",
        pre_payload["evidence_path"],
    )

    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["status"] == "blocked"
    assert payload["error"] == "operator_sleep_resume_confirmation_required"
    assert payload["operator_confirmed_sleep_resume"] is False
    assert payload["writes_evidence"] is False
    assert payload["writes_receipts"] is False
    assert payload["marks_stage16_closed"] is False
    assert list(output_dir.glob("post_resume_*.json")) == []


def test_federation_stage16_sleep_post_resume_sequence_runs_bounded_child_proofs(tmp_path: Path) -> None:
    output_dir = tmp_path / "evidence"
    data_dir = tmp_path / "proof_data"
    pre_proc = _run_evidence(
        "-Mode",
        "PreSleep",
        "-OutputDir",
        str(output_dir),
        "-ContinuityRecordId",
        "stage16-sleep-sequence-test",
        "-TraceId",
        "trace-stage16-sleep-sequence-test",
        "-AuthoritySnapshotId",
        "authsnap-stage16-sleep-sequence-test",
    )
    assert pre_proc.returncode == 0, pre_proc.stderr or pre_proc.stdout
    pre_payload = json.loads(pre_proc.stdout)

    proc = _run_sequence(
        "-Mode",
        "Run",
        "-OutputDir",
        str(output_dir),
        "-DataDir",
        str(data_dir),
        "-PreSleepEvidencePath",
        pre_payload["evidence_path"],
        "-OperatorConfirmedSleepResume",
    )

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["status"] == "sequence_passed"
    assert payload["operator_confirmed_sleep_resume"] is True
    assert payload["post_resume_evidence_status"] == "post_resume_evidence_written"
    assert payload["runtime_proof_status"] == "proof_passed"
    assert payload["readback_id"] == "workstation_sleep_continuity_validated"
    assert payload["runtime_proof_receipt_id"].startswith("fedlive_workstation_sleep_continuity_validated_")
    assert payload["completion_review_ready"] is False
    assert payload["ready_to_close"] is False
    assert payload["writes_evidence"] is True
    assert payload["writes_receipts"] is False
    assert payload["marks_stage16_closed"] is False
    assert payload["governance"]["uses_bounded_child_scripts"] is True
    assert payload["governance"]["child_scripts_are_invoked_with_argument_lists"] is True
    assert payload["governance"]["does_not_infer_sleep_from_delay"] is True
    assert payload["governance"]["marks_stage16_closed"] is False
    assert payload["next_smallest_truthful_gap"] == "stage16_pairing_runtime_readback"

    post_path = Path(payload["post_resume_evidence_path"])
    assert post_path.exists()
    post_evidence = json.loads(post_path.read_text(encoding="utf-8"))
    assert post_evidence["evidence_kind"] == "stage16_sleep_continuity_post_resume"
    assert post_evidence["sleep_observed"] is True
    assert post_evidence["resume_observed"] is True
    assert post_evidence["pre_sleep_evidence_path"] == str(Path(pre_payload["evidence_path"]).resolve())

    receipt_path = data_dir / "logs" / "federation" / "stage16_live_runtime_readbacks.jsonl"
    assert receipt_path.exists()


def test_federation_stage16_sleep_post_resume_sequence_blocks_commit_in_production(tmp_path: Path) -> None:
    pre_path = tmp_path / "evidence" / "pre_sleep.json"

    proc = _run_sequence(
        "-Mode",
        "Run",
        "-CommitEvidence",
        "-CommitReceipts",
        "-PreSleepEvidencePath",
        str(pre_path),
        "-OperatorConfirmedSleepResume",
        env={"FRANCIS_ENV_PROFILE": "production"},
    )

    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["status"] == "blocked"
    assert payload["error"] == "post_resume_sequence_commit_blocked_in_env_profile"
    assert payload["writes_evidence"] is False
    assert payload["writes_receipts"] is False
    assert payload["marks_stage16_closed"] is False
