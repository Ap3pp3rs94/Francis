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


def detect_presence_triggers(
    *,
    previous: Mapping[str, Any] | None,
    current: Mapping[str, Any],
) -> list[dict[str, Any]]:
    prior = previous if isinstance(previous, Mapping) else {}
    triggers: list[dict[str, Any]] = []

    previous_kill_switch = bool(_section(prior, "control").get("kill_switch"))
    current_kill_switch = bool(_section(current, "control").get("kill_switch"))
    if current_kill_switch and not previous_kill_switch:
        triggers.append(
            {
                "kind": "control.kill_switch.engaged",
                "severity": "critical",
                "trust": "Confirmed",
                "summary": "Kill switch engaged; mutating actions are blocked.",
            }
        )

    previous_incidents = _count(prior, "incidents", "open_count")
    current_incidents = _count(current, "incidents", "open_count")
    if current_incidents > previous_incidents:
        triggers.append(
            {
                "kind": "incident.pressure.increased",
                "severity": str(_section(current, "incidents").get("highest_severity", "high")).strip() or "high",
                "trust": "Confirmed",
                "summary": f"Open incidents increased from {previous_incidents} to {current_incidents}.",
            }
        )

    previous_approvals = _count(prior, "approvals", "pending_count")
    current_approvals = _count(current, "approvals", "pending_count")
    if current_approvals > previous_approvals:
        triggers.append(
            {
                "kind": "approvals.pending.increased",
                "severity": "medium",
                "trust": "Confirmed",
                "summary": f"Pending approvals increased from {previous_approvals} to {current_approvals}.",
            }
        )

    previous_alerts = _count(prior, "inbox", "alert_count")
    current_alerts = _count(current, "inbox", "alert_count")
    if current_alerts > previous_alerts:
        triggers.append(
            {
                "kind": "inbox.alerts.increased",
                "severity": "high",
                "trust": "Confirmed",
                "summary": f"Inbox alerts increased from {previous_alerts} to {current_alerts}.",
            }
        )

    previous_missions = _count(prior, "missions", "active_count")
    current_missions = _count(current, "missions", "active_count")
    if current_missions > previous_missions:
        triggers.append(
            {
                "kind": "missions.active.increased",
                "severity": "info",
                "trust": "Confirmed",
                "summary": f"Active missions increased from {previous_missions} to {current_missions}.",
            }
        )

    return triggers
