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
    mode: str | None = Field(default="assist", description="Optional control mode to apply at handback.")
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
        "objective": "",
        "reason": "",
        "scope": control.get("scopes", {}),
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
) -> dict[str, Any]:
    receipt = {
        "id": str(uuid4()),
        "ts": utc_now_iso(),
        "run_id": run_id,
        "trace_id": trace_id,
        "kind": kind,
        "reason": reason,
        "before": before,
        "after": after,
    }
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
        },
    )
    return receipt


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


@router.post("/control/takeover/request")
def control_takeover_request(request: Request, payload: ControlTakeoverRequest) -> dict:
    run_id = str(getattr(request.state, "run_id", uuid4()))
    trace_id = _normalize_trace_id(getattr(request.state, "trace_id", None), fallback_run_id=run_id)
    role = _role_from_request(request)
    before = _load_or_init_takeover_state()
    if str(before.get("status", "idle")).strip().lower() == "active":
        raise HTTPException(status_code=409, detail="Takeover already active; handback before requesting again.")

    objective = payload.objective.strip()
    if not objective:
        raise HTTPException(status_code=400, detail="objective is required")
    reason = str(payload.reason).strip() or "manual_takeover_request"
    now = utc_now_iso()
    after = _save_takeover_state(
        {
            **before,
            "status": "requested",
            "objective": objective,
            "reason": reason,
            "scope": _resolve_takeover_scope(payload),
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
        },
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
            "confirmed_at": utc_now_iso(),
            "confirmation_reason": reason,
            "confirm_run_id": run_id,
            "confirm_trace_id": trace_id,
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
        },
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

    control_before = load_or_init_control_state(_fs, _repo_root, _workspace_root)
    control_after = control_before
    if body.mode is not None:
        mode_after = str(body.mode).strip().lower()
        if mode_after not in VALID_MODES:
            raise HTTPException(status_code=400, detail=f"Invalid mode: {mode_after}")
        control_after = set_mode(
            _fs,
            repo_root=_repo_root,
            workspace_root=_workspace_root,
            mode=mode_after,
            kill_switch=False,
        )

    reason = str(body.reason).strip() or "manual_takeover_handback"
    takeover_after = _save_takeover_state(
        {
            **takeover_before,
            "status": "idle",
            "handed_back_at": utc_now_iso(),
            "handback_reason": reason,
            "handback_summary": str(body.summary).strip(),
            "handback_verification": body.verification if isinstance(body.verification, dict) else {},
            "handback_pending_approvals": int(body.pending_approvals),
            "handback_run_id": run_id,
            "handback_trace_id": trace_id,
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
        },
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
