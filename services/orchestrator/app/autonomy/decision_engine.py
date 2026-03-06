from __future__ import annotations

from typing import Any


def _risk_allowed(risk_tier: str, *, allow_medium: bool, allow_high: bool) -> tuple[bool, str]:
    risk = risk_tier.lower()
    if risk == "low":
        return (True, "allowed")
    if risk == "medium":
        return (allow_medium, "medium risk disabled" if not allow_medium else "allowed")
    if risk in {"high", "critical"}:
        return (allow_high, "high risk disabled" if not allow_high else "allowed")
    return (False, "unknown risk tier")


def build_plan(
    *,
    event_state: dict[str, Any],
    intent_state: dict[str, Any],
    max_actions: int,
    allow_medium: bool,
    allow_high: bool,
) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    telemetry_error_count = int(event_state.get("telemetry_error_count_horizon", 0))
    telemetry_critical_count = int(event_state.get("telemetry_critical_count_horizon", 0))

    scan_reasons: list[str] = []
    if event_state.get("observer_scan_due"):
        scan_reasons.append("observer scan interval elapsed")
    if event_state.get("critical_incident_count", 0) > 0:
        scan_reasons.append("critical incident exists")
    if telemetry_error_count > 0 or telemetry_critical_count > 0:
        scan_reasons.append(
            f"{telemetry_error_count} telemetry error(s) and {telemetry_critical_count} telemetry critical(s) detected"
        )
    if scan_reasons:
        candidates.append(
            {
                "kind": "observer.scan",
                "risk_tier": "low",
                "reason": "Observer scan requested because " + "; ".join(scan_reasons) + ".",
            }
        )

    worker_queue_due = int(event_state.get("worker_queue_due_count", 0))
    worker_leased_expired = int(event_state.get("worker_leased_expired_count", 0))
    if worker_leased_expired > 0:
        expired_classes = event_state.get("worker_leased_expired_classes_top", [])
        action_classes = [
            str(item.get("key", "")).strip().lower()
            for item in expired_classes
            if isinstance(item, dict) and str(item.get("key", "")).strip()
        ][:3]
        candidates.append(
            {
                "kind": "worker.recover_leases",
                "risk_tier": "low",
                "action_classes": action_classes,
                "reason": f"{worker_leased_expired} expired lease(s) queued for recovery.",
            }
        )

    if worker_queue_due > 0 or worker_leased_expired > 0:
        due_actions = event_state.get("worker_due_actions_top", [])
        action_allowlist = [
            str(item.get("key", "")).strip().lower()
            for item in due_actions
            if isinstance(item, dict) and str(item.get("key", "")).strip()
        ][:3]
        max_concurrent_cycles = max(1, int(event_state.get("worker_cycle_max_concurrent", 1)))
        max_jobs = min(20, max(worker_queue_due, worker_leased_expired, 1))
        if worker_queue_due > 0 and worker_leased_expired > 0:
            reason = (
                f"{worker_queue_due} due worker queue job(s) pending and "
                f"{worker_leased_expired} expired lease(s) detected."
            )
        elif worker_queue_due > 0:
            reason = f"{worker_queue_due} due worker queue job(s) pending."
        else:
            reason = f"{worker_leased_expired} expired worker lease(s) detected."
        candidates.append(
            {
                "kind": "worker.cycle",
                "risk_tier": "medium",
                "max_jobs": max_jobs,
                "max_runtime_seconds": 30,
                "max_concurrent_cycles": max_concurrent_cycles,
                "action_allowlist": action_allowlist,
                "reason": reason,
            }
        )

    queued_ids = event_state.get("queued_mission_ids", [])
    if queued_ids:
        candidates.append(
            {
                "kind": "mission.tick",
                "risk_tier": "medium",
                "mission_id": queued_ids[0],
                "reason": f"{len(queued_ids)} mission job(s) queued.",
            }
        )
    elif intent_state.get("intent_count", 0) > 0:
        first_intent = (intent_state.get("intents") or [{}])[0]
        mission_id = first_intent.get("mission_id")
        if mission_id:
            candidates.append(
                {
                    "kind": "mission.tick",
                    "risk_tier": "medium",
                    "mission_id": mission_id,
                    "reason": "Active mission exists without queued job.",
                }
            )

    if event_state.get("deadletter_count", 0) > 0:
        candidates.append(
            {
                "kind": "forge.propose",
                "risk_tier": "low",
                "context": {
                    "deadletter_count": event_state.get("deadletter_count", 0),
                    "open_incident_count": event_state.get("open_incident_count", 0),
                    "active_mission_count": event_state.get("active_mission_count", 0),
                },
                "reason": "Deadletter jobs detected.",
            }
        )
    elif telemetry_error_count >= 3:
        candidates.append(
            {
                "kind": "forge.propose",
                "risk_tier": "low",
                "context": {
                    "telemetry_error_count": telemetry_error_count,
                    "telemetry_critical_count": telemetry_critical_count,
                    "telemetry_streams_top": event_state.get("telemetry_streams_top", []),
                    "active_mission_count": event_state.get("active_mission_count", 0),
                },
                "reason": f"Telemetry friction detected ({telemetry_error_count} errors in horizon).",
            }
        )

    gated: list[dict[str, Any]] = []
    for candidate in candidates:
        allowed, policy_reason = _risk_allowed(
            str(candidate.get("risk_tier", "low")),
            allow_medium=allow_medium,
            allow_high=allow_high,
        )
        gated.append({**candidate, "allowed": allowed, "policy_reason": policy_reason})

    actions = [candidate for candidate in gated if candidate.get("allowed")][: max(0, max_actions)]
    blocked = [candidate for candidate in gated if not candidate.get("allowed")]

    return {
        "candidate_actions": gated,
        "selected_actions": actions,
        "blocked_actions": blocked,
    }
