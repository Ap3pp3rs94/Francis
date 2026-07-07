from __future__ import annotations

import json
import shutil
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from tests.powershell_script_runner import run_powershell_script
from tests.test_fr017_final_decision_record_gate_script import (
    _ready_args,
    _ready_final_decision_payload,
    _write_final_physical_gate_record,
    _write_ready_evidence,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "fr017-new-completion-ledger-handoff.ps1"
COMPLETION_LEDGER_GATE_SCRIPT = ROOT / "scripts" / "fr017-completion-ledger-gate.ps1"
TEMPLATE_PATH = ROOT / "FR-017_Stage17_Package" / "FR-017-COMPLETION-LEDGER-HANDOFF-TEMPLATE.md"

CONFIRM_ARGS = [
    "-ConfirmOperatorReviewedFinalDecision",
    "-ConfirmCandidateOnly",
    "-ConfirmDoesNotWriteCompletionLedger",
    "-ConfirmPhysicalValidationCompleteFalse",
    "-ConfirmStage17CompletionClaimAllowedFalse",
    "-ConfirmFr018ImplementationClearedFalse",
    "-ConfirmPoweredTestingNotCleared",
    "-ConfirmFrameCoupledTestingNotCleared",
    "-ConfirmLoadBearingUseNotApproved",
    "-ConfirmFr018Blocked",
]


def _powershell() -> str:
    exe = shutil.which("pwsh") or shutil.which("powershell")
    if not exe:
        pytest.skip("PowerShell is not available")
    return exe


def _run_script(script: Path, *args: str):
    return run_powershell_script(
        _powershell(),
        script,
        args,
        cwd=ROOT,
        timeout_seconds=140,
    )


def _payload(stdout: str) -> dict[str, Any]:
    return json.loads(stdout)


def _write_ready_final_decision(tmp_path: Path) -> tuple[tuple[Path, Path, Path, Path, Path, Path, Path], Path]:
    paths = _write_ready_evidence(tmp_path)
    final_physical_gate_record_path = _write_final_physical_gate_record(tmp_path, paths)
    final_decision_path = tmp_path / "ready-final-decision.json"
    final_decision_path.write_text(
        json.dumps(_ready_final_decision_payload(final_physical_gate_record_path)),
        encoding="utf-8",
    )
    return paths, final_decision_path


def _handoff_args(
    paths: tuple[Path, Path, Path, Path, Path, Path, Path],
    final_decision_path: Path,
    output_path: Path,
    *,
    validation_command_or_record: str = "python -m pytest tests/test_fr017_completion_ledger_gate_script.py -q",
    confirm_args: list[str] | None = None,
) -> list[str]:
    (
        measurement_path,
        mockup_path,
        mannequin_path,
        static_fit_path,
        movement_path,
        release_cable_path,
        engineering_review_path,
    ) = paths
    args = [
        "-Mode",
        "Create",
        "-OutputPath",
        str(output_path),
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
        "-HandoffDate",
        date.today().isoformat(),
        "-ValidationCommandOrRecord",
        validation_command_or_record,
    ]
    args.extend(CONFIRM_ARGS if confirm_args is None else confirm_args)
    return args


def test_fr017_completion_ledger_handoff_initializer_status_preflights_without_writing(
    tmp_path: Path,
) -> None:
    paths, final_decision_path = _write_ready_final_decision(tmp_path)
    output_path = tmp_path / "candidate-completion-ledger-handoff.md"

    proc = _run_script(
        SCRIPT,
        "-Mode",
        "Status",
        *_ready_args(paths),
        "-FinalDecisionPath",
        str(final_decision_path),
        "-OutputPath",
        str(output_path),
    )

    assert proc.returncode == 0, proc.stderr
    result = _payload(proc.stdout)
    assert result["kind"] == "francis.fr017.completion_ledger_handoff_initializer"
    assert result["status"] == "completion_ledger_handoff_initializer_status"
    assert result["template_exists"] is True
    assert result["template_parse_ok"] is True
    assert result["candidate_output_path_ready"] is True
    assert result["output_parent_exists"] is True
    assert result["output_exists"] is False
    assert result["wrote_file"] is False
    assert result["read_only_contract"] is True
    assert result["writes_repo"] is False
    assert result["writes_data"] is False
    assert result["writes_completion_ledger"] is False
    assert result["upstream_final_decision_status"] == "ready_for_completion_ledger_review"
    assert result["upstream_final_decision_ready"] is True
    assert result["upstream_final_decision_parse_ok"] is True
    assert result["measurement_file_exists"] is True
    assert result["mockup_file_exists"] is True
    assert result["mannequin_file_exists"] is True
    assert result["static_fit_file_exists"] is True
    assert result["movement_file_exists"] is True
    assert result["release_cable_file_exists"] is True
    assert result["engineering_review_file_exists"] is True
    assert result["final_decision_file_exists"] is True
    assert result["operator_supplied_completion_ledger_handoff_recorded"] is False
    assert result["candidate_ledger_handoff_ready_for_review"] is False
    assert result["completion_ledger_update_written"] is False
    assert result["physical_validation_complete"] is False
    assert result["stage17_completion_claim_allowed"] is False
    assert result["powered_or_frame_coupled_testing_cleared"] is False
    assert result["fr018_implementation_cleared"] is False
    assert result["prohibited_clearance_flags_recorded"] == []
    assert result["invalid_fields"] == []
    assert "fr017-new-completion-ledger-handoff.ps1 -Mode Create" in result["next_command"]
    assert not output_path.exists()


def test_fr017_completion_ledger_handoff_initializer_creates_candidate_without_writing_ledger(
    tmp_path: Path,
) -> None:
    paths, final_decision_path = _write_ready_final_decision(tmp_path)
    handoff_path = tmp_path / "candidate-ledger-handoff.md"

    proc = _run_script(
        SCRIPT,
        *_handoff_args(paths, final_decision_path, handoff_path),
    )

    assert proc.returncode == 0, proc.stderr
    result = _payload(proc.stdout)
    assert result["kind"] == "francis.fr017.completion_ledger_handoff_initializer"
    assert result["status"] == "created_completion_ledger_handoff"
    assert result["wrote_file"] is True
    assert result["operator_supplied_completion_ledger_handoff_recorded"] is True
    assert result["candidate_ledger_handoff_ready_for_review"] is True
    assert result["upstream_final_decision_status"] == "ready_for_completion_ledger_review"
    assert result["upstream_final_decision_ready"] is True
    assert result["writes_completion_ledger"] is False
    assert result["completion_ledger_update_written"] is False
    assert result["physical_validation_complete"] is False
    assert result["stage17_completion_claim_allowed"] is False
    assert result["powered_or_frame_coupled_testing_cleared"] is False
    assert result["fr018_implementation_cleared"] is False
    assert result["invalid_fields"] == []
    assert result["prohibited_clearance_flags_recorded"] == []
    assert "does not write docs/operations/COMPLETION_LEDGER.md" in result["no_fake_validation_lock"]
    assert "fr017-completion-ledger-gate.ps1" in result["next_command"]

    handoff = handoff_path.read_text(encoding="utf-8-sig")
    assert "PENDING" not in handoff
    assert str(final_decision_path.resolve()) in handoff
    assert "physical_validation_complete: false" in handoff
    assert "stage17_completion_claim_allowed: false" in handoff
    assert "fr018_implementation_cleared: false" in handoff
    assert "completion_ledger_update_written: false" in handoff

    gate = _run_script(
        COMPLETION_LEDGER_GATE_SCRIPT,
        "-Mode",
        "Status",
        *_ready_args(paths),
        "-FinalDecisionPath",
        str(final_decision_path),
        "-LedgerEntryPath",
        str(handoff_path),
    )
    assert gate.returncode == 0, gate.stderr
    gate_result = _payload(gate.stdout)
    assert gate_result["status"] == "ready_for_operator_completion_ledger_update"
    assert gate_result["ledger_entry_review_ready"] is True
    assert gate_result["physical_validation_complete"] is False
    assert gate_result["stage17_completion_claim_allowed"] is False
    assert gate_result["fr018_implementation_cleared"] is False


def test_fr017_completion_ledger_handoff_initializer_refuses_upstream_final_decision_not_ready(
    tmp_path: Path,
) -> None:
    paths, final_decision_path = _write_ready_final_decision(tmp_path)
    decision_payload = json.loads(final_decision_path.read_text(encoding="utf-8"))
    decision_payload["no_fake_validation_lock"]["fr018_implementation_cleared"] = True
    final_decision_path.write_text(json.dumps(decision_payload), encoding="utf-8")
    handoff_path = tmp_path / "candidate-ledger-handoff.md"

    proc = _run_script(
        SCRIPT,
        *_handoff_args(paths, final_decision_path, handoff_path),
    )

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "upstream_final_decision_not_ready"
    assert result["upstream_final_decision_status"] == "failed_final_decision_record"
    assert result["wrote_file"] is False
    assert result["completion_ledger_update_written"] is False
    assert result["fr018_implementation_cleared"] is False


def test_fr017_completion_ledger_handoff_initializer_refuses_template_target(tmp_path: Path) -> None:
    paths, final_decision_path = _write_ready_final_decision(tmp_path)

    proc = _run_script(
        SCRIPT,
        *_handoff_args(paths, final_decision_path, TEMPLATE_PATH),
    )

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "output_path_targets_template"
    assert result["wrote_file"] is False
    assert result["writes_completion_ledger"] is False


def test_fr017_completion_ledger_handoff_initializer_refuses_overwrite(tmp_path: Path) -> None:
    paths, final_decision_path = _write_ready_final_decision(tmp_path)
    handoff_path = tmp_path / "existing-ledger-handoff.md"
    handoff_path.write_text("do not replace", encoding="utf-8")

    proc = _run_script(
        SCRIPT,
        *_handoff_args(paths, final_decision_path, handoff_path),
    )

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "output_file_exists"
    assert result["wrote_file"] is False
    assert handoff_path.read_text(encoding="utf-8") == "do not replace"


def test_fr017_completion_ledger_handoff_initializer_rejects_missing_validation_record(
    tmp_path: Path,
) -> None:
    paths, final_decision_path = _write_ready_final_decision(tmp_path)
    handoff_path = tmp_path / "missing-validation-ledger-handoff.md"

    proc = _run_script(
        SCRIPT,
        *_handoff_args(
            paths,
            final_decision_path,
            handoff_path,
            validation_command_or_record=" ",
        ),
    )

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "invalid_completion_ledger_handoff_input"
    assert result["wrote_file"] is False
    assert result["invalid_fields"] == ["validation_command_or_record"]
    assert result["completion_ledger_update_written"] is False


def test_fr017_completion_ledger_handoff_initializer_blocks_prohibited_clearance_without_writing(
    tmp_path: Path,
) -> None:
    paths, final_decision_path = _write_ready_final_decision(tmp_path)
    handoff_path = tmp_path / "fr018-cleared-ledger-handoff.md"

    proc = _run_script(
        SCRIPT,
        *_handoff_args(
            paths,
            final_decision_path,
            handoff_path,
            confirm_args=CONFIRM_ARGS + ["-Fr018Cleared"],
        ),
    )

    assert proc.returncode == 1
    result = _payload(proc.stdout)
    assert result["status"] == "completion_ledger_prohibited_clearance_recorded_requires_review"
    assert result["wrote_file"] is False
    assert result["prohibited_clearance_flags_recorded"] == ["fr018_cleared"]
    assert result["fr018_implementation_cleared"] is False
