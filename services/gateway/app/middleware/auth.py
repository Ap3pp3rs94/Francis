from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request

DEFAULT_ROLE = "viewer"
DEFAULT_USER = "anonymous"
SCOPES_HEADER = "x-francis-scopes"
USER_HEADER = "x-francis-user"
ROLE_HEADER = "x-francis-role"


@dataclass(frozen=True)
class ActorContext:
    user_id: str
    role: str
    authenticated: bool
    scopes: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "user_id": self.user_id,
            "role": self.role,
            "authenticated": self.authenticated,
            "scopes": list(self.scopes),
        }


def _parse_scopes(raw_value: str) -> tuple[str, ...]:
    scopes = {token.strip().lower() for token in raw_value.split(",") if token.strip()}
    return tuple(sorted(scopes))


def _actor_from_request(request: Request) -> ActorContext:
    user_id = request.headers.get(USER_HEADER, "").strip() or DEFAULT_USER
    role = request.headers.get(ROLE_HEADER, "").strip().lower() or DEFAULT_ROLE
    scopes = _parse_scopes(request.headers.get(SCOPES_HEADER, ""))
    authenticated = user_id != DEFAULT_USER
    return ActorContext(user_id=user_id, role=role, authenticated=authenticated, scopes=scopes)


async def attach_actor_context(request: Request, call_next):
    request.state.actor = _actor_from_request(request)
    return await call_next(request)


def get_actor(request: Request) -> ActorContext:
    actor = getattr(request.state, "actor", None)
    if isinstance(actor, ActorContext):
        return actor
    return _actor_from_request(request)
