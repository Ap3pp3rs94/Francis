from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

from francis.kernel.paths import data_dir
from francis.telemetry.audit import record as audit_record
from francis.telemetry.status import STAGE7_TELEMETRY_STAGE, redact_telemetry_value

IDE_DIAGNOSTIC_KIND = "francis.stage7.telemetry.ide_diagnostic_event"
IDE_DIAGNOSTIC_EVENTS_KIND = "francis.stage7.telemetry.ide_diagnostic_events"
IDE_DIAGNOSTIC_SCOPE_KIND = "francis.stage7.telemetry.ide_diagnostic_scope"
IDE_DIAGNOSTIC_WRITE_SCOPE = "telemetry.ide_diagnostics.write"

_MAX_TEXT_LENGTH = 2_000
_MAX_DIAGNOSTICS = 50
_MAX_TAGS = 16
_MAX_LIMIT = 100


def ide_diagnostics_scope_snapshot(*, actor: str = "", permission: dict[str, Any] | None = None) -> dict[str, Any]:
    allowed = bool(permission and permission.get("allowed") is True)
    status = "write_scope_ready" if allowed else "write_scope_required"
    event_count = ide_diagnostics_event_count()

    return {
        "ok": True,
        "kind": IDE_DIAGNOSTIC_SCOPE_KIND,
        "stage": STAGE7_TELEMETRY_STAGE,
        "source_id": "ide_diagnostics",
        "status": status,
        "active": event_count > 0,
        "actor": _redact_text(actor),
        "required_scope": IDE_DIAGNOSTIC_WRITE_SCOPE,
        "write_route": "/telemetry/ide-diagnostics/events",
        "read_route": "/telemetry/ide-diagnostics/events",
        "capture_mode": "explicit_ide_diagnostic_report",
        "hidden_sensing": False,
        "visible_indicator": True,
        "redact_before_storage": True,
        "stores_raw_secret_values": False,
        "stores_file_contents": False,
        "event_count": event_count,
        "governance": {
            "permission_gate": "api_actor_scope",
            "permission_allowed": allowed,
            "telemetry_is_untrusted_input": True,
            "grants_execution_authority": False,
            "grants_memory_write_authority": False,
            "captures_file_contents": False,
        },
        "permission": permission or {"allowed": False, "reason": "actor_not_evaluated", "evidence": {}},
        "next_smallest_truthful_gap": "stage7_ide_diagnostics_event_ingest",
    }


def record_ide_diagnostic_event(
    *,
    actor: Any,
    reason: Any = "",
    source: Any = "",
    workspace: Any = "",
    file: Any = "",
    diagnostics: Any = None,
    operation_id: Any = "",
    approval_id: Any = "",
    trace_id: Any = "",
    run_id: Any = "",
    tags: Any = None,
    meta: Any = None,
) -> dict[str, Any]:
    now = _now_s()
    event_id = f"tel_ide_{uuid.uuid4().hex[:12]}"
    normalized_diagnostics = _safe_diagnostics(diagnostics)
    payload = {
        "ok": True,
        "kind": IDE_DIAGNOSTIC_KIND,
        "event_id": event_id,
        "source_id": "ide_diagnostics",
        "stage": STAGE7_TELEMETRY_STAGE,
        "capture_mode": "explicit_ide_diagnostic_report",
        "hidden_sensing": False,
        "visible_indicator": True,
        "actor": _redact_text(actor),
        "reason": _redact_text(reason),
        "source": _redact_text(source),
        "workspace": _redact_text(workspace),
        "file": _redact_text(file),
        "diagnostic_count": len(normalized_diagnostics),
        "diagnostics": normalized_diagnostics,
        "highest_severity": _highest_severity(normalized_diagnostics),
        "recorded_ts": now,
        "operation_id": _redact_text(operation_id),
        "approval_id": _redact_text(approval_id),
        "trace_id": _redact_text(trace_id),
        "run_id": _redact_text(run_id),
        "tags": _safe_tags(tags),
        "meta": _redact_jsonable(meta or {}),
        "governance": {
            "permission_scope": IDE_DIAGNOSTIC_WRITE_SCOPE,
            "redacted_before_storage": True,
            "telemetry_is_untrusted_input": True,
            "stores_file_contents": False,
            "stores_raw_secret_values": False,
            "grants_execution_authority": False,
            "grants_memory_write_authority": False,
        },
    }
    _append_line(_events_path(), payload)
    audit_record(
        "telemetry.ide_diagnostics.event_recorded",
        actor=payload["actor"],
        reason=payload["reason"],
        ide_diagnostic_event_id=event_id,
        file=payload["file"],
        diagnostic_count=payload["diagnostic_count"],
        highest_severity=payload["highest_severity"],
    )
    return payload


def ide_diagnostics_events_snapshot(*, limit: int = 20) -> dict[str, Any]:
    safe_limit = _safe_limit(limit)
    items = read_ide_diagnostics_events(limit=safe_limit)
    return {
        "ok": True,
        "kind": IDE_DIAGNOSTIC_EVENTS_KIND,
        "stage": STAGE7_TELEMETRY_STAGE,
        "source_id": "ide_diagnostics",
        "items": items,
        "count": len(items),
        "total": ide_diagnostics_event_count(),
        "limit": safe_limit,
        "redacted": True,
        "hidden_sensing": False,
        "stores_file_contents": False,
    }


def ide_diagnostics_source_snapshot() -> dict[str, Any]:
    count = ide_diagnostics_event_count()
    latest = read_ide_diagnostics_events(limit=1)
    latest_event = latest[-1] if latest else None
    active = count > 0
    return {
        "status": "explicit_diagnostics_recorded" if active else "write_scope_required",
        "active": active,
        "blocked_by": [] if active else ["operator_scope_not_granted"],
        "signals": ["diagnostic_summary"] if active else [],
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
        "latest_diagnostic": _diagnostic_event_summary(latest_event) if latest_event else None,
        "routes": {
            "scope": "/telemetry/ide-diagnostics/scope",
            "events": "/telemetry/ide-diagnostics/events",
            "record": "/telemetry/ide-diagnostics/events",
        },
    }


def read_ide_diagnostics_events(*, limit: int = 20) -> list[dict[str, Any]]:
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


def ide_diagnostics_event_count() -> int:
    path = _events_path()
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip())


def _events_path() -> Path:
    return data_dir() / "logs" / "telemetry" / "ide_diagnostics.jsonl"


def _append_line(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str) + "\n")


def _safe_diagnostics(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    diagnostics: list[dict[str, Any]] = []
    for item in value[:_MAX_DIAGNOSTICS]:
        if not isinstance(item, dict):
            continue
        diagnostics.append(
            {
                "severity": _redact_text(item.get("severity") or "unknown"),
                "code": _redact_text(item.get("code") or ""),
                "message": _redact_text(item.get("message") or "")[:_MAX_TEXT_LENGTH],
                "range": _safe_range(item.get("range")),
            }
        )
    return diagnostics


def _safe_range(value: Any) -> dict[str, int | None]:
    if not isinstance(value, dict):
        return {"start_line": None, "start_character": None, "end_line": None, "end_character": None}
    return {
        "start_line": _safe_int(value.get("start_line") or value.get("line")),
        "start_character": _safe_int(value.get("start_character") or value.get("character")),
        "end_line": _safe_int(value.get("end_line")),
        "end_character": _safe_int(value.get("end_character")),
    }


def _highest_severity(diagnostics: list[dict[str, Any]]) -> str:
    order = {"error": 0, "warning": 1, "info": 2, "hint": 3, "unknown": 4}
    highest = "unknown"
    highest_rank = order[highest]
    for diagnostic in diagnostics:
        severity = _safe_str(diagnostic.get("severity")).strip().lower() or "unknown"
        rank = order.get(severity, order["unknown"])
        if rank < highest_rank:
            highest = severity
            highest_rank = rank
    return highest


def _diagnostic_event_summary(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "event_id": event.get("event_id"),
        "recorded_ts": event.get("recorded_ts"),
        "source": event.get("source"),
        "workspace": event.get("workspace"),
        "file": event.get("file"),
        "diagnostic_count": event.get("diagnostic_count"),
        "highest_severity": event.get("highest_severity"),
        "operation_id": event.get("operation_id"),
        "approval_id": event.get("approval_id"),
        "trace_id": event.get("trace_id"),
        "run_id": event.get("run_id"),
    }


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


def _safe_tags(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    tags: list[str] = []
    for item in value[:_MAX_TAGS]:
        text = _redact_text(item).strip()
        if text:
            tags.append(text)
    return tags


def _safe_limit(value: int) -> int:
    try:
        limit = int(value)
    except Exception:
        return 20
    if limit <= 0:
        return 20
    return min(limit, _MAX_LIMIT)


def _safe_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except Exception:
        return None


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""


def _now_s() -> int:
    return int(time.time())
