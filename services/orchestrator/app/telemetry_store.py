from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from francis_core.clock import utc_now_iso
from francis_core.redaction import redact
from francis_core.workspace_fs import WorkspaceFS

TELEMETRY_CONFIG_PATH = "telemetry/config.json"
TELEMETRY_EVENTS_PATH = "telemetry/events.jsonl"
DEFAULT_ALLOWED_STREAMS = [
    "terminal",
    "git",
    "build",
    "ide",
    "browser_console",
    "dev_server",
    "filesystem",
]
DEFAULT_RETENTION_MAX_EVENTS = 5000
DEFAULT_RETENTION_MAX_AGE_HOURS = 168
ALLOWED_SEVERITIES = {"debug", "info", "warn", "error", "critical"}


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _normalize_severity(value: str | None) -> str:
    raw = str(value or "").strip().lower()
    mapping = {
        "warning": "warn",
        "err": "error",
        "fatal": "critical",
    }
    normalized = mapping.get(raw, raw or "info")
    if normalized not in ALLOWED_SEVERITIES:
        return "info"
    return normalized


def _parse_ts(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _read_json(fs: WorkspaceFS, rel_path: str, default: Any) -> Any:
    try:
        raw = fs.read_text(rel_path)
    except Exception:
        return default
    try:
        parsed = json.loads(raw)
    except Exception:
        return default
    return parsed


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


def _append_jsonl(fs: WorkspaceFS, rel_path: str, row: dict[str, Any]) -> None:
    existing = ""
    try:
        existing = fs.read_text(rel_path)
    except Exception:
        existing = ""
    if existing and not existing.endswith("\n"):
        existing += "\n"
    fs.write_text(rel_path, existing + json.dumps(row, ensure_ascii=False) + "\n")


def _write_jsonl(fs: WorkspaceFS, rel_path: str, rows: list[dict[str, Any]]) -> None:
    content = ""
    if rows:
        content = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n"
    fs.write_text(rel_path, content)


def _sanitize(value: Any) -> Any:
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _sanitize(item) for key, item in value.items()}
    return value


def _default_config() -> dict[str, Any]:
    return {
        "enabled": False,
        "allowed_streams": list(DEFAULT_ALLOWED_STREAMS),
        "max_text_chars": 8000,
        "retention_max_events": DEFAULT_RETENTION_MAX_EVENTS,
        "retention_max_age_hours": DEFAULT_RETENTION_MAX_AGE_HOURS,
        "updated_at": utc_now_iso(),
    }


def _normalize_streams(streams: list[str] | None) -> list[str]:
    if streams is None:
        return list(DEFAULT_ALLOWED_STREAMS)
    cleaned = sorted({str(item).strip().lower() for item in streams if str(item).strip()})
    return cleaned if cleaned else list(DEFAULT_ALLOWED_STREAMS)


def _normalize_config(parsed: dict[str, Any] | None) -> dict[str, Any]:
    parsed = parsed if isinstance(parsed, dict) else {}
    enabled = bool(parsed.get("enabled", False))
    allowed_streams = _normalize_streams(
        parsed.get("allowed_streams") if isinstance(parsed.get("allowed_streams"), list) else None
    )
    max_text_chars = max(256, min(20000, _safe_int(parsed.get("max_text_chars", 8000), 8000)))
    retention_max_events = max(
        1,
        min(200000, _safe_int(parsed.get("retention_max_events", DEFAULT_RETENTION_MAX_EVENTS), DEFAULT_RETENTION_MAX_EVENTS)),
    )
    retention_max_age_hours = max(
        1,
        min(
            2160,
            _safe_int(
                parsed.get("retention_max_age_hours", DEFAULT_RETENTION_MAX_AGE_HOURS),
                DEFAULT_RETENTION_MAX_AGE_HOURS,
            ),
        ),
    )
    updated_at = parsed.get("updated_at")
    updated_at_str = str(updated_at).strip() if updated_at is not None else ""
    config = {
        "enabled": enabled,
        "allowed_streams": allowed_streams,
        "max_text_chars": max_text_chars,
        "retention_max_events": retention_max_events,
        "retention_max_age_hours": retention_max_age_hours,
        "updated_at": updated_at_str or utc_now_iso(),
    }
    return config


def _load_config(fs: WorkspaceFS, *, persist_missing: bool) -> dict[str, Any]:
    parsed = _read_json(fs, TELEMETRY_CONFIG_PATH, None)
    if not isinstance(parsed, dict):
        config = _default_config()
        if persist_missing:
            fs.write_text(TELEMETRY_CONFIG_PATH, json.dumps(config, ensure_ascii=False, indent=2))
        return config
    config = _normalize_config(parsed)
    if persist_missing and config != parsed:
        fs.write_text(TELEMETRY_CONFIG_PATH, json.dumps(config, ensure_ascii=False, indent=2))
    return config


def load_or_init_config(fs: WorkspaceFS) -> dict[str, Any]:
    return _load_config(fs, persist_missing=True)


def read_config(fs: WorkspaceFS) -> dict[str, Any]:
    return _load_config(fs, persist_missing=False)


def update_config(
    fs: WorkspaceFS,
    *,
    enabled: bool | None = None,
    allowed_streams: list[str] | None = None,
    max_text_chars: int | None = None,
    retention_max_events: int | None = None,
    retention_max_age_hours: int | None = None,
) -> dict[str, Any]:
    config = load_or_init_config(fs)
    if enabled is not None:
        config["enabled"] = bool(enabled)
    if allowed_streams is not None:
        config["allowed_streams"] = _normalize_streams(allowed_streams)
    if max_text_chars is not None:
        config["max_text_chars"] = max(256, min(20000, _safe_int(max_text_chars, 8000)))
    if retention_max_events is not None:
        config["retention_max_events"] = max(
            1,
            min(200000, _safe_int(retention_max_events, DEFAULT_RETENTION_MAX_EVENTS)),
        )
    if retention_max_age_hours is not None:
        config["retention_max_age_hours"] = max(
            1,
            min(2160, _safe_int(retention_max_age_hours, DEFAULT_RETENTION_MAX_AGE_HOURS)),
        )
    config["updated_at"] = utc_now_iso()
    fs.write_text(TELEMETRY_CONFIG_PATH, json.dumps(config, ensure_ascii=False, indent=2))
    _enforce_retention(fs, config=config)
    return config


def _validate_event_contract(event: dict[str, Any]) -> bool:
    required_str = ["id", "ts", "ingested_at", "run_id", "kind", "stream", "source", "severity", "text"]
    for key in required_str:
        value = event.get(key)
        if not isinstance(value, str) or not value.strip():
            return False
    if event.get("kind") != "telemetry.event":
        return False
    if str(event.get("severity", "")).strip().lower() not in ALLOWED_SEVERITIES:
        return False
    if not isinstance(event.get("fields"), dict):
        return False
    return True


def _enforce_retention(fs: WorkspaceFS, *, config: dict[str, Any]) -> dict[str, int]:
    events = _read_jsonl(fs, TELEMETRY_EVENTS_PATH)
    if not events:
        return {"dropped_by_age": 0, "dropped_by_limit": 0, "remaining": 0}

    max_events = max(1, min(200000, _safe_int(config.get("retention_max_events"), DEFAULT_RETENTION_MAX_EVENTS)))
    max_age_hours = max(
        1,
        min(2160, _safe_int(config.get("retention_max_age_hours"), DEFAULT_RETENTION_MAX_AGE_HOURS)),
    )
    horizon = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)

    kept: list[dict[str, Any]] = []
    dropped_by_age = 0
    for event in events:
        ts = _parse_ts(str(event.get("ts", "")).strip() or None)
        if ts is not None and ts < horizon:
            dropped_by_age += 1
            continue
        kept.append(event)

    dropped_by_limit = 0
    if len(kept) > max_events:
        dropped_by_limit = len(kept) - max_events
        kept = kept[-max_events:]

    if dropped_by_age > 0 or dropped_by_limit > 0:
        _write_jsonl(fs, TELEMETRY_EVENTS_PATH, kept)

    return {
        "dropped_by_age": dropped_by_age,
        "dropped_by_limit": dropped_by_limit,
        "remaining": len(kept),
    }


def ingest_event(
    fs: WorkspaceFS,
    *,
    run_id: str,
    stream: str,
    source: str | None = None,
    severity: str = "info",
    text: str | None = None,
    fields: dict[str, Any] | None = None,
    ts: str | None = None,
) -> dict[str, Any]:
    config = load_or_init_config(fs)
    normalized_stream = str(stream).strip().lower()
    if not config.get("enabled", False):
        return {"status": "ignored", "reason": "telemetry disabled", "config": config}
    if normalized_stream not in set(config.get("allowed_streams", [])):
        return {"status": "ignored", "reason": f"stream not allowed: {normalized_stream}", "config": config}
    max_text_chars = max(256, min(20000, _safe_int(config.get("max_text_chars", 8000), 8000)))
    sanitized_text = redact(str(text or ""))[:max_text_chars]
    sanitized_fields = _sanitize(fields or {})
    event_ts = ts if _parse_ts(ts) is not None else utc_now_iso()
    event = {
        "id": str(uuid4()),
        "ts": event_ts,
        "ingested_at": utc_now_iso(),
        "run_id": run_id,
        "kind": "telemetry.event",
        "stream": normalized_stream,
        "source": str(source or "unknown"),
        "severity": _normalize_severity(severity),
        "text": sanitized_text,
        "fields": sanitized_fields,
    }
    if not _validate_event_contract(event):
        return {"status": "error", "reason": "telemetry event failed schema contract", "event": event}
    _append_jsonl(fs, TELEMETRY_EVENTS_PATH, event)
    retention = _enforce_retention(fs, config=config)
    return {"status": "ok", "event": event, "config": config, "retention": retention}


def status(fs: WorkspaceFS, *, horizon_hours: int = 24) -> dict[str, Any]:
    config = read_config(fs)
    events = _read_jsonl(fs, TELEMETRY_EVENTS_PATH)
    now = datetime.now(timezone.utc)
    horizon = now - timedelta(hours=max(1, min(168, _safe_int(horizon_hours, 24))))
    in_horizon: list[dict[str, Any]] = []
    for event in events:
        ts = _parse_ts(str(event.get("ts", "")) or None)
        if ts is None or ts >= horizon:
            in_horizon.append(event)
    active_streams = sorted(
        {
            str(item.get("stream", "")).strip().lower()
            for item in in_horizon
            if str(item.get("stream", "")).strip()
        }
    )
    warn_count = 0
    error_count = 0
    critical_count = 0
    for item in in_horizon:
        severity = _normalize_severity(str(item.get("severity", "info")))
        if severity == "warn":
            warn_count += 1
        elif severity == "error":
            error_count += 1
        elif severity == "critical":
            critical_count += 1
    last_event = events[-1] if events else None
    return {
        "enabled": bool(config.get("enabled", False)),
        "allowed_streams": list(config.get("allowed_streams", [])),
        "max_text_chars": _safe_int(config.get("max_text_chars", 8000), 8000),
        "retention_max_events": _safe_int(config.get("retention_max_events"), DEFAULT_RETENTION_MAX_EVENTS),
        "retention_max_age_hours": _safe_int(
            config.get("retention_max_age_hours"),
            DEFAULT_RETENTION_MAX_AGE_HOURS,
        ),
        "event_count_total": len(events),
        "event_count_horizon": len(in_horizon),
        "active_streams_horizon": active_streams,
        "warn_count_horizon": warn_count,
        "error_count_horizon": error_count,
        "critical_count_horizon": critical_count,
        "last_event_ts": last_event.get("ts") if isinstance(last_event, dict) else None,
        "last_event_stream": last_event.get("stream") if isinstance(last_event, dict) else None,
        "updated_at": config.get("updated_at"),
    }
