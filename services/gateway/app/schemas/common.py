from __future__ import annotations

from pydantic import BaseModel, Field


class ServiceStatus(BaseModel):
    status: str = "ok"
    service: str
    version: str
    request_id: str
    panic_mode: bool = False


class UpstreamTarget(BaseModel):
    name: str
    purpose: str
    default_base_url: str
    mode_support: list[str] = Field(default_factory=list)
    mutating_paths: list[str] = Field(default_factory=list)
