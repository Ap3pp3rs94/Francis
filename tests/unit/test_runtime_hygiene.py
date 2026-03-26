from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from francis_core.workspace_fs import WorkspaceFS
from services.orchestrator.app.autonomy.event_reactor import collect_events


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def test_event_reactor_ignores_archived_deadletters(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    fs = WorkspaceFS(roots=[root], journal_path=root / "journals" / "fs.jsonl")
    now_iso = datetime.now(timezone.utc).isoformat()

    _write_jsonl(
        root / "queue" / "deadletter.jsonl",
        [
            {
                "id": "dead-open",
                "ts": now_iso,
                "run_id": "run-open",
                "reason": "real failure",
                "status": "open",
            },
            {
                "id": "dead-archived",
                "ts": now_iso,
                "run_id": "run-archived",
                "reason": "test failure path",
                "status": "archived",
            },
        ],
    )

    state = collect_events(fs)
    assert state["deadletter_count"] == 1
    assert any(
        event.get("type") == "queue.deadletter_present" and int(event.get("count", 0)) == 1
        for event in state.get("events", [])
    )
