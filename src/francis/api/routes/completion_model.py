from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from francis.completion_model import completion_model_status_snapshot

router = APIRouter()


@router.get("/status")
def status() -> dict[str, Any]:
    return completion_model_status_snapshot()
