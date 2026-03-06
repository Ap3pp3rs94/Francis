from __future__ import annotations

from pathlib import Path

from francis_core.workspace_fs import WorkspaceFS


def test_workspace_fs_blocks_escape(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    fs = WorkspaceFS(roots=[root], journal_path=root / "journals" / "fs.jsonl")

    try:
        fs.write_text("../escape.txt", "x")
    except ValueError:
        assert True
    else:
        assert False


def test_workspace_fs_writes_and_journals(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    fs = WorkspaceFS(roots=[root], journal_path=root / "journals" / "fs.jsonl")
    fs.write_text("inbox/messages.jsonl", '{"x":1}\n')
    assert (root / "inbox" / "messages.jsonl").exists()
    assert (root / "journals" / "fs.jsonl").exists()

