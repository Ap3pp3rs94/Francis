"""Operator review and deterministic semantic replay for game teaching episodes."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any

from francis.apprenticeship_game_teaching import (
    GAME_TEACHING_CONTRACT_VERSION,
    GAME_TEACHING_EPISODE_RECEIPT_KIND,
    game_teaching_episode_digest,
    game_teaching_episode_receipt,
    latest_game_teaching_episode_receipt,
)
from francis.governance.redaction import redact_secret_text
from francis.kernel.paths import data_dir
from francis.telemetry.audit import record as audit_record

GAME_TEACHING_EPISODE_REVIEW_WRITE_SCOPE = "apprenticeship.game_teaching_episode_review.write"
GAME_TEACHING_EPISODE_REVIEW_CONTRACT_KIND = "francis.apprenticeship.game_teaching_episode_review.contract"
GAME_TEACHING_EPISODE_REVIEW_STATUS_KIND = "francis.apprenticeship.game_teaching_episode_review.status"
GAME_TEACHING_EPISODE_REPLAY_KIND = "francis.apprenticeship.game_teaching_episode.semantic_replay"
GAME_TEACHING_EPISODE_REVIEW_RECEIPT_KIND = "francis.apprenticeship.game_teaching_episode_review.receipt"
GAME_TEACHING_EPISODE_REVIEW_RECEIPTS_KIND = "francis.apprenticeship.game_teaching_episode_review.receipts"
GAME_TEACHING_EPISODE_REVIEW_VERSION = 1

MAX_REPLAY_PAGE_SIZE = 100
MAX_REVIEW_CORRECTIONS = 50

_ALLOWED_ENV_PROFILES = {"dev", "workstation", "local", "test"}
_ALLOWED_DECISIONS = {"accepted", "needs_correction", "rejected"}
_ALLOWED_CORRECTION_TYPES = {
    "branch",
    "intent",
    "missing_transition",
    "optional_transition",
    "other",
    "scene_label",
    "scope",
    "validation",
}
_EPISODE_RECEIPT_ID_PATTERN = re.compile(r"^game_teaching_episode_[a-f0-9]{16}$")


def game_teaching_episode_review_contract() -> dict[str, Any]:
    return {
        "ok": True,
        "kind": GAME_TEACHING_EPISODE_REVIEW_CONTRACT_KIND,
        "version": GAME_TEACHING_EPISODE_REVIEW_VERSION,
        "status": "ready",
        "source_id": "apprenticeship",
        "pipeline_stage": "replay",
        "requires_nonempty_episode": True,
        "requires_episode_digest": True,
        "requires_explicit_operator_review": True,
        "validates_declared_scene_confirmation_policy": True,
        "review_decisions": sorted(_ALLOWED_DECISIONS),
        "correction_types": sorted(_ALLOWED_CORRECTION_TYPES),
        "max_corrections": MAX_REVIEW_CORRECTIONS,
        "replay_mode": "deterministic_semantic_timeline_simulation",
        "replay_is_read_only": True,
        "replay_executes_input": False,
        "replay_runs_tools": False,
        "replay_runs_shell": False,
        "replay_starts_processes": False,
        "writes_memory": False,
        "learning_authority": False,
        "reward_authority": False,
        "input_execution_authority": False,
        "automatic_generalization": False,
        "automatic_skillization": False,
        "automatic_capability_promotion": False,
        "governance": _governance(),
        "next_smallest_truthful_gap": "capture_nonempty_game_teaching_episode",
    }


def game_teaching_episode_review_status(*, episode_receipt_id: Any = "") -> dict[str, Any]:
    requested_id = _safe_text(episode_receipt_id)
    if requested_id and not _EPISODE_RECEIPT_ID_PATTERN.fullmatch(requested_id):
        return _status_payload(
            status="invalid_request",
            blockers=["game_teaching_episode_receipt_id_invalid"],
        )

    episode = game_teaching_episode_receipt(requested_id) if requested_id else latest_game_teaching_episode_receipt()
    if not episode:
        return _status_payload(
            status="awaiting_episode",
            blockers=["game_teaching_episode_not_found"],
        )

    validation = _validate_episode(episode)
    receipt_id = _safe_text(episode.get("receipt_id"))
    reviews = _review_receipts_for_episode(receipt_id)
    latest_review = reviews[-1] if reviews else {}
    blockers = list(validation["blockers"])
    episode_digest = _safe_text(episode.get("episode_digest"))
    if latest_review and _safe_text(latest_review.get("episode_digest")) != episode_digest:
        blockers.append("game_teaching_episode_changed_after_review")

    replay_ready = bool(validation["ready"] and not blockers)
    decision = _safe_text(latest_review.get("decision"))
    accepted = decision == "accepted" and replay_ready
    if not replay_ready:
        status = "episode_invalid"
    elif accepted:
        status = "operator_accepted"
    elif decision == "needs_correction":
        status = "correction_required"
    elif decision == "rejected":
        status = "operator_rejected"
    else:
        status = "pending_operator_review"

    return _status_payload(
        status=status,
        episode=episode,
        latest_review=latest_review,
        replay_ready=replay_ready,
        blockers=_dedupe_text(blockers),
    )


def game_teaching_episode_replay(
    *,
    episode_receipt_id: Any,
    cursor: Any = 0,
    limit: Any = 50,
) -> dict[str, Any]:
    safe_receipt_id = _safe_text(episode_receipt_id)
    status = game_teaching_episode_review_status(episode_receipt_id=safe_receipt_id)
    safe_cursor = max(0, _safe_int(cursor))
    safe_limit = max(1, min(_safe_int(limit) or 50, MAX_REPLAY_PAGE_SIZE))
    if status.get("replay_ready") is not True:
        return {
            "ok": False,
            "kind": GAME_TEACHING_EPISODE_REPLAY_KIND,
            "version": GAME_TEACHING_EPISODE_REVIEW_VERSION,
            "status": status.get("status", "blocked"),
            "episode_receipt_id": safe_receipt_id,
            "episode_digest": status.get("episode_digest", ""),
            "cursor": safe_cursor,
            "limit": safe_limit,
            "total_steps": status.get("event_count", 0),
            "steps": [],
            "blockers": status.get("blockers", []),
            "executes_replay": False,
            "writes_receipt": False,
            "writes_memory": False,
            "learning_authority": False,
            "input_execution_authority": False,
            "governance": _governance(),
        }

    episode = game_teaching_episode_receipt(safe_receipt_id)
    steps = _semantic_replay_steps(episode)
    page = steps[safe_cursor : safe_cursor + safe_limit]
    next_cursor = safe_cursor + len(page)
    complete = next_cursor >= len(steps)
    replay_digest = _canonical_digest(
        {
            "episode_receipt_id": safe_receipt_id,
            "episode_digest": episode.get("episode_digest"),
            "steps": steps,
        }
    )
    return {
        "ok": True,
        "kind": GAME_TEACHING_EPISODE_REPLAY_KIND,
        "version": GAME_TEACHING_EPISODE_REVIEW_VERSION,
        "status": "ready",
        "source_id": "apprenticeship",
        "episode_receipt_id": safe_receipt_id,
        "episode_digest": _safe_text(episode.get("episode_digest")),
        "replay_digest": replay_digest,
        "replay_mode": "deterministic_semantic_timeline_simulation",
        "cursor": safe_cursor,
        "limit": safe_limit,
        "total_steps": len(steps),
        "next_cursor": None if complete else next_cursor,
        "complete": complete,
        "steps": page,
        "operator_review_required": status.get("operator_review_required") is True,
        "latest_review_receipt_id": status.get("latest_review_receipt_id", ""),
        "executes_replay": False,
        "runs_tools": False,
        "runs_shell": False,
        "starts_processes": False,
        "writes_receipt": False,
        "writes_memory": False,
        "learning_authority": False,
        "reward_authority": False,
        "input_execution_authority": False,
        "generalization_performed": False,
        "skillization_performed": False,
        "governance": _governance(),
    }


def record_game_teaching_episode_review(
    *,
    actor: Any,
    reason: Any,
    episode_receipt_id: Any,
    decision: Any,
    summary: Any,
    corrections: Any = None,
    now: float | None = None,
) -> dict[str, Any]:
    if _env_profile() not in _ALLOWED_ENV_PROFILES:
        return _blocked_action(
            "blocked_environment_profile",
            "game_teaching_episode_review_dev_or_workstation_only",
        )

    safe_actor = _redacted_text(actor)[:240]
    safe_reason = _redacted_text(reason)[:500]
    safe_receipt_id = _safe_text(episode_receipt_id)
    safe_decision = _safe_text(decision).casefold()
    safe_summary = _redacted_text(summary)[:1_000]
    if (
        not safe_actor
        or not safe_reason
        or not safe_summary
        or not _EPISODE_RECEIPT_ID_PATTERN.fullmatch(safe_receipt_id)
        or safe_decision not in _ALLOWED_DECISIONS
    ):
        return _blocked_action("invalid_request", "game_teaching_episode_review_context_invalid")

    status = game_teaching_episode_review_status(episode_receipt_id=safe_receipt_id)
    if status.get("replay_ready") is not True:
        return _blocked_action(
            str(status.get("status") or "episode_not_reviewable"),
            "game_teaching_episode_not_ready_for_review",
            episode_receipt_id=safe_receipt_id,
            blockers=_string_items(status.get("blockers")),
        )

    normalized_corrections, correction_error = _normalize_corrections(
        corrections,
        event_count=_safe_int(status.get("event_count")),
    )
    if correction_error:
        return _blocked_action(
            "invalid_request",
            correction_error,
            episode_receipt_id=safe_receipt_id,
        )
    if safe_decision == "needs_correction" and not normalized_corrections:
        return _blocked_action(
            "invalid_request",
            "game_teaching_episode_correction_required",
            episode_receipt_id=safe_receipt_id,
        )
    if safe_decision != "needs_correction" and normalized_corrections:
        return _blocked_action(
            "invalid_request",
            "game_teaching_episode_corrections_require_needs_correction_decision",
            episode_receipt_id=safe_receipt_id,
        )

    prior_reviews = _review_receipts_for_episode(safe_receipt_id)
    episode_digest = _safe_text(status.get("episode_digest"))
    if prior_reviews and any(_safe_text(item.get("episode_digest")) != episode_digest for item in prior_reviews):
        return _blocked_action(
            "episode_integrity_conflict",
            "game_teaching_episode_changed_after_review",
            episode_receipt_id=safe_receipt_id,
        )

    replay = game_teaching_episode_replay(
        episode_receipt_id=safe_receipt_id,
        cursor=0,
        limit=MAX_REPLAY_PAGE_SIZE,
    )
    fingerprint = _canonical_digest(
        {
            "actor": safe_actor,
            "reason": safe_reason,
            "episode_receipt_id": safe_receipt_id,
            "episode_digest": episode_digest,
            "decision": safe_decision,
            "summary": safe_summary,
            "corrections": normalized_corrections,
        }
    )
    for receipt in reversed(prior_reviews):
        if _safe_text(receipt.get("request_fingerprint")) == fingerprint:
            return {**receipt, "idempotent": True}

    reviewed_at = _validated_timestamp(now)
    review_receipt_id = f"game_teaching_review_{uuid.uuid4().hex[:16]}"
    review_state = {
        "accepted": "operator_accepted",
        "needs_correction": "correction_required",
        "rejected": "operator_rejected",
    }[safe_decision]
    receipt = {
        "ok": True,
        "kind": GAME_TEACHING_EPISODE_REVIEW_RECEIPT_KIND,
        "version": GAME_TEACHING_EPISODE_REVIEW_VERSION,
        "receipt_id": review_receipt_id,
        "episode_receipt_id": safe_receipt_id,
        "episode_digest": episode_digest,
        "replay_digest": _safe_text(replay.get("replay_digest")),
        "review_revision": len(prior_reviews) + 1,
        "reviewed_at": reviewed_at,
        "actor": safe_actor,
        "reason": safe_reason,
        "decision": safe_decision,
        "review_state": review_state,
        "summary": safe_summary,
        "corrections": normalized_corrections,
        "correction_count": len(normalized_corrections),
        "request_fingerprint": fingerprint,
        "replay_reviewed": True,
        "replay_executed": False,
        "generalization_candidate_ready": safe_decision == "accepted",
        "generalization_performed": False,
        "skillization_performed": False,
        "writes_receipt": True,
        "writes_memory": False,
        "creates_capability": False,
        "promotes_skill": False,
        "learning_authority": False,
        "reward_authority": False,
        "input_execution_authority": False,
        "governance": _governance(),
        "next_smallest_truthful_gap": (
            "generalize_operator_accepted_game_episode"
            if safe_decision == "accepted"
            else "resolve_game_episode_operator_review"
        ),
    }
    _append_jsonl(_review_receipts_path(), receipt)
    audit_record(
        "apprenticeship.game_teaching_episode_review_recorded",
        actor=safe_actor,
        reason=safe_reason,
        receipt_id=review_receipt_id,
        episode_receipt_id=safe_receipt_id,
        decision=safe_decision,
        correction_count=len(normalized_corrections),
    )
    return receipt


def game_teaching_episode_review_receipts(
    *,
    limit: int = 20,
    episode_receipt_id: Any = "",
) -> dict[str, Any]:
    safe_limit = max(1, min(int(limit), 100))
    safe_episode_receipt_id = _safe_text(episode_receipt_id)
    items = [
        item
        for item in _read_jsonl(_review_receipts_path())
        if item.get("kind") == GAME_TEACHING_EPISODE_REVIEW_RECEIPT_KIND
        and item.get("version") == GAME_TEACHING_EPISODE_REVIEW_VERSION
        and (not safe_episode_receipt_id or _safe_text(item.get("episode_receipt_id")) == safe_episode_receipt_id)
    ][-safe_limit:]
    return {
        "ok": True,
        "kind": GAME_TEACHING_EPISODE_REVIEW_RECEIPTS_KIND,
        "version": GAME_TEACHING_EPISODE_REVIEW_VERSION,
        "status": "ready",
        "count": len(items),
        "items": items,
        "reads_receipts": True,
        "writes_receipts": False,
        "writes_memory": False,
        "governance": _governance(),
    }


def _status_payload(
    *,
    status: str,
    episode: dict[str, Any] | None = None,
    latest_review: dict[str, Any] | None = None,
    replay_ready: bool = False,
    blockers: list[str] | None = None,
) -> dict[str, Any]:
    source = episode or {}
    review = latest_review or {}
    decision = _safe_text(review.get("decision"))
    accepted = decision == "accepted" and replay_ready
    return {
        "ok": status not in {"invalid_request", "episode_invalid"},
        "kind": GAME_TEACHING_EPISODE_REVIEW_STATUS_KIND,
        "version": GAME_TEACHING_EPISODE_REVIEW_VERSION,
        "status": status,
        "source_id": "apprenticeship",
        "episode_receipt_id": _safe_text(source.get("receipt_id")),
        "episode_digest": _safe_text(source.get("episode_digest")),
        "session_id": _safe_text(source.get("session_id")),
        "target_id": _safe_text(source.get("target_id")),
        "intent_label": _safe_text(source.get("intent_label")),
        "declared_scope": _safe_text(source.get("declared_scope")),
        "success_condition": _safe_text(source.get("success_condition")),
        "event_count": _safe_int(source.get("event_count")),
        "scene_transition_count": _safe_int(source.get("scene_transition_count")),
        "ready_for_operator_review": source.get("ready_for_operator_review") is True,
        "replay_ready": replay_ready,
        "review_state": _safe_text(review.get("review_state")) or "pending_operator_review",
        "review_decision": decision,
        "review_revision": _safe_int(review.get("review_revision")),
        "latest_review_receipt_id": _safe_text(review.get("receipt_id")),
        "correction_count": _safe_int(review.get("correction_count")),
        "operator_review_required": not accepted,
        "generalization_candidate_ready": accepted,
        "generalization_performed": False,
        "skillization_performed": False,
        "blockers": blockers or [],
        "writes_receipt": False,
        "writes_memory": False,
        "learning_authority": False,
        "reward_authority": False,
        "input_execution_authority": False,
        "creates_capability": False,
        "promotes_skill": False,
        "governance": _governance(),
        "next_smallest_truthful_gap": (
            "capture_nonempty_game_teaching_episode"
            if not source
            else (
                "generalize_operator_accepted_game_episode" if accepted else "operator_review_of_game_teaching_episode"
            )
        ),
    }


def _validate_episode(episode: dict[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    receipt_id = _safe_text(episode.get("receipt_id"))
    if (
        episode.get("kind") != GAME_TEACHING_EPISODE_RECEIPT_KIND
        or episode.get("version") != GAME_TEACHING_CONTRACT_VERSION
        or not _EPISODE_RECEIPT_ID_PATTERN.fullmatch(receipt_id)
    ):
        blockers.append("game_teaching_episode_contract_invalid")

    expected_digest = _safe_text(episode.get("episode_digest"))
    if episode.get("integrity_algorithm") != "sha256" or not re.fullmatch(r"[a-f0-9]{64}", expected_digest):
        blockers.append("game_teaching_episode_digest_missing")
    else:
        try:
            actual_digest = game_teaching_episode_digest(episode)
        except (TypeError, ValueError):
            actual_digest = ""
        if actual_digest != expected_digest:
            blockers.append("game_teaching_episode_digest_mismatch")

    sequence = _as_list(episode.get("scene_sequence"))
    event_count = _safe_int(episode.get("event_count"))
    transition_count = _safe_int(episode.get("scene_transition_count"))
    if event_count < 1 or event_count != len(sequence) or transition_count != len(sequence):
        blockers.append("game_teaching_episode_sequence_count_invalid")
    if "scene_confirmation_policy" in episode and not _scene_confirmation_policy_valid(episode, sequence):
        blockers.append("game_teaching_episode_scene_confirmation_invalid")
    previous_time: float | None = None
    for index, raw_step in enumerate(sequence, start=1):
        step = _as_dict(raw_step)
        observed_at = _safe_float(step.get("observed_at"))
        confidence = _safe_float(step.get("confidence"))
        margin = _safe_float(step.get("margin"))
        if (
            _safe_int(step.get("sequence")) != index
            or not _safe_text(step.get("scene_id"))
            or observed_at is None
            or confidence is None
            or not 0.0 <= confidence <= 1.0
            or margin is None
            or not 0.0 <= margin <= 1.0
            or not _safe_text(step.get("source_frame_id"))
        ):
            blockers.append("game_teaching_episode_sequence_invalid")
            break
        if previous_time is not None and observed_at < previous_time:
            blockers.append("game_teaching_episode_sequence_time_invalid")
            break
        previous_time = observed_at
    if episode.get("ready_for_operator_review") is not True:
        blockers.append("game_teaching_episode_not_ready_for_operator_review")

    return {
        "ready": not blockers,
        "receipt_id": receipt_id,
        "event_count": event_count,
        "blockers": _dedupe_text(blockers),
    }


def _scene_confirmation_policy_valid(episode: dict[str, Any], sequence: list[Any]) -> bool:
    policy = _as_dict(episode.get("scene_confirmation_policy"))
    requirements_observed = sorted(
        {_safe_int(item) for item in _as_list(policy.get("requirements_observed")) if _safe_int(item) > 0}
    )
    sequence_requirements: set[int] = set()
    if (
        policy.get("basis") != "distinct_classification_source_frames"
        or policy.get("all_events_temporally_confirmed") is not True
        or not sequence
    ):
        return False

    for raw_step in sequence:
        step = _as_dict(raw_step)
        required = _safe_int(step.get("confirmation_required"))
        count = _safe_int(step.get("confirmation_count"))
        source_frame_ids = _string_items(step.get("confirmation_source_frame_ids"))
        first_classified_at = _safe_float(step.get("confirmation_first_classified_at"))
        last_classified_at = _safe_float(step.get("confirmation_last_classified_at"))
        if (
            required < 1
            or count < required
            or count != len(source_frame_ids)
            or len(set(source_frame_ids)) != len(source_frame_ids)
            or first_classified_at is None
            or last_classified_at is None
            or first_classified_at > last_classified_at
        ):
            return False
        sequence_requirements.add(required)

    return requirements_observed == sorted(sequence_requirements)


def _semantic_replay_steps(episode: dict[str, Any]) -> list[dict[str, Any]]:
    sequence = [_as_dict(item) for item in _as_list(episode.get("scene_sequence"))]
    first_observed_at = _safe_float(sequence[0].get("observed_at")) if sequence else None
    steps: list[dict[str, Any]] = []
    previous_scene_id = ""
    for item in sequence:
        observed_at = _safe_float(item.get("observed_at"))
        offset_ms = 0.0
        if observed_at is not None and first_observed_at is not None:
            offset_ms = round(max(0.0, observed_at - first_observed_at) * 1_000.0, 3)
        scene_id = _safe_text(item.get("scene_id"))
        steps.append(
            {
                "sequence": _safe_int(item.get("sequence")),
                "transition_kind": "initial_scene" if not previous_scene_id else "scene_transition",
                "from_scene_id": previous_scene_id,
                "to_scene_id": scene_id,
                "offset_ms": offset_ms,
                "confidence": _safe_float(item.get("confidence")),
                "margin": _safe_float(item.get("margin")),
                "source_frame_id": _safe_text(item.get("source_frame_id")),
            }
        )
        previous_scene_id = scene_id
    return steps


def _normalize_corrections(value: Any, *, event_count: int) -> tuple[list[dict[str, Any]], str]:
    if value is None:
        return [], ""
    if not isinstance(value, list) or len(value) > MAX_REVIEW_CORRECTIONS:
        return [], "game_teaching_episode_corrections_invalid"
    normalized: list[dict[str, Any]] = []
    for raw_item in value:
        item = _as_dict(raw_item)
        correction_type = _safe_text(item.get("correction_type")).casefold()
        sequence = _safe_int(item.get("sequence"))
        note = _redacted_text(item.get("note"))[:500]
        replacement = _redacted_text(item.get("replacement"))[:240]
        if correction_type not in _ALLOWED_CORRECTION_TYPES or sequence < 0 or sequence > event_count or not note:
            return [], "game_teaching_episode_correction_invalid"
        normalized.append(
            {
                "correction_type": correction_type,
                "sequence": sequence,
                "note": note,
                "replacement": replacement,
            }
        )
    return normalized, ""


def _review_receipts_for_episode(episode_receipt_id: str) -> list[dict[str, Any]]:
    return [
        item
        for item in _read_jsonl(_review_receipts_path())
        if item.get("kind") == GAME_TEACHING_EPISODE_REVIEW_RECEIPT_KIND
        and item.get("version") == GAME_TEACHING_EPISODE_REVIEW_VERSION
        and _safe_text(item.get("episode_receipt_id")) == episode_receipt_id
    ]


def _blocked_action(
    status: str,
    reason: str,
    *,
    episode_receipt_id: str = "",
    blockers: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "ok": False,
        "kind": GAME_TEACHING_EPISODE_REVIEW_RECEIPT_KIND,
        "version": GAME_TEACHING_EPISODE_REVIEW_VERSION,
        "status": status,
        "reason": reason,
        "receipt_id": "",
        "episode_receipt_id": episode_receipt_id,
        "blockers": blockers or [reason],
        "writes_receipt": False,
        "writes_memory": False,
        "creates_capability": False,
        "promotes_skill": False,
        "learning_authority": False,
        "reward_authority": False,
        "input_execution_authority": False,
        "governance": _governance(),
    }


def _governance() -> dict[str, Any]:
    return {
        "required_scope": GAME_TEACHING_EPISODE_REVIEW_WRITE_SCOPE,
        "source_episode_immutable": True,
        "source_digest_required": True,
        "semantic_replay_only": True,
        "operator_review_required": True,
        "corrections_append_only": True,
        "replay_executes_input": False,
        "replay_runs_tools": False,
        "replay_runs_shell": False,
        "replay_starts_processes": False,
        "raw_pixels_persisted": False,
        "window_titles_persisted": False,
        "keyboard_content_captured": False,
        "user_mouse_captured": False,
        "remote_frame_transfer": False,
        "memory_write": False,
        "learning_authority": False,
        "reward_authority": False,
        "input_execution_authority": False,
        "automatic_generalization": False,
        "automatic_skillization": False,
        "automatic_capability_promotion": False,
    }


def _review_receipts_path() -> Path:
    return data_dir() / "logs" / "apprenticeship" / "game_teaching_episode_review_receipts.jsonl"


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True, sort_keys=True, allow_nan=False) + "\n")
        handle.flush()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    try:
        lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    except OSError:
        return []
    items: list[dict[str, Any]] = []
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


def _canonical_digest(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validated_timestamp(value: float | None) -> float:
    candidate = time.time() if value is None else _safe_float(value)
    if candidate is None or candidate < 0:
        return time.time()
    return candidate


def _safe_float(value: Any) -> float | None:
    try:
        candidate = float(value)
    except (TypeError, ValueError):
        return None
    return candidate if math.isfinite(candidate) else None


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _redacted_text(value: Any) -> str:
    return redact_secret_text(_safe_text(value)).strip()


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _string_items(value: Any) -> list[str]:
    return [_safe_text(item) for item in _as_list(value) if _safe_text(item)]


def _dedupe_text(values: Any) -> list[str]:
    return list(dict.fromkeys(_safe_text(value) for value in values if _safe_text(value)))


def _env_profile() -> str:
    return str(os.getenv("FRANCIS_ENV_PROFILE") or "dev").strip().casefold()
