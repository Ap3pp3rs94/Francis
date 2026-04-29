from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field

from francis.lens import (
    lens_host_activation_execution_preflight,
    lens_host_activation_readback,
    lens_host_launch_manifest,
    lens_host_status,
    lens_preflight,
    lens_status,
    request_lens_host_activation,
)

router = APIRouter()


class LensHostActivationRequestIn(BaseModel):
    actor: str | None = None
    reason: str = "request Lens host foreground activation"
    mode: str = Field(default="foreground_status_session")


@router.get("/status")
@router.get("/hud")
def status(limit: int = Query(5, ge=1, le=50)) -> dict[str, Any]:
    return lens_status(limit=limit)


@router.get("/preflight")
def preflight() -> dict[str, Any]:
    return lens_preflight()


@router.get("/host")
def host(limit: int = Query(5, ge=1, le=50)) -> dict[str, Any]:
    return lens_host_status(limit=limit)


@router.get("/host/manifest")
def host_manifest() -> dict[str, Any]:
    return lens_host_launch_manifest()


@router.get("/host/activation")
def host_activation(limit: int = Query(5, ge=1, le=50)) -> dict[str, Any]:
    return lens_host_activation_readback(limit=limit)


@router.get("/host/activation/preflight")
def host_activation_preflight(approval_id: str = "", actor: str = "") -> dict[str, Any]:
    return lens_host_activation_execution_preflight(approval_id=approval_id, actor=actor)


@router.post("/host/activation/request")
def host_activation_request(request: Request, payload: LensHostActivationRequestIn) -> dict[str, Any]:
    return request_lens_host_activation(
        actor=payload.actor,
        reason=payload.reason,
        mode=payload.mode,
        route=request.url.path,
        method=request.method,
    )
