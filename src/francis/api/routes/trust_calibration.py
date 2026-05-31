from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from francis.governance.api_permission_gate import ApiPermissionDecision, ApiPermissionGate
from francis.trust_calibration import (
    TRUST_CALIBRATION_BROWSER_VISUAL_READBACK_WRITE_SCOPE,
    TRUST_CALIBRATION_STAGE_CLOSURE_SCOPE,
    record_trust_calibration_operator_browser_visual_readback,
    record_trust_calibration_stage13_operator_stage_closure_decision,
    trust_calibration_anti_overclaim_policy,
    trust_calibration_calibrated_claim_logic,
    trust_calibration_claim_evaluation,
    trust_calibration_completion_review,
    trust_calibration_confidence_rules_contract,
    trust_calibration_operator_browser_visual_readback_receipts,
    trust_calibration_stage13_operator_stage_closure_decision_readback,
    trust_calibration_status_snapshot,
    trust_calibration_ui_state_coherence_review,
    trust_calibration_verification_gate_contract,
)

router = APIRouter()


class OperatorBrowserVisualReadbackIn(BaseModel):
    actor: str = Field(default="", max_length=240)
    reason: str = Field(default="", max_length=500)
    claim_text: str = Field(default="", max_length=280)
    surface_id: str = Field(default="", max_length=160)
    browser_name: str = Field(default="", max_length=120)
    viewport: str = Field(default="", max_length=80)
    artifact_paths: list[str] = Field(default_factory=list, max_length=6)
    claim_guard_visible: bool = False
    missing_verification_visible: bool = False
    forbidden_language_visible: bool = False
    side_effect_guard_visible: bool = False
    next_gap_visible: bool = False


class Stage13ClosureDecisionIn(BaseModel):
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
        "source_id": "trust_calibration",
        "operator_browser_visual_readback_observed": False,
        "writes_receipt": False,
        "writes_memory": False,
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
    return trust_calibration_status_snapshot()


@router.get("/confidence-rules-contract")
def confidence_rules_contract() -> dict[str, Any]:
    return trust_calibration_confidence_rules_contract()


@router.get("/verification-gate-contract")
def verification_gate_contract() -> dict[str, Any]:
    return trust_calibration_verification_gate_contract()


@router.get("/anti-overclaim-policy")
def anti_overclaim_policy() -> dict[str, Any]:
    return trust_calibration_anti_overclaim_policy()


@router.get("/calibrated-claim-logic")
def calibrated_claim_logic() -> dict[str, Any]:
    return trust_calibration_calibrated_claim_logic()


@router.get("/ui-state-coherence")
def ui_state_coherence() -> dict[str, Any]:
    return trust_calibration_ui_state_coherence_review()


@router.get("/operator-browser-visual-readbacks")
def operator_browser_visual_readbacks(limit: int = 20) -> dict[str, Any]:
    return trust_calibration_operator_browser_visual_readback_receipts(limit=limit)


@router.get("/completion-review")
def completion_review() -> dict[str, Any]:
    return trust_calibration_completion_review()


@router.get("/stage-closure-decisions")
def stage_closure_decisions(limit: int = 20) -> dict[str, Any]:
    return trust_calibration_stage13_operator_stage_closure_decision_readback(limit=limit)


@router.post("/operator-browser-visual-readback")
def operator_browser_visual_readback(payload: OperatorBrowserVisualReadbackIn) -> dict[str, Any]:
    decision = _write_permission(
        payload.actor,
        required_scope=TRUST_CALIBRATION_BROWSER_VISUAL_READBACK_WRITE_SCOPE,
        route="/trust-calibration/operator-browser-visual-readback",
        method="post",
    )
    if not decision.allowed:
        return _permission_denied(
            decision,
            required_scope=TRUST_CALIBRATION_BROWSER_VISUAL_READBACK_WRITE_SCOPE,
            next_gap="stage13_operator_browser_visual_readback",
        )
    return record_trust_calibration_operator_browser_visual_readback(**payload.model_dump())


@router.post("/stage-closure-decision")
def stage_closure_decision(request: Request, payload: Stage13ClosureDecisionIn) -> dict[str, Any]:
    route = "/trust-calibration/stage-closure-decision"
    decision = _write_permission(
        payload.actor,
        required_scope=TRUST_CALIBRATION_STAGE_CLOSURE_SCOPE,
        route=route,
        method="post",
    )
    if not decision.allowed:
        return _permission_denied(
            decision,
            required_scope=TRUST_CALIBRATION_STAGE_CLOSURE_SCOPE,
            next_gap="stage13_stage_closure_decision",
        )

    review = trust_calibration_completion_review()
    if not review.get("stage13_completion_review_ready"):
        return {
            "ok": False,
            "kind": "francis.stage13.trust_calibration.stage13_closure_decision.record",
            "status": "blocked_completion_review",
            "source_id": "trust_calibration",
            "receipt_id": "",
            "decision": "needs_more_evidence",
            "stage13_closed_by_receipt": False,
            "completion_review_ready": False,
            "writes_receipt": False,
            "writes_memory": False,
            "runs_tools": False,
            "runs_shell": False,
            "runs_git": False,
            "launches_browser": False,
            "captures_screen": False,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
            "governance": {
                "required_scope": TRUST_CALIBRATION_STAGE_CLOSURE_SCOPE,
                "route": str(request.url.path),
                "does_not_record_when_not_ready": True,
                "requires_completion_review_ready": True,
                "grants_execution_authority": False,
                "grants_mutation_authority": False,
            },
            "next_smallest_truthful_gap": review.get(
                "next_smallest_truthful_gap",
                "stage13_operator_browser_visual_readback",
            ),
        }

    receipt = record_trust_calibration_stage13_operator_stage_closure_decision(
        actor=payload.actor,
        reason=payload.reason,
        decision=payload.decision,
        review=review,
        notes=payload.notes,
    )
    return {
        "ok": bool(receipt.get("ok")),
        "kind": "francis.stage13.trust_calibration.stage13_closure_decision.record",
        "status": "recorded",
        "source_id": "trust_calibration",
        "receipt": receipt,
        "receipt_id": receipt.get("receipt_id", ""),
        "decision": receipt.get("decision", ""),
        "stage13_closed_by_receipt": bool(receipt.get("stage13_closed_by_receipt")),
        "completion_review_ready": bool(receipt.get("completion_review_ready")),
        "marks_runtime_stage_state": bool(receipt.get("marks_runtime_stage_state")),
        "writes_receipt": bool(receipt.get("writes_receipt")),
        "writes_memory": bool(receipt.get("writes_memory")),
        "runs_tools": bool(receipt.get("runs_tools")),
        "runs_shell": bool(receipt.get("runs_shell")),
        "runs_git": bool(receipt.get("runs_git")),
        "launches_browser": bool(receipt.get("launches_browser")),
        "captures_screen": bool(receipt.get("captures_screen")),
        "grants_execution_authority": bool(receipt.get("grants_execution_authority")),
        "grants_mutation_authority": bool(receipt.get("grants_mutation_authority")),
        "governance": {
            "required_scope": TRUST_CALIBRATION_STAGE_CLOSURE_SCOPE,
            "route": str(request.url.path),
            "explicit_operator_decision": True,
            "stage_closure_decision": True,
            "completion_review_ready": bool(receipt.get("completion_review_ready")),
            "does_not_mutate_runtime_stage_state": True,
            "does_not_write_memory": True,
            "does_not_run_tools": True,
            "does_not_run_shell": True,
            "does_not_run_git": True,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
        "next_smallest_truthful_gap": receipt.get(
            "next_smallest_truthful_gap",
            "stage13_stage_closure_decision",
        ),
    }


@router.post("/evaluate-claim")
def evaluate_claim(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return trust_calibration_claim_evaluation(payload)
