from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from francis.trust_calibration import (
    trust_calibration_confidence_rules_contract,
    trust_calibration_status_snapshot,
    trust_calibration_verification_gate_contract,
)

router = APIRouter()


@router.get("/status")
def status() -> dict[str, Any]:
    return trust_calibration_status_snapshot()


@router.get("/confidence-rules-contract")
def confidence_rules_contract() -> dict[str, Any]:
    return trust_calibration_confidence_rules_contract()


@router.get("/verification-gate-contract")
def verification_gate_contract() -> dict[str, Any]:
    return trust_calibration_verification_gate_contract()
