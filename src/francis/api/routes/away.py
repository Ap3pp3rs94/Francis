from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from francis.away import away_safe_task_classes_review, away_status_snapshot

router = APIRouter()


@router.get("/status")
def status() -> dict[str, Any]:
    return away_status_snapshot()


@router.get("/safe-task-classes")
def safe_task_classes() -> dict[str, Any]:
    return away_safe_task_classes_review()
