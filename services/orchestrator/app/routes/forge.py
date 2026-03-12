from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from francis_brain.ledger import RunLedger
from francis_core.clock import utc_now_iso
from francis_core.config import settings
from francis_core.workspace_fs import WorkspaceFS
from francis_forge.catalog import add_entry, list_entries
from francis_forge.diff_analyzer import summarize_files
from francis_forge.library import build_capability_library, build_quality_standard, next_patch_version
from francis_forge.proposal_engine import propose
from francis_forge.promotion import promote_stage
from francis_forge.scaffold_generator import generate_stage_files
from francis_forge.spec import CapabilitySpec
from francis_forge.test_generator import generate_test_files
from francis_forge.validation import validate_stage
from francis_policy.approvals import requires_approval
from francis_policy.rbac import can
from services.orchestrator.app.approvals_store import ensure_action_approved
from services.orchestrator.app.control_state import check_action_allowed

router = APIRouter(tags=["forge"])

_workspace_root = Path(settings.workspace_root).resolve()
_repo_root = _workspace_root.parent
_fs = WorkspaceFS(
    roots=[_workspace_root],
    journal_path=(_workspace_root / "journals" / "fs.jsonl").resolve(),
)
_ledger = RunLedger(_fs, rel_path="runs/run_ledger.jsonl")


class ForgeStageRequest(BaseModel):
    name: str
    description: str
    rationale: str = ""
    tags: list[str] = Field(default_factory=list)
    risk_tier: str = "low"


def _role_from_request(request: Request) -> str:
    return request.headers.get("x-francis-role", "architect").strip().lower()


def _enforce_rbac(request: Request, action: str) -> None:
    role = _role_from_request(request)
    if not can(role, action):
        raise HTTPException(status_code=403, detail=f"RBAC denied: role={role}, action={action}")


def _enforce_policy(
    request: Request,
    *,
    run_id: str,
    action: str,
    reason: str,
    metadata: dict | None = None,
) -> str | None:
    if not requires_approval(action):
        return None

    role = _role_from_request(request)
    approval_id = request.headers.get("x-approval-id", "").strip() or None
    approved, detail = ensure_action_approved(
        _fs,
        run_id=run_id,
        action=action,
        requested_by=role,
        reason=reason,
        approval_id=approval_id,
        metadata=metadata,
    )
    if approved:
        approval = str(detail.get("approval_request_id", "")).strip()
        return approval or None

    raise HTTPException(
        status_code=403,
        detail={
            "message": f"Action requires approval: {action}",
            **detail,
        },
    )


def _enforce_control(action: str, *, mutating: bool) -> None:
    allowed, reason, _state = check_action_allowed(
        _fs,
        repo_root=_repo_root,
        workspace_root=_workspace_root,
        app="forge",
        action=action,
        mutating=mutating,
    )
    if not allowed:
        raise HTTPException(status_code=403, detail=f"Control denied: {reason}")


def _read_json(rel_path: str, default: object) -> object:
    try:
        raw = _fs.read_text(rel_path)
    except Exception:
        return default
    try:
        return json.loads(raw)
    except Exception:
        return default


def _read_jsonl(rel_path: str) -> list[dict]:
    try:
        raw = _fs.read_text(rel_path)
    except Exception:
        return []
    rows: list[dict] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows


def _build_context() -> dict:
    deadletter_count = len(_read_jsonl("queue/deadletter.jsonl"))
    incidents = _read_jsonl("incidents/incidents.jsonl")
    open_incidents = sum(1 for item in incidents if str(item.get("status", "")).lower() == "open")
    missions_doc = _read_json("missions/missions.json", {"missions": []})
    missions = missions_doc.get("missions", []) if isinstance(missions_doc, dict) else []
    inactive = {"completed", "failed", "cancelled", "canceled"}
    active_missions = sum(
        1
        for mission in missions
        if isinstance(mission, dict) and str(mission.get("status", "")).lower() not in inactive
    )
    return {
        "deadletter_count": deadletter_count,
        "open_incident_count": open_incidents,
        "active_mission_count": active_missions,
    }


@router.get("/forge")
def forge_summary(request: Request) -> dict:
    _enforce_control("forge.read", mutating=False)
    _enforce_rbac(request, "forge.read")
    context = _build_context()
    entries = list_entries(_fs)
    return {
        "status": "ok",
        "context": context,
        "catalog_size": len(entries),
        "staged_count": sum(1 for entry in entries if entry.get("status") == "staged"),
        "active_count": sum(1 for entry in entries if entry.get("status") == "active"),
    }


@router.get("/forge/proposals")
def forge_proposals(request: Request) -> dict:
    _enforce_control("forge.propose", mutating=False)
    _enforce_rbac(request, "forge.propose")
    run_id = str(getattr(request.state, "run_id", uuid4()))
    context = _build_context()
    proposals = propose(context)
    _ledger.append(
        run_id=run_id,
        kind="forge.proposals",
        summary={"count": len(proposals), **context},
    )
    return {"status": "ok", "run_id": run_id, "context": context, "proposals": proposals}


@router.get("/forge/catalog")
def forge_catalog(request: Request) -> dict:
    _enforce_control("forge.read", mutating=False)
    _enforce_rbac(request, "forge.read")
    return {"status": "ok", "entries": list_entries(_fs)}


@router.get("/forge/library")
def forge_library(request: Request) -> dict:
    _enforce_control("forge.read", mutating=False)
    _enforce_rbac(request, "forge.read")
    library = build_capability_library(list_entries(_fs))
    return {"status": "ok", **library}


@router.post("/forge/stage")
def forge_stage(request: Request, payload: ForgeStageRequest) -> dict:
    _enforce_control("forge.stage", mutating=True)
    _enforce_rbac(request, "forge.stage")
    run_id = str(getattr(request.state, "run_id", uuid4()))
    _enforce_policy(
        request,
        run_id=run_id,
        action="forge.stage",
        reason=f"Stage capability: {payload.name}",
        metadata={"path": "/forge/stage"},
    )

    spec = CapabilitySpec(
        name=payload.name,
        description=payload.description,
        rationale=payload.rationale,
        tags=payload.tags,
        risk_tier=payload.risk_tier,
    )
    stage_id = f"{spec.slug}-{str(uuid4())[:8]}"
    stage_rel_root = f"forge/staging/{stage_id}"
    tool_pack_skill = f"forge.pack.{spec.slug}"
    tool_pack_manifest = {
        "version": 1,
        "skill_name": tool_pack_skill,
        "description": spec.description,
        "risk_tier": spec.risk_tier,
        "mutating": False,
        "requires_approval": spec.risk_tier.strip().lower() in {"medium", "high", "critical"},
        "args_schema": {"payload": "optional:dict"},
        "tags": [spec.slug, "forge", "tool-pack"],
        "behavior": {
            "type": "echo",
            "message": f"{spec.name} capability pack executed.",
        },
    }

    source_files = generate_stage_files(spec)
    test_files = generate_test_files(spec)
    all_files = {
        **{f"{stage_rel_root}/{name}": content for name, content in source_files.items()},
        **{f"{stage_rel_root}/tests/{name}": content for name, content in test_files.items()},
        f"{stage_rel_root}/tool_pack.json": json.dumps(tool_pack_manifest, ensure_ascii=False, indent=2),
    }

    for rel_path, content in all_files.items():
        _fs.write_text(rel_path, content)

    validation = validate_stage(_fs, list(all_files.keys()))
    diff_summary = summarize_files(all_files)
    version = next_patch_version(list_entries(_fs), spec.slug)
    quality_standard = build_quality_standard(
        {
            "slug": spec.slug,
            "version": version,
            "validation": validation,
            "diff_summary": diff_summary,
            "tool_pack": tool_pack_manifest,
        }
    )
    entry = add_entry(
        _fs,
        {
            "id": stage_id,
            "name": spec.name,
            "slug": spec.slug,
            "pack_id": spec.slug,
            "description": spec.description,
            "rationale": spec.rationale,
            "tags": spec.tags,
            "risk_tier": spec.risk_tier,
            "status": "staged",
            "version": version,
            "path": stage_rel_root,
            "created_at": utc_now_iso(),
            "validation": validation,
            "diff_summary": diff_summary,
            "tool_pack": tool_pack_manifest,
            "quality_standard": quality_standard,
        },
    )

    _ledger.append(
        run_id=run_id,
        kind="forge.stage",
        summary={
            "stage_id": stage_id,
            "name": spec.name,
            "version": version,
            "validation_ok": validation.get("ok"),
            "file_count": diff_summary.get("file_count"),
            "tool_pack_skill": tool_pack_skill,
            "quality_ok": quality_standard.get("ok"),
        },
    )
    return {
        "status": "ok",
        "run_id": run_id,
        "stage_id": stage_id,
        "entry": entry,
        "quality_standard": quality_standard,
        "written_files": sorted(all_files.keys()),
    }


@router.post("/forge/promote/{stage_id}")
def forge_promote(stage_id: str, request: Request) -> dict:
    _enforce_control("forge.promote", mutating=True)
    _enforce_rbac(request, "forge.promote")
    run_id = str(getattr(request.state, "run_id", uuid4()))
    approval_id = _enforce_policy(
        request,
        run_id=run_id,
        action="forge.promote",
        reason=f"Promote staged capability: {stage_id}",
        metadata={"path": f"/forge/promote/{stage_id}", "stage_id": stage_id},
    )

    try:
        promoted = promote_stage(_fs, stage_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if promoted is None:
        raise HTTPException(status_code=404, detail=f"Stage not found: {stage_id}")

    _ledger.append(
        run_id=run_id,
        kind="forge.promote",
        summary={"stage_id": stage_id, "status": promoted.get("status"), "approval_id": approval_id},
    )
    tool_pack_registered = isinstance(promoted.get("tool_pack"), dict) and bool(promoted["tool_pack"].get("skill_name"))
    return {
        "status": "ok",
        "run_id": run_id,
        "entry": promoted,
        "tool_pack_registered": tool_pack_registered,
        "tool_pack_skill": promoted.get("tool_pack", {}).get("skill_name") if tool_pack_registered else None,
    }
