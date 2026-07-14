"""Explicit, bounded game-demonstration sessions backed by Lens observations."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

from francis.governance.redaction import redact_secret_text
from francis.kernel.paths import data_dir
from francis.lens.atomic_io import atomic_write_json, read_json_object
from francis.lens.game_observer import LENS_GAME_OBSERVATION_KIND, LENS_GAME_OBSERVATION_VERSION
from francis.telemetry.audit import record as audit_record

GAME_TEACHING_SESSION_WRITE_SCOPE = "apprenticeship.game_teaching_session.write"
GAME_TEACHING_SESSION_CONTRACT_KIND = "francis.apprenticeship.game_teaching_session.contract"
GAME_TEACHING_SESSION_STATE_KIND = "francis.apprenticeship.game_teaching_session.state"
GAME_TEACHING_SESSION_STATUS_KIND = "francis.apprenticeship.game_teaching_session.status"
GAME_TEACHING_SESSION_START_RECEIPT_KIND = "francis.apprenticeship.game_teaching_session.start_receipt"
GAME_TEACHING_SEMANTIC_EVENT_KIND = "francis.apprenticeship.game_teaching.semantic_scene_transition"
GAME_TEACHING_EPISODE_RECEIPT_KIND = "francis.apprenticeship.game_teaching.episode_receipt"
GAME_TEACHING_EPISODE_RECEIPTS_KIND = "francis.apprenticeship.game_teaching.episode_receipts"
GAME_TEACHING_CONTRACT_VERSION = 1

MIN_GAME_TEACHING_DURATION_SECONDS = 30
MAX_GAME_TEACHING_DURATION_SECONDS = 28_800
MIN_GAME_TEACHING_EVENTS = 1
MAX_GAME_TEACHING_EVENTS = 1_000

_ALLOWED_ENV_PROFILES = {"dev", "workstation", "local", "test"}
_ALLOWED_OUTCOMES = {"completed", "cancelled", "needs_review"}
_TARGET_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,63}$")
_SCENE_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_]{0,47}$")
_SESSION_ID_PATTERN = re.compile(r"^game_teaching_[a-f0-9]{16}$")
_EPISODE_RECEIPT_ID_PATTERN = re.compile(r"^game_teaching_episode_[a-f0-9]{16}$")


class GameTeachingRecorder(Protocol):
    def record(self, observation: dict[str, Any], *, observed_at: float | None = None) -> dict[str, Any]: ...


def game_teaching_session_contract() -> dict[str, Any]:
    return {
        "ok": True,
        "kind": GAME_TEACHING_SESSION_CONTRACT_KIND,
        "version": GAME_TEACHING_CONTRACT_VERSION,
        "status": "ready",
        "source_id": "apprenticeship",
        "pipeline_stage": "demonstrate",
        "source_observation_kind": LENS_GAME_OBSERVATION_KIND,
        "source_observation_version": LENS_GAME_OBSERVATION_VERSION,
        "capture_mode": "explicit_semantic_scene_transition_session",
        "requires_explicit_start": True,
        "requires_explicit_stop": True,
        "requires_target_id": True,
        "requires_intent_label": True,
        "requires_declared_scope": True,
        "requires_success_condition": True,
        "min_duration_seconds": MIN_GAME_TEACHING_DURATION_SECONDS,
        "max_duration_seconds": MAX_GAME_TEACHING_DURATION_SECONDS,
        "min_events": MIN_GAME_TEACHING_EVENTS,
        "max_events": MAX_GAME_TEACHING_EVENTS,
        "records_scene_transitions_only": True,
        "records_raw_pixels": False,
        "records_window_titles": False,
        "records_keyboard_content": False,
        "records_user_mouse": False,
        "writes_memory": False,
        "learning_authority": False,
        "reward_authority": False,
        "input_execution_authority": False,
        "creates_capability": False,
        "promotes_skill": False,
        "governance": _governance(),
        "next_smallest_truthful_gap": "operator_review_of_game_teaching_episode",
    }


def start_game_teaching_session(
    *,
    actor: Any,
    reason: Any,
    target_id: Any,
    intent_label: Any,
    declared_scope: Any,
    success_condition: Any,
    max_duration_seconds: Any = 3_600,
    max_events: Any = 300,
    now: float | None = None,
) -> dict[str, Any]:
    if _env_profile() not in _ALLOWED_ENV_PROFILES:
        return _blocked_action("blocked_environment_profile", "game_teaching_session_dev_or_workstation_only")

    observed_at = _validated_timestamp(now)
    safe_target_id = _safe_text(target_id).casefold()
    safe_actor = _redacted_text(actor)[:240]
    safe_reason = _redacted_text(reason)[:500]
    safe_intent = _redacted_text(intent_label)[:240]
    safe_scope = _redacted_text(declared_scope)[:500]
    safe_success = _redacted_text(success_condition)[:500]
    duration = _bounded_int(
        max_duration_seconds,
        minimum=MIN_GAME_TEACHING_DURATION_SECONDS,
        maximum=MAX_GAME_TEACHING_DURATION_SECONDS,
    )
    event_limit = _bounded_int(
        max_events,
        minimum=MIN_GAME_TEACHING_EVENTS,
        maximum=MAX_GAME_TEACHING_EVENTS,
    )
    if not _TARGET_ID_PATTERN.fullmatch(safe_target_id):
        return _blocked_action("invalid_request", "game_teaching_target_id_invalid")
    if not safe_actor or not safe_reason or not safe_intent or not safe_scope or not safe_success:
        return _blocked_action("invalid_request", "game_teaching_required_context_missing")
    if duration is None:
        return _blocked_action("invalid_request", "game_teaching_duration_invalid")
    if event_limit is None:
        return _blocked_action("invalid_request", "game_teaching_event_limit_invalid")

    prior = read_json_object(_session_state_path())
    if _state_contract_valid(prior) and str(prior.get("status") or "") in {"active", "finalizing"}:
        return _blocked_action(
            "active_session_exists",
            "game_teaching_session_requires_explicit_stop",
            session_id=str(prior.get("session_id") or ""),
        )

    session_id = f"game_teaching_{uuid.uuid4().hex[:16]}"
    start_receipt_id = f"game_teaching_start_{uuid.uuid4().hex[:16]}"
    deadline_at = observed_at + duration
    start_receipt = {
        "ok": True,
        "kind": GAME_TEACHING_SESSION_START_RECEIPT_KIND,
        "version": GAME_TEACHING_CONTRACT_VERSION,
        "receipt_id": start_receipt_id,
        "session_id": session_id,
        "actor": safe_actor,
        "reason": safe_reason,
        "target_id": safe_target_id,
        "intent_label": safe_intent,
        "declared_scope": safe_scope,
        "success_condition": safe_success,
        "started_at": observed_at,
        "deadline_at": deadline_at,
        "max_duration_seconds": duration,
        "max_events": event_limit,
        "capture_mode": "explicit_semantic_scene_transition_session",
        "writes_receipt": True,
        "starts_teaching_session": True,
        "governance": _governance(),
    }
    _append_jsonl(_start_receipts_path(), start_receipt)
    state = {
        "kind": GAME_TEACHING_SESSION_STATE_KIND,
        "version": GAME_TEACHING_CONTRACT_VERSION,
        "status": "active",
        "session_id": session_id,
        "start_receipt_id": start_receipt_id,
        "target_id": safe_target_id,
        "actor": safe_actor,
        "reason": safe_reason,
        "intent_label": safe_intent,
        "declared_scope": safe_scope,
        "success_condition": safe_success,
        "started_at": observed_at,
        "deadline_at": deadline_at,
        "max_duration_seconds": duration,
        "max_events": event_limit,
        "capture_mode": "explicit_semantic_scene_transition_session",
        "review_required": True,
        "governance": _governance(),
    }
    atomic_write_json(_session_state_path(), state)
    audit_record(
        "apprenticeship.game_teaching_session_started",
        actor=safe_actor,
        reason=safe_reason,
        session_id=session_id,
        target_id=safe_target_id,
        receipt_id=start_receipt_id,
    )
    return {
        **game_teaching_session_status(now=observed_at),
        "action": "start_game_teaching_session",
        "receipt_id": start_receipt_id,
        "writes_receipt": True,
        "starts_teaching_session": True,
    }


def stop_game_teaching_session(
    *,
    actor: Any,
    reason: Any,
    session_id: Any,
    outcome: Any = "needs_review",
    notes: Any = "",
    now: float | None = None,
) -> dict[str, Any]:
    if _env_profile() not in _ALLOWED_ENV_PROFILES:
        return _blocked_action("blocked_environment_profile", "game_teaching_session_dev_or_workstation_only")

    stopped_at = _validated_timestamp(now)
    safe_session_id = _safe_text(session_id)
    safe_actor = _redacted_text(actor)[:240]
    safe_reason = _redacted_text(reason)[:500]
    safe_notes = _redacted_text(notes)[:500]
    safe_outcome = _safe_text(outcome).casefold()
    if not safe_actor or not safe_reason or not _SESSION_ID_PATTERN.fullmatch(safe_session_id):
        return _blocked_action("invalid_request", "game_teaching_stop_context_invalid")
    if safe_outcome not in _ALLOWED_OUTCOMES:
        return _blocked_action("invalid_request", "game_teaching_outcome_invalid")

    state = read_json_object(_session_state_path())
    if not _state_contract_valid(state):
        return _blocked_action("no_active_session", "game_teaching_session_not_found")
    if str(state.get("session_id") or "") != safe_session_id:
        return _blocked_action("session_mismatch", "game_teaching_session_id_mismatch")

    existing = _episode_for_session(safe_session_id)
    if existing:
        if str(state.get("status") or "") != "stopped":
            _finish_stopped_state(state, existing)
        return {**existing, "idempotent": True}
    if str(state.get("status") or "") not in {"active", "finalizing"}:
        return _blocked_action("no_active_session", "game_teaching_session_not_active")

    finalizing = {**state, "status": "finalizing", "stop_requested_at": stopped_at}
    atomic_write_json(_session_state_path(), finalizing)
    events = _read_events(safe_session_id)
    episode_receipt_id = f"game_teaching_episode_{uuid.uuid4().hex[:16]}"
    scene_sequence = [
        {
            "sequence": _safe_int(event.get("sequence")),
            "scene_id": _safe_text(event.get("scene_id")),
            "observed_at": _safe_float(event.get("observed_at")),
            "confidence": _safe_float(event.get("confidence")),
            "margin": _safe_float(event.get("margin")),
            "source_frame_id": _safe_text(event.get("source_frame_id")),
        }
        for event in events
    ]
    receipt = {
        "ok": True,
        "kind": GAME_TEACHING_EPISODE_RECEIPT_KIND,
        "version": GAME_TEACHING_CONTRACT_VERSION,
        "receipt_id": episode_receipt_id,
        "session_id": safe_session_id,
        "start_receipt_id": _safe_text(state.get("start_receipt_id")),
        "actor": safe_actor,
        "reason": safe_reason,
        "operator_outcome": safe_outcome,
        "notes": safe_notes,
        "target_id": _safe_text(state.get("target_id")),
        "intent_label": _safe_text(state.get("intent_label")),
        "declared_scope": _safe_text(state.get("declared_scope")),
        "success_condition": _safe_text(state.get("success_condition")),
        "started_at": _safe_float(state.get("started_at")),
        "stopped_at": stopped_at,
        "duration_seconds": round(max(0.0, stopped_at - (_safe_float(state.get("started_at")) or stopped_at)), 3),
        "event_count": len(events),
        "scene_transition_count": len(scene_sequence),
        "scene_sequence": scene_sequence,
        "model_ids": _dedupe_text(_safe_text(event.get("model_id")) for event in events),
        "authority_receipt_ids": _dedupe_text(_safe_text(event.get("authority_receipt_id")) for event in events),
        "source_observation_kind": LENS_GAME_OBSERVATION_KIND,
        "source_observation_version": LENS_GAME_OBSERVATION_VERSION,
        "capture_mode": "explicit_semantic_scene_transition_session",
        "review_state": "pending_operator_review",
        "ready_for_operator_review": bool(events),
        "eligible_for_replay": False,
        "eligible_for_generalization": False,
        "eligible_for_skillization": False,
        "writes_receipt": True,
        "writes_memory": False,
        "creates_capability": False,
        "promotes_skill": False,
        "governance": _governance(),
        "next_smallest_truthful_gap": "operator_review_of_game_teaching_episode",
    }
    receipt["integrity_algorithm"] = "sha256"
    receipt["episode_digest"] = game_teaching_episode_digest(receipt)
    _append_jsonl(_episode_receipts_path(), receipt)
    _finish_stopped_state(finalizing, receipt)
    audit_record(
        "apprenticeship.game_teaching_session_stopped",
        actor=safe_actor,
        reason=safe_reason,
        session_id=safe_session_id,
        receipt_id=episode_receipt_id,
        event_count=len(events),
    )
    return receipt


def game_teaching_session_status(*, now: float | None = None) -> dict[str, Any]:
    observed_at = _validated_timestamp(now)
    state = read_json_object(_session_state_path())
    if not state:
        return _status_payload(status="idle", observed_at=observed_at)
    if not _state_contract_valid(state):
        return _status_payload(
            status="unavailable",
            observed_at=observed_at,
            blockers=["game_teaching_session_state_invalid"],
        )

    session_id = _safe_text(state.get("session_id"))
    events = _read_events(session_id)
    event_count = len(events)
    max_events = _safe_int(state.get("max_events"))
    deadline_at = _safe_float(state.get("deadline_at")) or observed_at
    raw_status = _safe_text(state.get("status"))
    limit_reached = bool(max_events and event_count >= max_events)
    duration_reached = observed_at >= deadline_at
    recording_active = raw_status == "active" and not limit_reached and not duration_reached
    blockers: list[str] = []
    status = raw_status
    if raw_status == "active" and limit_reached:
        status = "awaiting_explicit_stop"
        blockers.append("game_teaching_event_limit_reached")
    elif raw_status == "active" and duration_reached:
        status = "awaiting_explicit_stop"
        blockers.append("game_teaching_duration_limit_reached")
    elif raw_status == "finalizing":
        blockers.append("game_teaching_session_finalization_incomplete")

    latest = events[-1] if events else {}
    return _status_payload(
        status=status,
        observed_at=observed_at,
        state=state,
        event_count=event_count,
        latest_event=latest,
        recording_active=recording_active,
        blockers=blockers,
    )


def game_teaching_episode_receipts(*, limit: int = 20) -> dict[str, Any]:
    safe_limit = max(1, min(int(limit), 100))
    items = _read_jsonl(_episode_receipts_path())[-safe_limit:]
    return {
        "ok": True,
        "kind": GAME_TEACHING_EPISODE_RECEIPTS_KIND,
        "version": GAME_TEACHING_CONTRACT_VERSION,
        "status": "ready",
        "count": len(items),
        "items": items,
        "reads_receipts": True,
        "writes_receipts": False,
        "governance": _governance(),
    }


def game_teaching_episode_receipt(receipt_id: Any) -> dict[str, Any]:
    safe_receipt_id = _safe_text(receipt_id)
    if not _EPISODE_RECEIPT_ID_PATTERN.fullmatch(safe_receipt_id):
        return {}
    for receipt in reversed(_read_jsonl(_episode_receipts_path())):
        if (
            receipt.get("kind") == GAME_TEACHING_EPISODE_RECEIPT_KIND
            and receipt.get("version") == GAME_TEACHING_CONTRACT_VERSION
            and _safe_text(receipt.get("receipt_id")) == safe_receipt_id
        ):
            return receipt
    return {}


def latest_game_teaching_episode_receipt() -> dict[str, Any]:
    for receipt in reversed(_read_jsonl(_episode_receipts_path())):
        if (
            receipt.get("kind") == GAME_TEACHING_EPISODE_RECEIPT_KIND
            and receipt.get("version") == GAME_TEACHING_CONTRACT_VERSION
            and _EPISODE_RECEIPT_ID_PATTERN.fullmatch(_safe_text(receipt.get("receipt_id")))
        ):
            return receipt
    return {}


def game_teaching_episode_digest(receipt: dict[str, Any]) -> str:
    payload = {
        field: receipt.get(field)
        for field in (
            "kind",
            "version",
            "receipt_id",
            "session_id",
            "start_receipt_id",
            "actor",
            "reason",
            "operator_outcome",
            "notes",
            "target_id",
            "intent_label",
            "declared_scope",
            "success_condition",
            "started_at",
            "stopped_at",
            "duration_seconds",
            "event_count",
            "scene_transition_count",
            "scene_sequence",
            "model_ids",
            "authority_receipt_ids",
            "source_observation_kind",
            "source_observation_version",
            "capture_mode",
        )
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class GameTeachingObservationRecorder:
    """Project allowlisted scene transitions into an explicit teaching episode."""

    def __init__(self, *, clock: Callable[[], float] = time.time) -> None:
        self._clock = clock

    def record(self, observation: dict[str, Any], *, observed_at: float | None = None) -> dict[str, Any]:
        now = self._clock() if observed_at is None else _validated_timestamp(observed_at)
        status = game_teaching_session_status(now=now)
        if status.get("recording_active") is not True:
            return status

        state = read_json_object(_session_state_path())
        reason = _observation_blocker(observation, target_id=_safe_text(state.get("target_id")))
        if reason:
            return {**status, "capture_status": "observation_blocked", "blockers": [reason]}

        session_id = _safe_text(state.get("session_id"))
        events = _read_events(session_id)
        scene = _as_dict(observation.get("scene"))
        scene_id = _safe_text(scene.get("id"))
        if events and _safe_text(events[-1].get("scene_id")) == scene_id:
            return {**status, "capture_status": "scene_unchanged", "event_written": False}

        max_events = _safe_int(state.get("max_events"))
        if len(events) >= max_events:
            return {
                **game_teaching_session_status(now=now),
                "capture_status": "event_limit_reached",
                "event_written": False,
            }

        classification = _as_dict(observation.get("classification"))
        model = _as_dict(observation.get("model"))
        runtime_identity = _as_dict(observation.get("runtime_identity"))
        event = {
            "kind": GAME_TEACHING_SEMANTIC_EVENT_KIND,
            "version": GAME_TEACHING_CONTRACT_VERSION,
            "session_id": session_id,
            "sequence": len(events) + 1,
            "observed_at": now,
            "target_id": _safe_text(_as_dict(observation.get("target")).get("id")),
            "scene_id": scene_id,
            "confidence": _safe_float(scene.get("confidence")),
            "margin": _safe_float(scene.get("margin")),
            "source_frame_id": _safe_text(observation.get("source_frame_id")),
            "classification_source_frame_id": _safe_text(classification.get("source_frame_id")),
            "classified_at": _safe_float(classification.get("classified_at")),
            "model_id": _safe_text(model.get("id")),
            "authority_receipt_id": _safe_text(runtime_identity.get("authority_receipt_id")),
            "source_observation_kind": LENS_GAME_OBSERVATION_KIND,
            "source_observation_version": LENS_GAME_OBSERVATION_VERSION,
            "governance": _governance(),
        }
        _append_jsonl(_session_events_path(session_id), event)
        updated = game_teaching_session_status(now=now)
        return {**updated, "capture_status": "scene_transition_recorded", "event_written": True}


def game_teaching_recording_error_status() -> dict[str, Any]:
    return _status_payload(
        status="recording_error",
        observed_at=time.time(),
        blockers=["game_teaching_semantic_event_write_failed"],
    )


def _status_payload(
    *,
    status: str,
    observed_at: float,
    state: dict[str, Any] | None = None,
    event_count: int = 0,
    latest_event: dict[str, Any] | None = None,
    recording_active: bool = False,
    blockers: list[str] | None = None,
) -> dict[str, Any]:
    session = state or {}
    latest = latest_event or {}
    deadline_at = _safe_float(session.get("deadline_at"))
    return {
        "ok": status not in {"unavailable", "recording_error"},
        "kind": GAME_TEACHING_SESSION_STATUS_KIND,
        "version": GAME_TEACHING_CONTRACT_VERSION,
        "status": status,
        "source_id": "apprenticeship",
        "session_id": _safe_text(session.get("session_id")),
        "target_id": _safe_text(session.get("target_id")),
        "intent_label": _safe_text(session.get("intent_label")),
        "declared_scope": _safe_text(session.get("declared_scope")),
        "success_condition": _safe_text(session.get("success_condition")),
        "started_at": _safe_float(session.get("started_at")),
        "deadline_at": deadline_at,
        "remaining_seconds": round(max(0.0, deadline_at - observed_at), 3) if deadline_at is not None else None,
        "recording_active": recording_active,
        "event_count": event_count,
        "max_events": _safe_int(session.get("max_events")),
        "latest_scene_id": _safe_text(latest.get("scene_id")),
        "latest_event_at": _safe_float(latest.get("observed_at")),
        "review_required": bool(session.get("review_required")),
        "start_receipt_id": _safe_text(session.get("start_receipt_id")),
        "episode_receipt_id": _safe_text(session.get("episode_receipt_id")),
        "capture_mode": "explicit_semantic_scene_transition_session",
        "blockers": blockers or [],
        "writes_receipt": False,
        "writes_memory": False,
        "learning_authority": False,
        "reward_authority": False,
        "input_execution_authority": False,
        "creates_capability": False,
        "promotes_skill": False,
        "governance": _governance(),
    }


def _observation_blocker(observation: dict[str, Any], *, target_id: str) -> str:
    if observation.get("kind") != LENS_GAME_OBSERVATION_KIND or observation.get("version") != 1:
        return "game_teaching_observation_contract_invalid"
    target = _as_dict(observation.get("target"))
    foreground = _as_dict(observation.get("foreground"))
    scene = _as_dict(observation.get("scene"))
    model = _as_dict(observation.get("model"))
    runtime_identity = _as_dict(observation.get("runtime_identity"))
    governance = _as_dict(observation.get("governance"))
    if _safe_text(target.get("id")) != target_id:
        return "game_teaching_observation_target_mismatch"
    if target.get("foreground") is not True or foreground.get("target_match") is not True:
        return "game_teaching_target_not_foreground"
    if observation.get("ready") is not True or observation.get("semantic_scene_ready") is not True:
        return "game_teaching_semantic_scene_not_ready"
    if scene.get("ready") is not True or not _SCENE_ID_PATTERN.fullmatch(_safe_text(scene.get("id"))):
        return "game_teaching_scene_invalid"
    confidence = _safe_float(scene.get("confidence"))
    margin = _safe_float(scene.get("margin"))
    if confidence is None or not 0.0 <= confidence <= 1.0 or margin is None or not 0.0 <= margin <= 1.0:
        return "game_teaching_scene_score_invalid"
    if not _safe_text(observation.get("source_frame_id")) or not _safe_text(
        runtime_identity.get("authority_receipt_id")
    ):
        return "game_teaching_observation_lineage_missing"
    if model.get("remote_inference") is not False:
        return "game_teaching_remote_inference_denied"
    required_true = ("observation_only", "local_inference_only")
    required_false = (
        "remote_frame_transfer",
        "raw_pixels_in_state",
        "window_titles_captured",
        "keyboard_content_captured",
        "user_mouse_captured",
        "input_execution_authority",
        "memory_write",
        "learning_authority",
        "reward_authority",
    )
    if any(governance.get(field) is not True for field in required_true) or any(
        governance.get(field) is not False for field in required_false
    ):
        return "game_teaching_observation_governance_invalid"
    return ""


def _finish_stopped_state(state: dict[str, Any], receipt: dict[str, Any]) -> None:
    atomic_write_json(
        _session_state_path(),
        {
            **state,
            "status": "stopped",
            "stopped_at": receipt.get("stopped_at"),
            "episode_receipt_id": receipt.get("receipt_id"),
            "event_count": receipt.get("event_count"),
            "review_required": True,
        },
    )


def _episode_for_session(session_id: str) -> dict[str, Any]:
    for receipt in reversed(_read_jsonl(_episode_receipts_path())):
        if _safe_text(receipt.get("session_id")) == session_id:
            return receipt
    return {}


def _state_contract_valid(state: dict[str, Any]) -> bool:
    governance = _as_dict(state.get("governance"))
    return bool(
        state.get("kind") == GAME_TEACHING_SESSION_STATE_KIND
        and state.get("version") == GAME_TEACHING_CONTRACT_VERSION
        and _SESSION_ID_PATTERN.fullmatch(_safe_text(state.get("session_id")))
        and _TARGET_ID_PATTERN.fullmatch(_safe_text(state.get("target_id")))
        and str(state.get("status") or "") in {"active", "finalizing", "stopped"}
        and governance.get("explicit_start_stop_required") is True
        and governance.get("semantic_transitions_only") is True
        and governance.get("learning_authority") is False
        and governance.get("input_execution_authority") is False
    )


def _governance() -> dict[str, Any]:
    return {
        "required_scope": GAME_TEACHING_SESSION_WRITE_SCOPE,
        "explicit_start_stop_required": True,
        "semantic_transitions_only": True,
        "raw_pixels_persisted": False,
        "window_titles_persisted": False,
        "keyboard_content_captured": False,
        "user_mouse_captured": False,
        "remote_frame_transfer": False,
        "passive_learning": False,
        "hidden_retention": False,
        "memory_write": False,
        "learning_authority": False,
        "reward_authority": False,
        "input_execution_authority": False,
        "automatic_replay": False,
        "automatic_generalization": False,
        "automatic_skillization": False,
        "automatic_capability_promotion": False,
        "operator_review_required": True,
    }


def _blocked_action(status: str, reason: str, *, session_id: str = "") -> dict[str, Any]:
    return {
        "ok": False,
        "kind": GAME_TEACHING_SESSION_STATUS_KIND,
        "version": GAME_TEACHING_CONTRACT_VERSION,
        "status": status,
        "reason": reason,
        "session_id": session_id,
        "recording_active": False,
        "writes_receipt": False,
        "writes_memory": False,
        "learning_authority": False,
        "reward_authority": False,
        "input_execution_authority": False,
        "creates_capability": False,
        "promotes_skill": False,
        "governance": _governance(),
    }


def _session_state_path() -> Path:
    return data_dir() / "runtime" / "apprenticeship" / "game-teaching-session.json"


def _session_events_path(session_id: str) -> Path:
    if not _SESSION_ID_PATTERN.fullmatch(session_id):
        raise ValueError("game_teaching_session_id_invalid")
    return data_dir() / "logs" / "apprenticeship" / "game-teaching-events" / f"{session_id}.jsonl"


def _start_receipts_path() -> Path:
    return data_dir() / "logs" / "apprenticeship" / "game_teaching_session_start_receipts.jsonl"


def _episode_receipts_path() -> Path:
    return data_dir() / "logs" / "apprenticeship" / "game_teaching_episode_receipts.jsonl"


def _read_events(session_id: str) -> list[dict[str, Any]]:
    if not _SESSION_ID_PATTERN.fullmatch(session_id):
        return []
    return [
        item
        for item in _read_jsonl(_session_events_path(session_id))
        if item.get("kind") == GAME_TEACHING_SEMANTIC_EVENT_KIND
        and item.get("version") == GAME_TEACHING_CONTRACT_VERSION
        and _safe_text(item.get("session_id")) == session_id
    ][:MAX_GAME_TEACHING_EVENTS]


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True, sort_keys=True, allow_nan=False) + "\n")
        handle.flush()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    items: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    except OSError:
        return []
    for line in lines:
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            items.append(item)
    return items


def _validated_timestamp(value: float | None) -> float:
    observed_at = time.time() if value is None else float(value)
    if not math.isfinite(observed_at) or observed_at < 0.0:
        raise ValueError("game_teaching_timestamp_invalid")
    return observed_at


def _bounded_int(value: Any, *, minimum: int, maximum: int) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return parsed if minimum <= parsed <= maximum else None


def _safe_int(value: Any) -> int:
    parsed = _bounded_int(value, minimum=0, maximum=1_000_000_000)
    return parsed or 0


def _safe_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return parsed if math.isfinite(parsed) else None


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value).strip()
    except Exception:
        return ""


def _redacted_text(value: Any) -> str:
    return redact_secret_text(_safe_text(value))


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _dedupe_text(values: Any) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _env_profile() -> str:
    return _safe_text(os.getenv("FRANCIS_ENV_PROFILE")).casefold() or "dev"


__all__ = [
    "GAME_TEACHING_CONTRACT_VERSION",
    "GAME_TEACHING_EPISODE_RECEIPT_KIND",
    "GAME_TEACHING_SEMANTIC_EVENT_KIND",
    "GAME_TEACHING_SESSION_STATUS_KIND",
    "GAME_TEACHING_SESSION_WRITE_SCOPE",
    "GameTeachingObservationRecorder",
    "GameTeachingRecorder",
    "game_teaching_episode_receipts",
    "game_teaching_recording_error_status",
    "game_teaching_session_contract",
    "game_teaching_session_status",
    "start_game_teaching_session",
    "stop_game_teaching_session",
]
