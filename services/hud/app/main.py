from __future__ import annotations

import asyncio
import hashlib
import json
import time
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from services.hud.app.fabric import get_fabric_surface, query_fabric_surface
from services.hud.app.orchestrator_bridge import execute_lens_action, get_lens_actions
from services.hud.app.state import build_lens_snapshot
from services.hud.app.views.dashboard import get_dashboard_view
from services.hud.app.views.inbox import get_inbox_view
from services.hud.app.views.incidents import get_incidents_view
from services.hud.app.views.missions import get_missions_view
from services.hud.app.views.runs import get_runs_view
from services.voice.app.operator import build_live_operator_briefing, build_operator_presence, preview_operator_command

SERVICE_VERSION = "0.2.0"
STATIC_INDEX = Path(__file__).resolve().parent / "static" / "index.html"


class HudActionExecuteRequest(BaseModel):
    kind: str
    args: dict[str, object] = Field(default_factory=dict)
    dry_run: bool = False
    role: str = "architect"
    user: str = "hud.operator"


class HudVoiceCommandPreviewRequest(BaseModel):
    utterance: str = Field(min_length=1, max_length=240)
    locale: str = Field(default="en-US")
    max_actions: int = Field(default=5, ge=1, le=8)


class HudFabricQueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=300)
    limit: int = Field(default=6, ge=1, le=12)
    sources: list[str] = Field(default_factory=list)
    run_id: str | None = None
    trace_id: str | None = None
    mission_id: str | None = None
    include_related: bool = True
    refresh: bool = False


def _build_bootstrap_payload(*, max_actions: int = 8) -> dict[str, object]:
    snapshot = build_lens_snapshot()
    actions = get_lens_actions(max_actions=max_actions)
    return {
        "status": "ok",
        "service": "hud",
        "version": SERVICE_VERSION,
        "snapshot": snapshot,
        "actions": actions,
        "voice": build_operator_presence(
            mode=str(snapshot.get("control", {}).get("mode", "assist")),
            max_actions=min(max_actions, 3),
            snapshot=snapshot,
            actions_payload=actions,
        ),
        "dashboard": get_dashboard_view(),
        "missions": get_missions_view(),
        "incidents": get_incidents_view(),
        "inbox": get_inbox_view(),
        "runs": get_runs_view(),
        "fabric": get_fabric_surface(refresh=False),
    }


def _payload_digest(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _sse_event(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _build_app() -> FastAPI:
    app = FastAPI(title="Francis HUD", version=SERVICE_VERSION)

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(STATIC_INDEX)

    @app.get("/health")
    def health() -> dict[str, object]:
        return {"status": "ok", "service": "hud", "version": app.version}

    @app.get("/api/dashboard")
    def dashboard() -> dict[str, object]:
        return get_dashboard_view()

    @app.get("/api/inbox")
    def inbox() -> dict[str, object]:
        return get_inbox_view()

    @app.get("/api/incidents")
    def incidents() -> dict[str, object]:
        return get_incidents_view()

    @app.get("/api/missions")
    def missions() -> dict[str, object]:
        return get_missions_view()

    @app.get("/api/runs")
    def runs() -> dict[str, object]:
        return get_runs_view()

    @app.get("/api/fabric")
    def fabric(refresh: bool = False) -> dict[str, object]:
        return get_fabric_surface(refresh=refresh)

    @app.post("/api/fabric/query")
    def fabric_query(payload: HudFabricQueryRequest) -> dict[str, object]:
        try:
            return query_fabric_surface(
                query=payload.query,
                limit=payload.limit,
                sources=payload.sources,
                run_id=payload.run_id,
                trace_id=payload.trace_id,
                mission_id=payload.mission_id,
                include_related=payload.include_related,
                refresh=payload.refresh,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/actions")
    def actions(max_actions: int = 8) -> dict[str, object]:
        return get_lens_actions(max_actions=max_actions)

    @app.post("/api/actions/execute")
    def action_execute(payload: HudActionExecuteRequest) -> dict[str, object]:
        return execute_lens_action(
            kind=payload.kind,
            args=payload.args,
            dry_run=payload.dry_run,
            role=payload.role,
            user=payload.user,
        )

    @app.get("/api/voice/briefing")
    def voice_briefing(
        mode: Literal["observe", "assist", "pilot", "away"] = "assist",
        max_actions: int = 3,
    ) -> dict[str, object]:
        try:
            return build_live_operator_briefing(mode=mode, max_actions=max_actions)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/voice/command/preview")
    def voice_command_preview(payload: HudVoiceCommandPreviewRequest) -> dict[str, object]:
        try:
            return preview_operator_command(
                utterance=payload.utterance,
                locale=payload.locale,
                max_actions=payload.max_actions,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/stream")
    async def stream(max_actions: int = 8, max_seconds: int = 45, poll_interval_ms: int = 1000) -> StreamingResponse:
        stream_id = str(uuid4())
        normalized_max_seconds = max(1, min(int(max_seconds), 300))
        sleep_seconds = max(0.1, min(float(poll_interval_ms) / 1000.0, 5.0))

        async def _iter_sse():
            bootstrap = _build_bootstrap_payload(max_actions=max_actions)
            digest = _payload_digest(bootstrap)
            updates = 1
            deadline = time.monotonic() + float(normalized_max_seconds)

            yield _sse_event(
                "bootstrap",
                {
                    "stream_id": stream_id,
                    "digest": digest,
                    "payload": bootstrap,
                },
            )

            while time.monotonic() < deadline:
                await asyncio.sleep(sleep_seconds)
                refreshed = _build_bootstrap_payload(max_actions=max_actions)
                refreshed_digest = _payload_digest(refreshed)
                if refreshed_digest != digest:
                    digest = refreshed_digest
                    updates += 1
                    yield _sse_event(
                        "bootstrap",
                        {
                            "stream_id": stream_id,
                            "digest": digest,
                            "payload": refreshed,
                        },
                    )
                    continue

                yield _sse_event(
                    "heartbeat",
                    {
                        "stream_id": stream_id,
                        "digest": digest,
                        "updates": updates,
                    },
                )

            yield _sse_event(
                "end",
                {
                    "stream_id": stream_id,
                    "digest": digest,
                    "updates": updates,
                },
            )

        headers = {
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
        return StreamingResponse(_iter_sse(), media_type="text/event-stream", headers=headers)

    @app.get("/api/bootstrap")
    def bootstrap() -> dict[str, object]:
        payload = _build_bootstrap_payload(max_actions=8)
        payload["version"] = app.version
        return payload

    return app


app = _build_app()
