from __future__ import annotations

from typing import Any

from francis.telemetry.status import STAGE7_TELEMETRY_STAGE, redact_telemetry_value, telemetry_status_snapshot

TELEMETRY_CONTEXT_KIND = "francis.stage7.telemetry.context"
_MAX_CONTEXT_ITEMS = 12
_MAX_PATHS = 5


def telemetry_context_snapshot(*, surface: Any = "assist") -> dict[str, Any]:
    status = telemetry_status_snapshot()
    raw_sources = status.get("sources")
    sources: list[Any] = raw_sources if isinstance(raw_sources, list) else []
    context_items = _context_items(sources)
    prompt_lines = _prompt_lines(context_items)

    return {
        "ok": True,
        "kind": TELEMETRY_CONTEXT_KIND,
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
        "next_smallest_truthful_gap": "stage7_context_awareness_action_quality_feedback",
    }


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


def _safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_int(value: Any, fallback: int) -> int:
    try:
        return int(value)
    except Exception:
        return fallback


def _redact_text(value: Any) -> str:
    redacted = redact_telemetry_value(_safe_str(value))
    return _safe_str(redacted)


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""
