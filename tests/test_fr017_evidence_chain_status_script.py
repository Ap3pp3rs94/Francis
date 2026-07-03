from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from tests.powershell_script_runner import run_powershell_script
from tests.test_fr017_engineering_review_gate_script import (
    _ready_engineering_review_payload,
    _write_release_ready_records,
)
from tests.test_fr017_final_decision_record_gate_script import (
    _ready_final_decision_payload,
    _write_final_physical_gate_record,
)
from tests.test_fr017_completion_ledger_gate_script import _ready_ledger_entry
from tests.test_fr017_mannequin_interface_gate_script import _ready_mannequin_payload
from tests.test_fr017_mockup_readiness_gate_script import (
    _ready_measurement_payload,
    _ready_mockup_payload,
)
from tests.test_fr017_quick_release_cable_snag_gate_script import (
    _ready_release_cable_payload,
    _write_movement_ready_records,
)
from tests.test_fr017_pilot_static_fit_gate_script import _ready_static_fit_payload
from tests.test_fr017_stage17_validation_gate_script import _copy_stage17_package


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "fr017-evidence-chain-status.ps1"


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
        timeout_seconds=140,
    )


def _payload(stdout: str) -> dict[str, Any]:
    return json.loads(stdout)


def _assert_unique(values: list[Any]) -> None:
    assert len(values) == len(set(values))


def test_fr017_evidence_chain_status_stops_at_measurement_template() -> None:
    proc = _run_gate("-Mode", "Status")

    assert proc.returncode == 0, proc.stderr
    payload = _payload(proc.stdout)
    assert payload["kind"] == "francis.fr017.evidence_chain_status"
    assert payload["status"] == "blocked_on_measurement_intake"
    assert payload["first_blocking_gate"] == "measurement_intake"
    assert payload["first_blocking_status"] == "pending_measurements"
    assert (
        payload["next_required_input"]
        == "scripts/fr017-new-measurement-record.ps1 + FR-017-MEASUREMENT-CAPTURE-RUNBOOK.md + FR-017-MEASUREMENTS-INPUT-TEMPLATE.json"
    )
    assert (
        payload["next_command"]
        == "create_pending_measurement_record_then_capture_with_runbook_and_rerun_measurement_intake"
    )
    assert (
        payload["first_blocking_details"]["next_required_physical_input"]
        == "create_pending_record_with_fr017-new-measurement-record.ps1_then_capture_with_FR-017-MEASUREMENT-CAPTURE-RUNBOOK.md_and_rerun_measurement_intake"
    )
    assert (
        str(payload["first_blocking_details"]["measurement_input_template_path"])
        .replace("/", "\\")
        .endswith("FR-017_Stage17_Package\\FR-017-MEASUREMENTS-INPUT-TEMPLATE.json")
    )
    assert (
        str(payload["first_blocking_details"]["measurement_capture_runbook_path"])
        .replace("/", "\\")
        .endswith("FR-017_Stage17_Package\\FR-017-MEASUREMENT-CAPTURE-RUNBOOK.md")
    )
    assert (
        str(payload["first_blocking_details"]["measurement_record_initializer_path"])
        .replace("/", "\\")
        .endswith("scripts\\fr017-new-measurement-record.ps1")
    )
    assert (
        str(payload["first_blocking_details"]["measurement_record_update_path"])
        .replace("/", "\\")
        .endswith("scripts\\fr017-update-measurement-record.ps1")
    )
    assert (
        str(payload["first_blocking_details"]["measurement_landmark_update_path"])
        .replace("/", "\\")
        .endswith("scripts\\fr017-update-landmark-record.ps1")
    )
    assert (
        payload["first_blocking_details"]["measurement_working_record_name_pattern"]
        == "FR-017-MEASUREMENTS-YYYY-MM-DD-PILOT-RECORD.json"
    )
    assert payload["first_blocking_details"]["measurement_capture_plan_not_completion_evidence"] is True
    assert "not physical validation evidence" in payload["first_blocking_details"]["measurement_capture_plan_contract"]
    assert "operator input tooling only" in payload["first_blocking_details"]["measurement_capture_runbook_contract"]
    assert (
        "fr017-new-measurement-record.ps1" in payload["first_blocking_details"]["measurement_capture_runbook_contract"]
    )
    assert (
        "fr017-update-measurement-record.ps1"
        in payload["first_blocking_details"]["measurement_capture_runbook_contract"]
    )
    assert (
        "fr017-update-landmark-record.ps1" in payload["first_blocking_details"]["measurement_capture_runbook_contract"]
    )
    assert "intake readiness only" in payload["first_blocking_details"]["measurement_capture_plan_status_contract"]
    assert (
        "not physical validation evidence" in payload["first_blocking_details"]["measurement_capture_summary_contract"]
    )
    assert payload["first_blocking_details"]["measurement_capture_total_groups"] == 5
    assert payload["first_blocking_details"]["measurement_capture_ready_groups"] == 0
    assert payload["first_blocking_details"]["measurement_capture_pending_groups"] == 5
    assert payload["first_blocking_details"]["measurement_capture_invalid_groups"] == 0
    assert payload["first_blocking_details"]["measurement_capture_failed_groups"] == 0
    assert payload["first_blocking_details"]["measurement_capture_first_blocking_group_id"] == "setup_and_safety_brief"
    assert (
        payload["first_blocking_details"]["measurement_capture_first_blocking_group_status"]
        == "pending_required_fields"
    )
    assert (
        "brief stop conditions" in payload["first_blocking_details"]["measurement_capture_first_blocking_group_action"]
    )
    capture_plan = payload["first_blocking_details"]["measurement_capture_plan"]
    assert isinstance(capture_plan, list)
    assert capture_plan[0]["id"] == "setup_and_safety_brief"
    assert "evidence.measurement_tool" in capture_plan[0]["required_fields"]
    assert capture_plan[-1]["id"] == "left_right_independence_and_safety_screen"
    assert "any_safety_screen_symptom_is_true" in capture_plan[-1]["stop_if"]
    capture_plan_status = payload["first_blocking_details"]["measurement_capture_plan_status"]
    assert isinstance(capture_plan_status, list)
    assert [step["id"] for step in capture_plan_status] == [step["id"] for step in capture_plan]
    assert all(step["status"] == "pending_required_fields" for step in capture_plan_status)
    assert "evidence.date" in capture_plan_status[0]["missing_fields"]
    assert "safety_screen.loss_of_grip_strength" in capture_plan_status[-1]["missing_fields"]
    assert "evidence.date" in payload["first_blocking_details"]["missing_fields"]
    assert "sides.left.wrist_clearance_gap" in payload["first_blocking_details"]["missing_fields"]
    missing_fields = payload["first_blocking_details"]["missing_fields"]
    assert isinstance(missing_fields, list)
    _assert_unique(missing_fields)
    assert missing_fields.count("left_right_independence.independence_notes") == 1
    assert missing_fields.count("measurement_conditions.condition_notes") == 1
    assert missing_fields.count("landmark_confirmation.landmark_notes") == 1
    assert payload["first_blocking_details"]["invalid_fields"] == []
    assert payload["first_blocking_details"]["safety_blockers"] == []
    assert payload["gates_ran"] == 2
    assert payload["gate_count"] == 11
    assert payload["evidence_chain_decision_ready"] is False
    assert payload["physical_validation_complete"] is False
    assert payload["stage17_completion_claim_allowed"] is False
    assert payload["fr018_implementation_cleared"] is False
    assert payload["read_only_contract"] is True
    assert payload["writes_repo"] is False
    assert payload["grants_mutation_authority"] is False


def test_fr017_evidence_chain_status_moves_blocker_after_measurement_ready(tmp_path: Path) -> None:
    measurement_path = tmp_path / "ready-measurements.json"
    measurement_path.write_text(json.dumps(_ready_measurement_payload()), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-MeasurementPath", str(measurement_path))

    assert proc.returncode == 0, proc.stderr
    payload = _payload(proc.stdout)
    assert payload["status"] == "blocked_on_mockup_readiness"
    assert payload["first_blocking_gate"] == "mockup_readiness"
    assert payload["first_blocking_status"] == "pending_mockup_build_record"
    assert payload["next_required_input"] == "FR-017-MOCKUP-BUILD-INPUT-TEMPLATE.json"
    assert "evidence.date" in payload["first_blocking_details"]["mockup_missing_fields"]
    assert payload["first_blocking_details"]["mockup_invalid_fields"] == []
    assert (
        "not physical validation evidence" in payload["first_blocking_details"]["measurement_capture_summary_contract"]
    )
    assert payload["first_blocking_details"]["measurement_capture_total_groups"] == 5
    assert payload["first_blocking_details"]["measurement_capture_ready_groups"] == 5
    assert payload["first_blocking_details"]["measurement_capture_pending_groups"] == 0
    assert payload["first_blocking_details"]["measurement_capture_invalid_groups"] == 0
    assert payload["first_blocking_details"]["measurement_capture_failed_groups"] == 0
    assert payload["first_blocking_details"]["measurement_capture_first_blocking_group_id"] == ""
    assert payload["first_blocking_details"]["measurement_capture_first_blocking_group_status"] == ""
    assert payload["first_blocking_details"]["measurement_capture_first_blocking_group_action"] == ""
    assert payload["first_blocking_details"]["mockup_capture_plan_not_completion_evidence"] is True
    assert "not physical validation evidence" in payload["first_blocking_details"]["mockup_capture_plan_contract"]
    assert "mockup readiness only" in payload["first_blocking_details"]["mockup_capture_plan_status_contract"]
    assert "not physical validation evidence" in payload["first_blocking_details"]["mockup_capture_summary_contract"]
    assert (
        payload["first_blocking_details"]["next_required_mockup_input"]
        == "complete_non_powered_mockup_build_record_at_FR-017-MOCKUP-BUILD-INPUT-TEMPLATE.json"
    )
    assert payload["first_blocking_details"]["mockup_capture_total_groups"] == 5
    assert payload["first_blocking_details"]["mockup_capture_ready_groups"] == 0
    assert payload["first_blocking_details"]["mockup_capture_pending_groups"] == 5
    assert payload["first_blocking_details"]["mockup_capture_invalid_groups"] == 0
    assert payload["first_blocking_details"]["mockup_capture_failed_groups"] == 0
    assert payload["first_blocking_details"]["mockup_capture_upstream_blocked_groups"] == 0
    assert payload["first_blocking_details"]["mockup_capture_first_blocking_group_id"] == "mockup_evidence_and_linkage"
    assert payload["first_blocking_details"]["mockup_capture_first_blocking_group_status"] == "pending_required_fields"
    assert (
        "matching measurement record path"
        in payload["first_blocking_details"]["mockup_capture_first_blocking_group_action"]
    )
    capture_status = {step["id"]: step for step in payload["first_blocking_details"]["mockup_capture_plan_status"]}
    assert "evidence.date" in capture_status["mockup_evidence_and_linkage"]["missing_fields"]
    assert "materials.padding_layer" in capture_status["mockup_material_stack"]["missing_fields"]
    assert "constraints.non_powered_only" in capture_status["mockup_global_safety_constraints"]["missing_fields"]
    assert payload["gates_ran"] == 3
    assert payload["physical_validation_complete"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_evidence_chain_status_moves_blocker_after_mockup_ready(tmp_path: Path) -> None:
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
    assert payload["status"] == "blocked_on_mannequin_interface"
    assert payload["first_blocking_gate"] == "mannequin_interface"
    assert payload["first_blocking_status"] == "pending_mannequin_interface_test"
    assert payload["next_required_input"] == "FR-017-MANNEQUIN-INTERFACE-INPUT-TEMPLATE.json"
    assert "evidence.date" in payload["first_blocking_details"]["missing_fields"]
    assert payload["first_blocking_details"]["invalid_fields"] == []
    assert payload["first_blocking_details"]["mannequin_capture_plan_not_completion_evidence"] is True
    assert "not physical validation evidence" in payload["first_blocking_details"]["mannequin_capture_plan_contract"]
    assert (
        "mannequin interface capture readiness only"
        in payload["first_blocking_details"]["mannequin_capture_plan_status_contract"]
    )
    assert "not physical validation evidence" in payload["first_blocking_details"]["mannequin_capture_summary_contract"]
    assert (
        payload["first_blocking_details"]["next_required_mannequin_input"]
        == "complete_non_powered_mannequin_interface_record_at_FR-017-MANNEQUIN-INTERFACE-INPUT-TEMPLATE.json"
    )
    assert payload["first_blocking_details"]["mannequin_capture_total_groups"] == 5
    assert payload["first_blocking_details"]["mannequin_capture_ready_groups"] == 0
    assert payload["first_blocking_details"]["mannequin_capture_pending_groups"] == 5
    assert payload["first_blocking_details"]["mannequin_capture_invalid_groups"] == 0
    assert payload["first_blocking_details"]["mannequin_capture_failed_groups"] == 0
    assert payload["first_blocking_details"]["mannequin_capture_upstream_blocked_groups"] == 0
    assert payload["first_blocking_details"]["mannequin_capture_first_blocking_group_id"] == (
        "mannequin_evidence_and_linkage"
    )
    assert payload["first_blocking_details"]["mannequin_capture_first_blocking_group_status"] == (
        "pending_required_fields"
    )
    assert (
        "matching mockup readiness record path"
        in payload["first_blocking_details"]["mannequin_capture_first_blocking_group_action"]
    )
    capture_status = {step["id"]: step for step in payload["first_blocking_details"]["mannequin_capture_plan_status"]}
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
    assert payload["gates_ran"] == 4
    assert payload["physical_validation_complete"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_evidence_chain_status_moves_blocker_after_mannequin_ready(tmp_path: Path) -> None:
    measurement_path = tmp_path / "ready-measurements.json"
    mockup_path = tmp_path / "ready-mockup.json"
    mannequin_path = tmp_path / "ready-mannequin.json"
    measurement_path.write_text(json.dumps(_ready_measurement_payload()), encoding="utf-8")
    mockup_path.write_text(json.dumps(_ready_mockup_payload(measurement_path)), encoding="utf-8")
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
    assert payload["status"] == "blocked_on_pilot_static_fit"
    assert payload["first_blocking_gate"] == "pilot_static_fit"
    assert payload["first_blocking_status"] == "pending_pilot_static_fit_test"
    assert payload["next_required_input"] == "FR-017-PILOT-STATIC-FIT-INPUT-TEMPLATE.json"
    assert "evidence.date" in payload["first_blocking_details"]["missing_fields"]
    assert payload["first_blocking_details"]["invalid_fields"] == []
    assert payload["first_blocking_details"]["static_fit_capture_plan_not_completion_evidence"] is True
    assert "not physical validation evidence" in payload["first_blocking_details"]["static_fit_capture_plan_contract"]
    assert (
        "pilot static-fit capture readiness only"
        in payload["first_blocking_details"]["static_fit_capture_plan_status_contract"]
    )
    assert (
        "not physical validation evidence" in payload["first_blocking_details"]["static_fit_capture_summary_contract"]
    )
    assert (
        payload["first_blocking_details"]["next_required_static_fit_input"]
        == "complete_non_powered_pilot_static_fit_record_at_FR-017-PILOT-STATIC-FIT-INPUT-TEMPLATE.json"
    )
    assert payload["first_blocking_details"]["static_fit_capture_total_groups"] == 6
    assert payload["first_blocking_details"]["static_fit_capture_ready_groups"] == 0
    assert payload["first_blocking_details"]["static_fit_capture_pending_groups"] == 6
    assert payload["first_blocking_details"]["static_fit_capture_invalid_groups"] == 0
    assert payload["first_blocking_details"]["static_fit_capture_failed_groups"] == 0
    assert payload["first_blocking_details"]["static_fit_capture_upstream_blocked_groups"] == 0
    assert payload["first_blocking_details"]["static_fit_capture_first_blocking_group_id"] == (
        "static_fit_evidence_and_linkage"
    )
    assert payload["first_blocking_details"]["static_fit_capture_first_blocking_group_status"] == (
        "pending_required_fields"
    )
    assert "matching pilot id" in payload["first_blocking_details"]["static_fit_capture_first_blocking_group_action"]
    capture_status = {step["id"]: step for step in payload["first_blocking_details"]["static_fit_capture_plan_status"]}
    assert "evidence.date" in capture_status["static_fit_evidence_and_linkage"]["missing_fields"]
    assert "preconditions.non_powered_only" in capture_status["static_fit_safety_preconditions"]["missing_fields"]
    assert (
        "sides.left.static_checks.quick_release_visible_tactile_reachable"
        in capture_status["left_static_fit_baseline_and_clearance"]["missing_fields"]
    )
    assert (
        "sides.right.symptoms.loss_of_grip_strength"
        in capture_status["right_static_fit_post_doff_and_symptoms"]["missing_fields"]
    )
    assert payload["gates_ran"] == 5
    assert payload["physical_validation_complete"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_evidence_chain_status_moves_blocker_after_static_fit_ready(tmp_path: Path) -> None:
    measurement_path = tmp_path / "ready-measurements.json"
    mockup_path = tmp_path / "ready-mockup.json"
    mannequin_path = tmp_path / "ready-mannequin.json"
    static_fit_path = tmp_path / "ready-static-fit.json"
    measurement_path.write_text(json.dumps(_ready_measurement_payload()), encoding="utf-8")
    mockup_path.write_text(json.dumps(_ready_mockup_payload(measurement_path)), encoding="utf-8")
    mannequin_path.write_text(json.dumps(_ready_mannequin_payload(mockup_path)), encoding="utf-8")
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
    assert payload["status"] == "blocked_on_pilot_movement"
    assert payload["first_blocking_gate"] == "pilot_movement"
    assert payload["first_blocking_status"] == "pending_pilot_movement_test"
    assert payload["next_required_input"] == "FR-017-PILOT-MOVEMENT-INPUT-TEMPLATE.json"
    assert "evidence.date" in payload["first_blocking_details"]["missing_fields"]
    assert payload["first_blocking_details"]["invalid_fields"] == []
    assert payload["first_blocking_details"]["movement_capture_plan_not_completion_evidence"] is True
    assert "not physical validation evidence" in payload["first_blocking_details"]["movement_capture_plan_contract"]
    assert (
        "pilot movement capture readiness only"
        in payload["first_blocking_details"]["movement_capture_plan_status_contract"]
    )
    assert "not physical validation evidence" in payload["first_blocking_details"]["movement_capture_summary_contract"]
    assert (
        payload["first_blocking_details"]["next_required_movement_input"]
        == "complete_non_powered_pilot_movement_record_at_FR-017-PILOT-MOVEMENT-INPUT-TEMPLATE.json"
    )
    assert payload["first_blocking_details"]["movement_capture_total_groups"] == 6
    assert payload["first_blocking_details"]["movement_capture_ready_groups"] == 0
    assert payload["first_blocking_details"]["movement_capture_pending_groups"] == 6
    assert payload["first_blocking_details"]["movement_capture_invalid_groups"] == 0
    assert payload["first_blocking_details"]["movement_capture_failed_groups"] == 0
    assert payload["first_blocking_details"]["movement_capture_upstream_blocked_groups"] == 0
    assert payload["first_blocking_details"]["movement_capture_first_blocking_group_id"] == (
        "movement_evidence_and_linkage"
    )
    assert payload["first_blocking_details"]["movement_capture_first_blocking_group_status"] == (
        "pending_required_fields"
    )
    assert "matching pilot id" in payload["first_blocking_details"]["movement_capture_first_blocking_group_action"]
    capture_status = {step["id"]: step for step in payload["first_blocking_details"]["movement_capture_plan_status"]}
    assert "evidence.date" in capture_status["movement_evidence_and_linkage"]["missing_fields"]
    assert "preconditions.non_powered_only" in capture_status["movement_safety_preconditions"]["missing_fields"]
    assert (
        "sides.left.movement_checks.outer_cable_route_no_snag"
        in capture_status["left_movement_clearance"]["missing_fields"]
    )
    assert (
        "sides.right.symptoms.loss_of_grip_strength"
        in capture_status["right_post_movement_and_symptoms"]["missing_fields"]
    )
    assert payload["gates_ran"] == 6
    assert payload["physical_validation_complete"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_evidence_chain_status_moves_blocker_after_movement_ready(tmp_path: Path) -> None:
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
    assert payload["status"] == "blocked_on_quick_release_cable_snag"
    assert payload["first_blocking_gate"] == "quick_release_cable_snag"
    assert payload["first_blocking_status"] == "pending_quick_release_cable_snag_test"
    assert payload["next_required_input"] == "FR-017-QUICK-RELEASE-CABLE-SNAG-INPUT-TEMPLATE.json"
    assert "evidence.date" in payload["first_blocking_details"]["missing_fields"]
    assert payload["first_blocking_details"]["invalid_fields"] == []
    assert payload["first_blocking_details"]["release_cable_capture_plan_not_completion_evidence"] is True
    assert (
        "not physical validation evidence" in payload["first_blocking_details"]["release_cable_capture_plan_contract"]
    )
    assert (
        "quick-release/cable-snag capture readiness only"
        in payload["first_blocking_details"]["release_cable_capture_plan_status_contract"]
    )
    assert (
        "not physical validation evidence"
        in payload["first_blocking_details"]["release_cable_capture_summary_contract"]
    )
    assert (
        payload["first_blocking_details"]["next_required_release_cable_input"]
        == "complete_non_powered_quick_release_cable_snag_record_at_FR-017-QUICK-RELEASE-CABLE-SNAG-INPUT-TEMPLATE.json"
    )
    assert payload["first_blocking_details"]["release_cable_capture_total_groups"] == 6
    assert payload["first_blocking_details"]["release_cable_capture_ready_groups"] == 0
    assert payload["first_blocking_details"]["release_cable_capture_pending_groups"] == 6
    assert payload["first_blocking_details"]["release_cable_capture_invalid_groups"] == 0
    assert payload["first_blocking_details"]["release_cable_capture_failed_groups"] == 0
    assert payload["first_blocking_details"]["release_cable_capture_upstream_blocked_groups"] == 0
    assert payload["first_blocking_details"]["release_cable_capture_first_blocking_group_id"] == (
        "release_cable_evidence_and_linkage"
    )
    assert payload["first_blocking_details"]["release_cable_capture_first_blocking_group_status"] == (
        "pending_required_fields"
    )
    assert (
        "linked movement record path"
        in payload["first_blocking_details"]["release_cable_capture_first_blocking_group_action"]
    )
    capture_status = {
        step["id"]: step for step in payload["first_blocking_details"]["release_cable_capture_plan_status"]
    }
    assert "evidence.date" in capture_status["release_cable_evidence_and_linkage"]["missing_fields"]
    assert "preconditions.non_powered_only" in capture_status["release_cable_safety_preconditions"]["missing_fields"]
    assert (
        "sides.left.release_checks.opposite_hand_release_reachable"
        in capture_status["left_quick_release_access"]["missing_fields"]
    )
    assert (
        "sides.right.cable_sleeve_checks.no_wrist_bone_crossing"
        in capture_status["right_cable_route_and_fail_observations"]["missing_fields"]
    )
    assert payload["gates_ran"] == 7
    assert payload["physical_validation_complete"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_evidence_chain_status_moves_blocker_after_release_cable_ready(tmp_path: Path) -> None:
    measurement_path, mockup_path, mannequin_path, static_fit_path, movement_path, release_cable_path = (
        _write_release_ready_records(tmp_path)
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
    assert payload["status"] == "blocked_on_engineering_review"
    assert payload["first_blocking_gate"] == "engineering_review"
    assert payload["first_blocking_status"] == "pending_engineering_review"
    assert payload["next_required_input"] == "FR-017-ENGINEERING-REVIEW-INPUT-TEMPLATE.json"
    assert "evidence.date" in payload["first_blocking_details"]["missing_fields"]
    assert payload["first_blocking_details"]["invalid_fields"] == []
    assert payload["first_blocking_details"]["engineering_review_capture_plan_not_completion_evidence"] is True
    assert (
        "not physical validation evidence"
        in payload["first_blocking_details"]["engineering_review_capture_plan_contract"]
    )
    assert (
        "engineering-review capture readiness only"
        in payload["first_blocking_details"]["engineering_review_capture_plan_status_contract"]
    )
    assert (
        "not physical validation evidence"
        in payload["first_blocking_details"]["engineering_review_capture_summary_contract"]
    )
    assert (
        payload["first_blocking_details"]["next_required_engineering_review_input"]
        == "complete_professional_engineering_review_record_at_FR-017-ENGINEERING-REVIEW-INPUT-TEMPLATE.json"
    )
    assert payload["first_blocking_details"]["engineering_review_capture_total_groups"] == 4
    assert payload["first_blocking_details"]["engineering_review_capture_ready_groups"] == 0
    assert payload["first_blocking_details"]["engineering_review_capture_pending_groups"] == 4
    assert payload["first_blocking_details"]["engineering_review_capture_invalid_groups"] == 0
    assert payload["first_blocking_details"]["engineering_review_capture_failed_groups"] == 0
    assert payload["first_blocking_details"]["engineering_review_capture_upstream_blocked_groups"] == 0
    assert payload["first_blocking_details"]["engineering_review_capture_first_blocking_group_id"] == (
        "engineering_review_evidence_and_linkage"
    )
    assert payload["first_blocking_details"]["engineering_review_capture_first_blocking_group_status"] == (
        "pending_required_fields"
    )
    assert (
        "linked quick-release/cable-snag record path"
        in payload["first_blocking_details"]["engineering_review_capture_first_blocking_group_action"]
    )
    capture_status = {
        step["id"]: step for step in payload["first_blocking_details"]["engineering_review_capture_plan_status"]
    }
    assert "evidence.date" in capture_status["engineering_review_evidence_and_linkage"]["missing_fields"]
    assert (
        "review_constraints.fr018_implementation_not_cleared"
        in capture_status["engineering_review_constraints"]["missing_fields"]
    )
    assert (
        "safety_review.quick_release_access_reviewed" in capture_status["engineering_safety_review"]["missing_fields"]
    )
    assert (
        "review_decision.powered_testing_approved"
        in capture_status["engineering_review_decision_and_limits"]["missing_fields"]
    )
    assert payload["gates_ran"] == 8
    assert payload["physical_validation_complete"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_evidence_chain_status_surfaces_package_template_drift(tmp_path: Path) -> None:
    manifest_path = _copy_stage17_package(tmp_path)
    package_root = manifest_path.parent
    engineering_template_path = package_root / "FR-017-ENGINEERING-REVIEW-INPUT-TEMPLATE.json"
    template = json.loads(engineering_template_path.read_text(encoding="utf-8"))
    del template["field_contract"]["required_false_checks"]
    del template["review_constraints"]["fr018_implementation_not_cleared"]
    engineering_template_path.write_text(json.dumps(template, indent=2), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-ManifestPath", str(manifest_path))

    assert proc.returncode == 1
    payload = _payload(proc.stdout)
    assert payload["status"] == "failed_stage17_package"
    assert payload["first_blocking_gate"] == "stage17_package"
    assert payload["first_blocking_status"] == "failed_contract"
    assert "engineering_input_template_contracts" in payload["first_blocking_details"]["failed_checks"]
    assert "engineering_input_template_required_fields" in payload["first_blocking_details"]["failed_checks"]
    assert payload["first_blocking_details"]["missing_engineering_template_contracts"] == ["required_false_checks"]
    assert payload["first_blocking_details"]["missing_engineering_template_fields"] == [
        "review_constraints.fr018_implementation_not_cleared"
    ]
    assert payload["gate_results"][0]["details"]["missing_engineering_template_contracts"] == ["required_false_checks"]
    assert payload["physical_validation_complete"] is False
    assert payload["stage17_completion_claim_allowed"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_evidence_chain_status_surfaces_package_pending_contract_text(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_stage17_package(tmp_path)
    package_root = manifest_path.parent
    measurement_template_path = package_root / "FR-017-MEASUREMENTS-INPUT-TEMPLATE.json"
    template = json.loads(measurement_template_path.read_text(encoding="utf-8"))
    template["field_contract"]["measurement_tool"] = " pending "
    measurement_template_path.write_text(json.dumps(template, indent=2), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-ManifestPath", str(manifest_path))

    assert proc.returncode == 1
    payload = _payload(proc.stdout)
    assert payload["status"] == "failed_stage17_package"
    assert payload["first_blocking_gate"] == "stage17_package"
    assert payload["first_blocking_status"] == "failed_contract"
    assert "measurement_input_template_contracts" in payload["first_blocking_details"]["failed_checks"]
    assert payload["first_blocking_details"]["missing_measurement_template_contracts"] == ["measurement_tool"]
    assert payload["gate_results"][0]["details"]["missing_measurement_template_contracts"] == ["measurement_tool"]
    assert payload["physical_validation_complete"] is False
    assert payload["stage17_completion_claim_allowed"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_evidence_chain_status_blocks_on_final_decision_record_after_final_gate_ready(tmp_path: Path) -> None:
    measurement_path, mockup_path, mannequin_path, static_fit_path, movement_path, release_cable_path = (
        _write_release_ready_records(tmp_path)
    )
    engineering_review_path = tmp_path / "ready-engineering-review.json"
    engineering_review_path.write_text(
        json.dumps(_ready_engineering_review_payload(release_cable_path)),
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
        "-EngineeringReviewPath",
        str(engineering_review_path),
    )

    assert proc.returncode == 0, proc.stderr
    payload = _payload(proc.stdout)
    assert payload["status"] == "blocked_on_final_decision_record"
    assert payload["first_blocking_gate"] == "final_decision_record"
    assert payload["first_blocking_status"] == "pending_final_decision_record"
    assert payload["next_required_input"] == "FR-017-FINAL-PHYSICAL-DECISION-INPUT-TEMPLATE.json"
    assert payload["next_command"] == (
        "complete_human_final_stage17_completion_decision_record_at_FR-017-FINAL-PHYSICAL-DECISION-INPUT-TEMPLATE.json"
    )
    assert payload["first_blocking_details"]["missing_fields"] == ["final_decision_path"]
    assert payload["first_blocking_details"]["failed_reasons"] == []
    assert payload["gates_ran"] == 10
    assert payload["gate_count"] == 11
    assert payload["gate_results"][8]["details"]["evidence_chronology_violations"] == []
    assert payload["gate_results"][8]["details"]["pilot_identity_continuity_violations"] == []
    assert payload["gate_results"][8]["details"]["pilot_identity_continuity_reference_record"] == "measurement"
    assert payload["gate_results"][8]["details"]["pilot_identity_continuity_reference_fingerprint"]
    assert payload["gate_results"][8]["details"]["final_physical_decision_plan_not_completion_evidence"] is True
    assert (
        "not physical validation evidence"
        in payload["gate_results"][8]["details"]["final_physical_decision_plan_contract"]
    )
    assert (
        "final physical decision readiness only"
        in payload["gate_results"][8]["details"]["final_physical_decision_plan_status_contract"]
    )
    assert payload["gate_results"][8]["details"]["final_physical_decision_total_groups"] == 5
    assert payload["gate_results"][8]["details"]["final_physical_decision_ready_groups"] == 5
    assert payload["gate_results"][8]["details"]["final_physical_decision_pending_groups"] == 0
    assert payload["gate_results"][8]["details"]["final_physical_decision_failed_groups"] == 0
    assert payload["gate_results"][8]["details"]["final_physical_decision_blocked_groups"] == 0
    assert payload["gate_results"][8]["details"]["final_physical_decision_first_blocking_group_id"] == ""
    assert all(
        step["status"] == "ready_for_final_physical_decision_review"
        for step in payload["gate_results"][8]["details"]["final_physical_decision_plan_status"]
    )
    assert payload["gate_results"][9]["id"] == "final_decision_record"
    assert payload["gate_results"][9]["details"]["final_decision_record_ready"] is False
    assert payload["gate_results"][9]["details"]["ledger_completion_review_ready"] is False
    assert payload["evidence_chain_decision_ready"] is False
    assert payload["ledger_completion_review_ready"] is False
    assert payload["physical_validation_complete"] is False
    assert payload["stage17_completion_claim_allowed"] is False
    assert payload["powered_or_frame_coupled_testing_cleared"] is False
    assert payload["fr018_implementation_cleared"] is False
    assert "never writes the ledger" in payload["no_fake_validation_lock"]


def test_fr017_evidence_chain_status_blocks_on_completion_ledger_after_final_decision_record(
    tmp_path: Path,
) -> None:
    measurement_path, mockup_path, mannequin_path, static_fit_path, movement_path, release_cable_path = (
        _write_release_ready_records(tmp_path)
    )
    engineering_review_path = tmp_path / "ready-engineering-review.json"
    engineering_review_path.write_text(
        json.dumps(_ready_engineering_review_payload(release_cable_path)),
        encoding="utf-8",
    )
    evidence_paths = (
        measurement_path,
        mockup_path,
        mannequin_path,
        static_fit_path,
        movement_path,
        release_cable_path,
        engineering_review_path,
    )
    final_physical_gate_record_path = _write_final_physical_gate_record(tmp_path, evidence_paths)
    final_decision_path = tmp_path / "ready-final-decision.json"
    final_decision_path.write_text(
        json.dumps(_ready_final_decision_payload(final_physical_gate_record_path)),
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
        "-EngineeringReviewPath",
        str(engineering_review_path),
        "-FinalDecisionPath",
        str(final_decision_path),
    )

    assert proc.returncode == 0, proc.stderr
    payload = _payload(proc.stdout)
    assert payload["status"] == "blocked_on_completion_ledger"
    assert payload["first_blocking_gate"] == "completion_ledger"
    assert payload["first_blocking_status"] == "pending_completion_ledger_entry"
    assert payload["next_required_input"] == "FR-017-COMPLETION-LEDGER-HANDOFF-TEMPLATE.md"
    assert (
        payload["next_command"]
        == "copy_and_complete_FR-017-COMPLETION-LEDGER-HANDOFF-TEMPLATE.md_with_operator_reviewed_final_decision_evidence"
    )
    assert payload["gates_ran"] == 11
    assert payload["gate_count"] == 11
    assert payload["gate_results"][9]["id"] == "final_decision_record"
    assert payload["gate_results"][9]["details"]["final_decision_record_ready"] is True
    assert payload["gate_results"][9]["details"]["ledger_completion_review_ready"] is True
    assert payload["gate_results"][9]["details"]["decision_lock_violations"] == []
    assert payload["gate_results"][9]["details"]["prohibited_clearance_flags"] == []
    assert payload["gate_results"][10]["id"] == "completion_ledger"
    assert payload["gate_results"][10]["details"]["final_decision_record_ready"] is True
    assert payload["gate_results"][10]["details"]["ledger_entry_review_ready"] is False
    assert payload["gate_results"][10]["details"]["missing_fields"] == ["ledger_entry_path"]
    assert payload["first_blocking_details"]["missing_fields"] == ["ledger_entry_path"]
    assert payload["evidence_chain_decision_ready"] is False
    assert payload["ledger_completion_review_ready"] is False
    assert payload["completion_ledger_handoff_ready"] is False
    assert payload["physical_validation_complete"] is False
    assert payload["stage17_completion_claim_allowed"] is False
    assert payload["powered_or_frame_coupled_testing_cleared"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_evidence_chain_status_ready_after_completion_ledger_handoff(
    tmp_path: Path,
) -> None:
    measurement_path, mockup_path, mannequin_path, static_fit_path, movement_path, release_cable_path = (
        _write_release_ready_records(tmp_path)
    )
    engineering_review_path = tmp_path / "ready-engineering-review.json"
    engineering_review_path.write_text(
        json.dumps(_ready_engineering_review_payload(release_cable_path)),
        encoding="utf-8",
    )
    evidence_paths = (
        measurement_path,
        mockup_path,
        mannequin_path,
        static_fit_path,
        movement_path,
        release_cable_path,
        engineering_review_path,
    )
    final_physical_gate_record_path = _write_final_physical_gate_record(tmp_path, evidence_paths)
    final_decision_path = tmp_path / "ready-final-decision.json"
    final_decision_path.write_text(
        json.dumps(_ready_final_decision_payload(final_physical_gate_record_path)),
        encoding="utf-8",
    )
    ledger_entry_path = tmp_path / "ready-ledger-handoff.md"
    ledger_entry_path.write_text(_ready_ledger_entry(final_decision_path), encoding="utf-8")

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
        "-EngineeringReviewPath",
        str(engineering_review_path),
        "-FinalDecisionPath",
        str(final_decision_path),
        "-LedgerEntryPath",
        str(ledger_entry_path),
    )

    assert proc.returncode == 0, proc.stderr
    payload = _payload(proc.stdout)
    assert payload["status"] == "ready_for_operator_completion_ledger_update"
    assert payload["first_blocking_gate"] == ""
    assert payload["gates_ran"] == 11
    assert payload["gate_count"] == 11
    assert payload["gate_results"][10]["id"] == "completion_ledger"
    assert payload["gate_results"][10]["details"]["ledger_entry_review_ready"] is True
    assert payload["gate_results"][10]["details"]["ledger_entry_exists"] is True
    assert payload["gate_results"][10]["details"]["prohibited_clearance_flags"] == []
    assert payload["evidence_chain_decision_ready"] is True
    assert payload["ledger_completion_review_ready"] is True
    assert payload["completion_ledger_handoff_ready"] is True
    assert payload["physical_validation_complete"] is False
    assert payload["stage17_completion_claim_allowed"] is False
    assert payload["powered_or_frame_coupled_testing_cleared"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_evidence_chain_status_fails_closed_on_unsafe_completion_ledger_handoff(
    tmp_path: Path,
) -> None:
    measurement_path, mockup_path, mannequin_path, static_fit_path, movement_path, release_cable_path = (
        _write_release_ready_records(tmp_path)
    )
    engineering_review_path = tmp_path / "ready-engineering-review.json"
    engineering_review_path.write_text(
        json.dumps(_ready_engineering_review_payload(release_cable_path)),
        encoding="utf-8",
    )
    evidence_paths = (
        measurement_path,
        mockup_path,
        mannequin_path,
        static_fit_path,
        movement_path,
        release_cable_path,
        engineering_review_path,
    )
    final_physical_gate_record_path = _write_final_physical_gate_record(tmp_path, evidence_paths)
    final_decision_path = tmp_path / "ready-final-decision.json"
    final_decision_path.write_text(
        json.dumps(_ready_final_decision_payload(final_physical_gate_record_path)),
        encoding="utf-8",
    )
    ledger_entry_path = tmp_path / "unsafe-ledger-handoff.md"
    ledger_entry_path.write_text(
        _ready_ledger_entry(final_decision_path).replace(
            "FR-018 implementation remains blocked and not cleared.",
            "FR-018 cleared.",
        ),
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
        "-EngineeringReviewPath",
        str(engineering_review_path),
        "-FinalDecisionPath",
        str(final_decision_path),
        "-LedgerEntryPath",
        str(ledger_entry_path),
    )

    assert proc.returncode == 1
    payload = _payload(proc.stdout)
    assert payload["status"] == "failed_completion_ledger"
    assert payload["first_blocking_gate"] == "completion_ledger"
    assert payload["first_blocking_status"] == "failed_completion_ledger_entry"
    assert "ledger_entry.FR-018_cleared" in payload["first_blocking_details"]["prohibited_clearance_flags"]
    assert payload["evidence_chain_decision_ready"] is False
    assert payload["ledger_completion_review_ready"] is False
    assert payload["completion_ledger_handoff_ready"] is False
    assert payload["physical_validation_complete"] is False
    assert payload["stage17_completion_claim_allowed"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_evidence_chain_status_surfaces_final_gate_pilot_identity_mismatch(
    tmp_path: Path,
) -> None:
    measurement_path, mockup_path, mannequin_path, static_fit_path, movement_path, release_cable_path = (
        _write_release_ready_records(tmp_path)
    )
    mockup_payload = json.loads(mockup_path.read_text(encoding="utf-8"))
    mockup_payload["evidence"]["pilot_id"] = "different-pilot"
    mockup_path.write_text(json.dumps(mockup_payload), encoding="utf-8")
    engineering_review_path = tmp_path / "ready-engineering-review.json"
    engineering_review_path.write_text(
        json.dumps(_ready_engineering_review_payload(release_cable_path)),
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
        "-EngineeringReviewPath",
        str(engineering_review_path),
    )

    assert proc.returncode == 1
    payload = _payload(proc.stdout)
    assert payload["status"] == "failed_final_physical_gate"
    assert payload["first_blocking_gate"] == "final_physical_gate"
    assert payload["first_blocking_status"] == "failed_pilot_identity_continuity"
    assert payload["first_blocking_details"]["evidence_chronology_violations"] == []
    assert payload["first_blocking_details"]["pilot_identity_continuity_violations"] == [
        "mockup.evidence.pilot_id_must_match_measurement"
    ]
    assert payload["first_blocking_details"]["pilot_identity_continuity_reference_record"] == "measurement"
    assert payload["first_blocking_details"]["pilot_identity_continuity_reference_fingerprint"]
    assert payload["first_blocking_details"]["failed_reasons"] == ["pilot_identity_continuity_violation"]
    assert payload["gate_results"][8]["details"]["pilot_identity_continuity_violations"] == [
        "mockup.evidence.pilot_id_must_match_measurement"
    ]
    assert payload["evidence_chain_decision_ready"] is False
    assert payload["physical_validation_complete"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_evidence_chain_status_fails_closed_on_measurement_symptom(tmp_path: Path) -> None:
    measurement_path = tmp_path / "symptom-measurements.json"
    payload = _ready_measurement_payload()
    payload["safety_screen"]["tingling"] = True
    measurement_path.write_text(json.dumps(payload), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-MeasurementPath", str(measurement_path))

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "failed_measurement_intake"
    assert result["first_blocking_gate"] == "measurement_intake"
    assert result["first_blocking_status"] == "failed_requires_redesign_or_medical_review"
    assert (
        result["next_required_input"]
        == "scripts/fr017-new-measurement-record.ps1 + FR-017-MEASUREMENT-CAPTURE-RUNBOOK.md + FR-017-MEASUREMENTS-INPUT-TEMPLATE.json"
    )
    assert result["first_blocking_details"]["safety_blockers"] == ["tingling"]
    assert result["gate_results"][1]["details"]["safety_blockers"] == ["tingling"]
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_evidence_chain_status_keeps_measurement_symptom_failed_when_fields_are_missing(
    tmp_path: Path,
) -> None:
    measurement_path = tmp_path / "symptom-incomplete-measurements.json"
    payload = _ready_measurement_payload()
    del payload["evidence"]["observer"]
    payload["safety_screen"]["tingling"] = True
    measurement_path.write_text(json.dumps(payload), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-MeasurementPath", str(measurement_path))

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "failed_measurement_intake"
    assert result["first_blocking_gate"] == "measurement_intake"
    assert result["first_blocking_status"] == "failed_requires_redesign_or_medical_review"
    assert "evidence.observer" in result["first_blocking_details"]["missing_fields"]
    assert result["first_blocking_details"]["safety_blockers"] == ["tingling"]
    assert result["gate_results"][1]["details"]["safety_blockers"] == ["tingling"]
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_evidence_chain_status_surfaces_release_fail_observation_when_fields_are_missing(
    tmp_path: Path,
) -> None:
    measurement_path, mockup_path, mannequin_path, static_fit_path, movement_path = _write_movement_ready_records(
        tmp_path
    )
    release_cable_path = tmp_path / "release-fail-and-missing.json"
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
    assert result["status"] == "failed_quick_release_cable_snag"
    assert result["first_blocking_gate"] == "quick_release_cable_snag"
    assert result["first_blocking_status"] == "failed_requires_release_cable_redesign_or_medical_review"
    assert "evidence.observer" in result["first_blocking_details"]["missing_fields"]
    assert result["first_blocking_details"]["fail_observations"] == ["sides.left.fail_observations.release_hidden"]
    assert result["gate_results"][6]["details"]["fail_observations"] == ["sides.left.fail_observations.release_hidden"]
    assert result["physical_validation_complete"] is False
    assert result["stage17_completion_claim_allowed"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_evidence_chain_status_surfaces_engineering_prohibited_clearance_when_fields_are_missing(
    tmp_path: Path,
) -> None:
    measurement_path, mockup_path, mannequin_path, static_fit_path, movement_path, release_cable_path = (
        _write_release_ready_records(tmp_path)
    )
    engineering_review_path = tmp_path / "engineering-clearance-and-missing.json"
    payload = _ready_engineering_review_payload(release_cable_path)
    del payload["evidence"]["reviewer"]
    payload["review_decision"]["fr018_implementation_cleared"] = True
    engineering_review_path.write_text(json.dumps(payload), encoding="utf-8")

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
        "-EngineeringReviewPath",
        str(engineering_review_path),
    )

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "failed_engineering_review"
    assert result["first_blocking_gate"] == "engineering_review"
    assert result["first_blocking_status"] == "failed_requires_stage17_redesign_or_review_rejection"
    assert "evidence.reviewer" in result["first_blocking_details"]["missing_fields"]
    assert result["first_blocking_details"]["prohibited_clearance_flags"] == [
        "review_decision.fr018_implementation_cleared"
    ]
    assert result["gate_results"][7]["details"]["prohibited_clearance_flags"] == [
        "review_decision.fr018_implementation_cleared"
    ]
    assert result["physical_validation_complete"] is False
    assert result["stage17_completion_claim_allowed"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_evidence_chain_status_fails_closed_on_left_right_independence_blocker(tmp_path: Path) -> None:
    measurement_path = tmp_path / "copied-left-right-measurements.json"
    payload = _ready_measurement_payload()
    payload["left_right_independence"]["values_not_copied_between_sides"] = False
    measurement_path.write_text(json.dumps(payload), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-MeasurementPath", str(measurement_path))

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    expected = ["left_right_independence.values_not_copied_between_sides_must_be_true"]
    assert result["status"] == "failed_measurement_intake"
    assert result["first_blocking_gate"] == "measurement_intake"
    assert result["first_blocking_status"] == "invalid_measurement_record"
    assert result["first_blocking_details"]["left_right_independence_blockers"] == expected
    assert result["gate_results"][1]["details"]["left_right_independence_blockers"] == expected
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_evidence_chain_status_fails_closed_on_identical_left_right_profile(tmp_path: Path) -> None:
    measurement_path = tmp_path / "identical-left-right-measurements.json"
    payload = _ready_measurement_payload()
    payload["sides"]["right"] = dict(payload["sides"]["left"])
    measurement_path.write_text(json.dumps(payload), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-MeasurementPath", str(measurement_path))

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    expected = ["left_right_independence.all_required_numeric_measurements_identical_requires_recheck"]
    assert result["status"] == "failed_measurement_intake"
    assert result["first_blocking_gate"] == "measurement_intake"
    assert result["first_blocking_status"] == "invalid_measurement_record"
    assert result["first_blocking_details"]["left_right_independence_blockers"] == expected
    assert result["gate_results"][1]["details"]["left_right_independence_blockers"] == expected
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_evidence_chain_status_fails_closed_on_measurement_condition_blocker(tmp_path: Path) -> None:
    measurement_path = tmp_path / "tissue-compression.json"
    payload = _ready_measurement_payload()
    payload["measurement_conditions"]["no_tissue_compression_used"] = False
    measurement_path.write_text(json.dumps(payload), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-MeasurementPath", str(measurement_path))

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    expected = ["measurement_conditions.no_tissue_compression_used_must_be_true"]
    assert result["status"] == "failed_measurement_intake"
    assert result["first_blocking_gate"] == "measurement_intake"
    assert result["first_blocking_status"] == "invalid_measurement_record"
    assert result["first_blocking_details"]["measurement_condition_blockers"] == expected
    assert result["gate_results"][1]["details"]["measurement_condition_blockers"] == expected
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_evidence_chain_status_surfaces_measurement_note_blockers(tmp_path: Path) -> None:
    measurement_path = tmp_path / "generic-measurement-notes.json"
    payload = _ready_measurement_payload()
    payload["measurement_conditions"]["condition_notes"] = "Fixture complete."
    measurement_path.write_text(json.dumps(payload), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-MeasurementPath", str(measurement_path))

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    expected = [
        "measurement_conditions.condition_notes_must_reference_no_tissue",
        "measurement_conditions.condition_notes_must_reference_wrist",
        "measurement_conditions.condition_notes_must_reference_metric",
        "measurement_conditions.condition_notes_must_reference_stop",
    ]
    assert result["status"] == "failed_measurement_intake"
    assert result["first_blocking_gate"] == "measurement_intake"
    assert result["first_blocking_status"] == "invalid_measurement_record"
    assert result["first_blocking_details"]["measurement_note_blockers"] == expected
    assert result["gate_results"][1]["details"]["measurement_note_blockers"] == expected
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_evidence_chain_status_fails_closed_on_landmark_confirmation_blocker(tmp_path: Path) -> None:
    measurement_path = tmp_path / "unconfirmed-landmark.json"
    payload = _ready_measurement_payload()
    payload["landmark_confirmation"]["wrist_bone_boundary_confirmed"] = False
    measurement_path.write_text(json.dumps(payload), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-MeasurementPath", str(measurement_path))

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    expected = ["landmark_confirmation.wrist_bone_boundary_confirmed_must_be_true"]
    assert result["status"] == "failed_measurement_intake"
    assert result["first_blocking_gate"] == "measurement_intake"
    assert result["first_blocking_status"] == "invalid_measurement_record"
    assert result["first_blocking_details"]["landmark_confirmation_blockers"] == expected
    assert result["gate_results"][1]["details"]["landmark_confirmation_blockers"] == expected
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False
