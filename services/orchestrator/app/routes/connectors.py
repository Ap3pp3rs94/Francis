from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from francis_brain.ledger import RunLedger
from francis_core.config import settings
from francis_core.workspace_fs import WorkspaceFS
from francis_connectors.library import (
    build_connector_library,
    build_connector_provenance,
    list_connector_entries,
    quarantine_connector,
    revoke_connector,
)
from francis_policy.rbac import can
from services.orchestrator.app.approvals_store import create_request, ensure_action_approved, list_requests
from services.orchestrator.app.control_state import check_action_allowed

router = APIRouter(tags=["connectors"])

_workspace_root = Path(settings.workspace_root).resolve()
_repo_root = _workspace_root.parent
_fs = WorkspaceFS(
    roots=[_workspace_root],
    journal_path=(_workspace_root / "journals" / "fs.jsonl").resolve(),
)
_ledger = RunLedger(_fs, rel_path="runs/run_ledger.jsonl")


class ConnectorLifecycleRequest(BaseModel):
    reason: str = ""


class ConnectorRevokeRequest(BaseModel):
    reason: str = ""
    approval_id: str | None = None


def _role_from_request(request: Request) -> str:
    return request.headers.get("x-francis-role", "architect").strip().lower()


def _enforce_rbac(request: Request, action: str) -> str:
    role = _role_from_request(request)
    if not can(role, action):
        raise HTTPException(status_code=403, detail=f"RBAC denied: role={role}, action={action}")
    return role


def _enforce_control(action: str, *, mutating: bool) -> None:
    allowed, reason, _state = check_action_allowed(
        _fs,
        repo_root=_repo_root,
        workspace_root=_workspace_root,
        app="connectors",
        action=action,
        mutating=mutating,
    )
    if not allowed:
        raise HTTPException(status_code=403, detail=f"Control denied: {reason}")


def _find_connector(connector_id: str) -> dict[str, Any] | None:
    normalized = str(connector_id or "").strip()
    if not normalized:
        return None
    return next((row for row in list_connector_entries(_fs) if str(row.get("id", "")).strip() == normalized), None)


def _find_revoke_approval(connector_id: str) -> dict[str, Any] | None:
    normalized = str(connector_id or "").strip()
    for row in reversed(list_requests(_fs, action="connectors.revoke", limit=100)):
        if not isinstance(row, dict):
            continue
        metadata = row.get("metadata", {}) if isinstance(row.get("metadata"), dict) else {}
        if str(metadata.get("connector_id", "")).strip() == normalized:
            return row
    return None


def _connector_presentation(connector: dict[str, Any]) -> dict[str, Any]:
    provenance = build_connector_provenance(connector)
    status = str(connector.get("status", "available")).strip().lower() or "available"
    summary = (
        f"{str(connector.get('name', 'Connector')).strip() or 'Connector'} is {status}. "
        f"{str(provenance.get('summary', '')).strip()}"
    ).strip()
    return {
        "kind": "connectors.lifecycle",
        "summary": summary,
        "severity": "high" if status in {"quarantined", "revoked"} or bool(provenance.get("review_required")) else "low",
        "cards": [
            {"label": "Status", "value": status, "tone": "high" if status in {"quarantined", "revoked"} else "low"},
            {
                "label": "Provenance",
                "value": str(provenance.get("label", "Internal")).strip() or "Internal",
                "tone": str(provenance.get("tone", "low")).strip() or "low",
            },
            {
                "label": "Review",
                "value": str(provenance.get("review_label", "internal")).strip() or "internal",
                "tone": "high" if bool(provenance.get("review_required")) else "low",
            },
            {
                "label": "Risk",
                "value": str(connector.get("risk_tier", "medium")).strip().lower() or "medium",
                "tone": "medium",
            },
        ],
        "detail": {
            "connector_id": str(connector.get("id", "")).strip(),
            "status": status,
            "provenance": provenance,
        },
    }


@router.get("/connectors/library")
def connector_library(request: Request) -> dict[str, Any]:
    _enforce_control("connectors.read", mutating=False)
    _enforce_rbac(request, "connectors.read")
    entries = list_connector_entries(_fs)
    library = build_connector_library(entries)
    return {
        "status": "ok",
        "surface": "connector_library",
        "summary": (
            f"{library['connector_count']} connector(s), {library['active_count']} active, "
            f"{library['quarantined_count']} quarantined, {library['revoked_count']} revoked."
            if library["connector_count"]
            else "No connector entries are cataloged yet."
        ),
        "library": library,
        "entries": entries,
    }


@router.post("/connectors/{connector_id}/quarantine")
def connector_quarantine(connector_id: str, request: Request, payload: ConnectorLifecycleRequest) -> dict[str, Any]:
    _enforce_control("connectors.quarantine", mutating=True)
    role = _enforce_rbac(request, "connectors.quarantine")
    run_id = str(getattr(request.state, "run_id", uuid4()))
    connector = quarantine_connector(
        _fs,
        connector_id,
        reason=payload.reason,
        actor=f"connectors:{role}",
    )
    if connector is None:
        raise HTTPException(status_code=404, detail=f"Connector not found: {connector_id}")
    _ledger.append(
        run_id=run_id,
        kind="connectors.quarantine",
        summary={
            "connector_id": str(connector.get("id", "")).strip(),
            "status": str(connector.get("status", "")).strip(),
            "reason": str(connector.get("quarantine_reason", "")).strip(),
        },
    )
    return {
        "status": "ok",
        "run_id": run_id,
        "connector": connector,
        "presentation": _connector_presentation(connector),
    }


@router.post("/connectors/{connector_id}/revoke/request-approval")
def connector_request_revoke_approval(
    connector_id: str,
    request: Request,
    payload: ConnectorLifecycleRequest,
) -> dict[str, Any]:
    _enforce_control("approvals.request", mutating=False)
    role = _enforce_rbac(request, "approvals.request")
    connector = _find_connector(connector_id)
    if connector is None:
        raise HTTPException(status_code=404, detail=f"Connector not found: {connector_id}")
    run_id = str(getattr(request.state, "run_id", uuid4()))
    existing = _find_revoke_approval(connector_id)
    if existing is None:
        approval = create_request(
            _fs,
            run_id=run_id,
            action="connectors.revoke",
            reason=str(payload.reason).strip() or f"Revoke connector {connector_id}",
            requested_by=role,
            metadata={
                "connector_id": connector_id,
                "action_kind": "connectors.revoke",
                "source": "connectors.library",
            },
        )
    else:
        approval = existing
    _ledger.append(
        run_id=run_id,
        kind="connectors.revoke.request_approval",
        summary={
            "connector_id": connector_id,
            "approval_id": str(approval.get("id", "")).strip(),
            "status": str(approval.get("status", "")).strip().lower() or "pending",
        },
    )
    return {"status": "ok", "run_id": run_id, "approval": approval, "connector": connector}


@router.post("/connectors/{connector_id}/revoke")
def connector_revoke(connector_id: str, request: Request, payload: ConnectorRevokeRequest) -> dict[str, Any]:
    _enforce_control("connectors.revoke", mutating=True)
    role = _enforce_rbac(request, "connectors.revoke")
    connector = _find_connector(connector_id)
    if connector is None:
        raise HTTPException(status_code=404, detail=f"Connector not found: {connector_id}")
    run_id = str(getattr(request.state, "run_id", uuid4()))
    approved, approval_detail = ensure_action_approved(
        _fs,
        run_id=run_id,
        action="connectors.revoke",
        requested_by=role,
        reason=str(payload.reason).strip() or f"Revoke connector {connector_id}",
        approval_id=str(payload.approval_id or "").strip() or None,
        metadata={
            "connector_id": connector_id,
            "action_kind": "connectors.revoke",
            "source": "connectors.library",
        },
    )
    if not approved:
        raise HTTPException(
            status_code=403,
            detail={
                "message": "Action requires approval: connectors.revoke",
                "approval": approval_detail,
            },
        )
    updated = revoke_connector(
        _fs,
        connector_id,
        reason=payload.reason,
        actor=f"connectors:{role}",
    )
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Connector not found: {connector_id}")
    approval_id = str(
        payload.approval_id
        or approval_detail.get("approval_request_id")
        or (approval_detail.get("request", {}) if isinstance(approval_detail.get("request"), dict) else {}).get("id")
        or ""
    ).strip()
    _ledger.append(
        run_id=run_id,
        kind="connectors.revoke",
        summary={
            "connector_id": str(updated.get("id", "")).strip(),
            "status": str(updated.get("status", "")).strip(),
            "approval_id": approval_id,
            "reason": str(updated.get("revocation_reason", "")).strip(),
        },
    )
    return {
        "status": "ok",
        "run_id": run_id,
        "connector": updated,
        "approval_id": approval_id,
        "presentation": _connector_presentation(updated),
    }
