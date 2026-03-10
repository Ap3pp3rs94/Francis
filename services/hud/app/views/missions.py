from __future__ import annotations

from services.hud.app.state import build_lens_snapshot


def get_missions_view(*, snapshot: dict[str, object] | None = None) -> dict[str, object]:
    if snapshot is None:
        snapshot = build_lens_snapshot()
    missions = snapshot["missions"]
    return {
        "status": "ok",
        "surface": "missions",
        "active_count": missions["active_count"],
        "backlog_count": missions["backlog_count"],
        "completed_count": missions["completed_count"],
        "active": missions["active"],
        "backlog": missions["backlog"],
        "completed": missions["completed"],
    }
