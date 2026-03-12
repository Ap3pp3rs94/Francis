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
from francis_policy.rbac import can
from services.orchestrator.app.control_state import check_action_allowed
from services.orchestrator.app.portability_store import (
    apply_portability_import,
    build_portability_state,
    export_portability_bundle,
    preview_portability_import,
)

router = APIRouter(tags=["portability"])

_workspace_root = Path(settings.workspace_root).resolve()
_repo_root = _workspace_root.parent
_fs = WorkspaceFS(
    roots=[_workspace_root],
    journal_path=(_workspace_root / "journals" / "fs.jsonl").resolve(),
)
_ledger = RunLedger(_fs, rel_path="runs/run_ledger.jsonl")


class PortabilityExportRequest(BaseModel):
    label: str = Field(default="", max_length=120)
    note: str = Field(default="", max_length=240)


class PortabilityImportPreviewRequest(BaseModel):
    bundle_id: str = Field(default="", max_length=120)
    path: str = Field(default="", max_length=260)


class PortabilityImportApplyRequest(BaseModel):
    preview_id: str = Field(default="", max_length=120)
    bundle_id: str = Field(default="", max_length=120)
    path: str = Field(default="", max_length=260)


def _append_jsonl(rel_path: str, row: dict[str, Any]) -> None:
    try:
        raw = _fs.read_text(rel_path)
    except Exception:
        raw = ""
    if raw and not raw.endswith("\n"):
        raw += "\n"
    _fs.write_text(rel_path, raw + json.dumps(row, ensure_ascii=False) + "\n")


def _role_from_request(request: Request) -> str:
    return request.headers.get("x-francis-role", "architect").strip().lower()


def _enforce_rbac(request: Request, action: str) -> str:
    role = _role_from_request(request)
    if not can(role, action):
        raise HTTPException(status_code=403, detail=f"RBAC denied: role={role}, action={action}")
    return role


def _enforce_control(action: str, *, mutating: bool) -> None:
    allowed, reason, _state = check_action_allowed(
        _fs,
        repo_root=_repo_root,
        workspace_root=_workspace_root,
        app="portability",
        action=action,
        mutating=mutating,
    )
    if not allowed:
        raise HTTPException(status_code=403, detail=f"Control denied: {reason}")


def _record_receipt(
    *,
    run_id: str,
    trace_id: str,
    kind: str,
    actor: str,
    summary: dict[str, Any],
    reason: str,
) -> None:
    receipt = {
        "id": str(uuid4()),
        "ts": utc_now_iso(),
        "run_id": run_id,
        "trace_id": trace_id,
        "kind": kind,
        "actor": actor,
        "reason": reason,
        "summary": summary,
    }
    _append_jsonl("logs/francis.log.jsonl", receipt)
    _append_jsonl("journals/decisions.jsonl", receipt)
    _ledger.append(run_id=run_id, kind=kind, summary={"trace_id": trace_id, "actor": actor, **summary})


@router.get("/portability/state")
def portability_state(request: Request) -> dict[str, Any]:
    _enforce_control("portability.read", mutating=False)
    _enforce_rbac(request, "portability.read")
    return {"status": "ok", **build_portability_state(_fs, repo_root=_repo_root, workspace_root=_workspace_root)}


@router.post("/portability/export")
def portability_export(request: Request, payload: PortabilityExportRequest | None = None) -> dict[str, Any]:
    _enforce_control("portability.write", mutating=True)
    role = _enforce_rbac(request, "portability.write")
    run_id = str(getattr(request.state, "run_id", uuid4()))
    trace_id = str(getattr(request.state, "trace_id", None) or run_id)
    body = payload or PortabilityExportRequest()
    result = export_portability_bundle(
        _fs,
        repo_root=_repo_root,
        workspace_root=_workspace_root,
        actor=role,
        label=body.label.strip(),
        note=body.note.strip(),
    )
    _record_receipt(
        run_id=run_id,
        trace_id=trace_id,
        kind="portability.bundle.exported",
        actor=role,
        reason=result["summary"],
        summary={
            "bundle_id": result["bundle_id"],
            "path": result["path"],
            "label": result["label"],
            "counts": result["counts"],
        },
    )
    return {"status": "ok", "run_id": run_id, "trace_id": trace_id, **result}


@router.post("/portability/import/preview")
def portability_import_preview(
    request: Request,
    payload: PortabilityImportPreviewRequest | None = None,
) -> dict[str, Any]:
    _enforce_control("portability.write", mutating=True)
    role = _enforce_rbac(request, "portability.write")
    run_id = str(getattr(request.state, "run_id", uuid4()))
    trace_id = str(getattr(request.state, "trace_id", None) or run_id)
    body = payload or PortabilityImportPreviewRequest()
    try:
        result = preview_portability_import(
            _fs,
            repo_root=_repo_root,
            workspace_root=_workspace_root,
            bundle_id=body.bundle_id.strip(),
            path=body.path.strip(),
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    preview = result.get("preview", {}) if isinstance(result.get("preview"), dict) else {}
    _record_receipt(
        run_id=run_id,
        trace_id=trace_id,
        kind="portability.bundle.previewed",
        actor=role,
        reason=str(preview.get("summary", "")).strip() or "Preview continuity bundle import",
        summary={
            "bundle_id": str(preview.get("bundle_id", "")).strip(),
            "preview_id": str(preview.get("preview_id", "")).strip(),
            "warning_count": len(preview.get("warnings", [])) if isinstance(preview.get("warnings"), list) else 0,
        },
    )
    return {"status": "ok", "run_id": run_id, "trace_id": trace_id, **result}


@router.post("/portability/import/apply")
def portability_import_apply(
    request: Request,
    payload: PortabilityImportApplyRequest | None = None,
) -> dict[str, Any]:
    _enforce_control("portability.write", mutating=True)
    role = _enforce_rbac(request, "portability.write")
    run_id = str(getattr(request.state, "run_id", uuid4()))
    trace_id = str(getattr(request.state, "trace_id", None) or run_id)
    body = payload or PortabilityImportApplyRequest()
    try:
        result = apply_portability_import(
            _fs,
            repo_root=_repo_root,
            workspace_root=_workspace_root,
            actor=role,
            preview_id=body.preview_id.strip(),
            bundle_id=body.bundle_id.strip(),
            path=body.path.strip(),
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _record_receipt(
        run_id=run_id,
        trace_id=trace_id,
        kind="portability.bundle.imported",
        actor=role,
        reason=result["summary"],
        summary={
            "bundle_id": result["bundle_id"],
            "import_id": result["import_id"],
            "warning_count": len(result.get("warnings", [])),
        },
    )
    return {"status": "ok", "run_id": run_id, "trace_id": trace_id, **result}
