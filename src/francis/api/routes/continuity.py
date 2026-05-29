from __future__ import annotations

from francis.api.errors import api_error_message
import time
from typing import Any

from fastapi import APIRouter

from francis.chat.continuity.ledger import tail
from francis.world_state.operator_mode import snapshot as operator_mode_snapshot
from francis.world_state.orb import snapshot as orb_status_snapshot
from francis.world_state.snapshot import (
    mission_continuity_snapshot,
    observer_incident_snapshot,
    observer_readiness,
    observer_scan_history,
    observer_summary,
)

router = APIRouter()


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _operator_surface() -> dict[str, Any]:
    try:
        payload = operator_mode_snapshot()
    except Exception as exc:
        return {"available": False, "error": api_error_message(exc)}

    if not bool(payload.get("ok")):
        return {
            "available": False,
            "error": str(payload.get("error") or "operator_mode_unavailable"),
        }

    return {
        "available": True,
        "control_mode": _as_dict(payload.get("control_mode")),
        "focus": _as_dict(payload.get("focus")),
        "posture": _as_dict(payload.get("posture")),
    }


def _orb_surface() -> dict[str, Any]:
    try:
        payload = orb_status_snapshot()
    except Exception as exc:
        return {"available": False, "error": api_error_message(exc)}

    if not bool(payload.get("ok")):
        return {
            "available": False,
            "error": str(payload.get("error") or "orb_status_unavailable"),
        }

    return {
        "available": True,
        "state": _as_dict(payload.get("state")),
    }


def _observer_briefing() -> dict[str, Any]:
    try:
        payload = observer_incident_snapshot()
        recent_scans = observer_scan_history(limit=3)
        summary = observer_summary(payload)
    except Exception as exc:
        return {
            "headline": "Observer summary unavailable.",
            "counts": {"active": 0},
            "focus": [],
            "recent_scans": [],
            "error": api_error_message(exc),
        }

    return {
        "headline": summary["headline"],
        "counts": summary["counts"],
        "focus": summary["focus"],
        "probes": summary["probe_statuses"],
        "anomaly": summary["anomaly"],
        "observed_at": float(payload.get("generated_at") or 0.0),
        "recent_scans": recent_scans,
        "readiness": observer_readiness(payload, recent_scans=recent_scans),
    }


@router.get("/ledger")
def ledger(limit: int = 200) -> dict[str, object]:
    try:
        return {"entries": tail(limit=limit)}
    except Exception as exc:
        return {"entries": [], "error": api_error_message(exc)}


@router.get("/briefing")
@router.get("/shift_briefing")
@router.get("/shift-briefing")
def briefing(
    recent_limit: int = 5,
    queue_limit: int = 3,
    deadletter_limit: int = 2,
    activity_log_limit: int = 20,
) -> dict[str, object]:
    try:
        continuity = mission_continuity_snapshot(
            recent_limit=max(1, min(recent_limit, 20)),
            queue_limit=max(1, min(queue_limit, 10)),
            deadletter_limit=max(1, min(deadletter_limit, 10)),
            activity_log_limit=max(1, min(activity_log_limit, 100)),
        )
        return {
            "ok": True,
            "subsystem": "continuity_briefing",
            "generated_at": time.time(),
            "briefing": {
                **_as_dict(continuity.get("mission_briefing")),
                "observer": _observer_briefing(),
            },
            "mission_status_counts": _as_dict(continuity.get("mission_status_counts")),
            "recent_missions": [item for item in _as_list(continuity.get("recent_missions")) if isinstance(item, dict)],
            "operator": _operator_surface(),
            "orb": _orb_surface(),
        }
    except Exception as exc:
        return {
            "ok": False,
            "subsystem": "continuity_briefing",
            "error": api_error_message(exc),
            "briefing": {},
            "mission_status_counts": {},
            "recent_missions": [],
            "operator": {"available": False},
            "orb": {"available": False},
        }
