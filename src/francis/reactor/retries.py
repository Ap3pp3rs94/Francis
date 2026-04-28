from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from francis.governance.redaction import redact_governed_display_value, redact_governed_value
from francis.kernel.paths import data_dir


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""


def _safe_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    if isinstance(value, bool):
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, parsed))


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _filtered_record(record: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in record.items() if value not in ("", {}, [])}


def _display(record: dict[str, Any]) -> dict[str, Any]:
    redacted = redact_governed_display_value(record)
    return redacted if isinstance(redacted, dict) else {}


def _retry_root() -> Path:
    return data_dir() / "reactor" / "retries"


def _retry_schedule_id(event_id: str, candidate_id: str) -> str:
    digest = hashlib.sha256(f"{event_id}:{candidate_id}".encode("utf-8")).hexdigest()[:12]
    return f"rrs_{digest}"


def _retry_schedule_path(retry_schedule_id: str) -> Path | None:
    cleaned = _safe_str(retry_schedule_id).strip()
    if not cleaned or "/" in cleaned or "\\" in cleaned or ".." in cleaned:
        return None
    return _retry_root() / f"{cleaned}.json"


def _atomic_write_json(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    os.replace(tmp, path)


def _read_raw(path: Path) -> dict[str, Any] | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None
    return raw if isinstance(raw, dict) else None


def _read(path: Path) -> dict[str, Any] | None:
    raw = _read_raw(path)
    return _display(raw) if raw is not None else None


def _receipt_reference(receipt: dict[str, Any]) -> str:
    for key in ("retry_schedule_id", "candidate_id", "receipt_id", "event_id"):
        value = _safe_str(receipt.get(key)).strip()
        if value:
            return value
    return ""


def _retry_schedule_item(
    *,
    event: dict[str, Any],
    source_receipt: dict[str, Any],
    actor: str,
    reason: str,
    ts: int,
) -> dict[str, Any]:
    event_id = _safe_str(event.get("event_id") or event.get("id")).strip()
    candidate_id = _safe_str(source_receipt.get("candidate_id")).strip()
    retry_schedule_id = _retry_schedule_id(event_id, candidate_id)
    source_snapshot = {
        **source_receipt,
        "retry_schedule_id": retry_schedule_id,
        "retry_schedule_receipt_id": retry_schedule_id,
        "retry_scheduled": True,
    }
    trigger = _as_dict(event.get("trigger"))
    classification = _as_dict(event.get("classification"))
    bounds = _as_dict(event.get("bounds"))
    due_after_ts = _safe_int(source_receipt.get("next_retry_after_ts"), default=0, minimum=0, maximum=2_147_483_647)
    if due_after_ts <= 0:
        due_after_ts = ts
    item = {
        "kind": "reactor.retry_schedule.item",
        "retry_schedule_id": retry_schedule_id,
        "id": retry_schedule_id,
        "event_id": event_id,
        "status": "scheduled",
        "route": "retry_backoff",
        "gate": _safe_str(source_receipt.get("gate")).strip() or "dispatch_engine_not_implemented",
        "stable_state": _safe_str(source_receipt.get("stable_state")).strip() or "awaiting_dispatch_engine",
        "next_step": "wait_until_retry_due_before_dispatch_attempt",
        "candidate_id": candidate_id,
        "source_receipt_kind": _safe_str(source_receipt.get("kind")).strip(),
        "source_receipt_ref": _receipt_reference(source_receipt),
        "source_receipt": source_snapshot,
        "trigger": {
            "source": trigger.get("source"),
            "type": trigger.get("type"),
            "summary": trigger.get("summary"),
            "mission_id": trigger.get("mission_id"),
            "operation_id": trigger.get("operation_id"),
            "trace_id": trigger.get("trace_id"),
            "run_id": trigger.get("run_id"),
        },
        "classification": {
            "mode": classification.get("mode"),
            "risk_tier": classification.get("risk_tier"),
            "action_class": classification.get("action_class"),
            "approval_required": classification.get("approval_required"),
        },
        "budget_snapshot": {
            "max_actions": bounds.get("max_actions"),
            "max_runtime_seconds": bounds.get("max_runtime_seconds"),
            "max_retries": bounds.get("max_retries"),
            "backoff_seconds": bounds.get("backoff_seconds"),
            "stop_conditions": bounds.get("stop_conditions"),
        },
        "attempt_count": source_receipt.get("attempt_count"),
        "max_retries": source_receipt.get("max_retries"),
        "remaining_retries": source_receipt.get("remaining_retries"),
        "backoff_seconds": source_receipt.get("backoff_seconds"),
        "due_after_ts": due_after_ts,
        "actor": actor,
        "reason": reason,
        "created_ts": ts,
        "updated_ts": ts,
        "retry_scheduled": True,
        "retry_started": False,
        "execution_started": False,
        "dispatch_applied": False,
        "applied": False,
        "governance": {
            "gate": "reactor_retry_schedule_queue",
            "execution_authority": False,
            "dispatch_authority": False,
            "retry_authority": False,
            "retry_execution_authority": False,
            "deadletter_resolution_authority": False,
            "escalation_authority": False,
            "memory_write": False,
        },
    }
    redacted = redact_governed_value(_filtered_record(item))
    return redacted if isinstance(redacted, dict) else {}


def _schedule_receipt(
    *,
    item: dict[str, Any],
    source_receipt: dict[str, Any],
    actor: str,
    reason: str,
    ts: int,
    created: bool,
) -> dict[str, Any]:
    receipt = {
        "kind": "reactor.retry.schedule.receipt",
        "retry_schedule_id": item.get("retry_schedule_id"),
        "event_id": item.get("event_id"),
        "candidate_id": item.get("candidate_id"),
        "status": "scheduled" if created else "already_scheduled",
        "route": "retry_backoff",
        "gate": item.get("gate"),
        "stable_state": item.get("stable_state"),
        "next_step": item.get("next_step"),
        "source_receipt_kind": _safe_str(source_receipt.get("kind")).strip(),
        "source_receipt_ref": _receipt_reference(source_receipt),
        "attempt_count": item.get("attempt_count"),
        "max_retries": item.get("max_retries"),
        "remaining_retries": item.get("remaining_retries"),
        "backoff_seconds": item.get("backoff_seconds"),
        "due_after_ts": item.get("due_after_ts"),
        "actor": actor,
        "reason": reason,
        "ts": ts,
        "retry_scheduled": True,
        "created": created,
        "retry_started": False,
        "execution_started": False,
        "dispatch_applied": False,
        "applied": False,
        "governance": {
            "gate": "reactor_retry_schedule_queue",
            "execution_authority": False,
            "dispatch_authority": False,
            "retry_authority": False,
            "retry_execution_authority": False,
            "deadletter_resolution_authority": False,
            "escalation_authority": False,
            "memory_write": False,
        },
    }
    redacted = redact_governed_value(_filtered_record(receipt))
    return redacted if isinstance(redacted, dict) else {}


def _due_receipt(
    *,
    item: dict[str, Any],
    actor: str,
    reason: str,
    ts: int,
    status: str,
    applied: bool,
) -> dict[str, Any]:
    retry_due = status in {"due", "already_due"}
    receipt = {
        "kind": "reactor.retry.due.receipt",
        "retry_schedule_id": item.get("retry_schedule_id"),
        "event_id": item.get("event_id"),
        "candidate_id": item.get("candidate_id"),
        "status": status,
        "route": "retry_due" if retry_due else "retry_backoff",
        "gate": item.get("gate"),
        "stable_state": "retry_due" if retry_due else item.get("stable_state"),
        "next_step": "record_bounded_dispatch_attempt_for_due_retry"
        if retry_due
        else "wait_until_retry_due_before_dispatch_attempt",
        "source_receipt_kind": "reactor.retry_schedule.item",
        "source_receipt_ref": item.get("retry_schedule_id"),
        "attempt_count": item.get("attempt_count"),
        "max_retries": item.get("max_retries"),
        "remaining_retries": item.get("remaining_retries"),
        "backoff_seconds": item.get("backoff_seconds"),
        "due_after_ts": item.get("due_after_ts"),
        "due_recorded_ts": ts if retry_due else 0,
        "actor": actor,
        "reason": reason,
        "ts": ts,
        "retry_due": retry_due,
        "retry_started": False,
        "execution_started": False,
        "dispatch_applied": False,
        "applied": applied,
        "governance": {
            "gate": "reactor_retry_due_handoff",
            "execution_authority": False,
            "dispatch_authority": False,
            "retry_authority": False,
            "retry_execution_authority": False,
            "deadletter_resolution_authority": False,
            "escalation_authority": False,
            "memory_write": False,
        },
    }
    redacted = redact_governed_value(_filtered_record(receipt))
    return redacted if isinstance(redacted, dict) else {}


def schedule_retry(
    *,
    event: dict[str, Any],
    source_receipt: dict[str, Any],
    actor: str = "",
    reason: str = "",
    ts: int = 0,
) -> dict[str, Any]:
    item = _retry_schedule_item(event=event, source_receipt=source_receipt, actor=actor, reason=reason, ts=ts)
    retry_schedule_id = _safe_str(item.get("retry_schedule_id")).strip()
    path = _retry_schedule_path(retry_schedule_id)
    if path is None:
        return {"ok": False, "created": False, "error": "invalid_retry_schedule_id", "item": {}, "receipt": {}}

    existing = _read_raw(path) if path.exists() and path.is_file() else None
    created = existing is None
    persisted = existing if existing is not None else item
    if created:
        _atomic_write_json(path, item)

    receipt = _schedule_receipt(
        item=persisted,
        source_receipt=source_receipt,
        actor=actor,
        reason=reason,
        ts=ts,
        created=created,
    )
    return {
        "ok": True,
        "created": created,
        "item": _display(persisted),
        "receipt": _display(receipt),
    }


def mark_retry_due(
    *,
    retry_schedule_id: str,
    actor: str = "",
    reason: str = "",
    ts: int = 0,
) -> dict[str, Any]:
    path = _retry_schedule_path(retry_schedule_id)
    if path is None or not path.exists() or not path.is_file():
        return {"ok": False, "applied": False, "error": "not_found", "item": {}, "receipt": {}}

    item = _read_raw(path)
    if item is None:
        return {"ok": False, "applied": False, "error": "unreadable_retry_schedule", "item": {}, "receipt": {}}

    due_after_ts = _safe_int(item.get("due_after_ts"), default=0, minimum=0, maximum=2_147_483_647)
    current_status = _safe_str(item.get("status")).strip() or "scheduled"
    if current_status == "due":
        receipt = _due_receipt(item=item, actor=actor, reason=reason, ts=ts, status="already_due", applied=False)
        return {
            "ok": True,
            "applied": False,
            "status": "already_due",
            "item": _display(item),
            "receipt": _display(receipt),
        }
    if due_after_ts > ts:
        receipt = _due_receipt(item=item, actor=actor, reason=reason, ts=ts, status="not_due", applied=False)
        return {
            "ok": True,
            "applied": False,
            "status": "not_due",
            "item": _display(item),
            "receipt": _display(receipt),
        }

    updated = {
        **item,
        "status": "due",
        "route": "retry_due",
        "stable_state": "retry_due",
        "next_step": "record_bounded_dispatch_attempt_for_due_retry",
        "due_recorded_ts": ts,
        "updated_ts": ts,
        "retry_due": True,
        "retry_started": False,
        "execution_started": False,
        "dispatch_applied": False,
        "applied": False,
        "governance": {
            **_as_dict(item.get("governance")),
            "gate": "reactor_retry_due_handoff",
            "execution_authority": False,
            "dispatch_authority": False,
            "retry_authority": False,
            "retry_execution_authority": False,
            "deadletter_resolution_authority": False,
            "escalation_authority": False,
            "memory_write": False,
        },
    }
    _atomic_write_json(path, updated)
    receipt = _due_receipt(item=updated, actor=actor, reason=reason, ts=ts, status="due", applied=True)
    return {
        "ok": True,
        "applied": True,
        "status": "due",
        "item": _display(updated),
        "receipt": _display(receipt),
    }


def list_retry_schedules(*, limit: int = 200, status: str | None = None) -> list[dict[str, Any]]:
    root = _retry_root()
    if not root.exists():
        return []
    status_filter = _safe_str(status).strip().lower()
    items: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.json")):
        if not path.is_file():
            continue
        item = _read(path)
        if not item:
            continue
        if status_filter and _safe_str(item.get("status")).strip().lower() != status_filter:
            continue
        items.append(item)
    items.sort(
        key=lambda item: (
            _safe_int(item.get("due_after_ts"), default=0, minimum=0, maximum=2_147_483_647),
            _safe_str(item.get("retry_schedule_id")),
        )
    )
    return items[: max(1, min(int(limit), 5000))]


def get_retry_schedule(retry_schedule_id: str) -> dict[str, Any] | None:
    path = _retry_schedule_path(retry_schedule_id)
    if path is None or not path.exists() or not path.is_file():
        return None
    return _read(path)
