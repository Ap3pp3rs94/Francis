from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def _section(snapshot: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = snapshot.get(key, {})
    return value if isinstance(value, Mapping) else {}


def _count(snapshot: Mapping[str, Any], section_name: str, field: str) -> int:
    section = _section(snapshot, section_name)
    try:
        return int(section.get(field, 0))
    except (TypeError, ValueError):
        return 0


def build_notification_digest(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    control = _section(snapshot, "control")
    incidents = _section(snapshot, "incidents")
    objective = _section(snapshot, "objective")

    objective_label = str(objective.get("label", "the current objective")).strip() or "the current objective"
    incident_count = _count(snapshot, "incidents", "open_count")
    approval_count = _count(snapshot, "approvals", "pending_count")
    mission_count = _count(snapshot, "missions", "active_count")

    if bool(control.get("kill_switch")):
        return {
            "kind": "control.kill_switch",
            "severity": "critical",
            "title": "Kill switch engaged",
            "body": "Mutating actions are paused until control is explicitly resumed.",
            "action_hint": "Review the operator deck before resuming execution.",
        }
    if incident_count > 0:
        highest = str(incidents.get("highest_severity", "unknown")).strip() or "unknown"
        return {
            "kind": "incident.pressure",
            "severity": highest,
            "title": f"{incident_count} incident(s) require attention",
            "body": f"Highest severity is {highest}. Keep {objective_label} bounded until containment is verified.",
            "action_hint": "Run the observer scan and review incident receipts first.",
        }
    if approval_count > 0:
        return {
            "kind": "approval.queue",
            "severity": "medium",
            "title": f"{approval_count} approval(s) are waiting",
            "body": f"Governed work on {objective_label} is waiting on explicit approval.",
            "action_hint": "Review pending approvals before opening new work.",
        }
    if mission_count > 0:
        return {
            "kind": "mission.focus",
            "severity": "info",
            "title": "Mission focus is active",
            "body": f"{mission_count} active mission(s) are carrying {objective_label}.",
            "action_hint": "Advance the primary mission before spawning new threads.",
        }
    return {
        "kind": "system.stable",
        "severity": "info",
        "title": "System state is stable",
        "body": "No incidents, approval queues, or kill-switch pressure are forcing a change in posture.",
        "action_hint": "Continue the current objective or stage the next high-leverage action.",
    }
