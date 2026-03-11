from __future__ import annotations

from typing import Any

from services.hud.app.state import build_lens_snapshot


def _priority_rank(value: object) -> int:
    normalized = str(value or "").strip().lower()
    if normalized in {"critical", "urgent"}:
        return 4
    if normalized == "high":
        return 3
    if normalized == "medium":
        return 2
    if normalized == "low":
        return 1
    return 0


def _severity_for_missions(active: list[dict[str, Any]], backlog: list[dict[str, Any]]) -> str:
    if any(_priority_rank(row.get("priority")) >= 3 for row in active):
        return "high"
    if active:
        return "medium"
    if backlog:
        return "low"
    return "low"


def _detail_summary(row: dict[str, Any]) -> str:
    title = str(row.get("title", "Untitled mission")).strip() or "Untitled mission"
    objective = str(row.get("objective", "")).strip()
    phase = str(row.get("phase") or row.get("status") or "planned").strip() or "planned"
    priority = str(row.get("priority", "normal")).strip() or "normal"
    if objective:
        return f"{title} is in {phase} with {priority} priority. {objective}".strip()
    return f"{title} is in {phase} with {priority} priority.".strip()


def _detail_cards(row: dict[str, Any], *, lane: str) -> list[dict[str, str]]:
    phase = str(row.get("phase") or row.get("status") or "planned").strip() or "planned"
    priority = str(row.get("priority", "normal")).strip() or "normal"
    return [
        {"label": "Mission", "value": str(row.get("title", "Untitled mission")).strip() or "Untitled mission", "tone": "high" if lane == "active" else "low"},
        {"label": "Lane", "value": lane, "tone": "medium" if lane == "active" else "low"},
        {"label": "Phase", "value": phase, "tone": "medium"},
        {"label": "Priority", "value": priority, "tone": "high" if priority.lower() in {"critical", "urgent", "high"} else "low"},
    ]


def _audit(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row.get("id", "")).strip(),
        "title": str(row.get("title", "Untitled mission")).strip() or "Untitled mission",
        "lane": str(row.get("lane", "")).strip(),
        "phase": str(row.get("phase") or row.get("status") or "planned").strip() or "planned",
        "priority": str(row.get("priority", "normal")).strip() or "normal",
        "summary": str(row.get("detail_summary", "")).strip(),
        "detail_state": str(row.get("detail_state", "historical")).strip(),
    }


def _decorate(rows: list[dict[str, Any]], *, lane: str, primary_id: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        item = dict(row)
        item["lane"] = lane
        item["detail_summary"] = _detail_summary(item)
        item["detail_cards"] = _detail_cards(item, lane=lane)
        item["detail_state"] = "current" if primary_id and str(item.get("id", "")).strip() == primary_id else "historical"
        item["audit"] = _audit(item)
        items.append(item)
    return items


def get_missions_view(*, snapshot: dict[str, object] | None = None) -> dict[str, object]:
    if snapshot is None:
        snapshot = build_lens_snapshot()
    missions = snapshot["missions"]
    active_rows = missions["active"] if isinstance(missions.get("active"), list) else []
    backlog_rows = missions["backlog"] if isinstance(missions.get("backlog"), list) else []
    completed_rows = missions["completed"] if isinstance(missions.get("completed"), list) else []
    primary_source = active_rows[0] if active_rows else (backlog_rows[0] if backlog_rows else None)
    primary_id = str(primary_source.get("id", "")).strip() if isinstance(primary_source, dict) else ""
    active = _decorate(
        active_rows,
        lane="active",
        primary_id=primary_id,
    )
    backlog = _decorate(
        backlog_rows,
        lane="backlog",
        primary_id=primary_id,
    )
    completed = _decorate(
        completed_rows,
        lane="completed",
        primary_id=primary_id,
    )
    primary = active[0] if active else (backlog[0] if backlog else None)
    severity = _severity_for_missions(active, backlog)
    if primary:
        summary = str(primary.get("detail_summary", "")).strip() or "Mission focus is available."
    else:
        summary = "No active mission is currently driving work."
    return {
        "status": "ok",
        "surface": "missions",
        "focus_mission_id": str(primary.get("id", "")).strip() if primary else "",
        "summary": summary,
        "severity": severity,
        "cards": [
            {"label": "Active", "value": str(len(active)), "tone": "high" if active else "low"},
            {"label": "Backlog", "value": str(len(backlog)), "tone": "medium" if backlog else "low"},
            {"label": "Completed", "value": str(len(completed)), "tone": "low"},
            {
                "label": "Primary",
                "value": str(primary.get("title", "none")).strip() if primary else "none",
                "tone": severity,
            },
        ],
        "active_count": missions["active_count"],
        "backlog_count": missions["backlog_count"],
        "completed_count": missions["completed_count"],
        "active": active,
        "backlog": backlog,
        "completed": completed,
        "detail": {
            "focus_state": "active" if active else "backlog" if backlog else "idle",
            "focus_mission_id": str(primary.get("id", "")).strip() if primary else "",
            "primary": primary,
            "active": active,
            "backlog": backlog,
            "completed": completed,
        },
    }
