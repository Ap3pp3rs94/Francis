from __future__ import annotations

from collections import Counter
from typing import Any
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from francis_core.config import settings
from francis_core.workspace_fs import WorkspaceFS
from francis_policy.rbac import can
from services.orchestrator.app.approvals_store import ensure_action_approved
from services.orchestrator.app.autonomy.event_queue import (
    complete_event,
    enqueue_event,
    fail_event,
    lease_due_events,
    preview_due_events,
    queue_status,
    read_last_dispatch,
    write_last_dispatch,
)
from services.orchestrator.app.autonomy.event_reactor import collect_events
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


class AutonomyCollectRequest(BaseModel):
    max_events: int = Field(default=20, ge=1, le=100)
    include_types: list[str] | None = None


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


def _risk_tier_rank(value: str | None) -> int:
    risk = str(value or "").strip().lower()
    if risk == "critical":
        return 4
    if risk == "high":
        return 3
    if risk == "medium":
        return 2
    return 1


def _max_risk_tier(events: list[dict[str, Any]]) -> str:
    if not events:
        return "low"
    tiers = [str(item.get("risk_tier", "low")).strip().lower() for item in events]
    return max(tiers, key=_risk_tier_rank)


def _event_signal_policy(event_type: str) -> tuple[str, str]:
    normalized = str(event_type).strip().lower()
    if normalized in {"incident.critical_open", "telemetry.critical_present"}:
        return ("critical", "high")
    if normalized in {
        "telemetry.errors_present",
        "queue.deadletter_present",
        "worker.queue_due",
        "worker.lease_expired",
        "mission.jobs_queued",
    }:
        return ("high", "medium")
    if normalized in {"observer.scan_due", "inbox.alerts_present", "worker.queue_backoff"}:
        return ("normal", "low")
    return ("normal", "low")


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
    role = _role_from_request(request)
    _enforce_rbac(request, "autonomy.dispatch")
    _enforce_control("autonomy.dispatch", mutating=True)
    approval_id = request.headers.get("x-approval-id", "").strip() or None
    due_preview = preview_due_events(_fs, max_events=body.max_events)
    due_count = len(due_preview)
    max_risk = _max_risk_tier(due_preview)
    risk_counts = Counter(str(item.get("risk_tier", "low")).strip().lower() for item in due_preview)
    approval_required = _risk_tier_rank(max_risk) >= _risk_tier_rank("high")
    approved, approval_detail = ensure_action_approved(
        _fs,
        run_id=run_id,
        action="autonomy.dispatch.high_risk",
        requested_by=role,
        reason=(
            "Autonomy event dispatch includes high-risk events: "
            f"max_risk={max_risk}, due_count={due_count}, risk_counts={dict(risk_counts)}"
        ),
        approval_required=approval_required,
        approval_id=approval_id,
        metadata={
            "max_risk": max_risk,
            "due_count": due_count,
            "risk_counts": dict(risk_counts),
        },
    )
    if not approved:
        raise HTTPException(
            status_code=403,
            detail={
                "message": "Autonomy dispatch requires approval for queued high-risk events.",
                "action": "autonomy.dispatch.high_risk",
                **approval_detail,
            },
        )
    approved_request_id = str(approval_detail.get("approval_request_id", "")).strip() or None

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
        "approval_id": approved_request_id,
        "max_risk_tier": max_risk,
        "due_preview_count": due_count,
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


@router.post("/autonomy/events/collect")
def autonomy_collect_events(request: Request, payload: AutonomyCollectRequest | None = None) -> dict:
    body = payload or AutonomyCollectRequest()
    run_id = str(getattr(request.state, "run_id", uuid4()))
    _enforce_rbac(request, "autonomy.enqueue")
    _enforce_control("autonomy.enqueue", mutating=True)

    include_types = {
        str(item).strip().lower()
        for item in (body.include_types or [])
        if isinstance(item, str) and str(item).strip()
    }
    snapshot = collect_events(_fs)
    raw_events = snapshot.get("events", []) if isinstance(snapshot, dict) else []
    event_signals = [item for item in raw_events if isinstance(item, dict) and str(item.get("type", "")).strip()]
    if include_types:
        event_signals = [item for item in event_signals if str(item.get("type", "")).strip().lower() in include_types]
    event_signals = event_signals[: body.max_events]

    queued: list[dict[str, Any]] = []
    duplicates: list[dict[str, Any]] = []
    for signal in event_signals:
        event_type = str(signal.get("type", "")).strip().lower()
        priority, risk_tier = _event_signal_policy(event_type)
        dedupe_key = f"reactor:{event_type}:{str(signal.get('count', signal.get('reason', '1')))}"
        result = enqueue_event(
            _fs,
            run_id=run_id,
            event_type=event_type,
            source="event_reactor",
            priority=priority,
            risk_tier=risk_tier,
            payload=signal,
            dedupe_key=dedupe_key,
        )
        if str(result.get("status", "")).strip().lower() == "duplicate":
            duplicates.append(result.get("event", {}))
        elif str(result.get("status", "")).strip().lower() == "ok":
            queued.append(result.get("event", {}))

    return {
        "status": "ok",
        "run_id": run_id,
        "seen_count": len(event_signals),
        "queued_count": len(queued),
        "duplicate_count": len(duplicates),
        "queued": queued,
        "duplicates": duplicates,
        "queue": queue_status(_fs, limit=100),
    }
