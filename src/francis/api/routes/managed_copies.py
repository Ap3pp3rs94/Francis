from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from francis.managed_copies import (
    managed_copies_status_snapshot,
    managed_copy_completion_review_snapshot,
    managed_copy_creation_contract_snapshot,
    managed_copy_decommission_contract_snapshot,
    managed_copy_isolation_rules_contract_snapshot,
    managed_copy_rogue_recovery_contract_snapshot,
    managed_copy_runtime_evidence_contract_snapshot,
    managed_copy_safe_delta_model_contract_snapshot,
    managed_copy_sla_framework_contract_snapshot,
    managed_copy_roles_contract_snapshot,
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


@router.get("/safe-delta-model-contract")
def safe_delta_model_contract() -> dict[str, Any]:
    return managed_copy_safe_delta_model_contract_snapshot()


@router.get("/rogue-recovery-contract")
def rogue_recovery_contract() -> dict[str, Any]:
    return managed_copy_rogue_recovery_contract_snapshot()


@router.get("/sla-framework-contract")
def sla_framework_contract() -> dict[str, Any]:
    return managed_copy_sla_framework_contract_snapshot()


@router.get("/roles-contract")
def roles_contract() -> dict[str, Any]:
    return managed_copy_roles_contract_snapshot()


@router.get("/decommission-contract")
def decommission_contract() -> dict[str, Any]:
    return managed_copy_decommission_contract_snapshot()


@router.get("/completion-review")
def completion_review() -> dict[str, Any]:
    return managed_copy_completion_review_snapshot()


@router.get("/runtime-evidence-contract")
def runtime_evidence_contract() -> dict[str, Any]:
    return managed_copy_runtime_evidence_contract_snapshot()
