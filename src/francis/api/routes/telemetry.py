from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from francis.api.routes.memory_timeline import record_memory_timeline_payload
from francis.governance.api_permission_gate import ApiPermissionDecision, ApiPermissionGate
from francis.telemetry.context import (
    MEMORY_TIMELINE_WRITE_SCOPE,
    TELEMETRY_CONTEXT_FEEDBACK_WRITE_SCOPE,
    record_telemetry_context_feedback,
    telemetry_context_feedback_memory_quality,
    telemetry_context_feedback_memory_retrieval_policy,
    telemetry_context_feedback_review,
    telemetry_context_feedback_snapshot,
    telemetry_context_snapshot,
)
from francis.telemetry.git import git_status_snapshot
from francis.telemetry.ide_diagnostics import (
    IDE_DIAGNOSTIC_WRITE_SCOPE,
    ide_diagnostics_events_snapshot,
    ide_diagnostics_scope_snapshot,
    record_ide_diagnostic_event,
)
from francis.telemetry.status import telemetry_status_snapshot
from francis.telemetry.terminal import (
    TERMINAL_WRITE_SCOPE,
    record_terminal_event,
    terminal_events_snapshot,
    terminal_scope_snapshot,
)

router = APIRouter()


class TerminalEventIn(BaseModel):
    actor: str | None = None
    reason: str = ""
    command: str = ""
    cwd: str | None = None
    shell: str | None = None
    exit_code: int | None = None
    duration_ms: int | None = None
    started_ts: int | float | None = None
    completed_ts: int | float | None = None
    operation_id: str | None = None
    approval_id: str | None = None
    trace_id: str | None = None
    run_id: str | None = None
    artifact_dir: str | None = None
    tags: list[str] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)


class IdeDiagnosticEventIn(BaseModel):
    actor: str | None = None
    reason: str = ""
    source: str | None = None
    workspace: str | None = None
    file: str | None = None
    diagnostics: list[dict[str, Any]] = Field(default_factory=list)
    operation_id: str | None = None
    approval_id: str | None = None
    trace_id: str | None = None
    run_id: str | None = None
    tags: list[str] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)


class TelemetryContextFeedbackIn(BaseModel):
    actor: str | None = None
    reason: str = ""
    context_id: str | None = None
    surface: str | None = None
    rating: str = ""
    message_id: str | None = None
    reply_mode: str | None = None
    notes: str = ""
    source_ids: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)


class TelemetryContextFeedbackMemoryQualityIn(BaseModel):
    actor: str | None = None
    reason: str = ""
    limit: int = 100
    event_id: str | None = None


@router.get("/status")
def status() -> dict[str, Any]:
    return telemetry_status_snapshot()


@router.get("/context")
def context(surface: str = "assist") -> dict[str, Any]:
    return telemetry_context_snapshot(surface=surface)


@router.get("/context/feedback")
def context_feedback(limit: int = 20) -> dict[str, Any]:
    return telemetry_context_feedback_snapshot(limit=limit)


@router.get("/context/feedback/review")
def context_feedback_review(limit: int = 100) -> dict[str, Any]:
    return telemetry_context_feedback_review(limit=limit)


@router.get("/context/feedback/memory-quality")
def context_feedback_memory_quality(limit: int = 100) -> dict[str, Any]:
    return telemetry_context_feedback_memory_quality(limit=limit)


@router.get("/context/feedback/memory-retrieval-policy")
def context_feedback_memory_retrieval_policy() -> dict[str, Any]:
    return telemetry_context_feedback_memory_retrieval_policy()


@router.post("/context/feedback/memory-quality")
def context_feedback_memory_quality_record(payload: TelemetryContextFeedbackMemoryQualityIn) -> dict[str, Any]:
    permission = _write_permission(
        payload.actor,
        required_scope=MEMORY_TIMELINE_WRITE_SCOPE,
        route="/telemetry/context/feedback/memory-quality",
        method="POST",
    )
    if not permission.allowed:
        return _permission_denied(
            permission,
            source_id="telemetry_context",
            required_scope=MEMORY_TIMELINE_WRITE_SCOPE,
            next_step="configure_memory_timeline_write_actor_scope_before_recording_feedback_quality",
        )

    quality = telemetry_context_feedback_memory_quality(limit=payload.limit)
    candidate = quality.get("memory_write_candidate") if isinstance(quality.get("memory_write_candidate"), dict) else {}
    if not candidate:
        return {
            "ok": True,
            "kind": "francis.stage7.telemetry.context_feedback_memory_quality.record",
            "status": "empty",
            "source_id": "telemetry_context",
            "quality": quality,
            "memory_event": None,
            "writes_memory": False,
            "governance": {
                "required_scope": MEMORY_TIMELINE_WRITE_SCOPE,
                "explicit_operator_decision": True,
                "empty_review_does_not_write_memory": True,
                "grants_execution_authority": False,
                "grants_mutation_authority": False,
            },
        }

    event_payload = dict(candidate)
    if payload.event_id:
        event_payload["id"] = payload.event_id
    event_payload["request_actor"] = payload.actor
    event_payload["actor"] = payload.actor
    event_payload["scope"] = "telemetry.context.feedback"
    event_payload["severity"] = "info"
    candidate_meta = candidate.get("meta")
    event_meta = dict(candidate_meta) if isinstance(candidate_meta, dict) else {}
    event_meta.update(
        {
            "reason": payload.reason,
            "source_id": "telemetry_context",
            "explicit_operator_decision": True,
            "feedback_memory_quality_route": "/telemetry/context/feedback/memory-quality",
        }
    )
    event_payload["meta"] = event_meta
    memory_event = record_memory_timeline_payload(
        event_payload,
        route="/telemetry/context/feedback/memory-quality",
        method="POST",
    )
    if not memory_event.get("ok"):
        return {
            "ok": False,
            "kind": "francis.stage7.telemetry.context_feedback_memory_quality.record",
            "status": "denied",
            "source_id": "telemetry_context",
            "quality": quality,
            "memory_event": memory_event,
            "writes_memory": False,
            "governance": {
                "required_scope": MEMORY_TIMELINE_WRITE_SCOPE,
                "explicit_operator_decision": True,
                "memory_timeline_contract_enforced": True,
                "grants_execution_authority": False,
                "grants_mutation_authority": False,
            },
        }

    return {
        "ok": True,
        "kind": "francis.stage7.telemetry.context_feedback_memory_quality.record",
        "status": "recorded",
        "source_id": "telemetry_context",
        "quality": quality,
        "memory_event": memory_event,
        "memory_event_id": memory_event.get("id"),
        "writes_memory": True,
        "governance": {
            "required_scope": MEMORY_TIMELINE_WRITE_SCOPE,
            "explicit_operator_decision": True,
            "memory_timeline_contract_enforced": True,
            "stores_prompt_body": False,
            "stores_model_response": False,
            "trains_model": False,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
    }


@router.get("/terminal/scope")
def terminal_scope(actor: str = "") -> dict[str, Any]:
    permission = _write_permission(
        actor,
        required_scope=TERMINAL_WRITE_SCOPE,
        route="/telemetry/terminal/events",
        method="POST",
    )
    return terminal_scope_snapshot(actor=actor, permission=_permission_projection(permission))


@router.get("/terminal/events")
def terminal_events(limit: int = 20) -> dict[str, Any]:
    return terminal_events_snapshot(limit=limit)


@router.get("/ide-diagnostics/scope")
def ide_diagnostics_scope(actor: str = "") -> dict[str, Any]:
    permission = _write_permission(
        actor,
        required_scope=IDE_DIAGNOSTIC_WRITE_SCOPE,
        route="/telemetry/ide-diagnostics/events",
        method="POST",
    )
    return ide_diagnostics_scope_snapshot(actor=actor, permission=_permission_projection(permission))


@router.get("/ide-diagnostics/events")
def ide_diagnostics_events(limit: int = 20) -> dict[str, Any]:
    return ide_diagnostics_events_snapshot(limit=limit)


@router.get("/git/status")
def git_status(limit: int = 50) -> dict[str, Any]:
    return git_status_snapshot(limit=limit)


@router.post("/context/feedback")
def context_feedback_event(payload: TelemetryContextFeedbackIn) -> dict[str, Any]:
    permission = _write_permission(
        payload.actor,
        required_scope=TELEMETRY_CONTEXT_FEEDBACK_WRITE_SCOPE,
        route="/telemetry/context/feedback",
        method="POST",
    )
    if not permission.allowed:
        return _permission_denied(
            permission,
            source_id="telemetry_context",
            required_scope=TELEMETRY_CONTEXT_FEEDBACK_WRITE_SCOPE,
            next_step="configure_telemetry_context_feedback_actor_scope_before_recording_feedback",
        )
    item = record_telemetry_context_feedback(
        actor=payload.actor,
        reason=payload.reason,
        context_id=payload.context_id,
        surface=payload.surface,
        rating=payload.rating,
        message_id=payload.message_id,
        reply_mode=payload.reply_mode,
        notes=payload.notes,
        source_ids=payload.source_ids,
        tags=payload.tags,
        meta=payload.meta,
    )
    return {
        "ok": True,
        "kind": "francis.stage7.telemetry.context_feedback.recorded",
        "status": "recorded",
        "source_id": "telemetry_context",
        "item": item,
        "governance": {
            "gate": "permission_gate",
            "required_scope": TELEMETRY_CONTEXT_FEEDBACK_WRITE_SCOPE,
            "redacted_before_storage": True,
            "stores_prompt_body": False,
            "stores_model_response": False,
            "trains_model": False,
            "grants_execution_authority": False,
            "grants_memory_write_authority": False,
        },
    }


@router.post("/terminal/events")
def terminal_event(payload: TerminalEventIn) -> dict[str, Any]:
    permission = _write_permission(
        payload.actor,
        required_scope=TERMINAL_WRITE_SCOPE,
        route="/telemetry/terminal/events",
        method="POST",
    )
    if not permission.allowed:
        return _permission_denied(
            permission,
            source_id="terminal",
            required_scope=TERMINAL_WRITE_SCOPE,
            next_step="configure_telemetry_write_actor_scope_before_recording_terminal_events",
        )
    item = record_terminal_event(
        actor=payload.actor,
        reason=payload.reason,
        command=payload.command,
        cwd=payload.cwd,
        shell=payload.shell,
        exit_code=payload.exit_code,
        duration_ms=payload.duration_ms,
        started_ts=payload.started_ts,
        completed_ts=payload.completed_ts,
        operation_id=payload.operation_id,
        approval_id=payload.approval_id,
        trace_id=payload.trace_id,
        run_id=payload.run_id,
        artifact_dir=payload.artifact_dir,
        tags=payload.tags,
        meta=payload.meta,
    )
    return {
        "ok": True,
        "kind": "francis.stage7.telemetry.terminal_event.recorded",
        "status": "recorded",
        "source_id": "terminal",
        "item": item,
        "governance": {
            "gate": "permission_gate",
            "required_scope": TERMINAL_WRITE_SCOPE,
            "redacted_before_storage": True,
            "stores_stdout_stderr": False,
            "grants_execution_authority": False,
            "grants_memory_write_authority": False,
        },
    }


@router.post("/ide-diagnostics/events")
def ide_diagnostic_event(payload: IdeDiagnosticEventIn) -> dict[str, Any]:
    permission = _write_permission(
        payload.actor,
        required_scope=IDE_DIAGNOSTIC_WRITE_SCOPE,
        route="/telemetry/ide-diagnostics/events",
        method="POST",
    )
    if not permission.allowed:
        return _permission_denied(
            permission,
            source_id="ide_diagnostics",
            required_scope=IDE_DIAGNOSTIC_WRITE_SCOPE,
            next_step="configure_telemetry_write_actor_scope_before_recording_ide_diagnostics",
        )
    item = record_ide_diagnostic_event(
        actor=payload.actor,
        reason=payload.reason,
        source=payload.source,
        workspace=payload.workspace,
        file=payload.file,
        diagnostics=payload.diagnostics,
        operation_id=payload.operation_id,
        approval_id=payload.approval_id,
        trace_id=payload.trace_id,
        run_id=payload.run_id,
        tags=payload.tags,
        meta=payload.meta,
    )
    return {
        "ok": True,
        "kind": "francis.stage7.telemetry.ide_diagnostic_event.recorded",
        "status": "recorded",
        "source_id": "ide_diagnostics",
        "item": item,
        "governance": {
            "gate": "permission_gate",
            "required_scope": IDE_DIAGNOSTIC_WRITE_SCOPE,
            "redacted_before_storage": True,
            "stores_file_contents": False,
            "grants_execution_authority": False,
            "grants_memory_write_authority": False,
        },
    }


def _write_permission(actor: Any, *, required_scope: str, route: str, method: str) -> ApiPermissionDecision:
    return ApiPermissionGate.from_env().check(
        actor_id=actor,
        required_scopes=[required_scope],
        route=route,
        method=method,
    )


def _permission_denied(
    decision: ApiPermissionDecision,
    *,
    source_id: str,
    required_scope: str,
    next_step: str,
) -> dict[str, object]:
    return {
        "ok": False,
        "status": "denied",
        "error": "api_permission_denied",
        "source_id": source_id,
        "governance": {
            "gate": "permission_gate",
            "reason": decision.reason,
            "required_scope": required_scope,
            "next_step": next_step,
            "evidence": decision.evidence,
        },
    }


def _permission_projection(decision: ApiPermissionDecision) -> dict[str, Any]:
    return {"allowed": decision.allowed, "reason": decision.reason, "evidence": decision.evidence}
