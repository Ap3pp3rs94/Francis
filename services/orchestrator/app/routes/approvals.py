from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from francis_brain.ledger import RunLedger
from francis_core.config import settings
from francis_core.workspace_fs import WorkspaceFS
from francis_policy.rbac import can
from services.orchestrator.app.adversarial_guard import assess_untrusted_input, quarantine_untrusted_input
from services.orchestrator.app.approvals_store import add_decision, create_request, get_request, list_requests
from services.orchestrator.app.control_state import check_action_allowed

router = APIRouter(tags=["approvals"])

_workspace_root = Path(settings.workspace_root).resolve()
_repo_root = _workspace_root.parent
_fs = WorkspaceFS(
    roots=[_workspace_root],
    journal_path=(_workspace_root / "journals" / "fs.jsonl").resolve(),
)
_ledger = RunLedger(_fs, rel_path="runs/run_ledger.jsonl")


class ApprovalRequestPayload(BaseModel):
    action: str
    reason: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class ApprovalDecisionPayload(BaseModel):
    decision: str = Field(description="approve|reject|approved|rejected")
    note: str = ""


def _role_from_request(request: Request) -> str:
    return request.headers.get("x-francis-role", "architect").strip().lower()


def _enforce_rbac(request: Request, action: str) -> None:
    role = _role_from_request(request)
    if not can(role, action):
        raise HTTPException(status_code=403, detail=f"RBAC denied: role={role}, action={action}")


def _enforce_control(action: str) -> None:
    allowed, reason, _state = check_action_allowed(
        _fs,
        repo_root=_repo_root,
        workspace_root=_workspace_root,
        app="approvals",
        action=action,
        mutating=False,
    )
    if not allowed:
        raise HTTPException(status_code=403, detail=f"Control denied: {reason}")


@router.get("/approvals")
def approvals(request: Request, status: str | None = None, action: str | None = None, limit: int = 50) -> dict:
    _enforce_control("approvals.read")
    _enforce_rbac(request, "approvals.read")
    approvals_list = list_requests(_fs, status=status, action=action, limit=limit)
    return {"status": "ok", "count": len(approvals_list), "approvals": approvals_list}


@router.get("/approvals/{approval_id}")
def approval_get(approval_id: str, request: Request) -> dict:
    _enforce_control("approvals.read")
    _enforce_rbac(request, "approvals.read")
    approval = get_request(_fs, approval_id)
    if approval is None:
        raise HTTPException(status_code=404, detail=f"Approval not found: {approval_id}")
    return {"status": "ok", "approval": approval}


@router.post("/approvals/request")
def approval_request(request: Request, payload: ApprovalRequestPayload) -> dict:
    _enforce_control("approvals.request")
    _enforce_rbac(request, "approvals.request")
    run_id = str(getattr(request.state, "run_id", uuid4()))
    trace_id = str(getattr(request.state, "trace_id", None) or run_id)
    role = _role_from_request(request)
    normalized_payload = payload.model_dump()
    assessment = assess_untrusted_input(
        surface="approvals",
        action="approvals.request",
        payload=normalized_payload,
    )
    if assessment.get("quarantined", False):
        quarantine = quarantine_untrusted_input(
            _fs,
            run_id=run_id,
            trace_id=trace_id,
            surface="approvals",
            action="approvals.request",
            payload=normalized_payload,
            assessment=assessment,
        )
        raise HTTPException(
            status_code=409,
            detail={"message": assessment["message"], "quarantine": quarantine},
        )

    approval = create_request(
        _fs,
        run_id=run_id,
        action=payload.action.strip(),
        reason=payload.reason.strip(),
        requested_by=role,
        metadata=payload.metadata,
    )
    _ledger.append(
        run_id=run_id,
        kind="approval.requested",
        summary={
            "approval_id": approval.get("id"),
            "action": approval.get("action"),
            "requested_by": role,
        },
    )
    return {"status": "ok", "run_id": run_id, "approval": approval}


@router.post("/approvals/{approval_id}/decision")
def approval_decision(approval_id: str, request: Request, payload: ApprovalDecisionPayload) -> dict:
    _enforce_control("approvals.decide")
    _enforce_rbac(request, "approvals.decide")
    run_id = str(getattr(request.state, "run_id", uuid4()))
    trace_id = str(getattr(request.state, "trace_id", None) or run_id)
    role = _role_from_request(request)
    normalized_payload = {
        "approval_id": str(approval_id).strip(),
        **payload.model_dump(),
    }
    assessment = assess_untrusted_input(
        surface="approvals",
        action="approvals.decision",
        payload=normalized_payload,
    )
    if assessment.get("quarantined", False):
        quarantine = quarantine_untrusted_input(
            _fs,
            run_id=run_id,
            trace_id=trace_id,
            surface="approvals",
            action="approvals.decision",
            payload=normalized_payload,
            assessment=assessment,
        )
        raise HTTPException(
            status_code=409,
            detail={"message": assessment["message"], "quarantine": quarantine},
        )

    try:
        decision_event = add_decision(
            _fs,
            run_id=run_id,
            approval_id=approval_id,
            decision=payload.decision.strip().lower(),
            decided_by=role,
            note=payload.note.strip(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if decision_event is None:
        raise HTTPException(status_code=404, detail=f"Approval not found: {approval_id}")

    approval = get_request(_fs, approval_id)
    _ledger.append(
        run_id=run_id,
        kind="approval.decided",
        summary={
            "approval_id": approval_id,
            "decision": decision_event.get("decision"),
            "decided_by": role,
            "action": approval.get("action") if isinstance(approval, dict) else None,
        },
    )
    return {"status": "ok", "run_id": run_id, "approval": approval, "decision": decision_event}
