from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from francis_brain.ledger import RunLedger
from francis_core.clock import utc_now_iso
from francis_core.config import settings
from francis_core.workspace_fs import WorkspaceFS
from francis_forge.catalog import list_entries
from francis_policy.rbac import can
from services.observer.app.main import run_cycle as run_observer_cycle

from services.orchestrator.app.approvals_store import pending_count
from services.orchestrator.app.autonomy.action_budget import check_action_budget, load_state as load_budget_state
from services.orchestrator.app.autonomy.decision_engine import build_plan
from services.orchestrator.app.autonomy.event_queue import (
    append_reactor_guardrail_history,
    queue_status as autonomy_queue_status,
    recover_stale_leased_events,
    write_reactor_guardrail_state,
    read_last_dispatch as read_autonomy_last_dispatch,
    read_reactor_guardrail_state as read_autonomy_reactor_guardrail_state,
    read_last_tick as read_autonomy_last_tick,
)
from services.orchestrator.app.autonomy.event_reactor import collect_events
from services.orchestrator.app.autonomy.intent_engine import collect_intents
from services.orchestrator.app.autonomy.trust_calibration import trust_badge
from services.orchestrator.app.control_state import (
    VALID_MODES,
    check_action_allowed,
    load_or_init_control_state,
    set_mode,
)
from services.orchestrator.app.routes.control import (
    ControlRemoteApprovalDecisionRequest,
    ControlRemotePanicRequest,
    ControlRemoteResumeRequest,
    ControlRemoteTakeoverConfirmRequest,
    ControlRemoteTakeoverHandbackRequest,
    ControlRemoteTakeoverRequest,
    ControlTakeoverConfirmRequest,
    ControlTakeoverHandbackExportRequest,
    ControlTakeoverHandbackRequest,
    ControlTakeoverRequest,
    append_takeover_activity,
    control_remote_approval_approve,
    control_remote_approval_reject,
    control_remote_approvals,
    control_remote_feed,
    control_remote_panic,
    control_remote_resume,
    control_remote_state,
    control_remote_takeover_confirm,
    control_remote_takeover_handback,
    control_remote_takeover_request,
    control_takeover_activity,
    control_takeover_confirm,
    control_takeover_handback_export,
    control_takeover_handback,
    control_takeover_handback_package,
    control_takeover_session,
    control_takeover_sessions,
    control_takeover_request,
    control_takeover_state,
)
from services.orchestrator.app.routes.autonomy import (
    AutonomyDispatchRequest,
    AutonomyReactorTickRequest,
    autonomy_dispatch_events,
    autonomy_reactor_tick,
)
from services.orchestrator.app.routes.forge import forge_proposals
from services.orchestrator.app.routes.missions import execute_mission_tick
from services.orchestrator.app.telemetry_store import status as telemetry_status
from services.worker.app.main import recover_stale_leased_jobs, run_worker_cycle

router = APIRouter(tags=["lens"])

_workspace_root = Path(settings.workspace_root).resolve()
_repo_root = _workspace_root.parent
_fs = WorkspaceFS(
    roots=[_workspace_root],
    journal_path=(_workspace_root / "journals" / "fs.jsonl").resolve(),
)
_ledger = RunLedger(_fs, rel_path="runs/run_ledger.jsonl")


class LensExecuteRequest(BaseModel):
    kind: str
    args: dict[str, Any] = Field(default_factory=dict)
    dry_run: bool = False


def _read_jsonl(rel_path: str) -> list[dict[str, Any]]:
    try:
        raw = _fs.read_text(rel_path)
    except Exception:
        return []
    rows: list[dict[str, Any]] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
            if isinstance(parsed, dict):
                rows.append(parsed)
        except Exception:
            continue
    return rows


def _mode_allows_medium_high(mode: str) -> tuple[bool, bool]:
    lowered = mode.lower()
    if lowered == "pilot":
        return (True, False)
    if lowered == "away":
        return (True, False)
    return (False, False)


def _append_jsonl(rel_path: str, row: dict[str, Any]) -> None:
    try:
        raw = _fs.read_text(rel_path)
    except Exception:
        raw = ""
    if raw and not raw.endswith("\n"):
        raw += "\n"
    _fs.write_text(rel_path, raw + json.dumps(row, ensure_ascii=False) + "\n")


def _normalize_trace_id(trace_id: str | None, *, fallback_run_id: str) -> str:
    normalized = str(trace_id or "").strip()
    return normalized or fallback_run_id


def _role_from_request(request: Request) -> str:
    return request.headers.get("x-francis-role", "architect").strip().lower()


def _enforce_action_scope(*, app: str, action: str, mutating: bool = True) -> None:
    allowed, reason, _state = check_action_allowed(
        _fs,
        repo_root=_repo_root,
        workspace_root=_workspace_root,
        app=app,
        action=action,
        mutating=mutating,
    )
    if not allowed:
        raise HTTPException(status_code=403, detail=f"Control denied: {reason}")


def _enforce_rbac(role: str, action: str) -> None:
    if not can(role, action):
        raise HTTPException(status_code=403, detail=f"RBAC denied: role={role}, action={action}")


def _record_lens_execution(
    *,
    run_id: str,
    trace_id: str,
    role: str,
    action_kind: str,
    dry_run: bool,
    ok: bool,
    detail: dict[str, Any],
) -> None:
    takeover_activity = append_takeover_activity(
        run_id=run_id,
        trace_id=trace_id,
        actor=f"lens:{str(role).strip().lower() or 'architect'}",
        kind="lens.action.execute",
        detail={
            "action_kind": action_kind,
            "dry_run": dry_run,
            "ok": ok,
            "result_status": detail.get("status"),
        },
        ok=ok,
    )
    receipt = {
        "id": str(uuid4()),
        "ts": utc_now_iso(),
        "run_id": run_id,
        "trace_id": trace_id,
        "session_id": takeover_activity.get("session_id") if isinstance(takeover_activity, dict) else None,
        "kind": "lens.action.execute",
        "action_kind": action_kind,
        "dry_run": dry_run,
        "ok": ok,
        "detail": detail,
    }
    _append_jsonl("logs/francis.log.jsonl", receipt)
    _append_jsonl("journals/decisions.jsonl", receipt)
    _ledger.append(
        run_id=run_id,
        kind="lens.action.execute",
        summary={
            "trace_id": trace_id,
            "action_kind": action_kind,
            "dry_run": dry_run,
            "ok": ok,
            "result_status": detail.get("status"),
        },
    )


def _execute_lens_action(
    *,
    request: Request,
    kind: str,
    args: dict[str, Any],
    dry_run: bool,
    run_id: str,
    trace_id: str,
    role: str,
) -> dict[str, Any]:
    normalized_kind = str(kind or "").strip().lower()

    if normalized_kind == "control.panic":
        _enforce_action_scope(app="control", action="control.mode", mutating=False)
        before = load_or_init_control_state(_fs, _repo_root, _workspace_root)
        reason = str(args.get("reason", "")).strip() or "lens.action.panic"
        if dry_run:
            return {
                "status": "dry_run",
                "kind": normalized_kind,
                "before": {"mode": before.get("mode"), "kill_switch": before.get("kill_switch")},
                "after": {"mode": before.get("mode"), "kill_switch": True},
                "reason": reason,
            }
        after = set_mode(
            _fs,
            repo_root=_repo_root,
            workspace_root=_workspace_root,
            mode=str(before.get("mode", "pilot")).strip().lower(),
            kill_switch=True,
        )
        return {
            "status": "ok",
            "kind": normalized_kind,
            "before": {"mode": before.get("mode"), "kill_switch": before.get("kill_switch")},
            "after": {"mode": after.get("mode"), "kill_switch": after.get("kill_switch")},
            "reason": reason,
        }

    if normalized_kind == "control.resume":
        _enforce_action_scope(app="control", action="control.mode", mutating=False)
        before = load_or_init_control_state(_fs, _repo_root, _workspace_root)
        requested_mode = str(args.get("mode", before.get("mode", "pilot"))).strip().lower()
        if requested_mode not in VALID_MODES:
            raise HTTPException(status_code=400, detail=f"Invalid mode: {requested_mode}")
        reason = str(args.get("reason", "")).strip() or "lens.action.resume"
        if dry_run:
            return {
                "status": "dry_run",
                "kind": normalized_kind,
                "before": {"mode": before.get("mode"), "kill_switch": before.get("kill_switch")},
                "after": {"mode": requested_mode, "kill_switch": False},
                "reason": reason,
            }
        after = set_mode(
            _fs,
            repo_root=_repo_root,
            workspace_root=_workspace_root,
            mode=requested_mode,
            kill_switch=False,
        )
        return {
            "status": "ok",
            "kind": normalized_kind,
            "before": {"mode": before.get("mode"), "kill_switch": before.get("kill_switch")},
            "after": {"mode": after.get("mode"), "kill_switch": after.get("kill_switch")},
            "reason": reason,
        }

    if normalized_kind == "control.takeover.request":
        _enforce_action_scope(app="control", action="control.mode", mutating=False)
        objective = str(args.get("objective", "")).strip()
        if not objective:
            raise HTTPException(status_code=400, detail="objective is required for control.takeover.request")
        reason = str(args.get("reason", "")).strip()
        repos = [str(item) for item in args.get("repos", []) if isinstance(item, str) and str(item).strip()]
        workspaces = [
            str(item) for item in args.get("workspaces", []) if isinstance(item, str) and str(item).strip()
        ]
        apps = [str(item) for item in args.get("apps", []) if isinstance(item, str) and str(item).strip()]
        payload = {
            "objective": objective,
            "reason": reason,
            "repos": repos if repos else None,
            "workspaces": workspaces if workspaces else None,
            "apps": apps if apps else None,
        }
        if dry_run:
            return {"status": "dry_run", "kind": normalized_kind, "execution_args": payload}
        summary = control_takeover_request(
            request,
            payload=ControlTakeoverRequest(
                objective=objective,
                reason=reason,
                repos=repos if repos else None,
                workspaces=workspaces if workspaces else None,
                apps=apps if apps else None,
            ),
        )
        return {"status": "ok", "kind": normalized_kind, "summary": summary}

    if normalized_kind == "control.takeover.confirm":
        _enforce_action_scope(app="control", action="control.mode", mutating=False)
        confirm = bool(args.get("confirm", True))
        reason = str(args.get("reason", "")).strip()
        mode = str(args.get("mode", "pilot")).strip().lower() or "pilot"
        execution_args = {
            "confirm": confirm,
            "reason": reason,
            "mode": mode,
        }
        if dry_run:
            return {"status": "dry_run", "kind": normalized_kind, "execution_args": execution_args}
        summary = control_takeover_confirm(
            request,
            payload=ControlTakeoverConfirmRequest(
                confirm=confirm,
                reason=reason,
                mode=mode,
            ),
        )
        return {"status": "ok", "kind": normalized_kind, "summary": summary}

    if normalized_kind == "control.takeover.handback":
        _enforce_action_scope(app="control", action="control.mode", mutating=False)
        summary_text = str(args.get("summary", "")).strip()
        verification = args.get("verification", {})
        pending_approvals = max(0, int(args.get("pending_approvals", 0)))
        mode = args.get("mode", "assist")
        reason = str(args.get("reason", "")).strip()
        execution_args = {
            "summary": summary_text,
            "verification": verification if isinstance(verification, dict) else {},
            "pending_approvals": pending_approvals,
            "mode": mode,
            "reason": reason,
        }
        if dry_run:
            return {"status": "dry_run", "kind": normalized_kind, "execution_args": execution_args}
        summary = control_takeover_handback(
            request,
            payload=ControlTakeoverHandbackRequest(
                summary=summary_text,
                verification=verification if isinstance(verification, dict) else {},
                pending_approvals=pending_approvals,
                mode=str(mode).strip().lower() if isinstance(mode, str) and str(mode).strip() else None,
                reason=reason,
            ),
        )
        return {"status": "ok", "kind": normalized_kind, "summary": summary}

    if normalized_kind == "control.takeover.activity":
        _enforce_action_scope(app="control", action="control.takeover.read", mutating=False)
        limit = max(1, min(500, int(args.get("limit", 100))))
        session_id = str(args.get("session_id", "")).strip() or None
        execution_args = {"limit": limit, "session_id": session_id}
        if dry_run:
            return {"status": "dry_run", "kind": normalized_kind, "execution_args": execution_args}
        summary = control_takeover_activity(limit=limit, session_id=session_id)
        return {"status": "ok", "kind": normalized_kind, "execution_args": execution_args, "summary": summary}

    if normalized_kind == "control.takeover.handback.package":
        _enforce_action_scope(app="control", action="control.takeover.read", mutating=False)
        limit = max(1, min(500, int(args.get("limit", 200))))
        session_id = str(args.get("session_id", "")).strip() or None
        execution_args = {"limit": limit, "session_id": session_id}
        if dry_run:
            return {"status": "dry_run", "kind": normalized_kind, "execution_args": execution_args}
        summary = control_takeover_handback_package(limit=limit, session_id=session_id)
        return {"status": "ok", "kind": normalized_kind, "execution_args": execution_args, "summary": summary}

    if normalized_kind == "control.takeover.handback.export":
        _enforce_action_scope(app="control", action="control.takeover.read", mutating=False)
        limit = max(1, min(5000, int(args.get("limit", 300))))
        session_id = str(args.get("session_id", "")).strip() or None
        reason = str(args.get("reason", "")).strip()
        execution_args = {"limit": limit, "session_id": session_id, "reason": reason}
        if dry_run:
            return {"status": "dry_run", "kind": normalized_kind, "execution_args": execution_args}
        summary = control_takeover_handback_export(
            request,
            payload=ControlTakeoverHandbackExportRequest(
                session_id=session_id,
                limit=limit,
                reason=reason,
            ),
        )
        return {"status": "ok", "kind": normalized_kind, "execution_args": execution_args, "summary": summary}

    if normalized_kind == "control.takeover.sessions":
        _enforce_action_scope(app="control", action="control.takeover.read", mutating=False)
        limit = max(1, min(200, int(args.get("limit", 20))))
        execution_args = {"limit": limit}
        if dry_run:
            return {"status": "dry_run", "kind": normalized_kind, "execution_args": execution_args}
        summary = control_takeover_sessions(limit=limit)
        return {"status": "ok", "kind": normalized_kind, "execution_args": execution_args, "summary": summary}

    if normalized_kind == "control.takeover.session":
        _enforce_action_scope(app="control", action="control.takeover.read", mutating=False)
        session_id = str(args.get("session_id", "")).strip()
        if not session_id:
            raise HTTPException(status_code=400, detail="session_id is required for control.takeover.session")
        limit = max(1, min(500, int(args.get("limit", 200))))
        execution_args = {"session_id": session_id, "limit": limit}
        if dry_run:
            return {"status": "dry_run", "kind": normalized_kind, "execution_args": execution_args}
        summary = control_takeover_session(session_id=session_id, limit=limit)
        return {"status": "ok", "kind": normalized_kind, "execution_args": execution_args, "summary": summary}

    if normalized_kind == "control.remote.state":
        _enforce_action_scope(app="control", action="control.remote.read", mutating=False)
        _enforce_rbac(role, "approvals.read")
        approval_limit = max(1, min(100, int(args.get("approval_limit", 10))))
        session_limit = max(1, min(50, int(args.get("session_limit", 5))))
        execution_args = {"approval_limit": approval_limit, "session_limit": session_limit}
        if dry_run:
            return {"status": "dry_run", "kind": normalized_kind, "execution_args": execution_args}
        summary = control_remote_state(request, approval_limit=approval_limit, session_limit=session_limit)
        return {"status": "ok", "kind": normalized_kind, "execution_args": execution_args, "summary": summary}

    if normalized_kind == "control.remote.approvals":
        _enforce_action_scope(app="control", action="control.remote.read", mutating=False)
        _enforce_rbac(role, "approvals.read")
        status = str(args.get("status", "pending")).strip().lower() or "pending"
        action_filter = str(args.get("action", "")).strip() or None
        limit = max(1, min(200, int(args.get("limit", 50))))
        execution_args = {"status": status, "action": action_filter, "limit": limit}
        if dry_run:
            return {"status": "dry_run", "kind": normalized_kind, "execution_args": execution_args}
        summary = control_remote_approvals(
            request,
            status=status,
            action=action_filter,
            limit=limit,
        )
        return {"status": "ok", "kind": normalized_kind, "execution_args": execution_args, "summary": summary}

    if normalized_kind == "control.remote.feed":
        _enforce_action_scope(app="control", action="control.remote.read", mutating=False)
        _enforce_rbac(role, "approvals.read")
        limit = max(1, min(1000, int(args.get("limit", 100))))
        cursor = str(args.get("cursor", "")).strip() or None
        session_id = str(args.get("session_id", "")).strip() or None
        execution_args = {"limit": limit, "cursor": cursor, "session_id": session_id}
        if dry_run:
            return {"status": "dry_run", "kind": normalized_kind, "execution_args": execution_args}
        summary = control_remote_feed(
            request,
            limit=limit,
            cursor=cursor,
            session_id=session_id,
        )
        return {"status": "ok", "kind": normalized_kind, "execution_args": execution_args, "summary": summary}

    if normalized_kind == "control.remote.panic":
        _enforce_action_scope(app="control", action="control.remote.write", mutating=False)
        _enforce_rbac(role, "control.remote.write")
        reason = str(args.get("reason", "")).strip()
        session_id = str(args.get("session_id", "")).strip() or None
        execution_args = {"reason": reason, "session_id": session_id}
        if dry_run:
            return {"status": "dry_run", "kind": normalized_kind, "execution_args": execution_args}
        summary = control_remote_panic(
            request,
            payload=ControlRemotePanicRequest(reason=reason, session_id=session_id),
        )
        return {"status": "ok", "kind": normalized_kind, "execution_args": execution_args, "summary": summary}

    if normalized_kind == "control.remote.resume":
        _enforce_action_scope(app="control", action="control.remote.write", mutating=False)
        _enforce_rbac(role, "control.remote.write")
        reason = str(args.get("reason", "")).strip()
        mode = str(args.get("mode", "pilot")).strip().lower()
        if mode not in VALID_MODES:
            raise HTTPException(status_code=400, detail=f"Invalid mode: {mode}")
        session_id = str(args.get("session_id", "")).strip() or None
        execution_args = {"reason": reason, "mode": mode, "session_id": session_id}
        if dry_run:
            return {"status": "dry_run", "kind": normalized_kind, "execution_args": execution_args}
        summary = control_remote_resume(
            request,
            payload=ControlRemoteResumeRequest(reason=reason, mode=mode, session_id=session_id),
        )
        return {"status": "ok", "kind": normalized_kind, "execution_args": execution_args, "summary": summary}

    if normalized_kind == "control.remote.takeover.request":
        _enforce_action_scope(app="control", action="control.remote.write", mutating=False)
        _enforce_rbac(role, "control.remote.write")
        objective = str(args.get("objective", "")).strip()
        if not objective:
            raise HTTPException(status_code=400, detail="objective is required for control.remote.takeover.request")
        reason = str(args.get("reason", "")).strip()
        repos = [str(item) for item in args.get("repos", []) if isinstance(item, str) and str(item).strip()]
        workspaces = [
            str(item) for item in args.get("workspaces", []) if isinstance(item, str) and str(item).strip()
        ]
        apps = [str(item) for item in args.get("apps", []) if isinstance(item, str) and str(item).strip()]
        execution_args = {
            "objective": objective,
            "reason": reason,
            "repos": repos if repos else None,
            "workspaces": workspaces if workspaces else None,
            "apps": apps if apps else None,
        }
        if dry_run:
            return {"status": "dry_run", "kind": normalized_kind, "execution_args": execution_args}
        summary = control_remote_takeover_request(
            request,
            payload=ControlRemoteTakeoverRequest(
                objective=objective,
                reason=reason,
                repos=repos if repos else None,
                workspaces=workspaces if workspaces else None,
                apps=apps if apps else None,
            ),
        )
        return {"status": "ok", "kind": normalized_kind, "execution_args": execution_args, "summary": summary}

    if normalized_kind == "control.remote.takeover.confirm":
        _enforce_action_scope(app="control", action="control.remote.write", mutating=False)
        _enforce_rbac(role, "control.remote.write")
        confirm = bool(args.get("confirm", True))
        reason = str(args.get("reason", "")).strip()
        mode = str(args.get("mode", "pilot")).strip().lower() or "pilot"
        session_id = str(args.get("session_id", "")).strip() or None
        execution_args = {
            "confirm": confirm,
            "reason": reason,
            "mode": mode,
            "session_id": session_id,
        }
        if dry_run:
            return {"status": "dry_run", "kind": normalized_kind, "execution_args": execution_args}
        summary = control_remote_takeover_confirm(
            request,
            payload=ControlRemoteTakeoverConfirmRequest(
                confirm=confirm,
                reason=reason,
                mode=mode,
                session_id=session_id,
            ),
        )
        return {"status": "ok", "kind": normalized_kind, "execution_args": execution_args, "summary": summary}

    if normalized_kind == "control.remote.takeover.handback":
        _enforce_action_scope(app="control", action="control.remote.write", mutating=False)
        _enforce_rbac(role, "control.remote.write")
        summary_text = str(args.get("summary", "")).strip()
        verification = args.get("verification", {})
        pending_approvals = max(0, int(args.get("pending_approvals", 0)))
        mode = args.get("mode", "assist")
        reason = str(args.get("reason", "")).strip()
        session_id = str(args.get("session_id", "")).strip() or None
        execution_args = {
            "summary": summary_text,
            "verification": verification if isinstance(verification, dict) else {},
            "pending_approvals": pending_approvals,
            "mode": mode,
            "reason": reason,
            "session_id": session_id,
        }
        if dry_run:
            return {"status": "dry_run", "kind": normalized_kind, "execution_args": execution_args}
        summary = control_remote_takeover_handback(
            request,
            payload=ControlRemoteTakeoverHandbackRequest(
                summary=summary_text,
                verification=verification if isinstance(verification, dict) else {},
                pending_approvals=pending_approvals,
                mode=str(mode).strip().lower() if isinstance(mode, str) and str(mode).strip() else None,
                reason=reason,
                session_id=session_id,
            ),
        )
        return {"status": "ok", "kind": normalized_kind, "execution_args": execution_args, "summary": summary}

    if normalized_kind == "control.remote.approval.approve":
        _enforce_action_scope(app="control", action="control.remote.write", mutating=False)
        _enforce_rbac(role, "control.remote.write")
        _enforce_rbac(role, "approvals.decide")
        approval_id = str(args.get("approval_id", "")).strip()
        if not approval_id:
            raise HTTPException(status_code=400, detail="approval_id is required for control.remote.approval.approve")
        note = str(args.get("note", "")).strip()
        session_id = str(args.get("session_id", "")).strip() or None
        execution_args = {"approval_id": approval_id, "note": note, "session_id": session_id}
        if dry_run:
            return {"status": "dry_run", "kind": normalized_kind, "execution_args": execution_args}
        summary = control_remote_approval_approve(
            approval_id=approval_id,
            request=request,
            payload=ControlRemoteApprovalDecisionRequest(note=note, session_id=session_id),
        )
        return {"status": "ok", "kind": normalized_kind, "execution_args": execution_args, "summary": summary}

    if normalized_kind == "control.remote.approval.reject":
        _enforce_action_scope(app="control", action="control.remote.write", mutating=False)
        _enforce_rbac(role, "control.remote.write")
        _enforce_rbac(role, "approvals.decide")
        approval_id = str(args.get("approval_id", "")).strip()
        if not approval_id:
            raise HTTPException(status_code=400, detail="approval_id is required for control.remote.approval.reject")
        note = str(args.get("note", "")).strip()
        session_id = str(args.get("session_id", "")).strip() or None
        execution_args = {"approval_id": approval_id, "note": note, "session_id": session_id}
        if dry_run:
            return {"status": "dry_run", "kind": normalized_kind, "execution_args": execution_args}
        summary = control_remote_approval_reject(
            approval_id=approval_id,
            request=request,
            payload=ControlRemoteApprovalDecisionRequest(note=note, session_id=session_id),
        )
        return {"status": "ok", "kind": normalized_kind, "execution_args": execution_args, "summary": summary}

    if normalized_kind == "worker.cycle":
        _enforce_rbac(role, "worker.cycle")
        _enforce_action_scope(app="worker", action="worker.cycle")
        max_jobs = max(1, min(500, int(args.get("max_jobs", 20))))
        max_runtime_seconds = max(1, min(600, int(args.get("max_runtime_seconds", 60))))
        allowlist = {
            str(item).strip().lower()
            for item in args.get("action_allowlist", [])
            if isinstance(item, str) and str(item).strip()
        }
        execution_args = {
            "max_jobs": max_jobs,
            "max_runtime_seconds": max_runtime_seconds,
            "action_allowlist": sorted(allowlist) if allowlist else None,
        }
        if dry_run:
            return {"status": "dry_run", "kind": normalized_kind, "execution_args": execution_args}
        summary = run_worker_cycle(
            run_id=f"{run_id}:lens-worker:{uuid4()}",
            trace_id=trace_id,
            max_jobs=max_jobs,
            max_runtime_seconds=max_runtime_seconds,
            action_allowlist=allowlist if allowlist else None,
        )
        return {"status": "ok", "kind": normalized_kind, "execution_args": execution_args, "summary": summary}

    if normalized_kind == "worker.recover_leases":
        _enforce_rbac(role, "worker.cycle")
        _enforce_action_scope(app="worker", action="worker.recover")
        action_classes = {
            str(item).strip().lower()
            for item in args.get("action_classes", [])
            if isinstance(item, str) and str(item).strip()
        }
        if dry_run:
            return {
                "status": "dry_run",
                "kind": normalized_kind,
                "execution_args": {"action_classes": sorted(action_classes) if action_classes else None},
            }
        summary = recover_stale_leased_jobs(
            run_id=f"{run_id}:lens-worker-recover:{uuid4()}",
            trace_id=trace_id,
            action_classes=action_classes if action_classes else None,
        )
        return {"status": "ok", "kind": normalized_kind, "summary": summary}

    if normalized_kind == "autonomy.recover":
        _enforce_rbac(role, "autonomy.recover")
        _enforce_action_scope(app="autonomy", action="autonomy.recover")
        lease_ttl_seconds = max(15, min(3600, int(args.get("lease_ttl_seconds", 300))))
        max_recover = max(1, min(1000, int(args.get("max_recover", 100))))
        if dry_run:
            return {
                "status": "dry_run",
                "kind": normalized_kind,
                "execution_args": {
                    "lease_ttl_seconds": lease_ttl_seconds,
                    "max_recover": max_recover,
                },
            }
        recovery = recover_stale_leased_events(
            _fs,
            run_id=f"{run_id}:lens-autonomy-recover:{uuid4()}",
            lease_ttl_seconds=lease_ttl_seconds,
            max_recover=max_recover,
        )
        return {"status": "ok", "kind": normalized_kind, "recovery": recovery}

    if normalized_kind == "autonomy.dispatch":
        _enforce_rbac(role, "autonomy.dispatch")
        _enforce_action_scope(app="autonomy", action="autonomy.dispatch")
        max_events = max(1, min(100, int(args.get("max_events", 5))))
        max_actions = max(0, min(10, int(args.get("max_actions", 2))))
        max_runtime_seconds = max(1, min(120, int(args.get("max_runtime_seconds", 10))))
        max_dispatch_actions = max(0, min(200, int(args.get("max_dispatch_actions", 10))))
        max_dispatch_runtime_seconds = max(1, min(600, int(args.get("max_dispatch_runtime_seconds", 30))))
        max_attempts = max(1, min(20, int(args.get("max_attempts", 3))))
        retry_backoff_seconds = max(0, min(3600, int(args.get("retry_backoff_seconds", 60))))
        lease_ttl_seconds = max(15, min(3600, int(args.get("lease_ttl_seconds", 300))))
        recover_stale_leases = bool(args.get("recover_stale_leases", True))
        allow_medium = bool(args.get("allow_medium", False))
        allow_high = bool(args.get("allow_high", False))
        stop_on_critical = bool(args.get("stop_on_critical", True))
        execution_args = {
            "max_events": max_events,
            "max_actions": max_actions,
            "max_runtime_seconds": max_runtime_seconds,
            "max_dispatch_actions": max_dispatch_actions,
            "max_dispatch_runtime_seconds": max_dispatch_runtime_seconds,
            "max_attempts": max_attempts,
            "retry_backoff_seconds": retry_backoff_seconds,
            "lease_ttl_seconds": lease_ttl_seconds,
            "recover_stale_leases": recover_stale_leases,
            "allow_medium": allow_medium,
            "allow_high": allow_high,
            "stop_on_critical": stop_on_critical,
        }
        if dry_run:
            return {"status": "dry_run", "kind": normalized_kind, "execution_args": execution_args}
        summary = autonomy_dispatch_events(
            request,
            payload=AutonomyDispatchRequest(
                max_events=max_events,
                max_actions=max_actions,
                max_runtime_seconds=max_runtime_seconds,
                max_dispatch_actions=max_dispatch_actions,
                max_dispatch_runtime_seconds=max_dispatch_runtime_seconds,
                max_attempts=max_attempts,
                retry_backoff_seconds=retry_backoff_seconds,
                lease_ttl_seconds=lease_ttl_seconds,
                recover_stale_leases=recover_stale_leases,
                allow_medium=allow_medium,
                allow_high=allow_high,
                stop_on_critical=stop_on_critical,
            ),
        )
        return {"status": "ok", "kind": normalized_kind, "execution_args": execution_args, "summary": summary}

    if normalized_kind == "autonomy.reactor.tick":
        _enforce_rbac(role, "autonomy.enqueue")
        _enforce_rbac(role, "autonomy.dispatch")
        _enforce_action_scope(app="autonomy", action="autonomy.enqueue")
        _enforce_action_scope(app="autonomy", action="autonomy.dispatch")
        max_collect_events = max(1, min(100, int(args.get("max_collect_events", 20))))
        max_events = max(1, min(100, int(args.get("max_events", 5))))
        max_actions = max(0, min(10, int(args.get("max_actions", 2))))
        max_runtime_seconds = max(1, min(120, int(args.get("max_runtime_seconds", 10))))
        max_dispatch_actions = max(0, min(200, int(args.get("max_dispatch_actions", 10))))
        max_dispatch_runtime_seconds = max(1, min(600, int(args.get("max_dispatch_runtime_seconds", 30))))
        max_attempts = max(1, min(20, int(args.get("max_attempts", 3))))
        retry_backoff_seconds = max(0, min(3600, int(args.get("retry_backoff_seconds", 60))))
        retry_pressure_threshold = max(0, min(500, int(args.get("retry_pressure_threshold", 5))))
        retry_pressure_consecutive_ticks = max(1, min(50, int(args.get("retry_pressure_consecutive_ticks", 3))))
        retry_pressure_cooldown_ticks = max(1, min(50, int(args.get("retry_pressure_cooldown_ticks", 2))))
        lease_ttl_seconds = max(15, min(3600, int(args.get("lease_ttl_seconds", 300))))
        recover_stale_leases = bool(args.get("recover_stale_leases", True))
        allow_medium = bool(args.get("allow_medium", False))
        allow_high = bool(args.get("allow_high", False))
        stop_on_critical = bool(args.get("stop_on_critical", True))
        include_types = [
            str(item).strip()
            for item in args.get("include_types", [])
            if isinstance(item, str) and str(item).strip()
        ]
        execution_args = {
            "max_collect_events": max_collect_events,
            "include_types": include_types,
            "max_events": max_events,
            "max_actions": max_actions,
            "max_runtime_seconds": max_runtime_seconds,
            "max_dispatch_actions": max_dispatch_actions,
            "max_dispatch_runtime_seconds": max_dispatch_runtime_seconds,
            "max_attempts": max_attempts,
            "retry_backoff_seconds": retry_backoff_seconds,
            "retry_pressure_threshold": retry_pressure_threshold,
            "retry_pressure_consecutive_ticks": retry_pressure_consecutive_ticks,
            "retry_pressure_cooldown_ticks": retry_pressure_cooldown_ticks,
            "lease_ttl_seconds": lease_ttl_seconds,
            "recover_stale_leases": recover_stale_leases,
            "allow_medium": allow_medium,
            "allow_high": allow_high,
            "stop_on_critical": stop_on_critical,
        }
        if dry_run:
            return {"status": "dry_run", "kind": normalized_kind, "execution_args": execution_args}
        summary = autonomy_reactor_tick(
            request,
            payload=AutonomyReactorTickRequest(
                max_collect_events=max_collect_events,
                include_types=include_types,
                max_events=max_events,
                max_actions=max_actions,
                max_runtime_seconds=max_runtime_seconds,
                max_dispatch_actions=max_dispatch_actions,
                max_dispatch_runtime_seconds=max_dispatch_runtime_seconds,
                max_attempts=max_attempts,
                retry_backoff_seconds=retry_backoff_seconds,
                retry_pressure_threshold=retry_pressure_threshold,
                retry_pressure_consecutive_ticks=retry_pressure_consecutive_ticks,
                retry_pressure_cooldown_ticks=retry_pressure_cooldown_ticks,
                lease_ttl_seconds=lease_ttl_seconds,
                recover_stale_leases=recover_stale_leases,
                allow_medium=allow_medium,
                allow_high=allow_high,
                stop_on_critical=stop_on_critical,
            ),
        )
        return {"status": "ok", "kind": normalized_kind, "execution_args": execution_args, "summary": summary}

    if normalized_kind == "observer.scan":
        _enforce_action_scope(app="observer", action="observer.scan")
        if dry_run:
            return {"status": "dry_run", "kind": normalized_kind}
        summary = run_observer_cycle(
            run_id=f"{run_id}:lens-observer:{uuid4()}",
            repo_root=_repo_root,
            workspace_root=_workspace_root,
        )
        return {"status": "ok", "kind": normalized_kind, "summary": summary}

    if normalized_kind == "mission.tick":
        _enforce_rbac(role, "missions.tick")
        _enforce_action_scope(app="missions", action="missions.tick")
        mission_id = str(args.get("mission_id", "")).strip()
        if not mission_id:
            raise HTTPException(status_code=400, detail="mission_id is required for mission.tick")
        force_fail = bool(args.get("force_fail", False))
        reason = str(args.get("reason", "")).strip()
        idempotency_key = str(args.get("idempotency_key", "")).strip() or None
        if dry_run:
            return {
                "status": "dry_run",
                "kind": normalized_kind,
                "execution_args": {
                    "mission_id": mission_id,
                    "force_fail": force_fail,
                    "reason": reason,
                    "idempotency_key": idempotency_key,
                },
            }
        summary = execute_mission_tick(
            mission_id=mission_id,
            run_id=f"{run_id}:lens-mission:{uuid4()}",
            trace_id=trace_id,
            role=role,
            force_fail=force_fail,
            reason=reason,
            idempotency_key=idempotency_key,
        )
        return {"status": "ok", "kind": normalized_kind, "summary": summary}

    if normalized_kind == "forge.propose":
        _enforce_rbac(role, "forge.propose")
        _enforce_action_scope(app="forge", action="forge.propose", mutating=False)
        if dry_run:
            return {"status": "dry_run", "kind": normalized_kind}
        summary = forge_proposals(request)
        return {"status": "ok", "kind": normalized_kind, "summary": summary}

    if normalized_kind == "autonomy.reactor.guardrail.reset":
        _enforce_rbac(role, "autonomy.guardrail.reset")
        _enforce_action_scope(app="autonomy", action="autonomy.guardrail.reset")
        reason = str(args.get("reason", "")).strip() or "lens.guardrail.reset"
        before = read_autonomy_reactor_guardrail_state(_fs)
        if dry_run:
            return {
                "status": "dry_run",
                "kind": normalized_kind,
                "reason": reason,
                "before": before,
                "after": {
                    **before,
                    "consecutive_retry_pressure_ticks": 0,
                    "cooldown_remaining_ticks": 0,
                    "last_reason": reason,
                },
            }
        after = write_reactor_guardrail_state(
            _fs,
            payload={
                **before,
                "consecutive_retry_pressure_ticks": 0,
                "cooldown_remaining_ticks": 0,
                "last_reason": reason,
            },
        )
        receipt = {
            "id": str(uuid4()),
            "ts": utc_now_iso(),
            "run_id": run_id,
            "trace_id": trace_id,
            "kind": "autonomy.reactor.guardrail.reset",
            "reason": reason,
            "before": before,
            "after": after,
        }
        append_reactor_guardrail_history(_fs, payload=receipt)
        return {"status": "ok", "kind": normalized_kind, "receipt": receipt}

    raise HTTPException(status_code=400, detail=f"Unsupported lens action kind: {normalized_kind}")


def _with_execute_hint(chip: dict[str, Any]) -> dict[str, Any]:
    kind = str(chip.get("kind", "")).strip()
    hinted = {
        **chip,
        "execute_via": {
            "endpoint": "/lens/actions/execute",
            "method": "POST",
            "payload": {"kind": kind, "args": {}},
        },
    }
    if kind == "mission.tick":
        hinted["execute_via"]["payload"]["args"] = {"mission_id": "<required>"}
    elif kind == "control.takeover.request":
        hinted["execute_via"]["payload"]["args"] = {"objective": "<required>", "reason": ""}
    elif kind == "control.takeover.confirm":
        hinted["execute_via"]["payload"]["args"] = {"confirm": True, "mode": "pilot", "reason": ""}
    elif kind == "control.takeover.handback":
        hinted["execute_via"]["payload"]["args"] = {
            "summary": "",
            "verification": {},
            "pending_approvals": 0,
            "mode": "assist",
            "reason": "",
        }
    elif kind == "control.takeover.activity":
        hinted["execute_via"]["payload"]["args"] = {"limit": 50, "session_id": ""}
    elif kind == "control.takeover.handback.package":
        hinted["execute_via"]["payload"]["args"] = {"limit": 120, "session_id": ""}
    elif kind == "control.takeover.handback.export":
        hinted["execute_via"]["payload"]["args"] = {"limit": 300, "session_id": "", "reason": ""}
    elif kind == "control.takeover.sessions":
        hinted["execute_via"]["payload"]["args"] = {"limit": 20}
    elif kind == "control.takeover.session":
        hinted["execute_via"]["payload"]["args"] = {"session_id": "<required>", "limit": 200}
    elif kind == "control.remote.state":
        hinted["execute_via"]["payload"]["args"] = {"approval_limit": 10, "session_limit": 5}
    elif kind == "control.remote.approvals":
        hinted["execute_via"]["payload"]["args"] = {"status": "pending", "limit": 50}
    elif kind == "control.remote.feed":
        hinted["execute_via"]["payload"]["args"] = {"limit": 100, "cursor": "", "session_id": ""}
    elif kind == "control.remote.panic":
        hinted["execute_via"]["payload"]["args"] = {"reason": "", "session_id": ""}
    elif kind == "control.remote.resume":
        hinted["execute_via"]["payload"]["args"] = {"reason": "", "mode": "pilot", "session_id": ""}
    elif kind == "control.remote.takeover.request":
        hinted["execute_via"]["payload"]["args"] = {"objective": "<required>", "reason": ""}
    elif kind == "control.remote.takeover.confirm":
        hinted["execute_via"]["payload"]["args"] = {"confirm": True, "mode": "pilot", "reason": "", "session_id": ""}
    elif kind == "control.remote.takeover.handback":
        hinted["execute_via"]["payload"]["args"] = {
            "summary": "",
            "verification": {},
            "pending_approvals": 0,
            "mode": "assist",
            "reason": "",
            "session_id": "",
        }
    elif kind == "control.remote.approval.approve":
        hinted["execute_via"]["payload"]["args"] = {"approval_id": "<required>", "note": "", "session_id": ""}
    elif kind == "control.remote.approval.reject":
        hinted["execute_via"]["payload"]["args"] = {"approval_id": "<required>", "note": "", "session_id": ""}
    return hinted


@router.get("/lens/state")
def lens_state(request: Request) -> dict:
    allowed, reason, control = check_action_allowed(
        _fs,
        repo_root=_repo_root,
        workspace_root=_workspace_root,
        app="lens",
        action="lens.state",
        mutating=False,
    )
    if not allowed:
        raise HTTPException(status_code=403, detail=f"Control denied: {reason}")

    event_state = collect_events(_fs)
    intent_state = collect_intents(_fs)
    telemetry = telemetry_status(_fs)
    autonomy_queue = autonomy_queue_status(_fs, limit=200)
    autonomy_last_dispatch = read_autonomy_last_dispatch(_fs)
    autonomy_last_tick = read_autonomy_last_tick(_fs)
    autonomy_guardrail = read_autonomy_reactor_guardrail_state(_fs)
    dispatch_verification = (
        autonomy_last_dispatch.get("verification", {})
        if isinstance(autonomy_last_dispatch.get("verification"), dict)
        else {}
    )
    tick_verification = (
        autonomy_last_tick.get("verification", {})
        if isinstance(autonomy_last_tick.get("verification"), dict)
        else {}
    )
    last_dispatch_config = (
        autonomy_last_dispatch.get("config", {}) if isinstance(autonomy_last_dispatch, dict) else {}
    )
    halted_reason = str(autonomy_last_dispatch.get("halted_reason", "")).strip()
    dispatch_halted = bool(halted_reason) and halted_reason != "completed"
    dispatch_budget_halt = halted_reason in {"dispatch_action_budget_exceeded", "dispatch_runtime_budget_exceeded"}
    dispatch_critical_halt = halted_reason in {"critical_incident_present", "critical_anomaly"}
    tick_dispatch = autonomy_last_tick.get("dispatch", {}) if isinstance(autonomy_last_tick, dict) else {}
    tick_collect = autonomy_last_tick.get("collect", {}) if isinstance(autonomy_last_tick, dict) else {}
    tick_halted_reason = str(tick_dispatch.get("halted_reason", "")).strip()
    tick_halted = bool(tick_halted_reason) and tick_halted_reason != "completed"
    guardrail_cooldown_active = int(autonomy_guardrail.get("cooldown_remaining_ticks", 0)) > 0
    manual_reset_available = str(control.get("mode", "observe")).strip().lower() == "pilot"
    autonomy_high_risk_due = sum(
        1
        for row in autonomy_queue.get("queued", [])
        if str(row.get("risk_tier", "")).strip().lower() in {"high", "critical"}
    )
    autonomy_leased_expired_count = int(autonomy_queue.get("leased_expired_count", 0))
    autonomy_retry_pressure = int(autonomy_queue.get("queued_retry_count", 0))
    catalog_entries = list_entries(_fs)
    staged_count = sum(1 for entry in catalog_entries if str(entry.get("status", "")).lower() == "staged")
    pending_approvals = pending_count(_fs) + len(_read_jsonl("queue/deadletter.jsonl")) + staged_count

    mode = str(control.get("mode", "observe")).strip().lower()
    kill_switch = bool(control.get("kill_switch", False))
    takeover_state = control_takeover_state().get("takeover", {})
    takeover_status = str(takeover_state.get("status", "idle")).strip().lower() or "idle"
    takeover_session_id = str(takeover_state.get("session_id") or "").strip() or None
    takeover_last_session_id = str(takeover_state.get("last_session_id") or "").strip() or None
    activity_session_id = takeover_session_id or takeover_last_session_id
    takeover_activity_payload = control_takeover_activity(limit=10, session_id=activity_session_id)
    takeover_recent_activity = takeover_activity_payload.get("activity", [])
    takeover_sessions_payload = control_takeover_sessions(limit=3)
    takeover_recent_sessions = takeover_sessions_payload.get("sessions", [])
    remote_state = control_remote_state(request, approval_limit=10, session_limit=3)
    handback_package_available = False
    handback_package_summary: dict[str, Any] | None = None
    if takeover_last_session_id:
        try:
            handback_package = control_takeover_handback_package(limit=20, session_id=takeover_last_session_id)
            handback_package_available = True
            handback_package_summary = handback_package.get("summary", {})
        except HTTPException:
            handback_package_available = False
            handback_package_summary = None
    pilot_mode_on = mode == "pilot" and not kill_switch
    pilot_indicator_status = "on" if pilot_mode_on else "paused" if mode == "pilot" and kill_switch else "off"
    pilot_indicator_label = (
        "PILOT MODE ON"
        if pilot_indicator_status == "on"
        else "PILOT MODE PAUSED"
        if pilot_indicator_status == "paused"
        else "PILOT MODE OFF"
    )
    panic_available = not kill_switch
    resume_available = kill_switch

    return {
        "status": "ok",
        "mode": control.get("mode"),
        "kill_switch": control.get("kill_switch"),
        "scope": control.get("scopes", {}),
        "control_surface": {
            "mode": mode,
            "kill_switch": kill_switch,
            "panic_available": panic_available,
            "resume_available": resume_available,
            "mutating_actions_blocked": kill_switch,
            "pilot_mode_on": pilot_mode_on,
            "pilot_indicator": {
                "visible": True,
                "status": pilot_indicator_status,
                "label": pilot_indicator_label,
                "kill_switch_active": kill_switch,
            },
            "takeover": {
                "status": takeover_status,
                "active": takeover_status == "active",
                "pending_confirmation": takeover_status == "requested",
                "session_id": takeover_session_id,
                "last_session_id": takeover_last_session_id,
                "objective": takeover_state.get("objective"),
                "requested_by": takeover_state.get("requested_by"),
                "requested_at": takeover_state.get("requested_at"),
                "confirmed_at": takeover_state.get("confirmed_at"),
                "handed_back_at": takeover_state.get("handed_back_at"),
                "recent_activity": takeover_recent_activity,
                "recent_sessions": takeover_recent_sessions,
                "session_count": int(takeover_sessions_payload.get("count", len(takeover_recent_sessions))),
                "handback_package_available": handback_package_available,
                "handback_package_summary": handback_package_summary,
            },
        },
        "intent_state": intent_state,
        "event_state": event_state,
        "telemetry": {
            "enabled": bool(telemetry.get("enabled", False)),
            "event_count_horizon": int(telemetry.get("event_count_horizon", 0)),
            "active_streams_horizon": list(telemetry.get("active_streams_horizon", [])),
            "last_event_ts": telemetry.get("last_event_ts"),
        },
        "remote": remote_state,
        "autonomy_queue": {
            "queued_count": int(autonomy_queue.get("queued_count", 0)),
            "queued_retry_count": autonomy_retry_pressure,
            "leased_count": int(autonomy_queue.get("leased_count", 0)),
            "leased_expired_count": autonomy_leased_expired_count,
            "dispatched_count": int(autonomy_queue.get("dispatched_count", 0)),
            "failed_count": int(autonomy_queue.get("failed_count", 0)),
            "deadletter_count": int(autonomy_queue.get("deadletter_count", 0)),
            "high_risk_due_count": autonomy_high_risk_due,
        },
        "autonomy_dispatch": {
            "last_run_id": autonomy_last_dispatch.get("run_id"),
            "halted_reason": halted_reason or None,
            "halted": dispatch_halted,
            "processed_count": int(autonomy_last_dispatch.get("processed_count", 0)),
            "failed_count": int(autonomy_last_dispatch.get("failed_count", 0)),
            "retried_count": int(autonomy_last_dispatch.get("retried_count", 0)),
            "released_count": int(autonomy_last_dispatch.get("released_count", 0)),
            "dispatch_executed_actions": int(autonomy_last_dispatch.get("dispatch_executed_actions", 0)),
            "max_dispatch_actions": int(last_dispatch_config.get("max_dispatch_actions", 0)),
            "max_dispatch_runtime_seconds": int(last_dispatch_config.get("max_dispatch_runtime_seconds", 0)),
            "max_attempts": int(last_dispatch_config.get("max_attempts", 0)),
            "retry_backoff_seconds": int(last_dispatch_config.get("retry_backoff_seconds", 0)),
            "verification_status": dispatch_verification.get("verification_status"),
            "confidence": dispatch_verification.get("confidence"),
            "can_claim_done": bool(dispatch_verification.get("can_claim_done", False)),
            "claim": dispatch_verification.get("claim"),
            "completion_state": autonomy_last_dispatch.get("completion_state"),
            "trust_badge": trust_badge(
                confidence=str(dispatch_verification.get("confidence", "")),
                can_claim_done=bool(dispatch_verification.get("can_claim_done", False)),
            ),
        },
        "autonomy_reactor": {
            "last_run_id": autonomy_last_tick.get("run_id"),
            "last_ts": autonomy_last_tick.get("ts"),
            "halted": tick_halted,
            "halted_reason": tick_halted_reason or None,
            "collect_seen_count": int(tick_collect.get("seen_count", 0)),
            "collect_queued_count": int(tick_collect.get("queued_count", 0)),
            "dispatch_processed_count": int(tick_dispatch.get("processed_count", 0)),
            "dispatch_failed_count": int(tick_dispatch.get("failed_count", 0)),
            "dispatch_retried_count": int(tick_dispatch.get("retried_count", 0)),
            "dispatch_released_count": int(tick_dispatch.get("released_count", 0)),
            "verification_status": tick_verification.get("verification_status"),
            "confidence": tick_verification.get("confidence"),
            "can_claim_done": bool(tick_verification.get("can_claim_done", False)),
            "claim": tick_verification.get("claim"),
            "completion_state": autonomy_last_tick.get("completion_state"),
            "trust_badge": trust_badge(
                confidence=str(tick_verification.get("confidence", "")),
                can_claim_done=bool(tick_verification.get("can_claim_done", False)),
            ),
            "guardrail": {
                "tick_count": int(autonomy_guardrail.get("tick_count", 0)),
                "consecutive_retry_pressure_ticks": int(
                    autonomy_guardrail.get("consecutive_retry_pressure_ticks", 0)
                ),
                "cooldown_remaining_ticks": int(autonomy_guardrail.get("cooldown_remaining_ticks", 0)),
                "escalations_count": int(autonomy_guardrail.get("escalations_count", 0)),
                "last_retry_pressure_count": int(autonomy_guardrail.get("last_retry_pressure_count", 0)),
                "last_reason": autonomy_guardrail.get("last_reason"),
                "manual_reset_available": manual_reset_available,
                "updated_at": autonomy_guardrail.get("updated_at"),
            },
        },
        "pending_approvals": pending_approvals,
        "blockers": {
            "critical_incidents": event_state.get("critical_incident_count", 0),
            "deadletters": event_state.get("deadletter_count", 0),
            "worker_queue_due": event_state.get("worker_queue_due_count", 0),
            "worker_queue_backoff": event_state.get("worker_queue_backoff_count", 0),
            "worker_leased": event_state.get("worker_leased_count", 0),
            "worker_leased_expired": event_state.get("worker_leased_expired_count", 0),
            "worker_cycle_active": event_state.get("worker_cycle_active_count", 0),
            "worker_cycle_max": event_state.get("worker_cycle_max_concurrent", 1),
            "worker_cycle_gate_saturated": event_state.get("worker_cycle_gate_saturated", False),
            "worker_last_lease_lost": event_state.get("worker_last_lease_lost_count", 0),
            "worker_last_lease_conflict": event_state.get("worker_last_lease_conflict_count", 0),
            "autonomy_queue_due": int(autonomy_queue.get("queued_count", 0)),
            "autonomy_queue_high_risk_due": autonomy_high_risk_due,
            "autonomy_queue_retry_pressure": autonomy_retry_pressure,
            "autonomy_queue_leased_expired": autonomy_leased_expired_count,
            "autonomy_dispatch_halted": dispatch_halted,
            "autonomy_dispatch_halted_reason": halted_reason or None,
            "autonomy_dispatch_budget_halt": dispatch_budget_halt,
            "autonomy_dispatch_critical_halt": dispatch_critical_halt,
            "autonomy_dispatch_claim_confidence": dispatch_verification.get("confidence"),
            "autonomy_dispatch_can_claim_done": bool(dispatch_verification.get("can_claim_done", False)),
            "autonomy_reactor_halted": tick_halted,
            "autonomy_reactor_halted_reason": tick_halted_reason or None,
            "autonomy_reactor_cooldown_active": guardrail_cooldown_active,
            "autonomy_reactor_claim_confidence": tick_verification.get("confidence"),
            "autonomy_reactor_can_claim_done": bool(tick_verification.get("can_claim_done", False)),
            "pending_approvals": pending_approvals,
        },
    }


@router.get("/lens/actions")
def lens_actions(request: Request, max_actions: int = 6) -> dict:
    allowed, reason, control = check_action_allowed(
        _fs,
        repo_root=_repo_root,
        workspace_root=_workspace_root,
        app="lens",
        action="lens.actions",
        mutating=False,
    )
    if not allowed:
        raise HTTPException(status_code=403, detail=f"Control denied: {reason}")

    event_state = collect_events(_fs)
    intent_state = collect_intents(_fs)
    autonomy_queue = autonomy_queue_status(_fs, limit=200)
    autonomy_last_dispatch = read_autonomy_last_dispatch(_fs)
    autonomy_last_tick = read_autonomy_last_tick(_fs)
    autonomy_guardrail = read_autonomy_reactor_guardrail_state(_fs)
    dispatch_halted_reason = str(autonomy_last_dispatch.get("halted_reason", "")).strip()
    dispatch_verification = (
        autonomy_last_dispatch.get("verification", {})
        if isinstance(autonomy_last_dispatch.get("verification"), dict)
        else {}
    )
    last_dispatch_config = (
        autonomy_last_dispatch.get("config", {}) if isinstance(autonomy_last_dispatch, dict) else {}
    )
    tick_dispatch = autonomy_last_tick.get("dispatch", {}) if isinstance(autonomy_last_tick, dict) else {}
    tick_verification = (
        autonomy_last_tick.get("verification", {})
        if isinstance(autonomy_last_tick.get("verification"), dict)
        else {}
    )
    tick_halted_reason = str(tick_dispatch.get("halted_reason", "")).strip()
    guardrail_cooldown_remaining = int(autonomy_guardrail.get("cooldown_remaining_ticks", 0))
    guardrail_cooldown_active = guardrail_cooldown_remaining > 0
    autonomy_queued_count = int(autonomy_queue.get("queued_count", 0))
    autonomy_retry_pressure = int(autonomy_queue.get("queued_retry_count", 0))
    autonomy_high_risk_due = sum(
        1
        for row in autonomy_queue.get("queued", [])
        if str(row.get("risk_tier", "")).strip().lower() in {"high", "critical"}
    )
    autonomy_leased_expired_count = int(autonomy_queue.get("leased_expired_count", 0))
    allow_medium, allow_high = _mode_allows_medium_high(str(control.get("mode", "observe")))
    plan = build_plan(
        event_state=event_state,
        intent_state=intent_state,
        max_actions=max_actions,
        allow_medium=allow_medium,
        allow_high=allow_high,
    )
    budget_state = load_budget_state(_fs)
    gated_candidates: list[dict[str, Any]] = []
    for candidate in plan.get("candidate_actions", []):
        if not bool(candidate.get("allowed", False)):
            gated_candidates.append({**candidate})
            continue
        allowed_by_budget, reason, action_key = check_action_budget(candidate, state=budget_state)
        if allowed_by_budget:
            gated_candidates.append({**candidate})
        else:
            gated_candidates.append(
                {
                    **candidate,
                    "allowed": False,
                    "policy_reason": reason,
                    "blocked_by": "action_budget",
                    "action_key": action_key,
                }
            )

    selected_actions = [item for item in gated_candidates if bool(item.get("allowed"))][: max(0, max_actions)]
    blocked_actions = [item for item in gated_candidates if not bool(item.get("allowed"))]

    action_chips = []
    for action in gated_candidates:
        kind = str(action.get("kind", ""))
        label = {
            "observer.scan": "Run Observer Scan",
            "worker.cycle": "Process Worker Queue",
            "worker.recover_leases": "Recover Stale Leases",
            "mission.tick": "Advance Mission",
            "forge.propose": "Generate Forge Proposals",
        }.get(kind, kind)
        chip = {
            "kind": kind,
            "label": label,
            "enabled": bool(action.get("allowed")),
            "reason": action.get("reason", ""),
            "policy_reason": action.get("policy_reason", ""),
            "risk_tier": action.get("risk_tier", "low"),
            "trust_badge": "Likely" if bool(action.get("allowed")) else "Uncertain",
        }
        if kind == "worker.cycle":
            chip["lease_telemetry"] = {
                "renewed_last_cycle": event_state.get("worker_last_lease_renewed_count", 0),
                "lost_last_cycle": event_state.get("worker_last_lease_lost_count", 0),
                "conflicts_last_cycle": event_state.get("worker_last_lease_conflict_count", 0),
                "recovered_last_cycle": event_state.get("worker_last_recovered_count", 0),
                "gate_saturated": event_state.get("worker_cycle_gate_saturated", False),
                "active_cycles": event_state.get("worker_cycle_active_count", 0),
                "max_concurrent_cycles": event_state.get("worker_cycle_max_concurrent", 1),
            }
        if kind == "worker.recover_leases":
            chip["recovery_scope"] = action.get("action_classes", [])
        action_chips.append(_with_execute_hint(chip))

    mode = str(control.get("mode", "observe")).strip().lower()
    kill_switch = bool(control.get("kill_switch", False))
    takeover_state = control_takeover_state().get("takeover", {})
    takeover_status = str(takeover_state.get("status", "idle")).strip().lower() or "idle"
    takeover_session_id = str(takeover_state.get("session_id") or "").strip()
    takeover_last_session_id = str(takeover_state.get("last_session_id") or "").strip()
    takeover_sessions_payload = control_takeover_sessions(limit=5)
    takeover_sessions_rows = takeover_sessions_payload.get("sessions", [])
    remote_pending_rows: list[dict[str, Any]] = []
    try:
        remote_approvals = control_remote_approvals(request, status="pending", limit=3)
        remote_pending_rows = [
            row for row in remote_approvals.get("approvals", []) if isinstance(row, dict)
        ]
    except HTTPException:
        remote_pending_rows = []
    action_chips.append(
        _with_execute_hint(
            {
            "kind": "control.panic" if not kill_switch else "control.resume",
            "label": "Panic Stop (Kill Switch)" if not kill_switch else "Resume Mutations",
            "enabled": True,
            "reason": (
                "Instantly block all mutating actions."
                if not kill_switch
                else "Kill switch is active; resume mutating actions when ready."
            ),
            "policy_reason": "",
            "risk_tier": "high" if not kill_switch else "medium",
            "trust_badge": "Confirmed",
            "requires_confirmation": True,
            "mode": mode,
            }
        )
    )
    remote_control_chip = _with_execute_hint(
        {
        "kind": "control.remote.panic" if not kill_switch else "control.remote.resume",
        "label": "Remote Panic Stop" if not kill_switch else "Remote Resume Mutations",
        "enabled": True,
        "reason": (
            "Trigger kill switch through the remote control plane."
            if not kill_switch
            else "Resume mutating actions through the remote control plane."
        ),
        "policy_reason": "",
        "risk_tier": "high" if not kill_switch else "medium",
        "trust_badge": "Confirmed",
        "requires_confirmation": True,
        }
    )
    if takeover_session_id:
        remote_control_chip["execute_via"]["payload"]["args"]["session_id"] = takeover_session_id
    action_chips.append(remote_control_chip)
    action_chips.append(
        _with_execute_hint(
            {
            "kind": "control.remote.state",
            "label": "Remote Snapshot",
            "enabled": True,
            "reason": "Fetch compact control/takeover/approvals state for remote steering.",
            "policy_reason": "",
            "risk_tier": "low",
            "trust_badge": "Confirmed",
            }
        )
    )
    if remote_pending_rows:
        approvals_chip = _with_execute_hint(
            {
            "kind": "control.remote.approvals",
            "label": "Review Pending Approvals",
            "enabled": True,
            "reason": f"{len(remote_pending_rows)} pending approval(s) available.",
            "policy_reason": "",
            "risk_tier": "low",
            "trust_badge": "Confirmed",
            }
        )
        approvals_chip["execute_via"]["payload"]["args"]["status"] = "pending"
        action_chips.append(approvals_chip)
        remote_feed_chip = _with_execute_hint(
            {
            "kind": "control.remote.feed",
            "label": "Remote Feed",
            "enabled": True,
            "reason": "Stream recent remote control and takeover events with receipts.",
            "policy_reason": "",
            "risk_tier": "low",
            "trust_badge": "Confirmed",
            }
        )
        action_chips.append(remote_feed_chip)
        first_pending_id = str(remote_pending_rows[0].get("id", "")).strip()
        if first_pending_id:
            approve_chip = _with_execute_hint(
                {
                "kind": "control.remote.approval.approve",
                "label": "Approve Top Request",
                "enabled": True,
                "reason": f"Approve request {first_pending_id[:8]}... from Lens.",
                "policy_reason": "",
                "risk_tier": "low",
                "trust_badge": "Likely",
                "requires_confirmation": True,
                }
            )
            approve_chip["execute_via"]["payload"]["args"]["approval_id"] = first_pending_id
            action_chips.append(approve_chip)
    if takeover_status == "active":
        action_chips.append(
            _with_execute_hint(
                {
                "kind": "control.takeover.handback",
                "label": "Hand Back Pilot Control",
                "enabled": True,
                "reason": "Takeover is active; return control with summary and receipts.",
                "policy_reason": "",
                "risk_tier": "low",
                "trust_badge": "Confirmed",
                "requires_confirmation": True,
                }
            )
        )
        remote_handback_chip = _with_execute_hint(
            {
            "kind": "control.remote.takeover.handback",
            "label": "Remote Handback Control",
            "enabled": True,
            "reason": "Complete takeover handback through the remote command plane.",
            "policy_reason": "",
            "risk_tier": "low",
            "trust_badge": "Confirmed",
            "requires_confirmation": True,
            }
        )
        if takeover_session_id:
            remote_handback_chip["execute_via"]["payload"]["args"]["session_id"] = takeover_session_id
        action_chips.append(remote_handback_chip)
    elif takeover_status == "requested":
        confirmation_enabled = not kill_switch
        confirmation_policy = ""
        if kill_switch:
            confirmation_policy = "kill switch active; resume before confirming takeover"
        action_chips.append(
            _with_execute_hint(
                {
                "kind": "control.takeover.confirm",
                "label": "Confirm Pilot Takeover",
                "enabled": confirmation_enabled,
                "reason": "Takeover request is pending explicit confirmation.",
                "policy_reason": confirmation_policy,
                "risk_tier": "medium",
                "trust_badge": "Likely" if confirmation_enabled else "Uncertain",
                "requires_confirmation": True,
                }
            )
        )
        remote_confirm_chip = _with_execute_hint(
            {
            "kind": "control.remote.takeover.confirm",
            "label": "Remote Confirm Takeover",
            "enabled": confirmation_enabled,
            "reason": "Confirm takeover via remote command plane.",
            "policy_reason": confirmation_policy,
            "risk_tier": "medium",
            "trust_badge": "Likely" if confirmation_enabled else "Uncertain",
            "requires_confirmation": True,
            }
        )
        if takeover_session_id:
            remote_confirm_chip["execute_via"]["payload"]["args"]["session_id"] = takeover_session_id
        action_chips.append(remote_confirm_chip)
    else:
        action_chips.append(
            _with_execute_hint(
                {
                "kind": "control.takeover.request",
                "label": "Request Pilot Takeover",
                "enabled": True,
                "reason": "Start explicit takeover handshake with scoped objective.",
                "policy_reason": "",
                "risk_tier": "low",
                "trust_badge": "Confirmed",
                "requires_confirmation": True,
                }
            )
        )
        action_chips.append(
            _with_execute_hint(
                {
                "kind": "control.remote.takeover.request",
                "label": "Remote Request Takeover",
                "enabled": True,
                "reason": "Start takeover handshake through remote command plane.",
                "policy_reason": "",
                "risk_tier": "low",
                "trust_badge": "Confirmed",
                "requires_confirmation": True,
                }
            )
        )

    activity_session_id = takeover_session_id or takeover_last_session_id
    sessions_chip = _with_execute_hint(
        {
        "kind": "control.takeover.sessions",
        "label": "Browse Takeover Sessions",
        "enabled": True,
        "reason": "Inspect recent takeover sessions and handback outcomes.",
        "policy_reason": "",
        "risk_tier": "low",
        "trust_badge": "Confirmed",
        }
    )
    sessions_chip["execute_via"]["payload"]["args"]["limit"] = 20
    action_chips.append(sessions_chip)
    if activity_session_id:
        activity_chip = _with_execute_hint(
            {
            "kind": "control.takeover.activity",
            "label": "View Takeover Activity",
            "enabled": True,
            "reason": "Review the latest takeover session action feed.",
            "policy_reason": "",
            "risk_tier": "low",
            "trust_badge": "Confirmed",
            }
        )
        activity_chip["execute_via"]["payload"]["args"]["session_id"] = activity_session_id
        action_chips.append(activity_chip)
        session_chip = _with_execute_hint(
            {
            "kind": "control.takeover.session",
            "label": "Open Current Session",
            "enabled": True,
            "reason": "Load full session timeline, receipts, and exports.",
            "policy_reason": "",
            "risk_tier": "low",
            "trust_badge": "Confirmed",
            }
        )
        session_chip["execute_via"]["payload"]["args"]["session_id"] = activity_session_id
        action_chips.append(session_chip)
    elif takeover_sessions_rows:
        latest_session_id = str(takeover_sessions_rows[0].get("session_id", "")).strip()
        if latest_session_id:
            latest_chip = _with_execute_hint(
                {
                "kind": "control.takeover.session",
                "label": "Open Latest Session",
                "enabled": True,
                "reason": "Review the latest session timeline and receipts.",
                "policy_reason": "",
                "risk_tier": "low",
                "trust_badge": "Confirmed",
                }
            )
            latest_chip["execute_via"]["payload"]["args"]["session_id"] = latest_session_id
            action_chips.append(latest_chip)
    if takeover_last_session_id:
        package_chip = _with_execute_hint(
            {
            "kind": "control.takeover.handback.package",
            "label": "Open Handback Package",
            "enabled": True,
            "reason": "Load the latest handback receipts bundle for review.",
            "policy_reason": "",
            "risk_tier": "low",
            "trust_badge": "Confirmed",
            }
        )
        package_chip["execute_via"]["payload"]["args"]["session_id"] = takeover_last_session_id
        action_chips.append(package_chip)
        export_chip = _with_execute_hint(
            {
            "kind": "control.takeover.handback.export",
            "label": "Export Handback Bundle",
            "enabled": True,
            "reason": "Write a durable handback bundle to workspace/control/handback_exports.",
            "policy_reason": "",
            "risk_tier": "low",
            "trust_badge": "Confirmed",
            }
        )
        export_chip["execute_via"]["payload"]["args"]["session_id"] = takeover_last_session_id
        action_chips.append(export_chip)

    if autonomy_queued_count > 0:
        dispatch_enabled = mode in {"pilot", "away"}
        policy_reason = ""
        if not dispatch_enabled:
            policy_reason = f"mutating action autonomy.dispatch not allowed in {mode} mode"
        elif autonomy_high_risk_due > 0:
            policy_reason = "approval required for queued high-risk autonomy events"
        action_chips.append(
            _with_execute_hint(
                {
                "kind": "autonomy.dispatch",
                "label": "Dispatch Autonomy Events",
                "enabled": dispatch_enabled,
                "reason": f"{autonomy_queued_count} queued autonomy event(s)",
                "policy_reason": policy_reason,
                "risk_tier": "medium" if autonomy_high_risk_due == 0 else "high",
                "trust_badge": trust_badge(
                    confidence=str(dispatch_verification.get("confidence", "")),
                    can_claim_done=bool(dispatch_verification.get("can_claim_done", False)),
                ),
                "queue_telemetry": {
                    "queued_count": autonomy_queued_count,
                    "high_risk_due_count": autonomy_high_risk_due,
                    "last_halted_reason": dispatch_halted_reason or None,
                    "last_max_dispatch_actions": int(last_dispatch_config.get("max_dispatch_actions", 0)),
                    "last_max_dispatch_runtime_seconds": int(last_dispatch_config.get("max_dispatch_runtime_seconds", 0)),
                    "last_verification_status": dispatch_verification.get("verification_status"),
                    "last_confidence": dispatch_verification.get("confidence"),
                    "last_can_claim_done": bool(dispatch_verification.get("can_claim_done", False)),
                    "last_completion_state": autonomy_last_dispatch.get("completion_state"),
                },
                }
            )
        )
    if autonomy_leased_expired_count > 0:
        recover_enabled = mode in {"pilot", "away"}
        recover_policy_reason = ""
        if not recover_enabled:
            recover_policy_reason = f"mutating action autonomy.recover not allowed in {mode} mode"
        action_chips.append(
            _with_execute_hint(
                {
                "kind": "autonomy.recover",
                "label": "Recover Stale Autonomy Leases",
                "enabled": recover_enabled,
                "reason": f"{autonomy_leased_expired_count} stale leased autonomy event(s)",
                "policy_reason": recover_policy_reason,
                "risk_tier": "low",
                "trust_badge": "Likely" if recover_enabled else "Uncertain",
                "queue_telemetry": {
                    "leased_expired_count": autonomy_leased_expired_count,
                },
                }
            )
        )
    if tick_halted_reason or autonomy_retry_pressure > 0 or guardrail_cooldown_active:
        tick_enabled = mode in {"pilot", "away"}
        tick_policy_reason = ""
        if not tick_enabled:
            tick_policy_reason = f"mutating action autonomy.reactor.tick not allowed in {mode} mode"
        elif guardrail_cooldown_active:
            tick_policy_reason = (
                "guardrail cooldown active; dispatch will remain suppressed until cooldown clears"
            )
        risk_tier = "high" if tick_halted_reason in {"critical_incident_present", "critical_anomaly"} else "medium"
        reason_parts: list[str] = []
        if tick_halted_reason:
            reason_parts.append(f"last tick halted: {tick_halted_reason}")
        if autonomy_retry_pressure > 0:
            reason_parts.append(f"{autonomy_retry_pressure} queued retry event(s)")
        if guardrail_cooldown_active:
            reason_parts.append(f"cooldown active ({guardrail_cooldown_remaining} tick(s) remaining)")
        action_chips.append(
            _with_execute_hint(
                {
                "kind": "autonomy.reactor.tick",
                "label": "Run Reactor Tick",
                "enabled": tick_enabled,
                "reason": "; ".join(reason_parts) if reason_parts else "reactor health check",
                "policy_reason": tick_policy_reason,
                "risk_tier": risk_tier,
                "trust_badge": trust_badge(
                    confidence=str(tick_verification.get("confidence", "")),
                    can_claim_done=bool(tick_verification.get("can_claim_done", False)),
                ),
                "queue_telemetry": {
                    "queued_retry_count": autonomy_retry_pressure,
                    "last_tick_halted_reason": tick_halted_reason or None,
                    "guardrail_cooldown_active": guardrail_cooldown_active,
                    "guardrail_cooldown_remaining_ticks": guardrail_cooldown_remaining,
                    "guardrail_escalations_count": int(autonomy_guardrail.get("escalations_count", 0)),
                    "last_tick_verification_status": tick_verification.get("verification_status"),
                    "last_tick_confidence": tick_verification.get("confidence"),
                    "last_tick_can_claim_done": bool(tick_verification.get("can_claim_done", False)),
                    "last_tick_completion_state": autonomy_last_tick.get("completion_state"),
                    "last_tick_processed_count": int(tick_dispatch.get("processed_count", 0)),
                    "last_tick_failed_count": int(tick_dispatch.get("failed_count", 0)),
                    "last_tick_retried_count": int(tick_dispatch.get("retried_count", 0)),
                    "last_tick_released_count": int(tick_dispatch.get("released_count", 0)),
                },
                }
            )
        )
    if guardrail_cooldown_active:
        reset_enabled = mode == "pilot"
        reset_policy_reason = ""
        if not reset_enabled:
            reset_policy_reason = "manual guardrail reset requires pilot mode"
        action_chips.append(
            _with_execute_hint(
                {
                "kind": "autonomy.reactor.guardrail.reset",
                "label": "Reset Reactor Cooldown",
                "enabled": reset_enabled,
                "reason": f"cooldown active ({guardrail_cooldown_remaining} tick(s) remaining)",
                "policy_reason": reset_policy_reason,
                "risk_tier": "low",
                "trust_badge": "Likely" if reset_enabled else "Uncertain",
                "queue_telemetry": {
                    "guardrail_cooldown_active": guardrail_cooldown_active,
                    "guardrail_cooldown_remaining_ticks": guardrail_cooldown_remaining,
                    "guardrail_escalations_count": int(autonomy_guardrail.get("escalations_count", 0)),
                },
                }
            )
        )

    return {
        "status": "ok",
        "mode": control.get("mode"),
        "action_chips": action_chips,
        "selected_actions": selected_actions,
        "blocked_actions": blocked_actions,
    }


@router.post("/lens/actions/execute")
def lens_execute_action(request: Request, payload: LensExecuteRequest) -> dict:
    run_id = str(getattr(request.state, "run_id", uuid4()))
    trace_id = _normalize_trace_id(getattr(request.state, "trace_id", None), fallback_run_id=run_id)
    role = _role_from_request(request)
    kind = str(payload.kind).strip().lower()
    args = payload.args if isinstance(payload.args, dict) else {}
    dry_run = bool(payload.dry_run)

    try:
        result = _execute_lens_action(
            request=request,
            kind=kind,
            args=args,
            dry_run=dry_run,
            run_id=run_id,
            trace_id=trace_id,
            role=role,
        )
    except HTTPException as exc:
        _record_lens_execution(
            run_id=run_id,
            trace_id=trace_id,
            role=role,
            action_kind=kind,
            dry_run=dry_run,
            ok=False,
            detail={"status": "error", "error": exc.detail, "status_code": exc.status_code},
        )
        raise
    except Exception as exc:
        _record_lens_execution(
            run_id=run_id,
            trace_id=trace_id,
            role=role,
            action_kind=kind,
            dry_run=dry_run,
            ok=False,
            detail={"status": "error", "error": str(exc), "status_code": 500},
        )
        raise HTTPException(status_code=500, detail=f"Lens action execution failed: {exc}")

    _record_lens_execution(
        run_id=run_id,
        trace_id=trace_id,
        role=role,
        action_kind=kind,
        dry_run=dry_run,
        ok=True,
        detail={"status": str(result.get("status", "ok")), "kind": kind},
    )
    return {
        "status": "ok" if not dry_run else "dry_run",
        "run_id": run_id,
        "trace_id": trace_id,
        "action": {"kind": kind, "dry_run": dry_run, "args": args},
        "result": result,
    }
