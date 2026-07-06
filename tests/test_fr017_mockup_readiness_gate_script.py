from __future__ import annotations

import json
import shutil
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest

from tests.powershell_script_runner import run_powershell_script


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "fr017-mockup-readiness-gate.ps1"


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
        timeout_seconds=20,
    )


def _payload(stdout: str) -> dict[str, Any]:
    return json.loads(stdout)


def _ready_measurement_payload() -> dict[str, Any]:
    measurement_values = {
        "forearm_circumference_25mm_below_elbow_crease": 235,
        "forearm_circumference_mid_forearm": 225,
        "forearm_circumference_40mm_above_wrist_crease": 172,
        "forearm_length_elbow_crease_to_wrist_crease": 258,
        "outer_forearm_usable_panel_length": 178,
        "upper_strap_allowed_band_width": 45,
        "lower_strap_allowed_band_width": 38,
        "bone_ridge_relief_length": 160,
        "inner_forearm_no_pressure_zone_width": 52,
        "wrist_clearance_gap": 42,
    }
    marked_zones = {
        "inner_elbow_crease_boundary": "marked_photo_ref_left",
        "wrist_bone_boundary": "marked_photo_ref_left",
        "radius_ridge_relief": "marked_photo_ref_left",
        "ulna_ridge_relief": "marked_photo_ref_left",
        "outer_forearm_cable_route": "marked_photo_ref_left",
        "quick_release_reach_zone": "marked_photo_ref_left",
        "glove_removal_path": "marked_photo_ref_left",
    }
    return {
        "kind": "francis.fr017.measurements.v1",
        "component": "FR-017 Forearm Cuffs",
        "units": "mm",
        "evidence": {
            "date": "2026-06-23",
            "observer": "test-observer",
            "pilot_id": "pilot-reference",
            "measurement_tool": "flexible metric tape",
            "method": "flexible tape, no tissue compression",
            "posture": "arm relaxed, palm neutral",
        },
        "sides": {
            "left": measurement_values,
            "right": {**measurement_values, "forearm_circumference_mid_forearm": 228},
        },
        "marked_zones": {
            "left": marked_zones,
            "right": {key: value.replace("left", "right") for key, value in marked_zones.items()},
        },
        "left_right_independence": {
            "left_arm_measured_separately": True,
            "right_arm_measured_separately": True,
            "side_labels_verified": True,
            "values_not_copied_between_sides": True,
            "left_measurement_reference": "measurement_sheet_left_passes_1_2",
            "right_measurement_reference": "measurement_sheet_right_passes_1_2",
            "independence_notes": "Fixture records separate left and right measurement passes with verified side label anchors.",
        },
        "measurement_conditions": {
            "no_tissue_compression_used": True,
            "no_wrist_bone_compression_used": True,
            "metric_tool_used": True,
            "arm_relaxed_palm_neutral_or_exception_recorded": True,
            "stop_conditions_briefed": True,
            "condition_notes": (
                "Fixture confirms no tissue compression, no wrist-bone compression, metric tape use, "
                "and stop-condition briefing."
            ),
        },
        "landmark_confirmation": {
            "inner_elbow_crease_boundary_confirmed": True,
            "wrist_bone_boundary_confirmed": True,
            "radius_ulna_relief_paths_confirmed": True,
            "outer_forearm_cable_route_confirmed": True,
            "quick_release_reach_zone_confirmed": True,
            "glove_removal_path_confirmed": True,
            "skin_safe_marking_used": True,
            "landmark_notes": (
                "Fixture confirms skin-safe marks for inner elbow, wrist, radius, ulna, cable route, "
                "quick release reach, and glove removal path."
            ),
        },
        "repeatability": {
            "left": {
                "second_pass_completed": True,
                "max_delta_mm": 3,
                "all_required_measurements_within_5mm": True,
            },
            "right": {
                "second_pass_completed": True,
                "max_delta_mm": 4,
                "all_required_measurements_within_5mm": True,
            },
        },
        "safety_screen": {
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
        },
    }


def _ready_mockup_payload(measurement_path: Path) -> dict[str, Any]:
    side_checks = {
        "upper_strap_width_matches_measurement": True,
        "lower_strap_width_matches_measurement": True,
        "bone_relief_channel_present": True,
        "inner_forearm_no_pressure_zone_marked": True,
        "wrist_clearance_kept": True,
        "quick_release_installed_outer_or_lateral": True,
        "alignment_tabs_non_load_bearing": True,
        "cable_sleeve_outer_route_only": True,
    }
    return {
        "kind": "francis.fr017.mockup_build.v1",
        "component": "FR-017 Forearm Cuffs",
        "evidence": {
            "date": "2026-06-23",
            "observer": "test-observer",
            "build_method": "non-powered soft cuff mockup only",
            "measurement_record_path": str(measurement_path),
        },
        "materials": {
            "padding_layer": "6mm closed-cell foam",
            "semi_rigid_outer_layer": "thin thermoform sheet",
            "upper_forearm_strap": "50mm hook-and-loop strap",
            "lower_forearm_strap": "38mm hook-and-loop strap",
            "quick_release": "side pull tab",
            "outer_forearm_cable_sleeve": "removable fabric sleeve",
            "non_load_bearing_alignment_tabs": "soft locator tabs",
            "sensor_placeholder_blanks": "flat fabric markers",
        },
        "constraints": {
            "non_powered_only": True,
            "no_load_bearing_claim": True,
            "no_hard_inner_forearm_buckles": True,
            "no_inner_elbow_crossing": True,
            "no_wrist_bone_pressure": True,
            "releases_visible_and_reachable": True,
            "glove_removal_path_preserved": True,
            "outer_forearm_cable_route_only": True,
            "stop_on_symptoms": True,
        },
        "sides": {
            "left": side_checks,
            "right": side_checks,
        },
    }


def test_fr017_mockup_gate_reports_default_templates_as_pending_measurement() -> None:
    proc = _run_gate("-Mode", "Status")

    assert proc.returncode == 0, proc.stderr
    payload = _payload(proc.stdout)
    assert payload["kind"] == "francis.fr017.mockup_readiness_gate"
    assert payload["status"] == "pending_measurement_intake"
    assert payload["measurement_status"] == "pending_measurement_intake"
    assert payload["physical_validation_complete"] is False
    assert payload["mannequin_interface_test_ready"] is False
    assert payload["pilot_testing_cleared"] is False
    assert payload["fr018_implementation_cleared"] is False
    assert payload["read_only_contract"] is True
    assert payload["writes_repo"] is False
    assert payload["grants_mutation_authority"] is False
    assert payload["mockup_capture_plan_not_completion_evidence"] is True
    assert "not physical validation evidence" in payload["mockup_capture_plan_contract"]
    assert "mockup readiness only" in payload["mockup_capture_plan_status_contract"]
    assert "not physical validation evidence" in payload["mockup_capture_summary_contract"]
    assert "operator input tooling only" in payload["mockup_capture_runbook_contract"]
    assert "fr017-new-mockup-record.ps1" in payload["mockup_capture_runbook_contract"]
    assert (
        payload["next_required_mockup_input"]
        == "create_non_powered_mockup_record_with_fr017-new-mockup-record.ps1_then_rerun_mockup_readiness_gate"
    )
    assert (
        str(payload["mockup_input_template_path"])
        .replace("/", "\\")
        .endswith("FR-017_Stage17_Package\\FR-017-MOCKUP-BUILD-INPUT-TEMPLATE.json")
    )
    assert (
        str(payload["mockup_record_initializer_path"])
        .replace("/", "\\")
        .endswith("scripts\\fr017-new-mockup-record.ps1")
    )
    assert payload["mockup_working_record_name_pattern"] == "FR-017-MOCKUP-YYYY-MM-DD-PILOT-RECORD.json"
    assert payload["mockup_capture_total_groups"] == 5
    assert payload["mockup_capture_ready_groups"] == 0
    assert payload["mockup_capture_pending_groups"] == 0
    assert payload["mockup_capture_invalid_groups"] == 0
    assert payload["mockup_capture_failed_groups"] == 0
    assert payload["mockup_capture_upstream_blocked_groups"] == 5
    assert payload["mockup_capture_first_blocking_group_id"] == "mockup_evidence_and_linkage"
    assert payload["mockup_capture_first_blocking_group_status"] == "blocked_by_upstream_measurement_intake"
    assert "complete measurement intake" in payload["mockup_capture_first_blocking_group_action"]
    capture_plan = payload["mockup_capture_plan"]
    assert [step["id"] for step in capture_plan] == [
        "mockup_evidence_and_linkage",
        "mockup_material_stack",
        "mockup_global_safety_constraints",
        "left_mockup_side_checks",
        "right_mockup_side_checks",
    ]
    assert "evidence.measurement_record_path" in capture_plan[0]["required_fields"]
    capture_status = payload["mockup_capture_plan_status"]
    assert all(step["status"] == "blocked_by_upstream_measurement_intake" for step in capture_status)
    assert all(step["ready_for_mockup_readiness"] is False for step in capture_status)


def test_fr017_mockup_gate_requires_mockup_record_after_measurements(tmp_path: Path) -> None:
    measurement_path = tmp_path / "ready-measurements.json"
    measurement_path.write_text(json.dumps(_ready_measurement_payload()), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-MeasurementPath", str(measurement_path))

    assert proc.returncode == 0, proc.stderr
    payload = _payload(proc.stdout)
    assert payload["status"] == "pending_mockup_build_record"
    assert payload["measurement_status"] == "ready_for_non_powered_mockup_patterning"
    assert payload["mockup_status"] == "pending_mockup_build_record"
    assert (
        payload["next_required_mockup_input"]
        == "create_non_powered_mockup_record_with_fr017-new-mockup-record.ps1_then_rerun_mockup_readiness_gate"
    )
    assert "evidence.date" in payload["mockup_missing_fields"]
    assert payload["mockup_capture_total_groups"] == 5
    assert payload["mockup_capture_ready_groups"] == 0
    assert payload["mockup_capture_pending_groups"] == 5
    assert payload["mockup_capture_invalid_groups"] == 0
    assert payload["mockup_capture_failed_groups"] == 0
    assert payload["mockup_capture_upstream_blocked_groups"] == 0
    assert payload["mockup_capture_first_blocking_group_id"] == "mockup_evidence_and_linkage"
    assert payload["mockup_capture_first_blocking_group_status"] == "pending_required_fields"
    assert "matching measurement record path" in payload["mockup_capture_first_blocking_group_action"]
    capture_status = {step["id"]: step for step in payload["mockup_capture_plan_status"]}
    assert "evidence.date" in capture_status["mockup_evidence_and_linkage"]["missing_fields"]
    assert "materials.padding_layer" in capture_status["mockup_material_stack"]["missing_fields"]
    assert "constraints.non_powered_only" in capture_status["mockup_global_safety_constraints"]["missing_fields"]
    assert "sides.left.wrist_clearance_kept" in capture_status["left_mockup_side_checks"]["missing_fields"]
    assert "sides.right.wrist_clearance_kept" in capture_status["right_mockup_side_checks"]["missing_fields"]
    assert payload["mannequin_interface_test_ready"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_mockup_gate_treats_lowercase_or_padded_pending_text_as_missing(
    tmp_path: Path,
) -> None:
    measurement_path = tmp_path / "ready-measurements.json"
    mockup_path = tmp_path / "placeholder-mockup.json"
    measurement_path.write_text(json.dumps(_ready_measurement_payload()), encoding="utf-8")
    mockup_payload = _ready_mockup_payload(measurement_path)
    mockup_payload["evidence"]["observer"] = " pending "
    mockup_payload["evidence"]["build_method"] = "pending"
    mockup_payload["constraints"]["no_inner_elbow_crossing"] = " PENDING "
    mockup_path.write_text(json.dumps(mockup_payload), encoding="utf-8")

    proc = _run_gate(
        "-Mode",
        "Status",
        "-MeasurementPath",
        str(measurement_path),
        "-MockupPath",
        str(mockup_path),
    )

    assert proc.returncode == 0, proc.stderr
    payload = _payload(proc.stdout)
    assert payload["status"] == "pending_mockup_build_record"
    assert payload["mockup_invalid_fields"] == []
    assert "evidence.observer" in payload["mockup_missing_fields"]
    assert "evidence.build_method" in payload["mockup_missing_fields"]
    assert "constraints.no_inner_elbow_crossing" in payload["mockup_missing_fields"]
    assert payload["physical_validation_complete"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_mockup_gate_accepts_complete_non_powered_mockup_record(tmp_path: Path) -> None:
    measurement_path = tmp_path / "ready-measurements.json"
    mockup_path = tmp_path / "ready-mockup.json"
    measurement_path.write_text(json.dumps(_ready_measurement_payload()), encoding="utf-8")
    mockup_path.write_text(json.dumps(_ready_mockup_payload(measurement_path)), encoding="utf-8")

    proc = _run_gate(
        "-Mode",
        "Status",
        "-MeasurementPath",
        str(measurement_path),
        "-MockupPath",
        str(mockup_path),
    )

    assert proc.returncode == 0, proc.stderr
    payload = _payload(proc.stdout)
    assert payload["status"] == "ready_for_mannequin_interface_test"
    assert payload["measurement_status"] == "ready_for_non_powered_mockup_patterning"
    assert payload["upstream_measurement_intake_status"] == "ready_for_non_powered_mockup_patterning"
    assert payload["upstream_measurement_intake_ready"] is True
    assert payload["mockup_status"] == "ready_for_mannequin_interface_test"
    assert payload["measurement_missing_fields"] == []
    assert payload["measurement_invalid_fields"] == []
    assert payload["repeatability_blockers"] == []
    assert payload["left_right_independence_blockers"] == []
    assert payload["measurement_condition_blockers"] == []
    assert payload["landmark_confirmation_blockers"] == []
    assert payload["mockup_missing_fields"] == []
    assert payload["mockup_linkage_violations"] == []
    assert payload["mockup_chronology_violations"] == []
    assert payload["mockup_redesign_triggers"] == []
    assert payload["mockup_capture_total_groups"] == 5
    assert payload["mockup_capture_ready_groups"] == 5
    assert payload["mockup_capture_pending_groups"] == 0
    assert payload["mockup_capture_invalid_groups"] == 0
    assert payload["mockup_capture_failed_groups"] == 0
    assert payload["mockup_capture_upstream_blocked_groups"] == 0
    assert payload["mockup_capture_first_blocking_group_id"] == ""
    assert payload["mockup_capture_first_blocking_group_status"] == ""
    assert payload["mockup_capture_first_blocking_group_action"] == ""
    assert all(step["ready_for_mockup_readiness"] is True for step in payload["mockup_capture_plan_status"])
    assert payload["physical_validation_complete"] is False
    assert payload["mannequin_interface_test_ready"] is True
    assert payload["mannequin_interface_test_complete"] is False
    assert payload["pilot_testing_cleared"] is False
    assert payload["powered_or_frame_coupled_testing_cleared"] is False
    assert payload["fr018_implementation_cleared"] is False
    assert "YYYY-MM-DD" in payload["evidence_date_contract"]
    assert "same as or later than the linked measurement" in payload["evidence_chronology_contract"]
    assert "non-powered" in payload["build_method_contract"]
    assert "soft or semi-rigid" in payload["build_method_contract"]
    assert "must resolve to the same measurement record path" in payload["record_linkage_contract"]
    assert "Use unquoted JSON boolean true only" in payload["boolean_value_contract"]


def test_fr017_mockup_gate_rejects_unlinked_measurement_record_path(tmp_path: Path) -> None:
    measurement_path = tmp_path / "ready-measurements.json"
    unrelated_measurement_path = tmp_path / "unrelated-measurements.json"
    mockup_path = tmp_path / "unlinked-mockup.json"
    measurement_path.write_text(json.dumps(_ready_measurement_payload()), encoding="utf-8")
    unrelated_measurement_path.write_text(json.dumps(_ready_measurement_payload()), encoding="utf-8")
    mockup_path.write_text(
        json.dumps(_ready_mockup_payload(unrelated_measurement_path)),
        encoding="utf-8",
    )

    proc = _run_gate(
        "-Mode",
        "Status",
        "-MeasurementPath",
        str(measurement_path),
        "-MockupPath",
        str(mockup_path),
    )

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "failed_mockup_record"
    assert result["mockup_invalid_fields"] == []
    assert result["mockup_linkage_violations"] == ["evidence.measurement_record_path_must_match_measurement_path"]
    assert result["mannequin_interface_test_ready"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_mockup_gate_rejects_mockup_date_before_measurement_date(tmp_path: Path) -> None:
    measurement_path = tmp_path / "ready-measurements.json"
    mockup_path = tmp_path / "backdated-mockup.json"
    measurement_path.write_text(json.dumps(_ready_measurement_payload()), encoding="utf-8")
    payload = _ready_mockup_payload(measurement_path)
    payload["evidence"]["date"] = "2026-06-22"
    mockup_path.write_text(json.dumps(payload), encoding="utf-8")

    proc = _run_gate(
        "-Mode",
        "Status",
        "-MeasurementPath",
        str(measurement_path),
        "-MockupPath",
        str(mockup_path),
    )

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "failed_mockup_record"
    assert result["mockup_invalid_fields"] == []
    assert result["mockup_linkage_violations"] == []
    assert result["mockup_chronology_violations"] == ["evidence.date_before_measurement.evidence.date"]
    assert result["mannequin_interface_test_ready"] is False
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_mockup_gate_rejects_malformed_mockup_evidence_date(tmp_path: Path) -> None:
    measurement_path = tmp_path / "ready-measurements.json"
    mockup_path = tmp_path / "malformed-date-mockup.json"
    measurement_path.write_text(json.dumps(_ready_measurement_payload()), encoding="utf-8")
    payload = _ready_mockup_payload(measurement_path)
    payload["evidence"]["date"] = "06/23/2026"
    mockup_path.write_text(json.dumps(payload), encoding="utf-8")

    proc = _run_gate(
        "-Mode",
        "Status",
        "-MeasurementPath",
        str(measurement_path),
        "-MockupPath",
        str(mockup_path),
    )

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "failed_mockup_record"
    assert result["mockup_invalid_fields"] == ["evidence.date"]
    assert result["mockup_linkage_violations"] == []
    assert "YYYY-MM-DD" in result["evidence_date_contract"]
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_mockup_gate_rejects_powered_or_rigid_build_method_text(tmp_path: Path) -> None:
    measurement_path = tmp_path / "ready-measurements.json"
    mockup_path = tmp_path / "unsafe-build-method-mockup.json"
    measurement_path.write_text(json.dumps(_ready_measurement_payload()), encoding="utf-8")
    payload = _ready_mockup_payload(measurement_path)
    payload["evidence"]["build_method"] = "powered rigid forearm frame prototype"
    mockup_path.write_text(json.dumps(payload), encoding="utf-8")

    proc = _run_gate(
        "-Mode",
        "Status",
        "-MeasurementPath",
        str(measurement_path),
        "-MockupPath",
        str(mockup_path),
    )

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "failed_mockup_record"
    assert result["mockup_invalid_fields"] == ["evidence.build_method"]
    assert result["mockup_redesign_triggers"] == []
    assert result["mannequin_interface_test_ready"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_mockup_gate_rejects_future_mockup_evidence_date(tmp_path: Path) -> None:
    measurement_path = tmp_path / "ready-measurements.json"
    mockup_path = tmp_path / "future-date-mockup.json"
    measurement_path.write_text(json.dumps(_ready_measurement_payload()), encoding="utf-8")
    payload = _ready_mockup_payload(measurement_path)
    payload["evidence"]["date"] = (date.today() + timedelta(days=1)).isoformat()
    mockup_path.write_text(json.dumps(payload), encoding="utf-8")

    proc = _run_gate(
        "-Mode",
        "Status",
        "-MeasurementPath",
        str(measurement_path),
        "-MockupPath",
        str(mockup_path),
    )

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "failed_mockup_record"
    assert result["mockup_invalid_fields"] == ["evidence.date"]
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_mockup_gate_rejects_measurement_record_rejected_by_intake(tmp_path: Path) -> None:
    measurement_path = tmp_path / "quoted-measurements.json"
    payload = _ready_measurement_payload()
    payload["sides"]["left"]["forearm_length_elbow_crease_to_wrist_crease"] = "258"
    measurement_path.write_text(json.dumps(payload), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-MeasurementPath", str(measurement_path))

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "invalid_measurement_record"
    assert result["measurement_status"] == "invalid_measurement_record"
    assert result["upstream_measurement_intake_status"] == "invalid_measurement_record"
    assert result["upstream_measurement_intake_ready"] is False
    assert result["measurement_invalid_fields"] == ["sides.left.forearm_length_elbow_crease_to_wrist_crease"]
    assert result["mockup_status"] == "pending_mockup_build_record"
    assert result["mannequin_interface_test_ready"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_mockup_gate_blocks_symptom_positive_measurements(tmp_path: Path) -> None:
    measurement_path = tmp_path / "symptom-measurements.json"
    payload = _ready_measurement_payload()
    payload["safety_screen"]["wrist_pain"] = True
    measurement_path.write_text(json.dumps(payload), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-MeasurementPath", str(measurement_path))

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "failed_requires_redesign_or_medical_review"
    assert result["safety_blockers"] == ["wrist_pain"]
    assert result["mannequin_interface_test_ready"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_mockup_gate_blocks_mockup_constraint_violation(tmp_path: Path) -> None:
    measurement_path = tmp_path / "ready-measurements.json"
    mockup_path = tmp_path / "unsafe-mockup.json"
    measurement_path.write_text(json.dumps(_ready_measurement_payload()), encoding="utf-8")
    payload = _ready_mockup_payload(measurement_path)
    payload["constraints"]["no_wrist_bone_pressure"] = False
    mockup_path.write_text(json.dumps(payload), encoding="utf-8")

    proc = _run_gate(
        "-Mode",
        "Status",
        "-MeasurementPath",
        str(measurement_path),
        "-MockupPath",
        str(mockup_path),
    )

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "failed_requires_mockup_redesign"
    assert result["mockup_redesign_triggers"] == ["constraints.no_wrist_bone_pressure"]
    assert result["mockup_capture_total_groups"] == 5
    assert result["mockup_capture_ready_groups"] == 4
    assert result["mockup_capture_failed_groups"] == 1
    assert result["mockup_capture_first_blocking_group_id"] == "mockup_global_safety_constraints"
    assert result["mockup_capture_first_blocking_group_status"] == "failed_stop_condition_or_blocking_signal"
    capture_status = {step["id"]: step for step in result["mockup_capture_plan_status"]}
    safety_status = capture_status["mockup_global_safety_constraints"]
    assert safety_status["ready_for_mockup_readiness"] is False
    assert safety_status["blocking_signals"] == ["constraints.no_wrist_bone_pressure"]
    assert result["mannequin_interface_test_ready"] is False
    assert result["pilot_testing_cleared"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_mockup_gate_rejects_ambiguous_constraint_text(tmp_path: Path) -> None:
    measurement_path = tmp_path / "ready-measurements.json"
    mockup_path = tmp_path / "ambiguous-mockup.json"
    measurement_path.write_text(json.dumps(_ready_measurement_payload()), encoding="utf-8")
    payload = _ready_mockup_payload(measurement_path)
    payload["constraints"]["no_inner_elbow_crossing"] = "yes"
    mockup_path.write_text(json.dumps(payload), encoding="utf-8")

    proc = _run_gate(
        "-Mode",
        "Status",
        "-MeasurementPath",
        str(measurement_path),
        "-MockupPath",
        str(mockup_path),
    )

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "failed_mockup_record"
    assert result["mockup_invalid_fields"] == ["constraints.no_inner_elbow_crossing"]
    assert result["mockup_redesign_triggers"] == []
    assert result["mannequin_interface_test_ready"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_mockup_gate_rejects_quoted_boolean_text(tmp_path: Path) -> None:
    measurement_path = tmp_path / "ready-measurements.json"
    mockup_path = tmp_path / "quoted-boolean-mockup.json"
    measurement_path.write_text(json.dumps(_ready_measurement_payload()), encoding="utf-8")
    payload = _ready_mockup_payload(measurement_path)
    payload["constraints"]["non_powered_only"] = "true"
    mockup_path.write_text(json.dumps(payload), encoding="utf-8")

    proc = _run_gate(
        "-Mode",
        "Status",
        "-MeasurementPath",
        str(measurement_path),
        "-MockupPath",
        str(mockup_path),
    )

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "failed_mockup_record"
    assert result["mockup_invalid_fields"] == ["constraints.non_powered_only"]
    assert result["mockup_redesign_triggers"] == []
    assert result["fr018_implementation_cleared"] is False
