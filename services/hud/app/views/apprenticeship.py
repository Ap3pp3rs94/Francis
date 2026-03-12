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
from francis_brain.calibration import summarize_fabric_posture
from francis_brain.ledger import RunLedger
from francis_brain.memory_store import load_snapshot
from francis_brain.recall import query_fabric
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


def _clip(value: object, *, limit: int = 96) -> str:
    text = " ".join(str(value or "").strip().split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def _slug_tag(value: object) -> str:
    token = "".join(
        ch.lower()
        if ch.isalnum()
        else "-"
        for ch in str(value or "").strip()
    )
    token = "-".join(part for part in token.split("-") if part)
    return token[:32]


def _mission_from_snapshot(snapshot: dict[str, object]) -> dict[str, Any]:
    current_work = snapshot.get("current_work", {}) if isinstance(snapshot.get("current_work"), dict) else {}
    mission = current_work.get("mission")
    if isinstance(mission, dict):
        return mission
    missions = snapshot.get("missions", {}) if isinstance(snapshot.get("missions"), dict) else {}
    active = missions.get("active", []) if isinstance(missions.get("active"), list) else []
    if active and isinstance(active[0], dict):
        return active[0]
    return {}


def _teaching_context(snapshot: dict[str, object]) -> dict[str, Any]:
    current_work = snapshot.get("current_work", {}) if isinstance(snapshot.get("current_work"), dict) else {}
    repo = current_work.get("repo", {}) if isinstance(current_work.get("repo"), dict) else {}
    telemetry = current_work.get("telemetry", {}) if isinstance(current_work.get("telemetry"), dict) else {}
    terminal = telemetry.get("last_terminal", {}) if isinstance(telemetry.get("last_terminal"), dict) else {}
    attention = current_work.get("attention", {}) if isinstance(current_work.get("attention"), dict) else {}
    next_action = (
        snapshot.get("next_best_action", {}) if isinstance(snapshot.get("next_best_action"), dict) else {}
    )
    objective = snapshot.get("objective", {}) if isinstance(snapshot.get("objective"), dict) else {}
    mission = _mission_from_snapshot(snapshot)
    mission_title = str(mission.get("title", "")).strip()
    mission_objective = str(mission.get("objective", "")).strip()
    next_label = str(next_action.get("label", "")).strip()
    next_reason = str(next_action.get("reason", "")).strip()
    next_kind = str(next_action.get("kind", "")).strip().lower()
    branch = str(repo.get("branch", "unknown")).strip() or "unknown"
    changed_count = int(repo.get("changed_count", 0) or 0)
    top_paths = [str(item).strip() for item in repo.get("top_paths", []) if str(item).strip()]
    top_path = top_paths[0] if top_paths else ""
    command = str(terminal.get("command", "")).strip()
    attention_label = str(attention.get("label", "Stable")).strip() or "Stable"
    attention_reason = str(attention.get("reason", "")).strip()

    if mission_title:
        title = f"Teach {mission_title}"
    elif next_label:
        title = f"Teach {next_label}"
    elif top_path:
        title = f"Teach {Path(top_path).stem.replace('_', ' ').replace('-', ' ').strip() or 'Current'} workflow"
    else:
        title = f"Teach {branch} workflow"

    if mission_objective:
        session_objective = mission_objective
    elif str(objective.get("label", "")).strip():
        session_objective = str(objective.get("label", "")).strip()
    elif next_reason:
        session_objective = next_reason
    elif command:
        session_objective = f"Capture the workflow around `{_clip(command, limit=72)}`."
    elif attention_reason:
        session_objective = attention_reason
    else:
        session_objective = "Capture the current workflow as a reusable bounded teaching session."

    tags: list[str] = []
    for candidate in (
        "teaching",
        mission_title,
        next_kind.split(".", 1)[0] if next_kind else "",
        attention.get("kind", ""),
        branch if branch != "unknown" else "",
    ):
        slug = _slug_tag(candidate)
        if slug and slug not in tags:
            tags.append(slug)

    if command:
        record_action = command
    elif next_label:
        record_action = next_label
    elif top_path:
        record_action = f"Inspect {top_path}"
    else:
        record_action = "Describe the demonstrated step"

    if next_reason:
        record_intent = next_reason
    elif mission_objective:
        record_intent = mission_objective
    elif mission_title:
        record_intent = f"Advance {mission_title}."
    elif attention_reason:
        record_intent = attention_reason
    else:
        record_intent = "Capture the demonstrated operator step as reusable workflow knowledge."

    summary_parts = []
    if mission_title:
        summary_parts.append(f"Mission {mission_title} is the current teaching anchor.")
    if command:
        summary_parts.append(f"Latest terminal command: {_clip(command, limit=84)}.")
    elif next_label:
        summary_parts.append(f"Next move: {next_label}.")
    if top_path:
        summary_parts.append(f"Primary repo path: {top_path}.")
    if not summary_parts:
        summary_parts.append("Teaching defaults are grounded in the current repo and operator context.")

    cards = [
        {
            "label": "Mission",
            "value": mission_title or "no active mission",
            "tone": "medium" if mission_title else "low",
        },
        {
            "label": "Repo",
            "value": f"{branch} | {changed_count} change(s)" if repo else "status unavailable",
            "tone": "medium" if changed_count > 0 else "low",
        },
        {
            "label": "Terminal",
            "value": _clip(command or "no recent terminal command", limit=44),
            "tone": "high" if command else "low",
        },
        {
            "label": "Next Move",
            "value": _clip(next_label or attention_label or "no current move", limit=44),
            "tone": "medium" if next_label else "low",
        },
        {
            "label": "Path",
            "value": top_path or "not anchored",
            "tone": "medium" if top_path else "low",
        },
    ]

    return {
        "summary": " ".join(summary_parts),
        "cards": cards,
        "create_defaults": {
            "title": _clip(title, limit=96) or "Teach Current Workflow",
            "objective": _clip(session_objective, limit=180),
            "mission_id": str(mission.get("id", "")).strip() or None,
            "tags": tags,
        },
        "record_defaults": {
            "kind": "command",
            "action": _clip(record_action, limit=240),
            "intent": _clip(record_intent, limit=180),
            "artifact_path": top_path,
            "notes": "",
        },
    }


def _citation_label(citation: dict[str, Any]) -> str:
    rel_path = str(citation.get("rel_path", "")).strip()
    if not rel_path:
        return "uncited"
    line = citation.get("line")
    if isinstance(line, int) and line > 0:
        return f"{rel_path}:{line}"
    record_index = citation.get("record_index")
    if isinstance(record_index, int) and record_index >= 0:
        return f"{rel_path}#record-{record_index}"
    return rel_path


def _session_query_text(
    *,
    session: dict[str, Any],
    steps: list[dict[str, Any]],
    skill_artifact: dict[str, Any],
) -> str:
    tokens: list[str] = []
    seen: set[str] = set()

    def _push(value: object) -> None:
        text = " ".join(str(value or "").strip().split())
        if not text:
            return
        lowered = text.lower()
        if lowered in seen:
            return
        seen.add(lowered)
        tokens.append(text)

    _push(session.get("title"))
    _push(session.get("objective"))
    _push(session.get("mission_id"))
    generalization = session.get("generalization", {}) if isinstance(session.get("generalization"), dict) else {}
    _push(generalization.get("summary"))
    for step in steps[:2]:
        if not isinstance(step, dict):
            continue
        _push(step.get("intent"))
        _push(step.get("action"))
        _push(step.get("artifact_path"))
    forge_payload = skill_artifact.get("forge_payload", {}) if isinstance(skill_artifact.get("forge_payload"), dict) else {}
    _push(forge_payload.get("name"))
    _push(forge_payload.get("description"))
    return " ".join(tokens[:8])


def _fabric_evidence(
    *,
    fs: WorkspaceFS,
    session: dict[str, Any],
    steps: list[dict[str, Any]],
    skill_artifact: dict[str, Any],
) -> list[dict[str, Any]]:
    if load_snapshot(fs) is None:
        return []

    query = _session_query_text(session=session, steps=steps, skill_artifact=skill_artifact)
    if not query:
        return []

    try:
        payload = query_fabric(
            fs,
            query=query,
            limit=3,
            mission_id=str(session.get("mission_id", "")).strip() or None,
            include_related=True,
            refresh=False,
        )
    except Exception:
        return []

    rows: list[dict[str, Any]] = []
    for row in payload.get("results", []):
        if not isinstance(row, dict):
            continue
        citation = row.get("citation", {}) if isinstance(row.get("citation"), dict) else {}
        title = str(row.get("title", "")).strip() or str(row.get("artifact_id", "Artifact")).strip() or "Artifact"
        summary = str(row.get("summary", "")).strip() or "No summary available."
        rows.append(
            {
                "title": title,
                "summary": summary,
                "artifact_id": str(row.get("artifact_id", "")).strip(),
                "source": str(row.get("source", "")).strip(),
                "trust_badge": str(row.get("trust_badge", row.get("confidence", "Uncertain"))).strip() or "Uncertain",
                "citation": citation,
                "detail": f"{title} | {_citation_label(citation)} | {summary}",
            }
        )
    return rows


def _trust_posture(rows: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {"confirmed": 0, "likely": 0, "uncertain": 0}
    citation_ready_count = 0
    for row in rows:
        trust = str(row.get("trust_badge", "")).strip().lower()
        if trust == "confirmed":
            counts["confirmed"] += 1
        elif trust == "likely":
            counts["likely"] += 1
        else:
            counts["uncertain"] += 1
        citation = row.get("citation", {}) if isinstance(row.get("citation"), dict) else {}
        if str(citation.get("rel_path", "")).strip():
            citation_ready_count += 1

    return summarize_fabric_posture(
        {
            "citation_ready_count": citation_ready_count,
            "calibration": {
                "confidence_counts": counts,
                "stale_current_state_count": 0,
                "done_claim_ready_count": counts["confirmed"],
            },
        }
    )


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
    defaults: dict[str, object] | None = None,
) -> dict[str, Any]:
    return {
        "kind": kind,
        "label": label,
        "enabled": enabled,
        "summary": summary,
        "control_type": "execute",
        "execute_kind": kind,
        "args": args or {},
        "defaults": defaults or {},
    }


def _session_controls(
    *,
    fs: WorkspaceFS,
    repo_root: Path,
    workspace_root: Path,
    session: dict[str, Any],
    steps: list[dict[str, Any]],
    teaching_context: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    session_id = str(session.get("id", "")).strip()
    title = str(session.get("title", "Teaching session")).strip() or "Teaching session"
    generalization = session.get("generalization", {}) if isinstance(session.get("generalization"), dict) else {}
    record_defaults = (
        teaching_context.get("record_defaults", {}) if isinstance(teaching_context.get("record_defaults"), dict) else {}
    )
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
                f"Record another demonstrated step into {title} using the live repo and terminal context."
                if can_write and bool(session_id)
                else f"Step recording is blocked: {write_reason}."
            ),
            args={"session_id": session_id, "step_kind": "command"},
            defaults=record_defaults,
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
    trust_posture: dict[str, Any],
    fabric_evidence: list[dict[str, Any]],
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
            "label": "Trust",
            "value": str(trust_posture.get("trust", "Uncertain")).strip() or "Uncertain",
            "tone": "low"
            if str(trust_posture.get("trust", "Uncertain")).strip() == "Confirmed"
            else "medium"
            if str(trust_posture.get("trust", "Uncertain")).strip() == "Likely"
            else "high",
        },
        {
            "label": "Citations",
            "value": str(len(fabric_evidence)),
            "tone": "low" if fabric_evidence else "medium",
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
    teaching_context: dict[str, Any],
) -> dict[str, Any]:
    steps = load_session_steps(fs, str(session.get("id", "")).strip())
    replay = build_replay(session, steps)
    skill_artifact = _skill_artifact(root, session)
    fabric_evidence = _fabric_evidence(fs=fs, session=session, steps=steps, skill_artifact=skill_artifact)
    trust_posture = _trust_posture(fabric_evidence)
    controls = _session_controls(
        fs=fs,
        repo_root=repo_root,
        workspace_root=workspace_root,
        session=session,
        steps=steps,
        teaching_context=teaching_context,
    )
    return {
        "session": session,
        "replay": replay,
        "generalization": session.get("generalization", {})
        if isinstance(session.get("generalization"), dict)
        else {},
        "skill_artifact": skill_artifact,
        "fabric_evidence": fabric_evidence,
        "trust_posture": trust_posture,
        "controls": controls,
        "audit": {
            "session_id": str(session.get("id", "")).strip(),
            "status": _session_status(session),
            "step_count": int(session.get("step_count", 0) or 0),
            "mission_id": str(session.get("mission_id", "")).strip(),
            "skill_artifact_path": str(session.get("skill_artifact_path", "")).strip(),
            "forge_stage_id": str(session.get("forge_stage_id", "")).strip(),
            "replay_step_count": len(replay.get("steps", [])),
            "fabric_trust": str(trust_posture.get("trust", "Uncertain")).strip() or "Uncertain",
            "fabric_evidence_count": len(fabric_evidence),
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
    teaching_context: dict[str, Any],
) -> dict[str, Any]:
    detail = _session_detail(
        root=root,
        fs=fs,
        repo_root=repo_root,
        workspace_root=workspace_root,
        session=session,
        teaching_context=teaching_context,
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
        )
        + (
            f" Grounded by {len(detail.get('fabric_evidence', []))} cited artifact(s)."
            if isinstance(detail.get("fabric_evidence"), list) and detail.get("fabric_evidence")
            else ""
        ),
        "detail_state": _detail_state(session),
        "detail_cards": _detail_cards(
            session=session,
            skill_artifact=detail.get("skill_artifact", {}),
            trust_posture=detail.get("trust_posture", {}) if isinstance(detail.get("trust_posture"), dict) else {},
            fabric_evidence=detail.get("fabric_evidence", []) if isinstance(detail.get("fabric_evidence"), list) else [],
        ),
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
    teaching_context = _teaching_context(snapshot)
    rows = [
        _session_row(
            root=root,
            fs=fs,
            repo_root=repo_root,
            workspace_root=root,
            session=session,
            teaching_context=teaching_context,
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
    focused_controls = focused_row.get("controls", {}) if isinstance(focused_row, dict) else {}
    create_defaults = (
        teaching_context.get("create_defaults", {})
        if isinstance(teaching_context.get("create_defaults"), dict)
        else {}
    )
    record_defaults = (
        teaching_context.get("record_defaults", {})
        if isinstance(teaching_context.get("record_defaults"), dict)
        else {}
    )
    record_control = focused_controls.get(
        "record_step",
        _base_control(
            kind="apprenticeship.step.record",
            label="Record Step",
            enabled=False,
            summary="Select or start a teaching session before recording steps.",
            defaults=record_defaults,
        ),
    )
    if isinstance(record_control, dict):
        record_control = {
            **record_control,
            "defaults": record_defaults,
        }

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
        "context": teaching_context,
        "sessions": rows,
        "controls": {
            "create_session": {
                "kind": "apprenticeship.session.create",
                "label": "Start Teaching Session",
                "enabled": create_allowed,
                "summary": teaching_context.get("summary", "Start a bounded teaching session for the current workflow.")
                if create_allowed
                else f"Teaching sessions are blocked: {create_reason}.",
                "control_type": "create_session",
                "execute_kind": "apprenticeship.session.create",
                "defaults": create_defaults,
            },
            "record_step": record_control,
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
