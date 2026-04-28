from __future__ import annotations

import json
import os
import re
import hashlib
from pathlib import Path
from typing import Any

from francis.governance.redaction import redact_governed_display_value, redact_governed_value
from francis.kernel.paths import data_dir
from francis.reactor.external_escalation import external_escalation_adapter_preflight


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


def _external_delivery_root() -> Path:
    return data_dir() / "reactor" / "external_escalation_outbox"


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


def _external_delivery_path(delivery_id: str) -> Path | None:
    cleaned = _safe_str(delivery_id).strip()
    if not cleaned or "/" in cleaned or "\\" in cleaned or ".." in cleaned:
        return None
    return _external_delivery_root() / f"{cleaned}.json"


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


def _review_decision(value: Any) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", _safe_str(value).strip().lower()).strip("_")
    if normalized in {"retry_later", "retry", "recover", "recovery"}:
        return "retry_later"
    if normalized in {"escalate_later", "escalate", "escalation"}:
        return "escalate_later"
    if normalized in {"operator_reviewed", "reviewed", "acknowledge", "acknowledged"}:
        return "operator_reviewed"
    return "defer"


def _review_next_step(decision: str) -> str:
    if decision == "retry_later":
        return "wait_for_explicit_deadletter_recovery_path_before_retry"
    if decision == "escalate_later":
        return "wait_for_explicit_deadletter_escalation_path"
    if decision == "operator_reviewed":
        return "keep_deadletter_review_visible_until_resolution_or_escalation"
    return "defer_deadletter_until_resolution_or_escalation_path_exists"


def _review_receipt(
    *,
    item: dict[str, Any],
    actor: str,
    reason: str,
    decision: str,
    ts: int,
    status: str,
    applied: bool,
) -> dict[str, Any]:
    receipt = {
        "kind": "reactor.deadletter.review.receipt",
        "receipt_id": f"{item.get('deadletter_id')}_review_{decision}",
        "deadletter_id": item.get("deadletter_id"),
        "event_id": item.get("event_id"),
        "status": status,
        "route": "deadletter_review",
        "gate": "reactor_deadletter_review",
        "stable_state": "deadletter_reviewed",
        "next_step": _review_next_step(decision),
        "source_receipt_kind": _safe_str(item.get("kind")).strip(),
        "source_receipt_ref": item.get("deadletter_id"),
        "source_gate": item.get("gate"),
        "review_decision": decision,
        "actor": actor,
        "reason": reason,
        "ts": ts,
        "reviewed": status in {"reviewed", "already_reviewed"},
        "deadletter_resolved": False,
        "recovery_started": False,
        "execution_started": False,
        "retry_started": False,
        "escalation_started": False,
        "memory_write": False,
        "applied": applied,
        "governance": {
            "gate": "reactor_deadletter_review",
            "execution_authority": False,
            "dispatch_authority": False,
            "retry_authority": False,
            "deadletter_resolution_authority": False,
            "escalation_authority": False,
            "memory_write": False,
        },
    }
    redacted = redact_governed_value(_filtered_record(receipt))
    return redacted if isinstance(redacted, dict) else {}


def _resolution_decision(value: Any) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", _safe_str(value).strip().lower()).strip("_")
    if normalized in {
        "resolve",
        "resolved",
        "resolved_no_action",
        "resolve_no_action",
        "closed",
        "close",
        "no_action",
        "operator_resolved",
    }:
        return "resolved_no_action"
    if normalized in {"escalate", "escalation", "escalate_later", "escalation_pending"}:
        return "escalation_pending"
    return "defer"


def _resolution_state(decision: str) -> tuple[str, str, str]:
    if decision == "resolved_no_action":
        return ("resolved", "deadletter_resolution", "deadletter_resolved")
    if decision == "escalation_pending":
        return ("escalation_pending", "deadletter_escalation", "deadletter_escalation_pending")
    return ("resolution_deferred", "deadletter_review", "deadletter_resolution_deferred")


def _resolution_next_step(decision: str) -> str:
    if decision == "resolved_no_action":
        return "keep_deadletter_resolution_receipt_for_audit"
    if decision == "escalation_pending":
        return "track_escalation_pending_external_or_operator_followup"
    return "keep_deadletter_review_visible_until_resolution_or_escalation"


def _escalation_handoff_next_step() -> str:
    return "operator_or_external_escalation_must_acknowledge_before_recovery_execution"


def _escalation_acknowledgement_next_step() -> str:
    return "wait_for_explicit_recovery_execution_boundary_after_acknowledgement"


def _external_escalation_attempt_next_step() -> str:
    return "queue_recovery_request_or_configure_external_escalation_adapter_before_delivery"


def _external_escalation_delivery_next_step() -> str:
    return "await_local_outbox_external_delivery_processor_or_operator_review"


def _recovery_request_next_step() -> str:
    return "dispatch_recovery_event_through_existing_operation_run_gate"


def _recovery_dispatch_next_step() -> str:
    return "keep_recovery_dispatch_receipt_for_audit"


def _resolution_receipt(
    *,
    item: dict[str, Any],
    actor: str,
    reason: str,
    decision: str,
    ts: int,
    status: str,
    applied: bool,
) -> dict[str, Any]:
    persisted_status, route, stable_state = _resolution_state(decision)
    resolved = persisted_status == "resolved"
    escalation_recorded = persisted_status == "escalation_pending"
    latest_review = _as_dict(item.get("latest_review_receipt"))
    receipt = {
        "kind": "reactor.deadletter.resolution.receipt",
        "receipt_id": f"{item.get('deadletter_id')}_resolution_{decision}",
        "deadletter_id": item.get("deadletter_id"),
        "event_id": item.get("event_id"),
        "status": status,
        "route": route,
        "gate": "reactor_deadletter_resolution",
        "stable_state": stable_state,
        "next_step": _resolution_next_step(decision),
        "source_receipt_kind": _safe_str(item.get("kind")).strip(),
        "source_receipt_ref": item.get("deadletter_id"),
        "source_gate": item.get("gate"),
        "review_receipt_id": latest_review.get("receipt_id"),
        "resolution_decision": decision,
        "actor": actor,
        "reason": reason,
        "ts": ts,
        "deadletter_resolved": resolved,
        "escalation_recorded": escalation_recorded,
        "recovery_started": False,
        "execution_started": False,
        "retry_started": False,
        "escalation_started": False,
        "memory_write": False,
        "applied": applied,
        "governance": {
            "gate": "reactor_deadletter_resolution",
            "execution_authority": False,
            "dispatch_authority": False,
            "retry_authority": False,
            "retry_execution_authority": False,
            "deadletter_disposition_authority": applied,
            "deadletter_resolution_authority": resolved and applied,
            "escalation_authority": False,
            "memory_write": False,
        },
    }
    redacted = redact_governed_value(_filtered_record(receipt))
    return redacted if isinstance(redacted, dict) else {}


def _escalation_handoff_receipt(
    *,
    item: dict[str, Any],
    actor: str,
    reason: str,
    ts: int,
    status: str,
    applied: bool,
) -> dict[str, Any]:
    latest_resolution = _as_dict(item.get("latest_resolution_receipt"))
    source_ref = (
        _safe_str(latest_resolution.get("receipt_id")).strip()
        or _safe_str(latest_resolution.get("deadletter_id")).strip()
        or _safe_str(item.get("deadletter_id")).strip()
    )
    receipt = {
        "kind": "reactor.deadletter.escalation_handoff.receipt",
        "receipt_id": f"{item.get('deadletter_id')}_escalation_handoff",
        "deadletter_id": item.get("deadletter_id"),
        "event_id": item.get("event_id"),
        "status": status,
        "route": "deadletter_escalation_handoff",
        "gate": "reactor_deadletter_escalation_handoff",
        "stable_state": "deadletter_escalation_handoff_recorded",
        "next_step": _escalation_handoff_next_step(),
        "source_receipt_kind": _safe_str(latest_resolution.get("kind")).strip(),
        "source_receipt_ref": source_ref,
        "source_gate": _safe_str(latest_resolution.get("gate") or item.get("gate")).strip(),
        "resolution_receipt_id": latest_resolution.get("receipt_id"),
        "resolution_decision": latest_resolution.get("resolution_decision") or item.get("resolution_decision"),
        "actor": actor,
        "reason": reason,
        "ts": ts,
        "escalation_handoff_recorded": True,
        "external_escalation_started": False,
        "recovery_started": False,
        "execution_started": False,
        "retry_started": False,
        "escalation_started": False,
        "memory_write": False,
        "applied": applied,
        "governance": {
            "gate": "reactor_deadletter_escalation_handoff",
            "execution_authority": False,
            "dispatch_authority": False,
            "retry_authority": False,
            "retry_execution_authority": False,
            "deadletter_disposition_authority": False,
            "deadletter_resolution_authority": False,
            "escalation_authority": False,
            "memory_write": False,
        },
    }
    redacted = redact_governed_value(_filtered_record(receipt))
    return redacted if isinstance(redacted, dict) else {}


def _escalation_acknowledgement_receipt(
    *,
    item: dict[str, Any],
    actor: str,
    reason: str,
    ts: int,
    status: str,
    applied: bool,
) -> dict[str, Any]:
    latest_handoff = _as_dict(item.get("latest_escalation_handoff_receipt"))
    source_ref = (
        _safe_str(latest_handoff.get("receipt_id")).strip()
        or _safe_str(latest_handoff.get("deadletter_id")).strip()
        or _safe_str(item.get("deadletter_id")).strip()
    )
    receipt = {
        "kind": "reactor.deadletter.escalation_acknowledgement.receipt",
        "receipt_id": f"{item.get('deadletter_id')}_escalation_acknowledgement",
        "deadletter_id": item.get("deadletter_id"),
        "event_id": item.get("event_id"),
        "status": status,
        "route": "deadletter_escalation_acknowledgement",
        "gate": "reactor_deadletter_escalation_acknowledgement",
        "stable_state": "deadletter_escalation_acknowledged",
        "next_step": _escalation_acknowledgement_next_step(),
        "source_receipt_kind": _safe_str(latest_handoff.get("kind")).strip(),
        "source_receipt_ref": source_ref,
        "source_gate": _safe_str(latest_handoff.get("gate") or item.get("gate")).strip(),
        "escalation_handoff_receipt_id": latest_handoff.get("receipt_id"),
        "resolution_decision": latest_handoff.get("resolution_decision") or item.get("resolution_decision"),
        "actor": actor,
        "reason": reason,
        "ts": ts,
        "escalation_acknowledged": True,
        "external_escalation_started": False,
        "recovery_started": False,
        "execution_started": False,
        "retry_started": False,
        "escalation_started": False,
        "memory_write": False,
        "applied": applied,
        "governance": {
            "gate": "reactor_deadletter_escalation_acknowledgement",
            "execution_authority": False,
            "dispatch_authority": False,
            "retry_authority": False,
            "retry_execution_authority": False,
            "deadletter_disposition_authority": False,
            "deadletter_resolution_authority": False,
            "escalation_authority": False,
            "memory_write": False,
        },
    }
    redacted = redact_governed_value(_filtered_record(receipt))
    return redacted if isinstance(redacted, dict) else {}


def _recovery_request_receipt(
    *,
    item: dict[str, Any],
    actor: str,
    reason: str,
    ts: int,
    status: str,
    applied: bool,
    operation_id: str,
    recovery_event_id: str,
) -> dict[str, Any]:
    latest_external_attempt = _as_dict(item.get("latest_external_escalation_attempt_receipt"))
    latest_acknowledgement = _as_dict(item.get("latest_escalation_acknowledgement_receipt"))
    source_receipt = latest_external_attempt or latest_acknowledgement
    source_ref = (
        _safe_str(source_receipt.get("receipt_id")).strip()
        or _safe_str(source_receipt.get("deadletter_id")).strip()
        or _safe_str(item.get("deadletter_id")).strip()
    )
    receipt = {
        "kind": "reactor.deadletter.recovery_request.receipt",
        "receipt_id": f"{item.get('deadletter_id')}_recovery_request",
        "deadletter_id": item.get("deadletter_id"),
        "event_id": item.get("event_id"),
        "status": status,
        "route": "deadletter_recovery_request",
        "gate": "reactor_deadletter_recovery_request",
        "stable_state": "deadletter_recovery_requested",
        "next_step": _recovery_request_next_step(),
        "source_receipt_kind": _safe_str(source_receipt.get("kind")).strip(),
        "source_receipt_ref": source_ref,
        "source_gate": _safe_str(source_receipt.get("gate") or item.get("gate")).strip(),
        "escalation_acknowledgement_receipt_id": latest_acknowledgement.get("receipt_id"),
        "external_escalation_attempt_receipt_id": _safe_str(latest_external_attempt.get("receipt_id")).strip(),
        "resolution_decision": source_receipt.get("resolution_decision") or item.get("resolution_decision"),
        "operation_id": operation_id,
        "recovery_event_id": recovery_event_id,
        "actor": actor,
        "reason": reason,
        "ts": ts,
        "recovery_requested": True,
        "recovery_event_enqueued": bool(recovery_event_id),
        "external_escalation_started": False,
        "recovery_started": False,
        "execution_started": False,
        "retry_started": False,
        "escalation_started": False,
        "memory_write": False,
        "applied": applied,
        "governance": {
            "gate": "reactor_deadletter_recovery_request",
            "execution_authority": False,
            "dispatch_authority": False,
            "retry_authority": False,
            "retry_execution_authority": False,
            "deadletter_disposition_authority": False,
            "deadletter_resolution_authority": False,
            "recovery_request_authority": applied,
            "escalation_authority": False,
            "memory_write": False,
        },
    }
    redacted = redact_governed_value(_filtered_record(receipt))
    return redacted if isinstance(redacted, dict) else {}


def _external_escalation_attempt_receipt(
    *,
    item: dict[str, Any],
    actor: str,
    reason: str,
    external_channel: str,
    external_target: str,
    adapter: str,
    ts: int,
    status: str,
    applied: bool,
) -> dict[str, Any]:
    latest_acknowledgement = _as_dict(item.get("latest_escalation_acknowledgement_receipt"))
    preflight = external_escalation_adapter_preflight(
        adapter,
        channel=external_channel,
        target=external_target,
    )
    source_ref = (
        _safe_str(latest_acknowledgement.get("receipt_id")).strip()
        or _safe_str(latest_acknowledgement.get("deadletter_id")).strip()
        or _safe_str(item.get("deadletter_id")).strip()
    )
    receipt = {
        "kind": "reactor.deadletter.external_escalation_attempt.receipt",
        "receipt_id": f"{item.get('deadletter_id')}_external_escalation_attempt",
        "deadletter_id": item.get("deadletter_id"),
        "event_id": item.get("event_id"),
        "status": status,
        "route": "deadletter_external_escalation_attempt",
        "gate": "reactor_deadletter_external_escalation_attempt",
        "stable_state": "deadletter_external_escalation_attempt_recorded",
        "next_step": preflight.get("next_step") or _external_escalation_attempt_next_step(),
        "source_receipt_kind": _safe_str(latest_acknowledgement.get("kind")).strip(),
        "source_receipt_ref": source_ref,
        "source_gate": _safe_str(latest_acknowledgement.get("gate") or item.get("gate")).strip(),
        "escalation_acknowledgement_receipt_id": latest_acknowledgement.get("receipt_id"),
        "resolution_decision": latest_acknowledgement.get("resolution_decision") or item.get("resolution_decision"),
        "external_channel": external_channel,
        "external_target": external_target,
        "external_adapter": preflight.get("external_adapter") or adapter,
        "external_adapter_declared": bool(preflight.get("external_adapter_declared")),
        "external_adapter_known": bool(preflight.get("external_adapter_known")),
        "external_adapter_configured": bool(preflight.get("external_adapter_configured")),
        "external_adapter_status": preflight.get("external_adapter_status"),
        "external_delivery_mode": preflight.get("external_delivery_mode"),
        "external_delivery_ready": bool(preflight.get("external_delivery_ready")),
        "external_delivery_queued": False,
        "external_delivery_blocker": preflight.get("external_delivery_blocker"),
        "missing_requirements": preflight.get("missing_requirements"),
        "actor": actor,
        "reason": reason,
        "ts": ts,
        "external_escalation_attempt_recorded": True,
        "external_escalation_started": False,
        "external_delivery_started": False,
        "recovery_started": False,
        "execution_started": False,
        "dispatch_applied": False,
        "retry_started": False,
        "escalation_started": False,
        "memory_write": False,
        "completion_claimed": False,
        "completion_claim_allowed": False,
        "applied": applied,
        "governance": {
            "gate": "reactor_deadletter_external_escalation_attempt",
            "execution_authority": False,
            "dispatch_authority": False,
            "retry_authority": False,
            "retry_execution_authority": False,
            "deadletter_disposition_authority": False,
            "deadletter_resolution_authority": False,
            "external_escalation_authority": False,
            "escalation_authority": False,
            "approval_authority": False,
            "promotion_authority": False,
            "memory_write": False,
        },
    }
    redacted = redact_governed_value(_filtered_record(receipt))
    return redacted if isinstance(redacted, dict) else {}


def _local_outbox_delivery_id(item: dict[str, Any], source_receipt: dict[str, Any]) -> str:
    deadletter_id = _safe_str(item.get("deadletter_id")).strip()
    receipt_id = _safe_str(source_receipt.get("receipt_id")).strip()
    digest = hashlib.sha256(f"{deadletter_id}:{receipt_id}:local_outbox".encode("utf-8")).hexdigest()[:12]
    return f"red_{digest}"


def _local_outbox_delivery_item(
    *,
    item: dict[str, Any],
    source_receipt: dict[str, Any],
    actor: str,
    reason: str,
    ts: int,
) -> dict[str, Any]:
    delivery_id = _local_outbox_delivery_id(item, source_receipt)
    delivery = {
        "kind": "reactor.deadletter.external_escalation.local_outbox.item",
        "delivery_id": delivery_id,
        "id": delivery_id,
        "deadletter_id": item.get("deadletter_id"),
        "event_id": item.get("event_id"),
        "status": "queued",
        "route": "deadletter_external_escalation_delivery",
        "gate": "reactor_deadletter_external_escalation_delivery",
        "stable_state": "deadletter_external_escalation_delivery_queued",
        "next_step": _external_escalation_delivery_next_step(),
        "source_receipt_kind": _safe_str(source_receipt.get("kind")).strip(),
        "source_receipt_ref": _safe_str(source_receipt.get("receipt_id")).strip()
        or _safe_str(source_receipt.get("deadletter_id")).strip(),
        "source_gate": _safe_str(source_receipt.get("gate") or item.get("gate")).strip(),
        "external_escalation_attempt_receipt_id": source_receipt.get("receipt_id"),
        "external_channel": source_receipt.get("external_channel"),
        "external_target": source_receipt.get("external_target"),
        "external_adapter": source_receipt.get("external_adapter"),
        "external_adapter_status": source_receipt.get("external_adapter_status"),
        "external_delivery_mode": source_receipt.get("external_delivery_mode"),
        "external_delivery_ready": bool(source_receipt.get("external_delivery_ready")),
        "external_delivery_queued": True,
        "external_delivery_started": False,
        "external_message_sent": False,
        "external_network_send": False,
        "external_escalation_started": False,
        "recovery_started": False,
        "execution_started": False,
        "dispatch_applied": False,
        "retry_started": False,
        "escalation_started": False,
        "memory_write": False,
        "completion_claimed": False,
        "completion_claim_allowed": False,
        "actor": actor,
        "reason": reason,
        "created_ts": ts,
        "updated_ts": ts,
        "applied": False,
        "governance": {
            "gate": "reactor_deadletter_external_escalation_delivery",
            "execution_authority": False,
            "dispatch_authority": False,
            "retry_authority": False,
            "retry_execution_authority": False,
            "deadletter_disposition_authority": False,
            "deadletter_resolution_authority": False,
            "external_delivery_queue_authority": True,
            "external_delivery_authority": False,
            "external_escalation_authority": False,
            "escalation_authority": False,
            "approval_authority": False,
            "promotion_authority": False,
            "memory_write": False,
        },
    }
    redacted = redact_governed_value(_filtered_record(delivery))
    return redacted if isinstance(redacted, dict) else {}


def _external_escalation_delivery_receipt(
    *,
    item: dict[str, Any],
    source_receipt: dict[str, Any],
    delivery_item: dict[str, Any],
    actor: str,
    reason: str,
    ts: int,
    status: str,
    applied: bool,
) -> dict[str, Any]:
    source_ref = (
        _safe_str(source_receipt.get("receipt_id")).strip()
        or _safe_str(source_receipt.get("deadletter_id")).strip()
        or _safe_str(item.get("deadletter_id")).strip()
    )
    receipt = {
        "kind": "reactor.deadletter.external_escalation_delivery.receipt",
        "receipt_id": f"{item.get('deadletter_id')}_external_escalation_delivery",
        "delivery_id": delivery_item.get("delivery_id"),
        "outbox_item_kind": delivery_item.get("kind"),
        "deadletter_id": item.get("deadletter_id"),
        "event_id": item.get("event_id"),
        "status": status,
        "route": "deadletter_external_escalation_delivery",
        "gate": "reactor_deadletter_external_escalation_delivery",
        "stable_state": "deadletter_external_escalation_delivery_queued",
        "next_step": _external_escalation_delivery_next_step(),
        "source_receipt_kind": _safe_str(source_receipt.get("kind")).strip(),
        "source_receipt_ref": source_ref,
        "source_gate": _safe_str(source_receipt.get("gate") or item.get("gate")).strip(),
        "external_escalation_attempt_receipt_id": source_receipt.get("receipt_id"),
        "external_channel": source_receipt.get("external_channel"),
        "external_target": source_receipt.get("external_target"),
        "external_adapter": source_receipt.get("external_adapter"),
        "external_adapter_status": source_receipt.get("external_adapter_status"),
        "external_delivery_mode": source_receipt.get("external_delivery_mode"),
        "external_delivery_ready": bool(source_receipt.get("external_delivery_ready")),
        "external_delivery_queued": True,
        "external_delivery_started": False,
        "external_message_sent": False,
        "external_network_send": False,
        "external_escalation_started": False,
        "recovery_started": False,
        "execution_started": False,
        "dispatch_applied": False,
        "retry_started": False,
        "escalation_started": False,
        "memory_write": False,
        "completion_claimed": False,
        "completion_claim_allowed": False,
        "actor": actor,
        "reason": reason,
        "ts": ts,
        "applied": applied,
        "governance": {
            "gate": "reactor_deadletter_external_escalation_delivery",
            "execution_authority": False,
            "dispatch_authority": False,
            "retry_authority": False,
            "retry_execution_authority": False,
            "deadletter_disposition_authority": False,
            "deadletter_resolution_authority": False,
            "external_delivery_queue_authority": applied,
            "external_delivery_authority": False,
            "external_escalation_authority": False,
            "escalation_authority": False,
            "approval_authority": False,
            "promotion_authority": False,
            "memory_write": False,
        },
    }
    redacted = redact_governed_value(_filtered_record(receipt))
    return redacted if isinstance(redacted, dict) else {}


def _external_delivery_processor_readiness(item: dict[str, Any]) -> dict[str, Any]:
    status = _safe_str(item.get("status")).strip().lower()
    delivery_mode = _safe_str(item.get("external_delivery_mode")).strip().lower()
    adapter = _safe_str(item.get("external_adapter")).strip().lower()
    blockers: list[str] = []
    if status != "queued":
        blockers.append("delivery_not_queued")
    if delivery_mode != "local_outbox" or adapter != "local_outbox":
        blockers.append("local_outbox_delivery_required")
    if bool(item.get("external_delivery_started")):
        blockers.append("external_delivery_already_started")
    if bool(item.get("external_message_sent")) or bool(item.get("external_network_send")):
        blockers.append("external_message_already_sent")
    if not _safe_str(item.get("deadletter_id")).strip():
        blockers.append("deadletter_id_required")
    if not _safe_str(item.get("event_id")).strip():
        blockers.append("event_id_required")

    ready = not blockers
    processor_status = "ready" if ready else "blocked"
    next_step = (
        "run_explicit_local_outbox_delivery_processor_after_operator_approval"
        if ready
        else "repair_local_outbox_delivery_metadata_before_processor_handoff"
    )
    readiness = {
        "kind": "reactor.deadletter.external_escalation.delivery_processor_readiness",
        "delivery_id": item.get("delivery_id"),
        "deadletter_id": item.get("deadletter_id"),
        "event_id": item.get("event_id"),
        "status": processor_status,
        "delivery_status": item.get("status"),
        "route": "deadletter_external_escalation_delivery_processor_readiness",
        "gate": "reactor_external_escalation_delivery_processor_readiness",
        "stable_state": item.get("stable_state"),
        "next_step": next_step,
        "delivery_processor_ready": ready,
        "delivery_processor_status": processor_status,
        "delivery_processor_mode": "local_outbox",
        "delivery_processor_blockers": blockers,
        "external_adapter": item.get("external_adapter"),
        "external_channel": item.get("external_channel"),
        "external_target": item.get("external_target"),
        "external_delivery_mode": item.get("external_delivery_mode"),
        "external_delivery_queued": bool(item.get("external_delivery_queued")),
        "external_delivery_started": bool(item.get("external_delivery_started")),
        "external_message_sent": bool(item.get("external_message_sent")),
        "external_network_send": bool(item.get("external_network_send")),
        "external_escalation_started": bool(item.get("external_escalation_started")),
        "execution_started": bool(item.get("execution_started")),
        "dispatch_applied": bool(item.get("dispatch_applied")),
        "memory_write": bool(item.get("memory_write")),
        "completion_claim_allowed": False,
        "created_ts": item.get("created_ts"),
        "updated_ts": item.get("updated_ts"),
        "governance": {
            "gate": "reactor_external_escalation_delivery_processor_readiness",
            "execution_authority": False,
            "dispatch_authority": False,
            "retry_authority": False,
            "retry_execution_authority": False,
            "external_delivery_queue_authority": False,
            "external_delivery_authority": False,
            "external_escalation_authority": False,
            "escalation_authority": False,
            "approval_authority": False,
            "promotion_authority": False,
            "delivery_processor_claim_authority": False,
            "memory_write": False,
        },
    }
    redacted = redact_governed_value(readiness)
    return _display(redacted if isinstance(redacted, dict) else {})


def _history_entry(
    *,
    item: dict[str, Any],
    source: str,
    receipt: dict[str, Any],
    sequence: int,
    fallback_ts: int,
) -> dict[str, Any]:
    receipt_kind = _safe_str(receipt.get("kind")).strip()
    receipt_id = (
        _safe_str(receipt.get("receipt_id")).strip()
        or _safe_str(receipt.get("candidate_id")).strip()
        or _safe_str(receipt.get("exhaustion_id")).strip()
        or _safe_str(receipt.get("blocker_id")).strip()
        or _safe_str(receipt.get("delivery_id")).strip()
        or _safe_str(receipt.get("deadletter_id")).strip()
    )
    ts = _safe_int(
        receipt.get("ts") or receipt.get("created_ts") or receipt.get("updated_ts"),
        default=fallback_ts,
        minimum=0,
        maximum=2_147_483_647,
    )
    entry = {
        "kind": "reactor.deadletter.history.entry",
        "entry_id": f"{item.get('deadletter_id')}:{source}:{sequence}:{receipt_id or 'receipt'}",
        "deadletter_id": item.get("deadletter_id"),
        "event_id": item.get("event_id"),
        "sequence": sequence,
        "source": source,
        "receipt_kind": receipt_kind,
        "receipt_id": receipt_id,
        "status": receipt.get("status"),
        "route": receipt.get("route"),
        "gate": receipt.get("gate"),
        "stable_state": receipt.get("stable_state"),
        "next_step": receipt.get("next_step"),
        "ts": ts,
        "actor": receipt.get("actor"),
        "reason": receipt.get("reason"),
        "applied": bool(receipt.get("applied")),
        "execution_started": bool(receipt.get("execution_started")),
        "dispatch_applied": bool(receipt.get("dispatch_applied")),
        "retry_started": bool(receipt.get("retry_started")),
        "escalation_started": bool(receipt.get("escalation_started")),
        "external_delivery_started": bool(receipt.get("external_delivery_started")),
        "external_message_sent": bool(receipt.get("external_message_sent")),
        "external_network_send": bool(receipt.get("external_network_send")),
        "memory_write": bool(receipt.get("memory_write")),
        "completion_claim_allowed": bool(receipt.get("completion_claim_allowed")),
        "governance": _as_dict(receipt.get("governance")),
    }
    redacted = redact_governed_value(entry)
    return _display(redacted if isinstance(redacted, dict) else {})


_DEADLETTER_HISTORY_RECEIPT_FIELDS: tuple[tuple[str, str], ...] = (
    ("source_receipt", "source_receipt"),
    ("review_receipts", "review"),
    ("resolution_receipts", "resolution"),
    ("escalation_handoff_receipts", "escalation_handoff"),
    ("escalation_acknowledgement_receipts", "escalation_acknowledgement"),
    ("external_escalation_attempt_receipts", "external_escalation_attempt"),
    ("external_escalation_delivery_receipts", "external_escalation_delivery"),
    ("recovery_request_receipts", "recovery_request"),
    ("recovery_dispatch_receipts", "recovery_dispatch"),
)


def _deadletter_history(
    item: dict[str, Any],
    *,
    limit: int = 200,
    receipt_kind: str | None = None,
    route: str | None = None,
) -> list[dict[str, Any]]:
    created_ts = _safe_int(item.get("created_ts"), default=0, minimum=0, maximum=2_147_483_647)
    base_receipt = {
        "kind": item.get("kind"),
        "receipt_id": item.get("deadletter_id"),
        "deadletter_id": item.get("deadletter_id"),
        "event_id": item.get("event_id"),
        "status": "queued",
        "route": "deadletter",
        "gate": item.get("gate"),
        "stable_state": item.get("stable_state"),
        "next_step": "review_deadletter_item_before_escalation_or_recovery",
        "created_ts": created_ts,
        "actor": item.get("actor"),
        "reason": item.get("reason"),
        "applied": item.get("applied"),
        "execution_started": item.get("execution_started"),
        "dispatch_applied": item.get("dispatch_applied"),
        "retry_started": item.get("retry_started"),
        "escalation_started": item.get("escalation_started"),
        "memory_write": item.get("memory_write"),
        "governance": item.get("governance"),
    }
    entries = [
        _history_entry(item=item, source="deadletter_item", receipt=base_receipt, sequence=0, fallback_ts=created_ts)
    ]
    sequence = 1
    for field, source in _DEADLETTER_HISTORY_RECEIPT_FIELDS:
        raw_value = item.get(field)
        raw_receipts = raw_value if isinstance(raw_value, list) else [raw_value]
        for receipt_value in raw_receipts:
            receipt = _as_dict(receipt_value)
            if not receipt:
                continue
            entries.append(
                _history_entry(
                    item=item,
                    source=source,
                    receipt=receipt,
                    sequence=sequence,
                    fallback_ts=created_ts,
                )
            )
            sequence += 1

    receipt_kind_filter = _safe_str(receipt_kind).strip()
    route_filter = _safe_str(route).strip()
    if receipt_kind_filter:
        entries = [entry for entry in entries if _safe_str(entry.get("receipt_kind")).strip() == receipt_kind_filter]
    if route_filter:
        entries = [entry for entry in entries if _safe_str(entry.get("route")).strip() == route_filter]
    entries.sort(
        key=lambda entry: (
            _safe_int(entry.get("ts"), default=0, minimum=0, maximum=2_147_483_647),
            _safe_int(entry.get("sequence"), default=0, minimum=0, maximum=2_147_483_647),
        )
    )
    safe_limit = _safe_int(limit, default=200, minimum=1, maximum=5000)
    return entries[:safe_limit]


def _recovery_dispatch_receipt(
    *,
    item: dict[str, Any],
    recovery_event: dict[str, Any],
    dispatch_execution: dict[str, Any],
    stable_return: dict[str, Any],
    actor: str,
    reason: str,
    ts: int,
    status: str,
    applied: bool,
) -> dict[str, Any]:
    latest_request = _as_dict(item.get("latest_recovery_request_receipt"))
    recovery_event_id = _safe_str(recovery_event.get("event_id") or recovery_event.get("id")).strip()
    source_ref = (
        _safe_str(dispatch_execution.get("receipt_id")).strip()
        or _safe_str(stable_return.get("receipt_id")).strip()
        or recovery_event_id
    )
    receipt = {
        "kind": "reactor.deadletter.recovery_dispatch.receipt",
        "receipt_id": f"{item.get('deadletter_id')}_recovery_dispatch",
        "deadletter_id": item.get("deadletter_id"),
        "event_id": item.get("event_id"),
        "recovery_event_id": recovery_event_id,
        "status": status,
        "route": "deadletter_recovery_dispatch",
        "gate": "reactor_deadletter_recovery_dispatch",
        "stable_state": "deadletter_recovery_dispatched",
        "next_step": _recovery_dispatch_next_step(),
        "source_receipt_kind": _safe_str(dispatch_execution.get("kind")).strip(),
        "source_receipt_ref": source_ref,
        "source_gate": _safe_str(dispatch_execution.get("gate") or stable_return.get("gate")).strip(),
        "recovery_request_receipt_id": latest_request.get("receipt_id"),
        "operation_id": dispatch_execution.get("operation_id") or item.get("recovery_operation_id"),
        "operation_status": dispatch_execution.get("operation_status"),
        "trace_id": dispatch_execution.get("trace_id"),
        "run_id": dispatch_execution.get("run_id"),
        "actor": actor,
        "reason": reason,
        "ts": ts,
        "recovery_dispatched": True,
        "recovery_event_dispatched": True,
        "deadletter_settled": applied,
        "external_escalation_started": False,
        "recovery_started": bool(dispatch_execution.get("execution_started")),
        "execution_started": bool(dispatch_execution.get("execution_started")),
        "dispatch_applied": bool(dispatch_execution.get("dispatch_applied")),
        "retry_started": False,
        "escalation_started": False,
        "memory_write": bool(dispatch_execution.get("memory_write")),
        "applied": applied,
        "governance": {
            "gate": "reactor_deadletter_recovery_dispatch",
            "execution_authority": bool(dispatch_execution.get("execution_started")),
            "dispatch_authority": bool(dispatch_execution.get("dispatch_applied")),
            "retry_authority": False,
            "retry_execution_authority": False,
            "deadletter_disposition_authority": False,
            "deadletter_resolution_authority": False,
            "deadletter_settlement_authority": applied,
            "recovery_execution_authority": bool(dispatch_execution.get("execution_started")),
            "approval_authority": False,
            "promotion_authority": False,
            "escalation_authority": False,
            "memory_write": bool(dispatch_execution.get("memory_write")),
            "authority_source": dispatch_execution.get("governance", {}).get("authority_source") or "operations.run",
        },
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


def review_deadletter(
    *,
    deadletter_id: str,
    actor: str = "",
    reason: str = "",
    decision: str = "",
    ts: int = 0,
) -> dict[str, Any]:
    path = _deadletter_path(deadletter_id)
    if path is None or not path.exists() or not path.is_file():
        return {"ok": False, "applied": False, "error": "not_found", "item": {}, "receipt": {}}

    item = _read_raw(path)
    if item is None:
        return {"ok": False, "applied": False, "error": "unreadable_deadletter", "item": {}, "receipt": {}}

    review_decision = _review_decision(decision)
    latest_review = _as_dict(item.get("latest_review_receipt"))
    if (
        _safe_str(item.get("status")).strip() == "reviewed"
        and _safe_str(latest_review.get("review_decision")).strip() == review_decision
    ):
        receipt = _review_receipt(
            item=item,
            actor=actor,
            reason=reason,
            decision=review_decision,
            ts=ts,
            status="already_reviewed",
            applied=False,
        )
        return {
            "ok": True,
            "applied": False,
            "status": "already_reviewed",
            "item": _display(item),
            "receipt": _display(receipt),
        }

    receipt = _review_receipt(
        item=item,
        actor=actor,
        reason=reason,
        decision=review_decision,
        ts=ts,
        status="reviewed",
        applied=True,
    )
    raw_review_receipts = item.get("review_receipts")
    review_receipts = raw_review_receipts if isinstance(raw_review_receipts, list) else []
    review_receipts.append(receipt)
    updated = {
        **item,
        "status": "reviewed",
        "route": "deadletter_review",
        "stable_state": "deadletter_reviewed",
        "next_step": _review_next_step(review_decision),
        "review_decision": review_decision,
        "reviewed_ts": ts,
        "updated_ts": ts,
        "review_receipts": review_receipts,
        "latest_review_receipt": receipt,
        "deadletter_resolved": False,
        "recovery_started": False,
        "execution_started": False,
        "retry_started": False,
        "escalation_started": False,
        "memory_write": False,
        "applied": False,
        "governance": {
            **_as_dict(item.get("governance")),
            "gate": "reactor_deadletter_review",
            "execution_authority": False,
            "dispatch_authority": False,
            "retry_authority": False,
            "deadletter_resolution_authority": False,
            "escalation_authority": False,
            "memory_write": False,
        },
    }
    _atomic_write_json(path, updated)
    return {
        "ok": True,
        "applied": True,
        "status": "reviewed",
        "item": _display(updated),
        "receipt": _display(receipt),
    }


def resolve_deadletter(
    *,
    deadletter_id: str,
    actor: str = "",
    reason: str = "",
    decision: str = "",
    ts: int = 0,
) -> dict[str, Any]:
    path = _deadletter_path(deadletter_id)
    if path is None or not path.exists() or not path.is_file():
        return {"ok": False, "applied": False, "error": "not_found", "item": {}, "receipt": {}}

    item = _read_raw(path)
    if item is None:
        return {"ok": False, "applied": False, "error": "unreadable_deadletter", "item": {}, "receipt": {}}

    current_status = _safe_str(item.get("status")).strip()
    if current_status not in {"reviewed", "resolved", "escalation_pending", "resolution_deferred"}:
        return {
            "ok": False,
            "applied": False,
            "error": "deadletter_review_required",
            "item": _display(item),
            "receipt": {},
        }

    resolution_decision = _resolution_decision(decision)
    persisted_status, route, stable_state = _resolution_state(resolution_decision)
    latest_resolution = _as_dict(item.get("latest_resolution_receipt"))
    if (
        _safe_str(item.get("status")).strip() == persisted_status
        and _safe_str(latest_resolution.get("resolution_decision")).strip() == resolution_decision
    ):
        return {
            "ok": True,
            "applied": False,
            "status": f"already_{persisted_status}",
            "item": _display(item),
            "receipt": _display(latest_resolution),
        }

    receipt = _resolution_receipt(
        item=item,
        actor=actor,
        reason=reason,
        decision=resolution_decision,
        ts=ts,
        status=persisted_status,
        applied=True,
    )
    raw_resolution_receipts = item.get("resolution_receipts")
    resolution_receipts = raw_resolution_receipts if isinstance(raw_resolution_receipts, list) else []
    resolution_receipts.append(receipt)
    resolved = persisted_status == "resolved"
    escalation_recorded = persisted_status == "escalation_pending"
    updated = {
        **item,
        "status": persisted_status,
        "route": route,
        "stable_state": stable_state,
        "next_step": _resolution_next_step(resolution_decision),
        "resolution_decision": resolution_decision,
        "resolved_ts": ts if resolved else item.get("resolved_ts"),
        "escalation_recorded_ts": ts if escalation_recorded else item.get("escalation_recorded_ts"),
        "updated_ts": ts,
        "resolution_receipts": resolution_receipts,
        "latest_resolution_receipt": receipt,
        "deadletter_resolved": resolved,
        "escalation_recorded": escalation_recorded,
        "recovery_started": False,
        "execution_started": False,
        "retry_started": False,
        "escalation_started": False,
        "memory_write": False,
        "applied": False,
        "governance": {
            **_as_dict(item.get("governance")),
            "gate": "reactor_deadletter_resolution",
            "execution_authority": False,
            "dispatch_authority": False,
            "retry_authority": False,
            "retry_execution_authority": False,
            "deadletter_disposition_authority": True,
            "deadletter_resolution_authority": resolved,
            "escalation_authority": False,
            "memory_write": False,
        },
    }
    _atomic_write_json(path, _filtered_record(updated))
    return {
        "ok": True,
        "applied": True,
        "status": persisted_status,
        "item": _display(updated),
        "receipt": _display(receipt),
    }


def record_escalation_handoff(
    *,
    deadletter_id: str,
    actor: str = "",
    reason: str = "",
    ts: int = 0,
) -> dict[str, Any]:
    path = _deadletter_path(deadletter_id)
    if path is None or not path.exists() or not path.is_file():
        return {"ok": False, "applied": False, "error": "not_found", "item": {}, "receipt": {}}

    item = _read_raw(path)
    if item is None:
        return {"ok": False, "applied": False, "error": "unreadable_deadletter", "item": {}, "receipt": {}}

    current_status = _safe_str(item.get("status")).strip()
    latest_handoff = _as_dict(item.get("latest_escalation_handoff_receipt"))
    if current_status == "escalation_handoff_recorded" and latest_handoff:
        return {
            "ok": True,
            "applied": False,
            "status": "already_escalation_handoff_recorded",
            "item": _display(item),
            "receipt": _display(latest_handoff),
        }
    if current_status != "escalation_pending":
        return {
            "ok": False,
            "applied": False,
            "error": "deadletter_escalation_required",
            "item": _display(item),
            "receipt": {},
        }

    receipt = _escalation_handoff_receipt(
        item=item,
        actor=actor,
        reason=reason,
        ts=ts,
        status="handoff_recorded",
        applied=True,
    )
    raw_handoff_receipts = item.get("escalation_handoff_receipts")
    handoff_receipts = raw_handoff_receipts if isinstance(raw_handoff_receipts, list) else []
    handoff_receipts.append(receipt)
    updated = {
        **item,
        "status": "escalation_handoff_recorded",
        "route": "deadletter_escalation_handoff",
        "stable_state": "deadletter_escalation_handoff_recorded",
        "next_step": _escalation_handoff_next_step(),
        "escalation_handoff_recorded": True,
        "escalation_handoff_recorded_ts": ts,
        "updated_ts": ts,
        "escalation_handoff_receipts": handoff_receipts,
        "latest_escalation_handoff_receipt": receipt,
        "recovery_started": False,
        "execution_started": False,
        "retry_started": False,
        "escalation_started": False,
        "memory_write": False,
        "applied": False,
        "governance": {
            **_as_dict(item.get("governance")),
            "gate": "reactor_deadletter_escalation_handoff",
            "execution_authority": False,
            "dispatch_authority": False,
            "retry_authority": False,
            "retry_execution_authority": False,
            "deadletter_disposition_authority": False,
            "deadletter_resolution_authority": False,
            "escalation_authority": False,
            "memory_write": False,
        },
    }
    _atomic_write_json(path, _filtered_record(updated))
    return {
        "ok": True,
        "applied": True,
        "status": "deadletter_escalation_handoff_recorded",
        "item": _display(updated),
        "receipt": _display(receipt),
    }


def record_escalation_acknowledgement(
    *,
    deadletter_id: str,
    actor: str = "",
    reason: str = "",
    ts: int = 0,
) -> dict[str, Any]:
    path = _deadletter_path(deadletter_id)
    if path is None or not path.exists() or not path.is_file():
        return {"ok": False, "applied": False, "error": "not_found", "item": {}, "receipt": {}}

    item = _read_raw(path)
    if item is None:
        return {"ok": False, "applied": False, "error": "unreadable_deadletter", "item": {}, "receipt": {}}

    current_status = _safe_str(item.get("status")).strip()
    latest_acknowledgement = _as_dict(item.get("latest_escalation_acknowledgement_receipt"))
    if current_status == "escalation_acknowledged" and latest_acknowledgement:
        return {
            "ok": True,
            "applied": False,
            "status": "already_escalation_acknowledged",
            "item": _display(item),
            "receipt": _display(latest_acknowledgement),
        }
    if current_status != "escalation_handoff_recorded":
        return {
            "ok": False,
            "applied": False,
            "error": "deadletter_escalation_handoff_required",
            "item": _display(item),
            "receipt": {},
        }

    receipt = _escalation_acknowledgement_receipt(
        item=item,
        actor=actor,
        reason=reason,
        ts=ts,
        status="acknowledged",
        applied=True,
    )
    raw_acknowledgement_receipts = item.get("escalation_acknowledgement_receipts")
    acknowledgement_receipts = raw_acknowledgement_receipts if isinstance(raw_acknowledgement_receipts, list) else []
    acknowledgement_receipts.append(receipt)
    updated = {
        **item,
        "status": "escalation_acknowledged",
        "route": "deadletter_escalation_acknowledgement",
        "stable_state": "deadletter_escalation_acknowledged",
        "next_step": _escalation_acknowledgement_next_step(),
        "escalation_acknowledged": True,
        "escalation_acknowledged_ts": ts,
        "updated_ts": ts,
        "escalation_acknowledgement_receipts": acknowledgement_receipts,
        "latest_escalation_acknowledgement_receipt": receipt,
        "external_escalation_started": False,
        "recovery_started": False,
        "execution_started": False,
        "retry_started": False,
        "escalation_started": False,
        "memory_write": False,
        "applied": False,
        "governance": {
            **_as_dict(item.get("governance")),
            "gate": "reactor_deadletter_escalation_acknowledgement",
            "execution_authority": False,
            "dispatch_authority": False,
            "retry_authority": False,
            "retry_execution_authority": False,
            "deadletter_disposition_authority": False,
            "deadletter_resolution_authority": False,
            "escalation_authority": False,
            "memory_write": False,
        },
    }
    _atomic_write_json(path, _filtered_record(updated))
    return {
        "ok": True,
        "applied": True,
        "status": "deadletter_escalation_acknowledged",
        "item": _display(updated),
        "receipt": _display(receipt),
    }


def record_external_escalation_attempt(
    *,
    deadletter_id: str,
    actor: str = "",
    reason: str = "",
    external_channel: str = "",
    external_target: str = "",
    adapter: str = "",
    ts: int = 0,
) -> dict[str, Any]:
    path = _deadletter_path(deadletter_id)
    if path is None or not path.exists() or not path.is_file():
        return {"ok": False, "applied": False, "error": "not_found", "item": {}, "receipt": {}}

    item = _read_raw(path)
    if item is None:
        return {"ok": False, "applied": False, "error": "unreadable_deadletter", "item": {}, "receipt": {}}

    current_status = _safe_str(item.get("status")).strip()
    latest_attempt = _as_dict(item.get("latest_external_escalation_attempt_receipt"))
    if current_status == "external_escalation_attempt_recorded" and latest_attempt:
        return {
            "ok": True,
            "applied": False,
            "status": "already_external_escalation_attempt_recorded",
            "item": _display(item),
            "receipt": _display(latest_attempt),
        }
    if current_status != "escalation_acknowledged":
        return {
            "ok": False,
            "applied": False,
            "error": "deadletter_escalation_acknowledgement_required",
            "item": _display(item),
            "receipt": {},
        }

    receipt = _external_escalation_attempt_receipt(
        item=item,
        actor=actor,
        reason=reason,
        external_channel=_safe_str(external_channel).strip(),
        external_target=_safe_str(external_target).strip(),
        adapter=_safe_str(adapter).strip(),
        ts=ts,
        status="attempt_recorded",
        applied=True,
    )
    raw_attempt_receipts = item.get("external_escalation_attempt_receipts")
    attempt_receipts = raw_attempt_receipts if isinstance(raw_attempt_receipts, list) else []
    attempt_receipts.append(receipt)
    updated = {
        **item,
        "status": "external_escalation_attempt_recorded",
        "route": "deadletter_external_escalation_attempt",
        "stable_state": "deadletter_external_escalation_attempt_recorded",
        "next_step": _external_escalation_attempt_next_step(),
        "external_escalation_attempt_recorded": True,
        "external_escalation_attempt_recorded_ts": ts,
        "external_channel": _safe_str(external_channel).strip(),
        "external_target": _safe_str(external_target).strip(),
        "external_adapter": receipt.get("external_adapter") or _safe_str(adapter).strip(),
        "external_adapter_declared": receipt.get("external_adapter_declared"),
        "external_adapter_known": receipt.get("external_adapter_known"),
        "external_adapter_configured": receipt.get("external_adapter_configured"),
        "external_adapter_status": receipt.get("external_adapter_status"),
        "external_delivery_mode": receipt.get("external_delivery_mode"),
        "external_delivery_ready": receipt.get("external_delivery_ready"),
        "external_delivery_queued": receipt.get("external_delivery_queued"),
        "external_delivery_blocker": receipt.get("external_delivery_blocker"),
        "missing_requirements": receipt.get("missing_requirements"),
        "updated_ts": ts,
        "external_escalation_attempt_receipts": attempt_receipts,
        "latest_external_escalation_attempt_receipt": receipt,
        "external_escalation_started": False,
        "external_delivery_started": False,
        "recovery_started": False,
        "execution_started": False,
        "dispatch_applied": False,
        "retry_started": False,
        "escalation_started": False,
        "memory_write": False,
        "applied": False,
        "governance": {
            **_as_dict(item.get("governance")),
            "gate": "reactor_deadletter_external_escalation_attempt",
            "execution_authority": False,
            "dispatch_authority": False,
            "retry_authority": False,
            "retry_execution_authority": False,
            "deadletter_disposition_authority": False,
            "deadletter_resolution_authority": False,
            "external_escalation_authority": False,
            "escalation_authority": False,
            "memory_write": False,
        },
    }
    _atomic_write_json(path, _filtered_record(updated))
    return {
        "ok": True,
        "applied": True,
        "status": "deadletter_external_escalation_attempt_recorded",
        "item": _display(updated),
        "receipt": _display(receipt),
    }


def record_external_escalation_delivery(
    *,
    deadletter_id: str,
    actor: str = "",
    reason: str = "",
    ts: int = 0,
) -> dict[str, Any]:
    path = _deadletter_path(deadletter_id)
    if path is None or not path.exists() or not path.is_file():
        return {
            "ok": False,
            "applied": False,
            "error": "not_found",
            "item": {},
            "receipt": {},
            "delivery_item": {},
        }

    item = _read_raw(path)
    if item is None:
        return {
            "ok": False,
            "applied": False,
            "error": "unreadable_deadletter",
            "item": {},
            "receipt": {},
            "delivery_item": {},
        }

    current_status = _safe_str(item.get("status")).strip()
    latest_delivery = _as_dict(item.get("latest_external_escalation_delivery_receipt"))
    existing_delivery_item = _as_dict(item.get("external_escalation_delivery_item"))
    if current_status == "external_escalation_delivery_queued" and latest_delivery:
        return {
            "ok": True,
            "applied": False,
            "status": "already_external_escalation_delivery_queued",
            "item": _display(item),
            "receipt": _display(latest_delivery),
            "delivery_item": _display(existing_delivery_item),
        }
    if current_status != "external_escalation_attempt_recorded":
        return {
            "ok": False,
            "applied": False,
            "error": "deadletter_external_escalation_attempt_required",
            "item": _display(item),
            "receipt": {},
            "delivery_item": {},
        }

    latest_attempt = _as_dict(item.get("latest_external_escalation_attempt_receipt"))
    if not latest_attempt:
        return {
            "ok": False,
            "applied": False,
            "error": "deadletter_external_escalation_attempt_required",
            "item": _display(item),
            "receipt": {},
            "delivery_item": {},
        }
    if _safe_str(latest_attempt.get("external_delivery_mode")).strip() != "local_outbox":
        return {
            "ok": False,
            "applied": False,
            "error": "local_outbox_external_escalation_adapter_required",
            "item": _display(item),
            "receipt": _display(latest_attempt),
            "delivery_item": {},
        }
    if not bool(latest_attempt.get("external_delivery_ready")):
        return {
            "ok": False,
            "applied": False,
            "error": "external_escalation_delivery_not_ready",
            "item": _display(item),
            "receipt": _display(latest_attempt),
            "delivery_item": {},
        }

    delivery_item = _local_outbox_delivery_item(
        item=item,
        source_receipt=latest_attempt,
        actor=actor,
        reason=reason,
        ts=ts,
    )
    delivery_id = _safe_str(delivery_item.get("delivery_id")).strip()
    delivery_path = _external_delivery_path(delivery_id)
    if delivery_path is None:
        return {
            "ok": False,
            "applied": False,
            "error": "invalid_external_escalation_delivery_id",
            "item": _display(item),
            "receipt": {},
            "delivery_item": {},
        }

    existing_delivery = _read_raw(delivery_path) if delivery_path.exists() and delivery_path.is_file() else None
    persisted_delivery = existing_delivery if existing_delivery is not None else delivery_item
    if existing_delivery is None:
        _atomic_write_json(delivery_path, _filtered_record(delivery_item))

    receipt = _external_escalation_delivery_receipt(
        item=item,
        source_receipt=latest_attempt,
        delivery_item=persisted_delivery,
        actor=actor,
        reason=reason,
        ts=ts,
        status="delivery_queued",
        applied=True,
    )
    raw_delivery_receipts = item.get("external_escalation_delivery_receipts")
    delivery_receipts = raw_delivery_receipts if isinstance(raw_delivery_receipts, list) else []
    delivery_receipts.append(receipt)
    updated = {
        **item,
        "status": "external_escalation_delivery_queued",
        "route": "deadletter_external_escalation_delivery",
        "stable_state": "deadletter_external_escalation_delivery_queued",
        "next_step": _external_escalation_delivery_next_step(),
        "external_escalation_delivery_queued": True,
        "external_escalation_delivery_queued_ts": ts,
        "external_escalation_delivery_id": delivery_id,
        "external_delivery_id": delivery_id,
        "external_escalation_delivery_item": persisted_delivery,
        "external_delivery_queued": True,
        "external_delivery_started": False,
        "external_message_sent": False,
        "external_network_send": False,
        "updated_ts": ts,
        "external_escalation_delivery_receipts": delivery_receipts,
        "latest_external_escalation_delivery_receipt": receipt,
        "external_escalation_started": False,
        "recovery_started": False,
        "execution_started": False,
        "dispatch_applied": False,
        "retry_started": False,
        "escalation_started": False,
        "memory_write": False,
        "applied": False,
        "governance": {
            **_as_dict(item.get("governance")),
            "gate": "reactor_deadletter_external_escalation_delivery",
            "execution_authority": False,
            "dispatch_authority": False,
            "retry_authority": False,
            "retry_execution_authority": False,
            "deadletter_disposition_authority": False,
            "deadletter_resolution_authority": False,
            "external_delivery_queue_authority": True,
            "external_delivery_authority": False,
            "external_escalation_authority": False,
            "escalation_authority": False,
            "approval_authority": False,
            "promotion_authority": False,
            "memory_write": False,
        },
    }
    _atomic_write_json(path, _filtered_record(updated))
    return {
        "ok": True,
        "applied": True,
        "status": "deadletter_external_escalation_delivery_queued",
        "item": _display(updated),
        "receipt": _display(receipt),
        "delivery_item": _display(persisted_delivery),
    }


def record_recovery_request(
    *,
    deadletter_id: str,
    operation_id: str,
    recovery_event_id: str,
    actor: str = "",
    reason: str = "",
    ts: int = 0,
) -> dict[str, Any]:
    path = _deadletter_path(deadletter_id)
    if path is None or not path.exists() or not path.is_file():
        return {"ok": False, "applied": False, "error": "not_found", "item": {}, "receipt": {}}

    item = _read_raw(path)
    if item is None:
        return {"ok": False, "applied": False, "error": "unreadable_deadletter", "item": {}, "receipt": {}}

    current_status = _safe_str(item.get("status")).strip()
    latest_request = _as_dict(item.get("latest_recovery_request_receipt"))
    if current_status == "recovery_requested" and latest_request:
        return {
            "ok": True,
            "applied": False,
            "status": "already_recovery_requested",
            "item": _display(item),
            "receipt": _display(latest_request),
        }
    if current_status not in {"escalation_acknowledged", "external_escalation_attempt_recorded"}:
        return {
            "ok": False,
            "applied": False,
            "error": "deadletter_escalation_acknowledgement_required",
            "item": _display(item),
            "receipt": {},
        }

    operation_key = _safe_str(operation_id).strip()
    recovery_event_key = _safe_str(recovery_event_id).strip()
    if not operation_key:
        return {
            "ok": False,
            "applied": False,
            "error": "deadletter_recovery_operation_required",
            "item": _display(item),
            "receipt": {},
        }
    if not recovery_event_key:
        return {
            "ok": False,
            "applied": False,
            "error": "deadletter_recovery_event_required",
            "item": _display(item),
            "receipt": {},
        }

    receipt = _recovery_request_receipt(
        item=item,
        actor=actor,
        reason=reason,
        ts=ts,
        status="recovery_requested",
        applied=True,
        operation_id=operation_key,
        recovery_event_id=recovery_event_key,
    )
    raw_request_receipts = item.get("recovery_request_receipts")
    request_receipts = raw_request_receipts if isinstance(raw_request_receipts, list) else []
    request_receipts.append(receipt)
    updated = {
        **item,
        "status": "recovery_requested",
        "route": "deadletter_recovery_request",
        "stable_state": "deadletter_recovery_requested",
        "next_step": _recovery_request_next_step(),
        "recovery_requested": True,
        "recovery_requested_ts": ts,
        "recovery_operation_id": operation_key,
        "recovery_event_id": recovery_event_key,
        "updated_ts": ts,
        "recovery_request_receipts": request_receipts,
        "latest_recovery_request_receipt": receipt,
        "external_escalation_started": False,
        "recovery_started": False,
        "execution_started": False,
        "retry_started": False,
        "escalation_started": False,
        "memory_write": False,
        "applied": False,
        "governance": {
            **_as_dict(item.get("governance")),
            "gate": "reactor_deadletter_recovery_request",
            "execution_authority": False,
            "dispatch_authority": False,
            "retry_authority": False,
            "retry_execution_authority": False,
            "deadletter_disposition_authority": False,
            "deadletter_resolution_authority": False,
            "recovery_request_authority": True,
            "escalation_authority": False,
            "memory_write": False,
        },
    }
    _atomic_write_json(path, _filtered_record(updated))
    return {
        "ok": True,
        "applied": True,
        "status": "deadletter_recovery_requested",
        "item": _display(updated),
        "receipt": _display(receipt),
    }


def record_recovery_dispatch(
    *,
    deadletter_id: str,
    recovery_event: dict[str, Any],
    dispatch_execution: dict[str, Any],
    stable_return: dict[str, Any],
    actor: str = "",
    reason: str = "",
    ts: int = 0,
) -> dict[str, Any]:
    path = _deadletter_path(deadletter_id)
    if path is None or not path.exists() or not path.is_file():
        return {"ok": False, "applied": False, "error": "not_found", "item": {}, "receipt": {}}

    item = _read_raw(path)
    if item is None:
        return {"ok": False, "applied": False, "error": "unreadable_deadletter", "item": {}, "receipt": {}}

    latest_dispatch = _as_dict(item.get("latest_recovery_dispatch_receipt"))
    if _safe_str(item.get("status")).strip() == "recovery_dispatched" and latest_dispatch:
        return {
            "ok": True,
            "applied": False,
            "status": "already_recovery_dispatched",
            "item": _display(item),
            "receipt": _display(latest_dispatch),
        }

    if _safe_str(item.get("status")).strip() != "recovery_requested":
        return {
            "ok": False,
            "applied": False,
            "error": "deadletter_recovery_request_required",
            "item": _display(item),
            "receipt": {},
        }

    latest_request = _as_dict(item.get("latest_recovery_request_receipt"))
    recovery_event_key = _safe_str(recovery_event.get("event_id") or recovery_event.get("id")).strip()
    if (
        _safe_str(latest_request.get("recovery_event_id") or item.get("recovery_event_id")).strip()
        != recovery_event_key
    ):
        return {
            "ok": False,
            "applied": False,
            "error": "deadletter_recovery_event_mismatch",
            "item": _display(item),
            "receipt": {},
        }
    if not bool(dispatch_execution.get("verified")):
        return {
            "ok": False,
            "applied": False,
            "error": "deadletter_recovery_dispatch_success_required",
            "item": _display(item),
            "receipt": {},
        }

    receipt = _recovery_dispatch_receipt(
        item=item,
        recovery_event=recovery_event,
        dispatch_execution=dispatch_execution,
        stable_return=stable_return,
        actor=actor,
        reason=reason,
        ts=ts,
        status="recovery_dispatched",
        applied=True,
    )
    raw_dispatch_receipts = item.get("recovery_dispatch_receipts")
    dispatch_receipts = raw_dispatch_receipts if isinstance(raw_dispatch_receipts, list) else []
    dispatch_receipts.append(receipt)
    updated = {
        **item,
        "status": "recovery_dispatched",
        "route": "deadletter_recovery_dispatch",
        "stable_state": "deadletter_recovery_dispatched",
        "next_step": _recovery_dispatch_next_step(),
        "recovery_dispatched": True,
        "recovery_dispatched_ts": ts,
        "recovery_started": bool(dispatch_execution.get("execution_started")),
        "execution_started": bool(dispatch_execution.get("execution_started")),
        "dispatch_applied": bool(dispatch_execution.get("dispatch_applied")),
        "operation_status": dispatch_execution.get("operation_status"),
        "trace_id": dispatch_execution.get("trace_id"),
        "run_id": dispatch_execution.get("run_id"),
        "updated_ts": ts,
        "recovery_dispatch_receipts": dispatch_receipts,
        "latest_recovery_dispatch_receipt": receipt,
        "external_escalation_started": False,
        "retry_started": False,
        "escalation_started": False,
        "memory_write": bool(dispatch_execution.get("memory_write")),
        "applied": False,
        "governance": {
            **_as_dict(item.get("governance")),
            "gate": "reactor_deadletter_recovery_dispatch",
            "execution_authority": bool(dispatch_execution.get("execution_started")),
            "dispatch_authority": bool(dispatch_execution.get("dispatch_applied")),
            "retry_authority": False,
            "retry_execution_authority": False,
            "deadletter_disposition_authority": False,
            "deadletter_resolution_authority": False,
            "deadletter_settlement_authority": True,
            "recovery_execution_authority": bool(dispatch_execution.get("execution_started")),
            "approval_authority": False,
            "promotion_authority": False,
            "escalation_authority": False,
            "memory_write": bool(dispatch_execution.get("memory_write")),
        },
    }
    _atomic_write_json(path, _filtered_record(updated))
    return {
        "ok": True,
        "applied": True,
        "status": "deadletter_recovery_dispatched",
        "item": _display(updated),
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


def get_deadletter_history(
    deadletter_id: str,
    *,
    limit: int = 200,
    receipt_kind: str | None = None,
    route: str | None = None,
) -> dict[str, Any] | None:
    path = _deadletter_path(deadletter_id)
    if path is None or not path.exists() or not path.is_file():
        return None
    item = _read_raw(path)
    if item is None:
        return None
    history = _deadletter_history(item, limit=limit, receipt_kind=receipt_kind, route=route)
    latest = history[-1] if history else {}
    result = {
        "kind": "reactor.deadletter.history",
        "deadletter_id": item.get("deadletter_id"),
        "event_id": item.get("event_id"),
        "status": item.get("status"),
        "route": "deadletter_history",
        "gate": "reactor_deadletter_history_readback",
        "stable_state": item.get("stable_state"),
        "history": history,
        "total": len(history),
        "limit": _safe_int(limit, default=200, minimum=1, maximum=5000),
        "latest_receipt_kind": latest.get("receipt_kind"),
        "latest_route": latest.get("route"),
        "latest_ts": latest.get("ts"),
        "governance": {
            "gate": "reactor_deadletter_history_readback",
            "execution_authority": False,
            "dispatch_authority": False,
            "retry_authority": False,
            "retry_execution_authority": False,
            "deadletter_disposition_authority": False,
            "deadletter_resolution_authority": False,
            "external_delivery_authority": False,
            "external_escalation_authority": False,
            "escalation_authority": False,
            "approval_authority": False,
            "promotion_authority": False,
            "memory_write": False,
        },
    }
    redacted = redact_governed_value(result)
    return _display(redacted if isinstance(redacted, dict) else {})


def list_external_escalation_deliveries(
    *,
    limit: int = 200,
    status: str | None = None,
    deadletter_id: str | None = None,
    event_id: str | None = None,
) -> list[dict[str, Any]]:
    root = _external_delivery_root()
    if not root.exists():
        return []
    status_filter = _safe_str(status).strip().lower()
    deadletter_filter = _safe_str(deadletter_id).strip()
    event_filter = _safe_str(event_id).strip()
    items: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.json")):
        if not path.is_file():
            continue
        item = _read(path)
        if not item:
            continue
        if status_filter and _safe_str(item.get("status")).strip().lower() != status_filter:
            continue
        if deadletter_filter and _safe_str(item.get("deadletter_id")).strip() != deadletter_filter:
            continue
        if event_filter and _safe_str(item.get("event_id")).strip() != event_filter:
            continue
        items.append(item)
    items.sort(
        key=lambda item: (
            _safe_int(item.get("created_ts"), default=0, minimum=0, maximum=2_147_483_647),
            _safe_str(item.get("delivery_id")),
        ),
        reverse=True,
    )
    return items[: max(1, min(int(limit), 5000))]


def get_external_escalation_delivery(delivery_id: str) -> dict[str, Any] | None:
    path = _external_delivery_path(delivery_id)
    if path is None or not path.exists() or not path.is_file():
        return None
    return _read(path)


def list_external_escalation_delivery_processor_readiness(
    *,
    limit: int = 200,
    status: str | None = None,
    deadletter_id: str | None = None,
    event_id: str | None = None,
    processor_status: str | None = None,
) -> list[dict[str, Any]]:
    processor_filter = _safe_str(processor_status).strip().lower()
    items = [
        _external_delivery_processor_readiness(item)
        for item in list_external_escalation_deliveries(
            limit=limit,
            status=status,
            deadletter_id=deadletter_id,
            event_id=event_id,
        )
    ]
    if processor_filter:
        items = [
            item
            for item in items
            if _safe_str(item.get("delivery_processor_status") or item.get("status")).strip().lower()
            == processor_filter
        ]
    return items


def get_external_escalation_delivery_processor_readiness(delivery_id: str) -> dict[str, Any] | None:
    item = get_external_escalation_delivery(delivery_id)
    if item is None:
        return None
    return _external_delivery_processor_readiness(item)
