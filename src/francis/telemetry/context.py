from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

from francis.kernel.paths import data_dir
from francis.telemetry.audit import record as audit_record
from francis.telemetry.status import STAGE7_TELEMETRY_STAGE, redact_telemetry_value, telemetry_status_snapshot

TELEMETRY_CONTEXT_KIND = "francis.stage7.telemetry.context"
TELEMETRY_CONTEXT_FEEDBACK_KIND = "francis.stage7.telemetry.context_feedback"
TELEMETRY_CONTEXT_FEEDBACK_EVENTS_KIND = "francis.stage7.telemetry.context_feedback_events"
TELEMETRY_CONTEXT_FEEDBACK_WRITE_SCOPE = "telemetry.context.feedback.write"
_MAX_CONTEXT_ITEMS = 12
_MAX_PATHS = 5
_MAX_LIMIT = 100
_MAX_TEXT_LENGTH = 2_000
_MAX_TAGS = 16


def telemetry_context_snapshot(*, surface: Any = "assist") -> dict[str, Any]:
    status = telemetry_status_snapshot()
    raw_sources = status.get("sources")
    sources: list[Any] = raw_sources if isinstance(raw_sources, list) else []
    context_items = _context_items(sources)
    prompt_lines = _prompt_lines(context_items)
    feedback_count = telemetry_context_feedback_count()

    return {
        "ok": True,
        "kind": TELEMETRY_CONTEXT_KIND,
        "context_id": f"tel_ctx_{uuid.uuid4().hex[:12]}",
        "stage": STAGE7_TELEMETRY_STAGE,
        "surface": _redact_text(surface),
        "status": "available" if context_items else "empty",
        "source_status": status.get("status", "unknown"),
        "claim": status.get("claim", ""),
        "active": bool(status.get("active")),
        "source_total": _safe_int(status.get("source_total"), 0),
        "active_source_total": _safe_int(status.get("active_source_total"), 0),
        "event_count": _safe_int(_safe_dict(status.get("retention")).get("event_count"), 0),
        "context_items": context_items,
        "prompt_lines": prompt_lines,
        "visible_indicator": True,
        "hidden_sensing": False,
        "redacted": True,
        "stores_raw_events": False,
        "feedback": {
            "status": "available",
            "event_count": feedback_count,
            "write_route": "/telemetry/context/feedback",
            "read_route": "/telemetry/context/feedback",
            "required_scope": TELEMETRY_CONTEXT_FEEDBACK_WRITE_SCOPE,
        },
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "governance": {
            "read_only": True,
            "on_request_only": True,
            "source_status_route": "/telemetry/status",
            "telemetry_is_untrusted_input": True,
            "requires_visible_indicator": True,
            "hidden_sensing": False,
            "does_not_expand_collection_scope": True,
            "grants_execution_authority": False,
            "grants_memory_write_authority": False,
        },
        "next_smallest_truthful_gap": "stage7_context_feedback_quality_review",
    }


def record_telemetry_context_feedback(
    *,
    actor: Any,
    reason: Any = "",
    context_id: Any = "",
    surface: Any = "",
    rating: Any = "",
    message_id: Any = "",
    reply_mode: Any = "",
    notes: Any = "",
    source_ids: Any = None,
    tags: Any = None,
    meta: Any = None,
) -> dict[str, Any]:
    feedback_id = f"tel_ctx_feedback_{uuid.uuid4().hex[:12]}"
    payload = {
        "ok": True,
        "kind": TELEMETRY_CONTEXT_FEEDBACK_KIND,
        "feedback_id": feedback_id,
        "stage": STAGE7_TELEMETRY_STAGE,
        "source_id": "telemetry_context",
        "capture_mode": "explicit_operator_feedback",
        "hidden_sensing": False,
        "visible_indicator": True,
        "actor": _redact_text(actor),
        "reason": _redact_text(reason),
        "context_id": _redact_text(context_id),
        "surface": _redact_text(surface),
        "rating": _safe_rating(rating),
        "message_id": _redact_text(message_id),
        "reply_mode": _redact_text(reply_mode),
        "notes": _redact_text(notes)[:_MAX_TEXT_LENGTH],
        "source_ids": _safe_text_list(source_ids, limit=_MAX_CONTEXT_ITEMS),
        "tags": _safe_text_list(tags, limit=_MAX_TAGS),
        "meta": _feedback_meta(meta or {}),
        "recorded_ts": _now_s(),
        "governance": {
            "permission_scope": TELEMETRY_CONTEXT_FEEDBACK_WRITE_SCOPE,
            "redacted_before_storage": True,
            "telemetry_is_untrusted_input": True,
            "stores_prompt_body": False,
            "stores_model_response": False,
            "trains_model": False,
            "grants_execution_authority": False,
            "grants_memory_write_authority": False,
        },
    }
    _append_line(_feedback_path(), payload)
    audit_record(
        "telemetry.context.feedback_recorded",
        actor=payload["actor"],
        reason=payload["reason"],
        feedback_id=feedback_id,
        context_id=payload["context_id"],
        rating=payload["rating"],
        surface=payload["surface"],
    )
    return payload


def telemetry_context_feedback_snapshot(*, limit: int = 20) -> dict[str, Any]:
    safe_limit = _safe_limit(limit)
    items = read_telemetry_context_feedback(limit=safe_limit)
    return {
        "ok": True,
        "kind": TELEMETRY_CONTEXT_FEEDBACK_EVENTS_KIND,
        "stage": STAGE7_TELEMETRY_STAGE,
        "source_id": "telemetry_context",
        "items": items,
        "count": len(items),
        "total": telemetry_context_feedback_count(),
        "limit": safe_limit,
        "redacted": True,
        "hidden_sensing": False,
        "stores_prompt_body": False,
        "stores_model_response": False,
        "trains_model": False,
        "grants_execution_authority": False,
        "grants_memory_write_authority": False,
        "governance": {
            "capture_mode": "explicit_operator_feedback",
            "permission_scope": TELEMETRY_CONTEXT_FEEDBACK_WRITE_SCOPE,
            "redacted_before_storage": True,
            "telemetry_is_untrusted_input": True,
            "stores_prompt_body": False,
            "stores_model_response": False,
            "trains_model": False,
            "grants_execution_authority": False,
            "grants_memory_write_authority": False,
        },
    }


def read_telemetry_context_feedback(*, limit: int = 20) -> list[dict[str, Any]]:
    path = _feedback_path()
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


def telemetry_context_feedback_count() -> int:
    path = _feedback_path()
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip())


def telemetry_context_prompt_lines(context: dict[str, Any] | None) -> list[str]:
    if not isinstance(context, dict):
        return []
    lines = context.get("prompt_lines")
    if not isinstance(lines, list):
        return []
    return [_redact_text(line).strip() for line in lines if _redact_text(line).strip()][:_MAX_CONTEXT_ITEMS]


def _context_items(sources: list[Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for source in sources:
        if not isinstance(source, dict) or source.get("active") is not True:
            continue
        source_id = _redact_text(source.get("id"))
        if source_id == "terminal":
            item = _terminal_item(source)
        elif source_id == "git":
            item = _git_item(source)
        elif source_id == "ide_diagnostics":
            item = _ide_diagnostic_item(source)
        else:
            item = _generic_source_item(source)
        if item:
            items.append(item)
    return items[:_MAX_CONTEXT_ITEMS]


def _terminal_item(source: dict[str, Any]) -> dict[str, Any]:
    latest = _safe_dict(source.get("latest_event"))
    event_id = _redact_text(latest.get("event_id"))
    if not event_id:
        return _generic_source_item(source)
    item: dict[str, Any] = {
        "source_id": "terminal",
        "status": _redact_text(source.get("status")),
        "summary": _redact_text(f"latest terminal event {event_id}"),
        "event_id": event_id,
        "exit_code": latest.get("exit_code"),
        "operation_id": _redact_text(latest.get("operation_id")),
        "artifact_dir": _redact_text(latest.get("artifact_dir")),
    }
    command = _redact_text(latest.get("command"))
    if command:
        item["command"] = command
    return item


def _git_item(source: dict[str, Any]) -> dict[str, Any]:
    snapshot = _safe_dict(source.get("latest_snapshot"))
    branch = _redact_text(snapshot.get("branch"))
    changed_count = _safe_int(snapshot.get("changed_count"), 0)
    changed_paths = _changed_paths(snapshot.get("changed_paths"))
    return {
        "source_id": "git",
        "status": _redact_text(source.get("status")),
        "summary": _redact_text(f"git branch {branch or 'unknown'}, changed {changed_count}"),
        "branch": branch,
        "head": _redact_text(snapshot.get("head")),
        "upstream": _redact_text(snapshot.get("upstream")),
        "dirty": bool(snapshot.get("dirty")),
        "changed_count": changed_count,
        "changed_paths": changed_paths,
    }


def _ide_diagnostic_item(source: dict[str, Any]) -> dict[str, Any]:
    latest = _safe_dict(source.get("latest_diagnostic"))
    event_id = _redact_text(latest.get("event_id"))
    if not event_id:
        return _generic_source_item(source)
    diagnostic_count = _safe_int(latest.get("diagnostic_count"), 0)
    severity = _redact_text(latest.get("highest_severity")) or "unknown"
    file_path = _redact_text(latest.get("file"))
    return {
        "source_id": "ide_diagnostics",
        "status": _redact_text(source.get("status")),
        "summary": _redact_text(f"IDE diagnostics {severity}, count {diagnostic_count}"),
        "event_id": event_id,
        "file": file_path,
        "diagnostic_count": diagnostic_count,
        "highest_severity": severity,
        "operation_id": _redact_text(latest.get("operation_id")),
    }


def _generic_source_item(source: dict[str, Any]) -> dict[str, Any]:
    source_id = _redact_text(source.get("id"))
    status = _redact_text(source.get("status"))
    if not source_id:
        return {}
    return {
        "source_id": source_id,
        "status": status,
        "summary": _redact_text(f"{source_id} status {status or 'active'}"),
    }


def _prompt_lines(items: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for item in items:
        source_id = _redact_text(item.get("source_id"))
        summary = _redact_text(item.get("summary"))
        if not source_id or not summary:
            continue
        details: list[str] = []
        if source_id == "git":
            if item.get("dirty") is True:
                details.append("dirty")
            changed_count = _safe_int(item.get("changed_count"), 0)
            if changed_count:
                details.append(f"{changed_count} changed")
            paths = item.get("changed_paths") if isinstance(item.get("changed_paths"), list) else []
            if paths:
                path_text = ", ".join(_redact_text(_safe_dict(path).get("path")) for path in paths[:3])
                if path_text:
                    details.append(f"paths {path_text}")
        elif source_id == "terminal":
            exit_code = item.get("exit_code")
            if exit_code is not None:
                details.append(f"exit {exit_code}")
            command = _redact_text(item.get("command"))
            if command:
                details.append(f"command {command}")
        elif source_id == "ide_diagnostics":
            file_path = _redact_text(item.get("file"))
            if file_path:
                details.append(f"file {file_path}")
            severity = _redact_text(item.get("highest_severity"))
            if severity:
                details.append(f"severity {severity}")
        suffix = f"; {'; '.join(details)}" if details else ""
        lines.append(_redact_text(f"{source_id}: {summary}{suffix}"))
    return lines[:_MAX_CONTEXT_ITEMS]


def _changed_paths(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    paths: list[dict[str, str]] = []
    for item in value[:_MAX_PATHS]:
        record = _safe_dict(item)
        path = _redact_text(record.get("path")).strip()
        if not path:
            continue
        paths.append({"status": _redact_text(record.get("status")).strip(), "path": path})
    return paths


def _feedback_path() -> Path:
    return data_dir() / "logs" / "telemetry" / "context_feedback.jsonl"


def _append_line(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str) + "\n")


def _redact_jsonable(value: Any) -> Any:
    return redact_telemetry_value(_coerce_jsonable(value))


def _feedback_meta(value: Any) -> dict[str, Any]:
    redacted = _redact_jsonable(value)
    if not isinstance(redacted, dict):
        return {}
    blocked_keys = {
        "message",
        "messages",
        "model_response",
        "prompt",
        "prompt_body",
        "response",
        "response_body",
    }
    return {key: item for key, item in redacted.items() if str(key).strip().lower() not in blocked_keys}


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


def _safe_text_list(value: Any, *, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for item in value[:limit]:
        text = _redact_text(item).strip()
        if text:
            items.append(text[:_MAX_TEXT_LENGTH])
    return items


def _safe_rating(value: Any) -> str:
    text = _redact_text(value).strip().lower()
    if text in {"useful", "not_useful", "neutral"}:
        return text
    return "neutral"


def _safe_limit(value: int) -> int:
    try:
        limit = int(value)
    except Exception:
        return 20
    if limit <= 0:
        return 20
    return min(limit, _MAX_LIMIT)


def _safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_int(value: Any, fallback: int) -> int:
    try:
        return int(value)
    except Exception:
        return fallback


def _redact_text(value: Any) -> str:
    redacted = redact_telemetry_value(_safe_str(value))
    return _safe_str(redacted)[:_MAX_TEXT_LENGTH]


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""


def _now_s() -> int:
    return int(time.time())
