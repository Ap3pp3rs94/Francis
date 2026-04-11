from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from francis.kernel.feature_flags import list_flags
from francis.kernel.paths import data_dir, repo_root
from francis.kernel.services import services_status
from francis.kernel.stack import stack_status
from francis.missions import store as mission_store
from francis.trust.levels import get_state


_TERMINAL_TASK_STATUSES = {"completed", "failed", "cancelled"}
_TERMINAL_MISSION_STATUSES = {"completed", "failed", "deadlettered", "cancelled"}
_INCIDENT_SEVERITY_ORDER = {"critical": 0, "error": 1, "warning": 2, "info": 3}


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
                "last_task_next_step": str(meta.get("last_task_next_step") or "").strip(),
                "last_task_updated_at": str(meta.get("last_task_updated_at") or "").strip(),
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


def _pending_approval_summary(path: Path, limit: int = 10) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        candidates = sorted(path.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)[: max(0, int(limit))]
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
) -> dict[str, Any]:
    return {
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


def _first_task_for_status(recent_tasks: list[dict[str, Any]], status: str) -> dict[str, Any]:
    for item in recent_tasks:
        if str(item.get("status") or "").strip().lower() == status:
            return item
    return {}


def _stack_incidents(stack_report: dict[str, Any]) -> list[dict[str, Any]]:
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
    return [
        _incident_record(
            "runtime.stack_missing",
            severity="critical",
            category="runtime",
            title="Core stack surfaces are missing",
            detail=f"Missing stack surfaces: {preview}.",
            source="stack",
            count=len(labels),
        )
    ]


def _service_incidents(services_report: dict[str, Any]) -> list[dict[str, Any]]:
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

    missing = [str(item.get("name") or "").strip() for item in degraded if str(item.get("status") or "").strip().lower() == "missing"]
    disabled = [str(item.get("name") or "").strip() for item in degraded if str(item.get("status") or "").strip().lower() == "disabled"]
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

    return [
        _incident_record(
            "runtime.services_degraded",
            severity="critical" if missing else "warning",
            category="runtime",
            title="Service surfaces need attention",
            detail="; ".join(parts) or "One or more services are not ready.",
            source="services",
            count=len(degraded),
        )
    ]


def _governance_incidents(
    pending_approvals: list[dict[str, Any]],
    task_status_counts: dict[str, Any],
    recent_tasks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    incidents: list[dict[str, Any]] = []

    pending_approval_count = int(task_status_counts.get("needs_approval") or 0)
    blocked_count = int(task_status_counts.get("blocked") or 0)
    failed_count = int(task_status_counts.get("failed") or 0)
    queued_approval_count = len(pending_approvals)

    if queued_approval_count > 0:
        approval_id = str((pending_approvals[0] or {}).get("id") or "").strip()
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
            )
        )

    if pending_approval_count > 0:
        task = _first_task_for_status(recent_tasks, "needs_approval")
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
            )
        )

    if blocked_count > 0:
        task = _first_task_for_status(recent_tasks, "blocked")
        detail = str(task.get("status_reason") or "").strip() or "Policy or trust gates blocked execution."
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
            )
        )

    if failed_count > 0:
        task = _first_task_for_status(recent_tasks, "failed")
        detail = str(task.get("status_reason") or "").strip() or "Execution failed and needs review."
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


def snapshot() -> dict[str, Any]:
    root = repo_root()
    data = data_dir()

    approvals_root = data / "approvals"
    tasks_root = data / "tasks"
    missions_root = data / "missions"
    logs_root = data / "logs"
    plugins_root = root / "plugins" / "generated"
    stack_report = stack_status()
    services_report = services_status()
    task_summary = _task_summary(tasks_root)
    mission_summary = _mission_summary()
    task_status_counts = task_summary["status_counts"] if isinstance(task_summary.get("status_counts"), dict) else {}
    recent_tasks = task_summary["recent"] if isinstance(task_summary.get("recent"), list) else []
    mission_status_counts = mission_summary["status_counts"] if isinstance(mission_summary.get("status_counts"), dict) else {}
    recent_missions = mission_summary["recent"] if isinstance(mission_summary.get("recent"), list) else []
    mission_queue = mission_store.mission_queue_items(limit=5, include_terminal=False)
    deadletter_missions = mission_store.deadletter_queue_items(limit=5)
    pending_approval_items = _pending_approval_summary(approvals_root / "pending")
    pending_approvals = _count_json_entries(approvals_root / "pending")
    incidents = [
        *_stack_incidents(stack_report),
        *_service_incidents(services_report),
        *_governance_incidents(pending_approval_items, task_status_counts, recent_tasks),
    ]

    return {
        "ok": True,
        "subsystem": "world_state",
        "generated_at": time.time(),
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
            "incidents": incidents,
        },
    }
