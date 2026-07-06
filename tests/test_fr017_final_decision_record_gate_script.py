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


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "fr017-final-decision-record-gate.ps1"
FINAL_PHYSICAL_SCRIPT = ROOT / "scripts" / "fr017-final-physical-gate.ps1"


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
        timeout_seconds=100,
    )


def _run_final_physical_gate(*args: str):
    return run_powershell_script(
        _powershell(),
        FINAL_PHYSICAL_SCRIPT,
        args,
        cwd=ROOT,
        timeout_seconds=90,
    )


def _payload(stdout: str) -> dict[str, Any]:
    return json.loads(stdout)


def _write_ready_evidence(tmp_path: Path) -> tuple[Path, Path, Path, Path, Path, Path, Path]:
    measurement_path, mockup_path, mannequin_path, static_fit_path, movement_path, release_cable_path = (
        _write_release_ready_records(tmp_path)
    )
    engineering_review_path = tmp_path / "ready-engineering-review.json"
    engineering_review_path.write_text(
        json.dumps(_ready_engineering_review_payload(release_cable_path)),
        encoding="utf-8",
    )
    return (
        measurement_path,
        mockup_path,
        mannequin_path,
        static_fit_path,
        movement_path,
        release_cable_path,
        engineering_review_path,
    )


def _ready_args(paths: tuple[Path, Path, Path, Path, Path, Path, Path]) -> list[str]:
    (
        measurement_path,
        mockup_path,
        mannequin_path,
        static_fit_path,
        movement_path,
        release_cable_path,
        engineering_review_path,
    ) = paths
    return [
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
    ]


def _write_final_physical_gate_record(tmp_path: Path, paths: tuple[Path, Path, Path, Path, Path, Path, Path]) -> Path:
    proc = _run_final_physical_gate("-Mode", "Status", *_ready_args(paths))

    assert proc.returncode == 0, proc.stderr
    payload = _payload(proc.stdout)
    assert payload["status"] == "ready_for_stage17_final_physical_completion_decision"
    output_path = tmp_path / "ready-final-physical-gate.json"
    output_path.write_text(proc.stdout, encoding="utf-8")
    return output_path


def _ready_final_decision_payload(final_physical_gate_record_path: Path) -> dict[str, Any]:
    return {
        "kind": "francis.fr017.final_physical_decision.v1",
        "component": "FR-017 Forearm Cuffs",
        "evidence": {
            "date": "2026-06-23",
            "decision_reviewer": "Pilot reviewer",
            "reviewer_role": "human_final_decision_reviewer",
            "pilot_id": "pilot-reference",
            "final_physical_gate_status": "ready_for_stage17_final_physical_completion_decision",
            "final_physical_gate_record_path": str(final_physical_gate_record_path),
        },
        "decision_locks": {
            "real_records_reviewed": True,
            "all_stop_conditions_reviewed": True,
            "no_unresolved_safety_fail_conditions": True,
            "no_powered_testing_cleared": True,
            "no_frame_coupled_testing_cleared": True,
            "no_load_bearing_use_approved": True,
            "fr018_implementation_not_cleared": True,
        },
        "completion_decision": {
            "stage17_completion_claim_requested": True,
            "physical_validation_accepted_by_human_reviewer": True,
            "completion_ledger_update_required": True,
            "completion_decision_notes": (
                "Remaining limitations: FR-018 stays blocked; powered, frame-coupled, "
                "and load-bearing use stay blocked until separate ledger review."
            ),
        },
        "no_fake_validation_lock": {
            "template_is_not_physical_validation": True,
            "requires_real_records": True,
            "fr018_implementation_cleared": False,
            "powered_or_frame_coupled_testing_cleared": False,
        },
    }


def test_fr017_final_decision_record_gate_blocks_until_final_physical_gate_ready() -> None:
    proc = _run_gate("-Mode", "Status")

    assert proc.returncode == 0, proc.stderr
    payload = _payload(proc.stdout)
    assert payload["kind"] == "francis.fr017.final_decision_record_gate"
    assert payload["status"] == "pending_final_physical_gate"
    assert payload["final_physical_gate_ready"] is False
    assert payload["final_decision_record_ready"] is False
    assert payload["ledger_completion_review_ready"] is False
    assert payload["physical_validation_complete"] is False
    assert payload["stage17_completion_claim_allowed"] is False
    assert payload["fr018_implementation_cleared"] is False
    assert payload["read_only_contract"] is True


def test_fr017_final_decision_record_gate_requires_decision_record_after_final_gate_ready(
    tmp_path: Path,
) -> None:
    paths = _write_ready_evidence(tmp_path)

    proc = _run_gate("-Mode", "Status", *_ready_args(paths))

    assert proc.returncode == 0, proc.stderr
    payload = _payload(proc.stdout)
    assert payload["status"] == "pending_final_decision_record"
    assert payload["final_physical_gate_ready"] is True
    assert payload["missing_fields"] == ["final_decision_path"]
    assert payload["next_required_final_decision_input"] == (
        "create_human_final_decision_record_with_fr017-new-final-decision-record.ps1_then_rerun_final_decision_record_gate"
    )
    assert "fr017-new-final-decision-record.ps1" in payload["final_decision_record_runbook_contract"]
    assert payload["final_decision_input_template_path"].endswith(
        "FR-017_Stage17_Package\\FR-017-FINAL-PHYSICAL-DECISION-INPUT-TEMPLATE.json"
    )
    assert payload["final_decision_record_initializer_path"].endswith("scripts\\fr017-new-final-decision-record.ps1")
    assert payload["final_decision_working_record_name_pattern"] == (
        "FR-017-FINAL-DECISION-YYYY-MM-DD-PILOT-RECORD.json"
    )
    assert payload["final_physical_gate_record_name_pattern"] == (
        "FR-017-FINAL-PHYSICAL-GATE-YYYY-MM-DD-PILOT-RECORD.json"
    )
    assert payload["physical_validation_complete"] is False
    assert payload["stage17_completion_claim_allowed"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_final_decision_record_gate_reports_default_template_as_pending(
    tmp_path: Path,
) -> None:
    paths = _write_ready_evidence(tmp_path)
    decision_path = tmp_path / "pending-final-decision.json"
    decision_path.write_text(
        (ROOT / "FR-017_Stage17_Package" / "FR-017-FINAL-PHYSICAL-DECISION-INPUT-TEMPLATE.json").read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )

    proc = _run_gate("-Mode", "Status", *_ready_args(paths), "-FinalDecisionPath", str(decision_path))

    assert proc.returncode == 0, proc.stderr
    payload = _payload(proc.stdout)
    assert payload["status"] == "pending_final_decision_record"
    assert "evidence.date" in payload["missing_fields"]
    assert "decision_locks.real_records_reviewed" in payload["missing_fields"]
    assert "completion_decision.completion_decision_notes" in payload["missing_fields"]
    assert payload["final_decision_record_ready"] is False
    assert payload["physical_validation_complete"] is False
    assert payload["stage17_completion_claim_allowed"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_final_decision_record_gate_ready_state_remains_read_only(
    tmp_path: Path,
) -> None:
    paths = _write_ready_evidence(tmp_path)
    final_physical_gate_record_path = _write_final_physical_gate_record(tmp_path, paths)
    decision_path = tmp_path / "ready-final-decision.json"
    decision_path.write_text(
        json.dumps(_ready_final_decision_payload(final_physical_gate_record_path)),
        encoding="utf-8",
    )

    proc = _run_gate("-Mode", "Status", *_ready_args(paths), "-FinalDecisionPath", str(decision_path))

    assert proc.returncode == 0, proc.stderr
    payload = _payload(proc.stdout)
    assert payload["status"] == "ready_for_completion_ledger_review"
    assert payload["final_physical_gate_ready"] is True
    assert payload["final_decision_record_ready"] is True
    assert payload["ledger_completion_review_ready"] is True
    assert payload["saved_final_physical_gate_record_status"] == "ready_for_stage17_final_physical_completion_decision"
    assert "fr017-new-final-decision-record.ps1" in payload["final_decision_record_runbook_contract"]
    assert "redacted SHA-256-derived" in payload["final_decision_pilot_identity_contract"]
    assert payload["final_physical_gate_reference_pilot_fingerprint"]
    assert payload["final_decision_pilot_fingerprint"] == payload["final_physical_gate_reference_pilot_fingerprint"]
    assert payload["missing_fields"] == []
    assert payload["invalid_fields"] == []
    assert payload["decision_lock_violations"] == []
    assert payload["completion_decision_violations"] == []
    assert payload["prohibited_clearance_flags"] == []
    assert payload["physical_validation_complete"] is False
    assert payload["stage17_completion_claim_allowed"] is False
    assert payload["powered_or_frame_coupled_testing_cleared"] is False
    assert payload["fr018_implementation_cleared"] is False
    assert "does not mark physical_validation_complete" in payload["no_fake_validation_lock"]


def test_fr017_final_decision_record_gate_fails_closed_on_pilot_identity_mismatch(
    tmp_path: Path,
) -> None:
    paths = _write_ready_evidence(tmp_path)
    final_physical_gate_record_path = _write_final_physical_gate_record(tmp_path, paths)
    decision_payload = _ready_final_decision_payload(final_physical_gate_record_path)
    decision_payload["evidence"]["pilot_id"] = "different-pilot"
    decision_path = tmp_path / "pilot-mismatch-final-decision.json"
    decision_path.write_text(json.dumps(decision_payload), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", *_ready_args(paths), "-FinalDecisionPath", str(decision_path))

    assert proc.returncode == 1
    payload = _payload(proc.stdout)
    assert payload["status"] == "failed_final_decision_record"
    assert "evidence.pilot_id" in payload["invalid_fields"]
    assert "evidence.pilot_id_must_match_final_physical_gate_reference" in payload["decision_lock_violations"]
    assert payload["final_physical_gate_reference_pilot_fingerprint"]
    assert payload["final_decision_pilot_fingerprint"] != payload["final_physical_gate_reference_pilot_fingerprint"]
    assert payload["physical_validation_complete"] is False
    assert payload["stage17_completion_claim_allowed"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_final_decision_record_gate_fails_closed_on_prohibited_clearance(
    tmp_path: Path,
) -> None:
    paths = _write_ready_evidence(tmp_path)
    final_physical_gate_record_path = _write_final_physical_gate_record(tmp_path, paths)
    decision_payload = _ready_final_decision_payload(final_physical_gate_record_path)
    decision_payload["no_fake_validation_lock"]["fr018_implementation_cleared"] = True
    decision_payload["completion_decision"]["completion_decision_notes"] = (
        "Remaining limitations reviewed; FR-018 cleared."
    )
    decision_path = tmp_path / "bad-final-decision.json"
    decision_path.write_text(json.dumps(decision_payload), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", *_ready_args(paths), "-FinalDecisionPath", str(decision_path))

    assert proc.returncode == 1
    payload = _payload(proc.stdout)
    assert payload["status"] == "failed_final_decision_record"
    assert "no_fake_validation_lock.fr018_implementation_cleared" in payload["invalid_fields"]
    assert "no_fake_validation_lock.fr018_implementation_cleared" in payload["prohibited_clearance_flags"]
    assert "completion_decision_notes.fr-018_cleared" in payload["prohibited_clearance_flags"]
    assert payload["physical_validation_complete"] is False
    assert payload["stage17_completion_claim_allowed"] is False
    assert payload["fr018_implementation_cleared"] is False
