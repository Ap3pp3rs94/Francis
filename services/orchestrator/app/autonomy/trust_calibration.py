from __future__ import annotations

from typing import Any


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _normalized_halted_reason(value: object) -> str:
    reason = str(value or "").strip().lower()
    return reason or "completed"


def _count_cycle_executed(cycle: dict[str, Any]) -> int:
    executed = cycle.get("executed_actions", [])
    if isinstance(executed, list):
        return len(executed)
    return _safe_int(cycle.get("executed_count"), 0)


def _count_cycle_blocked(cycle: dict[str, Any]) -> int:
    blocked = cycle.get("blocked_actions", [])
    if isinstance(blocked, list):
        return len(blocked)
    return _safe_int(cycle.get("blocked_count"), 0)


def trust_badge(*, confidence: str | None, can_claim_done: bool | None = None) -> str:
    normalized = str(confidence or "").strip().lower()
    if normalized == "confirmed" and bool(can_claim_done):
        return "Confirmed"
    if normalized == "likely":
        return "Likely"
    if normalized == "confirmed":
        return "Likely"
    return "Uncertain"


def completion_state(verification: dict[str, Any] | None) -> str:
    row = verification if isinstance(verification, dict) else {}
    status = str(row.get("verification_status", "")).strip().lower()
    can_claim_done = bool(row.get("can_claim_done"))
    if status == "verified" and can_claim_done:
        return "done"
    return "incomplete"


def calibrate_cycle_result(cycle: dict[str, Any]) -> dict[str, Any]:
    halted_reason = _normalized_halted_reason(cycle.get("halted_reason"))
    executed_count = _count_cycle_executed(cycle)
    blocked_count = _count_cycle_blocked(cycle)
    event_state = cycle.get("event_state", {})
    critical_incident_count = (
        _safe_int(event_state.get("critical_incident_count"), 0)
        if isinstance(event_state, dict)
        else 0
    )

    verification_status = "uncertain"
    confidence = "uncertain"
    can_claim_done = False
    claim = "cycle_uncertain"

    if halted_reason == "critical_anomaly" or critical_incident_count > 0:
        verification_status = "blocked"
        confidence = "uncertain"
        claim = "blocked_by_critical_anomaly"
    elif halted_reason == "runtime_budget_exceeded":
        verification_status = "partial"
        confidence = "likely"
        claim = "runtime_budget_exceeded"
    elif halted_reason != "completed":
        verification_status = "partial"
        confidence = "likely"
        claim = "halted_before_completion"
    elif executed_count > 0 and blocked_count == 0:
        verification_status = "verified"
        confidence = "confirmed"
        can_claim_done = True
        claim = "cycle_completed"
    elif executed_count > 0:
        verification_status = "partial"
        confidence = "likely"
        claim = "cycle_partial_with_blockers"
    elif blocked_count > 0:
        verification_status = "partial"
        confidence = "likely"
        claim = "cycle_blocked"
    else:
        verification_status = "verified"
        confidence = "confirmed"
        can_claim_done = True
        claim = "no_action_required"

    return {
        "verification_status": verification_status,
        "confidence": confidence,
        "can_claim_done": can_claim_done,
        "claim": claim,
        "evidence": {
            "halted_reason": halted_reason,
            "executed_count": executed_count,
            "blocked_count": blocked_count,
            "critical_incident_count": critical_incident_count,
        },
    }


def calibrate_dispatch_result(
    *,
    halted_reason: str,
    processed_count: int,
    failed_count: int,
    retried_count: int,
    released_count: int,
    due_preview_count: int,
    critical_incident_count: int,
    processed: list[dict[str, Any]],
) -> dict[str, Any]:
    normalized_halt = _normalized_halted_reason(halted_reason)
    processed_cycle_verifications = [
        item.get("verification", {})
        for item in processed
        if isinstance(item, dict) and isinstance(item.get("verification"), dict)
    ]
    verified_cycle_count = sum(
        1
        for item in processed_cycle_verifications
        if str(item.get("verification_status", "")).strip().lower() == "verified"
        and bool(item.get("can_claim_done"))
    )

    verification_status = "uncertain"
    confidence = "uncertain"
    can_claim_done = False
    claim = "dispatch_uncertain"

    if critical_incident_count > 0 or normalized_halt in {"critical_incident_present", "critical_anomaly"}:
        verification_status = "blocked"
        confidence = "uncertain"
        claim = "blocked_by_critical_incident"
    elif failed_count > 0:
        verification_status = "failed"
        confidence = "uncertain"
        claim = "dispatch_failed"
    elif (
        processed_count > 0
        and verified_cycle_count == processed_count
        and retried_count == 0
        and released_count == 0
        and normalized_halt == "completed"
    ):
        verification_status = "verified"
        confidence = "confirmed"
        can_claim_done = True
        claim = "dispatch_completed"
    elif due_preview_count == 0 and processed_count == 0 and normalized_halt == "completed":
        verification_status = "verified"
        confidence = "confirmed"
        can_claim_done = True
        claim = "no_due_events"
    elif processed_count > 0 or retried_count > 0 or released_count > 0:
        verification_status = "partial"
        confidence = "likely"
        claim = "dispatch_partial"
    elif normalized_halt in {"dispatch_action_budget_exceeded", "dispatch_runtime_budget_exceeded"}:
        verification_status = "partial"
        confidence = "likely"
        claim = "dispatch_budget_halted"

    return {
        "verification_status": verification_status,
        "confidence": confidence,
        "can_claim_done": can_claim_done,
        "claim": claim,
        "evidence": {
            "halted_reason": normalized_halt,
            "processed_count": _safe_int(processed_count, 0),
            "verified_cycle_count": verified_cycle_count,
            "failed_count": _safe_int(failed_count, 0),
            "retried_count": _safe_int(retried_count, 0),
            "released_count": _safe_int(released_count, 0),
            "due_preview_count": _safe_int(due_preview_count, 0),
            "critical_incident_count": _safe_int(critical_incident_count, 0),
        },
    }


def calibrate_reactor_tick(
    *,
    collect_result: dict[str, Any],
    dispatch_result: dict[str, Any],
    guardrail_receipt: dict[str, Any],
) -> dict[str, Any]:
    dispatch_verification = (
        dispatch_result.get("verification", {})
        if isinstance(dispatch_result.get("verification"), dict)
        else {}
    )
    dispatch_status = str(dispatch_verification.get("verification_status", "")).strip().lower()
    dispatch_confidence = str(dispatch_verification.get("confidence", "")).strip().lower()
    dispatch_can_claim_done = bool(dispatch_verification.get("can_claim_done"))
    cooldown_active = bool(guardrail_receipt.get("cooldown_active"))
    collect_seen = _safe_int(collect_result.get("seen_count", 0), 0)
    collect_queued = _safe_int(collect_result.get("queued_count", 0), 0)
    collect_duplicates = _safe_int(collect_result.get("duplicate_count", 0), 0)

    verification_status = "uncertain"
    confidence = "uncertain"
    can_claim_done = False
    claim = "reactor_uncertain"

    if cooldown_active:
        verification_status = "partial"
        confidence = "likely"
        claim = "reactor_cooldown_active"
    elif dispatch_status in {"blocked", "failed"}:
        verification_status = dispatch_status
        confidence = "uncertain"
        claim = "reactor_dispatch_blocked"
    elif dispatch_status == "verified" and dispatch_can_claim_done:
        verification_status = "verified"
        confidence = "confirmed"
        can_claim_done = True
        claim = "reactor_tick_completed"
    elif dispatch_status == "partial":
        verification_status = "partial"
        confidence = "likely"
        claim = "reactor_tick_partial"
    elif collect_seen == 0 and collect_queued == 0:
        verification_status = "verified"
        confidence = "confirmed"
        can_claim_done = True
        claim = "reactor_idle"
    elif dispatch_confidence in {"confirmed", "likely"}:
        verification_status = "partial"
        confidence = dispatch_confidence
        claim = "reactor_inferred_from_dispatch"

    return {
        "verification_status": verification_status,
        "confidence": confidence,
        "can_claim_done": can_claim_done,
        "claim": claim,
        "evidence": {
            "collect_seen_count": collect_seen,
            "collect_queued_count": collect_queued,
            "collect_duplicate_count": collect_duplicates,
            "dispatch_verification_status": dispatch_status or None,
            "dispatch_confidence": dispatch_confidence or None,
            "dispatch_can_claim_done": dispatch_can_claim_done,
            "guardrail_cooldown_active": cooldown_active,
        },
    }
