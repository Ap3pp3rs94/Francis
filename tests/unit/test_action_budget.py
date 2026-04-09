from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from francis_core.workspace_fs import WorkspaceFS
from services.orchestrator.app.autonomy.action_budget import BUDGET_STATE_PATH, load_state


def test_action_budget_read_does_not_rewrite_clean_state(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    fs = WorkspaceFS(roots=[root], journal_path=root / "journals" / "fs.jsonl")
    state_path = root / BUDGET_STATE_PATH
    now = datetime(2026, 4, 9, 12, 0, tzinfo=timezone.utc)
    payload = {
        "date": "2026-04-09",
        "counts": {"mission.tick": 2},
        "last_executed_at": {"mission.tick": "2026-04-09T11:30:00+00:00"},
        "updated_at": "2026-04-09T11:45:00+00:00",
    }
    fs.write_text(BUDGET_STATE_PATH, json.dumps(payload, ensure_ascii=False, indent=2))
    before = state_path.read_text(encoding="utf-8")

    state = load_state(fs, now=now)
    after = state_path.read_text(encoding="utf-8")

    assert state["updated_at"] == "2026-04-09T11:45:00+00:00"
    assert after == before
