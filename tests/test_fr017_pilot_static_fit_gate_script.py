from __future__ import annotations

import json
import shutil
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest

from tests.powershell_script_runner import run_powershell_script
from tests.test_fr017_mannequin_interface_gate_script import _ready_mannequin_payload
from tests.test_fr017_mockup_readiness_gate_script import (
    _ready_measurement_payload,
    _ready_mockup_payload,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "fr017-pilot-static-fit-gate.ps1"


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
        timeout_seconds=40,
    )


def _payload(stdout: str) -> dict[str, Any]:
    return json.loads(stdout)


def _capture_status_by_id(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {step["id"]: step for step in payload["static_fit_capture_plan_status"]}


def _write_upstream_ready_records(tmp_path: Path) -> tuple[Path, Path, Path]:
    measurement_path = tmp_path / "ready-measurements.json"
    mockup_path = tmp_path / "ready-mockup.json"
    mannequin_path = tmp_path / "ready-mannequin.json"
    measurement_path.write_text(json.dumps(_ready_measurement_payload()), encoding="utf-8")
    mockup_path.write_text(json.dumps(_ready_mockup_payload(measurement_path)), encoding="utf-8")
    mannequin_path.write_text(json.dumps(_ready_mannequin_payload(mockup_path)), encoding="utf-8")
    return measurement_path, mockup_path, mannequin_path


def _ready_static_fit_payload(
    measurement_path: Path,
    mockup_path: Path,
    mannequin_path: Path,
) -> dict[str, Any]:
    baseline = {
        "fingers_warm_before_donning": True,
        "normal_color_before_donning": True,
        "baseline_grip_present": True,
    }
    static_checks = {
        "cuff_below_elbow_crease": True,
        "lower_cuff_above_wrist_bones": True,
        "upper_strap_broad_non_compressive": True,
        "lower_strap_broad_non_compressive": True,
        "inner_forearm_clear": True,
        "bone_relief_present": True,
        "quick_release_visible_tactile_reachable": True,
        "cuff_stable_without_migration": True,
        "glove_removal_path_open": True,
        "wrist_assembly_removal_path_open": True,
        "cable_route_static_no_snag": True,
    }
    post_doff = {
        "fingers_warm_after_doffing": True,
        "normal_color_after_doffing": True,
        "grip_strength_unchanged": True,
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
        "baseline": baseline,
        "static_checks": static_checks,
        "post_doff": post_doff,
        "symptoms": symptoms,
    }
    return {
        "kind": "francis.fr017.pilot_static_fit.v1",
        "component": "FR-017 Forearm Cuffs",
        "evidence": {
            "date": "2026-06-23",
            "observer": "test-observer",
            "pilot_id": "pilot-reference",
            "prototype_revision": "soft-cuff-rev-a",
            "measurement_record_path": str(measurement_path),
            "mockup_build_record_path": str(mockup_path),
            "mannequin_interface_record_path": str(mannequin_path),
            "test_duration_minutes": 5,
        },
        "preconditions": {
            "non_powered_only": True,
            "no_frame_or_power_coupling": True,
            "observer_present": True,
            "emergency_release_briefed": True,
            "stop_on_symptoms": True,
            "pilot_can_self_remove_or_abort": True,
        },
        "sides": {
            "left": {
                "baseline": dict(side_payload["baseline"]),
                "static_checks": dict(side_payload["static_checks"]),
                "post_doff": dict(side_payload["post_doff"]),
                "symptoms": dict(side_payload["symptoms"]),
            },
            "right": {
                "baseline": dict(side_payload["baseline"]),
                "static_checks": dict(side_payload["static_checks"]),
                "post_doff": dict(side_payload["post_doff"]),
                "symptoms": dict(side_payload["symptoms"]),
            },
        },
    }


def test_fr017_pilot_static_gate_reports_default_templates_as_pending_upstream() -> None:
    proc = _run_gate("-Mode", "Status")

    assert proc.returncode == 0, proc.stderr
    payload = _payload(proc.stdout)
    assert payload["kind"] == "francis.fr017.pilot_static_fit_gate"
    assert payload["status"] == "pending_mannequin_interface_gate"
    assert payload["upstream_mannequin_status"] == "pending_mockup_readiness"
    assert payload["upstream_mannequin_gate_ready"] is False
    assert payload["physical_validation_complete"] is False
    assert payload["pilot_static_fit_test_complete"] is False
    assert payload["pilot_movement_test_planning_ready"] is False
    assert payload["pilot_movement_testing_cleared"] is False
    assert payload["fr018_implementation_cleared"] is False
    assert payload["read_only_contract"] is True
    assert payload["writes_repo"] is False
    assert payload["grants_mutation_authority"] is False
    assert payload["static_fit_capture_plan_not_completion_evidence"] is True
    assert "not physical validation evidence" in payload["static_fit_capture_plan_contract"]
    assert "pilot static-fit capture readiness only" in payload["static_fit_capture_plan_status_contract"]
    assert "not physical validation evidence" in payload["static_fit_capture_summary_contract"]
    assert payload["next_required_static_fit_input"] == (
        "complete_non_powered_pilot_static_fit_record_at_FR-017-PILOT-STATIC-FIT-INPUT-TEMPLATE.json"
    )
    assert payload["static_fit_capture_total_groups"] == 6
    assert payload["static_fit_capture_ready_groups"] == 0
    assert payload["static_fit_capture_pending_groups"] == 0
    assert payload["static_fit_capture_invalid_groups"] == 0
    assert payload["static_fit_capture_failed_groups"] == 0
    assert payload["static_fit_capture_upstream_blocked_groups"] == 6
    assert payload["static_fit_capture_first_blocking_group_id"] == "static_fit_evidence_and_linkage"
    assert payload["static_fit_capture_first_blocking_group_status"] == "blocked_by_upstream_mannequin_interface"
    assert "mannequin interface" in payload["static_fit_capture_first_blocking_group_action"]
    capture_plan = payload["static_fit_capture_plan"]
    assert [step["id"] for step in capture_plan] == [
        "static_fit_evidence_and_linkage",
        "static_fit_safety_preconditions",
        "left_static_fit_baseline_and_clearance",
        "right_static_fit_baseline_and_clearance",
        "left_static_fit_post_doff_and_symptoms",
        "right_static_fit_post_doff_and_symptoms",
    ]
    assert "evidence.measurement_record_path" in capture_plan[0]["required_fields"]
    assert "preconditions.stop_on_symptoms" in capture_plan[1]["required_fields"]
    assert "sides.left.static_checks.quick_release_visible_tactile_reachable" in capture_plan[2]["required_fields"]
    assert "sides.right.symptoms.loss_of_grip_strength" in capture_plan[5]["required_fields"]
    capture_status = payload["static_fit_capture_plan_status"]
    assert [step["id"] for step in capture_status] == [step["id"] for step in capture_plan]
    assert all(step["status"] == "blocked_by_upstream_mannequin_interface" for step in capture_status)
    assert all(step["ready_for_static_fit_record_review"] is False for step in capture_status)


def test_fr017_pilot_static_gate_requires_static_record_after_upstream_ready(tmp_path: Path) -> None:
    measurement_path, mockup_path, mannequin_path = _write_upstream_ready_records(tmp_path)

    proc = _run_gate(
        "-Mode",
        "Status",
        "-MeasurementPath",
        str(measurement_path),
        "-MockupPath",
        str(mockup_path),
        "-MannequinPath",
        str(mannequin_path),
    )

    assert proc.returncode == 0, proc.stderr
    payload = _payload(proc.stdout)
    assert payload["status"] == "pending_pilot_static_fit_test"
    assert payload["upstream_mannequin_status"] == "ready_for_pilot_static_fit_planning"
    assert payload["upstream_mannequin_gate_ready"] is True
    assert "evidence.date" in payload["missing_fields"]
    assert payload["pilot_static_fit_test_complete"] is False
    assert payload["pilot_movement_testing_cleared"] is False
    assert payload["fr018_implementation_cleared"] is False
    assert payload["static_fit_capture_plan_not_completion_evidence"] is True
    assert payload["static_fit_capture_total_groups"] == 6
    assert payload["static_fit_capture_ready_groups"] == 0
    assert payload["static_fit_capture_pending_groups"] == 6
    assert payload["static_fit_capture_invalid_groups"] == 0
    assert payload["static_fit_capture_failed_groups"] == 0
    assert payload["static_fit_capture_upstream_blocked_groups"] == 0
    assert payload["static_fit_capture_first_blocking_group_id"] == "static_fit_evidence_and_linkage"
    assert payload["static_fit_capture_first_blocking_group_status"] == "pending_required_fields"
    assert "matching pilot id" in payload["static_fit_capture_first_blocking_group_action"]
    capture_status = _capture_status_by_id(payload)
    assert "evidence.date" in capture_status["static_fit_evidence_and_linkage"]["missing_fields"]
    assert "preconditions.non_powered_only" in capture_status["static_fit_safety_preconditions"]["missing_fields"]
    assert (
        "sides.left.baseline.fingers_warm_before_donning"
        in capture_status["left_static_fit_baseline_and_clearance"]["missing_fields"]
    )
    assert (
        "sides.right.static_checks.quick_release_visible_tactile_reachable"
        in capture_status["right_static_fit_baseline_and_clearance"]["missing_fields"]
    )
    assert "sides.left.symptoms.tingling" in capture_status["left_static_fit_post_doff_and_symptoms"]["missing_fields"]
    assert (
        "sides.right.symptoms.loss_of_grip_strength"
        in capture_status["right_static_fit_post_doff_and_symptoms"]["missing_fields"]
    )


def test_fr017_pilot_static_gate_treats_lowercase_or_padded_pending_text_as_missing(
    tmp_path: Path,
) -> None:
    measurement_path, mockup_path, mannequin_path = _write_upstream_ready_records(tmp_path)
    static_fit_path = tmp_path / "placeholder-static-fit.json"
    static_payload = _ready_static_fit_payload(measurement_path, mockup_path, mannequin_path)
    static_payload["evidence"]["pilot_id"] = " pending "
    static_payload["preconditions"]["non_powered_only"] = "pending"
    static_payload["sides"]["left"]["baseline"]["fingers_warm_before_donning"] = " PENDING "
    static_fit_path.write_text(json.dumps(static_payload), encoding="utf-8")

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
    assert payload["status"] == "pending_pilot_static_fit_test"
    assert payload["invalid_fields"] == []
    assert "evidence.pilot_id" in payload["missing_fields"]
    assert "preconditions.non_powered_only" in payload["missing_fields"]
    assert "sides.left.baseline.fingers_warm_before_donning" in payload["missing_fields"]
    assert payload["physical_validation_complete"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_pilot_static_gate_accepts_complete_static_fit_record(tmp_path: Path) -> None:
    measurement_path, mockup_path, mannequin_path = _write_upstream_ready_records(tmp_path)
    static_fit_path = tmp_path / "ready-static-fit.json"
    static_fit_path.write_text(
        json.dumps(_ready_static_fit_payload(measurement_path, mockup_path, mannequin_path)),
        encoding="utf-8",
    )

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
    assert payload["status"] == "ready_for_pilot_movement_test_planning"
    assert payload["upstream_mannequin_status"] == "ready_for_pilot_static_fit_planning"
    assert payload["upstream_mannequin_gate_ready"] is True
    assert payload["static_fit_status"] == "ready_for_pilot_movement_test_planning"
    assert payload["missing_fields"] == []
    assert payload["invalid_fields"] == []
    assert payload["record_linkage_violations"] == []
    assert payload["record_chronology_violations"] == []
    assert payload["fit_redesign_triggers"] == []
    assert payload["symptom_blockers"] == []
    assert payload["physical_validation_complete"] is False
    assert payload["pilot_static_fit_test_complete"] is True
    assert payload["pilot_movement_test_planning_ready"] is True
    assert payload["pilot_movement_testing_cleared"] is False
    assert payload["powered_or_frame_coupled_testing_cleared"] is False
    assert payload["fr018_implementation_cleared"] is False
    assert payload["static_fit_capture_total_groups"] == 6
    assert payload["static_fit_capture_ready_groups"] == 6
    assert payload["static_fit_capture_pending_groups"] == 0
    assert payload["static_fit_capture_invalid_groups"] == 0
    assert payload["static_fit_capture_failed_groups"] == 0
    assert payload["static_fit_capture_upstream_blocked_groups"] == 0
    assert payload["static_fit_capture_first_blocking_group_id"] == ""
    assert payload["static_fit_capture_first_blocking_group_status"] == ""
    assert payload["static_fit_capture_first_blocking_group_action"] == ""
    assert all(step["ready_for_static_fit_record_review"] is True for step in payload["static_fit_capture_plan_status"])
    assert "must resolve to the same records passed into this gate" in payload["record_linkage_contract"]
    assert "must match evidence.pilot_id in the linked measurement record" in payload["pilot_identity_linkage_contract"]
    assert "YYYY-MM-DD" in payload["evidence_date_contract"]
    assert "same as or later than the linked measurement" in payload["evidence_chronology_contract"]
    assert "unquoted JSON number greater than 0" in payload["test_duration_value_contract"]
    assert "Use unquoted JSON boolean true only" in payload["boolean_value_contract"]


def test_fr017_pilot_static_gate_rejects_malformed_evidence_date(tmp_path: Path) -> None:
    measurement_path, mockup_path, mannequin_path = _write_upstream_ready_records(tmp_path)
    static_fit_path = tmp_path / "malformed-date-static-fit.json"
    payload = _ready_static_fit_payload(measurement_path, mockup_path, mannequin_path)
    payload["evidence"]["date"] = "06/23/2026"
    static_fit_path.write_text(json.dumps(payload), encoding="utf-8")

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

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "failed_static_fit_record"
    assert result["invalid_fields"] == ["evidence.date"]
    assert result["pilot_static_fit_test_complete"] is False
    assert result["pilot_movement_testing_cleared"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_pilot_static_gate_rejects_future_evidence_date(tmp_path: Path) -> None:
    measurement_path, mockup_path, mannequin_path = _write_upstream_ready_records(tmp_path)
    static_fit_path = tmp_path / "future-date-static-fit.json"
    payload = _ready_static_fit_payload(measurement_path, mockup_path, mannequin_path)
    payload["evidence"]["date"] = (date.today() + timedelta(days=1)).isoformat()
    static_fit_path.write_text(json.dumps(payload), encoding="utf-8")

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

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "failed_static_fit_record"
    assert result["invalid_fields"] == ["evidence.date"]
    assert result["pilot_static_fit_test_complete"] is False
    assert result["pilot_movement_testing_cleared"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_pilot_static_gate_rejects_static_fit_date_before_upstream_dates(
    tmp_path: Path,
) -> None:
    measurement_path, mockup_path, mannequin_path = _write_upstream_ready_records(tmp_path)
    static_fit_path = tmp_path / "backdated-static-fit.json"
    payload = _ready_static_fit_payload(measurement_path, mockup_path, mannequin_path)
    payload["evidence"]["date"] = "2026-06-22"
    static_fit_path.write_text(json.dumps(payload), encoding="utf-8")

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

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "failed_static_fit_record"
    assert result["invalid_fields"] == []
    assert result["record_linkage_violations"] == []
    assert result["record_chronology_violations"] == [
        "evidence.date_before_measurement.evidence.date",
        "evidence.date_before_mockup.evidence.date",
        "evidence.date_before_mannequin.evidence.date",
    ]
    assert result["fit_redesign_triggers"] == []
    assert result["symptom_blockers"] == []
    assert result["pilot_static_fit_test_complete"] is False
    assert result["pilot_movement_test_planning_ready"] is False
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_pilot_static_gate_rejects_unlinked_upstream_record_paths(tmp_path: Path) -> None:
    measurement_path, mockup_path, mannequin_path = _write_upstream_ready_records(tmp_path)
    unrelated_measurement_path = tmp_path / "unrelated-measurements.json"
    unrelated_mockup_path = tmp_path / "unrelated-mockup.json"
    unrelated_mannequin_path = tmp_path / "unrelated-mannequin.json"
    static_fit_path = tmp_path / "unlinked-static-fit.json"
    payload = _ready_static_fit_payload(
        unrelated_measurement_path,
        unrelated_mockup_path,
        unrelated_mannequin_path,
    )
    static_fit_path.write_text(json.dumps(payload), encoding="utf-8")

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

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "failed_static_fit_record"
    assert result["invalid_fields"] == []
    assert result["record_linkage_violations"] == [
        "evidence.measurement_record_path_must_match_measurement_path",
        "evidence.mockup_build_record_path_must_match_mockup_path",
        "evidence.mannequin_interface_record_path_must_match_mannequin_path",
    ]
    assert result["pilot_static_fit_test_complete"] is False
    assert result["pilot_movement_test_planning_ready"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_pilot_static_gate_rejects_mismatched_measurement_pilot_id(tmp_path: Path) -> None:
    measurement_path, mockup_path, mannequin_path = _write_upstream_ready_records(tmp_path)
    static_fit_path = tmp_path / "mismatched-pilot-static-fit.json"
    payload = _ready_static_fit_payload(measurement_path, mockup_path, mannequin_path)
    payload["evidence"]["pilot_id"] = "different-pilot"
    static_fit_path.write_text(json.dumps(payload), encoding="utf-8")

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

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "failed_static_fit_record"
    assert result["invalid_fields"] == []
    assert result["record_linkage_violations"] == ["evidence.pilot_id_must_match_measurement_pilot_id"]
    assert result["pilot_static_fit_test_complete"] is False
    assert result["pilot_movement_test_planning_ready"] is False
    assert result["physical_validation_complete"] is False
    assert result["pilot_movement_testing_cleared"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_pilot_static_gate_blocks_measurement_rejected_by_intake(tmp_path: Path) -> None:
    measurement_path = tmp_path / "quoted-measurements.json"
    payload = _ready_measurement_payload()
    payload["sides"]["left"]["forearm_length_elbow_crease_to_wrist_crease"] = "258"
    measurement_path.write_text(json.dumps(payload), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-MeasurementPath", str(measurement_path))

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "failed_upstream_mannequin_gate"
    assert result["upstream_mannequin_status"] == "failed_upstream_mockup_gate"
    assert result["upstream_mannequin_gate_ready"] is False
    assert result["upstream_mockup_status"] == "invalid_measurement_record"
    assert result["upstream_measurement_intake_status"] == "invalid_measurement_record"
    assert result["upstream_measurement_invalid_fields"] == ["sides.left.forearm_length_elbow_crease_to_wrist_crease"]
    assert result["pilot_static_fit_test_complete"] is False
    assert result["pilot_movement_test_planning_ready"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_pilot_static_gate_blocks_symptom_positive_static_fit(tmp_path: Path) -> None:
    measurement_path, mockup_path, mannequin_path = _write_upstream_ready_records(tmp_path)
    static_fit_path = tmp_path / "symptom-static-fit.json"
    payload = _ready_static_fit_payload(measurement_path, mockup_path, mannequin_path)
    payload["sides"]["left"]["symptoms"]["tingling"] = True
    static_fit_path.write_text(json.dumps(payload), encoding="utf-8")

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

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "failed_requires_fit_redesign_or_medical_review"
    assert result["symptom_blockers"] == ["sides.left.symptoms.tingling"]
    assert result["static_fit_capture_total_groups"] == 6
    assert result["static_fit_capture_ready_groups"] == 5
    assert result["static_fit_capture_pending_groups"] == 0
    assert result["static_fit_capture_invalid_groups"] == 0
    assert result["static_fit_capture_failed_groups"] == 1
    assert result["static_fit_capture_upstream_blocked_groups"] == 0
    assert result["static_fit_capture_first_blocking_group_id"] == "left_static_fit_post_doff_and_symptoms"
    assert result["static_fit_capture_first_blocking_group_status"] == "failed_stop_condition_or_blocking_signal"
    capture_status = _capture_status_by_id(result)
    assert capture_status["left_static_fit_post_doff_and_symptoms"]["blocking_signals"] == [
        "sides.left.symptoms.tingling"
    ]
    assert result["pilot_static_fit_test_complete"] is False
    assert result["pilot_movement_testing_cleared"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_pilot_static_gate_symptom_overrides_missing_fields(tmp_path: Path) -> None:
    measurement_path, mockup_path, mannequin_path = _write_upstream_ready_records(tmp_path)
    static_fit_path = tmp_path / "symptom-and-missing-static-fit.json"
    payload = _ready_static_fit_payload(measurement_path, mockup_path, mannequin_path)
    del payload["evidence"]["observer"]
    payload["sides"]["left"]["symptoms"]["tingling"] = True
    static_fit_path.write_text(json.dumps(payload), encoding="utf-8")

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

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "failed_requires_fit_redesign_or_medical_review"
    assert result["missing_fields"] == ["evidence.observer"]
    assert result["symptom_blockers"] == ["sides.left.symptoms.tingling"]
    assert result["pilot_static_fit_test_complete"] is False
    assert result["pilot_movement_testing_cleared"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_pilot_static_gate_blocks_release_access_failure(tmp_path: Path) -> None:
    measurement_path, mockup_path, mannequin_path = _write_upstream_ready_records(tmp_path)
    static_fit_path = tmp_path / "release-failed-static-fit.json"
    payload = _ready_static_fit_payload(measurement_path, mockup_path, mannequin_path)
    payload["sides"]["right"]["static_checks"]["quick_release_visible_tactile_reachable"] = False
    static_fit_path.write_text(json.dumps(payload), encoding="utf-8")

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

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "failed_requires_fit_redesign_or_medical_review"
    assert result["fit_redesign_triggers"] == ["sides.right.static_checks.quick_release_visible_tactile_reachable"]
    assert result["pilot_static_fit_test_complete"] is False
    assert result["pilot_movement_testing_cleared"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_pilot_static_gate_rejects_quoted_boolean_text(tmp_path: Path) -> None:
    measurement_path, mockup_path, mannequin_path = _write_upstream_ready_records(tmp_path)
    static_fit_path = tmp_path / "quoted-boolean-static-fit.json"
    payload = _ready_static_fit_payload(measurement_path, mockup_path, mannequin_path)
    payload["preconditions"]["observer_present"] = "true"
    static_fit_path.write_text(json.dumps(payload), encoding="utf-8")

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

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "failed_static_fit_record"
    assert result["invalid_fields"] == ["preconditions.observer_present"]
    assert result["fit_redesign_triggers"] == []
    assert result["fr018_implementation_cleared"] is False


def test_fr017_pilot_static_gate_rejects_quoted_test_duration_text(tmp_path: Path) -> None:
    measurement_path, mockup_path, mannequin_path = _write_upstream_ready_records(tmp_path)
    static_fit_path = tmp_path / "quoted-duration-static-fit.json"
    payload = _ready_static_fit_payload(measurement_path, mockup_path, mannequin_path)
    payload["evidence"]["test_duration_minutes"] = "5"
    static_fit_path.write_text(json.dumps(payload), encoding="utf-8")

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

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "failed_static_fit_record"
    assert result["missing_fields"] == []
    assert result["invalid_fields"] == ["evidence.test_duration_minutes"]
    assert result["pilot_static_fit_test_complete"] is False
    assert result["fr018_implementation_cleared"] is False
