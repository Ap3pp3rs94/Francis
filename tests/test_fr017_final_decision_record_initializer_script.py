from __future__ import annotations

import json
import shutil
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from tests.powershell_script_runner import run_powershell_script
from tests.test_fr017_final_decision_record_gate_script import _ready_args, _write_ready_evidence


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "fr017-new-final-decision-record.ps1"
FINAL_DECISION_GATE_SCRIPT = ROOT / "scripts" / "fr017-final-decision-record-gate.ps1"
TEMPLATE_PATH = ROOT / "FR-017_Stage17_Package" / "FR-017-FINAL-PHYSICAL-DECISION-INPUT-TEMPLATE.json"

CONFIRM_ARGS = [
    "-ConfirmHumanDecisionReviewer",
    "-ConfirmRealRecordsReviewed",
    "-ConfirmAllStopConditionsReviewed",
    "-ConfirmNoUnresolvedSafetyFailConditions",
    "-ConfirmNoPoweredTestingCleared",
    "-ConfirmNoFrameCoupledTestingCleared",
    "-ConfirmNoLoadBearingUseApproved",
    "-ConfirmFr018ImplementationNotCleared",
    "-ConfirmStage17CompletionClaimRequested",
    "-ConfirmPhysicalValidationAcceptedByHumanReviewer",
    "-ConfirmCompletionLedgerUpdateRequired",
    "-ConfirmTemplateIsNotPhysicalValidation",
    "-ConfirmRequiresRealRecords",
    "-ConfirmFr018ImplementationNotClearedByLock",
    "-ConfirmPoweredOrFrameCoupledTestingNotClearedByLock",
]


def _powershell() -> str:
    exe = shutil.which("pwsh") or shutil.which("powershell")
    if not exe:
        pytest.skip("PowerShell is not available")
    return exe


def _run_script(script: Path, *args: str):
    return run_powershell_script(
        _powershell(),
        script,
        args,
        cwd=ROOT,
        timeout_seconds=140,
    )


def _payload(stdout: str) -> dict[str, Any]:
    return json.loads(stdout)


def _final_decision_args(
    paths: tuple[Path, Path, Path, Path, Path, Path, Path],
    final_decision_path: Path,
    final_physical_gate_record_path: Path,
    *,
    pilot_id: str = "pilot-reference",
    decision_reviewer: str = "Pilot reviewer",
    notes: str = (
        "Remaining limitations: FR-018 stays blocked; powered, frame-coupled, "
        "and load-bearing use stay blocked until separate ledger review."
    ),
    confirm_args: list[str] | None = None,
) -> list[str]:
    (
        measurement_path,
        mockup_path,
        mannequin_path,
        static_fit_path,
        movement_path,
        release_cable_path,
        engineering_review_path,
    ) = paths
    args = [
        "-Mode",
        "Create",
        "-OutputPath",
        str(final_decision_path),
        "-FinalPhysicalGateRecordOutputPath",
        str(final_physical_gate_record_path),
        "-MeasurementPath",
        str(measurement_path),
        "-MockupPath",
        str(mockup_path),
        "-MannequinPath",
        str(mannequin_path),
        "-StaticFitPath",
        str(static_fit_path),
        "-MovementPath",
        str(movement_path),
        "-ReleaseCablePath",
        str(release_cable_path),
        "-EngineeringReviewPath",
        str(engineering_review_path),
        "-EvidenceDate",
        date.today().isoformat(),
        "-DecisionReviewer",
        decision_reviewer,
        "-ReviewerRole",
        "human_final_decision_reviewer",
        "-PilotId",
        pilot_id,
        "-CompletionDecisionNotes",
        notes,
    ]
    args.extend(CONFIRM_ARGS if confirm_args is None else confirm_args)
    return args


def test_fr017_final_decision_initializer_creates_record_and_saved_gate_without_clearance(
    tmp_path: Path,
) -> None:
    paths = _write_ready_evidence(tmp_path)
    final_decision_path = tmp_path / "ready-final-decision.json"
    final_physical_gate_record_path = tmp_path / "ready-final-physical-gate.json"

    proc = _run_script(
        SCRIPT,
        *_final_decision_args(paths, final_decision_path, final_physical_gate_record_path),
    )

    assert proc.returncode == 0, proc.stderr
    result = _payload(proc.stdout)
    assert result["kind"] == "francis.fr017.final_decision_record_initializer"
    assert result["status"] == "created_final_decision_record"
    assert result["wrote_file"] is True
    assert result["wrote_final_physical_gate_record"] is True
    assert result["operator_supplied_final_decision_input_recorded"] is True
    assert result["upstream_final_physical_gate_status"] == "ready_for_stage17_final_physical_completion_decision"
    assert result["upstream_final_physical_gate_ready"] is True
    assert result["final_decision_record_is_ledger_review_input"] is True
    assert result["final_decision_record_is_stage17_completion_by_itself"] is False
    assert result["physical_validation_complete"] is False
    assert result["stage17_completion_claim_allowed"] is False
    assert result["completion_ledger_update_written"] is False
    assert result["powered_or_frame_coupled_testing_cleared"] is False
    assert result["fr018_implementation_cleared"] is False
    assert result["decision_lock_violations"] == []
    assert result["completion_decision_violations"] == []
    assert result["prohibited_clearance_flags_recorded"] == []
    assert result["final_physical_gate_reference_pilot_fingerprint"]
    assert result["final_decision_pilot_fingerprint"] == result["final_physical_gate_reference_pilot_fingerprint"]
    assert "does not write the completion ledger" in result["no_fake_validation_lock"]
    assert "fr017-final-decision-record-gate.ps1" in result["next_command"]

    saved_gate = json.loads(final_physical_gate_record_path.read_text(encoding="utf-8-sig"))
    assert saved_gate["status"] == "ready_for_stage17_final_physical_completion_decision"
    assert saved_gate["physical_validation_complete"] is False
    assert saved_gate["stage17_completion_claim_allowed"] is False
    assert saved_gate["fr018_implementation_cleared"] is False

    record = json.loads(final_decision_path.read_text(encoding="utf-8-sig"))
    assert record["kind"] == "francis.fr017.final_physical_decision.v1"
    assert record["evidence"]["final_physical_gate_status"] == "ready_for_stage17_final_physical_completion_decision"
    assert record["evidence"]["final_physical_gate_record_path"] == str(final_physical_gate_record_path.resolve())
    assert record["evidence"]["pilot_id"] == "pilot-reference"
    assert record["decision_locks"]["fr018_implementation_not_cleared"] is True
    assert record["completion_decision"]["stage17_completion_claim_requested"] is True
    assert record["completion_decision"]["physical_validation_accepted_by_human_reviewer"] is True
    assert record["no_fake_validation_lock"]["fr018_implementation_cleared"] is False
    assert record["record_generation"]["final_decision_record_is_stage17_completion_by_itself"] is False
    assert record["record_generation"]["completion_ledger_update_written"] is False

    gate = _run_script(
        FINAL_DECISION_GATE_SCRIPT,
        "-Mode",
        "Status",
        *_ready_args(paths),
        "-FinalDecisionPath",
        str(final_decision_path),
    )
    assert gate.returncode == 0, gate.stderr
    gate_result = _payload(gate.stdout)
    assert gate_result["status"] == "ready_for_completion_ledger_review"
    assert gate_result["physical_validation_complete"] is False
    assert gate_result["stage17_completion_claim_allowed"] is False
    assert gate_result["fr018_implementation_cleared"] is False


def test_fr017_final_decision_initializer_refuses_upstream_final_physical_gate_not_ready(
    tmp_path: Path,
) -> None:
    paths = _write_ready_evidence(tmp_path)
    engineering_review_path = paths[-1]
    engineering_payload = json.loads(engineering_review_path.read_text(encoding="utf-8"))
    engineering_payload["review_decision"]["powered_testing_approved"] = True
    engineering_review_path.write_text(json.dumps(engineering_payload), encoding="utf-8")
    final_decision_path = tmp_path / "final-decision.json"
    final_physical_gate_record_path = tmp_path / "final-physical-gate.json"

    proc = _run_script(
        SCRIPT,
        *_final_decision_args(paths, final_decision_path, final_physical_gate_record_path),
    )

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "upstream_final_physical_gate_not_ready"
    assert result["upstream_final_physical_gate_status"] == "failed_engineering_review_gate"
    assert result["wrote_file"] is False
    assert result["wrote_final_physical_gate_record"] is False
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_final_decision_initializer_refuses_template_target(tmp_path: Path) -> None:
    paths = _write_ready_evidence(tmp_path)
    final_physical_gate_record_path = tmp_path / "ready-final-physical-gate.json"

    proc = _run_script(
        SCRIPT,
        *_final_decision_args(paths, TEMPLATE_PATH, final_physical_gate_record_path),
    )

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "output_path_targets_template"
    assert result["wrote_file"] is False
    assert result["wrote_final_physical_gate_record"] is False


def test_fr017_final_decision_initializer_refuses_overwrite(tmp_path: Path) -> None:
    paths = _write_ready_evidence(tmp_path)
    final_decision_path = tmp_path / "existing-final-decision.json"
    final_decision_path.write_text("do not replace", encoding="utf-8")
    final_physical_gate_record_path = tmp_path / "ready-final-physical-gate.json"

    proc = _run_script(
        SCRIPT,
        *_final_decision_args(paths, final_decision_path, final_physical_gate_record_path),
    )

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "output_file_exists"
    assert result["wrote_file"] is False
    assert final_decision_path.read_text(encoding="utf-8") == "do not replace"


def test_fr017_final_decision_initializer_refuses_final_gate_record_overwrite(
    tmp_path: Path,
) -> None:
    paths = _write_ready_evidence(tmp_path)
    final_decision_path = tmp_path / "final-decision.json"
    final_physical_gate_record_path = tmp_path / "existing-final-physical-gate.json"
    final_physical_gate_record_path.write_text("do not replace", encoding="utf-8")

    proc = _run_script(
        SCRIPT,
        *_final_decision_args(paths, final_decision_path, final_physical_gate_record_path),
    )

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "final_physical_gate_record_output_file_exists"
    assert result["wrote_file"] is False
    assert result["wrote_final_physical_gate_record"] is False
    assert final_physical_gate_record_path.read_text(encoding="utf-8") == "do not replace"


def test_fr017_final_decision_initializer_rejects_mismatched_pilot_id(tmp_path: Path) -> None:
    paths = _write_ready_evidence(tmp_path)
    final_decision_path = tmp_path / "mismatched-final-decision.json"
    final_physical_gate_record_path = tmp_path / "ready-final-physical-gate.json"

    proc = _run_script(
        SCRIPT,
        *_final_decision_args(
            paths,
            final_decision_path,
            final_physical_gate_record_path,
            pilot_id="different-pilot",
        ),
    )

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "invalid_final_decision_record_input"
    assert result["wrote_file"] is False
    assert result["invalid_fields"] == ["evidence.pilot_id_must_match_final_physical_gate_reference"]
    assert result["final_physical_gate_reference_pilot_fingerprint"]
    assert result["final_decision_pilot_fingerprint"] != result["final_physical_gate_reference_pilot_fingerprint"]
    assert result["fr018_implementation_cleared"] is False


def test_fr017_final_decision_initializer_rejects_missing_human_reviewer_and_notes(
    tmp_path: Path,
) -> None:
    paths = _write_ready_evidence(tmp_path)
    final_decision_path = tmp_path / "missing-final-decision.json"
    final_physical_gate_record_path = tmp_path / "ready-final-physical-gate.json"
    confirm_args = [arg for arg in CONFIRM_ARGS if arg != "-ConfirmHumanDecisionReviewer"]

    proc = _run_script(
        SCRIPT,
        *_final_decision_args(
            paths,
            final_decision_path,
            final_physical_gate_record_path,
            decision_reviewer=" ",
            notes=" ",
            confirm_args=confirm_args,
        ),
    )

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "invalid_final_decision_record_input"
    assert result["wrote_file"] is False
    assert result["invalid_fields"] == [
        "evidence.decision_reviewer_human_confirmation",
        "evidence.decision_reviewer",
        "completion_decision.completion_decision_notes",
    ]
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_final_decision_initializer_blocks_prohibited_clearance_without_writing(
    tmp_path: Path,
) -> None:
    paths = _write_ready_evidence(tmp_path)
    final_decision_path = tmp_path / "fr018-clearance-final-decision.json"
    final_physical_gate_record_path = tmp_path / "ready-final-physical-gate.json"
    confirm_args = [arg for arg in CONFIRM_ARGS if arg != "-ConfirmFr018ImplementationNotClearedByLock"]
    confirm_args.append("-Fr018ImplementationCleared")

    proc = _run_script(
        SCRIPT,
        *_final_decision_args(
            paths,
            final_decision_path,
            final_physical_gate_record_path,
            notes="Remaining limitations reviewed; FR-018 cleared.",
            confirm_args=confirm_args,
        ),
    )

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "final_decision_prohibited_clearance_recorded_requires_review"
    assert result["wrote_file"] is False
    assert result["wrote_final_physical_gate_record"] is False
    assert result["prohibited_clearance_flags_recorded"] == [
        "completion_decision_notes.fr-018_cleared",
        "no_fake_validation_lock.fr018_implementation_cleared",
    ]
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False
