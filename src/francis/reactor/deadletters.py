from __future__ import annotations

import json
import os
import re
import hashlib
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


def _deadletter_root() -> Path:
    return data_dir() / "reactor" / "deadletters"


def _path_token(value: Any) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", _safe_str(value).strip()).strip("._")
    return cleaned[:160] or "unknown"


def _deadletter_id(event_id: str, gate: str) -> str:
    digest = hashlib.sha256(f"{event_id}:{gate}".encode("utf-8")).hexdigest()[:12]
    return f"rdl_{digest}"


def _deadletter_path(deadletter_id: str) -> Path | None:
    cleaned = _safe_str(deadletter_id).strip()
    if not cleaned or "/" in cleaned or "\\" in cleaned or ".." in cleaned:
        return None
    return _deadletter_root() / f"{cleaned}.json"


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
    for key in ("deadletter_id", "candidate_id", "exhaustion_id", "blocker_id", "receipt_id", "event_id"):
        value = _safe_str(receipt.get(key)).strip()
        if value:
            return value
    return ""


def _deadletter_item(
    *,
    event: dict[str, Any],
    source_receipt: dict[str, Any],
    actor: str,
    reason: str,
    ts: int,
) -> dict[str, Any]:
    event_id = _safe_str(event.get("event_id") or event.get("id")).strip()
    trigger = _as_dict(event.get("trigger"))
    classification = _as_dict(event.get("classification"))
    bounds = _as_dict(event.get("bounds"))
    gate = (
        _safe_str(source_receipt.get("gate")).strip()
        or _safe_str(source_receipt.get("stable_state")).strip()
        or "deadletter"
    )
    deadletter_id = _deadletter_id(event_id, gate)
    source_kind = _safe_str(source_receipt.get("kind")).strip()
    source_ref = _receipt_reference(source_receipt)
    item = {
        "kind": "reactor.deadletter.item",
        "deadletter_id": deadletter_id,
        "id": deadletter_id,
        "event_id": event_id,
        "status": "queued",
        "route": "deadletter",
        "source_route": _safe_str(source_receipt.get("route")).strip() or "deadletter_candidate",
        "gate": gate,
        "stable_state": _safe_str(source_receipt.get("stable_state") or event.get("stable_state")).strip(),
        "next_step": "review_deadletter_item_before_escalation_or_recovery",
        "source_receipt_kind": source_kind,
        "source_receipt_ref": source_ref,
        "source_receipt": source_receipt,
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
        "actor": actor,
        "reason": reason,
        "created_ts": ts,
        "updated_ts": ts,
        "execution_started": False,
        "retry_started": False,
        "escalation_started": False,
        "applied": False,
        "governance": {
            "gate": "reactor_deadletter_queue",
            "execution_authority": False,
            "dispatch_authority": False,
            "retry_authority": False,
            "deadletter_resolution_authority": False,
            "escalation_authority": False,
            "memory_write": False,
        },
    }
    redacted = redact_governed_value(_filtered_record(item))
    return redacted if isinstance(redacted, dict) else {}


def _enqueue_receipt(
    *,
    item: dict[str, Any],
    source_receipt: dict[str, Any],
    actor: str,
    reason: str,
    ts: int,
    created: bool,
) -> dict[str, Any]:
    receipt = {
        "kind": "reactor.deadletter.enqueue.receipt",
        "deadletter_id": item.get("deadletter_id"),
        "event_id": item.get("event_id"),
        "status": "queued" if created else "already_queued",
        "route": "deadletter",
        "source_route": item.get("source_route"),
        "gate": item.get("gate"),
        "stable_state": item.get("stable_state"),
        "next_step": item.get("next_step"),
        "source_receipt_kind": _safe_str(source_receipt.get("kind")).strip(),
        "source_receipt_ref": _receipt_reference(source_receipt),
        "actor": actor,
        "reason": reason,
        "ts": ts,
        "deadletter_enqueued": True,
        "created": created,
        "execution_started": False,
        "retry_started": False,
        "escalation_started": False,
        "applied": False,
    }
    redacted = redact_governed_value(_filtered_record(receipt))
    return redacted if isinstance(redacted, dict) else {}


def queue_deadletter(
    *,
    event: dict[str, Any],
    source_receipt: dict[str, Any],
    actor: str = "",
    reason: str = "",
    ts: int = 0,
) -> dict[str, Any]:
    item = _deadletter_item(event=event, source_receipt=source_receipt, actor=actor, reason=reason, ts=ts)
    deadletter_id = _safe_str(item.get("deadletter_id")).strip()
    path = _deadletter_path(deadletter_id)
    if path is None:
        return {"ok": False, "created": False, "error": "invalid_deadletter_id", "item": {}, "receipt": {}}

    existing = _read_raw(path) if path.exists() and path.is_file() else None
    created = existing is None
    persisted = existing if existing is not None else item
    if created:
        _atomic_write_json(path, item)

    receipt = _enqueue_receipt(
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


def list_deadletters(*, limit: int = 200, status: str | None = None) -> list[dict[str, Any]]:
    root = _deadletter_root()
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
            _safe_int(item.get("created_ts"), default=0, minimum=0, maximum=2_147_483_647),
            _safe_str(item.get("deadletter_id")),
        ),
        reverse=True,
    )
    return items[: max(1, min(int(limit), 5000))]


def get_deadletter(deadletter_id: str) -> dict[str, Any] | None:
    path = _deadletter_path(deadletter_id)
    if path is None or not path.exists() or not path.is_file():
        return None
    return _read(path)
