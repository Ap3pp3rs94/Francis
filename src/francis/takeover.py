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
from francis.operations.runtime import get_operation_detail
from francis.telemetry.audit import record as audit_record
from francis.world_state.operator_mode import set_control_mode, snapshot as operator_mode_snapshot

STAGE9_TAKEOVER_STAGE = "Stage 9 / Takeover (Pilot Mode)"
TAKEOVER_STATUS_KIND = "francis.stage9.takeover.status"
TAKEOVER_ACTION_FEED_KIND = "francis.stage9.takeover.action_feed"
TAKEOVER_CONTROL_TRANSFER_RECEIPT_KIND = "francis.stage9.takeover.control_transfer_receipt"
TAKEOVER_PANIC_STOP_RECEIPT_KIND = "francis.stage9.takeover.panic_stop_receipt"
TAKEOVER_HANDBACK_SUMMARY_RECEIPT_KIND = "francis.stage9.takeover.handback_summary_receipt"

TAKEOVER_CONTROL_TRANSFER_SCOPE = "takeover.control.write"
TAKEOVER_PANIC_STOP_SCOPE = "takeover.panic.write"
TAKEOVER_HANDBACK_SUMMARY_SCOPE = "takeover.handback.write"

_ALLOWED_ENV_PROFILES = {"dev", "workstation", "local", "test"}


def takeover_status_snapshot(*, limit: int = 10) -> dict[str, Any]:
    safe_limit = _safe_limit(limit, default=10)
    stage8 = stage8_operator_stage_closure_decision_readback(limit=5)
    operator = operator_mode_snapshot()
    control_mode = _as_dict(operator.get("control_mode"))
    action_feed = takeover_action_feed(limit=safe_limit)
    transfers = read_takeover_control_transfer_receipts(limit=10)
    panic_receipts = read_takeover_panic_stop_receipts(limit=10)
    handback_receipts = read_takeover_handback_summary_receipts(limit=10)
    active_transfer = _active_control_transfer(
        transfers=transfers,
        panic_receipts=panic_receipts,
        handback_receipts=handback_receipts,
    )
    stage8_closed = bool(stage8.get("stage8_closed_by_receipt"))
    pilot_visible = _safe_text(control_mode.get("id")) == "pilot"
    control_transfer_ready = stage8_closed and not bool(active_transfer)
    handback_ready = bool(handback_receipts)
    return {
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
        "panic_stop_ready": bool(active_transfer),
        "handback_required": bool(active_transfer),
        "handback_summary_ready": handback_ready,
        "action_feed": action_feed,
        "deliverables": {
            "control_transfer_flow": bool(transfers),
            "live_action_feed": True,
            "panic_stop": bool(panic_receipts),
            "handback_summary": handback_ready,
            "pilot_visibility": pilot_visible or bool(transfers),
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
        "next_smallest_truthful_gap": "stage9_handback_summary_receipts"
        if active_transfer
        else "stage9_handback_summary_receipts"
        if transfers and not handback_ready
        else "stage9_operator_surface_contract"
        if handback_ready
        else "stage9_control_transfer_receipts"
        if stage8_closed
        else "stage8_ledger_closure",
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
            "required_scope": TAKEOVER_PANIC_STOP_SCOPE,
            "panic_stop": True,
            "revokes_pilot_control_mode": env_profile in _ALLOWED_ENV_PROFILES,
            "does_not_cancel_operations_yet": True,
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


def read_takeover_control_transfer_receipts(*, limit: int = 20) -> list[dict[str, Any]]:
    return _read_jsonl_tail(_control_transfer_path(), limit=_safe_limit(limit, default=20))


def read_takeover_panic_stop_receipts(*, limit: int = 20) -> list[dict[str, Any]]:
    return _read_jsonl_tail(_panic_stop_path(), limit=_safe_limit(limit, default=20))


def read_takeover_handback_summary_receipts(*, limit: int = 20) -> list[dict[str, Any]]:
    return _read_jsonl_tail(_handback_summary_path(), limit=_safe_limit(limit, default=20))


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
