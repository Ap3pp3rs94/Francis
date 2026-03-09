from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from services.gateway.app.middleware.auth import get_actor
from services.gateway.app.middleware.panic_mode import is_panic_mode_enabled
from services.gateway.app.middleware.rbac import require_roles
from services.gateway.app.middleware.request_id import get_request_id

router = APIRouter(prefix="/admin", tags=["admin"])


class AdminProbeRequest(BaseModel):
    action: str = Field(min_length=3, max_length=80)
    dry_run: bool = True


@router.get("/status")
def admin_status(request: Request) -> dict[str, object]:
    require_roles(request, "architect", "admin")
    actor = get_actor(request)
    rate_limiter = getattr(request.app.state, "rate_limiter", None)
    return {
        "status": "ok",
        "service": "gateway",
        "version": request.app.version,
        "request_id": get_request_id(request),
        "panic_mode": is_panic_mode_enabled(request),
        "actor": actor.as_dict(),
        "governance": {
            "rbac": "enabled",
            "request_ids": "required",
            "panic_mode": is_panic_mode_enabled(request),
            "rate_limit": {
                "limit": getattr(rate_limiter, "limit", None),
                "window_seconds": getattr(rate_limiter, "window_seconds", None),
            },
        },
    }


@router.post("/probe")
def admin_probe(request: Request, payload: AdminProbeRequest) -> dict[str, object]:
    require_roles(request, "architect", "admin")
    actor = get_actor(request)
    return {
        "status": "accepted",
        "service": "gateway",
        "request_id": get_request_id(request),
        "actor": actor.as_dict(),
        "action": payload.action.strip().lower(),
        "dry_run": payload.dry_run,
        "mutating": not payload.dry_run,
    }
