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
from services.orchestrator.app.federation_store import get_paired_node
from services.orchestrator.app.managed_copy_store import (
    build_managed_copy_state,
    create_copy,
    materialize_copy,
    quarantine_copy,
    record_delta,
    replace_copy,
)

router = APIRouter(tags=["managed-copies"])

_workspace_root = Path(settings.workspace_root).resolve()
_repo_root = _workspace_root.parent
_fs = WorkspaceFS(
    roots=[_workspace_root],
    journal_path=(_workspace_root / "journals" / "fs.jsonl").resolve(),
)
_ledger = RunLedger(_fs, rel_path="runs/run_ledger.jsonl")


class ManagedCopyCreateRequest(BaseModel):
    customer_label: str = Field(min_length=1, max_length=160)
    baseline_version: str = Field(default="francis-core", min_length=1, max_length=120)
    sla_tier: str = Field(default="standard", min_length=1, max_length=40)
    capability_packs: list[str] = Field(default_factory=list)
    notes: str = ""


class ManagedCopyDeltaRequest(BaseModel):
    signal_kind: str = Field(default="capability_signal", min_length=1, max_length=80)
    summary: str = Field(min_length=1, max_length=280)
    evidence_refs: list[str] = Field(default_factory=list)
    capability_packs: list[str] = Field(default_factory=list)
    source_node_id: str | None = None


class ManagedCopyQuarantineRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=280)


class ManagedCopyReplaceRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=280)
    baseline_version: str | None = Field(default=None, max_length=120)


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


def _enforce_control(action: str, *, mutating: bool = False) -> None:
    allowed, reason, _state = check_action_allowed(
        _fs,
        repo_root=_repo_root,
        workspace_root=_workspace_root,
        app="managed_copies",
        action=action,
        mutating=mutating,
    )
    if not allowed:
        raise HTTPException(status_code=403, detail=f"Control denied: {reason}")


def _record_managed_copy_receipt(
    *,
    run_id: str,
    trace_id: str,
    kind: str,
    actor: str,
    copy_id: str,
    reason: str,
    summary: dict[str, Any],
) -> dict[str, Any]:
    receipt = {
        "id": str(uuid4()),
        "ts": utc_now_iso(),
        "run_id": run_id,
        "trace_id": trace_id,
        "kind": kind,
        "actor": actor,
        "copy_id": copy_id,
        "reason": reason,
        "summary": summary,
    }
    _append_jsonl("logs/francis.log.jsonl", receipt)
    _append_jsonl("journals/decisions.jsonl", receipt)
    _ledger.append(
        run_id=run_id,
        kind=kind,
        summary={
            "trace_id": trace_id,
            "actor": actor,
            "copy_id": copy_id,
            **summary,
        },
    )
    return receipt


def _validate_source_node(source_node_id: str | None) -> dict[str, Any] | None:
    normalized_source_node_id = str(source_node_id or "").strip()
    if not normalized_source_node_id:
        return None
    node = get_paired_node(
        _fs,
        repo_root=_repo_root,
        workspace_root=_workspace_root,
        node_id=normalized_source_node_id,
    )
    if node is None:
        raise HTTPException(status_code=404, detail=f"Federation node not found: {normalized_source_node_id}")
    if str(node.get("status", "")).strip().lower() == "revoked":
        raise HTTPException(status_code=409, detail=f"Federation node {normalized_source_node_id} is revoked")
    return node


@router.get("/managed-copies/state")
def managed_copy_state(request: Request) -> dict[str, Any]:
    _enforce_control("managed_copies.read")
    _enforce_rbac(request, "managed_copies.read")
    state = build_managed_copy_state(_fs)
    return {"status": "ok", **state}


@router.post("/managed-copies/create")
def managed_copy_create(request: Request, payload: ManagedCopyCreateRequest) -> dict[str, Any]:
    _enforce_control("managed_copies.write", mutating=True)
    role = _enforce_rbac(request, "managed_copies.write")
    run_id = str(getattr(request.state, "run_id", uuid4()))
    trace_id = str(getattr(request.state, "trace_id", None) or run_id)
    copy_entry = create_copy(
        _fs,
        customer_label=payload.customer_label.strip(),
        baseline_version=payload.baseline_version.strip(),
        sla_tier=payload.sla_tier.strip().lower(),
        capability_packs=[str(item).strip() for item in payload.capability_packs if str(item).strip()],
        notes=payload.notes.strip(),
        created_by=role,
    )
    _record_managed_copy_receipt(
        run_id=run_id,
        trace_id=trace_id,
        kind="managed.copy.created",
        actor=role,
        copy_id=str(copy_entry.get("copy_id", "")).strip(),
        reason=f"Created managed copy for {str(copy_entry.get('customer_label', '')).strip() or 'customer'}",
        summary={
            "customer_label": str(copy_entry.get("customer_label", "")).strip(),
            "status": str(copy_entry.get("status", "")).strip(),
            "sla_tier": str(copy_entry.get("sla_tier", "")).strip(),
            "baseline_version": str(copy_entry.get("baseline_version", "")).strip(),
        },
    )
    return {"status": "ok", "run_id": run_id, "trace_id": trace_id, "copy": copy_entry, "state": build_managed_copy_state(_fs)}


@router.post("/managed-copies/copies/{copy_id}/delta")
def managed_copy_delta(copy_id: str, request: Request, payload: ManagedCopyDeltaRequest) -> dict[str, Any]:
    _enforce_control("managed_copies.write", mutating=True)
    role = _enforce_rbac(request, "managed_copies.write")
    run_id = str(getattr(request.state, "run_id", uuid4()))
    trace_id = str(getattr(request.state, "trace_id", None) or run_id)
    source_node = _validate_source_node(payload.source_node_id)
    try:
        delta = record_delta(
            _fs,
            run_id=run_id,
            copy_id=str(copy_id).strip(),
            signal_kind=payload.signal_kind.strip(),
            summary=payload.summary.strip(),
            evidence_refs=[str(item).strip() for item in payload.evidence_refs if str(item).strip()],
            capability_packs=[str(item).strip() for item in payload.capability_packs if str(item).strip()],
            source_node_id=str(source_node.get("node_id", "")).strip() if source_node is not None else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if delta is None:
        raise HTTPException(status_code=404, detail=f"Managed copy not found: {copy_id}")
    _record_managed_copy_receipt(
        run_id=run_id,
        trace_id=trace_id,
        kind="managed.copy.delta.recorded",
        actor=role,
        copy_id=str(copy_id).strip(),
        reason=payload.summary.strip(),
        summary={
            "signal_kind": str(delta.get("signal_kind", "")).strip(),
            "source_node_id": str(delta.get("source_node_id", "")).strip() or None,
            "capability_packs": delta.get("capability_packs", []),
            "delta_model": str(delta.get("delta_model", "")).strip(),
        },
    )
    return {"status": "ok", "run_id": run_id, "trace_id": trace_id, "delta": delta, "state": build_managed_copy_state(_fs)}


@router.post("/managed-copies/copies/{copy_id}/materialize")
def managed_copy_materialize(copy_id: str, request: Request) -> dict[str, Any]:
    _enforce_control("managed_copies.write", mutating=True)
    role = _enforce_rbac(request, "managed_copies.write")
    run_id = str(getattr(request.state, "run_id", uuid4()))
    trace_id = str(getattr(request.state, "trace_id", None) or run_id)
    copy_entry = materialize_copy(_fs, copy_id=str(copy_id).strip())
    if copy_entry is None:
        raise HTTPException(status_code=404, detail=f"Managed copy not found: {copy_id}")
    runtime = copy_entry.get("runtime", {}) if isinstance(copy_entry.get("runtime"), dict) else {}
    _record_managed_copy_receipt(
        run_id=run_id,
        trace_id=trace_id,
        kind="managed.copy.materialized",
        actor=role,
        copy_id=str(copy_entry.get("copy_id", "")).strip(),
        reason="Materialized managed copy runtime namespace.",
        summary={
            "customer_label": str(copy_entry.get("customer_label", "")).strip(),
            "namespace_root": str(runtime.get("namespace_root", "")).strip(),
            "materialized": bool(runtime.get("materialized", False)),
            "missing_count": int(runtime.get("missing_count", 0) or 0),
        },
    )
    return {"status": "ok", "run_id": run_id, "trace_id": trace_id, "copy": copy_entry, "state": build_managed_copy_state(_fs)}


@router.post("/managed-copies/copies/{copy_id}/quarantine")
def managed_copy_quarantine(copy_id: str, request: Request, payload: ManagedCopyQuarantineRequest) -> dict[str, Any]:
    _enforce_control("managed_copies.write", mutating=True)
    role = _enforce_rbac(request, "managed_copies.write")
    run_id = str(getattr(request.state, "run_id", uuid4()))
    trace_id = str(getattr(request.state, "trace_id", None) or run_id)
    copy_entry = quarantine_copy(_fs, copy_id=str(copy_id).strip(), reason=payload.reason.strip())
    if copy_entry is None:
        raise HTTPException(status_code=404, detail=f"Managed copy not found: {copy_id}")
    _record_managed_copy_receipt(
        run_id=run_id,
        trace_id=trace_id,
        kind="managed.copy.quarantined",
        actor=role,
        copy_id=str(copy_entry.get("copy_id", "")).strip(),
        reason=payload.reason.strip(),
        summary={
            "customer_label": str(copy_entry.get("customer_label", "")).strip(),
            "status": str(copy_entry.get("status", "")).strip(),
            "quarantine_reason": str(copy_entry.get("quarantine_reason", "")).strip(),
        },
    )
    return {"status": "ok", "run_id": run_id, "trace_id": trace_id, "copy": copy_entry, "state": build_managed_copy_state(_fs)}


@router.post("/managed-copies/copies/{copy_id}/replace")
def managed_copy_replace(copy_id: str, request: Request, payload: ManagedCopyReplaceRequest) -> dict[str, Any]:
    _enforce_control("managed_copies.write", mutating=True)
    role = _enforce_rbac(request, "managed_copies.write")
    run_id = str(getattr(request.state, "run_id", uuid4()))
    trace_id = str(getattr(request.state, "trace_id", None) or run_id)
    try:
        result = replace_copy(
            _fs,
            copy_id=str(copy_id).strip(),
            reason=payload.reason.strip(),
            baseline_version=str(payload.baseline_version or "").strip() or None,
            replaced_by=role,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail=f"Managed copy not found: {copy_id}")
    replaced, replacement = result
    _record_managed_copy_receipt(
        run_id=run_id,
        trace_id=trace_id,
        kind="managed.copy.replaced",
        actor=role,
        copy_id=str(replaced.get("copy_id", "")).strip(),
        reason=payload.reason.strip(),
        summary={
            "customer_label": str(replaced.get("customer_label", "")).strip(),
            "replacement_copy_id": str(replacement.get("copy_id", "")).strip(),
            "baseline_version": str(replacement.get("baseline_version", "")).strip(),
            "status": str(replaced.get("status", "")).strip(),
        },
    )
    return {
        "status": "ok",
        "run_id": run_id,
        "trace_id": trace_id,
        "replaced": replaced,
        "replacement": replacement,
        "state": build_managed_copy_state(_fs),
    }
