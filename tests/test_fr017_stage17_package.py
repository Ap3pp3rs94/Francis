from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MANUAL_PATH = ROOT / "FRANCIS_FR-017_Forearm_Cuffs_v1.0"
PACKAGE_DIR = ROOT / "FR-017_Stage17_Package"
MANIFEST_PATH = PACKAGE_DIR / "FR-017-STAGE17-PACKAGE-MANIFEST.json"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _manifest() -> dict[str, Any]:
    return json.loads(_read(MANIFEST_PATH))


def test_fr017_stage17_manual_keeps_required_packet_and_safety_scope() -> None:
    manual = _read(MANUAL_PATH)

    assert "FRANCIS ONLINE." in manual
    assert "Stage 17 loaded: FR-017 Forearm Cuffs." in manual
    assert "25/25 required Stage 17 packet deliverables documented" in manual
    assert "FR-018 cleared to begin: Not cleared for implementation." in manual
    assert "Physical validation completion percentage: 0 percent." in manual
    assert "The cuffs are not armor, powered joints, wrist joints, gloves" in manual
    assert "They must never trap, overpower, or prevent emergency egress by the pilot." in manual
    assert "No strap crosses the inner elbow crease." in manual
    assert "No cable crosses wrist bones." in manual
    assert "Any numbness, tingling, cold fingers, discoloration" in manual


def test_fr017_stage17_custom_records_remain_complete() -> None:
    text = _read(MANUAL_PATH) + "\n" + _read(PACKAGE_DIR / "FR-017-MAPS-AND-LAYOUTS.md")

    expected_ids = {f"FR-017-CUSTOM-{index:03d}" for index in range(1, 20)}
    for record_id in expected_ids:
        assert record_id in text


def test_fr017_stage17_package_manifest_resolves_all_records() -> None:
    manifest = _manifest()
    records = manifest["records"]

    assert manifest["package_id"] == "FR-017-STAGE17"
    assert manifest["component"] == "FR-017 Forearm Cuffs"
    assert len(records) == 25
    assert len(manifest["custom_records"]) == 19

    for record in records:
        path = PACKAGE_DIR / record["path"]
        assert path.resolve().exists(), record["path"]


def test_fr017_stage17_manifest_preserves_no_fake_validation_gate() -> None:
    manifest = _manifest()
    status = manifest["status"]

    assert status["documentation"] == "complete"
    assert status["evidence_containers"] == "complete"
    assert status["physical_validation"] == "not_complete"
    assert status["powered_or_frame_coupled_testing"] == "not_cleared"
    assert status["fr_018_implementation"] == "not_cleared"
    assert manifest["source_basis"]["prior_fr017_source_found"] is False
    assert "safety_critical_landmark_confirmation" in manifest["blocked_inputs"]
    assert "pilot_static_fit_session" in manifest["blocked_inputs"]
    assert "professional_engineering_review" in manifest["blocked_inputs"]
    assert "human_final_stage17_completion_decision" in manifest["blocked_inputs"]
    assert "operator_reviewed_completion_ledger_entry" in manifest["blocked_inputs"]
    assert any(record["kind"] == "engineering_review_record" for record in manifest["records"])
    assert any(record["kind"] == "engineering_review_input_template" for record in manifest["records"])
    assert any(record["kind"] == "final_physical_decision_input_template" for record in manifest["records"])
    assert any(record["kind"] == "measurement_capture_runbook" for record in manifest["records"])
    assert any(record["kind"] == "completion_ledger_handoff_template" for record in manifest["records"])
    assert any(record["kind"] == "validation_gate_chain_runbook" for record in manifest["records"])
    assert "unconfirmed_landmark_boundaries" in manifest["safety_fail_conditions"]
    assert "unreachable_release" in manifest["safety_fail_conditions"]


def test_fr017_stage17_final_audit_blocks_physical_and_fr018_claims() -> None:
    audit = _read(PACKAGE_DIR / "FR-017-STAGE17-FINAL-AUDIT-2026-06-23.md")
    gate = _read(PACKAGE_DIR / "FR-017-COMPLETION-GATE-2026-06-23.md")
    package_index = _read(PACKAGE_DIR / "README.md")

    assert "Stage 17 is finished as a documentation and evidence-record package." in audit
    assert "Stage 17 is not physically validated." in audit
    assert "## No-Fake-Validation Lock" in audit
    assert "FR-018 implementation is not cleared by this audit." in audit
    assert "Stage 17 physical validation: NOT COMPLETE." in gate
    assert "FR-018 implementation clearance: NOT CLEARED." in gate
    assert "Physical validation: NOT COMPLETE." in package_index
    assert "FR-018 implementation: NOT CLEARED." in package_index
    assert "FR-017-FINAL-PHYSICAL-DECISION-INPUT-TEMPLATE.json" in package_index
    assert "FR-017-MEASUREMENT-CAPTURE-RUNBOOK.md" in package_index
    assert "FR-017-COMPLETION-LEDGER-HANDOFF-TEMPLATE.md" in package_index
    assert "fr017-completion-ledger-gate.ps1" in package_index


def test_fr017_stage17_pending_records_keep_evidence_fields() -> None:
    required_records = [
        "FR-017-MEASUREMENTS-LEFT-RIGHT_PENDING.md",
        "FR-017-ADJUSTMENT-WORKSHEET_PENDING.md",
        "FR-017-FIT-2026-06-23-LEFT_PENDING.md",
        "FR-017-FIT-2026-06-23-RIGHT_PENDING.md",
        "FR-017-MANNEQUIN-INTERFACE-TEST_PENDING.md",
        "FR-017-QUICK-RELEASE-TEST_PENDING.md",
        "FR-017-ENGINEERING-REVIEW_PENDING.md",
    ]

    for record_name in required_records:
        record = _read(PACKAGE_DIR / record_name)
        assert "PENDING" in record
        assert "NOT TESTED" in record or "REQUIRES MEASUREMENT" in record
        assert "NOT VALIDATED" in record or "No measurements have been entered." in record


def test_fr017_measurement_capture_runbook_preserves_first_physical_input_lock() -> None:
    runbook = _read(PACKAGE_DIR / "FR-017-MEASUREMENT-CAPTURE-RUNBOOK.md")

    assert "FR-017 Measurement Capture Runbook" in runbook
    assert "This runbook is not physical validation evidence." in runbook
    assert "FR-017-MEASUREMENTS-INPUT-TEMPLATE.json" in runbook
    assert "fr017-new-measurement-record.ps1" in runbook
    assert "fr017-update-measurement-record.ps1" in runbook
    assert "refuses to overwrite an existing file" in runbook
    assert "refuses to update the template" in runbook
    assert "AllowOverwrite" in runbook
    assert "ConfirmNoTissueCompressionUsed" in runbook
    assert "ConfirmSecondPassCompleted" in runbook
    assert "setup_and_safety_brief" in runbook
    assert "still not physical validation evidence" in runbook
    assert "fr017-measurement-intake.ps1 -Mode Status" in runbook
    assert "measurement_capture_plan" in runbook
    assert "setup_and_safety_brief" in runbook
    assert "left_arm_numeric_measurement_passes" in runbook
    assert "right_arm_numeric_measurement_passes" in runbook
    assert "safety_critical_landmark_and_zone_references" in runbook
    assert "left_right_independence_and_safety_screen" in runbook
    assert "ready_for_non_powered_mockup_patterning" in runbook
    assert "physical_validation_complete: false" in runbook
    assert "stage17_completion_claim_allowed: false" in runbook
    assert "fr018_implementation_cleared: false" in runbook


def test_fr017_validation_gate_chain_preserves_gate_order_and_no_fake_validation() -> None:
    runbook = _read(PACKAGE_DIR / "FR-017-VALIDATION-GATE-CHAIN.md")

    expected_order = [
        "fr017-evidence-chain-status.ps1",
        "fr017-stage17-validation-gate.ps1",
        "fr017-measurement-intake.ps1",
        "fr017-mockup-readiness-gate.ps1",
        "fr017-mannequin-interface-gate.ps1",
        "fr017-pilot-static-fit-gate.ps1",
        "fr017-pilot-movement-gate.ps1",
        "fr017-quick-release-cable-snag-gate.ps1",
        "fr017-engineering-review-gate.ps1",
        "fr017-final-physical-gate.ps1",
        "fr017-final-decision-record-gate.ps1",
        "fr017-completion-ledger-gate.ps1",
    ]
    positions = [runbook.index(item) for item in expected_order]

    assert positions == sorted(positions)
    assert "physical_validation_complete" in runbook
    assert "stage17_completion_claim_allowed" in runbook
    assert "fr018_implementation_cleared" in runbook
    assert "FR-018 implementation is NOT CLEARED." in runbook
    assert "FR-017-FINAL-PHYSICAL-DECISION-INPUT-TEMPLATE.json" in runbook
    assert "FR-017-COMPLETION-LEDGER-HANDOFF-TEMPLATE.md" in runbook
    assert "ready_for_completion_ledger_review" in runbook
    assert "ready_for_operator_completion_ledger_update" in runbook
    assert "A blank or" in runbook
    assert "ready_for_pilot_static_fit_planning" in runbook
    assert "ready_for_pilot_movement_test_planning" in runbook
    assert "ready_for_non_powered_mockup_patterning" in runbook
    assert "safety-critical landmark confirmation" in runbook
    assert "derived consistency checks passed" in runbook
