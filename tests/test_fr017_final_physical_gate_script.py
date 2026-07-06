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
from tests.test_fr017_mockup_readiness_gate_script import _ready_measurement_payload
from tests.test_fr017_pilot_movement_gate_script import (
    _ready_movement_payload,
    _write_static_ready_records,
)
from tests.test_fr017_pilot_static_fit_gate_script import (
    _ready_static_fit_payload,
    _write_upstream_ready_records as _write_static_fit_upstream_ready_records,
)
from tests.test_fr017_quick_release_cable_snag_gate_script import _ready_release_cable_payload
from tests.test_fr017_stage17_validation_gate_script import _copy_stage17_package


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "fr017-final-physical-gate.ps1"


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
        timeout_seconds=80,
    )


def _payload(stdout: str) -> dict[str, Any]:
    return json.loads(stdout)


def _portable_path(path: str) -> str:
    return path.replace("\\", "/")


def _decision_status_by_id(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {step["id"]: step for step in payload["final_physical_decision_plan_status"]}


def test_fr017_final_physical_gate_reports_default_templates_as_pending() -> None:
    proc = _run_gate("-Mode", "Status")

    assert proc.returncode == 0, proc.stderr
    payload = _payload(proc.stdout)
    assert payload["kind"] == "francis.fr017.final_physical_gate"
    assert payload["status"] == "pending_engineering_review_gate"
    assert payload["stage17_package_gate_status"] == "blocked_physical_validation"
    assert payload["engineering_review_gate_status"] == "pending_quick_release_cable_snag_gate"
    assert payload["engineering_review_gate_ready"] is False
    assert payload["upstream_measurement_intake_status"] == "pending_measurements"
    assert (
        payload["upstream_next_required_physical_input"]
        == "create_pending_record_with_fr017-new-measurement-record.ps1_then_capture_with_FR-017-MEASUREMENT-CAPTURE-RUNBOOK.md_and_rerun_measurement_intake"
    )
    assert payload["upstream_measurement_capture_plan_not_completion_evidence"] is True
    assert "intake readiness only" in payload["upstream_measurement_capture_plan_status_contract"]
    assert "not physical validation evidence" in payload["upstream_measurement_capture_summary_contract"]
    assert payload["upstream_measurement_capture_total_groups"] == 5
    assert payload["upstream_measurement_capture_ready_groups"] == 0
    assert payload["upstream_measurement_capture_pending_groups"] == 5
    assert payload["upstream_measurement_capture_invalid_groups"] == 0
    assert payload["upstream_measurement_capture_failed_groups"] == 0
    assert payload["upstream_measurement_capture_first_blocking_group_id"] == "setup_and_safety_brief"
    assert payload["upstream_measurement_capture_first_blocking_group_status"] == "pending_required_fields"
    assert "brief stop conditions" in payload["upstream_measurement_capture_first_blocking_group_action"]
    capture_status = payload["upstream_measurement_capture_plan_status"]
    assert isinstance(capture_status, list)
    assert [step["id"] for step in capture_status] == [
        "setup_and_safety_brief",
        "left_arm_numeric_measurement_passes",
        "right_arm_numeric_measurement_passes",
        "safety_critical_landmark_and_zone_references",
        "left_right_independence_and_safety_screen",
    ]
    assert all(step["status"] == "pending_required_fields" for step in capture_status)
    assert "evidence.date" in capture_status[0]["missing_fields"]
    assert "safety_screen.loss_of_grip_strength" in capture_status[-1]["missing_fields"]
    assert payload["documentation_complete"] is True
    assert payload["evidence_containers_complete"] is True
    assert payload["physical_validation_evidence_chain_complete"] is False
    assert payload["physical_validation_complete"] is False
    assert payload["stage17_completion_claim_allowed"] is False
    assert payload["fr018_implementation_cleared"] is False
    assert payload["final_physical_decision_plan_not_completion_evidence"] is True
    assert "not physical validation evidence" in payload["final_physical_decision_plan_contract"]
    assert "fr017-new-final-decision-record.ps1" in payload["final_physical_decision_runbook_contract"]
    assert "final physical decision readiness only" in payload["final_physical_decision_plan_status_contract"]
    assert "not physical validation evidence" in payload["final_physical_decision_summary_contract"]
    assert payload["next_required_final_physical_input"] == (
        "create_human_final_decision_record_with_fr017-new-final-decision-record.ps1_then_rerun_final_decision_record_gate"
    )
    assert _portable_path(payload["final_decision_input_template_path"]).endswith(
        "FR-017_Stage17_Package/FR-017-FINAL-PHYSICAL-DECISION-INPUT-TEMPLATE.json"
    )
    assert _portable_path(payload["final_decision_record_initializer_path"]).endswith(
        "scripts/fr017-new-final-decision-record.ps1"
    )
    assert payload["final_decision_working_record_name_pattern"] == (
        "FR-017-FINAL-DECISION-YYYY-MM-DD-PILOT-RECORD.json"
    )
    assert payload["final_physical_gate_record_name_pattern"] == (
        "FR-017-FINAL-PHYSICAL-GATE-YYYY-MM-DD-PILOT-RECORD.json"
    )
    assert [step["id"] for step in payload["final_physical_decision_plan"]] == [
        "stage17_package_and_manifest_lock",
        "engineering_review_gate_lock",
        "evidence_chronology_audit",
        "pilot_identity_continuity_audit",
        "human_final_decision_and_no_clearance_locks",
    ]
    assert payload["final_physical_decision_total_groups"] == 5
    assert payload["final_physical_decision_ready_groups"] == 1
    assert payload["final_physical_decision_pending_groups"] == 1
    assert payload["final_physical_decision_invalid_groups"] == 0
    assert payload["final_physical_decision_failed_groups"] == 0
    assert payload["final_physical_decision_blocked_groups"] == 3
    assert payload["final_physical_decision_first_blocking_group_id"] == "engineering_review_gate_lock"
    assert payload["final_physical_decision_first_blocking_group_status"] == (
        "pending_required_engineering_review_gate"
    )
    decision_status = _decision_status_by_id(payload)
    assert decision_status["stage17_package_and_manifest_lock"]["ready_for_final_physical_decision_review"] is True
    assert decision_status["engineering_review_gate_lock"]["blocking_signals"] == [
        "engineering_review_gate_status.pending_quick_release_cable_snag_gate"
    ]
    assert decision_status["evidence_chronology_audit"]["status"] == "blocked_by_engineering_review_gate"
    assert decision_status["pilot_identity_continuity_audit"]["status"] == "blocked_by_engineering_review_gate"
    assert decision_status["human_final_decision_and_no_clearance_locks"]["status"] == (
        "blocked_by_engineering_review_gate"
    )
    assert payload["read_only_contract"] is True
    assert payload["writes_repo"] is False
    assert payload["grants_mutation_authority"] is False


def test_fr017_final_physical_gate_fails_closed_if_package_gate_fails(tmp_path: Path) -> None:
    missing_manifest = tmp_path / "missing-manifest.json"

    proc = _run_gate("-Mode", "Status", "-ManifestPath", str(missing_manifest))

    assert proc.returncode == 1
    payload = _payload(proc.stdout)
    assert payload["status"] == "failed_stage17_package_gate"
    assert payload["stage17_package_gate_status"] == "failed_contract"
    assert payload["physical_validation_complete"] is False
    assert payload["fr018_implementation_cleared"] is False
    assert payload["final_physical_decision_total_groups"] == 5
    assert payload["final_physical_decision_ready_groups"] == 0
    assert payload["final_physical_decision_pending_groups"] == 0
    assert payload["final_physical_decision_failed_groups"] == 1
    assert payload["final_physical_decision_blocked_groups"] == 4
    assert payload["final_physical_decision_first_blocking_group_id"] == "stage17_package_and_manifest_lock"
    assert payload["final_physical_decision_first_blocking_group_status"] == "failed_stop_condition_or_blocking_signal"
    decision_status = _decision_status_by_id(payload)
    assert decision_status["stage17_package_and_manifest_lock"]["blocking_signals"] == [
        "stage17_package_gate_status.failed_contract",
        "stage17_package.failed_checks.manifest_exists",
        "stage17_package.failed_checks.manifest_parse",
    ]
    assert decision_status["engineering_review_gate_lock"]["status"] == "blocked_by_stage17_package_gate"
    assert "stage17_package_gate_not_clean" in payload["failed_reasons"]


def test_fr017_final_physical_gate_surfaces_package_template_drift(tmp_path: Path) -> None:
    manifest_path = _copy_stage17_package(tmp_path)
    package_root = manifest_path.parent
    release_cable_template_path = package_root / "FR-017-QUICK-RELEASE-CABLE-SNAG-INPUT-TEMPLATE.json"
    template = json.loads(release_cable_template_path.read_text(encoding="utf-8"))
    del template["field_contract"]["fail_observations"]
    del template["sides"]["right"]["fail_observations"]["release_hidden"]
    release_cable_template_path.write_text(json.dumps(template, indent=2), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-ManifestPath", str(manifest_path))

    assert proc.returncode == 1
    payload = _payload(proc.stdout)
    assert payload["status"] == "failed_stage17_package_gate"
    assert payload["stage17_package_gate_status"] == "failed_contract"
    assert "release_cable_input_template_contracts" in payload["stage17_package_failed_checks"]
    assert "release_cable_input_template_required_fields" in payload["stage17_package_failed_checks"]
    assert payload["stage17_package_missing_release_cable_template_contracts"] == ["fail_observations"]
    assert payload["stage17_package_missing_release_cable_template_fields"] == [
        "sides.right.fail_observations.release_hidden"
    ]
    assert payload["physical_validation_complete"] is False
    assert payload["stage17_completion_claim_allowed"] is False
    assert payload["fr018_implementation_cleared"] is False
    assert "stage17_package_gate_not_clean" in payload["failed_reasons"]


def test_fr017_final_physical_gate_surfaces_package_pending_contract_text(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_stage17_package(tmp_path)
    package_root = manifest_path.parent
    movement_template_path = package_root / "FR-017-PILOT-MOVEMENT-INPUT-TEMPLATE.json"
    template = json.loads(movement_template_path.read_text(encoding="utf-8"))
    template["field_contract"]["test_duration"] = " pending "
    movement_template_path.write_text(json.dumps(template, indent=2), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-ManifestPath", str(manifest_path))

    assert proc.returncode == 1
    payload = _payload(proc.stdout)
    assert payload["status"] == "failed_stage17_package_gate"
    assert payload["stage17_package_gate_status"] == "failed_contract"
    assert "movement_input_template_contracts" in payload["stage17_package_failed_checks"]
    assert payload["stage17_package_missing_movement_template_contracts"] == ["test_duration"]
    assert payload["stage17_package_missing_final_decision_template_contracts"] == []
    assert payload["stage17_package_missing_final_decision_template_fields"] == []
    assert payload["physical_validation_evidence_chain_complete"] is False
    assert payload["stage17_physical_completion_decision_ready"] is False
    assert payload["physical_validation_complete"] is False
    assert payload["stage17_completion_claim_allowed"] is False
    assert payload["fr018_implementation_cleared"] is False
    assert "stage17_package_gate_not_clean" in payload["failed_reasons"]


def test_fr017_final_physical_gate_ready_state_does_not_claim_completion(tmp_path: Path) -> None:
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
    assert payload["status"] == "ready_for_stage17_final_physical_completion_decision"
    assert payload["stage17_package_gate_status"] == "blocked_physical_validation"
    assert payload["engineering_review_gate_status"] == "ready_for_final_stage17_physical_gate_audit"
    assert payload["engineering_review_gate_ready"] is True
    assert payload["upstream_quick_release_cable_snag_gate_ready"] is True
    assert payload["physical_validation_evidence_chain_complete"] is True
    assert payload["stage17_physical_completion_decision_ready"] is True
    assert payload["engineering_review_record_linkage_contract_present"] is True
    assert payload["engineering_review_record_linkage_violations"] == []
    assert payload["evidence_chronology_violations"] == []
    assert "must not move backward" in payload["evidence_chronology_contract"]
    assert payload["pilot_identity_continuity_violations"] == []
    assert "redacted identity fingerprints" in payload["pilot_identity_continuity_contract"]
    assert payload["pilot_identity_continuity_reference_record"] == "measurement"
    assert payload["pilot_identity_continuity_reference_fingerprint"]
    pilot_identity_records = {record["id"]: record for record in payload["pilot_identity_continuity_records"]}
    assert pilot_identity_records["measurement"]["pilot_id_present"] is True
    assert pilot_identity_records["mockup"]["required"] is False
    assert pilot_identity_records["mockup"]["pilot_id_present"] is False
    assert pilot_identity_records["pilot_static_fit"]["pilot_id_present"] is True
    assert pilot_identity_records["pilot_movement"]["pilot_id_present"] is True
    assert pilot_identity_records["quick_release_cable_snag"]["pilot_id_present"] is True
    assert pilot_identity_records["engineering_review"]["pilot_id_present"] is True
    assert payload["physical_validation_complete"] is False
    assert payload["stage17_completion_claim_allowed"] is False
    assert payload["powered_or_frame_coupled_testing_cleared"] is False
    assert payload["fr018_implementation_cleared"] is False
    assert payload["final_physical_decision_total_groups"] == 5
    assert payload["final_physical_decision_ready_groups"] == 5
    assert payload["final_physical_decision_pending_groups"] == 0
    assert payload["final_physical_decision_failed_groups"] == 0
    assert payload["final_physical_decision_blocked_groups"] == 0
    assert payload["final_physical_decision_first_blocking_group_id"] == ""
    assert payload["final_physical_decision_first_blocking_group_status"] == ""
    assert payload["final_physical_decision_first_blocking_group_action"] == ""
    assert payload["next_required_final_physical_input"] == (
        "create_human_final_decision_record_with_fr017-new-final-decision-record.ps1_then_rerun_final_decision_record_gate"
    )
    assert "fr017-new-final-decision-record.ps1" in payload["final_physical_decision_runbook_contract"]
    assert _portable_path(payload["final_decision_record_initializer_path"]).endswith(
        "scripts/fr017-new-final-decision-record.ps1"
    )
    assert all(
        step["status"] == "ready_for_final_physical_decision_review"
        for step in payload["final_physical_decision_plan_status"]
    )
    assert all(
        step["ready_for_final_physical_decision_review"] for step in payload["final_physical_decision_plan_status"]
    )
    assert "does not mark physical_validation_complete" in payload["no_fake_validation_lock"]


def test_fr017_final_physical_gate_treats_optional_mockup_pending_pilot_id_as_missing(
    tmp_path: Path,
) -> None:
    measurement_path, mockup_path, mannequin_path, static_fit_path, movement_path, release_cable_path = (
        _write_release_ready_records(tmp_path)
    )
    mockup_payload = json.loads(mockup_path.read_text(encoding="utf-8"))
    mockup_payload["evidence"]["pilot_id"] = " pending "
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

    assert proc.returncode == 0, proc.stderr
    payload = _payload(proc.stdout)
    assert payload["status"] == "ready_for_stage17_final_physical_completion_decision"
    assert payload["pilot_identity_continuity_violations"] == []
    pilot_identity_records = {record["id"]: record for record in payload["pilot_identity_continuity_records"]}
    assert pilot_identity_records["mockup"]["required"] is False
    assert pilot_identity_records["mockup"]["pilot_id_present"] is False
    assert pilot_identity_records["mockup"]["pilot_id_fingerprint"] == ""
    assert pilot_identity_records["mockup"]["issue"] == "pilot_id_not_present_optional"
    assert payload["physical_validation_complete"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_final_physical_gate_blocks_engineering_review_chronology_failure(tmp_path: Path) -> None:
    measurement_path, mockup_path, mannequin_path, static_fit_path, movement_path, release_cable_path = (
        _write_release_ready_records(tmp_path)
    )
    engineering_review_path = tmp_path / "ready-engineering-review.json"
    engineering_review_payload = _ready_engineering_review_payload(release_cable_path)
    engineering_review_payload["evidence"]["date"] = "2026-06-22"
    engineering_review_path.write_text(
        json.dumps(engineering_review_payload),
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
    assert payload["status"] == "failed_engineering_review_gate"
    assert payload["engineering_review_gate_status"] == "failed_engineering_review_record"
    assert payload["engineering_review_gate_ready"] is False
    assert payload["engineering_review_invalid_fields"] == []
    assert payload["engineering_review_record_linkage_violations"] == []
    assert payload["evidence_chronology_violations"] == []
    assert payload["engineering_review_redesign_triggers"] == []
    assert payload["engineering_review_prohibited_clearance_flags"] == []
    assert payload["upstream_release_cable_record_linkage_violations"] == []
    assert payload["upstream_release_cable_redesign_triggers"] == []
    assert payload["upstream_release_cable_fail_observations"] == []
    assert payload["physical_validation_evidence_chain_complete"] is False
    assert payload["stage17_physical_completion_decision_ready"] is False
    assert payload["physical_validation_complete"] is False
    assert payload["fr018_implementation_cleared"] is False
    assert "engineering_review_gate_failed" in payload["failed_reasons"]
    assert "evidence_chronology_violation" not in payload["failed_reasons"]


def test_fr017_final_physical_gate_fails_closed_on_optional_mockup_pilot_identity_mismatch(
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
    assert payload["status"] == "failed_pilot_identity_continuity"
    assert payload["engineering_review_gate_status"] == "ready_for_final_stage17_physical_gate_audit"
    assert payload["engineering_review_gate_ready"] is True
    assert payload["evidence_chronology_violations"] == []
    assert payload["pilot_identity_continuity_violations"] == ["mockup.evidence.pilot_id_must_match_measurement"]
    assert payload["physical_validation_evidence_chain_complete"] is False
    assert payload["stage17_physical_completion_decision_ready"] is False
    assert payload["physical_validation_complete"] is False
    assert payload["fr018_implementation_cleared"] is False
    assert "pilot_identity_continuity_violation" in payload["failed_reasons"]


def test_fr017_final_physical_gate_exposes_unlinked_engineering_review_record(tmp_path: Path) -> None:
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
    assert payload["status"] == "failed_engineering_review_gate"
    assert payload["engineering_review_gate_status"] == "failed_engineering_review_record"
    assert payload["engineering_review_record_linkage_contract_present"] is True
    assert payload["engineering_review_record_linkage_violations"] == [
        "evidence.quick_release_cable_snag_record_path_must_match_release_cable_path"
    ]
    assert payload["physical_validation_evidence_chain_complete"] is False
    assert payload["stage17_physical_completion_decision_ready"] is False
    assert payload["physical_validation_complete"] is False
    assert payload["fr018_implementation_cleared"] is False
    assert "engineering_review_gate_failed" in payload["failed_reasons"]


def test_fr017_final_physical_gate_exposes_measurement_rejected_by_intake(tmp_path: Path) -> None:
    measurement_path = tmp_path / "quoted-measurements.json"
    payload = _ready_measurement_payload()
    payload["sides"]["left"]["forearm_length_elbow_crease_to_wrist_crease"] = "258"
    measurement_path.write_text(json.dumps(payload), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-MeasurementPath", str(measurement_path))

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "failed_engineering_review_gate"
    assert result["engineering_review_gate_status"] == "failed_upstream_quick_release_cable_snag_gate"
    assert result["engineering_review_gate_ready"] is False
    assert result["upstream_quick_release_cable_snag_status"] == "failed_upstream_pilot_movement_gate"
    assert result["upstream_pilot_movement_status"] == "failed_upstream_static_fit_gate"
    assert result["upstream_static_fit_status"] == "failed_upstream_mannequin_gate"
    assert result["upstream_mannequin_status"] == "failed_upstream_mockup_gate"
    assert result["upstream_mockup_status"] == "invalid_measurement_record"
    assert result["upstream_measurement_intake_status"] == "invalid_measurement_record"
    assert result["upstream_measurement_invalid_fields"] == ["sides.left.forearm_length_elbow_crease_to_wrist_crease"]
    assert result["physical_validation_evidence_chain_complete"] is False
    assert result["stage17_physical_completion_decision_ready"] is False
    assert result["physical_validation_complete"] is False
    assert result["stage17_completion_claim_allowed"] is False
    assert result["fr018_implementation_cleared"] is False
    assert "engineering_review_gate_failed" in result["failed_reasons"]


def test_fr017_final_physical_gate_exposes_measurement_safety_blocker(tmp_path: Path) -> None:
    measurement_path = tmp_path / "symptom-measurements.json"
    payload = _ready_measurement_payload()
    payload["safety_screen"]["tingling"] = True
    measurement_path.write_text(json.dumps(payload), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-MeasurementPath", str(measurement_path))

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "failed_engineering_review_gate"
    assert result["engineering_review_gate_status"] == "failed_upstream_quick_release_cable_snag_gate"
    assert result["engineering_review_gate_ready"] is False
    assert result["upstream_quick_release_cable_snag_status"] == "failed_upstream_pilot_movement_gate"
    assert result["upstream_pilot_movement_status"] == "failed_upstream_static_fit_gate"
    assert result["upstream_static_fit_status"] == "failed_upstream_mannequin_gate"
    assert result["upstream_mannequin_status"] == "failed_upstream_mockup_gate"
    assert result["upstream_mockup_status"] == "failed_requires_redesign_or_medical_review"
    assert result["upstream_measurement_intake_status"] == "failed_requires_redesign_or_medical_review"
    assert result["upstream_safety_blockers"] == ["tingling"]
    assert result["upstream_measurement_capture_total_groups"] == 5
    assert result["upstream_measurement_capture_ready_groups"] == 4
    assert result["upstream_measurement_capture_failed_groups"] == 1
    assert result["upstream_measurement_capture_first_blocking_group_id"] == "left_right_independence_and_safety_screen"
    assert (
        result["upstream_measurement_capture_first_blocking_group_status"] == "failed_stop_condition_or_blocking_signal"
    )
    capture_status = {step["id"]: step for step in result["upstream_measurement_capture_plan_status"]}
    safety_status = capture_status["left_right_independence_and_safety_screen"]
    assert safety_status["status"] == "failed_stop_condition_or_blocking_signal"
    assert safety_status["ready_for_measurement_intake"] is False
    assert safety_status["blocking_signals"] == ["safety_screen.tingling"]
    assert result["physical_validation_evidence_chain_complete"] is False
    assert result["stage17_physical_completion_decision_ready"] is False
    assert result["physical_validation_complete"] is False
    assert result["stage17_completion_claim_allowed"] is False
    assert result["fr018_implementation_cleared"] is False
    assert "engineering_review_gate_failed" in result["failed_reasons"]


def test_fr017_final_physical_gate_exposes_marked_zone_specificity_violation(tmp_path: Path) -> None:
    measurement_path = tmp_path / "copied-zone-reference-measurements.json"
    payload = _ready_measurement_payload()
    payload["marked_zones"]["right"]["wrist_bone_boundary"] = payload["marked_zones"]["left"]["wrist_bone_boundary"]
    measurement_path.write_text(json.dumps(payload), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-MeasurementPath", str(measurement_path))

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "failed_engineering_review_gate"
    assert result["engineering_review_gate_status"] == "failed_upstream_quick_release_cable_snag_gate"
    assert result["engineering_review_gate_ready"] is False
    assert result["upstream_measurement_intake_status"] == "invalid_measurement_record"
    assert result["upstream_marked_zone_specificity_violations"] == [
        "marked_zones.wrist_bone_boundary_left_right_references_must_be_distinct"
    ]
    assert result["physical_validation_evidence_chain_complete"] is False
    assert result["physical_validation_complete"] is False
    assert result["stage17_completion_claim_allowed"] is False
    assert result["fr018_implementation_cleared"] is False
    assert "engineering_review_gate_failed" in result["failed_reasons"]


def test_fr017_final_physical_gate_exposes_measurement_note_blockers(tmp_path: Path) -> None:
    measurement_path = tmp_path / "generic-measurement-notes.json"
    payload = _ready_measurement_payload()
    payload["measurement_conditions"]["condition_notes"] = "Fixture complete."
    payload["landmark_confirmation"]["landmark_notes"] = "Fixture complete."
    measurement_path.write_text(json.dumps(payload), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-MeasurementPath", str(measurement_path))

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "failed_engineering_review_gate"
    assert result["engineering_review_gate_status"] == "failed_upstream_quick_release_cable_snag_gate"
    assert result["engineering_review_gate_ready"] is False
    assert result["upstream_measurement_intake_status"] == "invalid_measurement_record"
    assert result["upstream_measurement_note_blockers"] == [
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
    assert result["physical_validation_evidence_chain_complete"] is False
    assert result["physical_validation_complete"] is False
    assert result["stage17_completion_claim_allowed"] is False
    assert result["fr018_implementation_cleared"] is False
    assert "engineering_review_gate_failed" in result["failed_reasons"]


def test_fr017_final_physical_gate_exposes_measurement_condition_blocker(tmp_path: Path) -> None:
    measurement_path = tmp_path / "tissue-compression-measurements.json"
    payload = _ready_measurement_payload()
    payload["measurement_conditions"]["no_tissue_compression_used"] = False
    measurement_path.write_text(json.dumps(payload), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-MeasurementPath", str(measurement_path))

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "failed_engineering_review_gate"
    assert result["engineering_review_gate_status"] == "failed_upstream_quick_release_cable_snag_gate"
    assert result["engineering_review_gate_ready"] is False
    assert result["upstream_measurement_intake_status"] == "invalid_measurement_record"
    assert result["upstream_measurement_condition_blockers"] == [
        "measurement_conditions.no_tissue_compression_used_must_be_true"
    ]
    assert result["physical_validation_evidence_chain_complete"] is False
    assert result["stage17_physical_completion_decision_ready"] is False
    assert result["physical_validation_complete"] is False
    assert result["stage17_completion_claim_allowed"] is False
    assert result["fr018_implementation_cleared"] is False
    assert "engineering_review_gate_failed" in result["failed_reasons"]


def test_fr017_final_physical_gate_exposes_landmark_confirmation_blocker(tmp_path: Path) -> None:
    measurement_path = tmp_path / "landmark-unconfirmed-measurements.json"
    payload = _ready_measurement_payload()
    payload["landmark_confirmation"]["wrist_bone_boundary_confirmed"] = False
    measurement_path.write_text(json.dumps(payload), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-MeasurementPath", str(measurement_path))

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "failed_engineering_review_gate"
    assert result["engineering_review_gate_status"] == "failed_upstream_quick_release_cable_snag_gate"
    assert result["engineering_review_gate_ready"] is False
    assert result["upstream_measurement_intake_status"] == "invalid_measurement_record"
    assert result["upstream_landmark_confirmation_blockers"] == [
        "landmark_confirmation.wrist_bone_boundary_confirmed_must_be_true"
    ]
    assert result["physical_validation_evidence_chain_complete"] is False
    assert result["stage17_physical_completion_decision_ready"] is False
    assert result["physical_validation_complete"] is False
    assert result["stage17_completion_claim_allowed"] is False
    assert result["fr018_implementation_cleared"] is False
    assert "engineering_review_gate_failed" in result["failed_reasons"]


def test_fr017_final_physical_gate_exposes_left_right_independence_blocker(tmp_path: Path) -> None:
    measurement_path = tmp_path / "copied-left-right-measurements.json"
    payload = _ready_measurement_payload()
    payload["left_right_independence"]["values_not_copied_between_sides"] = False
    measurement_path.write_text(json.dumps(payload), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-MeasurementPath", str(measurement_path))

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "failed_engineering_review_gate"
    assert result["engineering_review_gate_status"] == "failed_upstream_quick_release_cable_snag_gate"
    assert result["engineering_review_gate_ready"] is False
    assert result["upstream_left_right_independence_blockers"] == [
        "left_right_independence.values_not_copied_between_sides_must_be_true"
    ]
    assert result["physical_validation_evidence_chain_complete"] is False
    assert result["physical_validation_complete"] is False
    assert result["stage17_completion_claim_allowed"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_final_physical_gate_exposes_static_fit_symptom_blocker(tmp_path: Path) -> None:
    measurement_path, mockup_path, mannequin_path = _write_static_fit_upstream_ready_records(tmp_path)
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
    assert result["status"] == "failed_engineering_review_gate"
    assert result["engineering_review_gate_status"] == "failed_upstream_quick_release_cable_snag_gate"
    assert result["upstream_quick_release_cable_snag_status"] == "failed_upstream_pilot_movement_gate"
    assert result["upstream_pilot_movement_status"] == "failed_upstream_static_fit_gate"
    assert result["upstream_static_fit_status"] == "failed_requires_fit_redesign_or_medical_review"
    assert result["upstream_static_fit_symptom_blockers"] == ["sides.left.symptoms.tingling"]
    assert result["physical_validation_evidence_chain_complete"] is False
    assert result["physical_validation_complete"] is False
    assert result["stage17_completion_claim_allowed"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_final_physical_gate_exposes_movement_symptom_blocker(tmp_path: Path) -> None:
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
    assert result["status"] == "failed_engineering_review_gate"
    assert result["engineering_review_gate_status"] == "failed_upstream_quick_release_cable_snag_gate"
    assert result["upstream_quick_release_cable_snag_status"] == "failed_upstream_pilot_movement_gate"
    assert result["upstream_pilot_movement_status"] == "failed_requires_movement_redesign_or_medical_review"
    assert result["upstream_movement_symptom_blockers"] == ["sides.right.symptoms.numbness"]
    assert result["physical_validation_evidence_chain_complete"] is False
    assert result["physical_validation_complete"] is False
    assert result["stage17_completion_claim_allowed"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_final_physical_gate_exposes_release_fail_observation(tmp_path: Path) -> None:
    measurement_path, mockup_path, mannequin_path, static_fit_path, movement_path, release_cable_path = (
        _write_release_ready_records(tmp_path)
    )
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
    assert result["status"] == "failed_engineering_review_gate"
    assert result["engineering_review_gate_status"] == "failed_upstream_quick_release_cable_snag_gate"
    assert result["upstream_quick_release_cable_snag_status"] == (
        "failed_requires_release_cable_redesign_or_medical_review"
    )
    assert result["upstream_release_cable_redesign_triggers"] == []
    assert result["upstream_release_cable_fail_observations"] == ["sides.left.fail_observations.release_hidden"]
    assert result["physical_validation_evidence_chain_complete"] is False
    assert result["physical_validation_complete"] is False
    assert result["stage17_completion_claim_allowed"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_final_physical_gate_blocks_failed_engineering_review(tmp_path: Path) -> None:
    measurement_path, mockup_path, mannequin_path, static_fit_path, movement_path, release_cable_path = (
        _write_release_ready_records(tmp_path)
    )
    engineering_review_path = tmp_path / "bad-engineering-review.json"
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
    assert result["status"] == "failed_engineering_review_gate"
    assert result["engineering_review_gate_status"] == "failed_requires_stage17_redesign_or_review_rejection"
    assert result["engineering_review_missing_fields"] == ["evidence.reviewer"]
    assert result["engineering_review_prohibited_clearance_flags"] == ["review_decision.fr018_implementation_cleared"]
    assert result["final_physical_decision_total_groups"] == 5
    assert result["final_physical_decision_ready_groups"] == 1
    assert result["final_physical_decision_pending_groups"] == 0
    assert result["final_physical_decision_failed_groups"] == 1
    assert result["final_physical_decision_blocked_groups"] == 3
    assert result["final_physical_decision_first_blocking_group_id"] == "engineering_review_gate_lock"
    assert result["final_physical_decision_first_blocking_group_status"] == "failed_stop_condition_or_blocking_signal"
    decision_status = _decision_status_by_id(result)
    assert decision_status["engineering_review_gate_lock"]["blocking_signals"] == [
        "engineering_review_gate_status.failed_requires_stage17_redesign_or_review_rejection",
        "evidence.reviewer",
        "review_decision.fr018_implementation_cleared",
    ]
    assert decision_status["human_final_decision_and_no_clearance_locks"]["status"] == (
        "blocked_by_engineering_review_gate"
    )
    assert result["physical_validation_complete"] is False
    assert result["stage17_completion_claim_allowed"] is False
    assert result["fr018_implementation_cleared"] is False
    assert "engineering_review_gate_failed" in result["failed_reasons"]
