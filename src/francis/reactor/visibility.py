from __future__ import annotations

from typing import Any

from francis.reactor.deadletters import (
    list_deadletter_recovery_receipts,
    list_deadletters,
    list_external_escalation_deliveries,
    list_external_escalation_delivery_processor_readiness,
    list_external_escalation_delivery_sender_readiness,
)
from francis.reactor.events import list_events, list_proposal_review_history, reactor_review_queue, reactor_status
from francis.reactor.external_escalation import external_delivery_sender_contract
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


def _safe_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for item in value:
        text = _safe_str(item).strip()
        if text and text not in items:
            items.append(text)
    return items


def _list_presence_counts(items: list[str]) -> dict[str, int]:
    return {item: 1 for item in items}


def _safe_count_map(value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    counts: dict[str, int] = {}
    for raw_key, raw_count in value.items():
        key = _safe_str(raw_key).strip()
        if not key:
            continue
        count = _safe_int(raw_count)
        if count > 0:
            counts[key] = count
    return counts


def _safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _bounded_plan_trace_item(item: dict[str, Any]) -> dict[str, Any] | None:
    bounded_plan = _safe_dict(item.get("latest_bounded_plan_receipt")) or _safe_dict(item.get("bounded_plan"))
    if not bounded_plan:
        return None

    dispatch = _safe_dict(item.get("dispatch"))
    dispatch_attempt = _safe_dict(item.get("latest_dispatch_attempt_receipt")) or _safe_dict(
        dispatch.get("last_receipt")
    )
    trigger = _safe_dict(item.get("trigger"))
    classification = _safe_dict(item.get("classification"))
    plan_receipt_id = _safe_str(bounded_plan.get("receipt_id")).strip()
    dispatch_plan_receipt_id = _safe_str(dispatch_attempt.get("bounded_plan_receipt_id")).strip()
    dispatch_attempt_recorded = bool(dispatch_attempt)
    dispatch_attempt_linked = bool(plan_receipt_id and dispatch_plan_receipt_id == plan_receipt_id)
    if dispatch_attempt_linked:
        trace_status = "dispatch_linked"
    elif dispatch_attempt_recorded:
        trace_status = "dispatch_unlinked"
    else:
        trace_status = "dispatch_pending"

    return {
        "kind": "reactor.bounded_plan_trace.readback",
        "event_id": _safe_str(item.get("event_id") or item.get("id")).strip(),
        "status": _safe_str(item.get("status")).strip(),
        "stable_state": _safe_str(item.get("stable_state")).strip(),
        "trigger_source": _safe_str(trigger.get("source")).strip(),
        "trigger_type": _safe_str(trigger.get("type")).strip(),
        "action_class": _safe_str(classification.get("action_class")).strip(),
        "bounded_plan_receipt_id": plan_receipt_id,
        "bounded_plan_status": _safe_str(bounded_plan.get("status")).strip(),
        "bounded_plan_route": _safe_str(bounded_plan.get("route")).strip(),
        "bounded_plan_max_actions": _safe_int(bounded_plan.get("max_actions"), maximum=50),
        "bounded_plan_max_runtime_seconds": _safe_int(
            bounded_plan.get("max_runtime_seconds"),
            minimum=0,
            maximum=86_400,
        ),
        "dispatch_attempt_recorded": dispatch_attempt_recorded,
        "dispatch_attempt_status": _safe_str(dispatch_attempt.get("status")).strip(),
        "dispatch_attempt_outcome": _safe_str(dispatch_attempt.get("outcome")).strip(),
        "dispatch_attempt_bounded_plan_receipt_id": dispatch_plan_receipt_id,
        "dispatch_attempt_linked": dispatch_attempt_linked,
        "trace_status": trace_status,
        "execution_started": bool(dispatch_attempt.get("execution_started")),
        "dispatch_applied": bool(dispatch_attempt.get("applied")),
        "memory_write": False,
        "governance": _readback_governance(),
    }


def _readback_governance() -> dict[str, Any]:
    return {
        "gate": "reactor_operator_visibility_readback",
        "execution_authority": False,
        "dispatch_authority": False,
        "plugin_run_authority": False,
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
    reflection_counts = _safe_count_map(status.get("reflection_counts"))
    reflection_outcome_counts = _safe_count_map(status.get("reflection_outcome_counts"))
    bounded_plan_traces = [
        trace
        for event in list_events(limit=5000, receipt_kind="reactor.bounded_plan.receipt")
        if (trace := _bounded_plan_trace_item(event)) is not None
    ]
    delivery_sender_contract = external_delivery_sender_contract()
    delivery_sender_contract_status = _safe_str(delivery_sender_contract.get("status")).strip() or "unknown"
    delivery_sender_contract_ready = bool(delivery_sender_contract.get("external_sender_contract_ready"))
    dispatch_engine_supported_actions = _safe_str_list(status.get("dispatch_engine_supported_actions"))
    dispatch_engine_boundary_actions = _safe_str_list(status.get("dispatch_engine_boundary_actions"))
    supported_external_sender_adapters = _safe_str_list(
        delivery_sender_contract.get("supported_external_sender_adapters")
    )
    external_sender_required_fields = _safe_str_list(delivery_sender_contract.get("external_sender_required_fields"))

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
    linked_bounded_plan_traces = [item for item in bounded_plan_traces if bool(item.get("dispatch_attempt_linked"))]
    pending_bounded_plan_traces = [
        item for item in bounded_plan_traces if _safe_str(item.get("trace_status")).strip() == "dispatch_pending"
    ]
    unlinked_bounded_plan_traces = [
        item for item in bounded_plan_traces if _safe_str(item.get("trace_status")).strip() == "dispatch_unlinked"
    ]

    if review_queue_total:
        next_step = "review_active_reactor_queue"
    elif unlinked_bounded_plan_traces:
        next_step = "inspect_unlinked_bounded_plan_dispatch_traces"
    elif ready_delivery_processors:
        next_step = "inspect_ready_external_delivery_processor_items"
    elif ready_delivery_senders:
        next_step = "inspect_ready_external_delivery_sender_items"
    elif blocked_delivery_senders:
        next_step = "inspect_blocked_external_delivery_sender_items"
    elif not delivery_sender_contract_ready:
        next_step = "inspect_external_delivery_sender_contract"
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
        "dispatch_engine": _safe_str(status.get("dispatch_engine")).strip() or "unknown",
        "dispatch_engine_supported_actions": dispatch_engine_supported_actions,
        "dispatch_engine_supported_action_total": len(dispatch_engine_supported_actions),
        "dispatch_engine_boundary_actions": dispatch_engine_boundary_actions,
        "dispatch_engine_boundary_action_total": len(dispatch_engine_boundary_actions),
        "external_delivery_total": len(external_deliveries),
        "external_delivery_sender_readiness_total": len(delivery_sender_readiness),
        "external_delivery_sender_contract_status": delivery_sender_contract_status,
        "external_delivery_sender_contract_ready": delivery_sender_contract_ready,
        "external_delivery_sender_contract_blocker": _safe_str(
            delivery_sender_contract.get("external_sender_contract_blocker")
        ).strip(),
        "bounded_plan_trace_total": len(bounded_plan_traces),
        "bounded_plan_dispatch_linked_total": len(linked_bounded_plan_traces),
        "bounded_plan_dispatch_pending_total": len(pending_bounded_plan_traces),
        "bounded_plan_dispatch_unlinked_total": len(unlinked_bounded_plan_traces),
        "reflection_receipt_total": sum(reflection_counts.values()),
        "supported_external_sender_adapters": supported_external_sender_adapters,
        "supported_external_sender_adapter_total": len(supported_external_sender_adapters),
        "external_sender_required_fields": external_sender_required_fields,
        "recovery_receipt_total": len(recovery_receipts),
        "proposal_review_history_total": len(proposal_reviews),
        "attention": {
            "review_queue_total": review_queue_total,
            "dispatch_engine_boundary_action_total": len(dispatch_engine_boundary_actions),
            "ready_external_delivery_processor_total": len(ready_delivery_processors),
            "blocked_external_delivery_processor_total": len(delivery_processor_readiness)
            - len(ready_delivery_processors),
            "ready_external_delivery_sender_total": len(ready_delivery_senders),
            "blocked_external_delivery_sender_total": len(blocked_delivery_senders),
            "external_delivery_sender_contract_ready_total": 1 if delivery_sender_contract_ready else 0,
            "external_delivery_sender_contract_blocked_total": 0 if delivery_sender_contract_ready else 1,
            "bounded_plan_dispatch_unlinked_total": len(unlinked_bounded_plan_traces),
            "bounded_plan_dispatch_pending_total": len(pending_bounded_plan_traces),
            "due_retry_total": len(due_retries),
            "proposal_review_ready_total": len(ready_proposal_reviews),
            "proposal_review_blocked_total": len(proposal_reviews) - len(ready_proposal_reviews),
        },
        "counts": {
            "event_status": status.get("status_counts", {}),
            "stable_state": status.get("stable_state_counts", {}),
            "trigger_source": status.get("trigger_source_counts", {}),
            "blocker_route": _safe_count_map(status.get("blocker_route_counts")),
            "approval_request": _safe_count_map(status.get("approval_request_counts")),
            "approval_decision": _safe_count_map(status.get("approval_decision_counts")),
            "review_route": review_queue.get("route_counts", {}),
            "dispatch_execution": _safe_count_map(status.get("dispatch_execution_counts")),
            "dispatch_engine_supported_action": _list_presence_counts(dispatch_engine_supported_actions),
            "dispatch_engine_boundary_action": _list_presence_counts(dispatch_engine_boundary_actions),
            "verification": _safe_count_map(status.get("verification_counts")),
            "verification_outcome": _safe_count_map(status.get("verification_outcome_counts")),
            "reflection": reflection_counts,
            "reflection_outcome": reflection_outcome_counts,
            "stable_return": _safe_count_map(status.get("stable_return_counts")),
            "bounded_plan_trace": _count_by(bounded_plan_traces, "trace_status"),
            "deadletter_candidate": _safe_count_map(status.get("deadletter_candidate_counts")),
            "deadletter_queue": _safe_count_map(status.get("deadletter_queue_counts")),
            "deadletter_status": _count_by(deadletters, "status"),
            "deadletter_review": _safe_count_map(status.get("deadletter_review_counts")),
            "deadletter_resolution": _safe_count_map(status.get("deadletter_resolution_counts")),
            "deadletter_escalation_handoff": _safe_count_map(status.get("deadletter_escalation_handoff_counts")),
            "deadletter_escalation_acknowledgement": _safe_count_map(
                status.get("deadletter_escalation_acknowledgement_counts")
            ),
            "deadletter_external_escalation_attempt": _safe_count_map(
                status.get("deadletter_external_escalation_attempt_counts")
            ),
            "deadletter_external_escalation_delivery": _safe_count_map(
                status.get("deadletter_external_escalation_delivery_counts")
            ),
            "deadletter_external_delivery_processor_handoff": _safe_count_map(
                status.get("deadletter_external_escalation_delivery_processor_handoff_counts")
            ),
            "deadletter_external_delivery_processor_completion": _safe_count_map(
                status.get("deadletter_external_escalation_delivery_processor_completion_counts")
            ),
            "deadletter_external_delivery_sender_attempt": _safe_count_map(
                status.get("deadletter_external_escalation_delivery_sender_attempt_counts")
            ),
            "deadletter_recovery_request": _safe_count_map(status.get("deadletter_recovery_request_counts")),
            "deadletter_recovery_dispatch": _safe_count_map(status.get("deadletter_recovery_dispatch_counts")),
            "retry_candidate": _safe_count_map(status.get("retry_candidate_counts")),
            "retry_schedule": _safe_count_map(status.get("retry_schedule_counts")),
            "retry_due": _safe_count_map(status.get("retry_due_counts")),
            "retry_dispatch_attempt": _safe_count_map(status.get("retry_dispatch_attempt_counts")),
            "retry_exhausted": _safe_count_map(status.get("retry_exhausted_counts")),
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
            "external_delivery_sender_contract": {delivery_sender_contract_status: 1},
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
            "external_delivery_sender_contract": (
                "/reactor/deadletters/external_escalation_deliveries/sender_contract"
            ),
            "bounded_plan_events": "/reactor/events/list?receipt_kind=reactor.bounded_plan.receipt",
            "bounded_plan_dispatch_traces": ("/reactor/events/list?receipt_kind=reactor.dispatch_attempt.receipt"),
            "reflection_receipts": "/reactor/events/list?receipt_kind=reactor.reflection.receipt",
            "retry_schedules": "/reactor/retries/list",
        },
        "external_delivery_sender_contract": delivery_sender_contract,
        "latest_bounded_plan_traces": bounded_plan_traces[:safe_limit],
        "latest_review_items": review_queue.get("items", [])[:safe_limit],
        "latest_proposal_reviews": proposal_reviews[:safe_limit],
        "ready_external_delivery_processor_items": ready_delivery_processors[:safe_limit],
        "ready_external_delivery_sender_items": ready_delivery_senders[:safe_limit],
        "blocked_external_delivery_sender_items": blocked_delivery_senders[:safe_limit],
        "governance": _readback_governance(),
    }
