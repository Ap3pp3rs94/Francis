from __future__ import annotations

from typing import Any

from francis_llm import chat
from francis_presence.orb import build_orb_state
from services.hud.app.orb_authority import get_orb_authority_view
from services.hud.app.orb_perception import get_orb_perception_view
from services.hud.app.orchestrator_bridge import get_lens_actions
from services.hud.app.state import build_lens_snapshot
from services.hud.app.views.approval_queue import get_approval_queue_view
from services.hud.app.views.blocked_actions import get_blocked_actions_view
from services.hud.app.views.current_work import get_current_work_view
from services.hud.app.views.execution_journal import get_execution_journal_view
from services.hud.app.views.incidents import get_incidents_view
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


def _build_orb_operator_view(
    *,
    snapshot: dict[str, Any],
    actions: dict[str, Any],
) -> dict[str, Any]:
    current_work = get_current_work_view(snapshot=snapshot, actions=actions)
    approval_queue = get_approval_queue_view(snapshot=snapshot, actions=actions)
    journal = get_execution_journal_view(snapshot=snapshot)

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
    preview_enabled = bool(focus_action.get("enabled"))
    run_enabled = can_approve_and_run or preview_enabled
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
