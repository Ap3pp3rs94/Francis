from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from francis.apprenticeship import (
    APPRENTICESHIP_REPLAY_RECEIPT_WRITE_SCOPE,
    APPRENTICESHIP_TEACHING_SESSION_WRITE_SCOPE,
    apprenticeship_forge_handoff_contract,
    apprenticeship_live_teaching_session_ux,
    apprenticeship_replay_receipts,
    apprenticeship_replay_generalization_contract,
    apprenticeship_skillization_artifact_contract,
    apprenticeship_status_snapshot,
    apprenticeship_teaching_session_contract,
    apprenticeship_teaching_session_receipts,
    record_apprenticeship_replay_receipt,
    record_apprenticeship_teaching_session,
)
from francis.governance.api_permission_gate import ApiPermissionDecision, ApiPermissionGate

router = APIRouter()


class ApprenticeshipTeachingSessionIn(BaseModel):
    actor: str = Field(default="", max_length=240)
    reason: str = Field(default="", max_length=500)
    action: str = Field(default="start_teaching_session", max_length=120)
    intent_label: str = Field(default="", max_length=240)
    declared_scope: str = Field(default="", max_length=500)
    success_condition: str = Field(default="", max_length=500)
    demonstration_summary: str = Field(default="", max_length=1000)
    notes: str = Field(default="", max_length=500)


class ApprenticeshipReplayReceiptIn(BaseModel):
    actor: str = Field(default="", max_length=240)
    reason: str = Field(default="", max_length=500)
    action: str = Field(default="review_replay", max_length=120)
    teaching_session_receipt_id: str = Field(default="", max_length=160)
    intent_label: str = Field(default="", max_length=240)
    replay_summary: str = Field(default="", max_length=1000)
    generalization_summary: str = Field(default="", max_length=1000)
    assumptions: str = Field(default="", max_length=800)
    validation_result: str = Field(default="", max_length=500)
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
        "source_id": "apprenticeship",
        "writes_receipt": False,
        "writes_memory": False,
        "writes_skill_artifact": False,
        "writes_forge_proposal": False,
        "starts_teaching_session": False,
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
    return apprenticeship_status_snapshot()


@router.get("/teaching-session-contract")
def teaching_session_contract() -> dict[str, Any]:
    return apprenticeship_teaching_session_contract()


@router.get("/replay-generalization-contract")
def replay_generalization_contract() -> dict[str, Any]:
    return apprenticeship_replay_generalization_contract()


@router.get("/skillization-artifact-contract")
def skillization_artifact_contract() -> dict[str, Any]:
    return apprenticeship_skillization_artifact_contract()


@router.get("/forge-handoff-contract")
def forge_handoff_contract() -> dict[str, Any]:
    return apprenticeship_forge_handoff_contract()


@router.get("/live-teaching-session-ux")
def live_teaching_session_ux() -> dict[str, Any]:
    return apprenticeship_live_teaching_session_ux()


@router.get("/teaching-session-receipts")
def teaching_session_receipts(limit: int = 20) -> dict[str, Any]:
    return apprenticeship_teaching_session_receipts(limit=limit)


@router.get("/replay-receipts")
def replay_receipts(limit: int = 20) -> dict[str, Any]:
    return apprenticeship_replay_receipts(limit=limit)


@router.post("/teaching-session")
def teaching_session(request: Request, payload: ApprenticeshipTeachingSessionIn) -> dict[str, Any]:
    route = "/apprenticeship/teaching-session"
    permission = _write_permission(
        payload.actor,
        required_scope=APPRENTICESHIP_TEACHING_SESSION_WRITE_SCOPE,
        route=route,
        method="POST",
    )
    if not permission.allowed:
        return _permission_denied(
            permission,
            required_scope=APPRENTICESHIP_TEACHING_SESSION_WRITE_SCOPE,
            next_step="configure_apprenticeship_teaching_session_write_scope_before_recording",
        )

    receipt = record_apprenticeship_teaching_session(
        actor=payload.actor,
        reason=payload.reason,
        action=payload.action,
        intent_label=payload.intent_label,
        declared_scope=payload.declared_scope,
        success_condition=payload.success_condition,
        demonstration_summary=payload.demonstration_summary,
        notes=payload.notes,
    )
    return {
        "ok": bool(receipt.get("ok")),
        "kind": "francis.stage11.apprenticeship.teaching_session.record",
        "status": "recorded" if receipt.get("receipt_id") else receipt.get("status", "blocked"),
        "source_id": "apprenticeship",
        "receipt": receipt if receipt.get("receipt_id") else None,
        "receipt_id": receipt.get("receipt_id", ""),
        "action": receipt.get("action", ""),
        "writes_receipt": bool(receipt.get("writes_receipt")),
        "writes_memory": bool(receipt.get("writes_memory")),
        "writes_skill_artifact": bool(receipt.get("writes_skill_artifact")),
        "writes_forge_proposal": bool(receipt.get("writes_forge_proposal")),
        "starts_teaching_session": bool(receipt.get("starts_teaching_session")),
        "runs_tools": bool(receipt.get("runs_tools")),
        "runs_shell": bool(receipt.get("runs_shell")),
        "runs_git": bool(receipt.get("runs_git")),
        "starts_processes": bool(receipt.get("starts_processes")),
        "grants_execution_authority": bool(receipt.get("grants_execution_authority")),
        "grants_mutation_authority": bool(receipt.get("grants_mutation_authority")),
        "governance": {
            "required_scope": APPRENTICESHIP_TEACHING_SESSION_WRITE_SCOPE,
            "route": str(request.url.path),
            "explicit_operator_teaching_session": True,
            "operator_supplied_steps_only": True,
            "does_not_write_memory": True,
            "does_not_run_tools": True,
            "does_not_run_shell": True,
            "does_not_run_git": True,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
        "next_smallest_truthful_gap": receipt.get(
            "next_smallest_truthful_gap",
            "stage11_teaching_session_receipt_write_path",
        ),
    }


@router.post("/replay-receipt")
def replay_receipt(request: Request, payload: ApprenticeshipReplayReceiptIn) -> dict[str, Any]:
    route = "/apprenticeship/replay-receipt"
    permission = _write_permission(
        payload.actor,
        required_scope=APPRENTICESHIP_REPLAY_RECEIPT_WRITE_SCOPE,
        route=route,
        method="POST",
    )
    if not permission.allowed:
        return _permission_denied(
            permission,
            required_scope=APPRENTICESHIP_REPLAY_RECEIPT_WRITE_SCOPE,
            next_step="configure_apprenticeship_replay_receipt_write_scope_before_recording",
        )

    receipt = record_apprenticeship_replay_receipt(
        actor=payload.actor,
        reason=payload.reason,
        action=payload.action,
        teaching_session_receipt_id=payload.teaching_session_receipt_id,
        intent_label=payload.intent_label,
        replay_summary=payload.replay_summary,
        generalization_summary=payload.generalization_summary,
        assumptions=payload.assumptions,
        validation_result=payload.validation_result,
        notes=payload.notes,
    )
    return {
        "ok": bool(receipt.get("ok")),
        "kind": "francis.stage11.apprenticeship.replay_receipt.record",
        "status": "recorded" if receipt.get("receipt_id") else receipt.get("status", "blocked"),
        "source_id": "apprenticeship",
        "receipt": receipt if receipt.get("receipt_id") else None,
        "receipt_id": receipt.get("receipt_id", ""),
        "action": receipt.get("action", ""),
        "writes_receipt": bool(receipt.get("writes_receipt")),
        "writes_memory": bool(receipt.get("writes_memory")),
        "writes_skill_artifact": bool(receipt.get("writes_skill_artifact")),
        "writes_forge_proposal": bool(receipt.get("writes_forge_proposal")),
        "starts_teaching_session": bool(receipt.get("starts_teaching_session")),
        "executes_replay": bool(receipt.get("executes_replay")),
        "promotes_skill": bool(receipt.get("promotes_skill")),
        "runs_tools": bool(receipt.get("runs_tools")),
        "runs_shell": bool(receipt.get("runs_shell")),
        "runs_git": bool(receipt.get("runs_git")),
        "starts_processes": bool(receipt.get("starts_processes")),
        "grants_execution_authority": bool(receipt.get("grants_execution_authority")),
        "grants_mutation_authority": bool(receipt.get("grants_mutation_authority")),
        "governance": {
            "required_scope": APPRENTICESHIP_REPLAY_RECEIPT_WRITE_SCOPE,
            "route": str(request.url.path),
            "requires_teaching_session_receipt": True,
            "explicit_operator_replay_review": True,
            "does_not_execute_replay": True,
            "does_not_write_memory": True,
            "does_not_run_tools": True,
            "does_not_run_shell": True,
            "does_not_run_git": True,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
        "next_smallest_truthful_gap": receipt.get(
            "next_smallest_truthful_gap",
            "stage11_replay_receipt_write_path",
        ),
    }
