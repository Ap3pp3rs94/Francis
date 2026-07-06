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
UPDATE_SCRIPT = ROOT / "scripts" / "fr017-update-measurement-record.ps1"
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


def _left_measurement_args() -> list[str]:
    return [
        "-Mode",
        "UpdateSide",
        "-Side",
        "left",
        "-ForearmCircumference25mmBelowElbowCrease",
        "235",
        "-ForearmCircumferenceMidForearm",
        "225",
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


@pytest.mark.unit
def test_fr017_measurement_record_update_records_left_side_without_completion_claim(tmp_path: Path) -> None:
    measurement_path = tmp_path / "measurement-record.json"
    _create_setup_brief_record(measurement_path)

    proc = _run_script(
        UPDATE_SCRIPT,
        "-MeasurementPath",
        str(measurement_path),
        *_left_measurement_args(),
    )

    assert proc.returncode == 0, proc.stderr
    result = _payload(proc.stdout)
    assert result["kind"] == "francis.fr017.measurement_record_update"
    assert result["status"] == "updated_measurement_side_pass"
    assert result["wrote_file"] is True
    assert result["writes_data"] is True
    assert result["operator_supplied_measurement_input_recorded"] is True
    assert result["side_update_is_physical_validation_evidence"] is False
    assert result["physical_validation_complete"] is False
    assert result["stage17_completion_claim_allowed"] is False
    assert result["fr018_implementation_cleared"] is False
    assert result["updated_fields"] == [
        "sides.left.forearm_circumference_25mm_below_elbow_crease",
        "sides.left.forearm_circumference_mid_forearm",
        "sides.left.forearm_circumference_40mm_above_wrist_crease",
        "sides.left.forearm_length_elbow_crease_to_wrist_crease",
        "sides.left.outer_forearm_usable_panel_length",
        "sides.left.upper_strap_allowed_band_width",
        "sides.left.lower_strap_allowed_band_width",
        "sides.left.bone_ridge_relief_length",
        "sides.left.inner_forearm_no_pressure_zone_width",
        "sides.left.wrist_clearance_gap",
        "repeatability.left.second_pass_completed",
        "repeatability.left.max_delta_mm",
        "repeatability.left.all_required_measurements_within_5mm",
    ]

    record = json.loads(measurement_path.read_text(encoding="utf-8-sig"))
    assert record["sides"]["left"]["wrist_clearance_gap"] == 42
    assert record["repeatability"]["left"]["max_delta_mm"] == 3
    assert record["measurement_update_events"][0]["side"] == "left"
    assert record["measurement_update_events"][0]["side_update_is_physical_validation_evidence"] is False

    intake = _run_script(INTAKE_SCRIPT, "-Mode", "Status", "-MeasurementPath", str(measurement_path))
    assert intake.returncode == 0, intake.stderr
    intake_result = _payload(intake.stdout)
    assert intake_result["status"] == "pending_measurements"
    assert intake_result["measurement_capture_ready_groups"] == 2
    assert intake_result["measurement_capture_pending_groups"] == 3
    assert intake_result["measurement_capture_first_blocking_group_id"] == "right_arm_numeric_measurement_passes"
    assert intake_result["physical_validation_complete"] is False
    assert intake_result["fr018_implementation_cleared"] is False


@pytest.mark.unit
def test_fr017_measurement_record_update_refuses_template_target() -> None:
    proc = _run_script(
        UPDATE_SCRIPT,
        "-MeasurementPath",
        str(TEMPLATE_PATH),
        *_left_measurement_args(),
    )

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "measurement_path_targets_template"
    assert result["wrote_file"] is False
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


@pytest.mark.unit
def test_fr017_measurement_record_update_refuses_overwrite_without_explicit_flag(tmp_path: Path) -> None:
    measurement_path = tmp_path / "measurement-record.json"
    _create_setup_brief_record(measurement_path)
    first = _run_script(UPDATE_SCRIPT, "-MeasurementPath", str(measurement_path), *_left_measurement_args())
    assert first.returncode == 0, first.stderr

    second = _run_script(UPDATE_SCRIPT, "-MeasurementPath", str(measurement_path), *_left_measurement_args())

    assert second.returncode == 1
    result = _payload(second.stdout)
    assert result["status"] == "measurement_fields_already_populated"
    assert result["wrote_file"] is False
    assert "sides.left.wrist_clearance_gap" in result["overwrite_blocked_fields"]
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


@pytest.mark.unit
def test_fr017_measurement_record_update_rejects_excess_repeatability_delta(tmp_path: Path) -> None:
    measurement_path = tmp_path / "measurement-record.json"
    _create_setup_brief_record(measurement_path)
    args = _left_measurement_args()
    args[args.index("-MaxDeltaMm") + 1] = "6"

    proc = _run_script(UPDATE_SCRIPT, "-MeasurementPath", str(measurement_path), *args)

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "invalid_measurement_update_input"
    assert result["wrote_file"] is False
    assert result["invalid_fields"] == ["repeatability.left.max_delta_mm"]
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


@pytest.mark.unit
def test_fr017_measurement_record_update_reports_missing_top_level_properties(tmp_path: Path) -> None:
    measurement_path = tmp_path / "measurement-record.json"
    measurement_path.write_text("{}", encoding="utf-8")

    proc = _run_script(
        UPDATE_SCRIPT,
        "-MeasurementPath",
        str(measurement_path),
        *_left_measurement_args(),
    )

    assert proc.returncode == 1
    assert proc.stderr == ""
    result = _payload(proc.stdout)
    assert result["status"] == "invalid_measurement_update_input"
    assert result["wrote_file"] is False
    assert result["invalid_fields"] == [
        "kind",
        "component",
        "units",
        "sides.left",
        "repeatability.left",
    ]
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False
