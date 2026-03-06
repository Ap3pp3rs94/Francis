from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter

from francis_core.config import settings
from francis_core.workspace_fs import WorkspaceFS

router = APIRouter(tags=["receipts"])

_workspace_root = Path(settings.workspace_root).resolve()
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
            if isinstance(parsed, dict):
                rows.append(parsed)
        except Exception:
            continue
    return rows


def _tail(rows: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    n = max(0, min(limit, 200))
    return rows[-n:] if n else []


def _combine_ledger(
    ledger_primary: list[dict[str, Any]],
    ledger_legacy: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    combined = [*ledger_primary, *ledger_legacy]
    combined.sort(key=lambda row: str(row.get("ts", "")))
    return combined


@router.get("/receipts/latest")
def receipts_latest(limit: int = 20) -> dict:
    ledger_primary = _read_jsonl("runs/run_ledger.jsonl")
    ledger_legacy = _read_jsonl("brain/run_ledger.jsonl")
    ledger = _combine_ledger(ledger_primary, ledger_legacy)
    decisions = _read_jsonl("journals/decisions.jsonl")
    logs = _read_jsonl("logs/francis.log.jsonl")
    mission_history = _read_jsonl("missions/history.jsonl")
    queue_deadletter = _read_jsonl("queue/deadletter.jsonl")

    latest_run_id = None
    for row in reversed(ledger):
        if row.get("run_id"):
            latest_run_id = str(row["run_id"])
            break

    return {
        "status": "ok",
        "latest_run_id": latest_run_id,
        "receipts": {
            "ledger": _tail(ledger, limit),
            "decisions": _tail(decisions, limit),
            "logs": _tail(logs, limit),
            "mission_history": _tail(mission_history, limit),
            "deadletter": _tail(queue_deadletter, limit),
        },
    }


@router.get("/runs/{run_id}")
def run_receipts(run_id: str, limit: int = 100) -> dict:
    def by_run(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [row for row in rows if str(row.get("run_id", "")) == run_id]

    ledger_primary = by_run(_read_jsonl("runs/run_ledger.jsonl"))
    ledger_legacy = by_run(_read_jsonl("brain/run_ledger.jsonl"))
    ledger = _combine_ledger(ledger_primary, ledger_legacy)
    decisions = by_run(_read_jsonl("journals/decisions.jsonl"))
    logs = by_run(_read_jsonl("logs/francis.log.jsonl"))
    mission_history = by_run(_read_jsonl("missions/history.jsonl"))
    deadletter = by_run(_read_jsonl("queue/deadletter.jsonl"))

    combined_count = (
        len(ledger)
        + len(decisions)
        + len(logs)
        + len(mission_history)
        + len(deadletter)
    )
    return {
        "status": "ok",
        "run_id": run_id,
        "count": combined_count,
        "receipts": {
            "ledger": _tail(ledger, limit),
            "decisions": _tail(decisions, limit),
            "logs": _tail(logs, limit),
            "mission_history": _tail(mission_history, limit),
            "deadletter": _tail(deadletter, limit),
        },
    }
