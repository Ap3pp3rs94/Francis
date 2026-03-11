from __future__ import annotations

from typing import Any

from services.hud.app.orchestrator_bridge import get_lens_actions
from services.hud.app.state import build_lens_snapshot


def _has_action(actions: dict[str, Any], kind: str) -> bool:
    for chip in actions.get("action_chips", []):
        if str(chip.get("kind", "")).strip().lower() == kind:
            return True
    return False


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

    items: list[dict[str, Any]] = []
    for row in pending:
        if not isinstance(row, dict):
            continue
        approval_id = str(row.get("id", "")).strip()
        metadata = row.get("metadata", {}) if isinstance(row.get("metadata"), dict) else {}
        tool_skill = str(metadata.get("skill", "")).strip().lower()
        summary = (
            f"{str(row.get('action', 'approval')).strip()} requested by "
            f"{str(row.get('requested_by', 'unknown')).strip() or 'unknown'}"
        )
        if tool_skill == "repo.tests":
            args = metadata.get("args", {}) if isinstance(metadata.get("args"), dict) else {}
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
                "reason": str(row.get("reason", "")).strip(),
                "requested_by": str(row.get("requested_by", "")).strip(),
                "summary": summary,
                "skill": tool_skill,
                "args": metadata.get("args", {}) if isinstance(metadata.get("args"), dict) else {},
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
