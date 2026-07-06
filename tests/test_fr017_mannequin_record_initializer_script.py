from __future__ import annotations

import json
import shutil
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from tests.powershell_script_runner import run_powershell_script
from tests.test_fr017_mockup_readiness_gate_script import (
    _ready_measurement_payload,
    _ready_mockup_payload,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "fr017-new-mannequin-interface-record.ps1"
MANNEQUIN_GATE_SCRIPT = ROOT / "scripts" / "fr017-mannequin-interface-gate.ps1"
TEMPLATE_PATH = ROOT / "FR-017_Stage17_Package" / "FR-017-MANNEQUIN-INTERFACE-INPUT-TEMPLATE.json"


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


def _write_ready_upstream(tmp_path: Path) -> tuple[Path, Path]:
    measurement_path = tmp_path / "ready-measurements.json"
    mockup_path = tmp_path / "ready-mockup.json"
    measurement_path.write_text(json.dumps(_ready_measurement_payload()), encoding="utf-8")
    mockup_path.write_text(json.dumps(_ready_mockup_payload(measurement_path)), encoding="utf-8")
    return measurement_path, mockup_path


def _mannequin_args(
    measurement_path: Path,
    mockup_path: Path,
    output_path: Path,
    *,
    subject: str = "test-arm-form-rev-a",
    include_no_release_hidden: bool = True,
    release_hidden: bool = False,
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
        "-EvidenceDate",
        date.today().isoformat(),
        "-Observer",
        "test-observer",
        "-MannequinOrArmFormId",
        subject,
        "-FutureInterfaceMockGeometryRevision",
        "ghosted-interface-rev-a",
        "-CableSleeveMockId",
        "outer-sleeve-rev-a",
        "-LeftCuffRevision",
        "left-soft-cuff-rev-a",
        "-RightCuffRevision",
        "right-soft-cuff-rev-a",
        "-ConfirmNonPoweredOnly",
        "-ConfirmAllInterfaceMocksInstalled",
        "-ConfirmAllInterfaceClearancesPassed",
        "-InterfaceNotes",
        "clearance verified against non-powered mock geometry",
        "-ConfirmFr163OuterRouteOnly",
        "-ConfirmFr069NoPressureOrPalmCrossing",
        "-ConfirmFr070NoPoweredAnchoring",
        "-ConfirmFr145NoRaisedHardSpot",
        "-ConfirmFr149NoPressureZonePlacement",
        "-ConfirmLeftReleaseVisibleAndReachable",
        "-ConfirmRightReleaseVisibleAndReachable",
        "-ConfirmArmorDoesNotHideRelease",
        "-ConfirmGloveAndWristRemovalPathsOpen",
        "-ConfirmNoSnagDetected",
        "-ConfirmNoCompressionDetected",
        "-ConfirmNoWristPathBlocked",
        "-ConfirmNoGlovePathBlocked",
        "-ConfirmNoCableInnerElbowCrossing",
        "-ConfirmNoCableWristBoneCrossing",
        "-ConfirmNoCablePalmOrGripCrossing",
    ]
    if include_no_release_hidden:
        args.insert(args.index("-ConfirmNoWristPathBlocked"), "-ConfirmNoReleaseHidden")
    if release_hidden:
        args.append("-ReleaseHidden")
    return args


def test_fr017_mannequin_initializer_creates_non_powered_interface_record_without_clearance(
    tmp_path: Path,
) -> None:
    measurement_path, mockup_path = _write_ready_upstream(tmp_path)
    mannequin_path = tmp_path / "ready-mannequin.json"

    proc = _run_script(SCRIPT, *_mannequin_args(measurement_path, mockup_path, mannequin_path))

    assert proc.returncode == 0, proc.stderr
    result = _payload(proc.stdout)
    assert result["kind"] == "francis.fr017.mannequin_interface_record_initializer"
    assert result["status"] == "created_mannequin_interface_record"
    assert result["wrote_file"] is True
    assert result["operator_supplied_mannequin_interface_input_recorded"] is True
    assert result["upstream_mockup_status"] == "ready_for_mannequin_interface_test"
    assert result["upstream_mockup_ready"] is True
    assert result["mannequin_interface_record_is_physical_validation_evidence"] is False
    assert result["physical_validation_complete"] is False
    assert result["stage17_completion_claim_allowed"] is False
    assert result["pilot_testing_cleared"] is False
    assert result["powered_or_frame_coupled_testing_cleared"] is False
    assert result["fr018_implementation_cleared"] is False
    assert result["fail_observations_recorded"] == []
    assert "does not mark physical validation complete" in result["no_fake_validation_lock"]
    assert "fr017-mannequin-interface-gate.ps1" in result["next_command"]

    record = json.loads(mannequin_path.read_text(encoding="utf-8-sig"))
    assert record["kind"] == "francis.fr017.mannequin_interface_test.v1"
    assert record["evidence"]["mockup_readiness_record_path"] == str(mockup_path.resolve())
    assert record["evidence"]["mannequin_or_arm_form_id"] == "test-arm-form-rev-a"
    assert record["test_article"]["non_powered_only"] is True
    assert record["interfaces"]["fr184_forearm_armor"]["clearance_passed"] is True
    assert record["cable_sensor_checks"]["fr163_outer_route_only"] is True
    assert record["release_checks"]["armor_does_not_hide_release"] is True
    assert record["fail_observations"]["release_hidden"] is False
    assert record["record_generation"]["mannequin_interface_record_is_physical_validation_evidence"] is False
    assert record["record_generation"]["fr018_implementation_cleared"] is False

    gate = _run_script(
        MANNEQUIN_GATE_SCRIPT,
        "-Mode",
        "Status",
        "-MeasurementPath",
        str(measurement_path),
        "-MockupPath",
        str(mockup_path),
        "-MannequinPath",
        str(mannequin_path),
    )
    assert gate.returncode == 0, gate.stderr
    gate_result = _payload(gate.stdout)
    assert gate_result["status"] == "ready_for_pilot_static_fit_planning"
    assert gate_result["mannequin_capture_ready_groups"] == 5
    assert gate_result["physical_validation_complete"] is False
    assert gate_result["pilot_testing_cleared"] is False
    assert gate_result["fr018_implementation_cleared"] is False


def test_fr017_mannequin_initializer_refuses_upstream_mockup_that_is_not_ready(
    tmp_path: Path,
) -> None:
    measurement_path, mockup_path = _write_ready_upstream(tmp_path)
    mockup_payload = json.loads(mockup_path.read_text(encoding="utf-8"))
    mockup_payload["constraints"]["no_wrist_bone_pressure"] = False
    mockup_path.write_text(json.dumps(mockup_payload), encoding="utf-8")
    mannequin_path = tmp_path / "mannequin.json"

    proc = _run_script(SCRIPT, *_mannequin_args(measurement_path, mockup_path, mannequin_path))

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "upstream_mockup_readiness_not_ready"
    assert result["upstream_mockup_status"] == "failed_requires_mockup_redesign"
    assert result["wrote_file"] is False
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_mannequin_initializer_refuses_template_target(tmp_path: Path) -> None:
    measurement_path, mockup_path = _write_ready_upstream(tmp_path)

    proc = _run_script(SCRIPT, *_mannequin_args(measurement_path, mockup_path, TEMPLATE_PATH))

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "output_path_targets_template"
    assert result["wrote_file"] is False
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_mannequin_initializer_refuses_overwrite(tmp_path: Path) -> None:
    measurement_path, mockup_path = _write_ready_upstream(tmp_path)
    mannequin_path = tmp_path / "existing-mannequin.json"
    mannequin_path.write_text("do not replace", encoding="utf-8")

    proc = _run_script(SCRIPT, *_mannequin_args(measurement_path, mockup_path, mannequin_path))

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "output_file_exists"
    assert result["wrote_file"] is False
    assert mannequin_path.read_text(encoding="utf-8") == "do not replace"
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_mannequin_initializer_rejects_pilot_subject(tmp_path: Path) -> None:
    measurement_path, mockup_path = _write_ready_upstream(tmp_path)
    mannequin_path = tmp_path / "pilot-subject.json"

    proc = _run_script(
        SCRIPT,
        *_mannequin_args(measurement_path, mockup_path, mannequin_path, subject="pilot-left-arm"),
    )

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "invalid_mannequin_interface_record_input"
    assert result["wrote_file"] is False
    assert result["invalid_fields"] == ["evidence.mannequin_or_arm_form_id"]
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_mannequin_initializer_blocks_fail_observation_without_writing(
    tmp_path: Path,
) -> None:
    measurement_path, mockup_path = _write_ready_upstream(tmp_path)
    mannequin_path = tmp_path / "failed-mannequin.json"

    proc = _run_script(
        SCRIPT,
        *_mannequin_args(
            measurement_path,
            mockup_path,
            mannequin_path,
            include_no_release_hidden=False,
            release_hidden=True,
        ),
    )

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "mannequin_fail_observation_recorded_requires_review"
    assert result["wrote_file"] is False
    assert result["fail_observations_recorded"] == ["fail_observations.release_hidden"]
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False
