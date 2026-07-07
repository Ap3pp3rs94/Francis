from __future__ import annotations

import json
import shutil
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest

from tests.powershell_script_runner import run_powershell_script


ROOT = Path(__file__).resolve().parents[1]
INITIALIZER_SCRIPT = ROOT / "scripts" / "fr017-new-measurement-record.ps1"
UPDATE_SCRIPT = ROOT / "scripts" / "fr017-update-measurement-setup-record.ps1"
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
        timeout_seconds=30,
    )


def _payload(stdout: str) -> dict[str, Any]:
    return json.loads(stdout)


def _create_pending_record(output_path: Path) -> None:
    proc = _run_script(INITIALIZER_SCRIPT, "-Mode", "Create", "-OutputPath", str(output_path))
    assert proc.returncode == 0, proc.stderr


def _setup_args() -> list[str]:
    return [
        "-Mode",
        "UpdateSetup",
        "-EvidenceDate",
        date.today().isoformat(),
        "-Observer",
        "test-observer",
        "-PilotId",
        "pilot-reference",
        "-MeasurementTool",
        "flexible metric tape",
        "-Method",
        "flexible tape, no tissue compression",
        "-Posture",
        "arm relaxed, palm neutral unless otherwise noted",
        "-ConfirmNoTissueCompressionUsed",
        "-ConfirmNoWristBoneCompressionUsed",
        "-ConfirmMetricToolUsed",
        "-ConfirmArmRelaxedPalmNeutralOrExceptionRecorded",
        "-ConfirmStopConditionsBriefed",
        "-ConditionNotes",
        "No tissue compression, no wrist-bone compression, metric tool, and stop briefing confirmed.",
    ]


def test_fr017_measurement_setup_update_status_preflights_pending_record_without_writing(
    tmp_path: Path,
) -> None:
    measurement_path = tmp_path / "measurement-record.json"
    _create_pending_record(measurement_path)
    before = measurement_path.read_bytes()

    proc = _run_script(UPDATE_SCRIPT, "-Mode", "Status", "-MeasurementPath", str(measurement_path))

    assert proc.returncode == 0, proc.stderr
    result = _payload(proc.stdout)
    assert result["kind"] == "francis.fr017.measurement_setup_record_update"
    assert result["mode"] == "Status"
    assert result["status"] == "measurement_setup_update_status"
    assert result["output_exists"] is True
    assert result["wrote_file"] is False
    assert result["read_only_contract"] is True
    assert result["writes_repo"] is False
    assert result["writes_data"] is False
    assert result["operator_supplied_setup_input_recorded"] is False
    assert result["setup_update_is_physical_validation_evidence"] is False
    assert result["physical_validation_complete"] is False
    assert result["stage17_completion_claim_allowed"] is False
    assert result["fr018_implementation_cleared"] is False
    assert "evidence.date" in result["setup_missing_fields"]
    assert "measurement_conditions.stop_conditions_briefed" in result["setup_missing_fields"]
    assert "evidence.method" in result["setup_existing_fields"]
    assert result["setup_missing_field_count"] == len(result["setup_missing_fields"])
    assert result["setup_capture_group_complete"] is False
    assert "fr017-update-measurement-setup-record.ps1 -Mode UpdateSetup" in result["update_command_template"]
    assert str(measurement_path) in result["update_command_template"]
    assert result["next_command_kind"] == "update_setup_safety_brief"
    assert "operator handoff only" in result["next_command_contract"]
    assert "does not clear FR-018" in result["next_command_contract"]
    assert "fr017-measurement-intake.ps1 -Mode Status" in result["next_status_command_template"]
    assert str(measurement_path) in result["next_status_command_template"]
    assert result["next_command"] == result["update_command_template"]
    assert measurement_path.read_bytes() == before
    record = json.loads(measurement_path.read_text(encoding="utf-8-sig"))
    assert "measurement_setup_update_events" not in record


def test_fr017_measurement_setup_update_records_first_capture_group_without_completion_claim(
    tmp_path: Path,
) -> None:
    measurement_path = tmp_path / "measurement-record.json"
    _create_pending_record(measurement_path)

    proc = _run_script(UPDATE_SCRIPT, "-MeasurementPath", str(measurement_path), *_setup_args())

    assert proc.returncode == 0, proc.stderr
    result = _payload(proc.stdout)
    assert result["kind"] == "francis.fr017.measurement_setup_record_update"
    assert result["status"] == "updated_measurement_setup_brief"
    assert result["wrote_file"] is True
    assert result["operator_supplied_setup_input_recorded"] is True
    assert result["setup_update_is_physical_validation_evidence"] is False
    assert result["physical_validation_complete"] is False
    assert result["stage17_completion_claim_allowed"] is False
    assert result["fr018_implementation_cleared"] is False
    assert result["next_command_kind"] == "rerun_measurement_intake"
    assert "fr017-measurement-intake.ps1 -Mode Status" in result["next_status_command_template"]
    assert str(measurement_path) in result["next_status_command_template"]
    assert result["next_command"] == result["next_status_command_template"]
    assert result["updated_fields"] == [
        "evidence.date",
        "evidence.observer",
        "evidence.pilot_id",
        "evidence.measurement_tool",
        "evidence.method",
        "evidence.posture",
        "measurement_conditions.no_tissue_compression_used",
        "measurement_conditions.no_wrist_bone_compression_used",
        "measurement_conditions.metric_tool_used",
        "measurement_conditions.arm_relaxed_palm_neutral_or_exception_recorded",
        "measurement_conditions.stop_conditions_briefed",
        "measurement_conditions.condition_notes",
    ]

    record = json.loads(measurement_path.read_text(encoding="utf-8-sig"))
    assert record["evidence"]["method"] == "flexible tape, no tissue compression"
    assert record["evidence"]["posture"] == "arm relaxed, palm neutral unless otherwise noted"
    assert record["measurement_conditions"]["stop_conditions_briefed"] is True
    assert record["measurement_setup_update_events"][0]["setup_update_is_physical_validation_evidence"] is False

    intake = _run_script(INTAKE_SCRIPT, "-Mode", "Status", "-MeasurementPath", str(measurement_path))
    assert intake.returncode == 0, intake.stderr
    intake_result = _payload(intake.stdout)
    assert intake_result["status"] == "pending_measurements"
    assert intake_result["measurement_capture_ready_groups"] == 1
    assert intake_result["measurement_capture_pending_groups"] == 4
    assert intake_result["measurement_capture_first_blocking_group_id"] == "left_arm_numeric_measurement_passes"
    assert intake_result["physical_validation_complete"] is False
    assert intake_result["fr018_implementation_cleared"] is False


def test_fr017_measurement_setup_update_refuses_template_target() -> None:
    proc = _run_script(UPDATE_SCRIPT, "-MeasurementPath", str(TEMPLATE_PATH), *_setup_args())

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "measurement_path_targets_template"
    assert result["wrote_file"] is False
    assert result["next_command_kind"] == "none"
    assert result["next_command"] == ""
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_measurement_setup_update_refuses_overwrite_without_explicit_flag(
    tmp_path: Path,
) -> None:
    measurement_path = tmp_path / "measurement-record.json"
    _create_pending_record(measurement_path)
    first = _run_script(UPDATE_SCRIPT, "-MeasurementPath", str(measurement_path), *_setup_args())
    assert first.returncode == 0, first.stderr

    second = _run_script(UPDATE_SCRIPT, "-MeasurementPath", str(measurement_path), *_setup_args())

    assert second.returncode == 1
    result = _payload(second.stdout)
    assert result["status"] == "measurement_setup_fields_already_populated"
    assert result["wrote_file"] is False
    assert "evidence.date" in result["overwrite_blocked_fields"]
    assert "measurement_conditions.stop_conditions_briefed" in result["overwrite_blocked_fields"]
    assert result["next_command_kind"] == "none"
    assert result["next_command"] == ""
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_measurement_setup_update_rejects_future_date(tmp_path: Path) -> None:
    measurement_path = tmp_path / "measurement-record.json"
    _create_pending_record(measurement_path)
    args = _setup_args()
    args[args.index("-EvidenceDate") + 1] = (date.today() + timedelta(days=1)).isoformat()

    proc = _run_script(UPDATE_SCRIPT, "-MeasurementPath", str(measurement_path), *args)

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "invalid_measurement_setup_update_input"
    assert result["wrote_file"] is False
    assert result["invalid_fields"] == ["evidence.date"]
    assert result["next_command_kind"] == "none"
    assert result["next_command"] == ""
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False
