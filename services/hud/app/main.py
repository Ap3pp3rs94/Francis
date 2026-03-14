from __future__ import annotations

import asyncio
import hashlib
import json
import time
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
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
from services.hud.app.views.apprenticeship import (
    create_apprenticeship_session_record,
    get_apprenticeship_view,
    record_apprenticeship_step,
)
from services.hud.app.views.blocked_actions import get_blocked_actions_view
from services.hud.app.views.capability_library import get_capability_library_view
from services.hud.app.views.connector_library import get_connector_library_view
from services.hud.app.views.current_work import get_current_work_view
from services.hud.app.views.dashboard import get_dashboard_view
from services.hud.app.views.dependency_library import get_dependency_library_view
from services.hud.app.views.execution_feed import get_execution_feed_view
from services.hud.app.views.execution_journal import get_execution_journal_view
from services.hud.app.views.federation import get_federation_view
from services.hud.app.views.inbox import get_inbox_view
from services.hud.app.views.incidents import get_incidents_view
from services.hud.app.views.managed_copies import get_managed_copies_view
from services.hud.app.views.portability import get_portability_view
from services.hud.app.views.missions import get_missions_view
from services.hud.app.views.repo_drilldown import get_repo_drilldown_view
from services.hud.app.views.runs import get_runs_view
from services.hud.app.views.shift_report import get_shift_report_view
from services.hud.app.views.swarm import get_swarm_view
from services.orchestrator.app.routes.swarm import (
    SwarmCompleteRequest,
    SwarmCycleRequest,
    SwarmDelegateRequest,
    SwarmFailRequest,
    SwarmLeaseRequest,
    swarm_cycle,
    swarm_complete,
    swarm_delegate,
    swarm_execute,
    swarm_fail,
    swarm_lease,
)
from services.orchestrator.app.routes.federation import (
    FederationPairRequest,
    FederationRevokeRequest,
    FederationSyncRequest,
    federation_pair,
    federation_node_approvals,
    federation_remote_approval_approve,
    federation_remote_approval_reject,
    federation_revoke,
    federation_sync,
)
from services.orchestrator.app.routes.control import ControlRemoteApprovalDecisionRequest
from services.orchestrator.app.routes.connectors import (
    ConnectorLifecycleRequest,
    ConnectorRevokeRequest,
    connector_quarantine,
    connector_request_revoke_approval,
    connector_revoke,
)
from services.orchestrator.app.routes.dependencies import (
    DependencyLifecycleRequest,
    DependencyRevokeRequest,
    dependency_quarantine,
    dependency_request_revoke_approval,
    dependency_revoke,
)
from services.orchestrator.app.routes.managed_copies import (
    ManagedCopyCreateRequest,
    ManagedCopyDeltaRequest,
    ManagedCopyQuarantineRequest,
    ManagedCopyReplaceRequest,
    managed_copy_create,
    managed_copy_delta,
    managed_copy_materialize,
    managed_copy_quarantine,
    managed_copy_replace,
)
from services.orchestrator.app.routes.portability import (
    PortabilityExportRequest,
    PortabilityImportApplyRequest,
    PortabilityImportPreviewRequest,
    portability_export,
    portability_import_apply,
    portability_import_preview,
)
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


class HudApprenticeshipSessionCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    objective: str = ""
    mission_id: str | None = None
    tags: list[str] = Field(default_factory=list)
    created_by: str = "hud.operator"


class HudApprenticeshipStepCreateRequest(BaseModel):
    kind: str = Field(default="command", min_length=1, max_length=40)
    action: str = Field(min_length=1, max_length=400)
    intent: str = Field(min_length=1, max_length=200)
    artifact_path: str = ""
    notes: str = ""
    inputs: dict[str, object] = Field(default_factory=dict)
    outputs: dict[str, object] = Field(default_factory=dict)


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
        "shift_report": get_shift_report_view(
            snapshot=snapshot_payload,
            actions=actions_payload,
            current_work=current_work,
        ),
        "repo_drilldown": get_repo_drilldown_view(snapshot=snapshot_payload, actions=actions_payload),
        "capability_library": get_capability_library_view(snapshot=snapshot_payload),
        "connector_library": get_connector_library_view(snapshot=snapshot_payload),
        "dependency_library": get_dependency_library_view(snapshot=snapshot_payload),
        "swarm": get_swarm_view(snapshot=snapshot_payload),
        "federation": get_federation_view(snapshot=snapshot_payload),
        "managed_copies": get_managed_copies_view(snapshot=snapshot_payload),
        "portability": get_portability_view(snapshot=snapshot_payload),
        "approval_queue": approval_queue,
        "blocked_actions": blocked_actions,
        "action_deck": action_deck,
        "apprenticeship_surface": get_apprenticeship_view(snapshot=snapshot_payload),
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
        "capability_library",
        "connector_library",
        "dependency_library",
        "swarm",
        "federation",
        "managed_copies",
        "portability",
        "approval_queue",
        "blocked_actions",
        "action_deck",
        "apprenticeship_surface",
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
        "capability_library",
        "connector_library",
        "dependency_library",
        "swarm",
        "federation",
        "managed_copies",
        "approval_queue",
        "blocked_actions",
        "action_deck",
        "apprenticeship_surface",
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

    @app.get("/api/capability-library")
    def capability_library() -> dict[str, object]:
        return get_capability_library_view()

    @app.get("/api/connector-library")
    def connector_library() -> dict[str, object]:
        return get_connector_library_view()

    @app.get("/api/dependency-library")
    def dependency_library() -> dict[str, object]:
        return get_dependency_library_view()

    @app.post("/api/connectors/{connector_id}/quarantine")
    def hud_connector_quarantine(
        connector_id: str,
        request: Request,
        payload: ConnectorLifecycleRequest,
    ) -> dict[str, object]:
        result = connector_quarantine(connector_id=connector_id, request=request, payload=payload)
        refresh_payload = _build_hud_payload()
        return {**refresh_payload, **result}

    @app.post("/api/connectors/{connector_id}/revoke/request-approval")
    def hud_connector_request_revoke_approval(
        connector_id: str,
        request: Request,
        payload: ConnectorLifecycleRequest,
    ) -> dict[str, object]:
        result = connector_request_revoke_approval(connector_id=connector_id, request=request, payload=payload)
        refresh_payload = _build_hud_payload()
        return {**refresh_payload, **result}

    @app.post("/api/connectors/{connector_id}/revoke")
    def hud_connector_revoke(
        connector_id: str,
        request: Request,
        payload: ConnectorRevokeRequest,
    ) -> dict[str, object]:
        result = connector_revoke(connector_id=connector_id, request=request, payload=payload)
        refresh_payload = _build_hud_payload()
        return {**refresh_payload, **result}

    @app.post("/api/dependencies/{dependency_id}/quarantine")
    def hud_dependency_quarantine(
        dependency_id: str,
        request: Request,
        payload: DependencyLifecycleRequest,
    ) -> dict[str, object]:
        result = dependency_quarantine(dependency_id=dependency_id, request=request, payload=payload)
        refresh_payload = _build_hud_payload()
        return {**refresh_payload, **result}

    @app.post("/api/dependencies/{dependency_id}/revoke/request-approval")
    def hud_dependency_request_revoke_approval(
        dependency_id: str,
        request: Request,
        payload: DependencyLifecycleRequest,
    ) -> dict[str, object]:
        result = dependency_request_revoke_approval(dependency_id=dependency_id, request=request, payload=payload)
        refresh_payload = _build_hud_payload()
        return {**refresh_payload, **result}

    @app.post("/api/dependencies/{dependency_id}/revoke")
    def hud_dependency_revoke(
        dependency_id: str,
        request: Request,
        payload: DependencyRevokeRequest,
    ) -> dict[str, object]:
        result = dependency_revoke(dependency_id=dependency_id, request=request, payload=payload)
        refresh_payload = _build_hud_payload()
        return {**refresh_payload, **result}

    @app.get("/api/swarm")
    def swarm_surface() -> dict[str, object]:
        return get_swarm_view()

    @app.get("/api/federation")
    def federation_surface() -> dict[str, object]:
        return get_federation_view()

    @app.get("/api/managed-copies")
    def managed_copies_surface() -> dict[str, object]:
        return get_managed_copies_view()

    @app.get("/api/portability")
    def portability_surface() -> dict[str, object]:
        return get_portability_view()

    @app.get("/api/apprenticeship")
    def apprenticeship_surface() -> dict[str, object]:
        return get_apprenticeship_view()

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
            "capability_library": refresh_payload["capability_library"],
            "swarm": refresh_payload["swarm"],
            "federation": refresh_payload["federation"],
            "approval_queue": refresh_payload["approval_queue"],
            "blocked_actions": refresh_payload["blocked_actions"],
            "apprenticeship_surface": refresh_payload["apprenticeship_surface"],
            "execution_journal": refresh_payload["execution_journal"],
            "execution_feed": refresh_payload["execution_feed"],
            "dashboard": refresh_payload["dashboard"],
            "missions": refresh_payload["missions"],
            "incidents": refresh_payload["incidents"],
            "inbox": refresh_payload["inbox"],
            "runs": refresh_payload["runs"],
            "fabric": refresh_payload["fabric"],
        }

    @app.post("/api/portability/export")
    def portability_export_route(request: Request, payload: PortabilityExportRequest) -> dict[str, object]:
        result = portability_export(request, payload)
        refresh_payload = _build_hud_payload()
        return {**refresh_payload, **result}

    @app.post("/api/portability/import/preview")
    def portability_import_preview_route(
        request: Request,
        payload: PortabilityImportPreviewRequest,
    ) -> dict[str, object]:
        result = portability_import_preview(request, payload)
        refresh_payload = _build_hud_payload()
        return {**refresh_payload, **result}

    @app.post("/api/portability/import/apply")
    def portability_import_apply_route(
        request: Request,
        payload: PortabilityImportApplyRequest,
    ) -> dict[str, object]:
        result = portability_import_apply(request, payload)
        refresh_payload = _build_hud_payload()
        return {**refresh_payload, **result}

    @app.post("/api/apprenticeship/sessions")
    def apprenticeship_create(payload: HudApprenticeshipSessionCreateRequest) -> dict[str, object]:
        result = create_apprenticeship_session_record(
            title=payload.title,
            objective=payload.objective,
            mission_id=payload.mission_id,
            tags=payload.tags,
            created_by=payload.created_by,
        )
        refresh_payload = _build_hud_payload()
        return {
            **refresh_payload,
            **result,
            "snapshot": refresh_payload["snapshot"],
            "actions": refresh_payload["actions"],
            "voice": refresh_payload["voice"],
            "orb": refresh_payload["orb"],
            "current_work": refresh_payload["current_work"],
            "shift_report": refresh_payload["shift_report"],
            "repo_drilldown": refresh_payload["repo_drilldown"],
            "capability_library": refresh_payload["capability_library"],
            "swarm": refresh_payload["swarm"],
            "federation": refresh_payload["federation"],
            "approval_queue": refresh_payload["approval_queue"],
            "blocked_actions": refresh_payload["blocked_actions"],
            "action_deck": refresh_payload["action_deck"],
            "apprenticeship_surface": refresh_payload["apprenticeship_surface"],
            "execution_journal": refresh_payload["execution_journal"],
            "execution_feed": refresh_payload["execution_feed"],
            "dashboard": refresh_payload["dashboard"],
            "missions": refresh_payload["missions"],
            "incidents": refresh_payload["incidents"],
            "inbox": refresh_payload["inbox"],
            "runs": refresh_payload["runs"],
            "fabric": refresh_payload["fabric"],
        }

    @app.post("/api/apprenticeship/sessions/{session_id}/steps")
    def apprenticeship_record_step(session_id: str, payload: HudApprenticeshipStepCreateRequest) -> dict[str, object]:
        try:
            result = record_apprenticeship_step(
                session_id=session_id,
                kind=payload.kind,
                action=payload.action,
                intent=payload.intent,
                artifact_path=payload.artifact_path,
                notes=payload.notes,
                inputs=payload.inputs,
                outputs=payload.outputs,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        refresh_payload = _build_hud_payload()
        return {
            **refresh_payload,
            **result,
            "snapshot": refresh_payload["snapshot"],
            "actions": refresh_payload["actions"],
            "voice": refresh_payload["voice"],
            "orb": refresh_payload["orb"],
            "current_work": refresh_payload["current_work"],
            "shift_report": refresh_payload["shift_report"],
            "repo_drilldown": refresh_payload["repo_drilldown"],
            "capability_library": refresh_payload["capability_library"],
            "swarm": refresh_payload["swarm"],
            "federation": refresh_payload["federation"],
            "approval_queue": refresh_payload["approval_queue"],
            "blocked_actions": refresh_payload["blocked_actions"],
            "action_deck": refresh_payload["action_deck"],
            "apprenticeship_surface": refresh_payload["apprenticeship_surface"],
            "execution_journal": refresh_payload["execution_journal"],
            "execution_feed": refresh_payload["execution_feed"],
            "dashboard": refresh_payload["dashboard"],
            "missions": refresh_payload["missions"],
            "incidents": refresh_payload["incidents"],
            "inbox": refresh_payload["inbox"],
            "runs": refresh_payload["runs"],
            "fabric": refresh_payload["fabric"],
        }

    @app.post("/api/federation/pair")
    def hud_federation_pair(request: Request, payload: FederationPairRequest) -> dict[str, object]:
        result = federation_pair(request, payload)
        refresh_payload = _build_hud_payload()
        return {
            **refresh_payload,
            **result,
            "snapshot": refresh_payload["snapshot"],
            "actions": refresh_payload["actions"],
            "voice": refresh_payload["voice"],
            "orb": refresh_payload["orb"],
            "current_work": refresh_payload["current_work"],
            "shift_report": refresh_payload["shift_report"],
            "repo_drilldown": refresh_payload["repo_drilldown"],
            "capability_library": refresh_payload["capability_library"],
            "swarm": refresh_payload["swarm"],
            "federation": refresh_payload["federation"],
            "approval_queue": refresh_payload["approval_queue"],
            "blocked_actions": refresh_payload["blocked_actions"],
            "action_deck": refresh_payload["action_deck"],
            "apprenticeship_surface": refresh_payload["apprenticeship_surface"],
            "execution_journal": refresh_payload["execution_journal"],
            "execution_feed": refresh_payload["execution_feed"],
            "dashboard": refresh_payload["dashboard"],
            "missions": refresh_payload["missions"],
            "incidents": refresh_payload["incidents"],
            "inbox": refresh_payload["inbox"],
            "runs": refresh_payload["runs"],
            "fabric": refresh_payload["fabric"],
        }

    @app.post("/api/federation/nodes/{node_id}/revoke")
    def hud_federation_revoke(
        node_id: str,
        request: Request,
        payload: FederationRevokeRequest,
    ) -> dict[str, object]:
        result = federation_revoke(node_id, request, payload)
        refresh_payload = _build_hud_payload()
        return {
            **refresh_payload,
            **result,
            "snapshot": refresh_payload["snapshot"],
            "actions": refresh_payload["actions"],
            "voice": refresh_payload["voice"],
            "orb": refresh_payload["orb"],
            "current_work": refresh_payload["current_work"],
            "shift_report": refresh_payload["shift_report"],
            "repo_drilldown": refresh_payload["repo_drilldown"],
            "capability_library": refresh_payload["capability_library"],
            "swarm": refresh_payload["swarm"],
            "federation": refresh_payload["federation"],
            "approval_queue": refresh_payload["approval_queue"],
            "blocked_actions": refresh_payload["blocked_actions"],
            "action_deck": refresh_payload["action_deck"],
            "apprenticeship_surface": refresh_payload["apprenticeship_surface"],
            "execution_journal": refresh_payload["execution_journal"],
            "execution_feed": refresh_payload["execution_feed"],
            "dashboard": refresh_payload["dashboard"],
            "missions": refresh_payload["missions"],
            "incidents": refresh_payload["incidents"],
            "inbox": refresh_payload["inbox"],
            "runs": refresh_payload["runs"],
            "fabric": refresh_payload["fabric"],
        }

    @app.post("/api/federation/nodes/{node_id}/sync")
    def hud_federation_sync(
        node_id: str,
        request: Request,
        payload: FederationSyncRequest,
    ) -> dict[str, object]:
        result = federation_sync(node_id=node_id, request=request, payload=payload)
        refresh_payload = _build_hud_payload()
        return {
            **refresh_payload,
            **result,
            "snapshot": refresh_payload["snapshot"],
            "actions": refresh_payload["actions"],
            "voice": refresh_payload["voice"],
            "orb": refresh_payload["orb"],
            "current_work": refresh_payload["current_work"],
            "shift_report": refresh_payload["shift_report"],
            "repo_drilldown": refresh_payload["repo_drilldown"],
            "capability_library": refresh_payload["capability_library"],
            "swarm": refresh_payload["swarm"],
            "federation": refresh_payload["federation"],
            "approval_queue": refresh_payload["approval_queue"],
            "blocked_actions": refresh_payload["blocked_actions"],
            "action_deck": refresh_payload["action_deck"],
            "apprenticeship_surface": refresh_payload["apprenticeship_surface"],
            "execution_journal": refresh_payload["execution_journal"],
            "execution_feed": refresh_payload["execution_feed"],
            "dashboard": refresh_payload["dashboard"],
            "missions": refresh_payload["missions"],
            "incidents": refresh_payload["incidents"],
            "inbox": refresh_payload["inbox"],
            "runs": refresh_payload["runs"],
            "fabric": refresh_payload["fabric"],
        }

    @app.get("/api/federation/nodes/{node_id}/approvals")
    def hud_federation_node_approvals(
        node_id: str,
        request: Request,
        status: str = "pending",
        limit: int = 20,
    ) -> dict[str, object]:
        result = federation_node_approvals(node_id=node_id, request=request, status=status, limit=limit)
        refresh_payload = _build_hud_payload()
        return {
            **refresh_payload,
            **result,
            "snapshot": refresh_payload["snapshot"],
            "actions": refresh_payload["actions"],
            "voice": refresh_payload["voice"],
            "orb": refresh_payload["orb"],
            "current_work": refresh_payload["current_work"],
            "shift_report": refresh_payload["shift_report"],
            "repo_drilldown": refresh_payload["repo_drilldown"],
            "capability_library": refresh_payload["capability_library"],
            "swarm": refresh_payload["swarm"],
            "federation": refresh_payload["federation"],
            "approval_queue": refresh_payload["approval_queue"],
            "blocked_actions": refresh_payload["blocked_actions"],
            "action_deck": refresh_payload["action_deck"],
            "apprenticeship_surface": refresh_payload["apprenticeship_surface"],
            "execution_journal": refresh_payload["execution_journal"],
            "execution_feed": refresh_payload["execution_feed"],
            "dashboard": refresh_payload["dashboard"],
            "missions": refresh_payload["missions"],
            "incidents": refresh_payload["incidents"],
            "inbox": refresh_payload["inbox"],
            "runs": refresh_payload["runs"],
            "fabric": refresh_payload["fabric"],
        }

    @app.post("/api/federation/nodes/{node_id}/approvals/{approval_id}/approve")
    def hud_federation_approval_approve(
        node_id: str,
        approval_id: str,
        request: Request,
        payload: ControlRemoteApprovalDecisionRequest | None = None,
    ) -> dict[str, object]:
        result = federation_remote_approval_approve(
            node_id=node_id,
            approval_id=approval_id,
            request=request,
            payload=payload,
        )
        refresh_payload = _build_hud_payload()
        return {
            **refresh_payload,
            **result,
            "snapshot": refresh_payload["snapshot"],
            "actions": refresh_payload["actions"],
            "voice": refresh_payload["voice"],
            "orb": refresh_payload["orb"],
            "current_work": refresh_payload["current_work"],
            "shift_report": refresh_payload["shift_report"],
            "repo_drilldown": refresh_payload["repo_drilldown"],
            "capability_library": refresh_payload["capability_library"],
            "swarm": refresh_payload["swarm"],
            "federation": refresh_payload["federation"],
            "approval_queue": refresh_payload["approval_queue"],
            "blocked_actions": refresh_payload["blocked_actions"],
            "action_deck": refresh_payload["action_deck"],
            "apprenticeship_surface": refresh_payload["apprenticeship_surface"],
            "execution_journal": refresh_payload["execution_journal"],
            "execution_feed": refresh_payload["execution_feed"],
            "dashboard": refresh_payload["dashboard"],
            "missions": refresh_payload["missions"],
            "incidents": refresh_payload["incidents"],
            "inbox": refresh_payload["inbox"],
            "runs": refresh_payload["runs"],
            "fabric": refresh_payload["fabric"],
        }

    @app.post("/api/federation/nodes/{node_id}/approvals/{approval_id}/reject")
    def hud_federation_approval_reject(
        node_id: str,
        approval_id: str,
        request: Request,
        payload: ControlRemoteApprovalDecisionRequest | None = None,
    ) -> dict[str, object]:
        result = federation_remote_approval_reject(
            node_id=node_id,
            approval_id=approval_id,
            request=request,
            payload=payload,
        )
        refresh_payload = _build_hud_payload()
        return {
            **refresh_payload,
            **result,
            "snapshot": refresh_payload["snapshot"],
            "actions": refresh_payload["actions"],
            "voice": refresh_payload["voice"],
            "orb": refresh_payload["orb"],
            "current_work": refresh_payload["current_work"],
            "shift_report": refresh_payload["shift_report"],
            "repo_drilldown": refresh_payload["repo_drilldown"],
            "capability_library": refresh_payload["capability_library"],
            "swarm": refresh_payload["swarm"],
            "federation": refresh_payload["federation"],
            "approval_queue": refresh_payload["approval_queue"],
            "blocked_actions": refresh_payload["blocked_actions"],
            "action_deck": refresh_payload["action_deck"],
            "apprenticeship_surface": refresh_payload["apprenticeship_surface"],
            "execution_journal": refresh_payload["execution_journal"],
            "execution_feed": refresh_payload["execution_feed"],
            "dashboard": refresh_payload["dashboard"],
            "missions": refresh_payload["missions"],
            "incidents": refresh_payload["incidents"],
            "inbox": refresh_payload["inbox"],
            "runs": refresh_payload["runs"],
            "fabric": refresh_payload["fabric"],
        }

    @app.post("/api/managed-copies/create")
    def hud_managed_copy_create(request: Request, payload: ManagedCopyCreateRequest) -> dict[str, object]:
        result = managed_copy_create(request=request, payload=payload)
        refresh_payload = _build_hud_payload()
        return {
            **refresh_payload,
            **result,
        }

    @app.post("/api/managed-copies/copies/{copy_id}/delta")
    def hud_managed_copy_delta(
        copy_id: str,
        request: Request,
        payload: ManagedCopyDeltaRequest,
    ) -> dict[str, object]:
        result = managed_copy_delta(copy_id=copy_id, request=request, payload=payload)
        refresh_payload = _build_hud_payload()
        return {
            **refresh_payload,
            **result,
        }

    @app.post("/api/managed-copies/copies/{copy_id}/materialize")
    def hud_managed_copy_materialize(copy_id: str, request: Request) -> dict[str, object]:
        result = managed_copy_materialize(copy_id=copy_id, request=request)
        refresh_payload = _build_hud_payload()
        return {
            **refresh_payload,
            **result,
        }

    @app.post("/api/managed-copies/copies/{copy_id}/quarantine")
    def hud_managed_copy_quarantine(
        copy_id: str,
        request: Request,
        payload: ManagedCopyQuarantineRequest,
    ) -> dict[str, object]:
        result = managed_copy_quarantine(copy_id=copy_id, request=request, payload=payload)
        refresh_payload = _build_hud_payload()
        return {
            **refresh_payload,
            **result,
        }

    @app.post("/api/managed-copies/copies/{copy_id}/replace")
    def hud_managed_copy_replace(
        copy_id: str,
        request: Request,
        payload: ManagedCopyReplaceRequest,
    ) -> dict[str, object]:
        result = managed_copy_replace(copy_id=copy_id, request=request, payload=payload)
        refresh_payload = _build_hud_payload()
        return {
            **refresh_payload,
            **result,
        }

    @app.post("/api/swarm/delegate")
    def hud_swarm_delegate(request: Request, payload: SwarmDelegateRequest) -> dict[str, object]:
        result = swarm_delegate(request, payload)
        refresh_payload = _build_hud_payload()
        return {
            **refresh_payload,
            **result,
            "snapshot": refresh_payload["snapshot"],
            "actions": refresh_payload["actions"],
            "voice": refresh_payload["voice"],
            "orb": refresh_payload["orb"],
            "current_work": refresh_payload["current_work"],
            "shift_report": refresh_payload["shift_report"],
            "repo_drilldown": refresh_payload["repo_drilldown"],
            "capability_library": refresh_payload["capability_library"],
            "swarm": refresh_payload["swarm"],
            "federation": refresh_payload["federation"],
            "approval_queue": refresh_payload["approval_queue"],
            "blocked_actions": refresh_payload["blocked_actions"],
            "action_deck": refresh_payload["action_deck"],
            "apprenticeship_surface": refresh_payload["apprenticeship_surface"],
            "execution_journal": refresh_payload["execution_journal"],
            "execution_feed": refresh_payload["execution_feed"],
            "dashboard": refresh_payload["dashboard"],
            "missions": refresh_payload["missions"],
            "incidents": refresh_payload["incidents"],
            "inbox": refresh_payload["inbox"],
            "runs": refresh_payload["runs"],
            "fabric": refresh_payload["fabric"],
        }

    @app.post("/api/swarm/delegations/{delegation_id}/lease")
    def hud_swarm_lease(
        delegation_id: str,
        request: Request,
        payload: SwarmLeaseRequest,
    ) -> dict[str, object]:
        result = swarm_lease(delegation_id, request, payload)
        refresh_payload = _build_hud_payload()
        return {
            **refresh_payload,
            **result,
            "snapshot": refresh_payload["snapshot"],
            "actions": refresh_payload["actions"],
            "voice": refresh_payload["voice"],
            "orb": refresh_payload["orb"],
            "current_work": refresh_payload["current_work"],
            "shift_report": refresh_payload["shift_report"],
            "repo_drilldown": refresh_payload["repo_drilldown"],
            "capability_library": refresh_payload["capability_library"],
            "swarm": refresh_payload["swarm"],
            "federation": refresh_payload["federation"],
            "approval_queue": refresh_payload["approval_queue"],
            "blocked_actions": refresh_payload["blocked_actions"],
            "action_deck": refresh_payload["action_deck"],
            "apprenticeship_surface": refresh_payload["apprenticeship_surface"],
            "execution_journal": refresh_payload["execution_journal"],
            "execution_feed": refresh_payload["execution_feed"],
            "dashboard": refresh_payload["dashboard"],
            "missions": refresh_payload["missions"],
            "incidents": refresh_payload["incidents"],
            "inbox": refresh_payload["inbox"],
            "runs": refresh_payload["runs"],
            "fabric": refresh_payload["fabric"],
        }

    @app.post("/api/swarm/delegations/{delegation_id}/complete")
    def hud_swarm_complete(
        delegation_id: str,
        request: Request,
        payload: SwarmCompleteRequest,
    ) -> dict[str, object]:
        result = swarm_complete(delegation_id, request, payload)
        refresh_payload = _build_hud_payload()
        return {
            **refresh_payload,
            **result,
            "snapshot": refresh_payload["snapshot"],
            "actions": refresh_payload["actions"],
            "voice": refresh_payload["voice"],
            "orb": refresh_payload["orb"],
            "current_work": refresh_payload["current_work"],
            "shift_report": refresh_payload["shift_report"],
            "repo_drilldown": refresh_payload["repo_drilldown"],
            "capability_library": refresh_payload["capability_library"],
            "swarm": refresh_payload["swarm"],
            "federation": refresh_payload["federation"],
            "approval_queue": refresh_payload["approval_queue"],
            "blocked_actions": refresh_payload["blocked_actions"],
            "action_deck": refresh_payload["action_deck"],
            "apprenticeship_surface": refresh_payload["apprenticeship_surface"],
            "execution_journal": refresh_payload["execution_journal"],
            "execution_feed": refresh_payload["execution_feed"],
            "dashboard": refresh_payload["dashboard"],
            "missions": refresh_payload["missions"],
            "incidents": refresh_payload["incidents"],
            "inbox": refresh_payload["inbox"],
            "runs": refresh_payload["runs"],
            "fabric": refresh_payload["fabric"],
        }

    @app.post("/api/swarm/delegations/{delegation_id}/fail")
    def hud_swarm_fail(
        delegation_id: str,
        request: Request,
        payload: SwarmFailRequest,
    ) -> dict[str, object]:
        result = swarm_fail(delegation_id, request, payload)
        refresh_payload = _build_hud_payload()
        return {
            **refresh_payload,
            **result,
            "snapshot": refresh_payload["snapshot"],
            "actions": refresh_payload["actions"],
            "voice": refresh_payload["voice"],
            "orb": refresh_payload["orb"],
            "current_work": refresh_payload["current_work"],
            "shift_report": refresh_payload["shift_report"],
            "repo_drilldown": refresh_payload["repo_drilldown"],
            "capability_library": refresh_payload["capability_library"],
            "swarm": refresh_payload["swarm"],
            "federation": refresh_payload["federation"],
            "approval_queue": refresh_payload["approval_queue"],
            "blocked_actions": refresh_payload["blocked_actions"],
            "action_deck": refresh_payload["action_deck"],
            "apprenticeship_surface": refresh_payload["apprenticeship_surface"],
            "execution_journal": refresh_payload["execution_journal"],
            "execution_feed": refresh_payload["execution_feed"],
            "dashboard": refresh_payload["dashboard"],
            "missions": refresh_payload["missions"],
            "incidents": refresh_payload["incidents"],
            "inbox": refresh_payload["inbox"],
            "runs": refresh_payload["runs"],
            "fabric": refresh_payload["fabric"],
        }

    @app.post("/api/swarm/delegations/{delegation_id}/execute")
    def hud_swarm_execute(
        delegation_id: str,
        request: Request,
    ) -> dict[str, object]:
        result = swarm_execute(delegation_id, request)
        refresh_payload = _build_hud_payload()
        return {
            **refresh_payload,
            **result,
            "snapshot": refresh_payload["snapshot"],
            "actions": refresh_payload["actions"],
            "voice": refresh_payload["voice"],
            "orb": refresh_payload["orb"],
            "current_work": refresh_payload["current_work"],
            "shift_report": refresh_payload["shift_report"],
            "repo_drilldown": refresh_payload["repo_drilldown"],
            "capability_library": refresh_payload["capability_library"],
            "swarm": refresh_payload["swarm"],
            "federation": refresh_payload["federation"],
            "approval_queue": refresh_payload["approval_queue"],
            "blocked_actions": refresh_payload["blocked_actions"],
            "action_deck": refresh_payload["action_deck"],
            "apprenticeship_surface": refresh_payload["apprenticeship_surface"],
            "execution_journal": refresh_payload["execution_journal"],
            "execution_feed": refresh_payload["execution_feed"],
            "dashboard": refresh_payload["dashboard"],
            "missions": refresh_payload["missions"],
            "incidents": refresh_payload["incidents"],
            "inbox": refresh_payload["inbox"],
            "runs": refresh_payload["runs"],
            "fabric": refresh_payload["fabric"],
        }

    @app.post("/api/swarm/cycle")
    def hud_swarm_cycle(request: Request, payload: SwarmCycleRequest) -> dict[str, object]:
        result = swarm_cycle(request, payload)
        refresh_payload = _build_hud_payload()
        return {
            **refresh_payload,
            **result,
            "snapshot": refresh_payload["snapshot"],
            "actions": refresh_payload["actions"],
            "voice": refresh_payload["voice"],
            "orb": refresh_payload["orb"],
            "current_work": refresh_payload["current_work"],
            "shift_report": refresh_payload["shift_report"],
            "repo_drilldown": refresh_payload["repo_drilldown"],
            "capability_library": refresh_payload["capability_library"],
            "swarm": refresh_payload["swarm"],
            "federation": refresh_payload["federation"],
            "approval_queue": refresh_payload["approval_queue"],
            "blocked_actions": refresh_payload["blocked_actions"],
            "action_deck": refresh_payload["action_deck"],
            "apprenticeship_surface": refresh_payload["apprenticeship_surface"],
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

