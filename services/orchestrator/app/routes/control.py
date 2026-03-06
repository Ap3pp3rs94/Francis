from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from francis_core.config import settings
from francis_core.workspace_fs import WorkspaceFS

from services.orchestrator.app.control_state import (
    VALID_MODES,
    load_or_init_control_state,
    set_mode,
    set_scope,
)

router = APIRouter(tags=["control"])

_workspace_root = Path(settings.workspace_root).resolve()
_repo_root = _workspace_root.parent
_fs = WorkspaceFS(
    roots=[_workspace_root],
    journal_path=(_workspace_root / "journals" / "fs.jsonl").resolve(),
)


class ControlModeRequest(BaseModel):
    mode: str = Field(description="observe|assist|pilot|away")
    kill_switch: bool | None = None


class ControlScopeRequest(BaseModel):
    repos: list[str] | None = None
    workspaces: list[str] | None = None
    apps: list[str] | None = None


@router.get("/control/mode")
def get_control_mode() -> dict:
    state = load_or_init_control_state(_fs, _repo_root, _workspace_root)
    return {
        "status": "ok",
        "mode": state.get("mode"),
        "kill_switch": state.get("kill_switch"),
        "updated_at": state.get("updated_at"),
    }


@router.put("/control/mode")
def put_control_mode(payload: ControlModeRequest) -> dict:
    if payload.mode.strip().lower() not in VALID_MODES:
        raise HTTPException(status_code=400, detail=f"Invalid mode: {payload.mode}")
    state = set_mode(
        _fs,
        repo_root=_repo_root,
        workspace_root=_workspace_root,
        mode=payload.mode.strip().lower(),
        kill_switch=payload.kill_switch,
    )
    return {
        "status": "ok",
        "mode": state.get("mode"),
        "kill_switch": state.get("kill_switch"),
        "updated_at": state.get("updated_at"),
    }


@router.get("/control/scope")
def get_control_scope() -> dict:
    state = load_or_init_control_state(_fs, _repo_root, _workspace_root)
    return {"status": "ok", "scope": state.get("scopes", {}), "updated_at": state.get("updated_at")}


@router.put("/control/scope")
def put_control_scope(payload: ControlScopeRequest) -> dict:
    state = set_scope(
        _fs,
        repo_root=_repo_root,
        workspace_root=_workspace_root,
        repos=payload.repos,
        workspaces=payload.workspaces,
        apps=payload.apps,
    )
    return {"status": "ok", "scope": state.get("scopes", {}), "updated_at": state.get("updated_at")}

