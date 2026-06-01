from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from francis.swarm import swarm_status_snapshot, swarm_unit_roles_contract

router = APIRouter()


@router.get("/status")
def status() -> dict[str, Any]:
    return swarm_status_snapshot()


@router.get("/unit-roles-contract")
def unit_roles_contract() -> dict[str, Any]:
    return swarm_unit_roles_contract()
