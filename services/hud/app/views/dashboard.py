from __future__ import annotations

from typing import Any

from services.hud.app.state import build_lens_snapshot


def _card(
    *,
    card_id: str,
    title: str,
    tone: str,
    signal: str,
    summary: str,
    evidence: list[str],
    detail: dict[str, Any],
) -> dict[str, Any]:
    compact_summary = str(summary).strip() or f"{title} is available."
    return {
        "id": card_id,
        "title": title,
        "tone": tone,
        "signal": signal,
        "summary": compact_summary,
        "body": compact_summary,
        "evidence": [str(item).strip() for item in evidence if str(item).strip()][:4],
        "detail": detail,
    }


def get_dashboard_view(*, snapshot: dict[str, object] | None = None) -> dict[str, object]:
    if snapshot is None:
        snapshot = build_lens_snapshot()
    control = snapshot["control"]
    missions = snapshot["missions"]
    approvals = snapshot["approvals"]
    incidents = snapshot["incidents"]
    security = snapshot.get("security", {})
    runs = snapshot["runs"]
    apprenticeship = snapshot.get("apprenticeship", {})
    fabric = snapshot.get("fabric", {})
    current_work = snapshot.get("current_work", {}) if isinstance(snapshot.get("current_work"), dict) else {}
    next_best_action = (
        snapshot.get("next_best_action", {}) if isinstance(snapshot.get("next_best_action"), dict) else {}
    )
    fabric_calibration = fabric.get("calibration", {}) if isinstance(fabric.get("calibration"), dict) else {}
    fabric_confidence = (
        fabric_calibration.get("confidence_counts", {})
        if isinstance(fabric_calibration.get("confidence_counts"), dict)
        else {}
    )
    next_action_signal = (
        current_work.get("next_action_signal", {})
        if isinstance(current_work.get("next_action_signal"), dict)
        else {}
    )
    attention = current_work.get("attention", {}) if isinstance(current_work.get("attention"), dict) else {}
    repo = current_work.get("repo", {}) if isinstance(current_work.get("repo"), dict) else {}
    terminal_summary = str(current_work.get("terminal_summary", "")).strip()
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
    mission_signal = "high" if int(missions["active_count"]) > 0 else "low"
    governance_signal = (
        "high"
        if bool(control.get("kill_switch")) or int(approvals["pending_count"]) > 0
        else "medium"
        if int(apprenticeship.get("review_count", 0)) > 0
        else "low"
    )
    receipts_signal = (
        "high"
        if int(incidents["open_count"]) > 0 or int(security.get("quarantine_count", 0)) > 0
        else "medium"
        if int(runs["ledger_count"]) > 0
        else "low"
    )
    current_work_signal = (
        str(repo.get("severity", "")).strip().lower()
        or str(next_action_signal.get("severity", "")).strip().lower()
        or "low"
    )
    next_action_signal_value = (
        str(next_action_signal.get("severity", "")).strip().lower()
        or str(next_best_action.get("risk_tier", "")).strip().lower()
        or "low"
    )
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
            _card(
                card_id="mission-pressure",
                title="Mission Pressure",
                tone="primary",
                signal=mission_signal,
                summary=(
                    f"{missions['active_count']} active mission(s), "
                    f"{missions['backlog_count']} backlog, "
                    f"{missions['completed_count']} completed."
                ),
                evidence=[
                    f"Objective: {str(snapshot['objective'].get('label', 'No objective selected.')).strip()}",
                    f"Active missions: {int(missions['active_count'])}",
                    f"Backlog missions: {int(missions['backlog_count'])}",
                ],
                detail={
                    "objective": snapshot["objective"],
                    "missions": missions,
                },
            ),
            _card(
                card_id="governance",
                title="Governance",
                tone="neutral",
                signal=governance_signal,
                summary=(
                    f"Mode {control['mode']}. "
                    f"Kill switch {'active' if control.get('kill_switch') else 'clear'}. "
                    f"{approvals['pending_count']} pending approval(s)."
                ),
                evidence=[
                    f"Teaching reviews: {int(apprenticeship.get('review_count', 0))}",
                    f"Approvals pending: {int(approvals['pending_count'])}",
                    f"Visible mode: {control['mode']}",
                ],
                detail={
                    "control": control,
                    "approvals": approvals,
                    "apprenticeship": apprenticeship,
                },
            ),
            _card(
                card_id="receipts",
                title="Receipts",
                tone="accent",
                signal=receipts_signal,
                summary=(
                    f"{runs['ledger_count']} ledger event(s) tracked. "
                    f"{incidents['open_count']} open incident(s). "
                    f"Highest severity: {incidents['highest_severity']}."
                ),
                evidence=[
                    security_line,
                    f"Fabric citations ready: {int(fabric.get('citation_ready_count', 0))}",
                    (
                        f"Trust state: {int(fabric_confidence.get('confirmed', 0))} confirmed, "
                        f"{int(fabric_confidence.get('likely', 0))} likely, "
                        f"{int(fabric_confidence.get('uncertain', 0))} uncertain."
                    ),
                ],
                detail={
                    "runs": runs,
                    "incidents": incidents,
                    "security": security,
                    "fabric": fabric,
                },
            ),
            _card(
                card_id="current-work",
                title="Current Work",
                tone="primary",
                signal=current_work_signal,
                summary=str(current_work.get("summary", "Current work context is not available.")),
                evidence=[
                    f"Attention: {str(attention.get('label', 'Stable')).strip() or 'Stable'}",
                    terminal_summary or "Terminal anchor unavailable.",
                    f"Repo: {str(repo.get('branch', 'unknown')).strip() or 'unknown'} | {'dirty' if bool(repo.get('dirty', False)) else 'clean'}",
                ],
                detail={
                    "attention": attention,
                    "repo": repo,
                    "terminal_summary": terminal_summary,
                    "current_work": current_work,
                },
            ),
            _card(
                card_id="next-best-action",
                title="Next Best Action",
                tone="neutral",
                signal=next_action_signal_value,
                summary=(
                    f"{str(next_best_action.get('label', 'No next action selected.')).strip()} | "
                    f"{str(next_best_action.get('reason', 'No usage guidance is available.')).strip()}"
                ),
                evidence=[
                    f"Signal severity: {str(next_action_signal.get('severity', next_action_signal_value)).strip() or next_action_signal_value}",
                    str(next_action_signal.get("reason", "")).strip() or "No signal reason is available.",
                    f"Trust badge: {str(next_best_action.get('trust_badge', 'Likely')).strip() or 'Likely'}",
                ],
                detail={
                    "next_best_action": next_best_action,
                    "next_action_signal": next_action_signal,
                    "current_work": current_work,
                },
            ),
        ],
    }
