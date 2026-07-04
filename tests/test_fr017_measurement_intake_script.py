from __future__ import annotations

import json
import shutil
from datetime import date, timedelta
from pathlib import Path

import pytest

from tests.powershell_script_runner import run_powershell_script


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "fr017-measurement-intake.ps1"


def _powershell() -> str:
    exe = shutil.which("pwsh") or shutil.which("powershell")
    if not exe:
        pytest.skip("PowerShell is not available")
    return exe


def _run_intake(*args: str):
    return run_powershell_script(
        _powershell(),
        SCRIPT,
        args,
        cwd=ROOT,
        timeout_seconds=20,
    )


def _payload(stdout: str) -> dict[str, object]:
    return json.loads(stdout)


def _assert_unique(values: list[object]) -> None:
    assert len(values) == len(set(values))


def _ready_measurement_payload() -> dict[str, object]:
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


def test_fr017_measurement_intake_reports_template_as_pending() -> None:
    proc = _run_intake("-Mode", "Status")

    assert proc.returncode == 0, proc.stderr
    payload = _payload(proc.stdout)
    assert payload["kind"] == "francis.fr017.measurement_intake"
    assert payload["status"] == "pending_measurements"
    assert payload["using_template"] is True
    assert payload["parse_ok"] is True
    assert payload["physical_validation_complete"] is False
    assert payload["fr018_implementation_cleared"] is False
    assert payload["read_only_contract"] is True
    assert payload["writes_repo"] is False
    assert payload["writes_data"] is False
    assert payload["grants_execution_authority"] is False
    assert payload["grants_mutation_authority"] is False
    assert (
        str(payload["measurement_input_template_path"])
        .replace("/", "\\")
        .endswith("FR-017_Stage17_Package\\FR-017-MEASUREMENTS-INPUT-TEMPLATE.json")
    )
    assert (
        str(payload["measurement_capture_runbook_path"])
        .replace("/", "\\")
        .endswith("FR-017_Stage17_Package\\FR-017-MEASUREMENT-CAPTURE-RUNBOOK.md")
    )
    assert (
        str(payload["measurement_record_initializer_path"])
        .replace("/", "\\")
        .endswith("scripts\\fr017-new-measurement-record.ps1")
    )
    assert payload["measurement_working_record_name_pattern"] == "FR-017-MEASUREMENTS-YYYY-MM-DD-PILOT-RECORD.json"
    assert payload["measurement_capture_plan_not_completion_evidence"] is True
    assert "not physical validation evidence" in payload["measurement_capture_plan_contract"]
    assert "not measurement evidence" in payload["measurement_capture_runbook_contract"]
    assert "FR-017-MEASUREMENT-CAPTURE-RUNBOOK.md" in payload["measurement_capture_runbook_contract"]
    assert "fr017-new-measurement-record.ps1" in payload["measurement_capture_runbook_contract"]
    assert (
        payload["next_required_physical_input"]
        == "create_pending_record_with_fr017-new-measurement-record.ps1_then_capture_with_FR-017-MEASUREMENT-CAPTURE-RUNBOOK.md_and_rerun_measurement_intake"
    )
    capture_plan = payload["measurement_capture_plan"]
    assert isinstance(capture_plan, list)
    assert [step["id"] for step in capture_plan] == [
        "setup_and_safety_brief",
        "left_arm_numeric_measurement_passes",
        "right_arm_numeric_measurement_passes",
        "safety_critical_landmark_and_zone_references",
        "left_right_independence_and_safety_screen",
    ]
    setup_step = capture_plan[0]
    assert setup_step["validation_state"] == "REQUIRES_MEASUREMENT"
    assert "evidence.measurement_tool" in setup_step["required_fields"]
    assert "measurement_conditions.stop_conditions_briefed" in setup_step["required_fields"]
    assert "tool_is_not_metric_or_millimeter_capable" in setup_step["stop_if"]
    safety_step = capture_plan[-1]
    assert "left_right_independence.values_not_copied_between_sides" in safety_step["required_fields"]
    assert "safety_screen.loss_of_grip_strength" in safety_step["required_fields"]
    assert "any_safety_screen_symptom_is_true" in safety_step["stop_if"]
    assert "intake readiness only" in payload["measurement_capture_plan_status_contract"]
    assert "not physical validation evidence" in payload["measurement_capture_summary_contract"]
    assert payload["measurement_capture_total_groups"] == 5
    assert payload["measurement_capture_ready_groups"] == 0
    assert payload["measurement_capture_pending_groups"] == 5
    assert payload["measurement_capture_invalid_groups"] == 0
    assert payload["measurement_capture_failed_groups"] == 0
    assert payload["measurement_capture_first_blocking_group_id"] == "setup_and_safety_brief"
    assert payload["measurement_capture_first_blocking_group_status"] == "pending_required_fields"
    assert "brief stop conditions" in payload["measurement_capture_first_blocking_group_action"]
    capture_plan_status = payload["measurement_capture_plan_status"]
    assert isinstance(capture_plan_status, list)
    assert [step["id"] for step in capture_plan_status] == [step["id"] for step in capture_plan]
    assert all(step["status"] == "pending_required_fields" for step in capture_plan_status)
    assert all(step["ready_for_measurement_intake"] is False for step in capture_plan_status)
    assert "evidence.date" in capture_plan_status[0]["missing_fields"]
    assert "repeatability.left.max_delta_mm" in capture_plan_status[1]["missing_fields"]
    assert "repeatability.right.max_delta_mm" in capture_plan_status[2]["missing_fields"]
    assert "marked_zones.left.wrist_bone_boundary" in capture_plan_status[3]["missing_fields"]
    assert "safety_screen.loss_of_grip_strength" in capture_plan_status[4]["missing_fields"]
    assert "evidence.date" in payload["missing_fields"]
    assert "evidence.pilot_id" in payload["missing_fields"]
    assert "evidence.measurement_tool" in payload["missing_fields"]
    assert "repeatability.left.second_pass_completed" in payload["missing_fields"]
    assert "repeatability.left.max_delta_mm" in payload["missing_fields"]
    assert "repeatability.left.all_required_measurements_within_5mm" in payload["missing_fields"]
    assert "left_right_independence.left_arm_measured_separately" in payload["missing_fields"]
    assert "left_right_independence.left_measurement_reference" in payload["missing_fields"]
    assert "measurement_conditions.no_tissue_compression_used" in payload["missing_fields"]
    assert "measurement_conditions.condition_notes" in payload["missing_fields"]
    assert "landmark_confirmation.inner_elbow_crease_boundary_confirmed" in payload["missing_fields"]
    assert "landmark_confirmation.landmark_notes" in payload["missing_fields"]
    assert "repeatability.right.second_pass_completed" in payload["missing_fields"]
    assert "repeatability.right.max_delta_mm" in payload["missing_fields"]
    assert "repeatability.right.all_required_measurements_within_5mm" in payload["missing_fields"]
    missing_fields = payload["missing_fields"]
    assert isinstance(missing_fields, list)
    _assert_unique(missing_fields)
    assert missing_fields.count("left_right_independence.independence_notes") == 1
    assert missing_fields.count("measurement_conditions.condition_notes") == 1
    assert missing_fields.count("landmark_confirmation.landmark_notes") == 1


def test_fr017_measurement_intake_fails_closed_when_file_missing(tmp_path: Path) -> None:
    proc = _run_intake("-Mode", "Status", "-MeasurementPath", str(tmp_path / "missing.json"))

    assert proc.returncode == 1
    payload = _payload(proc.stdout)
    assert payload["status"] == "missing_measurement_file"
    assert payload["parse_ok"] is False
    assert payload["physical_validation_complete"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_measurement_intake_classifies_incomplete_input(tmp_path: Path) -> None:
    measurement_path = tmp_path / "incomplete.json"
    payload = _ready_measurement_payload()
    del payload["sides"]["left"]["wrist_clearance_gap"]  # type: ignore[index]
    measurement_path.write_text(json.dumps(payload), encoding="utf-8")

    proc = _run_intake("-Mode", "Status", "-MeasurementPath", str(measurement_path))

    assert proc.returncode == 0
    result = _payload(proc.stdout)
    assert result["status"] == "pending_measurements"
    assert result["physical_validation_complete"] is False
    assert "sides.left.wrist_clearance_gap" in result["missing_fields"]


def test_fr017_measurement_intake_requires_pilot_id_and_tool(tmp_path: Path) -> None:
    measurement_path = tmp_path / "missing-pilot-tool.json"
    payload = _ready_measurement_payload()
    del payload["evidence"]["pilot_id"]  # type: ignore[index]
    del payload["evidence"]["measurement_tool"]  # type: ignore[index]
    measurement_path.write_text(json.dumps(payload), encoding="utf-8")

    proc = _run_intake("-Mode", "Status", "-MeasurementPath", str(measurement_path))

    assert proc.returncode == 0
    result = _payload(proc.stdout)
    assert result["status"] == "pending_measurements"
    assert "evidence.pilot_id" in result["missing_fields"]
    assert "evidence.measurement_tool" in result["missing_fields"]
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_measurement_intake_treats_lowercase_or_padded_pending_text_as_missing(
    tmp_path: Path,
) -> None:
    measurement_path = tmp_path / "placeholder-text.json"
    payload = _ready_measurement_payload()
    payload["evidence"]["observer"] = " pending "  # type: ignore[index]
    payload["evidence"]["pilot_id"] = "pending"  # type: ignore[index]
    payload["marked_zones"]["left"]["glove_removal_path"] = " pending "  # type: ignore[index]
    payload["left_right_independence"]["left_measurement_reference"] = "pending"  # type: ignore[index]
    payload["measurement_conditions"]["condition_notes"] = " PENDING "  # type: ignore[index]
    measurement_path.write_text(json.dumps(payload), encoding="utf-8")

    proc = _run_intake("-Mode", "Status", "-MeasurementPath", str(measurement_path))

    assert proc.returncode == 0
    result = _payload(proc.stdout)
    assert result["status"] == "pending_measurements"
    assert result["invalid_fields"] == []
    assert result["measurement_note_blockers"] == []
    assert "evidence.observer" in result["missing_fields"]
    assert "evidence.pilot_id" in result["missing_fields"]
    assert "marked_zones.left.glove_removal_path" in result["missing_fields"]
    assert "left_right_independence.left_measurement_reference" in result["missing_fields"]
    assert "measurement_conditions.condition_notes" in result["missing_fields"]
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_measurement_intake_accepts_complete_symptom_free_input(tmp_path: Path) -> None:
    measurement_path = tmp_path / "ready.json"
    measurement_path.write_text(json.dumps(_ready_measurement_payload()), encoding="utf-8")

    proc = _run_intake("-Mode", "Status", "-MeasurementPath", str(measurement_path))

    assert proc.returncode == 0, proc.stderr
    payload = _payload(proc.stdout)
    assert payload["status"] == "ready_for_non_powered_mockup_patterning"
    assert payload["missing_fields"] == []
    assert payload["invalid_fields"] == []
    assert payload["measurement_consistency_violations"] == []
    assert payload["marked_zone_specificity_violations"] == []
    assert payload["repeatability_blockers"] == []
    assert payload["left_right_independence_blockers"] == []
    assert payload["measurement_condition_blockers"] == []
    assert payload["landmark_confirmation_blockers"] == []
    assert payload["measurement_note_blockers"] == []
    assert payload["safety_blockers"] == []
    assert "intake readiness only" in payload["measurement_capture_plan_status_contract"]
    assert payload["measurement_capture_total_groups"] == 5
    assert payload["measurement_capture_ready_groups"] == 5
    assert payload["measurement_capture_pending_groups"] == 0
    assert payload["measurement_capture_invalid_groups"] == 0
    assert payload["measurement_capture_failed_groups"] == 0
    assert payload["measurement_capture_first_blocking_group_id"] == ""
    assert payload["measurement_capture_first_blocking_group_status"] == ""
    assert payload["measurement_capture_first_blocking_group_action"] == ""
    assert [step["status"] for step in payload["measurement_capture_plan_status"]] == [
        "ready_for_measurement_intake_review",
        "ready_for_measurement_intake_review",
        "ready_for_measurement_intake_review",
        "ready_for_measurement_intake_review",
        "ready_for_measurement_intake_review",
    ]
    assert all(step["ready_for_measurement_intake"] is True for step in payload["measurement_capture_plan_status"])
    assert payload["measurement_bounds_mm"]["wrist_clearance_gap"]["min"] == 10
    assert "YYYY-MM-DD" in payload["evidence_date_contract"]
    assert "metric" in payload["measurement_tool_contract"]
    assert "millimeter" in payload["measurement_tool_contract"]
    assert "imperial/negated metric" in payload["measurement_tool_contract"]
    assert "no tissue compression" in payload["measurement_method_contract"]
    assert "with-compression" in payload["measurement_method_exclusions_contract"]
    assert "palm neutral" in payload["measurement_posture_contract"]
    assert "under-load collection language" in payload["measurement_posture_exclusions_contract"]
    assert "case-insensitively" in payload["placeholder_value_contract"]
    assert "Use unquoted JSON numbers" in payload["measurement_number_value_contract"]
    assert "broad human-scale sanity checks only" in payload["measurement_bounds_contract"]
    assert "not fit approval" in payload["measurement_consistency_contract"]
    assert (
        "Left and right marked-zone evidence references must be distinct" in payload["marked_zone_specificity_contract"]
    )
    assert "Left and right arms must be measured independently" in payload["left_right_independence_contract"]
    assert (
        "Measurement collection must explicitly confirm no tissue compression"
        in payload["measurement_condition_contract"]
    )
    assert "Safety-critical forearm landmarks must be visibly confirmed" in payload["landmark_confirmation_contract"]
    assert "Measurement evidence notes must be specific enough" in payload["measurement_note_contract"]
    assert "second-pass confirmation" in payload["repeatability_value_contract"]
    assert payload["repeatability_max_delta_mm"] == 5
    assert payload["required_repeatability_fields"] == [
        "second_pass_completed",
        "max_delta_mm",
        "all_required_measurements_within_5mm",
    ]
    assert payload["required_left_right_independence_true_fields"] == [
        "left_arm_measured_separately",
        "right_arm_measured_separately",
        "side_labels_verified",
        "values_not_copied_between_sides",
    ]
    assert payload["required_left_right_independence_note_fragments"] == [
        "left",
        "right",
        "separate",
        "side label",
    ]
    assert payload["required_measurement_condition_true_fields"] == [
        "no_tissue_compression_used",
        "no_wrist_bone_compression_used",
        "metric_tool_used",
        "arm_relaxed_palm_neutral_or_exception_recorded",
        "stop_conditions_briefed",
    ]
    assert payload["required_measurement_condition_note_fragments"] == [
        "no tissue",
        "wrist",
        "metric",
        "stop",
    ]
    assert payload["required_landmark_confirmation_true_fields"] == [
        "inner_elbow_crease_boundary_confirmed",
        "wrist_bone_boundary_confirmed",
        "radius_ulna_relief_paths_confirmed",
        "outer_forearm_cable_route_confirmed",
        "quick_release_reach_zone_confirmed",
        "glove_removal_path_confirmed",
        "skin_safe_marking_used",
    ]
    assert payload["required_landmark_confirmation_note_fragments"] == [
        "inner elbow",
        "wrist",
        "radius",
        "ulna",
        "cable",
        "quick",
        "release",
        "glove",
        "skin",
        "safe",
    ]
    assert payload["excluded_measurement_method_patterns"] == [
        "\\bcalipers?\\b",
        "hard\\s+calipers?",
        "rigid\\s+calipers?",
        "with\\s+(?:tissue\\s+)?compression",
        "under\\s+(?:tissue\\s+)?compression",
        "\\bcompressive\\b",
    ]
    assert payload["excluded_measurement_posture_patterns"] == [
        "under\\s+load",
        "\\bloaded\\b",
        "\\bweighted\\b",
        "\\bforced\\b",
        "\\bclench(?:ed|ing)?\\b",
        "\\bgripping\\b",
    ]
    assert payload["physical_validation_complete"] is False
    assert payload["fr018_implementation_cleared"] is False
    assert "run_mannequin_interface_test_before_pilot_motion" in payload["next_actions"]


def test_fr017_measurement_intake_rejects_non_mm_units(tmp_path: Path) -> None:
    measurement_path = tmp_path / "inch-units.json"
    payload = _ready_measurement_payload()
    payload["units"] = "in"
    measurement_path.write_text(json.dumps(payload), encoding="utf-8")

    proc = _run_intake("-Mode", "Status", "-MeasurementPath", str(measurement_path))

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "invalid_measurement_record"
    assert result["invalid_fields"] == ["units"]
    assert result["units_required"] == "mm"
    assert 'must be exactly "mm"' in result["units_value_contract"]
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_measurement_intake_rejects_unsafe_measurement_method_text(tmp_path: Path) -> None:
    measurement_path = tmp_path / "unsafe-method.json"
    payload = _ready_measurement_payload()
    payload["evidence"]["method"] = "hard calipers with compression"  # type: ignore[index]
    measurement_path.write_text(json.dumps(payload), encoding="utf-8")

    proc = _run_intake("-Mode", "Status", "-MeasurementPath", str(measurement_path))

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "invalid_measurement_record"
    assert result["invalid_fields"] == ["evidence.method"]
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_measurement_intake_rejects_compressive_method_with_required_baseline_text(
    tmp_path: Path,
) -> None:
    measurement_path = tmp_path / "compressive-baseline-method.json"
    payload = _ready_measurement_payload()
    payload["evidence"]["method"] = "flexible tape, no tissue compression, then hard calipers with compression"  # type: ignore[index]
    measurement_path.write_text(json.dumps(payload), encoding="utf-8")

    proc = _run_intake("-Mode", "Status", "-MeasurementPath", str(measurement_path))

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "invalid_measurement_record"
    assert result["invalid_fields"] == ["evidence.method"]
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_measurement_intake_rejects_non_metric_measurement_tool_text(tmp_path: Path) -> None:
    measurement_path = tmp_path / "non-metric-tool.json"
    payload = _ready_measurement_payload()
    payload["evidence"]["measurement_tool"] = "inch tape"  # type: ignore[index]
    measurement_path.write_text(json.dumps(payload), encoding="utf-8")

    proc = _run_intake("-Mode", "Status", "-MeasurementPath", str(measurement_path))

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "invalid_measurement_record"
    assert result["invalid_fields"] == ["evidence.measurement_tool"]
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_measurement_intake_rejects_contradictory_metric_tool_text(tmp_path: Path) -> None:
    measurement_path = tmp_path / "contradictory-metric-tool.json"
    payload = _ready_measurement_payload()
    payload["evidence"]["measurement_tool"] = "non-metric inch tape with mm marks"  # type: ignore[index]
    measurement_path.write_text(json.dumps(payload), encoding="utf-8")

    proc = _run_intake("-Mode", "Status", "-MeasurementPath", str(measurement_path))

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "invalid_measurement_record"
    assert result["invalid_fields"] == ["evidence.measurement_tool"]
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_measurement_intake_rejects_unsafe_measurement_posture_text(tmp_path: Path) -> None:
    measurement_path = tmp_path / "unsafe-posture.json"
    payload = _ready_measurement_payload()
    payload["evidence"]["posture"] = "wrist flexed under load"  # type: ignore[index]
    measurement_path.write_text(json.dumps(payload), encoding="utf-8")

    proc = _run_intake("-Mode", "Status", "-MeasurementPath", str(measurement_path))

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "invalid_measurement_record"
    assert result["invalid_fields"] == ["evidence.posture"]
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_measurement_intake_rejects_loaded_posture_with_required_baseline_text(
    tmp_path: Path,
) -> None:
    measurement_path = tmp_path / "loaded-baseline-posture.json"
    payload = _ready_measurement_payload()
    payload["evidence"]["posture"] = "arm relaxed, palm neutral, weighted grip under load"  # type: ignore[index]
    measurement_path.write_text(json.dumps(payload), encoding="utf-8")

    proc = _run_intake("-Mode", "Status", "-MeasurementPath", str(measurement_path))

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "invalid_measurement_record"
    assert result["invalid_fields"] == ["evidence.posture"]
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_measurement_intake_rejects_malformed_evidence_date(tmp_path: Path) -> None:
    measurement_path = tmp_path / "malformed-date.json"
    payload = _ready_measurement_payload()
    payload["evidence"]["date"] = "06/23/2026"  # type: ignore[index]
    measurement_path.write_text(json.dumps(payload), encoding="utf-8")

    proc = _run_intake("-Mode", "Status", "-MeasurementPath", str(measurement_path))

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "invalid_measurement_record"
    assert result["invalid_fields"] == ["evidence.date"]
    assert "YYYY-MM-DD" in result["evidence_date_contract"]
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_measurement_intake_rejects_future_evidence_date(tmp_path: Path) -> None:
    measurement_path = tmp_path / "future-date.json"
    payload = _ready_measurement_payload()
    payload["evidence"]["date"] = (date.today() + timedelta(days=1)).isoformat()  # type: ignore[index]
    measurement_path.write_text(json.dumps(payload), encoding="utf-8")

    proc = _run_intake("-Mode", "Status", "-MeasurementPath", str(measurement_path))

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "invalid_measurement_record"
    assert result["invalid_fields"] == ["evidence.date"]
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_measurement_intake_rejects_copied_left_right_zone_references(tmp_path: Path) -> None:
    measurement_path = tmp_path / "copied-zone-reference.json"
    payload = _ready_measurement_payload()
    payload["marked_zones"]["right"]["wrist_bone_boundary"] = payload["marked_zones"]["left"][  # type: ignore[index]
        "wrist_bone_boundary"
    ]
    measurement_path.write_text(json.dumps(payload), encoding="utf-8")

    proc = _run_intake("-Mode", "Status", "-MeasurementPath", str(measurement_path))

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "invalid_measurement_record"
    assert result["invalid_fields"] == []
    assert result["marked_zone_specificity_violations"] == [
        "marked_zones.wrist_bone_boundary_left_right_references_must_be_distinct"
    ]
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_measurement_intake_rejects_non_independent_left_right_measurements(tmp_path: Path) -> None:
    measurement_path = tmp_path / "copied-left-right-measurements.json"
    payload = _ready_measurement_payload()
    payload["left_right_independence"]["values_not_copied_between_sides"] = False  # type: ignore[index]
    measurement_path.write_text(json.dumps(payload), encoding="utf-8")

    proc = _run_intake("-Mode", "Status", "-MeasurementPath", str(measurement_path))

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "invalid_measurement_record"
    assert result["left_right_independence_blockers"] == [
        "left_right_independence.values_not_copied_between_sides_must_be_true"
    ]
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_measurement_intake_rejects_identical_left_right_numeric_profile(tmp_path: Path) -> None:
    measurement_path = tmp_path / "identical-left-right-measurements.json"
    payload = _ready_measurement_payload()
    payload["sides"]["right"] = dict(payload["sides"]["left"])  # type: ignore[index]
    measurement_path.write_text(json.dumps(payload), encoding="utf-8")

    proc = _run_intake("-Mode", "Status", "-MeasurementPath", str(measurement_path))

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "invalid_measurement_record"
    assert result["left_right_independence_blockers"] == [
        "left_right_independence.all_required_numeric_measurements_identical_requires_recheck"
    ]
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_measurement_intake_rejects_tissue_compression_condition(tmp_path: Path) -> None:
    measurement_path = tmp_path / "tissue-compression.json"
    payload = _ready_measurement_payload()
    payload["measurement_conditions"]["no_tissue_compression_used"] = False  # type: ignore[index]
    measurement_path.write_text(json.dumps(payload), encoding="utf-8")

    proc = _run_intake("-Mode", "Status", "-MeasurementPath", str(measurement_path))

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "invalid_measurement_record"
    assert result["measurement_condition_blockers"] == [
        "measurement_conditions.no_tissue_compression_used_must_be_true"
    ]
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_measurement_intake_rejects_quoted_condition_boolean(tmp_path: Path) -> None:
    measurement_path = tmp_path / "quoted-condition.json"
    payload = _ready_measurement_payload()
    payload["measurement_conditions"]["metric_tool_used"] = "true"  # type: ignore[index]
    measurement_path.write_text(json.dumps(payload), encoding="utf-8")

    proc = _run_intake("-Mode", "Status", "-MeasurementPath", str(measurement_path))

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "invalid_measurement_record"
    assert result["invalid_fields"] == ["measurement_conditions.metric_tool_used"]
    assert result["measurement_condition_blockers"] == []
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_measurement_intake_rejects_generic_measurement_notes(tmp_path: Path) -> None:
    measurement_path = tmp_path / "generic-notes.json"
    payload = _ready_measurement_payload()
    payload["left_right_independence"]["independence_notes"] = "Fixture complete."  # type: ignore[index]
    payload["measurement_conditions"]["condition_notes"] = "Fixture complete."  # type: ignore[index]
    payload["landmark_confirmation"]["landmark_notes"] = "Fixture complete."  # type: ignore[index]
    measurement_path.write_text(json.dumps(payload), encoding="utf-8")

    proc = _run_intake("-Mode", "Status", "-MeasurementPath", str(measurement_path))

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "invalid_measurement_record"
    assert result["invalid_fields"] == []
    assert result["measurement_note_blockers"] == [
        "left_right_independence.independence_notes_must_reference_left",
        "left_right_independence.independence_notes_must_reference_right",
        "left_right_independence.independence_notes_must_reference_separate",
        "left_right_independence.independence_notes_must_reference_side_label",
        "measurement_conditions.condition_notes_must_reference_no_tissue",
        "measurement_conditions.condition_notes_must_reference_wrist",
        "measurement_conditions.condition_notes_must_reference_metric",
        "measurement_conditions.condition_notes_must_reference_stop",
        "landmark_confirmation.landmark_notes_must_reference_inner_elbow",
        "landmark_confirmation.landmark_notes_must_reference_wrist",
        "landmark_confirmation.landmark_notes_must_reference_radius",
        "landmark_confirmation.landmark_notes_must_reference_ulna",
        "landmark_confirmation.landmark_notes_must_reference_cable",
        "landmark_confirmation.landmark_notes_must_reference_quick",
        "landmark_confirmation.landmark_notes_must_reference_release",
        "landmark_confirmation.landmark_notes_must_reference_glove",
        "landmark_confirmation.landmark_notes_must_reference_skin",
        "landmark_confirmation.landmark_notes_must_reference_safe",
    ]
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_measurement_intake_rejects_unconfirmed_landmark(tmp_path: Path) -> None:
    measurement_path = tmp_path / "unconfirmed-landmark.json"
    payload = _ready_measurement_payload()
    payload["landmark_confirmation"]["wrist_bone_boundary_confirmed"] = False  # type: ignore[index]
    measurement_path.write_text(json.dumps(payload), encoding="utf-8")

    proc = _run_intake("-Mode", "Status", "-MeasurementPath", str(measurement_path))

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "invalid_measurement_record"
    assert result["landmark_confirmation_blockers"] == [
        "landmark_confirmation.wrist_bone_boundary_confirmed_must_be_true"
    ]
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_measurement_intake_rejects_quoted_landmark_boolean(tmp_path: Path) -> None:
    measurement_path = tmp_path / "quoted-landmark.json"
    payload = _ready_measurement_payload()
    payload["landmark_confirmation"]["skin_safe_marking_used"] = "true"  # type: ignore[index]
    measurement_path.write_text(json.dumps(payload), encoding="utf-8")

    proc = _run_intake("-Mode", "Status", "-MeasurementPath", str(measurement_path))

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "invalid_measurement_record"
    assert result["invalid_fields"] == ["landmark_confirmation.skin_safe_marking_used"]
    assert result["landmark_confirmation_blockers"] == []
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_measurement_intake_rejects_quoted_repeatability_boolean(tmp_path: Path) -> None:
    measurement_path = tmp_path / "quoted-repeatability-bool.json"
    payload = _ready_measurement_payload()
    payload["repeatability"]["left"]["second_pass_completed"] = "true"  # type: ignore[index]
    measurement_path.write_text(json.dumps(payload), encoding="utf-8")

    proc = _run_intake("-Mode", "Status", "-MeasurementPath", str(measurement_path))

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "invalid_measurement_record"
    assert result["invalid_fields"] == ["repeatability.left.second_pass_completed"]
    assert result["repeatability_blockers"] == []
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_measurement_intake_rejects_excess_repeatability_delta(tmp_path: Path) -> None:
    measurement_path = tmp_path / "excess-repeatability-delta.json"
    payload = _ready_measurement_payload()
    payload["repeatability"]["right"]["max_delta_mm"] = 6  # type: ignore[index]
    measurement_path.write_text(json.dumps(payload), encoding="utf-8")

    proc = _run_intake("-Mode", "Status", "-MeasurementPath", str(measurement_path))

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "invalid_measurement_record"
    assert result["invalid_fields"] == []
    assert result["repeatability_blockers"] == ["repeatability.right.max_delta_mm_exceeds_5mm_limit"]
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_measurement_intake_rejects_quoted_repeatability_delta(tmp_path: Path) -> None:
    measurement_path = tmp_path / "quoted-repeatability-delta.json"
    payload = _ready_measurement_payload()
    payload["repeatability"]["left"]["max_delta_mm"] = "3"  # type: ignore[index]
    measurement_path.write_text(json.dumps(payload), encoding="utf-8")

    proc = _run_intake("-Mode", "Status", "-MeasurementPath", str(measurement_path))

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "invalid_measurement_record"
    assert result["invalid_fields"] == ["repeatability.left.max_delta_mm"]
    assert result["repeatability_blockers"] == []
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_measurement_intake_rejects_incomplete_second_pass(tmp_path: Path) -> None:
    measurement_path = tmp_path / "incomplete-second-pass.json"
    payload = _ready_measurement_payload()
    payload["repeatability"]["left"]["all_required_measurements_within_5mm"] = False  # type: ignore[index]
    measurement_path.write_text(json.dumps(payload), encoding="utf-8")

    proc = _run_intake("-Mode", "Status", "-MeasurementPath", str(measurement_path))

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "invalid_measurement_record"
    assert result["repeatability_blockers"] == ["repeatability.left.all_required_measurements_within_5mm_must_be_true"]
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_measurement_intake_rejects_quoted_false_safety_values(tmp_path: Path) -> None:
    measurement_path = tmp_path / "quoted-false.json"
    payload = _ready_measurement_payload()
    payload["safety_screen"] = {key: "false" for key in payload["safety_screen"]}  # type: ignore[index]
    measurement_path.write_text(json.dumps(payload), encoding="utf-8")

    proc = _run_intake("-Mode", "Status", "-MeasurementPath", str(measurement_path))

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "invalid_measurement_record"
    assert result["invalid_fields"] == [
        f"safety_screen.{field}"
        for field in [
            "pain",
            "tingling",
            "numbness",
            "cold_fingers",
            "discoloration",
            "hand_weakness",
            "wrist_pain",
            "sharp_pressure",
            "reduced_finger_motion",
            "loss_of_grip_strength",
        ]
    ]
    assert result["safety_blockers"] == []
    assert "Use unquoted JSON boolean false" in result["safety_screen_value_contract"]


def test_fr017_measurement_intake_blocks_symptom_positive_input(tmp_path: Path) -> None:
    measurement_path = tmp_path / "symptom.json"
    payload = _ready_measurement_payload()
    payload["safety_screen"]["tingling"] = True  # type: ignore[index]
    measurement_path.write_text(json.dumps(payload), encoding="utf-8")

    proc = _run_intake("-Mode", "Status", "-MeasurementPath", str(measurement_path))

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "failed_requires_redesign_or_medical_review"
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False
    assert result["safety_blockers"] == ["tingling"]
    assert result["measurement_capture_total_groups"] == 5
    assert result["measurement_capture_ready_groups"] == 4
    assert result["measurement_capture_failed_groups"] == 1
    assert result["measurement_capture_first_blocking_group_id"] == "left_right_independence_and_safety_screen"
    assert result["measurement_capture_first_blocking_group_status"] == "failed_stop_condition_or_blocking_signal"
    capture_status = {step["id"]: step for step in result["measurement_capture_plan_status"]}
    safety_status = capture_status["left_right_independence_and_safety_screen"]
    assert safety_status["status"] == "failed_stop_condition_or_blocking_signal"
    assert safety_status["ready_for_measurement_intake"] is False
    assert safety_status["blocking_signals"] == ["safety_screen.tingling"]


def test_fr017_measurement_intake_safety_symptom_overrides_pending_measurement_fields(
    tmp_path: Path,
) -> None:
    measurement_path = tmp_path / "symptom-with-missing-fields.json"
    payload = _ready_measurement_payload()
    del payload["evidence"]["observer"]  # type: ignore[index]
    payload["safety_screen"]["tingling"] = True  # type: ignore[index]
    measurement_path.write_text(json.dumps(payload), encoding="utf-8")

    proc = _run_intake("-Mode", "Status", "-MeasurementPath", str(measurement_path))

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "failed_requires_redesign_or_medical_review"
    assert "evidence.observer" in result["missing_fields"]
    assert result["safety_blockers"] == ["tingling"]
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_measurement_intake_rejects_ambiguous_safety_text(tmp_path: Path) -> None:
    measurement_path = tmp_path / "ambiguous-safety.json"
    payload = _ready_measurement_payload()
    payload["safety_screen"]["pain"] = "no"  # type: ignore[index]
    measurement_path.write_text(json.dumps(payload), encoding="utf-8")

    proc = _run_intake("-Mode", "Status", "-MeasurementPath", str(measurement_path))

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "invalid_measurement_record"
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False
    assert result["invalid_fields"] == ["safety_screen.pain"]
    assert result["safety_blockers"] == []


def test_fr017_measurement_intake_rejects_out_of_bounds_measurement(tmp_path: Path) -> None:
    measurement_path = tmp_path / "out-of-bounds.json"
    payload = _ready_measurement_payload()
    payload["sides"]["left"]["forearm_circumference_mid_forearm"] = 5  # type: ignore[index]
    measurement_path.write_text(json.dumps(payload), encoding="utf-8")

    proc = _run_intake("-Mode", "Status", "-MeasurementPath", str(measurement_path))

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "invalid_measurement_record"
    assert result["invalid_fields"] == ["sides.left.forearm_circumference_mid_forearm"]
    assert result["measurement_consistency_violations"] == []
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_measurement_intake_rejects_quoted_numeric_measurement(tmp_path: Path) -> None:
    measurement_path = tmp_path / "quoted-numeric.json"
    payload = _ready_measurement_payload()
    payload["sides"]["left"]["forearm_length_elbow_crease_to_wrist_crease"] = "258"  # type: ignore[index]
    measurement_path.write_text(json.dumps(payload), encoding="utf-8")

    proc = _run_intake("-Mode", "Status", "-MeasurementPath", str(measurement_path))

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "invalid_measurement_record"
    assert result["invalid_fields"] == ["sides.left.forearm_length_elbow_crease_to_wrist_crease"]
    assert result["measurement_consistency_violations"] == []
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_measurement_intake_rejects_contradictory_measurements(tmp_path: Path) -> None:
    measurement_path = tmp_path / "contradictory.json"
    payload = _ready_measurement_payload()
    payload["sides"]["right"]["outer_forearm_usable_panel_length"] = 300  # type: ignore[index]
    payload["sides"]["right"]["forearm_length_elbow_crease_to_wrist_crease"] = 250  # type: ignore[index]
    measurement_path.write_text(json.dumps(payload), encoding="utf-8")

    proc = _run_intake("-Mode", "Status", "-MeasurementPath", str(measurement_path))

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "invalid_measurement_record"
    assert result["invalid_fields"] == []
    assert result["measurement_consistency_violations"] == [
        "sides.right.outer_forearm_usable_panel_length_must_be_less_than_sides.right.forearm_length_elbow_crease_to_wrist_crease"
    ]
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False
