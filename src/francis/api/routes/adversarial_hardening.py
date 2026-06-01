from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from francis.governance.api_permission_gate import ApiPermissionDecision, ApiPermissionGate
from francis.adversarial_hardening import (
    ADVERSARIAL_HARDENING_STAGE_CLOSURE_SCOPE,
    adversarial_hardening_completion_review,
    adversarial_hardening_injection_containment_contract,
    adversarial_hardening_policy_bypass_regression_suite,
    adversarial_hardening_quarantine_model_contract,
    adversarial_hardening_red_team_regression_suite,
    adversarial_hardening_stage14_operator_stage_closure_decision_readback,
    adversarial_hardening_status_snapshot,
    record_adversarial_hardening_stage14_operator_stage_closure_decision,
)

router = APIRouter()


class Stage14ClosureDecisionIn(BaseModel):
    actor: str = Field(default="", max_length=240)
    reason: str = Field(default="", max_length=500)
    decision: str = Field(default="needs_more_evidence", max_length=80)
    notes: str = Field(default="", max_length=500)


def _write_permission(
    actor: Any,
    *,
    required_scope: str,
    route: str,
    method: str,
) -> ApiPermissionDecision:
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
    next_gap: str,
) -> dict[str, Any]:
    return {
        "ok": False,
        "status": "denied",
        "error": "api_permission_denied",
        "source_id": "adversarial_hardening",
        "stage14_closed_by_receipt": False,
        "writes_receipt": False,
        "writes_memory": False,
        "writes_quarantine": False,
        "runs_tools": False,
        "runs_shell": False,
        "runs_git": False,
        "launches_browser": False,
        "captures_screen": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "governance": {
            "gate": "permission_gate",
            "required_scope": required_scope,
            "reason": decision.reason,
            "evidence": decision.evidence,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
        "next_smallest_truthful_gap": next_gap,
    }


@router.get("/status")
def status() -> dict[str, Any]:
    return adversarial_hardening_status_snapshot()


@router.get("/injection-containment-contract")
def injection_containment_contract() -> dict[str, Any]:
    return adversarial_hardening_injection_containment_contract()


@router.get("/quarantine-model-contract")
def quarantine_model_contract() -> dict[str, Any]:
    return adversarial_hardening_quarantine_model_contract()


@router.get("/red-team-regression-suite")
def red_team_regression_suite() -> dict[str, Any]:
    return adversarial_hardening_red_team_regression_suite()


@router.get("/policy-bypass-regression-suite")
def policy_bypass_regression_suite() -> dict[str, Any]:
    return adversarial_hardening_policy_bypass_regression_suite()


@router.get("/completion-review")
def completion_review() -> dict[str, Any]:
    return adversarial_hardening_completion_review()


@router.get("/stage-closure-decisions")
def stage_closure_decisions(limit: int = 20) -> dict[str, Any]:
    return adversarial_hardening_stage14_operator_stage_closure_decision_readback(limit=limit)


@router.post("/stage-closure-decision")
def stage_closure_decision(request: Request, payload: Stage14ClosureDecisionIn) -> dict[str, Any]:
    route = "/adversarial-hardening/stage-closure-decision"
    decision = _write_permission(
        payload.actor,
        required_scope=ADVERSARIAL_HARDENING_STAGE_CLOSURE_SCOPE,
        route=route,
        method="post",
    )
    if not decision.allowed:
        return _permission_denied(
            decision,
            required_scope=ADVERSARIAL_HARDENING_STAGE_CLOSURE_SCOPE,
            next_gap="stage14_operator_stage_closure_decision",
        )

    review = adversarial_hardening_completion_review()
    if not review.get("stage14_completion_review_ready"):
        return {
            "ok": False,
            "kind": "francis.stage14.adversarial_hardening.stage14_closure_decision.record",
            "status": "blocked_completion_review",
            "source_id": "adversarial_hardening",
            "receipt_id": "",
            "decision": "needs_more_evidence",
            "stage14_closed_by_receipt": False,
            "completion_review_ready": False,
            "writes_receipt": False,
            "writes_memory": False,
            "writes_quarantine": False,
            "runs_tools": False,
            "runs_shell": False,
            "runs_git": False,
            "launches_browser": False,
            "captures_screen": False,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
            "governance": {
                "required_scope": ADVERSARIAL_HARDENING_STAGE_CLOSURE_SCOPE,
                "route": str(request.url.path),
                "does_not_record_when_not_ready": True,
                "requires_completion_review_ready": True,
                "grants_execution_authority": False,
                "grants_mutation_authority": False,
            },
            "next_smallest_truthful_gap": review.get(
                "next_smallest_truthful_gap",
                "stage14_completion_review",
            ),
        }

    receipt = record_adversarial_hardening_stage14_operator_stage_closure_decision(
        actor=payload.actor,
        reason=payload.reason,
        decision=payload.decision,
        review=review,
        notes=payload.notes,
    )
    return {
        "ok": bool(receipt.get("ok")),
        "kind": "francis.stage14.adversarial_hardening.stage14_closure_decision.record",
        "status": "recorded",
        "source_id": "adversarial_hardening",
        "receipt": receipt,
        "receipt_id": receipt.get("receipt_id", ""),
        "decision": receipt.get("decision", ""),
        "stage14_closed_by_receipt": bool(receipt.get("stage14_closed_by_receipt")),
        "completion_review_ready": bool(receipt.get("completion_review_ready")),
        "marks_runtime_stage_state": bool(receipt.get("marks_runtime_stage_state")),
        "writes_receipt": bool(receipt.get("writes_receipt")),
        "writes_memory": bool(receipt.get("writes_memory")),
        "writes_quarantine": bool(receipt.get("writes_quarantine")),
        "runs_tools": bool(receipt.get("runs_tools")),
        "runs_shell": bool(receipt.get("runs_shell")),
        "runs_git": bool(receipt.get("runs_git")),
        "launches_browser": bool(receipt.get("launches_browser")),
        "captures_screen": bool(receipt.get("captures_screen")),
        "grants_execution_authority": bool(receipt.get("grants_execution_authority")),
        "grants_mutation_authority": bool(receipt.get("grants_mutation_authority")),
        "governance": {
            "required_scope": ADVERSARIAL_HARDENING_STAGE_CLOSURE_SCOPE,
            "route": str(request.url.path),
            "explicit_operator_decision": True,
            "stage_closure_decision": True,
            "completion_review_ready": bool(receipt.get("completion_review_ready")),
            "does_not_mutate_runtime_stage_state": True,
            "does_not_write_memory": True,
            "does_not_write_quarantine": True,
            "does_not_run_tools": True,
            "does_not_run_shell": True,
            "does_not_run_git": True,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
        "next_smallest_truthful_gap": receipt.get(
            "next_smallest_truthful_gap",
            "stage14_operator_stage_closure_decision",
        ),
    }
