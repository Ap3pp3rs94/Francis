from __future__ import annotations

from typing import Any

from francis_brain.recall import query_fabric, summarize_fabric
from francis_brain.memory_store import load_snapshot, summarize_snapshot
from francis_core.workspace_fs import WorkspaceFS
from services.hud.app.state import get_workspace_root


def _build_fs() -> WorkspaceFS:
    workspace_root = get_workspace_root().resolve()
    return WorkspaceFS(
        roots=[workspace_root],
        journal_path=(workspace_root / "journals" / "fs.jsonl").resolve(),
    )


def _build_deferred_summary() -> dict[str, Any]:
    summary = summarize_snapshot(None)
    summary["pending"] = True
    summary["note"] = "Fabric summary is deferred until a cached snapshot exists or a full fabric request is made."
    summary["calibration"] = {
        "confidence_counts": {"confirmed": 0, "likely": 0, "uncertain": 0},
        "done_claim_ready_count": 0,
        "stale_current_state_count": 0,
        "local_provenance_count": 0,
        "anchored_provenance_count": 0,
    }
    return summary


def get_fabric_surface(*, refresh: bool = False, defer_if_missing: bool = False) -> dict[str, Any]:
    fs = _build_fs()
    if defer_if_missing and not refresh and load_snapshot(fs) is None:
        return {
            "status": "ok",
            "surface": "fabric",
            "summary": _build_deferred_summary(),
        }
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
