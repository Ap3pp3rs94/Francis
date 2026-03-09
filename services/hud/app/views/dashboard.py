from __future__ import annotations

from services.hud.app.state import build_lens_snapshot


def get_dashboard_view() -> dict[str, object]:
    snapshot = build_lens_snapshot()
    control = snapshot["control"]
    missions = snapshot["missions"]
    approvals = snapshot["approvals"]
    incidents = snapshot["incidents"]
    runs = snapshot["runs"]
    apprenticeship = snapshot.get("apprenticeship", {})
    fabric = snapshot.get("fabric", {})
    return {
        "status": "ok",
        "surface": "dashboard",
        "mode": {
            "current": control["mode"],
            "visible": True,
            "available": ["observe", "assist", "pilot", "away"],
            "kill_switch": bool(control.get("kill_switch", False)),
        },
        "objective": snapshot["objective"],
        "cards": [
            {
                "id": "mission-pressure",
                "title": "Mission Pressure",
                "tone": "primary",
                "body": (
                    f"{missions['active_count']} active mission(s), "
                    f"{missions['backlog_count']} backlog, "
                    f"{missions['completed_count']} completed."
                ),
            },
            {
                "id": "governance",
                "title": "Governance",
                "tone": "neutral",
                "body": (
                    f"Mode {control['mode']}. "
                    f"Kill switch {'active' if control.get('kill_switch') else 'clear'}. "
                    f"{approvals['pending_count']} pending approval(s). "
                    f"{int(apprenticeship.get('review_count', 0))} teaching session(s) ready for review."
                ),
            },
            {
                "id": "receipts",
                "title": "Receipts",
                "tone": "accent",
                "body": (
                    f"{runs['ledger_count']} ledger event(s) tracked. "
                    f"{incidents['open_count']} open incident(s). "
                    f"Highest severity: {incidents['highest_severity']}. "
                    f"Fabric citations ready: {int(fabric.get('citation_ready_count', 0))}."
                ),
            },
        ],
    }
