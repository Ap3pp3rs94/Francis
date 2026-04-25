from __future__ import annotations

import json
import os
import re
import secrets
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from francis.kernel.paths import data_dir

__all__ = [
    "AUTO_ADVANCE_ACTIONS",
    "RECOVERY_REVIEW_ACTIONS",
    "MissionStatus",
    "MissionCreateRequest",
    "MissionRecord",
    "create_mission",
    "create_replacement_mission",
    "deadletter_mission",
    "deadletter_queue_items",
    "failed_queue_items",
    "mission_queue_item",
    "mission_queue_items",
    "record_advance_receipt",
    "record_recovery_review_receipt",
    "record_linked_task_transition",
    "run_queue_once",
    "tick_all_missions",
    "tick_mission",
    "read_mission",
    "list_missions",
    "read_history",
    "update_mission",
    "link_task",
]


class MissionStatus(str, Enum):
    QUEUED = "queued"
    ACTIVE = "active"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"
    DEADLETTERED = "deadlettered"
    CANCELLED = "cancelled"


_STATUS_ALIASES: dict[str, str] = {
    "pending": MissionStatus.QUEUED.value,
    "queued": MissionStatus.QUEUED.value,
    "running": MissionStatus.ACTIVE.value,
    "active": MissionStatus.ACTIVE.value,
    "blocked": MissionStatus.BLOCKED.value,
    "complete": MissionStatus.COMPLETED.value,
    "completed": MissionStatus.COMPLETED.value,
    "failed": MissionStatus.FAILED.value,
    "deadletter": MissionStatus.DEADLETTERED.value,
    "deadlettered": MissionStatus.DEADLETTERED.value,
    "cancelled": MissionStatus.CANCELLED.value,
    "canceled": MissionStatus.CANCELLED.value,
}
_TERMINAL_STATUSES = {
    MissionStatus.COMPLETED,
    MissionStatus.FAILED,
    MissionStatus.DEADLETTERED,
    MissionStatus.CANCELLED,
}
_QUEUE_STATUS_ORDER = {
    MissionStatus.BLOCKED.value: 0,
    MissionStatus.QUEUED.value: 1,
    MissionStatus.FAILED.value: 2,
    MissionStatus.ACTIVE.value: 3,
    MissionStatus.COMPLETED.value: 9,
    MissionStatus.CANCELLED.value: 9,
    MissionStatus.DEADLETTERED.value: 10,
}
AUTO_ADVANCE_ACTIONS = frozenset({"create_first_operation", "run_linked_operation"})
RECOVERY_REVIEW_ACTIONS = frozenset({"retry_or_deadletter", "review_deadletter"})
_ID_RE = re.compile(r"^[a-zA-Z0-9_\-]{6,128}$")


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _coerce_status(value: Any) -> MissionStatus:
    if isinstance(value, MissionStatus):
        return value
    raw = str(value or MissionStatus.QUEUED.value).strip().lower()
    normalized = _STATUS_ALIASES.get(raw, MissionStatus.QUEUED.value)
    return MissionStatus(normalized)


def _normalize_task_status(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if raw == "complete":
        return "completed"
    if raw == "canceled":
        return "cancelled"
    return raw


def _parse_ts(value: Any) -> float:
    text = str(value or "").strip()
    if not text:
        return 0.0
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.timestamp()
    except Exception:
        return 0.0


def _missions_dir(repo_root: Path | None = None) -> Path:
    if repo_root is not None:
        return repo_root.resolve() / "data" / "missions"
    return data_dir() / "missions"


def _mission_dir(mission_id: str, repo_root: Path | None = None) -> Path:
    return _missions_dir(repo_root) / mission_id


def _record_path(mission_id: str, repo_root: Path | None = None) -> Path:
    return _mission_dir(mission_id, repo_root) / "record.json"


def _history_path(mission_id: str, repo_root: Path | None = None) -> Path:
    return _mission_dir(mission_id, repo_root) / "history.jsonl"


def _tasks_dir(repo_root: Path | None = None) -> Path:
    if repo_root is not None:
        return repo_root.resolve() / "data" / "tasks"
    return data_dir() / "tasks"


def _task_record_path(task_id: str, repo_root: Path | None = None) -> Path:
    return _tasks_dir(repo_root) / task_id / "record.json"


def _safe_mkdir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _atomic_write_text(path: Path, text: str) -> None:
    _safe_mkdir(path.parent)
    tmp = path.with_suffix(path.suffix + f".tmp_{secrets.token_hex(4)}")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _append_history(mission_id: str, event: str, details: dict[str, Any], repo_root: Path | None = None) -> None:
    line = {"ts": _now(), "mission_id": mission_id, "event": event, "details": details}
    path = _history_path(mission_id, repo_root)
    _safe_mkdir(path.parent)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(line, ensure_ascii=False, default=str) + "\n")


def _is_jsonable(value: Any, depth: int = 0) -> bool:
    if depth > 20:
        return False
    if value is None or isinstance(value, (bool, int, float, str)):
        return True
    if isinstance(value, (list, tuple)):
        return all(_is_jsonable(item, depth + 1) for item in value)
    if isinstance(value, dict):
        return all(isinstance(key, str) and _is_jsonable(item, depth + 1) for key, item in value.items())
    return False


def _normalize_task_ids(task_ids: list[str] | tuple[str, ...] | None) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in task_ids or []:
        value = str(item or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _new_mission_id() -> str:
    return f"msn_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}_{secrets.token_hex(4)}"


def _read_json_dict(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


def _linked_task_snapshot(task_id: str, repo_root: Path | None = None) -> dict[str, Any]:
    task = _read_json_dict(_task_record_path(task_id, repo_root))
    if not task:
        return {}
    result = task.get("result") if isinstance(task.get("result"), dict) else {}
    payload = result.get("data") if isinstance(result.get("data"), dict) else {}
    governance = payload.get("governance") if isinstance(payload.get("governance"), dict) else {}
    approval_id = str(payload.get("approval_id") or "").strip()
    previous_approval_id = str(payload.get("previous_approval_id") or "").strip()
    approval_status = str(governance.get("approval_status") or "").strip()
    updated_at = str(task.get("updated_at") or "")
    created_at = str(task.get("created_at") or "")
    return {
        "task_id": str(task.get("task_id") or task_id).strip(),
        "task_status": _normalize_task_status(task.get("status")),
        "result_status": _normalize_task_status(payload.get("status")),
        "status_reason": str(task.get("status_reason") or payload.get("error") or payload.get("message") or "").strip(),
        "gate": str(governance.get("gate") or "").strip(),
        "approval_id": approval_id,
        "previous_approval_id": previous_approval_id,
        "approval_status": approval_status,
        "next_step": str(governance.get("next_step") or "").strip(),
        "updated_at": updated_at,
        "created_at": created_at,
        "_sort_ts": _parse_ts(updated_at) or _parse_ts(created_at),
    }


def _latest_linked_snapshot(task_ids: list[str], repo_root: Path | None = None) -> dict[str, Any]:
    snapshots = [_linked_task_snapshot(task_id, repo_root) for task_id in task_ids]
    snapshots = [item for item in snapshots if item]
    if not snapshots:
        return {}
    snapshots.sort(key=lambda item: (float(item.get("_sort_ts") or 0.0), str(item.get("task_id") or "")), reverse=True)
    latest = dict(snapshots[0])
    latest.pop("_sort_ts", None)
    return latest


def _derive_mission_status_from_tasks(
    task_ids: list[str], repo_root: Path | None = None
) -> tuple[MissionStatus | None, dict[str, Any]]:
    snapshots = [_linked_task_snapshot(task_id, repo_root) for task_id in task_ids]
    snapshots = [item for item in snapshots if item]
    if not snapshots:
        return None, {}

    blocked = [
        item
        for item in snapshots
        if str(item.get("result_status") or "").strip().lower() in {"pending", "needs_approval", "blocked", "denied"}
    ]
    if blocked:
        blocked.sort(
            key=lambda item: (float(item.get("_sort_ts") or 0.0), str(item.get("task_id") or "")), reverse=True
        )
        latest = dict(blocked[0])
        latest.pop("_sort_ts", None)
        return MissionStatus.BLOCKED, latest

    running = [item for item in snapshots if str(item.get("task_status") or "").strip().lower() == "running"]
    if running:
        running.sort(
            key=lambda item: (float(item.get("_sort_ts") or 0.0), str(item.get("task_id") or "")), reverse=True
        )
        latest = dict(running[0])
        latest.pop("_sort_ts", None)
        return MissionStatus.ACTIVE, latest

    queued = [
        item for item in snapshots if str(item.get("task_status") or "").strip().lower() in {"pending", "accepted"}
    ]
    if queued:
        queued.sort(key=lambda item: (float(item.get("_sort_ts") or 0.0), str(item.get("task_id") or "")), reverse=True)
        latest = dict(queued[0])
        latest.pop("_sort_ts", None)
        return MissionStatus.QUEUED, latest

    failed = [item for item in snapshots if str(item.get("task_status") or "").strip().lower() == "failed"]
    if failed:
        failed.sort(key=lambda item: (float(item.get("_sort_ts") or 0.0), str(item.get("task_id") or "")), reverse=True)
        latest = dict(failed[0])
        latest.pop("_sort_ts", None)
        return MissionStatus.FAILED, latest

    cancelled = [item for item in snapshots if str(item.get("task_status") or "").strip().lower() == "cancelled"]
    if cancelled and len(cancelled) == len(snapshots):
        cancelled.sort(
            key=lambda item: (float(item.get("_sort_ts") or 0.0), str(item.get("task_id") or "")), reverse=True
        )
        latest = dict(cancelled[0])
        latest.pop("_sort_ts", None)
        return MissionStatus.CANCELLED, latest

    completed = [item for item in snapshots if str(item.get("task_status") or "").strip().lower() == "completed"]
    if completed and len(completed) == len(snapshots):
        completed.sort(
            key=lambda item: (float(item.get("_sort_ts") or 0.0), str(item.get("task_id") or "")), reverse=True
        )
        latest = dict(completed[0])
        latest.pop("_sort_ts", None)
        return MissionStatus.COMPLETED, latest

    return None, _latest_linked_snapshot(task_ids, repo_root)


def _dependency_item(dependency_id: str, record: "MissionRecord", repo_root: Path | None = None) -> dict[str, Any]:
    cleaned = str(dependency_id or "").strip()
    if not cleaned:
        return {}

    if cleaned == record.mission_id:
        return {
            "id": cleaned,
            "kind": "mission",
            "state": "blocked",
            "status": "self_dependency",
            "detail": "Mission depends on itself and cannot advance until the dependency is removed.",
        }

    mission, _ = read_mission(cleaned, repo_root)
    if mission is not None:
        status = mission.status.value
        if mission.status == MissionStatus.COMPLETED:
            state = "resolved"
        elif mission.status in {MissionStatus.FAILED, MissionStatus.DEADLETTERED, MissionStatus.CANCELLED}:
            state = "blocked"
        else:
            state = "waiting"
        return {
            "id": cleaned,
            "kind": "mission",
            "state": state,
            "status": status,
            "objective": mission.objective,
            "updated_at": mission.updated_at,
        }

    task = _linked_task_snapshot(cleaned, repo_root)
    if task:
        task_status = str(task.get("task_status") or "").strip().lower()
        result_status = str(task.get("result_status") or "").strip().lower()
        if result_status in {"blocked", "denied"} or task_status in {"failed", "cancelled"}:
            state = "blocked"
        elif result_status in {"pending", "needs_approval"} or task_status in {"pending", "accepted", "running"}:
            state = "waiting"
        elif task_status == "completed":
            state = "resolved"
        else:
            state = "waiting"
        return {
            "id": cleaned,
            "kind": "operation",
            "state": state,
            "status": task_status or result_status or "unknown",
            "result_status": result_status,
            "gate": str(task.get("gate") or "").strip(),
            "approval_id": str(task.get("approval_id") or "").strip(),
            "updated_at": str(task.get("updated_at") or task.get("created_at") or "").strip(),
        }

    return {
        "id": cleaned,
        "kind": "unknown",
        "state": "missing",
        "status": "missing",
        "detail": "Dependency record was not found in mission or operation storage.",
    }


def _dependency_state(record: "MissionRecord", repo_root: Path | None = None) -> dict[str, Any]:
    items = [
        item
        for item in (_dependency_item(dependency_id, record, repo_root) for dependency_id in record.dependency_ids)
        if item
    ]
    unresolved = [item for item in items if str(item.get("state") or "").strip().lower() != "resolved"]
    blocked = [item for item in unresolved if str(item.get("state") or "").strip().lower() in {"blocked", "missing"}]
    if not unresolved:
        status = "clear"
    elif blocked:
        status = "blocked"
    else:
        status = "waiting"
    return {
        "status": status,
        "total": len(items),
        "resolved": len(items) - len(unresolved),
        "unresolved": len(unresolved),
        "items": items,
        "first_unresolved": unresolved[0] if unresolved else None,
    }


def _queue_sort_key(record: "MissionRecord") -> tuple[int, int, float, str]:
    status = str(record.status.value or "").strip().lower()
    status_rank = _QUEUE_STATUS_ORDER.get(status, 99)
    priority = int(record.priority or 0)
    updated_ts = _parse_ts(record.updated_at) or _parse_ts(record.created_at)
    return (status_rank, -priority, -updated_ts, record.mission_id)


def _queue_action(record: "MissionRecord", dependency_state: dict[str, Any] | None = None) -> tuple[str, str, str]:
    meta = dict(record.meta) if isinstance(record.meta, dict) else {}
    status = str(record.status.value or "").strip().lower()
    last_task_id = str(meta.get("last_task_id") or "").strip()
    last_task_result_status = str(meta.get("last_task_result_status") or "").strip().lower()
    last_task_gate = str(meta.get("last_task_gate") or "").strip().lower()
    last_task_approval_id = str(meta.get("last_task_approval_id") or "").strip()
    last_task_approval_status = str(meta.get("last_task_approval_status") or "").strip().lower()
    next_step = str(meta.get("last_task_next_step") or record.next_step or "").strip()

    if status in {MissionStatus.QUEUED.value, MissionStatus.ACTIVE.value}:
        dependency_payload = dependency_state if isinstance(dependency_state, dict) else {}
        first_unresolved = dependency_payload.get("first_unresolved")
        if isinstance(first_unresolved, dict):
            dependency_id = str(first_unresolved.get("id") or "").strip()
            dependency_kind = str(first_unresolved.get("kind") or "dependency").strip() or "dependency"
            dependency_status = str(first_unresolved.get("status") or "unresolved").strip() or "unresolved"
            dependency_state_value = str(first_unresolved.get("state") or "waiting").strip().lower()
            escalation = record.escalation_path.strip()
            hint = (
                f"Dependency {dependency_id or 'unknown'} is {dependency_state_value} "
                f"({dependency_kind} status {dependency_status}) before the mission can continue."
            )
            if escalation:
                hint = f"{hint} Escalation: {escalation}"
            if dependency_state_value in {"blocked", "missing"}:
                return "resolve_dependency_blocker", hint, dependency_id
            return "wait_for_dependency", hint, dependency_id

    if status == MissionStatus.BLOCKED.value:
        if last_task_gate == "approvals_gate" or last_task_result_status in {"pending", "needs_approval"}:
            approval_hint = ""
            if last_task_approval_id:
                approval_state = last_task_approval_status or "pending"
                approval_hint = f"Approval {last_task_approval_id} is {approval_state} before the mission can continue."
            return (
                "review_pending_approval",
                approval_hint or next_step or "A linked task is waiting on approval before the mission can continue.",
                last_task_id,
            )
        if last_task_gate == "trust_gate":
            return "raise_trust_or_reduce_risk", next_step or "A linked task is blocked by trust posture.", last_task_id
        return "resolve_blocker", next_step or "A linked task is blocked and needs operator intervention.", last_task_id

    if status == MissionStatus.QUEUED.value:
        if not record.linked_task_ids:
            return (
                "create_first_operation",
                next_step or "Mission has no linked work yet. Create the first governed operation.",
                "",
            )
        return (
            "run_linked_operation",
            next_step or "A linked task is queued but not advancing yet.",
            last_task_id or record.linked_task_ids[0],
        )

    if status == MissionStatus.ACTIVE.value:
        return (
            "observe_running_operation",
            next_step or "A linked task is already running. Observe before changing mission posture.",
            last_task_id,
        )

    if status == MissionStatus.FAILED.value:
        return (
            "retry_or_deadletter",
            next_step or "The latest linked task failed. Retry the work or deadletter the mission.",
            last_task_id,
        )

    if status == MissionStatus.DEADLETTERED.value:
        return "review_deadletter", record.deadletter_reason or "Mission has been deadlettered.", last_task_id

    if status == MissionStatus.COMPLETED.value:
        return (
            "review_completion",
            next_step or "Mission completed. Review outcome and decide whether follow-up work is needed.",
            last_task_id,
        )

    return "review_mission", next_step or "Mission needs operator review.", last_task_id


def _advance_projection(recommended_action: str, action_target_id: str, operator_hint: str) -> dict[str, Any]:
    action = str(recommended_action or "").strip()
    target_id = str(action_target_id or "").strip()
    eligible = action in AUTO_ADVANCE_ACTIONS
    reason = (
        "Mission queue item is eligible for one bounded advance through the governed mission runtime."
        if eligible
        else str(operator_hint or "").strip() or "Mission requires operator review before it can advance."
    )
    return {
        "eligible": eligible,
        "action": action,
        "target_id": target_id,
        "reason": reason,
    }


def _recovery_projection(
    record: "MissionRecord",
    *,
    recommended_action: str,
    action_target_id: str,
    operator_hint: str,
) -> dict[str, Any]:
    status = str(record.status.value or "").strip().lower()
    if status not in {MissionStatus.FAILED.value, MissionStatus.DEADLETTERED.value}:
        return {}

    meta = dict(record.meta) if isinstance(record.meta, dict) else {}
    target_id = str(action_target_id or "").strip()
    reason = _first_text(record.deadletter_reason, operator_hint, record.next_step)
    if status == MissionStatus.DEADLETTERED.value:
        next_step = (
            "Review mission receipts and declare replacement work if continuation is still needed; "
            "deadlettered missions are not reopened automatically."
        )
    else:
        next_step = (
            "Review the failed linked task, then retry through existing governed operation paths or "
            "deadletter the mission explicitly."
        )

    return {
        "source_status": status,
        "action": str(recommended_action or "").strip() or "review_mission",
        "target_id": target_id,
        "reason": reason or "Mission requires operator recovery review.",
        "next_step": next_step,
        "operator_required": True,
        "automatic_retry": False,
        "read_only": True,
        "last_review_action": str(meta.get("last_recovery_action") or "").strip(),
        "last_review_outcome": str(meta.get("last_recovery_outcome") or "").strip(),
        "last_review_target_id": str(meta.get("last_recovery_target_id") or "").strip(),
        "last_review_actor": str(meta.get("last_recovery_actor") or "").strip(),
        "last_reviewed_at": str(meta.get("last_recovery_at") or "").strip(),
    }


def _replacement_lineage_projection(meta: dict[str, Any]) -> dict[str, Any]:
    return {
        "replacement_for_mission_id": str(meta.get("replacement_for_mission_id") or "").strip(),
        "replacement_for_status": str(meta.get("replacement_for_status") or "").strip(),
        "replacement_source_objective": str(meta.get("replacement_source_objective") or "").strip(),
        "replacement_source_action": str(meta.get("replacement_source_action") or "").strip(),
        "replacement_source_target_id": str(meta.get("replacement_source_target_id") or "").strip(),
        "replacement_reason": str(meta.get("replacement_reason") or "").strip(),
        "replacement_declared_by": str(meta.get("replacement_declared_by") or "").strip(),
        "replacement_note": str(meta.get("replacement_note") or "").strip(),
    }


def _first_text(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _queue_current_task_projection(
    record: "MissionRecord",
    meta: dict[str, Any],
    *,
    recommended_action: str,
    operator_hint: str,
    action_target_id: str,
) -> dict[str, Any]:
    action_target = str(action_target_id or "").strip()
    last_task_id = str(meta.get("last_task_id") or "").strip()
    last_advance_operation_id = str(meta.get("last_advance_operation_id") or "").strip()
    has_meta_task = any(
        str(meta.get(key) or "").strip()
        for key in (
            "last_task_id",
            "last_task_status",
            "last_task_result_status",
            "last_task_reason",
            "last_task_gate",
            "last_task_next_step",
        )
    )
    operation_id = _first_text(
        last_task_id,
        action_target if action_target.startswith("tsk_") else "",
        last_advance_operation_id,
    )
    source = "mission_meta" if has_meta_task else "queue_item" if operation_id else "mission"
    payload: dict[str, Any] = {
        "mission_id": record.mission_id,
        "source": source,
    }
    values = {
        "operation_id": operation_id,
        "task_status": meta.get("last_task_status"),
        "operation_status": meta.get("last_advance_operation_status"),
        "result_status": meta.get("last_task_result_status"),
        "gate": meta.get("last_task_gate"),
        "next_step": _first_text(meta.get("last_task_next_step"), record.next_step),
        "reason": _first_text(meta.get("last_task_reason"), operator_hint),
        "approval_id": meta.get("last_task_approval_id"),
        "approval_status": meta.get("last_task_approval_status"),
        "handoff_action": recommended_action,
        "last_advance_operation_id": last_advance_operation_id,
    }
    for key, value in values.items():
        text = str(value or "").strip()
        if text:
            payload[key] = text
    return payload


def _queue_item(record: "MissionRecord", repo_root: Path | None = None) -> dict[str, Any]:
    meta = dict(record.meta) if isinstance(record.meta, dict) else {}
    dependency_state = _dependency_state(record, repo_root)
    recommended_action, operator_hint, action_target_id = _queue_action(record, dependency_state)
    history_summary = _history_summary(record.mission_id, repo_root)
    return {
        "id": record.mission_id,
        "status": record.status.value,
        "objective": record.objective,
        "summary": record.summary,
        "next_step": record.next_step,
        "owner_id": record.owner_id,
        "priority": int(record.priority or 0),
        "risk_tier": record.risk_tier,
        "dependency_ids": list(record.dependency_ids),
        "dependency_count": len(record.dependency_ids),
        "dependency_state": dependency_state,
        "escalation_path": record.escalation_path,
        "linked_task_count": len(record.linked_task_ids),
        "linked_task_ids": list(record.linked_task_ids),
        "last_task_id": str(meta.get("last_task_id") or "").strip(),
        "last_task_status": str(meta.get("last_task_status") or "").strip(),
        "last_task_result_status": str(meta.get("last_task_result_status") or "").strip(),
        "last_task_reason": str(meta.get("last_task_reason") or "").strip(),
        "last_task_gate": str(meta.get("last_task_gate") or "").strip(),
        "last_task_next_step": str(meta.get("last_task_next_step") or "").strip(),
        "last_task_approval_id": str(meta.get("last_task_approval_id") or "").strip(),
        "last_task_previous_approval_id": str(meta.get("last_task_previous_approval_id") or "").strip(),
        "last_task_approval_status": str(meta.get("last_task_approval_status") or "").strip(),
        "last_advance_action": str(meta.get("last_advance_action") or "").strip(),
        "last_advance_outcome": str(meta.get("last_advance_outcome") or "").strip(),
        "last_advance_operation_id": str(meta.get("last_advance_operation_id") or "").strip(),
        "last_advance_operation_status": str(meta.get("last_advance_operation_status") or "").strip(),
        "last_advance_message": str(meta.get("last_advance_message") or "").strip(),
        "last_advance_actor": str(meta.get("last_advance_actor") or "").strip(),
        "last_advance_applied": bool(meta.get("last_advance_applied")),
        "last_advance_at": str(meta.get("last_advance_at") or "").strip(),
        "last_recovery_action": str(meta.get("last_recovery_action") or "").strip(),
        "last_recovery_outcome": str(meta.get("last_recovery_outcome") or "").strip(),
        "last_recovery_target_id": str(meta.get("last_recovery_target_id") or "").strip(),
        "last_recovery_message": str(meta.get("last_recovery_message") or "").strip(),
        "last_recovery_actor": str(meta.get("last_recovery_actor") or "").strip(),
        "last_recovery_source_status": str(meta.get("last_recovery_source_status") or "").strip(),
        "last_recovery_at": str(meta.get("last_recovery_at") or "").strip(),
        **_replacement_lineage_projection(meta),
        "recommended_action": recommended_action,
        "operator_hint": operator_hint,
        "action_target_id": action_target_id,
        "advance": _advance_projection(recommended_action, action_target_id, operator_hint),
        "recovery": _recovery_projection(
            record,
            recommended_action=recommended_action,
            action_target_id=action_target_id,
            operator_hint=operator_hint,
        ),
        "current_task": _queue_current_task_projection(
            record,
            meta,
            recommended_action=recommended_action,
            operator_hint=operator_hint,
            action_target_id=action_target_id,
        ),
        **history_summary,
        "deadletter_reason": record.deadletter_reason,
        "updated_at": record.updated_at,
    }


def mission_queue_item(
    mission_id: str,
    repo_root: Path | None = None,
) -> tuple[MissionRecord | None, dict[str, Any] | None, str | None]:
    record, err = read_mission(mission_id, repo_root)
    if not record:
        return None, None, err
    return record, _queue_item(record, repo_root), None


@dataclass(frozen=True)
class MissionCreateRequest:
    objective: str
    requester_id: str = "api"
    status: MissionStatus = MissionStatus.QUEUED
    summary: str = ""
    next_step: str = ""
    owner_id: str = ""
    priority: int = 5
    risk_tier: str = "medium"
    dependency_ids: list[str] = field(default_factory=list)
    escalation_path: str = ""
    linked_task_ids: list[str] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class MissionRecord:
    mission_id: str
    created_at: str
    updated_at: str
    status: MissionStatus
    objective: str
    requester_id: str
    summary: str = ""
    next_step: str = ""
    owner_id: str = ""
    priority: int = 5
    risk_tier: str = "medium"
    dependency_ids: list[str] = field(default_factory=list)
    escalation_path: str = ""
    linked_task_ids: list[str] = field(default_factory=list)
    deadletter_reason: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    def to_json_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        data["dependency_ids"] = _normalize_task_ids(self.dependency_ids)
        data["linked_task_ids"] = _normalize_task_ids(self.linked_task_ids)
        return data

    @staticmethod
    def from_json_dict(data: dict[str, Any]) -> "MissionRecord":
        return MissionRecord(
            mission_id=str(data.get("mission_id") or ""),
            created_at=str(data.get("created_at") or ""),
            updated_at=str(data.get("updated_at") or ""),
            status=_coerce_status(data.get("status")),
            objective=str(data.get("objective") or ""),
            requester_id=str(data.get("requester_id") or "api"),
            summary=str(data.get("summary") or ""),
            next_step=str(data.get("next_step") or ""),
            owner_id=str(data.get("owner_id") or data.get("requester_id") or "api"),
            priority=int(data.get("priority") or 5),
            risk_tier=str(data.get("risk_tier") or "medium"),
            dependency_ids=_normalize_task_ids(list(data.get("dependency_ids") or [])),
            escalation_path=str(data.get("escalation_path") or ""),
            linked_task_ids=_normalize_task_ids(list(data.get("linked_task_ids") or [])),
            deadletter_reason=(str(data.get("deadletter_reason")) if data.get("deadletter_reason") else None),
            meta=dict(data.get("meta") or {}) if isinstance(data.get("meta"), dict) else {},
        )


def create_mission(
    request: MissionCreateRequest, repo_root: Path | None = None
) -> tuple[MissionRecord | None, str | None]:
    objective = str(request.objective or "").strip()
    if not objective:
        return None, "objective_required"
    if not _is_jsonable(request.meta):
        return None, "meta_not_json_serializable"

    mission_id = _new_mission_id()
    record = MissionRecord(
        mission_id=mission_id,
        created_at=_now(),
        updated_at=_now(),
        status=_coerce_status(request.status),
        objective=objective,
        requester_id=str(request.requester_id or "api").strip() or "api",
        summary=str(request.summary or "").strip(),
        next_step=str(request.next_step or "").strip(),
        owner_id=str(request.owner_id or request.requester_id or "api").strip() or "api",
        priority=max(1, min(int(request.priority), 9)),
        risk_tier=str(request.risk_tier or "medium").strip() or "medium",
        dependency_ids=_normalize_task_ids(request.dependency_ids),
        escalation_path=str(request.escalation_path or "").strip(),
        linked_task_ids=_normalize_task_ids(request.linked_task_ids),
        meta=dict(request.meta or {}),
    )

    try:
        _atomic_write_text(
            _record_path(mission_id, repo_root), json.dumps(record.to_json_dict(), indent=2, ensure_ascii=False)
        )
        _append_history(
            mission_id,
            "created",
            {
                "status": record.status.value,
                "objective": record.objective,
                "next_step": record.next_step or None,
                "owner_id": record.owner_id or None,
                "dependency_count": len(record.dependency_ids),
                "escalation_path": record.escalation_path or None,
                "linked_task_count": len(record.linked_task_ids),
            },
            repo_root,
        )
        return record, None
    except Exception as exc:
        return None, f"create_failed:{type(exc).__name__}"


def create_replacement_mission(
    source_mission_id: str,
    repo_root: Path | None = None,
    *,
    objective: str = "",
    summary: str = "",
    next_step: str = "",
    owner_id: str = "",
    priority: int | None = None,
    risk_tier: str = "",
    actor: str | None = None,
    note: str | None = None,
    meta: dict[str, Any] | None = None,
) -> tuple[MissionRecord | None, MissionRecord | None, str | None]:
    source, err = read_mission(source_mission_id, repo_root)
    if not source:
        return None, None, err
    if source.status not in {MissionStatus.FAILED, MissionStatus.DEADLETTERED}:
        return None, source, "invalid_replacement_source_status"
    if meta is not None and not _is_jsonable(meta):
        return None, source, "meta_not_json_serializable"

    source_queue_item = _queue_item(source, repo_root)
    recovery = source_queue_item.get("recovery") if isinstance(source_queue_item.get("recovery"), dict) else {}
    source_meta = dict(source.meta) if isinstance(source.meta, dict) else {}
    default_action = "review_deadletter" if source.status == MissionStatus.DEADLETTERED else "retry_or_deadletter"
    recovery_action = str(
        recovery.get("action") or source_queue_item.get("recommended_action") or default_action
    ).strip()
    if recovery_action not in RECOVERY_REVIEW_ACTIONS:
        recovery_action = default_action
    recovery_target_id = _first_text(
        recovery.get("target_id"),
        source_queue_item.get("action_target_id"),
        source_meta.get("last_task_id"),
        source_meta.get("last_advance_operation_id"),
    )
    replacement_reason = _first_text(
        source.deadletter_reason,
        recovery.get("reason"),
        source_meta.get("last_task_reason"),
        source.next_step,
        "Operator declared replacement mission.",
    )
    cleaned_actor = str(actor or "").strip()
    cleaned_note = str(note or "").strip()

    replacement_meta = dict(meta or {})
    replacement_meta.update(
        {
            "replacement_for_mission_id": source.mission_id,
            "replacement_for_status": source.status.value,
            "replacement_source_objective": source.objective,
            "replacement_source_action": recovery_action,
            "replacement_source_target_id": recovery_target_id or None,
            "replacement_reason": replacement_reason,
            "replacement_declared_by": cleaned_actor or None,
            "replacement_note": cleaned_note or None,
        }
    )

    replacement, create_err = create_mission(
        MissionCreateRequest(
            objective=str(objective or "").strip() or f"Replacement for: {source.objective}",
            summary=str(summary or "").strip()
            or f"Replacement declared from {source.status.value} mission {source.mission_id}. {source.summary}".strip(),
            next_step=str(next_step or "").strip()
            or "Declare the first bounded operation for this replacement mission.",
            requester_id=cleaned_actor or source.requester_id or "api",
            owner_id=str(owner_id or "").strip() or source.owner_id or cleaned_actor or source.requester_id or "api",
            priority=source.priority if priority is None else priority,
            risk_tier=str(risk_tier or "").strip() or source.risk_tier or "medium",
            status=MissionStatus.QUEUED,
            meta=replacement_meta,
        ),
        repo_root,
    )
    if not replacement:
        return None, source, create_err or "replacement_create_failed"

    try:
        _append_history(
            replacement.mission_id,
            "replacement_declared",
            {
                "source_mission_id": source.mission_id,
                "source_status": source.status.value,
                "source_action": recovery_action,
                "source_target_id": recovery_target_id or None,
                "reason": replacement_reason,
                "actor": cleaned_actor or None,
                "note": cleaned_note or None,
                "automatic_retry": False,
                "source_reopened": False,
            },
            repo_root,
        )
    except Exception as exc:
        return replacement, source, f"history_failed:{type(exc).__name__}"

    reviewed_source, review_err = record_recovery_review_receipt(
        source.mission_id,
        repo_root,
        action=recovery_action,
        outcome="replacement_declared",
        actor=cleaned_actor or None,
        note=cleaned_note or None,
        target_id=replacement.mission_id,
        message=f"Replacement mission {replacement.mission_id} declared.",
        source_status=source.status.value,
    )
    if not reviewed_source:
        return replacement, source, review_err or "replacement_receipt_failed"
    return replacement, reviewed_source, review_err


def read_mission(mission_id: str, repo_root: Path | None = None) -> tuple[MissionRecord | None, str | None]:
    cleaned = str(mission_id or "").strip()
    if not cleaned or (not _ID_RE.match(cleaned) and not cleaned.startswith("msn_")):
        return None, "invalid_mission_id"
    path = _record_path(cleaned, repo_root)
    if not path.exists():
        return None, "not_found"
    try:
        raw = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        if not isinstance(raw, dict):
            return None, "corrupt_record"
        return MissionRecord.from_json_dict(raw), None
    except Exception as exc:
        return None, f"read_failed:{type(exc).__name__}"


def list_missions(
    repo_root: Path | None = None,
    *,
    limit: int = 200,
    status: MissionStatus | str | None = None,
) -> list[MissionRecord]:
    root = _missions_dir(repo_root)
    if not root.exists():
        return []
    status_filter = _coerce_status(status).value if status else ""
    out: list[MissionRecord] = []
    try:
        for child in root.iterdir():
            record_path = child if child.is_file() else child / "record.json"
            if not record_path.is_file():
                continue
            raw = json.loads(record_path.read_text(encoding="utf-8", errors="replace"))
            if not isinstance(raw, dict):
                continue
            record = MissionRecord.from_json_dict(raw)
            if status_filter and record.status.value != status_filter:
                continue
            out.append(record)
    except Exception:
        return []
    out.sort(key=lambda item: (item.updated_at, item.mission_id), reverse=True)
    return out[: max(0, int(limit))]


def read_history(mission_id: str, repo_root: Path | None = None, limit: int = 200) -> list[dict[str, Any]]:
    path = _history_path(mission_id, repo_root)
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        tail = lines[-int(limit) :] if limit and limit > 0 else lines
        out: list[dict[str, Any]] = []
        for line in tail:
            try:
                item = json.loads(line)
            except Exception:
                continue
            if isinstance(item, dict):
                out.append(item)
        return out
    except Exception:
        return []


def _history_summary(mission_id: str, repo_root: Path | None = None) -> dict[str, Any]:
    history = read_history(mission_id, repo_root, limit=200)
    latest_history = history[-1] if history and isinstance(history[-1], dict) else {}
    history_tail: list[dict[str, Any]] = []
    for entry in history[-2:]:
        if not isinstance(entry, dict):
            continue
        details = entry.get("details")
        history_tail.append(
            {
                "event": str(entry.get("event") or "").strip(),
                "ts": str(entry.get("ts") or "").strip(),
                "details": dict(details) if isinstance(details, dict) else {},
            }
        )
    return {
        "history_count": len(history),
        "latest_history_event": str(latest_history.get("event") or "").strip(),
        "latest_history_ts": str(latest_history.get("ts") or "").strip(),
        "history_tail": history_tail,
    }


def update_mission(
    mission_id: str,
    repo_root: Path | None = None,
    *,
    status: MissionStatus | str | None = None,
    summary: str | None = None,
    next_step: str | None = None,
    owner_id: str | None = None,
    dependency_ids: list[str] | None = None,
    escalation_path: str | None = None,
    add_task_ids: list[str] | None = None,
    remove_task_ids: list[str] | None = None,
    deadletter_reason: str | None = None,
    meta_updates: dict[str, Any] | None = None,
    actor: str | None = None,
    note: str | None = None,
) -> tuple[MissionRecord | None, str | None]:
    record, err = read_mission(mission_id, repo_root)
    if not record:
        return None, err
    if meta_updates is not None and not _is_jsonable(meta_updates):
        return None, "meta_not_json_serializable"

    new_status = _coerce_status(status) if status is not None else record.status
    if record.status in _TERMINAL_STATUSES and new_status != record.status:
        return None, "terminal_status"

    changes: dict[str, Any] = {}
    previous_status = record.status

    if status is not None and new_status != record.status:
        record.status = new_status
        changes["status"] = {"from": previous_status.value, "to": new_status.value}

    if summary is not None:
        cleaned_summary = str(summary or "").strip()
        if cleaned_summary != record.summary:
            record.summary = cleaned_summary
            changes["summary"] = record.summary

    if next_step is not None:
        cleaned_next_step = str(next_step or "").strip()
        if cleaned_next_step != record.next_step:
            record.next_step = cleaned_next_step
            changes["next_step"] = record.next_step

    if owner_id is not None:
        cleaned_owner_id = str(owner_id or "").strip()
        if cleaned_owner_id != record.owner_id:
            record.owner_id = cleaned_owner_id
            changes["owner_id"] = record.owner_id

    if dependency_ids is not None:
        cleaned_dependency_ids = _normalize_task_ids(dependency_ids)
        if cleaned_dependency_ids != record.dependency_ids:
            record.dependency_ids = cleaned_dependency_ids
            changes["dependency_ids"] = list(record.dependency_ids)

    if escalation_path is not None:
        cleaned_escalation_path = str(escalation_path or "").strip()
        if cleaned_escalation_path != record.escalation_path:
            record.escalation_path = cleaned_escalation_path
            changes["escalation_path"] = record.escalation_path

    if deadletter_reason is not None:
        cleaned_reason = str(deadletter_reason or "").strip() or None
        if cleaned_reason != record.deadletter_reason:
            record.deadletter_reason = cleaned_reason
            changes["deadletter_reason"] = cleaned_reason

    added_task_ids = [item for item in _normalize_task_ids(add_task_ids) if item not in set(record.linked_task_ids)]
    if added_task_ids:
        record.linked_task_ids.extend(added_task_ids)
        record.linked_task_ids = _normalize_task_ids(record.linked_task_ids)
        changes["added_task_ids"] = added_task_ids

    if remove_task_ids:
        remove_set = set(_normalize_task_ids(remove_task_ids))
        next_task_ids = [item for item in record.linked_task_ids if item not in remove_set]
        removed_task_ids = [item for item in record.linked_task_ids if item in remove_set]
        if removed_task_ids:
            record.linked_task_ids = next_task_ids
            changes["removed_task_ids"] = removed_task_ids

    if meta_updates:
        merged = dict(record.meta)
        merged.update(meta_updates)
        if merged != record.meta:
            record.meta = merged
            changes["meta_keys"] = sorted(meta_updates.keys())

    if not changes:
        return record, None

    record.updated_at = _now()

    try:
        _atomic_write_text(
            _record_path(record.mission_id, repo_root),
            json.dumps(record.to_json_dict(), indent=2, ensure_ascii=False),
        )
        if "status" in changes:
            _append_history(
                record.mission_id,
                "status_changed",
                {
                    **dict(changes["status"]),
                    "actor": str(actor or "").strip() or None,
                    "note": str(note or "").strip() or None,
                    "deadletter_reason": record.deadletter_reason,
                },
                repo_root,
            )
        if "added_task_ids" in changes or "removed_task_ids" in changes:
            _append_history(
                record.mission_id,
                "task_links_updated",
                {
                    "added_task_ids": changes.get("added_task_ids") or [],
                    "removed_task_ids": changes.get("removed_task_ids") or [],
                    "linked_task_count": len(record.linked_task_ids),
                    "actor": str(actor or "").strip() or None,
                },
                repo_root,
            )
        continuity_changes = {
            key: value
            for key, value in changes.items()
            if key
            in {
                "summary",
                "next_step",
                "owner_id",
                "dependency_ids",
                "escalation_path",
                "deadletter_reason",
                "meta_keys",
            }
        }
        if continuity_changes:
            _append_history(
                record.mission_id,
                "continuity_updated",
                {
                    **continuity_changes,
                    "actor": str(actor or "").strip() or None,
                    "note": str(note or "").strip() or None,
                },
                repo_root,
            )
        return record, None
    except Exception as exc:
        return None, f"update_failed:{type(exc).__name__}"


def link_task(
    mission_id: str,
    task_id: str,
    repo_root: Path | None = None,
    *,
    actor: str | None = None,
    note: str | None = None,
) -> tuple[MissionRecord | None, str | None]:
    cleaned = str(task_id or "").strip()
    if not cleaned:
        return None, "task_id_required"
    return update_mission(
        mission_id,
        repo_root,
        add_task_ids=[cleaned],
        actor=actor,
        note=note,
    )


def record_linked_task_transition(
    mission_id: str,
    task_id: str,
    repo_root: Path | None = None,
    *,
    task_status: str,
    result_status: str = "",
    status_reason: str = "",
    governance: dict[str, Any] | None = None,
    approval_id: str = "",
    previous_approval_id: str = "",
    approval_status: str = "",
    actor: str | None = None,
    note: str | None = None,
) -> tuple[MissionRecord | None, str | None]:
    record, err = read_mission(mission_id, repo_root)
    if not record:
        return None, err

    governance_payload = dict(governance or {})
    normalized_task_status = _normalize_task_status(task_status)
    normalized_result_status = _normalize_task_status(result_status)
    cleaned_task_id = str(task_id or "").strip()
    cleaned_approval_id = str(approval_id or "").strip()
    cleaned_previous_approval_id = str(previous_approval_id or "").strip()
    cleaned_approval_status = str(approval_status or governance_payload.get("approval_status") or "").strip().lower()
    if not cleaned_task_id:
        return None, "task_id_required"

    if cleaned_task_id not in record.linked_task_ids:
        record.linked_task_ids.append(cleaned_task_id)
        record.linked_task_ids = _normalize_task_ids(record.linked_task_ids)

    previous_status = record.status
    next_status = record.status
    if normalized_result_status in {"pending", "needs_approval", "blocked", "denied"}:
        next_status = MissionStatus.BLOCKED
    elif normalized_task_status == "running":
        next_status = MissionStatus.ACTIVE
    elif normalized_task_status in {"pending", "accepted"}:
        next_status = MissionStatus.QUEUED
    elif len(record.linked_task_ids) <= 1:
        if normalized_task_status == "completed":
            next_status = MissionStatus.COMPLETED
        elif normalized_task_status == "failed":
            next_status = MissionStatus.FAILED
        elif normalized_task_status == "cancelled":
            next_status = MissionStatus.CANCELLED

    record.meta = dict(record.meta)
    record.meta.update(
        {
            "last_task_id": cleaned_task_id,
            "last_task_status": normalized_task_status or None,
            "last_task_result_status": normalized_result_status or None,
            "last_task_reason": str(status_reason or "").strip() or None,
            "last_task_gate": str(governance_payload.get("gate") or "").strip() or None,
            "last_task_approval_id": cleaned_approval_id or None,
            "last_task_previous_approval_id": cleaned_previous_approval_id or None,
            "last_task_approval_status": cleaned_approval_status or None,
            "last_task_next_step": str(governance_payload.get("next_step") or "").strip() or None,
            "last_task_updated_at": _now(),
        }
    )

    if record.status not in _TERMINAL_STATUSES and next_status != record.status:
        record.status = next_status

    record.updated_at = _now()

    try:
        _atomic_write_text(
            _record_path(record.mission_id, repo_root),
            json.dumps(record.to_json_dict(), indent=2, ensure_ascii=False),
        )
        _append_history(
            record.mission_id,
            "linked_task_transition",
            {
                "task_id": cleaned_task_id,
                "task_status": normalized_task_status or None,
                "result_status": normalized_result_status or None,
                "status_reason": str(status_reason or "").strip() or None,
                "gate": str(governance_payload.get("gate") or "").strip() or None,
                "approval_id": cleaned_approval_id or None,
                "previous_approval_id": cleaned_previous_approval_id or None,
                "approval_status": cleaned_approval_status or None,
                "next_step": str(governance_payload.get("next_step") or "").strip() or None,
                "actor": str(actor or "").strip() or None,
                "note": str(note or "").strip() or None,
                "mission_status_before": previous_status.value,
                "mission_status_after": record.status.value,
            },
            repo_root,
        )
        return record, None
    except Exception as exc:
        return None, f"update_failed:{type(exc).__name__}"


def tick_mission(
    mission_id: str,
    repo_root: Path | None = None,
    *,
    actor: str | None = None,
    note: str | None = None,
) -> tuple[MissionRecord | None, bool, str | None]:
    record, err = read_mission(mission_id, repo_root)
    if not record:
        return None, False, err

    derived_status, latest = _derive_mission_status_from_tasks(record.linked_task_ids, repo_root)
    if not latest:
        return record, False, None

    meta_updates = {
        "last_task_id": str(latest.get("task_id") or "").strip() or None,
        "last_task_status": str(latest.get("task_status") or "").strip() or None,
        "last_task_result_status": str(latest.get("result_status") or "").strip() or None,
        "last_task_reason": str(latest.get("status_reason") or "").strip() or None,
        "last_task_gate": str(latest.get("gate") or "").strip() or None,
        "last_task_approval_id": str(latest.get("approval_id") or "").strip() or None,
        "last_task_previous_approval_id": str(latest.get("previous_approval_id") or "").strip() or None,
        "last_task_approval_status": str(latest.get("approval_status") or "").strip().lower() or None,
        "last_task_next_step": str(latest.get("next_step") or "").strip() or None,
        "last_task_updated_at": str(latest.get("updated_at") or latest.get("created_at") or "").strip() or None,
    }

    status_changed = False
    previous_status = record.status
    if derived_status is not None and record.status not in _TERMINAL_STATUSES and derived_status != record.status:
        record.status = derived_status
        status_changed = True

    record.meta = dict(record.meta)
    meta_changed = False
    for key, value in meta_updates.items():
        if record.meta.get(key) != value:
            record.meta[key] = value
            meta_changed = True

    if not status_changed and not meta_changed:
        return record, False, None

    record.updated_at = _now()

    try:
        _atomic_write_text(
            _record_path(record.mission_id, repo_root),
            json.dumps(record.to_json_dict(), indent=2, ensure_ascii=False),
        )
        _append_history(
            record.mission_id,
            "mission_ticked",
            {
                "actor": str(actor or "").strip() or None,
                "note": str(note or "").strip() or None,
                "mission_status_before": previous_status.value,
                "mission_status_after": record.status.value,
                "latest_task_id": meta_updates["last_task_id"],
                "latest_task_status": meta_updates["last_task_status"],
                "latest_task_result_status": meta_updates["last_task_result_status"],
                "latest_task_gate": meta_updates["last_task_gate"],
                "latest_task_approval_id": meta_updates["last_task_approval_id"],
                "latest_task_previous_approval_id": meta_updates["last_task_previous_approval_id"],
                "latest_task_approval_status": meta_updates["last_task_approval_status"],
                "latest_task_next_step": meta_updates["last_task_next_step"],
                "latest_task_reason": meta_updates["last_task_reason"],
            },
            repo_root,
        )
        return record, True, None
    except Exception as exc:
        return None, False, f"update_failed:{type(exc).__name__}"


def tick_all_missions(
    repo_root: Path | None = None,
    *,
    limit: int = 200,
    actor: str | None = None,
    note: str | None = None,
) -> tuple[list[MissionRecord], int, list[dict[str, Any]]]:
    records: list[MissionRecord] = []
    applied_count = 0
    errors: list[dict[str, Any]] = []
    for record in list_missions(repo_root, limit=limit):
        updated, applied, err = tick_mission(record.mission_id, repo_root, actor=actor, note=note)
        if updated:
            records.append(updated)
        if applied:
            applied_count += 1
        if err:
            errors.append({"mission_id": record.mission_id, "error": err})
    return records, applied_count, errors


def mission_queue_items(
    repo_root: Path | None = None,
    *,
    limit: int = 50,
    include_terminal: bool = False,
) -> list[dict[str, Any]]:
    records = list_missions(repo_root, limit=10_000)
    if not include_terminal:
        records = [record for record in records if record.status not in _TERMINAL_STATUSES]
    records.sort(key=_queue_sort_key)
    return [_queue_item(record, repo_root) for record in records[: max(0, int(limit))]]


def deadletter_queue_items(repo_root: Path | None = None, *, limit: int = 50) -> list[dict[str, Any]]:
    records = list_missions(repo_root, limit=10_000, status=MissionStatus.DEADLETTERED.value)
    records.sort(key=lambda record: (-_parse_ts(record.updated_at), record.mission_id))
    return [_queue_item(record, repo_root) for record in records[: max(0, int(limit))]]


def failed_queue_items(repo_root: Path | None = None, *, limit: int = 50) -> list[dict[str, Any]]:
    records = list_missions(repo_root, limit=10_000, status=MissionStatus.FAILED.value)
    records.sort(key=lambda record: (-_parse_ts(record.updated_at), record.mission_id))
    return [_queue_item(record, repo_root) for record in records[: max(0, int(limit))]]


def run_queue_once(
    repo_root: Path | None = None,
    *,
    limit: int = 50,
    actor: str | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    if repo_root is not None:
        safe_limit = max(1, int(limit))
        records, applied_count, errors = tick_all_missions(
            repo_root,
            limit=max(safe_limit, 200),
            actor=actor,
            note=note or "mission_queue_run_once",
        )
        queue_items = mission_queue_items(repo_root, limit=safe_limit, include_terminal=False)
        failed_items = failed_queue_items(repo_root, limit=min(safe_limit, 20))
        deadletter_items = deadletter_queue_items(repo_root, limit=min(safe_limit, 20))
        counts = {
            "queued": 0,
            "active": 0,
            "blocked": 0,
            "failed": len(failed_items),
            "deadlettered": len(deadletter_items),
        }
        for item in queue_items:
            status = str(item.get("status") or "").strip().lower()
            if status in counts:
                counts[status] += 1
        return {
            "ok": not errors,
            "items": queue_items,
            "failed": failed_items,
            "deadletter": deadletter_items,
            "total": len(queue_items),
            "applied": applied_count,
            "errors": errors,
            "counts": counts,
            "processed": len(records),
        }
    from francis.missions import runtime as mission_runtime

    return mission_runtime.run_queue_once(
        limit=limit,
        actor=str(actor or "").strip() or "missions.runner",
        note=str(note or "").strip() or "mission_queue_run_once",
    )


def record_advance_receipt(
    mission_id: str,
    repo_root: Path | None = None,
    *,
    action: str,
    outcome: str,
    actor: str | None = None,
    note: str | None = None,
    operation_id: str = "",
    operation_status: str = "",
    message: str = "",
    applied: bool = False,
) -> tuple[MissionRecord | None, str | None]:
    record, err = read_mission(mission_id, repo_root)
    if not record:
        return None, err

    record.meta = dict(record.meta)
    record.meta.update(
        {
            "last_advance_action": str(action or "").strip() or None,
            "last_advance_outcome": str(outcome or "").strip() or None,
            "last_advance_operation_id": str(operation_id or "").strip() or None,
            "last_advance_operation_status": str(operation_status or "").strip() or None,
            "last_advance_message": str(message or "").strip() or None,
            "last_advance_actor": str(actor or "").strip() or None,
            "last_advance_applied": bool(applied),
            "last_advance_at": _now(),
        }
    )
    record.updated_at = _now()

    try:
        _atomic_write_text(
            _record_path(record.mission_id, repo_root),
            json.dumps(record.to_json_dict(), indent=2, ensure_ascii=False),
        )
        _append_history(
            record.mission_id,
            "advance_receipt",
            {
                "action": str(action or "").strip() or None,
                "outcome": str(outcome or "").strip() or None,
                "actor": str(actor or "").strip() or None,
                "note": str(note or "").strip() or None,
                "operation_id": str(operation_id or "").strip() or None,
                "operation_status": str(operation_status or "").strip() or None,
                "message": str(message or "").strip() or None,
                "applied": bool(applied),
            },
            repo_root,
        )
        return record, None
    except Exception as exc:
        return None, f"update_failed:{type(exc).__name__}"


def record_recovery_review_receipt(
    mission_id: str,
    repo_root: Path | None = None,
    *,
    action: str,
    outcome: str,
    actor: str | None = None,
    note: str | None = None,
    target_id: str = "",
    message: str = "",
    source_status: str = "",
) -> tuple[MissionRecord | None, str | None]:
    record, err = read_mission(mission_id, repo_root)
    if not record:
        return None, err

    normalized_action = str(action or "").strip() or "review_mission"
    if normalized_action not in RECOVERY_REVIEW_ACTIONS:
        return record, None
    status = str(source_status or record.status.value or "").strip().lower()
    if status not in {MissionStatus.FAILED.value, MissionStatus.DEADLETTERED.value}:
        return None, "invalid_recovery_review_source_status"

    reviewed_at = _now()
    record.meta = dict(record.meta)
    record.meta.update(
        {
            "last_recovery_action": normalized_action,
            "last_recovery_outcome": str(outcome or "").strip() or None,
            "last_recovery_target_id": str(target_id or "").strip() or None,
            "last_recovery_message": str(message or "").strip() or None,
            "last_recovery_actor": str(actor or "").strip() or None,
            "last_recovery_source_status": status,
            "last_recovery_at": reviewed_at,
        }
    )
    record.updated_at = reviewed_at

    try:
        _atomic_write_text(
            _record_path(record.mission_id, repo_root),
            json.dumps(record.to_json_dict(), indent=2, ensure_ascii=False),
        )
        _append_history(
            record.mission_id,
            "recovery_review",
            {
                "action": normalized_action,
                "outcome": str(outcome or "").strip() or None,
                "actor": str(actor or "").strip() or None,
                "note": str(note or "").strip() or None,
                "target_id": str(target_id or "").strip() or None,
                "message": str(message or "").strip() or None,
                "source_status": status,
                "operator_required": True,
                "automatic_retry": False,
            },
            repo_root,
        )
        return record, None
    except Exception as exc:
        return None, f"update_failed:{type(exc).__name__}"


def deadletter_mission(
    mission_id: str,
    reason: str,
    repo_root: Path | None = None,
    *,
    actor: str | None = None,
    note: str | None = None,
) -> tuple[MissionRecord | None, str | None]:
    record, err = read_mission(mission_id, repo_root)
    if not record:
        return None, err
    if record.status in {MissionStatus.COMPLETED, MissionStatus.CANCELLED, MissionStatus.DEADLETTERED}:
        return None, "invalid_deadletter_source_status"
    cleaned_reason = str(reason or "").strip() or "manual_deadletter"
    return update_mission(
        mission_id,
        repo_root,
        status=MissionStatus.DEADLETTERED.value,
        deadletter_reason=cleaned_reason,
        actor=actor,
        note=note or "mission_deadlettered",
    )
