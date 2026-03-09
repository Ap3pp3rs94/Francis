from __future__ import annotations

from pydantic import BaseModel, Field


class AuthenticatedActor(BaseModel):
    user_id: str
    role: str
    authenticated: bool
    scopes: list[str] = Field(default_factory=list)


class WhoAmIResponse(BaseModel):
    status: str
    service: str
    version: str
    request_id: str
    panic_mode: bool
    actor: AuthenticatedActor
