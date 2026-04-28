from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

from francis.governance import approvals
from francis.governance.redaction import redact_governed_display_value, redact_governed_value
from francis.kernel.paths import data_dir
from francis.reactor.deadletters import list_deadletters, queue_deadletter
from francis.reactor.retries import list_retry_schedules, schedule_retry

VALID_TRIGGER_SOURCES = frozenset(
    {
        "approval_decision",
        "federated_handoff",
        "forge_proposal",
        "mission_queue",
        "observer_anomaly",
        "schedule_window",
        "telemetry_event",
        "user_request",
    }
)
_VALID_MODES = frozenset({"observe", "assist", "pilot", "away"})
_VALID_RISK_TIERS = frozenset({"readonly", "normal", "critical", "safety_critical"})
_EXECUTION_ACTION_CLASSES = frozenset({"dispatch", "execute", "mutate", "operation_run", "plugin_run"})
_DEFAULT_STOP_CONDITIONS = (
    "objective_reached",
    "approval_required",
    "budget_exhausted",
    "verification_failed",
    "policy_denied",
    "user_interrupted",
)


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""


def _safe_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    if isinstance(value, bool):
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, parsed))


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, (list, tuple, set)):
        return [text for item in value if (text := _safe_str(item).strip())]
    text = _safe_str(value).strip()
    return [text] if text else []


def _now_s() -> int:
    return int(time.time())


def _event_root() -> Path:
    return data_dir() / "reactor" / "events"


def _event_path(event_id: str) -> Path | None:
    cleaned = _safe_str(event_id).strip()
    if not cleaned or "/" in cleaned or "\\" in cleaned or ".." in cleaned:
        return None
    return _event_root() / f"{cleaned}.json"


def _atomic_write_json(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    os.replace(tmp, path)


def _event_id(payload: dict[str, Any], created_ts: int) -> str:
    seed = json.dumps(payload, sort_keys=True, default=str, ensure_ascii=False)
    digest = hashlib.sha256(f"{created_ts}:{time.time_ns()}:{seed}".encode("utf-8")).hexdigest()[:12]
    return f"reactor_evt_{created_ts}_{digest}"


def _bounds(payload: dict[str, Any]) -> dict[str, Any]:
    stop_conditions = _as_list(payload.get("stop_conditions")) or list(_DEFAULT_STOP_CONDITIONS)
    return {
        "max_actions": _safe_int(payload.get("max_actions"), default=1, minimum=0, maximum=50),
        "max_runtime_seconds": _safe_int(payload.get("max_runtime_seconds"), default=60, minimum=1, maximum=86_400),
        "max_retries": _safe_int(payload.get("max_retries"), default=0, minimum=0, maximum=10),
        "backoff_seconds": _safe_int(payload.get("backoff_seconds"), default=0, minimum=0, maximum=3_600),
        "resource_budget": _safe_str(payload.get("resource_budget")).strip(),
        "stop_conditions": stop_conditions,
    }


def _classification(payload: dict[str, Any], bounds: dict[str, Any]) -> dict[str, Any]:
    trigger_source = _safe_str(payload.get("trigger_source") or payload.get("source")).strip().lower()
    trigger_type = _safe_str(payload.get("trigger_type") or payload.get("type")).strip().lower() or trigger_source
    risk_tier = _safe_str(payload.get("risk_tier")).strip().lower() or "normal"
    if risk_tier not in _VALID_RISK_TIERS:
        risk_tier = "normal"
    mode = _safe_str(payload.get("mode")).strip().lower() or "assist"
    if mode not in _VALID_MODES:
        mode = "assist"
    action_class = _safe_str(payload.get("action_class")).strip().lower() or _default_action_class(trigger_source)
    approval_required = bool(payload.get("approval_required")) or risk_tier in {"critical", "safety_critical"}
    dispatch_allowed = not approval_required
    stable_state = "awaiting_dispatch"
    next_step = "dispatch_with_explicit_budget_and_receipt"

    if mode == "observe" and action_class in _EXECUTION_ACTION_CLASSES:
        dispatch_allowed = False
        stable_state = "blocked_by_mode"
        next_step = "switch_mode_or_create_approval_before_dispatch"
    elif approval_required:
        stable_state = "awaiting_approval"
        next_step = "request_or_attach_approval_before_dispatch"
    elif bounds["max_actions"] <= 0:
        dispatch_allowed = False
        stable_state = "blocked_by_budget"
        next_step = "set_positive_action_budget_before_dispatch"

    return {
        "trigger_source": trigger_source,
        "trigger_type": trigger_type,
        "mode": mode,
        "risk_tier": risk_tier,
        "action_class": action_class,
        "approval_required": approval_required,
        "dispatch_allowed": dispatch_allowed,
        "stable_state": stable_state,
        "next_step": next_step,
    }


def _default_action_class(trigger_source: str) -> str:
    if trigger_source in {"observer_anomaly", "telemetry_event"}:
        return "classify"
    if trigger_source == "approval_decision":
        return "resume"
    if trigger_source == "mission_queue":
        return "mission_tick"
    if trigger_source == "forge_proposal":
        return "proposal_review"
    return "classify"


def _validation_error(payload: dict[str, Any]) -> str:
    trigger_source = _safe_str(payload.get("trigger_source") or payload.get("source")).strip().lower()
    summary = _safe_str(payload.get("summary") or payload.get("reason")).strip()
    if trigger_source not in VALID_TRIGGER_SOURCES:
        return "invalid_trigger_source"
    if not summary:
        return "summary_required"
    return ""


def enqueue_event(payload: dict[str, Any]) -> dict[str, Any]:
    redacted_payload = redact_governed_value(payload)
    data = redacted_payload if isinstance(redacted_payload, dict) else {}
    error = _validation_error(data)
    if error:
        return {
            "ok": False,
            "applied": False,
            "error": error,
            "valid_trigger_sources": sorted(VALID_TRIGGER_SOURCES),
        }

    created_ts = _now_s()
    bounds = _bounds(data)
    classification = _classification(data, bounds)
    event_id = _event_id(data, created_ts)
    status = "queued"
    trigger_source = classification["trigger_source"]
    trigger = {
        "source": trigger_source,
        "type": classification["trigger_type"],
        "summary": _safe_str(data.get("summary") or data.get("reason")).strip(),
        "reason": _safe_str(data.get("reason")).strip(),
        "mission_id": _safe_str(data.get("mission_id")).strip(),
        "operation_id": _safe_str(data.get("operation_id")).strip(),
        "approval_id": _safe_str(data.get("approval_id")).strip(),
        "trace_id": _safe_str(data.get("trace_id")).strip(),
        "run_id": _safe_str(data.get("run_id")).strip(),
        "metadata": data.get("metadata") if isinstance(data.get("metadata"), dict) else {},
    }
    record = {
        "kind": "reactor.event",
        "event_id": event_id,
        "id": event_id,
        "status": status,
        "created_ts": created_ts,
        "updated_ts": created_ts,
        "trigger": {key: value for key, value in trigger.items() if value not in ("", {}, [])},
        "classification": classification,
        "bounds": bounds,
        "dispatch": {
            "status": "not_started",
            "allowed": bool(classification.get("dispatch_allowed")),
            "applied": False,
            "engine": "not_implemented",
        },
        "stable_state": classification["stable_state"],
        "decision_journal": [
            {
                "kind": "reactor.intake.classified",
                "ts": created_ts,
                "decision": status,
                "stable_state": classification["stable_state"],
                "next_step": classification["next_step"],
            }
        ],
        "receipt": {
            "kind": "reactor.intake.receipt",
            "event_id": event_id,
            "status": status,
            "trigger_source": trigger_source,
            "stable_state": classification["stable_state"],
            "next_step": classification["next_step"],
        },
        "governance": {
            "plane": "P4_COGNITION",
            "gate": "reactor_trigger_intake",
            "execution_authority": False,
            "approval_authority": False,
            "promotion_authority": False,
            "memory_write": False,
            "dispatch_authority": False,
            "next_step": classification["next_step"],
        },
    }
    path = _event_root() / f"{event_id}.json"
    record["path"] = str(path)
    _atomic_write_json(path, record)
    return {"ok": True, "applied": True, "event_id": event_id, "event": _display(record)}


def _display(record: dict[str, Any]) -> dict[str, Any]:
    redacted = redact_governed_display_value(record)
    return redacted if isinstance(redacted, dict) else {}


def _read_event(path: Path) -> dict[str, Any] | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None
    return _display(raw) if isinstance(raw, dict) else None


def _read_raw_event(path: Path) -> dict[str, Any] | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None
    return raw if isinstance(raw, dict) else None


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _filtered_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in receipt.items() if value not in ("", {}, [])}


def _receipt_reference(receipt: dict[str, Any]) -> str:
    for key in (
        "deadletter_id",
        "approval_id",
        "candidate_id",
        "exhaustion_id",
        "blocker_id",
        "receipt_id",
        "event_id",
    ):
        value = _safe_str(receipt.get(key)).strip()
        if value:
            return value
    return ""


def _dispatch_attempt_receipt(
    *,
    event_id: str,
    status: str,
    outcome: str,
    allowed: bool,
    stable_state: str,
    next_step: str,
    reason: str,
    actor: str,
    ts: int,
    bounds: dict[str, Any],
    blocker: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return _filtered_receipt(
        {
            "kind": "reactor.dispatch_attempt.receipt",
            "event_id": event_id,
            "status": status,
            "outcome": outcome,
            "allowed": allowed,
            "applied": False,
            "execution_started": False,
            "engine": "not_implemented",
            "actor": actor,
            "reason": reason,
            "ts": ts,
            "stable_state": stable_state,
            "next_step": next_step,
            "budget_snapshot": bounds,
            "blocker": blocker or {},
        }
    )


def _blocker_route(stable_state: str) -> tuple[str, str, str]:
    if stable_state == "awaiting_approval":
        return ("approval_queue", "waiting_for_approval", "approval_required")
    if stable_state == "blocked_by_mode":
        return ("operator_review", "waiting_for_mode_change", "mode_boundary")
    if stable_state == "blocked_by_budget":
        return ("deadletter_candidate", "waiting_for_budget_review", "budget_exhausted")
    return ("operator_review", "waiting_for_blocker_review", stable_state or "dispatch_not_allowed")


def _dispatch_blocker_record(
    *,
    event_id: str,
    stable_state: str,
    next_step: str,
    classification: dict[str, Any],
    bounds: dict[str, Any],
    trigger: dict[str, Any],
    actor: str,
    reason: str,
    attempt_count: int,
    ts: int,
) -> dict[str, Any]:
    route, queue_status, gate = _blocker_route(stable_state)
    return _filtered_receipt(
        {
            "kind": "reactor.dispatch_blocker",
            "blocker_id": f"{event_id}_blocker_{attempt_count}",
            "event_id": event_id,
            "ts": ts,
            "route": route,
            "status": queue_status,
            "gate": gate,
            "stable_state": stable_state,
            "next_step": next_step,
            "actor": actor,
            "reason": reason,
            "approval_required": bool(classification.get("approval_required")),
            "approval_id": _safe_str(trigger.get("approval_id")).strip(),
            "mode": _safe_str(classification.get("mode")).strip(),
            "risk_tier": _safe_str(classification.get("risk_tier")).strip(),
            "action_class": _safe_str(classification.get("action_class")).strip(),
            "max_actions": bounds.get("max_actions"),
            "deadletter_candidate": route == "deadletter_candidate",
            "execution_started": False,
            "applied": False,
        }
    )


def _deadletter_candidate_receipt(
    *,
    event_id: str,
    blocker: dict[str, Any],
    bounds: dict[str, Any],
    attempt_count: int,
    ts: int,
) -> dict[str, Any]:
    return _filtered_receipt(
        {
            "kind": "reactor.deadletter_candidate.receipt",
            "candidate_id": f"{event_id}_deadletter_candidate_{attempt_count}",
            "event_id": event_id,
            "status": "candidate",
            "route": "deadletter_candidate",
            "gate": blocker.get("gate"),
            "stable_state": blocker.get("stable_state"),
            "next_step": blocker.get("next_step"),
            "attempt_count": attempt_count,
            "max_actions": bounds.get("max_actions"),
            "max_retries": bounds.get("max_retries"),
            "backoff_seconds": bounds.get("backoff_seconds"),
            "stop_conditions": bounds.get("stop_conditions"),
            "ts": ts,
            "execution_started": False,
            "applied": False,
            "deadletter_enqueued": False,
            "retry_started": False,
        }
    )


def _retry_candidate_receipt(
    *,
    event_id: str,
    bounds: dict[str, Any],
    attempt_count: int,
    ts: int,
    actor: str,
    reason: str,
) -> dict[str, Any] | None:
    max_retries = _safe_int(bounds.get("max_retries"), default=0, minimum=0, maximum=10)
    if max_retries <= 0 or attempt_count > max_retries:
        return None
    backoff_seconds = _safe_int(bounds.get("backoff_seconds"), default=0, minimum=0, maximum=3_600)
    return _filtered_receipt(
        {
            "kind": "reactor.retry_candidate.receipt",
            "candidate_id": f"{event_id}_retry_candidate_{attempt_count}",
            "event_id": event_id,
            "status": "candidate",
            "route": "retry_backoff",
            "gate": "dispatch_engine_not_implemented",
            "outcome": "dispatch_engine_not_implemented",
            "stable_state": "awaiting_dispatch_engine",
            "next_step": "wait_for_dispatch_engine_before_retry",
            "attempt_count": attempt_count,
            "max_retries": max_retries,
            "remaining_retries": max(max_retries - attempt_count, 0),
            "backoff_seconds": backoff_seconds,
            "next_retry_after_ts": ts + backoff_seconds if backoff_seconds > 0 else 0,
            "stop_conditions": bounds.get("stop_conditions"),
            "actor": actor,
            "reason": reason,
            "ts": ts,
            "execution_started": False,
            "retry_scheduled": False,
            "retry_started": False,
            "applied": False,
        }
    )


def _retry_exhausted_receipt(
    *,
    event_id: str,
    bounds: dict[str, Any],
    attempt_count: int,
    ts: int,
    actor: str,
    reason: str,
) -> dict[str, Any] | None:
    max_retries = _safe_int(bounds.get("max_retries"), default=0, minimum=0, maximum=10)
    if max_retries <= 0 or attempt_count <= max_retries:
        return None
    backoff_seconds = _safe_int(bounds.get("backoff_seconds"), default=0, minimum=0, maximum=3_600)
    return _filtered_receipt(
        {
            "kind": "reactor.retry_exhausted.receipt",
            "exhaustion_id": f"{event_id}_retry_exhausted_{attempt_count}",
            "event_id": event_id,
            "status": "exhausted",
            "route": "deadletter_candidate",
            "gate": "retry_budget_exhausted",
            "outcome": "dispatch_engine_not_implemented",
            "stable_state": "retry_budget_exhausted",
            "next_step": "review_retry_exhaustion_before_deadletter_or_dispatch_engine",
            "attempt_count": attempt_count,
            "max_retries": max_retries,
            "remaining_retries": 0,
            "backoff_seconds": backoff_seconds,
            "stop_conditions": bounds.get("stop_conditions"),
            "actor": actor,
            "reason": reason,
            "ts": ts,
            "execution_started": False,
            "retry_scheduled": False,
            "retry_started": False,
            "deadletter_enqueued": False,
            "applied": False,
        }
    )


def _stable_return_route(
    *,
    status: str,
    blocker: dict[str, Any] | None,
    approval_decision: dict[str, Any] | None,
    approval_request: dict[str, Any] | None,
    deadletter_enqueue: dict[str, Any] | None,
    retry_schedule: dict[str, Any] | None,
    retry_candidate: dict[str, Any] | None,
    retry_exhausted: dict[str, Any] | None,
) -> str:
    if deadletter_enqueue:
        return "deadletter_queue"
    if retry_exhausted:
        return "deadletter_candidate"
    if retry_schedule:
        return "retry_backoff"
    if retry_candidate:
        return "retry_backoff"
    if approval_request:
        return "approval_queue"
    if approval_decision and approval_decision.get("approval_allows_dispatch") is False:
        return "operator_review"
    if blocker:
        return _safe_str(blocker.get("route")).strip() or "operator_review"
    if status == "dispatch_deferred":
        return "dispatch_engine"
    return "operator_review"


def _stable_return_source_receipt(
    *,
    dispatch_receipt: dict[str, Any],
    approval_decision: dict[str, Any] | None,
    approval_request: dict[str, Any] | None,
    deadletter_enqueue: dict[str, Any] | None,
    retry_schedule: dict[str, Any] | None,
    retry_candidate: dict[str, Any] | None,
    retry_exhausted: dict[str, Any] | None,
) -> dict[str, Any]:
    return (
        deadletter_enqueue
        or approval_request
        or approval_decision
        or retry_exhausted
        or retry_schedule
        or retry_candidate
        or dispatch_receipt
    )


def _stable_return_receipt(
    *,
    event_id: str,
    status: str,
    outcome: str,
    stable_state: str,
    next_step: str,
    actor: str,
    reason: str,
    attempt_count: int,
    ts: int,
    dispatch_receipt: dict[str, Any],
    blocker: dict[str, Any] | None,
    approval_decision: dict[str, Any] | None,
    approval_request: dict[str, Any] | None,
    deadletter_enqueue: dict[str, Any] | None,
    retry_schedule: dict[str, Any] | None,
    retry_candidate: dict[str, Any] | None,
    retry_exhausted: dict[str, Any] | None,
    verification_receipt: dict[str, Any] | None = None,
) -> dict[str, Any]:
    source_receipt = _stable_return_source_receipt(
        dispatch_receipt=dispatch_receipt,
        approval_decision=approval_decision,
        approval_request=approval_request,
        deadletter_enqueue=deadletter_enqueue,
        retry_schedule=retry_schedule,
        retry_candidate=retry_candidate,
        retry_exhausted=retry_exhausted,
    )
    route = _stable_return_route(
        status=status,
        blocker=blocker,
        approval_decision=approval_decision,
        approval_request=approval_request,
        deadletter_enqueue=deadletter_enqueue,
        retry_schedule=retry_schedule,
        retry_candidate=retry_candidate,
        retry_exhausted=retry_exhausted,
    )
    gate = (
        _safe_str(source_receipt.get("gate")).strip()
        or _safe_str((blocker or {}).get("gate")).strip()
        or _safe_str(stable_state).strip()
    )
    return _filtered_receipt(
        {
            "kind": "reactor.stable_return.receipt",
            "receipt_id": f"{event_id}_stable_return_{attempt_count}",
            "event_id": event_id,
            "status": "settled",
            "dispatch_status": status,
            "outcome": outcome,
            "route": route,
            "gate": gate,
            "stable_state": stable_state,
            "next_step": next_step,
            "source_receipt_kind": source_receipt.get("kind"),
            "source_receipt_ref": _receipt_reference(source_receipt),
            "verification_receipt_id": _safe_str((verification_receipt or {}).get("receipt_id")).strip(),
            "verification_status": (verification_receipt or {}).get("verification_status"),
            "verification_outcome": (verification_receipt or {}).get("verification_outcome"),
            "attempt_count": attempt_count,
            "actor": actor,
            "reason": reason,
            "ts": ts,
            "returned_to_stable_state": True,
            "approval_queued": approval_request is not None,
            "approval_status": (approval_decision or {}).get("status"),
            "deadletter_enqueued": deadletter_enqueue is not None,
            "retry_candidate": retry_candidate is not None,
            "retry_scheduled": retry_schedule is not None,
            "retry_exhausted": retry_exhausted is not None,
            "execution_started": False,
            "dispatch_applied": False,
            "retry_started": False,
            "escalation_started": False,
            "memory_write": False,
            "governance": {
                "gate": "reactor_stable_return_receipt",
                "execution_authority": False,
                "dispatch_authority": False,
                "approval_authority": False,
                "retry_authority": False,
                "deadletter_resolution_authority": False,
                "escalation_authority": False,
                "memory_write": False,
            },
        }
    )


def _verification_state(
    *,
    status: str,
    outcome: str,
    blocker: dict[str, Any] | None,
    approval_decision: dict[str, Any] | None,
    approval_request: dict[str, Any] | None,
    deadletter_enqueue: dict[str, Any] | None,
    retry_schedule: dict[str, Any] | None,
    retry_candidate: dict[str, Any] | None,
    retry_exhausted: dict[str, Any] | None,
) -> tuple[str, str, str]:
    if deadletter_enqueue:
        return (
            "not_run",
            "deadletter_queued_for_review",
            "deadletter_queue_item_requires_operator_review_before_recovery_claim",
        )
    if retry_exhausted:
        return (
            "not_run",
            "retry_budget_exhausted",
            "retry_exhaustion_requires_review_before_recovery_or_completion_claim",
        )
    if retry_schedule:
        return (
            "not_run",
            "retry_scheduled",
            "retry_schedule_item_waits_for_due_time_before_execution_claim",
        )
    if retry_candidate:
        return (
            "not_available",
            "retry_scheduler_not_implemented",
            "retry_scheduler_must_exist_before_retry_verification",
        )
    if approval_request:
        return ("not_run", "awaiting_approval", "approval_decision_required_before_verification")
    if approval_decision and approval_decision.get("approval_allows_dispatch") is False:
        return ("not_run", "approval_denied", "denied_approval_prevents_dispatch_verification")
    if blocker:
        return (
            "not_run",
            _safe_str(blocker.get("gate")).strip() or "dispatch_blocked",
            "blocked_dispatch_prevents_outcome_verification",
        )
    if status == "dispatch_deferred" and outcome == "dispatch_engine_not_implemented":
        return (
            "not_available",
            "dispatch_engine_not_implemented",
            "dispatch_engine_must_exist_before_reactor_outcome_verification",
        )
    return ("not_run", outcome or "dispatch_not_started", "dispatch_did_not_start")


def _verification_receipt(
    *,
    event_id: str,
    status: str,
    outcome: str,
    stable_state: str,
    next_step: str,
    actor: str,
    reason: str,
    attempt_count: int,
    ts: int,
    dispatch_receipt: dict[str, Any],
    blocker: dict[str, Any] | None,
    approval_decision: dict[str, Any] | None,
    approval_request: dict[str, Any] | None,
    deadletter_enqueue: dict[str, Any] | None,
    retry_schedule: dict[str, Any] | None,
    retry_candidate: dict[str, Any] | None,
    retry_exhausted: dict[str, Any] | None,
) -> dict[str, Any]:
    source_receipt = _stable_return_source_receipt(
        dispatch_receipt=dispatch_receipt,
        approval_decision=approval_decision,
        approval_request=approval_request,
        deadletter_enqueue=deadletter_enqueue,
        retry_schedule=retry_schedule,
        retry_candidate=retry_candidate,
        retry_exhausted=retry_exhausted,
    )
    route = _stable_return_route(
        status=status,
        blocker=blocker,
        approval_decision=approval_decision,
        approval_request=approval_request,
        deadletter_enqueue=deadletter_enqueue,
        retry_schedule=retry_schedule,
        retry_candidate=retry_candidate,
        retry_exhausted=retry_exhausted,
    )
    verification_status, verification_outcome, verification_reason = _verification_state(
        status=status,
        outcome=outcome,
        blocker=blocker,
        approval_decision=approval_decision,
        approval_request=approval_request,
        deadletter_enqueue=deadletter_enqueue,
        retry_schedule=retry_schedule,
        retry_candidate=retry_candidate,
        retry_exhausted=retry_exhausted,
    )
    return _filtered_receipt(
        {
            "kind": "reactor.verification.receipt",
            "receipt_id": f"{event_id}_verification_{attempt_count}",
            "event_id": event_id,
            "status": verification_status,
            "verification_status": verification_status,
            "verification_outcome": verification_outcome,
            "verification_reason": verification_reason,
            "route": route,
            "gate": source_receipt.get("gate") or (blocker or {}).get("gate") or stable_state,
            "stable_state": stable_state,
            "next_step": next_step,
            "source_receipt_kind": source_receipt.get("kind"),
            "source_receipt_ref": _receipt_reference(source_receipt),
            "attempt_count": attempt_count,
            "actor": actor,
            "reason": reason,
            "ts": ts,
            "verified": False,
            "completion_claimed": False,
            "completion_claim_allowed": False,
            "verification_required_before_completion_claim": True,
            "execution_started": False,
            "dispatch_applied": False,
            "retry_started": False,
            "escalation_started": False,
            "memory_write": False,
            "governance": {
                "gate": "reactor_verification_receipt",
                "execution_authority": False,
                "dispatch_authority": False,
                "approval_authority": False,
                "retry_authority": False,
                "deadletter_resolution_authority": False,
                "escalation_authority": False,
                "memory_write": False,
            },
        }
    )


def _reactor_approval_payload(
    *,
    event_id: str,
    trigger: dict[str, Any],
    classification: dict[str, Any],
    bounds: dict[str, Any],
    blocker: dict[str, Any],
    actor: str,
    reason: str,
    attempt_count: int,
) -> dict[str, Any]:
    payload = {
        "kind": "reactor.dispatch.approval_request",
        "event_id": event_id,
        "reactor_event_id": event_id,
        "trigger_source": trigger.get("source"),
        "trigger_type": trigger.get("type"),
        "summary": trigger.get("summary"),
        "mission_id": trigger.get("mission_id"),
        "operation_id": trigger.get("operation_id"),
        "trace_id": trigger.get("trace_id"),
        "run_id": trigger.get("run_id"),
        "mode": classification.get("mode"),
        "risk_tier": classification.get("risk_tier"),
        "action_class": classification.get("action_class"),
        "approval_required": True,
        "gate": blocker.get("gate"),
        "route": blocker.get("route"),
        "stable_state": blocker.get("stable_state"),
        "next_step": blocker.get("next_step"),
        "attempt_count": attempt_count,
        "max_actions": bounds.get("max_actions"),
        "max_runtime_seconds": bounds.get("max_runtime_seconds"),
        "max_retries": bounds.get("max_retries"),
        "stop_conditions": bounds.get("stop_conditions"),
        "reactor_actor": actor,
        "reactor_reason": reason,
        "execution_started": False,
        "dispatch_applied": False,
    }
    redacted = redact_governed_value(_filtered_receipt(payload))
    return redacted if isinstance(redacted, dict) else {}


def _approval_request_reason(trigger: dict[str, Any], reason: str) -> str:
    summary = _safe_str(trigger.get("summary")).strip()
    if summary:
        return f"Reactor dispatch requires approval: {summary}"
    if reason:
        return f"Reactor dispatch requires approval: {reason}"
    return "Reactor dispatch requires approval."


def _reactor_approval_request_receipt(
    *,
    event_id: str,
    approval_id: str,
    blocker: dict[str, Any],
    actor: str,
    reason: str,
    attempt_count: int,
    ts: int,
) -> dict[str, Any]:
    return _filtered_receipt(
        {
            "kind": "reactor.approval_request.receipt",
            "approval_id": approval_id,
            "event_id": event_id,
            "status": "pending",
            "route": "approval_queue",
            "gate": blocker.get("gate"),
            "stable_state": blocker.get("stable_state"),
            "next_step": "review_pending_approval_before_dispatch",
            "attempt_count": attempt_count,
            "actor": actor,
            "reason": reason,
            "ts": ts,
            "approval_queued": True,
            "approval_decision_started": False,
            "execution_started": False,
            "applied": False,
        }
    )


def _approval_record_status(approval_id: str) -> str:
    cleaned = _safe_str(approval_id).strip()
    if not cleaned:
        return ""
    candidates = (
        ("pending", approvals.pending_dir()),
        ("approved", approvals.approved_dir()),
        ("rejected", approvals.rejected_dir()),
        ("emergency", approvals.emergency_dir()),
    )
    for status, folder in candidates:
        path = folder / f"{cleaned}.json"
        if not path.exists() or not path.is_file():
            continue
        try:
            json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            return "corrupt"
        return status
    return "missing"


def _approval_decision_next_step(status: str) -> str:
    if status == "approved":
        return "implement_dispatch_engine_before_execution"
    if status == "rejected":
        return "review_rejected_approval_before_dispatch"
    if status == "emergency":
        return "review_emergency_approval_before_dispatch"
    return "wait_for_approval_decision_before_dispatch"


def _reactor_approval_decision_receipt(
    *,
    event_id: str,
    approval_id: str,
    approval_status: str,
    actor: str,
    reason: str,
    attempt_count: int,
    ts: int,
) -> dict[str, Any] | None:
    if approval_status not in {"approved", "rejected", "emergency"}:
        return None
    route = "approval_queue" if approval_status == "approved" else "operator_review"
    return _filtered_receipt(
        {
            "kind": "reactor.approval_decision.receipt",
            "approval_id": approval_id,
            "event_id": event_id,
            "status": approval_status,
            "route": route,
            "gate": f"approval_{approval_status}",
            "stable_state": "awaiting_dispatch_engine"
            if approval_status == "approved"
            else f"approval_{approval_status}",
            "next_step": _approval_decision_next_step(approval_status),
            "attempt_count": attempt_count,
            "actor": actor,
            "reason": reason,
            "ts": ts,
            "approval_allows_dispatch": approval_status == "approved",
            "approval_decision_recorded": True,
            "execution_started": False,
            "applied": False,
        }
    )


def _maybe_request_reactor_approval(
    *,
    event_id: str,
    trigger: dict[str, Any],
    classification: dict[str, Any],
    bounds: dict[str, Any],
    dispatch: dict[str, Any],
    blocker: dict[str, Any] | None,
    actor: str,
    reason: str,
    attempt_count: int,
    ts: int,
) -> dict[str, Any] | None:
    if blocker is None or blocker.get("route") != "approval_queue":
        return None

    existing_approval_id = (
        _safe_str(trigger.get("approval_id")).strip()
        or _safe_str(_as_dict(dispatch.get("approval_request")).get("approval_id")).strip()
    )
    if existing_approval_id:
        blocker["approval_id"] = existing_approval_id
        return None

    request_payload = _reactor_approval_payload(
        event_id=event_id,
        trigger=trigger,
        classification=classification,
        bounds=bounds,
        blocker=blocker,
        actor=actor,
        reason=reason,
        attempt_count=attempt_count,
    )
    approval = approvals.request(
        "reactor.dispatch",
        _approval_request_reason(trigger, reason),
        request_payload,
    )
    approval_id = _safe_str(approval.get("id")).strip()
    if not approval_id:
        return None

    receipt = _reactor_approval_request_receipt(
        event_id=event_id,
        approval_id=approval_id,
        blocker=blocker,
        actor=actor,
        reason=reason,
        attempt_count=attempt_count,
        ts=ts,
    )
    trigger["approval_id"] = approval_id
    blocker["approval_id"] = approval_id
    blocker["approval_request_receipt_id"] = approval_id
    blocker["approval_request_queued"] = True
    return receipt


def _approval_id_for_dispatch(trigger: dict[str, Any], dispatch: dict[str, Any]) -> str:
    return (
        _safe_str(trigger.get("approval_id")).strip()
        or _safe_str(_as_dict(dispatch.get("approval_request")).get("approval_id")).strip()
        or _safe_str(_as_dict(dispatch.get("approval_decision")).get("approval_id")).strip()
    )


def record_dispatch_attempt(event_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    path = _event_path(event_id)
    if path is None or not path.exists() or not path.is_file():
        return {"ok": False, "applied": False, "error": "not_found", "event": None}

    record = _read_raw_event(path)
    if record is None:
        return {"ok": False, "applied": False, "error": "unreadable_event", "event": None}

    redacted_payload = redact_governed_value(payload or {})
    data = redacted_payload if isinstance(redacted_payload, dict) else {}
    actor = _safe_str(data.get("actor")).strip()
    reason = _safe_str(data.get("reason") or data.get("summary")).strip()
    ts = _now_s()
    raw_classification = record.get("classification")
    classification = raw_classification if isinstance(raw_classification, dict) else {}
    raw_bounds = record.get("bounds")
    bounds = raw_bounds if isinstance(raw_bounds, dict) else {}
    raw_dispatch = record.get("dispatch")
    dispatch = raw_dispatch if isinstance(raw_dispatch, dict) else {}
    raw_trigger = record.get("trigger")
    trigger = raw_trigger if isinstance(raw_trigger, dict) else {}
    event_key = _safe_str(record.get("event_id") or record.get("id")).strip()
    attempt_count = _safe_int(dispatch.get("attempt_count"), default=0, minimum=0, maximum=100_000) + 1
    approval_id = _approval_id_for_dispatch(trigger, dispatch)
    approval_status = _approval_record_status(approval_id)
    approval_gate_state = _safe_str(classification.get("stable_state")).strip() == "awaiting_approval"
    approval_allows_dispatch = approval_gate_state and approval_status == "approved"
    approval_blocks_dispatch = approval_gate_state and approval_status in {"rejected", "emergency"}
    allowed = bool(classification.get("dispatch_allowed")) or approval_allows_dispatch

    if allowed:
        status = "dispatch_deferred"
        outcome = "dispatch_engine_not_implemented"
        stable_state = "awaiting_dispatch_engine"
        next_step = "implement_dispatch_engine_before_execution"
        blocker = None
    else:
        status = "dispatch_blocked"
        outcome = (
            f"approval_{approval_status}"
            if approval_blocks_dispatch
            else (_safe_str(classification.get("stable_state")).strip() or "dispatch_not_allowed")
        )
        stable_state = outcome
        next_step = (
            _approval_decision_next_step(approval_status)
            if approval_blocks_dispatch
            else _safe_str(classification.get("next_step")).strip() or "resolve_blocker_before_dispatch"
        )
        blocker = _dispatch_blocker_record(
            event_id=event_key,
            stable_state=stable_state,
            next_step=next_step,
            classification=classification,
            bounds=bounds,
            trigger=trigger,
            actor=actor,
            reason=reason,
            attempt_count=attempt_count,
            ts=ts,
        )
    approval_decision = _reactor_approval_decision_receipt(
        event_id=event_key,
        approval_id=approval_id,
        approval_status=approval_status,
        actor=actor,
        reason=reason,
        attempt_count=attempt_count,
        ts=ts,
    )
    approval_request = _maybe_request_reactor_approval(
        event_id=event_key,
        trigger=trigger,
        classification=classification,
        bounds=bounds,
        dispatch=dispatch,
        blocker=blocker,
        actor=actor,
        reason=reason,
        attempt_count=attempt_count,
        ts=ts,
    )
    deadletter_candidate = None
    deadletter_item = None
    deadletter_enqueue = None
    retry_schedule_item = None
    retry_schedule_receipt = None
    if blocker is not None and blocker.get("route") == "deadletter_candidate":
        deadletter_candidate = _deadletter_candidate_receipt(
            event_id=event_key,
            blocker=blocker,
            bounds=bounds,
            attempt_count=attempt_count,
            ts=ts,
        )
        blocker["deadletter_candidate_receipt_id"] = deadletter_candidate.get("candidate_id")
    retry_candidate = None
    retry_exhausted = None
    if allowed:
        retry_candidate = _retry_candidate_receipt(
            event_id=event_key,
            bounds=bounds,
            attempt_count=attempt_count,
            ts=ts,
            actor=actor,
            reason=reason,
        )
        retry_exhausted = _retry_exhausted_receipt(
            event_id=event_key,
            bounds=bounds,
            attempt_count=attempt_count,
            ts=ts,
            actor=actor,
            reason=reason,
        )
        if retry_exhausted is not None:
            stable_state = _safe_str(retry_exhausted.get("stable_state")).strip() or stable_state
            next_step = _safe_str(retry_exhausted.get("next_step")).strip() or next_step
    if retry_candidate is not None:
        scheduled_retry = schedule_retry(
            event=record,
            source_receipt=retry_candidate,
            actor=actor,
            reason=reason,
            ts=ts,
        )
        retry_schedule_item = _as_dict(scheduled_retry.get("item"))
        retry_schedule_receipt = _as_dict(scheduled_retry.get("receipt"))
        retry_schedule_id = _safe_str(
            retry_schedule_item.get("retry_schedule_id") or retry_schedule_receipt.get("retry_schedule_id")
        ).strip()
        if retry_schedule_id:
            retry_candidate["retry_schedule_id"] = retry_schedule_id
            retry_candidate["retry_schedule_receipt_id"] = retry_schedule_id
            retry_candidate["retry_scheduled"] = True
    deadletter_source = retry_exhausted or deadletter_candidate
    if deadletter_source is not None:
        queued_deadletter = queue_deadletter(
            event=record,
            source_receipt=deadletter_source,
            actor=actor,
            reason=reason,
            ts=ts,
        )
        deadletter_item = _as_dict(queued_deadletter.get("item"))
        deadletter_enqueue = _as_dict(queued_deadletter.get("receipt"))
        deadletter_id = _safe_str(deadletter_item.get("deadletter_id") or deadletter_enqueue.get("deadletter_id"))
        if deadletter_id:
            deadletter_source["deadletter_id"] = deadletter_id
            deadletter_source["deadletter_enqueued"] = True
            deadletter_source["deadletter_enqueue_receipt_id"] = deadletter_id

    receipt = _dispatch_attempt_receipt(
        event_id=event_key,
        status=status,
        outcome=outcome,
        allowed=allowed,
        stable_state=stable_state,
        next_step=next_step,
        reason=reason,
        actor=actor,
        ts=ts,
        bounds=bounds,
        blocker=blocker,
    )
    verification = _verification_receipt(
        event_id=event_key,
        status=status,
        outcome=outcome,
        stable_state=stable_state,
        next_step=next_step,
        actor=actor,
        reason=reason,
        attempt_count=attempt_count,
        ts=ts,
        dispatch_receipt=receipt,
        blocker=blocker,
        approval_decision=approval_decision,
        approval_request=approval_request,
        deadletter_enqueue=deadletter_enqueue,
        retry_schedule=retry_schedule_receipt,
        retry_candidate=retry_candidate,
        retry_exhausted=retry_exhausted,
    )
    stable_return = _stable_return_receipt(
        event_id=event_key,
        status=status,
        outcome=outcome,
        stable_state=stable_state,
        next_step=next_step,
        actor=actor,
        reason=reason,
        attempt_count=attempt_count,
        ts=ts,
        dispatch_receipt=receipt,
        blocker=blocker,
        approval_decision=approval_decision,
        approval_request=approval_request,
        deadletter_enqueue=deadletter_enqueue,
        retry_schedule=retry_schedule_receipt,
        retry_candidate=retry_candidate,
        retry_exhausted=retry_exhausted,
        verification_receipt=verification,
    )
    updated_dispatch = {
        **dispatch,
        "status": status,
        "allowed": allowed,
        "applied": False,
        "engine": "not_implemented",
        "attempt_count": attempt_count,
        "last_attempt_ts": ts,
        "last_outcome": outcome,
        "last_receipt": receipt,
    }
    if blocker is not None:
        updated_dispatch["blocker"] = blocker
        updated_dispatch["blocked_route"] = blocker.get("route")
    else:
        updated_dispatch.pop("blocker", None)
        updated_dispatch.pop("blocked_route", None)
    if deadletter_candidate is not None:
        updated_dispatch["deadletter_candidate"] = deadletter_candidate
    if deadletter_item:
        updated_dispatch["deadletter_item"] = deadletter_item
    if deadletter_enqueue:
        updated_dispatch["deadletter_enqueue"] = deadletter_enqueue
    if approval_decision is not None:
        updated_dispatch["approval_decision"] = approval_decision
    if approval_request is not None:
        updated_dispatch["approval_request"] = approval_request
    if retry_candidate is not None:
        updated_dispatch["retry_candidate"] = retry_candidate
    else:
        updated_dispatch.pop("retry_candidate", None)
    if retry_schedule_item:
        updated_dispatch["retry_schedule"] = retry_schedule_item
    else:
        updated_dispatch.pop("retry_schedule", None)
    if retry_schedule_receipt:
        updated_dispatch["retry_schedule_receipt"] = retry_schedule_receipt
    else:
        updated_dispatch.pop("retry_schedule_receipt", None)
    if retry_exhausted is not None:
        updated_dispatch["retry_exhausted"] = retry_exhausted
        updated_dispatch["retry_exhausted_route"] = retry_exhausted.get("route")
    else:
        updated_dispatch.pop("retry_exhausted", None)
        updated_dispatch.pop("retry_exhausted_route", None)

    raw_journal = record.get("decision_journal")
    decision_journal = raw_journal if isinstance(raw_journal, list) else []
    journal_entry = {
        "kind": "reactor.dispatch.attempted",
        "ts": ts,
        "decision": status,
        "outcome": outcome,
        "applied": False,
        "execution_started": False,
        "stable_state": stable_state,
        "next_step": next_step,
    }
    if blocker is not None:
        journal_entry["blocker_id"] = blocker.get("blocker_id")
        journal_entry["blocked_route"] = blocker.get("route")
    if deadletter_candidate is not None:
        journal_entry["deadletter_candidate_id"] = deadletter_candidate.get("candidate_id")
    if deadletter_enqueue:
        journal_entry["deadletter_id"] = deadletter_enqueue.get("deadletter_id")
        journal_entry["deadletter_enqueued"] = True
        journal_entry["deadletter_enqueue_status"] = deadletter_enqueue.get("status")
    if approval_decision is not None:
        journal_entry["approval_id"] = approval_decision.get("approval_id")
        journal_entry["approval_status"] = approval_decision.get("status")
        journal_entry["approval_allows_dispatch"] = approval_decision.get("approval_allows_dispatch")
    if approval_request is not None:
        journal_entry["approval_id"] = approval_request.get("approval_id")
        journal_entry["approval_request_queued"] = True
    if retry_candidate is not None:
        journal_entry["retry_candidate_id"] = retry_candidate.get("candidate_id")
    if retry_schedule_receipt:
        journal_entry["retry_schedule_id"] = retry_schedule_receipt.get("retry_schedule_id")
        journal_entry["retry_scheduled"] = True
        journal_entry["retry_schedule_status"] = retry_schedule_receipt.get("status")
    if retry_exhausted is not None:
        journal_entry["retry_exhausted_id"] = retry_exhausted.get("exhaustion_id")
        journal_entry["retry_exhausted_route"] = retry_exhausted.get("route")
    journal_entry["verification_receipt_id"] = verification.get("receipt_id")
    journal_entry["verification_status"] = verification.get("verification_status")
    journal_entry["verification_outcome"] = verification.get("verification_outcome")
    decision_journal.append(journal_entry)

    raw_receipts = record.get("receipts")
    receipts = raw_receipts if isinstance(raw_receipts, list) else []
    if not receipts and isinstance(record.get("receipt"), dict):
        receipts.append(record["receipt"])
    receipts.append(receipt)
    if approval_decision is not None:
        receipts.append(approval_decision)
    if approval_request is not None:
        receipts.append(approval_request)
    if deadletter_candidate is not None:
        receipts.append(deadletter_candidate)
    if retry_candidate is not None:
        receipts.append(retry_candidate)
    if retry_schedule_receipt:
        receipts.append(retry_schedule_receipt)
    if retry_exhausted is not None:
        receipts.append(retry_exhausted)
    if deadletter_enqueue:
        receipts.append(deadletter_enqueue)
    receipts.append(verification)
    receipts.append(stable_return)
    raw_blockers = record.get("blockers")
    blockers = raw_blockers if isinstance(raw_blockers, list) else []
    if blocker is not None:
        blockers.append(blocker)

    record["status"] = status
    record["updated_ts"] = ts
    record["stable_state"] = stable_state
    record["trigger"] = trigger
    record["dispatch"] = updated_dispatch
    record["decision_journal"] = decision_journal
    record["receipts"] = receipts
    record["latest_dispatch_attempt_receipt"] = receipt
    record["latest_verification_receipt"] = verification
    record["latest_stable_return"] = stable_return
    record["latest_receipt"] = stable_return
    if blocker is not None:
        record["blockers"] = blockers
        record["latest_blocker"] = blocker
    else:
        record.pop("latest_blocker", None)
    if deadletter_candidate is not None:
        raw_deadletter_candidates = record.get("deadletter_candidates")
        deadletter_candidates = raw_deadletter_candidates if isinstance(raw_deadletter_candidates, list) else []
        deadletter_candidates.append(deadletter_candidate)
        record["deadletter_candidates"] = deadletter_candidates
        record["latest_deadletter_candidate"] = deadletter_candidate
    if deadletter_item:
        raw_deadletter_items = record.get("deadletter_items")
        deadletter_items = raw_deadletter_items if isinstance(raw_deadletter_items, list) else []
        deadletter_item_id = _safe_str(deadletter_item.get("deadletter_id")).strip()
        if deadletter_item_id and all(
            _safe_str(_as_dict(item).get("deadletter_id")).strip() != deadletter_item_id for item in deadletter_items
        ):
            deadletter_items.append(deadletter_item)
        record["deadletter_items"] = deadletter_items
        record["latest_deadletter_item"] = deadletter_item
    if deadletter_enqueue:
        raw_deadletter_enqueues = record.get("deadletter_enqueues")
        deadletter_enqueues = raw_deadletter_enqueues if isinstance(raw_deadletter_enqueues, list) else []
        deadletter_enqueues.append(deadletter_enqueue)
        record["deadletter_enqueues"] = deadletter_enqueues
        record["latest_deadletter_enqueue"] = deadletter_enqueue
    if approval_request is not None:
        raw_approval_requests = record.get("approval_requests")
        approval_requests = raw_approval_requests if isinstance(raw_approval_requests, list) else []
        approval_requests.append(approval_request)
        record["approval_requests"] = approval_requests
        record["latest_approval_request"] = approval_request
    if approval_decision is not None:
        raw_approval_decisions = record.get("approval_decisions")
        approval_decisions = raw_approval_decisions if isinstance(raw_approval_decisions, list) else []
        approval_decisions.append(approval_decision)
        record["approval_decisions"] = approval_decisions
        record["latest_approval_decision"] = approval_decision
    if retry_candidate is not None:
        raw_retry_candidates = record.get("retry_candidates")
        retry_candidates = raw_retry_candidates if isinstance(raw_retry_candidates, list) else []
        retry_candidates.append(retry_candidate)
        record["retry_candidates"] = retry_candidates
        record["latest_retry_candidate"] = retry_candidate
    if retry_schedule_item:
        raw_retry_schedules = record.get("retry_schedules")
        retry_schedules = raw_retry_schedules if isinstance(raw_retry_schedules, list) else []
        retry_schedule_id = _safe_str(retry_schedule_item.get("retry_schedule_id")).strip()
        if retry_schedule_id and all(
            _safe_str(_as_dict(item).get("retry_schedule_id")).strip() != retry_schedule_id for item in retry_schedules
        ):
            retry_schedules.append(retry_schedule_item)
        record["retry_schedules"] = retry_schedules
        record["latest_retry_schedule"] = retry_schedule_item
    if retry_schedule_receipt:
        raw_retry_schedule_receipts = record.get("retry_schedule_receipts")
        retry_schedule_receipts = raw_retry_schedule_receipts if isinstance(raw_retry_schedule_receipts, list) else []
        retry_schedule_receipts.append(retry_schedule_receipt)
        record["retry_schedule_receipts"] = retry_schedule_receipts
        record["latest_retry_schedule_receipt"] = retry_schedule_receipt
    if retry_exhausted is not None:
        raw_retry_exhaustions = record.get("retry_exhaustions")
        retry_exhaustions = raw_retry_exhaustions if isinstance(raw_retry_exhaustions, list) else []
        retry_exhaustions.append(retry_exhausted)
        record["retry_exhaustions"] = retry_exhaustions
        record["latest_retry_exhausted"] = retry_exhausted
    raw_stable_returns = record.get("stable_returns")
    stable_returns = raw_stable_returns if isinstance(raw_stable_returns, list) else []
    stable_returns.append(stable_return)
    record["stable_returns"] = stable_returns
    raw_verifications = record.get("verification_receipts")
    verifications = raw_verifications if isinstance(raw_verifications, list) else []
    verifications.append(verification)
    record["verification_receipts"] = verifications
    raw_governance = record.get("governance")
    governance = raw_governance if isinstance(raw_governance, dict) else {}
    governance.update(
        {
            "gate": "reactor_dispatch_attempt",
            "execution_authority": False,
            "approval_authority": False,
            "promotion_authority": False,
            "memory_write": False,
            "dispatch_authority": False,
            "attempt_only": True,
            "approval_request_queued": approval_request is not None,
            "approval_status": approval_status,
            "approval_allows_dispatch": approval_allows_dispatch,
            "deadletter_enqueued": bool(deadletter_enqueue),
            "deadletter_resolution_authority": False,
            "retry_scheduled": bool(retry_schedule_receipt),
            "retry_execution_authority": False,
            "next_step": next_step,
        }
    )
    record["governance"] = governance

    _atomic_write_json(path, record)
    return {
        "ok": True,
        "applied": True,
        "event_id": record.get("event_id") or record.get("id"),
        "receipt": _display(receipt),
        "event": _display(record),
    }


def list_events(
    *,
    limit: int = 200,
    status: str | None = None,
    trigger_source: str | None = None,
    stable_state: str | None = None,
    blocker_route: str | None = None,
    review_route: str | None = None,
    receipt_kind: str | None = None,
) -> list[dict[str, Any]]:
    root = _event_root()
    if not root.exists():
        return []
    status_filter = _safe_str(status).strip().lower()
    source_filter = _safe_str(trigger_source).strip().lower()
    stable_state_filter = _safe_str(stable_state).strip().lower()
    blocker_route_filter = _safe_str(blocker_route).strip().lower()
    review_route_filter = _safe_str(review_route).strip().lower()
    receipt_kind_filter = _safe_str(receipt_kind).strip().lower()
    items: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.json")):
        if not path.is_file():
            continue
        item = _read_event(path)
        if not item:
            continue
        trigger = _as_dict(item.get("trigger"))
        dispatch = _as_dict(item.get("dispatch"))
        if status_filter and _safe_str(item.get("status")).strip().lower() != status_filter:
            continue
        if source_filter and _safe_str(trigger.get("source")).strip().lower() != source_filter:
            continue
        if stable_state_filter and _safe_str(item.get("stable_state")).strip().lower() != stable_state_filter:
            continue
        if blocker_route_filter and blocker_route_filter not in _blocker_routes(dispatch):
            continue
        if review_route_filter and review_route_filter not in _review_routes(item):
            continue
        if receipt_kind_filter and receipt_kind_filter not in _receipt_kinds(item):
            continue
        items.append(item)
    items.sort(
        key=lambda item: (
            _safe_int(item.get("created_ts"), default=0, minimum=0, maximum=2_147_483_647),
            _safe_str(item.get("event_id")),
        ),
        reverse=True,
    )
    return items[: max(1, min(int(limit), 5000))]


def _blocker_routes(dispatch: dict[str, Any]) -> set[str]:
    routes = {_safe_str(dispatch.get("blocked_route")).strip().lower()}
    blocker = _as_dict(dispatch.get("blocker"))
    routes.add(_safe_str(blocker.get("route")).strip().lower())
    return {route for route in routes if route}


def _review_routes(item: dict[str, Any]) -> set[str]:
    dispatch = _as_dict(item.get("dispatch"))
    routes = set(_blocker_routes(dispatch))
    routes.add(_safe_str(dispatch.get("retry_exhausted_route")).strip().lower())
    for key in ("deadletter_candidate", "retry_candidate", "retry_exhausted"):
        candidate = _as_dict(dispatch.get(key))
        routes.add(_safe_str(candidate.get("route")).strip().lower())
    retry_schedule = _as_dict(dispatch.get("retry_schedule")) or _as_dict(dispatch.get("retry_schedule_receipt"))
    routes.add(_safe_str(retry_schedule.get("route")).strip().lower())
    for key in ("latest_blocker", "latest_deadletter_candidate", "latest_retry_candidate", "latest_retry_exhausted"):
        candidate = _as_dict(item.get(key))
        routes.add(_safe_str(candidate.get("route")).strip().lower())
    latest_retry_schedule = _as_dict(item.get("latest_retry_schedule")) or _as_dict(
        item.get("latest_retry_schedule_receipt")
    )
    routes.add(_safe_str(latest_retry_schedule.get("route")).strip().lower())
    raw_blockers = item.get("blockers")
    blockers = raw_blockers if isinstance(raw_blockers, list) else []
    for blocker_item in blockers:
        blocker = _as_dict(blocker_item)
        routes.add(_safe_str(blocker.get("route")).strip().lower())
    return {route for route in routes if route}


def _receipt_kinds(item: dict[str, Any]) -> set[str]:
    kinds = set()
    for key in (
        "receipt",
        "latest_receipt",
        "latest_dispatch_attempt_receipt",
        "latest_verification_receipt",
        "latest_approval_decision",
        "latest_stable_return",
        "latest_deadletter_enqueue",
        "latest_deadletter_candidate",
        "latest_retry_candidate",
        "latest_retry_schedule_receipt",
        "latest_retry_exhausted",
    ):
        receipt = _as_dict(item.get(key))
        kinds.add(_safe_str(receipt.get("kind")).strip().lower())
    raw_receipts = item.get("receipts")
    receipts = raw_receipts if isinstance(raw_receipts, list) else []
    for receipt_item in receipts:
        receipt = _as_dict(receipt_item)
        kinds.add(_safe_str(receipt.get("kind")).strip().lower())
    return {kind for kind in kinds if kind}


def _review_action(route: str, status: str, gate: str) -> str:
    if route == "approval_queue":
        return "review_or_resolve_approval_before_dispatch"
    if route == "operator_review":
        return "review_mode_boundary_before_dispatch"
    if route == "deadletter_candidate" and gate == "retry_budget_exhausted":
        return "review_retry_exhaustion_before_deadletter_or_dispatch_engine"
    if route == "deadletter_candidate":
        return "review_deadletter_candidate_before_escalation"
    if route == "retry_backoff":
        return "review_retry_candidate_before_scheduler_exists"
    return f"review_{status or 'pending'}"


def _review_projection(
    *,
    item: dict[str, Any],
    route: str,
    status: str,
    gate: str,
    receipt: dict[str, Any],
    blocker: dict[str, Any] | None = None,
) -> dict[str, Any]:
    trigger = _as_dict(item.get("trigger"))
    classification = _as_dict(item.get("classification"))
    receipt_kind = _safe_str(receipt.get("kind")).strip()
    receipt_ref = _receipt_reference(receipt)
    blocker_ref = _receipt_reference(blocker or {})
    next_step = (
        _safe_str(receipt.get("next_step")).strip()
        or _safe_str((blocker or {}).get("next_step")).strip()
        or _safe_str(classification.get("next_step")).strip()
    )
    return _filtered_receipt(
        {
            "event_id": item.get("event_id") or item.get("id"),
            "status": item.get("status"),
            "stable_state": item.get("stable_state"),
            "created_ts": item.get("created_ts"),
            "updated_ts": item.get("updated_ts"),
            "trigger": {
                "source": trigger.get("source"),
                "type": trigger.get("type"),
                "summary": trigger.get("summary"),
                "mission_id": trigger.get("mission_id"),
                "operation_id": trigger.get("operation_id"),
                "approval_id": trigger.get("approval_id"),
            },
            "classification": {
                "mode": classification.get("mode"),
                "risk_tier": classification.get("risk_tier"),
                "action_class": classification.get("action_class"),
                "approval_required": classification.get("approval_required"),
            },
            "review": {
                "route": route,
                "status": status,
                "gate": gate,
                "action": _review_action(route, status, gate),
                "next_step": next_step,
                "receipt_kind": receipt_kind,
                "receipt_ref": receipt_ref,
                "blocker_ref": blocker_ref,
                "execution_started": False,
                "applied": False,
            },
            "governance": {
                "execution_authority": False,
                "approval_authority": False,
                "dispatch_authority": False,
                "deadletter_authority": False,
                "retry_authority": False,
                "memory_write": False,
            },
        }
    )


def _active_review_projection(item: dict[str, Any]) -> dict[str, Any] | None:
    dispatch = _as_dict(item.get("dispatch"))
    stable_state = _safe_str(item.get("stable_state")).strip().lower()
    blocker = _as_dict(dispatch.get("blocker")) or _as_dict(item.get("latest_blocker"))
    approval_request = _as_dict(dispatch.get("approval_request")) or _as_dict(item.get("latest_approval_request"))
    deadletter_candidate = _as_dict(dispatch.get("deadletter_candidate")) or _as_dict(
        item.get("latest_deadletter_candidate")
    )
    retry_candidate = _as_dict(dispatch.get("retry_candidate"))
    retry_schedule = _as_dict(dispatch.get("retry_schedule_receipt")) or _as_dict(
        item.get("latest_retry_schedule_receipt")
    )
    retry_exhausted = _as_dict(dispatch.get("retry_exhausted")) or _as_dict(item.get("latest_retry_exhausted"))

    if stable_state == "retry_budget_exhausted" and retry_exhausted:
        return _review_projection(
            item=item,
            route="deadletter_candidate",
            status=_safe_str(retry_exhausted.get("status")).strip() or "exhausted",
            gate=_safe_str(retry_exhausted.get("gate")).strip() or "retry_budget_exhausted",
            receipt=retry_exhausted,
            blocker=blocker,
        )
    if stable_state == "blocked_by_budget" and deadletter_candidate:
        return _review_projection(
            item=item,
            route="deadletter_candidate",
            status=_safe_str(deadletter_candidate.get("status")).strip() or "candidate",
            gate=_safe_str(deadletter_candidate.get("gate")).strip() or "budget_exhausted",
            receipt=deadletter_candidate,
            blocker=blocker,
        )
    if stable_state == "awaiting_dispatch_engine" and retry_schedule:
        return _review_projection(
            item=item,
            route="retry_backoff",
            status=_safe_str(retry_schedule.get("status")).strip() or "scheduled",
            gate=_safe_str(retry_schedule.get("gate")).strip() or "dispatch_engine_not_implemented",
            receipt=retry_schedule,
            blocker=blocker,
        )
    if stable_state == "awaiting_dispatch_engine" and retry_candidate:
        return _review_projection(
            item=item,
            route="retry_backoff",
            status=_safe_str(retry_candidate.get("status")).strip() or "candidate",
            gate=_safe_str(retry_candidate.get("gate")).strip() or "dispatch_engine_not_implemented",
            receipt=retry_candidate,
            blocker=blocker,
        )
    route = _safe_str(blocker.get("route")).strip()
    if route in {"approval_queue", "operator_review", "deadletter_candidate"}:
        receipt = approval_request if route == "approval_queue" and approval_request else blocker
        return _review_projection(
            item=item,
            route=route,
            status=_safe_str(blocker.get("status")).strip() or "waiting_for_review",
            gate=_safe_str(blocker.get("gate")).strip() or stable_state,
            receipt=receipt,
            blocker=blocker,
        )
    return None


def reactor_review_queue(*, limit: int = 200, route: str | None = None) -> dict[str, Any]:
    route_filter = _safe_str(route).strip().lower()
    items: list[dict[str, Any]] = []
    route_counts: dict[str, int] = {}
    stable_state_counts: dict[str, int] = {}
    for event in list_events(limit=5000):
        projection = _active_review_projection(event)
        if projection is None:
            continue
        review = _as_dict(projection.get("review"))
        review_route = _safe_str(review.get("route")).strip().lower()
        if route_filter and review_route != route_filter:
            continue
        items.append(projection)
        route_counts[review_route] = route_counts.get(review_route, 0) + 1
        stable_state = _safe_str(projection.get("stable_state")).strip() or "unknown"
        stable_state_counts[stable_state] = stable_state_counts.get(stable_state, 0) + 1
    limited = items[: max(1, min(int(limit), 5000))]
    return {
        "ok": True,
        "items": limited,
        "total": len(limited),
        "available_total": len(items),
        "limit": limit,
        "route": route_filter,
        "route_counts": route_counts,
        "stable_state_counts": stable_state_counts,
        "governance": {
            "gate": "reactor_review_queue_readback",
            "execution_authority": False,
            "approval_authority": False,
            "dispatch_authority": False,
            "deadletter_authority": False,
            "retry_authority": False,
            "memory_write": False,
        },
    }


def get_event(event_id: str) -> dict[str, Any] | None:
    path = _event_path(event_id)
    if path is None:
        return None
    if not path.exists() or not path.is_file():
        return None
    return _read_event(path)


def reactor_status() -> dict[str, Any]:
    items = list_events(limit=5000)
    status_counts: dict[str, int] = {}
    source_counts: dict[str, int] = {}
    stable_state_counts: dict[str, int] = {}
    blocker_route_counts: dict[str, int] = {}
    approval_request_counts: dict[str, int] = {}
    approval_decision_counts: dict[str, int] = {}
    deadletter_candidate_counts: dict[str, int] = {}
    deadletter_queue_counts: dict[str, int] = {}
    retry_candidate_counts: dict[str, int] = {}
    retry_schedule_counts: dict[str, int] = {}
    retry_exhausted_counts: dict[str, int] = {}
    verification_counts: dict[str, int] = {}
    verification_outcome_counts: dict[str, int] = {}
    stable_return_counts: dict[str, int] = {}
    deadletters = list_deadletters(limit=5000)
    retry_schedules = list_retry_schedules(limit=5000)
    for deadletter in deadletters:
        deadletter_status = _safe_str(deadletter.get("status")).strip() or "unknown"
        deadletter_queue_counts[deadletter_status] = deadletter_queue_counts.get(deadletter_status, 0) + 1
    for retry_schedule in retry_schedules:
        retry_schedule_status = _safe_str(retry_schedule.get("status")).strip() or "unknown"
        retry_schedule_counts[retry_schedule_status] = retry_schedule_counts.get(retry_schedule_status, 0) + 1
    for item in items:
        status = _safe_str(item.get("status")).strip() or "unknown"
        status_counts[status] = status_counts.get(status, 0) + 1
        stable_state = _safe_str(item.get("stable_state")).strip() or "unknown"
        stable_state_counts[stable_state] = stable_state_counts.get(stable_state, 0) + 1
        raw_trigger = item.get("trigger")
        trigger = raw_trigger if isinstance(raw_trigger, dict) else {}
        source = _safe_str(trigger.get("source")).strip() or "unknown"
        source_counts[source] = source_counts.get(source, 0) + 1
        raw_dispatch = item.get("dispatch")
        dispatch = raw_dispatch if isinstance(raw_dispatch, dict) else {}
        raw_blocker = dispatch.get("blocker")
        blocker = raw_blocker if isinstance(raw_blocker, dict) else {}
        route = _safe_str(blocker.get("route")).strip()
        if route:
            blocker_route_counts[route] = blocker_route_counts.get(route, 0) + 1
        raw_approval_request = dispatch.get("approval_request") or item.get("latest_approval_request")
        approval_request = raw_approval_request if isinstance(raw_approval_request, dict) else {}
        approval_request_status = _safe_str(approval_request.get("status")).strip()
        if approval_request_status:
            approval_request_counts[approval_request_status] = (
                approval_request_counts.get(approval_request_status, 0) + 1
            )
        raw_approval_decision = dispatch.get("approval_decision") or item.get("latest_approval_decision")
        approval_decision = raw_approval_decision if isinstance(raw_approval_decision, dict) else {}
        approval_decision_status = _safe_str(approval_decision.get("status")).strip()
        if approval_decision_status:
            approval_decision_counts[approval_decision_status] = (
                approval_decision_counts.get(approval_decision_status, 0) + 1
            )
        raw_deadletter_candidate = dispatch.get("deadletter_candidate") or item.get("latest_deadletter_candidate")
        deadletter_candidate = raw_deadletter_candidate if isinstance(raw_deadletter_candidate, dict) else {}
        deadletter_status = _safe_str(deadletter_candidate.get("status")).strip()
        if deadletter_status:
            deadletter_candidate_counts[deadletter_status] = deadletter_candidate_counts.get(deadletter_status, 0) + 1
        raw_retry_candidate = dispatch.get("retry_candidate")
        retry_candidate = raw_retry_candidate if isinstance(raw_retry_candidate, dict) else {}
        retry_status = _safe_str(retry_candidate.get("status")).strip()
        if retry_status:
            retry_candidate_counts[retry_status] = retry_candidate_counts.get(retry_status, 0) + 1
        raw_retry_exhausted = dispatch.get("retry_exhausted") or item.get("latest_retry_exhausted")
        retry_exhausted = raw_retry_exhausted if isinstance(raw_retry_exhausted, dict) else {}
        retry_exhausted_status = _safe_str(retry_exhausted.get("status")).strip()
        if retry_exhausted_status:
            retry_exhausted_counts[retry_exhausted_status] = retry_exhausted_counts.get(retry_exhausted_status, 0) + 1
        raw_stable_return = item.get("latest_stable_return")
        stable_return = raw_stable_return if isinstance(raw_stable_return, dict) else {}
        stable_return_status = _safe_str(stable_return.get("status")).strip()
        if stable_return_status:
            stable_return_counts[stable_return_status] = stable_return_counts.get(stable_return_status, 0) + 1
        raw_verification = item.get("latest_verification_receipt")
        verification = raw_verification if isinstance(raw_verification, dict) else {}
        verification_status = _safe_str(verification.get("verification_status")).strip()
        if verification_status:
            verification_counts[verification_status] = verification_counts.get(verification_status, 0) + 1
        verification_outcome = _safe_str(verification.get("verification_outcome")).strip()
        if verification_outcome:
            verification_outcome_counts[verification_outcome] = (
                verification_outcome_counts.get(verification_outcome, 0) + 1
            )
    return {
        "ok": True,
        "status": "ready",
        "total": len(items),
        "status_counts": status_counts,
        "trigger_source_counts": source_counts,
        "stable_state_counts": stable_state_counts,
        "blocker_route_counts": blocker_route_counts,
        "approval_request_counts": approval_request_counts,
        "approval_decision_counts": approval_decision_counts,
        "deadletter_candidate_counts": deadletter_candidate_counts,
        "deadletter_queue_counts": deadletter_queue_counts,
        "deadletter_total": len(deadletters),
        "retry_candidate_counts": retry_candidate_counts,
        "retry_schedule_counts": retry_schedule_counts,
        "retry_schedule_total": len(retry_schedules),
        "retry_exhausted_counts": retry_exhausted_counts,
        "verification_counts": verification_counts,
        "verification_outcome_counts": verification_outcome_counts,
        "stable_return_counts": stable_return_counts,
        "dispatch_engine": "not_implemented",
        "valid_trigger_sources": sorted(VALID_TRIGGER_SOURCES),
        "governance": {
            "gate": "reactor_trigger_intake",
            "execution_authority": False,
            "approval_authority": False,
            "dispatch_authority": False,
        },
    }
