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


def _has_action(actions: dict[str, Any], kind: str) -> bool:
    for chip in actions.get("action_chips", []):
        if str(chip.get("kind", "")).strip().lower() == kind:
            return True
    return False


def _requested_action_kind(row: dict[str, Any], metadata: dict[str, Any]) -> str:
    explicit = str(metadata.get("action_kind", "")).strip().lower()
    if explicit:
        return explicit
    skill = str(metadata.get("skill", "")).strip().lower()
    if skill:
        return skill
    return str(row.get("action", "")).strip().lower()


def _focus_action_kind(snapshot: dict[str, object]) -> str:
    next_action = snapshot.get("next_best_action", {}) if isinstance(snapshot.get("next_best_action"), dict) else {}
    return _normalize_usage_action_kind(next_action.get("kind"))


def _detail_summary(*, row: dict[str, Any], requested_action_kind: str, args: dict[str, Any]) -> str:
    lane = str(args.get("lane", "")).strip().lower()
    target = str(args.get("target", "")).strip()
    base = (
        f"{requested_action_kind} is waiting on an operator decision."
        if requested_action_kind
        else f"{str(row.get('action', 'approval')).strip() or 'approval'} is waiting on an operator decision."
    )
    details: list[str] = []
    if lane:
        details.append(f"lane {lane}")
    if target:
        details.append(target)
    reason = str(row.get("reason", "")).strip()
    if reason:
        details.append(reason)
    return f"{base} {' | '.join(details)}".strip() if details else base


def _detail_state_hint(*, requested_action_kind: str, focus_action_kind: str) -> str:
    if requested_action_kind and focus_action_kind and requested_action_kind == focus_action_kind:
        return "current"
    return "historical"


def _detail_cards(*, row: dict[str, Any], requested_action_kind: str, args: dict[str, Any]) -> list[dict[str, str]]:
    lane = str(args.get("lane", "")).strip().lower()
    target = str(args.get("target", "")).strip()
    cards = [
        {
            "label": "Action",
            "value": requested_action_kind or str(row.get("action", "approval")).strip() or "approval",
            "tone": "high",
        },
        {
            "label": "Requested By",
            "value": str(row.get("requested_by", "unknown")).strip() or "unknown",
            "tone": "low",
        },
        {
            "label": "Decision",
            "value": "awaiting operator",
            "tone": "medium",
        },
    ]
    if lane:
        cards.append({"label": "Lane", "value": lane, "tone": "medium"})
    if target:
        cards.append({"label": "Target", "value": target, "tone": "low"})
    return cards


def get_approval_queue_view(
    *,
    snapshot: dict[str, object] | None = None,
    actions: dict[str, object] | None = None,
) -> dict[str, object]:
    if snapshot is None:
        snapshot = build_lens_snapshot()
    if actions is None:
        actions = get_lens_actions(max_actions=8)

    approvals = snapshot.get("approvals", {}) if isinstance(snapshot.get("approvals"), dict) else {}
    pending = approvals.get("pending", []) if isinstance(approvals.get("pending"), list) else []
    can_read = _has_action(actions, "control.remote.approvals")
    can_approve = _has_action(actions, "control.remote.approval.approve")
    can_reject = _has_action(actions, "control.remote.approval.reject")
    focus_action_kind = _focus_action_kind(snapshot)

    items: list[dict[str, Any]] = []
    for row in pending:
        if not isinstance(row, dict):
            continue
        approval_id = str(row.get("id", "")).strip()
        metadata = row.get("metadata", {}) if isinstance(row.get("metadata"), dict) else {}
        tool_skill = str(metadata.get("skill", "")).strip().lower()
        args = metadata.get("args", {}) if isinstance(metadata.get("args"), dict) else {}
        requested_action_kind = _requested_action_kind(row, metadata)
        summary = (
            f"{str(row.get('action', 'approval')).strip()} requested by "
            f"{str(row.get('requested_by', 'unknown')).strip() or 'unknown'}"
        )
        if tool_skill == "repo.tests":
            lane = str(args.get("lane", "fast")).strip().lower() or "fast"
            target = str(args.get("target", "")).strip()
            summary = f"repo.tests approval queued for lane {lane}"
            if target:
                summary += f" on {target}"

        items.append(
            {
                "id": approval_id,
                "ts": row.get("ts"),
                "action": str(row.get("action", "")).strip(),
                "requested_action_kind": requested_action_kind,
                "reason": str(row.get("reason", "")).strip(),
                "requested_by": str(row.get("requested_by", "")).strip(),
                "summary": summary,
                "detail_summary": _detail_summary(
                    row=row,
                    requested_action_kind=requested_action_kind,
                    args=args,
                ),
                "detail_cards": _detail_cards(
                    row=row,
                    requested_action_kind=requested_action_kind,
                    args=args,
                ),
                "detail_state": _detail_state_hint(
                    requested_action_kind=requested_action_kind,
                    focus_action_kind=focus_action_kind,
                ),
                "skill": tool_skill,
                "args": args,
                "can_execute_after_approval": bool(
                    can_approve and approval_id and requested_action_kind and _has_action(actions, requested_action_kind)
                ),
                "execute_after_approval_kind": requested_action_kind,
                "execute_after_approval_args": args,
                "can_approve": bool(can_approve and approval_id),
                "can_reject": bool(can_reject and approval_id),
            }
        )

    return {
        "status": "ok",
        "surface": "approval_queue",
        "pending_count": int(approvals.get("pending_count", 0)),
        "can_read": can_read,
        "can_approve": can_approve,
        "can_reject": can_reject,
        "items": items,
    }
