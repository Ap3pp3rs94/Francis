from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from francis.governance.approval_projection import approval_projection_fields
from francis.kernel.feature_flags import list_flags
from francis.kernel.paths import data_dir, repo_root
from francis.kernel.services import services_status
from francis.kernel.stack import stack_status
from francis.missions import store as mission_store
from francis.operations import runtime as operations_runtime
from francis.telemetry.audit import read_events
from francis.trust.levels import get_state


_TERMINAL_TASK_STATUSES = {"completed", "failed", "cancelled"}
_TERMINAL_MISSION_STATUSES = {"completed", "failed", "deadlettered", "cancelled"}
_INCIDENT_SEVERITY_ORDER = {"critical": 0, "error": 1, "warning": 2, "info": 3}
_OBSERVER_ANOMALY_WEIGHTS = {"critical": 80, "error": 50, "warning": 20, "info": 5}


def _count_json_entries(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        return len([item for item in path.iterdir() if item.is_file()])
    except Exception:
        return 0


def _count_task_records(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        count = 0
        for item in path.iterdir():
            if item.is_file():
                count += 1
                continue
            if item.is_dir() and (item / "record.json").is_file():
                count += 1
        return count
    except Exception:
        return 0


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


def _parse_ts(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return 0.0
        try:
            return float(text)
        except Exception:
            pass
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            return dt.timestamp()
        except Exception:
            return 0.0
    return 0.0


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""


def _observer_anomaly_projection(raw: Any) -> dict[str, Any]:
    payload = raw if isinstance(raw, dict) else {}
    level = _safe_str(payload.get("level")).strip().lower()
    reasons = [_safe_str(item).strip() for item in payload.get("reasons", []) if _safe_str(item).strip()]
    score = int(payload.get("score") or 0)

    projected: dict[str, Any] = {"score": max(0, min(score, 100))}
    if level:
        projected["level"] = level
    if reasons:
        projected["reasons"] = reasons
    return projected


def observer_incident_counts(incidents: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"active": len(incidents), "critical": 0, "error": 0, "warning": 0, "info": 0}
    for item in incidents:
        severity = _safe_str(item.get("severity")).strip().lower()
        if severity in counts:
            counts[severity] += 1
    return counts


def observer_anomaly_summary(incidents: list[dict[str, Any]]) -> dict[str, Any]:
    counts = observer_incident_counts(incidents)
    if int(counts.get("active") or 0) <= 0:
        return {"score": 0, "level": "clear", "reasons": []}

    weighted_score = sum(
        int(counts.get(severity) or 0) * weight for severity, weight in _OBSERVER_ANOMALY_WEIGHTS.items()
    )
    weighted_score += max(0, int(counts.get("active") or 0) - 1) * 5
    score = max(0, min(weighted_score, 100))

    if score >= 80:
        level = "critical"
    elif score >= 50:
        level = "error"
    elif score >= 20:
        level = "warning"
    else:
        level = "info"

    reasons: list[str] = []
    for severity in ("critical", "error", "warning", "info"):
        count = int(counts.get(severity) or 0)
        if count > 0:
            reasons.append(f"{severity} incidents: {count}")

    probes = sorted(
        {_safe_str(item.get("probe")).strip() for item in incidents if _safe_str(item.get("probe")).strip()}
    )
    if probes:
        reasons.append(f"active probes: {', '.join(probes[:3])}")

    lead = incidents[0] if incidents else {}
    lead_title = _safe_str(lead.get("title")).strip() or _safe_str(lead.get("id")).strip()
    if lead_title:
        reasons.append(f"lead issue: {lead_title}")

    return {"score": score, "level": level, "reasons": reasons[:4]}


def observer_focus(incidents: list[dict[str, Any]], *, limit: int = 3) -> list[dict[str, Any]]:
    return [dict(item) for item in incidents[: max(0, int(limit))] if isinstance(item, dict)]


def _probe_severity(incidents: list[dict[str, Any]]) -> str:
    if not incidents:
        return "clear"
    ordered = sorted(
        (_safe_str(item.get("severity")).strip().lower() for item in incidents),
        key=lambda value: _INCIDENT_SEVERITY_ORDER.get(value, 99),
    )
    return ordered[0] if ordered else "clear"


def _observer_probe_summary(
    probe_id: str,
    *,
    status: str,
    incidents: list[dict[str, Any]],
    headline: str,
    detail: str,
) -> dict[str, Any]:
    return {
        "id": probe_id,
        "status": status,
        "severity": _probe_severity(incidents),
        "headline": headline,
        "detail": detail,
        "incident_count": len(incidents),
    }


def observer_probe_statuses(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    incidents = [dict(item) for item in snapshot.get("incidents", []) if isinstance(item, dict)]
    incidents_by_probe: dict[str, list[dict[str, Any]]] = {}
    for item in incidents:
        probe_id = _safe_str(item.get("probe")).strip()
        if not probe_id:
            continue
        incidents_by_probe.setdefault(probe_id, []).append(item)

    stack_report = snapshot.get("stack") if isinstance(snapshot.get("stack"), dict) else {}
    stack_counts = stack_report.get("counts") if isinstance(stack_report.get("counts"), dict) else {}
    stack_incidents = incidents_by_probe.get("stack_status", [])
    stack_total = int(stack_counts.get("total") or 0)
    stack_ready = int(stack_counts.get("ready") or 0)
    stack_missing = int(stack_counts.get("missing") or 0)

    services_report = snapshot.get("services") if isinstance(snapshot.get("services"), dict) else {}
    services_counts = services_report.get("counts") if isinstance(services_report.get("counts"), dict) else {}
    service_incidents = incidents_by_probe.get("services_status", [])
    services_ready = int(services_counts.get("ready") or 0)
    services_missing = int(services_counts.get("missing") or 0)
    services_disabled = int(services_counts.get("disabled") or 0)

    pending_approvals = snapshot.get("pending_approvals") if isinstance(snapshot.get("pending_approvals"), list) else []
    approval_incidents = incidents_by_probe.get("approval_queue", [])
    task_status_counts = (
        snapshot.get("task_status_counts") if isinstance(snapshot.get("task_status_counts"), dict) else {}
    )
    runtime_incidents = incidents_by_probe.get("task_runtime", [])
    blocked_tasks = int(task_status_counts.get("blocked") or 0)
    approval_pending_tasks = int(task_status_counts.get("needs_approval") or 0)
    failed_tasks = int(task_status_counts.get("failed") or 0)

    stack_headline = (
        _safe_str(stack_incidents[0].get("title")).strip() if stack_incidents else "Stack surfaces are ready."
    )
    services_headline = (
        _safe_str(service_incidents[0].get("title")).strip() if service_incidents else "Service surfaces are ready."
    )
    approval_headline = (
        _safe_str(approval_incidents[0].get("title")).strip() if approval_incidents else "Approval queue is clear."
    )
    runtime_headline = (
        _safe_str(runtime_incidents[0].get("title")).strip() if runtime_incidents else "Task runtime is clear."
    )

    return [
        _observer_probe_summary(
            "stack_status",
            status=_safe_str(stack_report.get("status")).strip() or "unknown",
            incidents=stack_incidents,
            headline=stack_headline,
            detail=f"{stack_ready}/{stack_total} stack surfaces ready; missing {stack_missing}.",
        ),
        _observer_probe_summary(
            "services_status",
            status=_safe_str(services_report.get("status")).strip() or "unknown",
            incidents=service_incidents,
            headline=services_headline,
            detail=f"{services_ready} ready; missing {services_missing}; disabled {services_disabled}.",
        ),
        _observer_probe_summary(
            "approval_queue",
            status="attention" if approval_incidents else "ok",
            incidents=approval_incidents,
            headline=approval_headline,
            detail=f"{len(pending_approvals)} approval request(s) queued for review.",
        ),
        _observer_probe_summary(
            "task_runtime",
            status="attention" if runtime_incidents else "ok",
            incidents=runtime_incidents,
            headline=runtime_headline,
            detail=(f"blocked {blocked_tasks}; awaiting approval {approval_pending_tasks}; failed {failed_tasks}."),
        ),
    ]


def observer_decision(counts: dict[str, int]) -> str:
    if int(counts.get("active") or 0) <= 0:
        return "stable"
    if int(counts.get("critical") or 0) > 0 or int(counts.get("error") or 0) > 0:
        return "urgent_review"
    return "review"


def observer_headline(incidents: list[dict[str, Any]], counts: dict[str, int]) -> str:
    active = int(counts.get("active") or 0)
    if active <= 0:
        return "Observer reports no active incidents."
    focus = incidents[0] if incidents else {}
    focus_title = _safe_str(focus.get("title")).strip() or "Observer findings need review"
    return f"Observer flagged {active} active incident(s); highest-priority issue: {focus_title}."


def observer_summary(snapshot: dict[str, Any], *, focus_limit: int = 3) -> dict[str, Any]:
    incidents = snapshot.get("incidents") if isinstance(snapshot.get("incidents"), list) else []
    normalized_incidents = [dict(item) for item in incidents if isinstance(item, dict)]
    counts = observer_incident_counts(normalized_incidents)
    focus = observer_focus(normalized_incidents, limit=focus_limit)
    probes = sorted(
        {_safe_str(item.get("probe")).strip() for item in normalized_incidents if _safe_str(item.get("probe")).strip()}
    )
    return {
        "headline": observer_headline(normalized_incidents, counts),
        "decision": observer_decision(counts),
        "counts": counts,
        "focus": focus,
        "incident_ids": [
            str(item.get("id") or "").strip() for item in normalized_incidents if str(item.get("id") or "").strip()
        ],
        "probes": probes,
        "probe_statuses": observer_probe_statuses(snapshot),
        "anomaly": observer_anomaly_summary(normalized_incidents),
    }


def observer_scan_event_projection(item: dict[str, Any]) -> dict[str, Any]:
    counts = item.get("counts") if isinstance(item.get("counts"), dict) else {}
    focus = [dict(entry) for entry in item.get("focus", []) if isinstance(entry, dict)]
    probe_statuses = [dict(entry) for entry in item.get("probe_statuses", []) if isinstance(entry, dict)]
    projected: dict[str, Any] = {
        "ts": float(item.get("ts") or 0.0),
        "receipt_id": _safe_str(item.get("receipt_id")).strip(),
        "event": _safe_str(item.get("event")).strip(),
        "status": _safe_str(item.get("status")).strip(),
        "decision": _safe_str(item.get("decision")).strip(),
        "headline": _safe_str(item.get("headline")).strip(),
        "incident_count": int(item.get("incident_count") or counts.get("active") or 0),
        "counts": {key: int(value) for key, value in counts.items() if isinstance(value, (int, float))},
        "incident_ids": [str(value).strip() for value in item.get("incident_ids", []) if str(value).strip()],
        "probes": [str(value).strip() for value in item.get("probes", []) if str(value).strip()],
        "focus": focus,
        "probe_statuses": probe_statuses,
        "anomaly": _observer_anomaly_projection(item.get("anomaly")),
        "generated_at": float(item.get("generated_at") or 0.0),
        "reason": _safe_str(item.get("reason")).strip(),
        "actor": _safe_str(item.get("actor")).strip(),
        "trace_id": _safe_str(item.get("trace_id")).strip(),
        "run_id": _safe_str(item.get("run_id")).strip(),
    }
    cleaned: dict[str, Any] = {}
    for key, value in projected.items():
        if value is None:
            continue
        if isinstance(value, str) and not value:
            continue
        if isinstance(value, (list, dict)) and not value:
            continue
        cleaned[key] = value
    return cleaned


def observer_scan_history(*, limit: int = 10, status: str = "", decision: str = "") -> list[dict[str, Any]]:
    items = read_events(limit=max(1, min(int(limit), 100)), event="observer.scan")
    status_filter = status.strip().lower()
    decision_filter = decision.strip().lower()
    projected = [observer_scan_event_projection(item) for item in items if isinstance(item, dict)]
    filtered: list[dict[str, Any]] = []
    for item in projected:
        if status_filter and _safe_str(item.get("status")).strip().lower() != status_filter:
            continue
        if decision_filter and _safe_str(item.get("decision")).strip().lower() != decision_filter:
            continue
        filtered.append(item)
    filtered.sort(key=lambda item: float(item.get("ts") or 0.0), reverse=True)
    return filtered


def _normalize_task_status(value: Any) -> str:
    status = str(value or "pending").strip().lower()
    if status == "complete":
        return "completed"
    if status == "canceled":
        return "cancelled"
    if not status:
        return "pending"
    return status


def _result_payload(record: dict[str, Any]) -> dict[str, Any]:
    result = record.get("result")
    if not isinstance(result, dict):
        return {}
    payload = result.get("data")
    return payload if isinstance(payload, dict) else {}


def _result_status(record: dict[str, Any]) -> str:
    return str(_result_payload(record).get("status") or "").strip().lower()


def _effective_task_status(record: dict[str, Any]) -> str:
    result_status = _result_status(record)
    if result_status in {"blocked", "denied"}:
        return "blocked"
    if result_status in {"pending", "needs_approval"}:
        return "needs_approval"
    return _normalize_task_status(record.get("status"))


def _task_status_reason(record: dict[str, Any]) -> str:
    status_reason = str(record.get("status_reason") or "").strip()
    if status_reason:
        return status_reason
    payload = _result_payload(record)
    return str(payload.get("error") or payload.get("message") or "").strip()


def _iter_task_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    try:
        for item in path.iterdir():
            record_path = item if item.is_file() else item / "record.json"
            if not record_path.is_file():
                continue
            record = _read_json(record_path)
            if record:
                records.append(record)
    except Exception:
        return []
    return records


def _task_summary(path: Path, limit: int = 10) -> dict[str, Any]:
    status_counts = {
        "pending": 0,
        "accepted": 0,
        "needs_approval": 0,
        "blocked": 0,
        "running": 0,
        "completed": 0,
        "failed": 0,
        "cancelled": 0,
        "unknown": 0,
    }
    recent: list[dict[str, Any]] = []
    for record in _iter_task_records(path):
        status = _effective_task_status(record)
        if status in status_counts:
            status_counts[status] += 1
        else:
            status_counts["unknown"] += 1

        updated_at = record.get("updated_at")
        created_at = record.get("created_at")
        recent.append(
            {
                "id": str(record.get("task_id") or "").strip(),
                "status": status,
                "capability": str(record.get("capability") or "").strip(),
                "objective": str(record.get("objective") or "").strip(),
                "requester_id": str(record.get("requester_id") or "").strip(),
                "assigned_to": str(record.get("assigned_to") or "").strip(),
                "created_at": str(created_at or "").strip(),
                "updated_at": str(updated_at or "").strip(),
                "status_reason": _task_status_reason(record),
                "terminal": status in _TERMINAL_TASK_STATUSES,
                "_sort_ts": _parse_ts(updated_at) or _parse_ts(created_at),
            }
        )

    recent.sort(key=lambda item: (float(item.get("_sort_ts") or 0.0), str(item.get("id") or "")), reverse=True)
    trimmed: list[dict[str, Any]] = []
    for item in recent[: max(0, int(limit))]:
        clean = dict(item)
        clean.pop("_sort_ts", None)
        trimmed.append(clean)

    return {
        "status_counts": status_counts,
        "recent": trimmed,
    }


def _mission_summary(limit: int = 10) -> dict[str, Any]:
    status_counts = {
        "queued": 0,
        "active": 0,
        "blocked": 0,
        "completed": 0,
        "failed": 0,
        "deadlettered": 0,
        "cancelled": 0,
        "unknown": 0,
    }
    recent: list[dict[str, Any]] = []
    for record in mission_store.list_missions(limit=10_000):
        status = str(record.status.value or "").strip().lower() or "queued"
        meta = dict(record.meta) if isinstance(record.meta, dict) else {}
        if status in status_counts:
            status_counts[status] += 1
        else:
            status_counts["unknown"] += 1
        recent.append(
            {
                "id": record.mission_id,
                "status": status,
                "objective": record.objective,
                "summary": record.summary,
                "next_step": record.next_step,
                "requester_id": record.requester_id,
                "priority": record.priority,
                "risk_tier": record.risk_tier,
                "linked_task_ids": list(record.linked_task_ids),
                "linked_task_count": len(record.linked_task_ids),
                "deadletter_reason": record.deadletter_reason,
                "last_task_id": str(meta.get("last_task_id") or "").strip(),
                "last_task_status": str(meta.get("last_task_status") or "").strip(),
                "last_task_result_status": str(meta.get("last_task_result_status") or "").strip(),
                "last_task_reason": str(meta.get("last_task_reason") or "").strip(),
                "last_task_gate": str(meta.get("last_task_gate") or "").strip(),
                "last_task_approval_id": str(meta.get("last_task_approval_id") or "").strip(),
                "last_task_previous_approval_id": str(meta.get("last_task_previous_approval_id") or "").strip(),
                "last_task_approval_status": str(meta.get("last_task_approval_status") or "").strip(),
                "last_task_next_step": str(meta.get("last_task_next_step") or "").strip(),
                "last_task_updated_at": str(meta.get("last_task_updated_at") or "").strip(),
                "last_advance_action": str(meta.get("last_advance_action") or "").strip(),
                "last_advance_outcome": str(meta.get("last_advance_outcome") or "").strip(),
                "last_advance_operation_id": str(meta.get("last_advance_operation_id") or "").strip(),
                "last_advance_operation_status": str(meta.get("last_advance_operation_status") or "").strip(),
                "last_advance_message": str(meta.get("last_advance_message") or "").strip(),
                "last_advance_actor": str(meta.get("last_advance_actor") or "").strip(),
                "last_advance_applied": bool(meta.get("last_advance_applied")),
                "last_advance_at": str(meta.get("last_advance_at") or "").strip(),
                "created_at": record.created_at,
                "updated_at": record.updated_at,
                "terminal": status in _TERMINAL_MISSION_STATUSES,
                "_sort_ts": _parse_ts(record.updated_at) or _parse_ts(record.created_at),
            }
        )

    recent.sort(key=lambda item: (float(item.get("_sort_ts") or 0.0), str(item.get("id") or "")), reverse=True)
    trimmed: list[dict[str, Any]] = []
    for item in recent[: max(0, int(limit))]:
        clean = dict(item)
        clean.pop("_sort_ts", None)
        trimmed.append(clean)

    return {
        "status_counts": status_counts,
        "recent": trimmed,
    }


def _mission_hold_projection(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "last_task_approval_id": str(item.get("last_task_approval_id") or "").strip(),
        "last_task_previous_approval_id": str(item.get("last_task_previous_approval_id") or "").strip(),
        "last_task_approval_status": str(item.get("last_task_approval_status") or "").strip(),
    }


def _activity_sort_key(item: dict[str, Any]) -> tuple[float, int, str]:
    return (
        float(item.get("ts") or 0.0),
        int(item.get("_seq") or 0),
        str(item.get("operation_id") or ""),
    )


def _operation_latest_activity(
    operation_id: str,
    *,
    log_limit: int = 20,
    cache: dict[str, dict[str, Any] | None] | None = None,
) -> dict[str, Any]:
    op_id = str(operation_id or "").strip()
    if not op_id:
        return {}
    if cache is not None and op_id in cache:
        cached = cache.get(op_id) or {}
        return dict(cached) if isinstance(cached, dict) else {}

    detail = operations_runtime.get_operation_detail(op_id, include_logs=True, log_limit=log_limit)
    if not bool(detail.get("ok")):
        if cache is not None:
            cache[op_id] = None
        return {}

    operation = detail.get("operation") if isinstance(detail.get("operation"), dict) else {}
    logs = detail.get("logs") if isinstance(detail.get("logs"), list) else []
    latest: dict[str, Any] = {}

    for seq, log in enumerate(logs):
        if not isinstance(log, dict):
            continue
        meta = log.get("meta") if isinstance(log.get("meta"), dict) else {}
        candidate = {
            "source": "run_ledger",
            "operation_id": op_id,
            "operation_name": str(operation.get("name") or "").strip(),
            "operation_status": str(operation.get("status") or "").strip(),
            "id": str(log.get("id") or "").strip(),
            "kind": str(log.get("kind") or "").strip(),
            "name": str(log.get("name") or "").strip(),
            "status": str(log.get("status") or "").strip(),
            "level": str(log.get("level") or "").strip(),
            "ts": int(log.get("ts") or 0),
            "reason": str(meta.get("reason") or "").strip(),
            "gate": str(meta.get("gate") or "").strip(),
            "next_step": str(meta.get("next_step") or "").strip(),
            "_seq": seq,
        }
        if not latest or _activity_sort_key(candidate) > _activity_sort_key(latest):
            latest = candidate

    if not latest and operation:
        op_meta = operation.get("meta") if isinstance(operation.get("meta"), dict) else {}
        latest = {
            "source": "operation_state",
            "operation_id": op_id,
            "operation_name": str(operation.get("name") or "").strip(),
            "operation_status": str(operation.get("status") or "").strip(),
            "id": f"{op_id}:state",
            "kind": str(operation.get("kind") or "").strip() or "delegated_task",
            "name": "operation_state",
            "status": str(operation.get("status") or "").strip(),
            "level": str(operation.get("level") or "").strip() or "info",
            "ts": int(operation.get("ts") or 0),
            "reason": str(operation.get("error") or op_meta.get("result_message") or "").strip(),
            "gate": "",
            "next_step": "",
            "_seq": -1,
        }

    if latest:
        latest.pop("_seq", None)
    if cache is not None:
        cache[op_id] = dict(latest) if latest else None
    return dict(latest) if latest else {}


def _mission_operation_ids(item: dict[str, Any]) -> list[str]:
    candidates: list[str] = []
    seen: set[str] = set()

    linked_task_ids = item.get("linked_task_ids")
    if isinstance(linked_task_ids, list):
        for task_id in linked_task_ids:
            value = str(task_id or "").strip()
            if value and value not in seen:
                seen.add(value)
                candidates.append(value)

    for field in ("last_task_id", "last_advance_operation_id", "action_target_id"):
        value = str(item.get(field) or "").strip()
        if value and value not in seen:
            seen.add(value)
            candidates.append(value)

    return candidates


def _attach_mission_activity(
    items: list[dict[str, Any]],
    *,
    log_limit: int = 20,
    cache: dict[str, dict[str, Any] | None] | None = None,
) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        latest: dict[str, Any] = {}
        for operation_id in _mission_operation_ids(item):
            activity = _operation_latest_activity(operation_id, log_limit=log_limit, cache=cache)
            if activity and (not latest or _activity_sort_key(activity) > _activity_sort_key(latest)):
                latest = activity
        enriched_item = dict(item)
        enriched_item["latest_activity"] = latest
        enriched.append(enriched_item)
    return enriched


def _mission_briefing(
    mission_status_counts: dict[str, Any],
    mission_queue: list[dict[str, Any]],
    deadletter_missions: list[dict[str, Any]],
    recent_missions: list[dict[str, Any]],
) -> dict[str, Any]:
    blocked = int(mission_status_counts.get("blocked") or 0)
    queued = int(mission_status_counts.get("queued") or 0)
    active = int(mission_status_counts.get("active") or 0)
    completed = int(mission_status_counts.get("completed") or 0)
    deadlettered = int(mission_status_counts.get("deadlettered") or 0)

    headline_parts: list[str] = []
    if blocked > 0:
        headline_parts.append(f"{blocked} blocked mission(s) need operator action.")
    elif queued > 0:
        headline_parts.append(f"{queued} queued mission(s) are ready for governed advancement.")
    elif active > 0:
        headline_parts.append(f"{active} mission(s) are currently in flight.")
    elif completed > 0:
        headline_parts.append(f"{completed} mission(s) have completed.")
    else:
        headline_parts.append("No mission backlog is currently active.")

    if deadlettered > 0:
        headline_parts.append(f"{deadlettered} mission(s) are sitting in deadletter.")

    focus_items: list[dict[str, Any]] = []
    for item in mission_queue[:3]:
        if not isinstance(item, dict):
            continue
        focus_items.append(
            {
                "id": str(item.get("id") or "").strip(),
                "status": str(item.get("status") or "").strip(),
                "objective": str(item.get("objective") or "").strip(),
                "summary": str(item.get("summary") or "").strip(),
                "next_step": str(item.get("next_step") or "").strip(),
                "priority": int(item.get("priority") or 0),
                "risk_tier": str(item.get("risk_tier") or "").strip(),
                "linked_task_count": int(item.get("linked_task_count") or 0),
                "recommended_action": str(item.get("recommended_action") or "").strip(),
                "operator_hint": str(item.get("operator_hint") or "").strip(),
                "action_target_id": str(item.get("action_target_id") or "").strip(),
                "last_task_id": str(item.get("last_task_id") or "").strip(),
                "last_task_status": str(item.get("last_task_status") or "").strip(),
                "last_task_result_status": str(item.get("last_task_result_status") or "").strip(),
                "last_task_gate": str(item.get("last_task_gate") or "").strip(),
                **_mission_hold_projection(item),
                "last_advance_action": str(item.get("last_advance_action") or "").strip(),
                "last_advance_outcome": str(item.get("last_advance_outcome") or "").strip(),
                "last_advance_operation_id": str(item.get("last_advance_operation_id") or "").strip(),
                "last_advance_operation_status": str(item.get("last_advance_operation_status") or "").strip(),
                "last_advance_message": str(item.get("last_advance_message") or "").strip(),
                "last_advance_actor": str(item.get("last_advance_actor") or "").strip(),
                "last_advance_applied": bool(item.get("last_advance_applied")),
                "last_advance_at": str(item.get("last_advance_at") or "").strip(),
                "deadletter_reason": str(item.get("deadletter_reason") or "").strip(),
                "updated_at": str(item.get("updated_at") or "").strip(),
                "latest_activity": dict(item.get("latest_activity") or {})
                if isinstance(item.get("latest_activity"), dict)
                else {},
            }
        )

    recently_completed: list[dict[str, Any]] = []
    for item in recent_missions:
        if not isinstance(item, dict):
            continue
        if str(item.get("status") or "").strip().lower() != "completed":
            continue
        recently_completed.append(
            {
                "id": str(item.get("id") or "").strip(),
                "objective": str(item.get("objective") or "").strip(),
                "updated_at": str(item.get("updated_at") or "").strip(),
                "last_task_id": str(item.get("last_task_id") or "").strip(),
                **_mission_hold_projection(item),
                "last_advance_action": str(item.get("last_advance_action") or "").strip(),
                "last_advance_outcome": str(item.get("last_advance_outcome") or "").strip(),
                "latest_activity": dict(item.get("latest_activity") or {})
                if isinstance(item.get("latest_activity"), dict)
                else {},
            }
        )
        if len(recently_completed) >= 2:
            break

    deadletter_preview: list[dict[str, Any]] = []
    for item in deadletter_missions[:2]:
        if not isinstance(item, dict):
            continue
        deadletter_preview.append(
            {
                "id": str(item.get("id") or "").strip(),
                "objective": str(item.get("objective") or "").strip(),
                "reason": str(item.get("deadletter_reason") or "").strip(),
                "recommended_action": str(item.get("recommended_action") or "").strip(),
                **_mission_hold_projection(item),
                "updated_at": str(item.get("updated_at") or "").strip(),
                "latest_activity": dict(item.get("latest_activity") or {})
                if isinstance(item.get("latest_activity"), dict)
                else {},
            }
        )

    return {
        "headline": " ".join(part for part in headline_parts if part).strip(),
        "counts": {
            "blocked": blocked,
            "queued": queued,
            "active": active,
            "completed": completed,
            "deadlettered": deadlettered,
        },
        "focus": focus_items,
        "recently_completed": recently_completed,
        "deadletter_preview": deadletter_preview,
    }


def mission_continuity_snapshot(
    *,
    recent_limit: int = 10,
    queue_limit: int = 5,
    deadletter_limit: int = 5,
    activity_log_limit: int = 20,
) -> dict[str, Any]:
    mission_summary = _mission_summary(limit=recent_limit)
    mission_status_counts = (
        mission_summary["status_counts"] if isinstance(mission_summary.get("status_counts"), dict) else {}
    )
    recent_missions = mission_summary["recent"] if isinstance(mission_summary.get("recent"), list) else []
    mission_queue = mission_store.mission_queue_items(limit=queue_limit, include_terminal=False)
    deadletter_missions = mission_store.deadletter_queue_items(limit=deadletter_limit)

    activity_cache: dict[str, dict[str, Any] | None] = {}
    recent_missions = _attach_mission_activity(recent_missions, log_limit=activity_log_limit, cache=activity_cache)
    mission_queue = _attach_mission_activity(mission_queue, log_limit=activity_log_limit, cache=activity_cache)
    deadletter_missions = _attach_mission_activity(
        deadletter_missions, log_limit=activity_log_limit, cache=activity_cache
    )
    mission_briefing = _mission_briefing(
        mission_status_counts,
        mission_queue,
        deadletter_missions,
        recent_missions,
    )

    return {
        "mission_status_counts": mission_status_counts,
        "recent_missions": recent_missions,
        "mission_queue": mission_queue,
        "deadletter_missions": deadletter_missions,
        "mission_briefing": mission_briefing,
    }


def _pending_approval_summary(path: Path, limit: int = 10) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        candidates = sorted(path.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)[
            : max(0, int(limit))
        ]
    except Exception:
        return []

    out: list[dict[str, Any]] = []
    for record_path in candidates:
        record = _read_json(record_path)
        if not record:
            continue
        out.append(
            {
                "id": str(record.get("id") or "").strip(),
                "action": str(record.get("action") or "").strip(),
                "reason": str(record.get("reason") or "").strip(),
                "status": str(record.get("status") or "").strip(),
                "ts": float(record.get("ts") or 0.0),
                **approval_projection_fields(record),
            }
        )
    return out


def _path_state(path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "exists": path.exists(),
        "is_dir": path.is_dir(),
    }


def _incident_record(
    incident_id: str,
    *,
    severity: str,
    category: str,
    title: str,
    detail: str,
    source: str,
    count: int = 0,
    approval_id: str = "",
    task_id: str = "",
    probe: str = "",
    observed_at: float = 0.0,
    evidence: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    record = {
        "id": incident_id,
        "severity": severity,
        "category": category,
        "status": "active",
        "title": title,
        "detail": detail,
        "source": source,
        "count": max(0, int(count)),
        "approval_id": approval_id,
        "task_id": task_id,
    }
    if probe:
        record["probe"] = probe
    cleaned_evidence = [dict(item) for item in (evidence or []) if isinstance(item, dict)]
    if cleaned_evidence:
        record["evidence"] = cleaned_evidence
    return record


def _incident_evidence_item(
    kind: str,
    *,
    evidence_id: str = "",
    label: str = "",
    status: str = "",
    detail: str = "",
    path: str = "",
    ts: float = 0.0,
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "kind": str(kind or "").strip(),
        "id": str(evidence_id or "").strip(),
        "label": str(label or "").strip(),
        "status": str(status or "").strip(),
        "detail": str(detail or "").strip(),
        "path": str(path or "").strip(),
    }
    if ts > 0:
        item["ts"] = ts
    return {key: value for key, value in item.items() if value not in {"", None}}


def _first_task_for_status(recent_tasks: list[dict[str, Any]], status: str) -> dict[str, Any]:
    for item in recent_tasks:
        if str(item.get("status") or "").strip().lower() == status:
            return item
    return {}


def _stack_incidents(stack_report: dict[str, Any], *, observed_at: float) -> list[dict[str, Any]]:
    items = stack_report.get("items")
    if not isinstance(items, list):
        return []

    missing_core = [
        item
        for item in items
        if isinstance(item, dict)
        and item.get("status") == "missing"
        and str(item.get("kind") or "").strip().lower() in {"root", "code", "config", "state"}
    ]
    if not missing_core:
        return []

    labels = [str(item.get("name") or item.get("kind") or "unknown").strip() for item in missing_core]
    labels = [label for label in labels if label]
    preview = ", ".join(labels[:3])
    if len(labels) > 3:
        preview = f"{preview}, +{len(labels) - 3} more"
    evidence = [
        _incident_evidence_item(
            "stack_item",
            evidence_id=str(item.get("name") or item.get("kind") or "").strip(),
            label=str(item.get("name") or item.get("kind") or "").strip(),
            status=str(item.get("status") or "").strip(),
            detail=f"{str(item.get('kind') or 'surface').strip()} surface missing",
            path=str(item.get("path") or "").strip(),
        )
        for item in missing_core[:3]
        if isinstance(item, dict)
    ]
    return [
        _incident_record(
            "runtime.stack_missing",
            severity="critical",
            category="runtime",
            title="Core stack surfaces are missing",
            detail=f"Missing stack surfaces: {preview}.",
            source="stack",
            count=len(labels),
            probe="stack_status",
            observed_at=observed_at,
            evidence=evidence,
        )
    ]


def _service_incidents(services_report: dict[str, Any], *, observed_at: float) -> list[dict[str, Any]]:
    items = services_report.get("services")
    if not isinstance(items, list):
        return []

    degraded = [
        item
        for item in items
        if isinstance(item, dict) and str(item.get("status") or "").strip().lower() in {"missing", "disabled"}
    ]
    if not degraded:
        return []

    missing = [
        str(item.get("name") or "").strip()
        for item in degraded
        if str(item.get("status") or "").strip().lower() == "missing"
    ]
    disabled = [
        str(item.get("name") or "").strip()
        for item in degraded
        if str(item.get("status") or "").strip().lower() == "disabled"
    ]
    missing = [item for item in missing if item]
    disabled = [item for item in disabled if item]

    parts: list[str] = []
    if missing:
        preview = ", ".join(missing[:3])
        if len(missing) > 3:
            preview = f"{preview}, +{len(missing) - 3} more"
        parts.append(f"missing: {preview}")
    if disabled:
        preview = ", ".join(disabled[:3])
        if len(disabled) > 3:
            preview = f"{preview}, +{len(disabled) - 3} more"
        parts.append(f"disabled: {preview}")
    evidence = [
        _incident_evidence_item(
            "service",
            evidence_id=str(item.get("name") or "").strip(),
            label=str(item.get("name") or "").strip(),
            status=str(item.get("status") or "").strip(),
            detail=f"service marked {str(item.get('status') or 'unknown').strip()}",
            path=str(item.get("path") or "").strip(),
        )
        for item in degraded[:3]
        if isinstance(item, dict)
    ]

    return [
        _incident_record(
            "runtime.services_degraded",
            severity="critical" if missing else "warning",
            category="runtime",
            title="Service surfaces need attention",
            detail="; ".join(parts) or "One or more services are not ready.",
            source="services",
            count=len(degraded),
            probe="services_status",
            observed_at=observed_at,
            evidence=evidence,
        )
    ]


def _governance_incidents(
    pending_approvals: list[dict[str, Any]],
    task_status_counts: dict[str, Any],
    recent_tasks: list[dict[str, Any]],
    *,
    observed_at: float,
) -> list[dict[str, Any]]:
    incidents: list[dict[str, Any]] = []

    pending_approval_count = int(task_status_counts.get("needs_approval") or 0)
    blocked_count = int(task_status_counts.get("blocked") or 0)
    failed_count = int(task_status_counts.get("failed") or 0)
    queued_approval_count = len(pending_approvals)

    if queued_approval_count > 0:
        approval_id = str((pending_approvals[0] or {}).get("id") or "").strip()
        evidence = [
            _incident_evidence_item(
                "approval",
                evidence_id=str(item.get("id") or "").strip(),
                label=str(item.get("action") or "").strip() or str(item.get("id") or "").strip(),
                status=str(item.get("status") or "").strip(),
                detail=str(item.get("reason") or "").strip(),
                ts=_parse_ts(item.get("ts")),
            )
            for item in pending_approvals[:3]
            if isinstance(item, dict)
        ]
        incidents.append(
            _incident_record(
                "governance.pending_approvals",
                severity="warning",
                category="governance",
                title="Approvals are waiting on operator review",
                detail=f"{queued_approval_count} pending approval(s) are queued for a decision.",
                source="approvals",
                count=queued_approval_count,
                approval_id=approval_id,
                probe="approval_queue",
                observed_at=observed_at,
                evidence=evidence,
            )
        )

    if pending_approval_count > 0:
        task = _first_task_for_status(recent_tasks, "needs_approval")
        evidence = []
        if task:
            evidence.append(
                _incident_evidence_item(
                    "task",
                    evidence_id=str(task.get("id") or "").strip(),
                    label=str(task.get("objective") or task.get("capability") or task.get("id") or "").strip(),
                    status=str(task.get("status") or "").strip(),
                    detail=str(task.get("status_reason") or "").strip(),
                    ts=_parse_ts(task.get("updated_at")),
                )
            )
        if pending_approvals:
            first_pending = pending_approvals[0]
            if isinstance(first_pending, dict):
                evidence.append(
                    _incident_evidence_item(
                        "approval",
                        evidence_id=str(first_pending.get("id") or "").strip(),
                        label=str(first_pending.get("action") or "").strip()
                        or str(first_pending.get("id") or "").strip(),
                        status=str(first_pending.get("status") or "").strip(),
                        detail=str(first_pending.get("reason") or "").strip(),
                        ts=_parse_ts(first_pending.get("ts")),
                    )
                )
        incidents.append(
            _incident_record(
                "governance.awaiting_approval",
                severity="warning",
                category="governance",
                title="Tasks are paused behind approval gates",
                detail=f"{pending_approval_count} task(s) cannot proceed until approval is granted.",
                source="tasks",
                count=pending_approval_count,
                task_id=str(task.get("id") or "").strip(),
                probe="task_runtime",
                observed_at=observed_at,
                evidence=evidence,
            )
        )

    if blocked_count > 0:
        task = _first_task_for_status(recent_tasks, "blocked")
        detail = str(task.get("status_reason") or "").strip() or "Policy or trust gates blocked execution."
        evidence = []
        if task:
            evidence.append(
                _incident_evidence_item(
                    "task",
                    evidence_id=str(task.get("id") or "").strip(),
                    label=str(task.get("objective") or task.get("capability") or task.get("id") or "").strip(),
                    status=str(task.get("status") or "").strip(),
                    detail=detail,
                    ts=_parse_ts(task.get("updated_at")),
                )
            )
        incidents.append(
            _incident_record(
                "governance.blocked_tasks",
                severity="error",
                category="governance",
                title="Tasks are blocked by governance",
                detail=f"{blocked_count} task(s) are blocked. {detail}",
                source="tasks",
                count=blocked_count,
                task_id=str(task.get("id") or "").strip(),
                probe="task_runtime",
                observed_at=observed_at,
                evidence=evidence,
            )
        )

    if failed_count > 0:
        task = _first_task_for_status(recent_tasks, "failed")
        detail = str(task.get("status_reason") or "").strip() or "Execution failed and needs review."
        evidence = []
        if task:
            evidence.append(
                _incident_evidence_item(
                    "task",
                    evidence_id=str(task.get("id") or "").strip(),
                    label=str(task.get("objective") or task.get("capability") or task.get("id") or "").strip(),
                    status=str(task.get("status") or "").strip(),
                    detail=detail,
                    ts=_parse_ts(task.get("updated_at")),
                )
            )
        incidents.append(
            _incident_record(
                "execution.failed_tasks",
                severity="error",
                category="execution",
                title="Recent task failures need review",
                detail=f"{failed_count} task(s) failed. {detail}",
                source="tasks",
                count=failed_count,
                task_id=str(task.get("id") or "").strip(),
                probe="task_runtime",
                observed_at=observed_at,
                evidence=evidence,
            )
        )

    incidents.sort(
        key=lambda item: (
            _INCIDENT_SEVERITY_ORDER.get(str(item.get("severity") or "").strip().lower(), 99),
            -int(item.get("count") or 0),
            str(item.get("id") or ""),
        )
    )
    return incidents


def observer_incident_snapshot() -> dict[str, Any]:
    data = data_dir()
    approvals_root = data / "approvals"
    tasks_root = data / "tasks"
    generated_at = time.time()

    stack_report = stack_status()
    services_report = services_status()
    task_summary = _task_summary(tasks_root)
    task_status_counts = task_summary["status_counts"] if isinstance(task_summary.get("status_counts"), dict) else {}
    recent_tasks = task_summary["recent"] if isinstance(task_summary.get("recent"), list) else []
    pending_approval_items = _pending_approval_summary(approvals_root / "pending")

    incidents = [
        *_stack_incidents(stack_report, observed_at=generated_at),
        *_service_incidents(services_report, observed_at=generated_at),
        *_governance_incidents(
            pending_approval_items,
            task_status_counts,
            recent_tasks,
            observed_at=generated_at,
        ),
    ]

    return {
        "ok": True,
        "subsystem": "observer_incidents",
        "generated_at": generated_at,
        "stack": stack_report,
        "services": services_report,
        "task_status_counts": task_status_counts,
        "recent_tasks": recent_tasks,
        "pending_approvals": pending_approval_items,
        "incidents": incidents,
    }


def snapshot() -> dict[str, Any]:
    root = repo_root()
    data = data_dir()

    approvals_root = data / "approvals"
    tasks_root = data / "tasks"
    missions_root = data / "missions"
    logs_root = data / "logs"
    plugins_root = root / "plugins" / "generated"
    observer = observer_incident_snapshot()
    generated_at = float(observer.get("generated_at") or time.time())
    stack_report = observer.get("stack") if isinstance(observer.get("stack"), dict) else {}
    services_report = observer.get("services") if isinstance(observer.get("services"), dict) else {}
    task_status_counts = (
        observer.get("task_status_counts") if isinstance(observer.get("task_status_counts"), dict) else {}
    )
    recent_tasks = observer.get("recent_tasks") if isinstance(observer.get("recent_tasks"), list) else []
    continuity = mission_continuity_snapshot()
    mission_status_counts = (
        continuity["mission_status_counts"] if isinstance(continuity.get("mission_status_counts"), dict) else {}
    )
    recent_missions = continuity["recent_missions"] if isinstance(continuity.get("recent_missions"), list) else []
    mission_queue = continuity["mission_queue"] if isinstance(continuity.get("mission_queue"), list) else []
    deadletter_missions = (
        continuity["deadletter_missions"] if isinstance(continuity.get("deadletter_missions"), list) else []
    )
    mission_briefing = continuity["mission_briefing"] if isinstance(continuity.get("mission_briefing"), dict) else {}
    pending_approval_items = (
        observer.get("pending_approvals") if isinstance(observer.get("pending_approvals"), list) else []
    )
    pending_approvals = _count_json_entries(approvals_root / "pending")
    incidents = observer.get("incidents") if isinstance(observer.get("incidents"), list) else []

    return {
        "ok": True,
        "subsystem": "world_state",
        "generated_at": generated_at,
        "repo_root": str(root),
        "data_dir": str(data),
        "trust": get_state(),
        "stack": stack_report,
        "services": services_report,
        "feature_flags": list_flags(),
        "paths": {
            "data": _path_state(data),
            "logs": _path_state(logs_root),
            "tasks": _path_state(tasks_root),
            "missions": _path_state(missions_root),
            "approvals": _path_state(approvals_root),
            "plugins_generated": _path_state(plugins_root),
        },
        "counts": {
            "pending_approvals": pending_approvals,
            "approved_approvals": _count_json_entries(approvals_root / "approved"),
            "rejected_approvals": _count_json_entries(approvals_root / "rejected"),
            "tasks": _count_task_records(tasks_root),
            "queued_tasks": int(task_status_counts.get("pending") or 0) + int(task_status_counts.get("accepted") or 0),
            "approval_pending_tasks": int(task_status_counts.get("needs_approval") or 0),
            "blocked_tasks": int(task_status_counts.get("blocked") or 0),
            "running_tasks": int(task_status_counts.get("running") or 0),
            "missions": sum(int(value or 0) for value in mission_status_counts.values()),
            "queued_missions": int(mission_status_counts.get("queued") or 0),
            "active_missions": int(mission_status_counts.get("active") or 0),
            "blocked_missions": int(mission_status_counts.get("blocked") or 0),
            "deadlettered_missions": int(mission_status_counts.get("deadlettered") or 0),
            "active_incidents": len(incidents),
            "generated_plugins": _count_json_entries(plugins_root),
        },
        "overview": {
            "pending_approvals": pending_approval_items,
            "task_status_counts": task_status_counts,
            "recent_tasks": recent_tasks,
            "mission_status_counts": mission_status_counts,
            "recent_missions": recent_missions,
            "mission_queue": mission_queue,
            "deadletter_missions": deadletter_missions,
            "mission_briefing": mission_briefing,
            "incidents": incidents,
        },
    }
