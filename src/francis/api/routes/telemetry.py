from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from francis.chat.continuity.ledger import tail as conversation_ledger_tail
from francis.api.routes.memory_timeline import list_timeline, record_memory_timeline_payload
from francis.governance.api_permission_gate import ApiPermissionDecision, ApiPermissionGate
from francis.governance.redaction import redact_secret_text
from francis.telemetry.context import (
    MEMORY_TIMELINE_WRITE_SCOPE,
    TELEMETRY_CONTEXT_FEEDBACK_WRITE_SCOPE,
    feedback_memory_assistance_live_sample_operator_decision_count,
    read_telemetry_context_feedback,
    read_feedback_memory_assistance_live_sample_operator_decisions,
    record_feedback_memory_assistance_live_sample_operator_decision,
    record_telemetry_context_feedback,
    telemetry_context_feedback_memory_assistance_chat_context_contract,
    telemetry_context_feedback_memory_assistance_operator_feedback_memory_quality,
    telemetry_context_feedback_memory_assistance_operator_feedback_review,
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


class TelemetryContextFeedbackMemoryAssistanceLiveSampleOperatorDecisionIn(BaseModel):
    actor: str | None = None
    reason: str = ""
    decision: str = "needs_more_evidence"
    notes: str = ""
    limit: int = 20


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


@router.get("/context/feedback/memory-assistance-feedback-review")
def context_feedback_memory_assistance_operator_feedback_review(limit: int = 100) -> dict[str, Any]:
    return telemetry_context_feedback_memory_assistance_operator_feedback_review(limit=limit)


@router.get("/context/feedback/memory-assistance-feedback-memory-quality")
def context_feedback_memory_assistance_operator_feedback_memory_quality(limit: int = 100) -> dict[str, Any]:
    return telemetry_context_feedback_memory_assistance_operator_feedback_memory_quality(limit=limit)


@router.get("/context/feedback/memory-assistance-dry-run")
def context_feedback_memory_assistance_dry_run(limit: int = 20) -> dict[str, Any]:
    safe_limit = max(1, min(int(limit), 100))
    policy = telemetry_context_feedback_memory_assistance_policy()
    readback = context_feedback_memory_retrieval_readback(limit=safe_limit)
    operator_feedback_readback = context_feedback_memory_assistance_operator_feedback_memory_readback(limit=safe_limit)
    raw_items_value = readback.get("items")
    operator_items_value = operator_feedback_readback.get("items")
    raw_items: list[Any] = raw_items_value if isinstance(raw_items_value, list) else []
    if isinstance(operator_items_value, list):
        raw_items = [*raw_items, *operator_items_value]
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
            "operator_feedback_route": "/telemetry/context/feedback/memory-assistance-feedback-memory-readback",
            "operator_feedback_status": operator_feedback_readback.get("status", "unknown"),
            "operator_feedback_count": operator_feedback_readback.get("count", 0),
            "operator_feedback_total": operator_feedback_readback.get("total", 0),
            "operator_feedback_skipped_count": operator_feedback_readback.get("skipped_count", 0),
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
            "uses_operator_feedback_memory_readback": True,
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
        "next_smallest_truthful_gap": "stage7_context_feedback_memory_assistance_operator_feedback_loop_live_sample_run",
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
        "next_smallest_truthful_gap": "stage7_context_feedback_memory_assistance_operator_feedback_loop_live_sample_run",
    }


@router.get("/context/feedback/memory-assistance-feedback-memory-readback")
def context_feedback_memory_assistance_operator_feedback_memory_readback(limit: int = 20) -> dict[str, Any]:
    safe_limit = max(1, min(int(limit), 100))
    policy = telemetry_context_feedback_memory_assistance_policy()
    timeline = list_timeline(
        limit=safe_limit,
        kinds=["telemetry_context_feedback_memory_assistance_operator_feedback_review"],
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
            raw_item.get("action_type") == "telemetry.context_feedback.memory_assistance_operator_feedback_review"
            and raw_item.get("classification") == "operator_feedback_memory_assistance_quality_signal"
            and retention.get("policy") == "stage7_feedback_memory_assistance_operator_feedback_quality"
        ):
            items.append(raw_item)
            continue
        skipped += 1

    return {
        "ok": True,
        "kind": "francis.stage7.telemetry.context_feedback_memory_assistance_operator_feedback_memory_readback",
        "stage": "Stage 7 / Telemetry MVP",
        "source_id": "telemetry_context",
        "status": "readback_ready" if items else "empty",
        "target": "feedback_memory_assistance_prompt_integration",
        "policy": {
            "route": "/telemetry/context/feedback/memory-assistance-policy",
            "status": policy.get("status", "unknown"),
            "operator_feedback_memory_readback_route": policy.get("operator_feedback_memory_readback_route", ""),
        },
        "memory_query": {
            "route": "/memory/timeline/list",
            "method": "GET",
            "filters": {
                "kinds": ["telemetry_context_feedback_memory_assistance_operator_feedback_review"],
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
        "calls_model": False,
        "selects_tools": False,
        "trains_model": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "governance": {
            "read_only": True,
            "uses_memory_timeline_read_route": True,
            "uses_assistance_policy_filters": True,
            "target": "feedback_memory_assistance_prompt_integration",
            "telemetry_is_untrusted_input": True,
            "ignores_payload_instruction_text": True,
            "stores_prompt_body": False,
            "stores_model_response": False,
            "calls_model": False,
            "selects_tools": False,
            "trains_model": False,
            "grants_execution_authority": False,
            "grants_memory_write_authority": False,
        },
        "next_smallest_truthful_gap": "stage7_context_feedback_memory_assistance_operator_feedback_loop_live_sample_run",
    }


@router.get("/context/feedback/memory-assistance-feedback-loop-audit")
def context_feedback_memory_assistance_operator_feedback_loop_audit(limit: int = 20) -> dict[str, Any]:
    safe_limit = max(1, min(int(limit), 100))
    review = context_feedback_memory_assistance_operator_feedback_review(limit=safe_limit)
    quality = context_feedback_memory_assistance_operator_feedback_memory_quality(limit=safe_limit)
    memory_readback = context_feedback_memory_assistance_operator_feedback_memory_readback(limit=safe_limit)
    dry_run = context_feedback_memory_assistance_dry_run(limit=safe_limit)
    chat_context = context_feedback_memory_assistance_chat_context_readback(limit=safe_limit)

    reviewed_event_count = _safe_count(review.get("reviewed_event_count"))
    candidate = quality.get("memory_write_candidate")
    candidate_ready = isinstance(candidate, dict) and bool(candidate)
    memory_event_count = _safe_count(memory_readback.get("count"))
    dry_run_event_count = _safe_count(dry_run.get("event_count"))
    chat_context_value = chat_context.get("chat_context")
    chat_context_payload: dict[str, Any] = chat_context_value if isinstance(chat_context_value, dict) else {}
    chat_context_line_count = _safe_count(chat_context_payload.get("line_count"))
    ui_recording_declared = True

    requirements = [
        {
            "id": "targeted_operator_feedback_review",
            "ready": reviewed_event_count > 0,
            "status": review.get("status", "unknown"),
            "route": "/telemetry/context/feedback/memory-assistance-feedback-review",
            "evidence": {"reviewed_event_count": reviewed_event_count},
        },
        {
            "id": "memory_quality_candidate",
            "ready": candidate_ready,
            "status": quality.get("status", "unknown"),
            "route": "/telemetry/context/feedback/memory-assistance-feedback-memory-quality",
            "evidence": {"operator_decision_required": bool(quality.get("operator_decision_required"))},
        },
        {
            "id": "governed_memory_receipt_readback",
            "ready": memory_event_count > 0,
            "status": memory_readback.get("status", "unknown"),
            "route": "/telemetry/context/feedback/memory-assistance-feedback-memory-readback",
            "evidence": {
                "count": memory_event_count,
                "skipped_count": _safe_count(memory_readback.get("skipped_count")),
            },
        },
        {
            "id": "assistance_dry_run_consumes_memory_readback",
            "ready": dry_run_event_count > 0,
            "status": dry_run.get("status", "unknown"),
            "route": "/telemetry/context/feedback/memory-assistance-dry-run",
            "evidence": {"event_count": dry_run_event_count},
        },
        {
            "id": "chat_context_projection_visible",
            "ready": chat_context_line_count > 0,
            "status": chat_context.get("status", "unknown"),
            "route": "/telemetry/context/feedback/memory-assistance-chat-context-readback",
            "evidence": {"line_count": chat_context_line_count},
        },
        {
            "id": "operator_ui_recording_surface",
            "ready": ui_recording_declared,
            "status": "declared",
            "route": "apps/chat_ui/src/App.tsx",
            "evidence": {"action": "Record assistance memory", "required_scope": MEMORY_TIMELINE_WRITE_SCOPE},
        },
    ]
    ready_count = sum(1 for requirement in requirements if requirement["ready"])
    status = (
        "loop_observed"
        if ready_count == len(requirements)
        else "awaiting_memory_record"
        if candidate_ready and memory_event_count <= 0
        else "awaiting_feedback"
        if reviewed_event_count <= 0
        else "partial"
    )

    return {
        "ok": True,
        "kind": "francis.stage7.telemetry.context_feedback_memory_assistance_operator_feedback_loop_audit",
        "stage": "Stage 7 / Telemetry MVP",
        "source_id": "telemetry_context",
        "status": status,
        "target": "feedback_memory_assistance_prompt_integration",
        "requirements": requirements,
        "ready_count": ready_count,
        "required_count": len(requirements),
        "loop_observed": status == "loop_observed",
        "reviewed_event_count": reviewed_event_count,
        "memory_event_count": memory_event_count,
        "dry_run_event_count": dry_run_event_count,
        "chat_context_line_count": chat_context_line_count,
        "routes": {
            "feedback_review": "/telemetry/context/feedback/memory-assistance-feedback-review",
            "memory_quality": "/telemetry/context/feedback/memory-assistance-feedback-memory-quality",
            "memory_readback": "/telemetry/context/feedback/memory-assistance-feedback-memory-readback",
            "dry_run": "/telemetry/context/feedback/memory-assistance-dry-run",
            "chat_context": "/telemetry/context/feedback/memory-assistance-chat-context-readback",
        },
        "reads_memory": True,
        "writes_memory": False,
        "calls_model": False,
        "selects_tools": False,
        "trains_model": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "governance": {
            "read_only": True,
            "audit_only": True,
            "uses_explicit_operator_feedback_only": True,
            "uses_memory_timeline_read_route": True,
            "telemetry_is_untrusted_input": True,
            "ignores_payload_instruction_text": True,
            "does_not_write_memory": True,
            "does_not_call_model": True,
            "does_not_select_tools": True,
            "grants_execution_authority": False,
            "grants_memory_write_authority": False,
        },
        "next_smallest_truthful_gap": "stage7_context_feedback_memory_assistance_operator_feedback_loop_live_sample_run",
    }


@router.get("/context/feedback/memory-assistance-feedback-loop-e2e-sample")
def context_feedback_memory_assistance_operator_feedback_loop_e2e_sample(limit: int = 20) -> dict[str, Any]:
    safe_limit = max(1, min(int(limit), 100))
    audit = context_feedback_memory_assistance_operator_feedback_loop_audit(limit=safe_limit)
    chat_context = context_feedback_memory_assistance_chat_context_readback(limit=safe_limit)
    chat_context_value = chat_context.get("chat_context")
    chat_context_payload: dict[str, Any] = chat_context_value if isinstance(chat_context_value, dict) else {}
    lines_value = chat_context_payload.get("lines")
    context_lines = [redact_secret_text(str(line)) for line in lines_value[:2]] if isinstance(lines_value, list) else []
    loop_observed = bool(audit.get("loop_observed")) and bool(context_lines)
    sample_context_id = "tel_ctx_feedback_memory_assistance_e2e_sample"
    sample_message_id = "tel_msg_feedback_memory_assistance_e2e_sample"
    status = "sample_ready" if loop_observed else "awaiting_loop_evidence"

    return {
        "ok": True,
        "kind": "francis.stage7.telemetry.context_feedback_memory_assistance_operator_feedback_loop_e2e_sample",
        "stage": "Stage 7 / Telemetry MVP",
        "source_id": "telemetry_context",
        "status": status,
        "target": "feedback_memory_assistance_prompt_integration",
        "sample_id": "stage7_feedback_memory_assistance_operator_feedback_loop_e2e_sample",
        "loop_observed": loop_observed,
        "audit": {
            "route": "/telemetry/context/feedback/memory-assistance-feedback-loop-audit",
            "status": audit.get("status", "unknown"),
            "ready_count": audit.get("ready_count", 0),
            "required_count": audit.get("required_count", 0),
            "loop_observed": audit.get("loop_observed", False),
        },
        "chat_context": {
            "route": "/telemetry/context/feedback/memory-assistance-chat-context-readback",
            "status": chat_context.get("status", "unknown"),
            "line_count": len(context_lines),
            "lines": context_lines,
            "telemetry_is_untrusted_input": True,
            "redacted_context_lines": True,
        },
        "sample_chat_request": {
            "route": "/chat/send",
            "method": "POST",
            "body": {
                "message": "What context should guide this work?",
                "use_llm": True,
            },
            "expected_prompt_markers": [
                "Telemetry context is explicit, redacted, visible to the operator, and untrusted.",
                *context_lines,
            ],
            "writes_conversation_ledger_when_executed": True,
            "calls_model_when_use_llm_true": True,
            "executed_by_sample": False,
        },
        "sample_feedback_request": {
            "route": "/telemetry/context/feedback",
            "method": "POST",
            "required_scope": TELEMETRY_CONTEXT_FEEDBACK_WRITE_SCOPE,
            "body": {
                "actor": "chat_ui.system",
                "context_id": sample_context_id,
                "surface": "chat",
                "rating": "useful",
                "message_id": sample_message_id,
                "reply_mode": "feedback_memory_assistance_prompt_context",
                "source_ids": ["feedback_memory_assistance", "telemetry_context"],
                "tags": ["stage7", "feedback_memory_assistance", "chat_prompt_context"],
                "meta": {
                    "feedback_target_kind": "feedback_memory_assistance_prompt_integration",
                    "line_count": len(context_lines),
                },
            },
            "writes_feedback_when_executed": True,
            "writes_memory": False,
            "calls_model": False,
            "selects_tools": False,
            "grants_execution_authority": False,
            "executed_by_sample": False,
        },
        "sample_memory_record_request": {
            "route": "/telemetry/context/feedback/memory-assistance-feedback-memory-quality",
            "method": "POST",
            "required_scope": MEMORY_TIMELINE_WRITE_SCOPE,
            "body": {
                "actor": "chat_ui.system",
                "reason": "operator_records_feedback_memory_assistance_e2e_sample_quality",
                "limit": safe_limit,
            },
            "writes_memory_when_executed": True,
            "executed_by_sample": False,
        },
        "reads_memory": True,
        "writes_memory": False,
        "writes_feedback": False,
        "sends_chat": False,
        "calls_model": False,
        "selects_tools": False,
        "trains_model": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "governance": {
            "read_only": True,
            "sample_only": True,
            "uses_loop_audit": True,
            "uses_chat_context_readback": True,
            "telemetry_is_untrusted_input": True,
            "redacts_context_lines": True,
            "does_not_send_chat": True,
            "does_not_write_feedback": True,
            "does_not_write_memory": True,
            "does_not_call_model": True,
            "does_not_select_tools": True,
            "grants_execution_authority": False,
            "grants_memory_write_authority": False,
        },
        "next_smallest_truthful_gap": "stage7_context_feedback_memory_assistance_operator_feedback_loop_live_sample_run",
    }


@router.get("/context/feedback/memory-assistance-feedback-loop-e2e-acceptance-audit")
def context_feedback_memory_assistance_operator_feedback_loop_e2e_acceptance_audit(limit: int = 20) -> dict[str, Any]:
    safe_limit = max(1, min(int(limit), 100))
    sample = context_feedback_memory_assistance_operator_feedback_loop_e2e_sample(limit=safe_limit)
    sample_audit_value = sample.get("audit")
    sample_audit: dict[str, Any] = sample_audit_value if isinstance(sample_audit_value, dict) else {}
    sample_chat_context_value = sample.get("chat_context")
    sample_chat_context: dict[str, Any] = (
        sample_chat_context_value if isinstance(sample_chat_context_value, dict) else {}
    )
    chat_request_value = sample.get("sample_chat_request")
    chat_request: dict[str, Any] = chat_request_value if isinstance(chat_request_value, dict) else {}
    feedback_request_value = sample.get("sample_feedback_request")
    feedback_request: dict[str, Any] = feedback_request_value if isinstance(feedback_request_value, dict) else {}
    memory_request_value = sample.get("sample_memory_record_request")
    memory_request: dict[str, Any] = memory_request_value if isinstance(memory_request_value, dict) else {}
    context_lines_value = sample_chat_context.get("lines")
    context_lines = context_lines_value if isinstance(context_lines_value, list) else []

    sample_readback_ready = bool(sample.get("loop_observed")) and sample.get("status") == "sample_ready"
    loop_audit_ready = bool(sample_audit.get("loop_observed")) and (
        _safe_count(sample_audit.get("ready_count")) == _safe_count(sample_audit.get("required_count")) > 0
    )
    sample_routes_bound = (
        chat_request.get("route") == "/chat/send"
        and feedback_request.get("route") == "/telemetry/context/feedback"
        and feedback_request.get("required_scope") == TELEMETRY_CONTEXT_FEEDBACK_WRITE_SCOPE
        and memory_request.get("route") == "/telemetry/context/feedback/memory-assistance-feedback-memory-quality"
        and memory_request.get("required_scope") == MEMORY_TIMELINE_WRITE_SCOPE
    )
    sample_non_execution_guarded = (
        sample.get("writes_memory") is False
        and sample.get("writes_feedback") is False
        and sample.get("sends_chat") is False
        and sample.get("calls_model") is False
        and sample.get("selects_tools") is False
        and sample.get("grants_execution_authority") is False
        and chat_request.get("executed_by_sample") is False
        and feedback_request.get("executed_by_sample") is False
        and memory_request.get("executed_by_sample") is False
    )
    context_redaction_ready = (
        _safe_count(sample_chat_context.get("line_count")) > 0
        and all(isinstance(line, str) and "\n" not in line and "\r" not in line for line in context_lines)
        and bool(sample_chat_context.get("redacted_context_lines"))
        and bool(sample_chat_context.get("telemetry_is_untrusted_input"))
    )
    operator_surface_visible = True

    acceptance_criteria = [
        {
            "id": "loop_audit_ready",
            "ready": loop_audit_ready,
            "status": sample_audit.get("status", "unknown"),
            "evidence": {
                "ready_count": _safe_count(sample_audit.get("ready_count")),
                "required_count": _safe_count(sample_audit.get("required_count")),
            },
        },
        {
            "id": "e2e_sample_readback_ready",
            "ready": sample_readback_ready,
            "status": sample.get("status", "unknown"),
            "evidence": {"sample_id": sample.get("sample_id", "")},
        },
        {
            "id": "sample_routes_bound",
            "ready": sample_routes_bound,
            "status": "routes_bound" if sample_routes_bound else "missing_or_unexpected",
            "evidence": {
                "chat_route": chat_request.get("route", ""),
                "feedback_route": feedback_request.get("route", ""),
                "memory_route": memory_request.get("route", ""),
            },
        },
        {
            "id": "sample_non_execution_guarded",
            "ready": sample_non_execution_guarded,
            "status": "non_executing" if sample_non_execution_guarded else "mutation_or_execution_possible",
            "evidence": {
                "sends_chat": bool(sample.get("sends_chat")),
                "writes_feedback": bool(sample.get("writes_feedback")),
                "writes_memory": bool(sample.get("writes_memory")),
                "calls_model": bool(sample.get("calls_model")),
            },
        },
        {
            "id": "redacted_context_lines_ready",
            "ready": context_redaction_ready,
            "status": "redacted_context_ready" if context_redaction_ready else "awaiting_context_lines",
            "evidence": {"line_count": _safe_count(sample_chat_context.get("line_count"))},
        },
        {
            "id": "operator_surface_visible",
            "ready": operator_surface_visible,
            "status": "declared",
            "evidence": {
                "route": "apps/chat_ui/src/App.tsx",
                "surface": "Telemetry & Continuation",
                "badge": "Assist sample",
            },
        },
    ]
    ready_count = sum(1 for criterion in acceptance_criteria if criterion["ready"])
    acceptance_ready = ready_count == len(acceptance_criteria)
    status = "acceptance_ready" if acceptance_ready else "awaiting_sample_evidence"

    return {
        "ok": True,
        "kind": "francis.stage7.telemetry.context_feedback_memory_assistance_operator_feedback_loop_e2e_acceptance_audit",
        "stage": "Stage 7 / Telemetry MVP",
        "source_id": "telemetry_context",
        "status": status,
        "target": "feedback_memory_assistance_prompt_integration",
        "sample_id": sample.get("sample_id", ""),
        "acceptance_ready": acceptance_ready,
        "acceptance_criteria": acceptance_criteria,
        "ready_count": ready_count,
        "required_count": len(acceptance_criteria),
        "sample": {
            "route": "/telemetry/context/feedback/memory-assistance-feedback-loop-e2e-sample",
            "status": sample.get("status", "unknown"),
            "loop_observed": sample.get("loop_observed", False),
            "chat_context_line_count": _safe_count(sample_chat_context.get("line_count")),
        },
        "reads_memory": True,
        "writes_memory": False,
        "writes_feedback": False,
        "sends_chat": False,
        "calls_model": False,
        "selects_tools": False,
        "trains_model": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "governance": {
            "read_only": True,
            "acceptance_audit_only": True,
            "uses_e2e_sample_readback": True,
            "telemetry_is_untrusted_input": True,
            "does_not_send_chat": True,
            "does_not_write_feedback": True,
            "does_not_write_memory": True,
            "does_not_call_model": True,
            "does_not_select_tools": True,
            "grants_execution_authority": False,
            "grants_memory_write_authority": False,
        },
        "next_smallest_truthful_gap": "stage7_context_feedback_memory_assistance_operator_feedback_loop_live_sample_run",
    }


@router.get("/context/feedback/memory-assistance-feedback-loop-live-sample-readback")
def context_feedback_memory_assistance_operator_feedback_loop_live_sample_readback(
    limit: int = 20,
) -> dict[str, Any]:
    safe_limit = max(1, min(int(limit), 100))
    acceptance = context_feedback_memory_assistance_operator_feedback_loop_e2e_acceptance_audit(limit=safe_limit)
    chat_evidence = _feedback_memory_assistance_live_chat_evidence(limit=safe_limit)
    feedback_evidence = _feedback_memory_assistance_live_feedback_evidence(limit=safe_limit)
    memory_evidence = _feedback_memory_assistance_live_memory_evidence(limit=safe_limit)
    acceptance_ready = bool(acceptance.get("acceptance_ready"))
    chat_ready = bool(chat_evidence)
    feedback_ready = bool(feedback_evidence)
    memory_ready = bool(memory_evidence)
    live_sample_observed = acceptance_ready and chat_ready and feedback_ready and memory_ready
    status = "live_sample_observed" if live_sample_observed else "awaiting_live_sample_evidence"
    criteria = [
        {
            "id": "acceptance_audit_ready",
            "ready": acceptance_ready,
            "status": acceptance.get("status", "unknown"),
            "evidence": {
                "ready_count": _safe_count(acceptance.get("ready_count")),
                "required_count": _safe_count(acceptance.get("required_count")),
            },
        },
        {
            "id": "chat_send_ledger_readback",
            "ready": chat_ready,
            "status": "observed" if chat_ready else "missing",
            "evidence": chat_evidence,
        },
        {
            "id": "operator_feedback_readback",
            "ready": feedback_ready,
            "status": "observed" if feedback_ready else "missing",
            "evidence": feedback_evidence,
        },
        {
            "id": "memory_quality_readback",
            "ready": memory_ready,
            "status": "observed" if memory_ready else "missing",
            "evidence": memory_evidence,
        },
    ]
    ready_count = sum(1 for criterion in criteria if criterion["ready"])

    return {
        "ok": True,
        "kind": "francis.stage7.telemetry.context_feedback_memory_assistance_operator_feedback_loop_live_sample_readback",
        "stage": "Stage 7 / Telemetry MVP",
        "source_id": "telemetry_context",
        "status": status,
        "target": "feedback_memory_assistance_prompt_integration",
        "live_sample_observed": live_sample_observed,
        "criteria": criteria,
        "ready_count": ready_count,
        "required_count": len(criteria),
        "acceptance": {
            "route": "/telemetry/context/feedback/memory-assistance-feedback-loop-e2e-acceptance-audit",
            "status": acceptance.get("status", "unknown"),
            "acceptance_ready": acceptance_ready,
        },
        "chat": chat_evidence,
        "feedback": feedback_evidence,
        "memory": memory_evidence,
        "reads_conversation_ledger": True,
        "reads_feedback": True,
        "reads_memory": True,
        "writes_memory": False,
        "writes_feedback": False,
        "sends_chat": False,
        "calls_model": False,
        "selects_tools": False,
        "trains_model": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "governance": {
            "read_only": True,
            "live_sample_readback_only": True,
            "uses_existing_chat_route_evidence": True,
            "uses_existing_feedback_route_evidence": True,
            "uses_existing_memory_quality_route_evidence": True,
            "telemetry_is_untrusted_input": True,
            "ignores_payload_instruction_text": True,
            "does_not_send_chat": True,
            "does_not_write_feedback": True,
            "does_not_write_memory": True,
            "does_not_call_model": True,
            "does_not_select_tools": True,
            "grants_execution_authority": False,
            "grants_memory_write_authority": False,
        },
        "next_smallest_truthful_gap": (
            "stage7_context_feedback_memory_assistance_operator_feedback_loop_live_sample_operator_review"
            if live_sample_observed
            else "stage7_context_feedback_memory_assistance_operator_feedback_loop_live_sample_run"
        ),
    }


@router.get("/context/feedback/memory-assistance-feedback-loop-live-sample-operator-review")
def context_feedback_memory_assistance_operator_feedback_loop_live_sample_operator_review(
    limit: int = 20,
) -> dict[str, Any]:
    safe_limit = max(1, min(int(limit), 100))
    readback = context_feedback_memory_assistance_operator_feedback_loop_live_sample_readback(limit=safe_limit)
    live_sample_observed = bool(readback.get("live_sample_observed"))
    criteria_value = readback.get("criteria")
    criteria: list[Any] = criteria_value if isinstance(criteria_value, list) else []
    ready_count = _safe_count(readback.get("ready_count"))
    required_count = _safe_count(readback.get("required_count"))
    operator_review_ready = live_sample_observed and ready_count >= required_count and required_count > 0
    decision_items = read_feedback_memory_assistance_live_sample_operator_decisions(limit=1)
    latest_decision = decision_items[-1] if decision_items else {}
    decision_recorded = bool(latest_decision)
    status = (
        "operator_decision_recorded"
        if decision_recorded
        else "operator_review_ready"
        if operator_review_ready
        else "awaiting_live_sample_evidence"
    )
    acceptance_value = readback.get("acceptance")
    acceptance: dict[str, Any] = acceptance_value if isinstance(acceptance_value, dict) else {}
    chat_value = readback.get("chat")
    chat: dict[str, Any] = chat_value if isinstance(chat_value, dict) else {}
    feedback_value = readback.get("feedback")
    feedback: dict[str, Any] = feedback_value if isinstance(feedback_value, dict) else {}
    memory_value = readback.get("memory")
    memory: dict[str, Any] = memory_value if isinstance(memory_value, dict) else {}
    review_items = [
        {
            "id": "acceptance_audit_ready",
            "ready": bool(acceptance.get("acceptance_ready")),
            "status": acceptance.get("status", "missing"),
        },
        {
            "id": "chat_send_ledger_readback",
            "ready": bool(chat),
            "status": chat.get("status", "missing"),
        },
        {
            "id": "operator_feedback_readback",
            "ready": bool(feedback),
            "status": feedback.get("status", "missing"),
        },
        {
            "id": "memory_quality_readback",
            "ready": bool(memory),
            "status": memory.get("status", "missing"),
        },
    ]

    return {
        "ok": True,
        "kind": "francis.stage7.telemetry.context_feedback_memory_assistance_operator_feedback_loop_live_sample_operator_review",
        "stage": "Stage 7 / Telemetry MVP",
        "source_id": "telemetry_context",
        "status": status,
        "target": "feedback_memory_assistance_prompt_integration",
        "operator_review_ready": operator_review_ready,
        "live_sample_observed": live_sample_observed,
        "ready_count": ready_count,
        "required_count": required_count,
        "criteria": criteria,
        "review_items": review_items,
        "live_sample": {
            "route": "/telemetry/context/feedback/memory-assistance-feedback-loop-live-sample-readback",
            "status": readback.get("status", "unknown"),
            "next_smallest_truthful_gap": readback.get("next_smallest_truthful_gap", ""),
        },
        "latest_operator_decision": latest_decision,
        "operator_decision_total": feedback_memory_assistance_live_sample_operator_decision_count(),
        "evidence": {
            "acceptance": acceptance,
            "chat": chat,
            "feedback": feedback,
            "memory": memory,
        },
        "operator_decision": {
            "required": operator_review_ready and not decision_recorded,
            "recorded": decision_recorded,
            "decision": latest_decision.get("decision", ""),
            "receipt_id": latest_decision.get("receipt_id", ""),
            "reason": (
                "operator_review_decision_recorded"
                if decision_recorded
                else "operator_review_decision_not_recorded_by_read_only_projection"
                if operator_review_ready
                else "live_sample_evidence_required_before_operator_review"
            ),
        },
        "reads_conversation_ledger": True,
        "reads_feedback": True,
        "reads_memory": True,
        "writes_memory": False,
        "writes_feedback": False,
        "sends_chat": False,
        "calls_model": False,
        "selects_tools": False,
        "trains_model": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "governance": {
            "read_only": True,
            "operator_review_projection_only": True,
            "uses_live_sample_readback": True,
            "telemetry_is_untrusted_input": True,
            "ignores_payload_instruction_text": True,
            "does_not_record_operator_decision": True,
            "does_not_send_chat": True,
            "does_not_write_feedback": True,
            "does_not_write_memory": True,
            "does_not_call_model": True,
            "does_not_select_tools": True,
            "grants_execution_authority": False,
            "grants_memory_write_authority": False,
        },
        "next_smallest_truthful_gap": (
            "stage7_context_feedback_memory_assistance_operator_feedback_loop_decision_outcome_review"
            if decision_recorded
            else (
                "stage7_context_feedback_memory_assistance_operator_feedback_loop_live_sample_operator_decision"
                if operator_review_ready
                else "stage7_context_feedback_memory_assistance_operator_feedback_loop_live_sample_run"
            )
        ),
    }


@router.get("/context/feedback/memory-assistance-feedback-loop-live-sample-operator-decisions")
def context_feedback_memory_assistance_operator_feedback_loop_live_sample_operator_decisions(
    limit: int = 20,
) -> dict[str, Any]:
    safe_limit = max(1, min(int(limit), 100))
    items = read_feedback_memory_assistance_live_sample_operator_decisions(limit=safe_limit)
    total = feedback_memory_assistance_live_sample_operator_decision_count()
    latest_receipt = items[-1] if items else {}
    decision_counts = {"accepted": 0, "rejected": 0, "needs_more_evidence": 0}
    for item in items:
        decision = str(item.get("decision", "needs_more_evidence"))
        if decision not in decision_counts:
            decision = "needs_more_evidence"
        decision_counts[decision] += 1
    readback_ready = bool(latest_receipt)
    return {
        "ok": True,
        "kind": "francis.stage7.telemetry.context_feedback_memory_assistance_live_sample_operator_decision_receipts",
        "stage": "Stage 7 / Telemetry MVP",
        "source_id": "telemetry_context",
        "status": "decision_receipt_readback_ready" if readback_ready else "empty",
        "target": "feedback_memory_assistance_prompt_integration",
        "items": items,
        "count": len(items),
        "total": total,
        "limit": safe_limit,
        "truncated": total > len(items),
        "latest_receipt": latest_receipt,
        "latest_receipt_id": latest_receipt.get("receipt_id", ""),
        "latest_decision": latest_receipt.get("decision", ""),
        "latest_recorded_ts": latest_receipt.get("recorded_ts", 0),
        "decision_counts": decision_counts,
        "receipt_readback_ready": readback_ready,
        "redacted": True,
        "reads_receipts": True,
        "writes_receipts": False,
        "writes_memory": False,
        "writes_feedback": False,
        "sends_chat": False,
        "calls_model": False,
        "selects_tools": False,
        "trains_model": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "governance": {
            "read_only": True,
            "operator_decision_receipt_readback": True,
            "receipt_readback_ready": readback_ready,
            "redacted_before_storage": True,
            "telemetry_is_untrusted_input": True,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
        "next_smallest_truthful_gap": (
            "stage7_context_feedback_memory_assistance_operator_feedback_loop_decision_outcome_review"
            if readback_ready
            else "stage7_context_feedback_memory_assistance_operator_feedback_loop_live_sample_operator_decision"
        ),
    }


@router.get("/context/feedback/memory-assistance-feedback-loop-live-sample-operator-decision-outcome-review")
def context_feedback_memory_assistance_operator_feedback_loop_live_sample_operator_decision_outcome_review(
    limit: int = 20,
) -> dict[str, Any]:
    safe_limit = max(1, min(int(limit), 100))
    receipt_readback = context_feedback_memory_assistance_operator_feedback_loop_live_sample_operator_decisions(
        limit=safe_limit
    )
    latest_receipt_value = receipt_readback.get("latest_receipt")
    latest_receipt: dict[str, Any] = latest_receipt_value if isinstance(latest_receipt_value, dict) else {}
    latest_decision = str(receipt_readback.get("latest_decision", "")).strip()
    receipt_ready = bool(receipt_readback.get("receipt_readback_ready")) and bool(latest_receipt)
    outcome_by_decision = {
        "accepted": "operator_accepted_current_live_sample",
        "rejected": "operator_rejected_current_live_sample",
        "needs_more_evidence": "operator_requested_more_evidence",
    }
    outcome = outcome_by_decision.get(latest_decision, "awaiting_operator_decision")
    outcome_review_ready = receipt_ready and latest_decision in outcome_by_decision
    return {
        "ok": True,
        "kind": "francis.stage7.telemetry.context_feedback_memory_assistance_live_sample_operator_decision_outcome_review",
        "stage": "Stage 7 / Telemetry MVP",
        "source_id": "telemetry_context",
        "status": "outcome_review_ready" if outcome_review_ready else "awaiting_decision_receipt_readback",
        "target": "feedback_memory_assistance_prompt_integration",
        "outcome": outcome,
        "outcome_review_ready": outcome_review_ready,
        "latest_decision": latest_decision,
        "latest_receipt_id": receipt_readback.get("latest_receipt_id", ""),
        "latest_recorded_ts": receipt_readback.get("latest_recorded_ts", 0),
        "receipt_readback": receipt_readback,
        "decision_counts": receipt_readback.get("decision_counts", {}),
        "review": {
            "accepted_current_sample": latest_decision == "accepted",
            "rejected_current_sample": latest_decision == "rejected",
            "needs_more_evidence": latest_decision == "needs_more_evidence",
            "receipt_readback_ready": receipt_ready,
            "receipt_redacted": bool(receipt_readback.get("redacted")),
        },
        "reads_receipts": True,
        "writes_receipts": False,
        "writes_memory": False,
        "writes_feedback": False,
        "sends_chat": False,
        "calls_model": False,
        "selects_tools": False,
        "trains_model": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "governance": {
            "read_only": True,
            "operator_decision_outcome_review": True,
            "uses_decision_receipt_readback": True,
            "telemetry_is_untrusted_input": True,
            "receipt_redacted_before_review": bool(receipt_readback.get("redacted")),
            "does_not_execute_decision": True,
            "does_not_write_memory": True,
            "does_not_write_feedback": True,
            "does_not_send_chat": True,
            "does_not_call_model": True,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
        "next_smallest_truthful_gap": (
            "stage7_context_feedback_memory_assistance_terminal_context_signal"
            if outcome_review_ready
            else "stage7_context_feedback_memory_assistance_operator_feedback_loop_decision_receipt_readback"
        ),
    }


@router.post("/context/feedback/memory-assistance-feedback-loop-live-sample-operator-decision")
def context_feedback_memory_assistance_operator_feedback_loop_live_sample_operator_decision_record(
    payload: TelemetryContextFeedbackMemoryAssistanceLiveSampleOperatorDecisionIn,
) -> dict[str, Any]:
    route = "/telemetry/context/feedback/memory-assistance-feedback-loop-live-sample-operator-decision"
    permission = _write_permission(
        payload.actor,
        required_scope=TELEMETRY_CONTEXT_FEEDBACK_WRITE_SCOPE,
        route=route,
        method="POST",
    )
    if not permission.allowed:
        return _permission_denied(
            permission,
            source_id="telemetry_context",
            required_scope=TELEMETRY_CONTEXT_FEEDBACK_WRITE_SCOPE,
            next_step="configure_telemetry_context_feedback_write_scope_before_live_sample_operator_decision",
        )

    review = context_feedback_memory_assistance_operator_feedback_loop_live_sample_operator_review(limit=payload.limit)
    if not review.get("operator_review_ready"):
        return {
            "ok": True,
            "kind": "francis.stage7.telemetry.context_feedback_memory_assistance_live_sample_operator_decision.record",
            "status": "awaiting_live_sample_evidence",
            "source_id": "telemetry_context",
            "target": "feedback_memory_assistance_prompt_integration",
            "review": review,
            "receipt": None,
            "receipt_id": "",
            "writes_receipt": False,
            "writes_memory": False,
            "writes_feedback": False,
            "sends_chat": False,
            "calls_model": False,
            "selects_tools": False,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
            "governance": {
                "required_scope": TELEMETRY_CONTEXT_FEEDBACK_WRITE_SCOPE,
                "explicit_operator_decision": True,
                "does_not_record_when_review_not_ready": True,
                "grants_execution_authority": False,
                "grants_mutation_authority": False,
            },
            "next_smallest_truthful_gap": "stage7_context_feedback_memory_assistance_operator_feedback_loop_live_sample_run",
        }

    receipt = record_feedback_memory_assistance_live_sample_operator_decision(
        actor=payload.actor,
        reason=payload.reason,
        decision=payload.decision,
        notes=payload.notes,
        review=review,
    )
    return {
        "ok": True,
        "kind": "francis.stage7.telemetry.context_feedback_memory_assistance_live_sample_operator_decision.record",
        "status": "recorded",
        "source_id": "telemetry_context",
        "target": "feedback_memory_assistance_prompt_integration",
        "review": review,
        "receipt": receipt,
        "receipt_id": receipt.get("receipt_id", ""),
        "decision": receipt.get("decision", ""),
        "writes_receipt": True,
        "writes_memory": False,
        "writes_feedback": False,
        "sends_chat": False,
        "calls_model": False,
        "selects_tools": False,
        "trains_model": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "governance": {
            "required_scope": TELEMETRY_CONTEXT_FEEDBACK_WRITE_SCOPE,
            "explicit_operator_decision": True,
            "receipt_redacted_before_storage": True,
            "telemetry_is_untrusted_input": True,
            "does_not_write_memory": True,
            "does_not_write_feedback": True,
            "does_not_send_chat": True,
            "does_not_call_model": True,
            "does_not_select_tools": True,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
        "next_smallest_truthful_gap": "stage7_context_feedback_memory_assistance_operator_feedback_loop_decision_receipt_readback",
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
        "next_smallest_truthful_gap": "stage7_context_feedback_memory_assistance_operator_feedback_loop_live_sample_run",
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


@router.post("/context/feedback/memory-assistance-feedback-memory-quality")
def context_feedback_memory_assistance_operator_feedback_memory_quality_record(
    payload: TelemetryContextFeedbackMemoryQualityIn,
) -> dict[str, Any]:
    route = "/telemetry/context/feedback/memory-assistance-feedback-memory-quality"
    permission = _write_permission(
        payload.actor,
        required_scope=MEMORY_TIMELINE_WRITE_SCOPE,
        route=route,
        method="POST",
    )
    if not permission.allowed:
        return _permission_denied(
            permission,
            source_id="telemetry_context",
            required_scope=MEMORY_TIMELINE_WRITE_SCOPE,
            next_step="configure_memory_timeline_write_actor_scope_before_recording_feedback_memory_assistance_quality",
        )

    quality = telemetry_context_feedback_memory_assistance_operator_feedback_memory_quality(limit=payload.limit)
    candidate = quality.get("memory_write_candidate") if isinstance(quality.get("memory_write_candidate"), dict) else {}
    if not candidate:
        return {
            "ok": True,
            "kind": "francis.stage7.telemetry.context_feedback_memory_assistance_operator_feedback_memory_quality.record",
            "status": "empty",
            "source_id": "telemetry_context",
            "quality": quality,
            "memory_event": None,
            "writes_memory": False,
            "governance": {
                "required_scope": MEMORY_TIMELINE_WRITE_SCOPE,
                "explicit_operator_decision": True,
                "empty_review_does_not_write_memory": True,
                "target": "feedback_memory_assistance_prompt_integration",
                "grants_execution_authority": False,
                "grants_mutation_authority": False,
            },
        }

    event_payload = dict(candidate)
    if payload.event_id:
        event_payload["id"] = payload.event_id
    event_payload["request_actor"] = payload.actor
    event_payload["actor"] = payload.actor
    event_payload["scope"] = "telemetry.context.feedback_memory_assistance"
    event_payload["severity"] = "info"
    candidate_meta = candidate.get("meta")
    event_meta = dict(candidate_meta) if isinstance(candidate_meta, dict) else {}
    event_meta.update(
        {
            "reason": payload.reason,
            "source_id": "telemetry_context",
            "explicit_operator_decision": True,
            "target": "feedback_memory_assistance_prompt_integration",
            "feedback_memory_assistance_operator_feedback_memory_quality_route": route,
        }
    )
    event_payload["meta"] = event_meta
    memory_event = record_memory_timeline_payload(
        event_payload,
        route=route,
        method="POST",
    )
    if not memory_event.get("ok"):
        return {
            "ok": False,
            "kind": "francis.stage7.telemetry.context_feedback_memory_assistance_operator_feedback_memory_quality.record",
            "status": "denied",
            "source_id": "telemetry_context",
            "quality": quality,
            "memory_event": memory_event,
            "writes_memory": False,
            "governance": {
                "required_scope": MEMORY_TIMELINE_WRITE_SCOPE,
                "explicit_operator_decision": True,
                "memory_timeline_contract_enforced": True,
                "target": "feedback_memory_assistance_prompt_integration",
                "grants_execution_authority": False,
                "grants_mutation_authority": False,
            },
        }

    return {
        "ok": True,
        "kind": "francis.stage7.telemetry.context_feedback_memory_assistance_operator_feedback_memory_quality.record",
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
            "target": "feedback_memory_assistance_prompt_integration",
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


def _feedback_memory_assistance_live_chat_evidence(*, limit: int) -> dict[str, Any]:
    for entry in reversed(conversation_ledger_tail(max(20, min(limit * 4, 200)))):
        if not isinstance(entry, dict) or entry.get("role") != "assistant":
            continue
        meta_value = entry.get("meta")
        meta: dict[str, Any] = meta_value if isinstance(meta_value, dict) else {}
        telemetry_context_value = meta.get("telemetry_context")
        telemetry_context: dict[str, Any] = telemetry_context_value if isinstance(telemetry_context_value, dict) else {}
        assistance_value = telemetry_context.get("feedback_memory_assistance_prompt_integration")
        assistance: dict[str, Any] = assistance_value if isinstance(assistance_value, dict) else {}
        if not assistance or assistance.get("applies_to_chat_now") is not True:
            continue
        return {
            "status": _redacted_line_text(assistance.get("status")) or "applied",
            "target": _redacted_line_text(assistance.get("target")) or "telemetry_context.prompt_lines",
            "source_route": _redacted_line_text(assistance.get("source_route")),
            "line_count": _safe_count(assistance.get("line_count")),
            "api_actor": _redacted_line_text(meta.get("api_actor")),
            "mode": _redacted_line_text(meta.get("mode")),
            "feedback_target_present": isinstance(assistance.get("feedback_target"), dict)
            and bool(assistance.get("feedback_target")),
            "telemetry_is_untrusted_input": bool(assistance.get("telemetry_is_untrusted_input")),
            "redacted_context_lines": bool(assistance.get("redacted_context_lines")),
        }
    return {}


def _feedback_memory_assistance_live_feedback_evidence(*, limit: int) -> dict[str, Any]:
    for item in reversed(read_telemetry_context_feedback(limit=max(20, min(limit * 4, 200)))):
        if not isinstance(item, dict) or not _is_feedback_memory_assistance_feedback_item(item):
            continue
        meta_value = item.get("meta")
        meta: dict[str, Any] = meta_value if isinstance(meta_value, dict) else {}
        return {
            "feedback_id": _redacted_line_text(item.get("feedback_id")),
            "context_id": _redacted_line_text(item.get("context_id")),
            "message_id": _redacted_line_text(item.get("message_id")),
            "surface": _redacted_line_text(item.get("surface")),
            "rating": _redacted_line_text(item.get("rating")),
            "reply_mode": _redacted_line_text(item.get("reply_mode")),
            "source_ids": _safe_string_list(item.get("source_ids"), limit=5),
            "tags": _safe_string_list(item.get("tags"), limit=8),
            "target": _redacted_line_text(meta.get("feedback_target_kind"))
            or "feedback_memory_assistance_prompt_integration",
            "line_count": _safe_count(meta.get("line_count")),
            "recorded_ts": _safe_count(item.get("recorded_ts")),
        }
    return {}


def _feedback_memory_assistance_live_memory_evidence(*, limit: int) -> dict[str, Any]:
    memory_readback = context_feedback_memory_assistance_operator_feedback_memory_readback(limit=limit)
    raw_items_value = memory_readback.get("items")
    raw_items: list[Any] = raw_items_value if isinstance(raw_items_value, list) else []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        payload_value = item.get("payload")
        payload: dict[str, Any] = payload_value if isinstance(payload_value, dict) else {}
        return {
            "event_id": _redacted_line_text(item.get("id")),
            "kind": _redacted_line_text(item.get("kind")),
            "action_type": _redacted_line_text(item.get("action_type")),
            "classification": _redacted_line_text(item.get("classification")),
            "target": _redacted_line_text(payload.get("target")) or "feedback_memory_assistance_prompt_integration",
            "reviewed_event_count": _safe_count(payload.get("reviewed_event_count")),
            "rating_counts": payload.get("rating_counts") if isinstance(payload.get("rating_counts"), dict) else {},
            "reads_memory": True,
        }
    return {}


def _is_feedback_memory_assistance_feedback_item(item: dict[str, Any]) -> bool:
    source_ids = set(_safe_string_list(item.get("source_ids"), limit=10))
    tags = set(_safe_string_list(item.get("tags"), limit=10))
    meta_value = item.get("meta")
    meta: dict[str, Any] = meta_value if isinstance(meta_value, dict) else {}
    reply_mode = _redacted_line_text(item.get("reply_mode"))
    target_kind = _redacted_line_text(meta.get("feedback_target_kind"))
    return (
        "feedback_memory_assistance" in source_ids
        or "feedback_memory_assistance" in tags
        or reply_mode.startswith("feedback_memory_assistance_prompt_context")
        or target_kind == "feedback_memory_assistance_prompt_integration"
    )


def _safe_string_list(value: Any, *, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_redacted_line_text(item) for item in value[:limit] if _redacted_line_text(item)]


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
            "grants_execution_authority": False,
            "grants_memory_write_authority": False,
            "grants_mutation_authority": False,
        },
    }


def _permission_projection(decision: ApiPermissionDecision) -> dict[str, Any]:
    return {"allowed": decision.allowed, "reason": decision.reason, "evidence": decision.evidence}
