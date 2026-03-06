from __future__ import annotations

from pathlib import Path

from francis_brain.ledger import RunLedger
from francis_core.workspace_fs import WorkspaceFS
from francis_presence.state import compute_state


def test_presence_state_defaults(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    fs = WorkspaceFS(roots=[root], journal_path=root / "journals" / "fs.jsonl")
    ledger = RunLedger(fs)
    state = compute_state(fs, ledger, root)
    assert state.inbox_count == 0
    assert state.inbox_alerts == 0
    assert isinstance(state.last_ledger, list)

