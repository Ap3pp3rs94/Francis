from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from francis.lens import lens_host_launch_manifest, lens_host_status, lens_preflight, lens_status

router = APIRouter()


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
