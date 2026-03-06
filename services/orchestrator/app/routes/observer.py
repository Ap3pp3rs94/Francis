from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request

from francis_core.workspace_fs import WorkspaceFS
from services.observer.app.main import run_cycle
from services.orchestrator.app.control_state import check_action_allowed

router = APIRouter(tags=["observer"])


@router.get("/observer")
def observer(request: Request) -> dict:
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
        app="observer",
        action="observer.scan",
        mutating=True,
    )
    if not allowed:
        raise HTTPException(status_code=403, detail=f"Control denied: {reason}")
    return run_cycle(run_id=run_id, repo_root=repo_root)
