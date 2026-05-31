from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from francis.knowledge_fabric import (
    knowledge_fabric_artifact_index_contract,
    knowledge_fabric_artifact_index_projection,
    knowledge_fabric_local_evidence_citations,
    knowledge_fabric_retrieval_preview,
    knowledge_fabric_status_snapshot,
)

router = APIRouter()


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
