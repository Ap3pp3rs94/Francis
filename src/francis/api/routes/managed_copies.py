from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from francis.managed_copies import managed_copies_status_snapshot

router = APIRouter()


@router.get("/status")
def status() -> dict[str, Any]:
    return managed_copies_status_snapshot()
