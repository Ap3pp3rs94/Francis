from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from francis.executor_substrate import executor_substrate_status_snapshot

router = APIRouter()


@router.get("/substrate/status")
def substrate_status() -> dict[str, Any]:
    return executor_substrate_status_snapshot()
