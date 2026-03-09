from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

LANE_PRIORITY = {"hot": 3, "warm": 2, "cold": 1}
HOT_SOURCES = {
    "approvals.requests",
    "incidents.incidents",
    "runs.last",
    "runs.ledger",
    "control.takeover_activity",
    "autonomy.last_dispatch",
    "autonomy.last_tick",
}
WARM_SOURCES = {
    "missions.missions",
    "missions.history",
    "journals.decisions",
    "forge.catalog",
    "apprenticeship.sessions",
    "apprenticeship.skills",
    "queue.deadletter",
    "autonomy.dispatch_history",
    "autonomy.tick_history",
}
SEVERITY_WEIGHT = {
    "critical": 4,
    "error": 3,
    "high": 3,
    "warn": 2,
    "warning": 2,
    "medium": 2,
    "alert": 2,
    "low": 1,
    "info": 1,
    "nominal": 0,
}


def _parse_ts(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        parsed = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except Exception:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def assign_retention_lane(artifact: dict[str, Any], *, now: datetime | None = None) -> str:
    current = now or datetime.now(timezone.utc)
    source = str(artifact.get("source", "")).strip().lower()
    ts = _parse_ts(str(artifact.get("ts", "")).strip() or None)
    age = current - ts if ts is not None else timedelta(days=3650)
    severity = str(artifact.get("severity", artifact.get("status", ""))).strip().lower()
    verification = str(artifact.get("verification_status", "")).strip().lower()
    relation_count = sum(
        1 for value in (artifact.get("relationships") or {}).values() if str(value or "").strip()
    )

    if source in HOT_SOURCES:
        return "hot"
    if severity in {"critical", "error", "high", "alert"}:
        return "hot"
    if verification == "verified":
        return "hot"
    if age <= timedelta(days=2) and relation_count >= 2:
        return "hot"
    if source in WARM_SOURCES:
        return "warm"
    if age <= timedelta(days=14):
        return "warm"
    return "cold"


def lane_weight(lane: str) -> float:
    return float(LANE_PRIORITY.get(str(lane).strip().lower(), 0))


def recency_weight(ts: str | None, *, now: datetime | None = None) -> float:
    current = now or datetime.now(timezone.utc)
    parsed = _parse_ts(ts)
    if parsed is None:
        return 0.0
    age = current - parsed
    if age <= timedelta(hours=24):
        return 4.0
    if age <= timedelta(days=7):
        return 2.5
    if age <= timedelta(days=30):
        return 1.0
    return 0.0


def severity_weight(value: str | None) -> float:
    return float(SEVERITY_WEIGHT.get(str(value or "").strip().lower(), 0))


def summarize_lanes(artifacts: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(str(item.get("retention_lane", "cold")).strip().lower() or "cold" for item in artifacts)
    return {
        "hot": int(counts.get("hot", 0)),
        "warm": int(counts.get("warm", 0)),
        "cold": int(counts.get("cold", 0)),
    }
