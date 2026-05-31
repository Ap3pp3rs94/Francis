from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from francis.governance.api_permission_gate import ApiPermissionDecision, ApiPermissionGate
from francis.trust_calibration import (
    TRUST_CALIBRATION_BROWSER_VISUAL_READBACK_WRITE_SCOPE,
    record_trust_calibration_operator_browser_visual_readback,
    trust_calibration_anti_overclaim_policy,
    trust_calibration_calibrated_claim_logic,
    trust_calibration_claim_evaluation,
    trust_calibration_completion_review,
    trust_calibration_confidence_rules_contract,
    trust_calibration_operator_browser_visual_readback_receipts,
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


def _write_permission(actor: Any, *, route: str, method: str) -> ApiPermissionDecision:
    return ApiPermissionGate.from_env().check(
        actor_id=actor,
        required_scopes=[TRUST_CALIBRATION_BROWSER_VISUAL_READBACK_WRITE_SCOPE],
        route=route,
        method=method,
    )


def _permission_denied(decision: ApiPermissionDecision) -> dict[str, Any]:
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
            "required_scope": TRUST_CALIBRATION_BROWSER_VISUAL_READBACK_WRITE_SCOPE,
            "reason": decision.reason,
            "evidence": decision.evidence,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
        "next_smallest_truthful_gap": "stage13_operator_browser_visual_readback",
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


@router.post("/operator-browser-visual-readback")
def operator_browser_visual_readback(payload: OperatorBrowserVisualReadbackIn) -> dict[str, Any]:
    decision = _write_permission(
        payload.actor,
        route="/trust-calibration/operator-browser-visual-readback",
        method="post",
    )
    if not decision.allowed:
        return _permission_denied(decision)
    return record_trust_calibration_operator_browser_visual_readback(**payload.model_dump())


@router.post("/evaluate-claim")
def evaluate_claim(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return trust_calibration_claim_evaluation(payload)
