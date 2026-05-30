from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from francis.api.routes.memory_timeline import list_timeline, record_memory_timeline_payload
from francis.governance.api_permission_gate import ApiPermissionDecision, ApiPermissionGate
from francis.governance.redaction import redact_secret_text
from francis.telemetry.context import (
    MEMORY_TIMELINE_WRITE_SCOPE,
    TELEMETRY_CONTEXT_FEEDBACK_WRITE_SCOPE,
    record_telemetry_context_feedback,
    telemetry_context_feedback_memory_assistance_chat_context_contract,
    telemetry_context_feedback_memory_assistance_policy,
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


@router.get("/context/feedback/memory-assistance-policy")
def context_feedback_memory_assistance_policy() -> dict[str, Any]:
    return telemetry_context_feedback_memory_assistance_policy()


@router.get("/context/feedback/memory-assistance-chat-context-contract")
def context_feedback_memory_assistance_chat_context_contract() -> dict[str, Any]:
    return telemetry_context_feedback_memory_assistance_chat_context_contract()


@router.get("/context/feedback/memory-assistance-dry-run")
def context_feedback_memory_assistance_dry_run(limit: int = 20) -> dict[str, Any]:
    safe_limit = max(1, min(int(limit), 100))
    policy = telemetry_context_feedback_memory_assistance_policy()
    readback = context_feedback_memory_retrieval_readback(limit=safe_limit)
    raw_items_value = readback.get("items")
    raw_items: list[Any] = raw_items_value if isinstance(raw_items_value, list) else []
    rating_counts = {"useful": 0, "not_useful": 0, "neutral": 0}
    source_counts: dict[str, int] = {}
    event_refs: list[dict[str, Any]] = []
    skipped = 0

    for item in raw_items:
        if not isinstance(item, dict):
            skipped += 1
            continue
        payload_value = item.get("payload")
        payload: dict[str, Any] = payload_value if isinstance(payload_value, dict) else {}
        _merge_known_counts(rating_counts, payload.get("rating_counts"), allowed_keys=rating_counts.keys())
        _merge_count_map(source_counts, payload.get("source_counts"))
        retention_value = item.get("retention")
        retention: dict[str, Any] = retention_value if isinstance(retention_value, dict) else {}
        event_refs.append(
            {
                "id": item.get("id", ""),
                "kind": item.get("kind", ""),
                "action_type": item.get("action_type", ""),
                "classification": item.get("classification", ""),
                "retention_policy": retention.get("policy", ""),
            }
        )

    source_attention = [
        {
            "source_id": source_id,
            "feedback_count": count,
            "suggested_use": "operator_review_context_relevance",
        }
        for source_id, count in sorted(source_counts.items(), key=lambda value: (-value[1], value[0]))[:12]
        if source_id and count > 0
    ]
    matched_count = len(event_refs)
    status = "dry_run_ready" if matched_count > 0 else "empty"
    return {
        "ok": True,
        "kind": "francis.stage7.telemetry.context_feedback_memory_assistance_dry_run",
        "stage": "Stage 7 / Telemetry MVP",
        "source_id": "telemetry_context",
        "status": status,
        "policy": policy,
        "memory_readback": {
            "route": "/telemetry/context/feedback/memory-retrieval-readback",
            "status": readback.get("status", "unknown"),
            "count": readback.get("count", 0),
            "total": readback.get("total", 0),
            "skipped_count": readback.get("skipped_count", 0),
        },
        "event_refs": event_refs,
        "event_count": matched_count,
        "rating_counts": rating_counts,
        "source_attention": source_attention,
        "assistance_projection": {
            "summary": _assistance_projection_summary(
                event_count=matched_count,
                rating_counts=rating_counts,
                source_attention=source_attention,
            ),
            "allowed_influence_applied": policy.get("allowed_influence", []),
            "forbidden_influence_respected": policy.get("forbidden_influence", []),
        },
        "dry_run_only": True,
        "reads_memory": True,
        "writes_memory": False,
        "trains_model": False,
        "calls_model": False,
        "mutates_prompt": False,
        "selects_tools": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "governance": {
            "read_only": True,
            "dry_run_only": True,
            "uses_memory_retrieval_readback": True,
            "uses_assistance_policy": True,
            "telemetry_is_untrusted_input": True,
            "ignores_payload_instruction_text": True,
            "does_not_call_model": True,
            "does_not_mutate_prompt": True,
            "does_not_select_tools": True,
            "writes_memory": False,
            "trains_model": False,
            "grants_execution_authority": False,
            "grants_memory_write_authority": False,
        },
        "skipped_untrusted_items": skipped,
        "next_smallest_truthful_gap": "stage7_context_feedback_memory_assistance_operator_feedback_review",
    }


@router.get("/context/feedback/memory-assistance-chat-context-readback")
def context_feedback_memory_assistance_chat_context_readback(limit: int = 20) -> dict[str, Any]:
    safe_limit = max(1, min(int(limit), 100))
    contract = telemetry_context_feedback_memory_assistance_chat_context_contract()
    dry_run = context_feedback_memory_assistance_dry_run(limit=safe_limit)
    max_lines = _safe_count(contract.get("max_context_lines")) or 2
    max_lines = max(1, min(max_lines, 2))
    context_lines = _feedback_memory_assistance_chat_context_lines(dry_run=dry_run, max_lines=max_lines)
    status = "context_ready" if context_lines else "empty"
    return {
        "ok": True,
        "kind": "francis.stage7.telemetry.context_feedback_memory_assistance_chat_context_readback",
        "stage": "Stage 7 / Telemetry MVP",
        "source_id": "telemetry_context",
        "status": status,
        "contract": contract,
        "dry_run": {
            "route": "/telemetry/context/feedback/memory-assistance-dry-run",
            "status": dry_run.get("status", "unknown"),
            "event_count": dry_run.get("event_count", 0),
            "dry_run_only": dry_run.get("dry_run_only", False),
        },
        "chat_context": {
            "target": "telemetry_context.prompt_lines",
            "line_count": len(context_lines),
            "max_context_lines": max_lines,
            "lines": context_lines,
            "visible_header_required": True,
            "telemetry_is_untrusted_input": True,
        },
        "would_change_chat_prompt": bool(context_lines),
        "applies_to_chat_now": bool(context_lines),
        "reads_memory": True,
        "writes_memory": False,
        "calls_model": False,
        "mutates_prompt": False,
        "selects_tools": False,
        "trains_model": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "governance": {
            "read_only": True,
            "readback_only": True,
            "uses_assistance_chat_context_contract": True,
            "uses_assistance_dry_run": True,
            "chat_prompt_integration_enabled": True,
            "does_not_change_chat_prompt_by_itself": True,
            "telemetry_is_untrusted_input": True,
            "redacts_context_lines": True,
            "does_not_call_model": True,
            "does_not_select_tools": True,
            "writes_memory": False,
            "trains_model": False,
            "grants_execution_authority": False,
            "grants_memory_write_authority": False,
        },
        "next_smallest_truthful_gap": "stage7_context_feedback_memory_assistance_operator_feedback_review",
    }


@router.get("/context/feedback/memory-retrieval-readback")
def context_feedback_memory_retrieval_readback(limit: int = 20) -> dict[str, Any]:
    safe_limit = max(1, min(int(limit), 100))
    policy = telemetry_context_feedback_memory_retrieval_policy()
    timeline = list_timeline(
        limit=safe_limit,
        kinds=["telemetry_context_feedback_quality_review"],
        include_payload=True,
    )
    raw_items_value = timeline.get("items")
    raw_items: list[Any] = raw_items_value if isinstance(raw_items_value, list) else []
    items: list[dict[str, Any]] = []
    skipped = 0
    for raw_item in raw_items:
        if not isinstance(raw_item, dict):
            skipped += 1
            continue
        retention_value = raw_item.get("retention")
        retention: dict[str, Any] = retention_value if isinstance(retention_value, dict) else {}
        if (
            raw_item.get("action_type") == "telemetry.context_feedback.quality_review"
            and raw_item.get("classification") == "operator_feedback_quality_signal"
            and retention.get("policy") == "stage7_context_feedback_quality"
        ):
            items.append(raw_item)
            continue
        skipped += 1

    return {
        "ok": True,
        "kind": "francis.stage7.telemetry.context_feedback_memory_retrieval_readback",
        "stage": "Stage 7 / Telemetry MVP",
        "source_id": "telemetry_context",
        "status": "readback_ready" if items else "empty",
        "policy": policy,
        "memory_query": {
            "route": "/memory/timeline/list",
            "method": "GET",
            "filters": {
                "kinds": ["telemetry_context_feedback_quality_review"],
                "include_payload": True,
                "limit": safe_limit,
            },
        },
        "items": items,
        "count": len(items),
        "total": timeline.get("total", len(items)),
        "skipped_count": skipped,
        "reads_memory": True,
        "writes_memory": False,
        "trains_model": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "governance": {
            "read_only": True,
            "uses_memory_timeline_read_route": True,
            "uses_policy_filters": True,
            "telemetry_is_untrusted_input": True,
            "ignores_payload_instruction_text": True,
            "stores_prompt_body": False,
            "stores_model_response": False,
            "trains_model": False,
            "grants_execution_authority": False,
            "grants_memory_write_authority": False,
        },
        "next_smallest_truthful_gap": "stage7_context_feedback_memory_assistance_operator_feedback_review",
    }


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


def _merge_known_counts(target: dict[str, int], value: Any, *, allowed_keys: Any) -> None:
    if not isinstance(value, dict):
        return
    allowed = {str(key) for key in allowed_keys}
    for key, raw_count in value.items():
        text_key = str(key)
        if text_key not in allowed:
            continue
        target[text_key] = target.get(text_key, 0) + _safe_count(raw_count)


def _merge_count_map(target: dict[str, int], value: Any) -> None:
    if not isinstance(value, dict):
        return
    for key, raw_count in value.items():
        text_key = str(key).strip()
        if not text_key:
            continue
        target[text_key] = target.get(text_key, 0) + _safe_count(raw_count)


def _safe_count(value: Any) -> int:
    try:
        count = int(value)
    except (TypeError, ValueError):
        return 0
    return max(count, 0)


def _assistance_projection_summary(
    *,
    event_count: int,
    rating_counts: dict[str, int],
    source_attention: list[dict[str, Any]],
) -> str:
    if event_count <= 0:
        return "No governed feedback-quality memory is available for assistance dry run."
    misses = rating_counts.get("not_useful", 0)
    useful = rating_counts.get("useful", 0)
    top_source = source_attention[0]["source_id"] if source_attention else "telemetry_context"
    if misses > useful:
        return f"Operator feedback trends suggest reviewing {top_source} context relevance before assistance."
    if useful > 0:
        return f"Operator feedback trends support surfacing {top_source} as a relevant context source."
    return f"Operator feedback memory is available for bounded {top_source} context review."


def _feedback_memory_assistance_chat_context_lines(*, dry_run: dict[str, Any], max_lines: int) -> list[str]:
    if dry_run.get("status") != "dry_run_ready":
        return []
    projection_value = dry_run.get("assistance_projection")
    projection: dict[str, Any] = projection_value if isinstance(projection_value, dict) else {}
    lines: list[str] = []
    summary = _redacted_line_text(projection.get("summary"))
    if summary:
        lines.append(_bounded_chat_context_line(f"feedback_memory_assistance.summary: {summary}"))
    attention_value = dry_run.get("source_attention")
    attention: list[Any] = attention_value if isinstance(attention_value, list) else []
    first_attention = attention[0] if attention and isinstance(attention[0], dict) else {}
    if first_attention:
        source_id = _redacted_line_text(first_attention.get("source_id"))
        feedback_count = _safe_count(first_attention.get("feedback_count"))
        suggested_use = _redacted_line_text(first_attention.get("suggested_use"))
        if source_id:
            lines.append(
                _bounded_chat_context_line(
                    "feedback_memory_assistance.source_attention: "
                    f"{source_id} feedback_count={feedback_count} suggested_use={suggested_use}"
                )
            )
    return [line for line in lines if line][:max_lines]


def _redacted_line_text(value: Any) -> str:
    return redact_secret_text(str(value or "").strip()).replace("\r", " ").replace("\n", " ").strip()


def _bounded_chat_context_line(value: str) -> str:
    return value[:400]


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
