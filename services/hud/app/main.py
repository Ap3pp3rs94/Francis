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
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from francis_presence.orb import build_orb_state
from services.hud.app.fabric import get_fabric_surface, query_fabric_surface
from services.hud.app.orb import get_orb_view
from services.hud.app.orchestrator_bridge import execute_lens_action, get_lens_actions
from services.hud.app.state import build_lens_snapshot
from services.hud.app.views.approval_queue import get_approval_queue_view
from services.hud.app.views.action_deck import get_action_deck_view
from services.hud.app.views.blocked_actions import get_blocked_actions_view
from services.hud.app.views.current_work import get_current_work_view
from services.hud.app.views.dashboard import get_dashboard_view
from services.hud.app.views.execution_feed import get_execution_feed_view
from services.hud.app.views.execution_journal import get_execution_journal_view
from services.hud.app.views.inbox import get_inbox_view
from services.hud.app.views.incidents import get_incidents_view
from services.hud.app.views.missions import get_missions_view
from services.hud.app.views.repo_drilldown import get_repo_drilldown_view
from services.hud.app.views.runs import get_runs_view
from services.hud.app.views.shift_report import get_shift_report_view
from services.voice.app.operator import build_live_operator_briefing, build_operator_presence, preview_operator_command

SERVICE_VERSION = "0.2.0"
STATIC_DIR = Path(__file__).resolve().parent / "static"
STATIC_INDEX = STATIC_DIR / "index.html"


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


def _build_hud_payload(
    *,
    snapshot: dict[str, object] | None = None,
    actions: dict[str, object] | None = None,
    max_actions: int = 8,
    execution: dict[str, object] | None = None,
) -> dict[str, object]:
    snapshot_payload = snapshot if snapshot else build_lens_snapshot()
    actions_payload = actions if actions else get_lens_actions(max_actions=max_actions)
    current_work = get_current_work_view(snapshot=snapshot_payload, actions=actions_payload)
    approval_queue = get_approval_queue_view(snapshot=snapshot_payload, actions=actions_payload)
    blocked_actions = get_blocked_actions_view(snapshot=snapshot_payload, actions=actions_payload)
    action_deck = get_action_deck_view(
        snapshot=snapshot_payload,
        actions=actions_payload,
        blocked_actions=blocked_actions,
    )
    execution_journal = get_execution_journal_view(snapshot=snapshot_payload)
    voice = build_operator_presence(
        mode=str(snapshot_payload.get("control", {}).get("mode", "assist")),
        max_actions=min(max_actions, 3),
        snapshot=snapshot_payload,
        actions_payload=actions_payload,
    )
    payload = {
        "status": "ok",
        "service": "hud",
        "version": SERVICE_VERSION,
        "snapshot": snapshot_payload,
        "actions": actions_payload,
        "voice": voice,
        "orb": build_orb_state(
            mode=str(snapshot_payload.get("control", {}).get("mode", "assist")),
            snapshot=snapshot_payload,
            actions_payload=actions_payload,
            voice=voice,
        ),
        "current_work": current_work,
        "shift_report": get_shift_report_view(snapshot=snapshot_payload),
        "repo_drilldown": get_repo_drilldown_view(snapshot=snapshot_payload, actions=actions_payload),
        "approval_queue": approval_queue,
        "blocked_actions": blocked_actions,
        "action_deck": action_deck,
        "execution_journal": execution_journal,
        "execution_feed": get_execution_feed_view(
            snapshot=snapshot_payload,
            actions=actions_payload,
            current_work=current_work,
            approval_queue=approval_queue,
            execution_journal=execution_journal,
            execution=execution,
        ),
        "dashboard": get_dashboard_view(snapshot=snapshot_payload),
        "missions": get_missions_view(snapshot=snapshot_payload),
        "incidents": get_incidents_view(snapshot=snapshot_payload),
        "inbox": get_inbox_view(snapshot=snapshot_payload),
        "runs": get_runs_view(snapshot=snapshot_payload),
        "fabric": get_fabric_surface(refresh=False, defer_if_missing=True),
    }
    payload["surface_digests"] = _surface_digests(payload)
    return payload


def _build_bootstrap_payload(*, max_actions: int = 8) -> dict[str, object]:
    return _build_hud_payload(max_actions=max_actions)


def _payload_digest(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _surface_digests(payload: dict[str, Any]) -> dict[str, str]:
    keys = (
        "snapshot",
        "actions",
        "voice",
        "orb",
        "current_work",
        "shift_report",
        "repo_drilldown",
        "approval_queue",
        "blocked_actions",
        "action_deck",
        "execution_journal",
        "execution_feed",
        "dashboard",
        "missions",
        "incidents",
        "inbox",
        "runs",
        "fabric",
    )
    digests: dict[str, str] = {}
    for key in keys:
        value = payload.get(key)
        if isinstance(value, dict):
            digests[key] = _payload_digest(value)
    return digests


def _surface_update_payload(previous: dict[str, Any], refreshed: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "snapshot",
        "actions",
        "voice",
        "orb",
        "current_work",
        "shift_report",
        "repo_drilldown",
        "approval_queue",
        "blocked_actions",
        "action_deck",
        "execution_journal",
        "execution_feed",
        "dashboard",
        "missions",
        "incidents",
        "inbox",
        "runs",
        "fabric",
    )
    payload: dict[str, Any] = {
        "status": refreshed.get("status", "ok"),
        "service": refreshed.get("service", "hud"),
        "version": refreshed.get("version", SERVICE_VERSION),
        "surface_digests": refreshed.get("surface_digests", {}),
    }
    changed: list[str] = []
    for key in keys:
        if previous.get(key) != refreshed.get(key):
            payload[key] = refreshed.get(key)
            changed.append(key)
    payload["changed"] = changed
    return payload


def _sse_event(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _build_app() -> FastAPI:
    app = FastAPI(title="Francis HUD", version=SERVICE_VERSION)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(STATIC_INDEX)

    @app.get("/health")
    def health() -> dict[str, object]:
        return {"status": "ok", "service": "hud", "version": app.version}

    @app.get("/api/dashboard")
    def dashboard() -> dict[str, object]:
        return get_dashboard_view()

    @app.get("/api/current-work")
    def current_work() -> dict[str, object]:
        return get_current_work_view()

    @app.get("/api/shift-report")
    def shift_report() -> dict[str, object]:
        return get_shift_report_view()

    @app.get("/api/approval-queue")
    def approval_queue() -> dict[str, object]:
        return get_approval_queue_view()

    @app.get("/api/blocked-actions")
    def blocked_actions() -> dict[str, object]:
        return get_blocked_actions_view()

    @app.get("/api/action-deck")
    def action_deck() -> dict[str, object]:
        return get_action_deck_view()

    @app.get("/api/repo-drilldown")
    def repo_drilldown() -> dict[str, object]:
        return get_repo_drilldown_view()

    @app.get("/api/execution-journal")
    def execution_journal() -> dict[str, object]:
        return get_execution_journal_view()

    @app.get("/api/execution-feed")
    def execution_feed() -> dict[str, object]:
        return get_execution_feed_view()

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

    @app.get("/api/orb")
    def orb(max_actions: int = 8) -> dict[str, object]:
        return get_orb_view(max_actions=max_actions)

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
        response = execute_lens_action(
            kind=payload.kind,
            args=payload.args,
            dry_run=payload.dry_run,
            role=payload.role,
            user=payload.user,
        )
        snapshot = response.get("snapshot", {}) if isinstance(response.get("snapshot"), dict) else {}
        actions = response.get("actions", {}) if isinstance(response.get("actions"), dict) else {}
        execution = response.get("execution", {}) if isinstance(response.get("execution"), dict) else None
        refresh_payload = _build_hud_payload(
            snapshot=snapshot,
            actions=actions,
            execution=execution,
        )
        return {
            **refresh_payload,
            **response,
            "snapshot": refresh_payload["snapshot"],
            "actions": refresh_payload["actions"],
            "voice": refresh_payload["voice"],
            "orb": refresh_payload["orb"],
            "current_work": refresh_payload["current_work"],
            "shift_report": refresh_payload["shift_report"],
            "repo_drilldown": refresh_payload["repo_drilldown"],
            "approval_queue": refresh_payload["approval_queue"],
            "blocked_actions": refresh_payload["blocked_actions"],
            "execution_journal": refresh_payload["execution_journal"],
            "execution_feed": refresh_payload["execution_feed"],
            "dashboard": refresh_payload["dashboard"],
            "missions": refresh_payload["missions"],
            "incidents": refresh_payload["incidents"],
            "inbox": refresh_payload["inbox"],
            "runs": refresh_payload["runs"],
            "fabric": refresh_payload["fabric"],
        }

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
                    update_payload = _surface_update_payload(bootstrap, refreshed)
                    bootstrap = refreshed
                    digest = refreshed_digest
                    updates += 1
                    yield _sse_event(
                        "surface_update",
                        {
                            "stream_id": stream_id,
                            "digest": digest,
                            "payload": update_payload,
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
