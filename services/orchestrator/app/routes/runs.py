from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from francis_core.config import settings
from francis_core.workspace_fs import WorkspaceFS
from services.orchestrator.app.control_state import check_action_allowed

router = APIRouter(tags=["runs"])

_workspace_root = Path(settings.workspace_root).resolve()
_repo_root = _workspace_root.parent
_fs = WorkspaceFS(
    roots=[_workspace_root],
    journal_path=(_workspace_root / "journals" / "fs.jsonl").resolve(),
)


def _read_jsonl(rel_path: str) -> list[dict[str, Any]]:
    try:
        raw = _fs.read_text(rel_path)
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


def _read_json(rel_path: str, default: Any) -> Any:
    try:
        raw = _fs.read_text(rel_path)
    except Exception:
        return default
    try:
        parsed = json.loads(raw)
    except Exception:
        return default
    return parsed


def _summarize_runs(events: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for event in events:
        run_id = str(event.get("run_id", "")).strip()
        if not run_id:
            continue
        ts = str(event.get("ts", "")).strip()
        kind = str(event.get("kind", "")).strip()

        bucket = grouped.setdefault(
            run_id,
            {
                "run_id": run_id,
                "first_ts": ts,
                "last_ts": ts,
                "event_count": 0,
                "last_kind": "",
                "kinds": [],
            },
        )
        bucket["event_count"] = int(bucket.get("event_count", 0)) + 1
        if ts and (not str(bucket.get("first_ts")) or ts < str(bucket.get("first_ts"))):
            bucket["first_ts"] = ts
        if ts and (not str(bucket.get("last_ts")) or ts >= str(bucket.get("last_ts"))):
            bucket["last_ts"] = ts
            if kind:
                bucket["last_kind"] = kind
        if kind and kind not in bucket["kinds"]:
            bucket["kinds"].append(kind)

    ordered = sorted(grouped.values(), key=lambda item: str(item.get("last_ts", "")), reverse=True)
    n = max(0, min(limit, 200))
    return ordered[:n]


@router.get("/runs")
def runs(limit: int = 20) -> dict:
    allowed, reason, _state = check_action_allowed(
        _fs,
        repo_root=_repo_root,
        workspace_root=_workspace_root,
        app="receipts",
        action="runs.read",
        mutating=False,
    )
    if not allowed:
        raise HTTPException(status_code=403, detail=f"Control denied: {reason}")

    ledger_primary = _read_jsonl("runs/run_ledger.jsonl")
    ledger_legacy = _read_jsonl("brain/run_ledger.jsonl")
    summaries = _summarize_runs(ledger_primary + ledger_legacy, limit=limit)
    last_run = _read_json("runs/last_run.json", {})
    if not isinstance(last_run, dict):
        last_run = {}

    return {
        "status": "ok",
        "count": len(summaries),
        "runs": summaries,
        "last_run": last_run,
    }
