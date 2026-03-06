from __future__ import annotations

from collections import Counter
import time
from typing import Any
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from francis_core.clock import utc_now_iso
from francis_core.config import settings
from francis_core.workspace_fs import WorkspaceFS
from francis_policy.rbac import can
from services.orchestrator.app.approvals_store import ensure_action_approved
from services.orchestrator.app.autonomy.event_queue import (
    append_tick_history,
    append_dispatch_history,
    complete_event,
    default_reactor_guardrail_state,
    enqueue_event,
    fail_event,
    lease_due_events,
    preview_due_events,
    queue_status,
    read_reactor_guardrail_state,
    read_last_tick,
    read_tick_history,
    read_dispatch_history,
    read_last_dispatch,
    release_leased_events,
    recover_stale_leased_events,
    write_reactor_guardrail_state,
    write_last_tick,
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
    max_dispatch_actions: int = Field(default=10, ge=0, le=200)
    max_dispatch_runtime_seconds: int = Field(default=30, ge=1, le=600)
    max_attempts: int = Field(default=3, ge=1, le=20)
    retry_backoff_seconds: int = Field(default=60, ge=0, le=3600)
    lease_ttl_seconds: int = Field(default=300, ge=15, le=3600)
    recover_stale_leases: bool = True
    allow_medium: bool = False
    allow_high: bool = False
    stop_on_critical: bool = True


class AutonomyCollectRequest(BaseModel):
    max_events: int = Field(default=20, ge=1, le=100)
    include_types: list[str] | None = None


class AutonomyRecoverRequest(BaseModel):
    max_recover: int = Field(default=100, ge=1, le=1000)
    lease_ttl_seconds: int = Field(default=300, ge=15, le=3600)


class AutonomyReactorTickRequest(BaseModel):
    max_collect_events: int = Field(default=20, ge=1, le=100)
    include_types: list[str] | None = None
    max_events: int = Field(default=5, ge=1, le=100)
    max_actions: int = Field(default=2, ge=0, le=10)
    max_runtime_seconds: int = Field(default=10, ge=1, le=120)
    max_dispatch_actions: int = Field(default=10, ge=0, le=200)
    max_dispatch_runtime_seconds: int = Field(default=30, ge=1, le=600)
    max_attempts: int = Field(default=3, ge=1, le=20)
    retry_backoff_seconds: int = Field(default=60, ge=0, le=3600)
    retry_pressure_threshold: int = Field(default=5, ge=0, le=500)
    retry_pressure_consecutive_ticks: int = Field(default=3, ge=1, le=50)
    retry_pressure_cooldown_ticks: int = Field(default=2, ge=1, le=50)
    lease_ttl_seconds: int = Field(default=300, ge=15, le=3600)
    recover_stale_leases: bool = True
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


@router.get("/autonomy/events/history")
def autonomy_dispatch_history(request: Request, limit: int = 50) -> dict:
    _enforce_rbac(request, "autonomy.read")
    _enforce_control("autonomy.read", mutating=False)
    history = read_dispatch_history(_fs, limit=limit)
    return {"status": "ok", "count": len(history), "history": history}


@router.get("/autonomy/reactor/last")
def autonomy_reactor_last(request: Request) -> dict:
    _enforce_rbac(request, "autonomy.read")
    _enforce_control("autonomy.read", mutating=False)
    return {"status": "ok", "last_tick": read_last_tick(_fs)}


@router.get("/autonomy/reactor/history")
def autonomy_reactor_history(request: Request, limit: int = 50) -> dict:
    _enforce_rbac(request, "autonomy.read")
    _enforce_control("autonomy.read", mutating=False)
    history = read_tick_history(_fs, limit=limit)
    return {"status": "ok", "count": len(history), "history": history}


@router.get("/autonomy/reactor/guardrail")
def autonomy_reactor_guardrail(request: Request) -> dict:
    _enforce_rbac(request, "autonomy.read")
    _enforce_control("autonomy.read", mutating=False)
    return {"status": "ok", "guardrail": read_reactor_guardrail_state(_fs)}


@router.post("/autonomy/events/dispatch")
def autonomy_dispatch_events(request: Request, payload: AutonomyDispatchRequest | None = None) -> dict:
    body = payload or AutonomyDispatchRequest()
    run_id = str(getattr(request.state, "run_id", uuid4()))
    role = _role_from_request(request)
    dispatch_started = time.monotonic()
    _enforce_rbac(request, "autonomy.dispatch")
    _enforce_control("autonomy.dispatch", mutating=True)
    recovery: dict[str, Any] = {
        "status": "skipped",
        "run_id": run_id,
        "checked_count": 0,
        "recovered_count": 0,
        "lease_ttl_seconds": body.lease_ttl_seconds,
        "recovered": [],
    }
    if body.recover_stale_leases:
        recovery = recover_stale_leased_events(
            _fs,
            run_id=f"{run_id}:recover",
            lease_ttl_seconds=body.lease_ttl_seconds,
            max_recover=max(1, body.max_events * 5),
        )
    approval_id = request.headers.get("x-approval-id", "").strip() or None
    due_preview = preview_due_events(_fs, max_events=body.max_events)
    due_count = len(due_preview)
    max_risk = _max_risk_tier(due_preview)
    risk_counts = Counter(str(item.get("risk_tier", "low")).strip().lower() for item in due_preview)
    critical_incident_count = 0
    if body.stop_on_critical:
        event_state = collect_events(_fs)
        critical_incident_count = int(event_state.get("critical_incident_count", 0))

    approval_required = _risk_tier_rank(max_risk) >= _risk_tier_rank("high")
    approved_request_id: str | None = None
    if not (body.stop_on_critical and critical_incident_count > 0):
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

    halted_reason = "completed"
    leased: list[dict[str, Any]] = []
    processed: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    retried: list[dict[str, Any]] = []
    released: list[dict[str, Any]] = []
    handled_event_ids: set[str] = set()
    dispatch_executed_actions = 0

    if body.stop_on_critical and critical_incident_count > 0:
        halted_reason = "critical_incident_present"
    else:
        leased = lease_due_events(
            _fs,
            max_events=body.max_events,
            lease_owner=f"autonomy.dispatch:{run_id}",
            lease_ttl_seconds=body.lease_ttl_seconds,
        )

        for index, event in enumerate(leased):
            elapsed = time.monotonic() - dispatch_started
            if elapsed >= body.max_dispatch_runtime_seconds:
                halted_reason = "dispatch_runtime_budget_exceeded"
                break

            remaining_actions = max(0, body.max_dispatch_actions - dispatch_executed_actions)
            if remaining_actions <= 0:
                halted_reason = "dispatch_action_budget_exceeded"
                break

            event_id = str(event.get("id", ""))
            dispatch_run_id = f"{run_id}:event:{event_id}"
            cycle_max_actions = min(body.max_actions, remaining_actions)
            try:
                cycle = run_cycle(
                    run_id=dispatch_run_id,
                    workspace_root=_workspace_root,
                    repo_root=_repo_root,
                    max_actions=cycle_max_actions,
                    max_runtime_seconds=body.max_runtime_seconds,
                    allow_medium=body.allow_medium,
                    allow_high=body.allow_high,
                    stop_on_critical=body.stop_on_critical,
                )
                executed_count = len(cycle.get("executed_actions", []))
                dispatch_executed_actions += executed_count

                completed = complete_event(
                    _fs,
                    event_id=event_id,
                    dispatch_run_id=dispatch_run_id,
                    result={
                        "halted_reason": cycle.get("halted_reason"),
                        "executed_count": executed_count,
                        "blocked_count": len(cycle.get("blocked_actions", [])),
                    },
                )
                handled_event_ids.add(event_id)
                processed.append(
                    {
                        "event": completed if isinstance(completed, dict) else event,
                        "cycle": {
                            "run_id": cycle.get("run_id"),
                            "halted_reason": cycle.get("halted_reason"),
                            "executed_count": executed_count,
                            "blocked_count": len(cycle.get("blocked_actions", [])),
                        },
                    }
                )

                cycle_state = cycle.get("event_state", {})
                cycle_critical_incidents = (
                    int(cycle_state.get("critical_incident_count", 0))
                    if isinstance(cycle_state, dict)
                    else 0
                )
                if body.stop_on_critical and (
                    str(cycle.get("halted_reason", "")) == "critical_anomaly" or cycle_critical_incidents > 0
                ):
                    halted_reason = "critical_anomaly"
                    break

                remaining_events = len(leased) - (index + 1)
                if remaining_events > 0 and dispatch_executed_actions >= body.max_dispatch_actions:
                    halted_reason = "dispatch_action_budget_exceeded"
                    break
            except Exception as exc:
                failed_event = fail_event(
                    _fs,
                    event_id=event_id,
                    dispatch_run_id=dispatch_run_id,
                    error=str(exc),
                    max_attempts=body.max_attempts,
                    retry_backoff_seconds=body.retry_backoff_seconds,
                )
                handled_event_ids.add(event_id)
                event_row = failed_event if isinstance(failed_event, dict) else event
                failed_status = str(event_row.get("status", "")).strip().lower()
                if failed_status == "queued":
                    retried.append({"event": event_row, "error": str(exc)})
                else:
                    failed.append({"event": event_row, "error": str(exc)})

        remaining_ids = [
            str(item.get("id", "")).strip()
            for item in leased
            if str(item.get("id", "")).strip() and str(item.get("id", "")).strip() not in handled_event_ids
        ]
        if remaining_ids:
            released = release_leased_events(
                _fs,
                run_id=run_id,
                event_ids=remaining_ids,
                reason=halted_reason if halted_reason != "completed" else "dispatch_partial",
            )

    dispatch_summary = {
        "status": "ok",
        "run_id": run_id,
        "leased_count": len(leased),
        "recovered_count": int(recovery.get("recovered_count", 0)),
        "processed_count": len(processed),
        "failed_count": len(failed),
        "retried_count": len(retried),
        "released_count": len(released),
        "dispatch_executed_actions": dispatch_executed_actions,
        "critical_incident_count": critical_incident_count,
        "halted_reason": halted_reason,
        "approval_id": approved_request_id,
        "approval_required": approval_required,
        "max_risk_tier": max_risk,
        "due_preview_count": due_count,
        "recovery": recovery,
        "processed": processed,
        "failed": failed,
        "retried": retried,
        "released": released,
        "config": {
            "max_events": body.max_events,
            "max_actions": body.max_actions,
            "max_runtime_seconds": body.max_runtime_seconds,
            "max_dispatch_actions": body.max_dispatch_actions,
            "max_dispatch_runtime_seconds": body.max_dispatch_runtime_seconds,
            "max_attempts": body.max_attempts,
            "retry_backoff_seconds": body.retry_backoff_seconds,
            "lease_ttl_seconds": body.lease_ttl_seconds,
            "recover_stale_leases": body.recover_stale_leases,
            "allow_medium": body.allow_medium,
            "allow_high": body.allow_high,
            "stop_on_critical": body.stop_on_critical,
        },
    }
    write_last_dispatch(_fs, payload=dispatch_summary)
    append_dispatch_history(
        _fs,
        payload={
            "id": str(uuid4()),
            "ts": utc_now_iso(),
            "run_id": run_id,
            "kind": "autonomy.dispatch",
            "leased_count": len(leased),
            "recovered_count": int(recovery.get("recovered_count", 0)),
            "processed_count": len(processed),
            "failed_count": len(failed),
            "retried_count": len(retried),
            "released_count": len(released),
            "dispatch_executed_actions": dispatch_executed_actions,
            "halted_reason": halted_reason,
            "approval_id": approved_request_id,
            "max_risk_tier": max_risk,
            "due_preview_count": due_count,
            "config": dispatch_summary.get("config", {}),
        },
    )
    dispatch_summary["queue"] = queue_status(_fs, limit=100)
    return dispatch_summary


@router.post("/autonomy/reactor/tick")
def autonomy_reactor_tick(request: Request, payload: AutonomyReactorTickRequest | None = None) -> dict:
    body = payload or AutonomyReactorTickRequest()
    run_id = str(getattr(request.state, "run_id", uuid4()))
    queue_before = queue_status(_fs, limit=100)
    retry_pressure_count_before = int(queue_before.get("queued_retry_count", 0))
    guardrail_before = read_reactor_guardrail_state(_fs)
    guardrail_state = {**default_reactor_guardrail_state(), **guardrail_before}
    guardrail_state["tick_count"] = int(guardrail_state.get("tick_count", 0)) + 1

    threshold = max(0, int(body.retry_pressure_threshold))
    consecutive_target = max(1, int(body.retry_pressure_consecutive_ticks))
    cooldown_ticks = max(1, int(body.retry_pressure_cooldown_ticks))
    in_retry_pressure = threshold > 0 and retry_pressure_count_before >= threshold

    if in_retry_pressure:
        guardrail_state["consecutive_retry_pressure_ticks"] = int(
            guardrail_state.get("consecutive_retry_pressure_ticks", 0)
        ) + 1
    else:
        guardrail_state["consecutive_retry_pressure_ticks"] = 0

    cooldown_active = False
    trigger_reason: str | None = None
    escalated = False
    cooldown_remaining = int(guardrail_state.get("cooldown_remaining_ticks", 0))
    if cooldown_remaining > 0:
        cooldown_active = True
        trigger_reason = "retry_pressure_cooldown"
        guardrail_state["cooldown_remaining_ticks"] = max(0, cooldown_remaining - 1)
        guardrail_state["consecutive_retry_pressure_ticks"] = 0
    elif int(guardrail_state.get("consecutive_retry_pressure_ticks", 0)) >= consecutive_target:
        cooldown_active = True
        escalated = True
        trigger_reason = "retry_pressure_cooldown"
        guardrail_state["escalations_count"] = int(guardrail_state.get("escalations_count", 0)) + 1
        guardrail_state["cooldown_remaining_ticks"] = max(0, cooldown_ticks - 1)
        guardrail_state["consecutive_retry_pressure_ticks"] = 0

    collect_result = autonomy_collect_events(
        request,
        payload=AutonomyCollectRequest(
            max_events=body.max_collect_events,
            include_types=body.include_types,
        ),
    )
    if cooldown_active:
        _enforce_rbac(request, "autonomy.dispatch")
        _enforce_control("autonomy.dispatch", mutating=True)
        queue_after_collect = queue_status(_fs, limit=100)
        dispatch_result = {
            "status": "ok",
            "run_id": run_id,
            "leased_count": 0,
            "recovered_count": 0,
            "processed_count": 0,
            "failed_count": 0,
            "retried_count": 0,
            "released_count": 0,
            "dispatch_executed_actions": 0,
            "critical_incident_count": 0,
            "halted_reason": "retry_pressure_cooldown",
            "approval_id": None,
            "approval_required": False,
            "max_risk_tier": "low",
            "due_preview_count": int(queue_after_collect.get("queued_count", 0)),
            "recovery": {
                "status": "skipped",
                "run_id": run_id,
                "checked_count": 0,
                "recovered_count": 0,
                "lease_ttl_seconds": body.lease_ttl_seconds,
                "recovered": [],
            },
            "processed": [],
            "failed": [],
            "retried": [],
            "released": [],
            "config": {
                "max_events": body.max_events,
                "max_actions": body.max_actions,
                "max_runtime_seconds": body.max_runtime_seconds,
                "max_dispatch_actions": body.max_dispatch_actions,
                "max_dispatch_runtime_seconds": body.max_dispatch_runtime_seconds,
                "max_attempts": body.max_attempts,
                "retry_backoff_seconds": body.retry_backoff_seconds,
                "lease_ttl_seconds": body.lease_ttl_seconds,
                "recover_stale_leases": body.recover_stale_leases,
                "allow_medium": body.allow_medium,
                "allow_high": body.allow_high,
                "stop_on_critical": body.stop_on_critical,
            },
            "queue": queue_after_collect,
            "guardrail_cooldown": True,
        }
    else:
        dispatch_result = autonomy_dispatch_events(
            request,
            payload=AutonomyDispatchRequest(
                max_events=body.max_events,
                max_actions=body.max_actions,
                max_runtime_seconds=body.max_runtime_seconds,
                max_dispatch_actions=body.max_dispatch_actions,
                max_dispatch_runtime_seconds=body.max_dispatch_runtime_seconds,
                max_attempts=body.max_attempts,
                retry_backoff_seconds=body.retry_backoff_seconds,
                lease_ttl_seconds=body.lease_ttl_seconds,
                recover_stale_leases=body.recover_stale_leases,
                allow_medium=body.allow_medium,
                allow_high=body.allow_high,
                stop_on_critical=body.stop_on_critical,
            ),
        )

    queue_after = dispatch_result.get("queue", queue_status(_fs, limit=100))
    retry_pressure_count_after = int(queue_after.get("queued_retry_count", 0))
    guardrail_state["last_retry_pressure_count"] = retry_pressure_count_after
    guardrail_state["last_reason"] = trigger_reason if cooldown_active else None
    guardrail_after = write_reactor_guardrail_state(_fs, payload=guardrail_state)

    guardrail_receipt = {
        "cooldown_active": cooldown_active,
        "trigger_reason": trigger_reason,
        "escalated": escalated,
        "retry_pressure_threshold": threshold,
        "retry_pressure_consecutive_ticks": consecutive_target,
        "retry_pressure_cooldown_ticks": cooldown_ticks,
        "retry_pressure_count_before": retry_pressure_count_before,
        "retry_pressure_count_after": retry_pressure_count_after,
        "state_before": guardrail_before,
        "state_after": guardrail_after,
    }
    tick_summary = {
        "id": str(uuid4()),
        "ts": utc_now_iso(),
        "run_id": run_id,
        "kind": "autonomy.reactor.tick",
        "collect": {
            "seen_count": int(collect_result.get("seen_count", 0)),
            "queued_count": int(collect_result.get("queued_count", 0)),
            "duplicate_count": int(collect_result.get("duplicate_count", 0)),
        },
        "dispatch": {
            "leased_count": int(dispatch_result.get("leased_count", 0)),
            "processed_count": int(dispatch_result.get("processed_count", 0)),
            "failed_count": int(dispatch_result.get("failed_count", 0)),
            "retried_count": int(dispatch_result.get("retried_count", 0)),
            "released_count": int(dispatch_result.get("released_count", 0)),
            "halted_reason": dispatch_result.get("halted_reason"),
        },
        "config": {
            "max_collect_events": body.max_collect_events,
            "include_types": body.include_types or [],
            "max_events": body.max_events,
            "max_actions": body.max_actions,
            "max_runtime_seconds": body.max_runtime_seconds,
            "max_dispatch_actions": body.max_dispatch_actions,
            "max_dispatch_runtime_seconds": body.max_dispatch_runtime_seconds,
            "max_attempts": body.max_attempts,
            "retry_backoff_seconds": body.retry_backoff_seconds,
            "retry_pressure_threshold": body.retry_pressure_threshold,
            "retry_pressure_consecutive_ticks": body.retry_pressure_consecutive_ticks,
            "retry_pressure_cooldown_ticks": body.retry_pressure_cooldown_ticks,
            "lease_ttl_seconds": body.lease_ttl_seconds,
            "recover_stale_leases": body.recover_stale_leases,
            "allow_medium": body.allow_medium,
            "allow_high": body.allow_high,
            "stop_on_critical": body.stop_on_critical,
        },
        "guardrail": guardrail_receipt,
    }
    write_last_tick(_fs, payload=tick_summary)
    append_tick_history(_fs, payload=tick_summary)
    return {
        "status": "ok",
        "run_id": run_id,
        "collect": collect_result,
        "dispatch": dispatch_result,
        "guardrail": guardrail_receipt,
        "tick": tick_summary,
        "queue": queue_after,
    }


@router.post("/autonomy/events/recover")
def autonomy_recover_events(request: Request, payload: AutonomyRecoverRequest | None = None) -> dict:
    body = payload or AutonomyRecoverRequest()
    run_id = str(getattr(request.state, "run_id", uuid4()))
    _enforce_rbac(request, "autonomy.recover")
    _enforce_control("autonomy.recover", mutating=True)
    recovery = recover_stale_leased_events(
        _fs,
        run_id=run_id,
        lease_ttl_seconds=body.lease_ttl_seconds,
        max_recover=body.max_recover,
    )
    return {"status": "ok", "run_id": run_id, "recovery": recovery, "queue": queue_status(_fs, limit=100)}


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
