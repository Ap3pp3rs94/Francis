from __future__ import annotations

import json
import shutil
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest

from tests.powershell_script_runner import run_powershell_script
from tests.test_fr017_mockup_readiness_gate_script import _ready_measurement_payload
from tests.test_fr017_quick_release_cable_snag_gate_script import (
    _ready_release_cable_payload,
    _write_movement_ready_records,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "fr017-engineering-review-gate.ps1"


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
    return {step["id"]: step for step in payload["engineering_review_capture_plan_status"]}


def _write_release_ready_records(tmp_path: Path) -> tuple[Path, Path, Path, Path, Path, Path]:
    measurement_path, mockup_path, mannequin_path, static_fit_path, movement_path = _write_movement_ready_records(
        tmp_path
    )
    release_cable_path = tmp_path / "ready-release-cable.json"
    release_cable_path.write_text(
        json.dumps(_ready_release_cable_payload(movement_path)),
        encoding="utf-8",
    )
    return measurement_path, mockup_path, mannequin_path, static_fit_path, movement_path, release_cable_path


def _ready_engineering_review_payload(release_cable_path: Path) -> dict[str, Any]:
    return {
        "kind": "francis.fr017.engineering_review.v1",
        "component": "FR-017 Forearm Cuffs",
        "evidence": {
            "date": "2026-06-23",
            "reviewer": "test-reviewer",
            "reviewer_role": "professional-engineering-review-fixture",
            "reviewer_credential_reference": "test-credential-reference",
            "pilot_id": "pilot-reference",
            "quick_release_cable_snag_record_path": str(release_cable_path),
            "review_scope": "non-powered FR-017 forearm cuff physical-validation evidence review only",
        },
        "review_constraints": {
            "documentation_package_reviewed": True,
            "measurement_record_reviewed": True,
            "mockup_record_reviewed": True,
            "mannequin_record_reviewed": True,
            "pilot_static_record_reviewed": True,
            "pilot_movement_record_reviewed": True,
            "quick_release_cable_record_reviewed": True,
            "no_load_bearing_claim_approved": True,
            "no_powered_testing_cleared": True,
            "no_frame_coupled_testing_cleared": True,
            "fr018_implementation_not_cleared": True,
            "redesign_items_closed_or_blocked": True,
        },
        "safety_review": {
            "circulation_nerve_risk_reviewed": True,
            "quick_release_access_reviewed": True,
            "glove_wrist_removal_reviewed": True,
            "cable_route_reviewed": True,
            "symptom_fail_conditions_reviewed": True,
            "stop_conditions_preserved": True,
        },
        "review_decision": {
            "non_powered_fr017_physical_validation_accepted": True,
            "requires_redesign": False,
            "load_bearing_use_approved": False,
            "powered_testing_approved": False,
            "frame_coupled_testing_approved": False,
            "fr018_implementation_cleared": False,
            "engineering_review_notes": "Fixture accepts only non-powered FR-017 evidence.",
        },
    }


def test_fr017_engineering_review_gate_reports_default_templates_as_pending_upstream() -> None:
    proc = _run_gate("-Mode", "Status")

    assert proc.returncode == 0, proc.stderr
    payload = _payload(proc.stdout)
    assert payload["kind"] == "francis.fr017.engineering_review_gate"
    assert payload["status"] == "pending_quick_release_cable_snag_gate"
    assert payload["upstream_quick_release_cable_snag_status"] == "pending_pilot_movement_gate"
    assert payload["upstream_quick_release_cable_snag_gate_ready"] is False
    assert payload["upstream_measurement_intake_status"] == "pending_measurements"
    assert payload["physical_validation_complete"] is False
    assert payload["stage17_completion_claim_allowed"] is False
    assert payload["engineering_review_complete"] is False
    assert payload["final_physical_gate_audit_ready"] is False
    assert payload["load_bearing_use_approved"] is False
    assert payload["fr018_implementation_cleared"] is False
    assert payload["engineering_review_capture_plan_not_completion_evidence"] is True
    assert "not physical validation evidence" in payload["engineering_review_capture_plan_contract"]
    assert "fr017-new-engineering-review-record.ps1" in payload["engineering_review_capture_runbook_contract"]
    assert "engineering-review capture readiness only" in payload["engineering_review_capture_plan_status_contract"]
    assert "not physical validation evidence" in payload["engineering_review_capture_summary_contract"]
    assert (
        payload["next_required_engineering_review_input"]
        == "create_professional_engineering_review_record_with_fr017-new-engineering-review-record.ps1_then_rerun_engineering_review_gate"
    )
    assert payload["engineering_review_input_template_path"].endswith(
        "FR-017_Stage17_Package\\FR-017-ENGINEERING-REVIEW-INPUT-TEMPLATE.json"
    )
    assert payload["engineering_review_record_initializer_path"].endswith(
        "scripts\\fr017-new-engineering-review-record.ps1"
    )
    assert payload["engineering_review_working_record_name_pattern"] == (
        "FR-017-ENGINEERING-REVIEW-YYYY-MM-DD-PILOT-RECORD.json"
    )
    assert payload["engineering_review_capture_total_groups"] == 4
    assert payload["engineering_review_capture_ready_groups"] == 0
    assert payload["engineering_review_capture_pending_groups"] == 0
    assert payload["engineering_review_capture_invalid_groups"] == 0
    assert payload["engineering_review_capture_failed_groups"] == 0
    assert payload["engineering_review_capture_upstream_blocked_groups"] == 4
    assert payload["engineering_review_capture_first_blocking_group_id"] == "engineering_review_evidence_and_linkage"
    assert (
        payload["engineering_review_capture_first_blocking_group_status"]
        == "blocked_by_upstream_quick_release_cable_snag"
    )
    assert "quick-release/cable-snag" in payload["engineering_review_capture_first_blocking_group_action"]
    assert [step["id"] for step in payload["engineering_review_capture_plan"]] == [
        "engineering_review_evidence_and_linkage",
        "engineering_review_constraints",
        "engineering_safety_review",
        "engineering_review_decision_and_limits",
    ]
    required_fields = [
        field for step in payload["engineering_review_capture_plan"] for field in step["required_fields"]
    ]
    assert "evidence.quick_release_cable_snag_record_path" in required_fields
    assert "review_constraints.fr018_implementation_not_cleared" in required_fields
    assert "safety_review.quick_release_access_reviewed" in required_fields
    assert "review_decision.powered_testing_approved" in required_fields
    assert all(
        step["status"] == "blocked_by_upstream_quick_release_cable_snag"
        for step in payload["engineering_review_capture_plan_status"]
    )
    assert all(
        not step["ready_for_engineering_review_record_review"]
        for step in payload["engineering_review_capture_plan_status"]
    )
    assert payload["read_only_contract"] is True
    assert payload["writes_repo"] is False
    assert payload["grants_mutation_authority"] is False


def test_fr017_engineering_review_gate_requires_review_after_release_ready(tmp_path: Path) -> None:
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
    assert payload["status"] == "pending_engineering_review"
    assert payload["upstream_quick_release_cable_snag_status"] == (
        "ready_for_engineering_review_or_final_physical_gate_audit"
    )
    assert payload["upstream_quick_release_cable_snag_gate_ready"] is True
    assert "evidence.date" in payload["missing_fields"]
    assert payload["engineering_review_complete"] is False
    assert payload["physical_validation_complete"] is False
    assert payload["stage17_completion_claim_allowed"] is False
    assert payload["load_bearing_use_approved"] is False
    assert payload["fr018_implementation_cleared"] is False
    assert "fr017-new-engineering-review-record.ps1" in payload["engineering_review_capture_runbook_contract"]
    assert payload["engineering_review_record_initializer_path"].endswith(
        "scripts\\fr017-new-engineering-review-record.ps1"
    )
    assert payload["engineering_review_capture_total_groups"] == 4
    assert payload["engineering_review_capture_ready_groups"] == 0
    assert payload["engineering_review_capture_pending_groups"] == 4
    assert payload["engineering_review_capture_invalid_groups"] == 0
    assert payload["engineering_review_capture_failed_groups"] == 0
    assert payload["engineering_review_capture_upstream_blocked_groups"] == 0
    assert payload["engineering_review_capture_first_blocking_group_id"] == "engineering_review_evidence_and_linkage"
    assert payload["engineering_review_capture_first_blocking_group_status"] == "pending_required_fields"
    capture_status = _capture_status_by_id(payload)
    assert "evidence.date" in capture_status["engineering_review_evidence_and_linkage"]["missing_fields"]
    assert (
        "review_constraints.documentation_package_reviewed"
        in capture_status["engineering_review_constraints"]["missing_fields"]
    )
    assert (
        "safety_review.quick_release_access_reviewed" in capture_status["engineering_safety_review"]["missing_fields"]
    )
    assert (
        "review_decision.engineering_review_notes"
        in capture_status["engineering_review_decision_and_limits"]["missing_fields"]
    )


def test_fr017_engineering_review_gate_treats_lowercase_or_padded_pending_text_as_missing(
    tmp_path: Path,
) -> None:
    measurement_path, mockup_path, mannequin_path, static_fit_path, movement_path, release_cable_path = (
        _write_release_ready_records(tmp_path)
    )
    engineering_review_path = tmp_path / "placeholder-engineering-review.json"
    review_payload = _ready_engineering_review_payload(release_cable_path)
    review_payload["evidence"]["reviewer"] = " pending "
    review_payload["evidence"]["pilot_id"] = "pending"
    review_payload["review_constraints"]["documentation_package_reviewed"] = " PENDING "
    review_payload["review_decision"]["engineering_review_notes"] = " pending "
    engineering_review_path.write_text(json.dumps(review_payload), encoding="utf-8")

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
    assert payload["status"] == "pending_engineering_review"
    assert payload["invalid_fields"] == []
    assert "evidence.reviewer" in payload["missing_fields"]
    assert "evidence.pilot_id" in payload["missing_fields"]
    assert "review_constraints.documentation_package_reviewed" in payload["missing_fields"]
    assert "review_decision.engineering_review_notes" in payload["missing_fields"]
    assert payload["physical_validation_complete"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_engineering_review_gate_accepts_complete_non_powered_review_record(tmp_path: Path) -> None:
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
    assert payload["status"] == "ready_for_final_stage17_physical_gate_audit"
    assert payload["engineering_review_status"] == "ready_for_final_stage17_physical_gate_audit"
    assert payload["upstream_quick_release_cable_snag_gate_ready"] is True
    assert payload["missing_fields"] == []
    assert payload["invalid_fields"] == []
    assert payload["record_linkage_violations"] == []
    assert payload["record_chronology_violations"] == []
    assert payload["review_redesign_triggers"] == []
    assert payload["prohibited_clearance_flags"] == []
    assert payload["engineering_review_complete"] is True
    assert payload["final_physical_gate_audit_ready"] is True
    assert payload["physical_validation_complete"] is False
    assert payload["stage17_completion_claim_allowed"] is False
    assert payload["load_bearing_use_approved"] is False
    assert payload["powered_or_frame_coupled_testing_cleared"] is False
    assert payload["fr018_implementation_cleared"] is False
    assert payload["engineering_review_capture_total_groups"] == 4
    assert payload["engineering_review_capture_ready_groups"] == 4
    assert payload["engineering_review_capture_pending_groups"] == 0
    assert payload["engineering_review_capture_invalid_groups"] == 0
    assert payload["engineering_review_capture_failed_groups"] == 0
    assert payload["engineering_review_capture_upstream_blocked_groups"] == 0
    assert payload["engineering_review_capture_first_blocking_group_id"] == ""
    assert payload["engineering_review_capture_first_blocking_group_status"] == ""
    assert payload["engineering_review_capture_first_blocking_group_action"] == ""
    assert all(
        step["status"] == "ready_for_engineering_review_record_review"
        for step in payload["engineering_review_capture_plan_status"]
    )
    assert all(
        step["ready_for_engineering_review_record_review"] for step in payload["engineering_review_capture_plan_status"]
    )
    assert "Use unquoted JSON booleans only" in payload["boolean_value_contract"]
    assert "must resolve to the same quick-release/cable-snag record path" in payload["record_linkage_contract"]
    assert (
        "must match evidence.pilot_id in the linked quick-release/cable-snag record"
        in payload["pilot_identity_linkage_contract"]
    )
    assert "YYYY-MM-DD" in payload["evidence_date_contract"]
    assert "same as or later than the linked quick-release/cable-snag" in payload["evidence_chronology_contract"]
    assert "non-powered FR-017" in payload["review_scope_contract"]


def test_fr017_engineering_review_gate_rejects_broadened_review_scope(tmp_path: Path) -> None:
    measurement_path, mockup_path, mannequin_path, static_fit_path, movement_path, release_cable_path = (
        _write_release_ready_records(tmp_path)
    )
    engineering_review_path = tmp_path / "broadened-scope-engineering-review.json"
    payload = _ready_engineering_review_payload(release_cable_path)
    payload["evidence"]["review_scope"] = "powered exosystem review and FR-018 clearance"
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
    assert result["status"] == "failed_engineering_review_record"
    assert result["invalid_fields"] == ["evidence.review_scope"]
    assert result["engineering_review_complete"] is False
    assert result["final_physical_gate_audit_ready"] is False
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_engineering_review_gate_rejects_malformed_evidence_date(tmp_path: Path) -> None:
    measurement_path, mockup_path, mannequin_path, static_fit_path, movement_path, release_cable_path = (
        _write_release_ready_records(tmp_path)
    )
    engineering_review_path = tmp_path / "malformed-date-engineering-review.json"
    payload = _ready_engineering_review_payload(release_cable_path)
    payload["evidence"]["date"] = "06/23/2026"
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
    assert result["status"] == "failed_engineering_review_record"
    assert result["invalid_fields"] == ["evidence.date"]
    assert result["engineering_review_complete"] is False
    assert result["final_physical_gate_audit_ready"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_engineering_review_gate_rejects_future_evidence_date(tmp_path: Path) -> None:
    measurement_path, mockup_path, mannequin_path, static_fit_path, movement_path, release_cable_path = (
        _write_release_ready_records(tmp_path)
    )
    engineering_review_path = tmp_path / "future-date-engineering-review.json"
    payload = _ready_engineering_review_payload(release_cable_path)
    payload["evidence"]["date"] = (date.today() + timedelta(days=1)).isoformat()
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
    assert result["status"] == "failed_engineering_review_record"
    assert result["invalid_fields"] == ["evidence.date"]
    assert result["engineering_review_complete"] is False
    assert result["final_physical_gate_audit_ready"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_engineering_review_gate_rejects_review_date_before_release_cable_date(
    tmp_path: Path,
) -> None:
    measurement_path, mockup_path, mannequin_path, static_fit_path, movement_path, release_cable_path = (
        _write_release_ready_records(tmp_path)
    )
    engineering_review_path = tmp_path / "backdated-engineering-review.json"
    payload = _ready_engineering_review_payload(release_cable_path)
    payload["evidence"]["date"] = "2026-06-22"
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
    assert result["status"] == "failed_engineering_review_record"
    assert result["invalid_fields"] == []
    assert result["record_linkage_violations"] == []
    assert result["record_chronology_violations"] == ["evidence.date_before_release_cable.evidence.date"]
    assert result["review_redesign_triggers"] == []
    assert result["prohibited_clearance_flags"] == []
    assert result["engineering_review_complete"] is False
    assert result["final_physical_gate_audit_ready"] is False
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_engineering_review_gate_rejects_unlinked_release_cable_record(tmp_path: Path) -> None:
    measurement_path, mockup_path, mannequin_path, static_fit_path, movement_path, release_cable_path = (
        _write_release_ready_records(tmp_path)
    )
    unrelated_release_cable_path = tmp_path / "unrelated-release-cable.json"
    unrelated_release_cable_path.write_text(
        json.dumps(_ready_release_cable_payload(movement_path)),
        encoding="utf-8",
    )
    engineering_review_path = tmp_path / "unlinked-engineering-review.json"
    engineering_review_path.write_text(
        json.dumps(_ready_engineering_review_payload(unrelated_release_cable_path)),
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
    assert payload["status"] == "failed_engineering_review_record"
    assert payload["engineering_review_status"] == "failed_engineering_review_record"
    assert payload["record_linkage_violations"] == [
        "evidence.quick_release_cable_snag_record_path_must_match_release_cable_path"
    ]
    assert payload["invalid_fields"] == []
    assert payload["engineering_review_complete"] is False
    assert payload["final_physical_gate_audit_ready"] is False
    assert payload["physical_validation_complete"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_engineering_review_gate_rejects_mismatched_release_cable_pilot_id(tmp_path: Path) -> None:
    measurement_path, mockup_path, mannequin_path, static_fit_path, movement_path, release_cable_path = (
        _write_release_ready_records(tmp_path)
    )
    engineering_review_path = tmp_path / "mismatched-pilot-engineering-review.json"
    payload = _ready_engineering_review_payload(release_cable_path)
    payload["evidence"]["pilot_id"] = "different-pilot"
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
    payload = _payload(proc.stdout)
    assert payload["status"] == "failed_engineering_review_record"
    assert payload["engineering_review_status"] == "failed_engineering_review_record"
    assert payload["record_linkage_violations"] == ["evidence.pilot_id_must_match_release_cable_pilot_id"]
    assert payload["invalid_fields"] == []
    assert payload["engineering_review_complete"] is False
    assert payload["final_physical_gate_audit_ready"] is False
    assert payload["physical_validation_complete"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_engineering_review_gate_blocks_measurement_rejected_by_intake(tmp_path: Path) -> None:
    measurement_path = tmp_path / "quoted-measurements.json"
    payload = _ready_measurement_payload()
    payload["sides"]["left"]["forearm_length_elbow_crease_to_wrist_crease"] = "258"
    measurement_path.write_text(json.dumps(payload), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-MeasurementPath", str(measurement_path))

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "failed_upstream_quick_release_cable_snag_gate"
    assert result["upstream_quick_release_cable_snag_status"] == "failed_upstream_pilot_movement_gate"
    assert result["upstream_quick_release_cable_snag_gate_ready"] is False
    assert result["upstream_pilot_movement_status"] == "failed_upstream_static_fit_gate"
    assert result["upstream_static_fit_status"] == "failed_upstream_mannequin_gate"
    assert result["upstream_mannequin_status"] == "failed_upstream_mockup_gate"
    assert result["upstream_mockup_status"] == "invalid_measurement_record"
    assert result["upstream_measurement_intake_status"] == "invalid_measurement_record"
    assert result["upstream_measurement_invalid_fields"] == ["sides.left.forearm_length_elbow_crease_to_wrist_crease"]
    assert result["engineering_review_complete"] is False
    assert result["final_physical_gate_audit_ready"] is False
    assert result["physical_validation_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_engineering_review_gate_blocks_powered_testing_clearance(tmp_path: Path) -> None:
    measurement_path, mockup_path, mannequin_path, static_fit_path, movement_path, release_cable_path = (
        _write_release_ready_records(tmp_path)
    )
    engineering_review_path = tmp_path / "powered-clearance.json"
    payload = _ready_engineering_review_payload(release_cable_path)
    payload["review_decision"]["powered_testing_approved"] = True
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
    assert result["status"] == "failed_requires_stage17_redesign_or_review_rejection"
    assert result["prohibited_clearance_flags"] == ["review_decision.powered_testing_approved"]
    assert result["engineering_review_capture_total_groups"] == 4
    assert result["engineering_review_capture_ready_groups"] == 3
    assert result["engineering_review_capture_pending_groups"] == 0
    assert result["engineering_review_capture_invalid_groups"] == 0
    assert result["engineering_review_capture_failed_groups"] == 1
    assert result["engineering_review_capture_upstream_blocked_groups"] == 0
    assert result["engineering_review_capture_first_blocking_group_id"] == "engineering_review_decision_and_limits"
    assert (
        result["engineering_review_capture_first_blocking_group_status"] == "failed_stop_condition_or_blocking_signal"
    )
    capture_status = _capture_status_by_id(result)
    assert capture_status["engineering_review_decision_and_limits"]["blocking_signals"] == [
        "review_decision.powered_testing_approved"
    ]
    assert result["engineering_review_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_engineering_review_gate_blocks_redesign_requirement(tmp_path: Path) -> None:
    measurement_path, mockup_path, mannequin_path, static_fit_path, movement_path, release_cable_path = (
        _write_release_ready_records(tmp_path)
    )
    engineering_review_path = tmp_path / "requires-redesign.json"
    payload = _ready_engineering_review_payload(release_cable_path)
    payload["review_decision"]["requires_redesign"] = True
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
    assert result["status"] == "failed_requires_stage17_redesign_or_review_rejection"
    assert result["prohibited_clearance_flags"] == ["review_decision.requires_redesign"]
    assert result["engineering_review_complete"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_engineering_review_gate_rejection_overrides_missing_fields(tmp_path: Path) -> None:
    measurement_path, mockup_path, mannequin_path, static_fit_path, movement_path, release_cable_path = (
        _write_release_ready_records(tmp_path)
    )
    engineering_review_path = tmp_path / "rejection-and-missing-review.json"
    payload = _ready_engineering_review_payload(release_cable_path)
    del payload["evidence"]["reviewer"]
    payload["review_decision"]["powered_testing_approved"] = True
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
    assert result["status"] == "failed_requires_stage17_redesign_or_review_rejection"
    assert result["missing_fields"] == ["evidence.reviewer"]
    assert result["prohibited_clearance_flags"] == ["review_decision.powered_testing_approved"]
    assert result["engineering_review_complete"] is False
    assert result["final_physical_gate_audit_ready"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_engineering_review_gate_rejects_quoted_boolean_text(tmp_path: Path) -> None:
    measurement_path, mockup_path, mannequin_path, static_fit_path, movement_path, release_cable_path = (
        _write_release_ready_records(tmp_path)
    )
    engineering_review_path = tmp_path / "quoted-boolean-review.json"
    payload = _ready_engineering_review_payload(release_cable_path)
    payload["review_constraints"]["documentation_package_reviewed"] = "true"
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
    assert result["status"] == "failed_engineering_review_record"
    assert result["invalid_fields"] == ["review_constraints.documentation_package_reviewed"]
    assert result["review_redesign_triggers"] == []
    assert result["fr018_implementation_cleared"] is False
