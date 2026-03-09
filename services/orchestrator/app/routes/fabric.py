from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from francis_brain.ledger import RunLedger
from francis_brain.memory_store import SNAPSHOT_PATH, load_snapshot
from francis_brain.recall import query_fabric, rebuild_fabric, summarize_fabric
from francis_core.config import settings
from francis_core.workspace_fs import WorkspaceFS
from francis_policy.rbac import can
from services.orchestrator.app.control_state import check_action_allowed

router = APIRouter(tags=["fabric"])

_workspace_root = Path(settings.workspace_root).resolve()
_repo_root = _workspace_root.parent
_fs = WorkspaceFS(
    roots=[_workspace_root],
    journal_path=(_workspace_root / "journals" / "fs.jsonl").resolve(),
)
_ledger = RunLedger(_fs, rel_path="runs/run_ledger.jsonl")


class FabricQueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=300)
    limit: int = Field(default=8, ge=1, le=25)
    sources: list[str] = Field(default_factory=list)
    run_id: str | None = None
    trace_id: str | None = None
    mission_id: str | None = None
    include_related: bool = True
    refresh: bool = False


class FabricRebuildRequest(BaseModel):
    reason: str = Field(default="manual rebuild", max_length=200)


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
        app="fabric",
        action=action,
        mutating=mutating,
    )
    if not allowed:
        raise HTTPException(status_code=403, detail=f"Control denied: {reason}")


@router.get("/fabric")
def fabric_summary(request: Request, refresh: bool = False) -> dict[str, object]:
    _enforce_control("fabric.read", mutating=False)
    _enforce_rbac(request, "fabric.read")
    summary = summarize_fabric(_fs, refresh=refresh)
    summary["snapshot_path"] = SNAPSHOT_PATH
    summary["persisted"] = load_snapshot(_fs) is not None
    return {"status": "ok", "summary": summary}


@router.post("/fabric/query")
def fabric_query(request: Request, payload: FabricQueryRequest) -> dict[str, object]:
    _enforce_control("fabric.read", mutating=False)
    _enforce_rbac(request, "fabric.read")
    try:
        return query_fabric(
            _fs,
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


@router.post("/fabric/rebuild")
def fabric_rebuild(request: Request, payload: FabricRebuildRequest | None = None) -> dict[str, object]:
    _enforce_control("fabric.rebuild", mutating=True)
    _enforce_rbac(request, "fabric.rebuild")
    run_id = str(getattr(request.state, "run_id", uuid4()))
    snapshot = rebuild_fabric(_fs)
    summary = summarize_fabric(_fs, refresh=False)
    reason = (payload.reason if payload is not None else "manual rebuild").strip() or "manual rebuild"
    _ledger.append(
        run_id=run_id,
        kind="fabric.rebuild",
        summary={
            "artifact_count": summary.get("artifact_count", 0),
            "source_count": summary.get("source_count", 0),
            "citation_ready_count": summary.get("citation_ready_count", 0),
            "reason": reason,
        },
    )
    return {
        "status": "ok",
        "run_id": run_id,
        "summary": summary,
        "snapshot_path": SNAPSHOT_PATH,
        "generated_at": snapshot.get("generated_at"),
    }
