from __future__ import annotations

import json
from typing import Any

from francis_core.workspace_fs import WorkspaceFS


def _read_json(fs: WorkspaceFS, rel_path: str, default: object) -> object:
    try:
        raw = fs.read_text(rel_path)
    except Exception:
        return default
    try:
        return json.loads(raw)
    except Exception:
        return default


def collect_intents(fs: WorkspaceFS) -> dict[str, Any]:
    missions_doc = _read_json(fs, "missions/missions.json", {"missions": []})
    missions = missions_doc.get("missions", []) if isinstance(missions_doc, dict) else []
    inactive = {"completed", "failed", "cancelled", "canceled"}

    intents: list[dict[str, Any]] = []
    for mission in missions:
        if not isinstance(mission, dict):
            continue
        status = str(mission.get("status", "")).lower()
        if status in inactive:
            continue
        intents.append(
            {
                "type": "mission",
                "mission_id": mission.get("id"),
                "title": mission.get("title", ""),
                "priority": mission.get("priority", "normal"),
                "status": mission.get("status", ""),
                "next_step_index": mission.get("next_step_index", 0),
            }
        )

    return {"intents": intents, "intent_count": len(intents)}

