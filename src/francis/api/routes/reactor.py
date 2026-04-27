from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field

from francis.governance.api_permission_gate import ApiPermissionDecision, ApiPermissionGate
from francis.reactor import enqueue_event, get_event, list_events, reactor_status, record_dispatch_attempt

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


@router.get("/events/list")
def events_list(
    limit: int = Query(200, ge=1, le=5000),
    status: str | None = None,
    trigger_source: str | None = None,
) -> dict[str, Any]:
    items = list_events(limit=limit, status=status, trigger_source=trigger_source)
    return {"ok": True, "items": items, "total": len(items), "limit": limit}


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
