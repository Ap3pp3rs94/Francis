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
