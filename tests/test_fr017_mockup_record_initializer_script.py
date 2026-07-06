from __future__ import annotations

import json
import shutil
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from tests.powershell_script_runner import run_powershell_script
from tests.test_fr017_mockup_readiness_gate_script import _ready_measurement_payload


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "fr017-new-mockup-record.ps1"
MOCKUP_GATE_SCRIPT = ROOT / "scripts" / "fr017-mockup-readiness-gate.ps1"
TEMPLATE_PATH = ROOT / "FR-017_Stage17_Package" / "FR-017-MOCKUP-BUILD-INPUT-TEMPLATE.json"


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


def _mockup_args(measurement_path: Path, output_path: Path, *, include_wrist_pressure: bool = True) -> list[str]:
    args = [
        "-Mode",
        "Create",
        "-OutputPath",
        str(output_path),
        "-MeasurementPath",
        str(measurement_path),
        "-EvidenceDate",
        date.today().isoformat(),
        "-Observer",
        "test-observer",
        "-BuildMethod",
        "non-powered soft cuff mockup only",
        "-PaddingLayer",
        "6mm closed-cell foam",
        "-SemiRigidOuterLayer",
        "thin semi-rigid thermoform sheet",
        "-UpperForearmStrap",
        "50mm hook-and-loop upper strap",
        "-LowerForearmStrap",
        "38mm hook-and-loop lower strap",
        "-QuickRelease",
        "outer forearm pull tab quick release",
        "-OuterForearmCableSleeve",
        "removable outer forearm fabric cable sleeve",
        "-NonLoadBearingAlignmentTabs",
        "soft non-load-bearing locator tabs",
        "-SensorPlaceholderBlanks",
        "flat fabric sensor placeholder blanks",
        "-ConfirmNonPoweredOnly",
        "-ConfirmNoLoadBearingClaim",
        "-ConfirmNoHardInnerForearmBuckles",
        "-ConfirmNoInnerElbowCrossing",
        "-ConfirmReleasesVisibleAndReachable",
        "-ConfirmGloveRemovalPathPreserved",
        "-ConfirmOuterForearmCableRouteOnly",
        "-ConfirmStopOnSymptoms",
        "-ConfirmLeftUpperStrapWidthMatchesMeasurement",
        "-ConfirmLeftLowerStrapWidthMatchesMeasurement",
        "-ConfirmLeftBoneReliefChannelPresent",
        "-ConfirmLeftInnerForearmNoPressureZoneMarked",
        "-ConfirmLeftWristClearanceKept",
        "-ConfirmLeftQuickReleaseInstalledOuterOrLateral",
        "-ConfirmLeftAlignmentTabsNonLoadBearing",
        "-ConfirmLeftCableSleeveOuterRouteOnly",
        "-ConfirmRightUpperStrapWidthMatchesMeasurement",
        "-ConfirmRightLowerStrapWidthMatchesMeasurement",
        "-ConfirmRightBoneReliefChannelPresent",
        "-ConfirmRightInnerForearmNoPressureZoneMarked",
        "-ConfirmRightWristClearanceKept",
        "-ConfirmRightQuickReleaseInstalledOuterOrLateral",
        "-ConfirmRightAlignmentTabsNonLoadBearing",
        "-ConfirmRightCableSleeveOuterRouteOnly",
    ]
    if include_wrist_pressure:
        args.insert(args.index("-ConfirmReleasesVisibleAndReachable"), "-ConfirmNoWristBonePressure")
    return args


def test_fr017_mockup_record_initializer_status_preflights_without_writing(
    tmp_path: Path,
) -> None:
    measurement_path = tmp_path / "ready-measurements.json"
    mockup_path = tmp_path / "candidate-mockup.json"
    measurement_path.write_text(json.dumps(_ready_measurement_payload()), encoding="utf-8")

    proc = _run_script(
        SCRIPT,
        "-Mode",
        "Status",
        "-MeasurementPath",
        str(measurement_path),
        "-OutputPath",
        str(mockup_path),
    )

    assert proc.returncode == 0, proc.stderr
    result = _payload(proc.stdout)
    assert result["kind"] == "francis.fr017.mockup_record_initializer"
    assert result["mode"] == "Status"
    assert result["status"] == "mockup_record_initializer_status"
    assert result["template_exists"] is True
    assert result["template_parse_ok"] is True
    assert result["output_path_required_for_create"] is False
    assert result["measurement_path_required_for_create"] is False
    assert result["output_path_targets_template"] is False
    assert result["output_parent_exists"] is True
    assert result["candidate_output_path_ready"] is True
    assert result["measurement_file_exists"] is True
    assert result["upstream_measurement_intake_status"] == "ready_for_non_powered_mockup_patterning"
    assert result["upstream_measurement_intake_ready"] is True
    assert result["wrote_file"] is False
    assert result["output_exists"] is False
    assert result["read_only_contract"] is True
    assert result["writes_repo"] is False
    assert result["writes_data"] is False
    assert result["operator_supplied_mockup_input_recorded"] is False
    assert result["mockup_record_is_physical_validation_evidence"] is False
    assert result["physical_validation_complete"] is False
    assert result["stage17_completion_claim_allowed"] is False
    assert result["mannequin_interface_test_complete"] is False
    assert result["pilot_testing_cleared"] is False
    assert result["powered_or_frame_coupled_testing_cleared"] is False
    assert result["fr018_implementation_cleared"] is False
    assert "fr017-new-mockup-record.ps1 -Mode Create" in result["create_command_template"]
    assert "fr017-mockup-readiness-gate.ps1 -Mode Status" in result["mockup_readiness_status_command_template"]
    assert result["next_command"] == result["create_command_template"]
    assert not mockup_path.exists()


def test_fr017_mockup_record_initializer_creates_non_powered_record_without_clearance(
    tmp_path: Path,
) -> None:
    measurement_path = tmp_path / "ready-measurements.json"
    mockup_path = tmp_path / "ready-mockup.json"
    measurement_path.write_text(json.dumps(_ready_measurement_payload()), encoding="utf-8")

    proc = _run_script(SCRIPT, *_mockup_args(measurement_path, mockup_path))

    assert proc.returncode == 0, proc.stderr
    result = _payload(proc.stdout)
    assert result["kind"] == "francis.fr017.mockup_record_initializer"
    assert result["status"] == "created_mockup_build_record"
    assert result["wrote_file"] is True
    assert result["operator_supplied_mockup_input_recorded"] is True
    assert result["upstream_measurement_intake_status"] == "ready_for_non_powered_mockup_patterning"
    assert result["upstream_measurement_intake_ready"] is True
    assert result["mockup_record_is_physical_validation_evidence"] is False
    assert result["physical_validation_complete"] is False
    assert result["stage17_completion_claim_allowed"] is False
    assert result["mannequin_interface_test_complete"] is False
    assert result["pilot_testing_cleared"] is False
    assert result["powered_or_frame_coupled_testing_cleared"] is False
    assert result["fr018_implementation_cleared"] is False
    assert "does not mark physical validation complete" in result["no_fake_validation_lock"]
    assert "fr017-mockup-readiness-gate.ps1" in result["next_command"]

    record = json.loads(mockup_path.read_text(encoding="utf-8-sig"))
    assert record["kind"] == "francis.fr017.mockup_build.v1"
    assert record["evidence"]["measurement_record_path"] == str(measurement_path.resolve())
    assert record["materials"]["padding_layer"] == "6mm closed-cell foam"
    assert record["constraints"]["no_wrist_bone_pressure"] is True
    assert record["sides"]["left"]["wrist_clearance_kept"] is True
    assert record["sides"]["right"]["cable_sleeve_outer_route_only"] is True
    assert record["record_generation"]["mockup_record_is_physical_validation_evidence"] is False
    assert record["record_generation"]["fr018_implementation_cleared"] is False

    gate = _run_script(
        MOCKUP_GATE_SCRIPT,
        "-Mode",
        "Status",
        "-MeasurementPath",
        str(measurement_path),
        "-MockupPath",
        str(mockup_path),
    )
    assert gate.returncode == 0, gate.stderr
    gate_result = _payload(gate.stdout)
    assert gate_result["status"] == "ready_for_mannequin_interface_test"
    assert gate_result["mockup_capture_ready_groups"] == 5
    assert gate_result["physical_validation_complete"] is False
    assert gate_result["mannequin_interface_test_complete"] is False
    assert gate_result["pilot_testing_cleared"] is False
    assert gate_result["fr018_implementation_cleared"] is False


def test_fr017_mockup_record_initializer_refuses_upstream_measurement_that_is_not_ready(
    tmp_path: Path,
) -> None:
    measurement_path = tmp_path / "pending-measurements.json"
    mockup_path = tmp_path / "mockup.json"
    measurement_payload = _ready_measurement_payload()
    measurement_payload["safety_screen"]["tingling"] = True
    measurement_path.write_text(json.dumps(measurement_payload), encoding="utf-8")

    proc = _run_script(SCRIPT, *_mockup_args(measurement_path, mockup_path))

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "upstream_measurement_intake_not_ready"
    assert result["upstream_measurement_intake_status"] == "failed_requires_redesign_or_medical_review"
    assert result["wrote_file"] is False
    assert result["output_exists"] is False
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_mockup_record_initializer_refuses_template_target(tmp_path: Path) -> None:
    measurement_path = tmp_path / "ready-measurements.json"
    measurement_path.write_text(json.dumps(_ready_measurement_payload()), encoding="utf-8")

    proc = _run_script(SCRIPT, *_mockup_args(measurement_path, TEMPLATE_PATH))

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "output_path_targets_template"
    assert result["wrote_file"] is False
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_mockup_record_initializer_refuses_overwrite(tmp_path: Path) -> None:
    measurement_path = tmp_path / "ready-measurements.json"
    mockup_path = tmp_path / "existing-mockup.json"
    measurement_path.write_text(json.dumps(_ready_measurement_payload()), encoding="utf-8")
    mockup_path.write_text("do not replace", encoding="utf-8")

    proc = _run_script(SCRIPT, *_mockup_args(measurement_path, mockup_path))

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "output_file_exists"
    assert result["wrote_file"] is False
    assert mockup_path.read_text(encoding="utf-8") == "do not replace"
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_mockup_record_initializer_rejects_missing_safety_confirmation(
    tmp_path: Path,
) -> None:
    measurement_path = tmp_path / "ready-measurements.json"
    mockup_path = tmp_path / "unsafe-mockup.json"
    measurement_path.write_text(json.dumps(_ready_measurement_payload()), encoding="utf-8")

    proc = _run_script(
        SCRIPT,
        *_mockup_args(measurement_path, mockup_path, include_wrist_pressure=False),
    )

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "invalid_mockup_record_input"
    assert result["wrote_file"] is False
    assert result["invalid_fields"] == ["constraints.no_wrist_bone_pressure"]
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_mockup_record_initializer_rejects_powered_build_method(
    tmp_path: Path,
) -> None:
    measurement_path = tmp_path / "ready-measurements.json"
    mockup_path = tmp_path / "unsafe-build-method.json"
    measurement_path.write_text(json.dumps(_ready_measurement_payload()), encoding="utf-8")
    args = _mockup_args(measurement_path, mockup_path)
    args[args.index("-BuildMethod") + 1] = "powered rigid forearm frame"

    proc = _run_script(SCRIPT, *args)

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "invalid_mockup_record_input"
    assert result["wrote_file"] is False
    assert result["invalid_fields"] == ["evidence.build_method"]
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False
