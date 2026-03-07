from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from francis_brain.ledger import RunLedger
from francis_core.clock import utc_now_iso
from francis_core.config import settings
from francis_core.workspace_fs import WorkspaceFS
from francis_policy.rbac import can
from services.orchestrator.app.approvals_store import add_decision, get_request, list_requests, pending_count

from services.orchestrator.app.control_state import (
    VALID_MODES,
    check_action_allowed,
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
_ledger = RunLedger(_fs, rel_path="runs/run_ledger.jsonl")
_takeover_state_path = "control/takeover.json"
_takeover_history_path = "control/takeover_history.jsonl"
_takeover_activity_path = "control/takeover_activity.jsonl"
_REMOTE_FEED_RISK_TIERS = {"low", "medium", "high", "critical"}
_REMOTE_FEED_SOURCES = {"takeover.activity", "journals.decisions"}


class ControlModeRequest(BaseModel):
    mode: str = Field(description="observe|assist|pilot|away")
    kill_switch: bool | None = None
    reason: str = ""


class ControlScopeRequest(BaseModel):
    repos: list[str] | None = None
    workspaces: list[str] | None = None
    apps: list[str] | None = None


class ControlPanicRequest(BaseModel):
    reason: str = ""


class ControlResumeRequest(BaseModel):
    reason: str = ""
    mode: str | None = Field(default=None, description="Optional mode to apply while resuming.")


class ControlTakeoverRequest(BaseModel):
    objective: str = Field(min_length=1)
    reason: str = ""
    repos: list[str] | None = None
    workspaces: list[str] | None = None
    apps: list[str] | None = None


class ControlTakeoverConfirmRequest(BaseModel):
    confirm: bool = True
    reason: str = ""
    mode: str = Field(default="pilot", description="Pilot mode expected for takeover activation.")


class ControlTakeoverHandbackRequest(BaseModel):
    summary: str = ""
    verification: dict[str, Any] = Field(default_factory=dict)
    pending_approvals: int = Field(default=0, ge=0)
    mode: str | None = Field(default=None, description="Optional control mode to apply at handback.")
    reason: str = ""


class ControlTakeoverHandbackExportRequest(BaseModel):
    session_id: str | None = None
    limit: int = Field(default=300, ge=1, le=5000)
    reason: str = ""


class ControlRemoteApprovalDecisionRequest(BaseModel):
    note: str = ""
    session_id: str | None = None


class ControlRemotePanicRequest(ControlPanicRequest):
    session_id: str | None = None


class ControlRemoteResumeRequest(ControlResumeRequest):
    session_id: str | None = None


class ControlRemoteTakeoverRequest(ControlTakeoverRequest):
    pass


class ControlRemoteTakeoverConfirmRequest(ControlTakeoverConfirmRequest):
    session_id: str | None = None


class ControlRemoteTakeoverHandbackRequest(ControlTakeoverHandbackRequest):
    session_id: str | None = None


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


def _enforce_remote_rbac(request: Request, action: str) -> str:
    role = _role_from_request(request)
    if not can(role, action):
        raise HTTPException(status_code=403, detail=f"RBAC denied: role={role}, action={action}")
    return role


def _enforce_remote_control(action: str) -> None:
    allowed, reason, _state = check_action_allowed(
        _fs,
        repo_root=_repo_root,
        workspace_root=_workspace_root,
        app="control",
        action=action,
        mutating=False,
    )
    if not allowed:
        raise HTTPException(status_code=403, detail=f"Control denied: {reason}")


def _default_takeover_state() -> dict[str, Any]:
    control = load_or_init_control_state(_fs, _repo_root, _workspace_root)
    return {
        "status": "idle",
        "session_id": None,
        "last_session_id": None,
        "objective": "",
        "reason": "",
        "scope": control.get("scopes", {}),
        "previous_mode": control.get("mode"),
        "previous_kill_switch": control.get("kill_switch"),
        "previous_scope": control.get("scopes", {}),
        "applied_scope": control.get("scopes", {}),
        "requested_by": "",
        "requested_at": None,
        "confirmed_at": None,
        "confirmation_reason": "",
        "handed_back_at": None,
        "handback_reason": "",
        "handback_summary": "",
        "handback_verification": {},
        "handback_pending_approvals": 0,
        "request_run_id": None,
        "request_trace_id": None,
        "confirm_run_id": None,
        "confirm_trace_id": None,
        "handback_run_id": None,
        "handback_trace_id": None,
        "updated_at": utc_now_iso(),
    }


def _read_jsonl_rows(rel_path: str) -> list[dict[str, Any]]:
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


def _tail_rows(rows: list[dict[str, Any]], limit: int, cap: int = 2000) -> list[dict[str, Any]]:
    n = max(0, min(limit, cap))
    if n == 0:
        return []
    return rows[-n:]


def _derive_trace_id(row: dict[str, Any]) -> str:
    explicit = str(row.get("trace_id", "")).strip()
    if explicit:
        return explicit
    summary = row.get("summary", {}) if isinstance(row.get("summary"), dict) else {}
    summary_trace = str(summary.get("trace_id", "")).strip()
    if summary_trace:
        return summary_trace
    run_id = str(row.get("run_id", "")).strip()
    if not run_id:
        return ""
    if ":" in run_id:
        return run_id.split(":", 1)[0].strip()
    return run_id


def _sanitize_scope(scope: dict[str, Any]) -> dict[str, list[str]]:
    repos = scope.get("repos", []) if isinstance(scope.get("repos"), list) else []
    workspaces = scope.get("workspaces", []) if isinstance(scope.get("workspaces"), list) else []
    apps = scope.get("apps", []) if isinstance(scope.get("apps"), list) else []
    return {
        "repos": [str(item) for item in repos if isinstance(item, str) and str(item).strip()],
        "workspaces": [str(item) for item in workspaces if isinstance(item, str) and str(item).strip()],
        "apps": [str(item) for item in apps if isinstance(item, str) and str(item).strip()],
    }


def _normalize_scope_paths(values: list[str]) -> list[str]:
    normalized: list[str] = []
    for item in values:
        if not isinstance(item, str):
            continue
        stripped = item.strip()
        if not stripped:
            continue
        normalized.append(str(Path(stripped).resolve()))
    return sorted(set(normalized))


def _normalize_scope_apps(values: list[str]) -> list[str]:
    normalized = [str(item).strip().lower() for item in values if isinstance(item, str) and str(item).strip()]
    return sorted(set(normalized))


def _path_in_allowed_roots(path_value: str, allowed_roots: list[str]) -> bool:
    target = Path(path_value).resolve()
    for root in allowed_roots:
        try:
            target.relative_to(Path(root).resolve())
            return True
        except Exception:
            continue
    return False


def _load_or_init_takeover_state() -> dict[str, Any]:
    baseline = _default_takeover_state()
    try:
        raw = _fs.read_text(_takeover_state_path)
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            merged = {**baseline, **parsed}
            merged["scope"] = _sanitize_scope(
                merged.get("scope", {}) if isinstance(merged.get("scope"), dict) else {}
            )
            merged["previous_scope"] = _sanitize_scope(
                merged.get("previous_scope", {}) if isinstance(merged.get("previous_scope"), dict) else {}
            )
            merged["applied_scope"] = _sanitize_scope(
                merged.get("applied_scope", {}) if isinstance(merged.get("applied_scope"), dict) else {}
            )
            _fs.write_text(_takeover_state_path, json.dumps(merged, ensure_ascii=False, indent=2))
            return merged
    except Exception:
        pass
    _fs.write_text(_takeover_state_path, json.dumps(baseline, ensure_ascii=False, indent=2))
    return baseline


def _save_takeover_state(state: dict[str, Any]) -> dict[str, Any]:
    baseline = _default_takeover_state()
    merged = {**baseline, **state}
    merged["scope"] = _sanitize_scope(merged.get("scope", {}) if isinstance(merged.get("scope"), dict) else {})
    merged["previous_scope"] = _sanitize_scope(
        merged.get("previous_scope", {}) if isinstance(merged.get("previous_scope"), dict) else {}
    )
    merged["applied_scope"] = _sanitize_scope(
        merged.get("applied_scope", {}) if isinstance(merged.get("applied_scope"), dict) else {}
    )
    merged["updated_at"] = utc_now_iso()
    _fs.write_text(_takeover_state_path, json.dumps(merged, ensure_ascii=False, indent=2))
    return merged


def _resolve_takeover_scope(payload: ControlTakeoverRequest) -> dict[str, list[str]]:
    control = load_or_init_control_state(_fs, _repo_root, _workspace_root)
    scope = _sanitize_scope(control.get("scopes", {}) if isinstance(control.get("scopes"), dict) else {})
    scope["repos"] = _normalize_scope_paths(scope.get("repos", []))
    scope["workspaces"] = _normalize_scope_paths(scope.get("workspaces", []))
    scope["apps"] = _normalize_scope_apps(scope.get("apps", []))
    allowed_apps = set(scope.get("apps", []))
    if payload.repos is not None:
        requested_repos = _normalize_scope_paths(
            [str(item) for item in payload.repos if isinstance(item, str) and str(item).strip()]
        )
        outside_repos = [repo for repo in requested_repos if not _path_in_allowed_roots(repo, scope.get("repos", []))]
        if outside_repos:
            raise HTTPException(
                status_code=403,
                detail=f"Takeover repo scope outside control contract: {outside_repos[0]}",
            )
        scope["repos"] = requested_repos
    if payload.workspaces is not None:
        requested_workspaces = _normalize_scope_paths(
            [str(item) for item in payload.workspaces if isinstance(item, str) and str(item).strip()]
        )
        outside_workspaces = [
            workspace for workspace in requested_workspaces if not _path_in_allowed_roots(workspace, scope.get("workspaces", []))
        ]
        if outside_workspaces:
            raise HTTPException(
                status_code=403,
                detail=f"Takeover workspace scope outside control contract: {outside_workspaces[0]}",
            )
        scope["workspaces"] = requested_workspaces
    if payload.apps is not None:
        requested_apps = _normalize_scope_apps(
            [str(item) for item in payload.apps if isinstance(item, str) and str(item).strip()]
        )
        outside_apps = [app for app in requested_apps if app not in allowed_apps]
        if outside_apps:
            raise HTTPException(
                status_code=403,
                detail=f"Takeover app scope outside control contract: {outside_apps[0]}",
            )
        scope["apps"] = requested_apps
    return scope


def _record_control_receipt(
    *,
    run_id: str,
    trace_id: str,
    kind: str,
    reason: str,
    before: dict[str, Any],
    after: dict[str, Any],
    session_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_session_id = str(session_id or "").strip()
    receipt = {
        "id": str(uuid4()),
        "ts": utc_now_iso(),
        "run_id": run_id,
        "trace_id": trace_id,
        "kind": kind,
        "reason": reason,
        "before": before,
        "after": after,
        "session_id": normalized_session_id or None,
    }
    if isinstance(metadata, dict):
        for key, value in metadata.items():
            if key not in receipt:
                receipt[key] = value
    _append_jsonl("logs/francis.log.jsonl", receipt)
    _append_jsonl("journals/decisions.jsonl", receipt)
    _ledger.append(
        run_id=run_id,
        kind=kind,
        summary={
            "trace_id": trace_id,
            "reason": reason,
            "before_mode": before.get("mode"),
            "before_kill_switch": before.get("kill_switch"),
                "after_mode": after.get("mode"),
                "after_kill_switch": after.get("kill_switch"),
                "before_status": before.get("status"),
                "after_status": after.get("status"),
                "objective": after.get("objective") or before.get("objective"),
                "session_id": normalized_session_id or None,
            },
    )
    return receipt


def _append_takeover_history(
    *,
    run_id: str,
    trace_id: str,
    kind: str,
    reason: str,
    before: dict[str, Any],
    after: dict[str, Any],
    session_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    row = {
        "id": str(uuid4()),
        "ts": utc_now_iso(),
        "run_id": run_id,
        "trace_id": trace_id,
        "kind": kind,
        "reason": reason,
        "before": before,
        "after": after,
        "session_id": str(session_id or "").strip() or None,
    }
    if isinstance(metadata, dict):
        for key, value in metadata.items():
            if key not in row:
                row[key] = value
    _append_jsonl(
        _takeover_history_path,
        row,
    )


def _read_takeover_history(limit: int) -> list[dict[str, Any]]:
    return _tail_rows(_read_jsonl_rows(_takeover_history_path), limit=limit, cap=1000)


def _read_takeover_activity_rows(session_id: str | None = None) -> list[dict[str, Any]]:
    rows = _read_jsonl_rows(_takeover_activity_path)
    normalized_session_id = str(session_id or "").strip()
    if normalized_session_id:
        rows = [row for row in rows if str(row.get("session_id", "")).strip() == normalized_session_id]
    return rows


def _read_takeover_activity(limit: int, session_id: str | None = None) -> list[dict[str, Any]]:
    rows = _read_takeover_activity_rows(session_id=session_id)
    return _tail_rows(rows, limit=limit, cap=5000)


def _resolve_takeover_session_id(
    *,
    state: dict[str, Any],
    requested_session_id: str | None = None,
    prefer_last: bool = False,
) -> str:
    requested = str(requested_session_id or "").strip()
    if requested:
        return requested
    active = str(state.get("session_id") or "").strip()
    last = str(state.get("last_session_id") or "").strip()
    if prefer_last:
        return last or active
    return active or last


def _parse_activity_cursor(raw_cursor: str | None) -> int | None:
    value = str(raw_cursor or "").strip()
    if not value:
        return None
    try:
        parsed = int(value)
    except Exception:
        return None
    return max(0, parsed)


def _slice_activity_rows(
    *,
    rows: list[dict[str, Any]],
    cursor: int,
    limit: int,
) -> tuple[list[dict[str, Any]], int, bool]:
    normalized_limit = max(1, min(limit, 1000))
    start = max(0, min(cursor, len(rows)))
    chunk = rows[start : start + normalized_limit]
    next_cursor = start + len(chunk)
    has_more = next_cursor < len(rows)
    return chunk, next_cursor, has_more


def _sse_event(event: str, data: dict[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"


def append_takeover_activity(
    *,
    run_id: str,
    trace_id: str,
    actor: str,
    kind: str,
    detail: dict[str, Any] | None = None,
    ok: bool | None = None,
    session_id: str | None = None,
    allow_inactive: bool = False,
    takeover_state: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    state = takeover_state if isinstance(takeover_state, dict) else _load_or_init_takeover_state()
    status = str(state.get("status", "idle")).strip().lower()
    resolved_session_id = str(session_id or state.get("session_id") or "").strip()
    if not resolved_session_id:
        return None
    if status != "active" and not allow_inactive:
        return None

    row = {
        "id": str(uuid4()),
        "ts": utc_now_iso(),
        "session_id": resolved_session_id,
        "status": status,
        "objective": str(state.get("objective", "")).strip(),
        "run_id": run_id,
        "trace_id": trace_id,
        "actor": str(actor).strip() or "system",
        "kind": str(kind).strip() or "unknown",
        "ok": bool(ok) if ok is not None else None,
        "detail": detail if isinstance(detail, dict) else {},
    }
    _append_jsonl(_takeover_activity_path, row)
    return row


def _collect_handback_receipts_for_session(session_id: str, limit: int) -> dict[str, list[dict[str, Any]]]:
    normalized_session_id = str(session_id).strip()
    transitions = [
        row
        for row in _read_jsonl_rows(_takeover_history_path)
        if str(row.get("session_id", "")).strip() == normalized_session_id
    ]
    activity = _read_takeover_activity(limit=limit, session_id=normalized_session_id)

    run_ids: set[str] = set()
    trace_ids: set[str] = set()
    for row in [*transitions, *activity]:
        run_id = str(row.get("run_id", "")).strip()
        trace_id = str(row.get("trace_id", "")).strip()
        if run_id:
            run_ids.add(run_id)
        if trace_id:
            trace_ids.add(trace_id)
            run_ids.add(trace_id)

    def should_include(row: dict[str, Any]) -> bool:
        row_session_id = str(row.get("session_id", "")).strip()
        if row_session_id and row_session_id == normalized_session_id:
            return True
        run_id = str(row.get("run_id", "")).strip()
        if run_id and run_id in run_ids:
            return True
        row_trace_id = _derive_trace_id(row)
        return bool(row_trace_id and row_trace_id in trace_ids)

    decisions = [row for row in _read_jsonl_rows("journals/decisions.jsonl") if should_include(row)]
    logs = [row for row in _read_jsonl_rows("logs/francis.log.jsonl") if should_include(row)]
    ledger = [row for row in _read_jsonl_rows("runs/run_ledger.jsonl") if should_include(row)]
    legacy_ledger = [row for row in _read_jsonl_rows("brain/run_ledger.jsonl") if should_include(row)]
    combined_ledger = sorted([*legacy_ledger, *ledger], key=lambda row: str(row.get("ts", "")))

    return {
        "transitions": _tail_rows(transitions, limit=limit, cap=1000),
        "activity": _tail_rows(activity, limit=limit, cap=5000),
        "decisions": _tail_rows(decisions, limit=limit, cap=2000),
        "logs": _tail_rows(logs, limit=limit, cap=2000),
        "ledger": _tail_rows(combined_ledger, limit=limit, cap=2000),
    }


def _safe_export_timestamp(ts: str) -> str:
    return str(ts).replace(":", "-")


def _read_handback_export_index_rows() -> list[dict[str, Any]]:
    return _read_jsonl_rows("control/handback_exports/index.jsonl")


def _session_event_ts(row: dict[str, Any]) -> str:
    return str(row.get("ts", "")).strip()


def _build_takeover_session_summary(
    *,
    session_id: str,
    state: dict[str, Any],
    transitions: list[dict[str, Any]],
    activity: list[dict[str, Any]],
    exports: list[dict[str, Any]],
) -> dict[str, Any]:
    ordered_transitions = sorted(transitions, key=_session_event_ts)
    ordered_activity = sorted(activity, key=_session_event_ts)
    ordered_exports = sorted(exports, key=_session_event_ts)
    request_row = next((row for row in ordered_transitions if str(row.get("kind", "")) == "control.takeover.request"), {})
    confirm_row = next((row for row in ordered_transitions if str(row.get("kind", "")) == "control.takeover.confirm"), {})
    handback_row = next((row for row in ordered_transitions if str(row.get("kind", "")) == "control.takeover.handback"), {})
    requested_activity = next((row for row in ordered_activity if str(row.get("kind", "")) == "control.takeover.requested"), {})
    handback_activity = next((row for row in ordered_activity if str(row.get("kind", "")) == "control.takeover.handed_back"), {})

    request_after = request_row.get("after", {}) if isinstance(request_row.get("after"), dict) else {}
    objective = str(request_after.get("objective", "")).strip()
    if not objective:
        objective = str(ordered_activity[-1].get("objective", "")).strip() if ordered_activity else ""
    requested_by = str(requested_activity.get("actor", "")).strip() or None
    requested_at = _session_event_ts(request_row) or _session_event_ts(requested_activity) or None
    confirmed_at = _session_event_ts(confirm_row) or None
    handed_back_at = _session_event_ts(handback_row) or _session_event_ts(handback_activity) or None
    handback_detail = (
        handback_activity.get("detail", {}) if isinstance(handback_activity.get("detail"), dict) else {}
    )
    pending_approvals = int(handback_detail.get("pending_approvals", 0))

    active_session_id = str(state.get("session_id") or "").strip()
    if active_session_id == session_id:
        status = str(state.get("status", "idle")).strip().lower() or "idle"
    else:
        status = "idle"

    last_activity = ordered_activity[-1] if ordered_activity else {}
    last_transition = ordered_transitions[-1] if ordered_transitions else {}
    last_export = ordered_exports[-1] if ordered_exports else {}
    last_event_ts = max(
        [
            str(last_activity.get("ts", "")).strip(),
            str(last_transition.get("ts", "")).strip(),
            str(last_export.get("ts", "")).strip(),
        ]
    )

    return {
        "session_id": session_id,
        "status": status,
        "objective": objective or None,
        "requested_by": requested_by,
        "requested_at": requested_at,
        "confirmed_at": confirmed_at,
        "handed_back_at": handed_back_at,
        "pending_approvals": pending_approvals,
        "counts": {
            "transitions": len(ordered_transitions),
            "activity": len(ordered_activity),
            "exports": len(ordered_exports),
        },
        "last_event_ts": last_event_ts or None,
        "last_transition_kind": str(last_transition.get("kind", "")).strip() or None,
        "last_activity_kind": str(last_activity.get("kind", "")).strip() or None,
        "last_export_id": str(last_export.get("id", "")).strip() or None,
    }


def _build_takeover_sessions(limit: int) -> list[dict[str, Any]]:
    state = _load_or_init_takeover_state()
    transitions = _read_jsonl_rows(_takeover_history_path)
    activity_rows = _read_jsonl_rows(_takeover_activity_path)
    export_rows = _read_handback_export_index_rows()
    active_session_id = str(state.get("session_id") or "").strip()
    last_session_id = str(state.get("last_session_id") or "").strip()

    session_ids: set[str] = set()
    for row in [*transitions, *activity_rows, *export_rows]:
        session_id = str(row.get("session_id", "")).strip()
        if session_id:
            session_ids.add(session_id)
    if active_session_id:
        session_ids.add(active_session_id)
    if last_session_id:
        session_ids.add(last_session_id)

    summaries: list[dict[str, Any]] = []
    for session_id in session_ids:
        session_transitions = [row for row in transitions if str(row.get("session_id", "")).strip() == session_id]
        session_activity = [row for row in activity_rows if str(row.get("session_id", "")).strip() == session_id]
        session_exports = [row for row in export_rows if str(row.get("session_id", "")).strip() == session_id]
        summaries.append(
            _build_takeover_session_summary(
                session_id=session_id,
                state=state,
                transitions=session_transitions,
                activity=session_activity,
                exports=session_exports,
            )
        )
    summaries.sort(key=lambda row: str(row.get("last_event_ts", "")), reverse=True)
    return summaries[: max(0, min(limit, 500))]


def _remote_feed_risk_tier(kind: str) -> str:
    normalized_kind = str(kind).strip().lower()
    if "panic" in normalized_kind:
        return "high"
    if normalized_kind in {
        "control.takeover.confirm",
        "control.remote.takeover.confirm",
        "control.takeover.request",
        "control.remote.takeover.request",
    }:
        return "medium"
    if "critical" in normalized_kind:
        return "critical"
    return "low"


def _normalize_remote_feed_risk_tier(risk_tier: str | None) -> str | None:
    normalized = str(risk_tier or "").strip().lower()
    if not normalized:
        return None
    if normalized not in _REMOTE_FEED_RISK_TIERS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid risk_tier: {normalized}. Expected one of {sorted(_REMOTE_FEED_RISK_TIERS)}",
        )
    return normalized


def _normalize_remote_feed_source(source: str | None) -> str | None:
    normalized = str(source or "").strip().lower()
    if not normalized:
        return None
    if normalized not in _REMOTE_FEED_SOURCES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid source: {normalized}. Expected one of {sorted(_REMOTE_FEED_SOURCES)}",
        )
    return normalized


def _parse_remote_feed_timestamp(value: str | None) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    candidate = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _normalize_remote_feed_timestamp(value: str | None, *, field_name: str) -> str | None:
    normalized = str(value or "").strip()
    if not normalized:
        return None
    parsed = _parse_remote_feed_timestamp(normalized)
    if parsed is None:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {field_name}: {normalized}. Expected ISO-8601 timestamp.",
        )
    return parsed.isoformat()


def _build_remote_feed_rows(
    session_id: str | None = None,
    *,
    kind: str | None = None,
    kind_prefix: str | None = None,
    risk_tier: str | None = None,
    source: str | None = None,
    since_ts: str | None = None,
    until_ts: str | None = None,
) -> list[dict[str, Any]]:
    normalized_session_id = str(session_id or "").strip()
    normalized_kind = str(kind or "").strip()
    normalized_kind_prefix = str(kind_prefix or "").strip()
    normalized_risk_tier = _normalize_remote_feed_risk_tier(risk_tier)
    normalized_source = _normalize_remote_feed_source(source)
    normalized_since_ts = _normalize_remote_feed_timestamp(since_ts, field_name="since_ts")
    normalized_until_ts = _normalize_remote_feed_timestamp(until_ts, field_name="until_ts")
    if normalized_since_ts and normalized_until_ts and normalized_since_ts > normalized_until_ts:
        raise HTTPException(status_code=400, detail="since_ts must be <= until_ts")
    since_dt = _parse_remote_feed_timestamp(normalized_since_ts)
    until_dt = _parse_remote_feed_timestamp(normalized_until_ts)
    feed_rows: list[dict[str, Any]] = []

    def _within_window(row_ts: str) -> bool:
        if since_dt is None and until_dt is None:
            return True
        row_dt = _parse_remote_feed_timestamp(row_ts)
        if row_dt is None:
            return False
        if since_dt is not None and row_dt < since_dt:
            return False
        if until_dt is not None and row_dt > until_dt:
            return False
        return True

    if normalized_source in {None, "takeover.activity"}:
        for row in _read_takeover_activity_rows(session_id=normalized_session_id or None):
            row_session_id = str(row.get("session_id", "")).strip()
            if normalized_session_id and row_session_id != normalized_session_id:
                continue
            row_ts = str(row.get("ts", "")).strip()
            if not _within_window(row_ts):
                continue
            row_kind = str(row.get("kind", "")).strip() or "unknown"
            row_risk_tier = _remote_feed_risk_tier(row_kind)
            if normalized_kind and row_kind != normalized_kind:
                continue
            if normalized_kind_prefix and not row_kind.startswith(normalized_kind_prefix):
                continue
            if normalized_risk_tier and row_risk_tier != normalized_risk_tier:
                continue
            feed_rows.append(
                {
                    "id": str(row.get("id", "")).strip() or f"activity:{uuid4()}",
                    "ts": row_ts,
                    "source": "takeover.activity",
                    "kind": row_kind,
                    "risk_tier": row_risk_tier,
                    "run_id": str(row.get("run_id", "")).strip() or None,
                    "trace_id": str(row.get("trace_id", "")).strip() or None,
                    "session_id": row_session_id or None,
                    "actor": str(row.get("actor", "")).strip() or None,
                    "detail": row.get("detail", {}) if isinstance(row.get("detail"), dict) else {},
                }
            )

    if normalized_source in {None, "journals.decisions"}:
        for row in _read_jsonl_rows("journals/decisions.jsonl"):
            row_kind = str(row.get("kind", "")).strip()
            if not (row_kind.startswith("control.remote.") or row_kind.startswith("control.takeover.")):
                continue
            row_session_id = str(row.get("session_id", "")).strip()
            if normalized_session_id and row_session_id and row_session_id != normalized_session_id:
                continue
            row_ts = str(row.get("ts", "")).strip()
            if not _within_window(row_ts):
                continue
            row_risk_tier = _remote_feed_risk_tier(row_kind)
            if normalized_kind and row_kind != normalized_kind:
                continue
            if normalized_kind_prefix and not row_kind.startswith(normalized_kind_prefix):
                continue
            if normalized_risk_tier and row_risk_tier != normalized_risk_tier:
                continue
            feed_rows.append(
                {
                    "id": str(row.get("id", "")).strip() or f"decision:{uuid4()}",
                    "ts": row_ts,
                    "source": "journals.decisions",
                    "kind": row_kind,
                    "risk_tier": row_risk_tier,
                    "run_id": str(row.get("run_id", "")).strip() or None,
                    "trace_id": str(row.get("trace_id", "")).strip() or None,
                    "session_id": row_session_id or None,
                    "actor": str(row.get("decided_by", "")).strip() or None,
                    "detail": {
                        "reason": str(row.get("reason", "")).strip() or None,
                        "before": row.get("before", {}) if isinstance(row.get("before"), dict) else {},
                        "after": row.get("after", {}) if isinstance(row.get("after"), dict) else {},
                        "approval_id": str(row.get("approval_id", "")).strip() or None,
                        "artifact_path": str(row.get("artifact_path", "")).strip() or None,
                    },
                }
            )

    feed_rows.sort(key=lambda item: (str(item.get("ts", "")), str(item.get("id", ""))))
    return feed_rows


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
def put_control_mode(request: Request, payload: ControlModeRequest) -> dict:
    if payload.mode.strip().lower() not in VALID_MODES:
        raise HTTPException(status_code=400, detail=f"Invalid mode: {payload.mode}")
    run_id = str(getattr(request.state, "run_id", uuid4()))
    trace_id = _normalize_trace_id(getattr(request.state, "trace_id", None), fallback_run_id=run_id)
    before = load_or_init_control_state(_fs, _repo_root, _workspace_root)
    state = set_mode(
        _fs,
        repo_root=_repo_root,
        workspace_root=_workspace_root,
        mode=payload.mode.strip().lower(),
        kill_switch=payload.kill_switch,
    )
    reason = str(payload.reason).strip() or "control.mode.update"
    if not bool(before.get("kill_switch", False)) and bool(state.get("kill_switch", False)):
        receipt_kind = "control.panic"
    elif bool(before.get("kill_switch", False)) and not bool(state.get("kill_switch", False)):
        receipt_kind = "control.resume"
    else:
        receipt_kind = "control.mode"
    receipt = _record_control_receipt(
        run_id=run_id,
        trace_id=trace_id,
        kind=receipt_kind,
        reason=reason,
        before={"mode": before.get("mode"), "kill_switch": before.get("kill_switch")},
        after={"mode": state.get("mode"), "kill_switch": state.get("kill_switch")},
    )
    return {
        "status": "ok",
        "run_id": run_id,
        "trace_id": trace_id,
        "mode": state.get("mode"),
        "kill_switch": state.get("kill_switch"),
        "updated_at": state.get("updated_at"),
        "receipt_id": receipt.get("id"),
    }


@router.get("/control/scope")
def get_control_scope() -> dict:
    state = load_or_init_control_state(_fs, _repo_root, _workspace_root)
    return {"status": "ok", "scope": state.get("scopes", {}), "updated_at": state.get("updated_at")}


@router.put("/control/scope")
def put_control_scope(request: Request, payload: ControlScopeRequest) -> dict:
    run_id = str(getattr(request.state, "run_id", uuid4()))
    trace_id = _normalize_trace_id(getattr(request.state, "trace_id", None), fallback_run_id=run_id)
    before = load_or_init_control_state(_fs, _repo_root, _workspace_root)
    state = set_scope(
        _fs,
        repo_root=_repo_root,
        workspace_root=_workspace_root,
        repos=payload.repos,
        workspaces=payload.workspaces,
        apps=payload.apps,
    )
    receipt = _record_control_receipt(
        run_id=run_id,
        trace_id=trace_id,
        kind="control.scope",
        reason="control.scope.update",
        before={"scope": before.get("scopes", {})},
        after={"scope": state.get("scopes", {})},
    )
    return {
        "status": "ok",
        "run_id": run_id,
        "trace_id": trace_id,
        "scope": state.get("scopes", {}),
        "updated_at": state.get("updated_at"),
        "receipt_id": receipt.get("id"),
    }


@router.post("/control/panic")
def control_panic(request: Request, payload: ControlPanicRequest | None = None) -> dict:
    run_id = str(getattr(request.state, "run_id", uuid4()))
    trace_id = _normalize_trace_id(getattr(request.state, "trace_id", None), fallback_run_id=run_id)
    state_before = load_or_init_control_state(_fs, _repo_root, _workspace_root)
    body = payload or ControlPanicRequest()
    reason = str(body.reason).strip() or "manual_panic"
    state_after = set_mode(
        _fs,
        repo_root=_repo_root,
        workspace_root=_workspace_root,
        mode=str(state_before.get("mode", "pilot")).strip().lower(),
        kill_switch=True,
    )
    receipt = _record_control_receipt(
        run_id=run_id,
        trace_id=trace_id,
        kind="control.panic",
        reason=reason,
        before={"mode": state_before.get("mode"), "kill_switch": state_before.get("kill_switch")},
        after={"mode": state_after.get("mode"), "kill_switch": state_after.get("kill_switch")},
    )
    return {
        "status": "ok",
        "run_id": run_id,
        "trace_id": trace_id,
        "mode": state_after.get("mode"),
        "kill_switch": state_after.get("kill_switch"),
        "updated_at": state_after.get("updated_at"),
        "receipt_id": receipt.get("id"),
        "reason": reason,
    }


@router.post("/control/resume")
def control_resume(request: Request, payload: ControlResumeRequest | None = None) -> dict:
    run_id = str(getattr(request.state, "run_id", uuid4()))
    trace_id = _normalize_trace_id(getattr(request.state, "trace_id", None), fallback_run_id=run_id)
    state_before = load_or_init_control_state(_fs, _repo_root, _workspace_root)
    body = payload or ControlResumeRequest()
    requested_mode = str(body.mode or state_before.get("mode", "pilot")).strip().lower()
    if requested_mode not in VALID_MODES:
        raise HTTPException(status_code=400, detail=f"Invalid mode: {requested_mode}")
    reason = str(body.reason).strip() or "manual_resume"
    state_after = set_mode(
        _fs,
        repo_root=_repo_root,
        workspace_root=_workspace_root,
        mode=requested_mode,
        kill_switch=False,
    )
    receipt = _record_control_receipt(
        run_id=run_id,
        trace_id=trace_id,
        kind="control.resume",
        reason=reason,
        before={"mode": state_before.get("mode"), "kill_switch": state_before.get("kill_switch")},
        after={"mode": state_after.get("mode"), "kill_switch": state_after.get("kill_switch")},
    )
    return {
        "status": "ok",
        "run_id": run_id,
        "trace_id": trace_id,
        "mode": state_after.get("mode"),
        "kill_switch": state_after.get("kill_switch"),
        "updated_at": state_after.get("updated_at"),
        "receipt_id": receipt.get("id"),
        "reason": reason,
    }


@router.get("/control/remote/state")
def control_remote_state(request: Request, approval_limit: int = 10, session_limit: int = 5) -> dict:
    _enforce_remote_control("control.remote.read")
    role = _enforce_remote_rbac(request, "control.remote.read")
    _enforce_remote_rbac(request, "approvals.read")
    control_state = load_or_init_control_state(_fs, _repo_root, _workspace_root)
    takeover_state = _load_or_init_takeover_state()
    sessions = _build_takeover_sessions(limit=session_limit)
    pending_approvals = list_requests(_fs, status="pending", limit=approval_limit)
    latest_session = sessions[0] if sessions else {}
    remote_write_allowed = can(role, "control.remote.write")
    approvals_decide_allowed = can(role, "approvals.decide")
    remote_actions = [
        "control.remote.state",
        "control.remote.approvals",
        "control.remote.feed",
    ]
    if remote_write_allowed:
        remote_actions.extend(
            [
                "control.remote.panic",
                "control.remote.resume",
                "control.remote.takeover.request",
                "control.remote.takeover.confirm",
                "control.remote.takeover.handback",
            ]
        )
    if remote_write_allowed and approvals_decide_allowed:
        remote_actions.extend(
            [
                "control.remote.approval.approve",
                "control.remote.approval.reject",
            ]
        )
    return {
        "status": "ok",
        "permissions": {
            "role": role,
            "control_remote_read": True,
            "control_remote_write": remote_write_allowed,
            "approvals_read": True,
            "approvals_decide": approvals_decide_allowed,
        },
        "control": {
            "mode": control_state.get("mode"),
            "kill_switch": bool(control_state.get("kill_switch", False)),
            "updated_at": control_state.get("updated_at"),
        },
        "takeover": {
            "status": str(takeover_state.get("status", "idle")).strip().lower() or "idle",
            "session_id": str(takeover_state.get("session_id") or "").strip() or None,
            "last_session_id": str(takeover_state.get("last_session_id") or "").strip() or None,
            "objective": str(takeover_state.get("objective", "")).strip() or None,
            "requested_at": takeover_state.get("requested_at"),
            "confirmed_at": takeover_state.get("confirmed_at"),
            "handed_back_at": takeover_state.get("handed_back_at"),
            "latest_session": latest_session,
        },
        "approvals": {
            "pending_count": pending_count(_fs),
            "pending": pending_approvals,
        },
        "sessions": {
            "count": len(sessions),
            "recent": sessions,
        },
        "remote_actions": remote_actions,
    }


@router.get("/control/remote/approvals")
def control_remote_approvals(
    request: Request,
    status: str = "pending",
    action: str | None = None,
    limit: int = 50,
) -> dict:
    _enforce_remote_control("control.remote.read")
    _enforce_remote_rbac(request, "control.remote.read")
    _enforce_remote_rbac(request, "approvals.read")
    approvals_list = list_requests(
        _fs,
        status=str(status).strip().lower() or None,
        action=str(action).strip() if action is not None else None,
        limit=limit,
    )
    return {
        "status": "ok",
        "count": len(approvals_list),
        "pending_count": pending_count(_fs),
        "approvals": approvals_list,
    }


@router.get("/control/remote/feed")
def control_remote_feed(
    request: Request,
    limit: int = 100,
    cursor: str | None = None,
    session_id: str | None = None,
    kind: str | None = None,
    kind_prefix: str | None = None,
    risk_tier: str | None = None,
    source: str | None = None,
    since_ts: str | None = None,
    until_ts: str | None = None,
) -> dict:
    _enforce_remote_control("control.remote.read")
    _enforce_remote_rbac(request, "control.remote.read")
    _enforce_remote_rbac(request, "approvals.read")
    normalized_session_id = str(session_id or "").strip()
    normalized_kind = str(kind or "").strip() or None
    normalized_kind_prefix = str(kind_prefix or "").strip() or None
    normalized_risk_tier = _normalize_remote_feed_risk_tier(risk_tier)
    normalized_source = _normalize_remote_feed_source(source)
    normalized_since_ts = _normalize_remote_feed_timestamp(since_ts, field_name="since_ts")
    normalized_until_ts = _normalize_remote_feed_timestamp(until_ts, field_name="until_ts")
    if normalized_since_ts and normalized_until_ts and normalized_since_ts > normalized_until_ts:
        raise HTTPException(status_code=400, detail="since_ts must be <= until_ts")
    rows = _build_remote_feed_rows(
        session_id=normalized_session_id or None,
        kind=normalized_kind,
        kind_prefix=normalized_kind_prefix,
        risk_tier=normalized_risk_tier,
        source=normalized_source,
        since_ts=normalized_since_ts,
        until_ts=normalized_until_ts,
    )
    parsed_cursor = _parse_activity_cursor(cursor)
    if parsed_cursor is None:
        normalized_limit = max(1, min(limit, 1000))
        start_cursor = max(0, len(rows) - normalized_limit)
    else:
        start_cursor = parsed_cursor
    chunk, next_cursor, has_more = _slice_activity_rows(rows=rows, cursor=start_cursor, limit=limit)
    return {
        "status": "ok",
        "session_id": normalized_session_id or None,
        "filters": {
            "kind": normalized_kind,
            "kind_prefix": normalized_kind_prefix,
            "risk_tier": normalized_risk_tier,
            "source": normalized_source,
            "since_ts": normalized_since_ts,
            "until_ts": normalized_until_ts,
        },
        "cursor": str(start_cursor),
        "next_cursor": str(next_cursor),
        "has_more": has_more,
        "total_available": len(rows),
        "count": len(chunk),
        "feed": chunk,
    }


@router.get("/control/remote/feed/stream")
async def control_remote_feed_stream(
    request: Request,
    session_id: str | None = None,
    cursor: str | None = None,
    limit: int = 100,
    kind: str | None = None,
    kind_prefix: str | None = None,
    risk_tier: str | None = None,
    source: str | None = None,
    since_ts: str | None = None,
    until_ts: str | None = None,
    max_seconds: int = 15,
    poll_interval_ms: int = 500,
) -> StreamingResponse:
    _enforce_remote_control("control.remote.read")
    _enforce_remote_rbac(request, "control.remote.read")
    _enforce_remote_rbac(request, "approvals.read")
    normalized_session_id = str(session_id or "").strip()
    normalized_kind = str(kind or "").strip() or None
    normalized_kind_prefix = str(kind_prefix or "").strip() or None
    normalized_risk_tier = _normalize_remote_feed_risk_tier(risk_tier)
    normalized_source = _normalize_remote_feed_source(source)
    normalized_since_ts = _normalize_remote_feed_timestamp(since_ts, field_name="since_ts")
    normalized_until_ts = _normalize_remote_feed_timestamp(until_ts, field_name="until_ts")
    if normalized_since_ts and normalized_until_ts and normalized_since_ts > normalized_until_ts:
        raise HTTPException(status_code=400, detail="since_ts must be <= until_ts")
    initial_rows = _build_remote_feed_rows(
        session_id=normalized_session_id or None,
        kind=normalized_kind,
        kind_prefix=normalized_kind_prefix,
        risk_tier=normalized_risk_tier,
        source=normalized_source,
        since_ts=normalized_since_ts,
        until_ts=normalized_until_ts,
    )
    parsed_cursor = _parse_activity_cursor(cursor)
    start_cursor = parsed_cursor if parsed_cursor is not None else len(initial_rows)
    max_events = max(1, min(limit, 2000))
    stream_window_seconds = max(1, min(max_seconds, 120))
    sleep_seconds = max(0.05, min(float(poll_interval_ms) / 1000.0, 5.0))

    async def _iter_sse():
        current_cursor = max(0, start_cursor)
        emitted = 0
        deadline = time.monotonic() + float(stream_window_seconds)
        yield _sse_event(
            "meta",
            {
                "session_id": normalized_session_id or None,
                "kind": normalized_kind,
                "kind_prefix": normalized_kind_prefix,
                "risk_tier": normalized_risk_tier,
                "source": normalized_source,
                "since_ts": normalized_since_ts,
                "until_ts": normalized_until_ts,
                "cursor": str(current_cursor),
                "max_events": max_events,
                "max_seconds": stream_window_seconds,
            },
        )
        while emitted < max_events and time.monotonic() < deadline:
            rows = _build_remote_feed_rows(
                session_id=normalized_session_id or None,
                kind=normalized_kind,
                kind_prefix=normalized_kind_prefix,
                risk_tier=normalized_risk_tier,
                source=normalized_source,
                since_ts=normalized_since_ts,
                until_ts=normalized_until_ts,
            )
            batch, next_cursor, has_more = _slice_activity_rows(
                rows=rows,
                cursor=current_cursor,
                limit=max_events - emitted,
            )
            if batch:
                for item in batch:
                    emitted += 1
                    current_cursor += 1
                    yield _sse_event(
                        "feed",
                        {
                            "session_id": str(item.get("session_id", "")).strip() or None,
                            "cursor": str(current_cursor - 1),
                            "next_cursor": str(current_cursor),
                            "has_more": has_more,
                            "entry": item,
                        },
                    )
                    if emitted >= max_events:
                        break
                continue

            yield _sse_event(
                "heartbeat",
                {
                    "session_id": normalized_session_id or None,
                    "kind": normalized_kind,
                    "kind_prefix": normalized_kind_prefix,
                    "risk_tier": normalized_risk_tier,
                    "source": normalized_source,
                    "since_ts": normalized_since_ts,
                    "until_ts": normalized_until_ts,
                    "cursor": str(current_cursor),
                },
            )
            await asyncio.sleep(sleep_seconds)

        yield _sse_event(
            "end",
            {
                "session_id": normalized_session_id or None,
                "kind": normalized_kind,
                "kind_prefix": normalized_kind_prefix,
                "risk_tier": normalized_risk_tier,
                "source": normalized_source,
                "since_ts": normalized_since_ts,
                "until_ts": normalized_until_ts,
                "cursor": str(current_cursor),
                "emitted": emitted,
                "max_events": max_events,
            },
        )

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(_iter_sse(), media_type="text/event-stream", headers=headers)


@router.post("/control/remote/panic")
def control_remote_panic(
    request: Request,
    payload: ControlRemotePanicRequest | None = None,
) -> dict:
    _enforce_remote_control("control.remote.write")
    role = _enforce_remote_rbac(request, "control.remote.write")
    body = payload or ControlRemotePanicRequest()
    state_before = load_or_init_control_state(_fs, _repo_root, _workspace_root)
    summary = control_panic(
        request,
        payload=ControlPanicRequest(reason=str(body.reason).strip()),
    )
    state_after = load_or_init_control_state(_fs, _repo_root, _workspace_root)
    takeover_state = _load_or_init_takeover_state()
    resolved_session_id = (
        str(body.session_id or takeover_state.get("session_id") or takeover_state.get("last_session_id") or "").strip()
        or None
    )
    reason = str(body.reason).strip() or "remote.panic"
    receipt = _record_control_receipt(
        run_id=str(summary.get("run_id", "")),
        trace_id=str(summary.get("trace_id", "")),
        kind="control.remote.panic",
        reason=reason,
        before={"mode": state_before.get("mode"), "kill_switch": state_before.get("kill_switch")},
        after={"mode": state_after.get("mode"), "kill_switch": state_after.get("kill_switch")},
        session_id=resolved_session_id,
        metadata={"remote_command": "control.panic"},
    )
    append_takeover_activity(
        run_id=str(summary.get("run_id", "")),
        trace_id=str(summary.get("trace_id", "")),
        actor=role,
        kind="control.remote.panic",
        detail={
            "remote_command": "control.panic",
            "reason": reason,
            "mode": state_after.get("mode"),
            "kill_switch": bool(state_after.get("kill_switch", False)),
        },
        ok=True,
        session_id=resolved_session_id,
        allow_inactive=True,
        takeover_state=takeover_state,
    )
    return {
        "status": "ok",
        "run_id": summary.get("run_id"),
        "trace_id": summary.get("trace_id"),
        "command": "control.panic",
        "session_id": resolved_session_id,
        "summary": summary,
        "receipt_id": receipt.get("id"),
    }


@router.post("/control/remote/resume")
def control_remote_resume(
    request: Request,
    payload: ControlRemoteResumeRequest | None = None,
) -> dict:
    _enforce_remote_control("control.remote.write")
    role = _enforce_remote_rbac(request, "control.remote.write")
    body = payload or ControlRemoteResumeRequest()
    state_before = load_or_init_control_state(_fs, _repo_root, _workspace_root)
    summary = control_resume(
        request,
        payload=ControlResumeRequest(
            reason=str(body.reason).strip(),
            mode=str(body.mode).strip().lower() if body.mode is not None else None,
        ),
    )
    state_after = load_or_init_control_state(_fs, _repo_root, _workspace_root)
    takeover_state = _load_or_init_takeover_state()
    resolved_session_id = (
        str(body.session_id or takeover_state.get("session_id") or takeover_state.get("last_session_id") or "").strip()
        or None
    )
    reason = str(body.reason).strip() or "remote.resume"
    receipt = _record_control_receipt(
        run_id=str(summary.get("run_id", "")),
        trace_id=str(summary.get("trace_id", "")),
        kind="control.remote.resume",
        reason=reason,
        before={"mode": state_before.get("mode"), "kill_switch": state_before.get("kill_switch")},
        after={"mode": state_after.get("mode"), "kill_switch": state_after.get("kill_switch")},
        session_id=resolved_session_id,
        metadata={"remote_command": "control.resume"},
    )
    append_takeover_activity(
        run_id=str(summary.get("run_id", "")),
        trace_id=str(summary.get("trace_id", "")),
        actor=role,
        kind="control.remote.resume",
        detail={
            "remote_command": "control.resume",
            "reason": reason,
            "mode": state_after.get("mode"),
            "kill_switch": bool(state_after.get("kill_switch", False)),
        },
        ok=True,
        session_id=resolved_session_id,
        allow_inactive=True,
        takeover_state=takeover_state,
    )
    return {
        "status": "ok",
        "run_id": summary.get("run_id"),
        "trace_id": summary.get("trace_id"),
        "command": "control.resume",
        "session_id": resolved_session_id,
        "summary": summary,
        "receipt_id": receipt.get("id"),
    }


@router.post("/control/remote/takeover/request")
def control_remote_takeover_request(request: Request, payload: ControlRemoteTakeoverRequest) -> dict:
    _enforce_remote_control("control.remote.write")
    role = _enforce_remote_rbac(request, "control.remote.write")
    before = _load_or_init_takeover_state()
    summary = control_takeover_request(
        request,
        payload=ControlTakeoverRequest(
            objective=str(payload.objective).strip(),
            reason=str(payload.reason).strip(),
            repos=payload.repos,
            workspaces=payload.workspaces,
            apps=payload.apps,
        ),
    )
    takeover_after = summary.get("takeover", {}) if isinstance(summary.get("takeover"), dict) else {}
    resolved_session_id = str(takeover_after.get("session_id") or "").strip() or None
    reason = str(payload.reason).strip() or "remote.takeover.request"
    receipt = _record_control_receipt(
        run_id=str(summary.get("run_id", "")),
        trace_id=str(summary.get("trace_id", "")),
        kind="control.remote.takeover.request",
        reason=reason,
        before={"status": before.get("status"), "objective": before.get("objective")},
        after={
            "status": takeover_after.get("status"),
            "objective": takeover_after.get("objective"),
            "session_id": resolved_session_id,
        },
        session_id=resolved_session_id,
        metadata={"remote_command": "control.takeover.request"},
    )
    append_takeover_activity(
        run_id=str(summary.get("run_id", "")),
        trace_id=str(summary.get("trace_id", "")),
        actor=role,
        kind="control.remote.takeover.request",
        detail={
            "remote_command": "control.takeover.request",
            "reason": reason,
            "objective": takeover_after.get("objective"),
            "session_id": resolved_session_id,
        },
        ok=True,
        session_id=resolved_session_id,
        allow_inactive=True,
        takeover_state=takeover_after if isinstance(takeover_after, dict) else None,
    )
    return {
        "status": "ok",
        "run_id": summary.get("run_id"),
        "trace_id": summary.get("trace_id"),
        "command": "control.takeover.request",
        "session_id": resolved_session_id,
        "summary": summary,
        "receipt_id": receipt.get("id"),
    }


@router.post("/control/remote/takeover/confirm")
def control_remote_takeover_confirm(
    request: Request,
    payload: ControlRemoteTakeoverConfirmRequest | None = None,
) -> dict:
    _enforce_remote_control("control.remote.write")
    role = _enforce_remote_rbac(request, "control.remote.write")
    body = payload or ControlRemoteTakeoverConfirmRequest()
    before = _load_or_init_takeover_state()
    summary = control_takeover_confirm(
        request,
        payload=ControlTakeoverConfirmRequest(
            confirm=bool(body.confirm),
            reason=str(body.reason).strip(),
            mode=str(body.mode).strip().lower() or "pilot",
        ),
    )
    takeover_after = summary.get("takeover", {}) if isinstance(summary.get("takeover"), dict) else {}
    resolved_session_id = (
        str(body.session_id or takeover_after.get("session_id") or before.get("session_id") or "").strip() or None
    )
    reason = str(body.reason).strip() or "remote.takeover.confirm"
    receipt = _record_control_receipt(
        run_id=str(summary.get("run_id", "")),
        trace_id=str(summary.get("trace_id", "")),
        kind="control.remote.takeover.confirm",
        reason=reason,
        before={"status": before.get("status"), "objective": before.get("objective"), "session_id": before.get("session_id")},
        after={
            "status": takeover_after.get("status"),
            "objective": takeover_after.get("objective"),
            "session_id": takeover_after.get("session_id"),
            "mode": summary.get("mode"),
        },
        session_id=resolved_session_id,
        metadata={"remote_command": "control.takeover.confirm"},
    )
    append_takeover_activity(
        run_id=str(summary.get("run_id", "")),
        trace_id=str(summary.get("trace_id", "")),
        actor=role,
        kind="control.remote.takeover.confirm",
        detail={
            "remote_command": "control.takeover.confirm",
            "reason": reason,
            "mode": summary.get("mode"),
            "session_id": resolved_session_id,
        },
        ok=True,
        session_id=resolved_session_id,
        allow_inactive=True,
        takeover_state=takeover_after if isinstance(takeover_after, dict) else None,
    )
    return {
        "status": "ok",
        "run_id": summary.get("run_id"),
        "trace_id": summary.get("trace_id"),
        "command": "control.takeover.confirm",
        "session_id": resolved_session_id,
        "summary": summary,
        "receipt_id": receipt.get("id"),
    }


@router.post("/control/remote/takeover/handback")
def control_remote_takeover_handback(
    request: Request,
    payload: ControlRemoteTakeoverHandbackRequest | None = None,
) -> dict:
    _enforce_remote_control("control.remote.write")
    role = _enforce_remote_rbac(request, "control.remote.write")
    body = payload or ControlRemoteTakeoverHandbackRequest()
    before = _load_or_init_takeover_state()
    summary = control_takeover_handback(
        request,
        payload=ControlTakeoverHandbackRequest(
            summary=str(body.summary).strip(),
            verification=body.verification if isinstance(body.verification, dict) else {},
            pending_approvals=int(body.pending_approvals),
            mode=str(body.mode).strip().lower() if body.mode is not None else None,
            reason=str(body.reason).strip(),
        ),
    )
    takeover_after = summary.get("takeover", {}) if isinstance(summary.get("takeover"), dict) else {}
    resolved_session_id = (
        str(
            body.session_id
            or before.get("session_id")
            or takeover_after.get("last_session_id")
            or takeover_after.get("session_id")
            or ""
        ).strip()
        or None
    )
    reason = str(body.reason).strip() or "remote.takeover.handback"
    receipt = _record_control_receipt(
        run_id=str(summary.get("run_id", "")),
        trace_id=str(summary.get("trace_id", "")),
        kind="control.remote.takeover.handback",
        reason=reason,
        before={"status": before.get("status"), "objective": before.get("objective"), "session_id": before.get("session_id")},
        after={
            "status": takeover_after.get("status"),
            "objective": takeover_after.get("objective"),
            "session_id": takeover_after.get("session_id"),
            "last_session_id": takeover_after.get("last_session_id"),
            "mode": summary.get("mode"),
        },
        session_id=resolved_session_id,
        metadata={"remote_command": "control.takeover.handback"},
    )
    append_takeover_activity(
        run_id=str(summary.get("run_id", "")),
        trace_id=str(summary.get("trace_id", "")),
        actor=role,
        kind="control.remote.takeover.handback",
        detail={
            "remote_command": "control.takeover.handback",
            "reason": reason,
            "mode": summary.get("mode"),
            "pending_approvals": int(body.pending_approvals),
            "session_id": resolved_session_id,
        },
        ok=True,
        session_id=resolved_session_id,
        allow_inactive=True,
        takeover_state=takeover_after if isinstance(takeover_after, dict) else None,
    )
    return {
        "status": "ok",
        "run_id": summary.get("run_id"),
        "trace_id": summary.get("trace_id"),
        "command": "control.takeover.handback",
        "session_id": resolved_session_id,
        "summary": summary,
        "receipt_id": receipt.get("id"),
    }


def _control_remote_approval_decision(
    *,
    request: Request,
    approval_id: str,
    decision: str,
    payload: ControlRemoteApprovalDecisionRequest | None = None,
) -> dict:
    _enforce_remote_control("control.remote.write")
    role = _enforce_remote_rbac(request, "control.remote.write")
    if not can(role, "approvals.decide"):
        raise HTTPException(status_code=403, detail=f"RBAC denied: role={role}, action=approvals.decide")
    run_id = str(getattr(request.state, "run_id", uuid4()))
    trace_id = _normalize_trace_id(getattr(request.state, "trace_id", None), fallback_run_id=run_id)
    body = payload or ControlRemoteApprovalDecisionRequest()
    normalized_approval_id = str(approval_id).strip()
    if not normalized_approval_id:
        raise HTTPException(status_code=400, detail="approval_id is required")

    before = get_request(_fs, normalized_approval_id)
    if before is None:
        raise HTTPException(status_code=404, detail=f"Approval not found: {normalized_approval_id}")

    try:
        decision_event = add_decision(
            _fs,
            run_id=run_id,
            approval_id=normalized_approval_id,
            decision=decision,
            decided_by=role,
            note=str(body.note).strip(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if decision_event is None:
        raise HTTPException(status_code=404, detail=f"Approval not found: {normalized_approval_id}")
    after = get_request(_fs, normalized_approval_id)
    if after is None:
        raise HTTPException(status_code=404, detail=f"Approval not found after decision: {normalized_approval_id}")

    normalized_session_id = str(body.session_id or "").strip() or None
    receipt = _record_control_receipt(
        run_id=run_id,
        trace_id=trace_id,
        kind=f"control.remote.approval.{str(after.get('status', '')).strip().lower()}",
        reason="remote.approvals.decision",
        before={
            "approval_id": normalized_approval_id,
            "status": before.get("status"),
            "action": before.get("action"),
        },
        after={
            "approval_id": normalized_approval_id,
            "status": after.get("status"),
            "action": after.get("action"),
            "decided_by": role,
        },
        session_id=normalized_session_id,
        metadata={"approval_id": normalized_approval_id},
    )
    append_takeover_activity(
        run_id=run_id,
        trace_id=trace_id,
        actor=role,
        kind=f"control.remote.approval.{str(after.get('status', '')).strip().lower()}",
        detail={
            "approval_id": normalized_approval_id,
            "action": after.get("action"),
            "status": after.get("status"),
            "note": str(body.note).strip(),
        },
        ok=True,
        session_id=normalized_session_id,
        allow_inactive=True,
    )
    return {
        "status": "ok",
        "run_id": run_id,
        "trace_id": trace_id,
        "approval": after,
        "decision": decision_event,
        "receipt_id": receipt.get("id"),
    }


@router.post("/control/remote/approvals/{approval_id}/approve")
def control_remote_approval_approve(
    approval_id: str,
    request: Request,
    payload: ControlRemoteApprovalDecisionRequest | None = None,
) -> dict:
    return _control_remote_approval_decision(
        request=request,
        approval_id=approval_id,
        decision="approved",
        payload=payload,
    )


@router.post("/control/remote/approvals/{approval_id}/reject")
def control_remote_approval_reject(
    approval_id: str,
    request: Request,
    payload: ControlRemoteApprovalDecisionRequest | None = None,
) -> dict:
    return _control_remote_approval_decision(
        request=request,
        approval_id=approval_id,
        decision="rejected",
        payload=payload,
    )


@router.get("/control/takeover")
def control_takeover_state() -> dict:
    state = _load_or_init_takeover_state()
    return {"status": "ok", "takeover": state}


@router.get("/control/takeover/history")
def control_takeover_history(limit: int = 50) -> dict:
    rows = _read_takeover_history(limit=limit)
    return {"status": "ok", "count": len(rows), "history": rows}


@router.get("/control/takeover/sessions")
def control_takeover_sessions(limit: int = 20) -> dict:
    sessions = _build_takeover_sessions(limit=limit)
    return {"status": "ok", "count": len(sessions), "sessions": sessions}


@router.get("/control/takeover/sessions/{session_id}")
def control_takeover_session(session_id: str, limit: int = 200) -> dict:
    normalized_session_id = str(session_id).strip()
    if not normalized_session_id:
        raise HTTPException(status_code=400, detail="session_id is required")
    state = _load_or_init_takeover_state()
    transitions = [
        row
        for row in _read_jsonl_rows(_takeover_history_path)
        if str(row.get("session_id", "")).strip() == normalized_session_id
    ]
    activity = _read_takeover_activity_rows(session_id=normalized_session_id)
    exports = [
        row
        for row in _read_handback_export_index_rows()
        if str(row.get("session_id", "")).strip() == normalized_session_id
    ]
    active_session_id = str(state.get("session_id") or "").strip()
    last_session_id = str(state.get("last_session_id") or "").strip()
    if not transitions and not activity and not exports and normalized_session_id not in {active_session_id, last_session_id}:
        raise HTTPException(status_code=404, detail=f"Takeover session not found: {normalized_session_id}")

    summary = _build_takeover_session_summary(
        session_id=normalized_session_id,
        state=state,
        transitions=transitions,
        activity=activity,
        exports=exports,
    )
    receipts = _collect_handback_receipts_for_session(session_id=normalized_session_id, limit=limit)
    package_summary: dict[str, Any] | None = None
    try:
        package = control_takeover_handback_package(limit=limit, session_id=normalized_session_id)
        package_summary = package.get("summary", {})
    except HTTPException:
        package_summary = None

    return {
        "status": "ok",
        "session": summary,
        "timeline": {
            "transitions": _tail_rows(sorted(transitions, key=_session_event_ts), limit=limit, cap=1000),
            "activity": _tail_rows(sorted(activity, key=_session_event_ts), limit=limit, cap=5000),
        },
        "exports": _tail_rows(sorted(exports, key=_session_event_ts), limit=limit, cap=2000),
        "receipt_counts": {
            "decisions": len(receipts.get("decisions", [])),
            "logs": len(receipts.get("logs", [])),
            "ledger": len(receipts.get("ledger", [])),
        },
        "handback_package_summary": package_summary,
    }


@router.get("/control/takeover/activity")
def control_takeover_activity(
    limit: int = 100,
    session_id: str | None = None,
    cursor: str | None = None,
) -> dict:
    state = _load_or_init_takeover_state()
    resolved_session_id = _resolve_takeover_session_id(state=state, requested_session_id=session_id)
    rows = _read_takeover_activity_rows(session_id=resolved_session_id or None)

    parsed_cursor = _parse_activity_cursor(cursor)
    if parsed_cursor is None:
        normalized_limit = max(1, min(limit, 1000))
        start_cursor = max(0, len(rows) - normalized_limit)
    else:
        start_cursor = parsed_cursor
    chunk, next_cursor, has_more = _slice_activity_rows(rows=rows, cursor=start_cursor, limit=limit)

    return {
        "status": "ok",
        "takeover_status": str(state.get("status", "idle")).strip().lower() or "idle",
        "session_id": resolved_session_id or None,
        "cursor": str(start_cursor),
        "next_cursor": str(next_cursor),
        "has_more": has_more,
        "total_available": len(rows),
        "count": len(chunk),
        "activity": chunk,
    }


@router.get("/control/takeover/activity/stream")
async def control_takeover_activity_stream(
    session_id: str | None = None,
    cursor: str | None = None,
    limit: int = 100,
    max_seconds: int = 15,
    poll_interval_ms: int = 500,
) -> StreamingResponse:
    state = _load_or_init_takeover_state()
    resolved_session_id = _resolve_takeover_session_id(state=state, requested_session_id=session_id)
    initial_rows = _read_takeover_activity_rows(session_id=resolved_session_id or None)
    parsed_cursor = _parse_activity_cursor(cursor)
    start_cursor = parsed_cursor if parsed_cursor is not None else len(initial_rows)
    max_events = max(1, min(limit, 2000))
    stream_window_seconds = max(1, min(max_seconds, 120))
    sleep_seconds = max(0.05, min(float(poll_interval_ms) / 1000.0, 5.0))

    async def _iter_sse():
        current_cursor = max(0, start_cursor)
        emitted = 0
        deadline = time.monotonic() + float(stream_window_seconds)
        yield _sse_event(
            "meta",
            {
                "session_id": resolved_session_id or None,
                "takeover_status": str(state.get("status", "idle")).strip().lower() or "idle",
                "cursor": str(current_cursor),
                "max_events": max_events,
                "max_seconds": stream_window_seconds,
            },
        )
        while emitted < max_events and time.monotonic() < deadline:
            rows = _read_takeover_activity_rows(session_id=resolved_session_id or None)
            batch, next_cursor, has_more = _slice_activity_rows(
                rows=rows,
                cursor=current_cursor,
                limit=max_events - emitted,
            )
            if batch:
                for item in batch:
                    emitted += 1
                    current_cursor += 1
                    yield _sse_event(
                        "activity",
                        {
                            "session_id": str(item.get("session_id") or resolved_session_id or "").strip() or None,
                            "cursor": str(current_cursor - 1),
                            "next_cursor": str(current_cursor),
                            "has_more": has_more,
                            "activity": item,
                        },
                    )
                    if emitted >= max_events:
                        break
                continue

            yield _sse_event(
                "heartbeat",
                {
                    "session_id": resolved_session_id or None,
                    "cursor": str(current_cursor),
                },
            )
            await asyncio.sleep(sleep_seconds)
        yield _sse_event(
            "end",
            {
                "session_id": resolved_session_id or None,
                "cursor": str(current_cursor),
                "emitted": emitted,
                "max_events": max_events,
            },
        )

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(_iter_sse(), media_type="text/event-stream", headers=headers)


@router.get("/control/takeover/handback/package")
def control_takeover_handback_package(limit: int = 200, session_id: str | None = None) -> dict:
    state = _load_or_init_takeover_state()
    resolved_session_id = _resolve_takeover_session_id(
        state=state,
        requested_session_id=session_id,
        prefer_last=True,
    )
    if not resolved_session_id:
        raise HTTPException(status_code=404, detail="No takeover session available for handback package.")

    receipts = _collect_handback_receipts_for_session(session_id=resolved_session_id, limit=limit)
    latest_transition = receipts["transitions"][-1] if receipts["transitions"] else {}
    latest_activity = receipts["activity"][-1] if receipts["activity"] else {}

    return {
        "status": "ok",
        "session_id": resolved_session_id,
        "summary": {
            "latest_transition_kind": latest_transition.get("kind"),
            "latest_transition_ts": latest_transition.get("ts"),
            "latest_activity_kind": latest_activity.get("kind"),
            "latest_activity_ts": latest_activity.get("ts"),
            "counts": {
                "transitions": len(receipts["transitions"]),
                "activity": len(receipts["activity"]),
                "decisions": len(receipts["decisions"]),
                "logs": len(receipts["logs"]),
                "ledger": len(receipts["ledger"]),
            },
        },
        "timeline": {
            "transitions": receipts["transitions"],
            "activity": receipts["activity"],
        },
        "receipts": {
            "decisions": receipts["decisions"],
            "logs": receipts["logs"],
            "ledger": receipts["ledger"],
        },
    }


@router.get("/control/takeover/handback/exports")
def control_takeover_handback_exports(limit: int = 20, session_id: str | None = None) -> dict:
    rows = _read_jsonl_rows("control/handback_exports/index.jsonl")
    resolved_session_id = str(session_id or "").strip()
    if resolved_session_id:
        rows = [row for row in rows if str(row.get("session_id", "")).strip() == resolved_session_id]
    exports = _tail_rows(rows, limit=limit, cap=2000)
    return {
        "status": "ok",
        "session_id": resolved_session_id or None,
        "count": len(exports),
        "exports": exports,
    }


@router.get("/control/takeover/handback/exports/{export_id}")
def control_takeover_handback_export_by_id(export_id: str) -> dict:
    normalized_export_id = str(export_id).strip()
    if not normalized_export_id:
        raise HTTPException(status_code=400, detail="export_id is required")
    rows = _read_handback_export_index_rows()
    match = next((row for row in rows if str(row.get("id", "")).strip() == normalized_export_id), None)
    if not isinstance(match, dict):
        raise HTTPException(status_code=404, detail=f"Handback export not found: {normalized_export_id}")
    rel_path = str(match.get("path", "")).strip()
    if not rel_path:
        raise HTTPException(status_code=404, detail=f"Handback export path missing: {normalized_export_id}")
    try:
        raw = _fs.read_text(rel_path)
        doc = json.loads(raw)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read handback export {normalized_export_id}: {exc}")
    return {"status": "ok", "export": match, "document": doc}


@router.post("/control/takeover/handback/export")
def control_takeover_handback_export(
    request: Request,
    payload: ControlTakeoverHandbackExportRequest | None = None,
) -> dict:
    run_id = str(getattr(request.state, "run_id", uuid4()))
    trace_id = _normalize_trace_id(getattr(request.state, "trace_id", None), fallback_run_id=run_id)
    body = payload or ControlTakeoverHandbackExportRequest()
    state = _load_or_init_takeover_state()
    resolved_session_id = _resolve_takeover_session_id(
        state=state,
        requested_session_id=body.session_id,
        prefer_last=True,
    )
    if not resolved_session_id:
        raise HTTPException(status_code=404, detail="No takeover session available to export.")

    package = control_takeover_handback_package(limit=int(body.limit), session_id=resolved_session_id)
    export_id = str(uuid4())
    exported_at = utc_now_iso()
    export_rel_path = (
        f"control/handback_exports/{_safe_export_timestamp(exported_at)}_{resolved_session_id}_{export_id}.json"
    )
    export_doc = {
        "id": export_id,
        "ts": exported_at,
        "session_id": resolved_session_id,
        "run_id": run_id,
        "trace_id": trace_id,
        "source": "control.takeover.handback.package",
        "package": package,
    }
    _fs.write_text(export_rel_path, json.dumps(export_doc, ensure_ascii=False, indent=2))

    index_row = {
        "id": export_id,
        "ts": exported_at,
        "session_id": resolved_session_id,
        "run_id": run_id,
        "trace_id": trace_id,
        "path": export_rel_path,
        "summary": package.get("summary", {}),
    }
    _append_jsonl("control/handback_exports/index.jsonl", index_row)
    reason = str(body.reason).strip() or "manual_takeover_handback_export"
    receipt = _record_control_receipt(
        run_id=run_id,
        trace_id=trace_id,
        kind="control.takeover.handback.export",
        reason=reason,
        before={"session_id": resolved_session_id, "status": state.get("status")},
        after={
            "session_id": resolved_session_id,
            "export_id": export_id,
            "path": export_rel_path,
        },
        session_id=resolved_session_id,
        metadata={"artifact_path": export_rel_path, "export_id": export_id},
    )
    append_takeover_activity(
        run_id=run_id,
        trace_id=trace_id,
        actor=_role_from_request(request),
        kind="control.takeover.handback.exported",
        detail={
            "export_id": export_id,
            "path": export_rel_path,
            "counts": package.get("summary", {}).get("counts", {}),
        },
        ok=True,
        session_id=resolved_session_id,
        allow_inactive=True,
        takeover_state=state,
    )
    return {
        "status": "ok",
        "run_id": run_id,
        "trace_id": trace_id,
        "session_id": resolved_session_id,
        "export": {
            "id": export_id,
            "path": export_rel_path,
            "ts": exported_at,
        },
        "summary": package.get("summary", {}),
        "receipt_id": receipt.get("id"),
    }


@router.post("/control/takeover/request")
def control_takeover_request(request: Request, payload: ControlTakeoverRequest) -> dict:
    run_id = str(getattr(request.state, "run_id", uuid4()))
    trace_id = _normalize_trace_id(getattr(request.state, "trace_id", None), fallback_run_id=run_id)
    role = _role_from_request(request)
    before = _load_or_init_takeover_state()
    control_before = load_or_init_control_state(_fs, _repo_root, _workspace_root)
    if str(before.get("status", "idle")).strip().lower() == "active":
        raise HTTPException(status_code=409, detail="Takeover already active; handback before requesting again.")

    objective = payload.objective.strip()
    if not objective:
        raise HTTPException(status_code=400, detail="objective is required")
    reason = str(payload.reason).strip() or "manual_takeover_request"
    now = utc_now_iso()
    session_id = str(uuid4())
    after = _save_takeover_state(
        {
            **before,
            "status": "requested",
            "session_id": session_id,
            "objective": objective,
            "reason": reason,
            "scope": _resolve_takeover_scope(payload),
            "previous_mode": control_before.get("mode"),
            "previous_kill_switch": control_before.get("kill_switch"),
            "previous_scope": control_before.get("scopes", {}),
            "applied_scope": control_before.get("scopes", {}),
            "requested_by": role,
            "requested_at": now,
            "confirmed_at": None,
            "confirmation_reason": "",
            "handed_back_at": None,
            "handback_reason": "",
            "handback_summary": "",
            "handback_verification": {},
            "handback_pending_approvals": 0,
            "request_run_id": run_id,
            "request_trace_id": trace_id,
            "confirm_run_id": None,
            "confirm_trace_id": None,
            "handback_run_id": None,
            "handback_trace_id": None,
        }
    )
    receipt = _record_control_receipt(
        run_id=run_id,
        trace_id=trace_id,
        kind="control.takeover.request",
        reason=reason,
        before={"status": before.get("status"), "objective": before.get("objective")},
        after={
            "status": after.get("status"),
            "objective": after.get("objective"),
            "requested_by": after.get("requested_by"),
            "session_id": after.get("session_id"),
        },
        session_id=session_id,
    )
    _append_takeover_history(
        run_id=run_id,
        trace_id=trace_id,
        kind="control.takeover.request",
        reason=reason,
        before={"status": before.get("status"), "objective": before.get("objective")},
        after={
            "status": after.get("status"),
            "objective": after.get("objective"),
            "session_id": after.get("session_id"),
        },
        session_id=session_id,
    )
    append_takeover_activity(
        run_id=run_id,
        trace_id=trace_id,
        actor=role,
        kind="control.takeover.requested",
        detail={
            "objective": objective,
            "reason": reason,
            "scope": after.get("scope", {}),
        },
        ok=True,
        session_id=session_id,
        allow_inactive=True,
        takeover_state=after,
    )
    return {
        "status": "ok",
        "run_id": run_id,
        "trace_id": trace_id,
        "takeover": after,
        "receipt_id": receipt.get("id"),
    }


@router.post("/control/takeover/confirm")
def control_takeover_confirm(request: Request, payload: ControlTakeoverConfirmRequest | None = None) -> dict:
    run_id = str(getattr(request.state, "run_id", uuid4()))
    trace_id = _normalize_trace_id(getattr(request.state, "trace_id", None), fallback_run_id=run_id)
    body = payload or ControlTakeoverConfirmRequest()
    if not body.confirm:
        raise HTTPException(status_code=400, detail="Takeover confirmation requires confirm=true.")
    mode = str(body.mode).strip().lower()
    if mode != "pilot":
        raise HTTPException(status_code=400, detail="Takeover confirmation requires mode=pilot.")

    takeover_before = _load_or_init_takeover_state()
    if str(takeover_before.get("status", "idle")).strip().lower() != "requested":
        raise HTTPException(status_code=409, detail="No pending takeover request to confirm.")
    control_before = load_or_init_control_state(_fs, _repo_root, _workspace_root)
    if bool(control_before.get("kill_switch", False)):
        raise HTTPException(status_code=409, detail="Cannot confirm takeover while kill switch is active.")

    reason = str(body.reason).strip() or "manual_takeover_confirm"
    session_id = str(takeover_before.get("session_id") or "").strip() or str(uuid4())
    requested_scope = _sanitize_scope(
        takeover_before.get("scope", {}) if isinstance(takeover_before.get("scope"), dict) else {}
    )
    scoped_control = set_scope(
        _fs,
        repo_root=_repo_root,
        workspace_root=_workspace_root,
        repos=requested_scope.get("repos", []),
        workspaces=requested_scope.get("workspaces", []),
        apps=requested_scope.get("apps", []),
    )
    control_after = set_mode(
        _fs,
        repo_root=_repo_root,
        workspace_root=_workspace_root,
        mode="pilot",
        kill_switch=False,
    )
    takeover_after = _save_takeover_state(
        {
            **takeover_before,
            "status": "active",
            "session_id": session_id,
            "confirmed_at": utc_now_iso(),
            "confirmation_reason": reason,
            "confirm_run_id": run_id,
            "confirm_trace_id": trace_id,
            "applied_scope": control_after.get("scopes", scoped_control.get("scopes", requested_scope)),
        }
    )
    receipt = _record_control_receipt(
        run_id=run_id,
        trace_id=trace_id,
        kind="control.takeover.confirm",
        reason=reason,
        before={
            "status": takeover_before.get("status"),
            "objective": takeover_before.get("objective"),
            "mode": control_before.get("mode"),
            "kill_switch": control_before.get("kill_switch"),
        },
        after={
            "status": takeover_after.get("status"),
            "objective": takeover_after.get("objective"),
            "mode": control_after.get("mode"),
            "kill_switch": control_after.get("kill_switch"),
            "session_id": takeover_after.get("session_id"),
        },
        session_id=session_id,
    )
    _append_takeover_history(
        run_id=run_id,
        trace_id=trace_id,
        kind="control.takeover.confirm",
        reason=reason,
        before={"status": takeover_before.get("status"), "objective": takeover_before.get("objective")},
        after={
            "status": takeover_after.get("status"),
            "objective": takeover_after.get("objective"),
            "session_id": takeover_after.get("session_id"),
        },
        session_id=session_id,
    )
    append_takeover_activity(
        run_id=run_id,
        trace_id=trace_id,
        actor=_role_from_request(request),
        kind="control.takeover.confirmed",
        detail={
            "objective": str(takeover_after.get("objective", "")).strip(),
            "reason": reason,
            "mode": control_after.get("mode"),
            "scope": takeover_after.get("applied_scope", {}),
        },
        ok=True,
        session_id=session_id,
        allow_inactive=True,
        takeover_state=takeover_after,
    )
    return {
        "status": "ok",
        "run_id": run_id,
        "trace_id": trace_id,
        "mode": control_after.get("mode"),
        "kill_switch": control_after.get("kill_switch"),
        "takeover": takeover_after,
        "receipt_id": receipt.get("id"),
    }


@router.post("/control/takeover/handback")
def control_takeover_handback(request: Request, payload: ControlTakeoverHandbackRequest | None = None) -> dict:
    run_id = str(getattr(request.state, "run_id", uuid4()))
    trace_id = _normalize_trace_id(getattr(request.state, "trace_id", None), fallback_run_id=run_id)
    body = payload or ControlTakeoverHandbackRequest()
    takeover_before = _load_or_init_takeover_state()
    if str(takeover_before.get("status", "idle")).strip().lower() != "active":
        raise HTTPException(status_code=409, detail="No active takeover to hand back.")
    session_id = str(takeover_before.get("session_id") or "").strip()

    control_before = load_or_init_control_state(_fs, _repo_root, _workspace_root)
    restore_scope = _sanitize_scope(
        takeover_before.get("previous_scope", {})
        if isinstance(takeover_before.get("previous_scope"), dict)
        else control_before.get("scopes", {})
        if isinstance(control_before.get("scopes"), dict)
        else {}
    )
    scoped_control = set_scope(
        _fs,
        repo_root=_repo_root,
        workspace_root=_workspace_root,
        repos=restore_scope.get("repos", []),
        workspaces=restore_scope.get("workspaces", []),
        apps=restore_scope.get("apps", []),
    )

    if body.mode is None:
        mode_after = str(takeover_before.get("previous_mode", scoped_control.get("mode", "assist"))).strip().lower()
        kill_switch_after = bool(takeover_before.get("previous_kill_switch", False))
    else:
        mode_after = str(body.mode).strip().lower()
        kill_switch_after = False
    if mode_after not in VALID_MODES:
        raise HTTPException(status_code=400, detail=f"Invalid mode: {mode_after}")
    control_after = set_mode(
        _fs,
        repo_root=_repo_root,
        workspace_root=_workspace_root,
        mode=mode_after,
        kill_switch=kill_switch_after,
    )

    reason = str(body.reason).strip() or "manual_takeover_handback"
    takeover_after = _save_takeover_state(
        {
            **takeover_before,
            "status": "idle",
            "session_id": None,
            "last_session_id": session_id or takeover_before.get("last_session_id"),
            "handed_back_at": utc_now_iso(),
            "handback_reason": reason,
            "handback_summary": str(body.summary).strip(),
            "handback_verification": body.verification if isinstance(body.verification, dict) else {},
            "handback_pending_approvals": int(body.pending_approvals),
            "handback_run_id": run_id,
            "handback_trace_id": trace_id,
            "applied_scope": control_after.get("scopes", scoped_control.get("scopes", restore_scope)),
        }
    )
    receipt = _record_control_receipt(
        run_id=run_id,
        trace_id=trace_id,
        kind="control.takeover.handback",
        reason=reason,
        before={
            "status": takeover_before.get("status"),
            "objective": takeover_before.get("objective"),
            "mode": control_before.get("mode"),
            "kill_switch": control_before.get("kill_switch"),
        },
        after={
            "status": takeover_after.get("status"),
            "objective": takeover_after.get("objective"),
            "mode": control_after.get("mode"),
            "kill_switch": control_after.get("kill_switch"),
            "session_id": session_id or None,
        },
        session_id=session_id or None,
    )
    _append_takeover_history(
        run_id=run_id,
        trace_id=trace_id,
        kind="control.takeover.handback",
        reason=reason,
        before={"status": takeover_before.get("status"), "objective": takeover_before.get("objective")},
        after={
            "status": takeover_after.get("status"),
            "objective": takeover_after.get("objective"),
            "session_id": session_id or None,
        },
        session_id=session_id or None,
    )
    append_takeover_activity(
        run_id=run_id,
        trace_id=trace_id,
        actor=_role_from_request(request),
        kind="control.takeover.handed_back",
        detail={
            "summary": str(body.summary).strip(),
            "verification": body.verification if isinstance(body.verification, dict) else {},
            "pending_approvals": int(body.pending_approvals),
            "reason": reason,
            "mode": control_after.get("mode"),
        },
        ok=True,
        session_id=session_id or None,
        allow_inactive=True,
        takeover_state=takeover_after,
    )
    return {
        "status": "ok",
        "run_id": run_id,
        "trace_id": trace_id,
        "mode": control_after.get("mode"),
        "kill_switch": control_after.get("kill_switch"),
        "takeover": takeover_after,
        "receipt_id": receipt.get("id"),
    }
