from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Query
from fastapi.responses import Response

from francis.chat.continuity.ledger import tail as continuity_tail
from francis.kernel.paths import data_dir

router = APIRouter()
_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:-]{1,127}$")


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""


def _now_s() -> int:
    return int(time.time())


def _normalize_ts(value: Any) -> int:
    if isinstance(value, (int, float)):
        ts = int(value)
    else:
        text = _safe_str(value).strip()
        if not text:
            return _now_s()
        try:
            ts = int(float(text))
        except Exception:
            return _now_s()
    if ts > 10_000_000_000:
        return int(ts / 1000)
    return ts


def _slug(value: str) -> str:
    out = []
    last_sep = False
    for ch in value.strip().lower():
        if ch.isalnum():
            out.append(ch)
            last_sep = False
            continue
        if ch in {" ", "-", "_", ".", ":"} and not last_sep:
            out.append("-")
            last_sep = True
    slug = "".join(out).strip("-")
    return slug[:64] or "item"


def _new_id(prefix: str, seed: str) -> str:
    return f"{prefix}_{_slug(seed)}_{uuid.uuid4().hex[:8]}"


def _validate_id(value: str, field: str = "id") -> str:
    text = value.strip()
    if not text:
        raise ValueError(f"{field} is required")
    if not _ID_RE.match(text):
        raise ValueError(f"invalid {field}")
    return text


def _parse_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        candidates = [part.strip() for part in value.split(",")]
    elif isinstance(value, (list, tuple, set)):
        candidates = []
        for item in value:
            if isinstance(item, str):
                candidates.extend([part.strip() for part in item.split(",")])
            else:
                candidates.append(_safe_str(item).strip())
    else:
        return []

    out: list[str] = []
    for candidate in candidates:
        if candidate and candidate not in out:
            out.append(candidate)
    return out


def _meta(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _path() -> Path:
    return data_dir() / "memory" / "timeline" / "_events.json"


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    os.replace(tmp, path)


def _default_registry() -> dict[str, Any]:
    return {"version": 1, "updated_at": _now_s(), "events": []}


def _normalize_artifact(raw: dict[str, Any]) -> dict[str, Any]:
    artifact_id = _safe_str(raw.get("id")).strip() or _new_id("art", _safe_str(raw.get("kind") or raw.get("path") or "artifact").strip() or "artifact")
    return {
        "id": artifact_id,
        "kind": _safe_str(raw.get("kind")).strip(),
        "url": _safe_str(raw.get("url")).strip(),
        "path": _safe_str(raw.get("path")).strip(),
        "content_type": _safe_str(raw.get("content_type") or raw.get("contentType")).strip(),
        "size_bytes": int(raw.get("size_bytes") or raw.get("sizeBytes") or 0),
        "sha256": _safe_str(raw.get("sha256")).strip(),
        "meta": _meta(raw.get("meta")),
    }


def _normalize_event(event_id: str, raw: dict[str, Any]) -> dict[str, Any]:
    payload_value = raw.get("payload") if "payload" in raw else raw.get("data")
    if isinstance(payload_value, (dict, list, str, int, float, bool)) or payload_value is None:
        payload = payload_value
    else:
        payload = _safe_str(payload_value)

    artifacts_raw = raw.get("artifacts") if isinstance(raw.get("artifacts"), list) else raw.get("files") if isinstance(raw.get("files"), list) else []
    artifacts = [_normalize_artifact(item) for item in artifacts_raw if isinstance(item, dict)]

    return {
        "id": event_id,
        "ts": _normalize_ts(raw.get("ts") or raw.get("created_ts") or raw.get("time") or _now_s()),
        "kind": _safe_str(raw.get("kind") or raw.get("type")).strip() or "memory_write",
        "severity": _safe_str(raw.get("severity") or raw.get("level")).strip(),
        "domain": _safe_str(raw.get("domain")).strip(),
        "actor": _safe_str(raw.get("actor") or raw.get("role")).strip(),
        "scope": _safe_str(raw.get("scope") or raw.get("scope_id")).strip(),
        "correlation_id": _safe_str(raw.get("correlation_id") or raw.get("trace_id") or raw.get("correlationId")).strip(),
        "parent_id": _safe_str(raw.get("parent_id") or raw.get("parentId")).strip(),
        "title": _safe_str(raw.get("title")).strip(),
        "message": _safe_str(raw.get("message") or raw.get("summary") or raw.get("content")).strip(),
        "tags": _parse_list(raw.get("tags")),
        "payload": payload,
        "artifacts": artifacts,
        "meta": _meta(raw.get("meta")),
    }


def _public_event(item: dict[str, Any], *, include_payload: bool) -> dict[str, Any]:
    out = {
        "id": item.get("id"),
        "ts": item.get("ts"),
        "kind": item.get("kind"),
        "severity": item.get("severity"),
        "domain": item.get("domain"),
        "actor": item.get("actor"),
        "scope": item.get("scope"),
        "correlation_id": item.get("correlation_id"),
        "parent_id": item.get("parent_id"),
        "title": item.get("title"),
        "message": item.get("message"),
        "tags": item.get("tags") if isinstance(item.get("tags"), list) else [],
        "artifacts": item.get("artifacts") if isinstance(item.get("artifacts"), list) else [],
        "meta": item.get("meta") if isinstance(item.get("meta"), dict) else {},
    }
    if include_payload:
        out["payload"] = item.get("payload")
    return out


def _load_registry() -> dict[str, Any]:
    path = _path()
    if not path.exists():
        return _default_registry()
    try:
        raw = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return _default_registry()

    out = _default_registry()
    if isinstance(raw, dict):
        out["version"] = int(raw.get("version") or 1)
        out["updated_at"] = int(raw.get("updated_at") or _now_s())
        events_raw = raw.get("events")
    elif isinstance(raw, list):
        events_raw = raw
    else:
        events_raw = []

    events: list[dict[str, Any]] = []
    if isinstance(events_raw, list):
        for item in events_raw:
            if not isinstance(item, dict):
                continue
            event_id = _safe_str(item.get("id")).strip() or _new_id("evt", _safe_str(item.get("kind") or item.get("title")).strip() or "event")
            events.append(_normalize_event(event_id, item))

    if len(events) > 100_000:
        events = events[-100_000:]

    out["events"] = events
    return out


def _save_registry(registry: dict[str, Any]) -> None:
    events_obj = registry.get("events")
    events: list[dict[str, Any]] = []
    if isinstance(events_obj, list):
        for item in events_obj:
            if not isinstance(item, dict):
                continue
            event_id = _safe_str(item.get("id")).strip()
            if not event_id:
                continue
            events.append(_normalize_event(event_id, item))
    if len(events) > 100_000:
        events = events[-100_000:]

    payload = {
        "version": int(registry.get("version") or 1),
        "updated_at": _now_s(),
        "events": events,
    }
    _atomic_write(_path(), payload)


def _timeline_from_continuity(limit: int = 10_000) -> list[dict[str, Any]]:
    entries = continuity_tail(limit=max(1, min(limit, 10_000)))
    out: list[dict[str, Any]] = []
    for item in entries:
        if not isinstance(item, dict):
            continue
        ts_raw = item.get("ts")
        ts = _normalize_ts(ts_raw if ts_raw is not None else _now_s())
        role = _safe_str(item.get("role")).strip() or "unknown"
        content = _safe_str(item.get("content")).strip()
        digest = hashlib.sha1(f"{ts}:{role}:{content}".encode("utf-8", errors="ignore")).hexdigest()[:12]
        event_id = f"ledger_{digest}"
        out.append(
            _normalize_event(
                event_id,
                {
                    "id": event_id,
                    "ts": ts,
                    "kind": "ledger_append",
                    "severity": "info",
                    "domain": _safe_str((_meta(item.get("meta"))).get("domain")).strip(),
                    "actor": role,
                    "title": f"Ledger append ({role})",
                    "message": content[:512],
                    "payload": {"content": content, "meta": _meta(item.get("meta"))},
                    "tags": ["continuity", "ledger"],
                    "meta": {"source": "continuity.ledger"},
                },
            )
        )
    return out


def _all_events() -> list[dict[str, Any]]:
    registry = _load_registry()
    events = registry.get("events") if isinstance(registry.get("events"), list) else []

    merged: dict[str, dict[str, Any]] = {}
    for item in events:
        if not isinstance(item, dict):
            continue
        event_id = _safe_str(item.get("id")).strip()
        if not event_id:
            continue
        merged[event_id] = _normalize_event(event_id, item)

    for item in _timeline_from_continuity():
        event_id = _safe_str(item.get("id")).strip()
        if event_id and event_id not in merged:
            merged[event_id] = item

    return list(merged.values())


def _filter_events(
    items: list[dict[str, Any]],
    *,
    kinds: list[str] | None = None,
    severity: str = "",
    domain: str = "",
    actor: str = "",
    scope: str = "",
    correlation_id: str = "",
    tags: list[str] | None = None,
    start_ts: int | None = None,
    end_ts: int | None = None,
    search: str = "",
) -> list[dict[str, Any]]:
    kind_filter = {entry.strip().lower() for entry in (kinds or []) if entry.strip()}
    severity_filter = severity.strip().lower()
    domain_filter = domain.strip().lower()
    actor_filter = actor.strip().lower()
    scope_filter = scope.strip().lower()
    correlation_filter = correlation_id.strip().lower()
    tag_filter = {entry.strip().lower() for entry in (tags or []) if entry.strip()}
    search_filter = search.strip().lower()

    out: list[dict[str, Any]] = []
    for item in items:
        kind_value = _safe_str(item.get("kind")).strip().lower()
        if kind_filter and kind_value not in kind_filter:
            continue
        if severity_filter and _safe_str(item.get("severity")).strip().lower() != severity_filter:
            continue
        if domain_filter and _safe_str(item.get("domain")).strip().lower() != domain_filter:
            continue
        if actor_filter and _safe_str(item.get("actor")).strip().lower() != actor_filter:
            continue
        if scope_filter and _safe_str(item.get("scope")).strip().lower() != scope_filter:
            continue
        if correlation_filter and _safe_str(item.get("correlation_id")).strip().lower() != correlation_filter:
            continue

        if tag_filter:
            item_tags = {entry.strip().lower() for entry in _parse_list(item.get("tags")) if entry.strip()}
            if not tag_filter.issubset(item_tags):
                continue

        ts = int(item.get("ts") or 0)
        if start_ts is not None and ts < int(start_ts):
            continue
        if end_ts is not None and ts > int(end_ts):
            continue

        if search_filter:
            haystack = json.dumps(item, ensure_ascii=False, default=str).lower()
            if search_filter not in haystack:
                continue

        out.append(item)

    return out


def _paginate(items: list[dict[str, Any]], limit: int, offset: int, cursor: str | None) -> tuple[list[dict[str, Any]], int, int, int, str | None]:
    safe_limit = max(1, min(int(limit), 5000))
    safe_offset = int(cursor) if cursor and cursor.isdigit() else max(0, int(offset))
    total = len(items)
    page = items[safe_offset : safe_offset + safe_limit]
    next_cursor = str(safe_offset + safe_limit) if safe_offset + safe_limit < total else None
    return page, total, safe_limit, safe_offset, next_cursor


def _csv(items: list[dict[str, Any]]) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "id",
            "ts",
            "kind",
            "severity",
            "domain",
            "actor",
            "scope",
            "correlation_id",
            "parent_id",
            "title",
            "message",
            "tags",
            "artifacts",
            "meta",
            "payload",
        ],
    )
    writer.writeheader()
    for item in items:
        writer.writerow(
            {
                "id": item.get("id"),
                "ts": item.get("ts"),
                "kind": item.get("kind"),
                "severity": item.get("severity"),
                "domain": item.get("domain"),
                "actor": item.get("actor"),
                "scope": item.get("scope"),
                "correlation_id": item.get("correlation_id"),
                "parent_id": item.get("parent_id"),
                "title": item.get("title"),
                "message": item.get("message"),
                "tags": ",".join(_parse_list(item.get("tags"))),
                "artifacts": json.dumps(item.get("artifacts") if isinstance(item.get("artifacts"), list) else [], ensure_ascii=False),
                "meta": json.dumps(item.get("meta") if isinstance(item.get("meta"), dict) else {}, ensure_ascii=False),
                "payload": json.dumps(item.get("payload"), ensure_ascii=False, default=str),
            }
        )
    return output.getvalue()


def _filename(fmt: str) -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    ext = "jsonl" if fmt == "jsonl" else "csv" if fmt == "csv" else "json"
    return f"francis-memory-timeline-{stamp}.{ext}"


@router.get("/")
def root_status() -> dict[str, Any]:
    return status()


@router.get("/status")
def status() -> dict[str, Any]:
    try:
        items = _all_events()
        kinds: dict[str, int] = {}
        severities: dict[str, int] = {}
        for item in items:
            kind = _safe_str(item.get("kind")).strip() or "unknown"
            severity = _safe_str(item.get("severity")).strip() or "unknown"
            kinds[kind] = kinds.get(kind, 0) + 1
            severities[severity] = severities.get(severity, 0) + 1
        return {
            "ok": True,
            "route": "memory_timeline",
            "status": "ready",
            "ts": _now_s(),
            "counts": {
                "events": len(items),
                "kinds": kinds,
                "severities": severities,
            },
        }
    except Exception as exc:
        return {"ok": False, "route": "memory_timeline", "status": "error", "error": str(exc)}


@router.get("/health")
def health() -> dict[str, Any]:
    body = status()
    body["route"] = "memory_timeline.health"
    return body


@router.get("/list")
def list_timeline(
    limit: int = 200,
    offset: int = 0,
    cursor: str | None = None,
    start_ts: int | None = None,
    end_ts: int | None = None,
    kinds: list[str] | None = Query(default=None),
    severity: str | None = None,
    domain: str | None = None,
    actor: str | None = None,
    scope: str | None = None,
    correlation_id: str | None = None,
    search: str | None = None,
    tags: list[str] | None = Query(default=None),
    include_payload: bool = False,
) -> dict[str, Any]:
    try:
        items = _all_events()
        filtered = _filter_events(
            items,
            kinds=_parse_list(kinds),
            severity=_safe_str(severity),
            domain=_safe_str(domain),
            actor=_safe_str(actor),
            scope=_safe_str(scope),
            correlation_id=_safe_str(correlation_id),
            tags=_parse_list(tags),
            start_ts=start_ts,
            end_ts=end_ts,
            search=_safe_str(search),
        )
        filtered.sort(key=lambda item: (int(item.get("ts") or 0), _safe_str(item.get("id"))), reverse=True)
        page, total, safe_limit, safe_offset, next_cursor = _paginate(filtered, limit, offset, cursor)
        public_items = [_public_event(item, include_payload=include_payload) for item in page]
        return {
            "items": public_items,
            "events": public_items,
            "entries": public_items,
            "timeline": public_items,
            "total": total,
            "limit": safe_limit,
            "offset": safe_offset,
            "next_cursor": next_cursor,
        }
    except Exception as exc:
        return {
            "items": [],
            "events": [],
            "entries": [],
            "timeline": [],
            "total": 0,
            "limit": 0,
            "offset": 0,
            "next_cursor": None,
            "error": str(exc),
        }


@router.get("/get")
def get_timeline_event(id: str, include_payload: bool = True) -> dict[str, Any]:
    try:
        event_id = _validate_id(id, "event id")
        items = _all_events()
        found = next((item for item in items if _safe_str(item.get("id")).strip() == event_id), None)
        if not isinstance(found, dict):
            return {"ok": False, "error": "not_found", "item": None}
        event = _public_event(found, include_payload=include_payload)
        return {"ok": True, "item": event, "event": event}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "item": None}


@router.get("/export")
def export_timeline(
    format: str = "json",
    limit: int = 10_000,
    offset: int = 0,
    cursor: str | None = None,
    start_ts: int | None = None,
    end_ts: int | None = None,
    kinds: list[str] | None = Query(default=None),
    severity: str | None = None,
    domain: str | None = None,
    actor: str | None = None,
    scope: str | None = None,
    correlation_id: str | None = None,
    search: str | None = None,
    tags: list[str] | None = Query(default=None),
    include_payload: bool = True,
) -> Response:
    try:
        fmt = _safe_str(format).strip().lower() or "json"
        if fmt not in {"json", "jsonl", "csv"}:
            return Response(
                content=json.dumps({"ok": False, "error": "unsupported_format"}, ensure_ascii=False),
                media_type="application/json",
                status_code=400,
            )

        items = _all_events()
        filtered = _filter_events(
            items,
            kinds=_parse_list(kinds),
            severity=_safe_str(severity),
            domain=_safe_str(domain),
            actor=_safe_str(actor),
            scope=_safe_str(scope),
            correlation_id=_safe_str(correlation_id),
            tags=_parse_list(tags),
            start_ts=start_ts,
            end_ts=end_ts,
            search=_safe_str(search),
        )
        filtered.sort(key=lambda item: (int(item.get("ts") or 0), _safe_str(item.get("id"))), reverse=True)
        page, _, _, _, _ = _paginate(filtered, max(1, min(int(limit), 10_000)), offset, cursor)
        public_items = [_public_event(item, include_payload=include_payload) for item in page]

        if fmt == "csv":
            content = _csv(public_items)
            media_type = "text/csv"
        elif fmt == "jsonl":
            content = "\n".join(json.dumps(item, ensure_ascii=False, default=str) for item in public_items)
            media_type = "application/jsonl"
        else:
            content = json.dumps({"items": public_items}, ensure_ascii=False, indent=2, default=str)
            media_type = "application/json"

        return Response(
            content=content,
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{_filename(fmt)}"'},
        )
    except Exception as exc:
        return Response(
            content=json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False),
            media_type="application/json",
            status_code=500,
        )


@router.post("/record")
@router.post("/create")
def record_timeline_event(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        requested_id = _safe_str(payload.get("id")).strip()
        if requested_id:
            event_id = _validate_id(requested_id, "event id")
        else:
            event_id = _new_id("evt", _safe_str(payload.get("kind") or payload.get("title") or "event").strip() or "event")

        registry = _load_registry()
        events_obj = registry.get("events")
        if not isinstance(events_obj, list):
            events_obj = []
            registry["events"] = events_obj

        existing_idx = next((idx for idx, item in enumerate(events_obj) if _safe_str((item or {}).get("id")).strip() == event_id), -1)
        existing = events_obj[existing_idx] if existing_idx >= 0 and isinstance(events_obj[existing_idx], dict) else {}

        merged = {
            **existing,
            "id": event_id,
            "ts": _normalize_ts(payload.get("ts") if "ts" in payload else existing.get("ts") or _now_s()),
            "kind": _safe_str(payload.get("kind")).strip() or _safe_str(existing.get("kind")).strip() or "memory_write",
            "severity": _safe_str(payload.get("severity")).strip() or _safe_str(existing.get("severity")).strip(),
            "domain": _safe_str(payload.get("domain")).strip() or _safe_str(existing.get("domain")).strip(),
            "actor": _safe_str(payload.get("actor")).strip() or _safe_str(existing.get("actor")).strip(),
            "scope": _safe_str(payload.get("scope")).strip() or _safe_str(existing.get("scope")).strip(),
            "correlation_id": _safe_str(payload.get("correlation_id") or payload.get("trace_id")).strip()
            or _safe_str(existing.get("correlation_id")).strip(),
            "parent_id": _safe_str(payload.get("parent_id")).strip() or _safe_str(existing.get("parent_id")).strip(),
            "title": _safe_str(payload.get("title")).strip() or _safe_str(existing.get("title")).strip(),
            "message": _safe_str(payload.get("message") or payload.get("summary")).strip() or _safe_str(existing.get("message")).strip(),
            "tags": _parse_list(payload.get("tags") if "tags" in payload else existing.get("tags")),
            "payload": payload.get("payload")
            if "payload" in payload
            else payload.get("data")
            if "data" in payload
            else existing.get("payload"),
            "artifacts": payload.get("artifacts")
            if isinstance(payload.get("artifacts"), list)
            else payload.get("files")
            if isinstance(payload.get("files"), list)
            else existing.get("artifacts"),
            "meta": {**_meta(existing.get("meta")), **_meta(payload.get("meta"))},
        }
        item = _normalize_event(event_id, merged)
        if existing_idx >= 0:
            events_obj[existing_idx] = item
        else:
            events_obj.append(item)

        registry["events"] = events_obj
        _save_registry(registry)
        event = _public_event(item, include_payload=True)
        return {"ok": True, "id": event_id, "item": event, "event": event}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
