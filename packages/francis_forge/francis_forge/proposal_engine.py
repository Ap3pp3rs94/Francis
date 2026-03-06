from __future__ import annotations

from typing import Any


def propose(context: dict[str, Any]) -> list[dict[str, Any]]:
    deadletter_count = int(context.get("deadletter_count", 0))
    open_incidents = int(context.get("open_incident_count", 0))
    active_missions = int(context.get("active_mission_count", 0))

    proposals: list[dict[str, Any]] = []

    if deadletter_count > 0:
        proposals.append(
            {
                "name": "Deadletter Triager",
                "description": "Automatically classify and summarize deadletter mission jobs.",
                "rationale": f"Detected {deadletter_count} deadletter jobs.",
                "tags": ["ops", "queue", "reliability"],
                "risk_tier": "medium",
                "source": "queue.deadletter",
            }
        )

    if open_incidents > 0:
        proposals.append(
            {
                "name": "Incident Digest Generator",
                "description": "Generate concise incident digests from open anomaly evidence.",
                "rationale": f"Detected {open_incidents} open incidents.",
                "tags": ["observer", "incident", "reporting"],
                "risk_tier": "low",
                "source": "incidents.open",
            }
        )

    if active_missions >= 3:
        proposals.append(
            {
                "name": "Mission Batch Planner",
                "description": "Group active missions into batched execution windows.",
                "rationale": f"Detected {active_missions} active missions.",
                "tags": ["missions", "planning", "productivity"],
                "risk_tier": "medium",
                "source": "missions.active",
            }
        )

    if not proposals:
        proposals.append(
            {
                "name": "Workspace Signal Scanner",
                "description": "Scan workspace journals and produce a daily signal summary.",
                "rationale": "No pressing friction detected; propose a general utility capability.",
                "tags": ["workspace", "signals"],
                "risk_tier": "low",
                "source": "baseline",
            }
        )

    return proposals
