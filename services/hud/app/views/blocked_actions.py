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
        items.append(item)

    summary = (
        f"{len(items)} blocked action(s) are active."
        if items
        else "No blocked actions are currently surfaced by Lens."
    )

    return {
        "status": "ok",
        "surface": "blocked_actions",
        "count": len(items),
        "summary": summary,
        "items": items,
        "detail": {
            "focus_action_kind": focus_kind,
            "items": items,
        },
    }
