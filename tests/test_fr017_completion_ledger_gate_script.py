from __future__ import annotations

import json
import shutil
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
SCRIPT = ROOT / "scripts" / "fr017-completion-ledger-gate.ps1"


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
        timeout_seconds=120,
    )


def _payload(stdout: str) -> dict[str, Any]:
    return json.loads(stdout)


def _portable_path(path: str) -> str:
    return path.replace("\\", "/")


def _write_ready_final_decision(tmp_path: Path) -> tuple[tuple[Path, Path, Path, Path, Path, Path, Path], Path]:
    paths = _write_ready_evidence(tmp_path)
    final_physical_gate_record_path = _write_final_physical_gate_record(tmp_path, paths)
    final_decision_path = tmp_path / "ready-final-decision.json"
    final_decision_path.write_text(
        json.dumps(_ready_final_decision_payload(final_physical_gate_record_path)),
        encoding="utf-8",
    )
    return paths, final_decision_path


def _ready_ledger_entry(final_decision_path: Path) -> str:
    return f"""### 2026-06-23 - Stage 17 / FR-017 Forearm Cuffs completion ledger handoff

Current posture: Stage 17 / FR-017 Forearm Cuffs evidence chain reports ready_for_completion_ledger_review.

Evidence:

- Final decision record path: {final_decision_path}
- physical_validation_complete: false
- stage17_completion_claim_allowed: false
- fr018_implementation_cleared: false
- Powered testing: not cleared.
- Frame-coupled testing: not cleared.
- Load-bearing use: not approved.
- FR-018 implementation remains blocked and not cleared.

Remaining truthful gap:

- This is a candidate ledger handoff only. It does not clear FR-018 or powered,
  frame-coupled, or load-bearing use.
"""


def test_fr017_completion_ledger_gate_blocks_until_final_decision_ready() -> None:
    proc = _run_gate("-Mode", "Status")

    assert proc.returncode == 0, proc.stderr
    payload = _payload(proc.stdout)
    assert payload["kind"] == "francis.fr017.completion_ledger_gate"
    assert payload["status"] == "pending_final_decision_record"
    assert payload["final_decision_gate_status"] == "pending_final_physical_gate"
    assert payload["final_decision_record_ready"] is False
    assert payload["ledger_entry_review_ready"] is False
    assert payload["physical_validation_complete"] is False
    assert payload["stage17_completion_claim_allowed"] is False
    assert payload["fr018_implementation_cleared"] is False
    assert payload["read_only_contract"] is True
    assert payload["writes_repo"] is False


def test_fr017_completion_ledger_gate_requires_ledger_entry_after_final_decision_ready(
    tmp_path: Path,
) -> None:
    paths, final_decision_path = _write_ready_final_decision(tmp_path)

    proc = _run_gate("-Mode", "Status", *_ready_args(paths), "-FinalDecisionPath", str(final_decision_path))

    assert proc.returncode == 0, proc.stderr
    payload = _payload(proc.stdout)
    assert payload["status"] == "pending_completion_ledger_entry"
    assert payload["final_decision_record_ready"] is True
    assert payload["ledger_entry_review_ready"] is False
    assert payload["missing_fields"] == ["ledger_entry_path"]
    assert payload["next_required_ledger_input"] == (
        "create_candidate_completion_ledger_handoff_with_fr017-new-completion-ledger-handoff.ps1_then_rerun_completion_ledger_gate"
    )
    assert "fr017-new-completion-ledger-handoff.ps1" in payload["completion_ledger_handoff_runbook_contract"]
    assert _portable_path(payload["completion_ledger_handoff_template_path"]).endswith(
        "FR-017_Stage17_Package/FR-017-COMPLETION-LEDGER-HANDOFF-TEMPLATE.md"
    )
    assert _portable_path(payload["completion_ledger_handoff_initializer_path"]).endswith(
        "scripts/fr017-new-completion-ledger-handoff.ps1"
    )
    assert payload["completion_ledger_handoff_working_record_name_pattern"] == (
        "FR-017-COMPLETION-LEDGER-HANDOFF-YYYY-MM-DD-PILOT.md"
    )
    assert payload["physical_validation_complete"] is False
    assert payload["stage17_completion_claim_allowed"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_completion_ledger_gate_reports_default_template_as_pending(
    tmp_path: Path,
) -> None:
    paths, final_decision_path = _write_ready_final_decision(tmp_path)
    ledger_entry_path = tmp_path / "pending-ledger-handoff.md"
    ledger_entry_path.write_text(
        (ROOT / "FR-017_Stage17_Package" / "FR-017-COMPLETION-LEDGER-HANDOFF-TEMPLATE.md").read_text(encoding="utf-8"),
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
    )

    assert proc.returncode == 0, proc.stderr
    payload = _payload(proc.stdout)
    assert payload["status"] == "pending_completion_ledger_entry"
    assert payload["final_decision_record_ready"] is True
    assert payload["ledger_entry_review_ready"] is False
    assert "ledger_entry.template_placeholders" in payload["missing_fields"]
    assert payload["physical_validation_complete"] is False
    assert payload["stage17_completion_claim_allowed"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_completion_ledger_gate_ready_handoff_remains_read_only(
    tmp_path: Path,
) -> None:
    paths, final_decision_path = _write_ready_final_decision(tmp_path)
    ledger_entry_path = tmp_path / "candidate-ledger-entry.md"
    ledger_entry_path.write_text(_ready_ledger_entry(final_decision_path), encoding="utf-8")

    proc = _run_gate(
        "-Mode",
        "Status",
        *_ready_args(paths),
        "-FinalDecisionPath",
        str(final_decision_path),
        "-LedgerEntryPath",
        str(ledger_entry_path),
    )

    assert proc.returncode == 0, proc.stderr
    payload = _payload(proc.stdout)
    assert payload["status"] == "ready_for_operator_completion_ledger_update"
    assert payload["final_decision_record_ready"] is True
    assert payload["ledger_entry_exists"] is True
    assert payload["ledger_entry_read_ok"] is True
    assert payload["ledger_entry_review_ready"] is True
    assert "read-only" in payload["ledger_entry_contract"]
    assert "fr017-new-completion-ledger-handoff.ps1" in payload["completion_ledger_handoff_runbook_contract"]
    assert payload["missing_fields"] == []
    assert payload["invalid_fields"] == []
    assert payload["prohibited_clearance_flags"] == []
    assert payload["physical_validation_complete"] is False
    assert payload["stage17_completion_claim_allowed"] is False
    assert payload["powered_or_frame_coupled_testing_cleared"] is False
    assert payload["fr018_implementation_cleared"] is False
    assert payload["writes_repo"] is False
    assert payload["writes_data"] is False


def test_fr017_completion_ledger_gate_fails_closed_on_prohibited_clearance(
    tmp_path: Path,
) -> None:
    paths, final_decision_path = _write_ready_final_decision(tmp_path)
    ledger_entry_path = tmp_path / "unsafe-ledger-entry.md"
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
        *_ready_args(paths),
        "-FinalDecisionPath",
        str(final_decision_path),
        "-LedgerEntryPath",
        str(ledger_entry_path),
    )

    assert proc.returncode == 1
    payload = _payload(proc.stdout)
    assert payload["status"] == "failed_completion_ledger_entry"
    assert "ledger_entry.FR-018_cleared" in payload["prohibited_clearance_flags"]
    assert payload["ledger_entry_review_ready"] is False
    assert payload["physical_validation_complete"] is False
    assert payload["stage17_completion_claim_allowed"] is False
    assert payload["fr018_implementation_cleared"] is False
