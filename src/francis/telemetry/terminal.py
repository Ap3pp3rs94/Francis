from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

from francis.kernel.paths import data_dir
from francis.telemetry.audit import record as audit_record
from francis.telemetry.status import STAGE7_TELEMETRY_STAGE, redact_telemetry_value

TERMINAL_TELEMETRY_KIND = "francis.stage7.telemetry.terminal_event"
TERMINAL_SCOPE_KIND = "francis.stage7.telemetry.terminal_scope"
TERMINAL_EVENTS_KIND = "francis.stage7.telemetry.terminal_events"
TERMINAL_WRITE_SCOPE = "telemetry.terminal.write"

_MAX_TEXT_LENGTH = 2_000
_MAX_TAGS = 16
_MAX_LIMIT = 100


def terminal_scope_snapshot(*, actor: str = "", permission: dict[str, Any] | None = None) -> dict[str, Any]:
    allowed = bool(permission and permission.get("allowed") is True)
    status = "write_scope_ready" if allowed else "write_scope_required"
    event_count = terminal_event_count()

    return {
        "ok": True,
        "kind": TERMINAL_SCOPE_KIND,
        "stage": STAGE7_TELEMETRY_STAGE,
        "source_id": "terminal",
        "status": status,
        "active": event_count > 0,
        "actor": _redact_text(actor),
        "required_scope": TERMINAL_WRITE_SCOPE,
        "write_route": "/telemetry/terminal/events",
        "read_route": "/telemetry/terminal/events",
        "capture_mode": "explicit_command_outcome_report",
        "hidden_sensing": False,
        "visible_indicator": True,
        "redact_before_storage": True,
        "stores_raw_secret_values": False,
        "event_count": event_count,
        "governance": {
            "permission_gate": "api_actor_scope",
            "permission_allowed": allowed,
            "telemetry_is_untrusted_input": True,
            "grants_execution_authority": False,
            "grants_memory_write_authority": False,
            "captures_terminal_streams": False,
        },
        "permission": permission or {"allowed": False, "reason": "actor_not_evaluated", "evidence": {}},
        "next_smallest_truthful_gap": "stage7_terminal_connector_event_ingest",
    }


def record_terminal_event(
    *,
    actor: Any,
    reason: Any = "",
    command: Any = "",
    cwd: Any = "",
    shell: Any = "",
    exit_code: Any = None,
    duration_ms: Any = None,
    started_ts: Any = None,
    completed_ts: Any = None,
    operation_id: Any = "",
    approval_id: Any = "",
    trace_id: Any = "",
    run_id: Any = "",
    artifact_dir: Any = "",
    tags: Any = None,
    meta: Any = None,
) -> dict[str, Any]:
    now = _now_s()
    event_id = f"tel_terminal_{uuid.uuid4().hex[:12]}"
    payload = {
        "ok": True,
        "kind": TERMINAL_TELEMETRY_KIND,
        "event_id": event_id,
        "source_id": "terminal",
        "stage": STAGE7_TELEMETRY_STAGE,
        "capture_mode": "explicit_command_outcome_report",
        "hidden_sensing": False,
        "visible_indicator": True,
        "actor": _redact_text(actor),
        "reason": _redact_text(reason),
        "command": _redact_text(command),
        "cwd": _redact_text(cwd),
        "shell": _redact_text(shell),
        "exit_code": _safe_int(exit_code),
        "duration_ms": _safe_int(duration_ms),
        "started_ts": _normalize_ts(started_ts, fallback=now),
        "completed_ts": _normalize_ts(completed_ts, fallback=now),
        "recorded_ts": now,
        "operation_id": _redact_text(operation_id),
        "approval_id": _redact_text(approval_id),
        "trace_id": _redact_text(trace_id),
        "run_id": _redact_text(run_id),
        "artifact_dir": _redact_text(artifact_dir),
        "tags": _safe_tags(tags),
        "meta": _redact_jsonable(meta or {}),
        "governance": {
            "permission_scope": TERMINAL_WRITE_SCOPE,
            "redacted_before_storage": True,
            "telemetry_is_untrusted_input": True,
            "stores_stdout_stderr": False,
            "grants_execution_authority": False,
            "grants_memory_write_authority": False,
        },
    }
    _append_line(_events_path(), payload)
    audit_record(
        "telemetry.terminal.event_recorded",
        actor=payload["actor"],
        reason=payload["reason"],
        terminal_event_id=event_id,
        exit_code=payload["exit_code"],
        command=payload["command"],
        cwd=payload["cwd"],
    )
    return payload


def terminal_events_snapshot(*, limit: int = 20) -> dict[str, Any]:
    safe_limit = _safe_limit(limit)
    items = read_terminal_events(limit=safe_limit)
    return {
        "ok": True,
        "kind": TERMINAL_EVENTS_KIND,
        "stage": STAGE7_TELEMETRY_STAGE,
        "source_id": "terminal",
        "items": items,
        "count": len(items),
        "total": terminal_event_count(),
        "limit": safe_limit,
        "redacted": True,
        "hidden_sensing": False,
    }


def terminal_source_snapshot() -> dict[str, Any]:
    count = terminal_event_count()
    latest = read_terminal_events(limit=1)
    latest_event = latest[-1] if latest else None
    active = count > 0
    return {
        "status": "explicit_events_recorded" if active else "write_scope_required",
        "active": active,
        "blocked_by": [] if active else ["operator_scope_not_granted"],
        "signals": ["command_outcome"] if active else [],
        "retention": {
            "status": "bounded_redacted_events" if active else "none",
            "stores_raw_events": False,
            "event_count": count,
        },
        "scope": {
            "status": "write_scope_required",
            "allowed_paths": [],
            "allowed_processes": [],
            "denied_by_default": True,
        },
        "latest_event": _terminal_event_summary(latest_event) if latest_event else None,
        "routes": {
            "scope": "/telemetry/terminal/scope",
            "events": "/telemetry/terminal/events",
            "record": "/telemetry/terminal/events",
        },
    }


def read_terminal_events(*, limit: int = 20) -> list[dict[str, Any]]:
    path = _events_path()
    if not path.exists():
        return []
    items: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except Exception:
            continue
        if isinstance(payload, dict):
            items.append(payload)
    safe_limit = _safe_limit(limit)
    return items[-safe_limit:]


def terminal_event_count() -> int:
    path = _events_path()
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip())


def _events_path() -> Path:
    return data_dir() / "logs" / "telemetry" / "terminal_events.jsonl"


def _append_line(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str) + "\n")


def _redact_text(value: Any) -> str:
    redacted = redact_telemetry_value(_safe_str(value))
    return _safe_str(redacted)[:_MAX_TEXT_LENGTH]


def _redact_jsonable(value: Any) -> Any:
    return redact_telemetry_value(_coerce_jsonable(value))


def _coerce_jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _coerce_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_coerce_jsonable(item) for item in value]
    return _safe_str(value)


def _terminal_event_summary(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "event_id": event.get("event_id"),
        "recorded_ts": event.get("recorded_ts"),
        "exit_code": event.get("exit_code"),
        "cwd": event.get("cwd"),
        "command": event.get("command"),
        "operation_id": event.get("operation_id"),
        "approval_id": event.get("approval_id"),
        "trace_id": event.get("trace_id"),
        "run_id": event.get("run_id"),
        "artifact_dir": event.get("artifact_dir"),
    }


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""


def _safe_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except Exception:
        return None


def _normalize_ts(value: Any, *, fallback: int) -> int:
    if value is None or value == "":
        return fallback
    try:
        ts = int(float(value))
    except Exception:
        return fallback
    if ts > 10_000_000_000:
        return int(ts / 1000)
    return ts


def _safe_tags(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    tags: list[str] = []
    for item in value:
        text = _redact_text(item).strip()
        if text and text not in tags:
            tags.append(text)
        if len(tags) >= _MAX_TAGS:
            break
    return tags


def _safe_limit(value: int) -> int:
    try:
        limit = int(value)
    except Exception:
        return 20
    if limit <= 0:
        return 20
    return min(limit, _MAX_LIMIT)


def _now_s() -> int:
    return int(time.time())
