from __future__ import annotations

from fastapi import APIRouter, Request

from services.gateway.app.middleware.panic_mode import is_panic_mode_enabled
from services.gateway.app.middleware.request_id import get_request_id

router = APIRouter(tags=["health"])


@router.get("/health")
def health(request: Request) -> dict[str, object]:
    return {
        "status": "ok",
        "service": "gateway",
        "version": request.app.version,
        "request_id": get_request_id(request),
        "panic_mode": is_panic_mode_enabled(request),
    }
