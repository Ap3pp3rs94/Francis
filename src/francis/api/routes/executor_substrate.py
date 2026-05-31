from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from francis.api.mutation_authority_matrix import build_mutating_route_authority_matrix
from francis.executor_substrate import (
    STAGE8_OPERATOR_STAGE_CLOSURE_WRITE_SCOPE,
    executor_branch_first_workflow_review_snapshot,
    executor_leases_idempotency_review_snapshot,
    executor_substrate_scope_enforcement_review_snapshot,
    executor_substrate_status_snapshot,
    executor_toolbelt_allowlist_review_snapshot,
    executor_verification_hooks_review_snapshot,
    record_stage8_operator_stage_closure_decision,
    stage8_operator_stage_closure_decision_readback,
)
from francis.governance.api_permission_gate import ApiPermissionDecision, ApiPermissionGate

router = APIRouter()


class Stage8OperatorStageClosureDecisionIn(BaseModel):
    actor: str = Field(default="", max_length=240)
    reason: str = Field(default="", max_length=500)
    decision: str = Field(default="needs_more_evidence", max_length=80)
    notes: str = Field(default="", max_length=500)


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
        "source_id": "executor_substrate",
        "target": "stage8_executor_substrate",
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


@router.get("/substrate/status")
def substrate_status() -> dict[str, Any]:
    return executor_substrate_status_snapshot()


@router.get("/substrate/toolbelt-allowlist-review")
def toolbelt_allowlist_review() -> dict[str, Any]:
    return executor_toolbelt_allowlist_review_snapshot()


@router.get("/substrate/branch-first-workflow-review")
def branch_first_workflow_review() -> dict[str, Any]:
    return executor_branch_first_workflow_review_snapshot()


@router.get("/substrate/leases-idempotency-review")
def leases_idempotency_review() -> dict[str, Any]:
    return executor_leases_idempotency_review_snapshot()


@router.get("/substrate/verification-hooks-review")
def verification_hooks_review() -> dict[str, Any]:
    return executor_verification_hooks_review_snapshot()


@router.get("/substrate/scope-enforcement-review")
def scope_enforcement_review(request: Request) -> dict[str, Any]:
    return executor_substrate_scope_enforcement_review_snapshot(
        mutating_route_authority_matrix=build_mutating_route_authority_matrix(request.app.routes)
    )


@router.get("/substrate/stage-closure-decisions")
def stage_closure_decisions(limit: int = 20) -> dict[str, Any]:
    return stage8_operator_stage_closure_decision_readback(limit=limit)


@router.post("/substrate/stage-closure-decision")
def stage_closure_decision(payload: Stage8OperatorStageClosureDecisionIn, request: Request) -> dict[str, Any]:
    route = "/executor/substrate/stage-closure-decision"
    permission = _write_permission(
        payload.actor,
        required_scope=STAGE8_OPERATOR_STAGE_CLOSURE_WRITE_SCOPE,
        route=route,
        method="POST",
    )
    if not permission.allowed:
        return _permission_denied(
            permission,
            required_scope=STAGE8_OPERATOR_STAGE_CLOSURE_WRITE_SCOPE,
            next_step="configure_stage8_closure_write_scope_before_operator_stage_closure_decision",
        )

    review = executor_substrate_scope_enforcement_review_snapshot(
        mutating_route_authority_matrix=build_mutating_route_authority_matrix(request.app.routes)
    )
    if not review.get("scope_enforcement_review_ready"):
        return {
            "ok": True,
            "kind": "francis.stage8.executor_substrate.stage8_operator_stage_closure_decision.record",
            "status": "awaiting_stage8_closure_readiness",
            "source_id": "executor_substrate",
            "target": "stage8_executor_substrate",
            "review": review,
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
            "marks_runtime_stage_state": False,
            "governance": {
                "required_scope": STAGE8_OPERATOR_STAGE_CLOSURE_WRITE_SCOPE,
                "explicit_operator_decision": True,
                "does_not_record_when_review_not_ready": True,
                "does_not_mutate_runtime_stage_state": True,
                "grants_execution_authority": False,
                "grants_mutation_authority": False,
            },
            "next_smallest_truthful_gap": "stage8_substrate_scope_enforcement_review",
        }

    receipt = record_stage8_operator_stage_closure_decision(
        actor=payload.actor,
        reason=payload.reason,
        decision=payload.decision,
        notes=payload.notes,
        review=review,
    )
    return {
        "ok": True,
        "kind": "francis.stage8.executor_substrate.stage8_operator_stage_closure_decision.record",
        "status": "recorded",
        "source_id": "executor_substrate",
        "target": "stage8_executor_substrate",
        "review": review,
        "receipt": receipt,
        "receipt_id": receipt.get("receipt_id", ""),
        "decision": receipt.get("decision", ""),
        "stage8_closed_by_receipt": bool(receipt.get("stage8_closed_by_receipt")),
        "writes_receipt": True,
        "writes_tasks": False,
        "writes_memory": False,
        "runs_tools": False,
        "runs_shell": False,
        "runs_git": False,
        "starts_processes": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "marks_runtime_stage_state": False,
        "governance": {
            "required_scope": STAGE8_OPERATOR_STAGE_CLOSURE_WRITE_SCOPE,
            "explicit_operator_decision": True,
            "does_not_mutate_runtime_stage_state": True,
            "does_not_write_tasks": True,
            "does_not_write_memory": True,
            "does_not_run_tools": True,
            "does_not_run_shell": True,
            "does_not_run_git": True,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
        "next_smallest_truthful_gap": "stage8_ledger_closure",
    }
