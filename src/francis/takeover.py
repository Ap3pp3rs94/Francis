from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

from francis.agent import delegation as delegation_store
from francis.executor_substrate import stage8_operator_stage_closure_decision_readback
from francis.governance.redaction import redact_secret_text
from francis.kernel.paths import data_dir
from francis.operations.runtime import create_operation, get_operation_detail, run_operation
from francis.telemetry.audit import record as audit_record
from francis.world_state.operator_mode import set_control_mode, snapshot as operator_mode_snapshot

STAGE9_TAKEOVER_STAGE = "Stage 9 / Takeover (Pilot Mode)"
TAKEOVER_STATUS_KIND = "francis.stage9.takeover.status"
TAKEOVER_ACTION_FEED_KIND = "francis.stage9.takeover.action_feed"
TAKEOVER_CONTROL_TRANSFER_RECEIPT_KIND = "francis.stage9.takeover.control_transfer_receipt"
TAKEOVER_PANIC_STOP_RECEIPT_KIND = "francis.stage9.takeover.panic_stop_receipt"
TAKEOVER_HANDBACK_SUMMARY_RECEIPT_KIND = "francis.stage9.takeover.handback_summary_receipt"
TAKEOVER_LIVE_ACTION_RECEIPT_KIND = "francis.stage9.takeover.live_action_receipt"

TAKEOVER_CONTROL_TRANSFER_SCOPE = "takeover.control.write"
TAKEOVER_PANIC_STOP_SCOPE = "takeover.panic.write"
TAKEOVER_HANDBACK_SUMMARY_SCOPE = "takeover.handback.write"
TAKEOVER_LIVE_ACTION_SCOPE = "takeover.action.write"

_ALLOWED_ENV_PROFILES = {"dev", "workstation", "local", "test"}
_ALLOWED_TAKEOVER_LIVE_ACTIONS = {"plan.create"}


def takeover_status_snapshot(*, limit: int = 10) -> dict[str, Any]:
    safe_limit = _safe_limit(limit, default=10)
    stage8 = stage8_operator_stage_closure_decision_readback(limit=5)
    operator = operator_mode_snapshot()
    control_mode = _as_dict(operator.get("control_mode"))
    action_feed = takeover_action_feed(limit=safe_limit)
    transfers = read_takeover_control_transfer_receipts(limit=10)
    panic_receipts = read_takeover_panic_stop_receipts(limit=10)
    handback_receipts = read_takeover_handback_summary_receipts(limit=10)
    live_action_receipts = read_takeover_live_action_receipts(limit=10)
    active_transfer = _active_control_transfer(
        transfers=transfers,
        panic_receipts=panic_receipts,
        handback_receipts=handback_receipts,
    )
    stage8_closed = bool(stage8.get("stage8_closed_by_receipt"))
    pilot_visible = _safe_text(control_mode.get("id")) == "pilot"
    control_transfer_ready = stage8_closed and not bool(active_transfer)
    handback_ready = bool(handback_receipts)
    panic_operation_cancellation_ready = _panic_operation_cancellation_ready(panic_receipts)
    live_action_ready = bool(live_action_receipts)
    snapshot = {
        "ok": True,
        "kind": TAKEOVER_STATUS_KIND,
        "stage": STAGE9_TAKEOVER_STAGE,
        "source_id": "takeover",
        "status": "pilot_active" if active_transfer else "ready" if control_transfer_ready else "blocked",
        "stage8_closed_by_receipt": stage8_closed,
        "stage8_latest_receipt_id": _safe_text(stage8.get("latest_receipt_id")),
        "control_mode": control_mode,
        "pilot_indicator_visible": pilot_visible,
        "control_transfer_ready": control_transfer_ready,
        "control_transfer_active": bool(active_transfer),
        "active_session_id": _safe_text(active_transfer.get("session_id")) if active_transfer else "",
        "latest_control_transfer_receipt": transfers[-1] if transfers else {},
        "latest_panic_stop_receipt": panic_receipts[-1] if panic_receipts else {},
        "latest_handback_summary_receipt": handback_receipts[-1] if handback_receipts else {},
        "latest_live_action_receipt": live_action_receipts[-1] if live_action_receipts else {},
        "panic_stop_ready": bool(active_transfer),
        "handback_required": bool(active_transfer),
        "handback_summary_ready": handback_ready,
        "live_delegated_action_ready": live_action_ready,
        "action_feed": action_feed,
        "deliverables": {
            "control_transfer_flow": bool(transfers),
            "live_action_feed": True,
            "panic_stop": bool(panic_receipts),
            "handback_summary": handback_ready,
            "pilot_visibility": pilot_visible or bool(transfers),
            "live_delegated_action_runtime": live_action_ready,
        },
        "reads_receipts": True,
        "writes_receipts": False,
        "writes_tasks": False,
        "writes_memory": False,
        "runs_tools": False,
        "runs_shell": False,
        "runs_git": False,
        "starts_processes": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "governance": {
            "read_only": True,
            "requires_stage8_closure_receipt": True,
            "takeover_never_implicit": True,
            "panic_revocation_surface": "/takeover/panic-stop",
            "execution_still_uses_executor_governance": True,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
        "operator_surface_contract_route": "/takeover/operator-surface-contract",
        "operator_surface_contract_ready": False,
        "next_smallest_truthful_gap": _takeover_next_gap(
            active_transfer=bool(active_transfer),
            has_transfer=bool(transfers),
            handback_ready=handback_ready,
            stage8_closed=stage8_closed,
            operator_surface_ready=False,
            panic_operation_cancellation_ready=panic_operation_cancellation_ready,
            live_action_ready=live_action_ready,
        ),
    }
    surface_ready = _operator_surface_contract_ready(snapshot)
    snapshot["operator_surface_contract_ready"] = surface_ready
    snapshot["next_smallest_truthful_gap"] = _takeover_next_gap(
        active_transfer=bool(active_transfer),
        has_transfer=bool(transfers),
        handback_ready=handback_ready,
        stage8_closed=stage8_closed,
        operator_surface_ready=surface_ready,
        panic_operation_cancellation_ready=panic_operation_cancellation_ready,
        live_action_ready=live_action_ready,
    )
    return snapshot


def takeover_operator_surface_contract(*, limit: int = 10) -> dict[str, Any]:
    snapshot = takeover_status_snapshot(limit=limit)
    checks = _operator_surface_contract_checks(snapshot)
    ready = all(bool(check.get("passed")) for check in checks)
    return {
        "ok": True,
        "kind": "francis.stage9.takeover.operator_surface_contract",
        "stage": STAGE9_TAKEOVER_STAGE,
        "source_id": "takeover",
        "status": "ready" if ready else "blocked",
        "operator_surface_contract_ready": ready,
        "checks": checks,
        "routes": {
            "status": "/takeover/status",
            "action_feed": "/takeover/action-feed",
            "delegated_action_receipts": "/takeover/delegated-action-receipts",
            "control_transfer_receipts": "/takeover/control-transfer-receipts",
            "panic_stop_receipts": "/takeover/panic-stop-receipts",
            "handback_summaries": "/takeover/handback-summaries",
            "delegated_action": "/takeover/delegated-action",
            "control_transfer": "/takeover/control-transfer",
            "panic_stop": "/takeover/panic-stop",
            "handback_summary": "/takeover/handback-summary",
        },
        "latest_control_transfer_receipt_id": _safe_text(
            _as_dict(snapshot.get("latest_control_transfer_receipt")).get("receipt_id")
        ),
        "latest_panic_stop_receipt_id": _safe_text(
            _as_dict(snapshot.get("latest_panic_stop_receipt")).get("receipt_id")
        ),
        "latest_handback_summary_receipt_id": _safe_text(
            _as_dict(snapshot.get("latest_handback_summary_receipt")).get("receipt_id")
        ),
        "latest_live_action_receipt_id": _safe_text(
            _as_dict(snapshot.get("latest_live_action_receipt")).get("receipt_id")
        ),
        "reads_receipts": True,
        "writes_receipts": False,
        "writes_tasks": False,
        "writes_memory": False,
        "runs_tools": False,
        "runs_shell": False,
        "runs_git": False,
        "starts_processes": False,
        "cancels_operations": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "governance": {
            "read_only": True,
            "surface_contract_only": True,
            "execution_still_uses_executor_governance": True,
            "does_not_run_tools": True,
            "does_not_run_shell": True,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
        "next_smallest_truthful_gap": "stage9_panic_operation_cancellation"
        if ready and not _panic_operation_cancellation_ready(read_takeover_panic_stop_receipts(limit=10))
        else "stage9_live_delegated_action_runtime"
        if ready and not bool(read_takeover_live_action_receipts(limit=10))
        else "stage9_completion_review"
        if ready
        else "stage9_operator_surface_contract",
    }


def takeover_action_feed(*, limit: int = 10) -> dict[str, Any]:
    safe_limit = _safe_limit(limit, default=10)
    items: list[dict[str, Any]] = []
    try:
        task_ids = delegation_store.list_tasks(limit=max(safe_limit, 50))
    except Exception:
        task_ids = []
    for task_id in task_ids:
        detail = get_operation_detail(str(task_id), include_logs=False, log_limit=0)
        if not isinstance(detail, dict) or not detail.get("ok"):
            continue
        operation = _as_dict(detail.get("operation"))
        if not operation:
            continue
        items.append(_action_feed_item(operation))
    items.sort(key=lambda item: (_safe_int(item.get("ts"), 0), _safe_text(item.get("id"))), reverse=True)
    return {
        "ok": True,
        "kind": TAKEOVER_ACTION_FEED_KIND,
        "stage": STAGE9_TAKEOVER_STAGE,
        "source_id": "takeover",
        "status": "ready",
        "items": items[:safe_limit],
        "count": min(len(items), safe_limit),
        "limit": safe_limit,
        "reads_operations": True,
        "writes_receipts": False,
        "writes_tasks": False,
        "writes_memory": False,
        "runs_tools": False,
        "runs_shell": False,
        "runs_git": False,
        "starts_processes": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "governance": {
            "read_only": True,
            "bounded_recent_operations": True,
            "execution_still_uses_executor_governance": True,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
        "next_smallest_truthful_gap": "stage9_control_transfer_receipts",
    }


def record_takeover_control_transfer(
    *,
    actor: Any,
    reason: Any,
    scope: Any,
    mission_id: Any = "",
    operation_limit: int = 10,
) -> dict[str, Any]:
    env_profile = _env_profile()
    if env_profile not in _ALLOWED_ENV_PROFILES:
        return _blocked_no_receipt(
            status="blocked_environment_profile",
            reason="takeover_control_transfer_dev_or_workstation_only",
            required_scope=TAKEOVER_CONTROL_TRANSFER_SCOPE,
        )

    status = takeover_status_snapshot(limit=operation_limit)
    if not bool(status.get("stage8_closed_by_receipt")):
        return _blocked_no_receipt(
            status="awaiting_stage8_closure_receipt",
            reason="stage8_closure_receipt_required_before_takeover",
            required_scope=TAKEOVER_CONTROL_TRANSFER_SCOPE,
            next_gap="stage8_ledger_closure",
        )

    session_id = f"pilot_{uuid.uuid4().hex[:12]}"
    receipt_id = f"takeover_transfer_{uuid.uuid4().hex[:12]}"
    now = _now_s()
    safe_actor = _redacted_text(actor)[:240]
    safe_reason = _redacted_text(reason)[:500]
    safe_scope = _redacted_text(scope)[:500]
    safe_mission_id = _redacted_text(mission_id)[:160]

    set_control_mode(
        "pilot",
        reason=safe_reason or "stage9_takeover_control_transfer",
        actor=safe_actor,
        meta={
            "takeover_session_id": session_id,
            "takeover_receipt_id": receipt_id,
            "scope": safe_scope,
            "mission_id": safe_mission_id,
        },
    )
    action_feed = takeover_action_feed(limit=operation_limit)
    receipt = {
        "ok": True,
        "kind": TAKEOVER_CONTROL_TRANSFER_RECEIPT_KIND,
        "receipt_id": receipt_id,
        "session_id": session_id,
        "stage": STAGE9_TAKEOVER_STAGE,
        "source_id": "takeover",
        "target": "pilot_mode",
        "actor": safe_actor,
        "reason": safe_reason,
        "scope": safe_scope,
        "mission_id": safe_mission_id,
        "env_profile": env_profile,
        "stage8_closure_receipt_id": _safe_text(status.get("stage8_latest_receipt_id")),
        "stage8_closed_by_receipt": True,
        "control_transfer_active": True,
        "pilot_indicator_visible": True,
        "panic_stop_route": "/takeover/panic-stop",
        "handback_required": True,
        "action_feed_count": _safe_int(action_feed.get("count"), 0),
        "action_feed_operation_ids": [_safe_text(item.get("id")) for item in _as_list(action_feed.get("items"))[:5]],
        "recorded_ts": now,
        "writes_control_mode": True,
        "writes_receipt": True,
        "writes_tasks": False,
        "writes_memory": False,
        "runs_tools": False,
        "runs_shell": False,
        "runs_git": False,
        "starts_processes": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "governance": {
            "required_scope": TAKEOVER_CONTROL_TRANSFER_SCOPE,
            "explicit_control_transfer": True,
            "requires_stage8_closure_receipt": True,
            "dev_or_workstation_only": True,
            "panic_stop_available": True,
            "execution_still_uses_executor_governance": True,
            "does_not_run_tools": True,
            "does_not_run_shell": True,
            "does_not_run_git": True,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
        "next_smallest_truthful_gap": "stage9_handback_summary_receipts",
    }
    _append_jsonl(_control_transfer_path(), receipt)
    audit_record(
        "takeover.control_transfer_recorded",
        actor=safe_actor,
        reason=safe_reason,
        receipt_id=receipt_id,
        session_id=session_id,
        target="pilot_mode",
    )
    return receipt


def record_takeover_panic_stop(
    *,
    actor: Any,
    reason: Any,
) -> dict[str, Any]:
    env_profile = _env_profile()
    transfers = read_takeover_control_transfer_receipts(limit=10)
    panic_receipts = read_takeover_panic_stop_receipts(limit=10)
    handback_receipts = read_takeover_handback_summary_receipts(limit=10)
    active_transfer = _active_control_transfer(
        transfers=transfers,
        panic_receipts=panic_receipts,
        handback_receipts=handback_receipts,
    )
    session_id = _safe_text(active_transfer.get("session_id")) if active_transfer else ""
    receipt_id = f"takeover_panic_{uuid.uuid4().hex[:12]}"
    safe_actor = _redacted_text(actor)[:240]
    safe_reason = _redacted_text(reason)[:500]

    if env_profile in _ALLOWED_ENV_PROFILES:
        set_control_mode(
            "assist",
            reason=safe_reason or "stage9_takeover_panic_stop",
            actor=safe_actor,
            meta={
                "panic_stop_receipt_id": receipt_id,
                "revoked_takeover_session_id": session_id,
            },
        )
    operation_cancel_results = _cancel_takeover_operations_for_panic(
        active_transfer=active_transfer,
        reason=f"takeover_panic_stop:{receipt_id}",
    )
    cancelled_count = sum(1 for item in operation_cancel_results if bool(item.get("cancelled")))

    receipt = {
        "ok": True,
        "kind": TAKEOVER_PANIC_STOP_RECEIPT_KIND,
        "receipt_id": receipt_id,
        "session_id": session_id,
        "stage": STAGE9_TAKEOVER_STAGE,
        "source_id": "takeover",
        "target": "pilot_mode",
        "actor": safe_actor,
        "reason": safe_reason,
        "env_profile": env_profile,
        "revoked_control_transfer": bool(active_transfer),
        "latest_control_transfer_receipt_id": _safe_text(active_transfer.get("receipt_id")) if active_transfer else "",
        "control_mode_after": "assist" if env_profile in _ALLOWED_ENV_PROFILES else "",
        "recorded_ts": _now_s(),
        "writes_control_mode": env_profile in _ALLOWED_ENV_PROFILES,
        "writes_receipt": True,
        "writes_tasks": cancelled_count > 0,
        "writes_operation_state": cancelled_count > 0,
        "writes_memory": False,
        "runs_tools": False,
        "runs_shell": False,
        "runs_git": False,
        "starts_processes": False,
        "cancels_operations": cancelled_count > 0,
        "operation_cancellation_reviewed": True,
        "operation_cancel_attempt_count": len(operation_cancel_results),
        "operation_cancelled_count": cancelled_count,
        "operation_cancel_results": operation_cancel_results,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "governance": {
            "required_scope": TAKEOVER_PANIC_STOP_SCOPE,
            "panic_stop": True,
            "revokes_pilot_control_mode": env_profile in _ALLOWED_ENV_PROFILES,
            "cancels_only_control_transfer_action_feed_operations": True,
            "execution_still_uses_executor_governance": True,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
        "next_smallest_truthful_gap": "stage9_handback_summary_receipts"
        if active_transfer
        else "stage9_control_transfer_receipts",
    }
    _append_jsonl(_panic_stop_path(), receipt)
    audit_record(
        "takeover.panic_stop_recorded",
        actor=safe_actor,
        reason=safe_reason,
        receipt_id=receipt_id,
        session_id=session_id,
        revoked_control_transfer=bool(active_transfer),
    )
    return receipt


def record_takeover_handback_summary(
    *,
    actor: Any,
    reason: Any,
    summary: Any = "",
    validation_outcome: Any = "",
    remaining_uncertainty: Any = "",
    next_recommendation: Any = "",
    operation_limit: int = 10,
) -> dict[str, Any]:
    env_profile = _env_profile()
    if env_profile not in _ALLOWED_ENV_PROFILES:
        return _blocked_no_receipt(
            status="blocked_environment_profile",
            reason="takeover_handback_dev_or_workstation_only",
            required_scope=TAKEOVER_HANDBACK_SUMMARY_SCOPE,
        )

    transfers = read_takeover_control_transfer_receipts(limit=10)
    if not transfers:
        return _blocked_no_receipt(
            status="awaiting_control_transfer_receipt",
            reason="control_transfer_receipt_required_before_handback",
            required_scope=TAKEOVER_HANDBACK_SUMMARY_SCOPE,
        )

    panic_receipts = read_takeover_panic_stop_receipts(limit=10)
    handback_receipts = read_takeover_handback_summary_receipts(limit=10)
    active_transfer = _active_control_transfer(
        transfers=transfers,
        panic_receipts=panic_receipts,
        handback_receipts=handback_receipts,
    )
    latest_transfer = active_transfer or transfers[-1]
    session_id = _safe_text(latest_transfer.get("session_id"))
    transfer_ts = _safe_int(latest_transfer.get("recorded_ts"), 0)
    related_panic = _latest_receipt_for_session(
        receipts=panic_receipts,
        session_id=session_id,
        since_ts=transfer_ts,
    )
    action_feed = takeover_action_feed(limit=operation_limit)
    receipt_id = f"takeover_handback_{uuid.uuid4().hex[:12]}"
    safe_actor = _redacted_text(actor)[:240]
    safe_reason = _redacted_text(reason)[:500]
    safe_summary = _redacted_text(summary)[:800]
    safe_validation = _redacted_text(validation_outcome)[:500]
    safe_uncertainty = _redacted_text(remaining_uncertainty)[:500]
    safe_next = _redacted_text(next_recommendation)[:500]

    set_control_mode(
        "assist",
        reason=safe_reason or "stage9_takeover_handback_summary",
        actor=safe_actor,
        meta={
            "handback_receipt_id": receipt_id,
            "takeover_session_id": session_id,
            "control_transfer_receipt_id": _safe_text(latest_transfer.get("receipt_id")),
        },
    )

    receipt = {
        "ok": True,
        "kind": TAKEOVER_HANDBACK_SUMMARY_RECEIPT_KIND,
        "receipt_id": receipt_id,
        "session_id": session_id,
        "stage": STAGE9_TAKEOVER_STAGE,
        "source_id": "takeover",
        "target": "pilot_mode",
        "actor": safe_actor,
        "reason": safe_reason,
        "summary": safe_summary,
        "validation_outcome": safe_validation,
        "remaining_uncertainty": safe_uncertainty,
        "next_recommendation": safe_next,
        "env_profile": env_profile,
        "control_transfer_receipt_id": _safe_text(latest_transfer.get("receipt_id")),
        "panic_stop_receipt_id": _safe_text(related_panic.get("receipt_id")),
        "control_transferred_back": True,
        "control_mode_after": "assist",
        "was_active_at_handback": bool(active_transfer),
        "action_feed_count": _safe_int(action_feed.get("count"), 0),
        "action_feed_operation_ids": [_safe_text(item.get("id")) for item in _as_list(action_feed.get("items"))[:5]],
        "changed_artifacts": _bounded_unique_texts(
            [_safe_text(item.get("artifact_dir")) for item in _as_list(action_feed.get("items"))],
            limit=10,
        ),
        "trace_ids": _bounded_unique_texts(
            [_safe_text(item.get("trace_id")) for item in _as_list(action_feed.get("items"))],
            limit=10,
        ),
        "run_ids": _bounded_unique_texts(
            [_safe_text(item.get("run_id")) for item in _as_list(action_feed.get("items"))],
            limit=10,
        ),
        "recorded_ts": _now_s(),
        "writes_control_mode": True,
        "writes_receipt": True,
        "writes_tasks": False,
        "writes_memory": False,
        "runs_tools": False,
        "runs_shell": False,
        "runs_git": False,
        "starts_processes": False,
        "cancels_operations": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "governance": {
            "required_scope": TAKEOVER_HANDBACK_SUMMARY_SCOPE,
            "handback_summary": True,
            "requires_control_transfer_receipt": True,
            "proof_handles_included": True,
            "control_transferred_back": True,
            "execution_still_uses_executor_governance": True,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
        "next_smallest_truthful_gap": "stage9_operator_surface_contract",
    }
    _append_jsonl(_handback_summary_path(), receipt)
    audit_record(
        "takeover.handback_summary_recorded",
        actor=safe_actor,
        reason=safe_reason,
        receipt_id=receipt_id,
        session_id=session_id,
        control_transfer_receipt_id=receipt["control_transfer_receipt_id"],
    )
    return receipt


def record_takeover_live_action(
    *,
    actor: Any,
    reason: Any,
    goal: Any,
    action: Any = "plan.create",
    mission_id: Any = "",
    operation_limit: int = 10,
) -> dict[str, Any]:
    env_profile = _env_profile()
    if env_profile not in _ALLOWED_ENV_PROFILES:
        return _blocked_no_receipt(
            status="blocked_environment_profile",
            reason="takeover_live_action_dev_or_workstation_only",
            required_scope=TAKEOVER_LIVE_ACTION_SCOPE,
            next_gap="stage9_live_delegated_action_runtime",
        )

    transfers = read_takeover_control_transfer_receipts(limit=10)
    panic_receipts = read_takeover_panic_stop_receipts(limit=10)
    handback_receipts = read_takeover_handback_summary_receipts(limit=10)
    active_transfer = _active_control_transfer(
        transfers=transfers,
        panic_receipts=panic_receipts,
        handback_receipts=handback_receipts,
    )
    if not active_transfer:
        return _blocked_no_receipt(
            status="awaiting_active_control_transfer",
            reason="active_control_transfer_required_before_takeover_live_action",
            required_scope=TAKEOVER_LIVE_ACTION_SCOPE,
            next_gap="stage9_control_transfer_receipts",
        )

    safe_action = _redacted_text(action)[:120] or "plan.create"
    if safe_action not in _ALLOWED_TAKEOVER_LIVE_ACTIONS:
        return _blocked_no_receipt(
            status="unsupported_takeover_live_action",
            reason="takeover_live_action_not_allowlisted",
            required_scope=TAKEOVER_LIVE_ACTION_SCOPE,
            next_gap="stage9_live_delegated_action_runtime",
        )

    safe_actor = _redacted_text(actor)[:240]
    safe_reason = _redacted_text(reason)[:500]
    safe_goal = _redacted_text(goal)[:800] or "Run a bounded Takeover live action."
    safe_mission_id = _redacted_text(mission_id)[:160]
    session_id = _safe_text(active_transfer.get("session_id"))
    control_transfer_receipt_id = _safe_text(active_transfer.get("receipt_id"))
    receipt_id = f"takeover_live_action_{uuid.uuid4().hex[:12]}"

    created = create_operation(
        action=safe_action,
        reason=safe_reason or "stage9_takeover_live_action",
        actor=safe_actor,
        mission_id=safe_mission_id or None,
        idempotency_key=receipt_id,
        input={"goal": safe_goal},
        meta={
            "takeover_session_id": session_id,
            "control_transfer_receipt_id": control_transfer_receipt_id,
            "takeover_live_action_receipt_id": receipt_id,
            "takeover_live_action": True,
        },
        objective=f"takeover_live_action:{safe_goal}",
        priority=3,
        ttl_sec=3600,
    )
    operation_id = _safe_text(created.get("operation_id"))
    run_result: dict[str, Any] = {}
    if operation_id:
        run_result = run_operation(
            operation_id,
            worker_id="takeover.pilot",
            advance_action="takeover_live_action",
        )
    operation = _as_dict(run_result.get("operation")) or _as_dict(created.get("operation"))
    output = _as_dict(operation.get("output"))
    receipt = {
        "ok": bool(created.get("ok")) and bool(run_result.get("ok")) if operation_id else False,
        "kind": TAKEOVER_LIVE_ACTION_RECEIPT_KIND,
        "receipt_id": receipt_id,
        "session_id": session_id,
        "stage": STAGE9_TAKEOVER_STAGE,
        "source_id": "takeover",
        "target": "pilot_mode",
        "actor": safe_actor,
        "reason": safe_reason,
        "action": safe_action,
        "goal": safe_goal,
        "mission_id": safe_mission_id,
        "env_profile": env_profile,
        "control_transfer_receipt_id": control_transfer_receipt_id,
        "operation_id": operation_id,
        "operation_status": _safe_text(operation.get("status")) or _safe_text(run_result.get("status")),
        "trace_id": _safe_text(operation.get("trace_id") or output.get("trace_id")),
        "run_id": _safe_text(operation.get("run_id") or output.get("run_id")),
        "output_kind": _safe_text(output.get("kind")),
        "created_ok": bool(created.get("ok")),
        "run_ok": bool(run_result.get("ok")) if operation_id else False,
        "live_action_executed": bool(operation_id) and bool(run_result),
        "recorded_ts": _now_s(),
        "writes_receipt": True,
        "writes_operation_state": True,
        "writes_tasks": True,
        "writes_memory": bool(run_result.get("memory_receipt")),
        "runs_executor_operation": bool(operation_id),
        "runs_tools": False,
        "runs_shell": False,
        "runs_git": False,
        "starts_processes": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "governance": {
            "required_scope": TAKEOVER_LIVE_ACTION_SCOPE,
            "active_control_transfer_required": True,
            "control_transfer_receipt_id": control_transfer_receipt_id,
            "action_allowlisted": safe_action in _ALLOWED_TAKEOVER_LIVE_ACTIONS,
            "execution_still_uses_executor_governance": True,
            "does_not_run_shell": True,
            "does_not_run_git": True,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
        "next_smallest_truthful_gap": "stage9_completion_review",
    }
    _append_jsonl(_live_action_path(), receipt)
    audit_record(
        "takeover.live_action_recorded",
        actor=safe_actor,
        reason=safe_reason,
        receipt_id=receipt_id,
        session_id=session_id,
        operation_id=operation_id,
        operation_status=receipt["operation_status"],
    )
    return receipt


def read_takeover_control_transfer_receipts(*, limit: int = 20) -> list[dict[str, Any]]:
    return _read_jsonl_tail(_control_transfer_path(), limit=_safe_limit(limit, default=20))


def read_takeover_panic_stop_receipts(*, limit: int = 20) -> list[dict[str, Any]]:
    return _read_jsonl_tail(_panic_stop_path(), limit=_safe_limit(limit, default=20))


def read_takeover_handback_summary_receipts(*, limit: int = 20) -> list[dict[str, Any]]:
    return _read_jsonl_tail(_handback_summary_path(), limit=_safe_limit(limit, default=20))


def read_takeover_live_action_receipts(*, limit: int = 20) -> list[dict[str, Any]]:
    return _read_jsonl_tail(_live_action_path(), limit=_safe_limit(limit, default=20))


def _active_control_transfer(
    *,
    transfers: list[dict[str, Any]],
    panic_receipts: list[dict[str, Any]],
    handback_receipts: list[dict[str, Any]],
) -> dict[str, Any]:
    for transfer in reversed(transfers):
        if not bool(transfer.get("control_transfer_active")):
            continue
        session_id = _safe_text(transfer.get("session_id"))
        transfer_ts = _safe_int(transfer.get("recorded_ts"), 0)
        stopped = False
        for panic in panic_receipts:
            if (
                _safe_text(panic.get("session_id")) == session_id
                and _safe_int(panic.get("recorded_ts"), 0) >= transfer_ts
            ):
                stopped = True
                break
        if not stopped:
            for handback in handback_receipts:
                if (
                    _safe_text(handback.get("session_id")) == session_id
                    and _safe_int(handback.get("recorded_ts"), 0) >= transfer_ts
                ):
                    stopped = True
                    break
        if not stopped:
            return transfer
    return {}


def _action_feed_item(operation: dict[str, Any]) -> dict[str, Any]:
    meta = _as_dict(operation.get("meta"))
    return {
        "id": _safe_text(operation.get("id")),
        "ts": _safe_int(operation.get("ts"), 0),
        "status": _safe_text(operation.get("status")) or "unknown",
        "name": _safe_text(operation.get("name")),
        "actor": _safe_text(operation.get("actor")),
        "mission_id": _safe_text(operation.get("mission_id") or meta.get("mission_id")),
        "trace_id": _safe_text(operation.get("trace_id") or meta.get("trace_id")),
        "run_id": _safe_text(operation.get("run_id") or meta.get("run_id")),
        "artifact_dir": _safe_text(operation.get("artifact_dir") or meta.get("artifact_dir")),
        "objective": _redacted_text(meta.get("objective"))[:300],
        "result_status": _safe_text(meta.get("result_status")),
    }


def _cancel_takeover_operations_for_panic(*, active_transfer: dict[str, Any], reason: str) -> list[dict[str, Any]]:
    session_id = _safe_text(active_transfer.get("session_id"))
    transfer_ts = _safe_int(active_transfer.get("recorded_ts"), 0)
    live_action_operation_ids = [
        _safe_text(receipt.get("operation_id"))
        for receipt in read_takeover_live_action_receipts(limit=50)
        if _safe_text(receipt.get("session_id")) == session_id
        and _safe_int(receipt.get("recorded_ts"), 0) >= transfer_ts
    ]
    operation_ids = _bounded_unique_texts(
        [_safe_text(item) for item in _as_list(active_transfer.get("action_feed_operation_ids"))]
        + live_action_operation_ids,
        limit=20,
    )
    results: list[dict[str, Any]] = []
    for operation_id in operation_ids:
        detail = get_operation_detail(operation_id, include_logs=False, log_limit=0)
        operation = _as_dict(detail.get("operation")) if isinstance(detail, dict) else {}
        previous_status = _safe_text(operation.get("status")) or "unknown"
        if previous_status not in {"queued", "running", "blocked"}:
            results.append(
                {
                    "operation_id": operation_id,
                    "previous_status": previous_status,
                    "cancelled": False,
                    "reason": "terminal_or_not_active",
                }
            )
            continue
        ok, err = delegation_store.cancel_delegation(operation_id, reason=reason)
        results.append(
            {
                "operation_id": operation_id,
                "previous_status": previous_status,
                "cancelled": bool(ok),
                "reason": "" if ok else _redacted_text(err)[:240],
            }
        )
    return results


def _panic_operation_cancellation_ready(panic_receipts: list[dict[str, Any]]) -> bool:
    if not panic_receipts:
        return False
    latest = panic_receipts[-1]
    return bool(latest.get("operation_cancellation_reviewed"))


def _takeover_next_gap(
    *,
    active_transfer: bool,
    has_transfer: bool,
    handback_ready: bool,
    stage8_closed: bool,
    operator_surface_ready: bool,
    panic_operation_cancellation_ready: bool,
    live_action_ready: bool,
) -> str:
    if active_transfer or (has_transfer and not handback_ready):
        return "stage9_handback_summary_receipts"
    if handback_ready:
        if not operator_surface_ready:
            return "stage9_operator_surface_contract"
        return (
            "stage9_completion_review"
            if live_action_ready
            else "stage9_live_delegated_action_runtime"
            if panic_operation_cancellation_ready
            else "stage9_panic_operation_cancellation"
        )
    if stage8_closed:
        return "stage9_control_transfer_receipts"
    return "stage8_ledger_closure"


def _operator_surface_contract_ready(snapshot: dict[str, Any]) -> bool:
    return all(bool(check.get("passed")) for check in _operator_surface_contract_checks(snapshot))


def _operator_surface_contract_checks(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    latest_transfer = _as_dict(snapshot.get("latest_control_transfer_receipt"))
    latest_panic = _as_dict(snapshot.get("latest_panic_stop_receipt"))
    latest_handback = _as_dict(snapshot.get("latest_handback_summary_receipt"))
    action_feed = _as_dict(snapshot.get("action_feed"))
    deliverables = _as_dict(snapshot.get("deliverables"))
    status_governance = _as_dict(snapshot.get("governance"))
    handback_governance = _as_dict(latest_handback.get("governance"))
    next_gap = _safe_text(snapshot.get("next_smallest_truthful_gap"))
    return [
        _surface_check(
            "stage8_closure_receipt_visible",
            passed=bool(snapshot.get("stage8_closed_by_receipt"))
            and bool(_safe_text(snapshot.get("stage8_latest_receipt_id"))),
            evidence=_safe_text(snapshot.get("stage8_latest_receipt_id")),
        ),
        _surface_check(
            "control_transfer_receipt_visible",
            passed=bool(_safe_text(latest_transfer.get("receipt_id")))
            and bool(latest_transfer.get("handback_required")),
            evidence=_safe_text(latest_transfer.get("receipt_id")),
        ),
        _surface_check(
            "panic_stop_receipt_visible",
            passed=bool(_safe_text(latest_panic.get("receipt_id")))
            and bool(latest_panic.get("revoked_control_transfer")),
            evidence=_safe_text(latest_panic.get("receipt_id")),
        ),
        _surface_check(
            "handback_summary_receipt_visible",
            passed=bool(_safe_text(latest_handback.get("receipt_id")))
            and bool(latest_handback.get("control_transferred_back"))
            and bool(handback_governance.get("proof_handles_included")),
            evidence=_safe_text(latest_handback.get("receipt_id")),
        ),
        _surface_check(
            "live_action_feed_visible",
            passed=bool(action_feed.get("ok")) and isinstance(action_feed.get("items"), list),
            evidence="/takeover/action-feed",
        ),
        _surface_check(
            "pilot_visibility_visible",
            passed=bool(deliverables.get("pilot_visibility"))
            and bool(snapshot.get("pilot_indicator_visible") or latest_transfer),
            evidence=_safe_text(_as_dict(snapshot.get("control_mode")).get("id")),
        ),
        _surface_check(
            "next_gap_visible",
            passed=bool(next_gap),
            evidence=next_gap,
        ),
        _surface_check(
            "no_authority_escalation",
            passed=not bool(snapshot.get("writes_receipts"))
            and not bool(snapshot.get("writes_tasks"))
            and not bool(snapshot.get("writes_memory"))
            and not bool(snapshot.get("runs_tools"))
            and not bool(snapshot.get("runs_shell"))
            and not bool(snapshot.get("grants_execution_authority"))
            and not bool(snapshot.get("grants_mutation_authority"))
            and bool(status_governance.get("read_only")),
            evidence="read_only_status_projection",
        ),
    ]


def _surface_check(check_id: str, *, passed: bool, evidence: str) -> dict[str, Any]:
    return {
        "id": check_id,
        "passed": passed,
        "status": "ready" if passed else "blocked",
        "evidence": evidence,
    }


def _blocked_no_receipt(
    *,
    status: str,
    reason: str,
    required_scope: str,
    next_gap: str = "stage9_control_transfer_receipts",
) -> dict[str, Any]:
    return {
        "ok": True,
        "kind": "francis.stage9.takeover.control_transfer.record",
        "status": status,
        "reason": reason,
        "source_id": "takeover",
        "stage": STAGE9_TAKEOVER_STAGE,
        "receipt": None,
        "receipt_id": "",
        "writes_receipt": False,
        "writes_tasks": False,
        "writes_memory": False,
        "runs_tools": False,
        "runs_shell": False,
        "runs_git": False,
        "starts_processes": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "governance": {
            "required_scope": required_scope,
            "does_not_record_when_not_ready": True,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
        "next_smallest_truthful_gap": next_gap,
    }


def _control_transfer_path() -> Path:
    return data_dir() / "logs" / "takeover" / "control_transfer_receipts.jsonl"


def _panic_stop_path() -> Path:
    return data_dir() / "logs" / "takeover" / "panic_stop_receipts.jsonl"


def _handback_summary_path() -> Path:
    return data_dir() / "logs" / "takeover" / "handback_summary_receipts.jsonl"


def _live_action_path() -> Path:
    return data_dir() / "logs" / "takeover" / "live_action_receipts.jsonl"


def _latest_receipt_for_session(
    *,
    receipts: list[dict[str, Any]],
    session_id: str,
    since_ts: int,
) -> dict[str, Any]:
    matches = [
        receipt
        for receipt in receipts
        if _safe_text(receipt.get("session_id")) == session_id and _safe_int(receipt.get("recorded_ts"), 0) >= since_ts
    ]
    if not matches:
        return {}
    matches.sort(key=lambda item: _safe_int(item.get("recorded_ts"), 0))
    return matches[-1]


def _bounded_unique_texts(values: list[str], *, limit: int) -> list[str]:
    out: list[str] = []
    for value in values:
        text = _safe_text(value)
        if not text or text in out:
            continue
        out.append(text)
        if len(out) >= limit:
            break
    return out


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str) + "\n")


def _read_jsonl_tail(path: Path, *, limit: int) -> list[dict[str, Any]]:
    if not path.exists() or not path.is_file():
        return []
    items: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            items.append(payload)
    return items[-limit:]


def _env_profile() -> str:
    return _safe_text(os.getenv("FRANCIS_ENV_PROFILE")).strip().lower() or "dev"


def _now_s() -> int:
    return int(time.time())


def _safe_limit(value: Any, *, default: int) -> int:
    try:
        parsed = int(value)
    except Exception:
        parsed = default
    return max(1, min(parsed, 100))


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value).strip()
    except Exception:
        return ""


def _redacted_text(value: Any) -> str:
    return redact_secret_text(_safe_text(value))


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []
