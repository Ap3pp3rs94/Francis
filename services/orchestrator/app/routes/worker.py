from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from francis_core.config import settings
from francis_core.workspace_fs import WorkspaceFS
from francis_policy.rbac import can
from services.orchestrator.app.control_state import check_action_allowed
from services.worker.app.main import get_worker_status, recover_stale_leased_jobs, run_worker_cycle

router = APIRouter(tags=["worker"])

_workspace_root = Path(settings.workspace_root).resolve()
_repo_root = _workspace_root.parent
_fs = WorkspaceFS(
    roots=[_workspace_root],
    journal_path=(_workspace_root / "journals" / "fs.jsonl").resolve(),
)


class WorkerCycleRequest(BaseModel):
    max_jobs: int = Field(default=20, ge=1, le=500)
    max_runtime_seconds: int = Field(default=60, ge=1, le=600)
    lease_ttl_seconds: int = Field(default=120, ge=5, le=600)
    lease_heartbeat_seconds: int = Field(default=15, ge=1, le=300)
    max_concurrent_cycles: int = Field(default=1, ge=1, le=32)
    action_allowlist: list[str] | None = None
    action_limits: dict[str, int] | None = None
    action_timeouts: dict[str, int] | None = None


class WorkerRecoverRequest(BaseModel):
    action_classes: list[str] | None = None


def _normalize_trace_id(trace_id: str | None, *, fallback_run_id: str) -> str:
    normalized = str(trace_id or "").strip()
    return normalized or fallback_run_id


def _role_from_request(request: Request) -> str:
    return request.headers.get("x-francis-role", "architect").strip().lower()


def _enforce_rbac(request: Request, action: str) -> None:
    role = _role_from_request(request)
    if not can(role, action):
        raise HTTPException(status_code=403, detail=f"RBAC denied: role={role}, action={action}")


@router.post("/worker/cycle")
def worker_cycle(request: Request, payload: WorkerCycleRequest | None = None) -> dict:
    body = payload or WorkerCycleRequest()
    run_id = str(getattr(request.state, "run_id", uuid4()))
    trace_id = _normalize_trace_id(getattr(request.state, "trace_id", None), fallback_run_id=run_id)
    _enforce_rbac(request, "worker.cycle")

    allowed, reason, _state = check_action_allowed(
        _fs,
        repo_root=_repo_root,
        workspace_root=_workspace_root,
        app="worker",
        action="worker.cycle",
        mutating=True,
    )
    if not allowed:
        raise HTTPException(status_code=403, detail=f"Control denied: {reason}")

    allowlist = {item.strip().lower() for item in (body.action_allowlist or []) if item.strip()}
    limits = {
        str(key).strip().lower(): int(value)
        for key, value in (body.action_limits or {}).items()
        if str(key).strip()
    }
    timeouts = {
        str(key).strip().lower(): int(value)
        for key, value in (body.action_timeouts or {}).items()
        if str(key).strip()
    }
    return run_worker_cycle(
        run_id=run_id,
        trace_id=trace_id,
        max_jobs=body.max_jobs,
        max_runtime_seconds=body.max_runtime_seconds,
        lease_ttl_seconds=body.lease_ttl_seconds,
        lease_heartbeat_seconds=body.lease_heartbeat_seconds,
        max_concurrent_cycles=body.max_concurrent_cycles,
        action_allowlist=allowlist if allowlist else None,
        action_limits=limits if limits else None,
        action_timeouts=timeouts if timeouts else None,
    )


@router.post("/worker/recover")
def worker_recover(request: Request, payload: WorkerRecoverRequest | None = None) -> dict:
    body = payload or WorkerRecoverRequest()
    run_id = str(getattr(request.state, "run_id", uuid4()))
    trace_id = _normalize_trace_id(getattr(request.state, "trace_id", None), fallback_run_id=run_id)
    _enforce_rbac(request, "worker.cycle")
    allowed, reason, _state = check_action_allowed(
        _fs,
        repo_root=_repo_root,
        workspace_root=_workspace_root,
        app="worker",
        action="worker.recover",
        mutating=True,
    )
    if not allowed:
        raise HTTPException(status_code=403, detail=f"Control denied: {reason}")
    classes = {str(item).strip().lower() for item in (body.action_classes or []) if str(item).strip()}
    return recover_stale_leased_jobs(
        run_id=run_id,
        trace_id=trace_id,
        action_classes=classes if classes else None,
    )


@router.get("/worker/status")
def worker_status(request: Request) -> dict:
    _enforce_rbac(request, "worker.read")
    allowed, reason, _state = check_action_allowed(
        _fs,
        repo_root=_repo_root,
        workspace_root=_workspace_root,
        app="worker",
        action="worker.status",
        mutating=False,
    )
    if not allowed:
        raise HTTPException(status_code=403, detail=f"Control denied: {reason}")
    return get_worker_status()
