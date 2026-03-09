from __future__ import annotations

from fastapi import APIRouter, Request

from services.gateway.app.middleware.auth import get_actor
from services.gateway.app.middleware.panic_mode import is_panic_mode_enabled
from services.gateway.app.middleware.request_id import get_request_id
from services.gateway.app.schemas.auth import AuthenticatedActor, WhoAmIResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/whoami", response_model=WhoAmIResponse)
def whoami(request: Request) -> WhoAmIResponse:
    actor = get_actor(request)
    return WhoAmIResponse(
        status="ok",
        service="gateway",
        version=request.app.version,
        request_id=get_request_id(request),
        panic_mode=is_panic_mode_enabled(request),
        actor=AuthenticatedActor(
            user_id=actor.user_id,
            role=actor.role,
            authenticated=actor.authenticated,
            scopes=list(actor.scopes),
        ),
    )
