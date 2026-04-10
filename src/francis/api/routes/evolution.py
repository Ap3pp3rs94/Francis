from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/status")
def status() -> dict[str, object]:
    return {"ok": True, "route": "evolution", "status": "ready"}
