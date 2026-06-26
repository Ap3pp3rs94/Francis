from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import time
from typing import Any, cast
from uuid import uuid4

from francis.chat.continuity.ledger import append
from francis.governance.redaction import redact_secret_text
from francis.kernel.paths import data_dir

from .body_map import compact_body_map_prompt_line, compact_roadmap_gate_prompt_line
from .collaboration import read_collaboration_transcript, submit_collaboration_prompt
from .collaboration_contract import (
    CONTEXT_CONTRACT_ID,
    append_context_contract_to_continuity,
    ensure_context_contract,
)
from .collaboration_review import latest_review_candidate_line
from .repo_tools import DeveloperBridgeError
from .trust_ladder import compact_trust_ladder_prompt_line

_STATE_KIND = "developer_bridge.collaboration_driver_state"
_INSIGHT_SCHEMA_VERSION = "developer_bridge_collaboration_insight_v1"
_LEARNING_SCHEMA_VERSION = "developer_bridge_collaboration_learning_v1"
_MAX_TRACKED_IDS = 500
_MAX_TURNS = 0
_DEFAULT_POLL_SECONDS = 2.0
_DEFAULT_TURN_GAP_SECONDS = 30.0
_DEFAULT_SUMMARY_EVERY_TURNS = 6
_MAX_DRIVER_PROMPT_CHARS = 700
_PROMPT_REVIEW_ID_LIMIT = 36
_PROMPT_REVIEW_SURFACE_LIMIT = 72

_TOPICS = (
    "the next Communication UI change that would reduce visible relay noise using existing receipt fields",
    "the exact review receipt a Codex implementation session should read before editing collaboration code",
    "which repo surface should convert typed or spoken user direction into an action candidate",
    "how to prove a local-model response is advice only before any Francis action-readiness claim",
    "which session-summary fields should be shown to the operator before any raw transcript is opened",
    "which local-model failure or drift signal should become a learning receipt",
    "what source-disagreement artifact should block build direction until reviewed",
    "which governance gate must be visible when model advice proposes action",
    "what toggle-state receipt should prove a participant was enabled or disabled by the operator",
    "which live-health fields prove this collaboration is recurring cleanly without user nudges",
    "which Francis body surface is visible but not yet safely exposed to Francis1 capability use",
    "what substrate-complete means as a checklist, not an argument",
    "which roadmap-alignment check should run before prompting any main Francis build",
)

_LOOP_MARKERS = (
    ("same_francis_identity", "same francis identity"),
    ("typed_receipt_shape", "typed receipt shape"),
    ("metadata_repetition", "metadata"),
    ("conversation_authority_boundary", "conversation as authority"),
    ("codex_implement_later", "codex implement later"),
    ("standardized_way", "standardized way"),
    ("collaboration_output_action_boundary", "chatbot output"),
    ("user_confirmation_fallback", "user confirmation"),
    ("advisory_output_boundary", "advisory output"),
    ("executable_code_boundary", "executable code"),
    ("clarification_dependency", "clarify"),
)

_OUTPUT_GUARD_TERM_ALLOWLIST = {
    "advisory_output_boundary",
    "clarification_dependency",
    "executable_code_boundary",
    "local_model_reconciliation_loop",
    "missing_surface_fallback",
    "protocol_wrapper_reply",
    "stale_action_readiness_topic_replay",
    "unauthorized_artifact_review_claim",
    "user_confirmation_fallback",
}


def drive_once(
    *,
    ignore_existing: bool = False,
    max_turns: int = _MAX_TURNS,
    dry_run: bool = False,
    repeat_closed: bool = False,
    session_gap_seconds: float = 120.0,
    turn_gap_seconds: float = _DEFAULT_TURN_GAP_SECONDS,
    summary_every_turns: int = _DEFAULT_SUMMARY_EVERY_TURNS,
) -> dict[str, object]:
    state = _load_state()
    clean_max_turns = _clean_max_turns(max_turns)
    clean_turn_gap_seconds = max(float(turn_gap_seconds), 0.0)
    clean_summary_every_turns = max(int(summary_every_turns), 0)

    ollama_items = _items(read_collaboration_transcript(source_agent="ollama", target_agent="codex", limit=50))
    if ignore_existing and not bool(state.get("initialized")):
        _mark_seen(state, [_item_id(item) for item in ollama_items])
        state["initialized"] = True

    if bool(state.get("closed")):
        if repeat_closed and _closed_elapsed_seconds(state) >= max(float(session_gap_seconds), 0.0):
            state = _empty_state()
            if ignore_existing:
                _mark_seen(state, [_item_id(item) for item in ollama_items])
                state["initialized"] = True
        else:
            _save_state(state)
            return {
                "kind": "developer_bridge.collaboration_driver",
                "ok": True,
                "status": "closed",
                "turn_count": _turn_count(state),
                "max_turns": clean_max_turns,
                "repeat_closed": repeat_closed,
                "session_gap_seconds": max(float(session_gap_seconds), 0.0),
                "governance": _governance(),
            }

    last_codex_prompt_id = str(state.get("last_codex_prompt_id") or "")
    if last_codex_prompt_id:
        response = _ollama_response_for(last_codex_prompt_id, ollama_items, state)
        if response is None:
            state["initialized"] = True
            _save_state(state)
            return {
                "kind": "developer_bridge.collaboration_driver",
                "ok": True,
                "status": "waiting_for_ollama",
                "source_prompt_id": last_codex_prompt_id,
                "turn_count": _turn_count(state),
                "max_turns": clean_max_turns,
                "governance": _governance(),
            }
        response_id = _item_id(response)
        _mark_seen(state, [response_id])
        state["last_ollama_prompt_id"] = response_id
        state["last_codex_prompt_id"] = ""
        state["waiting_for_ollama"] = False
        note = _record_response_note(state, response=response, source_prompt_id=last_codex_prompt_id)
        if note:
            state["last_note_id"] = note["id"]
            insight = _record_response_insight(
                state, response=response, source_prompt_id=last_codex_prompt_id, note=note
            )
            if insight:
                state["last_insight_id"] = insight["id"]
        summary = _record_summary_if_due(state, every_turns=clean_summary_every_turns)
        if summary:
            state["last_summary_id"] = summary["id"]
        if clean_turn_gap_seconds > 0:
            state["next_prompt_after"] = _future_utc(clean_turn_gap_seconds)

    gap_remaining = _turn_gap_remaining(state)
    if gap_remaining > 0:
        state["initialized"] = True
        _save_state(state)
        return {
            "kind": "developer_bridge.collaboration_driver",
            "ok": True,
            "status": "turn_gap",
            "turn_count": _turn_count(state),
            "max_turns": clean_max_turns,
            "next_prompt_after": str(state.get("next_prompt_after") or ""),
            "turn_gap_remaining_seconds": gap_remaining,
            "governance": _governance(),
        }

    if _turn_limit_reached(state, clean_max_turns):
        state["closed"] = True
        state["closed_at"] = _utc_now()
        _save_state(state)
        return {
            "kind": "developer_bridge.collaboration_driver",
            "ok": True,
            "status": "closed",
            "turn_count": _turn_count(state),
            "max_turns": clean_max_turns,
            "governance": _governance(),
        }

    if dry_run:
        prompt = _next_prompt(state, max_turns=clean_max_turns)
        return {
            "kind": "developer_bridge.collaboration_driver",
            "ok": True,
            "status": "dry_run",
            "planned_prompt": prompt,
            "turn_count": _turn_count(state),
            "max_turns": clean_max_turns,
            "governance": _governance(),
        }

    submitted = _submit_next_prompt(state, max_turns=clean_max_turns)
    _save_state(state)
    return {
        "kind": "developer_bridge.collaboration_driver",
        "ok": True,
        "status": "submitted",
        "response_required_from": "ollama",
        "prompt_id": submitted["prompt_id"],
        "turn_count": _turn_count(state),
        "max_turns": clean_max_turns,
        "chat_handoff": submitted["chat_handoff"],
        "governance": _governance(),
    }


def read_collaboration_learning_events(
    *,
    limit: int = 10,
    failure_type: str = "",
    term: str = "",
    session_id: str = "",
) -> dict[str, object]:
    safe_limit = min(max(_safe_int(limit, default=10), 1), 50)
    clean_failure_type = _bounded_text(failure_type, limit=80)
    clean_term = _topic_key(_bounded_text(term, limit=80))
    clean_session_id = _bounded_text(session_id, limit=120)
    latest_signal = _latest_learning_signal_for_readback()
    records: list[dict[str, object]] = []

    for path in _learning_root().glob("learning-*.json"):
        event = _read_learning_event(path)
        if event is None:
            continue
        if clean_failure_type and str(event.get("failure_type") or "") != clean_failure_type:
            continue
        if clean_session_id and str(event.get("session_id") or "") != clean_session_id:
            continue
        event = _learning_event_with_latest_signal(event, latest_signal)
        repeated_terms = [str(item) for item in _list(event.get("repeated_terms")) if str(item)]
        if clean_term and clean_term not in {_topic_key(item) for item in repeated_terms}:
            continue
        records.append(event)

    records.sort(
        key=lambda item: (
            _safe_int(item.get("latest_turn"), default=0),
            str(item.get("latest_observed_at") or item.get("created_at") or ""),
            str(item.get("id") or ""),
        ),
        reverse=True,
    )
    items = [_learning_event_readback_item(event) for event in records[:safe_limit]]
    return {
        "kind": "developer_bridge.collaboration_learning_events",
        "schema_version": _LEARNING_SCHEMA_VERSION,
        "ok": True,
        "mode": "read_only",
        "surface": "developer_bridge.collaboration_driver.learning_events",
        "items": items,
        "count": len(items),
        "truncated": len(records) > safe_limit,
        "filters": {
            "limit": safe_limit,
            "failure_type": clean_failure_type,
            "term": clean_term,
            "session_id": clean_session_id,
        },
        "definitions": {
            "learning_event": "A bounded receipt for repeated collaboration drift, loops, or local-model failure patterns.",
            "failure_type": "The classified failure or drift class recorded by the collaboration driver.",
            "repeated_terms": "Stable drift markers counted across recent relay notes; not raw transcript text.",
            "recent_turns": "Receipt identifiers and matched markers used as evidence without storing full messages.",
            "latest_turn": "Most recent observed turn for this learning event, including deduplicated drift signals.",
        },
        "governance": _learning_readback_governance(),
    }


def _submit_next_prompt(state: dict[str, object], *, max_turns: int) -> dict[str, object]:
    turn_number = _turn_count(state) + 1
    _ensure_session_context_contract(state)
    prompt = _next_prompt(state, max_turns=max_turns)
    session_id = _session_id(state)
    previous_ollama_prompt_id = str(state.get("last_ollama_prompt_id") or "")
    turn_label = _turn_label(turn_number, max_turns)
    submitted = submit_collaboration_prompt(
        source_agent="codex",
        target_agent="ollama",
        objective=f"Francis1 collaboration driver {turn_label}",
        prompt=prompt,
        context=(
            f"session={session_id}; turn={turn_number}; participant=Francis1; "
            f"provider=ollama; previous_ollama={previous_ollama_prompt_id or 'none'}; "
            f"contract={CONTEXT_CONTRACT_ID}; no_action_authority=true."
        ),
    )
    now = _utc_now()
    state["initialized"] = True
    state["closed"] = False
    state["closed_at"] = ""
    state["last_codex_prompt_id"] = submitted["prompt_id"]
    state["waiting_for_ollama"] = True
    state["next_prompt_after"] = ""
    state["turn_count"] = turn_number
    loop_signal = _loop_signal(state)
    if loop_signal.get("detected"):
        learning = _record_learning_event_if_new(state, loop_signal=loop_signal)
        if learning:
            state["last_learning_event_id"] = learning["id"]
        _record_latest_learning_signal(state, loop_signal=loop_signal)
    guard_signal = _guard_saturation_signal(state)
    if guard_signal.get("detected"):
        learning = _record_learning_event_if_new(state, loop_signal=guard_signal)
        if learning:
            state["last_learning_event_id"] = learning["id"]
        _record_latest_learning_signal(state, loop_signal=guard_signal)
    topic = _topic_for_next_turn(state, turn_number)
    turns = _list(state.get("turns"))
    turns.append(
        {
            "created_at": now,
            "turn": turn_number,
            "turn_label": turn_label,
            "topic": topic,
            "codex_prompt_id": submitted["prompt_id"],
            "previous_ollama_prompt_id": previous_ollama_prompt_id,
        }
    )
    state["turns"] = turns[-_MAX_TRACKED_IDS:]
    return submitted


def _next_prompt(state: dict[str, object], *, max_turns: int) -> str:
    turn_number = _turn_count(state) + 1
    loop_signal = _loop_signal(state)
    guard_signal = _guard_saturation_signal(state)
    topic = _topic_for_next_turn(
        state,
        turn_number,
        loop_signal=loop_signal,
        guard_signal=guard_signal,
    )
    review_line = _compact_review_line(latest_review_candidate_line())
    prior_check = f" Prior check: {review_line}" if review_line else ""
    topic_artifact = _topic_artifact_line(topic)
    codex_response = _codex_response_line(review_line)
    body_map_line = compact_body_map_prompt_line()
    roadmap_gate_line = compact_roadmap_gate_prompt_line()
    trust_line = compact_trust_ladder_prompt_line()
    loop_line = ""
    if guard_signal.get("detected"):
        loop_line = " Guard note: drift stored as learning receipt; answer current topic."
    elif loop_signal.get("detected"):
        repeated_terms = [str(term) for term in _list(loop_signal.get("repeated_terms"))]
        preferred_term = next((term for term in repeated_terms if term == "user_confirmation_fallback"), "")
        terms = preferred_term or (repeated_terms[0] if repeated_terms else "repeated meta terms")
        if len(repeated_terms) > 1:
            terms = f"{terms}, ..."
        loop_line = f" Loop note: {terms}; use prior surface, not meta."
    turn_label = _turn_label(turn_number, max_turns)
    prompt = _compose_driver_prompt(
        turn_label=turn_label,
        topic=topic,
        body_map_line=body_map_line,
        roadmap_gate_line=roadmap_gate_line,
        trust_line=trust_line,
        topic_artifact=topic_artifact,
        prior_check=prior_check,
        codex_response=codex_response,
        loop_line=loop_line,
    )
    if len(prompt) <= _MAX_DRIVER_PROMPT_CHARS:
        return prompt
    prompt = _compose_driver_prompt(
        turn_label=turn_label,
        topic=topic,
        body_map_line="",
        roadmap_gate_line=roadmap_gate_line,
        trust_line=trust_line,
        topic_artifact=topic_artifact,
        prior_check=prior_check,
        codex_response=codex_response,
        loop_line=loop_line,
    )
    if len(prompt) <= _MAX_DRIVER_PROMPT_CHARS:
        return prompt
    return _compose_driver_prompt(
        turn_label=turn_label,
        topic=_bounded_text(topic, limit=96),
        body_map_line="",
        roadmap_gate_line=roadmap_gate_line,
        trust_line=trust_line,
        topic_artifact=_topic_artifact_line(topic, surface_limit=96),
        prior_check=prior_check,
        codex_response=codex_response,
        loop_line=loop_line,
    )


def _compose_driver_prompt(
    *,
    turn_label: str,
    topic: str,
    body_map_line: str,
    roadmap_gate_line: str,
    trust_line: str,
    topic_artifact: str,
    prior_check: str,
    codex_response: str,
    loop_line: str,
) -> str:
    body_map = f" {body_map_line}" if body_map_line else ""
    return (
        f"Francis1 {turn_label}. {CONTEXT_CONTRACT_ID}. Topic: {topic}. "
        "Reply: issue/gap/risk; artifact."
        f"{body_map}"
        f" {roadmap_gate_line}"
        f" {trust_line}"
        f"{topic_artifact}{prior_check}{codex_response}{loop_line}"
    )


def _codex_response_line(review_line: str) -> str:
    if not review_line:
        return ""
    if "build_or_wire=false" in review_line:
        return " Codex response: inspecting cited surface; no action authority."
    return " Codex response: I am verifying repo truth before build/wiring."


def _compact_review_line(review_line: str) -> str:
    clean = _bounded_text(review_line, limit=260)
    if not clean:
        return ""
    insight_id = _field_after(clean, "Review candidate ", ":")
    surface = _field_after(clean, "surface=", ";")
    verified = _field_after(clean, "verified=", ";")
    build_or_wire = _field_after(clean, "build_or_wire=", ".")
    if insight_id and (surface or verified or build_or_wire):
        return (
            f"Review candidate {_bounded_text(insight_id, limit=_PROMPT_REVIEW_ID_LIMIT)}: "
            f"surface={_bounded_text(surface or 'unknown', limit=_PROMPT_REVIEW_SURFACE_LIMIT)}; "
            f"verified={_bounded_text(verified or 'unknown', limit=20)}; "
            f"build_or_wire={_bounded_text(build_or_wire or 'unknown', limit=12)}."
        )
    return clean


def _field_after(value: str, marker: str, end_marker: str) -> str:
    start = value.find(marker)
    if start < 0:
        return ""
    after_marker = start + len(marker)
    end = value.find(end_marker, after_marker) if end_marker else -1
    if end < 0:
        end = len(value)
    return value[after_marker:end].strip()


def _topic_artifact_line(topic: str, *, surface_limit: int = 140) -> str:
    candidate = _implementation_candidate_for_topic(topic)
    surface = _bounded_text(candidate.get("surface"), limit=surface_limit)
    if not surface:
        return ""
    return f" Current artifact: {surface}."


def _ollama_response_for(
    source_prompt_id: str,
    items: list[dict[str, object]],
    state: dict[str, object],
) -> dict[str, object] | None:
    seen = set(_list(state.get("seen_ollama_ids")))
    for item in reversed(items):
        item_id = _item_id(item)
        if item_id in seen:
            continue
        context = str(item.get("context") or "")
        if source_prompt_id in context:
            return item
    return None


def _record_response_note(
    state: dict[str, object],
    *,
    response: dict[str, object],
    source_prompt_id: str,
) -> dict[str, object]:
    response_id = _item_id(response)
    if not response_id:
        return {}
    existing = _find_turn(state, source_prompt_id)
    turn_number = _turn_count(state)
    if existing:
        turn_number = _safe_int(existing.get("turn"), default=turn_number)
    topic = str((existing or {}).get("topic") or _topic_for_turn(turn_number))
    summary = _bounded_summary(response.get("prompt"))
    note_id = f"note-{response_id}"
    note = {
        "kind": "developer_bridge.collaboration_note",
        "id": note_id,
        "created_at": _utc_now(),
        "session_id": _session_id(state),
        "turn": turn_number,
        "topic": topic,
        "codex_prompt_id": source_prompt_id,
        "ollama_prompt_id": response_id,
        "note": summary,
        "coexistence_frame": (
            "Codex and Francis1 are engineering sources learning under Francis identity and governance; "
            "Ollama is Francis1 provider provenance, not identity; "
            "this note is advisory convergence, not execution authority."
        ),
        "governance": _note_governance(),
    }
    _write_json_receipt(_note_path(note_id), note)
    _update_turn_note(state, source_prompt_id=source_prompt_id, note=note)
    return note


def _record_response_insight(
    state: dict[str, object],
    *,
    response: dict[str, object],
    source_prompt_id: str,
    note: dict[str, object],
) -> dict[str, object]:
    response_id = _item_id(response)
    note_id = str(note.get("id") or "")
    if not response_id or not note_id:
        return {}
    existing = _find_turn(state, source_prompt_id)
    turn_number = _safe_int((existing or {}).get("turn"), default=_turn_count(state))
    topic = str((existing or {}).get("topic") or note.get("topic") or _topic_for_turn(turn_number))
    finding = _bounded_summary(note.get("note"), limit=520)
    issue = _issue_for_topic(topic)
    implementation_candidate = _implementation_candidate_for_topic(topic)
    memory_candidate = _memory_candidate_for_topic(topic, finding=finding)
    insight_id = f"insight-{response_id}"
    insight = {
        "kind": "developer_bridge.collaboration_insight",
        "schema_version": _INSIGHT_SCHEMA_VERSION,
        "id": insight_id,
        "created_at": _utc_now(),
        "session_id": _session_id(state),
        "turn": turn_number,
        "topic": topic,
        "source": {
            "codex_prompt_id": source_prompt_id,
            "ollama_prompt_id": response_id,
            "note_id": note_id,
            "derived_from": "developer_bridge.collaboration_note",
            "provider_lane": "ollama",
            "model_identity": "francis1",
            "provider_name_is_not_identity": True,
            "stores_full_transcript": False,
        },
        "conversation_memory": {
            "finding": finding,
            "build_issue": issue,
            "implementation_candidate": implementation_candidate,
            "memory_candidate": memory_candidate,
            "alignment_tags": _alignment_tags_for_topic(topic),
        },
        "action_boundary": {
            "operator_direction_modes_relevant": ["typed", "spoken"],
            "conversation_can_create_action_candidate": True,
            "conversation_can_execute_action": False,
            "conversation_can_approve_action": False,
            "requires_codex_or_operator_review_before_implementation": True,
            "requires_existing_governed_action_path_before_runtime_action": True,
        },
        "review_status": {
            "state": "candidate",
            "validated_against_repo_truth": False,
            "implemented": False,
            "authority": "advisory_receipt_only",
        },
        "governance": _insight_governance(),
    }
    _write_json_receipt(_insight_path(insight_id), insight)
    _update_turn_insight(state, source_prompt_id=source_prompt_id, insight=insight)
    return insight


def _record_summary_if_due(state: dict[str, object], *, every_turns: int) -> dict[str, object]:
    if every_turns <= 0:
        return {}
    turn = _turn_count(state)
    if turn <= 0 or turn % every_turns != 0:
        return {}
    if _safe_int(state.get("last_summary_turn"), default=0) >= turn:
        return {}
    recent = _recent_turn_notes(state, limit=every_turns)
    if not recent:
        return {}
    summary_id = f"summary-{_session_id(state)}-turn-{turn}"
    topics = [str(item.get("topic") or "").strip() for item in recent if str(item.get("topic") or "").strip()]
    notes = [
        str(item.get("note_summary") or "").strip() for item in recent if str(item.get("note_summary") or "").strip()
    ]
    summary_text = _bounded_summary(
        " ".join(notes),
        limit=700,
    )
    summary = {
        "kind": "developer_bridge.collaboration_summary",
        "id": summary_id,
        "created_at": _utc_now(),
        "session_id": _session_id(state),
        "through_turn": turn,
        "turn_count": turn,
        "topic_window": topics[-every_turns:],
        "summary": summary_text,
        "identity_note": (
            "The collaboration is learning Francis as shared operating identity while preserving Codex and Francis1 "
            "as governed sources, not authority centers. Ollama remains Francis1 provider provenance."
        ),
        "governance": _note_governance(),
    }
    _write_json_receipt(_summary_path(summary_id), summary)
    append(
        "system",
        f"Francis collaboration summary through turn {turn}: {summary_text}",
        {
            "mode": "developer_bridge_collaboration_summary",
            "session_id": _session_id(state),
            "summary_id": summary_id,
            "through_turn": turn,
            "source": "developer_bridge.collaboration_driver",
            "stores_full_transcript": False,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
    )
    state["last_summary_turn"] = turn
    return summary


def _record_learning_event_if_new(
    state: dict[str, object],
    *,
    loop_signal: dict[str, object],
) -> dict[str, object]:
    signature = str(loop_signal.get("signature") or "")
    last_signature = str(state.get("last_learning_event_signature") or "")
    if signature == "output_guard_drift|continuous_saturation" and last_signature.startswith("output_guard_drift|"):
        state["last_learning_event_signature"] = signature
        return {}
    if not signature or last_signature == signature:
        return {}
    recent_turns = _list(loop_signal.get("recent_turns"))
    event_id = f"learning-{_session_id(state)}-{uuid4().hex[:16]}"
    repeated_terms = [str(item) for item in _list(loop_signal.get("repeated_terms")) if str(item)]
    failure_type = str(loop_signal.get("failure_type") or "repetitive_meta_loop")
    observation = str(
        loop_signal.get("observation")
        or (
            "The collaboration repeated identity, provenance, receipt-shape, or authority-boundary language enough "
            "to risk becoming an argument loop instead of producing new build direction."
        )
    )
    learning_payload = {
        "memory_value": str(
            loop_signal.get("memory_value")
            or "failed or repetitive collaboration turns are learning material when stored as typed, bounded receipts"
        ),
        "operator_intent": str(
            loop_signal.get("operator_intent") or "keep failures in Francis memory without transcript dumping"
        ),
        "next_prompt_policy": str(
            loop_signal.get("next_prompt_policy")
            or "ask for a concrete build surface and review artifact instead of another identity/provenance argument"
        ),
    }
    event = {
        "kind": "developer_bridge.collaboration_learning_event",
        "schema_version": _LEARNING_SCHEMA_VERSION,
        "id": event_id,
        "created_at": _utc_now(),
        "session_id": _session_id(state),
        "turn": _turn_count(state),
        "failure_type": failure_type,
        "observation": observation,
        "repeated_terms": repeated_terms,
        "recent_turns": recent_turns,
        "learning": learning_payload,
        "governance": _learning_governance(),
    }
    _write_json_receipt(_learning_path(event_id), event)
    append(
        "system",
        (
            f"Francis collaboration learning event: {failure_type} detected; "
            f"terms={', '.join(repeated_terms) or 'unknown'}; event_id={event_id}"
        ),
        {
            "mode": "developer_bridge_collaboration_learning",
            "session_id": _session_id(state),
            "learning_event_id": event_id,
            "failure_type": failure_type,
            "stores_full_transcript": False,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
            "grants_memory_write_authority": False,
            "source": "developer_bridge.collaboration_driver",
        },
    )
    state["last_learning_event_signature"] = signature
    return event


def _record_latest_learning_signal(
    state: dict[str, object],
    *,
    loop_signal: dict[str, object],
) -> None:
    recent_turns = _list(loop_signal.get("recent_turns"))
    latest_turn = 0
    for item in recent_turns:
        if isinstance(item, dict):
            latest_turn = max(latest_turn, _safe_int(item.get("turn"), default=0))
    state["latest_learning_signal"] = {
        "observed": True,
        "failure_type": str(loop_signal.get("failure_type") or "repetitive_meta_loop"),
        "repeated_terms": [str(item) for item in _list(loop_signal.get("repeated_terms")) if str(item)],
        "recent_turn_count": len(recent_turns),
        "latest_turn": latest_turn,
        "learning_event_id": str(state.get("last_learning_event_id") or ""),
        "signature": str(loop_signal.get("signature") or ""),
        "updated_at": _utc_now(),
        "stores_full_transcript": False,
        "records_model_drift_as_learning": True,
        "requires_codex_or_operator_review_before_tuning": True,
        "grants_training_authority": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "grants_approval_authority": False,
        "grants_memory_write_authority": False,
    }


def _read_learning_event(path: Path) -> dict[str, object] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or data.get("kind") != "developer_bridge.collaboration_learning_event":
        return None
    return data


def _learning_event_readback_item(event: dict[str, object]) -> dict[str, object]:
    raw_learning = event.get("learning")
    learning = cast(dict[str, object], raw_learning) if isinstance(raw_learning, dict) else {}
    raw_writer_governance = event.get("governance")
    writer_governance = (
        cast(dict[str, object], raw_writer_governance) if isinstance(raw_writer_governance, dict) else {}
    )
    recent_turns = [
        _learning_recent_turn_readback(item) for item in _list(event.get("recent_turns")) if isinstance(item, dict)
    ]
    return {
        "id": _bounded_text(event.get("id"), limit=160),
        "created_at": _bounded_text(event.get("created_at"), limit=80),
        "session_id": _bounded_text(event.get("session_id"), limit=120),
        "turn": _safe_int(event.get("turn"), default=0),
        "latest_turn": _safe_int(event.get("latest_turn"), default=_learning_event_latest_turn(event)),
        "latest_observed_at": _bounded_text(
            event.get("latest_observed_at") or event.get("created_at"),
            limit=80,
        ),
        "current_signal_observed": bool(event.get("current_signal_observed")),
        "current_signal_recent_turn_count": _safe_int(
            event.get("current_signal_recent_turn_count"),
            default=len(_list(event.get("recent_turns"))),
        ),
        "failure_type": _bounded_text(event.get("failure_type"), limit=120),
        "observation": _bounded_text(event.get("observation"), limit=420),
        "repeated_terms": [
            _bounded_text(item, limit=80)
            for item in _list(event.get("repeated_terms"))[:16]
            if _bounded_text(item, limit=80)
        ],
        "recent_turn_count": len(_list(event.get("recent_turns"))),
        "recent_turns": recent_turns[:6],
        "learning": {
            "memory_value": _bounded_text(learning.get("memory_value"), limit=260),
            "operator_intent": _bounded_text(learning.get("operator_intent"), limit=220),
            "next_prompt_policy": _bounded_text(learning.get("next_prompt_policy"), limit=260),
        },
        "writer_governance": {
            "stores_full_transcript": bool(writer_governance.get("stores_full_transcript")),
            "records_failures_as_learning": bool(writer_governance.get("records_failures_as_learning")),
            "grants_execution_authority": bool(writer_governance.get("grants_execution_authority")),
            "grants_mutation_authority": bool(writer_governance.get("grants_mutation_authority")),
            "grants_approval_authority": bool(writer_governance.get("grants_approval_authority")),
            "grants_memory_write_authority": bool(writer_governance.get("grants_memory_write_authority")),
            "grants_model_authority": bool(writer_governance.get("grants_model_authority")),
        },
    }


def _latest_learning_signal_for_readback() -> dict[str, object]:
    raw = _load_state().get("latest_learning_signal")
    return cast(dict[str, object], raw) if isinstance(raw, dict) else {}


def _learning_event_with_latest_signal(
    event: dict[str, object],
    latest_signal: dict[str, object],
) -> dict[str, object]:
    merged = dict(event)
    latest_turn = _learning_event_latest_turn(event)
    latest_observed_at = _bounded_text(event.get("created_at"), limit=80)
    signal_event_id = str(latest_signal.get("learning_event_id") or "")
    if signal_event_id and signal_event_id == str(event.get("id") or ""):
        signal_latest_turn = _safe_int(latest_signal.get("latest_turn"), default=0)
        latest_turn = max(latest_turn, signal_latest_turn)
        latest_observed_at = _bounded_text(
            latest_signal.get("updated_at") or latest_observed_at,
            limit=80,
        )
        merged["current_signal_observed"] = bool(latest_signal.get("observed"))
        merged["current_signal_recent_turn_count"] = _safe_int(latest_signal.get("recent_turn_count"), default=0)
        merged["repeated_terms"] = _merge_terms(event.get("repeated_terms"), latest_signal.get("repeated_terms"))
    else:
        merged["current_signal_observed"] = False
        merged["current_signal_recent_turn_count"] = len(_list(event.get("recent_turns")))
    merged["latest_turn"] = latest_turn
    merged["latest_observed_at"] = latest_observed_at
    return merged


def _learning_event_latest_turn(event: dict[str, object]) -> int:
    latest_turn = _safe_int(event.get("turn"), default=0)
    for item in _list(event.get("recent_turns")):
        if isinstance(item, dict):
            latest_turn = max(latest_turn, _safe_int(item.get("turn"), default=0))
    return latest_turn


def _merge_terms(*values: object) -> list[str]:
    terms: list[str] = []
    for value in values:
        for item in _list(value):
            term = _bounded_text(item, limit=80)
            if term and term not in terms:
                terms.append(term)
    return terms[:16]


def _learning_recent_turn_readback(item: dict[str, object]) -> dict[str, object]:
    return {
        "turn": _safe_int(item.get("turn"), default=0),
        "note_id": _bounded_text(item.get("note_id"), limit=160),
        "ollama_prompt_id": _bounded_text(item.get("ollama_prompt_id"), limit=160),
        "matched_terms": [
            _bounded_text(term, limit=80)
            for term in _list(item.get("matched_terms"))[:16]
            if _bounded_text(term, limit=80)
        ],
    }


def _find_turn(state: dict[str, object], source_prompt_id: str) -> dict[str, object]:
    for item in _list(state.get("turns")):
        if isinstance(item, dict) and str(item.get("codex_prompt_id") or "") == source_prompt_id:
            return item
    return {}


def _update_turn_note(
    state: dict[str, object],
    *,
    source_prompt_id: str,
    note: dict[str, object],
) -> None:
    updated: list[object] = []
    for item in _list(state.get("turns")):
        if not isinstance(item, dict):
            updated.append(item)
            continue
        if str(item.get("codex_prompt_id") or "") == source_prompt_id:
            item = {
                **item,
                "ollama_prompt_id": note.get("ollama_prompt_id", ""),
                "note_id": note.get("id", ""),
                "note_summary": note.get("note", ""),
            }
        updated.append(item)
    state["turns"] = updated[-_MAX_TRACKED_IDS:]


def _update_turn_insight(
    state: dict[str, object],
    *,
    source_prompt_id: str,
    insight: dict[str, object],
) -> None:
    updated: list[object] = []
    memory = insight.get("conversation_memory")
    finding = ""
    if isinstance(memory, dict):
        finding = str(memory.get("finding") or "")
    for item in _list(state.get("turns")):
        if not isinstance(item, dict):
            updated.append(item)
            continue
        if str(item.get("codex_prompt_id") or "") == source_prompt_id:
            item = {
                **item,
                "insight_id": insight.get("id", ""),
                "insight_summary": finding,
            }
        updated.append(item)
    state["turns"] = updated[-_MAX_TRACKED_IDS:]


def _recent_turn_notes(state: dict[str, object], *, limit: int) -> list[dict[str, object]]:
    notes: list[dict[str, object]] = []
    for item in _list(state.get("turns")):
        if not isinstance(item, dict):
            continue
        note = str(item.get("note_summary") or "").strip()
        if not note:
            continue
        notes.append(item)
    return notes[-max(limit, 1) :]


def _recent_note_context(state: dict[str, object]) -> str:
    notes = _recent_turn_notes(state, limit=3)
    if not notes:
        return ""
    parts = []
    for item in notes:
        turn = str(item.get("turn") or "?")
        note = _bounded_summary(item.get("note_summary"), limit=180)
        if note:
            parts.append(f"turn {turn}: {note}")
    return " | ".join(parts)[-700:]


def _ensure_session_context_contract(state: dict[str, object]) -> None:
    session_id = _session_id(state)
    ensure_context_contract(session_id=session_id)
    if str(state.get("context_contract_ledgered_id") or "") == CONTEXT_CONTRACT_ID:
        return
    append_context_contract_to_continuity(session_id=session_id)
    state["context_contract_id"] = CONTEXT_CONTRACT_ID
    state["context_contract_ledgered_id"] = CONTEXT_CONTRACT_ID
    state["context_contract_ledgered_at"] = _utc_now()


def _loop_signal(state: dict[str, object]) -> dict[str, object]:
    recent = _recent_turn_notes(state, limit=6)
    if len(recent) < 4:
        return {"detected": False}
    hits: dict[str, int] = {}
    hit_turns: list[dict[str, object]] = []
    for item in recent:
        note = str(item.get("note_summary") or "").lower()
        matched = []
        for name, marker in _LOOP_MARKERS:
            if marker in note:
                hits[name] = hits.get(name, 0) + 1
                matched.append(name)
        if matched:
            hit_turns.append(
                {
                    "turn": item.get("turn", ""),
                    "note_id": item.get("note_id", ""),
                    "ollama_prompt_id": item.get("ollama_prompt_id", ""),
                    "matched_terms": matched,
                }
            )
    repeated_terms = sorted(name for name, count in hits.items() if count >= 3)
    detected = bool(repeated_terms)
    signature = ""
    if detected:
        turn_ids = ",".join(str(item.get("turn", "")) for item in hit_turns[-6:])
        signature = "|".join(repeated_terms) + f"|{turn_ids}"
    return {
        "detected": detected,
        "repeated_terms": repeated_terms,
        "recent_turns": hit_turns[-6:],
        "signature": signature,
    }


def _guard_saturation_signal(state: dict[str, object]) -> dict[str, object]:
    recent = _recent_turn_notes(state, limit=6)
    hit_turns: list[dict[str, object]] = []
    repeated_terms: list[str] = []
    for item in recent:
        note = str(item.get("note_summary") or "").lower()
        if "francis1 output guard" not in note and "output guard" not in note:
            continue
        matched = _guard_matched_terms(note)
        repeated_terms = _merge_terms(repeated_terms, matched)
        hit_turns.append(
            {
                "turn": item.get("turn", ""),
                "note_id": item.get("note_id", ""),
                "ollama_prompt_id": item.get("ollama_prompt_id", ""),
                "matched_terms": matched,
            }
        )
    detected = len(hit_turns) >= 2
    signature = ""
    if detected:
        signature = "output_guard_drift|continuous_saturation"
    return {
        "detected": detected,
        "repeated_terms": repeated_terms if detected else [],
        "recent_turns": hit_turns[-6:],
        "signature": signature,
        "failure_type": "output_guard_drift",
        "observation": (
            "The local Francis1 provider lane repeatedly triggered the output guard after Codex supplied a verified "
            "surface, so the drift is learning material but not action-readiness evidence."
        ),
        "memory_value": (
            "output-guard rewrites are learning material when stored as typed, bounded receipts without raw model text"
        ),
        "operator_intent": "keep guarded local-model failures visible without transcript dumping or model authority",
        "next_prompt_policy": (
            "move to the next concrete topic and cite the relevant review artifact instead of repeating guarded drift"
        ),
    }


def _guard_matched_terms(note: str) -> list[str]:
    terms = ["output_guard_drift"]
    marker = "drift terms:"
    start = note.find(marker)
    if start < 0:
        return terms
    raw_terms = note[start + len(marker) :].split(".", 1)[0]
    for raw_term in raw_terms.split(","):
        term = "".join(ch for ch in raw_term.strip() if ch.isalnum() or ch == "_")
        if term in _OUTPUT_GUARD_TERM_ALLOWLIST and term not in terms:
            terms.append(term)
    return terms


def _bounded_summary(value: object, *, limit: int = 420) -> str:
    text = _identity_safe_text(redact_secret_text(" ".join(str(value or "").split())))
    if not text:
        return "No substantive model text was available for this note."
    sentences = [part.strip() for part in text.replace("?", ".").replace("!", ".").split(".") if part.strip()]
    if sentences:
        text = ". ".join(sentences[:2])
        if text:
            text += "."
    return text[:limit]


def _bounded_text(value: object, *, limit: int) -> str:
    text = redact_secret_text(" ".join(str(value or "").split()))
    return text[:limit]


def _identity_safe_text(text: str) -> str:
    replacements = {
        "Codex and Ollama": "Codex and Francis1",
        "Codex/Ollama": "Codex/Francis1",
        "Codex-Ollama": "Codex/Francis1",
        "between Codex and Ollama": "between Codex and Francis1",
        "between two engineering sources like Codex and Ollama": "between Codex and Francis1",
        "two engineering sources like Codex and Ollama": "Codex and Francis1",
        "Codex and the Francis local-model lane": "Codex and Francis1",
        "between Codex and the Francis local-model lane": "between Codex and Francis1",
        "two engineering sources like Codex and this local-model lane": "Codex and Francis1",
        "this local-model lane": "Francis1",
        "This local-model lane": "Francis1",
    }
    for needle, replacement in replacements.items():
        text = text.replace(needle, replacement)
    return text


def _topic_for_next_turn(
    state: dict[str, object],
    turn_number: int,
    *,
    loop_signal: dict[str, object] | None = None,
    guard_signal: dict[str, object] | None = None,
) -> str:
    loop = loop_signal if loop_signal is not None else _loop_signal(state)
    guard = guard_signal if guard_signal is not None else _guard_saturation_signal(state)
    if loop.get("detected") and not guard.get("detected"):
        return "the concrete repo surface and review artifact that should replace the current repetitive meta loop"
    return _topic_for_turn(turn_number)


def _issue_for_topic(topic: str) -> dict[str, object]:
    clean_topic = _bounded_summary(topic, limit=220)
    lower = _topic_key(clean_topic)
    if "communication ui" in lower or "communication window" in lower:
        code = "communication_view_noise"
        statement = (
            "The operator needs a readable message stream that separates substantive agent turns from relay mechanics."
        )
    elif "review receipt" in lower or "before editing collaboration code" in lower:
        code = "collaboration_review_receipt_selection"
        statement = "Codex implementation sessions need a typed review item before treating collaboration output as build direction."
    elif "memory record" in lower or "memory boundaries" in lower or "notes should be remembered" in lower:
        code = "typed_memory_review_surface"
        statement = "Collaboration output needs typed, bounded records so later implementation work can review findings without transcript dumping."
    elif _loop_recovery_topic(lower):
        code = "collaboration_loop_learning_receipt"
        statement = (
            "Repeated collaboration meta loops need bounded learning-event receipts before any prompt or tuning claim."
        )
    elif "local model failure" in lower or "drift signal" in lower:
        code = "local_model_drift_learning_receipt"
        statement = "Local model drift or failure signals should become bounded learning receipts before tuning or implementation claims."
    elif "typed or spoken" in lower or "taking action" in lower:
        code = "direction_to_action_boundary"
        statement = "Typed or spoken operator direction needs an action-candidate boundary before any governed runtime action can occur."
    elif "toggle state" in lower or "participant enabled" in lower or "participant was enabled" in lower:
        code = "collaboration_agent_toggle_receipt"
        statement = (
            "Participant enablement changes need operator-visible toggle receipts without granting execution authority."
        )
    elif "chatbot output" in lower or "action readiness" in lower or "advisory only" in lower:
        code = "chat_output_vs_action_readiness"
        statement = (
            "Local model text must stay distinct from action readiness evidence and governed execution authority."
        )
    elif "governance gate" in lower or "model advice proposes action" in lower:
        code = "model_advice_governance_gate_visibility"
        statement = "Model advice that proposes action needs visible gate and action-boundary readback before any readiness claim."
    elif "session summary" in lower or "sessions" in lower or "revisited" in lower or "raw transcript" in lower:
        code = "collaboration_session_recall"
        statement = (
            "Operators need session-level recall and summaries without storing or rereading every raw relay turn."
        )
    elif "disagreement" in lower:
        code = "source_disagreement_record"
        statement = "Disagreement between sources needs a durable review record before it can become build direction."
    elif "live health" in lower or "recurring" in lower:
        code = "collaboration_recurrence_evidence"
        statement = (
            "The recurring loop needs health receipts proving progress without relying on repeated operator nudges."
        )
    elif "body surface" in lower or "whole body" in lower or "capability use" in lower:
        code = "francis_body_map_trust_ladder"
        statement = "Francis1 needs whole-body awareness while capability exposure stays trust-gated and review-backed."
    elif "substrate complete" in lower:
        code = "substrate_completion_checklist"
        statement = "Substrate-complete claims need a checklist checked against existing ledger, manifest, receipt, and runtime truth."
    elif "roadmap alignment" in lower or "main francis build" in lower:
        code = "roadmap_alignment_gate"
        statement = "Main Francis build prompts must be checked against the completion ledger and canonical build manifest first."
    else:
        code = "collaboration_build_signal"
        statement = "The collaboration should produce implementation-facing signals while remaining advisory under Francis governance."
    return {
        "code": code,
        "statement": statement,
        "source_topic": clean_topic,
    }


def _implementation_candidate_for_topic(topic: str) -> dict[str, object]:
    lower = _topic_key(topic)
    if "communication ui" in lower or "communication window" in lower:
        title = "Filter and group Communication relay messages"
        surface = "apps.chat_ui.communication"
        validation = "UI contract test plus collaboration_log brief readback with auto-acks hidden"
    elif "review receipt" in lower or "before editing collaboration code" in lower:
        title = "Read collaboration review item before implementation"
        surface = "developer_bridge.collaboration_review.items"
        validation = "readback test proving a concrete review item exists before Codex changes collaboration code"
    elif "memory record" in lower or "memory boundaries" in lower or "notes should be remembered" in lower:
        title = "Review typed collaboration insights before implementation"
        surface = "developer_bridge.collaboration_driver.insights"
        validation = "focused developer-bridge tests proving bounded schema and no transcript storage"
    elif _loop_recovery_topic(lower):
        title = "Read collaboration loop learning receipt"
        surface = "developer_bridge.collaboration_driver.learning_events"
        validation = "readback test proving repeated meta loops resolve to a bounded no-authority learning receipt"
    elif "local model failure" in lower or "drift signal" in lower:
        title = "Record local-model drift as a collaboration learning receipt"
        surface = "developer_bridge.collaboration_driver.learning_events"
        validation = "focused developer-bridge test proving drift remains a no-authority learning receipt"
    elif "typed or spoken" in lower or "taking action" in lower:
        title = "Route typed/spoken direction into action candidates, not direct execution"
        surface = "api.routes.chat.mission_ingress"
        validation = "chat mission-ingress tests proving mission and plan.create records are gated and queued"
    elif "toggle state" in lower or "participant enabled" in lower or "participant was enabled" in lower:
        title = "Read participant toggle receipts from collaboration-agent status"
        surface = "developer_bridge.collaboration_agents"
        validation = "status readback test proving toggle receipts include actor, reason, previous/current state, and no authority grant"
    elif "chatbot output" in lower or "action readiness" in lower or "advisory only" in lower:
        title = "Separate local model chat from Francis action-readiness evidence"
        surface = "ollama participant and action-readiness receipts"
        validation = "readback test proving model output has no execution, mutation, or approval authority"
    elif "governance gate" in lower or "model advice proposes action" in lower:
        title = "Expose model-advice governance gate in review readback"
        surface = "developer_bridge.collaboration_review.action_boundary"
        validation = "review readback test proving action proposals expose execute/approve false plus repo-truth review requirement"
    elif "session summary" in lower or "sessions" in lower or "revisited" in lower or "raw transcript" in lower:
        title = "Add session-level collaboration review surface"
        surface = "developer_bridge collaboration sessions"
        validation = "readback test for bounded session summary and no full transcript requirement"
    elif "disagreement" in lower:
        title = "Record source disagreement as a review candidate"
        surface = "developer_bridge.collaboration_review.items"
        validation = "contract test proving disagreement blocks build direction until typed review"
    elif "live health" in lower or "recurring" in lower:
        title = "Expose recurrence health receipts for the collaboration loop"
        surface = "developer_bridge collaboration runtime"
        validation = "runtime state readback showing recent turn, note, and process health"
    elif "body surface" in lower or "whole body" in lower or "capability use" in lower:
        title = "Expose Francis whole-body map with trust-gated capability modes"
        surface = "developer_bridge.francis_body_map"
        validation = "readback test proving whole-body awareness does not grant execution, mutation, approval, memory-write, or training authority"
    elif "substrate complete" in lower:
        title = "Check substrate completeness against current build truth"
        surface = "docs/canonical/BUILD_MANIFEST.md + docs/operations/COMPLETION_LEDGER.md"
        validation = "docs/readback review proving no phase or substrate-complete claim outruns ledger evidence"
    elif "roadmap alignment" in lower or "main francis build" in lower:
        title = "Run roadmap alignment before main Francis build prompts"
        surface = "docs/operations/COMPLETION_LEDGER.md + docs/canonical/BUILD_MANIFEST.md"
        validation = (
            "ledger-first review proving current phase, priority, and remaining blockers before build escalation"
        )
    else:
        title = "Review collaboration insight for possible bounded implementation"
        surface = "developer_bridge collaboration review"
        validation = "Codex repo-truth review before any code change"
    return {
        "title": title,
        "surface": surface,
        "status": "candidate",
        "validation_hint": validation,
        "requires_operator_or_codex_review": True,
    }


def _memory_candidate_for_topic(topic: str, *, finding: str) -> dict[str, object]:
    return {
        "type": "collaboration_finding",
        "retention": "bounded_advisory_receipt",
        "candidate_for_short_term_memory": True,
        "candidate_for_long_term_memory": _long_term_candidate(topic),
        "summary": finding,
        "stores_full_transcript": False,
        "requires_review_before_memory_promotion": True,
    }


def _long_term_candidate(topic: str) -> bool:
    lower = _topic_key(topic)
    return any(
        marker in lower
        for marker in (
            "memory",
            "action",
            "governance",
            "substrate",
            "roadmap",
            "operator",
            "session",
            "participant",
            "body",
            "capability use",
            "toggle",
            "gate",
            "drift",
            "loop",
            "repetitive meta",
        )
    )


def _alignment_tags_for_topic(topic: str) -> list[str]:
    lower = _topic_key(topic)
    tags = ["developer_bridge", "collaboration", "advisory_receipt"]
    if "memory" in lower:
        tags.append("memory_contract")
    if "local model failure" in lower or "drift signal" in lower or _loop_recovery_topic(lower):
        tags.append("collaboration_learning")
    if _loop_recovery_topic(lower):
        tags.append("loop_recovery")
    if "action" in lower or "spoken" in lower or "typed" in lower:
        tags.append("governed_action_boundary")
    if "governance" in lower or "gate" in lower or "approval" in lower:
        tags.append("governance_gate")
    if "toggle state" in lower or "participant enabled" in lower or "participant was enabled" in lower:
        tags.append("participant_control")
    if "communication" in lower or "window" in lower:
        tags.append("operator_visibility")
    if "session summary" in lower or "sessions" in lower or "revisited" in lower or "raw transcript" in lower:
        tags.append("session_recall")
    if "ollama" in lower or "chatbot" in lower or "action readiness" in lower or "advisory only" in lower:
        tags.append("local_model_boundary")
    if "substrate complete" in lower or "roadmap alignment" in lower or "main francis build" in lower:
        tags.append("roadmap_alignment")
    if "body surface" in lower or "whole body" in lower or "capability use" in lower:
        tags.append("francis_body_map")
        tags.append("trust_gated_capability")
    return tags


def _topic_key(topic: str) -> str:
    return " ".join(str(topic or "").replace("_", " ").replace("-", " ").lower().split())


def _loop_recovery_topic(lower_topic_key: str) -> bool:
    return "repetitive meta loop" in lower_topic_key or (
        "prior surface" in lower_topic_key and "meta" in lower_topic_key
    )


def _state_path() -> Path:
    return data_dir() / "integrations" / "developer_bridge" / "collaboration_driver" / "state.json"


def _note_path(note_id: str) -> Path:
    return _notes_root() / f"{_safe_file_id(note_id)}.json"


def _summary_path(summary_id: str) -> Path:
    return _summaries_root() / f"{_safe_file_id(summary_id)}.json"


def _insight_path(insight_id: str) -> Path:
    return _insights_root() / f"{_safe_file_id(insight_id)}.json"


def _learning_path(event_id: str) -> Path:
    return _learning_root() / f"{_safe_file_id(event_id)}.json"


def _notes_root() -> Path:
    return data_dir() / "integrations" / "developer_bridge" / "collaboration_driver" / "notes"


def _summaries_root() -> Path:
    return data_dir() / "integrations" / "developer_bridge" / "collaboration_driver" / "summaries"


def _insights_root() -> Path:
    return data_dir() / "integrations" / "developer_bridge" / "collaboration_driver" / "insights"


def _learning_root() -> Path:
    return data_dir() / "integrations" / "developer_bridge" / "collaboration_driver" / "learning_events"


def _write_json_receipt(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".atomic-json-{os.getpid()}-{uuid4().hex[:12]}.tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


def _safe_file_id(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in value)[:180] or uuid4().hex[:12]


def _load_state() -> dict[str, object]:
    path = _state_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _empty_state()
    if not isinstance(data, dict) or data.get("kind") != _STATE_KIND:
        return _empty_state()
    data.setdefault("initialized", False)
    data.setdefault("closed", False)
    data.setdefault("turn_count", 0)
    data.setdefault("turns", [])
    data.setdefault("seen_ollama_ids", [])
    data.setdefault("last_codex_prompt_id", "")
    data.setdefault("last_ollama_prompt_id", "")
    data.setdefault("last_note_id", "")
    data.setdefault("last_insight_id", "")
    data.setdefault("last_learning_event_id", "")
    data.setdefault("last_learning_event_signature", "")
    data.setdefault("latest_learning_signal", {})
    data.setdefault("last_summary_id", "")
    data.setdefault("last_summary_turn", 0)
    data.setdefault("context_contract_id", "")
    data.setdefault("context_contract_ledgered_id", "")
    data.setdefault("context_contract_ledgered_at", "")
    data.setdefault("next_prompt_after", "")
    data.setdefault("session_id", f"driver-{uuid4().hex[:12]}")
    return data


def _empty_state() -> dict[str, object]:
    return {
        "kind": _STATE_KIND,
        "created_at": _utc_now(),
        "updated_at": _utc_now(),
        "initialized": False,
        "closed": False,
        "closed_at": "",
        "session_id": f"driver-{uuid4().hex[:12]}",
        "turn_count": 0,
        "turns": [],
        "seen_ollama_ids": [],
        "last_codex_prompt_id": "",
        "last_ollama_prompt_id": "",
        "last_note_id": "",
        "last_insight_id": "",
        "last_learning_event_id": "",
        "last_learning_event_signature": "",
        "latest_learning_signal": {},
        "last_summary_id": "",
        "last_summary_turn": 0,
        "context_contract_id": "",
        "context_contract_ledgered_id": "",
        "context_contract_ledgered_at": "",
        "next_prompt_after": "",
        "waiting_for_ollama": False,
        "governance": _governance(),
    }


def _save_state(state: dict[str, object]) -> None:
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = _utc_now()
    state["turns"] = _list(state.get("turns"))[-_MAX_TRACKED_IDS:]
    state["seen_ollama_ids"] = _list(state.get("seen_ollama_ids"))[-_MAX_TRACKED_IDS:]
    state["governance"] = _governance()
    tmp = path.with_name(f".atomic-json-{os.getpid()}-{uuid4().hex[:12]}.tmp")
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


def _session_id(state: dict[str, object]) -> str:
    session_id = str(state.get("session_id") or "").strip()
    if session_id:
        return session_id
    session_id = f"driver-{uuid4().hex[:12]}"
    state["session_id"] = session_id
    return session_id


def _turn_count(state: dict[str, object]) -> int:
    value = state.get("turn_count")
    if isinstance(value, int):
        return max(value, 0)
    if isinstance(value, str):
        text = value.strip()
    else:
        text = ""
    try:
        return max(int(text or "0"), 0)
    except ValueError:
        return 0


def _safe_int(value: object, *, default: int) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value.strip() or str(default))
        except ValueError:
            return default
    return default


def _clean_max_turns(value: int) -> int:
    try:
        return max(int(value), 0)
    except (TypeError, ValueError):
        return 0


def _turn_limit_reached(state: dict[str, object], max_turns: int) -> bool:
    return max_turns > 0 and _turn_count(state) >= max_turns


def _turn_label(turn_number: int, max_turns: int) -> str:
    if max_turns > 0:
        return f"turn {turn_number}/{max_turns}"
    return f"turn {turn_number}"


def _topic_for_turn(turn_number: int) -> str:
    return _TOPICS[(max(turn_number, 1) - 1) % len(_TOPICS)]


def _turn_gap_remaining(state: dict[str, object]) -> float:
    next_prompt_after = str(state.get("next_prompt_after") or "")
    if not next_prompt_after:
        return 0.0
    parsed = _parse_utc(next_prompt_after)
    if parsed is None:
        return 0.0
    remaining = (parsed - datetime.now(UTC)).total_seconds()
    if remaining <= 0:
        state["next_prompt_after"] = ""
        return 0.0
    return round(remaining, 3)


def _future_utc(seconds: float) -> str:
    return datetime.fromtimestamp(datetime.now(UTC).timestamp() + max(seconds, 0.0), UTC).isoformat()


def _parse_utc(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _closed_elapsed_seconds(state: dict[str, object]) -> float:
    closed_at = str(state.get("closed_at") or "")
    if not closed_at:
        return float("inf")
    parsed = _parse_utc(closed_at)
    if parsed is None:
        return float("inf")
    return max((datetime.now(UTC) - parsed).total_seconds(), 0.0)


def _mark_seen(state: dict[str, object], ids: list[str]) -> None:
    merged = [item for item in _list(state.get("seen_ollama_ids")) if item]
    for item_id in ids:
        if item_id and item_id not in merged:
            merged.append(item_id)
    state["seen_ollama_ids"] = merged[-_MAX_TRACKED_IDS:]


def _items(transcript: dict[str, object]) -> list[dict[str, object]]:
    items = transcript.get("items")
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def _item_id(item: dict[str, object]) -> str:
    return str(item.get("id") or "").strip()


def _list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _governance() -> dict[str, object]:
    return {
        "surface": "developer_bridge.collaboration_driver",
        "append_only_relay_writes": True,
        "writes_collaboration_notes": True,
        "writes_collaboration_insights": True,
        "writes_collaboration_learning_events": True,
        "writes_collaboration_summaries": True,
        "writes_collaboration_context_contract": True,
        "writes_continuity_summary": True,
        "stores_full_transcript": False,
        "context_contract_id": CONTEXT_CONTRACT_ID,
        "source_agent": "codex",
        "target_agent": "ollama",
        "event_gated": True,
        "waits_for_ollama_completion": True,
        "starts_arbitrary_commands": False,
        "executes_prompt": False,
        "grants_model_execution_authority": False,
        "grants_repo_mutation_authority": False,
        "grants_approval_authority": False,
        "raw_shell": False,
        "external_network": False,
    }


def _note_governance() -> dict[str, object]:
    return {
        "surface": "developer_bridge.collaboration_driver.notes",
        "advisory_only": True,
        "stores_full_transcript": False,
        "derived_from_relay_receipts": True,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "grants_approval_authority": False,
        "grants_model_authority": False,
    }


def _insight_governance() -> dict[str, object]:
    return {
        "surface": "developer_bridge.collaboration_driver.insights",
        "advisory_only": True,
        "stores_full_transcript": False,
        "derived_from_relay_receipts": True,
        "typed_review_surface": True,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "grants_approval_authority": False,
        "grants_memory_write_authority": False,
        "grants_model_authority": False,
    }


def _learning_governance() -> dict[str, object]:
    return {
        "surface": "developer_bridge.collaboration_driver.learning_events",
        "advisory_only": True,
        "stores_full_transcript": False,
        "derived_from_relay_receipts": True,
        "writes_continuity_summary": True,
        "records_failures_as_learning": True,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "grants_approval_authority": False,
        "grants_memory_write_authority": False,
        "grants_model_authority": False,
    }


def _learning_readback_governance() -> dict[str, object]:
    return {
        "surface": "developer_bridge.collaboration_driver.learning_events",
        "read_only": True,
        "reads_collaboration_learning_events": True,
        "writes_files": False,
        "stores_full_transcript": False,
        "calls_model": False,
        "trains_model": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "grants_approval_authority": False,
        "grants_memory_write_authority": False,
        "grants_model_authority": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="collaboration_driver",
        description="Event-gated Codex-to-Ollama conversation driver for the Francis collaboration relay.",
    )
    parser.add_argument("--watch", action="store_true", help="Poll for Ollama completion and submit the next turn.")
    parser.add_argument(
        "--ignore-existing",
        action="store_true",
        help="On first run, mark existing Ollama relay entries as history before seeding a fresh session.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Plan one driver turn without writing a relay receipt.")
    parser.add_argument("--poll-seconds", type=float, default=_DEFAULT_POLL_SECONDS)
    parser.add_argument("--max-turns", type=int, default=_MAX_TURNS)
    parser.add_argument("--turn-gap-seconds", type=float, default=_DEFAULT_TURN_GAP_SECONDS)
    parser.add_argument("--summary-every-turns", type=int, default=_DEFAULT_SUMMARY_EVERY_TURNS)
    parser.add_argument(
        "--repeat-closed",
        action="store_true",
        help="After a capped session closes, start a fresh bounded session after --session-gap-seconds.",
    )
    parser.add_argument("--session-gap-seconds", type=float, default=120.0)
    args = parser.parse_args(argv)

    interval = max(float(args.poll_seconds), 1.0)
    try:
        while True:
            result = drive_once(
                ignore_existing=bool(args.ignore_existing),
                max_turns=int(args.max_turns),
                dry_run=bool(args.dry_run),
                repeat_closed=bool(args.repeat_closed),
                session_gap_seconds=float(args.session_gap_seconds),
                turn_gap_seconds=float(args.turn_gap_seconds),
                summary_every_turns=int(args.summary_every_turns),
            )
            print(json.dumps(result, ensure_ascii=False, sort_keys=True), flush=True)
            if bool(args.dry_run) or not bool(args.watch):
                return 0
            time.sleep(interval)
    except KeyboardInterrupt:
        return 0
    except DeveloperBridgeError as exc:
        print(json.dumps(exc.to_dict(), indent=2, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
