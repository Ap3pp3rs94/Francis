from __future__ import annotations

from typing import Any

from francis.reactor.deadletters import (
    list_deadletter_recovery_receipts,
    list_deadletters,
    list_external_escalation_deliveries,
    list_external_escalation_delivery_processor_readiness,
    list_external_escalation_delivery_sender_readiness,
)
from francis.reactor.events import list_proposal_review_history, reactor_review_queue, reactor_status
from francis.reactor.retries import list_retry_schedules


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""


def _safe_int(value: Any, *, default: int = 0, minimum: int = 0, maximum: int = 5000) -> int:
    if isinstance(value, bool):
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, parsed))


def _count_by(items: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        value = _safe_str(item.get(key)).strip() or "unknown"
        counts[value] = counts.get(value, 0) + 1
    return counts


def _readback_governance() -> dict[str, Any]:
    return {
        "gate": "reactor_operator_visibility_readback",
        "execution_authority": False,
        "dispatch_authority": False,
        "approval_authority": False,
        "deadletter_authority": False,
        "deadletter_resolution_authority": False,
        "retry_authority": False,
        "external_delivery_authority": False,
        "external_escalation_authority": False,
        "proposal_decision_authority": False,
        "promotion_authority": False,
        "memory_write": False,
    }


def reactor_operator_visibility_summary(*, limit: int = 10) -> dict[str, Any]:
    safe_limit = _safe_int(limit, default=10, minimum=1, maximum=100)
    status = reactor_status()
    review_queue = reactor_review_queue(limit=safe_limit)
    deadletters = list_deadletters(limit=5000)
    retry_schedules = list_retry_schedules(limit=5000)
    recovery_receipts = list_deadletter_recovery_receipts(limit=5000)
    proposal_reviews = list_proposal_review_history(limit=5000)
    external_deliveries = list_external_escalation_deliveries(limit=5000)
    delivery_processor_readiness = list_external_escalation_delivery_processor_readiness(limit=5000)
    delivery_sender_readiness = list_external_escalation_delivery_sender_readiness(limit=5000)

    ready_delivery_processors = [
        item for item in delivery_processor_readiness if bool(item.get("delivery_processor_ready"))
    ]
    ready_delivery_senders = [
        item for item in delivery_sender_readiness if bool(item.get("external_delivery_sender_ready"))
    ]
    blocked_delivery_senders = [
        item for item in delivery_sender_readiness if not bool(item.get("external_delivery_sender_ready"))
    ]
    due_retries = [item for item in retry_schedules if _safe_str(item.get("status")).strip().lower() == "due"]
    ready_proposal_reviews = [item for item in proposal_reviews if bool(item.get("quality_ready"))]
    review_queue_total = _safe_int(review_queue.get("available_total"))

    if review_queue_total:
        next_step = "review_active_reactor_queue"
    elif ready_delivery_processors:
        next_step = "inspect_ready_external_delivery_processor_items"
    elif ready_delivery_senders:
        next_step = "inspect_ready_external_delivery_sender_items"
    elif blocked_delivery_senders:
        next_step = "inspect_blocked_external_delivery_sender_items"
    elif due_retries:
        next_step = "dispatch_due_reactor_retries"
    elif proposal_reviews:
        next_step = "inspect_recent_reactor_proposal_review_history"
    else:
        next_step = "wait_for_reactor_trigger"

    return {
        "ok": True,
        "kind": "reactor.operator_visibility.summary",
        "status": "ready",
        "limit": safe_limit,
        "next_step": next_step,
        "event_total": _safe_int(status.get("total")),
        "review_queue_total": review_queue_total,
        "deadletter_total": len(deadletters),
        "retry_schedule_total": len(retry_schedules),
        "external_delivery_total": len(external_deliveries),
        "external_delivery_sender_readiness_total": len(delivery_sender_readiness),
        "recovery_receipt_total": len(recovery_receipts),
        "proposal_review_history_total": len(proposal_reviews),
        "attention": {
            "review_queue_total": review_queue_total,
            "ready_external_delivery_processor_total": len(ready_delivery_processors),
            "blocked_external_delivery_processor_total": len(delivery_processor_readiness)
            - len(ready_delivery_processors),
            "ready_external_delivery_sender_total": len(ready_delivery_senders),
            "blocked_external_delivery_sender_total": len(blocked_delivery_senders),
            "due_retry_total": len(due_retries),
            "proposal_review_ready_total": len(ready_proposal_reviews),
            "proposal_review_blocked_total": len(proposal_reviews) - len(ready_proposal_reviews),
        },
        "counts": {
            "event_status": status.get("status_counts", {}),
            "stable_state": status.get("stable_state_counts", {}),
            "trigger_source": status.get("trigger_source_counts", {}),
            "review_route": review_queue.get("route_counts", {}),
            "deadletter_status": _count_by(deadletters, "status"),
            "retry_status": _count_by(retry_schedules, "status"),
            "external_delivery_status": _count_by(external_deliveries, "status"),
            "delivery_processor_status": _count_by(
                delivery_processor_readiness,
                "delivery_processor_status",
            ),
            "delivery_sender_status": _count_by(
                delivery_sender_readiness,
                "external_delivery_sender_status",
            ),
            "proposal_review_outcome": _count_by(proposal_reviews, "outcome"),
        },
        "readback_surfaces": {
            "status": "/reactor/status",
            "events": "/reactor/events/list",
            "review_queue": "/reactor/review_queue",
            "deadletters": "/reactor/deadletters/list",
            "deadletter_history": "/reactor/deadletters/history/get",
            "recovery_receipts": "/reactor/deadletters/recovery_receipts/list",
            "proposal_review_history": "/reactor/proposal_reviews/history/list",
            "external_deliveries": "/reactor/deadletters/external_escalation_deliveries/list",
            "external_delivery_processor_readiness": (
                "/reactor/deadletters/external_escalation_deliveries/processor_readiness/list"
            ),
            "external_delivery_sender_readiness": (
                "/reactor/deadletters/external_escalation_deliveries/sender_readiness/list"
            ),
            "retry_schedules": "/reactor/retries/list",
        },
        "latest_review_items": review_queue.get("items", [])[:safe_limit],
        "latest_proposal_reviews": proposal_reviews[:safe_limit],
        "ready_external_delivery_processor_items": ready_delivery_processors[:safe_limit],
        "ready_external_delivery_sender_items": ready_delivery_senders[:safe_limit],
        "blocked_external_delivery_sender_items": blocked_delivery_senders[:safe_limit],
        "governance": _readback_governance(),
    }
