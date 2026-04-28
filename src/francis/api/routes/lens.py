from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from francis.lens import lens_status

router = APIRouter()


@router.get("/status")
@router.get("/hud")
def status(limit: int = Query(5, ge=1, le=50)) -> dict[str, Any]:
    return lens_status(limit=limit)
