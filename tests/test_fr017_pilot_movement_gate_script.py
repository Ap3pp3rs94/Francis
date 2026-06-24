from __future__ import annotations

import json
import shutil
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest

from tests.powershell_script_runner import run_powershell_script
from tests.test_fr017_mockup_readiness_gate_script import _ready_measurement_payload
from tests.test_fr017_pilot_static_fit_gate_script import (
    _ready_static_fit_payload,
    _write_upstream_ready_records,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "fr017-pilot-movement-gate.ps1"


def _powershell() -> str:
    exe = shutil.which("pwsh") or shutil.which("powershell")
    if not exe:
        pytest.skip("PowerShell is not available")
    return exe


def _run_gate(*args: str):
    return run_powershell_script(
        _powershell(),
        SCRIPT,
        args,
        cwd=ROOT,
        timeout_seconds=50,
    )


def _payload(stdout: str) -> dict[str, Any]:
    return json.loads(stdout)


def _write_static_ready_records(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    measurement_path, mockup_path, mannequin_path = _write_upstream_ready_records(tmp_path)
    static_fit_path = tmp_path / "ready-static-fit.json"
    static_fit_path.write_text(
        json.dumps(_ready_static_fit_payload(measurement_path, mockup_path, mannequin_path)),
        encoding="utf-8",
    )
    return measurement_path, mockup_path, mannequin_path, static_fit_path


def _ready_movement_payload(static_fit_path: Path) -> dict[str, Any]:
    movement_checks = {
        "elbow_flexion_no_crease_compression": True,
        "elbow_extension_no_cuff_migration": True,
        "wrist_flexion_no_distal_edge_pressure": True,
        "wrist_extension_no_distal_edge_pressure": True,
        "wrist_lateral_no_strap_or_cable_interference": True,
        "hand_opening_full": True,
        "grip_formation_clear": True,
        "glove_removal_not_trapped": True,
        "wrist_assembly_removal_not_blocked": True,
        "outer_cable_route_no_snag": True,
        "quick_release_reachable_during_motion": True,
        "cuff_returns_to_safe_position_after_motion": True,
    }
    post_movement = {
        "fingers_warm_after_motion": True,
        "normal_color_after_motion": True,
        "grip_strength_unchanged": True,
        "no_new_pressure_marks": True,
    }
    symptoms = {
        "pain": False,
        "tingling": False,
        "numbness": False,
        "cold_fingers": False,
        "discoloration": False,
        "hand_weakness": False,
        "wrist_pain": False,
        "sharp_pressure": False,
        "reduced_finger_motion": False,
        "loss_of_grip_strength": False,
    }
    side_payload = {
        "movement_checks": movement_checks,
        "post_movement": post_movement,
        "symptoms": symptoms,
    }
    return {
        "kind": "francis.fr017.pilot_movement_fit.v1",
        "component": "FR-017 Forearm Cuffs",
        "evidence": {
            "date": "2026-06-23",
            "observer": "test-observer",
            "pilot_id": "pilot-reference",
            "prototype_revision": "soft-cuff-rev-a",
            "pilot_static_fit_record_path": str(static_fit_path),
            "test_duration_minutes": 5,
        },
        "preconditions": {
            "non_powered_only": True,
            "no_frame_or_power_coupling": True,
            "pilot_static_fit_gate_passed": True,
            "observer_present": True,
            "emergency_release_briefed": True,
            "stop_on_symptoms": True,
            "pilot_can_self_remove_or_abort": True,
        },
        "sides": {
            "left": {
                "movement_checks": dict(side_payload["movement_checks"]),
                "post_movement": dict(side_payload["post_movement"]),
                "symptoms": dict(side_payload["symptoms"]),
            },
            "right": {
                "movement_checks": dict(side_payload["movement_checks"]),
                "post_movement": dict(side_payload["post_movement"]),
                "symptoms": dict(side_payload["symptoms"]),
            },
        },
    }


def test_fr017_pilot_movement_gate_reports_default_templates_as_pending_upstream() -> None:
    proc = _run_gate("-Mode", "Status")

    assert proc.returncode == 0, proc.stderr
    payload = _payload(proc.stdout)
    assert payload["kind"] == "francis.fr017.pilot_movement_gate"
    assert payload["status"] == "pending_pilot_static_fit_gate"
    assert payload["upstream_static_fit_status"] == "pending_mannequin_interface_gate"
    assert payload["upstream_static_fit_gate_ready"] is False
    assert payload["physical_validation_complete"] is False
    assert payload["pilot_movement_test_complete"] is False
    assert payload["quick_release_and_cable_snag_test_planning_ready"] is False
    assert payload["fr018_implementation_cleared"] is False
    assert payload["read_only_contract"] is True
    assert payload["writes_repo"] is False
    assert payload["grants_mutation_authority"] is False


def test_fr017_pilot_movement_gate_requires_movement_record_after_static_ready(
    tmp_path: Path,
) -> None:
    measurement_path, mockup_path, mannequin_path, static_fit_path = _write_static_ready_records(tmp_path)

    proc = _run_gate(
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
    )

    assert proc.returncode == 0, proc.stderr
    payload = _payload(proc.stdout)
    assert payload["status"] == "pending_pilot_movement_test"
    assert payload["upstream_static_fit_status"] == "ready_for_pilot_movement_test_planning"
    assert payload["upstream_static_fit_gate_ready"] is True
    assert "evidence.date" in payload["missing_fields"]
    assert payload["pilot_movement_test_complete"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_pilot_movement_gate_treats_lowercase_or_padded_pending_text_as_missing(
    tmp_path: Path,
) -> None:
    measurement_path, mockup_path, mannequin_path, static_fit_path = _write_static_ready_records(tmp_path)
    movement_path = tmp_path / "placeholder-movement.json"
    movement_payload = _ready_movement_payload(static_fit_path)
    movement_payload["evidence"]["pilot_id"] = " pending "
    movement_payload["preconditions"]["pilot_static_fit_gate_passed"] = "pending"
    movement_payload["sides"]["left"]["movement_checks"]["hand_opening_full"] = " PENDING "
    movement_path.write_text(json.dumps(movement_payload), encoding="utf-8")

    proc = _run_gate(
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

    assert proc.returncode == 0, proc.stderr
    payload = _payload(proc.stdout)
    assert payload["status"] == "pending_pilot_movement_test"
    assert payload["invalid_fields"] == []
    assert "evidence.pilot_id" in payload["missing_fields"]
    assert "preconditions.pilot_static_fit_gate_passed" in payload["missing_fields"]
    assert "sides.left.movement_checks.hand_opening_full" in payload["missing_fields"]
    assert payload["physical_validation_complete"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_pilot_movement_gate_accepts_complete_movement_record(tmp_path: Path) -> None:
    measurement_path, mockup_path, mannequin_path, static_fit_path = _write_static_ready_records(tmp_path)
    movement_path = tmp_path / "ready-movement.json"
    movement_path.write_text(json.dumps(_ready_movement_payload(static_fit_path)), encoding="utf-8")

    proc = _run_gate(
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

    assert proc.returncode == 0, proc.stderr
    payload = _payload(proc.stdout)
    assert payload["status"] == "ready_for_quick_release_and_cable_snag_test_planning"
    assert payload["upstream_static_fit_status"] == "ready_for_pilot_movement_test_planning"
    assert payload["upstream_static_fit_gate_ready"] is True
    assert payload["movement_status"] == "ready_for_quick_release_and_cable_snag_test_planning"
    assert payload["missing_fields"] == []
    assert payload["invalid_fields"] == []
    assert payload["record_linkage_violations"] == []
    assert payload["record_chronology_violations"] == []
    assert payload["movement_redesign_triggers"] == []
    assert payload["symptom_blockers"] == []
    assert payload["physical_validation_complete"] is False
    assert payload["pilot_movement_test_complete"] is True
    assert payload["quick_release_and_cable_snag_test_planning_ready"] is True
    assert payload["powered_or_frame_coupled_testing_cleared"] is False
    assert payload["fr018_implementation_cleared"] is False
    assert "must resolve to the same static-fit record path" in payload["record_linkage_contract"]
    assert "must match evidence.pilot_id in the linked static-fit record" in payload["pilot_identity_linkage_contract"]
    assert "YYYY-MM-DD" in payload["evidence_date_contract"]
    assert "same as or later than the linked static-fit" in payload["evidence_chronology_contract"]
    assert "unquoted JSON number greater than 0" in payload["test_duration_value_contract"]
    assert "Use unquoted JSON boolean true only" in payload["boolean_value_contract"]


def test_fr017_pilot_movement_gate_rejects_malformed_evidence_date(tmp_path: Path) -> None:
    measurement_path, mockup_path, mannequin_path, static_fit_path = _write_static_ready_records(tmp_path)
    movement_path = tmp_path / "malformed-date-movement.json"
    payload = _ready_movement_payload(static_fit_path)
    payload["evidence"]["date"] = "06/23/2026"
    movement_path.write_text(json.dumps(payload), encoding="utf-8")

    proc = _run_gate(
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

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "failed_movement_record"
    assert result["invalid_fields"] == ["evidence.date"]
    assert result["pilot_movement_test_complete"] is False
    assert result["quick_release_and_cable_snag_test_planning_ready"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_pilot_movement_gate_rejects_future_evidence_date(tmp_path: Path) -> None:
    measurement_path, mockup_path, mannequin_path, static_fit_path = _write_static_ready_records(tmp_path)
    movement_path = tmp_path / "future-date-movement.json"
    payload = _ready_movement_payload(static_fit_path)
    payload["evidence"]["date"] = (date.today() + timedelta(days=1)).isoformat()
    movement_path.write_text(json.dumps(payload), encoding="utf-8")

    proc = _run_gate(
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

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "failed_movement_record"
    assert result["invalid_fields"] == ["evidence.date"]
    assert result["pilot_movement_test_complete"] is False
    assert result["quick_release_and_cable_snag_test_planning_ready"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_pilot_movement_gate_rejects_movement_date_before_static_fit_date(
    tmp_path: Path,
) -> None:
    measurement_path, mockup_path, mannequin_path, static_fit_path = _write_static_ready_records(tmp_path)
    movement_path = tmp_path / "backdated-movement.json"
    payload = _ready_movement_payload(static_fit_path)
    payload["evidence"]["date"] = "2026-06-22"
    movement_path.write_text(json.dumps(payload), encoding="utf-8")

    proc = _run_gate(
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

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "failed_movement_record"
    assert result["invalid_fields"] == []
    assert result["record_linkage_violations"] == []
    assert result["record_chronology_violations"] == ["evidence.date_before_static_fit.evidence.date"]
    assert result["movement_redesign_triggers"] == []
    assert result["symptom_blockers"] == []
    assert result["pilot_movement_test_complete"] is False
    assert result["quick_release_and_cable_snag_test_planning_ready"] is False
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_pilot_movement_gate_rejects_unlinked_static_fit_record_path(tmp_path: Path) -> None:
    measurement_path, mockup_path, mannequin_path, static_fit_path = _write_static_ready_records(tmp_path)
    unrelated_static_fit_path = tmp_path / "unrelated-static-fit.json"
    movement_path = tmp_path / "unlinked-movement.json"
    movement_path.write_text(json.dumps(_ready_movement_payload(unrelated_static_fit_path)), encoding="utf-8")

    proc = _run_gate(
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

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "failed_movement_record"
    assert result["invalid_fields"] == []
    assert result["record_linkage_violations"] == ["evidence.pilot_static_fit_record_path_must_match_static_fit_path"]
    assert result["pilot_movement_test_complete"] is False
    assert result["quick_release_and_cable_snag_test_planning_ready"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_pilot_movement_gate_rejects_mismatched_static_fit_pilot_id(tmp_path: Path) -> None:
    measurement_path, mockup_path, mannequin_path, static_fit_path = _write_static_ready_records(tmp_path)
    movement_path = tmp_path / "mismatched-pilot-movement.json"
    payload = _ready_movement_payload(static_fit_path)
    payload["evidence"]["pilot_id"] = "different-pilot"
    movement_path.write_text(json.dumps(payload), encoding="utf-8")

    proc = _run_gate(
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

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "failed_movement_record"
    assert result["invalid_fields"] == []
    assert result["record_linkage_violations"] == ["evidence.pilot_id_must_match_static_fit_pilot_id"]
    assert result["pilot_movement_test_complete"] is False
    assert result["quick_release_and_cable_snag_test_planning_ready"] is False
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_pilot_movement_gate_blocks_measurement_rejected_by_intake(tmp_path: Path) -> None:
    measurement_path = tmp_path / "quoted-measurements.json"
    payload = _ready_measurement_payload()
    payload["sides"]["left"]["forearm_length_elbow_crease_to_wrist_crease"] = "258"
    measurement_path.write_text(json.dumps(payload), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-MeasurementPath", str(measurement_path))

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "failed_upstream_static_fit_gate"
    assert result["upstream_static_fit_status"] == "failed_upstream_mannequin_gate"
    assert result["upstream_static_fit_gate_ready"] is False
    assert result["upstream_mannequin_status"] == "failed_upstream_mockup_gate"
    assert result["upstream_mockup_status"] == "invalid_measurement_record"
    assert result["upstream_measurement_intake_status"] == "invalid_measurement_record"
    assert result["upstream_measurement_invalid_fields"] == ["sides.left.forearm_length_elbow_crease_to_wrist_crease"]
    assert result["pilot_movement_test_complete"] is False
    assert result["quick_release_and_cable_snag_test_planning_ready"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_pilot_movement_gate_blocks_symptom_positive_movement(tmp_path: Path) -> None:
    measurement_path, mockup_path, mannequin_path, static_fit_path = _write_static_ready_records(tmp_path)
    movement_path = tmp_path / "symptom-movement.json"
    payload = _ready_movement_payload(static_fit_path)
    payload["sides"]["right"]["symptoms"]["numbness"] = True
    movement_path.write_text(json.dumps(payload), encoding="utf-8")

    proc = _run_gate(
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

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "failed_requires_movement_redesign_or_medical_review"
    assert result["symptom_blockers"] == ["sides.right.symptoms.numbness"]
    assert result["pilot_movement_test_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_pilot_movement_gate_symptom_overrides_missing_fields(tmp_path: Path) -> None:
    measurement_path, mockup_path, mannequin_path, static_fit_path = _write_static_ready_records(tmp_path)
    movement_path = tmp_path / "symptom-and-missing-movement.json"
    payload = _ready_movement_payload(static_fit_path)
    del payload["evidence"]["observer"]
    payload["sides"]["left"]["symptoms"]["tingling"] = True
    movement_path.write_text(json.dumps(payload), encoding="utf-8")

    proc = _run_gate(
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

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "failed_requires_movement_redesign_or_medical_review"
    assert result["missing_fields"] == ["evidence.observer"]
    assert result["symptom_blockers"] == ["sides.left.symptoms.tingling"]
    assert result["pilot_movement_test_complete"] is False
    assert result["quick_release_and_cable_snag_test_planning_ready"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_pilot_movement_gate_blocks_cable_snag_failure(tmp_path: Path) -> None:
    measurement_path, mockup_path, mannequin_path, static_fit_path = _write_static_ready_records(tmp_path)
    movement_path = tmp_path / "snag-failed-movement.json"
    payload = _ready_movement_payload(static_fit_path)
    payload["sides"]["left"]["movement_checks"]["outer_cable_route_no_snag"] = False
    movement_path.write_text(json.dumps(payload), encoding="utf-8")

    proc = _run_gate(
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

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "failed_requires_movement_redesign_or_medical_review"
    assert result["movement_redesign_triggers"] == ["sides.left.movement_checks.outer_cable_route_no_snag"]
    assert result["pilot_movement_test_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_pilot_movement_gate_rejects_quoted_boolean_text(tmp_path: Path) -> None:
    measurement_path, mockup_path, mannequin_path, static_fit_path = _write_static_ready_records(tmp_path)
    movement_path = tmp_path / "quoted-boolean-movement.json"
    payload = _ready_movement_payload(static_fit_path)
    payload["preconditions"]["observer_present"] = "true"
    movement_path.write_text(json.dumps(payload), encoding="utf-8")

    proc = _run_gate(
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

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "failed_movement_record"
    assert result["invalid_fields"] == ["preconditions.observer_present"]
    assert result["movement_redesign_triggers"] == []
    assert result["fr018_implementation_cleared"] is False


def test_fr017_pilot_movement_gate_rejects_quoted_test_duration_text(tmp_path: Path) -> None:
    measurement_path, mockup_path, mannequin_path, static_fit_path = _write_static_ready_records(tmp_path)
    movement_path = tmp_path / "quoted-duration-movement.json"
    payload = _ready_movement_payload(static_fit_path)
    payload["evidence"]["test_duration_minutes"] = "5"
    movement_path.write_text(json.dumps(payload), encoding="utf-8")

    proc = _run_gate(
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

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "failed_movement_record"
    assert result["missing_fields"] == []
    assert result["invalid_fields"] == ["evidence.test_duration_minutes"]
    assert result["pilot_movement_test_complete"] is False
    assert result["fr018_implementation_cleared"] is False
