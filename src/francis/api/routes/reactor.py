from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field

from francis.governance.api_permission_gate import ApiPermissionDecision, ApiPermissionGate
from francis.reactor import (
    enqueue_event,
    get_deadletter,
    get_deadletter_history,
    get_deadletter_recovery_receipt,
    get_event,
    get_external_escalation_delivery,
    get_external_escalation_delivery_processor_readiness,
    get_external_escalation_delivery_sender_readiness,
    get_retry_schedule,
    list_approval_resume_history,
    list_deadletters,
    list_deadletter_recovery_receipts,
    list_events,
    list_external_escalation_deliveries,
    list_external_escalation_delivery_processor_readiness,
    list_external_escalation_delivery_sender_readiness,
    list_proposal_review_history,
    list_retry_schedules,
    reactor_operator_visibility_summary,
    reactor_review_queue,
    reactor_status,
    record_deadletter_escalation_acknowledgement,
    record_deadletter_escalation_handoff,
    record_deadletter_external_escalation_attempt,
    record_deadletter_external_escalation_delivery,
    record_deadletter_external_escalation_delivery_processor_completion,
    record_deadletter_external_escalation_delivery_processor_handoff,
    record_deadletter_external_escalation_delivery_sender_attempt,
    record_deadletter_recovery_request,
    record_deadletter_resolution,
    record_deadletter_review,
    record_dispatch_attempt,
    record_retry_dispatch_attempt,
    record_retry_due,
)

router = APIRouter()
_REACTOR_WRITE_SCOPE = "reactor.write"


class ReactorEventIn(BaseModel):
    trigger_source: str
    summary: str
    trigger_type: str = ""
    reason: str = ""
    actor: str = ""
    mode: str = "assist"
    scope: str = ""
    mission_id: str = ""
    operation_id: str = ""
    approval_id: str = ""
    trace_id: str = ""
    run_id: str = ""
    risk_tier: str = "normal"
    action_class: str = ""
    approval_required: bool = False
    max_actions: int = 1
    max_runtime_seconds: int = 60
    max_retries: int = 0
    backoff_seconds: int = 0
    resource_budget: str = ""
    stop_conditions: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReactorDispatchAttemptIn(BaseModel):
    event_id: str = ""
    id: str = ""
    actor: str = ""
    reason: str = ""
    summary: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReactorRetryDueIn(BaseModel):
    retry_schedule_id: str = ""
    id: str = ""
    actor: str = ""
    reason: str = ""
    summary: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReactorRetryDispatchAttemptIn(BaseModel):
    retry_schedule_id: str = ""
    id: str = ""
    actor: str = ""
    reason: str = ""
    summary: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReactorDeadletterReviewIn(BaseModel):
    deadletter_id: str = ""
    id: str = ""
    actor: str = ""
    decision: str = ""
    reason: str = ""
    summary: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReactorDeadletterResolutionIn(BaseModel):
    deadletter_id: str = ""
    id: str = ""
    actor: str = ""
    decision: str = ""
    reason: str = ""
    summary: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReactorDeadletterEscalationHandoffIn(BaseModel):
    deadletter_id: str = ""
    id: str = ""
    actor: str = ""
    reason: str = ""
    summary: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReactorDeadletterEscalationAcknowledgementIn(BaseModel):
    deadletter_id: str = ""
    id: str = ""
    actor: str = ""
    reason: str = ""
    summary: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReactorDeadletterExternalEscalationAttemptIn(BaseModel):
    deadletter_id: str = ""
    id: str = ""
    actor: str = ""
    reason: str = ""
    summary: str = ""
    external_channel: str = ""
    external_target: str = ""
    external_adapter: str = ""
    channel: str = ""
    target: str = ""
    adapter: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReactorDeadletterExternalEscalationDeliveryIn(BaseModel):
    deadletter_id: str = ""
    id: str = ""
    actor: str = ""
    reason: str = ""
    summary: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReactorDeadletterExternalEscalationDeliveryProcessorHandoffIn(BaseModel):
    delivery_id: str = ""
    id: str = ""
    actor: str = ""
    reason: str = ""
    summary: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReactorDeadletterExternalEscalationDeliveryProcessorCompletionIn(BaseModel):
    delivery_id: str = ""
    id: str = ""
    actor: str = ""
    reason: str = ""
    summary: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReactorDeadletterExternalEscalationDeliverySenderAttemptIn(BaseModel):
    delivery_id: str = ""
    id: str = ""
    actor: str = ""
    reason: str = ""
    summary: str = ""
    external_sender_adapter: str = ""
    external_sender_channel: str = ""
    external_sender_target: str = ""
    sender_adapter: str = ""
    sender_channel: str = ""
    sender_target: str = ""
    adapter: str = ""
    channel: str = ""
    target: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReactorDeadletterRecoveryRequestIn(BaseModel):
    deadletter_id: str = ""
    id: str = ""
    actor: str = ""
    reason: str = ""
    summary: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


def _write_permission(actor: Any, *, route: str, method: str) -> ApiPermissionDecision:
    return ApiPermissionGate.from_env().check(
        actor_id=actor,
        required_scopes=[_REACTOR_WRITE_SCOPE],
        route=route,
        method=method,
    )


def _permission_denied(decision: ApiPermissionDecision) -> dict[str, object]:
    return {
        "ok": False,
        "applied": False,
        "status": "denied",
        "error": "api_permission_denied",
        "governance": {
            "gate": "permission_gate",
            "scope": _REACTOR_WRITE_SCOPE,
            "reason": decision.reason,
            "next_step": "configure_actor_scope_before_mutating_reactor_events",
            "evidence": decision.evidence,
        },
    }


def _payload_dict(payload: Any) -> dict[str, Any]:
    dump = getattr(payload, "model_dump", None)
    if callable(dump):
        data = dump()
    else:
        data = payload.dict()
    return data if isinstance(data, dict) else {}


@router.get("/status")
def status() -> dict[str, Any]:
    return reactor_status()


@router.get("/operator_visibility/summary")
def operator_visibility_summary(limit: int = Query(10, ge=1, le=100)) -> dict[str, Any]:
    return reactor_operator_visibility_summary(limit=limit)


@router.get("/events/list")
def events_list(
    limit: int = Query(200, ge=1, le=5000),
    status: str | None = None,
    trigger_source: str | None = None,
    stable_state: str | None = None,
    blocker_route: str | None = None,
    review_route: str | None = None,
    receipt_kind: str | None = None,
) -> dict[str, Any]:
    items = list_events(
        limit=limit,
        status=status,
        trigger_source=trigger_source,
        stable_state=stable_state,
        blocker_route=blocker_route,
        review_route=review_route,
        receipt_kind=receipt_kind,
    )
    return {"ok": True, "items": items, "total": len(items), "limit": limit}


@router.get("/proposal_reviews/history/list")
def proposal_reviews_history_list(
    limit: int = Query(200, ge=1, le=5000),
    proposal_id: str | None = None,
    plugin_id: str | None = None,
    quality_ready: bool | None = None,
    review_status: str | None = None,
) -> dict[str, Any]:
    items = list_proposal_review_history(
        limit=limit,
        proposal_id=proposal_id,
        plugin_id=plugin_id,
        quality_ready=quality_ready,
        review_status=review_status,
    )
    ready_total = len([item for item in items if bool(item.get("quality_ready"))])
    return {
        "ok": True,
        "items": items,
        "total": len(items),
        "ready_total": ready_total,
        "blocked_total": len(items) - ready_total,
        "limit": limit,
        "proposal_id": proposal_id or "",
        "plugin_id": plugin_id or "",
        "quality_ready": quality_ready,
        "review_status": review_status or "",
        "governance": {
            "gate": "reactor_proposal_review_history_readback",
            "execution_authority": False,
            "dispatch_authority": False,
            "approval_authority": False,
            "proposal_decision_authority": False,
            "promotion_authority": False,
            "external_escalation_authority": False,
            "memory_write": False,
        },
    }


@router.get("/approval_resumes/history/list")
def approval_resumes_history_list(
    limit: int = Query(200, ge=1, le=5000),
    approval_id: str | None = None,
    approval_status: str | None = None,
    target_event_id: str | None = None,
    operation_id: str | None = None,
    approval_allows_dispatch: bool | None = None,
) -> dict[str, Any]:
    items = list_approval_resume_history(
        limit=limit,
        approval_id=approval_id,
        approval_status=approval_status,
        target_event_id=target_event_id,
        operation_id=operation_id,
        approval_allows_dispatch=approval_allows_dispatch,
    )
    allowed_total = len([item for item in items if bool(item.get("approval_allows_dispatch"))])
    return {
        "ok": True,
        "items": items,
        "total": len(items),
        "allowed_total": allowed_total,
        "blocked_total": len(items) - allowed_total,
        "limit": limit,
        "approval_id": approval_id or "",
        "approval_status": approval_status or "",
        "target_event_id": target_event_id or "",
        "operation_id": operation_id or "",
        "approval_allows_dispatch": approval_allows_dispatch,
        "governance": {
            "gate": "reactor_approval_resume_history_readback",
            "execution_authority": False,
            "dispatch_authority": False,
            "approval_authority": False,
            "approval_decision_authority": False,
            "retry_authority": False,
            "external_delivery_authority": False,
            "external_escalation_authority": False,
            "promotion_authority": False,
            "memory_write": False,
        },
    }


@router.get("/review_queue")
def review_queue(
    limit: int = Query(200, ge=1, le=5000),
    route: str | None = None,
) -> dict[str, Any]:
    return reactor_review_queue(limit=limit, route=route)


@router.get("/deadletters/list")
def deadletters_list(
    limit: int = Query(200, ge=1, le=5000),
    status: str | None = None,
) -> dict[str, Any]:
    items = list_deadletters(limit=limit, status=status)
    return {
        "ok": True,
        "items": items,
        "total": len(items),
        "limit": limit,
        "status": status or "",
        "governance": {
            "gate": "reactor_deadletter_queue_readback",
            "execution_authority": False,
            "dispatch_authority": False,
            "retry_authority": False,
            "deadletter_resolution_authority": False,
            "escalation_authority": False,
            "memory_write": False,
        },
    }


@router.get("/deadletters/get")
def deadletters_get(id: str) -> dict[str, Any]:
    item = get_deadletter(id)
    if item is None:
        return {"ok": False, "error": "not_found", "item": None}
    return {
        "ok": True,
        "item": item,
        "governance": {
            "gate": "reactor_deadletter_queue_readback",
            "execution_authority": False,
            "dispatch_authority": False,
            "retry_authority": False,
            "deadletter_resolution_authority": False,
            "escalation_authority": False,
            "memory_write": False,
        },
    }


@router.get("/deadletters/history/get")
def deadletters_history_get(
    id: str,
    limit: int = Query(200, ge=1, le=5000),
    receipt_kind: str | None = None,
    route: str | None = None,
) -> dict[str, Any]:
    history = get_deadletter_history(id, limit=limit, receipt_kind=receipt_kind, route=route)
    if history is None:
        return {"ok": False, "error": "not_found", "history": []}
    return {
        "ok": True,
        "history": history,
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


@router.get("/deadletters/recovery_receipts/list")
def deadletters_recovery_receipts_list(
    limit: int = Query(200, ge=1, le=5000),
    status: str | None = None,
    deadletter_id: str | None = None,
    event_id: str | None = None,
    recovery_event_id: str | None = None,
    route: str | None = None,
) -> dict[str, Any]:
    items = list_deadletter_recovery_receipts(
        limit=limit,
        status=status,
        deadletter_id=deadletter_id,
        event_id=event_id,
        recovery_event_id=recovery_event_id,
        route=route,
    )
    return {
        "ok": True,
        "items": items,
        "total": len(items),
        "limit": limit,
        "status": status or "",
        "deadletter_id": deadletter_id or "",
        "event_id": event_id or "",
        "recovery_event_id": recovery_event_id or "",
        "route": route or "",
        "governance": {
            "gate": "reactor_deadletter_recovery_receipt_readback",
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


@router.get("/deadletters/recovery_receipts/get")
def deadletters_recovery_receipts_get(id: str) -> dict[str, Any]:
    item = get_deadletter_recovery_receipt(id)
    if item is None:
        return {"ok": False, "error": "not_found", "item": None}
    return {
        "ok": True,
        "item": item,
        "governance": {
            "gate": "reactor_deadletter_recovery_receipt_readback",
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


@router.get("/deadletters/external_escalation_deliveries/list")
def deadletter_external_escalation_deliveries_list(
    limit: int = Query(200, ge=1, le=5000),
    status: str | None = None,
    deadletter_id: str | None = None,
    event_id: str | None = None,
) -> dict[str, Any]:
    items = list_external_escalation_deliveries(
        limit=limit,
        status=status,
        deadletter_id=deadletter_id,
        event_id=event_id,
    )
    return {
        "ok": True,
        "items": items,
        "total": len(items),
        "limit": limit,
        "status": status or "",
        "deadletter_id": deadletter_id or "",
        "event_id": event_id or "",
        "governance": {
            "gate": "reactor_external_escalation_delivery_readback",
            "execution_authority": False,
            "dispatch_authority": False,
            "retry_authority": False,
            "external_delivery_authority": False,
            "external_escalation_authority": False,
            "escalation_authority": False,
            "memory_write": False,
        },
    }


@router.get("/deadletters/external_escalation_deliveries/get")
def deadletter_external_escalation_deliveries_get(id: str) -> dict[str, Any]:
    item = get_external_escalation_delivery(id)
    if item is None:
        return {"ok": False, "error": "not_found", "item": None}
    return {
        "ok": True,
        "item": item,
        "governance": {
            "gate": "reactor_external_escalation_delivery_readback",
            "execution_authority": False,
            "dispatch_authority": False,
            "retry_authority": False,
            "external_delivery_authority": False,
            "external_escalation_authority": False,
            "escalation_authority": False,
            "memory_write": False,
        },
    }


@router.get("/deadletters/external_escalation_deliveries/processor_readiness/list")
def deadletter_external_escalation_delivery_processor_readiness_list(
    limit: int = Query(200, ge=1, le=5000),
    status: str | None = None,
    deadletter_id: str | None = None,
    event_id: str | None = None,
    processor_status: str | None = None,
) -> dict[str, Any]:
    items = list_external_escalation_delivery_processor_readiness(
        limit=limit,
        status=status,
        deadletter_id=deadletter_id,
        event_id=event_id,
        processor_status=processor_status,
    )
    ready_total = len([item for item in items if bool(item.get("delivery_processor_ready"))])
    return {
        "ok": True,
        "items": items,
        "total": len(items),
        "ready_total": ready_total,
        "blocked_total": len(items) - ready_total,
        "limit": limit,
        "status": status or "",
        "processor_status": processor_status or "",
        "deadletter_id": deadletter_id or "",
        "event_id": event_id or "",
        "governance": {
            "gate": "reactor_external_escalation_delivery_processor_readiness",
            "execution_authority": False,
            "dispatch_authority": False,
            "retry_authority": False,
            "external_delivery_queue_authority": False,
            "external_delivery_authority": False,
            "external_escalation_authority": False,
            "escalation_authority": False,
            "delivery_processor_claim_authority": False,
            "memory_write": False,
        },
    }


@router.get("/deadletters/external_escalation_deliveries/processor_readiness/get")
def deadletter_external_escalation_delivery_processor_readiness_get(id: str) -> dict[str, Any]:
    item = get_external_escalation_delivery_processor_readiness(id)
    if item is None:
        return {"ok": False, "error": "not_found", "item": None}
    return {
        "ok": True,
        "item": item,
        "governance": {
            "gate": "reactor_external_escalation_delivery_processor_readiness",
            "execution_authority": False,
            "dispatch_authority": False,
            "retry_authority": False,
            "external_delivery_queue_authority": False,
            "external_delivery_authority": False,
            "external_escalation_authority": False,
            "escalation_authority": False,
            "delivery_processor_claim_authority": False,
            "memory_write": False,
        },
    }


@router.get("/deadletters/external_escalation_deliveries/sender_readiness/list")
def deadletter_external_escalation_delivery_sender_readiness_list(
    limit: int = Query(200, ge=1, le=5000),
    status: str | None = None,
    deadletter_id: str | None = None,
    event_id: str | None = None,
    sender_status: str | None = None,
) -> dict[str, Any]:
    items = list_external_escalation_delivery_sender_readiness(
        limit=limit,
        status=status,
        deadletter_id=deadletter_id,
        event_id=event_id,
        sender_status=sender_status,
    )
    ready_total = len([item for item in items if bool(item.get("external_delivery_sender_ready"))])
    return {
        "ok": True,
        "items": items,
        "total": len(items),
        "ready_total": ready_total,
        "blocked_total": len(items) - ready_total,
        "limit": limit,
        "status": status or "",
        "sender_status": sender_status or "",
        "deadletter_id": deadletter_id or "",
        "event_id": event_id or "",
        "governance": {
            "gate": "reactor_external_escalation_delivery_sender_readiness",
            "execution_authority": False,
            "dispatch_authority": False,
            "retry_authority": False,
            "retry_execution_authority": False,
            "external_delivery_queue_authority": False,
            "external_delivery_authority": False,
            "external_delivery_sender_attempt_authority": False,
            "external_escalation_authority": False,
            "escalation_authority": False,
            "approval_authority": False,
            "promotion_authority": False,
            "delivery_processor_claim_authority": False,
            "memory_write": False,
        },
    }


@router.get("/deadletters/external_escalation_deliveries/sender_readiness/get")
def deadletter_external_escalation_delivery_sender_readiness_get(id: str) -> dict[str, Any]:
    item = get_external_escalation_delivery_sender_readiness(id)
    if item is None:
        return {"ok": False, "error": "not_found", "item": None}
    return {
        "ok": True,
        "item": item,
        "governance": {
            "gate": "reactor_external_escalation_delivery_sender_readiness",
            "execution_authority": False,
            "dispatch_authority": False,
            "retry_authority": False,
            "retry_execution_authority": False,
            "external_delivery_queue_authority": False,
            "external_delivery_authority": False,
            "external_delivery_sender_attempt_authority": False,
            "external_escalation_authority": False,
            "escalation_authority": False,
            "approval_authority": False,
            "promotion_authority": False,
            "delivery_processor_claim_authority": False,
            "memory_write": False,
        },
    }


@router.post("/deadletters/review")
def deadletters_review(payload: ReactorDeadletterReviewIn, request: Request) -> dict[str, Any]:
    permission = _write_permission(payload.actor, route=request.url.path, method=request.method)
    if not permission.allowed:
        return _permission_denied(permission)
    data = _payload_dict(payload)
    deadletter_id = str(data.get("deadletter_id") or data.get("id") or "")
    return record_deadletter_review(deadletter_id, data)


@router.post("/deadletters/resolve")
def deadletters_resolve(payload: ReactorDeadletterResolutionIn, request: Request) -> dict[str, Any]:
    permission = _write_permission(payload.actor, route=request.url.path, method=request.method)
    if not permission.allowed:
        return _permission_denied(permission)
    data = _payload_dict(payload)
    deadletter_id = str(data.get("deadletter_id") or data.get("id") or "")
    return record_deadletter_resolution(deadletter_id, data)


@router.post("/deadletters/escalation_handoff")
def deadletters_escalation_handoff(
    payload: ReactorDeadletterEscalationHandoffIn,
    request: Request,
) -> dict[str, Any]:
    permission = _write_permission(payload.actor, route=request.url.path, method=request.method)
    if not permission.allowed:
        return _permission_denied(permission)
    data = _payload_dict(payload)
    deadletter_id = str(data.get("deadletter_id") or data.get("id") or "")
    return record_deadletter_escalation_handoff(deadletter_id, data)


@router.post("/deadletters/escalation_acknowledgement")
def deadletters_escalation_acknowledgement(
    payload: ReactorDeadletterEscalationAcknowledgementIn,
    request: Request,
) -> dict[str, Any]:
    permission = _write_permission(payload.actor, route=request.url.path, method=request.method)
    if not permission.allowed:
        return _permission_denied(permission)
    data = _payload_dict(payload)
    deadletter_id = str(data.get("deadletter_id") or data.get("id") or "")
    return record_deadletter_escalation_acknowledgement(deadletter_id, data)


@router.post("/deadletters/external_escalation_attempt")
def deadletters_external_escalation_attempt(
    payload: ReactorDeadletterExternalEscalationAttemptIn,
    request: Request,
) -> dict[str, Any]:
    permission = _write_permission(payload.actor, route=request.url.path, method=request.method)
    if not permission.allowed:
        return _permission_denied(permission)
    data = _payload_dict(payload)
    deadletter_id = str(data.get("deadletter_id") or data.get("id") or "")
    return record_deadletter_external_escalation_attempt(deadletter_id, data)


@router.post("/deadletters/external_escalation_delivery")
def deadletters_external_escalation_delivery(
    payload: ReactorDeadletterExternalEscalationDeliveryIn,
    request: Request,
) -> dict[str, Any]:
    permission = _write_permission(payload.actor, route=request.url.path, method=request.method)
    if not permission.allowed:
        return _permission_denied(permission)
    data = _payload_dict(payload)
    deadletter_id = str(data.get("deadletter_id") or data.get("id") or "")
    return record_deadletter_external_escalation_delivery(deadletter_id, data)


@router.post("/deadletters/external_escalation_delivery_processor_handoff")
def deadletters_external_escalation_delivery_processor_handoff(
    payload: ReactorDeadletterExternalEscalationDeliveryProcessorHandoffIn,
    request: Request,
) -> dict[str, Any]:
    permission = _write_permission(payload.actor, route=request.url.path, method=request.method)
    if not permission.allowed:
        return _permission_denied(permission)
    data = _payload_dict(payload)
    delivery_id = str(data.get("delivery_id") or data.get("id") or "")
    return record_deadletter_external_escalation_delivery_processor_handoff(delivery_id, data)


@router.post("/deadletters/external_escalation_delivery_processor_completion")
def deadletters_external_escalation_delivery_processor_completion(
    payload: ReactorDeadletterExternalEscalationDeliveryProcessorCompletionIn,
    request: Request,
) -> dict[str, Any]:
    permission = _write_permission(payload.actor, route=request.url.path, method=request.method)
    if not permission.allowed:
        return _permission_denied(permission)
    data = _payload_dict(payload)
    delivery_id = str(data.get("delivery_id") or data.get("id") or "")
    return record_deadletter_external_escalation_delivery_processor_completion(delivery_id, data)


@router.post("/deadletters/external_escalation_delivery_sender_attempt")
def deadletters_external_escalation_delivery_sender_attempt(
    payload: ReactorDeadletterExternalEscalationDeliverySenderAttemptIn,
    request: Request,
) -> dict[str, Any]:
    permission = _write_permission(payload.actor, route=request.url.path, method=request.method)
    if not permission.allowed:
        return _permission_denied(permission)
    data = _payload_dict(payload)
    delivery_id = str(data.get("delivery_id") or data.get("id") or "")
    return record_deadletter_external_escalation_delivery_sender_attempt(delivery_id, data)


@router.post("/deadletters/recovery_request")
def deadletters_recovery_request(
    payload: ReactorDeadletterRecoveryRequestIn,
    request: Request,
) -> dict[str, Any]:
    permission = _write_permission(payload.actor, route=request.url.path, method=request.method)
    if not permission.allowed:
        return _permission_denied(permission)
    data = _payload_dict(payload)
    deadletter_id = str(data.get("deadletter_id") or data.get("id") or "")
    return record_deadletter_recovery_request(deadletter_id, data)


@router.get("/retries/list")
def retries_list(
    limit: int = Query(200, ge=1, le=5000),
    status: str | None = None,
) -> dict[str, Any]:
    items = list_retry_schedules(limit=limit, status=status)
    return {
        "ok": True,
        "items": items,
        "total": len(items),
        "limit": limit,
        "status": status or "",
        "governance": {
            "gate": "reactor_retry_schedule_readback",
            "execution_authority": False,
            "dispatch_authority": False,
            "retry_authority": False,
            "retry_execution_authority": False,
            "deadletter_resolution_authority": False,
            "escalation_authority": False,
            "memory_write": False,
        },
    }


@router.get("/retries/get")
def retries_get(id: str) -> dict[str, Any]:
    item = get_retry_schedule(id)
    if item is None:
        return {"ok": False, "error": "not_found", "item": None}
    return {
        "ok": True,
        "item": item,
        "governance": {
            "gate": "reactor_retry_schedule_readback",
            "execution_authority": False,
            "dispatch_authority": False,
            "retry_authority": False,
            "retry_execution_authority": False,
            "deadletter_resolution_authority": False,
            "escalation_authority": False,
            "memory_write": False,
        },
    }


@router.post("/retries/mark_due")
def retries_mark_due(payload: ReactorRetryDueIn, request: Request) -> dict[str, Any]:
    permission = _write_permission(payload.actor, route=request.url.path, method=request.method)
    if not permission.allowed:
        return _permission_denied(permission)
    data = _payload_dict(payload)
    retry_schedule_id = str(data.get("retry_schedule_id") or data.get("id") or "")
    return record_retry_due(retry_schedule_id, data)


@router.post("/retries/dispatch_attempt")
def retries_dispatch_attempt(payload: ReactorRetryDispatchAttemptIn, request: Request) -> dict[str, Any]:
    permission = _write_permission(payload.actor, route=request.url.path, method=request.method)
    if not permission.allowed:
        return _permission_denied(permission)
    data = _payload_dict(payload)
    retry_schedule_id = str(data.get("retry_schedule_id") or data.get("id") or "")
    return record_retry_dispatch_attempt(retry_schedule_id, data)


@router.get("/events/get")
def events_get(id: str) -> dict[str, Any]:
    item = get_event(id)
    if item is None:
        return {"ok": False, "error": "not_found", "item": None}
    return {"ok": True, "item": item}


@router.post("/events/enqueue")
def events_enqueue(payload: ReactorEventIn, request: Request) -> dict[str, Any]:
    permission = _write_permission(payload.actor, route=request.url.path, method=request.method)
    if not permission.allowed:
        return _permission_denied(permission)
    return enqueue_event(_payload_dict(payload))


@router.post("/events/dispatch_attempt")
def events_dispatch_attempt(payload: ReactorDispatchAttemptIn, request: Request) -> dict[str, Any]:
    permission = _write_permission(payload.actor, route=request.url.path, method=request.method)
    if not permission.allowed:
        return _permission_denied(permission)
    data = _payload_dict(payload)
    event_id = str(data.get("event_id") or data.get("id") or "")
    return record_dispatch_attempt(event_id, data)
