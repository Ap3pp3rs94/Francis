from __future__ import annotations

from typing import Any

from francis_brain.recall import query_fabric, summarize_fabric
from francis_core.workspace_fs import WorkspaceFS
from services.hud.app.state import get_workspace_root


def _build_fs() -> WorkspaceFS:
    workspace_root = get_workspace_root().resolve()
    return WorkspaceFS(
        roots=[workspace_root],
        journal_path=(workspace_root / "journals" / "fs.jsonl").resolve(),
    )


def get_fabric_surface(*, refresh: bool = False) -> dict[str, Any]:
    fs = _build_fs()
    summary = summarize_fabric(fs, refresh=refresh)
    return {
        "status": "ok",
        "surface": "fabric",
        "summary": summary,
    }


def query_fabric_surface(
    *,
    query: str,
    limit: int = 6,
    sources: list[str] | None = None,
    run_id: str | None = None,
    trace_id: str | None = None,
    mission_id: str | None = None,
    include_related: bool = True,
    refresh: bool = False,
) -> dict[str, Any]:
    fs = _build_fs()
    payload = query_fabric(
        fs,
        query=query,
        limit=limit,
        sources=sources,
        run_id=run_id,
        trace_id=trace_id,
        mission_id=mission_id,
        include_related=include_related,
        refresh=refresh,
    )
    payload["surface"] = "fabric"
    return payload
