from __future__ import annotations

from francis.api.errors import api_error_message
import csv
import io
import json
import math
import os
import re
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from fastapi.responses import Response

from francis.governance.operation_redaction import redact_operation_text
from francis.kernel.paths import data_dir

router = APIRouter()
_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:-]{1,127}$")
_CURRENT_TASK_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "operation_status": ("operation_status", "operationStatus"),
    "current_task_source": ("current_task_source", "currentTaskSource"),
    "current_task_approval_id": ("current_task_approval_id", "currentTaskApprovalId"),
    "current_task_approval_status": ("current_task_approval_status", "currentTaskApprovalStatus"),
    "current_task_previous_approval_id": ("current_task_previous_approval_id", "currentTaskPreviousApprovalId"),
    "current_task_previous_approval_status": (
        "current_task_previous_approval_status",
        "currentTaskPreviousApprovalStatus",
    ),
    "current_task_operation_id": ("current_task_operation_id", "currentTaskOperationId"),
    "current_task_operation_name": ("current_task_operation_name", "currentTaskOperationName"),
    "current_task_operation_plane": ("current_task_operation_plane", "currentTaskOperationPlane"),
    "current_task_advance_action": ("current_task_advance_action", "currentTaskAdvanceAction"),
    "current_task_gate": ("current_task_gate", "currentTaskGate"),
    "current_task_trace_id": ("current_task_trace_id", "currentTaskTraceId"),
    "current_task_run_id": ("current_task_run_id", "currentTaskRunId"),
    "current_task_artifact_dir": ("current_task_artifact_dir", "currentTaskArtifactDir"),
    "current_task_next_step": ("current_task_next_step", "currentTaskNextStep"),
}
_RECEIPT_CONTEXT_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "operation_error": ("operation_error", "operationError"),
    "result_message": ("result_message", "resultMessage"),
    "recovery_next_step": ("recovery_next_step", "recoveryNextStep"),
}
_PLAN_TEXT_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "plan_status": ("plan_status", "planStatus"),
    "plan_current_step_id": ("plan_current_step_id", "planCurrentStepId"),
    "plan_current_step_title": ("plan_current_step_title", "planCurrentStepTitle"),
}
_PLAN_NUMBER_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "plan_step_count": ("plan_step_count", "planStepCount"),
    "plan_checkpoint_count": ("plan_checkpoint_count", "planCheckpointCount"),
}
_REFERENCE_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "mission_id": (
        "mission_id",
        "missionId",
        "current_task_mission_id",
        "currentTaskMissionId",
        "handoff_mission_id",
        "handoffMissionId",
    ),
    "operation_id": (
        "operation_id",
        "operationId",
        "task_id",
        "taskId",
        "current_task_operation_id",
        "currentTaskOperationId",
        "handoff_operation_id",
        "handoffOperationId",
    ),
    "trace_id": (
        "trace_id",
        "traceId",
        "current_task_trace_id",
        "currentTaskTraceId",
        "handoff_trace_id",
        "handoffTraceId",
    ),
    "approval_id": (
        "approval_id",
        "approvalId",
        "current_task_approval_id",
        "currentTaskApprovalId",
        "handoff_approval_id",
        "handoffApprovalId",
    ),
    "run_id": (
        "run_id",
        "runId",
        "current_task_run_id",
        "currentTaskRunId",
        "handoff_run_id",
        "handoffRunId",
    ),
    "artifact_dir": (
        "artifact_dir",
        "artifactDir",
        "artifact_path",
        "artifactPath",
        "current_task_artifact_dir",
        "currentTaskArtifactDir",
        "handoff_artifact_dir",
        "handoffArtifactDir",
    ),
}


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""


def _safe_nonnegative_int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return max(0, value)
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        return max(0, int(value))
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            parsed = float(text)
        except ValueError:
            return None
        if not math.isfinite(parsed):
            return None
        return max(0, int(parsed))
    return None


def _now_s() -> int:
    return int(time.time())


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


def _parse_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        candidates = [part.strip() for part in value.split(",")]
    elif isinstance(value, list):
        candidates = [_safe_str(item).strip() for item in value]
    else:
        return []

    out: list[str] = []
    for candidate in candidates:
        if candidate and candidate not in out:
            out.append(candidate)
    return out


def _meta(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _first_text(sources: tuple[Any, ...], aliases: tuple[str, ...]) -> str:
    for source in sources:
        raw = _meta(source)
        for alias in aliases:
            value = _safe_str(raw.get(alias)).strip()
            if value:
                return value
    return ""


def _reference_handles(*sources: Any) -> dict[str, str]:
    return {
        field: value for field, aliases in _REFERENCE_FIELD_ALIASES.items() if (value := _first_text(sources, aliases))
    }


def _current_task_fields(*sources: Any) -> dict[str, str]:
    out: dict[str, str] = {}
    for field, aliases in _CURRENT_TASK_FIELD_ALIASES.items():
        for source in sources:
            raw = _meta(source)
            value = ""
            for alias in aliases:
                value = _safe_str(raw.get(alias)).strip()
                if value:
                    break
            if value:
                out[field] = value
                break
    return out


def _receipt_context_fields(*sources: Any) -> dict[str, str]:
    out: dict[str, str] = {}
    for field, aliases in _RECEIPT_CONTEXT_FIELD_ALIASES.items():
        for source in sources:
            raw = _meta(source)
            value = ""
            for alias in aliases:
                value = redact_operation_text(raw.get(alias))
                if value:
                    break
            if value:
                out[field] = value
                break
    return out


def _plan_fields(*sources: Any) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for field, aliases in _PLAN_TEXT_FIELD_ALIASES.items():
        value = _first_text(sources, aliases)
        if value:
            out[field] = value
    for field, aliases in _PLAN_NUMBER_FIELD_ALIASES.items():
        for source in sources:
            raw = _meta(source)
            for alias in aliases:
                value = _safe_nonnegative_int(raw.get(alias))
                if value is not None:
                    out[field] = value
                    break
            if field in out:
                break
    return out


def _validate_id(value: str, field: str = "id") -> str:
    text = value.strip()
    if not text:
        raise ValueError(f"{field} is required")
    if not _ID_RE.match(text):
        raise ValueError(f"invalid {field}")
    return text


def _path() -> Path:
    return data_dir() / "explanations" / "_registry.json"


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    os.replace(tmp, path)


def _default_registry() -> dict[str, Any]:
    return {"version": 1, "updated_at": _now_s(), "records": {}}


def _normalize_record(record_id: str, raw: dict[str, Any]) -> dict[str, Any]:
    ts = int(raw.get("ts") or raw.get("created_ts") or _now_s())
    tags = _parse_list(raw.get("tags"))
    tools_raw = raw.get("tools") if isinstance(raw.get("tools"), list) else []
    tools = [tool for tool in tools_raw if isinstance(tool, dict)]
    meta = _meta(raw.get("meta"))
    loop = _meta(raw.get("loop"))
    raw_references = _meta(raw.get("references"))
    references = _reference_handles(raw_references, loop, meta, raw)
    current_task_fields = _current_task_fields(raw, loop, raw_references, meta)
    receipt_context_fields = _receipt_context_fields(raw, loop, raw_references, meta)
    plan_fields = _plan_fields(raw, loop, raw_references, meta)
    trace_id = (
        _safe_str(raw.get("trace_id") or raw.get("traceId")).strip()
        or references.get("trace_id", "")
        or current_task_fields.get("current_task_trace_id", "")
        or _safe_str(meta.get("trace_id") or meta.get("traceId")).strip()
    )
    run_id = (
        _safe_str(raw.get("run_id") or raw.get("runId")).strip()
        or references.get("run_id", "")
        or current_task_fields.get("current_task_run_id", "")
        or _safe_str(meta.get("run_id") or meta.get("runId")).strip()
    )
    artifact_dir = (
        _safe_str(raw.get("artifact_dir") or raw.get("artifactDir")).strip()
        or references.get("artifact_dir", "")
        or current_task_fields.get("current_task_artifact_dir", "")
        or _safe_str(meta.get("artifact_dir") or meta.get("artifactDir")).strip()
    )
    mission_id = (
        _safe_str(raw.get("mission_id") or raw.get("missionId")).strip()
        or references.get("mission_id", "")
        or _safe_str(meta.get("mission_id") or meta.get("missionId")).strip()
    )
    operation_id = (
        _safe_str(raw.get("operation_id") or raw.get("operationId")).strip()
        or references.get("operation_id", "")
        or current_task_fields.get("current_task_operation_id", "")
        or _safe_str(meta.get("operation_id") or meta.get("operationId")).strip()
    )
    approval_id = (
        _safe_str(raw.get("approval_id") or raw.get("approvalId")).strip()
        or references.get("approval_id", "")
        or current_task_fields.get("current_task_approval_id", "")
        or _safe_str(meta.get("approval_id") or meta.get("approvalId")).strip()
    )
    normalized_references = {
        key: value
        for key, value in {
            "mission_id": mission_id,
            "operation_id": operation_id,
            "trace_id": trace_id,
            "approval_id": approval_id,
            "run_id": run_id,
            "artifact_dir": artifact_dir,
        }.items()
        if value
    }

    content_raw = raw.get("content")
    content: dict[str, Any] | str | None
    if isinstance(content_raw, dict):
        content = content_raw
    elif isinstance(content_raw, str):
        content = content_raw
    else:
        content = None

    normalized = {
        "id": record_id,
        "ts": ts,
        "kind": _safe_str(raw.get("kind")).strip() or "audit",
        "severity": _safe_str(raw.get("severity")).strip(),
        "title": _safe_str(raw.get("title")).strip(),
        "summary": _safe_str(raw.get("summary")).strip(),
        "run_id": run_id,
        "trace_id": trace_id,
        "artifact_dir": artifact_dir,
        "mission_id": mission_id,
        "operation_id": operation_id,
        "domain": _safe_str(raw.get("domain")).strip(),
        "conversation_id": _safe_str(raw.get("conversation_id") or raw.get("thread_id")).strip(),
        "approval_id": approval_id,
        "plugin_id": _safe_str(raw.get("plugin_id")).strip(),
        "references": normalized_references,
        "tags": tags,
        "content": content,
        "inputs": _meta(raw.get("inputs")),
        "outputs": _meta(raw.get("outputs")),
        "policy": _meta(raw.get("policy")),
        "tools": tools,
        "meta": meta,
    }
    normalized.update(current_task_fields)
    normalized.update(receipt_context_fields)
    normalized.update(plan_fields)
    return normalized


def _summary(record: dict[str, Any]) -> dict[str, Any]:
    summary = {
        "id": record.get("id"),
        "ts": record.get("ts"),
        "kind": record.get("kind"),
        "severity": record.get("severity"),
        "title": record.get("title"),
        "summary": record.get("summary"),
        "run_id": record.get("run_id"),
        "trace_id": record.get("trace_id"),
        "artifact_dir": record.get("artifact_dir"),
        "mission_id": record.get("mission_id"),
        "operation_id": record.get("operation_id"),
        "domain": record.get("domain"),
        "conversation_id": record.get("conversation_id"),
        "approval_id": record.get("approval_id"),
        "plugin_id": record.get("plugin_id"),
        "references": record.get("references") if isinstance(record.get("references"), dict) else {},
        "tags": record.get("tags") or [],
        "meta": record.get("meta") if isinstance(record.get("meta"), dict) else {},
    }
    for key in _CURRENT_TASK_FIELD_ALIASES:
        value = _safe_str(record.get(key)).strip()
        if value:
            summary[key] = value
    for key in _RECEIPT_CONTEXT_FIELD_ALIASES:
        value = _safe_str(record.get(key)).strip()
        if value:
            summary[key] = value
    for key in _PLAN_TEXT_FIELD_ALIASES:
        value = _safe_str(record.get(key)).strip()
        if value:
            summary[key] = value
    for key in _PLAN_NUMBER_FIELD_ALIASES:
        value = _safe_nonnegative_int(record.get(key))
        if value is not None:
            summary[key] = value
    return summary


def _load_registry() -> dict[str, Any]:
    path = _path()
    if not path.exists():
        return _default_registry()
    try:
        raw = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return _default_registry()
    if not isinstance(raw, dict):
        return _default_registry()

    out = _default_registry()
    out["version"] = int(raw.get("version") or 1)
    out["updated_at"] = int(raw.get("updated_at") or _now_s())

    records_obj = raw.get("records")
    records: dict[str, dict[str, Any]] = {}
    if isinstance(records_obj, dict):
        for rid, item in records_obj.items():
            record_id = _safe_str(rid).strip()
            if not record_id or not isinstance(item, dict):
                continue
            records[record_id] = _normalize_record(record_id, item)
    elif isinstance(records_obj, list):
        for item in records_obj:
            if not isinstance(item, dict):
                continue
            record_id = _safe_str(item.get("id")).strip() or _new_id(
                "exp", _safe_str(item.get("title") or item.get("kind")).strip() or "record"
            )
            records[record_id] = _normalize_record(record_id, item)

    if len(records) > 50_000:
        keep_ids = sorted(records.keys(), key=lambda rid: (int(records[rid].get("ts") or 0), rid), reverse=True)[
            :50_000
        ]
        records = {rid: records[rid] for rid in keep_ids}

    out["records"] = records
    return out


def _save_registry(registry: dict[str, Any]) -> None:
    records_obj = registry.get("records")
    records: dict[str, dict[str, Any]] = {}
    if isinstance(records_obj, dict):
        for rid, item in records_obj.items():
            record_id = _safe_str(rid).strip()
            if not record_id or not isinstance(item, dict):
                continue
            records[record_id] = _normalize_record(record_id, item)

    if len(records) > 50_000:
        keep_ids = sorted(records.keys(), key=lambda rid: (int(records[rid].get("ts") or 0), rid), reverse=True)[
            :50_000
        ]
        records = {rid: records[rid] for rid in keep_ids}

    payload = {
        "version": int(registry.get("version") or 1),
        "updated_at": _now_s(),
        "records": records,
    }
    _atomic_write(_path(), payload)


def _all_records(registry: dict[str, Any]) -> list[dict[str, Any]]:
    records_obj = registry.get("records")
    out: list[dict[str, Any]] = []
    if isinstance(records_obj, dict):
        for rid, item in records_obj.items():
            if isinstance(item, dict):
                out.append(_normalize_record(_safe_str(rid), item))
    return out


def _filter_records(
    items: list[dict[str, Any]],
    *,
    kind: str = "",
    severity: str = "",
    domain: str = "",
    run_id: str = "",
    trace_id: str = "",
    artifact_dir: str = "",
    mission_id: str = "",
    operation_id: str = "",
    conversation_id: str = "",
    approval_id: str = "",
    plugin_id: str = "",
    tags: list[str] | None = None,
    start_ts: int | None = None,
    end_ts: int | None = None,
    search: str = "",
) -> list[dict[str, Any]]:
    kind_filter = kind.strip().lower()
    severity_filter = severity.strip().lower()
    domain_filter = domain.strip().lower()
    run_filter = run_id.strip().lower()
    trace_filter = trace_id.strip().lower()
    artifact_filter = artifact_dir.strip().lower()
    mission_filter = mission_id.strip().lower()
    operation_filter = operation_id.strip().lower()
    conversation_filter = conversation_id.strip().lower()
    approval_filter = approval_id.strip().lower()
    plugin_filter = plugin_id.strip().lower()
    search_filter = search.strip().lower()
    tag_filter = set(tags or [])

    out: list[dict[str, Any]] = []
    for item in items:
        if kind_filter and _safe_str(item.get("kind")).strip().lower() != kind_filter:
            continue
        if severity_filter and _safe_str(item.get("severity")).strip().lower() != severity_filter:
            continue
        if domain_filter and _safe_str(item.get("domain")).strip().lower() != domain_filter:
            continue
        if run_filter and _safe_str(item.get("run_id")).strip().lower() != run_filter:
            continue
        if trace_filter and _safe_str(item.get("trace_id")).strip().lower() != trace_filter:
            continue
        if artifact_filter and _safe_str(item.get("artifact_dir")).strip().lower() != artifact_filter:
            continue
        if mission_filter and _safe_str(item.get("mission_id")).strip().lower() != mission_filter:
            continue
        if operation_filter and _safe_str(item.get("operation_id")).strip().lower() != operation_filter:
            continue
        if conversation_filter and _safe_str(item.get("conversation_id")).strip().lower() != conversation_filter:
            continue
        if approval_filter and _safe_str(item.get("approval_id")).strip().lower() != approval_filter:
            continue
        if plugin_filter and _safe_str(item.get("plugin_id")).strip().lower() != plugin_filter:
            continue
        if tag_filter and not tag_filter.issubset(set(_parse_list(item.get("tags")))):
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


def _paginate(items: list[dict[str, Any]], limit: int, offset: int) -> tuple[list[dict[str, Any]], int, int, int]:
    safe_limit = max(1, min(int(limit), 5000))
    safe_offset = max(0, int(offset))
    total = len(items)
    return items[safe_offset : safe_offset + safe_limit], total, safe_limit, safe_offset


def _csv(records: list[dict[str, Any]]) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "id",
            "ts",
            "kind",
            "severity",
            "title",
            "summary",
            "run_id",
            "trace_id",
            "artifact_dir",
            "mission_id",
            "operation_id",
            "operation_status",
            "operation_error",
            "result_message",
            "recovery_next_step",
            "current_task_source",
            "current_task_approval_id",
            "current_task_approval_status",
            "current_task_previous_approval_id",
            "current_task_previous_approval_status",
            "current_task_operation_id",
            "current_task_operation_name",
            "current_task_operation_plane",
            "current_task_advance_action",
            "current_task_gate",
            "current_task_trace_id",
            "current_task_run_id",
            "current_task_artifact_dir",
            "current_task_next_step",
            "plan_status",
            "plan_current_step_id",
            "plan_current_step_title",
            "plan_step_count",
            "plan_checkpoint_count",
            "domain",
            "conversation_id",
            "approval_id",
            "plugin_id",
            "tags",
            "meta",
        ],
    )
    writer.writeheader()
    for item in records:
        writer.writerow(
            {
                "id": item.get("id"),
                "ts": item.get("ts"),
                "kind": item.get("kind"),
                "severity": item.get("severity"),
                "title": item.get("title"),
                "summary": item.get("summary"),
                "run_id": item.get("run_id"),
                "trace_id": item.get("trace_id"),
                "artifact_dir": item.get("artifact_dir"),
                "mission_id": item.get("mission_id"),
                "operation_id": item.get("operation_id"),
                "operation_status": item.get("operation_status"),
                "operation_error": item.get("operation_error"),
                "result_message": item.get("result_message"),
                "recovery_next_step": item.get("recovery_next_step"),
                "current_task_source": item.get("current_task_source"),
                "current_task_approval_id": item.get("current_task_approval_id"),
                "current_task_approval_status": item.get("current_task_approval_status"),
                "current_task_previous_approval_id": item.get("current_task_previous_approval_id"),
                "current_task_previous_approval_status": item.get("current_task_previous_approval_status"),
                "current_task_operation_id": item.get("current_task_operation_id"),
                "current_task_operation_name": item.get("current_task_operation_name"),
                "current_task_operation_plane": item.get("current_task_operation_plane"),
                "current_task_advance_action": item.get("current_task_advance_action"),
                "current_task_gate": item.get("current_task_gate"),
                "current_task_trace_id": item.get("current_task_trace_id"),
                "current_task_run_id": item.get("current_task_run_id"),
                "current_task_artifact_dir": item.get("current_task_artifact_dir"),
                "current_task_next_step": item.get("current_task_next_step"),
                "plan_status": item.get("plan_status"),
                "plan_current_step_id": item.get("plan_current_step_id"),
                "plan_current_step_title": item.get("plan_current_step_title"),
                "plan_step_count": item.get("plan_step_count"),
                "plan_checkpoint_count": item.get("plan_checkpoint_count"),
                "domain": item.get("domain"),
                "conversation_id": item.get("conversation_id"),
                "approval_id": item.get("approval_id"),
                "plugin_id": item.get("plugin_id"),
                "tags": ",".join(_parse_list(item.get("tags"))),
                "meta": json.dumps(item.get("meta") if isinstance(item.get("meta"), dict) else {}, ensure_ascii=False),
            }
        )
    return output.getvalue()


def _export_filename(fmt: str) -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    ext = "csv" if fmt == "csv" else "json"
    return f"francis-explanations-{stamp}.{ext}"


def _query_records(
    *,
    kind: str | None = None,
    severity: str | None = None,
    domain: str | None = None,
    run_id: str | None = None,
    trace_id: str | None = None,
    artifact_dir: str | None = None,
    mission_id: str | None = None,
    operation_id: str | None = None,
    conversation_id: str | None = None,
    approval_id: str | None = None,
    plugin_id: str | None = None,
    tags: str | None = None,
    start_ts: int | None = None,
    end_ts: int | None = None,
    search: str | None = None,
) -> list[dict[str, Any]]:
    items = _all_records(_load_registry())
    filtered = _filter_records(
        items,
        kind=_safe_str(kind),
        severity=_safe_str(severity),
        domain=_safe_str(domain),
        run_id=_safe_str(run_id),
        trace_id=_safe_str(trace_id),
        artifact_dir=_safe_str(artifact_dir),
        mission_id=_safe_str(mission_id),
        operation_id=_safe_str(operation_id),
        conversation_id=_safe_str(conversation_id),
        approval_id=_safe_str(approval_id),
        plugin_id=_safe_str(plugin_id),
        tags=_parse_list(tags),
        start_ts=start_ts,
        end_ts=end_ts,
        search=_safe_str(search),
    )
    filtered.sort(key=lambda item: (int(item.get("ts") or 0), _safe_str(item.get("id"))), reverse=True)
    return filtered


@router.get("/")
def root_status() -> dict[str, Any]:
    return status()


@router.get("/status")
def status() -> dict[str, Any]:
    try:
        items = _all_records(_load_registry())
        kinds: dict[str, int] = {}
        severities: dict[str, int] = {}
        for item in items:
            kind = _safe_str(item.get("kind")).strip() or "audit"
            severity = _safe_str(item.get("severity")).strip() or "unknown"
            kinds[kind] = kinds.get(kind, 0) + 1
            severities[severity] = severities.get(severity, 0) + 1

        return {
            "ok": True,
            "route": "explanation",
            "status": "ready",
            "ts": _now_s(),
            "counts": {
                "records": len(items),
                "kinds": kinds,
                "severities": severities,
            },
        }
    except Exception as exc:
        return {"ok": False, "route": "explanation", "status": "error", "error": api_error_message(exc)}


@router.get("/health")
def health() -> dict[str, Any]:
    body = status()
    body["route"] = "explanation.health"
    return body


@router.get("/list")
def list_explanations(
    limit: int = 200,
    offset: int = 0,
    kind: str | None = None,
    severity: str | None = None,
    domain: str | None = None,
    run_id: str | None = None,
    trace_id: str | None = None,
    artifact_dir: str | None = None,
    mission_id: str | None = None,
    operation_id: str | None = None,
    conversation_id: str | None = None,
    approval_id: str | None = None,
    plugin_id: str | None = None,
    tags: str | None = None,
    start_ts: int | None = None,
    end_ts: int | None = None,
    search: str | None = None,
) -> dict[str, Any]:
    try:
        items = _query_records(
            kind=kind,
            severity=severity,
            domain=domain,
            run_id=run_id,
            trace_id=trace_id,
            artifact_dir=artifact_dir,
            mission_id=mission_id,
            operation_id=operation_id,
            conversation_id=conversation_id,
            approval_id=approval_id,
            plugin_id=plugin_id,
            tags=tags,
            start_ts=start_ts,
            end_ts=end_ts,
            search=search,
        )
        page, total, safe_limit, safe_offset = _paginate(items, limit, offset)
        summaries = [_summary(item) for item in page]
        return {"items": summaries, "records": summaries, "total": total, "limit": safe_limit, "offset": safe_offset}
    except Exception as exc:
        return {"items": [], "records": [], "total": 0, "limit": 0, "offset": 0, "error": api_error_message(exc)}


@router.get("/get")
def get_explanation(id: str) -> dict[str, Any]:
    try:
        explanation_id = _validate_id(id, "explanation id")
        registry = _load_registry()
        records_obj = registry.get("records")
        if not isinstance(records_obj, dict):
            records_obj = {}
        raw = records_obj.get(explanation_id)
        if not isinstance(raw, dict):
            return {"ok": False, "error": "not_found", "item": None}
        item = _normalize_record(explanation_id, raw)
        return {
            "ok": True,
            "item": _summary(item),
            "content": item.get("content"),
            "inputs": item.get("inputs") if isinstance(item.get("inputs"), dict) else {},
            "outputs": item.get("outputs") if isinstance(item.get("outputs"), dict) else {},
            "policy": item.get("policy") if isinstance(item.get("policy"), dict) else {},
            "tools": item.get("tools") if isinstance(item.get("tools"), list) else [],
            "meta": item.get("meta") if isinstance(item.get("meta"), dict) else {},
        }
    except Exception as exc:
        return {"ok": False, "error": api_error_message(exc), "item": None}


@router.get("/export")
def export_explanations(
    format: str = "json",
    limit: int = 10_000,
    offset: int = 0,
    kind: str | None = None,
    severity: str | None = None,
    domain: str | None = None,
    run_id: str | None = None,
    trace_id: str | None = None,
    artifact_dir: str | None = None,
    mission_id: str | None = None,
    operation_id: str | None = None,
    conversation_id: str | None = None,
    approval_id: str | None = None,
    plugin_id: str | None = None,
    tags: str | None = None,
    start_ts: int | None = None,
    end_ts: int | None = None,
    search: str | None = None,
) -> Response:
    try:
        fmt = _safe_str(format).strip().lower() or "json"
        if fmt not in {"json", "csv"}:
            return Response(
                content=json.dumps({"ok": False, "error": "unsupported_format"}, ensure_ascii=False),
                media_type="application/json",
                status_code=400,
            )

        safe_limit = max(1, min(int(limit), 10_000))
        safe_offset = max(0, int(offset))
        filtered = _query_records(
            kind=kind,
            severity=severity,
            domain=domain,
            run_id=run_id,
            trace_id=trace_id,
            artifact_dir=artifact_dir,
            mission_id=mission_id,
            operation_id=operation_id,
            conversation_id=conversation_id,
            approval_id=approval_id,
            plugin_id=plugin_id,
            tags=tags,
            start_ts=start_ts,
            end_ts=end_ts,
            search=search,
        )
        summaries = [_summary(item) for item in filtered[safe_offset : safe_offset + safe_limit]]

        if fmt == "csv":
            content = _csv(summaries)
            media_type = "text/csv"
        else:
            content = json.dumps({"items": summaries}, ensure_ascii=False, indent=2, default=str)
            media_type = "application/json"

        return Response(
            content=content,
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{_export_filename(fmt)}"'},
        )
    except Exception as exc:
        return Response(
            content=json.dumps({"ok": False, "error": api_error_message(exc)}, ensure_ascii=False),
            media_type="application/json",
            status_code=500,
        )


@router.post("/record")
@router.post("/create")
def record_explanation(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        requested_id = _safe_str(payload.get("id")).strip()
        title = _safe_str(payload.get("title")).strip()
        kind = _safe_str(payload.get("kind")).strip() or "audit"

        if requested_id:
            explanation_id = _validate_id(requested_id, "explanation id")
        else:
            explanation_id = _new_id("exp", title or kind or "record")

        registry = _load_registry()
        records_obj = registry.get("records")
        if not isinstance(records_obj, dict):
            records_obj = {}
            registry["records"] = records_obj

        existing = records_obj.get(explanation_id)
        existing_obj = existing if isinstance(existing, dict) else {}
        payload_meta = _meta(payload.get("meta"))
        existing_meta = _meta(existing_obj.get("meta"))
        payload_references = _reference_handles(payload.get("references"), payload.get("loop"), payload_meta, payload)
        existing_references = _reference_handles(
            existing_obj.get("references"), existing_obj.get("loop"), existing_meta, existing_obj
        )
        payload_current_task = _current_task_fields(
            payload, payload.get("loop"), payload.get("references"), payload_meta
        )
        existing_current_task = _current_task_fields(
            existing_obj, existing_obj.get("loop"), existing_obj.get("references"), existing_meta
        )
        current_task_fields = {**existing_current_task, **payload_current_task}
        payload_receipt_context = _receipt_context_fields(
            payload, payload.get("loop"), payload.get("references"), payload_meta
        )
        existing_receipt_context = _receipt_context_fields(
            existing_obj, existing_obj.get("loop"), existing_obj.get("references"), existing_meta
        )
        receipt_context_fields = {**existing_receipt_context, **payload_receipt_context}
        payload_plan_fields = _plan_fields(payload, payload.get("loop"), payload.get("references"), payload_meta)
        existing_plan_fields = _plan_fields(
            existing_obj, existing_obj.get("loop"), existing_obj.get("references"), existing_meta
        )
        plan_fields = {**existing_plan_fields, **payload_plan_fields}
        trace_id = (
            _safe_str(payload.get("trace_id") or payload.get("traceId")).strip()
            or _safe_str(existing_obj.get("trace_id") or existing_obj.get("traceId")).strip()
            or payload_references.get("trace_id", "")
            or existing_references.get("trace_id", "")
            or current_task_fields.get("current_task_trace_id", "")
            or _safe_str(payload_meta.get("trace_id") or payload_meta.get("traceId")).strip()
            or _safe_str(existing_meta.get("trace_id") or existing_meta.get("traceId")).strip()
        )
        run_id = (
            _safe_str(payload.get("run_id") or payload.get("runId")).strip()
            or _safe_str(existing_obj.get("run_id") or existing_obj.get("runId")).strip()
            or payload_references.get("run_id", "")
            or existing_references.get("run_id", "")
            or current_task_fields.get("current_task_run_id", "")
            or _safe_str(payload_meta.get("run_id") or payload_meta.get("runId")).strip()
            or _safe_str(existing_meta.get("run_id") or existing_meta.get("runId")).strip()
        )
        artifact_dir = (
            _safe_str(payload.get("artifact_dir") or payload.get("artifactDir")).strip()
            or _safe_str(existing_obj.get("artifact_dir") or existing_obj.get("artifactDir")).strip()
            or payload_references.get("artifact_dir", "")
            or existing_references.get("artifact_dir", "")
            or current_task_fields.get("current_task_artifact_dir", "")
            or _safe_str(payload_meta.get("artifact_dir") or payload_meta.get("artifactDir")).strip()
            or _safe_str(existing_meta.get("artifact_dir") or existing_meta.get("artifactDir")).strip()
        )
        mission_id = (
            _safe_str(payload.get("mission_id") or payload.get("missionId")).strip()
            or _safe_str(existing_obj.get("mission_id") or existing_obj.get("missionId")).strip()
            or payload_references.get("mission_id", "")
            or existing_references.get("mission_id", "")
            or _safe_str(payload_meta.get("mission_id") or payload_meta.get("missionId")).strip()
            or _safe_str(existing_meta.get("mission_id") or existing_meta.get("missionId")).strip()
        )
        operation_id = (
            _safe_str(payload.get("operation_id") or payload.get("operationId")).strip()
            or _safe_str(existing_obj.get("operation_id") or existing_obj.get("operationId")).strip()
            or payload_references.get("operation_id", "")
            or existing_references.get("operation_id", "")
            or current_task_fields.get("current_task_operation_id", "")
            or _safe_str(payload_meta.get("operation_id") or payload_meta.get("operationId")).strip()
            or _safe_str(existing_meta.get("operation_id") or existing_meta.get("operationId")).strip()
        )
        approval_id = (
            _safe_str(payload.get("approval_id") or payload.get("approvalId")).strip()
            or _safe_str(existing_obj.get("approval_id") or existing_obj.get("approvalId")).strip()
            or payload_references.get("approval_id", "")
            or existing_references.get("approval_id", "")
            or current_task_fields.get("current_task_approval_id", "")
            or _safe_str(payload_meta.get("approval_id") or payload_meta.get("approvalId")).strip()
            or _safe_str(existing_meta.get("approval_id") or existing_meta.get("approvalId")).strip()
        )
        references = {
            key: value
            for key, value in {
                "mission_id": mission_id,
                "operation_id": operation_id,
                "trace_id": trace_id,
                "approval_id": approval_id,
                "run_id": run_id,
                "artifact_dir": artifact_dir,
            }.items()
            if value
        }
        ts = int(payload.get("ts") or existing_obj.get("ts") or _now_s())

        merged = {
            **existing_obj,
            **current_task_fields,
            **receipt_context_fields,
            **plan_fields,
            "id": explanation_id,
            "ts": ts,
            "kind": kind or _safe_str(existing_obj.get("kind")).strip() or "audit",
            "severity": _safe_str(payload.get("severity")).strip() or _safe_str(existing_obj.get("severity")).strip(),
            "title": title or _safe_str(existing_obj.get("title")).strip(),
            "summary": _safe_str(payload.get("summary")).strip() or _safe_str(existing_obj.get("summary")).strip(),
            "run_id": run_id,
            "trace_id": trace_id,
            "artifact_dir": artifact_dir,
            "mission_id": mission_id,
            "operation_id": operation_id,
            "domain": _safe_str(payload.get("domain")).strip() or _safe_str(existing_obj.get("domain")).strip(),
            "conversation_id": _safe_str(payload.get("conversation_id") or payload.get("thread_id")).strip()
            or _safe_str(existing_obj.get("conversation_id")).strip(),
            "approval_id": approval_id,
            "plugin_id": _safe_str(payload.get("plugin_id")).strip()
            or _safe_str(existing_obj.get("plugin_id")).strip(),
            "references": references,
            "tags": _parse_list(payload.get("tags") if "tags" in payload else existing_obj.get("tags")),
            "content": payload.get("content") if "content" in payload else existing_obj.get("content"),
            "inputs": _meta(payload.get("inputs") if "inputs" in payload else existing_obj.get("inputs")),
            "outputs": _meta(payload.get("outputs") if "outputs" in payload else existing_obj.get("outputs")),
            "policy": _meta(payload.get("policy") if "policy" in payload else existing_obj.get("policy")),
            "tools": payload.get("tools")
            if isinstance(payload.get("tools"), list)
            else (existing_obj.get("tools") if isinstance(existing_obj.get("tools"), list) else []),
            "meta": {**existing_meta, **payload_meta},
        }
        item = _normalize_record(explanation_id, merged)
        records_obj[explanation_id] = item
        _save_registry(registry)
        return {"ok": True, "id": explanation_id, "item": _summary(item)}
    except Exception as exc:
        return {"ok": False, "error": api_error_message(exc)}
