from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from francis_brain.apprenticeship import (
    add_session_step,
    build_replay,
    create_session,
    generalize_session,
    get_session,
    list_sessions,
    load_session_steps,
    mark_session_skillized,
    summarize_apprenticeship,
    write_skill_artifact,
)
from francis_brain.ledger import RunLedger
from francis_core.config import settings
from francis_core.workspace_fs import WorkspaceFS
from francis_policy.rbac import can
from services.orchestrator.app.adversarial_guard import assess_untrusted_input, quarantine_untrusted_input
from services.orchestrator.app.control_state import check_action_allowed
from services.orchestrator.app.routes.forge import ForgeStageRequest, forge_stage

router = APIRouter(tags=["apprenticeship"])

_workspace_root = Path(settings.workspace_root).resolve()
_repo_root = _workspace_root.parent
_fs = WorkspaceFS(
    roots=[_workspace_root],
    journal_path=(_workspace_root / "journals" / "fs.jsonl").resolve(),
)
_ledger = RunLedger(_fs, rel_path="runs/run_ledger.jsonl")


class ApprenticeshipSessionCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    objective: str = ""
    mission_id: str | None = None
    tags: list[str] = Field(default_factory=list)


class ApprenticeshipStepRequest(BaseModel):
    kind: str = Field(default="command", min_length=1, max_length=40)
    action: str = Field(min_length=1, max_length=400)
    intent: str = Field(min_length=1, max_length=200)
    artifact_path: str = ""
    notes: str = ""
    inputs: dict[str, object] = Field(default_factory=dict)
    outputs: dict[str, object] = Field(default_factory=dict)


class ApprenticeshipSkillizeRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    rationale: str | None = None
    tags: list[str] = Field(default_factory=list)
    risk_tier: str = "low"


def _role_from_request(request: Request) -> str:
    return request.headers.get("x-francis-role", "architect").strip().lower()


def _enforce_rbac(request: Request, action: str) -> None:
    role = _role_from_request(request)
    if not can(role, action):
        raise HTTPException(status_code=403, detail=f"RBAC denied: role={role}, action={action}")


def _enforce_control(action: str, *, mutating: bool) -> None:
    allowed, reason, _state = check_action_allowed(
        _fs,
        repo_root=_repo_root,
        workspace_root=_workspace_root,
        app="apprenticeship",
        action=action,
        mutating=mutating,
    )
    if not allowed:
        raise HTTPException(status_code=403, detail=f"Control denied: {reason}")


def _session_detail(session_id: str) -> dict[str, object]:
    session = get_session(_fs, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Teaching session not found: {session_id}")
    steps = load_session_steps(_fs, session_id)
    return {"session": session, "steps": steps, "replay": build_replay(session, steps)}


@router.get("/apprenticeship")
def apprenticeship_summary(request: Request, limit: int = 5) -> dict[str, object]:
    _enforce_control("apprenticeship.read", mutating=False)
    _enforce_rbac(request, "apprenticeship.read")
    return {"status": "ok", **summarize_apprenticeship(_fs, limit=limit)}


@router.get("/apprenticeship/sessions")
def apprenticeship_sessions(request: Request, limit: int = 20) -> dict[str, object]:
    _enforce_control("apprenticeship.read", mutating=False)
    _enforce_rbac(request, "apprenticeship.read")
    return {
        "status": "ok",
        "sessions": list_sessions(_fs, limit=limit),
        "summary": summarize_apprenticeship(_fs, limit=limit),
    }


@router.get("/apprenticeship/sessions/{session_id}")
def apprenticeship_session_detail(request: Request, session_id: str) -> dict[str, object]:
    _enforce_control("apprenticeship.read", mutating=False)
    _enforce_rbac(request, "apprenticeship.read")
    detail = _session_detail(session_id)
    return {"status": "ok", **detail}


@router.post("/apprenticeship/sessions")
def apprenticeship_create_session(request: Request, payload: ApprenticeshipSessionCreateRequest) -> dict[str, object]:
    _enforce_control("apprenticeship.write", mutating=True)
    _enforce_rbac(request, "apprenticeship.write")
    run_id = str(getattr(request.state, "run_id", uuid4()))
    trace_id = str(getattr(request.state, "trace_id", None) or run_id)
    normalized_payload = payload.model_dump()
    assessment = assess_untrusted_input(
        surface="apprenticeship",
        action="apprenticeship.session.create",
        payload=normalized_payload,
    )
    if assessment.get("quarantined", False):
        quarantine = quarantine_untrusted_input(
            _fs,
            run_id=run_id,
            trace_id=trace_id,
            surface="apprenticeship",
            action="apprenticeship.session.create",
            payload=normalized_payload,
            assessment=assessment,
        )
        raise HTTPException(
            status_code=409,
            detail={"message": assessment["message"], "quarantine": quarantine},
        )
    session = create_session(
        _fs,
        title=payload.title,
        objective=payload.objective,
        mission_id=payload.mission_id,
        tags=payload.tags,
        created_by=_role_from_request(request),
    )
    _ledger.append(
        run_id=run_id,
        kind="apprenticeship.session.created",
        summary={"session_id": session["id"], "title": session["title"], "tags": session.get("tags", [])},
    )
    return {"status": "ok", "run_id": run_id, "session": session}


@router.post("/apprenticeship/sessions/{session_id}/steps")
def apprenticeship_add_step(
    request: Request,
    session_id: str,
    payload: ApprenticeshipStepRequest,
) -> dict[str, object]:
    _enforce_control("apprenticeship.write", mutating=True)
    _enforce_rbac(request, "apprenticeship.write")
    run_id = str(getattr(request.state, "run_id", uuid4()))
    trace_id = str(getattr(request.state, "trace_id", None) or run_id)
    normalized_payload = {
        "session_id": str(session_id).strip(),
        **payload.model_dump(),
    }
    assessment = assess_untrusted_input(
        surface="apprenticeship",
        action="apprenticeship.step.record",
        payload=normalized_payload,
    )
    if assessment.get("quarantined", False):
        quarantine = quarantine_untrusted_input(
            _fs,
            run_id=run_id,
            trace_id=trace_id,
            surface="apprenticeship",
            action="apprenticeship.step.record",
            payload=normalized_payload,
            assessment=assessment,
        )
        raise HTTPException(
            status_code=409,
            detail={"message": assessment["message"], "quarantine": quarantine},
        )
    try:
        session, step = add_session_step(
            _fs,
            session_id=session_id,
            kind=payload.kind,
            action=payload.action,
            intent=payload.intent,
            artifact_path=payload.artifact_path,
            notes=payload.notes,
            inputs=payload.inputs,
            outputs=payload.outputs,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    _ledger.append(
        run_id=run_id,
        kind="apprenticeship.step.recorded",
        summary={
            "session_id": session["id"],
            "step_id": step["id"],
            "intent": step["intent"],
            "kind": step["kind"],
        },
    )
    return {"status": "ok", "run_id": run_id, "session": session, "step": step}


@router.get("/apprenticeship/sessions/{session_id}/replay")
def apprenticeship_replay(request: Request, session_id: str) -> dict[str, object]:
    _enforce_control("apprenticeship.read", mutating=False)
    _enforce_rbac(request, "apprenticeship.read")
    detail = _session_detail(session_id)
    return {"status": "ok", "session": detail["session"], "replay": detail["replay"]}


@router.post("/apprenticeship/sessions/{session_id}/generalize")
def apprenticeship_generalize(request: Request, session_id: str) -> dict[str, object]:
    _enforce_control("apprenticeship.generalize", mutating=True)
    _enforce_rbac(request, "apprenticeship.generalize")
    run_id = str(getattr(request.state, "run_id", uuid4()))
    try:
        session, generalization = generalize_session(_fs, session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _ledger.append(
        run_id=run_id,
        kind="apprenticeship.generalized",
        summary={
            "session_id": session["id"],
            "parameter_count": len(generalization.get("parameter_candidates", [])),
            "workflow_steps": len(generalization.get("workflow", [])),
        },
    )
    return {"status": "ok", "run_id": run_id, "session": session, "generalization": generalization}


@router.post("/apprenticeship/sessions/{session_id}/skillize")
def apprenticeship_skillize(
    request: Request,
    session_id: str,
    payload: ApprenticeshipSkillizeRequest | None = None,
) -> dict[str, object]:
    _enforce_control("apprenticeship.skillize", mutating=True)
    _enforce_rbac(request, "apprenticeship.skillize")
    run_id = str(getattr(request.state, "run_id", uuid4()))
    trace_id = str(getattr(request.state, "trace_id", None) or run_id)
    normalized_payload = payload or ApprenticeshipSkillizeRequest()
    normalized_input = {
        "session_id": str(session_id).strip(),
        **normalized_payload.model_dump(),
    }
    assessment = assess_untrusted_input(
        surface="apprenticeship",
        action="apprenticeship.skillize",
        payload=normalized_input,
    )
    if assessment.get("quarantined", False):
        quarantine = quarantine_untrusted_input(
            _fs,
            run_id=run_id,
            trace_id=trace_id,
            surface="apprenticeship",
            action="apprenticeship.skillize",
            payload=normalized_input,
            assessment=assessment,
        )
        raise HTTPException(
            status_code=409,
            detail={"message": assessment["message"], "quarantine": quarantine},
        )

    session = get_session(_fs, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Teaching session not found: {session_id}")
    if not isinstance(session.get("generalization"), dict):
        session, _generalization = generalize_session(_fs, session_id)

    skill_session, skill_artifact = write_skill_artifact(
        _fs,
        session_id,
        name=normalized_payload.name,
        description=normalized_payload.description,
        rationale=normalized_payload.rationale,
        tags=normalized_payload.tags,
        risk_tier=normalized_payload.risk_tier,
    )
    forge_payload = skill_artifact.get("forge_payload", {})
    stage = forge_stage(
        request,
        ForgeStageRequest(
            name=str(forge_payload.get("name", skill_session.get("title", "Apprenticeship skill"))),
            description=str(
                forge_payload.get(
                    "description",
                    skill_artifact.get("generalization", {}).get("summary", ""),
                )
            ),
            rationale=str(forge_payload.get("rationale", "")),
            tags=[str(tag) for tag in forge_payload.get("tags", []) if isinstance(tag, str)],
            risk_tier=str(forge_payload.get("risk_tier", "low")),
        ),
    )
    finalized = mark_session_skillized(
        _fs,
        session_id,
        forge_stage_id=stage["stage_id"],
        skill_artifact_path=str(skill_artifact.get("path", "")),
    )
    _ledger.append(
        run_id=run_id,
        kind="apprenticeship.skillized",
        summary={
            "session_id": finalized["id"],
            "forge_stage_id": stage["stage_id"],
            "skill_artifact_path": skill_artifact.get("path"),
        },
    )
    return {
        "status": "ok",
        "run_id": run_id,
        "session": finalized,
        "skill_artifact": skill_artifact,
        "stage": stage,
    }
