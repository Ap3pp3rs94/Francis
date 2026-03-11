from __future__ import annotations

from typing import Any

from services.hud.app.state import build_lens_snapshot


def _normalize_usage_action_kind(value: object) -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        return ""
    suffix = ".request_approval"
    return raw[: -len(suffix)] if raw.endswith(suffix) else raw


def _summary_text(summary: Any) -> str:
    if isinstance(summary, str):
        return summary.strip()
    if isinstance(summary, dict):
        if str(summary.get("skill", "")).strip():
            skill = str(summary.get("skill", "")).strip()
            ok = summary.get("ok")
            suffix = ""
            if ok is not None:
                suffix = " ok" if bool(ok) else " failed"
            return f"{skill}{suffix}".strip()
        if str(summary.get("action_kind", "")).strip():
            kind = str(summary.get("action_kind", "")).strip()
            ok = summary.get("ok")
            suffix = ""
            if ok is not None:
                suffix = " ok" if bool(ok) else " failed"
            return f"{kind}{suffix}".strip()
        if str(summary.get("decision", "")).strip():
            return (
                f"approval {str(summary.get('decision', '')).strip()} "
                f"{str(summary.get('approval_id', '')).strip()}".strip()
            )
    return ""


def _action_kind(summary: Any, row: dict[str, Any]) -> str:
    detail = row.get("detail", {}) if isinstance(row.get("detail"), dict) else {}
    candidates = [
        row.get("action_kind"),
        detail.get("action_kind"),
        summary.get("action_kind") if isinstance(summary, dict) else None,
        detail.get("skill"),
        summary.get("skill") if isinstance(summary, dict) else None,
    ]
    for value in candidates:
        text = str(value or "").strip().lower()
        if text:
            return text
    return ""


def _approval_id(summary: Any, row: dict[str, Any]) -> str:
    detail = row.get("detail", {}) if isinstance(row.get("detail"), dict) else {}
    candidates = [
        row.get("approval_id"),
        detail.get("approval_id"),
        summary.get("approval_id") if isinstance(summary, dict) else None,
    ]
    for value in candidates:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _decision(summary: Any, row: dict[str, Any]) -> str:
    detail = row.get("detail", {}) if isinstance(row.get("detail"), dict) else {}
    candidates = [
        row.get("decision"),
        detail.get("decision"),
        summary.get("decision") if isinstance(summary, dict) else None,
    ]
    for value in candidates:
        text = str(value or "").strip().lower()
        if text:
            return text
    return ""


def _title_for_kind(kind: str) -> str:
    return {
        "tool.run": "Tool Run",
        "lens.action.execute": "Lens Action",
        "approval.decided": "Approval Decision",
        "approval.requested": "Approval Requested",
        "mission.tick": "Mission Tick",
    }.get(kind, kind.replace(".", " ").title())


def _focus_action_kind(snapshot: dict[str, object]) -> str:
    next_action = snapshot.get("next_best_action", {}) if isinstance(snapshot.get("next_best_action"), dict) else {}
    return _normalize_usage_action_kind(next_action.get("kind"))


def _detail_summary(
    *,
    title: str,
    action_kind: str,
    approval_id: str,
    decision: str,
    summary_text: str,
) -> str:
    compact = summary_text.strip() or "Receipt recorded."
    if decision and approval_id:
        return f"Approval {decision} for {approval_id}. {compact}".strip()
    if action_kind:
        return f"{title} for {action_kind}. {compact}".strip()
    return f"{title}. {compact}".strip()


def _detail_state_hint(*, action_kind: str, focus_action_kind: str) -> str:
    normalized_action = _normalize_usage_action_kind(action_kind)
    normalized_focus = _normalize_usage_action_kind(focus_action_kind)
    if normalized_action and normalized_focus and normalized_action == normalized_focus:
        return "current"
    return "historical"


def _detail_cards(
    *,
    kind: str,
    title: str,
    action_kind: str,
    approval_id: str,
    decision: str,
    run_id: str,
) -> list[dict[str, str]]:
    cards = [
        {"label": "Kind", "value": kind, "tone": "low"},
        {"label": "Run", "value": run_id or "none", "tone": "medium" if run_id else "low"},
    ]
    if action_kind:
        cards.append({"label": "Action", "value": action_kind, "tone": "medium"})
    else:
        cards.append({"label": "Title", "value": title, "tone": "low"})
    if approval_id:
        cards.append({"label": "Approval", "value": approval_id, "tone": "medium"})
    if decision:
        cards.append({"label": "Decision", "value": decision, "tone": "high" if decision == "rejected" else "low"})
    return cards


def get_execution_journal_view(*, snapshot: dict[str, object] | None = None) -> dict[str, object]:
    if snapshot is None:
        snapshot = build_lens_snapshot()

    runs = snapshot.get("runs", {}) if isinstance(snapshot.get("runs"), dict) else {}
    ledger_tail = runs.get("ledger_tail", []) if isinstance(runs.get("ledger_tail"), list) else []
    recent_runs = runs.get("recent", []) if isinstance(runs.get("recent"), list) else []
    last_run = runs.get("last_run", {}) if isinstance(runs.get("last_run"), dict) else {}
    focus_action_kind = _focus_action_kind(snapshot)

    items: list[dict[str, Any]] = []
    for row in reversed(ledger_tail):
        if not isinstance(row, dict):
            continue
        kind = str(row.get("kind", "")).strip() or "unknown"
        summary = row.get("summary")
        summary_text = _summary_text(summary)
        action_kind = _action_kind(summary, row)
        approval_id = _approval_id(summary, row)
        decision = _decision(summary, row)
        title = _title_for_kind(kind)
        items.append(
            {
                "run_id": str(row.get("run_id", "")).strip(),
                "ts": row.get("ts"),
                "kind": kind,
                "action_kind": action_kind,
                "approval_id": approval_id,
                "decision": decision,
                "title": title,
                "summary": summary_text or "Receipt captured with no compact summary.",
                "detail_summary": _detail_summary(
                    title=title,
                    action_kind=action_kind,
                    approval_id=approval_id,
                    decision=decision,
                    summary_text=summary_text or "Receipt recorded.",
                ),
                "detail_cards": _detail_cards(
                    kind=kind,
                    title=title,
                    action_kind=action_kind,
                    approval_id=approval_id,
                    decision=decision,
                    run_id=str(row.get("run_id", "")).strip(),
                ),
                "detail_state": _detail_state_hint(
                    action_kind=action_kind,
                    focus_action_kind=focus_action_kind,
                ),
                "detail": row,
            }
        )

    run_groups: list[dict[str, Any]] = []
    for row in recent_runs:
        if not isinstance(row, dict):
            continue
        run_groups.append(
            {
                "run_id": str(row.get("run_id", "")).strip(),
                "event_count": int(row.get("event_count", 0)),
                "last_kind": str(row.get("last_kind", "")).strip(),
                "last_ts": row.get("last_ts"),
            }
        )

    return {
        "status": "ok",
        "surface": "execution_journal",
        "active_run": {
            "run_id": str(last_run.get("run_id", "")).strip() or "none",
            "phase": str(last_run.get("phase", "unknown")).strip() or "unknown",
            "summary": str(last_run.get("summary", "")).strip() or "No active run recorded.",
        },
        "items": items,
        "run_groups": run_groups,
    }
