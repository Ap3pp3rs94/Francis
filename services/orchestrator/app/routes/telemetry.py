from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from francis_core.config import settings
from francis_core.workspace_fs import WorkspaceFS
from francis_policy.rbac import can
from services.orchestrator.app.control_state import check_action_allowed
from services.orchestrator.app.telemetry_connectors import (
    adapt_dev_server_event,
    adapt_git_event,
    adapt_terminal_event,
)
from services.orchestrator.app.telemetry_store import (
    ingest_event,
    load_or_init_config,
    status as telemetry_status,
    update_config,
)

router = APIRouter(tags=["telemetry"])

_workspace_root = Path(settings.workspace_root).resolve()
_repo_root = _workspace_root.parent
_fs = WorkspaceFS(
    roots=[_workspace_root],
    journal_path=(_workspace_root / "journals" / "fs.jsonl").resolve(),
)


class TelemetryConfigRequest(BaseModel):
    enabled: bool | None = None
    allowed_streams: list[str] | None = None
    max_text_chars: int | None = Field(default=None, ge=256, le=20000)
    retention_max_events: int | None = Field(default=None, ge=1, le=200000)
    retention_max_age_hours: int | None = Field(default=None, ge=1, le=2160)


class TelemetryEventRequest(BaseModel):
    stream: str = Field(min_length=1)
    source: str | None = None
    severity: str = "info"
    text: str | None = None
    fields: dict | None = None
    ts: str | None = None


class TerminalConnectorRequest(BaseModel):
    source: str | None = None
    command: str | None = None
    cwd: str | None = None
    exit_code: int | None = None
    stdout: str | None = None
    stderr: str | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    ts: str | None = None


class GitConnectorRequest(BaseModel):
    source: str | None = None
    action: str | None = None
    repo: str | None = None
    branch: str | None = None
    summary: str | None = None
    files: list[str] | None = None
    ts: str | None = None


class DevServerConnectorRequest(BaseModel):
    source: str | None = None
    service: str | None = None
    level: str | None = None
    message: str | None = None
    port: int | None = Field(default=None, ge=1, le=65535)
    ts: str | None = None


def _role_from_request(request: Request) -> str:
    return request.headers.get("x-francis-role", "architect").strip().lower()


def _enforce_rbac(request: Request, action: str) -> None:
    role = _role_from_request(request)
    if not can(role, action):
        raise HTTPException(status_code=403, detail=f"RBAC denied: role={role}, action={action}")


def _enforce_control(action: str, *, mutating: bool) -> None:
    allowed, reason, _state = check_action_allowed(
        _fs,
        repo_root=_repo_root,
        workspace_root=_workspace_root,
        app="telemetry",
        action=action,
        mutating=mutating,
    )
    if not allowed:
        raise HTTPException(status_code=403, detail=f"Control denied: {reason}")


@router.get("/telemetry/config")
def get_telemetry_config(request: Request) -> dict:
    _enforce_rbac(request, "telemetry.read")
    _enforce_control("telemetry.read", mutating=False)
    return {"status": "ok", "config": load_or_init_config(_fs)}


@router.put("/telemetry/config")
def put_telemetry_config(request: Request, payload: TelemetryConfigRequest) -> dict:
    _enforce_rbac(request, "telemetry.write")
    _enforce_control("telemetry.write", mutating=True)
    updated = update_config(
        _fs,
        enabled=payload.enabled,
        allowed_streams=payload.allowed_streams,
        max_text_chars=payload.max_text_chars,
        retention_max_events=payload.retention_max_events,
        retention_max_age_hours=payload.retention_max_age_hours,
    )
    return {"status": "ok", "config": updated}


@router.post("/telemetry/events")
def post_telemetry_event(request: Request, payload: TelemetryEventRequest) -> dict:
    _enforce_rbac(request, "telemetry.write")
    _enforce_control("telemetry.ingest", mutating=False)
    run_id = str(getattr(request.state, "run_id", uuid4()))
    result = ingest_event(
        _fs,
        run_id=run_id,
        stream=payload.stream,
        source=payload.source,
        severity=payload.severity,
        text=payload.text,
        fields=payload.fields,
        ts=payload.ts,
    )
    return {"run_id": run_id, **result}


@router.post("/telemetry/connectors/terminal")
def post_terminal_connector_event(request: Request, payload: TerminalConnectorRequest) -> dict:
    _enforce_rbac(request, "telemetry.write")
    _enforce_control("telemetry.ingest", mutating=False)
    run_id = str(getattr(request.state, "run_id", uuid4()))
    adapted = adapt_terminal_event(
        source=payload.source,
        command=payload.command,
        cwd=payload.cwd,
        exit_code=payload.exit_code,
        stdout=payload.stdout,
        stderr=payload.stderr,
        duration_ms=payload.duration_ms,
        ts=payload.ts,
    )
    result = ingest_event(
        _fs,
        run_id=run_id,
        stream=adapted["stream"],
        source=adapted["source"],
        severity=adapted["severity"],
        text=adapted["text"],
        fields=adapted["fields"],
        ts=adapted.get("ts"),
    )
    return {"run_id": run_id, "connector": "terminal", **result}


@router.post("/telemetry/connectors/git")
def post_git_connector_event(request: Request, payload: GitConnectorRequest) -> dict:
    _enforce_rbac(request, "telemetry.write")
    _enforce_control("telemetry.ingest", mutating=False)
    run_id = str(getattr(request.state, "run_id", uuid4()))
    adapted = adapt_git_event(
        source=payload.source,
        action=payload.action,
        repo=payload.repo,
        branch=payload.branch,
        summary=payload.summary,
        files=payload.files,
        ts=payload.ts,
    )
    result = ingest_event(
        _fs,
        run_id=run_id,
        stream=adapted["stream"],
        source=adapted["source"],
        severity=adapted["severity"],
        text=adapted["text"],
        fields=adapted["fields"],
        ts=adapted.get("ts"),
    )
    return {"run_id": run_id, "connector": "git", **result}


@router.post("/telemetry/connectors/dev-server")
def post_dev_server_connector_event(request: Request, payload: DevServerConnectorRequest) -> dict:
    _enforce_rbac(request, "telemetry.write")
    _enforce_control("telemetry.ingest", mutating=False)
    run_id = str(getattr(request.state, "run_id", uuid4()))
    adapted = adapt_dev_server_event(
        source=payload.source,
        service=payload.service,
        level=payload.level,
        message=payload.message,
        port=payload.port,
        ts=payload.ts,
    )
    result = ingest_event(
        _fs,
        run_id=run_id,
        stream=adapted["stream"],
        source=adapted["source"],
        severity=adapted["severity"],
        text=adapted["text"],
        fields=adapted["fields"],
        ts=adapted.get("ts"),
    )
    return {"run_id": run_id, "connector": "dev_server", **result}


@router.get("/telemetry/status")
def get_telemetry_status(request: Request) -> dict:
    _enforce_rbac(request, "telemetry.read")
    _enforce_control("telemetry.read", mutating=False)
    return {"status": "ok", "telemetry": telemetry_status(_fs)}
