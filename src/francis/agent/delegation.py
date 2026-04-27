from __future__ import annotations

import argparse
import json
import logging
import os
import re
import secrets
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from francis.governance.operation_redaction import (
    redact_operation_optional_text,
    redact_operation_text,
    redact_operation_value,
)
from francis.kernel.paths import data_dir

logger = logging.getLogger(__name__)

__all__ = [
    "TaskStatus",
    "DelegationRequest",
    "DelegationRecord",
    "DelegationDecision",
    "DelegationPolicy",
    "DelegationRouter",
    "create_delegation",
    "read_delegation",
    "update_status",
    "cancel_delegation",
    "list_tasks",
    "read_audit",
]


class TaskStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


_STATUS_ALIASES: dict[str, str] = {
    "pending": TaskStatus.PENDING.value,
    "accepted": TaskStatus.ACCEPTED.value,
    "running": TaskStatus.RUNNING.value,
    "completed": TaskStatus.COMPLETED.value,
    "complete": TaskStatus.COMPLETED.value,
    "failed": TaskStatus.FAILED.value,
    "cancelled": TaskStatus.CANCELLED.value,
    "canceled": TaskStatus.CANCELLED.value,
}


def _coerce_task_status(value: Any) -> TaskStatus:
    raw = str(value or TaskStatus.PENDING.value).strip().lower()
    normalized = _STATUS_ALIASES.get(raw, TaskStatus.PENDING.value)
    return TaskStatus(normalized)


@dataclass(frozen=True)
class DelegationRequest:
    requester_id: str
    capability: str
    objective: str
    inputs: dict[str, Any] = field(default_factory=dict)
    priority: int = 5
    ttl_sec: int = 3600


@dataclass
class DelegationRecord:
    task_id: str
    created_at: str
    updated_at: str
    status: TaskStatus
    requester_id: str
    capability: str
    objective: str
    inputs: dict[str, Any]
    priority: int
    ttl_sec: int
    assigned_to: str | None = None
    status_reason: str | None = None
    attempts: int = 0
    result: dict[str, Any] | None = None

    def to_json_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        return data

    @staticmethod
    def from_json_dict(data: dict[str, Any]) -> "DelegationRecord":
        return DelegationRecord(
            task_id=str(data.get("task_id", "")),
            created_at=str(data.get("created_at", "")),
            updated_at=str(data.get("updated_at", "")),
            status=_coerce_task_status(data.get("status", TaskStatus.PENDING.value)),
            requester_id=str(data.get("requester_id", "")),
            capability=str(data.get("capability", "")),
            objective=str(data.get("objective", "")),
            inputs=dict(data.get("inputs", {}) or {}),
            priority=int(data.get("priority", 5)),
            ttl_sec=int(data.get("ttl_sec", 3600)),
            assigned_to=(str(data["assigned_to"]) if data.get("assigned_to") else None),
            status_reason=redact_operation_optional_text(data.get("status_reason")),
            attempts=int(data.get("attempts", 0)),
            result=(dict(data["result"]) if isinstance(data.get("result"), dict) else None),
        )


@dataclass(frozen=True)
class DelegationDecision:
    action: str
    reason: str


@dataclass(frozen=True)
class DelegationPolicy:
    allowed_capabilities: set[str] | None = None
    max_priority: int = 9
    min_priority: int = 1
    max_ttl_sec: int = 7 * 24 * 3600


class DelegationRouter:
    def __init__(self, policy: DelegationPolicy | None = None) -> None:
        self.policy = policy or DelegationPolicy()

    def evaluate(self, request: DelegationRequest) -> DelegationDecision:
        if not request.requester_id.strip():
            return DelegationDecision(action="reject", reason="requester_id_required")
        if not request.capability.strip():
            return DelegationDecision(action="reject", reason="capability_required")
        if not request.objective.strip():
            return DelegationDecision(action="reject", reason="objective_required")
        if not (self.policy.min_priority <= int(request.priority) <= self.policy.max_priority):
            return DelegationDecision(action="reject", reason="priority_out_of_range")
        if int(request.ttl_sec) <= 0 or int(request.ttl_sec) > self.policy.max_ttl_sec:
            return DelegationDecision(action="reject", reason="ttl_out_of_range")
        if self.policy.allowed_capabilities is not None and request.capability not in self.policy.allowed_capabilities:
            return DelegationDecision(action="reject", reason="capability_not_allowed")
        if not _is_jsonable(request.inputs):
            return DelegationDecision(action="reject", reason="inputs_not_json_serializable")
        return DelegationDecision(action="accept", reason="ok")


_ID_RE = re.compile(r"^[a-zA-Z0-9_\-]{6,128}$")


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _tasks_dir(repo_root: Path | None = None) -> Path:
    if repo_root is not None:
        return repo_root.resolve() / "data" / "tasks"
    return data_dir() / "tasks"


def _task_dir(task_id: str, repo_root: Path | None = None) -> Path:
    return _tasks_dir(repo_root) / task_id


def _record_path(task_id: str, repo_root: Path | None = None) -> Path:
    return _task_dir(task_id, repo_root) / "record.json"


def _audit_path(task_id: str, repo_root: Path | None = None) -> Path:
    return _task_dir(task_id, repo_root) / "audit.log"


def _safe_mkdir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _atomic_write_text(path: Path, text: str) -> None:
    _safe_mkdir(path.parent)
    tmp = path.with_suffix(path.suffix + f".tmp_{secrets.token_hex(4)}")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _append_audit(task_id: str, event: str, details: dict[str, Any], repo_root: Path | None = None) -> None:
    redacted_details = redact_operation_value(details)
    line = {
        "ts": _now(),
        "task_id": task_id,
        "event": event,
        "details": redacted_details if isinstance(redacted_details, dict) else {},
    }
    path = _audit_path(task_id, repo_root)
    _safe_mkdir(path.parent)
    with path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(line, ensure_ascii=False, default=str) + "\n")


def _is_jsonable(value: Any, depth: int = 0) -> bool:
    if depth > 20:
        return False
    if value is None or isinstance(value, (bool, int, float, str)):
        return True
    if isinstance(value, (list, tuple)):
        return all(_is_jsonable(item, depth + 1) for item in value)
    if isinstance(value, dict):
        return all(isinstance(k, str) and _is_jsonable(v, depth + 1) for k, v in value.items())
    return False


def _new_task_id() -> str:
    return f"tsk_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}_{secrets.token_hex(4)}"


def _task_mission_id(inputs: dict[str, Any]) -> str:
    for key in ("mission_id", "current_task_mission_id", "handoff_mission_id"):
        mission_id = _safe_str(inputs.get(key)).strip()
        if mission_id:
            return mission_id
    meta = inputs.get("meta")
    if isinstance(meta, dict):
        for key in ("mission_id", "current_task_mission_id", "handoff_mission_id"):
            mission_id = _safe_str(meta.get(key)).strip()
            if mission_id:
                return mission_id
    return ""


def _created_audit_details(record: DelegationRecord) -> dict[str, Any]:
    input_keys = [key for key in record.inputs if isinstance(key, str) and key.strip()]
    details: dict[str, Any] = {
        "status": record.status.value,
        "capability": record.capability,
        "requester_id": record.requester_id,
        "priority": record.priority,
        "ttl_sec": record.ttl_sec,
        "input_key_count": len(input_keys),
    }
    mission_id = _task_mission_id(record.inputs)
    if mission_id:
        details["mission_id"] = mission_id
    return details


def create_delegation(
    request: DelegationRequest, repo_root: Path | None = None, *, policy: DelegationPolicy | None = None
) -> tuple[DelegationRecord | None, str | None]:
    decision = DelegationRouter(policy).evaluate(request)
    if decision.action != "accept":
        logger.warning("Delegation rejected: %s", decision.reason)
        return None, decision.reason

    task_id = _new_task_id()
    record = DelegationRecord(
        task_id=task_id,
        created_at=_now(),
        updated_at=_now(),
        status=TaskStatus.PENDING,
        requester_id=request.requester_id.strip(),
        capability=request.capability.strip(),
        objective=redact_operation_text(request.objective),
        inputs=request.inputs,
        priority=int(request.priority),
        ttl_sec=int(request.ttl_sec),
    )

    try:
        path = _record_path(task_id, repo_root)
        _atomic_write_text(path, json.dumps(record.to_json_dict(), indent=2, ensure_ascii=False))
        _append_audit(task_id, "created", _created_audit_details(record), repo_root)
        return record, None
    except Exception as exc:
        logger.error("Create failed: %s", exc)
        return None, f"create_failed:{type(exc).__name__}"


def read_delegation(task_id: str, repo_root: Path | None = None) -> tuple[DelegationRecord | None, str | None]:
    if not task_id or (not _ID_RE.match(task_id) and not task_id.startswith("tsk_")):
        return None, "invalid_task_id"
    path = _record_path(task_id, repo_root)
    if not path.exists():
        return None, "not_found"
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        if not isinstance(data, dict):
            return None, "corrupt_record"
        return DelegationRecord.from_json_dict(data), None
    except Exception as exc:
        logger.error("Read failed: %s", exc)
        return None, f"read_failed:{type(exc).__name__}"


def update_status(
    task_id: str,
    new_status: TaskStatus,
    repo_root: Path | None = None,
    *,
    assigned_to: str | None = None,
    status_reason: str | None = None,
    result: dict[str, Any] | None = None,
) -> tuple[bool, str | None]:
    record, err = read_delegation(task_id, repo_root)
    if not record:
        return False, err

    terminal = {TaskStatus.CANCELLED, TaskStatus.COMPLETED, TaskStatus.FAILED}
    if record.status in terminal:
        return False, "terminal_status"

    if result is not None and not _is_jsonable(result):
        return False, "result_not_json_serializable"

    record.updated_at = _now()
    record.status = new_status
    if assigned_to is not None:
        record.assigned_to = str(assigned_to)
    if status_reason is not None:
        record.status_reason = redact_operation_text(status_reason)
    if result is not None:
        record.result = result

    try:
        path = _record_path(task_id, repo_root)
        _atomic_write_text(path, json.dumps(record.to_json_dict(), indent=2, ensure_ascii=False))
        _append_audit(
            task_id,
            "status_updated",
            {"to": new_status.value, "assigned_to": record.assigned_to, "reason": record.status_reason},
            repo_root,
        )
        return True, None
    except Exception as exc:
        logger.error("Update failed: %s", exc)
        return False, f"update_failed:{type(exc).__name__}"


def cancel_delegation(
    task_id: str, repo_root: Path | None = None, *, reason: str = "cancelled_by_operator"
) -> tuple[bool, str | None]:
    return update_status(task_id, TaskStatus.CANCELLED, repo_root, status_reason=reason)


def list_tasks(repo_root: Path | None = None, limit: int = 200) -> list[str]:
    tdir = _tasks_dir(repo_root)
    if not tdir.exists():
        return []
    out: list[str] = []
    try:
        for child in sorted(tdir.iterdir()):
            if child.is_dir():
                out.append(child.name)
                if len(out) >= int(limit):
                    break
    except Exception as exc:
        logger.error("Failed to list tasks: %s", exc)
    return out


def read_audit(task_id: str, repo_root: Path | None = None, limit: int = 200) -> list[dict[str, Any]]:
    path = _audit_path(task_id, repo_root)
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        tail = lines[-int(limit) :] if limit and limit > 0 else lines
        out: list[dict[str, Any]] = []
        for line in tail:
            try:
                obj = json.loads(line)
                if isinstance(obj, dict):
                    out.append(obj)
            except Exception:
                continue
        return out
    except Exception as exc:
        logger.error("Failed to read audit: %s", exc)
        return []


def _print_json(obj: Any) -> None:
    print(json.dumps(obj, indent=2, ensure_ascii=False, default=str))


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="Local delegation record manager (FRANCIS).")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_create = sub.add_parser("create", help="Create a new delegation record")
    p_create.add_argument("--requester-id", required=True)
    p_create.add_argument("--capability", required=True)
    p_create.add_argument("--objective", required=True)
    p_create.add_argument("--inputs-json", default="{}")
    p_create.add_argument("--priority", type=int, default=5)
    p_create.add_argument("--ttl-sec", type=int, default=3600)

    p_show = sub.add_parser("show", help="Show a delegation record")
    p_show.add_argument("task_id")

    p_cancel = sub.add_parser("cancel", help="Cancel a task")
    p_cancel.add_argument("task_id")
    p_cancel.add_argument("--reason", default="cancelled_by_operator")

    p_list = sub.add_parser("list", help="List tasks")
    p_list.add_argument("--limit", type=int, default=50)

    p_audit = sub.add_parser("audit", help="Show audit tail")
    p_audit.add_argument("task_id")
    p_audit.add_argument("--limit", type=int, default=50)

    args = parser.parse_args(argv)

    if args.cmd == "create":
        try:
            inputs = json.loads(args.inputs_json)
            if not isinstance(inputs, dict):
                raise ValueError("inputs-json must decode to a JSON object")
        except Exception as exc:
            logger.error("Invalid --inputs-json: %s", exc)
            return 2

        record, err = create_delegation(
            DelegationRequest(
                requester_id=args.requester_id,
                capability=args.capability,
                objective=args.objective,
                inputs=inputs,
                priority=args.priority,
                ttl_sec=args.ttl_sec,
            )
        )
        if not record:
            logger.error("Create failed: %s", err)
            return 1
        _print_json(record.to_json_dict())
        return 0

    if args.cmd == "show":
        record, err = read_delegation(args.task_id)
        if not record:
            logger.error("Read failed: %s", err)
            return 1
        _print_json(record.to_json_dict())
        return 0

    if args.cmd == "cancel":
        ok, err = cancel_delegation(args.task_id, reason=args.reason)
        if not ok:
            logger.error("Cancel failed: %s", err)
            return 1
        _print_json({"task_id": args.task_id, "status": "cancelled"})
        return 0

    if args.cmd == "list":
        _print_json({"tasks": list_tasks(limit=args.limit)})
        return 0

    if args.cmd == "audit":
        _print_json({"audit": read_audit(args.task_id, limit=args.limit)})
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
