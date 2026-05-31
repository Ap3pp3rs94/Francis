from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from francis.knowledge_fabric import (
    KNOWLEDGE_FABRIC_STAGE_CLOSURE_SCOPE,
    knowledge_fabric_artifact_index_contract,
    knowledge_fabric_artifact_index_projection,
    knowledge_fabric_completion_review,
    knowledge_fabric_local_evidence_citations,
    knowledge_fabric_retention_model,
    knowledge_fabric_retrieval_preview,
    knowledge_fabric_stage12_operator_stage_closure_decision_readback,
    knowledge_fabric_status_snapshot,
    record_knowledge_fabric_stage12_operator_stage_closure_decision,
)
from francis.governance.api_permission_gate import ApiPermissionDecision, ApiPermissionGate

router = APIRouter()


class KnowledgeFabricStage12ClosureDecisionIn(BaseModel):
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
        "source_id": "knowledge_fabric",
        "writes_receipt": False,
        "writes_memory": False,
        "writes_index": False,
        "deletes_data": False,
        "mutates_retention": False,
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
    return knowledge_fabric_status_snapshot()


@router.get("/artifact-index-contract")
def artifact_index_contract() -> dict[str, Any]:
    return knowledge_fabric_artifact_index_contract()


@router.get("/artifact-index-projection")
def artifact_index_projection(limit: int = 50, memory_limit: int = 100, ledger_limit: int = 100) -> dict[str, Any]:
    return knowledge_fabric_artifact_index_projection(
        limit=limit,
        memory_limit=memory_limit,
        ledger_limit=ledger_limit,
    )


@router.get("/retrieval-preview")
def retrieval_preview(
    query: str = "",
    limit: int = 10,
    memory_limit: int = 100,
    ledger_limit: int = 100,
) -> dict[str, Any]:
    return knowledge_fabric_retrieval_preview(
        query=query,
        limit=limit,
        memory_limit=memory_limit,
        ledger_limit=ledger_limit,
    )


@router.get("/local-evidence-citations")
def local_evidence_citations(
    query: str = "",
    limit: int = 10,
    memory_limit: int = 100,
    ledger_limit: int = 100,
) -> dict[str, Any]:
    return knowledge_fabric_local_evidence_citations(
        query=query,
        limit=limit,
        memory_limit=memory_limit,
        ledger_limit=ledger_limit,
    )


@router.get("/retention-model")
def retention_model(
    query: str = "",
    limit: int = 10,
    memory_limit: int = 100,
    ledger_limit: int = 100,
) -> dict[str, Any]:
    return knowledge_fabric_retention_model(
        query=query,
        limit=limit,
        memory_limit=memory_limit,
        ledger_limit=ledger_limit,
    )


@router.get("/completion-review")
def completion_review(
    query: str = "",
    limit: int = 25,
    memory_limit: int = 100,
    ledger_limit: int = 100,
) -> dict[str, Any]:
    return knowledge_fabric_completion_review(
        query=query,
        limit=limit,
        memory_limit=memory_limit,
        ledger_limit=ledger_limit,
    )


@router.get("/stage-closure-decisions")
def stage_closure_decisions(limit: int = 20) -> dict[str, Any]:
    return knowledge_fabric_stage12_operator_stage_closure_decision_readback(limit=limit)


@router.post("/stage-closure-decision")
def stage_closure_decision(
    request: Request,
    payload: KnowledgeFabricStage12ClosureDecisionIn,
) -> dict[str, Any]:
    route = "/knowledge-fabric/stage-closure-decision"
    permission = _write_permission(
        payload.actor,
        required_scope=KNOWLEDGE_FABRIC_STAGE_CLOSURE_SCOPE,
        route=route,
        method="POST",
    )
    if not permission.allowed:
        return _permission_denied(
            permission,
            required_scope=KNOWLEDGE_FABRIC_STAGE_CLOSURE_SCOPE,
            next_step="configure_knowledge_fabric_stage12_closure_write_scope_before_decision",
        )

    review = knowledge_fabric_completion_review()
    receipt = record_knowledge_fabric_stage12_operator_stage_closure_decision(
        actor=payload.actor,
        reason=payload.reason,
        decision=payload.decision,
        review=review,
        notes=payload.notes,
    )
    return {
        "ok": bool(receipt.get("ok")),
        "kind": "francis.stage12.knowledge_fabric.stage12_closure_decision.record",
        "status": "recorded",
        "source_id": "knowledge_fabric",
        "receipt": receipt,
        "receipt_id": receipt.get("receipt_id", ""),
        "decision": receipt.get("decision", ""),
        "stage12_closed_by_receipt": bool(receipt.get("stage12_closed_by_receipt")),
        "completion_review_ready": bool(receipt.get("completion_review_ready")),
        "marks_runtime_stage_state": bool(receipt.get("marks_runtime_stage_state")),
        "writes_receipt": bool(receipt.get("writes_receipt")),
        "writes_memory": bool(receipt.get("writes_memory")),
        "writes_index": bool(receipt.get("writes_index")),
        "deletes_data": bool(receipt.get("deletes_data")),
        "mutates_retention": bool(receipt.get("mutates_retention")),
        "runs_tools": bool(receipt.get("runs_tools")),
        "runs_shell": bool(receipt.get("runs_shell")),
        "runs_git": bool(receipt.get("runs_git")),
        "starts_processes": bool(receipt.get("starts_processes")),
        "grants_execution_authority": bool(receipt.get("grants_execution_authority")),
        "grants_mutation_authority": bool(receipt.get("grants_mutation_authority")),
        "governance": {
            "required_scope": KNOWLEDGE_FABRIC_STAGE_CLOSURE_SCOPE,
            "route": str(request.url.path),
            "explicit_operator_decision": True,
            "stage_closure_decision": True,
            "completion_review_ready": bool(receipt.get("completion_review_ready")),
            "does_not_mutate_runtime_stage_state": True,
            "does_not_write_memory": True,
            "does_not_write_index": True,
            "does_not_delete_data": True,
            "does_not_mutate_retention": True,
            "does_not_run_tools": True,
            "does_not_run_shell": True,
            "does_not_run_git": True,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
        "next_smallest_truthful_gap": receipt.get(
            "next_smallest_truthful_gap",
            "stage12_operator_stage_closure_decision",
        ),
    }
