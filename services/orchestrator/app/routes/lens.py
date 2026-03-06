from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from francis_core.config import settings
from francis_core.workspace_fs import WorkspaceFS
from francis_forge.catalog import list_entries

from services.orchestrator.app.approvals_store import pending_count
from services.orchestrator.app.autonomy.action_budget import check_action_budget, load_state as load_budget_state
from services.orchestrator.app.autonomy.decision_engine import build_plan
from services.orchestrator.app.autonomy.event_queue import (
    queue_status as autonomy_queue_status,
    read_last_dispatch as read_autonomy_last_dispatch,
    read_reactor_guardrail_state as read_autonomy_reactor_guardrail_state,
    read_last_tick as read_autonomy_last_tick,
)
from services.orchestrator.app.autonomy.event_reactor import collect_events
from services.orchestrator.app.autonomy.intent_engine import collect_intents
from services.orchestrator.app.autonomy.trust_calibration import trust_badge
from services.orchestrator.app.control_state import check_action_allowed
from services.orchestrator.app.telemetry_store import status as telemetry_status

router = APIRouter(tags=["lens"])

_workspace_root = Path(settings.workspace_root).resolve()
_repo_root = _workspace_root.parent
_fs = WorkspaceFS(
    roots=[_workspace_root],
    journal_path=(_workspace_root / "journals" / "fs.jsonl").resolve(),
)


def _read_jsonl(rel_path: str) -> list[dict[str, Any]]:
    try:
        raw = _fs.read_text(rel_path)
    except Exception:
        return []
    rows: list[dict[str, Any]] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
            if isinstance(parsed, dict):
                rows.append(parsed)
        except Exception:
            continue
    return rows


def _mode_allows_medium_high(mode: str) -> tuple[bool, bool]:
    lowered = mode.lower()
    if lowered == "pilot":
        return (True, False)
    if lowered == "away":
        return (True, False)
    return (False, False)


@router.get("/lens/state")
def lens_state() -> dict:
    allowed, reason, control = check_action_allowed(
        _fs,
        repo_root=_repo_root,
        workspace_root=_workspace_root,
        app="lens",
        action="lens.state",
        mutating=False,
    )
    if not allowed:
        raise HTTPException(status_code=403, detail=f"Control denied: {reason}")

    event_state = collect_events(_fs)
    intent_state = collect_intents(_fs)
    telemetry = telemetry_status(_fs)
    autonomy_queue = autonomy_queue_status(_fs, limit=200)
    autonomy_last_dispatch = read_autonomy_last_dispatch(_fs)
    autonomy_last_tick = read_autonomy_last_tick(_fs)
    autonomy_guardrail = read_autonomy_reactor_guardrail_state(_fs)
    dispatch_verification = (
        autonomy_last_dispatch.get("verification", {})
        if isinstance(autonomy_last_dispatch.get("verification"), dict)
        else {}
    )
    tick_verification = (
        autonomy_last_tick.get("verification", {})
        if isinstance(autonomy_last_tick.get("verification"), dict)
        else {}
    )
    last_dispatch_config = (
        autonomy_last_dispatch.get("config", {}) if isinstance(autonomy_last_dispatch, dict) else {}
    )
    halted_reason = str(autonomy_last_dispatch.get("halted_reason", "")).strip()
    dispatch_halted = bool(halted_reason) and halted_reason != "completed"
    dispatch_budget_halt = halted_reason in {"dispatch_action_budget_exceeded", "dispatch_runtime_budget_exceeded"}
    dispatch_critical_halt = halted_reason in {"critical_incident_present", "critical_anomaly"}
    tick_dispatch = autonomy_last_tick.get("dispatch", {}) if isinstance(autonomy_last_tick, dict) else {}
    tick_collect = autonomy_last_tick.get("collect", {}) if isinstance(autonomy_last_tick, dict) else {}
    tick_halted_reason = str(tick_dispatch.get("halted_reason", "")).strip()
    tick_halted = bool(tick_halted_reason) and tick_halted_reason != "completed"
    guardrail_cooldown_active = int(autonomy_guardrail.get("cooldown_remaining_ticks", 0)) > 0
    manual_reset_available = str(control.get("mode", "observe")).strip().lower() == "pilot"
    autonomy_high_risk_due = sum(
        1
        for row in autonomy_queue.get("queued", [])
        if str(row.get("risk_tier", "")).strip().lower() in {"high", "critical"}
    )
    autonomy_leased_expired_count = int(autonomy_queue.get("leased_expired_count", 0))
    autonomy_retry_pressure = int(autonomy_queue.get("queued_retry_count", 0))
    catalog_entries = list_entries(_fs)
    staged_count = sum(1 for entry in catalog_entries if str(entry.get("status", "")).lower() == "staged")
    pending_approvals = pending_count(_fs) + len(_read_jsonl("queue/deadletter.jsonl")) + staged_count

    return {
        "status": "ok",
        "mode": control.get("mode"),
        "kill_switch": control.get("kill_switch"),
        "scope": control.get("scopes", {}),
        "intent_state": intent_state,
        "event_state": event_state,
        "telemetry": {
            "enabled": bool(telemetry.get("enabled", False)),
            "event_count_horizon": int(telemetry.get("event_count_horizon", 0)),
            "active_streams_horizon": list(telemetry.get("active_streams_horizon", [])),
            "last_event_ts": telemetry.get("last_event_ts"),
        },
        "autonomy_queue": {
            "queued_count": int(autonomy_queue.get("queued_count", 0)),
            "queued_retry_count": autonomy_retry_pressure,
            "leased_count": int(autonomy_queue.get("leased_count", 0)),
            "leased_expired_count": autonomy_leased_expired_count,
            "dispatched_count": int(autonomy_queue.get("dispatched_count", 0)),
            "failed_count": int(autonomy_queue.get("failed_count", 0)),
            "deadletter_count": int(autonomy_queue.get("deadletter_count", 0)),
            "high_risk_due_count": autonomy_high_risk_due,
        },
        "autonomy_dispatch": {
            "last_run_id": autonomy_last_dispatch.get("run_id"),
            "halted_reason": halted_reason or None,
            "halted": dispatch_halted,
            "processed_count": int(autonomy_last_dispatch.get("processed_count", 0)),
            "failed_count": int(autonomy_last_dispatch.get("failed_count", 0)),
            "retried_count": int(autonomy_last_dispatch.get("retried_count", 0)),
            "released_count": int(autonomy_last_dispatch.get("released_count", 0)),
            "dispatch_executed_actions": int(autonomy_last_dispatch.get("dispatch_executed_actions", 0)),
            "max_dispatch_actions": int(last_dispatch_config.get("max_dispatch_actions", 0)),
            "max_dispatch_runtime_seconds": int(last_dispatch_config.get("max_dispatch_runtime_seconds", 0)),
            "max_attempts": int(last_dispatch_config.get("max_attempts", 0)),
            "retry_backoff_seconds": int(last_dispatch_config.get("retry_backoff_seconds", 0)),
            "verification_status": dispatch_verification.get("verification_status"),
            "confidence": dispatch_verification.get("confidence"),
            "can_claim_done": bool(dispatch_verification.get("can_claim_done", False)),
            "claim": dispatch_verification.get("claim"),
            "completion_state": autonomy_last_dispatch.get("completion_state"),
            "trust_badge": trust_badge(
                confidence=str(dispatch_verification.get("confidence", "")),
                can_claim_done=bool(dispatch_verification.get("can_claim_done", False)),
            ),
        },
        "autonomy_reactor": {
            "last_run_id": autonomy_last_tick.get("run_id"),
            "last_ts": autonomy_last_tick.get("ts"),
            "halted": tick_halted,
            "halted_reason": tick_halted_reason or None,
            "collect_seen_count": int(tick_collect.get("seen_count", 0)),
            "collect_queued_count": int(tick_collect.get("queued_count", 0)),
            "dispatch_processed_count": int(tick_dispatch.get("processed_count", 0)),
            "dispatch_failed_count": int(tick_dispatch.get("failed_count", 0)),
            "dispatch_retried_count": int(tick_dispatch.get("retried_count", 0)),
            "dispatch_released_count": int(tick_dispatch.get("released_count", 0)),
            "verification_status": tick_verification.get("verification_status"),
            "confidence": tick_verification.get("confidence"),
            "can_claim_done": bool(tick_verification.get("can_claim_done", False)),
            "claim": tick_verification.get("claim"),
            "completion_state": autonomy_last_tick.get("completion_state"),
            "trust_badge": trust_badge(
                confidence=str(tick_verification.get("confidence", "")),
                can_claim_done=bool(tick_verification.get("can_claim_done", False)),
            ),
            "guardrail": {
                "tick_count": int(autonomy_guardrail.get("tick_count", 0)),
                "consecutive_retry_pressure_ticks": int(
                    autonomy_guardrail.get("consecutive_retry_pressure_ticks", 0)
                ),
                "cooldown_remaining_ticks": int(autonomy_guardrail.get("cooldown_remaining_ticks", 0)),
                "escalations_count": int(autonomy_guardrail.get("escalations_count", 0)),
                "last_retry_pressure_count": int(autonomy_guardrail.get("last_retry_pressure_count", 0)),
                "last_reason": autonomy_guardrail.get("last_reason"),
                "manual_reset_available": manual_reset_available,
                "updated_at": autonomy_guardrail.get("updated_at"),
            },
        },
        "pending_approvals": pending_approvals,
        "blockers": {
            "critical_incidents": event_state.get("critical_incident_count", 0),
            "deadletters": event_state.get("deadletter_count", 0),
            "worker_queue_due": event_state.get("worker_queue_due_count", 0),
            "worker_queue_backoff": event_state.get("worker_queue_backoff_count", 0),
            "worker_leased": event_state.get("worker_leased_count", 0),
            "worker_leased_expired": event_state.get("worker_leased_expired_count", 0),
            "worker_cycle_active": event_state.get("worker_cycle_active_count", 0),
            "worker_cycle_max": event_state.get("worker_cycle_max_concurrent", 1),
            "worker_cycle_gate_saturated": event_state.get("worker_cycle_gate_saturated", False),
            "worker_last_lease_lost": event_state.get("worker_last_lease_lost_count", 0),
            "worker_last_lease_conflict": event_state.get("worker_last_lease_conflict_count", 0),
            "autonomy_queue_due": int(autonomy_queue.get("queued_count", 0)),
            "autonomy_queue_high_risk_due": autonomy_high_risk_due,
            "autonomy_queue_retry_pressure": autonomy_retry_pressure,
            "autonomy_queue_leased_expired": autonomy_leased_expired_count,
            "autonomy_dispatch_halted": dispatch_halted,
            "autonomy_dispatch_halted_reason": halted_reason or None,
            "autonomy_dispatch_budget_halt": dispatch_budget_halt,
            "autonomy_dispatch_critical_halt": dispatch_critical_halt,
            "autonomy_dispatch_claim_confidence": dispatch_verification.get("confidence"),
            "autonomy_dispatch_can_claim_done": bool(dispatch_verification.get("can_claim_done", False)),
            "autonomy_reactor_halted": tick_halted,
            "autonomy_reactor_halted_reason": tick_halted_reason or None,
            "autonomy_reactor_cooldown_active": guardrail_cooldown_active,
            "autonomy_reactor_claim_confidence": tick_verification.get("confidence"),
            "autonomy_reactor_can_claim_done": bool(tick_verification.get("can_claim_done", False)),
            "pending_approvals": pending_approvals,
        },
    }


@router.get("/lens/actions")
def lens_actions(max_actions: int = 6) -> dict:
    allowed, reason, control = check_action_allowed(
        _fs,
        repo_root=_repo_root,
        workspace_root=_workspace_root,
        app="lens",
        action="lens.actions",
        mutating=False,
    )
    if not allowed:
        raise HTTPException(status_code=403, detail=f"Control denied: {reason}")

    event_state = collect_events(_fs)
    intent_state = collect_intents(_fs)
    autonomy_queue = autonomy_queue_status(_fs, limit=200)
    autonomy_last_dispatch = read_autonomy_last_dispatch(_fs)
    autonomy_last_tick = read_autonomy_last_tick(_fs)
    autonomy_guardrail = read_autonomy_reactor_guardrail_state(_fs)
    dispatch_halted_reason = str(autonomy_last_dispatch.get("halted_reason", "")).strip()
    dispatch_verification = (
        autonomy_last_dispatch.get("verification", {})
        if isinstance(autonomy_last_dispatch.get("verification"), dict)
        else {}
    )
    last_dispatch_config = (
        autonomy_last_dispatch.get("config", {}) if isinstance(autonomy_last_dispatch, dict) else {}
    )
    tick_dispatch = autonomy_last_tick.get("dispatch", {}) if isinstance(autonomy_last_tick, dict) else {}
    tick_verification = (
        autonomy_last_tick.get("verification", {})
        if isinstance(autonomy_last_tick.get("verification"), dict)
        else {}
    )
    tick_halted_reason = str(tick_dispatch.get("halted_reason", "")).strip()
    guardrail_cooldown_remaining = int(autonomy_guardrail.get("cooldown_remaining_ticks", 0))
    guardrail_cooldown_active = guardrail_cooldown_remaining > 0
    autonomy_queued_count = int(autonomy_queue.get("queued_count", 0))
    autonomy_retry_pressure = int(autonomy_queue.get("queued_retry_count", 0))
    autonomy_high_risk_due = sum(
        1
        for row in autonomy_queue.get("queued", [])
        if str(row.get("risk_tier", "")).strip().lower() in {"high", "critical"}
    )
    autonomy_leased_expired_count = int(autonomy_queue.get("leased_expired_count", 0))
    allow_medium, allow_high = _mode_allows_medium_high(str(control.get("mode", "observe")))
    plan = build_plan(
        event_state=event_state,
        intent_state=intent_state,
        max_actions=max_actions,
        allow_medium=allow_medium,
        allow_high=allow_high,
    )
    budget_state = load_budget_state(_fs)
    gated_candidates: list[dict[str, Any]] = []
    for candidate in plan.get("candidate_actions", []):
        if not bool(candidate.get("allowed", False)):
            gated_candidates.append({**candidate})
            continue
        allowed_by_budget, reason, action_key = check_action_budget(candidate, state=budget_state)
        if allowed_by_budget:
            gated_candidates.append({**candidate})
        else:
            gated_candidates.append(
                {
                    **candidate,
                    "allowed": False,
                    "policy_reason": reason,
                    "blocked_by": "action_budget",
                    "action_key": action_key,
                }
            )

    selected_actions = [item for item in gated_candidates if bool(item.get("allowed"))][: max(0, max_actions)]
    blocked_actions = [item for item in gated_candidates if not bool(item.get("allowed"))]

    action_chips = []
    for action in gated_candidates:
        kind = str(action.get("kind", ""))
        label = {
            "observer.scan": "Run Observer Scan",
            "worker.cycle": "Process Worker Queue",
            "worker.recover_leases": "Recover Stale Leases",
            "mission.tick": "Advance Mission",
            "forge.propose": "Generate Forge Proposals",
        }.get(kind, kind)
        chip = {
            "kind": kind,
            "label": label,
            "enabled": bool(action.get("allowed")),
            "reason": action.get("reason", ""),
            "policy_reason": action.get("policy_reason", ""),
            "risk_tier": action.get("risk_tier", "low"),
            "trust_badge": "Likely" if bool(action.get("allowed")) else "Uncertain",
        }
        if kind == "worker.cycle":
            chip["lease_telemetry"] = {
                "renewed_last_cycle": event_state.get("worker_last_lease_renewed_count", 0),
                "lost_last_cycle": event_state.get("worker_last_lease_lost_count", 0),
                "conflicts_last_cycle": event_state.get("worker_last_lease_conflict_count", 0),
                "recovered_last_cycle": event_state.get("worker_last_recovered_count", 0),
                "gate_saturated": event_state.get("worker_cycle_gate_saturated", False),
                "active_cycles": event_state.get("worker_cycle_active_count", 0),
                "max_concurrent_cycles": event_state.get("worker_cycle_max_concurrent", 1),
            }
        if kind == "worker.recover_leases":
            chip["recovery_scope"] = action.get("action_classes", [])
        action_chips.append(chip)

    if autonomy_queued_count > 0:
        mode = str(control.get("mode", "observe")).strip().lower()
        dispatch_enabled = mode in {"pilot", "away"}
        policy_reason = ""
        if not dispatch_enabled:
            policy_reason = f"mutating action autonomy.dispatch not allowed in {mode} mode"
        elif autonomy_high_risk_due > 0:
            policy_reason = "approval required for queued high-risk autonomy events"
        action_chips.append(
            {
                "kind": "autonomy.dispatch",
                "label": "Dispatch Autonomy Events",
                "enabled": dispatch_enabled,
                "reason": f"{autonomy_queued_count} queued autonomy event(s)",
                "policy_reason": policy_reason,
                "risk_tier": "medium" if autonomy_high_risk_due == 0 else "high",
                "trust_badge": trust_badge(
                    confidence=str(dispatch_verification.get("confidence", "")),
                    can_claim_done=bool(dispatch_verification.get("can_claim_done", False)),
                ),
                "queue_telemetry": {
                    "queued_count": autonomy_queued_count,
                    "high_risk_due_count": autonomy_high_risk_due,
                    "last_halted_reason": dispatch_halted_reason or None,
                    "last_max_dispatch_actions": int(last_dispatch_config.get("max_dispatch_actions", 0)),
                    "last_max_dispatch_runtime_seconds": int(last_dispatch_config.get("max_dispatch_runtime_seconds", 0)),
                    "last_verification_status": dispatch_verification.get("verification_status"),
                    "last_confidence": dispatch_verification.get("confidence"),
                    "last_can_claim_done": bool(dispatch_verification.get("can_claim_done", False)),
                    "last_completion_state": autonomy_last_dispatch.get("completion_state"),
                },
            }
        )
    if autonomy_leased_expired_count > 0:
        mode = str(control.get("mode", "observe")).strip().lower()
        recover_enabled = mode in {"pilot", "away"}
        recover_policy_reason = ""
        if not recover_enabled:
            recover_policy_reason = f"mutating action autonomy.recover not allowed in {mode} mode"
        action_chips.append(
            {
                "kind": "autonomy.recover",
                "label": "Recover Stale Autonomy Leases",
                "enabled": recover_enabled,
                "reason": f"{autonomy_leased_expired_count} stale leased autonomy event(s)",
                "policy_reason": recover_policy_reason,
                "risk_tier": "low",
                "trust_badge": "Likely" if recover_enabled else "Uncertain",
                "queue_telemetry": {
                    "leased_expired_count": autonomy_leased_expired_count,
                },
            }
        )
    if tick_halted_reason or autonomy_retry_pressure > 0 or guardrail_cooldown_active:
        mode = str(control.get("mode", "observe")).strip().lower()
        tick_enabled = mode in {"pilot", "away"}
        tick_policy_reason = ""
        if not tick_enabled:
            tick_policy_reason = f"mutating action autonomy.reactor.tick not allowed in {mode} mode"
        elif guardrail_cooldown_active:
            tick_policy_reason = (
                "guardrail cooldown active; dispatch will remain suppressed until cooldown clears"
            )
        risk_tier = "high" if tick_halted_reason in {"critical_incident_present", "critical_anomaly"} else "medium"
        reason_parts: list[str] = []
        if tick_halted_reason:
            reason_parts.append(f"last tick halted: {tick_halted_reason}")
        if autonomy_retry_pressure > 0:
            reason_parts.append(f"{autonomy_retry_pressure} queued retry event(s)")
        if guardrail_cooldown_active:
            reason_parts.append(f"cooldown active ({guardrail_cooldown_remaining} tick(s) remaining)")
        action_chips.append(
            {
                "kind": "autonomy.reactor.tick",
                "label": "Run Reactor Tick",
                "enabled": tick_enabled,
                "reason": "; ".join(reason_parts) if reason_parts else "reactor health check",
                "policy_reason": tick_policy_reason,
                "risk_tier": risk_tier,
                "trust_badge": trust_badge(
                    confidence=str(tick_verification.get("confidence", "")),
                    can_claim_done=bool(tick_verification.get("can_claim_done", False)),
                ),
                "queue_telemetry": {
                    "queued_retry_count": autonomy_retry_pressure,
                    "last_tick_halted_reason": tick_halted_reason or None,
                    "guardrail_cooldown_active": guardrail_cooldown_active,
                    "guardrail_cooldown_remaining_ticks": guardrail_cooldown_remaining,
                    "guardrail_escalations_count": int(autonomy_guardrail.get("escalations_count", 0)),
                    "last_tick_verification_status": tick_verification.get("verification_status"),
                    "last_tick_confidence": tick_verification.get("confidence"),
                    "last_tick_can_claim_done": bool(tick_verification.get("can_claim_done", False)),
                    "last_tick_completion_state": autonomy_last_tick.get("completion_state"),
                    "last_tick_processed_count": int(tick_dispatch.get("processed_count", 0)),
                    "last_tick_failed_count": int(tick_dispatch.get("failed_count", 0)),
                    "last_tick_retried_count": int(tick_dispatch.get("retried_count", 0)),
                    "last_tick_released_count": int(tick_dispatch.get("released_count", 0)),
                },
            }
        )
    if guardrail_cooldown_active:
        mode = str(control.get("mode", "observe")).strip().lower()
        reset_enabled = mode == "pilot"
        reset_policy_reason = ""
        if not reset_enabled:
            reset_policy_reason = "manual guardrail reset requires pilot mode"
        action_chips.append(
            {
                "kind": "autonomy.reactor.guardrail.reset",
                "label": "Reset Reactor Cooldown",
                "enabled": reset_enabled,
                "reason": f"cooldown active ({guardrail_cooldown_remaining} tick(s) remaining)",
                "policy_reason": reset_policy_reason,
                "risk_tier": "low",
                "trust_badge": "Likely" if reset_enabled else "Uncertain",
                "queue_telemetry": {
                    "guardrail_cooldown_active": guardrail_cooldown_active,
                    "guardrail_cooldown_remaining_ticks": guardrail_cooldown_remaining,
                    "guardrail_escalations_count": int(autonomy_guardrail.get("escalations_count", 0)),
                },
            }
        )

    return {
        "status": "ok",
        "mode": control.get("mode"),
        "action_chips": action_chips,
        "selected_actions": selected_actions,
        "blocked_actions": blocked_actions,
    }
