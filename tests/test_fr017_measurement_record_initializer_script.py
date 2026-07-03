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
    output_path = tmp_path / "FR-017-MEASUREMENTS-2026-07-03-PILOT-RECORD.json"

    proc = _run_initializer(
        "-Mode",
        "Create",
        "-OutputPath",
        str(output_path),
        "-EvidenceDate",
        "2026-07-03",
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
    assert record["evidence"]["date"] == "2026-07-03"
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
