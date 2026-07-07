from __future__ import annotations

import json
import shutil
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from tests.powershell_script_runner import run_powershell_script
from tests.test_fr017_quick_release_cable_snag_gate_script import _write_movement_ready_records


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "fr017-new-release-cable-record.ps1"
RELEASE_CABLE_GATE_SCRIPT = ROOT / "scripts" / "fr017-quick-release-cable-snag-gate.ps1"
TEMPLATE_PATH = ROOT / "FR-017_Stage17_Package" / "FR-017-QUICK-RELEASE-CABLE-SNAG-INPUT-TEMPLATE.json"

CONFIRM_ARGS = [
    "-ConfirmNonPoweredOnly",
    "-ConfirmNoFrameOrPowerCoupling",
    "-ConfirmPilotMovementGatePassed",
    "-ConfirmObserverPresent",
    "-ConfirmEmergencyReleaseBriefed",
    "-ConfirmStopOnSymptoms",
    "-ConfirmPilotCanSelfRemoveOrAbort",
    "-ConfirmLeftBareCuffReleaseVisibleTactileReachable",
    "-ConfirmLeftGloveBaseMockupReleaseVisibleTactileReachable",
    "-ConfirmLeftWristAssemblyMockupReleaseVisibleTactileReachable",
    "-ConfirmLeftForearmFrameMockupReleaseVisibleTactileReachable",
    "-ConfirmLeftForearmArmorMockupReleaseVisibleTactileReachable",
    "-ConfirmLeftPopulatedCableSleeveReleaseVisibleTactileReachable",
    "-ConfirmLeftPostMovementReleaseVisibleTactileReachable",
    "-ConfirmLeftOppositeHandReleaseReachable",
    "-ConfirmLeftSameSideReachRecorded",
    "-ConfirmLeftReleaseLoosensUpperStrap",
    "-ConfirmLeftReleaseLoosensLowerStrap",
    "-ConfirmLeftCuffRemovableWithoutTools",
    "-ConfirmLeftNoPainfulWristPostureRequired",
    "-ConfirmLeftGloveAndWristPathsNotTrapped",
    "-ConfirmRightBareCuffReleaseVisibleTactileReachable",
    "-ConfirmRightGloveBaseMockupReleaseVisibleTactileReachable",
    "-ConfirmRightWristAssemblyMockupReleaseVisibleTactileReachable",
    "-ConfirmRightForearmFrameMockupReleaseVisibleTactileReachable",
    "-ConfirmRightForearmArmorMockupReleaseVisibleTactileReachable",
    "-ConfirmRightPopulatedCableSleeveReleaseVisibleTactileReachable",
    "-ConfirmRightPostMovementReleaseVisibleTactileReachable",
    "-ConfirmRightOppositeHandReleaseReachable",
    "-ConfirmRightSameSideReachRecorded",
    "-ConfirmRightReleaseLoosensUpperStrap",
    "-ConfirmRightReleaseLoosensLowerStrap",
    "-ConfirmRightCuffRemovableWithoutTools",
    "-ConfirmRightNoPainfulWristPostureRequired",
    "-ConfirmRightGloveAndWristPathsNotTrapped",
    "-ConfirmLeftOuterForearmRoutePreserved",
    "-ConfirmLeftNoInnerElbowCrossing",
    "-ConfirmLeftNoWristBoneCrossing",
    "-ConfirmLeftNoPalmOrGripCrossing",
    "-ConfirmLeftNoReleaseHandleObstruction",
    "-ConfirmLeftNoSnagDuringRelease",
    "-ConfirmLeftNoSnagAfterElbowWristMotion",
    "-ConfirmLeftCableNotTrappedAfterRelease",
    "-ConfirmRightOuterForearmRoutePreserved",
    "-ConfirmRightNoInnerElbowCrossing",
    "-ConfirmRightNoWristBoneCrossing",
    "-ConfirmRightNoPalmOrGripCrossing",
    "-ConfirmRightNoReleaseHandleObstruction",
    "-ConfirmRightNoSnagDuringRelease",
    "-ConfirmRightNoSnagAfterElbowWristMotion",
    "-ConfirmRightCableNotTrappedAfterRelease",
    "-ConfirmNoLeftReleaseHidden",
    "-ConfirmNoLeftReleaseNotFoundByTouch",
    "-ConfirmNoLeftReleaseBlockedByGloveOrArmor",
    "-ConfirmNoLeftReleaseFailsToLoosen",
    "-ConfirmNoLeftCuffNotRemovableWithoutTools",
    "-ConfirmNoLeftPainfulWristPostureRequired",
    "-ConfirmNoLeftCableTrappedAfterRelease",
    "-ConfirmNoLeftCableCrossedNoGoZone",
    "-ConfirmNoRightReleaseHidden",
    "-ConfirmNoRightReleaseNotFoundByTouch",
    "-ConfirmNoRightReleaseBlockedByGloveOrArmor",
    "-ConfirmNoRightReleaseFailsToLoosen",
    "-ConfirmNoRightCuffNotRemovableWithoutTools",
    "-ConfirmNoRightPainfulWristPostureRequired",
    "-ConfirmNoRightCableTrappedAfterRelease",
    "-ConfirmNoRightCableCrossedNoGoZone",
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
        timeout_seconds=100,
    )


def _payload(stdout: str) -> dict[str, Any]:
    return json.loads(stdout)


def _release_cable_args(
    measurement_path: Path,
    mockup_path: Path,
    mannequin_path: Path,
    static_fit_path: Path,
    movement_path: Path,
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
        "-MovementPath",
        str(movement_path),
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


def test_fr017_release_cable_initializer_status_preflights_without_writing(
    tmp_path: Path,
) -> None:
    measurement_path, mockup_path, mannequin_path, static_fit_path, movement_path = _write_movement_ready_records(
        tmp_path
    )
    release_cable_path = tmp_path / "candidate-release-cable.json"

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
        "-OutputPath",
        str(release_cable_path),
    )

    assert proc.returncode == 0, proc.stderr
    result = _payload(proc.stdout)
    assert result["kind"] == "francis.fr017.release_cable_record_initializer"
    assert result["mode"] == "Status"
    assert result["status"] == "release_cable_record_initializer_status"
    assert result["template_exists"] is True
    assert result["template_parse_ok"] is True
    assert result["output_path_required_for_create"] is False
    assert result["measurement_path_required_for_create"] is False
    assert result["mockup_path_required_for_create"] is False
    assert result["mannequin_path_required_for_create"] is False
    assert result["static_fit_path_required_for_create"] is False
    assert result["movement_path_required_for_create"] is False
    assert result["output_path_targets_template"] is False
    assert result["output_parent_exists"] is True
    assert result["candidate_output_path_ready"] is True
    assert result["measurement_file_exists"] is True
    assert result["mockup_file_exists"] is True
    assert result["mannequin_file_exists"] is True
    assert result["static_fit_file_exists"] is True
    assert result["movement_file_exists"] is True
    assert result["upstream_pilot_movement_status"] == "ready_for_quick_release_and_cable_snag_test_planning"
    assert result["upstream_pilot_movement_ready"] is True
    assert result["wrote_file"] is False
    assert result["output_exists"] is False
    assert result["read_only_contract"] is True
    assert result["writes_repo"] is False
    assert result["writes_data"] is False
    assert result["operator_supplied_release_cable_input_recorded"] is False
    assert result["release_cable_record_is_stage17_completion_evidence"] is False
    assert result["physical_validation_complete"] is False
    assert result["stage17_completion_claim_allowed"] is False
    assert result["professional_engineering_review_cleared"] is False
    assert result["powered_or_frame_coupled_testing_cleared"] is False
    assert result["fr018_implementation_cleared"] is False
    assert "fr017-new-release-cable-record.ps1 -Mode Create" in result["create_command_template"]
    assert "fr017-quick-release-cable-snag-gate.ps1 -Mode Status" in result["release_cable_status_command_template"]
    assert result["next_command"] == result["create_command_template"]
    assert not release_cable_path.exists()


def test_fr017_release_cable_initializer_creates_non_powered_record_without_clearance(
    tmp_path: Path,
) -> None:
    measurement_path, mockup_path, mannequin_path, static_fit_path, movement_path = _write_movement_ready_records(
        tmp_path
    )
    release_cable_path = tmp_path / "ready-release-cable.json"

    proc = _run_script(
        SCRIPT,
        *_release_cable_args(
            measurement_path,
            mockup_path,
            mannequin_path,
            static_fit_path,
            movement_path,
            release_cable_path,
        ),
    )

    assert proc.returncode == 0, proc.stderr
    result = _payload(proc.stdout)
    assert result["kind"] == "francis.fr017.release_cable_record_initializer"
    assert result["status"] == "created_quick_release_cable_snag_record"
    assert result["wrote_file"] is True
    assert result["operator_supplied_release_cable_input_recorded"] is True
    assert result["upstream_pilot_movement_status"] == "ready_for_quick_release_and_cable_snag_test_planning"
    assert result["upstream_pilot_movement_ready"] is True
    assert result["release_cable_record_is_stage17_completion_evidence"] is False
    assert result["physical_validation_complete"] is False
    assert result["stage17_completion_claim_allowed"] is False
    assert result["professional_engineering_review_cleared"] is False
    assert result["powered_or_frame_coupled_testing_cleared"] is False
    assert result["fr018_implementation_cleared"] is False
    assert result["fail_observations_recorded"] == []
    assert "does not certify emergency release safety" in result["no_fake_validation_lock"]
    assert "fr017-quick-release-cable-snag-gate.ps1" in result["next_command"]

    record = json.loads(release_cable_path.read_text(encoding="utf-8-sig"))
    assert record["kind"] == "francis.fr017.quick_release_cable_snag.v1"
    assert record["evidence"]["pilot_movement_record_path"] == str(movement_path.resolve())
    assert record["evidence"]["pilot_id"] == "pilot-reference"
    assert record["evidence"]["test_duration_minutes"] == 5
    assert record["preconditions"]["non_powered_only"] is True
    assert record["preconditions"]["pilot_movement_gate_passed"] is True
    assert record["sides"]["left"]["release_checks"]["opposite_hand_release_reachable"] is True
    assert record["sides"]["right"]["cable_sleeve_checks"]["no_wrist_bone_crossing"] is True
    assert record["sides"]["right"]["fail_observations"]["cable_crossed_no_go_zone"] is False
    assert record["record_generation"]["operator_supplied_release_cable_input_recorded"] is True
    assert record["record_generation"]["physical_validation_complete"] is False
    assert record["record_generation"]["fr018_implementation_cleared"] is False

    gate = _run_script(
        RELEASE_CABLE_GATE_SCRIPT,
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
    )
    assert gate.returncode == 0, gate.stderr
    gate_result = _payload(gate.stdout)
    assert gate_result["status"] == "ready_for_engineering_review_or_final_physical_gate_audit"
    assert gate_result["release_cable_capture_ready_groups"] == 6
    assert gate_result["physical_validation_complete"] is False
    assert gate_result["stage17_completion_claim_allowed"] is False
    assert gate_result["professional_engineering_review_cleared"] is False
    assert gate_result["fr018_implementation_cleared"] is False


def test_fr017_release_cable_initializer_refuses_upstream_movement_that_is_not_ready(
    tmp_path: Path,
) -> None:
    measurement_path, mockup_path, mannequin_path, static_fit_path, movement_path = _write_movement_ready_records(
        tmp_path
    )
    movement_payload = json.loads(movement_path.read_text(encoding="utf-8"))
    movement_payload["sides"]["right"]["symptoms"]["numbness"] = True
    movement_path.write_text(json.dumps(movement_payload), encoding="utf-8")
    release_cable_path = tmp_path / "release-cable.json"

    proc = _run_script(
        SCRIPT,
        *_release_cable_args(
            measurement_path,
            mockup_path,
            mannequin_path,
            static_fit_path,
            movement_path,
            release_cable_path,
        ),
    )

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "upstream_pilot_movement_not_ready"
    assert result["upstream_pilot_movement_status"] == "failed_requires_movement_redesign_or_medical_review"
    assert result["wrote_file"] is False
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_release_cable_initializer_refuses_template_target(tmp_path: Path) -> None:
    measurement_path, mockup_path, mannequin_path, static_fit_path, movement_path = _write_movement_ready_records(
        tmp_path
    )

    proc = _run_script(
        SCRIPT,
        *_release_cable_args(
            measurement_path,
            mockup_path,
            mannequin_path,
            static_fit_path,
            movement_path,
            TEMPLATE_PATH,
        ),
    )

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "output_path_targets_template"
    assert result["wrote_file"] is False
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_release_cable_initializer_refuses_overwrite(tmp_path: Path) -> None:
    measurement_path, mockup_path, mannequin_path, static_fit_path, movement_path = _write_movement_ready_records(
        tmp_path
    )
    release_cable_path = tmp_path / "existing-release-cable.json"
    release_cable_path.write_text("do not replace", encoding="utf-8")

    proc = _run_script(
        SCRIPT,
        *_release_cable_args(
            measurement_path,
            mockup_path,
            mannequin_path,
            static_fit_path,
            movement_path,
            release_cable_path,
        ),
    )

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "output_file_exists"
    assert result["wrote_file"] is False
    assert release_cable_path.read_text(encoding="utf-8") == "do not replace"
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_release_cable_initializer_rejects_mismatched_pilot_id(tmp_path: Path) -> None:
    measurement_path, mockup_path, mannequin_path, static_fit_path, movement_path = _write_movement_ready_records(
        tmp_path
    )
    release_cable_path = tmp_path / "mismatched-pilot-release-cable.json"

    proc = _run_script(
        SCRIPT,
        *_release_cable_args(
            measurement_path,
            mockup_path,
            mannequin_path,
            static_fit_path,
            movement_path,
            release_cable_path,
            pilot_id="different-pilot",
        ),
    )

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "invalid_release_cable_record_input"
    assert result["wrote_file"] is False
    assert result["invalid_fields"] == ["evidence.pilot_id_must_match_movement_pilot_id"]
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_release_cable_initializer_rejects_missing_duration(tmp_path: Path) -> None:
    measurement_path, mockup_path, mannequin_path, static_fit_path, movement_path = _write_movement_ready_records(
        tmp_path
    )
    release_cable_path = tmp_path / "missing-duration-release-cable.json"

    proc = _run_script(
        SCRIPT,
        *_release_cable_args(
            measurement_path,
            mockup_path,
            mannequin_path,
            static_fit_path,
            movement_path,
            release_cable_path,
            test_duration_minutes="0",
        ),
    )

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "invalid_release_cable_record_input"
    assert result["wrote_file"] is False
    assert result["invalid_fields"] == ["evidence.test_duration_minutes"]
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_release_cable_initializer_blocks_fail_observation_without_writing(
    tmp_path: Path,
) -> None:
    measurement_path, mockup_path, mannequin_path, static_fit_path, movement_path = _write_movement_ready_records(
        tmp_path
    )
    release_cable_path = tmp_path / "hidden-release.json"
    confirm_args = [arg for arg in CONFIRM_ARGS if arg != "-ConfirmNoLeftReleaseHidden"]
    confirm_args.append("-LeftReleaseHiddenObserved")

    proc = _run_script(
        SCRIPT,
        *_release_cable_args(
            measurement_path,
            mockup_path,
            mannequin_path,
            static_fit_path,
            movement_path,
            release_cable_path,
            confirm_args=confirm_args,
        ),
    )

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "release_cable_fail_observation_recorded_requires_review"
    assert result["wrote_file"] is False
    assert result["fail_observations_recorded"] == ["sides.left.fail_observations.release_hidden"]
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False
