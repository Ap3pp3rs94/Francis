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


def _read_json(rel_path: str, default: object) -> object:
    try:
        raw = _fs.read_text(rel_path)
    except Exception:
        return default
    try:
        return json.loads(raw)
    except Exception:
        return default


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


def _map_dispatch_trust(row: dict[str, Any], source: str) -> dict[str, Any]:
    verification = row.get("verification", {}) if isinstance(row.get("verification"), dict) else {}
    verification_status = row.get("verification_status", verification.get("verification_status"))
    confidence = row.get("confidence", verification.get("confidence"))
    can_claim_done = row.get("can_claim_done", verification.get("can_claim_done"))
    claim = row.get("claim", verification.get("claim"))
    completion = row.get("completion_state")
    if not completion:
        completion = "done" if bool(can_claim_done) and str(verification_status or "").lower() == "verified" else "incomplete"
    return {
        "id": row.get("id"),
        "ts": row.get("ts"),
        "source": source,
        "kind": row.get("kind", "autonomy.dispatch"),
        "run_id": row.get("run_id"),
        "trace_id": _derive_trace_id(row),
        "verification_status": verification_status,
        "confidence": confidence,
        "can_claim_done": bool(can_claim_done),
        "claim": claim,
        "completion_state": completion,
        "trust_badge": row.get("trust_badge"),
    }


def _map_tick_trust(row: dict[str, Any], source: str) -> dict[str, Any]:
    verification = row.get("verification", {}) if isinstance(row.get("verification"), dict) else {}
    verification_status = verification.get("verification_status")
    confidence = verification.get("confidence")
    can_claim_done = bool(verification.get("can_claim_done"))
    completion = row.get("completion_state")
    if not completion:
        completion = "done" if can_claim_done and str(verification_status or "").lower() == "verified" else "incomplete"
    return {
        "id": row.get("id"),
        "ts": row.get("ts"),
        "source": source,
        "kind": row.get("kind", "autonomy.reactor.tick"),
        "run_id": row.get("run_id"),
        "trace_id": _derive_trace_id(row),
        "verification_status": verification_status,
        "confidence": confidence,
        "can_claim_done": can_claim_done,
        "claim": verification.get("claim"),
        "completion_state": completion,
        "trust_badge": row.get("trust_badge"),
        "evidence": verification.get("evidence") if isinstance(verification.get("evidence"), dict) else {},
    }


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


@router.get("/receipts/trust/latest")
def receipts_trust_latest(limit: int = 50, run_id: str | None = None, trace_id: str | None = None) -> dict:
    dispatch_history = _read_jsonl("autonomy/dispatch_history.jsonl")
    tick_history = _read_jsonl("autonomy/tick_history.jsonl")
    last_dispatch = _read_json("autonomy/last_dispatch.json", {})
    last_tick = _read_json("autonomy/last_tick.json", {})

    rows: list[dict[str, Any]] = []
    rows.extend(_map_dispatch_trust(item, source="autonomy.dispatch.history") for item in dispatch_history)
    rows.extend(_map_tick_trust(item, source="autonomy.reactor.tick.history") for item in tick_history)
    if isinstance(last_dispatch, dict) and last_dispatch:
        rows.append(_map_dispatch_trust(last_dispatch, source="autonomy.dispatch.last"))
    if isinstance(last_tick, dict) and last_tick:
        rows.append(_map_tick_trust(last_tick, source="autonomy.reactor.tick.last"))

    unique: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for row in rows:
        key = (
            str(row.get("source", "")),
            str(row.get("run_id", "")),
            str(row.get("trace_id", "")),
            str(row.get("ts", "")),
        )
        unique[key] = row

    merged = sorted(unique.values(), key=lambda item: str(item.get("ts", "")))
    run_filter = str(run_id or "").strip()
    trace_filter = str(trace_id or "").strip()
    if run_filter:
        merged = [
            row
            for row in merged
            if str(row.get("run_id", "")).strip() == run_filter or str(row.get("trace_id", "")).strip() == run_filter
        ]
    if trace_filter:
        merged = [row for row in merged if str(row.get("trace_id", "")).strip() == trace_filter]

    n = max(0, min(int(limit), 500))
    trust_rows = merged[-n:] if n else []
    return {
        "status": "ok",
        "count": len(trust_rows),
        "filters": {
            "run_id": run_filter or None,
            "trace_id": trace_filter or None,
            "limit": n,
        },
        "trust_receipts": trust_rows,
    }
