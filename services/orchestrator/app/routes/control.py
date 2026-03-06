from __future__ import annotations

import asyncio
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
_ledger = RunLedger(_fs, rel_path="runs/run_ledger.jsonl")
_takeover_state_path = "control/takeover.json"
_takeover_history_path = "control/takeover_history.jsonl"
_takeover_activity_path = "control/takeover_activity.jsonl"


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
    if payload.repos is not None:
        scope["repos"] = [str(item) for item in payload.repos if isinstance(item, str) and str(item).strip()]
    if payload.workspaces is not None:
        scope["workspaces"] = [
            str(item) for item in payload.workspaces if isinstance(item, str) and str(item).strip()
        ]
    if payload.apps is not None:
        scope["apps"] = [str(item) for item in payload.apps if isinstance(item, str) and str(item).strip()]
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


@router.get("/control/takeover")
def control_takeover_state() -> dict:
    state = _load_or_init_takeover_state()
    return {"status": "ok", "takeover": state}


@router.get("/control/takeover/history")
def control_takeover_history(limit: int = 50) -> dict:
    rows = _read_takeover_history(limit=limit)
    return {"status": "ok", "count": len(rows), "history": rows}


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
