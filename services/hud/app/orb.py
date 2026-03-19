from __future__ import annotations

from typing import Any

from francis_llm import chat
from francis_presence.orb import build_orb_state
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
        if zone_kind not in {"francis_action_row", "francis_workspace", "francis_footer_actions"}:
            return None
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
                and str(row.get("kind", "")).strip().lower() in {"focus_click", "confirm_key"}
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
    return orb


def build_orb_chat_reply(*, message: str, max_actions: int = 4) -> dict[str, Any]:
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

    system_prompt = (
        "You are Francis speaking through the Orb. Respond briefly, concretely, and calmly. "
        "Stay grounded in the supplied Francis state. Do not invent visual facts that are not present. "
        "If perception is present, use it carefully as the current visible context. "
        "Keep responses short enough for a compact Orb chat surface."
    )
    context_block = {
        "mode": orb.get("mode"),
        "posture": orb.get("posture"),
        "summary": orb.get("summary"),
        "detail": orb.get("detail"),
        "authority": orb.get("authority"),
        "operator": orb.get("operator"),
        "interjection": orb.get("interjection"),
        "current_work": snapshot.get("current_work", {}),
        "objective": snapshot.get("objective", {}),
        "approvals": snapshot.get("approvals", {}),
        "runs": snapshot.get("runs", {}),
        "perception": {
            "state": perception.get("state"),
            "summary": perception.get("summary"),
            "detail_summary": perception.get("detail_summary"),
            "captured_at": perception.get("captured_at"),
            "display_id": perception.get("display_id"),
            "display": perception.get("display"),
            "cursor": perception.get("cursor"),
            "window": perception.get("window"),
            "freshness": perception.get("freshness"),
            "sensing": perception.get("sensing"),
            "cards": perception.get("cards"),
            "focus": {
                "width": perception.get("focus", {}).get("width"),
                "height": perception.get("focus", {}).get("height"),
                "has_image": bool(
                    perception.get("focus", {}).get("has_image")
                    or perception.get("focus", {}).get("data_url")
                ),
            },
            "frame": {
                "width": perception.get("frame", {}).get("width"),
                "height": perception.get("frame", {}).get("height"),
                "has_image": bool(
                    perception.get("frame", {}).get("has_image")
                    or perception.get("frame", {}).get("data_url")
                ),
            },
        },
    }

    content = ""
    try:
        response = chat(
            "orb.quick_chat.operator_loop",
            [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": (
                        f"Orb context:\n{context_block}\n\n"
                        f"User message:\n{user_message}"
                    ),
                },
            ],
            timeout=45.0,
            options={"temperature": 0.2},
        )
        if isinstance(response, dict):
            message_payload = response.get("message", {})
            if isinstance(message_payload, dict):
                content = str(message_payload.get("content", "")).strip()
            elif response.get("response"):
                content = str(response.get("response", "")).strip()
    except Exception as exc:  # pragma: no cover - fallback is verified at the route layer
        content = (
            "Orb chat stayed local, but the model route did not answer cleanly. "
            f"Current mode is {orb.get('mode')}, posture is {orb.get('posture')}, and the visible context summary is: "
            f"{perception.get('summary') or orb.get('summary')}. Error: {exc}"
        )

    return {
        "status": "ok",
        "reply": content or "Orb chat is live, but no response text was returned.",
        "orb": {
            "mode": orb.get("mode"),
            "posture": orb.get("posture"),
            "summary": orb.get("summary"),
            "operator": orb.get("operator"),
            "interjection": orb.get("interjection"),
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
