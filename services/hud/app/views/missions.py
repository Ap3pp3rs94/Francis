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


def _decorate(rows: list[dict[str, Any]], *, lane: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        item = dict(row)
        item["lane"] = lane
        item["detail_summary"] = _detail_summary(item)
        items.append(item)
    return items


def get_missions_view(*, snapshot: dict[str, object] | None = None) -> dict[str, object]:
    if snapshot is None:
        snapshot = build_lens_snapshot()
    missions = snapshot["missions"]
    active = _decorate(
        missions["active"] if isinstance(missions.get("active"), list) else [],
        lane="active",
    )
    backlog = _decorate(
        missions["backlog"] if isinstance(missions.get("backlog"), list) else [],
        lane="backlog",
    )
    completed = _decorate(
        missions["completed"] if isinstance(missions.get("completed"), list) else [],
        lane="completed",
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
            "primary": primary,
            "active": active,
            "backlog": backlog,
            "completed": completed,
        },
    }
