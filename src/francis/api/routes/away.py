from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from francis.away import (
    AWAY_LIVE_PROGRESS_SCOPE,
    away_autonomy_budgets_review,
    away_completion_review,
    away_live_progress_sample_receipts,
    away_return_briefing_snapshot,
    away_safe_task_classes_review,
    away_shift_report_snapshot,
    away_status_snapshot,
    record_away_live_progress_sample,
)
from francis.governance.api_permission_gate import ApiPermissionDecision, ApiPermissionGate

router = APIRouter()


class AwayLiveProgressSampleIn(BaseModel):
    actor: str = Field(default="", max_length=240)
    reason: str = Field(default="", max_length=500)
    sample_type: str = Field(default="shift_report_review", max_length=120)
    summary: str = Field(default="", max_length=800)
    next_recommendation: str = Field(default="", max_length=500)


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
        "source_id": "away",
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
def status() -> dict[str, Any]:
    return away_status_snapshot()


@router.get("/safe-task-classes")
def safe_task_classes() -> dict[str, Any]:
    return away_safe_task_classes_review()


@router.get("/autonomy-budgets")
def autonomy_budgets() -> dict[str, Any]:
    return away_autonomy_budgets_review()


@router.get("/shift-report")
def shift_report() -> dict[str, Any]:
    return away_shift_report_snapshot()


@router.get("/return-briefing")
def return_briefing() -> dict[str, Any]:
    return away_return_briefing_snapshot()


@router.get("/completion-review")
def completion_review() -> dict[str, Any]:
    return away_completion_review()


@router.get("/live-progress-samples")
def live_progress_samples(limit: int = 20) -> dict[str, Any]:
    return away_live_progress_sample_receipts(limit=limit)


@router.post("/live-progress-sample")
def live_progress_sample(request: Request, payload: AwayLiveProgressSampleIn) -> dict[str, Any]:
    route = "/away/live-progress-sample"
    permission = _write_permission(
        payload.actor,
        required_scope=AWAY_LIVE_PROGRESS_SCOPE,
        route=route,
        method="POST",
    )
    if not permission.allowed:
        return _permission_denied(
            permission,
            required_scope=AWAY_LIVE_PROGRESS_SCOPE,
            next_step="configure_away_progress_write_scope_before_live_progress_sample",
        )

    receipt = record_away_live_progress_sample(
        actor=payload.actor,
        reason=payload.reason,
        sample_type=payload.sample_type,
        summary=payload.summary,
        next_recommendation=payload.next_recommendation,
    )
    return {
        "ok": bool(receipt.get("ok")),
        "kind": "francis.stage10.away.live_progress_sample.record",
        "status": "recorded" if receipt.get("receipt_id") else receipt.get("status", "blocked"),
        "source_id": "away",
        "receipt": receipt if receipt.get("receipt_id") else None,
        "receipt_id": receipt.get("receipt_id", ""),
        "sample_type": receipt.get("sample_type", ""),
        "writes_receipt": bool(receipt.get("writes_receipt")),
        "writes_tasks": bool(receipt.get("writes_tasks")),
        "writes_memory": bool(receipt.get("writes_memory")),
        "runs_tools": bool(receipt.get("runs_tools")),
        "runs_shell": bool(receipt.get("runs_shell")),
        "runs_git": bool(receipt.get("runs_git")),
        "starts_processes": bool(receipt.get("starts_processes")),
        "grants_execution_authority": bool(receipt.get("grants_execution_authority")),
        "grants_mutation_authority": bool(receipt.get("grants_mutation_authority")),
        "governance": {
            "required_scope": AWAY_LIVE_PROGRESS_SCOPE,
            "route": str(request.url.path),
            "live_progress_sample": True,
            "grounded_in_existing_readbacks": True,
            "does_not_activate_away_autonomy": True,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
        "next_smallest_truthful_gap": receipt.get(
            "next_smallest_truthful_gap",
            "stage10_live_away_progress_sample",
        ),
    }
