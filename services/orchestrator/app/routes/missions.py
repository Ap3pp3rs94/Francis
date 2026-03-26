from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from francis_brain.ledger import RunLedger
from francis_core.clock import utc_now_iso
from francis_core.config import settings
from francis_core.workspace_fs import WorkspaceFS
from francis_policy.approvals import requires_approval
from francis_policy.rbac import can
from services.orchestrator.app.control_state import check_action_allowed

router = APIRouter(tags=["missions"])

_workspace_root = Path(settings.workspace_root).resolve()
_repo_root = _workspace_root.parent
_fs = WorkspaceFS(
    roots=[_workspace_root],
    journal_path=(_workspace_root / "journals" / "fs.jsonl").resolve(),
)
_ledger = RunLedger(_fs, rel_path="runs/run_ledger.jsonl")


class MissionCreate(BaseModel):
    title: str
    objective: str = ""
    priority: str = "normal"
    steps: list[str] = Field(default_factory=list)


class MissionTickRequest(BaseModel):
    force_fail: bool = False
    reason: str = ""
    idempotency_key: str | None = None


def _read_json(rel_path: str, default: object) -> object:
    try:
        raw = _fs.read_text(rel_path)
    except Exception:
        return default
    try:
        return json.loads(raw)
    except Exception:
        return default


def _write_json(rel_path: str, value: object) -> None:
    _fs.write_text(rel_path, json.dumps(value, ensure_ascii=False, indent=2))


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


def _write_jsonl(rel_path: str, rows: list[dict]) -> None:
    if not rows:
        _fs.write_text(rel_path, "")
        return
    payload = "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in rows)
    _fs.write_text(rel_path, payload)


def _append_jsonl(rel_path: str, row: dict) -> None:
    rows = _read_jsonl(rel_path)
    rows.append(row)
    _write_jsonl(rel_path, rows)


def _load_missions() -> list[dict]:
    doc = _read_json("missions/missions.json", {"missions": []})
    if isinstance(doc, dict):
        missions = doc.get("missions", [])
        if isinstance(missions, list):
            return [m for m in missions if isinstance(m, dict)]
    return []


def _save_missions(missions: list[dict]) -> None:
    _write_json("missions/missions.json", {"missions": missions})


def _append_history(event: dict) -> None:
    _append_jsonl("missions/history.jsonl", event)


def _normalize_trace_id(trace_id: str | None, *, fallback_run_id: str) -> str:
    normalized = str(trace_id or "").strip()
    return normalized or fallback_run_id


TERMINAL_MISSION_STATUSES = {"completed", "failed", "cancelled", "canceled"}


def _job_status(job: dict) -> str:
    return str(job.get("status", "")).strip().lower()


def _is_mission_tick_job(job: dict, *, mission_id: str | None = None) -> bool:
    if str(job.get("action", "")).strip().lower() != "mission.tick":
        return False
    if mission_id is None:
        return True
    return str(job.get("mission_id", "")).strip() == mission_id


def _build_job(
    *,
    run_id: str,
    mission_id: str,
    action: str,
    priority: str,
    trace_id: str,
) -> dict:
    return {
        "id": str(uuid4()),
        "ts": utc_now_iso(),
        "run_id": run_id,
        "trace_id": trace_id,
        "mission_id": mission_id,
        "action": action,
        "priority": priority,
        "status": "queued",
        "attempts": 0,
        "lease_key": None,
        "lease_owner": None,
        "lease_expires_at": None,
        "finished_at": None,
        "last_result": None,
    }


def _mark_job_superseded(
    job: dict,
    *,
    ts: str,
    trace_id: str,
    reason: str,
    superseded_by: str | None = None,
) -> bool:
    changed = False
    if _job_status(job) != "superseded":
        job["status"] = "superseded"
        changed = True
    if job.get("finished_at") != ts:
        job["finished_at"] = ts
        changed = True
    normalized_trace_id = str(job.get("trace_id", "")).strip() or trace_id
    if job.get("trace_id") != normalized_trace_id:
        job["trace_id"] = normalized_trace_id
        changed = True
    if superseded_by and job.get("superseded_by") != superseded_by:
        job["superseded_by"] = superseded_by
        changed = True
    desired_result = {
        "status": "superseded",
        "reason": reason,
        "trace_id": normalized_trace_id,
    }
    if superseded_by:
        desired_result["superseded_by"] = superseded_by
    if job.get("last_result") != desired_result:
        job["last_result"] = desired_result
        changed = True
    return changed


def normalize_mission_job_queue(
    *,
    run_id: str,
    trace_id: str | None = None,
    mission_id: str | None = None,
) -> dict:
    normalized_trace_id = _normalize_trace_id(trace_id, fallback_run_id=run_id)
    missions = _load_missions()
    mission_statuses = {
        str(item.get("id", "")).strip(): str(item.get("status", "")).strip().lower()
        for item in missions
        if isinstance(item, dict) and str(item.get("id", "")).strip()
    }
    jobs = _read_jsonl("queue/jobs.jsonl")
    now = utc_now_iso()
    changed = False
    pending_by_mission: dict[str, str] = {}
    duplicate_superseded_count = 0
    terminal_superseded_count = 0
    considered_count = 0

    for index, job in enumerate(jobs):
        if not _is_mission_tick_job(job):
            continue
        current_mission_id = str(job.get("mission_id", "")).strip()
        if not current_mission_id:
            continue
        if mission_id is not None and current_mission_id != mission_id:
            continue
        considered_count += 1
        status = _job_status(job)
        if status != "queued":
            continue

        current_mission_status = mission_statuses.get(current_mission_id, "")
        if current_mission_status in TERMINAL_MISSION_STATUSES:
            if _mark_job_superseded(
                job,
                ts=now,
                trace_id=normalized_trace_id,
                reason=f"mission_terminal:{current_mission_status}",
            ):
                jobs[index] = job
                terminal_superseded_count += 1
                changed = True
            continue

        canonical_job_id = pending_by_mission.get(current_mission_id)
        if canonical_job_id:
            if _mark_job_superseded(
                job,
                ts=now,
                trace_id=normalized_trace_id,
                reason="duplicate_pending_mission_job",
                superseded_by=canonical_job_id,
            ):
                jobs[index] = job
                duplicate_superseded_count += 1
                changed = True
            continue

        canonical_job_id = str(job.get("id", "")).strip()
        if not canonical_job_id:
            canonical_job_id = str(uuid4())
            job["id"] = canonical_job_id
            changed = True
        if not str(job.get("trace_id", "")).strip():
            job["trace_id"] = normalized_trace_id
            changed = True
        jobs[index] = job
        pending_by_mission[current_mission_id] = canonical_job_id

    if changed:
        _write_jsonl("queue/jobs.jsonl", jobs)

    repaired_count = duplicate_superseded_count + terminal_superseded_count
    return {
        "status": "ok",
        "run_id": run_id,
        "trace_id": normalized_trace_id,
        "mission_id": mission_id,
        "considered_count": considered_count,
        "pending_active_count": len(pending_by_mission),
        "duplicate_superseded_count": duplicate_superseded_count,
        "terminal_superseded_count": terminal_superseded_count,
        "repaired_count": repaired_count,
        "changed": repaired_count > 0 or changed,
    }


def _queue_job(
    *,
    run_id: str,
    mission_id: str,
    action: str = "mission.tick",
    priority: str = "normal",
    trace_id: str | None = None,
) -> dict:
    normalized_trace_id = _normalize_trace_id(trace_id, fallback_run_id=run_id)
    if action != "mission.tick":
        job = _build_job(
            run_id=run_id,
            mission_id=mission_id,
            action=action,
            priority=priority,
            trace_id=normalized_trace_id,
        )
        _append_jsonl("queue/jobs.jsonl", job)
        return job

    jobs = _read_jsonl("queue/jobs.jsonl")
    queued_indexes = [
        index
        for index, job in enumerate(jobs)
        if _is_mission_tick_job(job, mission_id=mission_id) and _job_status(job) == "queued"
    ]
    if queued_indexes:
        now = utc_now_iso()
        keep_index = queued_indexes[0]
        keep_job = jobs[keep_index]
        changed = False
        if not str(keep_job.get("trace_id", "")).strip():
            keep_job["trace_id"] = normalized_trace_id
            changed = True
        jobs[keep_index] = keep_job
        keep_job_id = str(keep_job.get("id", "")).strip()
        for index in queued_indexes[1:]:
            duplicate = jobs[index]
            if _mark_job_superseded(
                duplicate,
                ts=now,
                trace_id=normalized_trace_id,
                reason="duplicate_pending_mission_job",
                superseded_by=keep_job_id or None,
            ):
                jobs[index] = duplicate
                changed = True
        if changed:
            _write_jsonl("queue/jobs.jsonl", jobs)
        return keep_job

    job = _build_job(
        run_id=run_id,
        mission_id=mission_id,
        action=action,
        priority=priority,
        trace_id=normalized_trace_id,
    )
    jobs.append(job)
    _write_jsonl("queue/jobs.jsonl", jobs)
    return job


def _parse_iso(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts)
    except Exception:
        return None


def _lease_or_replay_job(
    *,
    mission_id: str,
    lease_key: str,
    lease_owner: str,
    run_id: str,
    trace_id: str | None = None,
    ttl_seconds: int = 30,
) -> tuple[str, dict]:
    """
    Returns (state, job)
    state in {"leased", "replay", "busy"}.
    """
    jobs = _read_jsonl("queue/jobs.jsonl")

    now = datetime.now(timezone.utc)
    normalized_trace_id = _normalize_trace_id(trace_id, fallback_run_id=run_id)
    selected_idx: int | None = None

    for i, job in enumerate(jobs):
        if job.get("mission_id") != mission_id:
            continue
        status = str(job.get("status", "")).lower()
        existing_key = str(job.get("lease_key") or "")

        if existing_key == lease_key and status in {"done", "failed"} and isinstance(job.get("last_result"), dict):
            return ("replay", job)

        if status == "leased":
            lease_expiry = _parse_iso(job.get("lease_expires_at"))
            if lease_expiry and lease_expiry > now:
                if existing_key == lease_key:
                    return ("replay", job)
                return ("busy", job)
            job["status"] = "queued"
            job["lease_owner"] = None
            job["lease_key"] = None
            job["lease_expires_at"] = None

    for i, job in enumerate(jobs):
        if job.get("mission_id") == mission_id and str(job.get("status", "")).lower() == "queued":
            selected_idx = i
            break

    if selected_idx is None:
        jobs.append(_queue_job(run_id=run_id, mission_id=mission_id, trace_id=normalized_trace_id))
        selected_idx = len(jobs) - 1

    job = jobs[selected_idx]
    job["status"] = "leased"
    if not str(job.get("trace_id", "")).strip():
        job["trace_id"] = normalized_trace_id
    job["lease_key"] = lease_key
    job["lease_owner"] = lease_owner
    job["lease_expires_at"] = (now + timedelta(seconds=ttl_seconds)).isoformat()
    job["attempts"] = int(job.get("attempts", 0)) + 1
    jobs[selected_idx] = job
    _write_jsonl("queue/jobs.jsonl", jobs)
    return ("leased", job)


def _complete_lease(*, job_id: str, lease_key: str, outcome: str, result: dict) -> None:
    jobs = _read_jsonl("queue/jobs.jsonl")
    updated = False
    for i, job in enumerate(jobs):
        if job.get("id") != job_id:
            continue
        if str(job.get("lease_key") or "") != lease_key:
            continue
        job["status"] = "done" if outcome == "success" else "failed"
        job["finished_at"] = utc_now_iso()
        job["lease_expires_at"] = None
        job["last_result"] = result
        jobs[i] = job
        updated = True
        break
    if updated:
        _write_jsonl("queue/jobs.jsonl", jobs)


def _active_mission_count(missions: list[dict]) -> int:
    return sum(1 for mission in missions if str(mission.get("status", "")).lower() not in TERMINAL_MISSION_STATUSES)


def _enforce_policy(action: str) -> None:
    if requires_approval(action):
        raise HTTPException(status_code=403, detail=f"Action requires approval: {action}")


def _enforce_control(action: str, *, mutating: bool) -> None:
    allowed, reason, _state = check_action_allowed(
        _fs,
        repo_root=_repo_root,
        workspace_root=_workspace_root,
        app="missions",
        action=action,
        mutating=mutating,
    )
    if not allowed:
        raise HTTPException(status_code=403, detail=f"Control denied: {reason}")


def _role_from_request(request: Request) -> str:
    return request.headers.get("x-francis-role", "architect").strip().lower()


def _enforce_rbac_role(role: str, action: str) -> None:
    if not can(role, action):
        raise HTTPException(status_code=403, detail=f"RBAC denied: role={role}, action={action}")


def _enforce_rbac(request: Request, action: str) -> None:
    role = _role_from_request(request)
    _enforce_rbac_role(role, action)


def _find_mission(missions: list[dict], mission_id: str) -> tuple[int, dict]:
    for i, mission in enumerate(missions):
        if mission.get("id") == mission_id:
            return i, mission
    raise HTTPException(status_code=404, detail=f"Mission not found: {mission_id}")


@router.get("/missions")
def list_missions(request: Request) -> dict:
    _enforce_control("missions.read", mutating=False)
    _enforce_rbac(request, "missions.read")
    missions = _load_missions()
    return {"status": "ok", "missions": missions, "active_count": _active_mission_count(missions)}


@router.get("/missions/{mission_id}")
def get_mission(mission_id: str, request: Request) -> dict:
    _enforce_control("missions.read", mutating=False)
    _enforce_rbac(request, "missions.read")
    missions = _load_missions()
    _idx, mission = _find_mission(missions, mission_id)
    return {"status": "ok", "mission": mission}


@router.post("/missions")
def create_mission(request: Request, payload: MissionCreate) -> dict:
    _enforce_control("missions.create", mutating=True)
    _enforce_rbac(request, "missions.create")
    _enforce_policy("missions.create")
    run_id = str(getattr(request.state, "run_id", uuid4()))
    trace_id = _normalize_trace_id(getattr(request.state, "trace_id", None), fallback_run_id=run_id)
    now = utc_now_iso()

    missions = _load_missions()
    mission = {
        "id": str(uuid4()),
        "title": payload.title,
        "objective": payload.objective,
        "priority": payload.priority,
        "status": "queued",
        "steps": payload.steps,
        "next_step_index": 0,
        "completed_steps": [],
        "created_at": now,
        "updated_at": now,
        "last_error": "",
    }
    missions.append(mission)
    _save_missions(missions)

    history_event = {
        "id": str(uuid4()),
        "ts": now,
        "run_id": run_id,
        "trace_id": trace_id,
        "mission_id": mission["id"],
        "event": "mission.created",
        "status": mission["status"],
    }
    _append_history(history_event)

    queued_job = _queue_job(
        run_id=run_id,
        mission_id=mission["id"],
        priority=str(mission.get("priority", "normal")),
        trace_id=trace_id,
    )
    _ledger.append(
        run_id=run_id,
        kind="mission.created",
        summary={
            "mission_id": mission["id"],
            "status": mission["status"],
            "steps": len(mission["steps"]),
            "trace_id": trace_id,
        },
    )
    return {
        "status": "ok",
        "run_id": run_id,
        "trace_id": trace_id,
        "mission": mission,
        "queued_job": queued_job,
    }


@router.post("/missions/{mission_id}/tick")
def tick_mission(mission_id: str, request: Request, payload: MissionTickRequest | None = None) -> dict:
    body = payload or MissionTickRequest()
    run_id = str(getattr(request.state, "run_id", uuid4()))
    trace_id = _normalize_trace_id(getattr(request.state, "trace_id", None), fallback_run_id=run_id)
    role = _role_from_request(request)
    lease_key = body.idempotency_key or request.headers.get("x-idempotency-key")
    return execute_mission_tick(
        mission_id=mission_id,
        run_id=run_id,
        trace_id=trace_id,
        role=role,
        force_fail=body.force_fail,
        reason=body.reason,
        idempotency_key=lease_key,
    )


def execute_mission_tick(
    *,
    mission_id: str,
    run_id: str,
    trace_id: str | None = None,
    role: str = "architect",
    force_fail: bool = False,
    reason: str = "",
    idempotency_key: str | None = None,
) -> dict:
    _enforce_control("missions.tick", mutating=True)
    _enforce_rbac_role(role, "missions.tick")
    _enforce_policy("missions.tick")
    now = utc_now_iso()
    normalized_trace_id = _normalize_trace_id(trace_id, fallback_run_id=run_id)
    lease_key = idempotency_key or f"{mission_id}:{run_id}"

    missions = _load_missions()
    idx, mission = _find_mission(missions, mission_id)

    if mission.get("status") in TERMINAL_MISSION_STATUSES:
        queue_repair = normalize_mission_job_queue(
            run_id=run_id,
            trace_id=normalized_trace_id,
            mission_id=mission_id,
        )
        return {
            "status": "ok",
            "run_id": run_id,
            "trace_id": normalized_trace_id,
            "mission": mission,
            "tick": "skipped",
            "queue_repair": queue_repair,
        }

    lease_state, leased_job = _lease_or_replay_job(
        mission_id=mission_id,
        lease_key=lease_key,
        lease_owner=run_id,
        run_id=run_id,
        trace_id=normalized_trace_id,
    )
    if lease_state == "busy":
        raise HTTPException(status_code=409, detail="Mission job is currently leased by another run.")
    if lease_state == "replay":
        replay = leased_job.get("last_result")
        if isinstance(replay, dict):
            replay.setdefault("trace_id", normalized_trace_id)
            return replay

    if force_fail:
        mission["status"] = "failed"
        mission["last_error"] = reason or "Mission tick failed."
        mission["updated_at"] = now
        missions[idx] = mission
        _save_missions(missions)
        queue_repair = normalize_mission_job_queue(
            run_id=run_id,
            trace_id=normalized_trace_id,
            mission_id=mission_id,
        )

        dead = {
            "id": str(uuid4()),
            "ts": now,
            "run_id": run_id,
            "trace_id": normalized_trace_id,
            "mission_id": mission_id,
            "reason": mission["last_error"],
            "job": leased_job,
        }
        _append_jsonl("queue/deadletter.jsonl", dead)

        _append_history(
            {
                "id": str(uuid4()),
                "ts": now,
                "run_id": run_id,
                "trace_id": normalized_trace_id,
                "mission_id": mission_id,
                "event": "mission.failed",
                "status": "failed",
                "reason": mission["last_error"],
            }
        )
        _ledger.append(
            run_id=run_id,
            kind="mission.failed",
            summary={
                "mission_id": mission_id,
                "reason": mission["last_error"],
                "trace_id": normalized_trace_id,
                "queue_repair": queue_repair,
            },
        )
        result = {
            "status": "ok",
            "run_id": run_id,
            "trace_id": normalized_trace_id,
            "mission": mission,
            "deadletter": dead,
            "queue_repair": queue_repair,
        }
        _complete_lease(
            job_id=str(leased_job.get("id")),
            lease_key=lease_key,
            outcome="failed",
            result=result,
        )
        return result

    mission.setdefault("steps", [])
    mission.setdefault("completed_steps", [])
    next_idx = int(mission.get("next_step_index", 0))
    step_executed = None
    steps = mission["steps"]
    if next_idx < len(steps):
        step_executed = steps[next_idx]
        mission["completed_steps"].append(step_executed)
        mission["next_step_index"] = next_idx + 1

    if not steps:
        mission["status"] = "completed"
    elif int(mission["next_step_index"]) >= len(steps):
        mission["status"] = "completed"
    else:
        mission["status"] = "active"

    mission["updated_at"] = now
    missions[idx] = mission
    _save_missions(missions)
    queue_repair = normalize_mission_job_queue(
        run_id=run_id,
        trace_id=normalized_trace_id,
        mission_id=mission_id,
    )

    queued_job = None
    if mission["status"] == "active":
        queued_job = _queue_job(
            run_id=run_id,
            mission_id=mission_id,
            priority=str(mission.get("priority", "normal")),
            trace_id=normalized_trace_id,
        )

    _append_history(
        {
            "id": str(uuid4()),
            "ts": now,
            "run_id": run_id,
            "trace_id": normalized_trace_id,
            "mission_id": mission_id,
            "event": "mission.tick",
            "status": mission["status"],
            "step_executed": step_executed,
        }
    )
    _ledger.append(
        run_id=run_id,
        kind="mission.tick",
        summary={
            "mission_id": mission_id,
            "status": mission["status"],
            "step_executed": step_executed,
            "queued_next": queued_job is not None,
            "queue_repair": queue_repair,
            "trace_id": normalized_trace_id,
        },
    )
    result = {
        "status": "ok",
        "run_id": run_id,
        "trace_id": normalized_trace_id,
        "mission": mission,
        "step_executed": step_executed,
        "queued_job": queued_job,
        "queue_repair": queue_repair,
    }
    _complete_lease(
        job_id=str(leased_job.get("id")),
        lease_key=lease_key,
        outcome="success",
        result=result,
    )
    return result
