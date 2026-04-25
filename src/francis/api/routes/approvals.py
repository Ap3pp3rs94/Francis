from __future__ import annotations

import ipaddress
import os
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from francis.governance.approval_projection import approval_projection_fields
from francis.governance.approvals import decide as decide_request, list_requests, request as create_request
from francis.governance.redaction import redact_governed_display_value

router = APIRouter()
_TRUE_VALUES = {"1", "true", "t", "yes", "y", "on"}
_LOCAL_HOST_ALIASES = {"localhost", "testclient"}


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


class ApprovalIn(BaseModel):
    action: str
    reason: str = "requested"
    payload: dict[str, object] = Field(default_factory=dict)


class ApprovalDecisionIn(BaseModel):
    id: str
    action: str
    comment: str | None = None


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


@router.post("/decision")
def decide_approval(request: Request, payload: ApprovalDecisionIn) -> dict[str, object]:
    try:
        client_host = request.client.host if request.client is not None else ""
        if not _remote_decisions_allowed() and not _is_local_client(client_host):
            raise HTTPException(status_code=403, detail="approval decisions require a local caller")
        result = decide_request(payload.id, payload.action, payload.comment)
        if isinstance(result.get("item"), dict):
            result = dict(result)
            result["item"] = _approval_item(result["item"])
        return result
    except Exception as exc:
        if isinstance(exc, HTTPException):
            raise
        return {"ok": False, "error": str(exc)}
