from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from francis.governance.api_permission_gate import ApiPermissionDecision, ApiPermissionGate
from francis.takeover import (
    TAKEOVER_CONTROL_TRANSFER_SCOPE,
    TAKEOVER_HANDBACK_SUMMARY_SCOPE,
    TAKEOVER_LIVE_ACTION_SCOPE,
    TAKEOVER_PANIC_STOP_SCOPE,
    read_takeover_control_transfer_receipts,
    read_takeover_handback_summary_receipts,
    read_takeover_live_action_receipts,
    read_takeover_panic_stop_receipts,
    record_takeover_control_transfer,
    record_takeover_handback_summary,
    record_takeover_live_action,
    record_takeover_panic_stop,
    takeover_action_feed,
    takeover_operator_surface_contract,
    takeover_stage9_completion_review,
    takeover_status_snapshot,
)

router = APIRouter()


class TakeoverControlTransferIn(BaseModel):
    actor: str = Field(default="", max_length=240)
    reason: str = Field(default="", max_length=500)
    scope: str = Field(default="", max_length=500)
    mission_id: str = Field(default="", max_length=160)
    operation_limit: int = 10


class TakeoverPanicStopIn(BaseModel):
    actor: str = Field(default="", max_length=240)
    reason: str = Field(default="operator_panic_stop", max_length=500)


class TakeoverHandbackSummaryIn(BaseModel):
    actor: str = Field(default="", max_length=240)
    reason: str = Field(default="operator_handback_summary", max_length=500)
    summary: str = Field(default="", max_length=800)
    validation_outcome: str = Field(default="", max_length=500)
    remaining_uncertainty: str = Field(default="", max_length=500)
    next_recommendation: str = Field(default="", max_length=500)
    operation_limit: int = 10


class TakeoverDelegatedActionIn(BaseModel):
    actor: str = Field(default="", max_length=240)
    reason: str = Field(default="takeover_delegated_action", max_length=500)
    action: str = Field(default="plan.create", max_length=120)
    goal: str = Field(default="", max_length=800)
    mission_id: str = Field(default="", max_length=160)
    operation_limit: int = 10


def _write_permission(actor: Any, *, required_scope: str, route: str, method: str) -> ApiPermissionDecision:
    return ApiPermissionGate.from_env().check(
        actor_id=actor,
        required_scopes=[required_scope],
        route=route,
        method=method,
    )


def _permission_denied(
    decision: ApiPermissionDecision,
    *,
    required_scope: str,
    next_step: str,
) -> dict[str, Any]:
    return {
        "ok": False,
        "status": "denied",
        "error": "api_permission_denied",
        "source_id": "takeover",
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
            "gate": "permission_gate",
            "required_scope": required_scope,
            "reason": decision.reason,
            "next_step": next_step,
            "evidence": decision.evidence,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
    }


@router.get("/status")
def status(limit: int = 10) -> dict[str, Any]:
    return takeover_status_snapshot(limit=limit)


@router.get("/action-feed")
def action_feed(limit: int = 10) -> dict[str, Any]:
    return takeover_action_feed(limit=limit)


@router.get("/operator-surface-contract")
def operator_surface_contract(limit: int = 10) -> dict[str, Any]:
    return takeover_operator_surface_contract(limit=limit)


@router.get("/completion-review")
def completion_review(limit: int = 10) -> dict[str, Any]:
    return takeover_stage9_completion_review(limit=limit)


@router.get("/control-transfer-receipts")
def control_transfer_receipts(limit: int = 20) -> dict[str, Any]:
    items = read_takeover_control_transfer_receipts(limit=limit)
    return {
        "ok": True,
        "kind": "francis.stage9.takeover.control_transfer_receipts",
        "source_id": "takeover",
        "status": "ready" if items else "empty",
        "items": items,
        "count": len(items),
        "reads_receipts": True,
        "writes_receipts": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "next_smallest_truthful_gap": "stage9_panic_stop_receipts" if items else "stage9_control_transfer_receipts",
    }


@router.get("/panic-stop-receipts")
def panic_stop_receipts(limit: int = 20) -> dict[str, Any]:
    items = read_takeover_panic_stop_receipts(limit=limit)
    return {
        "ok": True,
        "kind": "francis.stage9.takeover.panic_stop_receipts",
        "source_id": "takeover",
        "status": "ready" if items else "empty",
        "items": items,
        "count": len(items),
        "reads_receipts": True,
        "writes_receipts": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "next_smallest_truthful_gap": "stage9_handback_summary_receipts" if items else "stage9_panic_stop_receipts",
    }


@router.get("/handback-summaries")
def handback_summaries(limit: int = 20) -> dict[str, Any]:
    items = read_takeover_handback_summary_receipts(limit=limit)
    return {
        "ok": True,
        "kind": "francis.stage9.takeover.handback_summary_receipts",
        "source_id": "takeover",
        "status": "ready" if items else "empty",
        "items": items,
        "count": len(items),
        "reads_receipts": True,
        "writes_receipts": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "next_smallest_truthful_gap": "stage9_operator_surface_contract"
        if items
        else "stage9_handback_summary_receipts",
    }


@router.get("/delegated-action-receipts")
def delegated_action_receipts(limit: int = 20) -> dict[str, Any]:
    items = read_takeover_live_action_receipts(limit=limit)
    return {
        "ok": True,
        "kind": "francis.stage9.takeover.live_action_receipts",
        "source_id": "takeover",
        "status": "ready" if items else "empty",
        "items": items,
        "count": len(items),
        "reads_receipts": True,
        "writes_receipts": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "next_smallest_truthful_gap": "stage9_completion_review" if items else "stage9_live_delegated_action_runtime",
    }


@router.post("/control-transfer")
def control_transfer(request: Request, payload: TakeoverControlTransferIn) -> dict[str, Any]:
    route = "/takeover/control-transfer"
    permission = _write_permission(
        payload.actor,
        required_scope=TAKEOVER_CONTROL_TRANSFER_SCOPE,
        route=route,
        method="POST",
    )
    if not permission.allowed:
        return _permission_denied(
            permission,
            required_scope=TAKEOVER_CONTROL_TRANSFER_SCOPE,
            next_step="configure_takeover_control_write_scope_before_pilot_control_transfer",
        )
    receipt = record_takeover_control_transfer(
        actor=payload.actor,
        reason=payload.reason,
        scope=payload.scope,
        mission_id=payload.mission_id,
        operation_limit=payload.operation_limit,
    )
    return {
        "ok": bool(receipt.get("ok")),
        "kind": "francis.stage9.takeover.control_transfer.record",
        "status": "recorded" if receipt.get("receipt_id") else receipt.get("status", "blocked"),
        "source_id": "takeover",
        "receipt": receipt if receipt.get("receipt_id") else None,
        "receipt_id": receipt.get("receipt_id", ""),
        "session_id": receipt.get("session_id", ""),
        "control_transfer_active": bool(receipt.get("control_transfer_active")),
        "writes_receipt": bool(receipt.get("writes_receipt")),
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
            "route": str(request.url.path),
            "explicit_control_transfer": True,
            "execution_still_uses_executor_governance": True,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
        "next_smallest_truthful_gap": receipt.get("next_smallest_truthful_gap", "stage9_control_transfer_receipts"),
    }


@router.post("/handback-summary")
def handback_summary(request: Request, payload: TakeoverHandbackSummaryIn) -> dict[str, Any]:
    route = "/takeover/handback-summary"
    permission = _write_permission(
        payload.actor,
        required_scope=TAKEOVER_HANDBACK_SUMMARY_SCOPE,
        route=route,
        method="POST",
    )
    if not permission.allowed:
        return _permission_denied(
            permission,
            required_scope=TAKEOVER_HANDBACK_SUMMARY_SCOPE,
            next_step="configure_takeover_handback_write_scope_before_pilot_handback",
        )
    receipt = record_takeover_handback_summary(
        actor=payload.actor,
        reason=payload.reason,
        summary=payload.summary,
        validation_outcome=payload.validation_outcome,
        remaining_uncertainty=payload.remaining_uncertainty,
        next_recommendation=payload.next_recommendation,
        operation_limit=payload.operation_limit,
    )
    return {
        "ok": bool(receipt.get("ok")),
        "kind": "francis.stage9.takeover.handback_summary.record",
        "status": "recorded" if receipt.get("receipt_id") else receipt.get("status", "blocked"),
        "source_id": "takeover",
        "receipt": receipt if receipt.get("receipt_id") else None,
        "receipt_id": receipt.get("receipt_id", ""),
        "session_id": receipt.get("session_id", ""),
        "control_transferred_back": bool(receipt.get("control_transferred_back")),
        "writes_receipt": bool(receipt.get("writes_receipt")),
        "writes_tasks": False,
        "writes_memory": False,
        "runs_tools": False,
        "runs_shell": False,
        "runs_git": False,
        "starts_processes": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "governance": {
            "required_scope": TAKEOVER_HANDBACK_SUMMARY_SCOPE,
            "route": str(request.url.path),
            "handback_summary": True,
            "execution_still_uses_executor_governance": True,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
        "next_smallest_truthful_gap": receipt.get("next_smallest_truthful_gap", "stage9_operator_surface_contract"),
    }


@router.post("/delegated-action")
def delegated_action(request: Request, payload: TakeoverDelegatedActionIn) -> dict[str, Any]:
    route = "/takeover/delegated-action"
    permission = _write_permission(
        payload.actor,
        required_scope=TAKEOVER_LIVE_ACTION_SCOPE,
        route=route,
        method="POST",
    )
    if not permission.allowed:
        return _permission_denied(
            permission,
            required_scope=TAKEOVER_LIVE_ACTION_SCOPE,
            next_step="configure_takeover_action_write_scope_before_delegated_action",
        )
    receipt = record_takeover_live_action(
        actor=payload.actor,
        reason=payload.reason,
        action=payload.action,
        goal=payload.goal,
        mission_id=payload.mission_id,
        operation_limit=payload.operation_limit,
    )
    return {
        "ok": bool(receipt.get("ok")),
        "kind": "francis.stage9.takeover.live_action.record",
        "status": "recorded" if receipt.get("receipt_id") else receipt.get("status", "blocked"),
        "source_id": "takeover",
        "receipt": receipt if receipt.get("receipt_id") else None,
        "receipt_id": receipt.get("receipt_id", ""),
        "session_id": receipt.get("session_id", ""),
        "operation_id": receipt.get("operation_id", ""),
        "operation_status": receipt.get("operation_status", ""),
        "trace_id": receipt.get("trace_id", ""),
        "run_id": receipt.get("run_id", ""),
        "writes_receipt": bool(receipt.get("writes_receipt")),
        "writes_tasks": bool(receipt.get("writes_tasks")),
        "writes_memory": bool(receipt.get("writes_memory")),
        "runs_executor_operation": bool(receipt.get("runs_executor_operation")),
        "runs_tools": False,
        "runs_shell": False,
        "runs_git": False,
        "starts_processes": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "governance": {
            "required_scope": TAKEOVER_LIVE_ACTION_SCOPE,
            "route": str(request.url.path),
            "active_control_transfer_required": True,
            "execution_still_uses_executor_governance": True,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
        "next_smallest_truthful_gap": receipt.get("next_smallest_truthful_gap", "stage9_live_delegated_action_runtime"),
    }


@router.post("/panic-stop")
def panic_stop(request: Request, payload: TakeoverPanicStopIn) -> dict[str, Any]:
    route = "/takeover/panic-stop"
    permission = _write_permission(
        payload.actor,
        required_scope=TAKEOVER_PANIC_STOP_SCOPE,
        route=route,
        method="POST",
    )
    if not permission.allowed:
        return _permission_denied(
            permission,
            required_scope=TAKEOVER_PANIC_STOP_SCOPE,
            next_step="configure_takeover_panic_write_scope_before_pilot_revocation",
        )
    receipt = record_takeover_panic_stop(actor=payload.actor, reason=payload.reason)
    return {
        "ok": True,
        "kind": "francis.stage9.takeover.panic_stop.record",
        "status": "recorded",
        "source_id": "takeover",
        "receipt": receipt,
        "receipt_id": receipt.get("receipt_id", ""),
        "session_id": receipt.get("session_id", ""),
        "revoked_control_transfer": bool(receipt.get("revoked_control_transfer")),
        "writes_receipt": True,
        "writes_tasks": bool(receipt.get("writes_tasks")),
        "writes_memory": False,
        "runs_tools": False,
        "runs_shell": False,
        "runs_git": False,
        "starts_processes": False,
        "cancels_operations": bool(receipt.get("cancels_operations")),
        "operation_cancellation_reviewed": bool(receipt.get("operation_cancellation_reviewed")),
        "operation_cancel_attempt_count": receipt.get("operation_cancel_attempt_count", 0),
        "operation_cancelled_count": receipt.get("operation_cancelled_count", 0),
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "governance": {
            "required_scope": TAKEOVER_PANIC_STOP_SCOPE,
            "route": str(request.url.path),
            "panic_stop": True,
            "execution_still_uses_executor_governance": True,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
        "next_smallest_truthful_gap": receipt.get("next_smallest_truthful_gap", "stage9_handback_summary_receipts"),
    }
