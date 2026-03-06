from __future__ import annotations

from typing import Any
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from francis_core.config import settings
from francis_core.workspace_fs import WorkspaceFS
from francis_policy.rbac import can
from services.orchestrator.app.autonomy.event_queue import (
    complete_event,
    enqueue_event,
    fail_event,
    lease_due_events,
    queue_status,
    read_last_dispatch,
    write_last_dispatch,
)
from services.orchestrator.app.autonomy.kernel import run_cycle
from services.orchestrator.app.control_state import check_action_allowed

router = APIRouter(tags=["autonomy"])

_workspace_root = Path(settings.workspace_root).resolve()
_repo_root = _workspace_root.parent
_fs = WorkspaceFS(
    roots=[_workspace_root],
    journal_path=(_workspace_root / "journals" / "fs.jsonl").resolve(),
)


class AutonomyCycleRequest(BaseModel):
    max_actions: int = Field(default=2, ge=0, le=10)
    max_runtime_seconds: int = Field(default=10, ge=1, le=120)
    allow_medium: bool = False
    allow_high: bool = False
    stop_on_critical: bool = True


class AutonomyEventEnqueueRequest(BaseModel):
    event_type: str = Field(min_length=1)
    source: str | None = None
    priority: str | None = None
    payload: dict[str, Any] | None = None
    dedupe_key: str | None = None
    next_run_after: str | None = None


class AutonomyDispatchRequest(BaseModel):
    max_events: int = Field(default=5, ge=1, le=100)
    max_actions: int = Field(default=2, ge=0, le=10)
    max_runtime_seconds: int = Field(default=10, ge=1, le=120)
    allow_medium: bool = False
    allow_high: bool = False
    stop_on_critical: bool = True


def _role_from_request(request: Request) -> str:
    return request.headers.get("x-francis-role", "architect").strip().lower()


def _enforce_rbac(request: Request, action: str) -> None:
    role = _role_from_request(request)
    if not can(role, action):
        raise HTTPException(status_code=403, detail=f"RBAC denied: role={role}, action={action}")


def _enforce_control(action: str, *, mutating: bool) -> None:
    allowed, reason, _state = check_action_allowed(
        _fs,
        repo_root=_repo_root,
        workspace_root=_workspace_root,
        app="autonomy",
        action=action,
        mutating=mutating,
    )
    if not allowed:
        raise HTTPException(status_code=403, detail=f"Control denied: {reason}")


@router.post("/autonomy/cycle")
def autonomy_cycle(request: Request, payload: AutonomyCycleRequest | None = None) -> dict:
    body = payload or AutonomyCycleRequest()
    run_id = str(getattr(request.state, "run_id", uuid4()))
    _enforce_rbac(request, "autonomy.cycle")
    _enforce_control("autonomy.cycle", mutating=True)
    return run_cycle(
        run_id=run_id,
        workspace_root=_workspace_root,
        repo_root=_repo_root,
        max_actions=body.max_actions,
        max_runtime_seconds=body.max_runtime_seconds,
        allow_medium=body.allow_medium,
        allow_high=body.allow_high,
        stop_on_critical=body.stop_on_critical,
    )


@router.post("/autonomy/events")
def autonomy_enqueue_event(request: Request, payload: AutonomyEventEnqueueRequest) -> dict:
    run_id = str(getattr(request.state, "run_id", uuid4()))
    _enforce_rbac(request, "autonomy.enqueue")
    _enforce_control("autonomy.enqueue", mutating=True)
    result = enqueue_event(
        _fs,
        run_id=run_id,
        event_type=payload.event_type,
        source=payload.source,
        priority=payload.priority,
        payload=payload.payload,
        dedupe_key=payload.dedupe_key,
        next_run_after=payload.next_run_after,
    )
    return {"status": "ok", "run_id": run_id, **result}


@router.get("/autonomy/events/queue")
def autonomy_queue_status(request: Request, limit: int = 100) -> dict:
    _enforce_rbac(request, "autonomy.read")
    _enforce_control("autonomy.read", mutating=False)
    return {
        "status": "ok",
        "queue": queue_status(_fs, limit=max(0, min(limit, 500))),
        "last_dispatch": read_last_dispatch(_fs),
    }


@router.post("/autonomy/events/dispatch")
def autonomy_dispatch_events(request: Request, payload: AutonomyDispatchRequest | None = None) -> dict:
    body = payload or AutonomyDispatchRequest()
    run_id = str(getattr(request.state, "run_id", uuid4()))
    _enforce_rbac(request, "autonomy.dispatch")
    _enforce_control("autonomy.dispatch", mutating=True)

    leased = lease_due_events(
        _fs,
        max_events=body.max_events,
        lease_owner=f"autonomy.dispatch:{run_id}",
    )
    processed: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []

    for event in leased:
        event_id = str(event.get("id", ""))
        dispatch_run_id = f"{run_id}:event:{event_id}"
        try:
            cycle = run_cycle(
                run_id=dispatch_run_id,
                workspace_root=_workspace_root,
                repo_root=_repo_root,
                max_actions=body.max_actions,
                max_runtime_seconds=body.max_runtime_seconds,
                allow_medium=body.allow_medium,
                allow_high=body.allow_high,
                stop_on_critical=body.stop_on_critical,
            )
            completed = complete_event(
                _fs,
                event_id=event_id,
                dispatch_run_id=dispatch_run_id,
                result={
                    "halted_reason": cycle.get("halted_reason"),
                    "executed_count": len(cycle.get("executed_actions", [])),
                    "blocked_count": len(cycle.get("blocked_actions", [])),
                },
            )
            processed.append(
                {
                    "event": completed if isinstance(completed, dict) else event,
                    "cycle": {
                        "run_id": cycle.get("run_id"),
                        "halted_reason": cycle.get("halted_reason"),
                        "executed_count": len(cycle.get("executed_actions", [])),
                        "blocked_count": len(cycle.get("blocked_actions", [])),
                    },
                }
            )
        except Exception as exc:
            failed_event = fail_event(
                _fs,
                event_id=event_id,
                dispatch_run_id=dispatch_run_id,
                error=str(exc),
            )
            failed.append({"event": failed_event if isinstance(failed_event, dict) else event, "error": str(exc)})

    dispatch_summary = {
        "status": "ok",
        "run_id": run_id,
        "leased_count": len(leased),
        "processed_count": len(processed),
        "failed_count": len(failed),
        "processed": processed,
        "failed": failed,
        "config": {
            "max_events": body.max_events,
            "max_actions": body.max_actions,
            "max_runtime_seconds": body.max_runtime_seconds,
            "allow_medium": body.allow_medium,
            "allow_high": body.allow_high,
            "stop_on_critical": body.stop_on_critical,
        },
    }
    write_last_dispatch(_fs, payload=dispatch_summary)
    dispatch_summary["queue"] = queue_status(_fs, limit=100)
    return dispatch_summary
