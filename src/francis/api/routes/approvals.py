from __future__ import annotations

import ipaddress
import os
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from francis.governance.approval_projection import approval_projection_fields
from francis.governance.approvals import (
    BUILDER_APPROVAL_ACTOR,
    builder_self_decide,
    decide as decide_request,
    list_operator_delegation_receipts,
    list_requests,
    request as create_request,
)
from francis.governance.api_permission_gate import ApiPermissionDecision, ApiPermissionGate
from francis.governance.redaction import redact_governed_display_value

router = APIRouter()
_TRUE_VALUES = {"1", "true", "t", "yes", "y", "on"}
_LOCAL_HOST_ALIASES = {"localhost", "testclient"}
_APPROVAL_DECISION_SCOPE = "approvals.decide"


def _to_bool(value: str | None, *, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in _TRUE_VALUES


def _remote_decisions_allowed() -> bool:
    return _to_bool(os.getenv("FRANCIS_APPROVALS_ALLOW_REMOTE_DECISIONS"), default=False)


def _is_local_client(host: str) -> bool:
    normalized = host.strip().lower()
    if not normalized:
        return False
    if normalized in _LOCAL_HOST_ALIASES:
        return True
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False


def _approval_item(record: dict[str, Any]) -> dict[str, Any]:
    item = dict(record) if isinstance(record, dict) else {}
    out = redact_governed_display_value(item)
    out = out if isinstance(out, dict) else {}
    out.update(approval_projection_fields(item))
    return out


def _decision_permission(actor: Any) -> ApiPermissionDecision:
    return ApiPermissionGate.from_env().check(
        actor_id=actor,
        required_scopes=[_APPROVAL_DECISION_SCOPE],
        route="/approvals/decision",
        method="POST",
    )


def _permission_denied(decision: ApiPermissionDecision) -> dict[str, object]:
    return {
        "ok": False,
        "status": "denied",
        "error": "api_permission_denied",
        "governance": {
            "gate": "permission_gate",
            "reason": decision.reason,
            "next_step": "configure_actor_scope_before_deciding_approvals",
            "evidence": decision.evidence,
        },
    }


class ApprovalIn(BaseModel):
    action: str
    reason: str = "requested"
    payload: dict[str, object] = Field(default_factory=dict)


class ApprovalDecisionIn(BaseModel):
    id: str
    action: str
    comment: str | None = None
    reason: str | None = None
    actor: str | None = None


@router.post("/request")
def request_approval(payload: ApprovalIn) -> dict[str, object]:
    try:
        item = create_request(payload.action, payload.reason, payload.payload)
        return _approval_item(item)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.get("/list")
def list_approvals(status: str = "pending", limit: int = 100) -> dict[str, object]:
    try:
        return {"items": [_approval_item(item) for item in list_requests(status=status, limit=limit)]}
    except Exception as exc:
        return {"items": [], "error": str(exc)}


@router.get("/delegations")
def list_delegations(limit: int = 100, receiving_actor: str = "", active_only: bool = False) -> dict[str, object]:
    try:
        return list_operator_delegation_receipts(
            limit=limit,
            receiving_actor=receiving_actor,
            active_only=active_only,
        )
    except Exception as exc:
        return {"ok": False, "items": [], "error": str(exc)}


@router.post("/decision")
def decide_approval(request: Request, payload: ApprovalDecisionIn) -> dict[str, object]:
    try:
        client_host = request.client.host if request.client is not None else ""
        if not _remote_decisions_allowed() and not _is_local_client(client_host):
            raise HTTPException(status_code=403, detail="approval decisions require a local caller")
        decision_note = payload.comment or payload.reason
        if (payload.actor or "").strip() == BUILDER_APPROVAL_ACTOR:
            result = builder_self_decide(payload.id, payload.action, reason=decision_note, actor=payload.actor)
            if isinstance(result.get("item"), dict):
                result = dict(result)
                result["item"] = _approval_item(result["item"])
            return result

        permission = _decision_permission(payload.actor)
        if not permission.allowed:
            return _permission_denied(permission)

        result = decide_request(payload.id, payload.action, decision_note, actor=payload.actor)
        if isinstance(result.get("item"), dict):
            result = dict(result)
            result["item"] = _approval_item(result["item"])
        return result
    except Exception as exc:
        if isinstance(exc, HTTPException):
            raise
        return {"ok": False, "error": str(exc)}
