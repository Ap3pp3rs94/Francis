from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from francis.apprenticeship import (
    apprenticeship_replay_generalization_contract,
    apprenticeship_status_snapshot,
    apprenticeship_teaching_session_contract,
)

router = APIRouter()


@router.get("/status")
def status() -> dict[str, Any]:
    return apprenticeship_status_snapshot()


@router.get("/teaching-session-contract")
def teaching_session_contract() -> dict[str, Any]:
    return apprenticeship_teaching_session_contract()


@router.get("/replay-generalization-contract")
def replay_generalization_contract() -> dict[str, Any]:
    return apprenticeship_replay_generalization_contract()
