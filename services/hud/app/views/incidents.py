from __future__ import annotations

from services.hud.app.state import build_lens_snapshot


def get_incidents_view() -> dict[str, object]:
    snapshot = build_lens_snapshot()
    incidents = snapshot["incidents"]
    security = snapshot.get("security", {})
    return {
        "status": "ok",
        "surface": "incidents",
        "severity": incidents["highest_severity"],
        "open_count": incidents["open_count"],
        "items": incidents["items"],
        "security": security,
    }
