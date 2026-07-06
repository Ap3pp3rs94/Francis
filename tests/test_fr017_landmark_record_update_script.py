from __future__ import annotations

import json
import shutil
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from tests.powershell_script_runner import run_powershell_script


ROOT = Path(__file__).resolve().parents[1]
INITIALIZER_SCRIPT = ROOT / "scripts" / "fr017-new-measurement-record.ps1"
MEASUREMENT_UPDATE_SCRIPT = ROOT / "scripts" / "fr017-update-measurement-record.ps1"
LANDMARK_UPDATE_SCRIPT = ROOT / "scripts" / "fr017-update-landmark-record.ps1"
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
        timeout_seconds=20,
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


def _landmark_args() -> list[str]:
    return [
        "-Mode",
        "UpdateLandmarks",
        "-LeftInnerElbowCreaseBoundary",
        "left inner elbow labeled photo A",
        "-LeftWristBoneBoundary",
        "left wrist labeled photo B",
        "-LeftRadiusRidgeRelief",
        "left radius labeled photo C",
        "-LeftUlnaRidgeRelief",
        "left ulna labeled photo D",
        "-LeftOuterForearmCableRoute",
        "left outer cable labeled photo E",
        "-LeftQuickReleaseReachZone",
        "left quick release labeled photo F",
        "-LeftGloveRemovalPath",
        "left glove path labeled photo G",
        "-RightInnerElbowCreaseBoundary",
        "right inner elbow labeled photo A",
        "-RightWristBoneBoundary",
        "right wrist labeled photo B",
        "-RightRadiusRidgeRelief",
        "right radius labeled photo C",
        "-RightUlnaRidgeRelief",
        "right ulna labeled photo D",
        "-RightOuterForearmCableRoute",
        "right outer cable labeled photo E",
        "-RightQuickReleaseReachZone",
        "right quick release labeled photo F",
        "-RightGloveRemovalPath",
        "right glove path labeled photo G",
        "-ConfirmInnerElbowCreaseBoundary",
        "-ConfirmWristBoneBoundary",
        "-ConfirmRadiusUlnaReliefPaths",
        "-ConfirmOuterForearmCableRoute",
        "-ConfirmQuickReleaseReachZone",
        "-ConfirmGloveRemovalPath",
        "-ConfirmSkinSafeMarkingUsed",
        "-LandmarkNotes",
        "Skin-safe marks identify inner elbow, wrist, radius, ulna, cable route, quick release, glove path, and side labels.",
    ]


def test_fr017_landmark_update_status_preflights_marked_zones_without_writing(tmp_path: Path) -> None:
    measurement_path = tmp_path / "measurement-record.json"
    _create_setup_and_numeric_record(measurement_path)
    before = measurement_path.read_bytes()

    proc = _run_script(
        LANDMARK_UPDATE_SCRIPT,
        "-Mode",
        "Status",
        "-MeasurementPath",
        str(measurement_path),
    )

    assert proc.returncode == 0, proc.stderr
    result = _payload(proc.stdout)
    assert result["kind"] == "francis.fr017.landmark_record_update"
    assert result["mode"] == "Status"
    assert result["status"] == "measurement_landmark_update_status"
    assert result["output_exists"] is True
    assert result["wrote_file"] is False
    assert result["read_only_contract"] is True
    assert result["writes_repo"] is False
    assert result["writes_data"] is False
    assert result["operator_supplied_landmark_input_recorded"] is False
    assert result["landmark_update_is_physical_validation_evidence"] is False
    assert result["physical_validation_complete"] is False
    assert result["stage17_completion_claim_allowed"] is False
    assert result["fr018_implementation_cleared"] is False
    assert "marked_zones.left.wrist_bone_boundary" in result["landmark_required_fields"]
    assert "marked_zones.right.quick_release_reach_zone" in result["landmark_required_fields"]
    assert "landmark_confirmation.landmark_notes" in result["landmark_required_fields"]
    assert "marked_zones.left.wrist_bone_boundary" in result["landmark_missing_fields"]
    assert "landmark_confirmation.landmark_notes" in result["landmark_missing_fields"]
    assert result["landmark_existing_fields"] == []
    assert result["landmark_missing_field_count"] == len(result["landmark_missing_fields"])
    assert result["landmark_capture_group_complete"] is False
    assert "fr017-update-landmark-record.ps1 -Mode UpdateLandmarks" in result["update_command_template"]
    assert str(measurement_path) in result["update_command_template"]
    assert result["next_command"] == result["update_command_template"]
    assert measurement_path.read_bytes() == before
    record = json.loads(measurement_path.read_text(encoding="utf-8-sig"))
    assert "landmark_update_events" not in record


def test_fr017_landmark_update_records_marked_zones_without_completion_claim(tmp_path: Path) -> None:
    measurement_path = tmp_path / "measurement-record.json"
    _create_setup_and_numeric_record(measurement_path)

    proc = _run_script(
        LANDMARK_UPDATE_SCRIPT,
        "-MeasurementPath",
        str(measurement_path),
        *_landmark_args(),
    )

    assert proc.returncode == 0, proc.stderr
    result = _payload(proc.stdout)
    assert result["kind"] == "francis.fr017.landmark_record_update"
    assert result["status"] == "updated_measurement_landmarks"
    assert result["wrote_file"] is True
    assert result["operator_supplied_landmark_input_recorded"] is True
    assert result["landmark_update_is_physical_validation_evidence"] is False
    assert result["physical_validation_complete"] is False
    assert result["stage17_completion_claim_allowed"] is False
    assert result["fr018_implementation_cleared"] is False
    assert "marked_zones.left.inner_elbow_crease_boundary" in result["updated_fields"]
    assert "landmark_confirmation.landmark_notes" in result["updated_fields"]

    record = json.loads(measurement_path.read_text(encoding="utf-8-sig"))
    assert record["marked_zones"]["left"]["wrist_bone_boundary"] == "left wrist labeled photo B"
    assert record["landmark_confirmation"]["skin_safe_marking_used"] is True
    assert record["landmark_update_events"][0]["landmark_update_is_physical_validation_evidence"] is False

    intake = _run_script(INTAKE_SCRIPT, "-Mode", "Status", "-MeasurementPath", str(measurement_path))
    assert intake.returncode == 0, intake.stderr
    intake_result = _payload(intake.stdout)
    assert intake_result["status"] == "pending_measurements"
    assert intake_result["measurement_capture_ready_groups"] == 4
    assert intake_result["measurement_capture_pending_groups"] == 1
    assert intake_result["measurement_capture_first_blocking_group_id"] == "left_right_independence_and_safety_screen"
    assert intake_result["physical_validation_complete"] is False
    assert intake_result["fr018_implementation_cleared"] is False


def test_fr017_landmark_update_refuses_template_target() -> None:
    proc = _run_script(
        LANDMARK_UPDATE_SCRIPT,
        "-MeasurementPath",
        str(TEMPLATE_PATH),
        *_landmark_args(),
    )

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "measurement_path_targets_template"
    assert result["wrote_file"] is False
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_landmark_update_rejects_copied_left_right_reference(tmp_path: Path) -> None:
    measurement_path = tmp_path / "measurement-record.json"
    _create_setup_and_numeric_record(measurement_path)
    args = _landmark_args()
    args[args.index("-RightWristBoneBoundary") + 1] = "left wrist labeled photo B"

    proc = _run_script(LANDMARK_UPDATE_SCRIPT, "-MeasurementPath", str(measurement_path), *args)

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "copied_left_right_landmark_reference"
    assert result["wrote_file"] is False
    assert result["reference_blockers"] == ["marked_zones.wrist_bone_boundary_left_right_references_must_be_distinct"]
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_landmark_update_refuses_overwrite_without_explicit_flag(tmp_path: Path) -> None:
    measurement_path = tmp_path / "measurement-record.json"
    _create_setup_and_numeric_record(measurement_path)
    first = _run_script(LANDMARK_UPDATE_SCRIPT, "-MeasurementPath", str(measurement_path), *_landmark_args())
    assert first.returncode == 0, first.stderr

    second = _run_script(LANDMARK_UPDATE_SCRIPT, "-MeasurementPath", str(measurement_path), *_landmark_args())

    assert second.returncode == 1
    result = _payload(second.stdout)
    assert result["status"] == "landmark_fields_already_populated"
    assert result["wrote_file"] is False
    assert "marked_zones.left.wrist_bone_boundary" in result["overwrite_blocked_fields"]
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False
