from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from francis_core.clock import utc_now_iso
from francis_core.workspace_fs import WorkspaceFS
from francis_forge.proposal_engine import propose

from services.observer.app.main import run_cycle as run_observer_cycle
from services.orchestrator.app.routes.missions import execute_mission_tick


def execute_action(
    *,
    action: dict[str, Any],
    run_id: str,
    trace_id: str | None = None,
    fs: WorkspaceFS,
    workspace_root: Path,
    repo_root: Path,
) -> dict[str, Any]:
    kind = str(action.get("kind", ""))
    ts = utc_now_iso()
    normalized_trace_id = str(trace_id or "").strip() or run_id

    if kind == "observer.scan":
        result = run_observer_cycle(
            run_id=f"{run_id}:observer:{uuid4()}",
            repo_root=repo_root,
            workspace_root=workspace_root,
        )
        return {"ok": True, "kind": kind, "ts": ts, "trace_id": normalized_trace_id, "result": result}

    if kind == "mission.tick":
        mission_id = str(action.get("mission_id", ""))
        if not mission_id:
            return {"ok": False, "kind": kind, "ts": ts, "trace_id": normalized_trace_id, "error": "missing mission_id"}
        result = execute_mission_tick(
            mission_id=mission_id,
            run_id=f"{run_id}:mission:{uuid4()}",
            trace_id=normalized_trace_id,
            role="architect",
            idempotency_key=f"autonomy:{run_id}:{mission_id}",
        )
        return {
            "ok": True,
            "kind": kind,
            "ts": ts,
            "trace_id": normalized_trace_id,
            "mission_id": mission_id,
            "result": result,
        }

    if kind == "forge.propose":
        context = action.get("context") if isinstance(action.get("context"), dict) else {}
        proposals = propose(context)
        report = {
            "ts": ts,
            "run_id": run_id,
            "trace_id": normalized_trace_id,
            "kind": kind,
            "context": context,
            "proposals": proposals,
        }
        report_name = f"autonomy_{ts.replace(':', '-').replace('.', '-')}.json"
        fs.write_text(f"forge/reports/{report_name}", json.dumps(report, ensure_ascii=False, indent=2))
        return {
            "ok": True,
            "kind": kind,
            "ts": ts,
            "trace_id": normalized_trace_id,
            "report_path": f"forge/reports/{report_name}",
            "proposal_count": len(proposals),
        }

    if kind == "worker.cycle":
        from services.worker.app.main import run_worker_cycle

        raw_allowlist = action.get("action_allowlist", [])
        allowlist = (
            {str(item).strip().lower() for item in raw_allowlist if str(item).strip()}
            if isinstance(raw_allowlist, list)
            else None
        )
        summary = run_worker_cycle(
            run_id=f"{run_id}:worker:{uuid4()}",
            trace_id=normalized_trace_id,
            max_jobs=int(action.get("max_jobs", 10)),
            max_runtime_seconds=int(action.get("max_runtime_seconds", 30)),
            lease_ttl_seconds=int(action.get("lease_ttl_seconds", 120)),
            lease_heartbeat_seconds=int(action.get("lease_heartbeat_seconds", 15)),
            max_concurrent_cycles=int(action.get("max_concurrent_cycles", 1)),
            action_allowlist=allowlist if allowlist else None,
        )
        return {
            "ok": True,
            "kind": kind,
            "ts": ts,
            "trace_id": normalized_trace_id,
            "result": summary,
            "processed_count": summary.get("processed_count", 0),
            "error_count": summary.get("error_count", 0),
        }

    if kind == "worker.recover_leases":
        from services.worker.app.main import recover_stale_leased_jobs

        raw_classes = action.get("action_classes", [])
        action_classes = (
            {str(item).strip().lower() for item in raw_classes if str(item).strip()}
            if isinstance(raw_classes, list)
            else None
        )
        summary = recover_stale_leased_jobs(
            run_id=f"{run_id}:worker-recover:{uuid4()}",
            trace_id=normalized_trace_id,
            action_classes=action_classes if action_classes else None,
        )
        return {
            "ok": True,
            "kind": kind,
            "ts": ts,
            "trace_id": normalized_trace_id,
            "result": summary,
            "recovered_count": summary.get("recovered_count", 0),
        }

    return {
        "ok": False,
        "kind": kind,
        "ts": ts,
        "trace_id": normalized_trace_id,
        "error": f"unknown action kind: {kind}",
    }
