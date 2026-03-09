from __future__ import annotations

from fastapi import APIRouter, Request

from services.gateway.app.middleware.auth import get_actor
from services.gateway.app.middleware.panic_mode import is_panic_mode_enabled
from services.gateway.app.middleware.request_id import get_request_id
from services.gateway.app.schemas.common import UpstreamTarget

router = APIRouter(prefix="/proxy", tags=["proxy"])

UPSTREAMS = [
    UpstreamTarget(
        name="orchestrator",
        purpose="Control state, missions, receipts, lens, and autonomy coordination",
        default_base_url="http://127.0.0.1:8000",
        mode_support=["observe", "assist", "pilot", "away"],
        mutating_paths=["/control/*", "/missions/*", "/autonomy/*"],
    ),
    UpstreamTarget(
        name="observer",
        purpose="System telemetry, anomalies, and repo/service probes",
        default_base_url="http://127.0.0.1:8010",
        mode_support=["observe", "assist", "away"],
        mutating_paths=[],
    ),
    UpstreamTarget(
        name="voice",
        purpose="Speech status, wakeword posture, and briefing generation",
        default_base_url="http://127.0.0.1:8020",
        mode_support=["observe", "assist", "pilot"],
        mutating_paths=["/voice/tts/*"],
    ),
    UpstreamTarget(
        name="hud",
        purpose="Lens dashboard, missions, inbox, runs, and incidents surfaces",
        default_base_url="http://127.0.0.1:8030",
        mode_support=["observe", "assist", "pilot", "away"],
        mutating_paths=[],
    ),
]


@router.get("/manifest")
def proxy_manifest(request: Request) -> dict[str, object]:
    return {
        "status": "ok",
        "service": "gateway",
        "request_id": get_request_id(request),
        "panic_mode": is_panic_mode_enabled(request),
        "forward_headers": [
            "x-request-id",
            "x-francis-user",
            "x-francis-role",
            "x-francis-scopes",
        ],
        "notes": (
            "Gateway currently exposes manifest-only proxy surfaces until explicit upstream "
            "dispatch contracts are enabled."
        ),
        "upstreams": [target.model_dump() for target in UPSTREAMS],
    }


@router.get("/context")
def proxy_context(request: Request) -> dict[str, object]:
    actor = get_actor(request)
    return {
        "status": "ok",
        "service": "gateway",
        "request_id": get_request_id(request),
        "panic_mode": is_panic_mode_enabled(request),
        "actor": actor.as_dict(),
        "scope_contract": "Gateway only forwards declared headers and documented upstream targets.",
        "visible_upstreams": [target.name for target in UPSTREAMS],
    }
