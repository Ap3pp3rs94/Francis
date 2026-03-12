from __future__ import annotations

from typing import Any

from services.hud.app.orchestrator_bridge import get_lens_actions
from services.hud.app.state import build_lens_snapshot


def _normalize_usage_action_kind(value: object) -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        return ""
    suffix = ".request_approval"
    return raw[: -len(suffix)] if raw.endswith(suffix) else raw


def _chip_args(chip: dict[str, Any]) -> dict[str, object]:
    execute_via = chip.get("execute_via", {}) if isinstance(chip.get("execute_via"), dict) else {}
    payload = execute_via.get("payload", {}) if isinstance(execute_via.get("payload"), dict) else {}
    if isinstance(payload.get("args"), dict):
        return dict(payload.get("args", {}))
    if isinstance(chip.get("args"), dict):
        return dict(chip.get("args", {}))
    return {}


def _focus_action_kind(snapshot: dict[str, object]) -> str:
    current_work = snapshot.get("current_work", {}) if isinstance(snapshot.get("current_work"), dict) else {}
    focus_action = current_work.get("focus_action", {}) if isinstance(current_work.get("focus_action"), dict) else {}
    focus_kind = _normalize_usage_action_kind(focus_action.get("kind"))
    if focus_kind:
        return focus_kind
    next_action = snapshot.get("next_best_action", {}) if isinstance(snapshot.get("next_best_action"), dict) else {}
    return _normalize_usage_action_kind(next_action.get("kind"))


def get_action_deck_view(
    *,
    snapshot: dict[str, object] | None = None,
    actions: dict[str, object] | None = None,
    blocked_actions: dict[str, object] | None = None,
) -> dict[str, object]:
    if snapshot is None:
        snapshot = build_lens_snapshot()
    if actions is None:
        actions = get_lens_actions(max_actions=8)

    chips = actions.get("action_chips", []) if isinstance(actions.get("action_chips"), list) else []
    blocked_surface = blocked_actions if isinstance(blocked_actions, dict) else {}
    blocked_count = int(blocked_surface.get("count", 0))
    blocked_summary = str(blocked_surface.get("summary", "")).strip()
    focus_kind = _focus_action_kind(snapshot)

    items: list[dict[str, Any]] = []
    for chip in chips[:8]:
        if not isinstance(chip, dict):
            continue
        chip_kind = str(chip.get("kind", "")).strip()
        normalized_kind = _normalize_usage_action_kind(chip_kind)
        enabled = bool(chip.get("enabled", False))
        request_flow = chip_kind.endswith(".request_approval")
        state = (
            "current"
            if normalized_kind and normalized_kind == focus_kind
            else "ready"
            if enabled
            else "blocked"
        )
        items.append(
            {
                "kind": normalized_kind or chip_kind,
                "execute_kind": chip_kind,
                "label": str(chip.get("label", "")).strip() or chip_kind or "Action",
                "enabled": enabled,
                "risk_tier": str(chip.get("risk_tier", "low")).strip().lower() or "low",
                "trust_badge": str(chip.get("trust_badge", "Likely" if enabled else "Blocked")).strip()
                or ("Likely" if enabled else "Blocked"),
                "requires_confirmation": bool(chip.get("requires_confirmation", False)),
                "state": state,
                "detail_summary": str(chip.get("policy_reason", "")).strip()
                or str(chip.get("reason", "")).strip()
                or "No operator note provided.",
                "guidance": (
                    "This action requires explicit confirmation."
                    if bool(chip.get("requires_confirmation", False))
                    else "This action can execute immediately."
                ),
                "primary_label": (
                    "Request"
                    if request_flow and enabled
                    else "Execute"
                    if enabled
                    else "Blocked"
                ),
                "args": _chip_args(chip),
                "audit": {
                    "kind": normalized_kind or chip_kind,
                    "execute_kind": chip_kind,
                    "enabled": enabled,
                    "risk_tier": str(chip.get("risk_tier", "low")).strip().lower() or "low",
                    "trust_badge": str(chip.get("trust_badge", "Likely" if enabled else "Blocked")).strip()
                    or ("Likely" if enabled else "Blocked"),
                    "requires_confirmation": bool(chip.get("requires_confirmation", False)),
                    "state": state,
                    "arg_keys": sorted(_chip_args(chip).keys()),
                },
            }
        )

    focus_item = next((row for row in items if str(row.get("state", "")).strip() == "current"), None)
    if focus_item is None and items:
        focus_item = items[0]

    return {
        "status": "ok",
        "surface": "action_deck",
        "summary": f"{len(items)} live action chip(s)",
        "blocked_summary": blocked_summary or (f"{blocked_count} currently blocked" if blocked_count else "No blocked actions surfaced"),
        "focus_action_kind": str(focus_item.get("kind", "")).strip() if isinstance(focus_item, dict) else "",
        "items": items,
        "detail": {
            "focus_action_kind": str(focus_item.get("kind", "")).strip() if isinstance(focus_item, dict) else "",
            "blocked_count": blocked_count,
            "blocked_summary": blocked_summary,
            "items": items,
        },
    }
