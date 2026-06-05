from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from francis.managed_copies import (
    managed_copies_status_snapshot,
    managed_copy_creation_contract_snapshot,
    managed_copy_isolation_rules_contract_snapshot,
)

router = APIRouter()


@router.get("/status")
def status() -> dict[str, Any]:
    return managed_copies_status_snapshot()


@router.get("/copy-creation-contract")
def copy_creation_contract() -> dict[str, Any]:
    return managed_copy_creation_contract_snapshot()


@router.get("/isolation-rules-contract")
def isolation_rules_contract() -> dict[str, Any]:
    return managed_copy_isolation_rules_contract_snapshot()
