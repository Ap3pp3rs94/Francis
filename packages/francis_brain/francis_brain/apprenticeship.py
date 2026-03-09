from __future__ import annotations

import json
import re
from typing import Any
from uuid import uuid4

from francis_core.clock import utc_now_iso
from francis_core.workspace_fs import WorkspaceFS

SESSIONS_INDEX_PATH = "apprenticeship/sessions.json"
SESSIONS_DIR = "apprenticeship/sessions"
SKILLS_DIR = "apprenticeship/skills"
REVIEW_READY_STATUSES = {"review"}


def _read_json(fs: WorkspaceFS, rel_path: str, default: Any) -> Any:
    try:
        raw = fs.read_text(rel_path)
    except Exception:
        return default
    try:
        return json.loads(raw)
    except Exception:
        return default


def _write_json(fs: WorkspaceFS, rel_path: str, value: Any) -> None:
    fs.write_text(rel_path, json.dumps(value, ensure_ascii=False, indent=2))


def _read_jsonl(fs: WorkspaceFS, rel_path: str) -> list[dict[str, Any]]:
    try:
        raw = fs.read_text(rel_path)
    except Exception:
        return []
    rows: list[dict[str, Any]] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
        except Exception:
            continue
        if isinstance(parsed, dict):
            rows.append(parsed)
    return rows


def _append_jsonl(fs: WorkspaceFS, rel_path: str, row: dict[str, Any]) -> None:
    rows = _read_jsonl(fs, rel_path)
    rows.append(row)
    payload = "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in rows)
    fs.write_text(rel_path, payload)


def _session_steps_path(session_id: str) -> str:
    return f"{SESSIONS_DIR}/{session_id}.jsonl"


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(value).strip().lower()).strip("-")
    return slug or "apprenticeship-skill"


def _load_sessions(fs: WorkspaceFS) -> list[dict[str, Any]]:
    document = _read_json(fs, SESSIONS_INDEX_PATH, {"sessions": []})
    rows = document.get("sessions", []) if isinstance(document, dict) else []
    sessions = [row for row in rows if isinstance(row, dict)]
    return sorted(sessions, key=lambda row: str(row.get("updated_at", "")), reverse=True)


def _save_sessions(fs: WorkspaceFS, sessions: list[dict[str, Any]]) -> None:
    ordered = sorted(sessions, key=lambda row: str(row.get("updated_at", "")), reverse=True)
    _write_json(fs, SESSIONS_INDEX_PATH, {"sessions": ordered})


def list_sessions(fs: WorkspaceFS, *, limit: int | None = None) -> list[dict[str, Any]]:
    sessions = _load_sessions(fs)
    if limit is None:
        return sessions
    normalized_limit = max(0, min(int(limit), 200))
    return sessions[:normalized_limit]


def get_session(fs: WorkspaceFS, session_id: str) -> dict[str, Any] | None:
    normalized_id = str(session_id).strip()
    if not normalized_id:
        return None
    for session in _load_sessions(fs):
        if str(session.get("id", "")).strip() == normalized_id:
            return session
    return None


def load_session_steps(fs: WorkspaceFS, session_id: str) -> list[dict[str, Any]]:
    return _read_jsonl(fs, _session_steps_path(str(session_id).strip()))


def _update_session(fs: WorkspaceFS, session_id: str, **updates: Any) -> dict[str, Any]:
    normalized_id = str(session_id).strip()
    sessions = _load_sessions(fs)
    for index, session in enumerate(sessions):
        if str(session.get("id", "")).strip() != normalized_id:
            continue
        updated = {**session, **updates, "updated_at": updates.get("updated_at", utc_now_iso())}
        sessions[index] = updated
        _save_sessions(fs, sessions)
        return updated
    raise KeyError(f"Unknown teaching session: {normalized_id}")


def summarize_apprenticeship(fs: WorkspaceFS, *, limit: int = 5) -> dict[str, Any]:
    sessions = list_sessions(fs, limit=None)
    review_ready = [
        session
        for session in sessions
        if str(session.get("status", "")).strip().lower() in REVIEW_READY_STATUSES
    ]
    recording = [
        session
        for session in sessions
        if str(session.get("status", "")).strip().lower() == "recording"
    ]
    skillized = [
        session
        for session in sessions
        if str(session.get("status", "")).strip().lower() == "skillized"
    ]
    recent = list_sessions(fs, limit=limit)
    return {
        "session_count": len(sessions),
        "recording_count": len(recording),
        "review_count": len(review_ready),
        "skillized_count": len(skillized),
        "recent_sessions": recent,
        "review_ready": review_ready[: max(0, min(int(limit), 20))],
    }


def create_session(
    fs: WorkspaceFS,
    *,
    title: str,
    objective: str = "",
    mission_id: str | None = None,
    tags: list[str] | None = None,
    created_by: str = "architect",
) -> dict[str, Any]:
    now = utc_now_iso()
    session = {
        "id": f"teach-{str(uuid4())[:8]}",
        "title": " ".join(str(title).strip().split()) or "Untitled teaching session",
        "objective": " ".join(str(objective).strip().split()),
        "mission_id": str(mission_id or "").strip() or None,
        "tags": [str(tag).strip().lower() for tag in tags or [] if str(tag).strip()],
        "created_by": str(created_by).strip().lower() or "architect",
        "status": "recording",
        "step_count": 0,
        "created_at": now,
        "updated_at": now,
        "last_event_at": now,
        "skill_artifact_path": None,
        "forge_stage_id": None,
        "generalization": None,
    }
    sessions = _load_sessions(fs)
    sessions.append(session)
    _save_sessions(fs, sessions)
    return session


def add_session_step(
    fs: WorkspaceFS,
    *,
    session_id: str,
    kind: str,
    action: str,
    intent: str,
    artifact_path: str = "",
    notes: str = "",
    inputs: dict[str, Any] | None = None,
    outputs: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    session = get_session(fs, session_id)
    if session is None:
        raise KeyError(f"Unknown teaching session: {session_id}")

    steps = load_session_steps(fs, session_id)
    step = {
        "id": f"step-{str(uuid4())[:8]}",
        "ts": utc_now_iso(),
        "index": len(steps) + 1,
        "kind": str(kind).strip().lower() or "command",
        "action": " ".join(str(action).strip().split()),
        "intent": " ".join(str(intent).strip().split()) or "unspecified",
        "artifact_path": str(artifact_path).strip() or None,
        "notes": " ".join(str(notes).strip().split()),
        "inputs": inputs if isinstance(inputs, dict) else {},
        "outputs": outputs if isinstance(outputs, dict) else {},
    }
    _append_jsonl(fs, _session_steps_path(session["id"]), step)
    updated = _update_session(
        fs,
        session["id"],
        status="recording",
        step_count=step["index"],
        last_event_at=step["ts"],
        updated_at=step["ts"],
    )
    return updated, step


def build_replay(session: dict[str, Any], steps: list[dict[str, Any]]) -> dict[str, Any]:
    lines = []
    for step in steps:
        lines.append(
            f"Step {int(step.get('index', 0))}: {str(step.get('intent', 'unspecified')).strip()} "
            f"via {str(step.get('kind', 'command')).strip()} -> {str(step.get('action', '')).strip()}"
        )
    return {
        "session_id": session["id"],
        "title": session["title"],
        "objective": session.get("objective", ""),
        "step_count": len(steps),
        "lines": lines,
        "steps": steps,
    }


def _extract_parameter_candidates(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for step in steps:
        artifact_path = str(step.get("artifact_path") or "").strip()
        if artifact_path and artifact_path.lower() not in seen:
            name = f"artifact_path_{len(candidates) + 1}"
            candidates.append(
                {
                    "name": name,
                    "kind": "path",
                    "example": artifact_path,
                    "source_step_id": step.get("id"),
                }
            )
            seen.add(artifact_path.lower())
    return candidates


def generalize_session(fs: WorkspaceFS, session_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    session = get_session(fs, session_id)
    if session is None:
        raise KeyError(f"Unknown teaching session: {session_id}")
    steps = load_session_steps(fs, session_id)
    if not steps:
        raise ValueError("Teaching session has no steps to generalize.")

    parameters = _extract_parameter_candidates(steps)
    workflow: list[dict[str, Any]] = []
    seen_intents: list[str] = []
    for step in steps:
        template = str(step.get("action", "")).strip()
        for candidate in parameters:
            example = str(candidate.get("example", "")).strip()
            if example:
                template = template.replace(example, f"<{candidate['name']}>")
        intent = str(step.get("intent", "unspecified")).strip() or "unspecified"
        if intent not in seen_intents:
            seen_intents.append(intent)
        workflow.append(
            {
                "index": int(step.get("index", 0)),
                "intent": intent,
                "kind": str(step.get("kind", "command")).strip() or "command",
                "action_template": template,
                "notes": str(step.get("notes", "")).strip(),
            }
        )

    title = str(session.get("title", "Teaching session")).strip() or "Teaching session"
    summary = f"Reusable workflow distilled from {len(steps)} demonstrated step(s) in {title}."
    forge_payload = {
        "name": title,
        "description": summary,
        "rationale": (
            f"Derived from explicit user demonstration with intents: {', '.join(seen_intents[:4]) or 'unspecified'}."
        ),
        "tags": sorted(set(["apprenticeship", *session.get("tags", [])])),
        "risk_tier": "low",
    }
    generalization = {
        "generated_at": utc_now_iso(),
        "summary": summary,
        "workflow": workflow,
        "parameter_candidates": parameters,
        "intent_sequence": seen_intents,
        "skill_candidate": {
            "slug": _slugify(title),
            "forge_payload": forge_payload,
        },
    }
    updated = _update_session(
        fs,
        session["id"],
        status="review",
        generalization=generalization,
        last_event_at=generalization["generated_at"],
        updated_at=generalization["generated_at"],
    )
    return updated, generalization


def write_skill_artifact(
    fs: WorkspaceFS,
    session_id: str,
    *,
    name: str | None = None,
    description: str | None = None,
    rationale: str | None = None,
    tags: list[str] | None = None,
    risk_tier: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    session = get_session(fs, session_id)
    if session is None:
        raise KeyError(f"Unknown teaching session: {session_id}")
    generalization = session.get("generalization")
    if not isinstance(generalization, dict):
        raise ValueError("Teaching session must be generalized before skillization.")

    forge_payload = generalization.get("skill_candidate", {}).get("forge_payload", {})
    base_name = " ".join(str(name or forge_payload.get("name", session.get("title", ""))).strip().split())
    base_description = " ".join(
        str(description or forge_payload.get("description", generalization.get("summary", ""))).strip().split()
    )
    base_rationale = " ".join(str(rationale or forge_payload.get("rationale", "")).strip().split())
    merged_tags = sorted(
        set(
            str(tag).strip().lower()
            for tag in [
                *(forge_payload.get("tags", []) if isinstance(forge_payload.get("tags"), list) else []),
                *(tags or []),
            ]
            if str(tag).strip()
        )
    )
    merged_risk_tier = str(risk_tier or forge_payload.get("risk_tier", "low")).strip().lower() or "low"
    artifact = {
        "version": 1,
        "created_at": utc_now_iso(),
        "session_id": session["id"],
        "session": {
            "id": session["id"],
            "title": session.get("title"),
            "objective": session.get("objective"),
            "mission_id": session.get("mission_id"),
            "tags": session.get("tags", []),
            "step_count": session.get("step_count", 0),
        },
        "generalization": generalization,
        "forge_payload": {
            "name": base_name,
            "description": base_description,
            "rationale": base_rationale,
            "tags": merged_tags,
            "risk_tier": merged_risk_tier,
        },
    }
    rel_path = f"{SKILLS_DIR}/{session['id']}.json"
    _write_json(fs, rel_path, artifact)
    updated = _update_session(
        fs,
        session["id"],
        skill_artifact_path=rel_path,
        last_event_at=artifact["created_at"],
        updated_at=artifact["created_at"],
    )
    return updated, {"path": rel_path, **artifact}


def mark_session_skillized(
    fs: WorkspaceFS,
    session_id: str,
    *,
    forge_stage_id: str,
    skill_artifact_path: str,
) -> dict[str, Any]:
    return _update_session(
        fs,
        session_id,
        status="skillized",
        forge_stage_id=str(forge_stage_id).strip() or None,
        skill_artifact_path=str(skill_artifact_path).strip() or None,
        last_event_at=utc_now_iso(),
    )
