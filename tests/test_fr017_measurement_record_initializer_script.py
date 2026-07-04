from __future__ import annotations

import json
import shutil
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest

from tests.powershell_script_runner import run_powershell_script


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "fr017-new-measurement-record.ps1"
INTAKE_SCRIPT = ROOT / "scripts" / "fr017-measurement-intake.ps1"
TEMPLATE_PATH = ROOT / "FR-017_Stage17_Package" / "FR-017-MEASUREMENTS-INPUT-TEMPLATE.json"


def _powershell() -> str:
    exe = shutil.which("pwsh") or shutil.which("powershell")
    if not exe:
        pytest.skip("PowerShell is not available")
    return exe


def _run_initializer(*args: str):
    return run_powershell_script(
        _powershell(),
        SCRIPT,
        args,
        cwd=ROOT,
        timeout_seconds=20,
    )


def _run_intake(*args: str):
    return run_powershell_script(
        _powershell(),
        INTAKE_SCRIPT,
        args,
        cwd=ROOT,
        timeout_seconds=20,
    )


def _payload(stdout: str) -> dict[str, Any]:
    return json.loads(stdout)


def test_fr017_measurement_record_initializer_creates_pending_working_record(tmp_path: Path) -> None:
    evidence_date = date.today().isoformat()
    output_path = tmp_path / f"FR-017-MEASUREMENTS-{evidence_date}-PILOT-RECORD.json"

    proc = _run_initializer(
        "-Mode",
        "Create",
        "-OutputPath",
        str(output_path),
        "-EvidenceDate",
        evidence_date,
        "-Observer",
        "test-observer",
        "-PilotId",
        "pilot-reference",
        "-MeasurementTool",
        "flexible metric tape",
    )

    assert proc.returncode == 0, proc.stderr
    result = _payload(proc.stdout)
    assert result["kind"] == "francis.fr017.measurement_record_initializer"
    assert result["status"] == "created_pending_measurement_record"
    assert result["wrote_file"] is True
    assert result["output_exists"] is True
    assert result["writes_data"] is True
    assert result["grants_execution_authority"] is False
    assert result["physical_validation_complete"] is False
    assert result["stage17_completion_claim_allowed"] is False
    assert result["fr018_implementation_cleared"] is False
    assert result["record_is_measurement_evidence"] is False
    assert "does not record physical measurements" in result["no_fake_validation_lock"]
    assert str(output_path) in result["next_command"]

    record = json.loads(output_path.read_text(encoding="utf-8-sig"))
    assert record["kind"] == "francis.fr017.measurements.v1"
    assert record["evidence"]["date"] == evidence_date
    assert record["evidence"]["observer"] == "test-observer"
    assert record["evidence"]["pilot_id"] == "pilot-reference"
    assert record["evidence"]["measurement_tool"] == "flexible metric tape"
    assert record["sides"]["left"]["wrist_clearance_gap"] == "PENDING"
    assert record["record_generation"]["record_is_measurement_evidence"] is False
    assert record["record_generation"]["physical_validation_complete"] is False
    assert record["record_generation"]["fr018_implementation_cleared"] is False

    intake = _run_intake("-Mode", "Status", "-MeasurementPath", str(output_path))
    assert intake.returncode == 0, intake.stderr
    intake_result = _payload(intake.stdout)
    assert intake_result["status"] == "pending_measurements"
    assert intake_result["physical_validation_complete"] is False
    assert intake_result["fr018_implementation_cleared"] is False
    assert "sides.left.wrist_clearance_gap" in intake_result["missing_fields"]


def test_fr017_measurement_record_initializer_can_capture_setup_brief_only(tmp_path: Path) -> None:
    evidence_date = date.today().isoformat()
    output_path = tmp_path / "setup-brief-only.json"

    proc = _run_initializer(
        "-Mode",
        "Create",
        "-OutputPath",
        str(output_path),
        "-EvidenceDate",
        evidence_date,
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
    result = _payload(proc.stdout)
    assert result["status"] == "created_pending_measurement_record"
    assert result["record_is_measurement_evidence"] is False
    assert result["setup_brief_is_physical_validation_evidence"] is False
    assert result["physical_validation_complete"] is False
    assert result["stage17_completion_claim_allowed"] is False
    assert result["fr018_implementation_cleared"] is False
    assert result["updated_fields"] == [
        "evidence.date",
        "evidence.observer",
        "evidence.pilot_id",
        "evidence.measurement_tool",
        "measurement_conditions.no_tissue_compression_used",
        "measurement_conditions.no_wrist_bone_compression_used",
        "measurement_conditions.metric_tool_used",
        "measurement_conditions.arm_relaxed_palm_neutral_or_exception_recorded",
        "measurement_conditions.stop_conditions_briefed",
        "measurement_conditions.condition_notes",
    ]

    record = json.loads(output_path.read_text(encoding="utf-8-sig"))
    assert record["measurement_conditions"] == {
        "no_tissue_compression_used": True,
        "no_wrist_bone_compression_used": True,
        "metric_tool_used": True,
        "arm_relaxed_palm_neutral_or_exception_recorded": True,
        "stop_conditions_briefed": True,
        "condition_notes": "No tissue compression, no wrist-bone compression, metric tape, and stop briefing completed.",
    }
    assert record["sides"]["left"]["wrist_clearance_gap"] == "PENDING"
    assert record["safety_screen"]["tingling"] == "PENDING"
    assert record["record_generation"]["initializer_updated_fields"] == result["updated_fields"]
    assert record["record_generation"]["setup_brief_is_physical_validation_evidence"] is False

    intake = _run_intake("-Mode", "Status", "-MeasurementPath", str(output_path))
    assert intake.returncode == 0, intake.stderr
    intake_result = _payload(intake.stdout)
    assert intake_result["status"] == "pending_measurements"
    assert intake_result["measurement_capture_ready_groups"] == 1
    assert intake_result["measurement_capture_pending_groups"] == 4
    assert intake_result["measurement_capture_first_blocking_group_id"] == "left_arm_numeric_measurement_passes"
    assert intake_result["measurement_capture_plan_status"][0]["status"] == "ready_for_measurement_intake_review"
    assert intake_result["physical_validation_complete"] is False
    assert intake_result["fr018_implementation_cleared"] is False


def test_fr017_measurement_record_initializer_refuses_overwrite(tmp_path: Path) -> None:
    output_path = tmp_path / "existing.json"
    output_path.write_text("do not replace", encoding="utf-8")

    proc = _run_initializer("-Mode", "Create", "-OutputPath", str(output_path))

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "output_file_exists"
    assert result["wrote_file"] is False
    assert result["writes_data"] is False
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False
    assert output_path.read_text(encoding="utf-8") == "do not replace"


def test_fr017_measurement_record_initializer_refuses_template_target() -> None:
    proc = _run_initializer("-Mode", "Create", "-OutputPath", str(TEMPLATE_PATH))

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "output_path_targets_template"
    assert result["wrote_file"] is False
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_measurement_record_initializer_rejects_pending_condition_notes(tmp_path: Path) -> None:
    output_path = tmp_path / "pending-condition-notes.json"

    proc = _run_initializer(
        "-Mode",
        "Create",
        "-OutputPath",
        str(output_path),
        "-ConditionNotes",
        "PENDING",
    )

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "invalid_initializer_input"
    assert result["invalid_fields"] == ["measurement_conditions.condition_notes"]
    assert result["wrote_file"] is False
    assert result["output_exists"] is False
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_measurement_record_initializer_rejects_future_date(tmp_path: Path) -> None:
    output_path = tmp_path / "future-date.json"
    future_date = (date.today() + timedelta(days=1)).isoformat()

    proc = _run_initializer(
        "-Mode",
        "Create",
        "-OutputPath",
        str(output_path),
        "-EvidenceDate",
        future_date,
    )

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "invalid_initializer_input"
    assert result["invalid_fields"] == ["evidence.date"]
    assert result["wrote_file"] is False
    assert result["output_exists"] is False
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False
