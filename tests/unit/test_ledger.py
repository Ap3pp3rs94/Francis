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
    summary = ledger.summary(recent_limit=5, tail_limit=5)

    assert len(entries) == 1
    assert entries[0]["kind"] == "presence.state"
    assert summary["count"] == 1
    assert summary["recent"][0]["run_id"] == "r-1"
    assert (root / "runs" / "run_ledger.summary.json").exists()


def test_ledger_summary_rebuilds_from_existing_ledger(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    fs = WorkspaceFS(roots=[root], journal_path=root / "journals" / "fs.jsonl")
    fs.append_jsonl(
        "runs/run_ledger.jsonl",
        {"ts": "2026-04-09T10:00:00+00:00", "run_id": "r-1", "kind": "mission.tick", "summary": {"ok": True}},
    )
    fs.append_jsonl(
        "runs/run_ledger.jsonl",
        {"ts": "2026-04-09T10:01:00+00:00", "run_id": "r-2", "kind": "worker.cycle", "summary": {"ok": True}},
    )

    ledger = RunLedger(fs)
    summary = ledger.summary(recent_limit=5, tail_limit=5)

    assert summary["count"] == 2
    assert [row["run_id"] for row in summary["recent"]] == ["r-2", "r-1"]
    assert [row["run_id"] for row in summary["tail"]] == ["r-1", "r-2"]
