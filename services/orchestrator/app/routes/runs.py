from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from francis_brain.calibration import summarize_fabric_posture
from francis_brain.recall import summarize_fabric_scope
from francis_core.config import settings
from francis_core.workspace_fs import WorkspaceFS
from services.orchestrator.app.control_state import check_action_allowed
from services.orchestrator.app.takeover_snapshot import load_takeover_state, summarize_takeover_handback

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


def _derive_trace_id(row: dict[str, Any]) -> str:
    explicit = str(row.get("trace_id", "")).strip()
    if explicit:
        return explicit
    run_id = str(row.get("run_id", "")).strip()
    if not run_id:
        return ""
    for marker in (
        ":event:",
        ":recover",
        ":observer:",
        ":mission:",
        ":worker:",
        ":worker-recover:",
    ):
        if marker in run_id:
            return run_id.split(marker, 1)[0].strip()
    if ":" in run_id:
        return run_id.split(":", 1)[0].strip()
    return run_id


def _tail(rows: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    n = max(0, min(limit, 500))
    return rows[-n:] if n else []


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


@router.get("/runs/trace/{trace_id}")
def runs_trace(trace_id: str, limit: int = 200) -> dict:
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

    normalized = str(trace_id).strip()
    if not normalized:
        raise HTTPException(status_code=400, detail="trace_id is required")

    sources = {
        "ledger_primary": _read_jsonl("runs/run_ledger.jsonl"),
        "ledger_legacy": _read_jsonl("brain/run_ledger.jsonl"),
        "decisions": _read_jsonl("journals/decisions.jsonl"),
        "logs": _read_jsonl("logs/francis.log.jsonl"),
        "mission_history": _read_jsonl("missions/history.jsonl"),
        "deadletter": _read_jsonl("queue/deadletter.jsonl"),
    }

    filtered: dict[str, list[dict[str, Any]]] = {}
    for source, rows in sources.items():
        filtered[source] = [
            row
            for row in rows
            if str(row.get("run_id", "")).strip() == normalized or _derive_trace_id(row) == normalized
        ]

    counts = {name: len(rows) for name, rows in filtered.items()}
    total = sum(counts.values())
    fabric_summary = summarize_fabric_scope(_fs, trace_id=normalized, refresh=False)
    handback_summary = summarize_takeover_handback(
        load_takeover_state(_workspace_root),
        evidence_scope="trace",
        trace_id=normalized,
    )
    return {
        "status": "ok",
        "trace_id": normalized,
        "count": total,
        "counts": counts,
        "summary": {
            "evidence_scope": "trace",
            "fabric": {
                "artifact_count": int(fabric_summary.get("artifact_count", 0) or 0),
                "citation_ready_count": int(fabric_summary.get("citation_ready_count", 0) or 0),
                "source_count": int(fabric_summary.get("source_count", 0) or 0),
                "generated_at": fabric_summary.get("generated_at"),
                "trust": summarize_fabric_posture(fabric_summary),
            },
            "handback": handback_summary,
        },
        "receipts": {
            name: _tail(rows, limit) for name, rows in filtered.items()
        },
    }
