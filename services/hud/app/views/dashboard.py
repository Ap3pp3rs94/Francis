from __future__ import annotations

from services.hud.app.state import build_lens_snapshot


def get_dashboard_view() -> dict[str, object]:
    snapshot = build_lens_snapshot()
    control = snapshot["control"]
    missions = snapshot["missions"]
    approvals = snapshot["approvals"]
    incidents = snapshot["incidents"]
    security = snapshot.get("security", {})
    runs = snapshot["runs"]
    apprenticeship = snapshot.get("apprenticeship", {})
    fabric = snapshot.get("fabric", {})
    fabric_calibration = fabric.get("calibration", {}) if isinstance(fabric.get("calibration"), dict) else {}
    fabric_confidence = (
        fabric_calibration.get("confidence_counts", {})
        if isinstance(fabric_calibration.get("confidence_counts"), dict)
        else {}
    )
    top_security_categories = (
        security.get("top_categories", {})
        if isinstance(security.get("top_categories"), dict)
        else {}
    )
    lead_security_category = next(iter(top_security_categories.items()), None)
    if int(security.get("quarantine_count", 0)) > 0:
        security_line = (
            f"Security quarantine: {int(security.get('quarantine_count', 0))} event(s), "
            f"severity {security.get('highest_severity', 'medium')}."
        )
        if lead_security_category is not None:
            security_line += f" Top category: {lead_security_category[0]} ({int(lead_security_category[1])})."
    else:
        security_line = "Security quarantine: none."
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
                    f"{security_line} "
                    f"Fabric citations ready: {int(fabric.get('citation_ready_count', 0))}. "
                    f"Trust state: {int(fabric_confidence.get('confirmed', 0))} confirmed, "
                    f"{int(fabric_confidence.get('likely', 0))} likely, "
                    f"{int(fabric_confidence.get('uncertain', 0))} uncertain."
                ),
            },
        ],
    }
