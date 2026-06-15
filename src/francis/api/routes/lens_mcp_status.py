from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from francis.lens import lens_orb_mcp_status_bridge

router = APIRouter()


@router.get("/mcp/status")
@router.get("/orb/mcp-status")
def mcp_status(
    actor: str = "",
    receipt_limit: int = Query(10, ge=1, le=100),
) -> dict[str, Any]:
    """Return the read-only Lens/Orb MCP body-state projection.

    This route exposes the existing Lens-Orb bridge to Lens/HUD/Chat UI
    consumers without introducing execution, screenshot, OCR, raw input, shell,
    or resident-claim authority.
    """

    return lens_orb_mcp_status_bridge(
        actor=actor or "api.lens.mcp.status",
        receipt_limit=receipt_limit,
    )
