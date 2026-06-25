from __future__ import annotations

import json
import shutil
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest

from tests.powershell_script_runner import run_powershell_script
from tests.test_fr017_mockup_readiness_gate_script import _ready_measurement_payload
from tests.test_fr017_pilot_movement_gate_script import (
    _ready_movement_payload,
    _write_static_ready_records,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "fr017-quick-release-cable-snag-gate.ps1"


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
        timeout_seconds=60,
    )


def _payload(stdout: str) -> dict[str, Any]:
    return json.loads(stdout)


def _capture_status_by_id(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {step["id"]: step for step in payload["release_cable_capture_plan_status"]}


def _write_movement_ready_records(tmp_path: Path) -> tuple[Path, Path, Path, Path, Path]:
    measurement_path, mockup_path, mannequin_path, static_fit_path = _write_static_ready_records(tmp_path)
    movement_path = tmp_path / "ready-movement.json"
    movement_path.write_text(json.dumps(_ready_movement_payload(static_fit_path)), encoding="utf-8")
    return measurement_path, mockup_path, mannequin_path, static_fit_path, movement_path


def _ready_release_cable_payload(movement_path: Path) -> dict[str, Any]:
    release_checks = {
        "bare_cuff_release_visible_tactile_reachable": True,
        "glove_base_mockup_release_visible_tactile_reachable": True,
        "wrist_assembly_mockup_release_visible_tactile_reachable": True,
        "forearm_frame_mockup_release_visible_tactile_reachable": True,
        "forearm_armor_mockup_release_visible_tactile_reachable": True,
        "populated_cable_sleeve_release_visible_tactile_reachable": True,
        "post_movement_release_visible_tactile_reachable": True,
        "opposite_hand_release_reachable": True,
        "same_side_reach_recorded": True,
        "release_loosens_upper_strap": True,
        "release_loosens_lower_strap": True,
        "cuff_removable_without_tools": True,
        "no_painful_wrist_posture_required": True,
        "glove_and_wrist_paths_not_trapped": True,
    }
    cable_sleeve_checks = {
        "outer_forearm_route_preserved": True,
        "no_inner_elbow_crossing": True,
        "no_wrist_bone_crossing": True,
        "no_palm_or_grip_crossing": True,
        "no_release_handle_obstruction": True,
        "no_snag_during_release": True,
        "no_snag_after_elbow_wrist_motion": True,
        "cable_not_trapped_after_release": True,
    }
    fail_observations = {
        "release_hidden": False,
        "release_not_found_by_touch": False,
        "release_blocked_by_glove_or_armor": False,
        "release_fails_to_loosen": False,
        "cuff_not_removable_without_tools": False,
        "painful_wrist_posture_required": False,
        "cable_trapped_after_release": False,
        "cable_crossed_no_go_zone": False,
    }
    side_payload = {
        "release_checks": release_checks,
        "cable_sleeve_checks": cable_sleeve_checks,
        "fail_observations": fail_observations,
    }
    return {
        "kind": "francis.fr017.quick_release_cable_snag.v1",
        "component": "FR-017 Forearm Cuffs",
        "evidence": {
            "date": "2026-06-23",
            "observer": "test-observer",
            "pilot_id": "pilot-reference",
            "prototype_revision": "soft-cuff-rev-a",
            "pilot_movement_record_path": str(movement_path),
            "test_duration_minutes": 5,
        },
        "preconditions": {
            "non_powered_only": True,
            "no_frame_or_power_coupling": True,
            "pilot_movement_gate_passed": True,
            "observer_present": True,
            "emergency_release_briefed": True,
            "stop_on_symptoms": True,
            "pilot_can_self_remove_or_abort": True,
        },
        "sides": {
            "left": {
                "release_checks": dict(side_payload["release_checks"]),
                "cable_sleeve_checks": dict(side_payload["cable_sleeve_checks"]),
                "fail_observations": dict(side_payload["fail_observations"]),
            },
            "right": {
                "release_checks": dict(side_payload["release_checks"]),
                "cable_sleeve_checks": dict(side_payload["cable_sleeve_checks"]),
                "fail_observations": dict(side_payload["fail_observations"]),
            },
        },
    }


def test_fr017_release_cable_gate_reports_default_templates_as_pending_upstream() -> None:
    proc = _run_gate("-Mode", "Status")

    assert proc.returncode == 0, proc.stderr
    payload = _payload(proc.stdout)
    assert payload["kind"] == "francis.fr017.quick_release_cable_snag_gate"
    assert payload["status"] == "pending_pilot_movement_gate"
    assert payload["upstream_pilot_movement_status"] == "pending_pilot_static_fit_gate"
    assert payload["upstream_pilot_movement_gate_ready"] is False
    assert payload["upstream_measurement_intake_status"] == "pending_measurements"
    assert payload["physical_validation_complete"] is False
    assert payload["quick_release_and_cable_snag_test_complete"] is False
    assert payload["engineering_review_or_final_physical_gate_audit_ready"] is False
    assert payload["fr018_implementation_cleared"] is False
    assert payload["release_cable_capture_plan_not_completion_evidence"] is True
    assert "not physical validation evidence" in payload["release_cable_capture_plan_contract"]
    assert "quick-release/cable-snag capture readiness only" in payload["release_cable_capture_plan_status_contract"]
    assert "not physical validation evidence" in payload["release_cable_capture_summary_contract"]
    assert (
        payload["next_required_release_cable_input"]
        == "complete_non_powered_quick_release_cable_snag_record_at_FR-017-QUICK-RELEASE-CABLE-SNAG-INPUT-TEMPLATE.json"
    )
    assert payload["release_cable_capture_total_groups"] == 6
    assert payload["release_cable_capture_ready_groups"] == 0
    assert payload["release_cable_capture_pending_groups"] == 0
    assert payload["release_cable_capture_invalid_groups"] == 0
    assert payload["release_cable_capture_failed_groups"] == 0
    assert payload["release_cable_capture_upstream_blocked_groups"] == 6
    assert payload["release_cable_capture_first_blocking_group_id"] == "release_cable_evidence_and_linkage"
    assert payload["release_cable_capture_first_blocking_group_status"] == "blocked_by_upstream_pilot_movement"
    assert "pilot movement" in payload["release_cable_capture_first_blocking_group_action"]
    assert [step["id"] for step in payload["release_cable_capture_plan"]] == [
        "release_cable_evidence_and_linkage",
        "release_cable_safety_preconditions",
        "left_quick_release_access",
        "right_quick_release_access",
        "left_cable_route_and_fail_observations",
        "right_cable_route_and_fail_observations",
    ]
    required_fields = [field for step in payload["release_cable_capture_plan"] for field in step["required_fields"]]
    assert "evidence.pilot_movement_record_path" in required_fields
    assert "preconditions.pilot_movement_gate_passed" in required_fields
    assert "sides.left.release_checks.opposite_hand_release_reachable" in required_fields
    assert "sides.right.fail_observations.cable_crossed_no_go_zone" in required_fields
    assert all(
        step["status"] == "blocked_by_upstream_pilot_movement" for step in payload["release_cable_capture_plan_status"]
    )
    assert all(
        not step["ready_for_release_cable_record_review"] for step in payload["release_cable_capture_plan_status"]
    )
    assert payload["read_only_contract"] is True
    assert payload["writes_repo"] is False
    assert payload["grants_mutation_authority"] is False


def test_fr017_release_cable_gate_requires_record_after_movement_ready(tmp_path: Path) -> None:
    measurement_path, mockup_path, mannequin_path, static_fit_path, movement_path = _write_movement_ready_records(
        tmp_path
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
        "-MovementPath",
        str(movement_path),
    )

    assert proc.returncode == 0, proc.stderr
    payload = _payload(proc.stdout)
    assert payload["status"] == "pending_quick_release_cable_snag_test"
    assert payload["upstream_pilot_movement_status"] == ("ready_for_quick_release_and_cable_snag_test_planning")
    assert payload["upstream_pilot_movement_gate_ready"] is True
    assert "evidence.date" in payload["missing_fields"]
    assert payload["quick_release_and_cable_snag_test_complete"] is False
    assert payload["fr018_implementation_cleared"] is False
    assert payload["release_cable_capture_total_groups"] == 6
    assert payload["release_cable_capture_ready_groups"] == 0
    assert payload["release_cable_capture_pending_groups"] == 6
    assert payload["release_cable_capture_invalid_groups"] == 0
    assert payload["release_cable_capture_failed_groups"] == 0
    assert payload["release_cable_capture_upstream_blocked_groups"] == 0
    assert payload["release_cable_capture_first_blocking_group_id"] == "release_cable_evidence_and_linkage"
    assert payload["release_cable_capture_first_blocking_group_status"] == "pending_required_fields"
    capture_status = _capture_status_by_id(payload)
    assert "evidence.date" in capture_status["release_cable_evidence_and_linkage"]["missing_fields"]
    assert "preconditions.non_powered_only" in capture_status["release_cable_safety_preconditions"]["missing_fields"]
    assert (
        "sides.left.release_checks.bare_cuff_release_visible_tactile_reachable"
        in capture_status["left_quick_release_access"]["missing_fields"]
    )
    assert (
        "sides.right.release_checks.opposite_hand_release_reachable"
        in capture_status["right_quick_release_access"]["missing_fields"]
    )
    assert (
        "sides.left.cable_sleeve_checks.no_inner_elbow_crossing"
        in capture_status["left_cable_route_and_fail_observations"]["missing_fields"]
    )
    assert (
        "sides.right.fail_observations.cable_crossed_no_go_zone"
        in capture_status["right_cable_route_and_fail_observations"]["missing_fields"]
    )


def test_fr017_release_cable_gate_treats_lowercase_or_padded_pending_text_as_missing(
    tmp_path: Path,
) -> None:
    measurement_path, mockup_path, mannequin_path, static_fit_path, movement_path = _write_movement_ready_records(
        tmp_path
    )
    release_cable_path = tmp_path / "placeholder-release-cable.json"
    release_payload = _ready_release_cable_payload(movement_path)
    release_payload["evidence"]["pilot_id"] = " pending "
    release_payload["preconditions"]["pilot_movement_gate_passed"] = "pending"
    release_payload["sides"]["left"]["release_checks"]["opposite_hand_release_reachable"] = " PENDING "
    release_cable_path.write_text(json.dumps(release_payload), encoding="utf-8")

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
        "-ReleaseCablePath",
        str(release_cable_path),
    )

    assert proc.returncode == 0, proc.stderr
    payload = _payload(proc.stdout)
    assert payload["status"] == "pending_quick_release_cable_snag_test"
    assert payload["invalid_fields"] == []
    assert "evidence.pilot_id" in payload["missing_fields"]
    assert "preconditions.pilot_movement_gate_passed" in payload["missing_fields"]
    assert "sides.left.release_checks.opposite_hand_release_reachable" in payload["missing_fields"]
    assert payload["physical_validation_complete"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_release_cable_gate_accepts_complete_release_cable_record(tmp_path: Path) -> None:
    measurement_path, mockup_path, mannequin_path, static_fit_path, movement_path = _write_movement_ready_records(
        tmp_path
    )
    release_cable_path = tmp_path / "ready-release-cable.json"
    release_cable_path.write_text(
        json.dumps(_ready_release_cable_payload(movement_path)),
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
        "-MovementPath",
        str(movement_path),
        "-ReleaseCablePath",
        str(release_cable_path),
    )

    assert proc.returncode == 0, proc.stderr
    payload = _payload(proc.stdout)
    assert payload["status"] == "ready_for_engineering_review_or_final_physical_gate_audit"
    assert payload["release_cable_status"] == "ready_for_engineering_review_or_final_physical_gate_audit"
    assert payload["upstream_pilot_movement_gate_ready"] is True
    assert payload["missing_fields"] == []
    assert payload["invalid_fields"] == []
    assert payload["record_linkage_violations"] == []
    assert payload["record_chronology_violations"] == []
    assert payload["release_cable_redesign_triggers"] == []
    assert payload["fail_observations"] == []
    assert payload["physical_validation_complete"] is False
    assert payload["quick_release_and_cable_snag_test_complete"] is True
    assert payload["engineering_review_or_final_physical_gate_audit_ready"] is True
    assert payload["powered_or_frame_coupled_testing_cleared"] is False
    assert payload["fr018_implementation_cleared"] is False
    assert payload["release_cable_capture_total_groups"] == 6
    assert payload["release_cable_capture_ready_groups"] == 6
    assert payload["release_cable_capture_pending_groups"] == 0
    assert payload["release_cable_capture_invalid_groups"] == 0
    assert payload["release_cable_capture_failed_groups"] == 0
    assert payload["release_cable_capture_upstream_blocked_groups"] == 0
    assert payload["release_cable_capture_first_blocking_group_id"] == ""
    assert payload["release_cable_capture_first_blocking_group_status"] == ""
    assert payload["release_cable_capture_first_blocking_group_action"] == ""
    assert all(
        step["status"] == "ready_for_release_cable_record_review"
        for step in payload["release_cable_capture_plan_status"]
    )
    assert all(step["ready_for_release_cable_record_review"] for step in payload["release_cable_capture_plan_status"])
    assert "must resolve to the same movement record path" in payload["record_linkage_contract"]
    assert "must match evidence.pilot_id in the linked movement record" in payload["pilot_identity_linkage_contract"]
    assert "YYYY-MM-DD" in payload["evidence_date_contract"]
    assert "same as or later than the linked pilot movement" in payload["evidence_chronology_contract"]
    assert "unquoted JSON number greater than 0" in payload["test_duration_value_contract"]
    assert "Use unquoted JSON boolean true only" in payload["boolean_value_contract"]


def test_fr017_release_cable_gate_rejects_malformed_evidence_date(tmp_path: Path) -> None:
    measurement_path, mockup_path, mannequin_path, static_fit_path, movement_path = _write_movement_ready_records(
        tmp_path
    )
    release_cable_path = tmp_path / "malformed-date-release-cable.json"
    payload = _ready_release_cable_payload(movement_path)
    payload["evidence"]["date"] = "06/23/2026"
    release_cable_path.write_text(json.dumps(payload), encoding="utf-8")

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
        "-ReleaseCablePath",
        str(release_cable_path),
    )

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "failed_release_cable_record"
    assert result["invalid_fields"] == ["evidence.date"]
    assert result["quick_release_and_cable_snag_test_complete"] is False
    assert result["engineering_review_or_final_physical_gate_audit_ready"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_release_cable_gate_rejects_future_evidence_date(tmp_path: Path) -> None:
    measurement_path, mockup_path, mannequin_path, static_fit_path, movement_path = _write_movement_ready_records(
        tmp_path
    )
    release_cable_path = tmp_path / "future-date-release-cable.json"
    payload = _ready_release_cable_payload(movement_path)
    payload["evidence"]["date"] = (date.today() + timedelta(days=1)).isoformat()
    release_cable_path.write_text(json.dumps(payload), encoding="utf-8")

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
        "-ReleaseCablePath",
        str(release_cable_path),
    )

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "failed_release_cable_record"
    assert result["invalid_fields"] == ["evidence.date"]
    assert result["quick_release_and_cable_snag_test_complete"] is False
    assert result["engineering_review_or_final_physical_gate_audit_ready"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_release_cable_gate_rejects_release_date_before_movement_date(
    tmp_path: Path,
) -> None:
    measurement_path, mockup_path, mannequin_path, static_fit_path, movement_path = _write_movement_ready_records(
        tmp_path
    )
    release_cable_path = tmp_path / "backdated-release-cable.json"
    payload = _ready_release_cable_payload(movement_path)
    payload["evidence"]["date"] = "2026-06-22"
    release_cable_path.write_text(json.dumps(payload), encoding="utf-8")

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
        "-ReleaseCablePath",
        str(release_cable_path),
    )

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "failed_release_cable_record"
    assert result["invalid_fields"] == []
    assert result["record_linkage_violations"] == []
    assert result["record_chronology_violations"] == ["evidence.date_before_movement.evidence.date"]
    assert result["release_cable_redesign_triggers"] == []
    assert result["fail_observations"] == []
    assert result["quick_release_and_cable_snag_test_complete"] is False
    assert result["engineering_review_or_final_physical_gate_audit_ready"] is False
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_release_cable_gate_rejects_unlinked_movement_record_path(tmp_path: Path) -> None:
    measurement_path, mockup_path, mannequin_path, static_fit_path, movement_path = _write_movement_ready_records(
        tmp_path
    )
    unrelated_movement_path = tmp_path / "unrelated-movement.json"
    release_cable_path = tmp_path / "unlinked-release-cable.json"
    release_cable_path.write_text(
        json.dumps(_ready_release_cable_payload(unrelated_movement_path)),
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
        "-MovementPath",
        str(movement_path),
        "-ReleaseCablePath",
        str(release_cable_path),
    )

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "failed_release_cable_record"
    assert result["invalid_fields"] == []
    assert result["record_linkage_violations"] == ["evidence.pilot_movement_record_path_must_match_movement_path"]
    assert result["quick_release_and_cable_snag_test_complete"] is False
    assert result["engineering_review_or_final_physical_gate_audit_ready"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_release_cable_gate_rejects_mismatched_movement_pilot_id(tmp_path: Path) -> None:
    measurement_path, mockup_path, mannequin_path, static_fit_path, movement_path = _write_movement_ready_records(
        tmp_path
    )
    release_cable_path = tmp_path / "mismatched-pilot-release-cable.json"
    payload = _ready_release_cable_payload(movement_path)
    payload["evidence"]["pilot_id"] = "different-pilot"
    release_cable_path.write_text(json.dumps(payload), encoding="utf-8")

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
        "-ReleaseCablePath",
        str(release_cable_path),
    )

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "failed_release_cable_record"
    assert result["invalid_fields"] == []
    assert result["record_linkage_violations"] == ["evidence.pilot_id_must_match_movement_pilot_id"]
    assert result["quick_release_and_cable_snag_test_complete"] is False
    assert result["engineering_review_or_final_physical_gate_audit_ready"] is False
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_release_cable_gate_blocks_measurement_rejected_by_intake(tmp_path: Path) -> None:
    measurement_path = tmp_path / "quoted-measurements.json"
    payload = _ready_measurement_payload()
    payload["sides"]["left"]["forearm_length_elbow_crease_to_wrist_crease"] = "258"
    measurement_path.write_text(json.dumps(payload), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-MeasurementPath", str(measurement_path))

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "failed_upstream_pilot_movement_gate"
    assert result["upstream_pilot_movement_status"] == "failed_upstream_static_fit_gate"
    assert result["upstream_pilot_movement_gate_ready"] is False
    assert result["upstream_static_fit_status"] == "failed_upstream_mannequin_gate"
    assert result["upstream_mannequin_status"] == "failed_upstream_mockup_gate"
    assert result["upstream_mockup_status"] == "invalid_measurement_record"
    assert result["upstream_measurement_intake_status"] == "invalid_measurement_record"
    assert result["upstream_measurement_invalid_fields"] == ["sides.left.forearm_length_elbow_crease_to_wrist_crease"]
    assert result["quick_release_and_cable_snag_test_complete"] is False
    assert result["engineering_review_or_final_physical_gate_audit_ready"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_release_cable_gate_blocks_hidden_release(tmp_path: Path) -> None:
    measurement_path, mockup_path, mannequin_path, static_fit_path, movement_path = _write_movement_ready_records(
        tmp_path
    )
    release_cable_path = tmp_path / "hidden-release.json"
    payload = _ready_release_cable_payload(movement_path)
    payload["sides"]["left"]["release_checks"]["forearm_armor_mockup_release_visible_tactile_reachable"] = False
    payload["sides"]["left"]["fail_observations"]["release_hidden"] = True
    release_cable_path.write_text(json.dumps(payload), encoding="utf-8")

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
        "-ReleaseCablePath",
        str(release_cable_path),
    )

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "failed_requires_release_cable_redesign_or_medical_review"
    assert result["release_cable_redesign_triggers"] == [
        "sides.left.release_checks.forearm_armor_mockup_release_visible_tactile_reachable"
    ]
    assert result["fail_observations"] == ["sides.left.fail_observations.release_hidden"]
    assert result["release_cable_capture_total_groups"] == 6
    assert result["release_cable_capture_ready_groups"] == 4
    assert result["release_cable_capture_pending_groups"] == 0
    assert result["release_cable_capture_invalid_groups"] == 0
    assert result["release_cable_capture_failed_groups"] == 2
    assert result["release_cable_capture_upstream_blocked_groups"] == 0
    assert result["release_cable_capture_first_blocking_group_id"] == "left_quick_release_access"
    assert result["release_cable_capture_first_blocking_group_status"] == "failed_stop_condition_or_blocking_signal"
    capture_status = _capture_status_by_id(result)
    assert capture_status["left_quick_release_access"]["blocking_signals"] == [
        "sides.left.release_checks.forearm_armor_mockup_release_visible_tactile_reachable"
    ]
    assert capture_status["left_cable_route_and_fail_observations"]["blocking_signals"] == [
        "sides.left.fail_observations.release_hidden"
    ]
    assert result["quick_release_and_cable_snag_test_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_release_cable_gate_blocks_no_go_zone_cable_crossing(tmp_path: Path) -> None:
    measurement_path, mockup_path, mannequin_path, static_fit_path, movement_path = _write_movement_ready_records(
        tmp_path
    )
    release_cable_path = tmp_path / "no-go-zone-cable.json"
    payload = _ready_release_cable_payload(movement_path)
    payload["sides"]["right"]["cable_sleeve_checks"]["no_wrist_bone_crossing"] = False
    payload["sides"]["right"]["fail_observations"]["cable_crossed_no_go_zone"] = True
    release_cable_path.write_text(json.dumps(payload), encoding="utf-8")

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
        "-ReleaseCablePath",
        str(release_cable_path),
    )

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "failed_requires_release_cable_redesign_or_medical_review"
    assert result["release_cable_redesign_triggers"] == ["sides.right.cable_sleeve_checks.no_wrist_bone_crossing"]
    assert result["fail_observations"] == ["sides.right.fail_observations.cable_crossed_no_go_zone"]
    assert result["quick_release_and_cable_snag_test_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_release_cable_gate_failure_overrides_missing_fields(tmp_path: Path) -> None:
    measurement_path, mockup_path, mannequin_path, static_fit_path, movement_path = _write_movement_ready_records(
        tmp_path
    )
    release_cable_path = tmp_path / "failure-and-missing-release-cable.json"
    payload = _ready_release_cable_payload(movement_path)
    del payload["evidence"]["observer"]
    payload["sides"]["left"]["fail_observations"]["release_hidden"] = True
    release_cable_path.write_text(json.dumps(payload), encoding="utf-8")

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
        "-ReleaseCablePath",
        str(release_cable_path),
    )

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "failed_requires_release_cable_redesign_or_medical_review"
    assert result["missing_fields"] == ["evidence.observer"]
    assert result["fail_observations"] == ["sides.left.fail_observations.release_hidden"]
    assert result["quick_release_and_cable_snag_test_complete"] is False
    assert result["engineering_review_or_final_physical_gate_audit_ready"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_release_cable_gate_rejects_quoted_boolean_text(tmp_path: Path) -> None:
    measurement_path, mockup_path, mannequin_path, static_fit_path, movement_path = _write_movement_ready_records(
        tmp_path
    )
    release_cable_path = tmp_path / "quoted-boolean-release-cable.json"
    payload = _ready_release_cable_payload(movement_path)
    payload["preconditions"]["observer_present"] = "true"
    release_cable_path.write_text(json.dumps(payload), encoding="utf-8")

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
        "-ReleaseCablePath",
        str(release_cable_path),
    )

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "failed_release_cable_record"
    assert result["invalid_fields"] == ["preconditions.observer_present"]
    assert result["release_cable_redesign_triggers"] == []
    assert result["fr018_implementation_cleared"] is False


def test_fr017_release_cable_gate_rejects_quoted_test_duration_text(tmp_path: Path) -> None:
    measurement_path, mockup_path, mannequin_path, static_fit_path, movement_path = _write_movement_ready_records(
        tmp_path
    )
    release_cable_path = tmp_path / "quoted-duration-release-cable.json"
    payload = _ready_release_cable_payload(movement_path)
    payload["evidence"]["test_duration_minutes"] = "5"
    release_cable_path.write_text(json.dumps(payload), encoding="utf-8")

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
        "-ReleaseCablePath",
        str(release_cable_path),
    )

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "failed_release_cable_record"
    assert result["missing_fields"] == []
    assert result["invalid_fields"] == ["evidence.test_duration_minutes"]
    assert result["quick_release_and_cable_snag_test_complete"] is False
    assert result["fr018_implementation_cleared"] is False
