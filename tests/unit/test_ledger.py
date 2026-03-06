from __future__ import annotations

from pathlib import Path

from francis_brain.ledger import RunLedger
from francis_core.workspace_fs import WorkspaceFS


def test_ledger_append_and_tail(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    fs = WorkspaceFS(roots=[root], journal_path=root / "journals" / "fs.jsonl")
    ledger = RunLedger(fs)

    ledger.append(run_id="r-1", kind="presence.state", summary={"ok": True})
    entries = ledger.tail(1)

    assert len(entries) == 1
    assert entries[0]["kind"] == "presence.state"

