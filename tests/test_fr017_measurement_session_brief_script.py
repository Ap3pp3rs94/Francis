from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from tests.powershell_script_runner import run_powershell_script
from tests.test_fr017_measurement_intake_script import _ready_measurement_payload


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "fr017-measurement-session-brief.ps1"


def _powershell() -> str:
    exe = shutil.which("pwsh") or shutil.which("powershell")
    if not exe:
        pytest.skip("PowerShell is not available")
    return exe


def _run_brief(*args: str):
    return run_powershell_script(
        _powershell(),
        SCRIPT,
        args,
        cwd=ROOT,
        timeout_seconds=40,
    )


def _payload(stdout: str) -> dict[str, Any]:
    return json.loads(stdout)


def test_fr017_measurement_session_brief_reports_first_template_blocker() -> None:
    proc = _run_brief("-Mode", "Status")

    assert proc.returncode == 0, proc.stderr
    payload = _payload(proc.stdout)
    assert payload["kind"] == "francis.fr017.measurement_session_brief"
    assert payload["status"] == "measurement_session_input_required"
    assert payload["intake_status"] == "pending_measurements"
    assert payload["using_template"] is True
    assert payload["first_blocking_group_id"] == "setup_and_safety_brief"
    assert payload["first_blocking_group_status"] == "pending_required_fields"
    assert "brief stop conditions" in payload["first_blocking_group_action"]
    assert "evidence.date" in payload["current_group_missing_fields"]
    assert "measurement_conditions.stop_conditions_briefed" in payload["current_group_missing_fields"]
    assert payload["measurement_capture_total_groups"] == 5
    assert payload["measurement_capture_ready_groups"] == 0
    assert payload["measurement_capture_pending_groups"] == 5
    assert payload["next_operator_action"] == (
        "complete_first_blocking_measurement_capture_group_then_rerun_measurement_intake"
    )
    assert payload["operator_sequence"][0] == "create_pending_measurement_record_with_fr017-new-measurement-record.ps1"
    assert (
        "update_setup_safety_brief_with_fr017-update-measurement-setup-record.ps1_when_pending_record_exists"
        in payload["operator_sequence"]
    )
    assert "loss_of_grip_strength" in payload["safety_stop_conditions"]
    assert "copied_left_right_values_or_references" in payload["safety_stop_conditions"]
    assert "Read-only operator brief" in payload["measurement_session_brief_contract"]
    assert payload["physical_validation_complete"] is False
    assert payload["stage17_completion_claim_allowed"] is False
    assert payload["powered_or_frame_coupled_testing_cleared"] is False
    assert payload["fr018_implementation_cleared"] is False
    assert payload["read_only_contract"] is True
    assert payload["writes_repo"] is False
    assert payload["writes_data"] is False


def test_fr017_measurement_session_brief_hands_off_ready_measurement_record(
    tmp_path: Path,
) -> None:
    measurement_path = tmp_path / "ready-measurements.json"
    measurement_path.write_text(json.dumps(_ready_measurement_payload()), encoding="utf-8")

    proc = _run_brief("-Mode", "Status", "-MeasurementPath", str(measurement_path))

    assert proc.returncode == 0, proc.stderr
    payload = _payload(proc.stdout)
    assert payload["status"] == "ready_for_non_powered_mockup_patterning_handoff"
    assert payload["intake_status"] == "ready_for_non_powered_mockup_patterning"
    assert payload["intake_ready_for_non_powered_mockup_patterning"] is True
    assert payload["using_template"] is False
    assert payload["measurement_path"] == str(measurement_path)
    assert payload["first_blocking_group_id"] == ""
    assert payload["current_group_missing_fields"] == []
    assert payload["current_group_invalid_fields"] == []
    assert payload["current_group_blocking_signals"] == []
    assert payload["measurement_capture_ready_groups"] == 5
    assert payload["measurement_capture_pending_groups"] == 0
    assert payload["next_operator_action"] == (
        "rerun_mockup_readiness_gate_with_the_accepted_measurement_record_without_claiming_physical_validation"
    )
    assert payload["physical_validation_complete"] is False
    assert payload["stage17_completion_claim_allowed"] is False
    assert payload["fr018_implementation_cleared"] is False
    assert payload["writes_repo"] is False


def test_fr017_measurement_session_brief_fails_closed_on_symptom(
    tmp_path: Path,
) -> None:
    measurement_path = tmp_path / "symptom-measurements.json"
    payload = _ready_measurement_payload()
    payload["safety_screen"]["tingling"] = True
    measurement_path.write_text(json.dumps(payload), encoding="utf-8")

    proc = _run_brief("-Mode", "Status", "-MeasurementPath", str(measurement_path))

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "failed_measurement_session_brief"
    assert result["intake_status"] == "failed_requires_redesign_or_medical_review"
    assert result["intake_failed"] is True
    assert result["first_blocking_group_id"] == "left_right_independence_and_safety_screen"
    assert result["current_group_blocking_signals"] == ["safety_screen.tingling"]
    assert result["next_operator_action"] == (
        "stop_measurement_session_and_resolve_intake_failure_before_any_mockup_or_FR-018_work"
    )
    assert result["physical_validation_complete"] is False
    assert result["stage17_completion_claim_allowed"] is False
    assert result["fr018_implementation_cleared"] is False
    assert result["writes_repo"] is False
