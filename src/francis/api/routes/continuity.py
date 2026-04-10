from __future__ import annotations

from fastapi import APIRouter

from francis.chat.continuity.ledger import tail

router = APIRouter()


@router.get("/ledger")
def ledger(limit: int = 200) -> dict[str, object]:
    try:
        return {"entries": tail(limit=limit)}
    except Exception as exc:
        return {"entries": [], "error": str(exc)}
