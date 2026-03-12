from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from francis_brain.ledger import RunLedger
from francis_core.clock import utc_now_iso
from francis_core.config import settings
from francis_core.workspace_fs import WorkspaceFS
from francis_policy.rbac import can
from services.orchestrator.app.control_state import check_action_allowed
from services.orchestrator.app.swarm_store import (
    DEFAULT_LEASE_TTL_SECONDS,
    DEFAULT_RETRY_BACKOFF_SECONDS,
    build_swarm_state,
    complete_delegation,
    delegate_work,
    fail_delegation,
    lease_delegation,
)

router = APIRouter(tags=["swarm"])

_workspace_root = Path(settings.workspace_root).resolve()
_repo_root = _workspace_root.parent
_fs = WorkspaceFS(
    roots=[_workspace_root],
    journal_path=(_workspace_root / "journals" / "fs.jsonl").resolve(),
)
_ledger = RunLedger(_fs, rel_path="runs/run_ledger.jsonl")


class SwarmDelegateRequest(BaseModel):
    target_unit_id: str = Field(min_length=1, max_length=80)
    action_kind: str = Field(min_length=1, max_length=120)
    summary: str = Field(min_length=1, max_length=240)
    handoff_note: str = ""
    source_unit_id: str = Field(default="coordinator", min_length=1, max_length=80)
    scope_apps: list[str] = Field(default_factory=list)
    mission_id: str | None = None
    approval_id: str | None = None
    max_attempts: int = Field(default=2, ge=1, le=5)


class SwarmLeaseRequest(BaseModel):
    unit_id: str = Field(min_length=1, max_length=80)
    lease_owner: str = Field(default="", max_length=120)
    lease_ttl_seconds: int = Field(default=DEFAULT_LEASE_TTL_SECONDS, ge=15, le=3600)


class SwarmCompleteRequest(BaseModel):
    unit_id: str = Field(min_length=1, max_length=80)
    result_summary: str = Field(min_length=1, max_length=240)


class SwarmFailRequest(BaseModel):
    unit_id: str = Field(min_length=1, max_length=80)
    error: str = Field(min_length=1, max_length=240)
    retryable: bool = True
    retry_backoff_seconds: int = Field(default=DEFAULT_RETRY_BACKOFF_SECONDS, ge=0, le=3600)


def _append_jsonl(rel_path: str, row: dict[str, Any]) -> None:
    try:
        raw = _fs.read_text(rel_path)
    except Exception:
        raw = ""
    if raw and not raw.endswith("\n"):
        raw += "\n"
    _fs.write_text(rel_path, raw + json.dumps(row, ensure_ascii=False) + "\n")


def _role_from_request(request: Request) -> str:
    return request.headers.get("x-francis-role", "architect").strip().lower()


def _enforce_rbac(request: Request, action: str) -> str:
    role = _role_from_request(request)
    if not can(role, action):
        raise HTTPException(status_code=403, detail=f"RBAC denied: role={role}, action={action}")
    return role


def _enforce_control(action: str, *, mutating: bool = False) -> dict[str, Any]:
    allowed, reason, state = check_action_allowed(
        _fs,
        repo_root=_repo_root,
        workspace_root=_workspace_root,
        app="swarm",
        action=action,
        mutating=mutating,
    )
    if not allowed:
        raise HTTPException(status_code=403, detail=f"Control denied: {reason}")
    return state


def _build_state_payload() -> dict[str, Any]:
    state = build_swarm_state(_fs, repo_root=_repo_root, workspace_root=_workspace_root)
    return {
        "status": "ok",
        "summary": state["summary"],
        "units": state["units"],
        "delegations": state["delegations"],
        "deadletter": state["deadletter"],
        "counts": {
            "units": state["unit_count"],
            "queued": state["queued_count"],
            "active": state["leased_count"],
            "completed": state["completed_count"],
            "deadletter": state["deadletter_count"],
        },
        "updated_at": state["updated_at"],
    }


def _record_swarm_receipt(
    *,
    run_id: str,
    trace_id: str,
    kind: str,
    actor: str,
    delegation: dict[str, Any],
    summary: dict[str, Any],
) -> dict[str, Any]:
    receipt = {
        "id": str(uuid4()),
        "ts": utc_now_iso(),
        "run_id": run_id,
        "trace_id": trace_id,
        "kind": kind,
        "actor": actor,
        "delegation_id": str(delegation.get("id", "")).strip(),
        "source_unit_id": str(delegation.get("source_unit_id", "")).strip(),
        "target_unit_id": str(delegation.get("target_unit_id", "")).strip(),
        "action_kind": str(delegation.get("action_kind", "")).strip(),
        "summary": summary,
    }
    _append_jsonl("logs/francis.log.jsonl", receipt)
    _append_jsonl("journals/decisions.jsonl", receipt)
    _ledger.append(
        run_id=run_id,
        kind=kind,
        summary={
            "trace_id": trace_id,
            "actor": actor,
            "delegation_id": str(delegation.get("id", "")).strip(),
            "source_unit_id": str(delegation.get("source_unit_id", "")).strip(),
            "target_unit_id": str(delegation.get("target_unit_id", "")).strip(),
            "action_kind": str(delegation.get("action_kind", "")).strip(),
            **summary,
        },
    )
    return receipt


@router.get("/swarm/state")
def swarm_state(request: Request) -> dict[str, Any]:
    _enforce_control("swarm.read")
    _enforce_rbac(request, "swarm.read")
    return _build_state_payload()


@router.post("/swarm/delegate")
def swarm_delegate(request: Request, payload: SwarmDelegateRequest) -> dict[str, Any]:
    control_state = _enforce_control("swarm.write", mutating=True)
    role = _enforce_rbac(request, "swarm.write")
    run_id = str(getattr(request.state, "run_id", uuid4()))
    trace_id = str(getattr(request.state, "trace_id", None) or run_id)
    scopes = control_state.get("scopes", {}) if isinstance(control_state.get("scopes"), dict) else {}
    scope_apps = payload.scope_apps or scopes.get("apps", [])
    delegation = delegate_work(
        _fs,
        repo_root=_repo_root,
        workspace_root=_workspace_root,
        run_id=run_id,
        trace_id=trace_id,
        source_unit_id=payload.source_unit_id,
        target_unit_id=payload.target_unit_id,
        action_kind=payload.action_kind,
        summary=payload.summary,
        handoff_note=payload.handoff_note,
        scope_apps=scope_apps if isinstance(scope_apps, list) else [],
        mission_id=payload.mission_id,
        approval_id=payload.approval_id,
        max_attempts=payload.max_attempts,
        authority_basis=f"mode={control_state.get('mode', 'unknown')} actor={role}",
    )
    state = _build_state_payload()
    _record_swarm_receipt(
        run_id=run_id,
        trace_id=trace_id,
        kind="swarm.delegation.created",
        actor=role,
        delegation=delegation,
        summary={
            "status": str(delegation.get("status", "")).strip(),
            "summary": str(delegation.get("summary", "")).strip(),
            "scope_apps": delegation.get("scope_apps", []),
        },
    )
    return {"status": "ok", "run_id": run_id, "trace_id": trace_id, "delegation": delegation, "swarm": state}


@router.post("/swarm/delegations/{delegation_id}/lease")
def swarm_lease(delegation_id: str, request: Request, payload: SwarmLeaseRequest) -> dict[str, Any]:
    _enforce_control("swarm.write", mutating=True)
    role = _enforce_rbac(request, "swarm.write")
    run_id = str(getattr(request.state, "run_id", uuid4()))
    trace_id = str(getattr(request.state, "trace_id", None) or run_id)
    try:
        delegation = lease_delegation(
            _fs,
            repo_root=_repo_root,
            workspace_root=_workspace_root,
            delegation_id=delegation_id,
            unit_id=payload.unit_id,
            lease_owner=payload.lease_owner.strip() or payload.unit_id.strip(),
            lease_ttl_seconds=payload.lease_ttl_seconds,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if delegation is None:
        raise HTTPException(status_code=404, detail=f"Delegation not found: {delegation_id}")
    state = _build_state_payload()
    _record_swarm_receipt(
        run_id=run_id,
        trace_id=trace_id,
        kind="swarm.delegation.leased",
        actor=role,
        delegation=delegation,
        summary={
            "status": str(delegation.get("status", "")).strip(),
            "lease_owner": str(delegation.get("lease_owner", "")).strip(),
        },
    )
    return {"status": "ok", "run_id": run_id, "trace_id": trace_id, "delegation": delegation, "swarm": state}


@router.post("/swarm/delegations/{delegation_id}/complete")
def swarm_complete(delegation_id: str, request: Request, payload: SwarmCompleteRequest) -> dict[str, Any]:
    _enforce_control("swarm.write", mutating=True)
    role = _enforce_rbac(request, "swarm.write")
    run_id = str(getattr(request.state, "run_id", uuid4()))
    trace_id = str(getattr(request.state, "trace_id", None) or run_id)
    try:
        delegation = complete_delegation(
            _fs,
            repo_root=_repo_root,
            workspace_root=_workspace_root,
            delegation_id=delegation_id,
            completed_by_unit_id=payload.unit_id,
            result_summary=payload.result_summary,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if delegation is None:
        raise HTTPException(status_code=404, detail=f"Delegation not found: {delegation_id}")
    state = _build_state_payload()
    _record_swarm_receipt(
        run_id=run_id,
        trace_id=trace_id,
        kind="swarm.delegation.completed",
        actor=role,
        delegation=delegation,
        summary={
            "status": str(delegation.get("status", "")).strip(),
            "result_summary": str(delegation.get("result_summary", "")).strip(),
        },
    )
    return {"status": "ok", "run_id": run_id, "trace_id": trace_id, "delegation": delegation, "swarm": state}


@router.post("/swarm/delegations/{delegation_id}/fail")
def swarm_fail(delegation_id: str, request: Request, payload: SwarmFailRequest) -> dict[str, Any]:
    _enforce_control("swarm.write", mutating=True)
    role = _enforce_rbac(request, "swarm.write")
    run_id = str(getattr(request.state, "run_id", uuid4()))
    trace_id = str(getattr(request.state, "trace_id", None) or run_id)
    try:
        delegation = fail_delegation(
            _fs,
            repo_root=_repo_root,
            workspace_root=_workspace_root,
            delegation_id=delegation_id,
            failed_by_unit_id=payload.unit_id,
            error=payload.error,
            retryable=payload.retryable,
            retry_backoff_seconds=payload.retry_backoff_seconds,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if delegation is None:
        raise HTTPException(status_code=404, detail=f"Delegation not found: {delegation_id}")
    state = _build_state_payload()
    receipt_kind = (
        "swarm.delegation.deadlettered"
        if str(delegation.get("status", "")).strip().lower() == "deadlettered"
        else "swarm.delegation.retried"
    )
    _record_swarm_receipt(
        run_id=run_id,
        trace_id=trace_id,
        kind=receipt_kind,
        actor=role,
        delegation=delegation,
        summary={
            "status": str(delegation.get("status", "")).strip(),
            "attempts": int(delegation.get("attempts", 0) or 0),
            "last_error": str(delegation.get("last_error", "")).strip(),
            "next_run_after": delegation.get("next_run_after"),
        },
    )
    return {"status": "ok", "run_id": run_id, "trace_id": trace_id, "delegation": delegation, "swarm": state}
