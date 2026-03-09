from __future__ import annotations

from fastapi import HTTPException, Request

from services.gateway.app.middleware.auth import get_actor


def require_roles(request: Request, *roles: str) -> None:
    allowed_roles = {role.strip().lower() for role in roles if role.strip()}
    actor = get_actor(request)
    if actor.role not in allowed_roles:
        expected = ", ".join(sorted(allowed_roles)) or "no roles configured"
        raise HTTPException(
            status_code=403,
            detail=f"RBAC denied: role={actor.role}, expected one of [{expected}]",
        )
