from __future__ import annotations

import json
import shutil
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from tests.powershell_script_runner import run_powershell_script
from tests.test_fr017_landmark_record_update_script import _landmark_args


ROOT = Path(__file__).resolve().parents[1]
INITIALIZER_SCRIPT = ROOT / "scripts" / "fr017-new-measurement-record.ps1"
MEASUREMENT_UPDATE_SCRIPT = ROOT / "scripts" / "fr017-update-measurement-record.ps1"
LANDMARK_UPDATE_SCRIPT = ROOT / "scripts" / "fr017-update-landmark-record.ps1"
INDEPENDENCE_SAFETY_UPDATE_SCRIPT = ROOT / "scripts" / "fr017-update-independence-safety-record.ps1"
INTAKE_SCRIPT = ROOT / "scripts" / "fr017-measurement-intake.ps1"
TEMPLATE_PATH = ROOT / "FR-017_Stage17_Package" / "FR-017-MEASUREMENTS-INPUT-TEMPLATE.json"


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
        timeout_seconds=60,
    )


def _payload(stdout: str) -> dict[str, Any]:
    return json.loads(stdout)


def _create_setup_brief_record(output_path: Path) -> None:
    proc = _run_script(
        INITIALIZER_SCRIPT,
        "-Mode",
        "Create",
        "-OutputPath",
        str(output_path),
        "-EvidenceDate",
        date.today().isoformat(),
        "-Observer",
        "test-observer",
        "-PilotId",
        "pilot-reference",
        "-MeasurementTool",
        "flexible metric tape",
        "-ConfirmNoTissueCompressionUsed",
        "-ConfirmNoWristBoneCompressionUsed",
        "-ConfirmMetricToolUsed",
        "-ConfirmArmRelaxedPalmNeutralOrExceptionRecorded",
        "-ConfirmStopConditionsBriefed",
        "-ConditionNotes",
        "No tissue compression, no wrist-bone compression, metric tape, and stop briefing completed.",
    )
    assert proc.returncode == 0, proc.stderr


def _measurement_args(side: str, mid_forearm: str) -> list[str]:
    return [
        "-Mode",
        "UpdateSide",
        "-Side",
        side,
        "-ForearmCircumference25mmBelowElbowCrease",
        "235",
        "-ForearmCircumferenceMidForearm",
        mid_forearm,
        "-ForearmCircumference40mmAboveWristCrease",
        "172",
        "-ForearmLengthElbowCreaseToWristCrease",
        "258",
        "-OuterForearmUsablePanelLength",
        "178",
        "-UpperStrapAllowedBandWidth",
        "45",
        "-LowerStrapAllowedBandWidth",
        "38",
        "-BoneRidgeReliefLength",
        "160",
        "-InnerForearmNoPressureZoneWidth",
        "52",
        "-WristClearanceGap",
        "42",
        "-ConfirmSecondPassCompleted",
        "-MaxDeltaMm",
        "3",
        "-ConfirmAllRequiredMeasurementsWithin5mm",
    ]


def _create_setup_and_numeric_record(output_path: Path) -> None:
    _create_setup_brief_record(output_path)
    left = _run_script(
        MEASUREMENT_UPDATE_SCRIPT,
        "-MeasurementPath",
        str(output_path),
        *_measurement_args("left", "225"),
    )
    assert left.returncode == 0, left.stderr
    right = _run_script(
        MEASUREMENT_UPDATE_SCRIPT,
        "-MeasurementPath",
        str(output_path),
        *_measurement_args("right", "228"),
    )
    assert right.returncode == 0, right.stderr


def _create_ready_until_independence_record(output_path: Path) -> None:
    _create_setup_and_numeric_record(output_path)
    proc = _run_script(
        LANDMARK_UPDATE_SCRIPT,
        "-MeasurementPath",
        str(output_path),
        *_landmark_args(),
    )
    assert proc.returncode == 0, proc.stderr


def _independence_safety_args(
    *,
    right_measurement_reference: str = "right independent measurement sheet pass 1 and 2",
    symptom_flag: str = "",
) -> list[str]:
    args = [
        "-Mode",
        "UpdateIndependenceSafety",
        "-ConfirmLeftArmMeasuredSeparately",
        "-ConfirmRightArmMeasuredSeparately",
        "-ConfirmSideLabelsVerified",
        "-ConfirmValuesNotCopiedBetweenSides",
        "-LeftMeasurementReference",
        "left independent measurement sheet pass 1 and 2",
        "-RightMeasurementReference",
        right_measurement_reference,
        "-IndependenceNotes",
        "Left and right measurement passes were separate with side label verification.",
        "-ConfirmNoPain",
        "-ConfirmNoTingling",
        "-ConfirmNoNumbness",
        "-ConfirmNoColdFingers",
        "-ConfirmNoDiscoloration",
        "-ConfirmNoHandWeakness",
        "-ConfirmNoWristPain",
        "-ConfirmNoSharpPressure",
        "-ConfirmNoReducedFingerMotion",
        "-ConfirmNoLossOfGripStrength",
    ]
    if symptom_flag:
        absent_flag = "-ConfirmNo" + symptom_flag.removesuffix("Observed")
        args.remove(absent_flag)
        args.append("-" + symptom_flag)
    return args


def test_fr017_independence_safety_update_records_final_measurement_group_without_clearance(
    tmp_path: Path,
) -> None:
    measurement_path = tmp_path / "measurement-record.json"
    _create_ready_until_independence_record(measurement_path)

    proc = _run_script(
        INDEPENDENCE_SAFETY_UPDATE_SCRIPT,
        "-MeasurementPath",
        str(measurement_path),
        *_independence_safety_args(),
    )

    assert proc.returncode == 0, proc.stderr
    result = _payload(proc.stdout)
    assert result["kind"] == "francis.fr017.independence_safety_record_update"
    assert result["status"] == "updated_measurement_independence_safety"
    assert result["wrote_file"] is True
    assert result["operator_supplied_independence_safety_input_recorded"] is True
    assert result["independence_safety_update_is_physical_validation_evidence"] is False
    assert result["physical_validation_complete"] is False
    assert result["stage17_completion_claim_allowed"] is False
    assert result["powered_or_frame_coupled_testing_cleared"] is False
    assert result["fr018_implementation_cleared"] is False
    assert result["safety_symptoms_recorded"] == []
    assert "left_right_independence.left_arm_measured_separately" in result["updated_fields"]
    assert "safety_screen.loss_of_grip_strength" in result["updated_fields"]

    record = json.loads(measurement_path.read_text(encoding="utf-8-sig"))
    assert record["left_right_independence"]["left_arm_measured_separately"] is True
    assert (
        record["left_right_independence"]["left_measurement_reference"]
        == "left independent measurement sheet pass 1 and 2"
    )
    assert record["left_right_independence"]["values_not_copied_between_sides"] is True
    assert all(value is False for value in record["safety_screen"].values())
    assert (
        record["independence_safety_update_events"][0]["independence_safety_update_is_physical_validation_evidence"]
        is False
    )
    assert record["independence_safety_update_events"][0]["fr018_implementation_cleared"] is False

    intake = _run_script(INTAKE_SCRIPT, "-Mode", "Status", "-MeasurementPath", str(measurement_path))
    assert intake.returncode == 0, intake.stderr
    intake_result = _payload(intake.stdout)
    assert intake_result["status"] == "ready_for_non_powered_mockup_patterning"
    assert intake_result["measurement_capture_ready_groups"] == 5
    assert intake_result["measurement_capture_pending_groups"] == 0
    assert intake_result["measurement_capture_failed_groups"] == 0
    assert intake_result["physical_validation_complete"] is False
    assert intake_result["stage17_completion_claim_allowed"] is False
    assert intake_result["fr018_implementation_cleared"] is False


def test_fr017_independence_safety_update_blocks_observed_symptom_without_writing(
    tmp_path: Path,
) -> None:
    measurement_path = tmp_path / "measurement-record.json"
    _create_ready_until_independence_record(measurement_path)

    proc = _run_script(
        INDEPENDENCE_SAFETY_UPDATE_SCRIPT,
        "-MeasurementPath",
        str(measurement_path),
        *_independence_safety_args(symptom_flag="TinglingObserved"),
    )

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "safety_symptom_recorded_requires_review"
    assert result["wrote_file"] is False
    assert result["operator_supplied_independence_safety_input_recorded"] is False
    assert result["safety_symptoms_recorded"] == ["tingling"]
    assert result["physical_validation_complete"] is False
    assert result["stage17_completion_claim_allowed"] is False
    assert result["fr018_implementation_cleared"] is False

    record = json.loads(measurement_path.read_text(encoding="utf-8-sig"))
    assert "independence_safety_update_events" not in record
    assert record["left_right_independence"]["left_arm_measured_separately"] == "PENDING"
    assert record["safety_screen"]["tingling"] == "PENDING"


def test_fr017_independence_safety_update_refuses_template_target() -> None:
    proc = _run_script(
        INDEPENDENCE_SAFETY_UPDATE_SCRIPT,
        "-MeasurementPath",
        str(TEMPLATE_PATH),
        *_independence_safety_args(),
    )

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "measurement_path_targets_template"
    assert result["wrote_file"] is False
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_independence_safety_update_rejects_duplicate_left_right_references(
    tmp_path: Path,
) -> None:
    measurement_path = tmp_path / "measurement-record.json"
    _create_ready_until_independence_record(measurement_path)

    proc = _run_script(
        INDEPENDENCE_SAFETY_UPDATE_SCRIPT,
        "-MeasurementPath",
        str(measurement_path),
        *_independence_safety_args(
            right_measurement_reference="left independent measurement sheet pass 1 and 2",
        ),
    )

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "invalid_independence_safety_update_input"
    assert result["wrote_file"] is False
    assert result["invalid_fields"] == ["left_right_independence.measurement_reference"]
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False
