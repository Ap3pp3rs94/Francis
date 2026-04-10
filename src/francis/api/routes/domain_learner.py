"""TEMP STUB: Domain-learner API surface is disabled while domain sources are quarantined."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/domain-learner/info")
def info() -> dict[str, object]:
    """Return placeholder metadata for the domain learner."""
    return {"status": "stub", "feature": "domain_learner"}
