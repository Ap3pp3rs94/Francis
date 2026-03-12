from __future__ import annotations

from typing import Any

from services.hud.app.orchestrator_bridge import get_lens_actions
from services.hud.app.state import build_lens_snapshot
from services.hud.app.views.current_work import get_current_work_view


def _int(value: object) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _severity_rank(value: object) -> int:
    normalized = str(value or "").strip().lower()
    if normalized in {"critical", "high"}:
        return 3
    if normalized == "medium":
        return 2
    if normalized == "low":
        return 1
    return 0


def _max_severity(*values: object, fallback: str = "low") -> str:
    highest = str(fallback or "low").strip().lower() or "low"
    for value in values:
        severity = str(value or "").strip().lower()
        if _severity_rank(severity) > _severity_rank(highest):
            highest = severity
    return highest


def _mission_focus(snapshot: dict[str, object]) -> dict[str, Any] | None:
    missions = snapshot.get("missions", {}) if isinstance(snapshot.get("missions"), dict) else {}
    active = missions.get("active", []) if isinstance(missions.get("active"), list) else []
    if active and isinstance(active[0], dict):
        return active[0]
    backlog = missions.get("backlog", []) if isinstance(missions.get("backlog"), list) else []
    if backlog and isinstance(backlog[0], dict):
        return backlog[0]
    current_work = snapshot.get("current_work", {}) if isinstance(snapshot.get("current_work"), dict) else {}
    mission = current_work.get("mission")
    return mission if isinstance(mission, dict) else None


def _trust_posture(snapshot: dict[str, object], handback: dict[str, Any]) -> str:
    fabric_posture = handback.get("fabric_posture", {}) if isinstance(handback.get("fabric_posture"), dict) else {}
    handback_trust = str(fabric_posture.get("trust", "")).strip()
    if handback_trust:
        return handback_trust.title()

    fabric = snapshot.get("fabric", {}) if isinstance(snapshot.get("fabric"), dict) else {}
    calibration = fabric.get("calibration", {}) if isinstance(fabric.get("calibration"), dict) else {}
    confidence_counts = (
        calibration.get("confidence_counts", {}) if isinstance(calibration.get("confidence_counts"), dict) else {}
    )
    if _int(calibration.get("stale_current_state_count")) > 0:
        return "Uncertain"
    if _int(confidence_counts.get("uncertain")) > 0:
        return "Uncertain"
    if _int(confidence_counts.get("likely")) > 0:
        return "Likely"
    if _int(confidence_counts.get("confirmed")) > 0:
        return "Confirmed"
    return "Likely"


def _shift_state(
    *,
    mode: str,
    approvals_pending: int,
    incidents_open: int,
    handback_available: bool,
    last_run_id: str,
) -> str:
    if mode == "away":
        return "away_live"
    if handback_available or approvals_pending > 0 or incidents_open > 0 or last_run_id:
        return "return_briefing"
    return "idle"


def _shift_summary(
    *,
    state: str,
    mission_title: str,
    approvals_pending: int,
    incidents_open: int,
    last_run_id: str,
    next_action_label: str,
    handback: dict[str, Any],
) -> str:
    run_text = last_run_id or "no recent run"
    if state == "away_live":
        return (
            f"Away Mode is active on {mission_title}. "
            f"{approvals_pending} approval(s) are queued, {incidents_open} incident(s) remain open, "
            f"and the latest run is {run_text}."
        ).strip()
    if state == "return_briefing":
        handback_summary = str(handback.get("summary", "")).strip()
        if handback_summary:
            return (
                f"Return briefing for {mission_title}. {handback_summary} "
                f"{approvals_pending} approval(s) are pending, {incidents_open} incident(s) remain open, "
                f"and the next move is {next_action_label or 'still being resolved'}."
            ).strip()
        return (
            f"Return briefing for {mission_title}. Latest run {run_text}. "
            f"{approvals_pending} approval(s) are pending, {incidents_open} incident(s) remain open, "
            f"and the next move is {next_action_label or 'still being resolved'}."
        ).strip()
    return "No away continuity requires review right now."


def _detail_cards(
    *,
    state: str,
    mode: str,
    mission_title: str,
    last_run_id: str,
    approvals_pending: int,
    incidents_open: int,
    trust: str,
) -> list[dict[str, str]]:
    return [
        {"label": "State", "value": state.replace("_", " "), "tone": "medium" if state != "idle" else "low"},
        {"label": "Mode", "value": mode, "tone": "medium" if mode == "away" else "low"},
        {"label": "Mission", "value": mission_title, "tone": "high" if mission_title != "No active mission" else "low"},
        {"label": "Latest Run", "value": last_run_id or "none", "tone": "medium" if last_run_id else "low"},
        {"label": "Approvals", "value": str(approvals_pending), "tone": "high" if approvals_pending else "low"},
        {"label": "Trust", "value": trust, "tone": "high" if trust == "Uncertain" else "medium" if trust == "Likely" else "low"},
    ]


def _evidence_row(*, kind: str, severity: str, detail: str) -> dict[str, str]:
    return {
        "kind": kind,
        "severity": severity,
        "detail": str(detail).strip(),
    }


def _build_evidence(
    *,
    mission_title: str,
    approvals_pending: int,
    incidents: dict[str, Any],
    last_run: dict[str, Any],
    handback: dict[str, Any],
    next_action: dict[str, Any],
    trust: str,
) -> list[dict[str, str]]:
    evidence: list[dict[str, str]] = []
    if mission_title != "No active mission":
        evidence.append(_evidence_row(kind="mission", severity="medium", detail=f"Mission focus is {mission_title}."))

    handback_summary = str(handback.get("summary", "")).strip()
    if handback_summary:
        evidence.append(
            _evidence_row(
                kind="handback",
                severity="high" if trust == "Uncertain" else "medium",
                detail=handback_summary,
            )
        )
    elif str(handback.get("handed_back_at", "")).strip():
        evidence.append(
            _evidence_row(
                kind="handback",
                severity="medium",
                detail=f"Latest handback was recorded at {handback.get('handed_back_at')}.",
            )
        )

    run_id = str(last_run.get("run_id", "")).strip()
    if run_id:
        phase = str(last_run.get("phase", "")).strip()
        summary = str(last_run.get("summary", "")).strip()
        detail = f"Latest run {run_id}"
        if phase:
            detail += f" | {phase}"
        if summary:
            detail += f" | {summary}"
        evidence.append(_evidence_row(kind="run", severity="medium", detail=detail))

    if approvals_pending > 0:
        evidence.append(
            _evidence_row(
                kind="approval",
                severity="high",
                detail=f"{approvals_pending} approval(s) are waiting for operator review.",
            )
        )

    incidents_open = _int(incidents.get("open_count"))
    if incidents_open > 0:
        top_item = incidents.get("items", [{}])[0] if isinstance(incidents.get("items"), list) else {}
        evidence.append(
            _evidence_row(
                kind="incident",
                severity=str(incidents.get("highest_severity", "high")).strip().lower() or "high",
                detail=str(top_item.get("summary", f"{incidents_open} open incident(s) remain.")).strip()
                or f"{incidents_open} open incident(s) remain.",
            )
        )

    next_label = str(next_action.get("label", "")).strip()
    next_reason = str(next_action.get("reason", "")).strip()
    if next_label:
        evidence.append(
            _evidence_row(
                kind="next_move",
                severity="medium" if next_reason else "low",
                detail=f"{next_label}{'' if not next_reason else f' | {next_reason}'}",
            )
        )

    if trust != "Confirmed":
        evidence.append(
            _evidence_row(
                kind="trust",
                severity="high" if trust == "Uncertain" else "medium",
                detail=f"Current continuity posture is {trust}.",
            )
        )
    return evidence[:6]


def _recommendations(
    *,
    state: str,
    approvals_pending: int,
    incidents_open: int,
    trust: str,
    next_action: dict[str, Any],
    handback: dict[str, Any],
) -> list[str]:
    rows: list[str] = []
    if approvals_pending > 0:
        rows.append("Review the pending approvals before resuming execution.")
    if incidents_open > 0:
        rows.append("Inspect the incident posture before advancing the mission further.")
    if str(handback.get("summary", "")).strip():
        rows.append("Read the latest handback summary before treating the shift as complete.")
    next_label = str(next_action.get("label", "")).strip()
    if next_label:
        rows.append(f"Resume with {next_label}.")
    if trust != "Confirmed":
        rows.append("Verify the latest evidence before claiming the work is done.")
    if state == "away_live" and not rows:
        rows.append("Away Mode is live, but there is no immediate operator intervention queued.")
    if not rows:
        rows.append("No shift-report follow-up is required right now.")
    return rows[:4]


def _build_controls(
    *,
    current_work: dict[str, Any],
    approvals_pending: int,
    incidents_open: int,
) -> dict[str, dict[str, Any]]:
    focus_action = current_work.get("focus_action", {}) if isinstance(current_work.get("focus_action"), dict) else {}
    focus_state = str(focus_action.get("state", "")).strip().lower()
    execute_kind = str(focus_action.get("execute_kind", "")).strip() or str(focus_action.get("kind", "")).strip()
    if focus_state == "approval_ready":
        resume_label = "Approve + Run"
    elif focus_state == "approval_request":
        resume_label = "Request Approval"
    elif focus_state == "ready":
        resume_label = "Execute Next Move"
    else:
        resume_label = str(focus_action.get("label", "")).strip() or "Resume Next Move"

    resume_summary = str(focus_action.get("reason", "")).strip() or "No resumable next move is available."
    return {
        "resume": {
            "kind": "shift.resume",
            "label": resume_label,
            "summary": resume_summary,
            "control_type": "execute",
            "enabled": bool(focus_action.get("enabled")) and bool(execute_kind),
            "execute_kind": execute_kind,
            "args": focus_action.get("args", {}) if isinstance(focus_action.get("args"), dict) else {},
        },
        "approvals": {
            "kind": "shift.approvals",
            "label": "Review Approvals",
            "summary": (
                f"{approvals_pending} approval(s) are waiting in the current workspace."
                if approvals_pending > 0
                else "No pending approvals are waiting."
            ),
            "control_type": "surface",
            "enabled": approvals_pending > 0,
            "target_surface": "approval_queue",
        },
        "incidents": {
            "kind": "shift.incidents",
            "label": "Inspect Incidents",
            "summary": (
                f"{incidents_open} incident(s) still require review."
                if incidents_open > 0
                else "No incident follow-up is currently required."
            ),
            "control_type": "surface",
            "enabled": incidents_open > 0,
            "target_surface": "incidents",
        },
        "current_work": {
            "kind": "shift.current_work",
            "label": "Open Current Work",
            "summary": "Jump back to the current work surface and its next move.",
            "control_type": "surface",
            "enabled": True,
            "target_surface": "current_work",
        },
    }


def get_shift_report_view(
    *,
    snapshot: dict[str, object] | None = None,
    actions: dict[str, object] | None = None,
    current_work: dict[str, object] | None = None,
) -> dict[str, object]:
    if snapshot is None:
        snapshot = build_lens_snapshot()
    if actions is None:
        actions = get_lens_actions(max_actions=8)

    control = snapshot.get("control", {}) if isinstance(snapshot.get("control"), dict) else {}
    approvals = snapshot.get("approvals", {}) if isinstance(snapshot.get("approvals"), dict) else {}
    incidents = snapshot.get("incidents", {}) if isinstance(snapshot.get("incidents"), dict) else {}
    runs = snapshot.get("runs", {}) if isinstance(snapshot.get("runs"), dict) else {}
    takeover = snapshot.get("takeover", {}) if isinstance(snapshot.get("takeover"), dict) else {}
    next_action = snapshot.get("next_best_action", {}) if isinstance(snapshot.get("next_best_action"), dict) else {}
    mission = _mission_focus(snapshot)

    mode = str(control.get("mode", "assist")).strip().lower() or "assist"
    mission_title = str((mission or {}).get("title", "")).strip() or "No active mission"
    approvals_pending = _int(approvals.get("pending_count"))
    incidents_open = _int(incidents.get("open_count"))
    last_run = runs.get("last_run", {}) if isinstance(runs.get("last_run"), dict) else {}
    last_run_id = str(last_run.get("run_id", "")).strip()
    handback_available = bool(takeover.get("handback_available"))
    handback = takeover.get("handback", {}) if isinstance(takeover.get("handback"), dict) else {}
    trust = _trust_posture(snapshot, handback)
    if current_work is None:
        current_work = get_current_work_view(snapshot=snapshot, actions=actions)
    state = _shift_state(
        mode=mode,
        approvals_pending=approvals_pending,
        incidents_open=incidents_open,
        handback_available=handback_available,
        last_run_id=last_run_id,
    )
    severity = _max_severity(
        "medium" if mode == "away" else "low",
        "high" if approvals_pending > 0 else "low",
        str(incidents.get("highest_severity", "low")),
        "high" if trust == "Uncertain" else "medium" if trust == "Likely" else "low",
        fallback="low",
    )
    summary = _shift_summary(
        state=state,
        mission_title=mission_title,
        approvals_pending=approvals_pending,
        incidents_open=incidents_open,
        last_run_id=last_run_id,
        next_action_label=str(next_action.get("label", "")).strip(),
        handback=handback,
    )
    evidence = _build_evidence(
        mission_title=mission_title,
        approvals_pending=approvals_pending,
        incidents=incidents,
        last_run=last_run,
        handback=handback,
        next_action=next_action,
        trust=trust,
    )
    recommendations = _recommendations(
        state=state,
        approvals_pending=approvals_pending,
        incidents_open=incidents_open,
        trust=trust,
        next_action=next_action,
        handback=handback,
    )
    controls = _build_controls(
        current_work=current_work,
        approvals_pending=approvals_pending,
        incidents_open=incidents_open,
    )

    return {
        "status": "ok",
        "surface": "shift_report",
        "state": state,
        "summary": summary,
        "severity": severity,
        "cards": _detail_cards(
            state=state,
            mode=mode,
            mission_title=mission_title,
            last_run_id=last_run_id,
            approvals_pending=approvals_pending,
            incidents_open=incidents_open,
            trust=trust,
        ),
        "evidence": evidence,
        "recommendations": recommendations,
        "controls": controls,
        "detail": {
            "state": state,
            "mode": mode,
            "mission": mission,
            "current_work": {
                "focus_action": current_work.get("focus_action", {})
                if isinstance(current_work.get("focus_action"), dict)
                else {},
                "operator_link": current_work.get("operator_link", {})
                if isinstance(current_work.get("operator_link"), dict)
                else {},
            },
            "latest_run": last_run,
            "approvals": {
                "pending_count": approvals_pending,
                "pending": approvals.get("pending", []) if isinstance(approvals.get("pending"), list) else [],
            },
            "incidents": {
                "open_count": incidents_open,
                "highest_severity": str(incidents.get("highest_severity", "nominal")).strip().lower() or "nominal",
                "items": incidents.get("items", []) if isinstance(incidents.get("items"), list) else [],
            },
            "handback": {
                "available": handback_available,
                "summary": str(handback.get("summary", "")).strip(),
                "reason": str(handback.get("reason", "")).strip(),
                "pending_approvals": _int(handback.get("pending_approvals")),
                "run_id": str(handback.get("run_id", "")).strip(),
                "trace_id": str(handback.get("trace_id", "")).strip(),
                "handed_back_at": handback.get("handed_back_at"),
                "trust": trust,
                "fabric_posture": handback.get("fabric_posture", {})
                if isinstance(handback.get("fabric_posture"), dict)
                else {},
            },
            "next_action": next_action,
            "recommendations": recommendations,
        },
    }
