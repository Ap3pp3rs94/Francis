from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from francis_core.workspace_fs import WorkspaceFS
from services.orchestrator.app.autonomy.kernel import run_cycle
from services.orchestrator.app.control_state import check_action_allowed

router = APIRouter(tags=["autonomy"])


class AutonomyCycleRequest(BaseModel):
    max_actions: int = Field(default=2, ge=0, le=10)
    max_runtime_seconds: int = Field(default=10, ge=1, le=120)
    allow_medium: bool = False
    allow_high: bool = False
    stop_on_critical: bool = True


@router.post("/autonomy/cycle")
def autonomy_cycle(request: Request, payload: AutonomyCycleRequest | None = None) -> dict:
    body = payload or AutonomyCycleRequest()
    run_id = str(getattr(request.state, "run_id", uuid4()))
    repo_root = Path(__file__).resolve().parents[4]
    workspace_root = repo_root / "workspace"
    fs = WorkspaceFS(
        roots=[workspace_root.resolve()],
        journal_path=(workspace_root / "journals" / "fs.jsonl").resolve(),
    )
    allowed, reason, _state = check_action_allowed(
        fs,
        repo_root=repo_root.resolve(),
        workspace_root=workspace_root.resolve(),
        app="autonomy",
        action="autonomy.cycle",
        mutating=True,
    )
    if not allowed:
        raise HTTPException(status_code=403, detail=f"Control denied: {reason}")
    return run_cycle(
        run_id=run_id,
        workspace_root=workspace_root.resolve(),
        repo_root=repo_root.resolve(),
        max_actions=body.max_actions,
        max_runtime_seconds=body.max_runtime_seconds,
        allow_medium=body.allow_medium,
        allow_high=body.allow_high,
        stop_on_critical=body.stop_on_critical,
    )
