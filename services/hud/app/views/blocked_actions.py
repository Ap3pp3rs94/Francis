from __future__ import annotations

from typing import Any

from services.hud.app.orchestrator_bridge import get_lens_actions
from services.hud.app.state import build_lens_snapshot


def _detail_summary(row: dict[str, Any]) -> str:
    kind = str(row.get("kind", "blocked action")).strip() or "blocked action"
    reason = str(row.get("policy_reason") or row.get("reason") or "No policy reason provided.").strip()
    return f"{kind} is blocked. {reason}".strip()


def _detail_cards(row: dict[str, Any]) -> list[dict[str, str]]:
    risk = str(row.get("risk_tier", "low")).strip().lower() or "low"
    trust = str(row.get("trust_badge", "Blocked")).strip() or "Blocked"
    return [
        {"label": "Action", "value": str(row.get("kind", "unknown")).strip() or "unknown", "tone": risk},
        {"label": "Risk", "value": risk, "tone": risk},
        {"label": "Trust", "value": trust, "tone": "medium" if trust.lower() != "blocked" else "high"},
    ]


def _audit(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": str(row.get("kind", "unknown")).strip() or "unknown",
        "policy_reason": str(row.get("policy_reason") or row.get("reason") or "").strip(),
        "risk_tier": str(row.get("risk_tier", "low")).strip().lower() or "low",
        "trust_badge": str(row.get("trust_badge", "Blocked")).strip() or "Blocked",
        "detail_state": str(row.get("detail_state", "historical")).strip(),
    }


def get_blocked_actions_view(
    *,
    snapshot: dict[str, object] | None = None,
    actions: dict[str, object] | None = None,
) -> dict[str, object]:
    if snapshot is None:
        snapshot = build_lens_snapshot()
    if actions is None:
        actions = get_lens_actions(max_actions=8)

    blocked = actions.get("blocked_actions", []) if isinstance(actions.get("blocked_actions"), list) else []
    focus = snapshot.get("next_best_action", {}) if isinstance(snapshot.get("next_best_action"), dict) else {}
    focus_kind = str(focus.get("kind", "")).strip().lower()

    items: list[dict[str, Any]] = []
    for row in blocked:
        if not isinstance(row, dict):
            continue
        item = dict(row)
        item["detail_summary"] = _detail_summary(item)
        item["detail_cards"] = _detail_cards(item)
        item["detail_state"] = "current" if str(item.get("kind", "")).strip().lower() == focus_kind else "historical"
        item["audit"] = _audit(item)
        items.append(item)

    focus_item = next((row for row in items if str(row.get("detail_state", "")).strip() == "current"), None)
    if focus_item is None and items:
        focus_item = items[0]

    summary = (
        f"{len(items)} blocked action(s) are active."
        if items
        else "No blocked actions are currently surfaced by Lens."
    )

    return {
        "status": "ok",
        "surface": "blocked_actions",
        "count": len(items),
        "focus_blocked_kind": str(focus_item.get("kind", "")).strip() if isinstance(focus_item, dict) else "",
        "summary": summary,
        "items": items,
        "detail": {
            "focus_action_kind": focus_kind,
            "focus_blocked_kind": str(focus_item.get("kind", "")).strip() if isinstance(focus_item, dict) else "",
            "items": items,
        },
    }
