from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from francis.governance.approvals import decide, list_requests, request

router = APIRouter()


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
        return request(payload.action, payload.reason, payload.payload)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.get("/list")
def list_approvals(status: str = "pending", limit: int = 100) -> dict[str, object]:
    try:
        return {"items": list_requests(status=status, limit=limit)}
    except Exception as exc:
        return {"items": [], "error": str(exc)}


@router.post("/decision")
def decide_approval(payload: ApprovalDecisionIn) -> dict[str, object]:
    try:
        return decide(payload.id, payload.action, payload.comment)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
