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
from services.orchestrator.app.federation_store import (
    load_or_init_topology,
    heartbeat_node,
    pair_node,
    revoke_node,
)

router = APIRouter(tags=["federation"])

_workspace_root = Path(settings.workspace_root).resolve()
_repo_root = _workspace_root.parent
_fs = WorkspaceFS(
    roots=[_workspace_root],
    journal_path=(_workspace_root / "journals" / "fs.jsonl").resolve(),
)
_ledger = RunLedger(_fs, rel_path="runs/run_ledger.jsonl")


class FederationPairRequest(BaseModel):
    label: str = Field(min_length=1, max_length=120)
    role: str = Field(default="always_on", min_length=1, max_length=40)
    trust_level: str = Field(default="scoped", min_length=1, max_length=20)
    apps: list[str] = Field(default_factory=list)
    remote_approvals: bool = True
    away_continuity: bool = False
    receipt_summary: bool = True
    notes: str = ""


class FederationHeartbeatRequest(BaseModel):
    status: str = Field(default="active", min_length=1, max_length=20)
    sync_summary: str = ""
    remote_approvals: bool | None = None
    away_continuity: bool | None = None
    receipt_summary: bool | None = None


class FederationRevokeRequest(BaseModel):
    reason: str = ""


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
        app="federation",
        action=action,
        mutating=mutating,
    )
    if not allowed:
        raise HTTPException(status_code=403, detail=f"Control denied: {reason}")


def _build_state_payload() -> dict[str, Any]:
    topology = load_or_init_topology(_fs, repo_root=_repo_root, workspace_root=_workspace_root)
    local_node = topology["local_node"] if isinstance(topology.get("local_node"), dict) else {}
    local_scopes = local_node.get("scopes", {}) if isinstance(local_node.get("scopes"), dict) else {}
    local_node = {
        **local_node,
        "scope_counts": {
            "repos": len(local_scopes.get("repos", [])) if isinstance(local_scopes.get("repos"), list) else 0,
            "workspaces": (
                len(local_scopes.get("workspaces", [])) if isinstance(local_scopes.get("workspaces"), list) else 0
            ),
            "apps": len(local_scopes.get("apps", [])) if isinstance(local_scopes.get("apps"), list) else 0,
        },
    }
    paired_nodes = [row for row in topology.get("paired_nodes", []) if isinstance(row, dict)]
    active_count = sum(1 for row in paired_nodes if str(row.get("status", "")).strip().lower() == "active")
    stale_count = sum(1 for row in paired_nodes if str(row.get("status", "")).strip().lower() == "stale")
    revoked_count = sum(1 for row in paired_nodes if str(row.get("status", "")).strip().lower() == "revoked")
    summary = (
        f"Local node {str(local_node.get('label', 'Primary Node')).strip() or 'Primary Node'} "
        f"with {len(paired_nodes)} paired node(s), {stale_count} stale, {revoked_count} revoked."
    )
    return {
        "status": "ok",
        "summary": summary,
        "local_node": local_node,
        "paired_nodes": paired_nodes,
        "counts": {
            "paired": len(paired_nodes),
            "active": active_count,
            "stale": stale_count,
            "revoked": revoked_count,
        },
        "updated_at": topology.get("updated_at"),
    }


def _record_federation_receipt(
    *,
    run_id: str,
    trace_id: str,
    kind: str,
    actor: str,
    local_node_id: str,
    target_node_id: str,
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
        "local_node_id": local_node_id,
        "target_node_id": target_node_id or None,
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
            "local_node_id": local_node_id,
            "target_node_id": target_node_id or None,
            **summary,
        },
    )
    return receipt


@router.get("/federation/state")
def federation_state(request: Request) -> dict[str, Any]:
    _enforce_control("federation.read")
    _enforce_rbac(request, "federation.read")
    return _build_state_payload()


@router.post("/federation/pair")
def federation_pair(request: Request, payload: FederationPairRequest) -> dict[str, Any]:
    _enforce_control("federation.write")
    role = _enforce_rbac(request, "federation.write")
    run_id = str(getattr(request.state, "run_id", uuid4()))
    trace_id = str(getattr(request.state, "trace_id", None) or run_id)
    node = pair_node(
        _fs,
        repo_root=_repo_root,
        workspace_root=_workspace_root,
        label=payload.label.strip(),
        role=payload.role.strip().lower(),
        trust_level=payload.trust_level.strip().lower(),
        scopes={"apps": [str(item).strip().lower() for item in payload.apps if str(item).strip()]},
        capabilities={
            "remote_approvals": payload.remote_approvals,
            "away_continuity": payload.away_continuity,
            "receipt_summary": payload.receipt_summary,
        },
        notes=payload.notes.strip(),
        paired_by=role,
    )
    topology = _build_state_payload()
    _record_federation_receipt(
        run_id=run_id,
        trace_id=trace_id,
        kind="federation.node.paired",
        actor=role,
        local_node_id=str(topology.get("local_node", {}).get("node_id", "")).strip(),
        target_node_id=str(node.get("node_id", "")).strip(),
        reason=f"Pair node {str(node.get('label', '')).strip() or 'paired node'}",
        summary={
            "label": str(node.get("label", "")).strip(),
            "role": str(node.get("role", "")).strip(),
            "trust_level": str(node.get("trust_level", "")).strip(),
            "status": str(node.get("status", "")).strip(),
        },
    )
    return {"status": "ok", "run_id": run_id, "trace_id": trace_id, "node": node, "topology": topology}


@router.post("/federation/nodes/{node_id}/heartbeat")
def federation_heartbeat(node_id: str, request: Request, payload: FederationHeartbeatRequest) -> dict[str, Any]:
    _enforce_control("federation.write")
    role = _enforce_rbac(request, "federation.write")
    run_id = str(getattr(request.state, "run_id", uuid4()))
    trace_id = str(getattr(request.state, "trace_id", None) or run_id)
    capability_patch = {
        key: value
        for key, value in {
            "remote_approvals": payload.remote_approvals,
            "away_continuity": payload.away_continuity,
            "receipt_summary": payload.receipt_summary,
        }.items()
        if value is not None
    }
    try:
        node = heartbeat_node(
            _fs,
            repo_root=_repo_root,
            workspace_root=_workspace_root,
            node_id=str(node_id).strip(),
            status=payload.status.strip().lower(),
            sync_summary=payload.sync_summary.strip(),
            capabilities=capability_patch or None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if node is None:
        raise HTTPException(status_code=404, detail=f"Node not found: {node_id}")
    topology = _build_state_payload()
    _record_federation_receipt(
        run_id=run_id,
        trace_id=trace_id,
        kind="federation.node.heartbeat",
        actor=role,
        local_node_id=str(topology.get("local_node", {}).get("node_id", "")).strip(),
        target_node_id=str(node.get("node_id", "")).strip(),
        reason=payload.sync_summary.strip() or "federation heartbeat",
        summary={
            "label": str(node.get("label", "")).strip(),
            "status": str(node.get("status", "")).strip(),
            "last_sync_summary": str(node.get("last_sync_summary", "")).strip(),
        },
    )
    return {"status": "ok", "run_id": run_id, "trace_id": trace_id, "node": node, "topology": topology}


@router.post("/federation/nodes/{node_id}/revoke")
def federation_revoke(node_id: str, request: Request, payload: FederationRevokeRequest) -> dict[str, Any]:
    _enforce_control("federation.write")
    role = _enforce_rbac(request, "federation.write")
    run_id = str(getattr(request.state, "run_id", uuid4()))
    trace_id = str(getattr(request.state, "trace_id", None) or run_id)
    reason = payload.reason.strip() or "Node trust revoked."
    node = revoke_node(
        _fs,
        repo_root=_repo_root,
        workspace_root=_workspace_root,
        node_id=str(node_id).strip(),
        reason=reason,
    )
    if node is None:
        raise HTTPException(status_code=404, detail=f"Node not found: {node_id}")
    topology = _build_state_payload()
    _record_federation_receipt(
        run_id=run_id,
        trace_id=trace_id,
        kind="federation.node.revoked",
        actor=role,
        local_node_id=str(topology.get("local_node", {}).get("node_id", "")).strip(),
        target_node_id=str(node.get("node_id", "")).strip(),
        reason=reason,
        summary={
            "label": str(node.get("label", "")).strip(),
            "status": str(node.get("status", "")).strip(),
            "trust_level": str(node.get("trust_level", "")).strip(),
        },
    )
    return {"status": "ok", "run_id": run_id, "trace_id": trace_id, "node": node, "topology": topology}
