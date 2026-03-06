from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from francis_core.clock import utc_now_iso
from francis_core.workspace_fs import WorkspaceFS

AUTONOMY_EVENTS_PATH = "autonomy/events.jsonl"
AUTONOMY_DEADLETTER_PATH = "autonomy/deadletter.jsonl"
AUTONOMY_LAST_DISPATCH_PATH = "autonomy/last_dispatch.json"
AUTONOMY_DISPATCH_HISTORY_PATH = "autonomy/dispatch_history.jsonl"
AUTONOMY_LAST_TICK_PATH = "autonomy/last_tick.json"
AUTONOMY_TICK_HISTORY_PATH = "autonomy/tick_history.jsonl"
VALID_PRIORITIES = {"low", "normal", "high", "critical"}
VALID_RISK_TIERS = {"low", "medium", "high", "critical"}
DEFAULT_LEASE_TTL_SECONDS = 300


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _normalize_lease_ttl_seconds(value: int | None) -> int:
    return max(15, min(3600, _safe_int(value, DEFAULT_LEASE_TTL_SECONDS)))


def _normalize_retry_backoff_seconds(value: int | None) -> int:
    return max(0, min(3600, _safe_int(value, 60)))


def _parse_ts(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        parsed = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except Exception:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _read_json(fs: WorkspaceFS, rel_path: str, default: object) -> object:
    try:
        raw = fs.read_text(rel_path)
    except Exception:
        return default
    try:
        return json.loads(raw)
    except Exception:
        return default


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


def _write_json(fs: WorkspaceFS, rel_path: str, payload: dict[str, Any]) -> None:
    fs.write_text(rel_path, json.dumps(payload, ensure_ascii=False, indent=2))


def _write_jsonl(fs: WorkspaceFS, rel_path: str, rows: list[dict[str, Any]]) -> None:
    content = ""
    if rows:
        content = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n"
    fs.write_text(rel_path, content)


def _append_jsonl(fs: WorkspaceFS, rel_path: str, row: dict[str, Any]) -> None:
    existing = ""
    try:
        existing = fs.read_text(rel_path)
    except Exception:
        existing = ""
    if existing and not existing.endswith("\n"):
        existing += "\n"
    fs.write_text(rel_path, existing + json.dumps(row, ensure_ascii=False) + "\n")


def _normalize_priority(value: str | None) -> str:
    raw = str(value or "").strip().lower()
    if raw not in VALID_PRIORITIES:
        return "normal"
    return raw


def _priority_rank(value: str | None) -> int:
    ranks = {"critical": 0, "high": 1, "normal": 2, "low": 3}
    return ranks.get(_normalize_priority(value), 2)


def _normalize_risk_tier(value: str | None, *, priority: str | None = None) -> str:
    raw = str(value or "").strip().lower()
    if raw in VALID_RISK_TIERS:
        return raw
    normalized_priority = _normalize_priority(priority)
    if normalized_priority == "critical":
        return "critical"
    if normalized_priority == "high":
        return "high"
    if normalized_priority == "normal":
        return "medium"
    return "low"


def _sort_due_events(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def key_fn(item: dict[str, Any]) -> tuple[int, str]:
        return (_priority_rank(str(item.get("priority", "normal"))), str(item.get("ts", "")))

    return sorted(rows, key=key_fn)


def _lease_expires_at(row: dict[str, Any], *, lease_ttl_seconds: int) -> datetime | None:
    explicit = _parse_ts(str(row.get("lease_expires_at", "")).strip() or None)
    if explicit is not None:
        return explicit
    leased_at = _parse_ts(str(row.get("leased_at", "")).strip() or None)
    if leased_at is None:
        return None
    ttl = _normalize_lease_ttl_seconds(lease_ttl_seconds)
    return leased_at + timedelta(seconds=ttl)


def enqueue_event(
    fs: WorkspaceFS,
    *,
    run_id: str,
    event_type: str,
    source: str | None = None,
    priority: str | None = None,
    payload: dict[str, Any] | None = None,
    dedupe_key: str | None = None,
    next_run_after: str | None = None,
    risk_tier: str | None = None,
) -> dict[str, Any]:
    now_iso = utc_now_iso()
    rows = _read_jsonl(fs, AUTONOMY_EVENTS_PATH)
    normalized_dedupe = str(dedupe_key or "").strip()
    if normalized_dedupe:
        for row in reversed(rows):
            if str(row.get("dedupe_key", "")).strip() != normalized_dedupe:
                continue
            status = str(row.get("status", "")).strip().lower()
            if status in {"queued", "leased"}:
                return {"status": "duplicate", "event": row}

    schedule_ts = next_run_after if _parse_ts(next_run_after) is not None else now_iso
    event = {
        "id": str(uuid4()),
        "ts": now_iso,
        "run_id": run_id,
        "kind": "autonomy.event",
        "event_type": str(event_type).strip(),
        "source": str(source or "api").strip() or "api",
        "priority": _normalize_priority(priority),
        "risk_tier": _normalize_risk_tier(risk_tier, priority=priority),
        "payload": payload if isinstance(payload, dict) else {},
        "status": "queued",
        "attempts": 0,
        "next_run_after": schedule_ts,
        "dedupe_key": normalized_dedupe or None,
        "lease_id": None,
        "lease_owner": None,
        "leased_at": None,
        "completed_at": None,
        "dispatch_run_id": None,
        "error": None,
    }
    rows.append(event)
    _write_jsonl(fs, AUTONOMY_EVENTS_PATH, rows)
    return {"status": "ok", "event": event}


def preview_due_events(fs: WorkspaceFS, *, max_events: int) -> list[dict[str, Any]]:
    rows = _read_jsonl(fs, AUTONOMY_EVENTS_PATH)
    now = datetime.now(timezone.utc)
    due_queued: list[dict[str, Any]] = []
    for row in rows:
        if str(row.get("status", "")).strip().lower() != "queued":
            continue
        next_run_after = _parse_ts(str(row.get("next_run_after", "")).strip() or None)
        if next_run_after is None or next_run_after <= now:
            due_queued.append(row)
    return _sort_due_events(due_queued)[: max(0, _safe_int(max_events, 0))]


def lease_due_events(
    fs: WorkspaceFS,
    *,
    max_events: int,
    lease_owner: str,
    lease_ttl_seconds: int = DEFAULT_LEASE_TTL_SECONDS,
) -> list[dict[str, Any]]:
    rows = _read_jsonl(fs, AUTONOMY_EVENTS_PATH)
    now = datetime.now(timezone.utc)
    due_queued: list[dict[str, Any]] = []
    for row in rows:
        if str(row.get("status", "")).strip().lower() != "queued":
            continue
        next_run_after = _parse_ts(str(row.get("next_run_after", "")).strip() or None)
        if next_run_after is None or next_run_after <= now:
            due_queued.append(row)
    selected = _sort_due_events(due_queued)[: max(0, _safe_int(max_events, 0))]
    selected_ids = {str(item.get("id", "")) for item in selected if str(item.get("id", ""))}
    if not selected_ids:
        return []

    lease_id = str(uuid4())
    now = datetime.now(timezone.utc)
    leased_at = now.isoformat()
    ttl = _normalize_lease_ttl_seconds(lease_ttl_seconds)
    lease_expires_at = (now + timedelta(seconds=ttl)).isoformat()
    leased_events: list[dict[str, Any]] = []
    updated_rows: list[dict[str, Any]] = []
    for row in rows:
        row_id = str(row.get("id", ""))
        if row_id in selected_ids and str(row.get("status", "")).strip().lower() == "queued":
            next_attempts = _safe_int(row.get("attempts", 0), 0) + 1
            leased = {
                **row,
                "status": "leased",
                "attempts": next_attempts,
                "lease_id": lease_id,
                "lease_owner": str(lease_owner).strip() or "autonomy.dispatch",
                "leased_at": leased_at,
                "lease_expires_at": lease_expires_at,
            }
            leased_events.append(leased)
            updated_rows.append(leased)
        else:
            updated_rows.append(row)
    _write_jsonl(fs, AUTONOMY_EVENTS_PATH, updated_rows)
    return leased_events


def recover_stale_leased_events(
    fs: WorkspaceFS,
    *,
    run_id: str,
    lease_ttl_seconds: int = DEFAULT_LEASE_TTL_SECONDS,
    max_recover: int = 100,
) -> dict[str, Any]:
    rows = _read_jsonl(fs, AUTONOMY_EVENTS_PATH)
    now = datetime.now(timezone.utc)
    ttl = _normalize_lease_ttl_seconds(lease_ttl_seconds)
    recover_budget = max(0, _safe_int(max_recover, 0))
    recovered: list[dict[str, Any]] = []
    updated_rows: list[dict[str, Any]] = []
    for row in rows:
        if str(row.get("status", "")).strip().lower() != "leased":
            updated_rows.append(row)
            continue
        expires_at = _lease_expires_at(row, lease_ttl_seconds=ttl)
        if expires_at is None or expires_at > now or len(recovered) >= recover_budget:
            updated_rows.append(row)
            continue
        queued = {
            **row,
            "status": "queued",
            "next_run_after": utc_now_iso(),
            "lease_id": None,
            "lease_owner": None,
            "leased_at": None,
            "lease_expires_at": None,
            "recovered_at": utc_now_iso(),
            "recovered_by_run_id": run_id,
            "error": None,
        }
        recovered.append(queued)
        updated_rows.append(queued)

    if recovered:
        _write_jsonl(fs, AUTONOMY_EVENTS_PATH, updated_rows)

    return {
        "status": "ok",
        "run_id": run_id,
        "checked_count": len(rows),
        "recovered_count": len(recovered),
        "lease_ttl_seconds": ttl,
        "recovered": recovered,
    }


def release_leased_events(
    fs: WorkspaceFS,
    *,
    run_id: str,
    event_ids: list[str],
    reason: str = "dispatch_halted",
) -> list[dict[str, Any]]:
    ids = {str(item).strip() for item in event_ids if str(item).strip()}
    if not ids:
        return []

    rows = _read_jsonl(fs, AUTONOMY_EVENTS_PATH)
    released_at = utc_now_iso()
    released: list[dict[str, Any]] = []
    updated_rows: list[dict[str, Any]] = []
    for row in rows:
        row_id = str(row.get("id", "")).strip()
        if row_id in ids and str(row.get("status", "")).strip().lower() == "leased":
            queued = {
                **row,
                "status": "queued",
                "next_run_after": released_at,
                "lease_id": None,
                "lease_owner": None,
                "leased_at": None,
                "lease_expires_at": None,
                "released_at": released_at,
                "released_by_run_id": run_id,
                "release_reason": str(reason or "dispatch_halted"),
                "error": None,
            }
            released.append(queued)
            updated_rows.append(queued)
        else:
            updated_rows.append(row)

    if released:
        _write_jsonl(fs, AUTONOMY_EVENTS_PATH, updated_rows)

    return released


def complete_event(
    fs: WorkspaceFS,
    *,
    event_id: str,
    dispatch_run_id: str,
    result: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    rows = _read_jsonl(fs, AUTONOMY_EVENTS_PATH)
    completed_at = utc_now_iso()
    target: dict[str, Any] | None = None
    updated_rows: list[dict[str, Any]] = []
    for row in rows:
        if str(row.get("id", "")) == str(event_id):
            target = {
                **row,
                "status": "dispatched",
                "completed_at": completed_at,
                "dispatch_run_id": dispatch_run_id,
                "result": result if isinstance(result, dict) else {},
                "error": None,
            }
            updated_rows.append(target)
        else:
            updated_rows.append(row)
    if target is not None:
        _write_jsonl(fs, AUTONOMY_EVENTS_PATH, updated_rows)
    return target


def fail_event(
    fs: WorkspaceFS,
    *,
    event_id: str,
    dispatch_run_id: str,
    error: str,
    deadletter_reason: str = "dispatch_failed",
    max_attempts: int = 3,
    retry_backoff_seconds: int = 60,
) -> dict[str, Any] | None:
    rows = _read_jsonl(fs, AUTONOMY_EVENTS_PATH)
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    attempts_limit = max(1, _safe_int(max_attempts, 3))
    backoff_seconds = _normalize_retry_backoff_seconds(retry_backoff_seconds)
    target: dict[str, Any] | None = None
    updated_rows: list[dict[str, Any]] = []
    for row in rows:
        if str(row.get("id", "")) == str(event_id):
            attempts = max(0, _safe_int(row.get("attempts", 0), 0))
            exhausted = attempts >= attempts_limit
            if exhausted:
                target = {
                    **row,
                    "status": "failed",
                    "completed_at": now_iso,
                    "dispatch_run_id": dispatch_run_id,
                    "error": str(error),
                    "max_attempts": attempts_limit,
                }
            else:
                next_run_after = (now + timedelta(seconds=backoff_seconds)).isoformat()
                target = {
                    **row,
                    "status": "queued",
                    "next_run_after": next_run_after,
                    "lease_id": None,
                    "lease_owner": None,
                    "leased_at": None,
                    "lease_expires_at": None,
                    "completed_at": None,
                    "dispatch_run_id": dispatch_run_id,
                    "error": str(error),
                    "last_error": str(error),
                    "last_failed_at": now_iso,
                    "retry_backoff_seconds": backoff_seconds,
                    "max_attempts": attempts_limit,
                }
            updated_rows.append(target)
        else:
            updated_rows.append(row)
    if target is not None:
        _write_jsonl(fs, AUTONOMY_EVENTS_PATH, updated_rows)
        if str(target.get("status", "")).strip().lower() == "failed":
            _append_jsonl(
                fs,
                AUTONOMY_DEADLETTER_PATH,
                {
                    "id": str(uuid4()),
                    "ts": now_iso,
                    "kind": "autonomy.event.deadletter",
                    "reason": deadletter_reason,
                    "dispatch_run_id": dispatch_run_id,
                    "event": target,
                },
            )
    return target


def queue_status(fs: WorkspaceFS, *, limit: int = 100) -> dict[str, Any]:
    rows = _read_jsonl(fs, AUTONOMY_EVENTS_PATH)
    deadletters = _read_jsonl(fs, AUTONOMY_DEADLETTER_PATH)
    now = datetime.now(timezone.utc)
    queued = [row for row in rows if str(row.get("status", "")).strip().lower() == "queued"]
    queued_retry = [row for row in queued if str(row.get("last_failed_at", "")).strip()]
    leased = [row for row in rows if str(row.get("status", "")).strip().lower() == "leased"]
    leased_expired = [
        row
        for row in leased
        if (_lease_expires_at(row, lease_ttl_seconds=DEFAULT_LEASE_TTL_SECONDS) or now) <= now
    ]
    dispatched = [row for row in rows if str(row.get("status", "")).strip().lower() == "dispatched"]
    failed = [row for row in rows if str(row.get("status", "")).strip().lower() == "failed"]
    return {
        "events_total": len(rows),
        "queued_count": len(queued),
        "queued_retry_count": len(queued_retry),
        "leased_count": len(leased),
        "leased_expired_count": len(leased_expired),
        "dispatched_count": len(dispatched),
        "failed_count": len(failed),
        "deadletter_count": len(deadletters),
        "queued": _sort_due_events(queued)[-max(0, limit) :],
        "leased": leased[-max(0, limit) :],
        "leased_expired": leased_expired[-max(0, limit) :],
        "recent_dispatched": dispatched[-max(0, limit) :],
        "recent_failed": failed[-max(0, limit) :],
        "recent_deadletter": deadletters[-max(0, limit) :],
    }


def write_last_dispatch(fs: WorkspaceFS, *, payload: dict[str, Any]) -> None:
    _write_json(fs, AUTONOMY_LAST_DISPATCH_PATH, payload)


def read_last_dispatch(fs: WorkspaceFS) -> dict[str, Any]:
    parsed = _read_json(fs, AUTONOMY_LAST_DISPATCH_PATH, {})
    return parsed if isinstance(parsed, dict) else {}


def append_dispatch_history(fs: WorkspaceFS, *, payload: dict[str, Any]) -> None:
    _append_jsonl(fs, AUTONOMY_DISPATCH_HISTORY_PATH, payload)


def read_dispatch_history(fs: WorkspaceFS, *, limit: int = 50) -> list[dict[str, Any]]:
    rows = _read_jsonl(fs, AUTONOMY_DISPATCH_HISTORY_PATH)
    n = max(0, min(_safe_int(limit, 50), 500))
    if n == 0:
        return []
    return rows[-n:]


def write_last_tick(fs: WorkspaceFS, *, payload: dict[str, Any]) -> None:
    _write_json(fs, AUTONOMY_LAST_TICK_PATH, payload)


def read_last_tick(fs: WorkspaceFS) -> dict[str, Any]:
    parsed = _read_json(fs, AUTONOMY_LAST_TICK_PATH, {})
    return parsed if isinstance(parsed, dict) else {}


def append_tick_history(fs: WorkspaceFS, *, payload: dict[str, Any]) -> None:
    _append_jsonl(fs, AUTONOMY_TICK_HISTORY_PATH, payload)


def read_tick_history(fs: WorkspaceFS, *, limit: int = 50) -> list[dict[str, Any]]:
    rows = _read_jsonl(fs, AUTONOMY_TICK_HISTORY_PATH)
    n = max(0, min(_safe_int(limit, 50), 500))
    if n == 0:
        return []
    return rows[-n:]
