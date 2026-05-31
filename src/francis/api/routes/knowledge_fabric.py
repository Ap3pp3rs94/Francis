from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from francis.knowledge_fabric import knowledge_fabric_artifact_index_contract, knowledge_fabric_status_snapshot

router = APIRouter()


@router.get("/status")
def status() -> dict[str, Any]:
    return knowledge_fabric_status_snapshot()


@router.get("/artifact-index-contract")
def artifact_index_contract() -> dict[str, Any]:
    return knowledge_fabric_artifact_index_contract()
