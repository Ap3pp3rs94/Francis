from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from francis_brain.ledger import RunLedger
from francis_core.config import settings
from francis_core.dependency_library import (
    build_dependency_library,
    build_dependency_provenance,
    list_dependency_entries,
    quarantine_dependency,
    revoke_dependency,
)
from francis_core.workspace_fs import WorkspaceFS
from francis_policy.rbac import can
from services.orchestrator.app.approvals_store import create_request, ensure_action_approved, list_requests
from services.orchestrator.app.control_state import check_action_allowed

router = APIRouter(tags=["dependencies"])

_workspace_root = Path(settings.workspace_root).resolve()
_repo_root = _workspace_root.parent
_fs = WorkspaceFS(
    roots=[_workspace_root],
    journal_path=(_workspace_root / "journals" / "fs.jsonl").resolve(),
)
_ledger = RunLedger(_fs, rel_path="runs/run_ledger.jsonl")


class DependencyLifecycleRequest(BaseModel):
    reason: str = ""


class DependencyRevokeRequest(BaseModel):
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
        app="dependencies",
        action=action,
        mutating=mutating,
    )
    if not allowed:
        raise HTTPException(status_code=403, detail=f"Control denied: {reason}")


def _find_dependency(dependency_id: str) -> dict[str, Any] | None:
    normalized = str(dependency_id or "").strip().lower()
    if not normalized:
        return None
    return next((row for row in list_dependency_entries(_fs) if str(row.get("id", "")).strip().lower() == normalized), None)


def _find_revoke_approval(dependency_id: str) -> dict[str, Any] | None:
    normalized = str(dependency_id or "").strip().lower()
    for row in reversed(list_requests(_fs, action="dependencies.revoke", limit=100)):
        if not isinstance(row, dict):
            continue
        metadata = row.get("metadata", {}) if isinstance(row.get("metadata"), dict) else {}
        if str(metadata.get("dependency_id", "")).strip().lower() == normalized:
            return row
    return None


def _dependency_presentation(dependency: dict[str, Any]) -> dict[str, Any]:
    provenance = build_dependency_provenance(dependency)
    status = str(dependency.get("status", "declared")).strip().lower() or "declared"
    summary = (
        f"{str(dependency.get('name', 'dependency')).strip() or 'dependency'} is {status}. "
        f"{str(provenance.get('summary', '')).strip()}"
    ).strip()
    return {
        "kind": "dependencies.lifecycle",
        "summary": summary,
        "severity": (
            "high"
            if status in {"quarantined", "revoked"} or not bool(provenance.get("pinned")) or bool(provenance.get("review_required"))
            else "low"
        ),
        "cards": [
            {"label": "Status", "value": status, "tone": "high" if status in {"quarantined", "revoked"} else "low"},
            {"label": "Ecosystem", "value": str(dependency.get("ecosystem", "python")).strip(), "tone": "low"},
            {"label": "Section", "value": str(dependency.get("section", "runtime")).strip(), "tone": "medium"},
            {
                "label": "Provenance",
                "value": str(provenance.get("label", "Third-Party")).strip() or "Third-Party",
                "tone": str(provenance.get("tone", "low")).strip() or "low",
            },
            {
                "label": "Pinning",
                "value": str(provenance.get("locked_version") or dependency.get("requirement") or "unlocked"),
                "tone": "low" if bool(provenance.get("pinned")) else "high",
            },
        ],
        "detail": {
            "dependency_id": str(dependency.get("id", "")).strip(),
            "status": status,
            "provenance": provenance,
        },
    }


@router.get("/dependencies/library")
def dependency_library(request: Request) -> dict[str, Any]:
    _enforce_control("dependencies.read", mutating=False)
    _enforce_rbac(request, "dependencies.read")
    entries = list_dependency_entries(_fs)
    library = build_dependency_library(entries)
    return {
        "status": "ok",
        "surface": "dependency_library",
        "summary": (
            f"{library['dependency_count']} dependency row(s), {library['runtime_count']} runtime, "
            f"{library['quarantined_count']} quarantined, {library['revoked_count']} revoked."
            if library["dependency_count"]
            else "No dependency rows are cataloged yet."
        ),
        "library": library,
        "entries": entries,
    }


@router.post("/dependencies/{dependency_id}/quarantine")
def dependency_quarantine(dependency_id: str, request: Request, payload: DependencyLifecycleRequest) -> dict[str, Any]:
    _enforce_control("dependencies.quarantine", mutating=True)
    role = _enforce_rbac(request, "dependencies.quarantine")
    run_id = str(getattr(request.state, "run_id", uuid4()))
    dependency = quarantine_dependency(
        _fs,
        dependency_id,
        reason=payload.reason,
        actor=f"dependencies:{role}",
    )
    if dependency is None:
        raise HTTPException(status_code=404, detail=f"Dependency not found: {dependency_id}")
    _ledger.append(
        run_id=run_id,
        kind="dependencies.quarantine",
        summary={
            "dependency_id": str(dependency.get("id", "")).strip(),
            "status": str(dependency.get("status", "")).strip(),
            "reason": str(dependency.get("quarantine_reason", "")).strip(),
        },
    )
    return {
        "status": "ok",
        "run_id": run_id,
        "dependency": dependency,
        "presentation": _dependency_presentation(dependency),
    }


@router.post("/dependencies/{dependency_id}/revoke/request-approval")
def dependency_request_revoke_approval(
    dependency_id: str,
    request: Request,
    payload: DependencyLifecycleRequest,
) -> dict[str, Any]:
    _enforce_control("approvals.request", mutating=False)
    role = _enforce_rbac(request, "approvals.request")
    dependency = _find_dependency(dependency_id)
    if dependency is None:
        raise HTTPException(status_code=404, detail=f"Dependency not found: {dependency_id}")
    run_id = str(getattr(request.state, "run_id", uuid4()))
    existing = _find_revoke_approval(dependency_id)
    if existing is None:
        approval = create_request(
            _fs,
            run_id=run_id,
            action="dependencies.revoke",
            reason=str(payload.reason).strip() or f"Revoke dependency {dependency_id}",
            requested_by=role,
            metadata={
                "dependency_id": dependency_id,
                "action_kind": "dependencies.revoke",
                "source": "dependencies.library",
            },
        )
    else:
        approval = existing
    _ledger.append(
        run_id=run_id,
        kind="dependencies.revoke.request_approval",
        summary={
            "dependency_id": dependency_id,
            "approval_id": str(approval.get("id", "")).strip(),
            "status": str(approval.get("status", "")).strip().lower() or "pending",
        },
    )
    return {"status": "ok", "run_id": run_id, "approval": approval, "dependency": dependency}


@router.post("/dependencies/{dependency_id}/revoke")
def dependency_revoke(dependency_id: str, request: Request, payload: DependencyRevokeRequest) -> dict[str, Any]:
    _enforce_control("dependencies.revoke", mutating=True)
    role = _enforce_rbac(request, "dependencies.revoke")
    dependency = _find_dependency(dependency_id)
    if dependency is None:
        raise HTTPException(status_code=404, detail=f"Dependency not found: {dependency_id}")
    run_id = str(getattr(request.state, "run_id", uuid4()))
    approved, approval_detail = ensure_action_approved(
        _fs,
        run_id=run_id,
        action="dependencies.revoke",
        requested_by=role,
        reason=str(payload.reason).strip() or f"Revoke dependency {dependency_id}",
        approval_id=str(payload.approval_id or "").strip() or None,
        metadata={
            "dependency_id": dependency_id,
            "action_kind": "dependencies.revoke",
            "source": "dependencies.library",
        },
    )
    if not approved:
        raise HTTPException(
            status_code=403,
            detail={
                "message": "Action requires approval: dependencies.revoke",
                "approval": approval_detail,
            },
        )
    updated = revoke_dependency(
        _fs,
        dependency_id,
        reason=payload.reason,
        actor=f"dependencies:{role}",
    )
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Dependency not found: {dependency_id}")
    approval_id = str(
        payload.approval_id
        or approval_detail.get("approval_request_id")
        or (approval_detail.get("request", {}) if isinstance(approval_detail.get("request"), dict) else {}).get("id")
        or ""
    ).strip()
    _ledger.append(
        run_id=run_id,
        kind="dependencies.revoke",
        summary={
            "dependency_id": str(updated.get("id", "")).strip(),
            "status": str(updated.get("status", "")).strip(),
            "approval_id": approval_id,
            "reason": str(updated.get("revocation_reason", "")).strip(),
        },
    )
    return {
        "status": "ok",
        "run_id": run_id,
        "dependency": updated,
        "approval_id": approval_id,
        "presentation": _dependency_presentation(updated),
    }
