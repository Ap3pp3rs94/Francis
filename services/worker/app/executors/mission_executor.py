from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from services.orchestrator.app.routes.missions import execute_mission_tick


def execute(job: dict[str, Any], *, run_id: str) -> dict[str, Any]:
    mission_id = str(job.get("mission_id", "")).strip()
    job_id = str(job.get("id", "")).strip()
    if not mission_id:
        return {
            "ok": False,
            "error": "missing mission_id",
            "job_id": job_id,
            "action": "mission.tick",
        }
    try:
        result = execute_mission_tick(
            mission_id=mission_id,
            run_id=run_id,
            role="worker",
            idempotency_key=f"worker:{job_id or mission_id}",
        )
        return {
            "ok": True,
            "job_id": job_id,
            "action": "mission.tick",
            "mission_id": mission_id,
            "result": result,
        }
    except HTTPException as exc:
        return {
            "ok": False,
            "job_id": job_id,
            "action": "mission.tick",
            "mission_id": mission_id,
            "status_code": exc.status_code,
            "error": str(exc.detail),
        }
    except Exception as exc:
        return {
            "ok": False,
            "job_id": job_id,
            "action": "mission.tick",
            "mission_id": mission_id,
            "error": str(exc),
        }
