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
from francis_policy.tool_policy import approval_policy_for_tool
from francis_skills.contracts import SkillCall
from francis_skills.executor import SkillExecutor
from services.orchestrator.app.adversarial_guard import assess_untrusted_input, quarantine_untrusted_input
from services.orchestrator.app.approvals_store import ensure_action_approved
from services.orchestrator.app.control_state import check_action_allowed

router = APIRouter(tags=["tools"])

_workspace_root = Path(settings.workspace_root).resolve()
_repo_root = _workspace_root.parent
_fs = WorkspaceFS(
    roots=[_workspace_root],
    journal_path=(_workspace_root / "journals" / "fs.jsonl").resolve(),
)
_ledger = RunLedger(_fs, rel_path="runs/run_ledger.jsonl")
_executor = SkillExecutor.with_defaults(fs=_fs, repo_root=_repo_root)


class ToolRunRequest(BaseModel):
    skill: str
    args: dict[str, Any] = Field(default_factory=dict)


class ToolChainStep(BaseModel):
    skill: str
    args: dict[str, Any] = Field(default_factory=dict)
    label: str = ""
    approval_id: str | None = None


class ToolChainRequest(BaseModel):
    mission_id: str | None = None
    goal: str = ""
    steps: list[ToolChainStep] = Field(default_factory=list)
    rollback_on_failure: bool = True


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


def _read_json(rel_path: str, default: Any) -> Any:
    try:
        raw = _fs.read_text(rel_path)
    except Exception:
        return default
    try:
        parsed = json.loads(raw)
    except Exception:
        return default
    return parsed


def _role_from_request(request: Request) -> str:
    return request.headers.get("x-francis-role", "architect").strip().lower()


def _enforce_rbac(request: Request, action: str) -> None:
    role = _role_from_request(request)
    if not can(role, action):
        raise HTTPException(status_code=403, detail=f"RBAC denied: role={role}, action={action}")


def _load_mission(mission_id: str) -> dict[str, Any] | None:
    doc = _read_json("missions/missions.json", {"missions": []})
    if not isinstance(doc, dict):
        return None
    missions = doc.get("missions", [])
    if not isinstance(missions, list):
        return None
    for mission in missions:
        if isinstance(mission, dict) and str(mission.get("id", "")) == mission_id:
            return mission
    return None


def _load_dynamic_tool_specs() -> dict[str, dict[str, Any]]:
    specs: dict[str, dict[str, Any]] = {}
    for entry in list_entries(_fs):
        if str(entry.get("status", "")).lower() != "active":
            continue
        pack = entry.get("tool_pack")
        if not isinstance(pack, dict):
            continue
        skill_name = str(pack.get("skill_name", "")).strip()
        if not skill_name:
            continue

        description = str(pack.get("description", entry.get("description", ""))).strip()
        risk_tier = str(pack.get("risk_tier", entry.get("risk_tier", "medium"))).strip().lower() or "medium"
        mutating = bool(pack.get("mutating", False))
        requires_approval = bool(pack.get("requires_approval", True))
        args_schema = pack.get("args_schema", {"payload": "optional:dict"})
        if not isinstance(args_schema, dict):
            args_schema = {"payload": "optional:dict"}
        tags_raw = pack.get("tags", [])
        tags = [str(tag) for tag in tags_raw if isinstance(tag, str)]

        specs[skill_name] = {
            "name": skill_name,
            "description": description or f"Forge tool pack for {entry.get('name', skill_name)}",
            "risk_tier": risk_tier,
            "mutating": mutating,
            "requires_approval": requires_approval,
            "args_schema": args_schema,
            "tags": sorted(set(tags + ["forge", "tool-pack"])),
            "source": "forge",
            "stage_id": entry.get("id"),
            "behavior": pack.get("behavior", {"type": "echo"}),
        }
    return specs


def _all_tool_specs() -> dict[str, dict[str, Any]]:
    specs: dict[str, dict[str, Any]] = {}
    for spec in _executor.registry.list_specs():
        payload = spec.to_dict()
        payload["source"] = "builtin"
        payload["stage_id"] = None
        specs[spec.name] = payload
    specs.update(_load_dynamic_tool_specs())
    return specs


def _resolve_tool_spec(skill_name: str) -> dict[str, Any] | None:
    return _all_tool_specs().get(skill_name.strip())


def _enforce_control_for_tool(spec: dict[str, Any]) -> None:
    allowed, reason, _state = check_action_allowed(
        _fs,
        repo_root=_repo_root,
        workspace_root=_workspace_root,
        app="tools",
        action=f"tools.run.{spec.get('name')}",
        mutating=bool(spec.get("mutating", False)),
    )
    if not allowed:
        raise HTTPException(status_code=403, detail=f"Control denied: {reason}")


def _enforce_tool_approval(
    *,
    run_id: str,
    request: Request,
    spec: dict[str, Any],
    reason: str,
    approval_id: str | None = None,
) -> str | None:
    policy = approval_policy_for_tool(
        skill_name=str(spec.get("name", "")),
        risk_tier=str(spec.get("risk_tier", "low")),
        mutating=bool(spec.get("mutating", False)),
        source=str(spec.get("source", "builtin")),
        declared_requires_approval=bool(spec.get("requires_approval", False)),
    )
    approved, approval_detail = ensure_action_approved(
        _fs,
        run_id=run_id,
        action=f"tools.{spec.get('name')}",
        requested_by=_role_from_request(request),
        reason=reason,
        approval_required=policy.requires_approval,
        approval_id=approval_id,
        metadata={"path": "/tools/run"},
    )
    if approved:
        maybe_id = str(approval_detail.get("approval_request_id", "")).strip()
        return maybe_id or None

    raise HTTPException(
        status_code=403,
        detail={
            "message": f"Action requires approval: tools.{spec.get('name')}",
            "policy_reason": policy.reason,
            **approval_detail,
        },
    )


def _execute_forge_tool_pack(spec: dict[str, Any], args: dict[str, Any]) -> dict[str, Any]:
    behavior = spec.get("behavior", {})
    if not isinstance(behavior, dict):
        behavior = {"type": "echo"}
    behavior_type = str(behavior.get("type", "echo")).strip().lower()
    payload = args.get("payload") if isinstance(args, dict) and "payload" in args else args

    if behavior_type == "echo":
        output = {
            "status": "ok",
            "tool_pack": spec.get("name"),
            "stage_id": spec.get("stage_id"),
            "message": str(behavior.get("message", "Forge tool pack executed.")),
            "input": payload,
        }
        return {
            "ok": True,
            "output": output,
            "error": "",
            "receipts": {"source": "forge", "stage_id": spec.get("stage_id"), "behavior": "echo"},
        }

    return {
        "ok": False,
        "output": {},
        "error": f"unsupported forge tool pack behavior: {behavior_type}",
        "receipts": {"source": "forge", "stage_id": spec.get("stage_id")},
    }


def _execute_tool(spec: dict[str, Any], args: dict[str, Any]) -> dict[str, Any]:
    source = str(spec.get("source", "builtin")).strip().lower()
    if source == "forge":
        return _execute_forge_tool_pack(spec, args)

    result = _executor.execute(SkillCall(name=str(spec.get("name", "")), args=args))
    return result.to_dict()


def _capture_rollback_snapshot(spec: dict[str, Any], args: dict[str, Any]) -> dict[str, Any] | None:
    if not bool(spec.get("mutating", False)):
        return None
    path = args.get("path")
    if not isinstance(path, str) or not path.strip():
        return None
    rel_path = path.strip()
    try:
        before = _fs.read_text(rel_path)
        existed = True
    except Exception:
        before = ""
        existed = False
    return {"path": rel_path, "existed": existed, "content": before}


def _apply_rollback_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    path = str(snapshot.get("path", "")).strip()
    if not path:
        return {"ok": False, "reason": "missing path"}
    existed = bool(snapshot.get("existed", False))
    content = str(snapshot.get("content", ""))
    if existed:
        _fs.write_text(path, content)
        return {"ok": True, "path": path, "restored": "original_content"}
    _fs.write_text(path, "")
    return {"ok": True, "path": path, "restored": "empty_placeholder"}


def _log_tool_run(
    *,
    run_id: str,
    trace_id: str | None,
    spec: dict[str, Any],
    result: dict[str, Any],
    approval_id: str | None = None,
) -> None:
    normalized_trace_id = _normalize_trace_id(trace_id, fallback_run_id=run_id)
    _append_jsonl(
        "logs/francis.log.jsonl",
        {
            "id": str(uuid4()),
            "ts": utc_now_iso(),
            "run_id": run_id,
            "trace_id": normalized_trace_id,
            "kind": "tool.run",
            "skill": spec.get("name"),
            "source": spec.get("source", "builtin"),
            "risk_tier": spec.get("risk_tier"),
            "mutating": spec.get("mutating"),
            "approval_id": approval_id,
            "ok": result.get("ok"),
            "error": result.get("error", ""),
        },
    )
    _append_jsonl(
        "journals/decisions.jsonl",
        {
            "id": str(uuid4()),
            "ts": utc_now_iso(),
            "run_id": run_id,
            "trace_id": normalized_trace_id,
            "kind": "tool.decision",
            "skill": spec.get("name"),
            "source": spec.get("source", "builtin"),
            "ok": result.get("ok"),
            "risk_tier": spec.get("risk_tier", "low"),
            "approval_id": approval_id,
        },
    )
    _ledger.append(
        run_id=run_id,
        kind="tool.run",
        summary={
            "skill": spec.get("name"),
            "source": spec.get("source", "builtin"),
            "ok": bool(result.get("ok")),
            "risk_tier": spec.get("risk_tier", "low"),
            "mutating": bool(spec.get("mutating", False)),
            "approval_id": approval_id,
            "trace_id": normalized_trace_id,
        },
    )


@router.get("/tools")
def list_tools(request: Request) -> dict:
    _enforce_rbac(request, "tools.read")
    allowed, reason, _state = check_action_allowed(
        _fs,
        repo_root=_repo_root,
        workspace_root=_workspace_root,
        app="tools",
        action="tools.read",
        mutating=False,
    )
    if not allowed:
        raise HTTPException(status_code=403, detail=f"Control denied: {reason}")

    specs = list(_all_tool_specs().values())
    specs.sort(key=lambda item: str(item.get("name", "")))
    return {"status": "ok", "count": len(specs), "tools": specs}


@router.post("/tools/run")
def run_tool(request: Request, payload: ToolRunRequest) -> dict:
    run_id = str(getattr(request.state, "run_id", uuid4()))
    trace_id = _normalize_trace_id(getattr(request.state, "trace_id", None), fallback_run_id=run_id)
    _enforce_rbac(request, "tools.run")
    assessment = assess_untrusted_input(
        surface="tools",
        action="tools.run",
        payload={"skill": payload.skill, "args": payload.args},
        inspect_paths=True,
    )
    if assessment["quarantined"]:
        quarantine = quarantine_untrusted_input(
            _fs,
            run_id=run_id,
            trace_id=trace_id,
            surface="tools",
            action="tools.run",
            payload={"skill": payload.skill, "args": payload.args},
            assessment=assessment,
        )
        raise HTTPException(status_code=409, detail={"message": assessment["message"], "quarantine": quarantine})
    spec = _resolve_tool_spec(payload.skill.strip())
    if spec is None:
        raise HTTPException(status_code=404, detail=f"Unknown tool: {payload.skill}")

    _enforce_control_for_tool(spec)
    approval_id = _enforce_tool_approval(
        run_id=run_id,
        request=request,
        spec=spec,
        reason=f"Tool run requested: {spec.get('name')}",
        approval_id=request.headers.get("x-approval-id", "").strip() or None,
    )
    result = _execute_tool(spec, payload.args)
    _log_tool_run(run_id=run_id, trace_id=trace_id, spec=spec, result=result, approval_id=approval_id)
    return {"status": "ok", "run_id": run_id, "trace_id": trace_id, "skill": spec, "result": result}


@router.post("/tools/chain")
def run_tool_chain(request: Request, payload: ToolChainRequest) -> dict:
    run_id = str(getattr(request.state, "run_id", uuid4()))
    trace_id = _normalize_trace_id(getattr(request.state, "trace_id", None), fallback_run_id=run_id)
    _enforce_rbac(request, "tools.run")
    if not payload.steps:
        raise HTTPException(status_code=400, detail="steps cannot be empty")
    chain_payload = {
        "mission_id": payload.mission_id,
        "goal": payload.goal,
        "steps": [step.model_dump() for step in payload.steps],
    }
    assessment = assess_untrusted_input(
        surface="tools",
        action="tools.chain",
        payload=chain_payload,
        inspect_paths=True,
    )
    if assessment["quarantined"]:
        quarantine = quarantine_untrusted_input(
            _fs,
            run_id=run_id,
            trace_id=trace_id,
            surface="tools",
            action="tools.chain",
            payload=chain_payload,
            assessment=assessment,
        )
        raise HTTPException(status_code=409, detail={"message": assessment["message"], "quarantine": quarantine})

    mission: dict[str, Any] | None = None
    if payload.mission_id:
        mission = _load_mission(payload.mission_id)
        if mission is None:
            raise HTTPException(status_code=404, detail=f"Mission not found: {payload.mission_id}")

    chain_id = str(uuid4())
    executed: list[dict[str, Any]] = []
    rollback_snapshots: list[dict[str, Any]] = []
    rollback_actions: list[dict[str, Any]] = []
    blocked_or_failed: dict[str, Any] | None = None

    for index, step in enumerate(payload.steps):
        spec = _resolve_tool_spec(step.skill.strip())
        if spec is None:
            blocked_or_failed = {
                "index": index,
                "skill": step.skill,
                "error": "unknown skill",
                "kind": "resolve",
            }
            break

        try:
            _enforce_control_for_tool(spec)
            approval_id = _enforce_tool_approval(
                run_id=run_id,
                request=request,
                spec=spec,
                reason=f"Tool chain step {index}: {spec.get('name')}",
                approval_id=(step.approval_id or request.headers.get("x-approval-id", "")).strip() or None,
            )
        except HTTPException as exc:
            blocked_or_failed = {
                "index": index,
                "skill": spec.get("name"),
                "kind": "approval_or_control",
                "detail": exc.detail,
            }
            break

        snapshot = _capture_rollback_snapshot(spec, step.args)
        if snapshot is not None:
            snapshot["index"] = index
            snapshot["skill"] = spec.get("name")
            rollback_snapshots.append(snapshot)

        result = _execute_tool(spec, step.args)
        _log_tool_run(run_id=run_id, trace_id=trace_id, spec=spec, result=result, approval_id=approval_id)
        step_receipt = {
            "index": index,
            "label": step.label or f"step-{index + 1}",
            "skill": spec.get("name"),
            "source": spec.get("source", "builtin"),
            "approval_id": approval_id,
            "trace_id": trace_id,
            "ok": bool(result.get("ok")),
            "result": result,
        }
        executed.append(step_receipt)
        if not result.get("ok"):
            blocked_or_failed = {
                "index": index,
                "skill": spec.get("name"),
                "kind": "execution",
                "error": result.get("error", "tool execution failed"),
            }
            break

    if blocked_or_failed and payload.rollback_on_failure and rollback_snapshots:
        for snapshot in reversed(rollback_snapshots):
            action = _apply_rollback_snapshot(snapshot)
            action["index"] = snapshot.get("index")
            action["skill"] = snapshot.get("skill")
            rollback_actions.append(action)

    status = "ok" if blocked_or_failed is None else "failed"
    response = {
        "status": status,
        "run_id": run_id,
        "trace_id": trace_id,
        "chain_id": chain_id,
        "mission_id": payload.mission_id,
        "goal": payload.goal,
        "steps_total": len(payload.steps),
        "steps_executed": len(executed),
        "executed": executed,
        "failed": blocked_or_failed,
        "rollback": {
            "enabled": payload.rollback_on_failure,
            "actions": rollback_actions,
            "count": len(rollback_actions),
        },
    }
    if mission is not None:
        response["mission"] = {
            "id": mission.get("id"),
            "title": mission.get("title"),
            "status": mission.get("status"),
            "priority": mission.get("priority"),
        }
        _append_jsonl(
            "missions/history.jsonl",
            {
                "id": str(uuid4()),
                "ts": utc_now_iso(),
                "run_id": run_id,
                "trace_id": trace_id,
                "mission_id": mission.get("id"),
                "event": "mission.tool_chain",
                "status": status,
                "chain_id": chain_id,
                "goal": payload.goal,
                "steps_total": len(payload.steps),
                "steps_executed": len(executed),
            },
        )

    _append_jsonl(
        "journals/decisions.jsonl",
        {
            "id": str(uuid4()),
            "ts": utc_now_iso(),
            "run_id": run_id,
            "trace_id": trace_id,
            "kind": "tool.chain",
            "chain_id": chain_id,
            "mission_id": payload.mission_id,
            "status": status,
            "steps_total": len(payload.steps),
            "steps_executed": len(executed),
            "rollback_count": len(rollback_actions),
        },
    )
    _ledger.append(
        run_id=run_id,
        kind="tool.chain",
        summary={
            "chain_id": chain_id,
            "mission_id": payload.mission_id,
            "status": status,
            "steps_total": len(payload.steps),
            "steps_executed": len(executed),
            "rollback_count": len(rollback_actions),
            "trace_id": trace_id,
        },
    )
    return response
