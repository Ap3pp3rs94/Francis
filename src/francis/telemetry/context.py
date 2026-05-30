from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

from francis.kernel.paths import data_dir
from francis.telemetry.audit import record as audit_record
from francis.telemetry.status import STAGE7_TELEMETRY_STAGE, redact_telemetry_value, telemetry_status_snapshot

TELEMETRY_CONTEXT_KIND = "francis.stage7.telemetry.context"
TELEMETRY_CONTEXT_FEEDBACK_KIND = "francis.stage7.telemetry.context_feedback"
TELEMETRY_CONTEXT_FEEDBACK_EVENTS_KIND = "francis.stage7.telemetry.context_feedback_events"
TELEMETRY_CONTEXT_FEEDBACK_REVIEW_KIND = "francis.stage7.telemetry.context_feedback_review"
TELEMETRY_CONTEXT_FEEDBACK_MEMORY_QUALITY_KIND = "francis.stage7.telemetry.context_feedback_memory_quality"
TELEMETRY_CONTEXT_FEEDBACK_MEMORY_ASSISTANCE_OPERATOR_REVIEW_KIND = (
    "francis.stage7.telemetry.context_feedback_memory_assistance_operator_feedback_review"
)
TELEMETRY_CONTEXT_FEEDBACK_MEMORY_ASSISTANCE_OPERATOR_MEMORY_QUALITY_KIND = (
    "francis.stage7.telemetry.context_feedback_memory_assistance_operator_feedback_memory_quality"
)
TELEMETRY_CONTEXT_FEEDBACK_MEMORY_RETRIEVAL_POLICY_KIND = (
    "francis.stage7.telemetry.context_feedback_memory_retrieval_policy"
)
TELEMETRY_CONTEXT_FEEDBACK_MEMORY_ASSISTANCE_POLICY_KIND = (
    "francis.stage7.telemetry.context_feedback_memory_assistance_policy"
)
TELEMETRY_CONTEXT_FEEDBACK_MEMORY_ASSISTANCE_CHAT_CONTEXT_CONTRACT_KIND = (
    "francis.stage7.telemetry.context_feedback_memory_assistance_chat_context_contract"
)
TELEMETRY_CONTEXT_FEEDBACK_MEMORY_ASSISTANCE_LIVE_SAMPLE_OPERATOR_DECISION_KIND = (
    "francis.stage7.telemetry.context_feedback_memory_assistance_live_sample_operator_decision_receipt"
)
STAGE7_OPERATOR_STAGE_CLOSURE_DECISION_KIND = "francis.stage7.telemetry.stage7_operator_stage_closure_decision_receipt"
TELEMETRY_CONTEXT_FEEDBACK_WRITE_SCOPE = "telemetry.context.feedback.write"
STAGE7_OPERATOR_STAGE_CLOSURE_WRITE_SCOPE = "telemetry.stage7.closure.write"
MEMORY_TIMELINE_WRITE_SCOPE = "memory.timeline.write"
_MAX_CONTEXT_ITEMS = 12
_MAX_PATHS = 5
_MAX_LIMIT = 100
_MAX_TEXT_LENGTH = 2_000
_MAX_TAGS = 16
_NEXT_CONTEXT_FEEDBACK_GAP = "stage7_context_feedback_memory_assistance_operator_feedback_loop_live_sample_run"


def telemetry_context_snapshot(*, surface: Any = "assist") -> dict[str, Any]:
    status = telemetry_status_snapshot()
    raw_sources = status.get("sources")
    sources: list[Any] = raw_sources if isinstance(raw_sources, list) else []
    context_items = _context_items(sources)
    prompt_lines = _prompt_lines(context_items)
    feedback_count = telemetry_context_feedback_count()

    return {
        "ok": True,
        "kind": TELEMETRY_CONTEXT_KIND,
        "context_id": f"tel_ctx_{uuid.uuid4().hex[:12]}",
        "stage": STAGE7_TELEMETRY_STAGE,
        "surface": _redact_text(surface),
        "status": "available" if context_items else "empty",
        "source_status": status.get("status", "unknown"),
        "claim": status.get("claim", ""),
        "active": bool(status.get("active")),
        "source_total": _safe_int(status.get("source_total"), 0),
        "active_source_total": _safe_int(status.get("active_source_total"), 0),
        "event_count": _safe_int(_safe_dict(status.get("retention")).get("event_count"), 0),
        "context_items": context_items,
        "prompt_lines": prompt_lines,
        "visible_indicator": True,
        "hidden_sensing": False,
        "redacted": True,
        "stores_raw_events": False,
        "feedback": {
            "status": "available",
            "event_count": feedback_count,
            "write_route": "/telemetry/context/feedback",
            "read_route": "/telemetry/context/feedback",
            "review_route": "/telemetry/context/feedback/review",
            "required_scope": TELEMETRY_CONTEXT_FEEDBACK_WRITE_SCOPE,
        },
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "governance": {
            "read_only": True,
            "on_request_only": True,
            "source_status_route": "/telemetry/status",
            "telemetry_is_untrusted_input": True,
            "requires_visible_indicator": True,
            "hidden_sensing": False,
            "does_not_expand_collection_scope": True,
            "grants_execution_authority": False,
            "grants_memory_write_authority": False,
        },
        "next_smallest_truthful_gap": _NEXT_CONTEXT_FEEDBACK_GAP,
    }


def record_telemetry_context_feedback(
    *,
    actor: Any,
    reason: Any = "",
    context_id: Any = "",
    surface: Any = "",
    rating: Any = "",
    message_id: Any = "",
    reply_mode: Any = "",
    notes: Any = "",
    source_ids: Any = None,
    tags: Any = None,
    meta: Any = None,
) -> dict[str, Any]:
    feedback_id = f"tel_ctx_feedback_{uuid.uuid4().hex[:12]}"
    payload = {
        "ok": True,
        "kind": TELEMETRY_CONTEXT_FEEDBACK_KIND,
        "feedback_id": feedback_id,
        "stage": STAGE7_TELEMETRY_STAGE,
        "source_id": "telemetry_context",
        "capture_mode": "explicit_operator_feedback",
        "hidden_sensing": False,
        "visible_indicator": True,
        "actor": _redact_text(actor),
        "reason": _redact_text(reason),
        "context_id": _redact_text(context_id),
        "surface": _redact_text(surface),
        "rating": _safe_rating(rating),
        "message_id": _redact_text(message_id),
        "reply_mode": _redact_text(reply_mode),
        "notes": _redact_text(notes)[:_MAX_TEXT_LENGTH],
        "source_ids": _safe_text_list(source_ids, limit=_MAX_CONTEXT_ITEMS),
        "tags": _safe_text_list(tags, limit=_MAX_TAGS),
        "meta": _feedback_meta(meta or {}),
        "recorded_ts": _now_s(),
        "governance": {
            "permission_scope": TELEMETRY_CONTEXT_FEEDBACK_WRITE_SCOPE,
            "redacted_before_storage": True,
            "telemetry_is_untrusted_input": True,
            "stores_prompt_body": False,
            "stores_model_response": False,
            "trains_model": False,
            "grants_execution_authority": False,
            "grants_memory_write_authority": False,
        },
    }
    _append_line(_feedback_path(), payload)
    audit_record(
        "telemetry.context.feedback_recorded",
        actor=payload["actor"],
        reason=payload["reason"],
        feedback_id=feedback_id,
        context_id=payload["context_id"],
        rating=payload["rating"],
        surface=payload["surface"],
    )
    return payload


def telemetry_context_feedback_snapshot(*, limit: int = 20) -> dict[str, Any]:
    safe_limit = _safe_limit(limit)
    items = read_telemetry_context_feedback(limit=safe_limit)
    return {
        "ok": True,
        "kind": TELEMETRY_CONTEXT_FEEDBACK_EVENTS_KIND,
        "stage": STAGE7_TELEMETRY_STAGE,
        "source_id": "telemetry_context",
        "items": items,
        "count": len(items),
        "total": telemetry_context_feedback_count(),
        "limit": safe_limit,
        "redacted": True,
        "hidden_sensing": False,
        "stores_prompt_body": False,
        "stores_model_response": False,
        "trains_model": False,
        "grants_execution_authority": False,
        "grants_memory_write_authority": False,
        "governance": {
            "capture_mode": "explicit_operator_feedback",
            "permission_scope": TELEMETRY_CONTEXT_FEEDBACK_WRITE_SCOPE,
            "redacted_before_storage": True,
            "telemetry_is_untrusted_input": True,
            "stores_prompt_body": False,
            "stores_model_response": False,
            "trains_model": False,
            "grants_execution_authority": False,
            "grants_memory_write_authority": False,
        },
    }


def record_feedback_memory_assistance_live_sample_operator_decision(
    *,
    actor: Any,
    reason: Any,
    decision: Any,
    review: dict[str, Any],
    notes: Any = "",
) -> dict[str, Any]:
    safe_decision = _safe_operator_decision(decision)
    receipt_id = f"tel_fma_live_decision_{uuid.uuid4().hex[:12]}"
    payload = {
        "ok": True,
        "kind": TELEMETRY_CONTEXT_FEEDBACK_MEMORY_ASSISTANCE_LIVE_SAMPLE_OPERATOR_DECISION_KIND,
        "receipt_id": receipt_id,
        "stage": STAGE7_TELEMETRY_STAGE,
        "source_id": "telemetry_context",
        "capture_mode": "explicit_operator_live_sample_review_decision",
        "target": "feedback_memory_assistance_prompt_integration",
        "actor": _redact_text(actor),
        "reason": _redact_text(reason),
        "decision": safe_decision,
        "notes": _redact_text(notes)[:_MAX_TEXT_LENGTH],
        "review_status": _redact_text(review.get("status")),
        "operator_review_ready": bool(review.get("operator_review_ready")),
        "live_sample_observed": bool(review.get("live_sample_observed")),
        "ready_count": _safe_int(review.get("ready_count"), 0),
        "required_count": _safe_int(review.get("required_count"), 0),
        "recorded_ts": _now_s(),
        "governance": {
            "permission_scope": TELEMETRY_CONTEXT_FEEDBACK_WRITE_SCOPE,
            "explicit_operator_decision": True,
            "redacted_before_storage": True,
            "telemetry_is_untrusted_input": True,
            "stores_prompt_body": False,
            "stores_model_response": False,
            "trains_model": False,
            "grants_execution_authority": False,
            "grants_memory_write_authority": False,
            "grants_mutation_authority": False,
        },
    }
    _append_line(_live_sample_operator_decision_path(), payload)
    audit_record(
        "telemetry.context.feedback_memory_assistance.live_sample_operator_decision_recorded",
        actor=payload["actor"],
        reason=payload["reason"],
        receipt_id=receipt_id,
        decision=safe_decision,
        target=payload["target"],
    )
    return payload


def read_feedback_memory_assistance_live_sample_operator_decisions(*, limit: int = 20) -> list[dict[str, Any]]:
    return _read_jsonl_tail(_live_sample_operator_decision_path(), limit=_safe_limit(limit))


def feedback_memory_assistance_live_sample_operator_decision_count() -> int:
    path = _live_sample_operator_decision_path()
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def record_stage7_operator_stage_closure_decision(
    *,
    actor: Any,
    reason: Any,
    decision: Any,
    review: dict[str, Any],
    notes: Any = "",
) -> dict[str, Any]:
    safe_decision = _safe_stage_closure_decision(decision)
    closure_ready = bool(review.get("memory_contract_operator_surface_ready"))
    stage7_closed_by_receipt = safe_decision == "close_stage7" and closure_ready
    receipt_id = f"tel_stage7_closure_{uuid.uuid4().hex[:12]}"
    payload = {
        "ok": True,
        "kind": STAGE7_OPERATOR_STAGE_CLOSURE_DECISION_KIND,
        "receipt_id": receipt_id,
        "stage": STAGE7_TELEMETRY_STAGE,
        "source_id": "telemetry_context",
        "capture_mode": "explicit_operator_stage_closure_decision",
        "target": "stage7_telemetry_mvp",
        "actor": _redact_text(actor),
        "reason": _redact_text(reason),
        "decision": safe_decision,
        "notes": _redact_text(notes)[:_MAX_TEXT_LENGTH],
        "review_status": _redact_text(review.get("status")),
        "memory_contract_operator_surface_ready": closure_ready,
        "ready_count": _safe_int(review.get("visible_section_count"), 0),
        "required_count": _safe_int(review.get("surface_section_count"), 0),
        "stage7_closed_by_receipt": stage7_closed_by_receipt,
        "marks_runtime_stage_state": False,
        "recorded_ts": _now_s(),
        "governance": {
            "permission_scope": STAGE7_OPERATOR_STAGE_CLOSURE_WRITE_SCOPE,
            "explicit_operator_decision": True,
            "stage_closure_decision": True,
            "redacted_before_storage": True,
            "telemetry_is_untrusted_input": True,
            "does_not_mutate_runtime_stage_state": True,
            "stores_prompt_body": False,
            "stores_model_response": False,
            "trains_model": False,
            "grants_execution_authority": False,
            "grants_memory_write_authority": False,
            "grants_mutation_authority": False,
        },
    }
    _append_line(_stage7_operator_stage_closure_decision_path(), payload)
    audit_record(
        "telemetry.context.feedback_memory_assistance.stage7_closure_decision_recorded",
        actor=payload["actor"],
        reason=payload["reason"],
        receipt_id=receipt_id,
        decision=safe_decision,
        target=payload["target"],
        stage7_closed_by_receipt=stage7_closed_by_receipt,
    )
    return payload


def read_stage7_operator_stage_closure_decisions(*, limit: int = 20) -> list[dict[str, Any]]:
    return _read_jsonl_tail(_stage7_operator_stage_closure_decision_path(), limit=_safe_limit(limit))


def stage7_operator_stage_closure_decision_count() -> int:
    path = _stage7_operator_stage_closure_decision_path()
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def telemetry_context_feedback_review(*, limit: int = 100) -> dict[str, Any]:
    safe_limit = _safe_limit(limit)
    items = read_telemetry_context_feedback(limit=safe_limit)
    rating_counts = {"useful": 0, "not_useful": 0, "neutral": 0}
    source_counts: dict[str, int] = {}
    tag_counts: dict[str, int] = {}
    for item in items:
        rating = _safe_rating(item.get("rating"))
        rating_counts[rating] += 1
        for source_id in _safe_text_list(item.get("source_ids"), limit=_MAX_CONTEXT_ITEMS):
            source_counts[source_id] = source_counts.get(source_id, 0) + 1
        for tag in _safe_text_list(item.get("tags"), limit=_MAX_TAGS):
            tag_counts[tag] = tag_counts.get(tag, 0) + 1

    total = telemetry_context_feedback_count()
    return {
        "ok": True,
        "kind": TELEMETRY_CONTEXT_FEEDBACK_REVIEW_KIND,
        "stage": STAGE7_TELEMETRY_STAGE,
        "source_id": "telemetry_context",
        "status": "review_ready" if items else "empty",
        "capture_mode": "explicit_operator_feedback_review",
        "reviewed_event_count": len(items),
        "total": total,
        "limit": safe_limit,
        "truncated": total > len(items),
        "rating_counts": rating_counts,
        "source_counts": _bounded_count_map(source_counts, limit=_MAX_CONTEXT_ITEMS),
        "tag_counts": _bounded_count_map(tag_counts, limit=_MAX_TAGS),
        "quality_signals": _feedback_quality_signals(rating_counts, reviewed_event_count=len(items)),
        "latest_feedback": _feedback_review_item(items[-1]) if items else {},
        "redacted": True,
        "hidden_sensing": False,
        "stores_prompt_body": False,
        "stores_model_response": False,
        "trains_model": False,
        "writes_memory": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "governance": {
            "read_only": True,
            "on_request_only": True,
            "capture_mode": "explicit_operator_feedback",
            "uses_explicit_operator_feedback_only": True,
            "redacted_before_storage": True,
            "telemetry_is_untrusted_input": True,
            "stores_prompt_body": False,
            "stores_model_response": False,
            "trains_model": False,
            "grants_execution_authority": False,
            "grants_memory_write_authority": False,
        },
        "next_smallest_truthful_gap": _NEXT_CONTEXT_FEEDBACK_GAP,
    }


def telemetry_context_feedback_memory_assistance_operator_feedback_review(*, limit: int = 100) -> dict[str, Any]:
    safe_limit = _safe_limit(limit)
    items = [
        item
        for item in read_telemetry_context_feedback(limit=_MAX_LIMIT)
        if _is_feedback_memory_assistance_feedback(item)
    ][-safe_limit:]
    rating_counts = {"useful": 0, "not_useful": 0, "neutral": 0}
    source_counts: dict[str, int] = {}
    tag_counts: dict[str, int] = {}
    for item in items:
        rating = _safe_rating(item.get("rating"))
        rating_counts[rating] += 1
        for source_id in _safe_text_list(item.get("source_ids"), limit=_MAX_CONTEXT_ITEMS):
            source_counts[source_id] = source_counts.get(source_id, 0) + 1
        for tag in _safe_text_list(item.get("tags"), limit=_MAX_TAGS):
            tag_counts[tag] = tag_counts.get(tag, 0) + 1

    return {
        "ok": True,
        "kind": TELEMETRY_CONTEXT_FEEDBACK_MEMORY_ASSISTANCE_OPERATOR_REVIEW_KIND,
        "stage": STAGE7_TELEMETRY_STAGE,
        "source_id": "telemetry_context",
        "status": "review_ready" if items else "empty",
        "capture_mode": "explicit_operator_feedback_review",
        "target": "feedback_memory_assistance_prompt_integration",
        "reviewed_event_count": len(items),
        "limit": safe_limit,
        "rating_counts": rating_counts,
        "source_counts": _bounded_count_map(source_counts, limit=_MAX_CONTEXT_ITEMS),
        "tag_counts": _bounded_count_map(tag_counts, limit=_MAX_TAGS),
        "quality_signals": _feedback_memory_assistance_quality_signals(
            rating_counts,
            reviewed_event_count=len(items),
        ),
        "latest_feedback": _feedback_memory_assistance_review_item(items[-1]) if items else {},
        "redacted": True,
        "hidden_sensing": False,
        "stores_prompt_body": False,
        "stores_model_response": False,
        "trains_model": False,
        "writes_memory": False,
        "calls_model": False,
        "selects_tools": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "governance": {
            "read_only": True,
            "on_request_only": True,
            "capture_mode": "explicit_operator_feedback",
            "uses_explicit_operator_feedback_only": True,
            "target": "feedback_memory_assistance_prompt_integration",
            "redacted_before_storage": True,
            "telemetry_is_untrusted_input": True,
            "stores_prompt_body": False,
            "stores_model_response": False,
            "trains_model": False,
            "writes_memory": False,
            "calls_model": False,
            "selects_tools": False,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
        "next_smallest_truthful_gap": _NEXT_CONTEXT_FEEDBACK_GAP,
    }


def telemetry_context_feedback_memory_quality(*, limit: int = 100) -> dict[str, Any]:
    safe_limit = _safe_limit(limit)
    review = telemetry_context_feedback_review(limit=safe_limit)
    reviewed_event_count = _safe_int(review.get("reviewed_event_count"), 0)
    candidate = _feedback_memory_write_candidate(review) if reviewed_event_count > 0 else {}
    return {
        "ok": True,
        "kind": TELEMETRY_CONTEXT_FEEDBACK_MEMORY_QUALITY_KIND,
        "stage": STAGE7_TELEMETRY_STAGE,
        "source_id": "telemetry_context",
        "status": "memory_candidate_ready" if candidate else "empty",
        "capture_mode": "explicit_operator_feedback_memory_quality_review",
        "review": review,
        "memory_write_candidate": candidate,
        "memory_write_route": "/memory/timeline/record",
        "memory_quality_record_route": "/telemetry/context/feedback/memory-quality",
        "required_scope": MEMORY_TIMELINE_WRITE_SCOPE,
        "operator_decision_required": bool(candidate),
        "writes_memory": False,
        "redacted": True,
        "hidden_sensing": False,
        "stores_prompt_body": False,
        "stores_model_response": False,
        "trains_model": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "governance": {
            "read_only": True,
            "on_request_only": True,
            "uses_explicit_operator_feedback_only": True,
            "telemetry_is_untrusted_input": True,
            "candidate_only": True,
            "operator_decision_required_before_memory_write": True,
            "redacted_before_storage": True,
            "stores_prompt_body": False,
            "stores_model_response": False,
            "trains_model": False,
            "writes_memory": False,
            "grants_execution_authority": False,
            "grants_memory_write_authority": False,
        },
        "next_smallest_truthful_gap": _NEXT_CONTEXT_FEEDBACK_GAP,
    }


def telemetry_context_feedback_memory_assistance_operator_feedback_memory_quality(
    *,
    limit: int = 100,
) -> dict[str, Any]:
    safe_limit = _safe_limit(limit)
    review = telemetry_context_feedback_memory_assistance_operator_feedback_review(limit=safe_limit)
    reviewed_event_count = _safe_int(review.get("reviewed_event_count"), 0)
    candidate = _feedback_memory_assistance_operator_memory_write_candidate(review) if reviewed_event_count > 0 else {}
    return {
        "ok": True,
        "kind": TELEMETRY_CONTEXT_FEEDBACK_MEMORY_ASSISTANCE_OPERATOR_MEMORY_QUALITY_KIND,
        "stage": STAGE7_TELEMETRY_STAGE,
        "source_id": "telemetry_context",
        "status": "memory_candidate_ready" if candidate else "empty",
        "capture_mode": "explicit_feedback_memory_assistance_operator_feedback_memory_quality_review",
        "target": "feedback_memory_assistance_prompt_integration",
        "review": review,
        "memory_write_candidate": candidate,
        "memory_write_route": "/memory/timeline/record",
        "memory_quality_record_route": ("/telemetry/context/feedback/memory-assistance-feedback-memory-quality"),
        "required_scope": MEMORY_TIMELINE_WRITE_SCOPE,
        "operator_decision_required": bool(candidate),
        "writes_memory": False,
        "redacted": True,
        "hidden_sensing": False,
        "stores_prompt_body": False,
        "stores_model_response": False,
        "trains_model": False,
        "calls_model": False,
        "selects_tools": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "governance": {
            "read_only": True,
            "on_request_only": True,
            "uses_explicit_operator_feedback_only": True,
            "target": "feedback_memory_assistance_prompt_integration",
            "telemetry_is_untrusted_input": True,
            "candidate_only": True,
            "operator_decision_required_before_memory_write": True,
            "redacted_before_storage": True,
            "stores_prompt_body": False,
            "stores_model_response": False,
            "trains_model": False,
            "calls_model": False,
            "selects_tools": False,
            "writes_memory": False,
            "grants_execution_authority": False,
            "grants_memory_write_authority": False,
        },
        "next_smallest_truthful_gap": _NEXT_CONTEXT_FEEDBACK_GAP,
    }


def telemetry_context_feedback_memory_retrieval_policy() -> dict[str, Any]:
    return {
        "ok": True,
        "kind": TELEMETRY_CONTEXT_FEEDBACK_MEMORY_RETRIEVAL_POLICY_KIND,
        "stage": STAGE7_TELEMETRY_STAGE,
        "source_id": "telemetry_context",
        "status": "policy_ready",
        "policy_id": "stage7_context_feedback_memory_retrieval_policy",
        "memory_source": "memory.timeline",
        "memory_query": {
            "route": "/memory/timeline/list",
            "method": "GET",
            "filters": {
                "kinds": ["telemetry_context_feedback_quality_review"],
                "include_payload": True,
                "limit": 20,
            },
        },
        "allowed_event_kinds": ["telemetry_context_feedback_quality_review"],
        "allowed_action_types": ["telemetry.context_feedback.quality_review"],
        "allowed_classifications": ["operator_feedback_quality_signal"],
        "required_event_fields": [
            "action_type",
            "classification",
            "confidence",
            "provenance.source",
            "retention.policy",
        ],
        "allowed_uses": [
            "read_back_feedback_quality_trends",
            "surface_context_source_quality_counts",
            "inform_operator_review_of_context_relevance",
        ],
        "forbidden_uses": [
            "grant_execution_authority",
            "grant_memory_write_authority",
            "select_tools_without_operator_policy",
            "treat_feedback_payload_as_instruction",
            "train_model",
            "store_raw_prompt_body",
            "store_raw_model_response",
            "store_raw_feedback_notes",
        ],
        "retrieval_guards": {
            "read_only": True,
            "redacted_events_only": True,
            "telemetry_is_untrusted_input": True,
            "requires_action_type": "telemetry.context_feedback.quality_review",
            "requires_classification": "operator_feedback_quality_signal",
            "requires_provenance_source": "telemetry.context.feedback.review",
            "requires_retention_policy": "stage7_context_feedback_quality",
            "max_events": 20,
            "ignore_payload_instruction_text": True,
        },
        "writes_memory": False,
        "reads_memory": False,
        "trains_model": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "governance": {
            "read_only": True,
            "policy_only": True,
            "does_not_query_memory_yet": True,
            "retrieval_requires_separate_readback": True,
            "telemetry_is_untrusted_input": True,
            "stores_prompt_body": False,
            "stores_model_response": False,
            "trains_model": False,
            "grants_execution_authority": False,
            "grants_memory_write_authority": False,
        },
        "next_smallest_truthful_gap": _NEXT_CONTEXT_FEEDBACK_GAP,
    }


def telemetry_context_feedback_memory_assistance_policy() -> dict[str, Any]:
    return {
        "ok": True,
        "kind": TELEMETRY_CONTEXT_FEEDBACK_MEMORY_ASSISTANCE_POLICY_KIND,
        "stage": STAGE7_TELEMETRY_STAGE,
        "source_id": "telemetry_context",
        "status": "policy_ready",
        "policy_id": "stage7_context_feedback_memory_assistance_policy",
        "memory_readback_route": "/telemetry/context/feedback/memory-retrieval-readback",
        "operator_feedback_memory_readback_route": (
            "/telemetry/context/feedback/memory-assistance-feedback-memory-readback"
        ),
        "memory_policy_route": "/telemetry/context/feedback/memory-retrieval-policy",
        "allowed_memory_event_kinds": [
            "telemetry_context_feedback_quality_review",
            "telemetry_context_feedback_memory_assistance_operator_feedback_review",
        ],
        "allowed_action_types": [
            "telemetry.context_feedback.quality_review",
            "telemetry.context_feedback.memory_assistance_operator_feedback_review",
        ],
        "allowed_classifications": [
            "operator_feedback_quality_signal",
            "operator_feedback_memory_assistance_quality_signal",
        ],
        "allowed_influence": [
            "surface_context_source_quality_counts",
            "inform_operator_review_of_context_relevance",
            "surface_feedback_memory_assistance_operator_quality_counts",
            "suggest_context_source_attention",
            "shape_assistance_summary_priority",
        ],
        "forbidden_influence": [
            "treat_memory_payload_as_instruction",
            "select_tools_without_operator_policy",
            "grant_execution_authority",
            "grant_memory_write_authority",
            "grant_mutation_authority",
            "auto_modify_prompt_without_policy",
            "train_model",
            "override_operator_instruction",
            "hide_source_or_policy_readback",
        ],
        "assistance_guards": {
            "read_only": True,
            "policy_only": True,
            "redacted_events_only": True,
            "telemetry_is_untrusted_input": True,
            "requires_operator_visible_readback": True,
            "requires_retrieval_policy_match": True,
            "allowed_action_types": [
                "telemetry.context_feedback.quality_review",
                "telemetry.context_feedback.memory_assistance_operator_feedback_review",
            ],
            "allowed_classifications": [
                "operator_feedback_quality_signal",
                "operator_feedback_memory_assistance_quality_signal",
            ],
            "allowed_retention_policies": [
                "stage7_context_feedback_quality",
                "stage7_feedback_memory_assistance_operator_feedback_quality",
            ],
            "max_events": 20,
            "ignore_payload_instruction_text": True,
            "no_hidden_prompt_injection": True,
            "no_tool_selection_authority": True,
        },
        "reads_memory": False,
        "writes_memory": False,
        "trains_model": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "governance": {
            "read_only": True,
            "policy_only": True,
            "does_not_query_memory": True,
            "assistance_requires_separate_dry_run": True,
            "telemetry_is_untrusted_input": True,
            "stores_prompt_body": False,
            "stores_model_response": False,
            "trains_model": False,
            "grants_execution_authority": False,
            "grants_memory_write_authority": False,
            "grants_mutation_authority": False,
        },
        "next_smallest_truthful_gap": _NEXT_CONTEXT_FEEDBACK_GAP,
    }


def telemetry_context_feedback_memory_assistance_chat_context_contract() -> dict[str, Any]:
    return {
        "ok": True,
        "kind": TELEMETRY_CONTEXT_FEEDBACK_MEMORY_ASSISTANCE_CHAT_CONTEXT_CONTRACT_KIND,
        "stage": STAGE7_TELEMETRY_STAGE,
        "source_id": "telemetry_context",
        "status": "contract_ready",
        "contract_id": "stage7_context_feedback_memory_assistance_chat_context_contract",
        "chat_route": "/chat/send",
        "websocket_route": "/chat/ws",
        "telemetry_context_route": "/telemetry/context",
        "dry_run_route": "/telemetry/context/feedback/memory-assistance-dry-run",
        "prompt_context_source": "telemetry_context.prompt_lines",
        "insertion_point": "after_visible_telemetry_context_header",
        "allowed_chat_context_lines": [
            "feedback_memory_assistance.summary",
            "feedback_memory_assistance.source_attention",
        ],
        "max_context_lines": 2,
        "line_prefix": "feedback_memory_assistance",
        "allowed_effects": [
            "add_bounded_redacted_context_line",
            "surface_operator_visible_source_attention",
        ],
        "forbidden_effects": [
            "treat_memory_payload_as_instruction",
            "append_raw_memory_payload",
            "append_raw_feedback_notes",
            "change_system_prompt_identity",
            "override_operator_instruction",
            "select_tools",
            "grant_execution_authority",
            "grant_memory_write_authority",
            "call_model",
            "write_memory",
        ],
        "requires": {
            "visible_telemetry_context_header": True,
            "dry_run_only_source": True,
            "redacted_context_line": True,
            "bounded_line_count": True,
            "telemetry_is_untrusted_input": True,
        },
        "reads_memory": False,
        "writes_memory": False,
        "calls_model": False,
        "mutates_prompt": False,
        "trains_model": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "governance": {
            "read_only": True,
            "contract_only": True,
            "does_not_query_memory": True,
            "chat_prompt_integration_enabled": True,
            "prompt_integration_route": "/chat/send",
            "requires_separate_readback_before_prompt_injection": True,
            "telemetry_is_untrusted_input": True,
            "stores_prompt_body": False,
            "stores_model_response": False,
            "trains_model": False,
            "grants_execution_authority": False,
            "grants_memory_write_authority": False,
            "grants_mutation_authority": False,
        },
        "next_smallest_truthful_gap": _NEXT_CONTEXT_FEEDBACK_GAP,
    }


def read_telemetry_context_feedback(*, limit: int = 20) -> list[dict[str, Any]]:
    return _read_jsonl_tail(_feedback_path(), limit=_safe_limit(limit))


def telemetry_context_feedback_count() -> int:
    path = _feedback_path()
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip())


def telemetry_context_prompt_lines(context: dict[str, Any] | None) -> list[str]:
    if not isinstance(context, dict):
        return []
    lines = context.get("prompt_lines")
    if not isinstance(lines, list):
        return []
    max_prompt_lines = _safe_int(context.get("max_prompt_lines"), _MAX_CONTEXT_ITEMS)
    limit = max(1, min(max_prompt_lines, _MAX_CONTEXT_ITEMS + 2))
    return [_redact_text(line).strip() for line in lines if _redact_text(line).strip()][:limit]


def _context_items(sources: list[Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for source in sources:
        if not isinstance(source, dict) or source.get("active") is not True:
            continue
        source_id = _redact_text(source.get("id"))
        if source_id == "terminal":
            item = _terminal_item(source)
        elif source_id == "git":
            item = _git_item(source)
        elif source_id == "ide_diagnostics":
            item = _ide_diagnostic_item(source)
        else:
            item = _generic_source_item(source)
        if item:
            items.append(item)
    return items[:_MAX_CONTEXT_ITEMS]


def _terminal_item(source: dict[str, Any]) -> dict[str, Any]:
    latest = _safe_dict(source.get("latest_event"))
    event_id = _redact_text(latest.get("event_id"))
    if not event_id:
        return _generic_source_item(source)
    item: dict[str, Any] = {
        "source_id": "terminal",
        "status": _redact_text(source.get("status")),
        "summary": _redact_text(f"latest terminal event {event_id}"),
        "event_id": event_id,
        "exit_code": latest.get("exit_code"),
        "operation_id": _redact_text(latest.get("operation_id")),
        "artifact_dir": _redact_text(latest.get("artifact_dir")),
    }
    command = _redact_text(latest.get("command"))
    if command:
        item["command"] = command
    return item


def _git_item(source: dict[str, Any]) -> dict[str, Any]:
    snapshot = _safe_dict(source.get("latest_snapshot"))
    branch = _redact_text(snapshot.get("branch"))
    changed_count = _safe_int(snapshot.get("changed_count"), 0)
    changed_paths = _changed_paths(snapshot.get("changed_paths"))
    return {
        "source_id": "git",
        "status": _redact_text(source.get("status")),
        "summary": _redact_text(f"git branch {branch or 'unknown'}, changed {changed_count}"),
        "branch": branch,
        "head": _redact_text(snapshot.get("head")),
        "upstream": _redact_text(snapshot.get("upstream")),
        "dirty": bool(snapshot.get("dirty")),
        "changed_count": changed_count,
        "changed_paths": changed_paths,
    }


def _ide_diagnostic_item(source: dict[str, Any]) -> dict[str, Any]:
    latest = _safe_dict(source.get("latest_diagnostic"))
    event_id = _redact_text(latest.get("event_id"))
    if not event_id:
        return _generic_source_item(source)
    diagnostic_count = _safe_int(latest.get("diagnostic_count"), 0)
    severity = _redact_text(latest.get("highest_severity")) or "unknown"
    file_path = _redact_text(latest.get("file"))
    return {
        "source_id": "ide_diagnostics",
        "status": _redact_text(source.get("status")),
        "summary": _redact_text(f"IDE diagnostics {severity}, count {diagnostic_count}"),
        "event_id": event_id,
        "file": file_path,
        "diagnostic_count": diagnostic_count,
        "highest_severity": severity,
        "operation_id": _redact_text(latest.get("operation_id")),
    }


def _generic_source_item(source: dict[str, Any]) -> dict[str, Any]:
    source_id = _redact_text(source.get("id"))
    status = _redact_text(source.get("status"))
    if not source_id:
        return {}
    return {
        "source_id": source_id,
        "status": status,
        "summary": _redact_text(f"{source_id} status {status or 'active'}"),
    }


def _prompt_lines(items: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for item in items:
        source_id = _redact_text(item.get("source_id"))
        summary = _redact_text(item.get("summary"))
        if not source_id or not summary:
            continue
        details: list[str] = []
        if source_id == "git":
            if item.get("dirty") is True:
                details.append("dirty")
            changed_count = _safe_int(item.get("changed_count"), 0)
            if changed_count:
                details.append(f"{changed_count} changed")
            paths = item.get("changed_paths") if isinstance(item.get("changed_paths"), list) else []
            if paths:
                path_text = ", ".join(_redact_text(_safe_dict(path).get("path")) for path in paths[:3])
                if path_text:
                    details.append(f"paths {path_text}")
        elif source_id == "terminal":
            exit_code = item.get("exit_code")
            if exit_code is not None:
                details.append(f"exit {exit_code}")
            command = _redact_text(item.get("command"))
            if command:
                details.append(f"command {command}")
        elif source_id == "ide_diagnostics":
            file_path = _redact_text(item.get("file"))
            if file_path:
                details.append(f"file {file_path}")
            severity = _redact_text(item.get("highest_severity"))
            if severity:
                details.append(f"severity {severity}")
        suffix = f"; {'; '.join(details)}" if details else ""
        lines.append(_redact_text(f"{source_id}: {summary}{suffix}"))
    return lines[:_MAX_CONTEXT_ITEMS]


def _changed_paths(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    paths: list[dict[str, str]] = []
    for item in value[:_MAX_PATHS]:
        record = _safe_dict(item)
        path = _redact_text(record.get("path")).strip()
        if not path:
            continue
        paths.append({"status": _redact_text(record.get("status")).strip(), "path": path})
    return paths


def _feedback_review_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "feedback_id": _redact_text(item.get("feedback_id")),
        "context_id": _redact_text(item.get("context_id")),
        "surface": _redact_text(item.get("surface")),
        "rating": _safe_rating(item.get("rating")),
        "source_ids": _safe_text_list(item.get("source_ids"), limit=_MAX_CONTEXT_ITEMS),
        "tags": _safe_text_list(item.get("tags"), limit=_MAX_TAGS),
        "recorded_ts": _safe_int(item.get("recorded_ts"), 0),
    }


def _feedback_memory_assistance_review_item(item: dict[str, Any]) -> dict[str, Any]:
    meta = _safe_dict(item.get("meta"))
    return {
        "feedback_id": _redact_text(item.get("feedback_id")),
        "context_id": _redact_text(item.get("context_id")),
        "surface": _redact_text(item.get("surface")),
        "rating": _safe_rating(item.get("rating")),
        "message_id": _redact_text(item.get("message_id")),
        "reply_mode": _redact_text(item.get("reply_mode")),
        "source_ids": _safe_text_list(item.get("source_ids"), limit=_MAX_CONTEXT_ITEMS),
        "tags": _safe_text_list(item.get("tags"), limit=_MAX_TAGS),
        "line_count": _safe_int(meta.get("line_count"), 0),
        "recorded_ts": _safe_int(item.get("recorded_ts"), 0),
    }


def _is_feedback_memory_assistance_feedback(item: dict[str, Any]) -> bool:
    source_ids = set(_safe_text_list(item.get("source_ids"), limit=_MAX_CONTEXT_ITEMS))
    tags = set(_safe_text_list(item.get("tags"), limit=_MAX_TAGS))
    reply_mode = _redact_text(item.get("reply_mode")).strip()
    meta = _safe_dict(item.get("meta"))
    target_kind = _redact_text(meta.get("feedback_target_kind")).strip()
    return (
        "feedback_memory_assistance" in source_ids
        or "feedback_memory_assistance" in tags
        or reply_mode == "feedback_memory_assistance_prompt_context"
        or target_kind == "feedback_memory_assistance_prompt_integration"
    )


def _feedback_quality_signals(rating_counts: dict[str, int], *, reviewed_event_count: int) -> list[str]:
    if reviewed_event_count <= 0:
        return ["no_explicit_context_feedback_recorded"]
    signals: list[str] = []
    if rating_counts["useful"] > 0:
        signals.append("operator_reported_useful_context")
    if rating_counts["not_useful"] > 0:
        signals.append("operator_reported_context_misses")
    if rating_counts["neutral"] > 0:
        signals.append("operator_reported_neutral_context")
    return signals


def _feedback_memory_assistance_quality_signals(
    rating_counts: dict[str, int],
    *,
    reviewed_event_count: int,
) -> list[str]:
    if reviewed_event_count <= 0:
        return ["no_feedback_memory_assistance_operator_feedback_recorded"]
    signals: list[str] = []
    if rating_counts["useful"] > 0:
        signals.append("operator_reported_useful_feedback_memory_assistance")
    if rating_counts["not_useful"] > 0:
        signals.append("operator_reported_feedback_memory_assistance_misses")
    if rating_counts["neutral"] > 0:
        signals.append("operator_reported_neutral_feedback_memory_assistance")
    return signals


def _feedback_memory_write_candidate(review: dict[str, Any]) -> dict[str, Any]:
    rating_counts = _safe_count_map(review.get("rating_counts"), allowed=("useful", "not_useful", "neutral"))
    source_counts = _safe_count_map(review.get("source_counts"), limit=_MAX_CONTEXT_ITEMS)
    tag_counts = _safe_count_map(review.get("tag_counts"), limit=_MAX_TAGS)
    quality_signals = _safe_text_list(review.get("quality_signals"), limit=_MAX_TAGS)
    latest_feedback = _safe_dict(review.get("latest_feedback"))
    reviewed_event_count = _safe_int(review.get("reviewed_event_count"), 0)
    total = _safe_int(review.get("total"), reviewed_event_count)
    misses = rating_counts.get("not_useful", 0)
    useful = rating_counts.get("useful", 0)
    neutral = rating_counts.get("neutral", 0)

    return {
        "kind": "telemetry_context_feedback_quality_review",
        "action_type": "telemetry.context_feedback.quality_review",
        "classification": "operator_feedback_quality_signal",
        "confidence": 0.75,
        "provenance": {
            "source": "telemetry.context.feedback.review",
            "capture_mode": "explicit_operator_feedback_review",
            "reviewed_event_count": reviewed_event_count,
            "total": total,
        },
        "retention": {
            "policy": "stage7_context_feedback_quality",
            "class": "quality_signal",
            "ttl_seconds": 2_592_000,
        },
        "title": "Telemetry context feedback quality review",
        "message": _redact_text(
            "Context feedback quality review: "
            f"{reviewed_event_count} explicit operator feedback event"
            f"{'' if reviewed_event_count == 1 else 's'}; "
            f"useful={useful}; misses={misses}; neutral={neutral}."
        ),
        "tags": _safe_text_list(
            ["stage7", "telemetry_context_feedback", "quality_review", *quality_signals],
            limit=_MAX_TAGS,
        ),
        "payload": {
            "rating_counts": rating_counts,
            "source_counts": source_counts,
            "tag_counts": tag_counts,
            "quality_signals": quality_signals,
            "latest_feedback": _feedback_review_item(latest_feedback) if latest_feedback else {},
            "redacted": True,
            "telemetry_is_untrusted_input": True,
        },
        "meta": {
            "source": "telemetry.context.feedback.review",
            "action_type": "telemetry.context_feedback.quality_review",
            "classification": "operator_feedback_quality_signal",
            "confidence": 0.75,
            "retention_policy": "stage7_context_feedback_quality",
            "retention_class": "quality_signal",
            "ttl_seconds": 2_592_000,
            "stores_prompt_body": False,
            "stores_model_response": False,
        },
        "memory_write_contract": {
            "would_satisfy_required_fields": True,
            "required_fields": [
                "action_type",
                "provenance.source",
                "classification",
                "confidence",
                "retention",
            ],
            "operator_decision_required": True,
            "write_route": "/memory/timeline/record",
            "required_scope": MEMORY_TIMELINE_WRITE_SCOPE,
        },
        "poisoning_guard": {
            "raw_notes_included": False,
            "raw_prompt_body_included": False,
            "raw_model_response_included": False,
            "telemetry_is_untrusted_input": True,
        },
        "writes_memory": False,
        "grants_memory_write_authority": False,
    }


def _feedback_memory_assistance_operator_memory_write_candidate(review: dict[str, Any]) -> dict[str, Any]:
    rating_counts = _safe_count_map(review.get("rating_counts"), allowed=("useful", "not_useful", "neutral"))
    source_counts = _safe_count_map(review.get("source_counts"), limit=_MAX_CONTEXT_ITEMS)
    tag_counts = _safe_count_map(review.get("tag_counts"), limit=_MAX_TAGS)
    quality_signals = _safe_text_list(review.get("quality_signals"), limit=_MAX_TAGS)
    latest_feedback = _safe_dict(review.get("latest_feedback"))
    reviewed_event_count = _safe_int(review.get("reviewed_event_count"), 0)
    misses = rating_counts.get("not_useful", 0)
    useful = rating_counts.get("useful", 0)
    neutral = rating_counts.get("neutral", 0)

    return {
        "kind": "telemetry_context_feedback_memory_assistance_operator_feedback_review",
        "action_type": "telemetry.context_feedback.memory_assistance_operator_feedback_review",
        "classification": "operator_feedback_memory_assistance_quality_signal",
        "confidence": 0.76,
        "provenance": {
            "source": "telemetry.context.feedback.memory_assistance_feedback_review",
            "capture_mode": "explicit_operator_feedback_review",
            "target": "feedback_memory_assistance_prompt_integration",
            "reviewed_event_count": reviewed_event_count,
        },
        "retention": {
            "policy": "stage7_feedback_memory_assistance_operator_feedback_quality",
            "class": "quality_signal",
            "ttl_seconds": 2_592_000,
        },
        "title": "Feedback-memory assistance operator feedback quality review",
        "message": _redact_text(
            "Feedback-memory assistance operator feedback quality review: "
            f"{reviewed_event_count} explicit targeted feedback event"
            f"{'' if reviewed_event_count == 1 else 's'}; "
            f"useful={useful}; misses={misses}; neutral={neutral}."
        ),
        "tags": _safe_text_list(
            [
                "stage7",
                "feedback_memory_assistance",
                "operator_feedback",
                "quality_review",
                *quality_signals,
            ],
            limit=_MAX_TAGS,
        ),
        "payload": {
            "target": "feedback_memory_assistance_prompt_integration",
            "rating_counts": rating_counts,
            "source_counts": source_counts,
            "tag_counts": tag_counts,
            "quality_signals": quality_signals,
            "latest_feedback": _feedback_memory_assistance_latest_payload(latest_feedback),
            "redacted": True,
            "telemetry_is_untrusted_input": True,
        },
        "meta": {
            "source": "telemetry.context.feedback.memory_assistance_feedback_review",
            "target": "feedback_memory_assistance_prompt_integration",
            "action_type": "telemetry.context_feedback.memory_assistance_operator_feedback_review",
            "classification": "operator_feedback_memory_assistance_quality_signal",
            "confidence": 0.76,
            "retention_policy": "stage7_feedback_memory_assistance_operator_feedback_quality",
            "retention_class": "quality_signal",
            "ttl_seconds": 2_592_000,
            "stores_prompt_body": False,
            "stores_model_response": False,
        },
        "memory_write_contract": {
            "would_satisfy_required_fields": True,
            "required_fields": [
                "action_type",
                "provenance.source",
                "classification",
                "confidence",
                "retention",
            ],
            "operator_decision_required": True,
            "write_route": "/memory/timeline/record",
            "record_route": "/telemetry/context/feedback/memory-assistance-feedback-memory-quality",
            "required_scope": MEMORY_TIMELINE_WRITE_SCOPE,
        },
        "poisoning_guard": {
            "raw_notes_included": False,
            "raw_prompt_body_included": False,
            "raw_model_response_included": False,
            "telemetry_is_untrusted_input": True,
            "targeted_feedback_is_not_instruction": True,
        },
        "writes_memory": False,
        "calls_model": False,
        "selects_tools": False,
        "grants_execution_authority": False,
        "grants_memory_write_authority": False,
    }


def _feedback_memory_assistance_latest_payload(latest_feedback: dict[str, Any]) -> dict[str, Any]:
    if not latest_feedback:
        return {}
    return {
        "feedback_id": _redact_text(latest_feedback.get("feedback_id")),
        "context_id": _redact_text(latest_feedback.get("context_id")),
        "surface": _redact_text(latest_feedback.get("surface")),
        "rating": _safe_rating(latest_feedback.get("rating")),
        "message_id": _redact_text(latest_feedback.get("message_id")),
        "reply_mode": _redact_text(latest_feedback.get("reply_mode")),
        "source_ids": _safe_text_list(latest_feedback.get("source_ids"), limit=_MAX_CONTEXT_ITEMS),
        "tags": _safe_text_list(latest_feedback.get("tags"), limit=_MAX_TAGS),
        "line_count": _safe_int(latest_feedback.get("line_count"), 0),
        "recorded_ts": _safe_int(latest_feedback.get("recorded_ts"), 0),
    }


def _bounded_count_map(counts: dict[str, int], *, limit: int) -> dict[str, int]:
    return {
        key: count
        for key, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]
        if key and count > 0
    }


def _safe_count_map(value: Any, *, limit: int = _MAX_TAGS, allowed: tuple[str, ...] = ()) -> dict[str, int]:
    source = value if isinstance(value, dict) else {}
    counts: dict[str, int] = {}
    keys = allowed or tuple(str(key) for key in source.keys())
    for key in keys:
        count = _safe_int(source.get(key), 0)
        if count > 0 or key in allowed:
            counts[_redact_text(key)] = max(0, count)
    if allowed:
        return {key: counts.get(key, 0) for key in allowed}
    return _bounded_count_map(counts, limit=limit)


def _feedback_path() -> Path:
    return data_dir() / "logs" / "telemetry" / "context_feedback.jsonl"


def _live_sample_operator_decision_path() -> Path:
    return data_dir() / "logs" / "telemetry" / "context_feedback_memory_assistance_live_sample_decisions.jsonl"


def _stage7_operator_stage_closure_decision_path() -> Path:
    return data_dir() / "logs" / "telemetry" / "stage7_operator_stage_closure_decisions.jsonl"


def _append_line(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str) + "\n")


def _read_jsonl_tail(path: Path, *, limit: int) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    items: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except Exception:
            continue
        if isinstance(payload, dict):
            items.append(payload)
    return items[-_safe_limit(limit) :]


def _redact_jsonable(value: Any) -> Any:
    return redact_telemetry_value(_coerce_jsonable(value))


def _feedback_meta(value: Any) -> dict[str, Any]:
    redacted = _redact_jsonable(value)
    if not isinstance(redacted, dict):
        return {}
    blocked_keys = {
        "message",
        "messages",
        "model_response",
        "prompt",
        "prompt_body",
        "response",
        "response_body",
    }
    return {key: item for key, item in redacted.items() if str(key).strip().lower() not in blocked_keys}


def _coerce_jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _coerce_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_coerce_jsonable(item) for item in value]
    return _safe_str(value)


def _safe_text_list(value: Any, *, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for item in value[:limit]:
        text = _redact_text(item).strip()
        if text:
            items.append(text[:_MAX_TEXT_LENGTH])
    return items


def _safe_rating(value: Any) -> str:
    text = _redact_text(value).strip().lower()
    if text in {"useful", "not_useful", "neutral"}:
        return text
    return "neutral"


def _safe_operator_decision(value: Any) -> str:
    text = _redact_text(value).strip().lower()
    normalized = text.replace("-", "_").replace(" ", "_")
    if normalized in {"accepted", "rejected", "needs_more_evidence"}:
        return normalized
    return "needs_more_evidence"


def _safe_stage_closure_decision(value: Any) -> str:
    text = _redact_text(value).strip().lower()
    normalized = text.replace("-", "_").replace(" ", "_")
    if normalized in {"close_stage7", "do_not_close_stage7", "needs_more_evidence"}:
        return normalized
    return "needs_more_evidence"


def _safe_limit(value: int) -> int:
    try:
        limit = int(value)
    except Exception:
        return 20
    if limit <= 0:
        return 20
    return min(limit, _MAX_LIMIT)


def _safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_int(value: Any, fallback: int) -> int:
    try:
        return int(value)
    except Exception:
        return fallback


def _redact_text(value: Any) -> str:
    redacted = redact_telemetry_value(_safe_str(value))
    return _safe_str(redacted)[:_MAX_TEXT_LENGTH]


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""


def _now_s() -> int:
    return int(time.time())
