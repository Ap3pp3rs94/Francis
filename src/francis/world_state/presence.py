from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any, Mapping


GROUNDED_PRESENCE_KIND = "francis.grounded_presence.snapshot"
GROUNDED_PRESENCE_SCHEMA_VERSION = "francis.grounded_presence.snapshot.v1"
GROUNDED_PRESENCE_SCHEMA_PATH = "schemas/grounded_presence_snapshot.schema.json"
GROUNDED_PRESENCE_TONE_CONTRACT = "francis.grounded_presence.tone.v1"
GROUNDED_PRESENCE_STALE_AFTER_SECONDS = 300


def build_grounded_presence_snapshot(
    *,
    briefing: Mapping[str, Any] | None,
    operator: Mapping[str, Any] | None,
    orb: Mapping[str, Any] | None,
    unreal_selection: Mapping[str, Any] | None = None,
    unreal_runtime: Mapping[str, Any] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Project current local readbacks into the Stage 1 presence contract."""

    briefing_map = _mapping(briefing)
    operator_map = _mapping(operator)
    orb_map = _mapping(orb)
    unreal_selection_map = _mapping(unreal_selection)
    unreal_runtime_map = _mapping(unreal_runtime)
    focus, focus_source = _focus_item(briefing_map)
    current_task = _mapping(focus.get("current_task"))
    generated_dt = _parse_datetime(generated_at) or datetime.now(UTC)
    now = generated_dt.isoformat()

    freshness = _freshness_projection(
        briefing=briefing_map,
        operator=operator_map,
        orb=orb_map,
        generated_at=generated_dt,
    )
    continuity_fresh = (
        _mapping(_mapping(freshness.get("sources")).get("continuity_briefing")).get("status") == "observed"
    )
    briefing_ready = (bool(briefing_map.get("headline")) or bool(focus)) and continuity_fresh
    intent = _intent_projection(focus, current_task)
    action = _text(intent.get("action"))
    receipt_links = _receipt_links(briefing_map, focus)
    actionable = bool(action)
    receipt_linkage_ready = not actionable or any(item["kind"] == "receipt" for item in receipt_links)
    source_readbacks = {
        "continuity_briefing": bool(briefing_map.get("headline")) or bool(focus),
        "operator_surface": bool(operator_map.get("available")),
        "orb_surface": bool(orb_map.get("available")),
    }
    criteria = {
        "no_fabricated_state": briefing_ready,
        "local_evidence_grounded": briefing_ready,
        "action_receipt_linkage": receipt_linkage_ready,
        "calm_non_theatrical_tone": True,
        "return_to_context": bool(briefing_map.get("headline")) or bool(focus),
    }
    blockers = [key for key, value in criteria.items() if not value]
    if not source_readbacks["continuity_briefing"]:
        evidence_status = "missing_evidence"
    elif not continuity_fresh or not receipt_linkage_ready:
        evidence_status = "blocked"
    else:
        evidence_status = "ready"

    focus_id = _first_text(focus.get("id"), focus.get("mission_id"))
    mission_id = _first_text(current_task.get("mission_id"), focus_id)
    operation_id = _text(current_task.get("operation_id"))
    receipt_ids = [item["id"] for item in receipt_links if item["kind"] == "receipt"]
    correlation_status = "not_required" if not actionable else "receipt_linked" if receipt_ids else "missing_receipt"
    voice_readback, voice_source = _voice_readback(orb_map)
    voice = _voice_projection(voice_readback, source=voice_source)
    unreal_selection_confirmed = bool(unreal_selection_map.get("valid")) and (
        _text(unreal_selection_map.get("status")) == "operator_selection_confirmed"
    )
    unreal_runtime_observed = (
        unreal_selection_confirmed
        and bool(unreal_runtime_map.get("observed"))
        and (_text(unreal_runtime_map.get("status")) == "runtime_observed")
    )
    limitations = [
        "presence_projection_does_not_execute_actions",
        "panic_stop_state_is_unknown_without_observed_control_readback",
    ]
    if unreal_runtime_observed:
        pass
    elif unreal_selection_confirmed:
        limitations.append("unreal_runtime_not_observed")
    else:
        limitations.extend(
            [
                "unreal_technology_selection_pending_operator_confirmation",
                "unreal_project_not_configured",
            ]
        )
        selection_status = _text(unreal_selection_map.get("status"))
        if selection_status in {"selection_invalid", "selection_stale"}:
            limitations.append(f"unreal_{selection_status}")
    if voice["status"] == "unknown":
        limitations.append("voice_state_is_unknown_without_observed_voice_readback")
    elif voice["listening"] is None or voice["speaking"] is None:
        limitations.append("voice_identity_observed_activity_state_unknown")
    identity_status = _text(voice_readback.get("identity_status"))
    if identity_status and identity_status != "ready":
        limitations.append("voice_identity_readback_not_ready")

    return {
        "kind": GROUNDED_PRESENCE_KIND,
        "schema_version": GROUNDED_PRESENCE_SCHEMA_VERSION,
        "schema_path": GROUNDED_PRESENCE_SCHEMA_PATH,
        "generated_at": now,
        "stage": {
            "id": 1,
            "name": "Grounded Presence",
            "status": "ready" if not blockers else "blocked",
            "criteria": criteria,
        },
        "presence": {
            "state": _presence_state(orb_map),
            "tone": "calm_operator",
            "tone_contract": {
                "id": GROUNDED_PRESENCE_TONE_CONTRACT,
                "style": "calm_operator",
                "theatricality_allowed": False,
                "claims_require_evidence": True,
                "missing_state_wording": "explicit_unknown",
            },
            "truthful": True,
            "headline": _text(briefing_map.get("headline")),
            "focus": {
                "source": focus_source,
                "id": focus_id,
                "objective": _text(focus.get("objective")),
                "title": _first_text(focus.get("title"), focus.get("name"), focus.get("objective")),
                "summary": _text(focus.get("summary")),
                "status": _text(focus.get("status")),
                "next_step": _first_text(current_task.get("next_step"), focus.get("next_step")),
                "recommended_action": action,
                "updated_at": _timestamp_text(focus.get("updated_at")),
            },
            "return_to_context": _return_to_context(
                briefing=briefing_map,
                focus=focus,
                focus_source=focus_source,
                current_task=current_task,
                actionable=actionable,
                continuity_fresh=continuity_fresh,
                reference_ids=[item["id"] for item in receipt_links],
            ),
        },
        "intent": intent,
        "evidence": {
            "status": evidence_status,
            "source_readbacks": source_readbacks,
            "correlation": {
                "status": correlation_status,
                "focus_id": focus_id,
                "mission_id": mission_id,
                "operation_id": operation_id,
                "action": action,
                "receipt_ids": receipt_ids,
            },
            "references": receipt_links,
            "receipt_linkage_required": actionable,
            "receipt_linkage_ready": receipt_linkage_ready,
        },
        "freshness": freshness,
        "voice": voice,
        "visual_state": _visual_state(operator_map, orb_map, intent),
        "unreal_adapter": {
            "engine": "Unreal Engine",
            "engine_version": "5.8",
            "role": "governed_renderer_adapter",
            "status": (
                "runtime_observed"
                if unreal_runtime_observed
                else "operator_selection_confirmed_runtime_not_observed"
                if unreal_selection_confirmed
                else "contract_defined_runtime_not_implemented"
            ),
            "technology_selection_status": (
                "operator_confirmed" if unreal_selection_confirmed else "operator_confirmation_required"
            ),
            "project_selection_status": (
                "operator_confirmed" if unreal_selection_confirmed else "operator_confirmation_required"
            ),
            "runtime_observed": unreal_runtime_observed,
            "accepts_authority": False,
        },
        "authority": {
            "read_only": True,
            "render_only": True,
            "francis_core_authoritative": True,
            "grants_execution_authority": False,
            "grants_desktop_authority": False,
            "grants_network_authority": False,
            "grants_memory_write_authority": False,
            "grants_approval_authority": False,
        },
        "blockers": blockers,
        "limitations": limitations,
    }


def _focus_item(briefing: Mapping[str, Any]) -> tuple[dict[str, Any], str]:
    for key in ("focus", "failed_preview", "deadletter_preview", "recently_completed"):
        items = briefing.get(key)
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict):
                    return dict(item), key
    return {}, ""


def _intent_projection(focus: Mapping[str, Any], current_task: Mapping[str, Any]) -> dict[str, Any]:
    action, action_source = _first_sourced_text(
        (current_task.get("handoff_action"), "focus.current_task.handoff_action"),
        (focus.get("recommended_action"), "focus.recommended_action"),
    )
    mission_id = _first_text(current_task.get("mission_id"), focus.get("id"), focus.get("mission_id"))
    operation_id = _text(current_task.get("operation_id"))
    explicit_target_id = _text(focus.get("action_target_id"))
    target_id = _first_text(explicit_target_id, operation_id, mission_id)
    if target_id.startswith("tsk_"):
        target_kind = "task"
    elif explicit_target_id and explicit_target_id == operation_id or operation_id and target_id == operation_id:
        target_kind = "operation"
    elif mission_id and target_id == mission_id:
        target_kind = "mission"
    elif target_id:
        target_kind = "unknown"
    else:
        target_kind = "none"

    return {
        "available": bool(action),
        "request_only": True,
        "action": action,
        "source": action_source,
        "target_kind": target_kind,
        "target_id": target_id,
        "mission_id": mission_id,
        "operation_id": operation_id,
        "operation_plane": _text(current_task.get("operation_plane")),
        "reason": _first_text(
            current_task.get("reason"),
            focus.get("reason"),
            focus.get("operator_hint"),
        ),
        "next_step": _first_text(current_task.get("next_step"), focus.get("next_step")),
        "stage": _first_text(current_task.get("stage"), focus.get("handoff_stage")),
        "gate": _first_text(current_task.get("gate"), focus.get("last_task_gate")),
        "approval": {
            "id": _first_text(current_task.get("approval_id"), focus.get("last_task_approval_id")),
            "status": _first_text(current_task.get("approval_status"), focus.get("last_task_approval_status")),
        },
        "grants_execution_authority": False,
    }


def _receipt_links(briefing: Mapping[str, Any], focus: Mapping[str, Any]) -> list[dict[str, Any]]:
    links: list[dict[str, Any]] = []
    current_task = _mapping(focus.get("current_task"))
    selected_ids = {
        value
        for value in (
            _text(focus.get("id")),
            _text(focus.get("mission_id")),
            _text(current_task.get("mission_id")),
            _text(current_task.get("operation_id")),
            _text(focus.get("action_target_id")),
        )
        if value
    }

    def add(kind: str, value: Any, source: str, metadata: Mapping[str, Any] | None = None) -> None:
        item_id = _text(value)
        if not item_id or any(item["kind"] == kind and item["id"] == item_id for item in links):
            return
        meta = _mapping(metadata)
        item: dict[str, Any] = {
            "kind": kind,
            "id": item_id,
            "source": source,
            "correlation_status": "correlated",
        }
        optional = {
            "mission_id": _first_text(meta.get("mission_id"), current_task.get("mission_id"), focus.get("id")),
            "operation_id": _first_text(meta.get("operation_id"), current_task.get("operation_id")),
            "status": _first_text(meta.get("operation_status"), meta.get("status")),
            "observed_at": _timestamp_text(meta.get("ts") or meta.get("observed_at")),
        }
        item.update({key: value for key, value in optional.items() if value})
        links.append(item)

    for index, item in enumerate(briefing.get("memory_receipts", [])):
        if isinstance(item, dict) and _receipt_matches_focus(item, selected_ids):
            add("receipt", item.get("receipt_id") or item.get("id"), f"memory_receipts[{index}]", item)
    latest = _mapping(focus.get("latest_memory_receipt"))
    add("receipt", latest.get("receipt_id") or latest.get("id"), "focus.latest_memory_receipt", latest)
    add(
        "receipt",
        current_task.get("receipt_id") or current_task.get("latest_receipt_id"),
        "focus.current_task",
        current_task,
    )
    add("approval", focus.get("last_task_approval_id"), "focus.last_task_approval_id", focus)
    add("approval", current_task.get("approval_id"), "focus.current_task.approval_id", current_task)
    add("trace", current_task.get("trace_id"), "focus.current_task.trace_id", current_task)
    add("run", current_task.get("run_id"), "focus.current_task.run_id", current_task)
    add("artifact", current_task.get("artifact_dir"), "focus.current_task.artifact_dir", current_task)
    return links


def _receipt_matches_focus(receipt: Mapping[str, Any], selected_ids: set[str]) -> bool:
    if not selected_ids:
        return False
    receipt_ids = {
        _text(receipt.get("mission_id")),
        _text(receipt.get("operation_id")),
        _text(receipt.get("task_id")),
        _text(receipt.get("focus_id")),
    }
    return bool(selected_ids.intersection(receipt_ids))


def _return_to_context(
    *,
    briefing: Mapping[str, Any],
    focus: Mapping[str, Any],
    focus_source: str,
    current_task: Mapping[str, Any],
    actionable: bool,
    continuity_fresh: bool,
    reference_ids: list[str],
) -> dict[str, Any]:
    latest_activity = _mapping(focus.get("latest_activity"))
    gate = _first_text(current_task.get("gate"), focus.get("last_task_gate"))
    approval_id = _first_text(current_task.get("approval_id"), focus.get("last_task_approval_id"))
    approval_status = _first_text(
        current_task.get("approval_status"),
        focus.get("last_task_approval_status"),
    )
    hold_active = bool(gate or approval_id or approval_status in {"pending", "needs_approval", "blocked"})
    return {
        "available": bool(briefing.get("headline")) or bool(focus),
        "source": "continuity_briefing",
        "focus_source": focus_source,
        "fresh": continuity_fresh,
        "actionable": actionable,
        "objective": _first_text(focus.get("objective"), focus.get("title")),
        "summary": _text(focus.get("summary")),
        "reason": _first_text(
            current_task.get("reason"),
            focus.get("reason"),
            focus.get("operator_hint"),
        ),
        "next_step": _first_text(current_task.get("next_step"), focus.get("next_step")),
        "changed_since": _first_text(
            focus.get("last_advance_message"),
            latest_activity.get("message"),
            latest_activity.get("name"),
            focus.get("latest_history_event"),
        ),
        "governance_hold": {
            "active": hold_active,
            "gate": gate,
            "approval_id": approval_id,
            "approval_status": approval_status,
            "reason": _first_text(current_task.get("reason"), focus.get("operator_hint")),
        },
        "last_meaningful_at": _first_text(
            _timestamp_text(current_task.get("latest_receipt_ts")),
            _timestamp_text(focus.get("last_advance_at")),
            _timestamp_text(latest_activity.get("ts")),
            _timestamp_text(focus.get("latest_history_ts")),
            _timestamp_text(focus.get("updated_at")),
        ),
        "reference_ids": list(dict.fromkeys(reference_ids)),
    }


def _freshness_projection(
    *,
    briefing: Mapping[str, Any],
    operator: Mapping[str, Any],
    orb: Mapping[str, Any],
    generated_at: datetime,
) -> dict[str, Any]:
    observer = _mapping(briefing.get("observer"))
    sources = {
        "continuity_briefing": _source_freshness(
            available=bool(briefing.get("headline")) or bool(_focus_item(briefing)[0]),
            observed_at=briefing.get("generated_at") or observer.get("observed_at"),
            generated_at=generated_at,
        ),
        "operator_surface": _source_freshness(
            available=bool(operator.get("available")),
            observed_at=operator.get("observed_at") or operator.get("generated_at"),
            generated_at=generated_at,
        ),
        "orb_surface": _source_freshness(
            available=bool(orb.get("available")),
            observed_at=orb.get("observed_at") or orb.get("generated_at"),
            generated_at=generated_at,
        ),
    }
    continuity_status = _text(sources["continuity_briefing"].get("status"))
    if continuity_status in {"stale", "invalid"}:
        status = continuity_status
    elif continuity_status == "missing_evidence":
        status = "missing_evidence"
    elif all(source["status"] == "observed" for source in sources.values()):
        status = "observed"
    else:
        status = "partial"
    return {
        "status": status,
        "stale_after_seconds": GROUNDED_PRESENCE_STALE_AFTER_SECONDS,
        "sources": sources,
    }


def _source_freshness(*, available: bool, observed_at: Any, generated_at: datetime) -> dict[str, Any]:
    observed_dt = _parse_datetime(observed_at)
    if observed_dt is None:
        return {
            "available": available,
            "status": "missing_evidence",
            "observed_at": None,
            "age_seconds": None,
            "stale": None,
            "reason": "source_timestamp_not_observed" if available else "source_unavailable",
        }
    age_seconds = (generated_at - observed_dt).total_seconds()
    if age_seconds < -5:
        return {
            "available": available,
            "status": "invalid",
            "observed_at": observed_dt.isoformat(),
            "age_seconds": round(age_seconds, 3),
            "stale": None,
            "reason": "source_timestamp_in_future",
        }
    age_seconds = max(0.0, age_seconds)
    stale = age_seconds > GROUNDED_PRESENCE_STALE_AFTER_SECONDS
    return {
        "available": available,
        "status": "stale" if stale else "observed",
        "observed_at": observed_dt.isoformat(),
        "age_seconds": round(age_seconds, 3),
        "stale": stale,
        "reason": "stale_after_threshold" if stale else "within_freshness_window",
    }


def _voice_readback(orb: Mapping[str, Any]) -> tuple[dict[str, Any], str]:
    state = _mapping(orb.get("state"))
    candidates = (
        (orb.get("voice"), "orb.voice"),
        (state.get("voice"), "orb.state.voice"),
        (state.get("voice_state"), "orb.state.voice_state"),
    )
    for candidate, candidate_source in candidates:
        if isinstance(candidate, Mapping) and candidate:
            return _mapping(candidate), candidate_source
    return {}, ""


def _voice_projection(voice: Mapping[str, Any], *, source: str) -> dict[str, Any]:
    listening = _optional_bool(voice.get("listening"))
    speaking = _optional_bool(voice.get("speaking"))
    provider = _first_text(
        voice.get("provider"),
        voice.get("runtime_provider"),
        voice.get("selected_provider"),
        voice.get("voice_provider"),
    )
    observed = listening is not None or speaking is not None or bool(provider)
    activity_observed = listening is not None or speaking is not None
    return {
        "status": "observed" if observed else "unknown",
        "listening": listening,
        "speaking": speaking,
        "provider": provider,
        "source": source,
        "reason": (
            "observed_voice_readback"
            if activity_observed
            else "voice_identity_observed_activity_state_unknown"
            if observed
            else "voice_readback_not_available_in_orb_surface"
        ),
    }


def _visual_state(operator: Mapping[str, Any], orb: Mapping[str, Any], intent: Mapping[str, Any]) -> dict[str, Any]:
    state = _mapping(orb.get("state"))
    mode = _mapping(state.get("mode"))
    control_mode = _mapping(operator.get("control_mode"))
    activity = _mapping(state.get("activity_intensity"))
    incident = _mapping(state.get("incident_pressure"))
    handback = _mapping(state.get("handback_state"))
    backlog = _mapping(operator.get("backlog"))
    approval = _mapping(intent.get("approval"))
    operator_available = bool(operator.get("available"))
    orb_available = bool(orb.get("available"))
    approval_pending = bool(approval.get("id")) or _text(approval.get("status")) in {
        "pending",
        "needs_approval",
        "blocked",
    }
    approval_pending = approval_pending or any(
        _safe_int(backlog.get(key)) > 0 for key in ("pending_approvals", "approval_pending_tasks")
    )
    approval_required = approval_pending if operator_available else None
    semantic_state = _first_text(
        state.get("semantic_state"), _mapping(state.get("semantic_operator_state")).get("state")
    )
    activity_level = _text(activity.get("level"))
    if not orb_available:
        execution_state = "unknown"
    elif activity_level == "active_execution" or semantic_state == "acting":
        execution_state = "active"
    else:
        execution_state = "inactive"

    panic_stop = _mapping(state.get("panic_stop"))
    panic_ready = _optional_bool(panic_stop.get("ready"))
    panic_observed = panic_ready is not None
    return {
        "source_status": "observed" if orb_available else "missing_evidence",
        "mode": _first_text(mode.get("id"), control_mode.get("id"), "unknown"),
        "semantic_state": semantic_state or "unknown",
        "render_state": _first_text(state.get("render_state"), "unknown"),
        "activity": activity_level or "unknown",
        "incident_pressure": _first_text(incident.get("level"), "unknown"),
        "approval_required": approval_required,
        "execution_state": execution_state,
        "handback_state": _first_text(handback.get("state"), "unknown"),
        "panic_stop": {
            "status": "observed" if panic_observed else "unknown",
            "ready": panic_ready,
            "source": "orb.state.panic_stop" if panic_observed else "",
            "reason": "observed_control_readback" if panic_observed else "panic_stop_readback_not_available",
        },
    }


def _presence_state(orb: Mapping[str, Any]) -> str:
    if not bool(orb.get("available")):
        return "unknown"
    state = _mapping(orb.get("state"))
    interjection = _mapping(state.get("interjection_state"))
    handback = _mapping(state.get("handback_state"))
    if _text(interjection.get("state")) == "attention_required":
        return "attention_required"
    if _text(handback.get("state")) not in {"", "none"}:
        return "handoff"
    return _first_text(state.get("semantic_state"), state.get("render_state"), "unknown")


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _text(value: Any, *, limit: int = 240) -> str:
    if value is None:
        return ""
    return str(value).strip()[:limit]


def _first_text(*values: Any) -> str:
    for value in values:
        text = _text(value)
        if text:
            return text
    return ""


def _first_sourced_text(*values: tuple[Any, str]) -> tuple[str, str]:
    for value, source in values:
        text = _text(value)
        if text:
            return text, source
    return "", ""


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _optional_bool(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        numeric = float(value)
        if not math.isfinite(numeric) or numeric <= 0:
            return None
        try:
            parsed = datetime.fromtimestamp(numeric, tz=UTC)
        except (OverflowError, OSError, ValueError):
            return None
    else:
        text = _text(value, limit=80)
        if not text:
            return None
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _timestamp_text(value: Any) -> str:
    parsed = _parse_datetime(value)
    return parsed.isoformat() if parsed is not None else ""
