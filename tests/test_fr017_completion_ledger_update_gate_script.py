from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from tests.powershell_script_runner import run_powershell_script
from tests.test_fr017_completion_ledger_gate_script import (
    _ready_ledger_entry,
    _write_ready_final_decision,
)
from tests.test_fr017_final_decision_record_gate_script import _ready_args


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "fr017-completion-ledger-update-gate.ps1"


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


def test_fr017_completion_ledger_update_gate_blocks_until_handoff_ready() -> None:
    proc = _run_gate("-Mode", "Status")

    assert proc.returncode == 0, proc.stderr
    payload = _payload(proc.stdout)
    assert payload["kind"] == "francis.fr017.completion_ledger_update_gate"
    assert payload["status"] == "pending_completion_ledger_handoff"
    assert payload["completion_ledger_gate_status"] == "pending_final_decision_record"
    assert payload["completion_ledger_handoff_ready"] is False
    assert payload["ledger_update_review_ready"] is False
    assert payload["physical_validation_complete"] is False
    assert payload["stage17_completion_claim_allowed"] is False
    assert payload["powered_or_frame_coupled_testing_cleared"] is False
    assert payload["fr018_implementation_cleared"] is False
    assert payload["read_only_contract"] is True
    assert payload["writes_repo"] is False


def test_fr017_completion_ledger_update_gate_requires_ledger_update_after_handoff_ready(
    tmp_path: Path,
) -> None:
    paths, final_decision_path = _write_ready_final_decision(tmp_path)
    ledger_entry_path = tmp_path / "candidate-ledger-entry.md"
    ledger_entry_path.write_text(_ready_ledger_entry(final_decision_path), encoding="utf-8")
    missing_completion_ledger_path = tmp_path / "missing-completion-ledger.md"

    proc = _run_gate(
        "-Mode",
        "Status",
        *_ready_args(paths),
        "-FinalDecisionPath",
        str(final_decision_path),
        "-LedgerEntryPath",
        str(ledger_entry_path),
        "-CompletionLedgerPath",
        str(missing_completion_ledger_path),
    )

    assert proc.returncode == 0, proc.stderr
    payload = _payload(proc.stdout)
    assert payload["status"] == "pending_completion_ledger_update"
    assert payload["completion_ledger_gate_status"] == "ready_for_operator_completion_ledger_update"
    assert payload["completion_ledger_handoff_ready"] is True
    assert payload["completion_ledger_exists"] is False
    assert payload["ledger_update_section_found"] is False
    assert payload["ledger_update_review_ready"] is False
    assert payload["missing_fields"] == ["completion_ledger_path"]
    assert payload["next_required_completion_ledger_update_input"] == (
        "operator_updates_or_provides_completion_ledger_file_containing_reviewed_FR-017_handoff_entry_then_reruns_completion_ledger_update_gate"
    )
    assert payload["physical_validation_complete"] is False
    assert payload["stage17_completion_claim_allowed"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_completion_ledger_update_gate_accepts_proposed_ledger_section_read_only(
    tmp_path: Path,
) -> None:
    paths, final_decision_path = _write_ready_final_decision(tmp_path)
    ledger_entry = _ready_ledger_entry(final_decision_path)
    ledger_entry_path = tmp_path / "candidate-ledger-entry.md"
    ledger_entry_path.write_text(ledger_entry, encoding="utf-8")
    completion_ledger_path = tmp_path / "COMPLETION_LEDGER.md"
    completion_ledger_path.write_text("# FRANCIS - COMPLETION LEDGER\n\n" + ledger_entry, encoding="utf-8")

    proc = _run_gate(
        "-Mode",
        "Status",
        *_ready_args(paths),
        "-FinalDecisionPath",
        str(final_decision_path),
        "-LedgerEntryPath",
        str(ledger_entry_path),
        "-CompletionLedgerPath",
        str(completion_ledger_path),
    )

    assert proc.returncode == 0, proc.stderr
    payload = _payload(proc.stdout)
    assert payload["status"] == "ready_for_operator_stage17_completion_ledger_update_review"
    assert payload["completion_ledger_handoff_ready"] is True
    assert payload["completion_ledger_exists"] is True
    assert payload["completion_ledger_read_ok"] is True
    assert payload["candidate_ledger_heading"].startswith("### 2026-06-23 - Stage 17 / FR-017")
    assert payload["ledger_update_section_found"] is True
    assert payload["ledger_update_review_ready"] is True
    assert "read-only" in payload["completion_ledger_update_guard_contract"]
    assert payload["missing_fields"] == []
    assert payload["invalid_fields"] == []
    assert payload["prohibited_clearance_flags"] == []
    assert payload["physical_validation_complete"] is False
    assert payload["stage17_completion_claim_allowed"] is False
    assert payload["powered_or_frame_coupled_testing_cleared"] is False
    assert payload["fr018_implementation_cleared"] is False
    assert payload["writes_repo"] is False
    assert payload["writes_data"] is False


def test_fr017_completion_ledger_update_gate_fails_closed_on_proposed_clearance(
    tmp_path: Path,
) -> None:
    paths, final_decision_path = _write_ready_final_decision(tmp_path)
    ledger_entry = _ready_ledger_entry(final_decision_path)
    ledger_entry_path = tmp_path / "candidate-ledger-entry.md"
    ledger_entry_path.write_text(ledger_entry, encoding="utf-8")
    completion_ledger_path = tmp_path / "unsafe-completion-ledger.md"
    completion_ledger_path.write_text(
        "# FRANCIS - COMPLETION LEDGER\n\n"
        + ledger_entry.replace(
            "FR-018 implementation remains blocked and not cleared.",
            "FR-018 cleared.",
        ),
        encoding="utf-8",
    )

    proc = _run_gate(
        "-Mode",
        "Status",
        *_ready_args(paths),
        "-FinalDecisionPath",
        str(final_decision_path),
        "-LedgerEntryPath",
        str(ledger_entry_path),
        "-CompletionLedgerPath",
        str(completion_ledger_path),
    )

    assert proc.returncode == 1
    payload = _payload(proc.stdout)
    assert payload["status"] == "failed_completion_ledger_update"
    assert "completion_ledger_update.FR-018_cleared" in payload["prohibited_clearance_flags"]
    assert payload["completion_ledger_handoff_ready"] is True
    assert payload["ledger_update_review_ready"] is False
    assert payload["physical_validation_complete"] is False
    assert payload["stage17_completion_claim_allowed"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_completion_ledger_update_gate_requires_candidate_heading_in_ledger(
    tmp_path: Path,
) -> None:
    paths, final_decision_path = _write_ready_final_decision(tmp_path)
    ledger_entry_path = tmp_path / "candidate-ledger-entry.md"
    ledger_entry_path.write_text(_ready_ledger_entry(final_decision_path), encoding="utf-8")
    completion_ledger_path = tmp_path / "no-fr017-section.md"
    completion_ledger_path.write_text(
        "# FRANCIS - COMPLETION LEDGER\n\n### unrelated entry\n\nNo FR-017 handoff.", encoding="utf-8"
    )

    proc = _run_gate(
        "-Mode",
        "Status",
        *_ready_args(paths),
        "-FinalDecisionPath",
        str(final_decision_path),
        "-LedgerEntryPath",
        str(ledger_entry_path),
        "-CompletionLedgerPath",
        str(completion_ledger_path),
    )

    assert proc.returncode == 0, proc.stderr
    payload = _payload(proc.stdout)
    assert payload["status"] == "pending_completion_ledger_update"
    assert payload["completion_ledger_handoff_ready"] is True
    assert payload["completion_ledger_exists"] is True
    assert payload["completion_ledger_read_ok"] is True
    assert payload["ledger_update_section_found"] is False
    assert payload["missing_fields"] == ["completion_ledger_update.candidate_heading"]
    assert payload["ledger_update_review_ready"] is False
    assert payload["physical_validation_complete"] is False
    assert payload["fr018_implementation_cleared"] is False
