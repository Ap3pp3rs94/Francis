from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from francis.adversarial_hardening import (
    adversarial_hardening_injection_containment_contract,
    adversarial_hardening_quarantine_model_contract,
    adversarial_hardening_status_snapshot,
)

router = APIRouter()


@router.get("/status")
def status() -> dict[str, Any]:
    return adversarial_hardening_status_snapshot()


@router.get("/injection-containment-contract")
def injection_containment_contract() -> dict[str, Any]:
    return adversarial_hardening_injection_containment_contract()


@router.get("/quarantine-model-contract")
def quarantine_model_contract() -> dict[str, Any]:
    return adversarial_hardening_quarantine_model_contract()
