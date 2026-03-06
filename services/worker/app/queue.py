from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from francis_core.workspace_fs import WorkspaceFS

QUEUE_PATH = "queue/jobs.jsonl"
PRIORITY_RANKS = {
    "critical": 0,
    "urgent": 1,
    "high": 2,
    "normal": 3,
    "low": 4,
}


def _read_jsonl(fs: WorkspaceFS, rel_path: str) -> list[dict[str, Any]]:
    try:
        raw = fs.read_text(rel_path)
    except Exception:
        return []
    rows: list[dict[str, Any]] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
        except Exception:
            continue
        if isinstance(parsed, dict):
            rows.append(parsed)
    return rows


def _parse_iso(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts)
    except Exception:
        return None


def _is_due(job: dict[str, Any]) -> bool:
    next_run_after = _parse_iso(str(job.get("next_run_after", "")).strip() or None)
    if next_run_after is None:
        return True
    return next_run_after <= datetime.now(timezone.utc)


def _priority_value(job: dict[str, Any]) -> int:
    raw = job.get("priority", "normal")
    if isinstance(raw, int):
        return max(-100, min(100, raw))
    text = str(raw).strip().lower()
    if text in PRIORITY_RANKS:
        return PRIORITY_RANKS[text]
    return PRIORITY_RANKS["normal"]


def list_queued_jobs(
    fs: WorkspaceFS,
    *,
    limit: int = 20,
    action_allowlist: set[str] | None = None,
    due_only: bool = True,
) -> list[dict[str, Any]]:
    rows = _read_jsonl(fs, QUEUE_PATH)
    queued = [row for row in rows if str(row.get("status", "")).strip().lower() == "queued"]
    if action_allowlist is not None:
        queued = [row for row in queued if str(row.get("action", "")).strip().lower() in action_allowlist]
    if due_only:
        queued = [row for row in queued if _is_due(row)]
    queued.sort(key=lambda row: (_priority_value(row), str(row.get("ts", ""))))
    n = max(0, min(int(limit), 500))
    if n == 0:
        return []
    return queued[:n]


def queued_count(
    fs: WorkspaceFS,
    *,
    action_allowlist: set[str] | None = None,
    due_only: bool = False,
) -> int:
    return len(list_queued_jobs(fs, limit=500, action_allowlist=action_allowlist, due_only=due_only))
