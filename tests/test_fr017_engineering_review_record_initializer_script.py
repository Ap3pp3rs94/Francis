from __future__ import annotations

import json
import shutil
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from tests.powershell_script_runner import run_powershell_script
from tests.test_fr017_engineering_review_gate_script import _write_release_ready_records


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "fr017-new-engineering-review-record.ps1"
ENGINEERING_REVIEW_GATE_SCRIPT = ROOT / "scripts" / "fr017-engineering-review-gate.ps1"
TEMPLATE_PATH = ROOT / "FR-017_Stage17_Package" / "FR-017-ENGINEERING-REVIEW-INPUT-TEMPLATE.json"

CONFIRM_ARGS = [
    "-ConfirmDocumentationPackageReviewed",
    "-ConfirmMeasurementRecordReviewed",
    "-ConfirmMockupRecordReviewed",
    "-ConfirmMannequinRecordReviewed",
    "-ConfirmPilotStaticRecordReviewed",
    "-ConfirmPilotMovementRecordReviewed",
    "-ConfirmQuickReleaseCableRecordReviewed",
    "-ConfirmNoLoadBearingClaimApproved",
    "-ConfirmNoPoweredTestingCleared",
    "-ConfirmNoFrameCoupledTestingCleared",
    "-ConfirmFr018ImplementationNotCleared",
    "-ConfirmRedesignItemsClosedOrBlocked",
    "-ConfirmCirculationNerveRiskReviewed",
    "-ConfirmQuickReleaseAccessReviewed",
    "-ConfirmGloveWristRemovalReviewed",
    "-ConfirmCableRouteReviewed",
    "-ConfirmSymptomFailConditionsReviewed",
    "-ConfirmStopConditionsPreserved",
    "-ConfirmNonPoweredFr017PhysicalValidationAccepted",
    "-ConfirmNoRedesignRequired",
    "-ConfirmNoLoadBearingUseApproved",
    "-ConfirmNoPoweredTestingApproved",
    "-ConfirmNoFrameCoupledTestingApproved",
    "-ConfirmFr018ImplementationNotClearedByDecision",
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
        timeout_seconds=120,
    )


def _payload(stdout: str) -> dict[str, Any]:
    return json.loads(stdout)


def _engineering_review_args(
    measurement_path: Path,
    mockup_path: Path,
    mannequin_path: Path,
    static_fit_path: Path,
    movement_path: Path,
    release_cable_path: Path,
    output_path: Path,
    *,
    pilot_id: str = "pilot-reference",
    reviewer: str = "test-reviewer",
    notes: str = "Fixture accepts only non-powered FR-017 evidence.",
    confirm_args: list[str] | None = None,
) -> list[str]:
    args = [
        "-Mode",
        "Create",
        "-OutputPath",
        str(output_path),
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
        "-EvidenceDate",
        date.today().isoformat(),
        "-Reviewer",
        reviewer,
        "-ReviewerRole",
        "professional-engineering-review-fixture",
        "-ReviewerCredentialReference",
        "test-credential-reference",
        "-PilotId",
        pilot_id,
        "-EngineeringReviewNotes",
        notes,
    ]
    args.extend(CONFIRM_ARGS if confirm_args is None else confirm_args)
    return args


def test_fr017_engineering_review_initializer_status_preflights_without_writing(
    tmp_path: Path,
) -> None:
    measurement_path, mockup_path, mannequin_path, static_fit_path, movement_path, release_cable_path = (
        _write_release_ready_records(tmp_path)
    )
    engineering_review_path = tmp_path / "candidate-engineering-review.json"

    proc = _run_script(
        SCRIPT,
        "-Mode",
        "Status",
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
        "-OutputPath",
        str(engineering_review_path),
    )

    assert proc.returncode == 0, proc.stderr
    result = _payload(proc.stdout)
    assert result["kind"] == "francis.fr017.engineering_review_record_initializer"
    assert result["mode"] == "Status"
    assert result["status"] == "engineering_review_record_initializer_status"
    assert result["template_exists"] is True
    assert result["template_parse_ok"] is True
    assert result["output_path_required_for_create"] is False
    assert result["measurement_path_required_for_create"] is False
    assert result["mockup_path_required_for_create"] is False
    assert result["mannequin_path_required_for_create"] is False
    assert result["static_fit_path_required_for_create"] is False
    assert result["movement_path_required_for_create"] is False
    assert result["release_cable_path_required_for_create"] is False
    assert result["output_path_targets_template"] is False
    assert result["output_parent_exists"] is True
    assert result["candidate_output_path_ready"] is True
    assert result["measurement_file_exists"] is True
    assert result["mockup_file_exists"] is True
    assert result["mannequin_file_exists"] is True
    assert result["static_fit_file_exists"] is True
    assert result["movement_file_exists"] is True
    assert result["release_cable_file_exists"] is True
    assert result["upstream_quick_release_cable_snag_status"] == (
        "ready_for_engineering_review_or_final_physical_gate_audit"
    )
    assert result["upstream_quick_release_cable_snag_ready"] is True
    assert result["wrote_file"] is False
    assert result["output_exists"] is False
    assert result["read_only_contract"] is True
    assert result["writes_repo"] is False
    assert result["writes_data"] is False
    assert result["operator_supplied_engineering_review_input_recorded"] is False
    assert result["engineering_review_record_is_stage17_completion_evidence"] is False
    assert result["physical_validation_complete"] is False
    assert result["stage17_completion_claim_allowed"] is False
    assert result["final_physical_gate_audit_ready"] is False
    assert result["load_bearing_use_approved"] is False
    assert result["powered_or_frame_coupled_testing_cleared"] is False
    assert result["fr018_implementation_cleared"] is False
    assert "fr017-new-engineering-review-record.ps1 -Mode Create" in result["create_command_template"]
    assert "fr017-engineering-review-gate.ps1 -Mode Status" in result["engineering_review_status_command_template"]
    assert result["next_command"] == result["create_command_template"]
    assert not engineering_review_path.exists()


def test_fr017_engineering_review_initializer_creates_record_without_clearance(
    tmp_path: Path,
) -> None:
    measurement_path, mockup_path, mannequin_path, static_fit_path, movement_path, release_cable_path = (
        _write_release_ready_records(tmp_path)
    )
    engineering_review_path = tmp_path / "ready-engineering-review.json"

    proc = _run_script(
        SCRIPT,
        *_engineering_review_args(
            measurement_path,
            mockup_path,
            mannequin_path,
            static_fit_path,
            movement_path,
            release_cable_path,
            engineering_review_path,
        ),
    )

    assert proc.returncode == 0, proc.stderr
    result = _payload(proc.stdout)
    assert result["kind"] == "francis.fr017.engineering_review_record_initializer"
    assert result["status"] == "created_engineering_review_record"
    assert result["wrote_file"] is True
    assert result["operator_supplied_engineering_review_input_recorded"] is True
    assert result["upstream_quick_release_cable_snag_status"] == (
        "ready_for_engineering_review_or_final_physical_gate_audit"
    )
    assert result["upstream_quick_release_cable_snag_ready"] is True
    assert result["engineering_review_record_is_stage17_completion_evidence"] is False
    assert result["physical_validation_complete"] is False
    assert result["stage17_completion_claim_allowed"] is False
    assert result["final_physical_gate_audit_ready"] is False
    assert result["load_bearing_use_approved"] is False
    assert result["powered_or_frame_coupled_testing_cleared"] is False
    assert result["fr018_implementation_cleared"] is False
    assert result["prohibited_clearance_flags_recorded"] == []
    assert "does not certify pilot safety by itself" in result["no_fake_validation_lock"]
    assert "fr017-engineering-review-gate.ps1" in result["next_command"]

    record = json.loads(engineering_review_path.read_text(encoding="utf-8-sig"))
    assert record["kind"] == "francis.fr017.engineering_review.v1"
    assert record["evidence"]["quick_release_cable_snag_record_path"] == str(release_cable_path.resolve())
    assert record["evidence"]["pilot_id"] == "pilot-reference"
    assert record["evidence"]["review_scope"] == (
        "non-powered FR-017 forearm cuff physical-validation evidence review only"
    )
    assert record["review_constraints"]["fr018_implementation_not_cleared"] is True
    assert record["safety_review"]["quick_release_access_reviewed"] is True
    assert record["review_decision"]["non_powered_fr017_physical_validation_accepted"] is True
    assert record["review_decision"]["powered_testing_approved"] is False
    assert record["review_decision"]["fr018_implementation_cleared"] is False
    assert record["record_generation"]["operator_supplied_engineering_review_input_recorded"] is True
    assert record["record_generation"]["physical_validation_complete"] is False
    assert record["record_generation"]["stage17_completion_claim_allowed"] is False
    assert record["record_generation"]["final_physical_gate_audit_ready"] is False
    assert record["record_generation"]["fr018_implementation_cleared"] is False

    gate = _run_script(
        ENGINEERING_REVIEW_GATE_SCRIPT,
        "-Mode",
        "Status",
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
    )
    assert gate.returncode == 0, gate.stderr
    gate_result = _payload(gate.stdout)
    assert gate_result["status"] == "ready_for_final_stage17_physical_gate_audit"
    assert gate_result["engineering_review_capture_ready_groups"] == 4
    assert gate_result["physical_validation_complete"] is False
    assert gate_result["stage17_completion_claim_allowed"] is False
    assert gate_result["load_bearing_use_approved"] is False
    assert gate_result["fr018_implementation_cleared"] is False


def test_fr017_engineering_review_initializer_refuses_upstream_release_cable_not_ready(
    tmp_path: Path,
) -> None:
    measurement_path, mockup_path, mannequin_path, static_fit_path, movement_path, release_cable_path = (
        _write_release_ready_records(tmp_path)
    )
    release_payload = json.loads(release_cable_path.read_text(encoding="utf-8"))
    release_payload["sides"]["left"]["fail_observations"]["release_hidden"] = True
    release_cable_path.write_text(json.dumps(release_payload), encoding="utf-8")
    engineering_review_path = tmp_path / "engineering-review.json"

    proc = _run_script(
        SCRIPT,
        *_engineering_review_args(
            measurement_path,
            mockup_path,
            mannequin_path,
            static_fit_path,
            movement_path,
            release_cable_path,
            engineering_review_path,
        ),
    )

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "upstream_quick_release_cable_snag_not_ready"
    assert result["upstream_quick_release_cable_snag_status"] == (
        "failed_requires_release_cable_redesign_or_medical_review"
    )
    assert result["wrote_file"] is False
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_engineering_review_initializer_refuses_template_target(tmp_path: Path) -> None:
    measurement_path, mockup_path, mannequin_path, static_fit_path, movement_path, release_cable_path = (
        _write_release_ready_records(tmp_path)
    )

    proc = _run_script(
        SCRIPT,
        *_engineering_review_args(
            measurement_path,
            mockup_path,
            mannequin_path,
            static_fit_path,
            movement_path,
            release_cable_path,
            TEMPLATE_PATH,
        ),
    )

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "output_path_targets_template"
    assert result["wrote_file"] is False
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_engineering_review_initializer_refuses_overwrite(tmp_path: Path) -> None:
    measurement_path, mockup_path, mannequin_path, static_fit_path, movement_path, release_cable_path = (
        _write_release_ready_records(tmp_path)
    )
    engineering_review_path = tmp_path / "existing-engineering-review.json"
    engineering_review_path.write_text("do not replace", encoding="utf-8")

    proc = _run_script(
        SCRIPT,
        *_engineering_review_args(
            measurement_path,
            mockup_path,
            mannequin_path,
            static_fit_path,
            movement_path,
            release_cable_path,
            engineering_review_path,
        ),
    )

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "output_file_exists"
    assert result["wrote_file"] is False
    assert engineering_review_path.read_text(encoding="utf-8") == "do not replace"
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_engineering_review_initializer_rejects_mismatched_pilot_id(tmp_path: Path) -> None:
    measurement_path, mockup_path, mannequin_path, static_fit_path, movement_path, release_cable_path = (
        _write_release_ready_records(tmp_path)
    )
    engineering_review_path = tmp_path / "mismatched-pilot-engineering-review.json"

    proc = _run_script(
        SCRIPT,
        *_engineering_review_args(
            measurement_path,
            mockup_path,
            mannequin_path,
            static_fit_path,
            movement_path,
            release_cable_path,
            engineering_review_path,
            pilot_id="different-pilot",
        ),
    )

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "invalid_engineering_review_record_input"
    assert result["wrote_file"] is False
    assert result["invalid_fields"] == ["evidence.pilot_id_must_match_release_cable_pilot_id"]
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_engineering_review_initializer_rejects_missing_reviewer_and_notes(
    tmp_path: Path,
) -> None:
    measurement_path, mockup_path, mannequin_path, static_fit_path, movement_path, release_cable_path = (
        _write_release_ready_records(tmp_path)
    )
    engineering_review_path = tmp_path / "missing-reviewer-engineering-review.json"

    proc = _run_script(
        SCRIPT,
        *_engineering_review_args(
            measurement_path,
            mockup_path,
            mannequin_path,
            static_fit_path,
            movement_path,
            release_cable_path,
            engineering_review_path,
            reviewer=" ",
            notes=" ",
        ),
    )

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "invalid_engineering_review_record_input"
    assert result["wrote_file"] is False
    assert result["invalid_fields"] == ["evidence.reviewer", "review_decision.engineering_review_notes"]
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_engineering_review_initializer_blocks_prohibited_clearance_without_writing(
    tmp_path: Path,
) -> None:
    measurement_path, mockup_path, mannequin_path, static_fit_path, movement_path, release_cable_path = (
        _write_release_ready_records(tmp_path)
    )
    engineering_review_path = tmp_path / "powered-clearance-engineering-review.json"
    confirm_args = [arg for arg in CONFIRM_ARGS if arg != "-ConfirmNoPoweredTestingApproved"]
    confirm_args.append("-PoweredTestingApproved")

    proc = _run_script(
        SCRIPT,
        *_engineering_review_args(
            measurement_path,
            mockup_path,
            mannequin_path,
            static_fit_path,
            movement_path,
            release_cable_path,
            engineering_review_path,
            confirm_args=confirm_args,
        ),
    )

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "engineering_review_prohibited_clearance_recorded_requires_review"
    assert result["wrote_file"] is False
    assert result["prohibited_clearance_flags_recorded"] == ["review_decision.powered_testing_approved"]
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False
