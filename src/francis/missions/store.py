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
    "MissionStatus",
    "MissionCreateRequest",
    "MissionRecord",
    "create_mission",
    "record_linked_task_transition",
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
_ID_RE = re.compile(r"^[a-zA-Z0-9_\-]{6,128}$")


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _coerce_status(value: Any) -> MissionStatus:
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


@dataclass(frozen=True)
class MissionCreateRequest:
    objective: str
    requester_id: str = "api"
    status: MissionStatus = MissionStatus.QUEUED
    summary: str = ""
    next_step: str = ""
    priority: int = 5
    risk_tier: str = "medium"
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
    priority: int = 5
    risk_tier: str = "medium"
    linked_task_ids: list[str] = field(default_factory=list)
    deadletter_reason: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    def to_json_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
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
            priority=int(data.get("priority") or 5),
            risk_tier=str(data.get("risk_tier") or "medium"),
            linked_task_ids=_normalize_task_ids(list(data.get("linked_task_ids") or [])),
            deadletter_reason=(str(data.get("deadletter_reason")) if data.get("deadletter_reason") else None),
            meta=dict(data.get("meta") or {}) if isinstance(data.get("meta"), dict) else {},
        )


def create_mission(request: MissionCreateRequest, repo_root: Path | None = None) -> tuple[MissionRecord | None, str | None]:
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
        priority=max(1, min(int(request.priority), 9)),
        risk_tier=str(request.risk_tier or "medium").strip() or "medium",
        linked_task_ids=_normalize_task_ids(request.linked_task_ids),
        meta=dict(request.meta or {}),
    )

    try:
        _atomic_write_text(_record_path(mission_id, repo_root), json.dumps(record.to_json_dict(), indent=2, ensure_ascii=False))
        _append_history(
            mission_id,
            "created",
            {
                "status": record.status.value,
                "objective": record.objective,
                "next_step": record.next_step or None,
                "linked_task_count": len(record.linked_task_ids),
            },
            repo_root,
        )
        return record, None
    except Exception as exc:
        return None, f"create_failed:{type(exc).__name__}"


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


def update_mission(
    mission_id: str,
    repo_root: Path | None = None,
    *,
    status: MissionStatus | str | None = None,
    summary: str | None = None,
    next_step: str | None = None,
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
            if key in {"summary", "next_step", "deadletter_reason", "meta_keys"}
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
