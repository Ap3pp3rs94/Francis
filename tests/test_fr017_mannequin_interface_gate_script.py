from __future__ import annotations

import json
import shutil
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest

from tests.powershell_script_runner import run_powershell_script
from tests.test_fr017_mockup_readiness_gate_script import (
    _ready_measurement_payload,
    _ready_mockup_payload,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "fr017-mannequin-interface-gate.ps1"


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
        timeout_seconds=30,
    )


def _payload(stdout: str) -> dict[str, Any]:
    return json.loads(stdout)


def _capture_status_by_id(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {step["id"]: step for step in payload["mannequin_capture_plan_status"]}


def _ready_mannequin_payload(mockup_path: Path) -> dict[str, Any]:
    interface_pass = {
        "mock_installed": True,
        "clearance_passed": True,
        "notes": "clearance verified against non-powered mock geometry",
    }
    return {
        "kind": "francis.fr017.mannequin_interface_test.v1",
        "component": "FR-017 Forearm Cuffs",
        "evidence": {
            "date": "2026-06-23",
            "observer": "test-observer",
            "mockup_readiness_record_path": str(mockup_path),
            "mannequin_or_arm_form_id": "test-arm-form-rev-a",
            "future_interface_mock_geometry_revision": "ghosted-interface-rev-a",
            "cable_sleeve_mock_id": "outer-sleeve-rev-a",
        },
        "test_article": {
            "left_cuff_revision": "left-soft-cuff-rev-a",
            "right_cuff_revision": "right-soft-cuff-rev-a",
            "non_powered_only": True,
        },
        "interfaces": {
            "fr032_left_forearm_frame": dict(interface_pass),
            "fr033_right_forearm_frame": dict(interface_pass),
            "fr043_left_elbow_joint": dict(interface_pass),
            "fr044_right_elbow_joint": dict(interface_pass),
            "fr045_left_wrist_joint": dict(interface_pass),
            "fr046_right_wrist_joint": dict(interface_pass),
            "fr066_left_glove_base": dict(interface_pass),
            "fr067_right_glove_base": dict(interface_pass),
            "fr068_palm_interface_ring": dict(interface_pass),
            "fr184_forearm_armor": dict(interface_pass),
        },
        "cable_sensor_checks": {
            "fr163_outer_route_only": True,
            "fr069_no_pressure_or_palm_crossing": True,
            "fr070_no_powered_anchoring": True,
            "fr145_no_raised_hard_spot": True,
            "fr149_no_pressure_zone_placement": True,
        },
        "release_checks": {
            "left_release_visible_and_reachable": True,
            "right_release_visible_and_reachable": True,
            "armor_does_not_hide_release": True,
            "glove_and_wrist_removal_paths_open": True,
        },
        "fail_observations": {
            "snag_detected": False,
            "compression_detected": False,
            "release_hidden": False,
            "wrist_path_blocked": False,
            "glove_path_blocked": False,
            "cable_inner_elbow_crossing": False,
            "cable_wrist_bone_crossing": False,
            "cable_palm_or_grip_crossing": False,
        },
    }


def _write_upstream_ready_records(tmp_path: Path) -> tuple[Path, Path]:
    measurement_path = tmp_path / "ready-measurements.json"
    mockup_path = tmp_path / "ready-mockup.json"
    measurement_path.write_text(json.dumps(_ready_measurement_payload()), encoding="utf-8")
    mockup_path.write_text(json.dumps(_ready_mockup_payload(measurement_path)), encoding="utf-8")
    return measurement_path, mockup_path


def test_fr017_mannequin_gate_reports_default_templates_as_pending_upstream() -> None:
    proc = _run_gate("-Mode", "Status")

    assert proc.returncode == 0, proc.stderr
    payload = _payload(proc.stdout)
    assert payload["kind"] == "francis.fr017.mannequin_interface_gate"
    assert payload["status"] == "pending_mockup_readiness"
    assert payload["upstream_mockup_status"] == "pending_measurement_intake"
    assert payload["upstream_mockup_gate_ready"] is False
    assert payload["physical_validation_complete"] is False
    assert payload["stage17_completion_claim_allowed"] is False
    assert payload["mannequin_interface_test_complete"] is False
    assert payload["pilot_static_fit_planning_ready"] is False
    assert payload["pilot_testing_cleared"] is False
    assert payload["fr018_implementation_cleared"] is False
    assert payload["read_only_contract"] is True
    assert payload["writes_repo"] is False
    assert payload["grants_mutation_authority"] is False
    assert payload["mannequin_capture_plan_not_completion_evidence"] is True
    assert "not physical validation evidence" in payload["mannequin_capture_plan_contract"]
    assert "mannequin interface capture readiness only" in payload["mannequin_capture_plan_status_contract"]
    assert "not physical validation evidence" in payload["mannequin_capture_summary_contract"]
    assert "operator input tooling only" in payload["mannequin_capture_runbook_contract"]
    assert "fr017-new-mannequin-interface-record.ps1" in payload["mannequin_capture_runbook_contract"]
    assert payload["next_required_mannequin_input"] == (
        "create_non_powered_mannequin_interface_record_with_fr017-new-mannequin-interface-record.ps1_then_rerun_mannequin_interface_gate"
    )
    assert (
        str(payload["mannequin_input_template_path"])
        .replace("/", "\\")
        .endswith("FR-017_Stage17_Package\\FR-017-MANNEQUIN-INTERFACE-INPUT-TEMPLATE.json")
    )
    assert (
        str(payload["mannequin_record_initializer_path"])
        .replace("/", "\\")
        .endswith("scripts\\fr017-new-mannequin-interface-record.ps1")
    )
    assert payload["mannequin_working_record_name_pattern"] == "FR-017-MANNEQUIN-YYYY-MM-DD-PILOT-RECORD.json"
    assert payload["mannequin_capture_total_groups"] == 5
    assert payload["mannequin_capture_ready_groups"] == 0
    assert payload["mannequin_capture_pending_groups"] == 0
    assert payload["mannequin_capture_invalid_groups"] == 0
    assert payload["mannequin_capture_failed_groups"] == 0
    assert payload["mannequin_capture_upstream_blocked_groups"] == 5
    assert payload["mannequin_capture_first_blocking_group_id"] == "mannequin_evidence_and_linkage"
    assert payload["mannequin_capture_first_blocking_group_status"] == "blocked_by_upstream_mockup_readiness"
    assert "mockup readiness" in payload["mannequin_capture_first_blocking_group_action"]
    capture_plan = payload["mannequin_capture_plan"]
    assert [step["id"] for step in capture_plan] == [
        "mannequin_evidence_and_linkage",
        "mannequin_test_article",
        "mannequin_future_interface_clearance",
        "mannequin_cable_sensor_and_release_checks",
        "mannequin_fail_observation_screen",
    ]
    assert "evidence.mockup_readiness_record_path" in capture_plan[0]["required_fields"]
    assert "interfaces.fr184_forearm_armor.clearance_passed" in capture_plan[2]["required_fields"]
    assert "fail_observations.cable_palm_or_grip_crossing" in capture_plan[4]["required_fields"]
    capture_status = payload["mannequin_capture_plan_status"]
    assert [step["id"] for step in capture_status] == [step["id"] for step in capture_plan]
    assert all(step["status"] == "blocked_by_upstream_mockup_readiness" for step in capture_status)
    assert all(step["ready_for_mannequin_interface"] is False for step in capture_status)


def test_fr017_mannequin_gate_requires_test_record_after_mockup_ready(tmp_path: Path) -> None:
    measurement_path, mockup_path = _write_upstream_ready_records(tmp_path)

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
    assert payload["status"] == "pending_mannequin_interface_test"
    assert payload["upstream_mockup_status"] == "ready_for_mannequin_interface_test"
    assert payload["upstream_mockup_gate_ready"] is True
    assert payload["next_required_mannequin_input"] == (
        "create_non_powered_mannequin_interface_record_with_fr017-new-mannequin-interface-record.ps1_then_rerun_mannequin_interface_gate"
    )
    assert "evidence.date" in payload["missing_fields"]
    assert payload["mannequin_interface_test_complete"] is False
    assert payload["pilot_testing_cleared"] is False
    assert payload["fr018_implementation_cleared"] is False
    assert payload["mannequin_capture_plan_not_completion_evidence"] is True
    assert payload["mannequin_capture_total_groups"] == 5
    assert payload["mannequin_capture_ready_groups"] == 0
    assert payload["mannequin_capture_pending_groups"] == 5
    assert payload["mannequin_capture_invalid_groups"] == 0
    assert payload["mannequin_capture_failed_groups"] == 0
    assert payload["mannequin_capture_upstream_blocked_groups"] == 0
    assert payload["mannequin_capture_first_blocking_group_id"] == "mannequin_evidence_and_linkage"
    assert payload["mannequin_capture_first_blocking_group_status"] == "pending_required_fields"
    assert "matching mockup readiness record path" in payload["mannequin_capture_first_blocking_group_action"]
    assert payload["mannequin_capture_first_blocking_group_missing_fields"] == [
        "evidence.date",
        "evidence.observer",
        "evidence.mockup_readiness_record_path",
        "evidence.mannequin_or_arm_form_id",
        "evidence.future_interface_mock_geometry_revision",
        "evidence.cable_sleeve_mock_id",
    ]
    assert payload["mannequin_capture_first_blocking_group_invalid_fields"] == []
    assert payload["mannequin_capture_first_blocking_group_blocking_signals"] == []
    capture_status = _capture_status_by_id(payload)
    assert "evidence.date" in capture_status["mannequin_evidence_and_linkage"]["missing_fields"]
    assert "test_article.left_cuff_revision" in capture_status["mannequin_test_article"]["missing_fields"]
    assert (
        "interfaces.fr032_left_forearm_frame.mock_installed"
        in capture_status["mannequin_future_interface_clearance"]["missing_fields"]
    )
    assert (
        "cable_sensor_checks.fr163_outer_route_only"
        in capture_status["mannequin_cable_sensor_and_release_checks"]["missing_fields"]
    )
    assert "fail_observations.release_hidden" in capture_status["mannequin_fail_observation_screen"]["missing_fields"]


def test_fr017_mannequin_gate_treats_lowercase_or_padded_pending_text_as_missing(
    tmp_path: Path,
) -> None:
    measurement_path, mockup_path = _write_upstream_ready_records(tmp_path)
    mannequin_path = tmp_path / "placeholder-mannequin.json"
    mannequin_payload = _ready_mannequin_payload(mockup_path)
    mannequin_payload["evidence"]["observer"] = " pending "
    mannequin_payload["evidence"]["mannequin_or_arm_form_id"] = "pending"
    mannequin_payload["interfaces"]["fr032_left_forearm_frame"]["mock_installed"] = " PENDING "
    mannequin_path.write_text(json.dumps(mannequin_payload), encoding="utf-8")

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
    assert payload["status"] == "pending_mannequin_interface_test"
    assert payload["invalid_fields"] == []
    assert "evidence.observer" in payload["missing_fields"]
    assert "evidence.mannequin_or_arm_form_id" in payload["missing_fields"]
    assert "interfaces.fr032_left_forearm_frame.mock_installed" in payload["missing_fields"]
    assert payload["physical_validation_complete"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_mannequin_gate_accepts_complete_interface_record(tmp_path: Path) -> None:
    measurement_path, mockup_path = _write_upstream_ready_records(tmp_path)
    mannequin_path = tmp_path / "ready-mannequin.json"
    mannequin_path.write_text(json.dumps(_ready_mannequin_payload(mockup_path)), encoding="utf-8")

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
    assert payload["status"] == "ready_for_pilot_static_fit_planning"
    assert payload["upstream_mockup_status"] == "ready_for_mannequin_interface_test"
    assert payload["upstream_mockup_gate_ready"] is True
    assert payload["mannequin_status"] == "ready_for_pilot_static_fit_planning"
    assert payload["missing_fields"] == []
    assert payload["invalid_fields"] == []
    assert payload["record_linkage_violations"] == []
    assert payload["record_chronology_violations"] == []
    assert payload["interface_redesign_triggers"] == []
    assert payload["fail_observations"] == []
    assert payload["physical_validation_complete"] is False
    assert payload["stage17_completion_claim_allowed"] is False
    assert payload["mannequin_interface_test_complete"] is True
    assert payload["pilot_static_fit_planning_ready"] is True
    assert payload["pilot_testing_cleared"] is False
    assert payload["fr018_implementation_cleared"] is False
    assert payload["mannequin_capture_total_groups"] == 5
    assert payload["mannequin_capture_ready_groups"] == 5
    assert payload["mannequin_capture_pending_groups"] == 0
    assert payload["mannequin_capture_invalid_groups"] == 0
    assert payload["mannequin_capture_failed_groups"] == 0
    assert payload["mannequin_capture_upstream_blocked_groups"] == 0
    assert payload["mannequin_capture_first_blocking_group_id"] == ""
    assert payload["mannequin_capture_first_blocking_group_status"] == ""
    assert payload["mannequin_capture_first_blocking_group_action"] == ""
    assert all(step["ready_for_mannequin_interface"] is True for step in payload["mannequin_capture_plan_status"])
    assert "YYYY-MM-DD" in payload["evidence_date_contract"]
    assert "non-human mannequin or arm-form" in payload["test_subject_contract"]
    assert "not a pilot test" in payload["test_subject_contract"]
    assert "must resolve to the same mockup record path" in payload["record_linkage_contract"]
    assert "same as or later than the linked mockup" in payload["evidence_chronology_contract"]
    assert "Use unquoted JSON boolean true only" in payload["boolean_value_contract"]


def test_fr017_mannequin_gate_rejects_unlinked_mockup_record_path(tmp_path: Path) -> None:
    measurement_path, mockup_path = _write_upstream_ready_records(tmp_path)
    unrelated_mockup_path = tmp_path / "unrelated-mockup.json"
    mannequin_path = tmp_path / "unlinked-mannequin.json"
    unrelated_mockup_path.write_text(json.dumps(_ready_mockup_payload(measurement_path)), encoding="utf-8")
    mannequin_path.write_text(
        json.dumps(_ready_mannequin_payload(unrelated_mockup_path)),
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
    )

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "failed_mannequin_record"
    assert result["invalid_fields"] == []
    assert result["record_linkage_violations"] == ["evidence.mockup_readiness_record_path_must_match_mockup_path"]
    assert result["record_chronology_violations"] == []
    assert result["mannequin_interface_test_complete"] is False
    assert result["pilot_static_fit_planning_ready"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_mannequin_gate_rejects_mannequin_date_before_mockup_date(tmp_path: Path) -> None:
    measurement_path, mockup_path = _write_upstream_ready_records(tmp_path)
    mannequin_path = tmp_path / "backdated-mannequin.json"
    payload = _ready_mannequin_payload(mockup_path)
    payload["evidence"]["date"] = "2026-06-22"
    mannequin_path.write_text(json.dumps(payload), encoding="utf-8")

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

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "failed_mannequin_record"
    assert result["invalid_fields"] == []
    assert result["record_linkage_violations"] == []
    assert result["record_chronology_violations"] == ["evidence.date_before_mockup.evidence.date"]
    assert result["interface_redesign_triggers"] == []
    assert result["mannequin_interface_test_complete"] is False
    assert result["pilot_static_fit_planning_ready"] is False
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_mannequin_gate_rejects_malformed_evidence_date(tmp_path: Path) -> None:
    measurement_path, mockup_path = _write_upstream_ready_records(tmp_path)
    mannequin_path = tmp_path / "malformed-date-mannequin.json"
    payload = _ready_mannequin_payload(mockup_path)
    payload["evidence"]["date"] = "06/23/2026"
    mannequin_path.write_text(json.dumps(payload), encoding="utf-8")

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

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "failed_mannequin_record"
    assert result["invalid_fields"] == ["evidence.date"]
    assert result["record_linkage_violations"] == []
    assert "YYYY-MM-DD" in result["evidence_date_contract"]
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_mannequin_gate_rejects_pilot_subject_as_mannequin_record(tmp_path: Path) -> None:
    measurement_path, mockup_path = _write_upstream_ready_records(tmp_path)
    mannequin_path = tmp_path / "pilot-subject-mannequin.json"
    payload = _ready_mannequin_payload(mockup_path)
    payload["evidence"]["mannequin_or_arm_form_id"] = "pilot-left-arm"
    mannequin_path.write_text(json.dumps(payload), encoding="utf-8")

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

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "failed_mannequin_record"
    assert result["invalid_fields"] == ["evidence.mannequin_or_arm_form_id"]
    assert result["interface_redesign_triggers"] == []
    assert result["mannequin_interface_test_complete"] is False
    assert result["pilot_static_fit_planning_ready"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_mannequin_gate_rejects_future_evidence_date(tmp_path: Path) -> None:
    measurement_path, mockup_path = _write_upstream_ready_records(tmp_path)
    mannequin_path = tmp_path / "future-date-mannequin.json"
    payload = _ready_mannequin_payload(mockup_path)
    payload["evidence"]["date"] = (date.today() + timedelta(days=1)).isoformat()
    mannequin_path.write_text(json.dumps(payload), encoding="utf-8")

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

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "failed_mannequin_record"
    assert result["invalid_fields"] == ["evidence.date"]
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_mannequin_gate_blocks_upstream_mockup_failure(tmp_path: Path) -> None:
    measurement_path = tmp_path / "symptom-measurements.json"
    payload = _ready_measurement_payload()
    payload["safety_screen"]["tingling"] = True
    measurement_path.write_text(json.dumps(payload), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-MeasurementPath", str(measurement_path))

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "failed_upstream_mockup_gate"
    assert result["upstream_mockup_status"] == "failed_requires_redesign_or_medical_review"
    assert result["mannequin_interface_test_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_mannequin_gate_blocks_measurement_rejected_by_intake(tmp_path: Path) -> None:
    measurement_path = tmp_path / "quoted-measurements.json"
    payload = _ready_measurement_payload()
    payload["sides"]["left"]["forearm_length_elbow_crease_to_wrist_crease"] = "258"
    measurement_path.write_text(json.dumps(payload), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-MeasurementPath", str(measurement_path))

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "failed_upstream_mockup_gate"
    assert result["upstream_mockup_status"] == "invalid_measurement_record"
    assert result["upstream_mockup_gate_ready"] is False
    assert result["upstream_measurement_intake_status"] == "invalid_measurement_record"
    assert result["upstream_measurement_invalid_fields"] == ["sides.left.forearm_length_elbow_crease_to_wrist_crease"]
    assert result["mannequin_interface_test_complete"] is False
    assert result["pilot_static_fit_planning_ready"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_mannequin_gate_blocks_interface_failure(tmp_path: Path) -> None:
    measurement_path, mockup_path = _write_upstream_ready_records(tmp_path)
    mannequin_path = tmp_path / "failed-mannequin.json"
    payload = _ready_mannequin_payload(mockup_path)
    payload["interfaces"]["fr184_forearm_armor"]["clearance_passed"] = False
    payload["fail_observations"]["release_hidden"] = True
    mannequin_path.write_text(json.dumps(payload), encoding="utf-8")

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

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "failed_requires_interface_redesign"
    assert result["interface_redesign_triggers"] == ["interfaces.fr184_forearm_armor.clearance_passed"]
    assert result["fail_observations"] == ["fail_observations.release_hidden"]
    assert result["mannequin_capture_total_groups"] == 5
    assert result["mannequin_capture_ready_groups"] == 3
    assert result["mannequin_capture_pending_groups"] == 0
    assert result["mannequin_capture_invalid_groups"] == 0
    assert result["mannequin_capture_failed_groups"] == 2
    assert result["mannequin_capture_upstream_blocked_groups"] == 0
    assert result["mannequin_capture_first_blocking_group_id"] == "mannequin_future_interface_clearance"
    assert result["mannequin_capture_first_blocking_group_status"] == "failed_stop_condition_or_blocking_signal"
    capture_status = _capture_status_by_id(result)
    assert capture_status["mannequin_future_interface_clearance"]["blocking_signals"] == [
        "interfaces.fr184_forearm_armor.clearance_passed"
    ]
    assert capture_status["mannequin_fail_observation_screen"]["blocking_signals"] == [
        "fail_observations.release_hidden"
    ]
    assert result["pilot_testing_cleared"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_mannequin_gate_rejects_quoted_boolean_text(tmp_path: Path) -> None:
    measurement_path, mockup_path = _write_upstream_ready_records(tmp_path)
    mannequin_path = tmp_path / "quoted-boolean-mannequin.json"
    payload = _ready_mannequin_payload(mockup_path)
    payload["interfaces"]["fr032_left_forearm_frame"]["mock_installed"] = "true"
    mannequin_path.write_text(json.dumps(payload), encoding="utf-8")

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

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "failed_mannequin_record"
    assert result["invalid_fields"] == ["interfaces.fr032_left_forearm_frame.mock_installed"]
    assert result["interface_redesign_triggers"] == []
    assert result["fr018_implementation_cleared"] is False
