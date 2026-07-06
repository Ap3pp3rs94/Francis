from __future__ import annotations

import json
import shutil
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from tests.powershell_script_runner import run_powershell_script
from tests.test_fr017_pilot_static_fit_gate_script import (
    _ready_static_fit_payload,
    _write_upstream_ready_records,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "fr017-new-pilot-movement-record.ps1"
MOVEMENT_GATE_SCRIPT = ROOT / "scripts" / "fr017-pilot-movement-gate.ps1"
TEMPLATE_PATH = ROOT / "FR-017_Stage17_Package" / "FR-017-PILOT-MOVEMENT-INPUT-TEMPLATE.json"

CONFIRM_ARGS = [
    "-ConfirmNonPoweredOnly",
    "-ConfirmNoFrameOrPowerCoupling",
    "-ConfirmPilotStaticFitGatePassed",
    "-ConfirmObserverPresent",
    "-ConfirmEmergencyReleaseBriefed",
    "-ConfirmStopOnSymptoms",
    "-ConfirmPilotCanSelfRemoveOrAbort",
    "-ConfirmLeftElbowFlexionNoCreaseCompression",
    "-ConfirmLeftElbowExtensionNoCuffMigration",
    "-ConfirmLeftWristFlexionNoDistalEdgePressure",
    "-ConfirmLeftWristExtensionNoDistalEdgePressure",
    "-ConfirmLeftWristLateralNoStrapOrCableInterference",
    "-ConfirmLeftHandOpeningFull",
    "-ConfirmLeftGripFormationClear",
    "-ConfirmLeftGloveRemovalNotTrapped",
    "-ConfirmLeftWristAssemblyRemovalNotBlocked",
    "-ConfirmLeftOuterCableRouteNoSnag",
    "-ConfirmLeftQuickReleaseReachableDuringMotion",
    "-ConfirmLeftCuffReturnsToSafePositionAfterMotion",
    "-ConfirmRightElbowFlexionNoCreaseCompression",
    "-ConfirmRightElbowExtensionNoCuffMigration",
    "-ConfirmRightWristFlexionNoDistalEdgePressure",
    "-ConfirmRightWristExtensionNoDistalEdgePressure",
    "-ConfirmRightWristLateralNoStrapOrCableInterference",
    "-ConfirmRightHandOpeningFull",
    "-ConfirmRightGripFormationClear",
    "-ConfirmRightGloveRemovalNotTrapped",
    "-ConfirmRightWristAssemblyRemovalNotBlocked",
    "-ConfirmRightOuterCableRouteNoSnag",
    "-ConfirmRightQuickReleaseReachableDuringMotion",
    "-ConfirmRightCuffReturnsToSafePositionAfterMotion",
    "-ConfirmLeftFingersWarmAfterMotion",
    "-ConfirmLeftNormalColorAfterMotion",
    "-ConfirmLeftGripStrengthUnchanged",
    "-ConfirmLeftNoNewPressureMarks",
    "-ConfirmRightFingersWarmAfterMotion",
    "-ConfirmRightNormalColorAfterMotion",
    "-ConfirmRightGripStrengthUnchanged",
    "-ConfirmRightNoNewPressureMarks",
    "-ConfirmNoLeftPain",
    "-ConfirmNoLeftTingling",
    "-ConfirmNoLeftNumbness",
    "-ConfirmNoLeftColdFingers",
    "-ConfirmNoLeftDiscoloration",
    "-ConfirmNoLeftHandWeakness",
    "-ConfirmNoLeftWristPain",
    "-ConfirmNoLeftSharpPressure",
    "-ConfirmNoLeftReducedFingerMotion",
    "-ConfirmNoLeftLossOfGripStrength",
    "-ConfirmNoRightPain",
    "-ConfirmNoRightTingling",
    "-ConfirmNoRightNumbness",
    "-ConfirmNoRightColdFingers",
    "-ConfirmNoRightDiscoloration",
    "-ConfirmNoRightHandWeakness",
    "-ConfirmNoRightWristPain",
    "-ConfirmNoRightSharpPressure",
    "-ConfirmNoRightReducedFingerMotion",
    "-ConfirmNoRightLossOfGripStrength",
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
        timeout_seconds=90,
    )


def _payload(stdout: str) -> dict[str, Any]:
    return json.loads(stdout)


def _write_ready_upstream(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    measurement_path, mockup_path, mannequin_path = _write_upstream_ready_records(tmp_path)
    static_fit_path = tmp_path / "ready-static-fit.json"
    static_fit_path.write_text(
        json.dumps(_ready_static_fit_payload(measurement_path, mockup_path, mannequin_path)),
        encoding="utf-8",
    )
    return measurement_path, mockup_path, mannequin_path, static_fit_path


def _movement_args(
    measurement_path: Path,
    mockup_path: Path,
    mannequin_path: Path,
    static_fit_path: Path,
    output_path: Path,
    *,
    pilot_id: str = "pilot-reference",
    test_duration_minutes: str = "5",
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
        "-EvidenceDate",
        date.today().isoformat(),
        "-Observer",
        "test-observer",
        "-PilotId",
        pilot_id,
        "-PrototypeRevision",
        "soft-cuff-rev-a",
        "-TestDurationMinutes",
        test_duration_minutes,
    ]
    args.extend(CONFIRM_ARGS if confirm_args is None else confirm_args)
    return args


def test_fr017_pilot_movement_initializer_creates_non_powered_record_without_clearance(
    tmp_path: Path,
) -> None:
    measurement_path, mockup_path, mannequin_path, static_fit_path = _write_ready_upstream(tmp_path)
    movement_path = tmp_path / "ready-movement.json"

    proc = _run_script(
        SCRIPT,
        *_movement_args(measurement_path, mockup_path, mannequin_path, static_fit_path, movement_path),
    )

    assert proc.returncode == 0, proc.stderr
    result = _payload(proc.stdout)
    assert result["kind"] == "francis.fr017.pilot_movement_record_initializer"
    assert result["status"] == "created_pilot_movement_record"
    assert result["wrote_file"] is True
    assert result["operator_supplied_pilot_movement_input_recorded"] is True
    assert result["upstream_static_fit_status"] == "ready_for_pilot_movement_test_planning"
    assert result["upstream_static_fit_ready"] is True
    assert result["pilot_movement_record_is_stage17_completion_evidence"] is False
    assert result["physical_validation_complete"] is False
    assert result["stage17_completion_claim_allowed"] is False
    assert result["quick_release_and_cable_snag_testing_cleared"] is False
    assert result["powered_or_frame_coupled_testing_cleared"] is False
    assert result["fr018_implementation_cleared"] is False
    assert result["symptom_observations_recorded"] == []
    assert "does not certify fit or pilot safety" in result["no_fake_validation_lock"]
    assert "fr017-pilot-movement-gate.ps1" in result["next_command"]

    record = json.loads(movement_path.read_text(encoding="utf-8-sig"))
    assert record["kind"] == "francis.fr017.pilot_movement_fit.v1"
    assert record["evidence"]["pilot_static_fit_record_path"] == str(static_fit_path.resolve())
    assert record["evidence"]["pilot_id"] == "pilot-reference"
    assert record["evidence"]["test_duration_minutes"] == 5
    assert record["preconditions"]["non_powered_only"] is True
    assert record["preconditions"]["pilot_static_fit_gate_passed"] is True
    assert record["sides"]["left"]["movement_checks"]["outer_cable_route_no_snag"] is True
    assert record["sides"]["right"]["post_movement"]["no_new_pressure_marks"] is True
    assert record["sides"]["right"]["symptoms"]["loss_of_grip_strength"] is False
    assert record["record_generation"]["operator_supplied_pilot_movement_input_recorded"] is True
    assert record["record_generation"]["physical_validation_complete"] is False
    assert record["record_generation"]["fr018_implementation_cleared"] is False

    gate = _run_script(
        MOVEMENT_GATE_SCRIPT,
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
    )
    assert gate.returncode == 0, gate.stderr
    gate_result = _payload(gate.stdout)
    assert gate_result["status"] == "ready_for_quick_release_and_cable_snag_test_planning"
    assert gate_result["movement_capture_ready_groups"] == 6
    assert gate_result["physical_validation_complete"] is False
    assert gate_result["stage17_completion_claim_allowed"] is False
    assert gate_result["quick_release_and_cable_snag_testing_cleared"] is False
    assert gate_result["fr018_implementation_cleared"] is False


def test_fr017_pilot_movement_initializer_refuses_upstream_static_fit_that_is_not_ready(
    tmp_path: Path,
) -> None:
    measurement_path, mockup_path, mannequin_path, static_fit_path = _write_ready_upstream(tmp_path)
    static_payload = json.loads(static_fit_path.read_text(encoding="utf-8"))
    static_payload["sides"]["left"]["symptoms"]["tingling"] = True
    static_fit_path.write_text(json.dumps(static_payload), encoding="utf-8")
    movement_path = tmp_path / "movement.json"

    proc = _run_script(
        SCRIPT,
        *_movement_args(measurement_path, mockup_path, mannequin_path, static_fit_path, movement_path),
    )

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "upstream_pilot_static_fit_not_ready"
    assert result["upstream_static_fit_status"] == "failed_requires_fit_redesign_or_medical_review"
    assert result["wrote_file"] is False
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_pilot_movement_initializer_refuses_template_target(tmp_path: Path) -> None:
    measurement_path, mockup_path, mannequin_path, static_fit_path = _write_ready_upstream(tmp_path)

    proc = _run_script(
        SCRIPT,
        *_movement_args(measurement_path, mockup_path, mannequin_path, static_fit_path, TEMPLATE_PATH),
    )

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "output_path_targets_template"
    assert result["wrote_file"] is False
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_pilot_movement_initializer_refuses_overwrite(tmp_path: Path) -> None:
    measurement_path, mockup_path, mannequin_path, static_fit_path = _write_ready_upstream(tmp_path)
    movement_path = tmp_path / "existing-movement.json"
    movement_path.write_text("do not replace", encoding="utf-8")

    proc = _run_script(
        SCRIPT,
        *_movement_args(measurement_path, mockup_path, mannequin_path, static_fit_path, movement_path),
    )

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "output_file_exists"
    assert result["wrote_file"] is False
    assert movement_path.read_text(encoding="utf-8") == "do not replace"
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_pilot_movement_initializer_rejects_mismatched_pilot_id(tmp_path: Path) -> None:
    measurement_path, mockup_path, mannequin_path, static_fit_path = _write_ready_upstream(tmp_path)
    movement_path = tmp_path / "mismatched-pilot-movement.json"

    proc = _run_script(
        SCRIPT,
        *_movement_args(
            measurement_path,
            mockup_path,
            mannequin_path,
            static_fit_path,
            movement_path,
            pilot_id="different-pilot",
        ),
    )

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "invalid_pilot_movement_record_input"
    assert result["wrote_file"] is False
    assert result["invalid_fields"] == ["evidence.pilot_id_must_match_static_fit_pilot_id"]
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_pilot_movement_initializer_rejects_missing_duration(tmp_path: Path) -> None:
    measurement_path, mockup_path, mannequin_path, static_fit_path = _write_ready_upstream(tmp_path)
    movement_path = tmp_path / "missing-duration-movement.json"

    proc = _run_script(
        SCRIPT,
        *_movement_args(
            measurement_path,
            mockup_path,
            mannequin_path,
            static_fit_path,
            movement_path,
            test_duration_minutes="0",
        ),
    )

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "invalid_pilot_movement_record_input"
    assert result["wrote_file"] is False
    assert result["invalid_fields"] == ["evidence.test_duration_minutes"]
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_pilot_movement_initializer_blocks_symptom_observed_without_writing(
    tmp_path: Path,
) -> None:
    measurement_path, mockup_path, mannequin_path, static_fit_path = _write_ready_upstream(tmp_path)
    movement_path = tmp_path / "symptom-movement.json"
    confirm_args = [arg for arg in CONFIRM_ARGS if arg != "-ConfirmNoRightNumbness"]
    confirm_args.append("-RightNumbnessObserved")

    proc = _run_script(
        SCRIPT,
        *_movement_args(
            measurement_path,
            mockup_path,
            mannequin_path,
            static_fit_path,
            movement_path,
            confirm_args=confirm_args,
        ),
    )

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "movement_symptom_recorded_requires_review"
    assert result["wrote_file"] is False
    assert result["symptom_observations_recorded"] == ["sides.right.symptoms.numbness"]
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False
