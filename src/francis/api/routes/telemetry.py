from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from francis.telemetry.status import telemetry_status_snapshot

router = APIRouter()


@router.get("/status")
def status() -> dict[str, Any]:
    return telemetry_status_snapshot()
