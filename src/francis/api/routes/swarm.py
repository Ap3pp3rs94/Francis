from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from francis.swarm import (
    swarm_delegation_etiquette_contract,
    swarm_messaging_model_contract,
    swarm_status_snapshot,
    swarm_trace_continuity_contract,
    swarm_unit_roles_contract,
)

router = APIRouter()


@router.get("/status")
def status() -> dict[str, Any]:
    return swarm_status_snapshot()


@router.get("/unit-roles-contract")
def unit_roles_contract() -> dict[str, Any]:
    return swarm_unit_roles_contract()


@router.get("/messaging-model-contract")
def messaging_model_contract() -> dict[str, Any]:
    return swarm_messaging_model_contract()


@router.get("/delegation-etiquette-contract")
def delegation_etiquette_contract() -> dict[str, Any]:
    return swarm_delegation_etiquette_contract()


@router.get("/trace-continuity-contract")
def trace_continuity_contract() -> dict[str, Any]:
    return swarm_trace_continuity_contract()
