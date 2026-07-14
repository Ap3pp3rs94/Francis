from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from francis.apprenticeship import (
    APPRENTICESHIP_FORGE_HANDOFF_WRITE_SCOPE,
    APPRENTICESHIP_REPLAY_RECEIPT_WRITE_SCOPE,
    APPRENTICESHIP_STAGE_CLOSURE_SCOPE,
    APPRENTICESHIP_SKILLIZATION_ARTIFACT_WRITE_SCOPE,
    APPRENTICESHIP_TEACHING_SESSION_WRITE_SCOPE,
    apprenticeship_forge_handoff_contract,
    apprenticeship_forge_handoff_receipts,
    apprenticeship_live_teaching_session_ux,
    apprenticeship_completion_review,
    apprenticeship_replay_receipts,
    apprenticeship_replay_generalization_contract,
    apprenticeship_skillization_artifact_receipts,
    apprenticeship_skillization_artifact_contract,
    apprenticeship_status_snapshot,
    apprenticeship_stage11_operator_stage_closure_decision_readback,
    apprenticeship_teaching_session_contract,
    apprenticeship_teaching_session_receipts,
    record_apprenticeship_stage11_operator_stage_closure_decision,
    record_apprenticeship_replay_receipt,
    record_apprenticeship_forge_handoff_receipt,
    record_apprenticeship_skillization_artifact_receipt,
    record_apprenticeship_teaching_session,
)
from francis.apprenticeship_game_teaching import (
    GAME_TEACHING_SESSION_WRITE_SCOPE,
    game_teaching_episode_receipts,
    game_teaching_session_contract,
    game_teaching_session_status,
    start_game_teaching_session,
    stop_game_teaching_session,
)
from francis.governance.api_permission_gate import ApiPermissionDecision, ApiPermissionGate

router = APIRouter()


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


class ApprenticeshipTeachingSessionIn(BaseModel):
    actor: str = Field(default="", max_length=240)
    reason: str = Field(default="", max_length=500)
    action: str = Field(default="start_teaching_session", max_length=120)
    intent_label: str = Field(default="", max_length=240)
    declared_scope: str = Field(default="", max_length=500)
    success_condition: str = Field(default="", max_length=500)
    demonstration_summary: str = Field(default="", max_length=1000)
    notes: str = Field(default="", max_length=500)


class ApprenticeshipGameTeachingSessionStartIn(BaseModel):
    actor: str = Field(default="", max_length=240)
    reason: str = Field(default="", max_length=500)
    target_id: str = Field(default="", min_length=1, max_length=64)
    intent_label: str = Field(default="", min_length=1, max_length=240)
    declared_scope: str = Field(default="", min_length=1, max_length=500)
    success_condition: str = Field(default="", min_length=1, max_length=500)
    max_duration_seconds: int = Field(default=3_600, ge=30, le=28_800)
    max_events: int = Field(default=300, ge=1, le=1_000)


class ApprenticeshipGameTeachingSessionStopIn(BaseModel):
    actor: str = Field(default="", max_length=240)
    reason: str = Field(default="", max_length=500)
    session_id: str = Field(default="", min_length=1, max_length=80)
    outcome: str = Field(default="needs_review", max_length=80)
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


class ApprenticeshipSkillizationArtifactReceiptIn(BaseModel):
    actor: str = Field(default="", max_length=240)
    reason: str = Field(default="", max_length=500)
    action: str = Field(default="prepare_skillization_artifact", max_length=120)
    replay_receipt_id: str = Field(default="", max_length=160)
    pattern_summary: str = Field(default="", max_length=1000)
    parameterization: str = Field(default="", max_length=1000)
    usage_scope: str = Field(default="", max_length=800)
    decision_logic: str = Field(default="", max_length=1000)
    validation_expectations: str = Field(default="", max_length=800)
    risk_tier_candidate: str = Field(default="", max_length=160)
    documentation_draft: str = Field(default="", max_length=1200)
    test_candidate_structure: str = Field(default="", max_length=1000)
    classification: str = Field(default="", max_length=240)
    notes: str = Field(default="", max_length=500)


class ApprenticeshipForgeHandoffReceiptIn(BaseModel):
    actor: str = Field(default="", max_length=240)
    reason: str = Field(default="", max_length=500)
    action: str = Field(default="review_forge_handoff", max_length=120)
    skillization_artifact_receipt_id: str = Field(default="", max_length=160)
    handoff_summary: str = Field(default="", max_length=1000)
    operator_review_state: str = Field(default="", max_length=500)
    risk_tier_review: str = Field(default="", max_length=500)
    documentation_review: str = Field(default="", max_length=500)
    test_candidate_review: str = Field(default="", max_length=500)
    promotion_boundary: str = Field(default="", max_length=500)
    explicit_promotion_decision: str = Field(default="", max_length=240)
    notes: str = Field(default="", max_length=500)


class ApprenticeshipStage11ClosureDecisionIn(BaseModel):
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


@router.get("/game-teaching-session/contract")
def game_teaching_contract() -> dict[str, Any]:
    return game_teaching_session_contract()


@router.get("/game-teaching-session/status")
def game_teaching_status() -> dict[str, Any]:
    return game_teaching_session_status()


@router.get("/game-teaching-session/receipts")
def game_teaching_receipts(limit: int = 20) -> dict[str, Any]:
    return game_teaching_episode_receipts(limit=limit)


@router.get("/replay-receipts")
def replay_receipts(limit: int = 20) -> dict[str, Any]:
    return apprenticeship_replay_receipts(limit=limit)


@router.get("/skillization-artifact-receipts")
def skillization_artifact_receipts(limit: int = 20) -> dict[str, Any]:
    return apprenticeship_skillization_artifact_receipts(limit=limit)


@router.get("/forge-handoff-receipts")
def forge_handoff_receipts(limit: int = 20) -> dict[str, Any]:
    return apprenticeship_forge_handoff_receipts(limit=limit)


@router.get("/completion-review")
def completion_review() -> dict[str, Any]:
    return apprenticeship_completion_review()


@router.get("/stage-closure-decisions")
def stage_closure_decisions(limit: int = 20) -> dict[str, Any]:
    return apprenticeship_stage11_operator_stage_closure_decision_readback(limit=limit)


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


@router.post("/game-teaching-session/start")
def game_teaching_start(
    request: Request,
    payload: ApprenticeshipGameTeachingSessionStartIn,
) -> dict[str, Any]:
    route = "/apprenticeship/game-teaching-session/start"
    permission = _write_permission(
        payload.actor,
        required_scope=GAME_TEACHING_SESSION_WRITE_SCOPE,
        route=route,
        method="POST",
    )
    if not permission.allowed:
        return _permission_denied(
            permission,
            required_scope=GAME_TEACHING_SESSION_WRITE_SCOPE,
            next_step="configure_game_teaching_session_write_scope_before_starting",
        )

    result = start_game_teaching_session(
        actor=payload.actor,
        reason=payload.reason,
        target_id=payload.target_id,
        intent_label=payload.intent_label,
        declared_scope=payload.declared_scope,
        success_condition=payload.success_condition,
        max_duration_seconds=payload.max_duration_seconds,
        max_events=payload.max_events,
    )
    return {
        **result,
        "kind": "francis.apprenticeship.game_teaching_session.start",
        "route": str(request.url.path),
        "session_status": result.get("status", "blocked"),
        "governance": {
            **_as_dict(result.get("governance")),
            "permission_gate": True,
            "required_scope": GAME_TEACHING_SESSION_WRITE_SCOPE,
            "route": str(request.url.path),
        },
    }


@router.post("/game-teaching-session/stop")
def game_teaching_stop(
    request: Request,
    payload: ApprenticeshipGameTeachingSessionStopIn,
) -> dict[str, Any]:
    route = "/apprenticeship/game-teaching-session/stop"
    permission = _write_permission(
        payload.actor,
        required_scope=GAME_TEACHING_SESSION_WRITE_SCOPE,
        route=route,
        method="POST",
    )
    if not permission.allowed:
        return _permission_denied(
            permission,
            required_scope=GAME_TEACHING_SESSION_WRITE_SCOPE,
            next_step="configure_game_teaching_session_write_scope_before_stopping",
        )

    result = stop_game_teaching_session(
        actor=payload.actor,
        reason=payload.reason,
        session_id=payload.session_id,
        outcome=payload.outcome,
        notes=payload.notes,
    )
    return {
        **result,
        "kind": "francis.apprenticeship.game_teaching_session.stop",
        "route": str(request.url.path),
        "receipt_kind": result.get("kind", ""),
        "governance": {
            **_as_dict(result.get("governance")),
            "permission_gate": True,
            "required_scope": GAME_TEACHING_SESSION_WRITE_SCOPE,
            "route": str(request.url.path),
        },
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


@router.post("/skillization-artifact-receipt")
def skillization_artifact_receipt(
    request: Request,
    payload: ApprenticeshipSkillizationArtifactReceiptIn,
) -> dict[str, Any]:
    route = "/apprenticeship/skillization-artifact-receipt"
    permission = _write_permission(
        payload.actor,
        required_scope=APPRENTICESHIP_SKILLIZATION_ARTIFACT_WRITE_SCOPE,
        route=route,
        method="POST",
    )
    if not permission.allowed:
        return _permission_denied(
            permission,
            required_scope=APPRENTICESHIP_SKILLIZATION_ARTIFACT_WRITE_SCOPE,
            next_step="configure_apprenticeship_skillization_artifact_write_scope_before_recording",
        )

    receipt = record_apprenticeship_skillization_artifact_receipt(
        actor=payload.actor,
        reason=payload.reason,
        action=payload.action,
        replay_receipt_id=payload.replay_receipt_id,
        pattern_summary=payload.pattern_summary,
        parameterization=payload.parameterization,
        usage_scope=payload.usage_scope,
        decision_logic=payload.decision_logic,
        validation_expectations=payload.validation_expectations,
        risk_tier_candidate=payload.risk_tier_candidate,
        documentation_draft=payload.documentation_draft,
        test_candidate_structure=payload.test_candidate_structure,
        classification=payload.classification,
        notes=payload.notes,
    )
    return {
        "ok": bool(receipt.get("ok")),
        "kind": "francis.stage11.apprenticeship.skillization_artifact.record",
        "status": "recorded" if receipt.get("receipt_id") else receipt.get("status", "blocked"),
        "source_id": "apprenticeship",
        "receipt": receipt if receipt.get("receipt_id") else None,
        "receipt_id": receipt.get("receipt_id", ""),
        "action": receipt.get("action", ""),
        "writes_receipt": bool(receipt.get("writes_receipt")),
        "writes_memory": bool(receipt.get("writes_memory")),
        "writes_skill_artifact": bool(receipt.get("writes_skill_artifact")),
        "writes_forge_proposal": bool(receipt.get("writes_forge_proposal")),
        "creates_capability": bool(receipt.get("creates_capability")),
        "promotes_to_forge": bool(receipt.get("promotes_to_forge")),
        "registers_capability": bool(receipt.get("registers_capability")),
        "runs_tools": bool(receipt.get("runs_tools")),
        "runs_shell": bool(receipt.get("runs_shell")),
        "runs_git": bool(receipt.get("runs_git")),
        "starts_processes": bool(receipt.get("starts_processes")),
        "grants_execution_authority": bool(receipt.get("grants_execution_authority")),
        "grants_mutation_authority": bool(receipt.get("grants_mutation_authority")),
        "governance": {
            "required_scope": APPRENTICESHIP_SKILLIZATION_ARTIFACT_WRITE_SCOPE,
            "route": str(request.url.path),
            "requires_replay_receipt": True,
            "explicit_operator_skillization_artifact_review": True,
            "operator_review_required_before_artifact_write": True,
            "does_not_write_memory": True,
            "does_not_write_skill_artifact": True,
            "does_not_run_tools": True,
            "does_not_run_shell": True,
            "does_not_run_git": True,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
        "next_smallest_truthful_gap": receipt.get(
            "next_smallest_truthful_gap",
            "stage11_skillization_artifact_receipt_write_path",
        ),
    }


@router.post("/forge-handoff-receipt")
def forge_handoff_receipt(request: Request, payload: ApprenticeshipForgeHandoffReceiptIn) -> dict[str, Any]:
    route = "/apprenticeship/forge-handoff-receipt"
    permission = _write_permission(
        payload.actor,
        required_scope=APPRENTICESHIP_FORGE_HANDOFF_WRITE_SCOPE,
        route=route,
        method="POST",
    )
    if not permission.allowed:
        return _permission_denied(
            permission,
            required_scope=APPRENTICESHIP_FORGE_HANDOFF_WRITE_SCOPE,
            next_step="configure_apprenticeship_forge_handoff_write_scope_before_recording",
        )

    receipt = record_apprenticeship_forge_handoff_receipt(
        actor=payload.actor,
        reason=payload.reason,
        action=payload.action,
        skillization_artifact_receipt_id=payload.skillization_artifact_receipt_id,
        handoff_summary=payload.handoff_summary,
        operator_review_state=payload.operator_review_state,
        risk_tier_review=payload.risk_tier_review,
        documentation_review=payload.documentation_review,
        test_candidate_review=payload.test_candidate_review,
        promotion_boundary=payload.promotion_boundary,
        explicit_promotion_decision=payload.explicit_promotion_decision,
        notes=payload.notes,
    )
    return {
        "ok": bool(receipt.get("ok")),
        "kind": "francis.stage11.apprenticeship.forge_handoff.record",
        "status": "recorded" if receipt.get("receipt_id") else receipt.get("status", "blocked"),
        "source_id": "apprenticeship",
        "receipt": receipt if receipt.get("receipt_id") else None,
        "receipt_id": receipt.get("receipt_id", ""),
        "action": receipt.get("action", ""),
        "writes_receipt": bool(receipt.get("writes_receipt")),
        "writes_memory": bool(receipt.get("writes_memory")),
        "writes_forge_proposal": bool(receipt.get("writes_forge_proposal")),
        "creates_capability": bool(receipt.get("creates_capability")),
        "promotes_to_forge": bool(receipt.get("promotes_to_forge")),
        "registers_capability": bool(receipt.get("registers_capability")),
        "runs_tools": bool(receipt.get("runs_tools")),
        "runs_shell": bool(receipt.get("runs_shell")),
        "runs_git": bool(receipt.get("runs_git")),
        "starts_processes": bool(receipt.get("starts_processes")),
        "grants_execution_authority": bool(receipt.get("grants_execution_authority")),
        "grants_mutation_authority": bool(receipt.get("grants_mutation_authority")),
        "governance": {
            "required_scope": APPRENTICESHIP_FORGE_HANDOFF_WRITE_SCOPE,
            "route": str(request.url.path),
            "requires_skillization_artifact_receipt": True,
            "explicit_operator_forge_handoff_review": True,
            "operator_review_required_before_forge_write": True,
            "does_not_write_memory": True,
            "does_not_write_forge_proposal": True,
            "does_not_run_tools": True,
            "does_not_run_shell": True,
            "does_not_run_git": True,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
        "next_smallest_truthful_gap": receipt.get(
            "next_smallest_truthful_gap",
            "stage11_forge_handoff_receipt_write_path",
        ),
    }


@router.post("/stage-closure-decision")
def stage_closure_decision(request: Request, payload: ApprenticeshipStage11ClosureDecisionIn) -> dict[str, Any]:
    route = "/apprenticeship/stage-closure-decision"
    permission = _write_permission(
        payload.actor,
        required_scope=APPRENTICESHIP_STAGE_CLOSURE_SCOPE,
        route=route,
        method="POST",
    )
    if not permission.allowed:
        return _permission_denied(
            permission,
            required_scope=APPRENTICESHIP_STAGE_CLOSURE_SCOPE,
            next_step="configure_apprenticeship_stage11_closure_write_scope_before_decision",
        )

    review = apprenticeship_completion_review()
    receipt = record_apprenticeship_stage11_operator_stage_closure_decision(
        actor=payload.actor,
        reason=payload.reason,
        decision=payload.decision,
        review=review,
        notes=payload.notes,
    )
    return {
        "ok": bool(receipt.get("ok")),
        "kind": "francis.stage11.apprenticeship.stage11_closure_decision.record",
        "status": "recorded",
        "source_id": "apprenticeship",
        "receipt": receipt,
        "receipt_id": receipt.get("receipt_id", ""),
        "decision": receipt.get("decision", ""),
        "stage11_closed_by_receipt": bool(receipt.get("stage11_closed_by_receipt")),
        "completion_review_ready": bool(receipt.get("completion_review_ready")),
        "marks_runtime_stage_state": bool(receipt.get("marks_runtime_stage_state")),
        "writes_receipt": bool(receipt.get("writes_receipt")),
        "writes_memory": bool(receipt.get("writes_memory")),
        "writes_skill_artifact": bool(receipt.get("writes_skill_artifact")),
        "writes_forge_proposal": bool(receipt.get("writes_forge_proposal")),
        "runs_tools": bool(receipt.get("runs_tools")),
        "runs_shell": bool(receipt.get("runs_shell")),
        "runs_git": bool(receipt.get("runs_git")),
        "starts_processes": bool(receipt.get("starts_processes")),
        "grants_execution_authority": bool(receipt.get("grants_execution_authority")),
        "grants_mutation_authority": bool(receipt.get("grants_mutation_authority")),
        "governance": {
            "required_scope": APPRENTICESHIP_STAGE_CLOSURE_SCOPE,
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
            "stage11_stage_closure_decision",
        ),
    }
