from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from francis_brain.apprenticeship import (
    add_session_step,
    build_replay,
    create_session,
    list_sessions,
    load_session_steps,
    summarize_apprenticeship,
)
from francis_brain.ledger import RunLedger
from francis_core.clock import utc_now_iso
from francis_core.workspace_fs import WorkspaceFS
from services.hud.app.state import build_lens_snapshot, get_workspace_root
from services.orchestrator.app.control_state import check_action_allowed

ACTIVE_SESSION_STATUSES = {"recording", "review"}


def _workspace_context(workspace_root: Path | None = None) -> tuple[Path, Path, WorkspaceFS, RunLedger]:
    root = (workspace_root or get_workspace_root()).resolve()
    repo_root = root.parent.resolve()
    fs = WorkspaceFS(
        roots=[root],
        journal_path=(root / "journals" / "fs.jsonl").resolve(),
    )
    ledger = RunLedger(fs, rel_path="runs/run_ledger.jsonl")
    return root, repo_root, fs, ledger


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _session_status(session: dict[str, Any]) -> str:
    return str(session.get("status", "")).strip().lower() or "recording"


def _session_tone(status: str) -> str:
    if status == "recording":
        return "high"
    if status == "review":
        return "medium"
    return "low"


def _focus_session(sessions: list[dict[str, Any]]) -> dict[str, Any] | None:
    for preferred in ("recording", "review", "skillized"):
        for session in sessions:
            if _session_status(session) == preferred:
                return session
    return sessions[0] if sessions else None


def _detail_state(session: dict[str, Any] | None) -> str:
    if not isinstance(session, dict):
        return "idle"
    return "current" if _session_status(session) in ACTIVE_SESSION_STATUSES else "historical"


def _action_allowed(
    *,
    fs: WorkspaceFS,
    repo_root: Path,
    workspace_root: Path,
    action: str,
) -> tuple[bool, str]:
    allowed, reason, _state = check_action_allowed(
        fs,
        repo_root=repo_root,
        workspace_root=workspace_root,
        app="apprenticeship",
        action=action,
        mutating=True,
    )
    return allowed, reason


def _skill_artifact(root: Path, session: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(session, dict):
        return {}
    rel_path = str(session.get("skill_artifact_path", "")).strip()
    if not rel_path:
        return {}
    return _read_json(root / rel_path)


def _base_control(
    *,
    kind: str,
    label: str,
    enabled: bool,
    summary: str,
    args: dict[str, object] | None = None,
) -> dict[str, Any]:
    return {
        "kind": kind,
        "label": label,
        "enabled": enabled,
        "summary": summary,
        "control_type": "execute",
        "execute_kind": kind,
        "args": args or {},
    }


def _session_controls(
    *,
    fs: WorkspaceFS,
    repo_root: Path,
    workspace_root: Path,
    session: dict[str, Any],
    steps: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    session_id = str(session.get("id", "")).strip()
    title = str(session.get("title", "Teaching session")).strip() or "Teaching session"
    generalization = session.get("generalization", {}) if isinstance(session.get("generalization"), dict) else {}
    can_write, write_reason = _action_allowed(
        fs=fs,
        repo_root=repo_root,
        workspace_root=workspace_root,
        action="apprenticeship.write",
    )
    can_generalize, generalize_reason = _action_allowed(
        fs=fs,
        repo_root=repo_root,
        workspace_root=workspace_root,
        action="apprenticeship.generalize",
    )
    can_skillize, skillize_reason = _action_allowed(
        fs=fs,
        repo_root=repo_root,
        workspace_root=workspace_root,
        action="apprenticeship.skillize",
    )

    return {
        "record_step": _base_control(
            kind="apprenticeship.step.record",
            label="Record Step",
            enabled=can_write and bool(session_id),
            summary=(
                f"Record another demonstrated step into {title}."
                if can_write and bool(session_id)
                else f"Step recording is blocked: {write_reason}."
            ),
            args={"session_id": session_id, "step_kind": "command"},
        ),
        "generalize": _base_control(
            kind="apprenticeship.generalize",
            label="Generalize",
            enabled=can_generalize and bool(session_id) and bool(steps),
            summary=(
                f"Generalize {title} into a reusable workflow."
                if can_generalize and bool(session_id) and bool(steps)
                else f"Generalization is blocked: {generalize_reason if not can_generalize else 'a session needs recorded steps'}."
            ),
            args={"session_id": session_id},
        ),
        "skillize": _base_control(
            kind="apprenticeship.skillize",
            label="Skillize",
            enabled=can_skillize and bool(session_id) and bool(generalization),
            summary=(
                f"Skillize {title} into a Forge-ready artifact."
                if can_skillize and bool(session_id) and bool(generalization)
                else f"Skillization is blocked: {skillize_reason if not can_skillize else 'generalization must exist first'}."
            ),
            args={"session_id": session_id},
        ),
    }


def _session_summary(session: dict[str, Any]) -> str:
    status = _session_status(session)
    step_count = int(session.get("step_count", 0) or 0)
    if status == "recording":
        return f"{step_count} step(s) captured. Still recording."
    if status == "review":
        return f"{step_count} step(s) captured. Ready for generalization review."
    if status == "skillized":
        return f"{step_count} step(s) captured. Already skillized."
    return f"{step_count} step(s) captured."


def _detail_cards(
    *,
    session: dict[str, Any] | None,
    skill_artifact: dict[str, Any],
) -> list[dict[str, str]]:
    if not isinstance(session, dict):
        return [{"label": "Session", "value": "no teaching session", "tone": "low"}]

    generalization = session.get("generalization", {}) if isinstance(session.get("generalization"), dict) else {}
    return [
        {
            "label": "Status",
            "value": _session_status(session),
            "tone": _session_tone(_session_status(session)),
        },
        {
            "label": "Steps",
            "value": str(int(session.get("step_count", 0) or 0)),
            "tone": "medium" if int(session.get("step_count", 0) or 0) > 0 else "low",
        },
        {
            "label": "Mission",
            "value": str(session.get("mission_id", "")).strip() or "unscoped",
            "tone": "low",
        },
        {
            "label": "Parameters",
            "value": str(len(generalization.get("parameter_candidates", [])))
            if isinstance(generalization.get("parameter_candidates"), list)
            else "0",
            "tone": "medium" if generalization else "low",
        },
        {
            "label": "Skill Artifact",
            "value": str(session.get("skill_artifact_path", "")).strip() or "not written",
            "tone": "low" if str(session.get("skill_artifact_path", "")).strip() else "medium",
        },
        {
            "label": "Forge Stage",
            "value": str(session.get("forge_stage_id", "")).strip() or "not staged",
            "tone": "low" if str(session.get("forge_stage_id", "")).strip() else "medium",
        },
        {
            "label": "Artifact Name",
            "value": str(skill_artifact.get("forge_payload", {}).get("name", "")).strip() or "pending",
            "tone": "low" if skill_artifact else "medium",
        },
    ]


def _session_detail(
    *,
    root: Path,
    fs: WorkspaceFS,
    repo_root: Path,
    workspace_root: Path,
    session: dict[str, Any],
) -> dict[str, Any]:
    steps = load_session_steps(fs, str(session.get("id", "")).strip())
    replay = build_replay(session, steps)
    skill_artifact = _skill_artifact(root, session)
    controls = _session_controls(
        fs=fs,
        repo_root=repo_root,
        workspace_root=workspace_root,
        session=session,
        steps=steps,
    )
    return {
        "session": session,
        "replay": replay,
        "generalization": session.get("generalization", {})
        if isinstance(session.get("generalization"), dict)
        else {},
        "skill_artifact": skill_artifact,
        "controls": controls,
        "audit": {
            "session_id": str(session.get("id", "")).strip(),
            "status": _session_status(session),
            "step_count": int(session.get("step_count", 0) or 0),
            "mission_id": str(session.get("mission_id", "")).strip(),
            "skill_artifact_path": str(session.get("skill_artifact_path", "")).strip(),
            "forge_stage_id": str(session.get("forge_stage_id", "")).strip(),
            "replay_step_count": len(replay.get("steps", [])),
            "parameter_count": len(
                session.get("generalization", {}).get("parameter_candidates", [])
                if isinstance(session.get("generalization"), dict)
                and isinstance(session.get("generalization", {}).get("parameter_candidates"), list)
                else []
            ),
        },
    }


def _session_row(
    *,
    root: Path,
    fs: WorkspaceFS,
    repo_root: Path,
    workspace_root: Path,
    session: dict[str, Any],
) -> dict[str, Any]:
    detail = _session_detail(
        root=root,
        fs=fs,
        repo_root=repo_root,
        workspace_root=workspace_root,
        session=session,
    )
    return {
        "id": str(session.get("id", "")).strip(),
        "title": str(session.get("title", "Teaching session")).strip() or "Teaching session",
        "objective": str(session.get("objective", "")).strip(),
        "mission_id": str(session.get("mission_id", "")).strip(),
        "status": _session_status(session),
        "step_count": int(session.get("step_count", 0) or 0),
        "created_at": str(session.get("created_at", "")).strip(),
        "updated_at": str(session.get("updated_at", "")).strip(),
        "last_event_at": str(session.get("last_event_at", "")).strip(),
        "summary": _session_summary(session),
        "detail_summary": (
            str(detail["generalization"].get("summary", "")).strip()
            if isinstance(detail.get("generalization"), dict)
            and str(detail["generalization"].get("summary", "")).strip()
            else _session_summary(session)
        ),
        "detail_state": _detail_state(session),
        "detail_cards": _detail_cards(session=session, skill_artifact=detail.get("skill_artifact", {})),
        "controls": detail.get("controls", {}),
        "detail": detail,
        "audit": detail.get("audit", {}),
    }


def _surface_summary(summary: dict[str, Any], focus_session: dict[str, Any] | None) -> str:
    if not focus_session:
        return "No teaching session is active. Start one to capture a reusable workflow from explicit demonstration."
    title = str(focus_session.get("title", "Teaching session")).strip() or "Teaching session"
    status = _session_status(focus_session)
    step_count = int(focus_session.get("step_count", 0) or 0)
    if status == "recording":
        return f"{title} is recording with {step_count} demonstrated step(s)."
    if status == "review":
        return f"{title} is ready for replay and generalization review with {step_count} demonstrated step(s)."
    if status == "skillized":
        return f"{title} has been skillized and staged into Forge."
    return f"{title} is available for apprenticeship review."


def create_apprenticeship_session_record(
    *,
    title: str,
    objective: str = "",
    mission_id: str | None = None,
    tags: list[str] | None = None,
    created_by: str = "hud.operator",
) -> dict[str, Any]:
    _root, _repo_root, fs, ledger = _workspace_context()
    session = create_session(
        fs,
        title=title,
        objective=objective,
        mission_id=mission_id,
        tags=tags or [],
        created_by=created_by,
    )
    run_id = f"hud-teach:{uuid4()}"
    ledger.append(
        run_id=run_id,
        kind="apprenticeship.session.created",
        summary={
            "session_id": session["id"],
            "title": session["title"],
            "objective": session.get("objective", ""),
            "tags": session.get("tags", []),
            "ts": utc_now_iso(),
        },
    )
    return {"status": "ok", "run_id": run_id, "session": session}


def record_apprenticeship_step(
    *,
    session_id: str,
    kind: str,
    action: str,
    intent: str,
    artifact_path: str = "",
    notes: str = "",
    inputs: dict[str, object] | None = None,
    outputs: dict[str, object] | None = None,
) -> dict[str, Any]:
    _root, _repo_root, fs, ledger = _workspace_context()
    session, step = add_session_step(
        fs,
        session_id=session_id,
        kind=kind,
        action=action,
        intent=intent,
        artifact_path=artifact_path,
        notes=notes,
        inputs=inputs if isinstance(inputs, dict) else {},
        outputs=outputs if isinstance(outputs, dict) else {},
    )
    run_id = f"hud-teach:{uuid4()}"
    ledger.append(
        run_id=run_id,
        kind="apprenticeship.step.recorded",
        summary={
            "session_id": session["id"],
            "step_id": step["id"],
            "intent": step["intent"],
            "action": step["action"],
            "ts": utc_now_iso(),
        },
    )
    return {"status": "ok", "run_id": run_id, "session": session, "step": step}


def get_apprenticeship_view(
    *,
    snapshot: dict[str, object] | None = None,
) -> dict[str, object]:
    if snapshot is None:
        snapshot = build_lens_snapshot()

    root, repo_root, fs, _ledger = _workspace_context()
    summary = summarize_apprenticeship(fs, limit=8)
    sessions = [row for row in list_sessions(fs, limit=12) if isinstance(row, dict)]
    focus_session = _focus_session(sessions)
    focus_session_id = str((focus_session or {}).get("id", "")).strip()
    rows = [
        _session_row(
            root=root,
            fs=fs,
            repo_root=repo_root,
            workspace_root=root,
            session=session,
        )
        for session in sessions
    ]
    focused_row = next((row for row in rows if str(row.get("id", "")).strip() == focus_session_id), None)

    create_allowed, create_reason = _action_allowed(
        fs=fs,
        repo_root=repo_root,
        workspace_root=root,
        action="apprenticeship.write",
    )
    objective = snapshot.get("objective", {}) if isinstance(snapshot.get("objective"), dict) else {}
    missions = snapshot.get("missions", {}) if isinstance(snapshot.get("missions"), dict) else {}
    active_missions = missions.get("active", []) if isinstance(missions.get("active"), list) else []
    default_mission_id = (
        str(active_missions[0].get("id", "")).strip()
        if active_missions and isinstance(active_missions[0], dict)
        else ""
    )
    focused_controls = focused_row.get("controls", {}) if isinstance(focused_row, dict) else {}

    return {
        "status": "ok",
        "surface": "apprenticeship_surface",
        "summary": _surface_summary(summary, focus_session),
        "severity": "medium"
        if int(summary.get("review_count", 0) or 0) > 0
        else "high"
        if int(summary.get("recording_count", 0) or 0) > 0
        else "low",
        "focus_session_id": focus_session_id,
        "cards": [
            {"label": "Sessions", "value": str(int(summary.get("session_count", 0) or 0)), "tone": "low"},
            {
                "label": "Recording",
                "value": str(int(summary.get("recording_count", 0) or 0)),
                "tone": "high" if int(summary.get("recording_count", 0) or 0) > 0 else "low",
            },
            {
                "label": "Review",
                "value": str(int(summary.get("review_count", 0) or 0)),
                "tone": "medium" if int(summary.get("review_count", 0) or 0) > 0 else "low",
            },
            {
                "label": "Skillized",
                "value": str(int(summary.get("skillized_count", 0) or 0)),
                "tone": "low",
            },
        ],
        "sessions": rows,
        "controls": {
            "create_session": {
                "kind": "apprenticeship.session.create",
                "label": "Start Teaching Session",
                "enabled": create_allowed,
                "summary": "Start a bounded teaching session for the current workflow."
                if create_allowed
                else f"Teaching sessions are blocked: {create_reason}.",
                "control_type": "create_session",
                "execute_kind": "apprenticeship.session.create",
                "defaults": {
                    "title": "",
                    "objective": str(objective.get("label", "")).strip(),
                    "mission_id": default_mission_id,
                    "tags": "",
                },
            },
            "record_step": focused_controls.get("record_step", _base_control(
                kind="apprenticeship.step.record",
                label="Record Step",
                enabled=False,
                summary="Select or start a teaching session before recording steps.",
            )),
            "generalize": focused_controls.get("generalize", _base_control(
                kind="apprenticeship.generalize",
                label="Generalize",
                enabled=False,
                summary="Select a teaching session before generalizing.",
            )),
            "skillize": focused_controls.get("skillize", _base_control(
                kind="apprenticeship.skillize",
                label="Skillize",
                enabled=False,
                summary="Select a teaching session before skillizing.",
            )),
        },
        "detail": focused_row.get("detail", {}) if isinstance(focused_row, dict) else {},
    }
