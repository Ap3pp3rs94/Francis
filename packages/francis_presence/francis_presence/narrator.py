from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from francis_brain.calibration import summarize_fabric_posture

from .notifications import build_notification_digest
from .tone import MODE_OPENERS, normalize_mode
from .triggers import detect_presence_triggers


def _section(snapshot: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = snapshot.get(key, {})
    return value if isinstance(value, Mapping) else {}


def _count(snapshot: Mapping[str, Any], section_name: str, field: str) -> int:
    section = _section(snapshot, section_name)
    try:
        return int(section.get(field, 0))
    except (TypeError, ValueError):
        return 0


def _fabric_trust(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    return summarize_fabric_posture(_section(snapshot, "fabric"))


def _takeover(snapshot: Mapping[str, Any]) -> Mapping[str, Any]:
    return _section(snapshot, "takeover")


def _handback(snapshot: Mapping[str, Any]) -> Mapping[str, Any]:
    return _section(_takeover(snapshot), "handback")


def build_presence_headline(snapshot: Mapping[str, Any]) -> str:
    control = _section(snapshot, "control")
    incidents = _section(snapshot, "incidents")
    objective = _section(snapshot, "objective")
    takeover = _takeover(snapshot)

    mode = str(control.get("mode", "pilot")).strip().lower() or "pilot"
    objective_label = str(objective.get("label", "Systematically build Francis")).strip() or "Systematically build Francis"

    if bool(control.get("kill_switch")):
        return f"Kill switch is active. {objective_label} is paused in {mode} mode."
    if _count(snapshot, "incidents", "open_count") > 0:
        highest = str(incidents.get("highest_severity", "unknown")).strip() or "unknown"
        return f"Incident pressure is {highest}. {objective_label} remains the current objective."
    if _count(snapshot, "approvals", "pending_count") > 0:
        pending = _count(snapshot, "approvals", "pending_count")
        noun = "approval" if pending == 1 else "approvals"
        return f"{pending} pending {noun} are waiting on the current objective: {objective_label}."
    if bool(takeover.get("handback_available")):
        return f"Handback is complete. {objective_label} has returned to ambient control."
    if _count(snapshot, "missions", "active_count") > 0:
        return f"Mission focus is active: {objective_label}."
    return f"System state is stable. Current objective: {objective_label}."


def build_presence_lines(
    snapshot: Mapping[str, Any],
    actions: Sequence[Mapping[str, Any]],
    *,
    mode: str,
) -> list[str]:
    normalized_mode = normalize_mode(mode)
    control = _section(snapshot, "control")
    incidents = _section(snapshot, "incidents")
    missions = _section(snapshot, "missions")
    runs = _section(snapshot, "runs")
    takeover = _takeover(snapshot)
    handback = _handback(snapshot)
    fabric_trust = _fabric_trust(snapshot)

    active_mission = missions.get("active", [])
    top_mission = active_mission[0] if isinstance(active_mission, list) and active_mission else {}
    top_mission = top_mission if isinstance(top_mission, Mapping) else {}
    last_run = runs.get("last_run", {})
    last_run = last_run if isinstance(last_run, Mapping) else {}

    lines = [
        f"Control mode is {str(control.get('mode', normalized_mode)).strip().lower()} with kill switch "
        f"{'engaged' if bool(control.get('kill_switch')) else 'disengaged'}.",
        f"Incidents: {_count(snapshot, 'incidents', 'open_count')} open, highest severity "
        f"{str(incidents.get('highest_severity', 'nominal')).strip() or 'nominal'}.",
        f"Approvals: {_count(snapshot, 'approvals', 'pending_count')} pending. "
        f"Inbox alerts: {_count(snapshot, 'inbox', 'alert_count')}.",
    ]
    if top_mission:
        title = str(top_mission.get("title", "Untitled mission")).strip() or "Untitled mission"
        status = str(top_mission.get("status", "active")).strip().lower() or "active"
        lines.append(f"Primary mission is {title} with status {status}.")
    summary = str(last_run.get("summary", "")).strip()
    if summary:
        lines.append(f"Latest recorded run: {summary}")
    if bool(takeover.get("handback_available")):
        handed_back_at = str(handback.get("handed_back_at", "")).strip()
        handback_run_id = str(handback.get("run_id", "")).strip()
        handback_summary = str(handback.get("summary", "")).strip()
        handback_pending_approvals = _count({"handback": handback}, "handback", "pending_approvals")
        handback_fabric_posture = _section(handback, "fabric_posture")
        handback_trust = (
            str(handback_fabric_posture.get("trust", "")).strip() or str(fabric_trust["trust"]).strip()
        )
        if handed_back_at:
            returned = f"Last handback returned authority at {handed_back_at}"
            if handback_run_id:
                returned += f" via run {handback_run_id}"
            lines.append(f"{returned}.")
        if handback_summary:
            lines.append(f"Handback summary: {handback_summary}")
        lines.append(
            f"Handback trust is {handback_trust.lower()} with {handback_pending_approvals} pending approval"
            f"{'' if handback_pending_approvals == 1 else 's'}."
        )
    lines.append(
        "Fabric trust is "
        f"{str(fabric_trust['trust']).lower()} with "
        f"{fabric_trust['confirmed_count']} confirmed, "
        f"{fabric_trust['likely_count']} likely, and "
        f"{fabric_trust['uncertain_count']} uncertain artifacts."
    )
    if fabric_trust["warning"]:
        lines.append(str(fabric_trust["warning"]))
    action_labels = ", ".join(str(action.get("label", "")).strip() for action in actions[:3] if action.get("label"))
    if action_labels:
        lines.append(f"Recommended next actions: {action_labels}.")
    lines.append("Claims remain tied to visible receipts and current scope.")
    return lines


def build_presence_grounding(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    fabric_trust = _fabric_trust(snapshot)
    takeover = _takeover(snapshot)
    handback = _handback(snapshot)
    handback_fabric_posture = _section(handback, "fabric_posture")
    return {
        "trust": fabric_trust["trust"],
        "workspace_root": snapshot.get("workspace_root"),
        "objective": dict(_section(snapshot, "objective")),
        "incident_count": _count(snapshot, "incidents", "open_count"),
        "pending_approvals": _count(snapshot, "approvals", "pending_count"),
        "active_missions": _count(snapshot, "missions", "active_count"),
        "fabric": fabric_trust,
        "handback": {
            "available": bool(takeover.get("handback_available")),
            "handed_back_at": handback.get("handed_back_at"),
            "summary": str(handback.get("summary", "")).strip() or None,
            "pending_approvals": _count({"handback": handback}, "handback", "pending_approvals"),
            "run_id": str(handback.get("run_id", "")).strip() or None,
            "trace_id": str(handback.get("trace_id", "")).strip() or None,
            "trust": str(handback_fabric_posture.get("trust", "")).strip() or fabric_trust["trust"],
        },
    }


def compose_operator_presence(
    *,
    mode: str,
    snapshot: Mapping[str, Any],
    actions: Sequence[Mapping[str, Any]],
    surface: str = "voice",
    receipt_mode: str = "explicit",
) -> dict[str, Any]:
    normalized_mode = normalize_mode(mode)
    headline = build_presence_headline(snapshot)
    lines = build_presence_lines(snapshot, actions, mode=normalized_mode)
    body = " ".join([MODE_OPENERS[normalized_mode], headline, *lines])

    return {
        "surface": surface,
        "mode": normalized_mode,
        "headline": headline,
        "body": body,
        "lines": lines,
        "grounding": build_presence_grounding(snapshot),
        "actions": [dict(action) for action in actions],
        "notification": build_notification_digest(snapshot),
        "triggers": detect_presence_triggers(previous=None, current=snapshot),
        "receipt_mode": receipt_mode,
    }
