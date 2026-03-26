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


def test_presence_state_ignores_archived_inbox_rows(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    fs = WorkspaceFS(roots=[root], journal_path=root / "journals" / "fs.jsonl")
    ledger = RunLedger(fs)
    inbox = root / "inbox" / "messages.jsonl"
    inbox.parent.mkdir(parents=True, exist_ok=True)
    inbox.write_text(
        "\n".join(
            [
                '{"id":"live-alert","severity":"alert","title":"Live","status":"open"}',
                '{"id":"old-alert","severity":"alert","title":"Old","status":"archived"}',
                '{"id":"live-info","severity":"info","title":"Info","status":"open"}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    state = compute_state(fs, ledger, root)
    assert state.inbox_count == 2
    assert state.inbox_alerts == 1
