from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from francis_llm import chat
from francis_presence.orb import build_orb_state
from services.hud.app.orb_memory import (
    DEFAULT_ORB_CONVERSATION_ID,
    append_orb_turn,
    build_orb_chat_history,
    refresh_orb_long_term_memory,
)
from services.hud.app.orb_planner import build_orb_chat_plan
from services.orchestrator.app.orb_perception import get_orb_perception_view, resolve_orb_focus_target
from services.hud.app.orchestrator_bridge import get_lens_actions
from services.hud.app.state import build_lens_snapshot
from services.hud.app.views.approval_queue import get_approval_queue_view
from services.hud.app.views.blocked_actions import get_blocked_actions_view
from services.hud.app.views.current_work import get_current_work_view
from services.hud.app.views.execution_journal import get_execution_journal_view
from services.hud.app.views.incidents import get_incidents_view
from services.orchestrator.app.orb_authority import get_orb_authority_view
from services.voice.app.operator import build_operator_presence


def _normalize_usage_action_kind(value: object) -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        return ""
    suffix = ".request_approval"
    return raw[: -len(suffix)] if raw.endswith(suffix) else raw


def _receipt_summary(row: dict[str, Any]) -> str:
    detail_summary = str(row.get("detail_summary", "")).strip()
    if detail_summary:
        return detail_summary
    title = str(row.get("title", "")).strip() or str(row.get("kind", "Receipt")).strip() or "Receipt"
    summary = str(row.get("summary", "")).strip()
    if summary:
        return f"{title}. {summary}".strip()
    return f"{title}. Receipt recorded."


def _incident_rank(value: object) -> int:
    normalized = str(value or "").strip().lower()
    if normalized in {"critical", "severe"}:
        return 4
    if normalized == "high":
        return 3
    if normalized == "medium":
        return 2
    if normalized in {"low", "nominal"}:
        return 1
    return 0


def _coerce_orb_coordinate(value: object) -> int | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def _build_orb_target_cue() -> dict[str, Any] | None:
    focus_target = resolve_orb_focus_target()
    if not isinstance(focus_target, dict):
        return None

    surface = focus_target.get("surface", {}) if isinstance(focus_target.get("surface"), dict) else {}
    zone = focus_target.get("zone", {}) if isinstance(focus_target.get("zone"), dict) else {}
    target = focus_target.get("target", {}) if isinstance(focus_target.get("target"), dict) else {}
    affordances = focus_target.get("affordances", []) if isinstance(focus_target.get("affordances"), list) else []
    target_window = target.get("window", {}) if isinstance(target.get("window"), dict) else {}
    target_stability = target.get("stability", {}) if isinstance(target.get("stability"), dict) else {}

    surface_kind = str(surface.get("kind", "")).strip().lower() or "application"
    surface_label = str(surface.get("label", "Application surface")).strip() or "Application surface"
    zone_kind = str(zone.get("kind", "")).strip().lower() or "application_content"
    zone_label = str(zone.get("label", "Active zone")).strip() or "Active zone"
    target_label = str(target.get("label", "Active focus point")).strip() or "Active focus point"
    confidence = str(target.get("confidence", "low")).strip().lower() or "low"
    stability = str(target_stability.get("state", "idle")).strip().lower() or "idle"
    in_bounds = bool(target_window.get("in_bounds"))

    primary_affordance = next(
        (
            row
            for row in affordances
            if isinstance(row, dict) and str(row.get("label", "")).strip()
        ),
        None,
    )
    primary_label = str(primary_affordance.get("label", "")).strip() if isinstance(primary_affordance, dict) else ""
    control_ready = bool(
        surface_kind == "francis"
        and zone_kind.startswith("francis_")
        and stability == "settled"
        and confidence in {"likely", "medium"}
        and in_bounds
        and primary_label
    )

    if control_ready:
        state = "concrete"
        summary = f"Concrete {zone_label.lower()} target. {primary_label} is grounded from the Orb."
        detail = f"{target_label} is inside the foreground Francis surface and stable enough for precise handoff."
    elif stability == "tracking" and in_bounds:
        state = "tracking"
        summary = f"Tracking {zone_label.lower()} target. Let it settle before Francis acts."
        detail = f"{target_label} is inside {surface_label.lower()}, but the cursor is still moving."
    else:
        state = "weak"
        summary = f"Weak {zone_label.lower()} target. Francis is holding off until the control becomes concrete."
        detail = (
            f"{target_label} is not grounded enough yet"
            + (" because it is outside the foreground window." if not in_bounds else ".")
        )

    return {
        "title": "",
        "state": state,
        "control_ready": control_ready,
        "surface_kind": surface_kind,
        "surface_label": surface_label,
        "zone_kind": zone_kind,
        "zone_label": zone_label,
        "target_label": target_label,
        "confidence": confidence,
        "stability": stability,
        "window_match": "inside_foreground_window" if in_bounds else "weak",
        "primary_action_label": primary_label,
        "summary": summary,
        "detail": detail,
    }


def _build_orb_receipt_cue(
    *,
    related_receipt: dict[str, Any] | None,
    focus_kind: str,
    target_cue: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not isinstance(related_receipt, dict):
        return None

    receipt_run_id = str(related_receipt.get("run_id", "")).strip()
    receipt_action_kind = _normalize_usage_action_kind(related_receipt.get("action_kind"))
    normalized_focus_kind = _normalize_usage_action_kind(focus_kind)
    aligned = bool(
        receipt_action_kind
        and normalized_focus_kind
        and receipt_action_kind == normalized_focus_kind
    )
    cue = target_cue if isinstance(target_cue, dict) else {}
    cue_state = str(cue.get("state", "weak")).strip().lower() or "weak"
    zone_label = str(cue.get("zone_label", "active control region")).strip() or "active control region"
    surface_label = str(cue.get("surface_label", "foreground surface")).strip() or "foreground surface"
    target_label = str(cue.get("target_label", "active focus point")).strip() or "active focus point"
    primary_label = str(cue.get("primary_action_label", "")).strip()
    action_label = primary_label or target_label
    receipt_label = f"Receipt {receipt_run_id}" if receipt_run_id else "Latest receipt"

    if aligned and cue_state == "concrete":
        state = "concrete"
        summary = f"{receipt_label} is grounded by a concrete {zone_label.lower()}."
        detail = (
            f"{action_label} was lawful because {target_label} was inside the foreground "
            f"{surface_label.lower()} and stable enough for precise handoff."
        )
    elif aligned and cue_state == "tracking":
        state = "tracking"
        summary = f"{receipt_label} is attached, but the target was still tracking."
        detail = (
            f"{target_label} stayed inside the foreground {surface_label.lower()}, "
            "but Francis held it below concrete control readiness."
        )
    else:
        state = "weak"
        summary = f"{receipt_label} is attached, but no concrete target cue is grounded now."
        detail = (
            "The receipt remains visible, but the Orb is holding off on claiming a precise control target "
            "until the active surface becomes concrete again."
        )

    return {
        "title": "Receipt Grounding",
        "state": state,
        "control_ready": bool(aligned and cue_state == "concrete"),
        "surface_kind": str(cue.get("surface_kind", "")).strip(),
        "surface_label": surface_label,
        "zone_kind": str(cue.get("zone_kind", "")).strip(),
        "zone_label": zone_label,
        "target_label": target_label,
        "confidence": str(cue.get("confidence", "low")).strip().lower() or "low",
        "stability": str(cue.get("stability", "idle")).strip().lower() or "idle",
        "window_match": str(cue.get("window_match", "weak")).strip().lower() or "weak",
        "primary_action_label": primary_label,
        "summary": summary,
        "detail": detail,
        "receipt_run_id": receipt_run_id,
        "receipt_action_kind": receipt_action_kind,
    }


def _build_takeover_desktop_run_contract(
    *,
    focus_action: dict[str, Any],
    takeover: dict[str, Any],
) -> dict[str, Any] | None:
    if not isinstance(focus_action, dict) or not isinstance(takeover, dict):
        return None
    if not bool(takeover.get("active", False)):
        return None
    if not str(takeover.get("session_id", "")).strip():
        return None

    focus_kind = str(focus_action.get("execute_kind") or focus_action.get("kind") or "").strip().lower()
    focus_args = focus_action.get("args", {}) if isinstance(focus_action.get("args"), dict) else {}
    target_cue = _build_orb_target_cue()
    command: dict[str, Any] | None = None
    summary = ""

    if focus_kind == "orb.authority.queue_focus_move":
        focus_target = resolve_orb_focus_target()
        if not isinstance(focus_target, dict):
            return None
        target_label = str(
            (focus_target.get("target", {}) if isinstance(focus_target.get("target"), dict) else {}).get("label", "live focus point")
        ).strip() or "live focus point"
        command = {
            "kind": "mouse.move",
            "args": {
                "x": int(focus_target["x"]),
                "y": int(focus_target["y"]),
                "coordinate_space": "display",
            },
            "reason": (
                f"Move the Francis Orb operator cursor to the {target_label.lower()} "
                f"({int(focus_target['x'])}, {int(focus_target['y'])}) during takeover."
            ),
        }
        summary = f"Queue the current {target_label.lower()} into the active Francis takeover session."
    elif focus_kind == "orb.authority.queue_focus_click":
        focus_target = resolve_orb_focus_target()
        if not isinstance(focus_target, dict):
            return None
        target_label = str(
            (focus_target.get("target", {}) if isinstance(focus_target.get("target"), dict) else {}).get("label", "live focus point")
        ).strip() or "live focus point"
        button = str(focus_args.get("button", "left")).strip().lower() or "left"
        command = {
            "kind": "mouse.click",
            "args": {
                "x": int(focus_target["x"]),
                "y": int(focus_target["y"]),
                "button": button,
                "coordinate_space": "display",
            },
            "reason": (
                f"{button.title()} click the {target_label.lower()} "
                f"({int(focus_target['x'])}, {int(focus_target['y'])}) during takeover."
            ),
        }
        summary = f"Queue a click at the current {target_label.lower()} into the active Francis takeover session."
    elif focus_kind == "orb.authority.queue_move":
        x = _coerce_orb_coordinate(focus_args.get("x"))
        y = _coerce_orb_coordinate(focus_args.get("y"))
        if x is None or y is None:
            return None
        command = {
            "kind": "mouse.move",
            "args": {
                "x": x,
                "y": y,
                "coordinate_space": str(focus_args.get("coordinate_space", "display")).strip().lower() or "display",
            },
            "reason": f"Move the Francis Orb operator cursor to ({x}, {y}) during takeover.",
        }
        summary = "Queue the current move target into the active Francis takeover session."
    elif focus_kind == "orb.authority.queue_click":
        x = _coerce_orb_coordinate(focus_args.get("x"))
        y = _coerce_orb_coordinate(focus_args.get("y"))
        if x is None or y is None:
            return None
        button = str(focus_args.get("button", "left")).strip().lower() or "left"
        command = {
            "kind": "mouse.click",
            "args": {
                "x": x,
                "y": y,
                "button": button,
                "coordinate_space": str(focus_args.get("coordinate_space", "display")).strip().lower() or "display",
            },
            "reason": f"{button.title()} click ({x}, {y}) during takeover.",
        }
        summary = "Queue the current click target into the active Francis takeover session."
    elif focus_kind == "orb.authority.queue_save":
        command = {
            "kind": "keyboard.shortcut",
            "args": {"keys": ["ctrl", "s"]},
            "reason": "Press Ctrl+S through the active Francis takeover session.",
        }
        summary = "Queue save into the active Francis takeover session."
    elif focus_kind == "orb.authority.queue_type":
        text = str(focus_args.get("text", "")).strip()
        if not text:
            return None
        command = {
            "kind": "keyboard.type",
            "args": {"text": text},
            "reason": "Type queued text through the active Francis takeover session.",
        }
        summary = "Queue typed input into the active Francis takeover session."
    elif focus_kind == "orb.authority.queue_key":
        key = str(focus_args.get("key", "")).strip().lower()
        if not key:
            return None
        command = {
            "kind": "keyboard.key",
            "args": {"key": key},
            "reason": f"Press {key} through the active Francis takeover session.",
        }
        summary = f"Queue {key} into the active Francis takeover session."
    elif focus_kind in {
        "apprenticeship.skillize",
        "forge.promote",
        "forge.promote.request_approval",
        "forge.revoke",
        "forge.quarantine",
        "repo.tests",
        "repo.tests.request_approval",
        "control.takeover.confirm",
        "control.remote.approval.reject",
    }:
        focus_target = resolve_orb_focus_target()
        if not isinstance(focus_target, dict):
            return None
        surface = focus_target.get("surface", {}) if isinstance(focus_target.get("surface"), dict) else {}
        zone = focus_target.get("zone", {}) if isinstance(focus_target.get("zone"), dict) else {}
        target = focus_target.get("target", {}) if isinstance(focus_target.get("target"), dict) else {}
        affordances = focus_target.get("affordances", []) if isinstance(focus_target.get("affordances"), list) else []
        if str(surface.get("kind", "")).strip().lower() != "francis":
            return None
        zone_kind = str(zone.get("kind", "")).strip().lower()
        if zone_kind not in {"francis_action_row", "francis_navigation", "francis_workspace", "francis_footer_actions"}:
            return None
        preferred_affordance_kinds = {"focus_click", "open_key", "confirm_key"}
        if focus_kind == "control.remote.approval.reject":
            if zone_kind not in {"francis_action_row", "francis_workspace", "francis_footer_actions"}:
                return None
            preferred_affordance_kinds = {"focus_click", "cancel_key"}
        if str(target.get("confidence", "")).strip().lower() not in {"likely", "medium"}:
            return None
        target_stability = target.get("stability", {}) if isinstance(target.get("stability"), dict) else {}
        if str(target_stability.get("state", "")).strip().lower() != "settled":
            return None
        target_window = target.get("window", {}) if isinstance(target.get("window"), dict) else {}
        if not bool(target_window.get("in_bounds")):
            return None
        preferred = next(
            (
                row
                for row in affordances
                if isinstance(row, dict)
                and str(row.get("kind", "")).strip().lower() in preferred_affordance_kinds
                and isinstance(row.get("command"), dict)
            ),
            None,
        )
        if not isinstance(preferred, dict):
            return None
        command = preferred.get("command", {}) if isinstance(preferred.get("command"), dict) else None
        if not isinstance(command, dict):
            return None
        action_label = str(focus_action.get("label", "")).strip() or focus_kind.replace(".", " ")
        affordance_label = str(preferred.get("label", "Confirm")).strip() or "Confirm"
        summary = (
            f"Queue {affordance_label.lower()} for {action_label} from the active Francis control surface."
        )

    if not isinstance(command, dict):
        return None
    if isinstance(target_cue, dict):
        command = {**command, "grounding": target_cue}
    return {
        "enabled": True,
        "kind": "control.takeover.desktop.enqueue",
        "args": {"summary": summary, "commands": [command]},
        "summary": summary,
    }


def _build_surface_action_contract() -> dict[str, Any] | None:
    focus_target = resolve_orb_focus_target()
    if not isinstance(focus_target, dict):
        return None
    target = focus_target.get("target", {}) if isinstance(focus_target.get("target"), dict) else {}
    affordances = target.get("affordances", []) if isinstance(target.get("affordances"), list) else []
    if not affordances:
        return None
    preferred_order = {
        "submit_key": 0,
        "open_key": 1,
        "save_shortcut": 2,
        "confirm_key": 3,
        "cancel_key": 4,
        "focus_click": 5,
    }
    affordance = min(
        (
            row
            for row in affordances
            if isinstance(row, dict)
            and isinstance(row.get("command"), dict)
            and str(row.get("label", "")).strip()
        ),
        key=lambda row: preferred_order.get(str(row.get("kind", "")).strip().lower(), 99),
        default=None,
    )
    if not isinstance(affordance, dict):
        return None
    command = affordance.get("command", {}) if isinstance(affordance.get("command"), dict) else {}
    command_kind = str(command.get("kind", "")).strip().lower()
    command_args = command.get("args", {}) if isinstance(command.get("args"), dict) else {}
    if not command_kind:
        return None
    return {
        "enabled": True,
        "kind": str(affordance.get("kind", "")).strip().lower(),
        "label": str(affordance.get("label", "")).strip() or "Surface Action",
        "summary": str(affordance.get("summary", "")).strip() or "Queue the current surface action through the Orb authority channel.",
        "command_kind": command_kind,
        "command_args": command_args,
        "reason": str(command.get("reason", "")).strip()
        or str(affordance.get("summary", "")).strip()
        or "Queue the current surface action through the Orb authority channel.",
    }


def _build_orb_operator_view(
    *,
    snapshot: dict[str, Any],
    actions: dict[str, Any],
) -> dict[str, Any]:
    current_work = get_current_work_view(snapshot=snapshot, actions=actions)
    approval_queue = get_approval_queue_view(snapshot=snapshot, actions=actions)
    journal = get_execution_journal_view(snapshot=snapshot)
    takeover = snapshot.get("takeover", {}) if isinstance(snapshot.get("takeover"), dict) else {}

    focus_action = current_work.get("focus_action", {}) if isinstance(current_work.get("focus_action"), dict) else {}
    next_action = current_work.get("next_action", {}) if isinstance(current_work.get("next_action"), dict) else {}
    next_action_resume = (
        current_work.get("next_action_resume", {})
        if isinstance(current_work.get("next_action_resume"), dict)
        else {}
    )
    operator_link = current_work.get("operator_link", {}) if isinstance(current_work.get("operator_link"), dict) else {}
    focus_kind = _normalize_usage_action_kind(
        operator_link.get("action_kind")
        or focus_action.get("execute_kind")
        or focus_action.get("kind")
        or next_action.get("kind")
    )

    approvals = approval_queue.get("items", []) if isinstance(approval_queue.get("items"), list) else []
    related_approval = next(
        (
            row
            for row in approvals
            if _normalize_usage_action_kind(row.get("requested_action_kind")) == focus_kind
        ),
        None,
    )
    receipt_rows = journal.get("items", []) if isinstance(journal.get("items"), list) else []
    linked_run_id = str(operator_link.get("run_id", "")).strip()
    linked_approval_id = str(operator_link.get("approval_id", "")).strip()
    related_receipt = None
    if linked_run_id:
        related_receipt = next(
            (row for row in receipt_rows if str(row.get("run_id", "")).strip() == linked_run_id),
            None,
        )
    if related_receipt is None and linked_approval_id:
        related_receipt = next(
            (row for row in receipt_rows if str(row.get("approval_id", "")).strip() == linked_approval_id),
            None,
        )
    if related_receipt is None and focus_kind:
        related_receipt = next(
            (
                row
                for row in receipt_rows
                if _normalize_usage_action_kind(row.get("action_kind")) == focus_kind
            ),
            None,
        )

    focus_label = (
        str(focus_action.get("label", "")).strip()
        or str(next_action.get("label", "")).strip()
        or "No current move selected."
    )
    focus_reason = (
        str(focus_action.get("reason", "")).strip()
        or str(next_action_resume.get("summary", "")).strip()
        or str(next_action.get("reason", "")).strip()
        or "Francis is waiting for the next grounded move."
    )
    focus_state = str(focus_action.get("state", "")).strip().lower() or "idle"
    can_approve_and_run = bool(
        isinstance(related_approval, dict)
        and related_approval.get("can_execute_after_approval")
        and str(related_approval.get("id", "")).strip()
    )
    target_cue = _build_orb_target_cue()
    receipt_cue = _build_orb_receipt_cue(
        related_receipt=related_receipt if isinstance(related_receipt, dict) else None,
        focus_kind=focus_kind,
        target_cue=target_cue if isinstance(target_cue, dict) else None,
    )
    takeover_desktop_run = _build_takeover_desktop_run_contract(focus_action=focus_action, takeover=takeover)
    surface_action = _build_surface_action_contract()
    preview_enabled = bool(focus_action.get("enabled"))
    run_enabled = can_approve_and_run or preview_enabled or bool(
        isinstance(takeover_desktop_run, dict) and takeover_desktop_run.get("enabled")
    )
    receipt_summary = (
        _receipt_summary(related_receipt)
        if isinstance(related_receipt, dict)
        else "No latest receipt is anchoring the Orb surface yet."
    )

    if can_approve_and_run:
        meta = (
            f"Approval {str(related_approval.get('id', '')).strip() or 'pending'} is ready. "
            "The Orb can approve and continue this move."
        )
        state = "approval_ready"
    elif preview_enabled:
        meta = (
            f"{str(focus_action.get('execute_kind') or focus_action.get('kind') or 'unknown')} | "
            f"risk {str(focus_action.get('risk_tier', 'low')).strip() or 'low'} | "
            f"{focus_state or 'ready'}"
        )
        state = focus_state or "ready"
    elif isinstance(related_receipt, dict):
        meta = "A recent receipt is anchoring the current Orb move."
        state = "receipt_grounded"
    else:
        meta = "No current move is surfaced yet."
        state = "idle"

    return {
        "surface": "orb_operator",
        "state": state,
        "focus_kind": focus_kind,
        "summary": f"{focus_label} | {focus_reason}".strip(),
        "meta": meta,
        "focus_action": focus_action,
        "next_action_resume": next_action_resume,
        "approval": related_approval if isinstance(related_approval, dict) else None,
        "latest_receipt": related_receipt if isinstance(related_receipt, dict) else None,
        "target_cue": target_cue if isinstance(target_cue, dict) else None,
        "receipt_cue": receipt_cue if isinstance(receipt_cue, dict) else None,
        "receipt_summary": receipt_summary,
        "controls": {
            "preview_enabled": preview_enabled,
            "preview_kind": str(focus_action.get("kind", "")).strip(),
            "preview_args": focus_action.get("args", {}) if isinstance(focus_action.get("args"), dict) else {},
            "run_enabled": run_enabled,
            "run_mode": "approve_and_run" if can_approve_and_run else "execute",
            "run_kind": str(focus_action.get("execute_kind") or focus_action.get("kind") or "").strip(),
            "run_args": focus_action.get("args", {}) if isinstance(focus_action.get("args"), dict) else {},
            "approval_id": str(related_approval.get("id", "")).strip() if isinstance(related_approval, dict) else "",
            "receipt_available": isinstance(related_receipt, dict),
            "takeover_active": bool(takeover.get("active", False)),
            "takeover_session_id": str(takeover.get("session_id", "")).strip(),
            "desktop_run_enabled": bool(
                isinstance(takeover_desktop_run, dict) and takeover_desktop_run.get("enabled")
            ),
            "desktop_run_kind": str(takeover_desktop_run.get("kind", "")).strip()
            if isinstance(takeover_desktop_run, dict)
            else "",
            "desktop_run_args": takeover_desktop_run.get("args", {})
            if isinstance(takeover_desktop_run, dict)
            else {},
            "surface_action_enabled": bool(isinstance(surface_action, dict) and surface_action.get("enabled")),
            "surface_action_kind": str(surface_action.get("kind", "")).strip() if isinstance(surface_action, dict) else "",
            "surface_action_label": str(surface_action.get("label", "")).strip() if isinstance(surface_action, dict) else "",
            "surface_action_summary": str(surface_action.get("summary", "")).strip() if isinstance(surface_action, dict) else "",
            "surface_action_command_kind": str(surface_action.get("command_kind", "")).strip()
            if isinstance(surface_action, dict)
            else "",
            "surface_action_command_args": surface_action.get("command_args", {})
            if isinstance(surface_action, dict)
            else {},
            "surface_action_reason": str(surface_action.get("reason", "")).strip() if isinstance(surface_action, dict) else "",
        },
    }


def _build_orb_interjection_view(
    *,
    snapshot: dict[str, Any],
    actions: dict[str, Any],
    operator: dict[str, Any],
) -> dict[str, Any]:
    control = snapshot.get("control", {}) if isinstance(snapshot.get("control"), dict) else {}
    kill_switch = bool(control.get("kill_switch", False))
    try:
        incidents = get_incidents_view(snapshot=snapshot)
    except Exception:
        incidents = {"surface": "incidents", "severity": "nominal", "items": []}
    try:
        blocked_actions = get_blocked_actions_view(snapshot=snapshot, actions=actions)
    except Exception:
        blocked_actions = {"surface": "blocked_actions", "count": 0, "items": []}

    incident_items = incidents.get("items", []) if isinstance(incidents.get("items"), list) else []
    top_incident = incident_items[0] if incident_items and isinstance(incident_items[0], dict) else None
    incident_severity = str(incidents.get("severity", "nominal")).strip().lower() or "nominal"
    blocked_items = (
        blocked_actions.get("items", [])
        if isinstance(blocked_actions.get("items"), list)
        else []
    )
    top_blocked = blocked_items[0] if blocked_items and isinstance(blocked_items[0], dict) else None
    operator_controls = operator.get("controls", {}) if isinstance(operator.get("controls"), dict) else {}
    operator_approval = operator.get("approval", {}) if isinstance(operator.get("approval"), dict) else {}
    target_cue = operator.get("target_cue", {}) if isinstance(operator.get("target_cue"), dict) else {}
    focus_action = operator.get("focus_action", {}) if isinstance(operator.get("focus_action"), dict) else {}
    next_action_resume = (
        operator.get("next_action_resume", {})
        if isinstance(operator.get("next_action_resume"), dict)
        else {}
    )

    if kill_switch or _incident_rank(incident_severity) >= 4:
        summary = "Immediate intervention is required."
        detail = (
            "Kill switch is live. Francis is halted until you explicitly inspect or resume."
            if kill_switch
            else str(top_incident.get("detail_summary", "")).strip()
            or "A critical incident is active in the current workspace."
        )
        prompt = "Stop, inspect, or revoke before allowing further work."
        return {
            "surface": "orb_interjection",
            "state": "immediate_intervention",
            "level": 3,
            "reason_kind": "kill_switch" if kill_switch else "critical_incident",
            "summary": summary,
            "detail": detail,
            "prompt": prompt,
            "can_defer": False,
            "target_cue": target_cue if target_cue else None,
            "controls": {
                "primary_action": "open_lens",
                "primary_label": "Open Lens",
                "secondary_action": "receipt"
                if bool(operator_controls.get("receipt_available"))
                else "",
                "secondary_label": "Latest Receipt"
                if bool(operator_controls.get("receipt_available"))
                else "",
            },
        }

    if str(operator_controls.get("run_mode", "")).strip() == "approve_and_run" and str(
        operator_controls.get("approval_id", "")
    ).strip():
        approval_id = str(operator_controls.get("approval_id", "")).strip()
        summary = "Decision required to continue the current move."
        detail = str(operator.get("meta", "")).strip() or str(
            operator_approval.get("detail_summary", "")
        ).strip() or "Approval is waiting before Francis can continue."
        prompt = (
            f"Approval {approval_id} is ready. Approve and continue {str(operator.get('summary', 'the current move')).strip()}."
        )
        return {
            "surface": "orb_interjection",
            "state": "needed_decision",
            "level": 2,
            "reason_kind": "approval_ready",
            "summary": summary,
            "detail": detail,
            "prompt": prompt,
            "can_defer": False,
            "target_cue": target_cue if target_cue else None,
            "controls": {
                "primary_action": "run",
                "primary_label": "Approve + Run",
                "secondary_action": "preview"
                if bool(operator_controls.get("preview_enabled"))
                else "",
                "secondary_label": "Preview"
                if bool(operator_controls.get("preview_enabled"))
                else "",
            },
        }

    if top_blocked is not None or str(focus_action.get("state", "")).strip().lower() == "blocked":
        summary = "Work is blocked on a governed edge."
        detail = (
            str(top_blocked.get("detail_summary", "")).strip()
            if isinstance(top_blocked, dict)
            else str(focus_action.get("reason", "")).strip()
            or "A blocked action needs your review before Francis can continue intelligently."
        )
        prompt = "Clarify scope, lower risk, or open Lens to inspect the blocked path."
        return {
            "surface": "orb_interjection",
            "state": "needed_decision",
            "level": 2,
            "reason_kind": "blocked_action",
            "summary": summary,
            "detail": detail,
            "prompt": prompt,
            "can_defer": False,
            "target_cue": target_cue if target_cue else None,
            "controls": {
                "primary_action": "open_lens",
                "primary_label": "Open Lens",
                "secondary_action": "preview"
                if bool(operator_controls.get("preview_enabled"))
                else "",
                "secondary_label": "Preview"
                if bool(operator_controls.get("preview_enabled"))
                else "",
            },
        }

    if _incident_rank(incident_severity) >= 2 or bool(next_action_resume.get("can_resume")):
        summary = "Francis has a grounded prompt."
        detail = str(next_action_resume.get("summary", "")).strip()
        if not detail and isinstance(top_incident, dict):
            detail = str(top_incident.get("detail_summary", "")).strip()
        detail = detail or "A non-critical incident or resumable move is worth your attention."
        prompt = "You can defer briefly, but Francis is surfacing a real decision edge."
        return {
            "surface": "orb_interjection",
            "state": "soft_prompt",
            "level": 1,
            "reason_kind": "incident_attention"
            if _incident_rank(incident_severity) >= 2
            else "resume_ready",
            "summary": summary,
            "detail": detail,
            "prompt": prompt,
            "can_defer": True,
            "target_cue": target_cue if target_cue else None,
            "controls": {
                "primary_action": "preview"
                if bool(operator_controls.get("preview_enabled"))
                else "open_lens",
                "primary_label": "Preview"
                if bool(operator_controls.get("preview_enabled"))
                else "Open Lens",
                "secondary_action": "open_lens"
                if bool(operator_controls.get("preview_enabled"))
                else "",
                "secondary_label": "Open Lens"
                if bool(operator_controls.get("preview_enabled"))
                else "",
            },
        }

    return {
        "surface": "orb_interjection",
        "state": "idle",
        "level": 0,
        "reason_kind": "idle",
        "summary": "Francis is not interrupting the work.",
        "detail": "Interjections stay earned and grounded. The Orb remains ambient until a real decision edge appears.",
        "prompt": "",
        "can_defer": True,
        "target_cue": target_cue if target_cue else None,
        "controls": {
            "primary_action": "",
            "primary_label": "",
            "secondary_action": "",
            "secondary_label": "",
        },
    }


def _normalize_orb_chat_message(value: object) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _orb_chat_status_reply(orb: dict[str, Any]) -> str:
    authority = orb.get("authority", {}) if isinstance(orb.get("authority"), dict) else {}
    operator = orb.get("operator", {}) if isinstance(orb.get("operator"), dict) else {}
    parts = [
        f"Mode is {str(orb.get('mode', 'assist')).strip() or 'assist'} and posture is {str(orb.get('posture', 'resting')).strip() or 'resting'}.",
        str(orb.get("summary", "")).strip() or "Francis is ambient.",
    ]
    operator_summary = str(operator.get("summary", "")).strip()
    if operator_summary:
        parts.append(f"Current move: {operator_summary}.")
    authority_summary = str(authority.get("summary", "")).strip()
    if authority_summary:
        parts.append(authority_summary)
    return " ".join(part for part in parts if part)


def _orb_chat_surface_reply(orb: dict[str, Any], perception: dict[str, Any]) -> str:
    operator = orb.get("operator", {}) if isinstance(orb.get("operator"), dict) else {}
    target_cue = operator.get("target_cue", {}) if isinstance(operator.get("target_cue"), dict) else {}
    parts = [
        str(perception.get("summary", "")).strip() or "Visible context is not attached yet.",
        str(perception.get("detail_summary", "")).strip(),
        str(target_cue.get("summary", "")).strip(),
    ]
    return " ".join(part for part in parts if part)


def _orb_chat_receipt_reply(orb: dict[str, Any]) -> str:
    operator = orb.get("operator", {}) if isinstance(orb.get("operator"), dict) else {}
    authority = orb.get("authority", {}) if isinstance(orb.get("authority"), dict) else {}
    receipt_summary = str(operator.get("receipt_summary", "")).strip()
    receipt_cue = operator.get("receipt_cue", {}) if isinstance(operator.get("receipt_cue"), dict) else {}
    if receipt_summary:
        parts = [receipt_summary, str(receipt_cue.get("summary", "")).strip()]
        return " ".join(part for part in parts if part)
    recent = authority.get("recent", []) if isinstance(authority.get("recent"), list) else []
    latest = recent[0] if recent and isinstance(recent[0], dict) else {}
    latest_summary = str(latest.get("summary_text", "")).strip()
    if latest_summary:
        return latest_summary
    return "No receipt is anchoring the Orb right now."


def _orb_chat_why_reply(orb: dict[str, Any]) -> str:
    operator = orb.get("operator", {}) if isinstance(orb.get("operator"), dict) else {}
    interjection = orb.get("interjection", {}) if isinstance(orb.get("interjection"), dict) else {}
    target_cue = operator.get("target_cue", {}) if isinstance(operator.get("target_cue"), dict) else {}
    if str(interjection.get("state", "idle")).strip().lower() != "idle":
        parts = [
            str(interjection.get("summary", "")).strip(),
            str(interjection.get("detail", "")).strip(),
            str(interjection.get("prompt", "")).strip(),
        ]
        if target_cue:
            parts.append(str(target_cue.get("summary", "")).strip())
        return " ".join(part for part in parts if part)
    parts = [
        str(operator.get("summary", "")).strip(),
        str(operator.get("meta", "")).strip(),
        str(target_cue.get("summary", "")).strip() if target_cue else "",
    ]
    return " ".join(part for part in parts if part) or "Francis is ambient and not asking for anything right now."


def _orb_chat_run_reply(orb: dict[str, Any]) -> str:
    operator = orb.get("operator", {}) if isinstance(orb.get("operator"), dict) else {}
    controls = operator.get("controls", {}) if isinstance(operator.get("controls"), dict) else {}
    if bool(controls.get("run_enabled")):
        run_mode = str(controls.get("run_mode", "execute")).strip().lower() or "execute"
        if run_mode == "approve_and_run":
            return (
                "The current move is ready to approve and run from the Orb. "
                + (str(operator.get("summary", "")).strip() or "Francis has a grounded move ready.")
            )
        return (
            "The current move is ready to run from the Orb. "
            + (str(operator.get("summary", "")).strip() or "Francis has a grounded move ready.")
        )
    if bool(controls.get("preview_enabled")):
        return (
            "The current move is previewable, but it is not yet ready to run. "
            + (str(operator.get("meta", "")).strip() or "Francis is holding on the current edge.")
        )
    return "No grounded move is ready to run from the Orb right now."


def _build_orb_direct_chat_reply(
    *,
    message: str,
    orb: dict[str, Any],
    perception: dict[str, Any],
) -> str | None:
    normalized = _normalize_orb_chat_message(message)
    if not normalized:
        return None
    if any(phrase in normalized for phrase in {"status", "state", "what are you doing", "who has control"}):
        return _orb_chat_status_reply(orb)
    if any(phrase in normalized for phrase in {"what do you see", "what are you seeing", "surface", "screen", "what am i looking at"}):
        return _orb_chat_surface_reply(orb, perception)
    if any(phrase in normalized for phrase in {"receipt", "latest receipt", "last receipt", "latest run"}):
        return _orb_chat_receipt_reply(orb)
    if normalized.startswith("why") or any(
        phrase in normalized for phrase in {"what do you need", "why are you asking", "why this move"}
    ):
        return _orb_chat_why_reply(orb)
    if any(phrase in normalized for phrase in {"can you run", "ready to run", "can you continue", "are you ready"}):
        return _orb_chat_run_reply(orb)
    return None


def _hash_orb_thought_id(*parts: object) -> str:
    digest = hashlib.sha1()
    for part in parts:
        digest.update(str(part or "").encode("utf-8"))
        digest.update(b"|")
    return digest.hexdigest()[:16]


def _build_orb_thought_view(
    *,
    operator: dict[str, Any],
    interjection: dict[str, Any],
) -> dict[str, Any]:
    interjection_state = str(interjection.get("state", "idle")).strip().lower() or "idle"
    interjection_summary = str(interjection.get("summary", "")).strip()
    interjection_prompt = str(interjection.get("prompt", "")).strip()
    interjection_detail = str(interjection.get("detail", "")).strip()
    receipt_summary = str(operator.get("receipt_summary", "")).strip()
    target_cue = operator.get("target_cue", {}) if isinstance(operator.get("target_cue"), dict) else {}

    if interjection_state != "idle" and interjection_summary:
        detail = interjection_prompt or interjection_detail
        return {
            "visible": True,
            "id": _hash_orb_thought_id(interjection_state, interjection_summary, detail),
            "source": "interjection",
            "summary": interjection_summary,
            "detail": detail,
            "target_cue": target_cue if target_cue else None,
        }
    if receipt_summary and receipt_summary != "No latest receipt is anchoring the Orb surface yet.":
        return {
            "visible": True,
            "id": _hash_orb_thought_id("receipt", receipt_summary),
            "source": "receipt",
            "summary": receipt_summary,
            "detail": str(operator.get("meta", "")).strip(),
            "target_cue": target_cue if target_cue else None,
        }
    return {
        "visible": False,
        "id": "",
        "source": "",
        "summary": "",
        "detail": "",
        "target_cue": None,
    }


def _extract_json_object(raw: str) -> dict[str, Any] | None:
    text = str(raw or "").strip()
    if not text:
        return None
    candidates = [text]
    fence_match = re.search(r"```(?:json)?\s*(\{[\s\S]*\})\s*```", text, re.IGNORECASE)
    if fence_match:
        candidates.insert(0, fence_match.group(1).strip())
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        candidates.append(text[start : end + 1])
    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except Exception:
            continue
        if isinstance(payload, dict):
            return payload
    return None


def _coerce_plan_step(row: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(row, dict):
        return None
    kind = str(row.get("kind", "")).strip().lower()
    if kind not in {"keyboard.shortcut", "keyboard.type", "keyboard.key", "mouse.move", "mouse.click"}:
        return None
    args = row.get("args", {}) if isinstance(row.get("args"), dict) else {}
    reason = str(row.get("reason", "")).strip() or str(row.get("why", "")).strip()
    if kind == "mouse.click":
        button = str(args.get("button", "")).strip().lower()
        if button not in {"left", "right"}:
            return None
    if kind == "keyboard.type" and not str(args.get("text", "")).strip():
        return None
    if kind == "keyboard.key" and not str(args.get("key", "")).strip():
        return None
    if kind == "keyboard.shortcut":
        keys = args.get("keys")
        if not isinstance(keys, list) or not keys:
            return None
    if kind in {"mouse.move", "mouse.click"}:
        try:
            float(args.get("x"))
            float(args.get("y"))
        except Exception:
            return None
    return {
        "kind": kind,
        "args": args,
        "reason": reason or f"Carry out {kind} through the Orb shell execution layer.",
        "pause_ms": max(0, min(1200, int(row.get("pause_ms", 80) or 80))),
    }


def _normalize_orb_desktop_plan(plan: dict[str, Any] | None, *, mode: str) -> dict[str, Any] | None:
    if not isinstance(plan, dict):
        return None
    steps = []
    for row in plan.get("steps", []) if isinstance(plan.get("steps"), list) else []:
        normalized = _coerce_plan_step(row)
        if normalized:
            steps.append(normalized)
    if not steps:
        return None
    mode_requirement = str(plan.get("mode_requirement", "")).strip().lower() or "pilot"
    title = str(plan.get("title", "")).strip() or "Orb desktop action"
    summary = str(plan.get("summary", "")).strip() or title
    reasoning = [
        str(row).strip()
        for row in (plan.get("reasoning", []) if isinstance(plan.get("reasoning"), list) else [])
        if str(row).strip()
    ][:4]
    ready = bool(mode in {"pilot", "away"} and mode_requirement in {"pilot", "away"})
    if mode == "away" and mode_requirement == "pilot":
        ready = False
    return {
        "id": _hash_orb_thought_id(title, summary, json.dumps(steps, sort_keys=True)),
        "title": title,
        "summary": summary,
        "reasoning": reasoning,
        "mode_requirement": mode_requirement,
        "ready": ready,
        "steps": steps,
    }


def _heuristic_orb_desktop_plan(message: str, *, mode: str) -> dict[str, Any] | None:
    lowered = str(message or "").strip().lower()
    launch_match = re.match(r"^(?:open|launch|start|run)\s+(.+)$", lowered)
    if launch_match:
        target = launch_match.group(1).strip(" .")
        if target:
            return _normalize_orb_desktop_plan(
                {
                    "title": f"Open {target.title()}",
                    "summary": f"Open {target} through Windows Start search the way the user would.",
                    "mode_requirement": "pilot",
                    "reasoning": [
                        "Open Start instead of launching a process directly so the action follows the visible desktop path.",
                        f"Type {target} into Windows search, then confirm the highlighted result with the equivalent of a left-navigation open.",
                    ],
                    "steps": [
                        {
                            "kind": "keyboard.shortcut",
                            "args": {"keys": ["ctrl", "esc"]},
                            "reason": "Open the Windows Start surface for direct keyboard navigation.",
                            "pause_ms": 180,
                        },
                        {
                            "kind": "keyboard.type",
                            "args": {"text": target},
                            "reason": f"Search for {target} from Start so Francis follows the same visible path as the user.",
                            "pause_ms": 220,
                        },
                        {
                            "kind": "keyboard.key",
                            "args": {"key": "enter"},
                            "reason": f"Open the highlighted {target} result with the normal left-navigation equivalent.",
                            "pause_ms": 260,
                        },
                    ],
                },
                mode=mode,
            )
    type_match = re.match(r"^(?:type|enter text)\s+(.+)$", str(message or "").strip(), re.IGNORECASE)
    if type_match:
        text = type_match.group(1).strip()
        if text:
            return _normalize_orb_desktop_plan(
                {
                    "title": "Type Text",
                    "summary": "Type the requested text through the Orb shell execution layer.",
                    "mode_requirement": "pilot",
                    "reasoning": [
                        "Typing is a direct desktop action and should use the shell executor, not the planner.",
                    ],
                    "steps": [
                        {
                            "kind": "keyboard.type",
                            "args": {"text": text},
                            "reason": "Type the exact requested text into the active surface.",
                            "pause_ms": 120,
                        }
                    ],
                },
                mode=mode,
            )
    if lowered in {"save", "save this", "save it"}:
        return _normalize_orb_desktop_plan(
            {
                "title": "Save Active Surface",
                "summary": "Save through the standard desktop shortcut.",
                "mode_requirement": "pilot",
                "reasoning": [
                    "Use the standard save shortcut because it is the most direct visible save path across Windows applications.",
                ],
                "steps": [
                    {
                        "kind": "keyboard.shortcut",
                        "args": {"keys": ["ctrl", "s"]},
                        "reason": "Use the standard save shortcut.",
                        "pause_ms": 120,
                    }
                ],
            },
            mode=mode,
        )
    return None


def _assistant_reply_from_plan(plan: dict[str, Any], *, mode: str) -> str:
    if not isinstance(plan, dict):
        return ""
    summary = str(plan.get("summary", "")).strip() or "Francis prepared a desktop action."
    reasoning = plan.get("reasoning", []) if isinstance(plan.get("reasoning"), list) else []
    primary_reason = str(reasoning[0]).strip() if reasoning else ""
    if bool(plan.get("ready")):
        return f"{summary} {primary_reason}".strip()
    requirement = str(plan.get("mode_requirement", "pilot")).strip().lower() or "pilot"
    if requirement == "pilot" and mode != "pilot":
        return (
            f"{summary} Francis has the plan, but execution stays gated until you put Francis in Pilot. "
            f"{primary_reason}"
        ).strip()
    return f"{summary} {primary_reason}".strip()


def _build_orb_planner_messages(
    *,
    user_message: str,
    context_block: dict[str, Any],
    history: dict[str, Any],
) -> list[dict[str, str]]:
    recent_turns = history.get("recent_turns", []) if isinstance(history.get("recent_turns"), list) else []
    short_term = [
        {
            "role": str(turn.get("role", "assistant")).strip().lower() or "assistant",
            "content": str(turn.get("content", "")).strip(),
        }
        for turn in recent_turns[-10:]
        if isinstance(turn, dict) and str(turn.get("content", "")).strip()
    ]
    long_term = history.get("long_term_memory", {}) if isinstance(history.get("long_term_memory"), dict) else {}
    system_prompt = (
        "You are Francis speaking through the Orb. "
        "Francis is a governed autonomous operator, not a generic assistant. "
        "Every turn must stay grounded in explicit mode, posture, visible context, and receipts. "
        "You may prepare a desktop action plan, but you do not execute it. The shell executes the plan later. "
        "Return strict JSON with keys reply, thought, should_execute, mode_requirement, and plan. "
        "If planning a desktop action, plan only with these command kinds: keyboard.shortcut, keyboard.type, keyboard.key, mouse.move, mouse.click. "
        "Every step must include a reason explaining why that interaction is the right human-like path, including left versus right click reasoning when relevant. "
        "For opening Windows applications, do not launch processes directly; navigate through Start/search/open. "
        "Keep reply text calm, specific, and short enough for an Orb chat window."
    )
    return [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": (
                f"Long-term memory:\n{json.dumps(long_term, ensure_ascii=False)}\n\n"
                f"Recent conversation:\n{json.dumps(short_term, ensure_ascii=False)}\n\n"
                f"Live Francis state:\n{json.dumps(context_block, ensure_ascii=False)}\n\n"
                f"User turn:\n{user_message}"
            ),
        },
    ]


def _call_orb_planner(
    *,
    user_message: str,
    context_block: dict[str, Any],
    history: dict[str, Any],
    mode: str,
) -> dict[str, Any]:
    parsed: dict[str, Any] | None = None
    raw_content = ""
    try:
        response = chat(
            "orb.desktop_analysis.operator_loop",
            _build_orb_planner_messages(
                user_message=user_message,
                context_block=context_block,
                history=history,
            ),
            timeout=60.0,
            options={"temperature": 0.15},
        )
        if isinstance(response, dict):
            message_payload = response.get("message", {})
            if isinstance(message_payload, dict):
                raw_content = str(message_payload.get("content", "")).strip()
            elif response.get("response"):
                raw_content = str(response.get("response", "")).strip()
        parsed = _extract_json_object(raw_content)
    except Exception:
        parsed = None

    if not isinstance(parsed, dict):
        plan = _heuristic_orb_desktop_plan(user_message, mode=mode)
        return {
            "reply": _assistant_reply_from_plan(plan, mode=mode) if plan else "Francis can continue in chat, but this turn did not produce a grounded desktop plan.",
            "thought": "",
            "plan": plan,
            "reply_kind": "planner_fallback" if plan else "planner_error",
        }

    plan = _normalize_orb_desktop_plan(parsed.get("plan"), mode=mode)
    reply = str(parsed.get("reply", "")).strip() or _assistant_reply_from_plan(plan, mode=mode)
    thought = str(parsed.get("thought", "")).strip()
    return {
        "reply": reply or "Francis answered without reply text.",
        "thought": thought,
        "plan": plan,
        "reply_kind": "planner",
    }


def _summarize_long_term_memory(
    *,
    history: dict[str, Any],
    user_message: str,
    assistant_reply: str,
) -> dict[str, Any] | None:
    long_term = history.get("long_term_memory", {}) if isinstance(history.get("long_term_memory"), dict) else {}
    recent_turns = history.get("recent_turns", []) if isinstance(history.get("recent_turns"), list) else []
    if long_term.get("summary") and len(recent_turns) % 4 != 0:
        return None
    try:
        response = chat(
            "orb.long_term_memory.synthesis",
            [
                {
                    "role": "system",
                    "content": (
                        "Summarize Orb conversation continuity into strict JSON with keys "
                        "summary, preferences, operator_context, and open_loops. "
                        "Keep only durable information worth remembering across restarts."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "existing_memory": long_term,
                            "recent_turns": recent_turns[-12:],
                            "latest_user_turn": user_message,
                            "latest_assistant_turn": assistant_reply,
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            timeout=45.0,
            options={"temperature": 0.1},
        )
        raw = ""
        if isinstance(response, dict):
            message_payload = response.get("message", {})
            if isinstance(message_payload, dict):
                raw = str(message_payload.get("content", "")).strip()
            elif response.get("response"):
                raw = str(response.get("response", "")).strip()
        parsed = _extract_json_object(raw)
        if not isinstance(parsed, dict):
            return None
        return {
            "summary": str(parsed.get("summary", "")).strip(),
            "preferences": parsed.get("preferences", []),
            "operator_context": parsed.get("operator_context", []),
            "open_loops": parsed.get("open_loops", []),
            "conversation_count": int(long_term.get("conversation_count", 0) or 0) + 1,
        }
    except Exception:
        fallback_summary = str(long_term.get("summary", "")).strip()
        if not fallback_summary:
            fallback_summary = assistant_reply
        return {
            **long_term,
            "summary": fallback_summary[:1000],
            "conversation_count": int(long_term.get("conversation_count", 0) or 0) + 1,
        }


def get_orb_view(
    *,
    max_actions: int = 8,
    snapshot: dict[str, Any] | None = None,
    actions: dict[str, Any] | None = None,
    voice: dict[str, Any] | None = None,
    include_perception_frame: bool = False,
) -> dict[str, object]:
    snapshot = snapshot if isinstance(snapshot, dict) else build_lens_snapshot()
    actions = actions if isinstance(actions, dict) else get_lens_actions(max_actions=max_actions)
    voice = voice if isinstance(voice, dict) else build_operator_presence(
        mode=str(snapshot.get("control", {}).get("mode", "assist")),
        max_actions=min(max_actions, 3),
        snapshot=snapshot,
        actions_payload=actions,
    )
    orb = build_orb_state(
        mode=str(snapshot.get("control", {}).get("mode", "assist")),
        snapshot=snapshot,
        actions_payload=actions,
        voice=voice,
    )
    orb["authority"] = get_orb_authority_view()
    orb["perception"] = get_orb_perception_view(include_frame_data=include_perception_frame)
    orb["operator"] = _build_orb_operator_view(snapshot=snapshot, actions=actions)
    orb["interjection"] = _build_orb_interjection_view(
        snapshot=snapshot,
        actions=actions,
        operator=orb["operator"],
    )
    orb["thought"] = _build_orb_thought_view(
        operator=orb["operator"],
        interjection=orb["interjection"],
    )
    return orb


def build_orb_chat_reply(
    *,
    message: str,
    conversation_id: str = DEFAULT_ORB_CONVERSATION_ID,
    max_actions: int = 4,
) -> dict[str, Any]:
    snapshot = build_lens_snapshot()
    actions = get_lens_actions(max_actions=max_actions)
    voice = build_operator_presence(
        mode=str(snapshot.get("control", {}).get("mode", "assist")),
        max_actions=min(max_actions, 3),
        snapshot=snapshot,
        actions_payload=actions,
    )
    orb = get_orb_view(
        max_actions=max_actions,
        snapshot=snapshot,
        actions=actions,
        voice=voice,
    )
    perception = get_orb_perception_view(include_frame_data=False)
    user_message = str(message or "").strip()
    if not user_message:
        raise ValueError("Orb chat message is required.")
    normalized_conversation_id = (
        DEFAULT_ORB_CONVERSATION_ID if not conversation_id else str(conversation_id).strip() or DEFAULT_ORB_CONVERSATION_ID
    )
    history = build_orb_chat_history(normalized_conversation_id)

    direct_reply = _build_orb_direct_chat_reply(message=user_message, orb=orb, perception=perception)
    if direct_reply:
        append_orb_turn(
            conversation_id=normalized_conversation_id,
            role="user",
            content=user_message,
            kind="chat",
            source="orb.chat",
        )
        append_orb_turn(
            conversation_id=normalized_conversation_id,
            role="assistant",
            content=direct_reply,
            kind="chat",
            source="orb.chat.direct",
            metadata={"reply_kind": "direct"},
        )
        refreshed_history = build_orb_chat_history(normalized_conversation_id)
        return {
            "status": "ok",
            "reply": direct_reply,
            "reply_kind": "direct",
            "conversation": refreshed_history,
            "memory": {
                "conversation_id": refreshed_history.get("conversation_id", normalized_conversation_id),
                "short_term": refreshed_history.get("short_term_memory", {}),
                "long_term": refreshed_history.get("long_term_memory", {}),
            },
            "plan": None,
            "execution": {
                "ready": False,
                "mode_requirement": "pilot",
                "auto_execute": False,
            },
            "thought": None,
            "orb": {
                "mode": orb.get("mode"),
                "posture": orb.get("posture"),
                "summary": orb.get("summary"),
                "operator": orb.get("operator"),
                "interjection": orb.get("interjection"),
                "thought": orb.get("thought"),
            },
            "perception": {
                "state": perception.get("state"),
                "summary": perception.get("summary"),
                "detail_summary": perception.get("detail_summary"),
                "captured_at": perception.get("captured_at"),
                "freshness": perception.get("freshness"),
                "window": perception.get("window"),
            },
        }

    planned = build_orb_chat_plan(
        message=user_message,
        orb_context={
            "mode": orb.get("mode"),
            "posture": orb.get("posture"),
            "summary": orb.get("summary"),
            "detail": orb.get("detail"),
            "operator": orb.get("operator"),
            "interjection": orb.get("interjection"),
            "authority": orb.get("authority"),
            "run_state": snapshot.get("runs", {}).get("last_run", {}),
        },
        perception=perception,
        snapshot=snapshot,
        short_term_messages=history.get("recent_turns", []),
        long_term_memory=history.get("long_term_memory", {}),
    )
    content = str(planned.get("reply", "")).strip() or "Orb chat is live, but no response text was returned."
    plan = planned.get("plan") if isinstance(planned.get("plan"), dict) else None
    thought_text = str(planned.get("thought", "")).strip()
    thought_summary = thought_text or (str(plan.get("summary", "")).strip() if isinstance(plan, dict) else "")
    thought_payload = None
    if thought_summary:
        thought_payload = {
            "id": _hash_orb_thought_id(normalized_conversation_id, user_message, thought_summary),
            "source": "orb.chat",
            "summary": thought_summary,
            "detail": content,
            "visible": True,
        }

    append_orb_turn(
        conversation_id=normalized_conversation_id,
        role="user",
        content=user_message,
        kind="chat",
        source="orb.chat",
    )
    append_orb_turn(
        conversation_id=normalized_conversation_id,
        role="assistant",
        content=content,
        kind="chat",
        source="orb.chat.planner",
        metadata={
            "reply_kind": "planner",
            "planner": str(planned.get("planner", "ollama")).strip() or "ollama",
            "plan_ready": bool(plan),
            "mode_requirement": str(plan.get("mode_requirement", "pilot")).strip() if isinstance(plan, dict) else "",
        },
    )
    refresh_orb_long_term_memory(
        conversation_id=normalized_conversation_id,
        snapshot=snapshot,
        perception=perception,
    )
    refreshed_history = build_orb_chat_history(normalized_conversation_id)

    execution_ready = bool(
        isinstance(plan, dict)
        and str(plan.get("mode_requirement", "pilot")).strip().lower() in {"pilot", "away"}
        and str(orb.get("mode", "assist")).strip().lower() in {"pilot", "away"}
    )
    return {
        "status": "ok",
        "reply": content,
        "reply_kind": "planner",
        "conversation": refreshed_history,
        "memory": {
            "conversation_id": refreshed_history.get("conversation_id", normalized_conversation_id),
            "short_term": refreshed_history.get("short_term_memory", {}),
            "long_term": refreshed_history.get("long_term_memory", {}),
        },
        "plan": plan,
        "execution": {
            "ready": execution_ready,
            "mode_requirement": str(plan.get("mode_requirement", "pilot")).strip() if isinstance(plan, dict) else "pilot",
            "auto_execute": False,
            "executor": "shell",
        },
        "thought": thought_payload,
        "orb": {
            "mode": orb.get("mode"),
            "posture": orb.get("posture"),
            "summary": orb.get("summary"),
            "operator": orb.get("operator"),
            "interjection": orb.get("interjection"),
            "thought": orb.get("thought"),
        },
        "perception": {
            "state": perception.get("state"),
            "summary": perception.get("summary"),
            "detail_summary": perception.get("detail_summary"),
            "captured_at": perception.get("captured_at"),
            "freshness": perception.get("freshness"),
            "window": perception.get("window"),
        },
        "planner": {
            "provider": str(planned.get("planner", "ollama")).strip() or "ollama",
            "planning_only": True,
        },
    }
