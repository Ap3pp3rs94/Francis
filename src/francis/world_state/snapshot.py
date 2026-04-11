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
from francis.trust.levels import get_state


_TERMINAL_TASK_STATUSES = {"completed", "failed", "cancelled"}


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
        "running": 0,
        "completed": 0,
        "failed": 0,
        "cancelled": 0,
        "unknown": 0,
    }
    recent: list[dict[str, Any]] = []
    for record in _iter_task_records(path):
        status = _normalize_task_status(record.get("status"))
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
                "status_reason": str(record.get("status_reason") or "").strip(),
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


def snapshot() -> dict[str, Any]:
    root = repo_root()
    data = data_dir()

    approvals_root = data / "approvals"
    tasks_root = data / "tasks"
    logs_root = data / "logs"
    plugins_root = root / "plugins" / "generated"
    task_summary = _task_summary(tasks_root)

    return {
        "ok": True,
        "subsystem": "world_state",
        "generated_at": time.time(),
        "repo_root": str(root),
        "data_dir": str(data),
        "trust": get_state(),
        "stack": stack_status(),
        "services": services_status(),
        "feature_flags": list_flags(),
        "paths": {
            "data": _path_state(data),
            "logs": _path_state(logs_root),
            "tasks": _path_state(tasks_root),
            "approvals": _path_state(approvals_root),
            "plugins_generated": _path_state(plugins_root),
        },
        "counts": {
            "pending_approvals": _count_json_entries(approvals_root / "pending"),
            "approved_approvals": _count_json_entries(approvals_root / "approved"),
            "rejected_approvals": _count_json_entries(approvals_root / "rejected"),
            "tasks": _count_task_records(tasks_root),
            "generated_plugins": _count_json_entries(plugins_root),
        },
        "overview": {
            "pending_approvals": _pending_approval_summary(approvals_root / "pending"),
            "task_status_counts": task_summary["status_counts"],
            "recent_tasks": task_summary["recent"],
        },
    }
