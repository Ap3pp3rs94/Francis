from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from francis_brain.ledger import RunLedger
from francis_core.clock import utc_now_iso
from francis_core.config import settings
from francis_core.workspace_fs import WorkspaceFS

QUEUE_PATH = "orb/authority_queue.jsonl"
STATE_PATH = "orb/authority_state.json"
LOG_PATH = "logs/francis.log.jsonl"
DECISIONS_PATH = "journals/decisions.jsonl"
SUPPORTED_COMMAND_KINDS = {
    "mouse.move",
    "mouse.click",
    "mouse.drag",
    "keyboard.type",
    "keyboard.key",
    "keyboard.shortcut",
}
SUPPORTED_COMPLETE_STATUSES = {"completed", "failed", "released", "canceled"}
AUTHORITY_STATE_VALUES = {"human_active", "idle_armed", "francis_authority", "handback"}

_workspace_root = Path(settings.workspace_root).resolve()
_repo_root = _workspace_root.parent
_fs = WorkspaceFS(
    roots=[_workspace_root],
    journal_path=(_workspace_root / "journals" / "fs.jsonl").resolve(),
)
_ledger = RunLedger(_fs, rel_path="runs/run_ledger.jsonl")


def _read_json(rel_path: str, default: Any) -> Any:
    try:
        raw = _fs.read_text(rel_path)
    except Exception:
        return default
    try:
        return json.loads(raw)
    except Exception:
        return default



def _write_json(rel_path: str, value: Any) -> None:
    _fs.write_text(rel_path, json.dumps(value, ensure_ascii=False, indent=2))



def _read_jsonl(rel_path: str) -> list[dict[str, Any]]:
    try:
        raw = _fs.read_text(rel_path)
    except Exception:
        return []
    rows: list[dict[str, Any]] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except Exception:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows



def _write_jsonl(rel_path: str, rows: list[dict[str, Any]]) -> None:
    if not rows:
        _fs.write_text(rel_path, "")
        return
    payload = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
    _fs.write_text(rel_path, payload)



def _append_jsonl(rel_path: str, row: dict[str, Any]) -> None:
    rows = _read_jsonl(rel_path)
    rows.append(row)
    _write_jsonl(rel_path, rows)



def _default_state() -> dict[str, Any]:
    return {
        "surface": "orb_authority",
        "state": "human_active",
        "eligible": False,
        "live": False,
        "idle_seconds": 0.0,
        "idle_threshold_seconds": 30.0,
        "claimed_command_id": "",
        "reason": "",
        "updated_at": "",
        "actor": "",
        "last_human_return_at": "",
        "last_human_return_reason": "",
        "last_release_at": "",
        "last_release_reason": "",
    }



def _load_state() -> dict[str, Any]:
    state = _read_json(STATE_PATH, _default_state())
    if not isinstance(state, dict):
        return _default_state()
    merged = _default_state()
    merged.update(state)
    merged["state"] = str(merged.get("state", "human_active")).strip().lower() or "human_active"
    if merged["state"] not in AUTHORITY_STATE_VALUES:
        merged["state"] = "human_active"
    merged["eligible"] = bool(merged.get("eligible", False))
    merged["live"] = bool(merged.get("live", False))
    merged["idle_seconds"] = max(0.0, float(merged.get("idle_seconds", 0.0) or 0.0))
    merged["idle_threshold_seconds"] = max(1.0, float(merged.get("idle_threshold_seconds", 30.0) or 30.0))
    merged["claimed_command_id"] = str(merged.get("claimed_command_id", "")).strip()
    merged["reason"] = str(merged.get("reason", "")).strip()
    merged["actor"] = str(merged.get("actor", "")).strip()
    return merged



def _save_state(state: dict[str, Any]) -> dict[str, Any]:
    normalized = _default_state()
    normalized.update(state)
    normalized["state"] = str(normalized.get("state", "human_active")).strip().lower() or "human_active"
    if normalized["state"] not in AUTHORITY_STATE_VALUES:
        normalized["state"] = "human_active"
    normalized["eligible"] = bool(normalized.get("eligible", False))
    normalized["live"] = bool(normalized.get("live", False))
    normalized["idle_seconds"] = round(max(0.0, float(normalized.get("idle_seconds", 0.0) or 0.0)), 3)
    normalized["idle_threshold_seconds"] = round(max(1.0, float(normalized.get("idle_threshold_seconds", 30.0) or 30.0)), 3)
    normalized["claimed_command_id"] = str(normalized.get("claimed_command_id", "")).strip()
    normalized["reason"] = str(normalized.get("reason", "")).strip()
    normalized["actor"] = str(normalized.get("actor", "")).strip()
    normalized["updated_at"] = str(normalized.get("updated_at") or utc_now_iso())
    _write_json(STATE_PATH, normalized)
    return normalized


def _normalize_grounding(value: Any) -> dict[str, Any]:
    payload = value if isinstance(value, dict) else {}
    return {
        "title": str(payload.get("title", "")).strip(),
        "state": str(payload.get("state", "weak")).strip().lower() or "weak",
        "control_ready": bool(payload.get("control_ready", False)),
        "surface_kind": str(payload.get("surface_kind", "")).strip().lower(),
        "surface_label": str(payload.get("surface_label", "")).strip(),
        "zone_kind": str(payload.get("zone_kind", "")).strip().lower(),
        "zone_label": str(payload.get("zone_label", "")).strip(),
        "target_label": str(payload.get("target_label", "")).strip(),
        "confidence": str(payload.get("confidence", "low")).strip().lower() or "low",
        "stability": str(payload.get("stability", "idle")).strip().lower() or "idle",
        "window_match": str(payload.get("window_match", "weak")).strip().lower() or "weak",
        "primary_action_label": str(payload.get("primary_action_label", "")).strip(),
        "summary": str(payload.get("summary", "")).strip(),
        "detail": str(payload.get("detail", "")).strip(),
    }


def _normalize_policy_scope(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {
        "observation",
        "navigation",
        "click",
        "typing",
        "drag",
        "destructive",
        "cross_app_transfer",
        "sensitive",
    }:
        return normalized
    return "observation"


def _policy_scope_label(scope: str) -> str:
    return {
        "observation": "Observation",
        "navigation": "Navigation",
        "click": "Click",
        "typing": "Typing",
        "drag": "Drag",
        "destructive": "Destructive",
        "cross_app_transfer": "Cross-app transfer",
        "sensitive": "Sensitive",
    }.get(scope, "Observation")


def _text_contains_any(text: str, tokens: tuple[str, ...]) -> bool:
    lowered = str(text or "").strip().lower()
    return any(token in lowered for token in tokens)


def _derive_policy_scope(kind: str, args: dict[str, Any] | None = None) -> str:
    normalized_kind = str(kind or "").strip().lower()
    normalized_args = args if isinstance(args, dict) else {}
    if bool(normalized_args.get("cross_app")) or bool(normalized_args.get("transfer")):
        return "cross_app_transfer"
    if str(normalized_args.get("source_app", "")).strip() and str(normalized_args.get("target_app", "")).strip():
        return "cross_app_transfer"
    if bool(normalized_args.get("sensitive")):
        return "sensitive"
    if normalized_kind == "mouse.drag":
        return "drag"
    if normalized_kind == "mouse.click":
        return "click"
    if normalized_kind == "mouse.move":
        return "navigation"
    if normalized_kind.startswith("keyboard."):
        if _text_contains_any(str(normalized_args.get("text", "")), ("password", "token", "secret", "credential")):
            return "sensitive"
        return "typing"
    if _text_contains_any(normalized_kind, ("delete", "remove", "revoke", "destroy", "kill")):
        return "destructive"
    return "observation"


def _normalize_policy(value: Any, *, row: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = value if isinstance(value, dict) else {}
    source_row = row if isinstance(row, dict) else {}
    normalized_kind = str(payload.get("kind", source_row.get("kind", ""))).strip().lower()
    normalized_args = source_row.get("args") if isinstance(source_row.get("args"), dict) else {}
    scope = _normalize_policy_scope(payload.get("scope"))
    if scope == "observation" and not str(payload.get("scope", "")).strip():
        scope = _derive_policy_scope(normalized_kind, normalized_args)
    scope_label = _policy_scope_label(scope)
    explicit_state = str(payload.get("state", "")).strip().lower()
    requires_approval = bool(payload.get("requires_approval", False))
    if explicit_state in {"approval_required", "policy_blocked", "allowed", "observe_only"}:
        state = explicit_state
    elif requires_approval:
        state = "approval_required"
    else:
        state = "allowed"
    risk_tier = str(payload.get("risk_tier", "")).strip().lower()
    if not risk_tier:
        risk_tier = "high" if scope in {"destructive", "cross_app_transfer", "sensitive"} else "medium" if scope in {"click", "drag", "typing"} else "low"
    policy_reason = str(payload.get("policy_reason", source_row.get("reason", ""))).strip()
    if state == "approval_required":
        summary = str(payload.get("summary", "")).strip() or f"Waiting approval before {scope_label.lower()}."
        detail = str(payload.get("detail", "")).strip() or policy_reason or f"{scope_label} action is held at the policy boundary."
    elif state == "policy_blocked":
        summary = str(payload.get("summary", "")).strip() or "Blocked by policy."
        detail = str(payload.get("detail", "")).strip() or policy_reason or f"{scope_label} action is outside the current governed boundary."
    elif state == "observe_only":
        summary = str(payload.get("summary", "")).strip() or "Observe only."
        detail = str(payload.get("detail", "")).strip() or "No active authority command is armed."
    else:
        summary = str(payload.get("summary", "")).strip() or f"Allowed {scope_label.lower()} inside scoped desktop control."
        detail = str(payload.get("detail", "")).strip() or policy_reason or f"{scope_label} action is within the current approved authority scope."
    return {
        "state": state,
        "scope": scope,
        "scope_label": scope_label,
        "risk_tier": risk_tier,
        "requires_approval": requires_approval or state == "approval_required",
        "policy_reason": policy_reason,
        "summary": summary,
        "detail": detail,
    }


def _normalize_execution_target(value: Any, *, fallback_args: dict[str, Any] | None = None) -> dict[str, Any] | None:
    payload = value if isinstance(value, dict) else {}
    args = fallback_args if isinstance(fallback_args, dict) else {}
    target_x = payload.get("x", payload.get("target_x", args.get("x")))
    target_y = payload.get("y", payload.get("target_y", args.get("y")))
    try:
        if target_x is None or target_y is None:
            return None
        return {
            "x": int(round(float(target_x))),
            "y": int(round(float(target_y))),
            "coordinate_space": str(
                payload.get("coordinate_space", payload.get("coordinateSpace", args.get("coordinate_space", args.get("coordinateSpace", "screen"))))
            ).strip().lower() or "screen",
        }
    except (TypeError, ValueError):
        return None


def _derive_execution_phase(kind: str, status: str) -> str:
    normalized_kind = str(kind or "").strip().lower()
    normalized_status = str(status or "queued").strip().lower() or "queued"
    if normalized_status in {"released", "canceled"}:
        return "interrupted"
    if normalized_status == "failed":
        return "blocked"
    if normalized_status == "hover_ready":
        return "hover_ready"
    if normalized_status == "completed":
        if normalized_kind == "mouse.click":
            return "click_act"
        if normalized_kind == "mouse.drag":
            return "drag_act"
        if normalized_kind.startswith("keyboard."):
            return "type_hold"
        return "commit_move"
    if normalized_kind.startswith("keyboard."):
        return "type_hold"
    return "commit_move"


def _derive_execution_summary(kind: str, phase: str, status: str) -> str:
    normalized_kind = str(kind or "").strip().lower()
    normalized_phase = str(phase or "").strip().lower() or "commit_move"
    normalized_status = str(status or "queued").strip().lower() or "queued"
    if normalized_phase == "interrupted":
        return "Yielding cleanly."
    if normalized_phase == "blocked":
        return "Execution blocked." if normalized_status == "failed" else "Backing off to reassess."
    if normalized_phase == "hover_ready":
        return "Holding poised contact before click."
    if normalized_phase == "click_act":
        return "Click committed cleanly." if normalized_status == "completed" else "Click is committing now."
    if normalized_phase == "drag_act":
        return "Drag completed cleanly." if normalized_status == "completed" else "Anchored drag control is live."
    if normalized_phase == "type_hold":
        if normalized_kind == "keyboard.shortcut":
            return "Shortcut committed cleanly." if normalized_status == "completed" else "Holding the active shortcut lane."
        if normalized_kind == "keyboard.key":
            return "Key committed cleanly." if normalized_status == "completed" else "Holding the active key lane."
        return "Typing completed cleanly." if normalized_status == "completed" else "Holding the active typing lane."
    if normalized_kind == "mouse.click":
        return "Committed to the grounded click point."
    if normalized_kind == "mouse.drag":
        return "Committing to the drag path."
    if normalized_kind == "mouse.move":
        return "Move completed cleanly." if normalized_status == "completed" else "Travelling directly to the grounded point."
    return "Committing to the execution path."


def _derive_execution_detail(kind: str, phase: str, status: str) -> str:
    normalized_kind = str(kind or "").strip().lower()
    normalized_phase = str(phase or "").strip().lower() or "commit_move"
    normalized_status = str(status or "queued").strip().lower() or "queued"
    if normalized_phase == "interrupted":
        return "Francis released execution posture deliberately and yielded control."
    if normalized_phase == "blocked":
        return (
            "The command could not complete cleanly, so Francis is holding a blocked execution posture."
            if normalized_status == "failed"
            else "Francis backed off the action path and is reassessing before recommitting."
        )
    if normalized_phase == "hover_ready":
        return "Francis is holding directly over the target so contact reads as intentional before actuation."
    if normalized_phase == "click_act":
        return "Francis is pulsing a short, controlled click directly through the grounded target."
    if normalized_phase == "drag_act":
        return "Francis is maintaining anchored contact and tension across the drag path."
    if normalized_phase == "type_hold":
        if normalized_kind == "keyboard.shortcut":
            return "Francis is holding a stable execution posture while the shortcut commits through the active context."
        if normalized_kind == "keyboard.key":
            return "Francis is holding a stable execution posture while the key commits through the active context."
        return "Francis is holding a stable execution posture while typing through the active context."
    if normalized_kind == "mouse.drag":
        return "Francis is advancing with resolve into the drag path before sustained contact takes over."
    if normalized_kind == "mouse.click":
        return "Francis is advancing with resolve toward the grounded click point."
    if normalized_kind == "mouse.move":
        return "Francis is physically travelling to the grounded execution point."
    return "Francis is advancing directly into the execution path."


def _normalize_execution(value: Any, *, row: dict[str, Any] | None = None, status: str = "") -> dict[str, Any]:
    payload = value if isinstance(value, dict) else {}
    source_row = row if isinstance(row, dict) else {}
    normalized_kind = str(payload.get("kind", source_row.get("kind", ""))).strip().lower()
    normalized_status = str(status or source_row.get("status", "queued")).strip().lower() or "queued"
    phase = str(payload.get("phase", "")).strip().lower() or _derive_execution_phase(normalized_kind, normalized_status)
    target = _normalize_execution_target(payload.get("target"), fallback_args=source_row.get("args") if isinstance(source_row.get("args"), dict) else {})
    summary = str(payload.get("summary", "")).strip() or _derive_execution_summary(normalized_kind, phase, normalized_status)
    detail = str(payload.get("detail", "")).strip() or _derive_execution_detail(normalized_kind, phase, normalized_status)
    return {
        "kind": normalized_kind,
        "phase": phase,
        "body_state_hint": str(payload.get("body_state_hint", "")).strip().lower() or phase,
        "summary": summary,
        "detail": detail,
        "target": target,
        "hover_ready_capable": bool(payload.get("hover_ready_capable", normalized_kind == "mouse.click")),
        "click_pulse": bool(payload.get("click_pulse", phase == "click_act")),
        "sustained_contact": bool(payload.get("sustained_contact", phase in {"drag_act", "type_hold"})),
    }


def _payload_value(payload: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in payload:
            return payload[key]
    return None


def _normalize_bounds(value: Any) -> dict[str, Any] | None:
    payload = value if isinstance(value, dict) else {}
    try:
        x = _payload_value(payload, "x")
        y = _payload_value(payload, "y")
        width = _payload_value(payload, "width")
        height = _payload_value(payload, "height")
        if x is None and y is None and width is None and height is None:
            return None
        return {
            "x": int(round(float(x or 0))),
            "y": int(round(float(y or 0))),
            "width": max(0, int(round(float(width or 0)))),
            "height": max(0, int(round(float(height or 0)))),
        }
    except (TypeError, ValueError):
        return None


def _normalize_foreground_window(value: Any) -> dict[str, Any]:
    payload = value if isinstance(value, dict) else {}
    return {
        "title": str(_payload_value(payload, "title") or "").strip(),
        "process": str(_payload_value(payload, "process") or "").strip(),
        "pid": int(_payload_value(payload, "pid") or 0) or None,
        "elevated": bool(_payload_value(payload, "elevated")),
        "fullscreen_like": bool(_payload_value(payload, "fullscreen_like", "fullscreenLike")),
        "display_label": str(_payload_value(payload, "host_display_label", "hostDisplayLabel") or "").strip(),
        "bounds": _normalize_bounds(_payload_value(payload, "bounds")),
    }


def _normalize_desktop_authority_limit(value: Any) -> dict[str, Any] | None:
    payload = value if isinstance(value, dict) else {}
    key = str(_payload_value(payload, "key") or "").strip()
    summary = str(_payload_value(payload, "summary") or "").strip()
    if not key and not summary:
        return None
    return {
        "key": key,
        "scope": str(_payload_value(payload, "scope") or "").strip(),
        "severity": str(_payload_value(payload, "severity") or "").strip().lower() or "low",
        "summary": summary,
        "fallback": str(_payload_value(payload, "fallback") or "").strip(),
    }


def _normalize_desktop_authority(value: Any) -> dict[str, Any]:
    payload = value if isinstance(value, dict) else {}
    active_limitations = [
        normalized
        for normalized in (
            _normalize_desktop_authority_limit(row)
            for row in (_payload_value(payload, "active_limitations", "activeLimitations") or [])
        )
        if normalized is not None
    ][:4]
    fallback_payload = _payload_value(payload, "fallback_posture", "fallbackPosture")
    fallback = fallback_payload if isinstance(fallback_payload, dict) else {}
    return {
        "mode": str(_payload_value(payload, "mode") or "").strip().lower(),
        "summary": str(_payload_value(payload, "summary") or "").strip(),
        "target_display_label": str(
            _payload_value(
                _payload_value(payload, "target_display", "targetDisplay") or {},
                "label",
            )
            or ""
        ).strip(),
        "active_display_label": str(
            _payload_value(
                _payload_value(payload, "active_display", "activeDisplay") or {},
                "label",
            )
            or ""
        ).strip(),
        "topmost_level": str(_payload_value(payload, "topmost_level", "topmostLevel") or "").strip(),
        "fallback_mode": str(_payload_value(fallback, "mode") or "").strip().lower(),
        "fallback_summary": str(_payload_value(fallback, "summary") or "").strip(),
        "active_limitations": active_limitations,
    }


def _normalize_receipt_target(
    *,
    grounding: dict[str, Any],
    execution: dict[str, Any],
) -> dict[str, Any]:
    target_payload = execution.get("target") if isinstance(execution.get("target"), dict) else {}
    return {
        "label": (
            str(grounding.get("primary_action_label", "")).strip()
            or str(grounding.get("target_label", "")).strip()
            or str(grounding.get("zone_label", "")).strip()
        ),
        "x": int(target_payload.get("x")) if isinstance(target_payload.get("x"), int) else None,
        "y": int(target_payload.get("y")) if isinstance(target_payload.get("y"), int) else None,
        "coordinate_space": str(target_payload.get("coordinate_space", "")).strip().lower() or "",
    }


def _normalize_surface_context(
    *,
    grounding: dict[str, Any],
    window: dict[str, Any],
) -> dict[str, Any]:
    return {
        "kind": str(grounding.get("surface_kind", "")).strip().lower(),
        "label": str(grounding.get("surface_label", "")).strip() or str(window.get("title", "")).strip(),
        "zone_kind": str(grounding.get("zone_kind", "")).strip().lower(),
        "zone_label": str(grounding.get("zone_label", "")).strip(),
    }


def _normalize_authority_posture(
    value: Any,
    *,
    actor: str,
    status: str,
    human_returned: bool,
) -> dict[str, Any]:
    payload = value if isinstance(value, dict) else {}
    mode = str(_payload_value(payload, "mode", "state") or "").strip().lower()
    if not mode:
        if human_returned or status in {"released", "canceled"}:
            mode = "yielded"
        elif status == "claimed":
            mode = "francis_authority"
        elif status == "completed":
            mode = "completed"
        elif status == "failed":
            mode = "blocked"
        else:
            mode = status or "queued"
    summary = str(_payload_value(payload, "summary") or "").strip()
    if not summary:
        if mode == "yielded":
            summary = "Francis yielded authority cleanly."
        elif mode == "francis_authority":
            summary = "Francis held live execution authority."
        elif mode == "blocked":
            summary = "Authority execution was blocked."
        elif mode == "completed":
            summary = "Authority execution completed cleanly."
        else:
            summary = "Authority posture recorded."
    return {
        "mode": mode,
        "actor": str(actor or "").strip(),
        "summary": summary,
    }


def _normalize_interruption(
    value: Any,
    *,
    status: str,
    detail: str,
    human_returned: bool,
) -> dict[str, Any]:
    payload = value if isinstance(value, dict) else {}
    state = str(_payload_value(payload, "state", "kind") or "").strip().lower()
    lowered_detail = str(detail or "").strip().lower()
    if not state:
        if human_returned:
            state = "user_override"
        elif status == "released":
            state = "yielded"
        elif status == "canceled" and "panic" in lowered_detail:
            state = "panic_stop"
        elif status == "canceled" and "pause" in lowered_detail:
            state = "paused"
        elif status == "canceled":
            state = "canceled"
    summary = str(_payload_value(payload, "summary") or "").strip()
    detail_text = str(_payload_value(payload, "detail") or detail).strip()
    if not summary:
        if state == "user_override":
            summary = "Interrupted locally by user override."
        elif state == "panic_stop":
            summary = "Interrupted by panic stop."
        elif state == "paused":
            summary = "Execution paused at the local authority boundary."
        elif state == "yielded":
            summary = "Francis yielded authority cleanly."
        elif state == "canceled":
            summary = "Execution canceled before completion."
    return {
        "state": state,
        "summary": summary,
        "detail": detail_text,
    }


def _normalize_replay_step(value: Any) -> dict[str, Any] | None:
    payload = value if isinstance(value, dict) else {}
    kind = str(_payload_value(payload, "kind") or "").strip().lower()
    reason = str(_payload_value(payload, "reason") or "").strip()
    if not kind and not reason:
        return None
    execution_payload = _payload_value(payload, "execution")
    execution = execution_payload if isinstance(execution_payload, dict) else {}
    return {
        "index": int(_payload_value(payload, "index") or 0),
        "kind": kind,
        "status": str(_payload_value(payload, "status") or "").strip().lower(),
        "reason": reason,
        "phase": str(_payload_value(execution, "phase") or "").strip().lower(),
        "summary": str(_payload_value(execution, "summary") or "").strip(),
    }


def _normalize_replay(
    value: Any,
    *,
    kind: str,
    status: str,
    summary_text: str,
    execution: dict[str, Any],
    target: dict[str, Any],
    detail: str,
) -> dict[str, Any]:
    payload = value if isinstance(value, dict) else {}
    source_steps = _payload_value(payload, "steps")
    steps = [
        normalized
        for normalized in (_normalize_replay_step(row) for row in (source_steps or []))
        if normalized is not None
    ][:12]
    if not steps and kind:
        steps.append(
            {
                "index": 0,
                "kind": kind,
                "status": status,
                "reason": str(detail or summary_text).strip(),
                "phase": str(execution.get("phase", "")).strip().lower(),
                "summary": str(execution.get("summary", "")).strip() or str(summary_text or "").strip(),
            }
        )
    step_count = int(_payload_value(payload, "step_count", "stepCount") or len(steps) or 0)
    completed_steps = int(_payload_value(payload, "completed_steps", "completedSteps") or min(len(steps), step_count))
    return {
        "source": str(_payload_value(payload, "source") or "operator_receipt").strip().lower() or "operator_receipt",
        "step_count": max(step_count, len(steps)),
        "completed_steps": max(0, completed_steps),
        "target": target,
        "steps": steps,
    }


def _make_card(label: str, value: str, tone: str = "low") -> dict[str, Any] | None:
    normalized_label = str(label or "").strip()
    normalized_value = str(value or "").strip()
    if not normalized_label or not normalized_value:
        return None
    return {
        "label": normalized_label,
        "value": normalized_value,
        "tone": str(tone or "low").strip().lower() or "low",
    }


def _receipt_card_priority(row: dict[str, Any]) -> int:
    label = str(row.get("label", "")).strip().lower()
    tone = str(row.get("tone", "low")).strip().lower()
    label_weight = {
        "policy": 120,
        "interruption": 118,
        "execution": 112,
        "desktop": 108,
        "authority": 104,
        "target": 98,
        "window": 92,
        "grounding": 88,
        "status": 84,
        "command": 80,
        "conversation": 72,
        "plan": 68,
        "steps": 64,
        "mode": 60,
        "kind": 12,
        "run": 8,
    }.get(label, 20)
    tone_weight = {"high": 12, "medium": 6, "low": 0}.get(tone, 0)
    return label_weight + tone_weight


def _rank_receipt_cards(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: dict[str, dict[str, Any]] = {}
    for row in cards:
        if not isinstance(row, dict):
            continue
        label = str(row.get("label", "")).strip()
        value = str(row.get("value", "")).strip()
        if not label or not value:
            continue
        key = label.lower()
        next_row = {"label": label, "value": value, "tone": str(row.get("tone", "low")).strip().lower() or "low"}
        previous = deduped.get(key)
        if previous is None or _receipt_card_priority(next_row) > _receipt_card_priority(previous):
            deduped[key] = next_row
    return sorted(deduped.values(), key=_receipt_card_priority, reverse=True)[:8]


def _build_receipt_flags(
    *,
    kind: str,
    status: str,
    policy: dict[str, Any],
    execution: dict[str, Any],
    interruption: dict[str, Any],
    desktop_authority: dict[str, Any],
) -> dict[str, Any]:
    return {
        "policy_hold": str(policy.get("state", "")).strip().lower() == "approval_required",
        "policy_blocked": str(policy.get("state", "")).strip().lower() == "policy_blocked",
        "interrupted": bool(str(interruption.get("state", "")).strip()),
        "failed": status == "failed" or str(execution.get("phase", "")).strip().lower() == "blocked",
        "desktop_fallback": bool(desktop_authority.get("active_limitations")),
        "approval_event": str(kind or "").strip().lower().startswith("approval."),
        "execution_event": bool(str(execution.get("phase", "")).strip()),
    }


def _build_receipt_priority(*, flags: dict[str, Any], status: str) -> int:
    priority = 100
    if flags.get("policy_blocked"):
        priority += 900
    elif flags.get("policy_hold"):
        priority += 860
    elif flags.get("interrupted"):
        priority += 820
    elif flags.get("failed"):
        priority += 780
    elif status == "completed":
        priority += 720
    elif status == "claimed":
        priority += 640
    elif status == "queued":
        priority += 520
    if flags.get("desktop_fallback"):
        priority += 80
    if flags.get("approval_event"):
        priority += 40
    return priority


def _derive_review_summary(
    *,
    summary_text: str,
    policy: dict[str, Any],
    interruption: dict[str, Any],
    execution: dict[str, Any],
    desktop_authority: dict[str, Any],
    target: dict[str, Any],
) -> str:
    policy_state = str(policy.get("state", "")).strip().lower()
    interruption_summary = str(interruption.get("summary", "")).strip()
    execution_summary = str(execution.get("summary", "")).strip()
    target_label = str(target.get("label", "")).strip()
    if policy_state == "policy_blocked":
        return str(policy.get("summary", "")).strip() or "Policy blocked"
    if policy_state == "approval_required":
        return "Policy hold"
    if interruption_summary:
        return interruption_summary
    if summary_text:
        return summary_text
    if execution_summary:
        return execution_summary
    if desktop_authority.get("active_limitations") and target_label:
        return f"Desktop fallback while acting on {target_label}."
    return "Receipt recorded."


def _derive_review_detail(
    *,
    review_summary: str,
    summary_text: str,
    policy: dict[str, Any],
    interruption: dict[str, Any],
    execution: dict[str, Any],
    desktop_authority: dict[str, Any],
    window: dict[str, Any],
    target: dict[str, Any],
) -> str:
    parts = [
        str(review_summary or summary_text).strip(),
    ]
    target_label = str(target.get("label", "")).strip()
    window_label = str(window.get("title", "")).strip() or str(window.get("process", "")).strip()
    if target_label and window_label:
        parts.append(f"Target: {target_label} in {window_label}.")
    elif target_label:
        parts.append(f"Target: {target_label}.")
    interruption_detail = str(interruption.get("detail", "")).strip()
    if interruption_detail:
        parts.append(interruption_detail)
    elif str(policy.get("detail", "")).strip():
        parts.append(str(policy.get("detail", "")).strip())
    elif str(execution.get("detail", "")).strip():
        parts.append(str(execution.get("detail", "")).strip())
    limitation = (desktop_authority.get("active_limitations") or [None])[0]
    if isinstance(limitation, dict) and str(limitation.get("summary", "")).strip():
        parts.append(str(limitation.get("summary", "")).strip())
    return " ".join(part for part in parts if part).strip() or "Receipt recorded."


def build_operator_receipt_summary(
    *,
    kind: str,
    status: str,
    summary_text: str,
    detail_text: str = "",
    actor: str = "",
    action_kind: str = "",
    command_kind: str = "",
    approval_id: str = "",
    decision: str = "",
    grounding: dict[str, Any] | None = None,
    policy: dict[str, Any] | None = None,
    execution: dict[str, Any] | None = None,
    authority: dict[str, Any] | None = None,
    desktop_authority: dict[str, Any] | None = None,
    foreground_window: dict[str, Any] | None = None,
    interruption: dict[str, Any] | None = None,
    replay: dict[str, Any] | None = None,
    human_returned: bool = False,
    presentation_cards: list[dict[str, Any]] | None = None,
    conversation_id: str = "",
) -> dict[str, Any]:
    normalized_kind = str(kind or "").strip()
    normalized_status = str(status or "").strip().lower()
    normalized_grounding = _normalize_grounding(grounding)
    normalized_policy = _normalize_policy(policy, row={"kind": command_kind or action_kind or normalized_kind})
    normalized_execution = _normalize_execution(execution, row={"kind": command_kind or action_kind or normalized_kind}, status=normalized_status)
    normalized_window = _normalize_foreground_window(foreground_window)
    normalized_target = _normalize_receipt_target(
        grounding=normalized_grounding,
        execution=normalized_execution,
    )
    normalized_surface = _normalize_surface_context(
        grounding=normalized_grounding,
        window=normalized_window,
    )
    normalized_desktop_authority = _normalize_desktop_authority(desktop_authority)
    normalized_authority = _normalize_authority_posture(
        authority,
        actor=actor,
        status=normalized_status,
        human_returned=human_returned,
    )
    normalized_interruption = _normalize_interruption(
        interruption,
        status=normalized_status,
        detail=str(detail_text or summary_text or "").strip(),
        human_returned=human_returned,
    )
    normalized_replay = _normalize_replay(
        replay,
        kind=command_kind or action_kind,
        status=normalized_status,
        summary_text=summary_text,
        execution=normalized_execution,
        target=normalized_target,
        detail=str(detail_text or summary_text or "").strip(),
    )
    flags = _build_receipt_flags(
        kind=normalized_kind,
        status=normalized_status,
        policy=normalized_policy,
        execution=normalized_execution,
        interruption=normalized_interruption,
        desktop_authority=normalized_desktop_authority,
    )
    review_summary = _derive_review_summary(
        summary_text=str(summary_text or "").strip(),
        policy=normalized_policy,
        interruption=normalized_interruption,
        execution=normalized_execution,
        desktop_authority=normalized_desktop_authority,
        target=normalized_target,
    )
    review_detail = _derive_review_detail(
        review_summary=review_summary,
        summary_text=str(summary_text or "").strip(),
        policy=normalized_policy,
        interruption=normalized_interruption,
        execution=normalized_execution,
        desktop_authority=normalized_desktop_authority,
        window=normalized_window,
        target=normalized_target,
    )

    candidate_cards = [
        _make_card("Policy", str(normalized_policy.get("summary", "")).strip(), "high" if flags.get("policy_blocked") else "medium"),
        _make_card("Interruption", str(normalized_interruption.get("summary", "")).strip(), "high"),
        _make_card("Execution", str(normalized_execution.get("summary", "")).strip(), "high" if normalized_status in {"completed", "failed"} else "medium"),
        _make_card("Desktop", str(((normalized_desktop_authority.get("active_limitations") or [None])[0] or {}).get("summary", "")).strip(), "high" if flags.get("desktop_fallback") else "low"),
        _make_card("Authority", str(normalized_authority.get("summary", "")).strip(), "medium"),
        _make_card("Target", str(normalized_target.get("label", "")).strip(), "medium" if normalized_grounding.get("control_ready") else "low"),
        _make_card("Window", str(normalized_window.get("title", "")).strip() or str(normalized_window.get("process", "")).strip(), "low"),
        _make_card("Grounding", str(normalized_grounding.get("summary", "")).strip(), "medium" if normalized_grounding.get("state") in {"concrete", "grounded", "tracking"} else "low"),
        _make_card("Status", normalized_status.replace("_", " "), "medium"),
        _make_card("Command", command_kind or action_kind, "medium"),
        _make_card("Conversation", conversation_id, "low"),
    ]
    if isinstance(presentation_cards, list):
        candidate_cards.extend(presentation_cards)

    priority = _build_receipt_priority(flags=flags, status=normalized_status)
    ranked_cards = _rank_receipt_cards([row for row in candidate_cards if row is not None])

    return {
        "receipt_version": 2,
        "receipt_priority": priority,
        "receipt_brief": review_summary,
        "review_summary": review_summary,
        "review_detail": review_detail,
        "receipt_flags": flags,
        "receipt_context": {
            "target": normalized_target,
            "surface": normalized_surface,
            "window": normalized_window,
            "authority": normalized_authority,
            "desktop_authority": normalized_desktop_authority,
            "interruption": normalized_interruption,
        },
        "replay": normalized_replay,
        "summary_text": str(summary_text or "").strip() or review_summary,
        "action_kind": str(action_kind or "").strip().lower(),
        "command_kind": str(command_kind or "").strip().lower(),
        "approval_id": str(approval_id or "").strip(),
        "decision": str(decision or "").strip().lower(),
        "status": normalized_status,
        "grounding_state": str(normalized_grounding.get("state", "weak")).strip().lower() or "weak",
        "grounding_summary": str(normalized_grounding.get("summary", "")).strip(),
        "grounding_control_ready": bool(normalized_grounding.get("control_ready", False)),
        "policy": normalized_policy,
        "policy_state": str(normalized_policy.get("state", "allowed")).strip().lower() or "allowed",
        "policy_scope": str(normalized_policy.get("scope", "observation")).strip().lower() or "observation",
        "policy_summary": str(normalized_policy.get("summary", "")).strip(),
        "execution": normalized_execution,
        "execution_phase": str(normalized_execution.get("phase", "")).strip().lower(),
        "execution_summary": str(normalized_execution.get("summary", "")).strip(),
        "presentation_cards": ranked_cards,
        "grounding": normalized_grounding,
    }


def _infer_receipt_status(payload: dict[str, Any], row: dict[str, Any] | None = None) -> str:
    raw = str(payload.get("status", "") or (row or {}).get("status", "")).strip().lower()
    if raw:
        return raw
    kind = str((row or {}).get("kind", "")).strip().lower()
    for candidate in ("completed", "failed", "claimed", "queued", "rejected", "approved", "canceled", "cancelled"):
        if kind.endswith(f".{candidate}"):
            if candidate == "cancelled":
                return "canceled"
            if candidate in {"approved", "rejected"}:
                return "completed"
            return candidate
    return ""


def normalize_operator_receipt_summary(summary: Any, *, row: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = summary if isinstance(summary, dict) else {}
    canonical = build_operator_receipt_summary(
        kind=str((row or {}).get("kind", "")),
        status=_infer_receipt_status(payload, row=row),
        summary_text=str(payload.get("summary_text", "")).strip()
        or str(payload.get("review_summary", "")).strip()
        or str(payload.get("receipt_brief", "")).strip()
        or (
            f"{str(payload.get('decision', '')).strip()} {str(payload.get('approval_id', '')).strip()}".strip()
            if str(payload.get("decision", "")).strip()
            else str(payload.get("action_kind", "")).strip() or str(payload.get("command_kind", "")).strip()
        ),
        detail_text=str(payload.get("review_detail", "")).strip(),
        actor=str(((row or {}).get("actor", ""))).strip(),
        action_kind=str(payload.get("action_kind", "")).strip(),
        command_kind=str(payload.get("command_kind", "")).strip(),
        approval_id=str(payload.get("approval_id", "")).strip(),
        decision=str(payload.get("decision", "")).strip().lower(),
        grounding=payload.get("grounding"),
        policy=payload.get("policy"),
        execution=payload.get("execution"),
        authority=(payload.get("receipt_context", {}) if isinstance(payload.get("receipt_context"), dict) else {}).get("authority"),
        desktop_authority=(payload.get("receipt_context", {}) if isinstance(payload.get("receipt_context"), dict) else {}).get("desktop_authority"),
        foreground_window=(payload.get("receipt_context", {}) if isinstance(payload.get("receipt_context"), dict) else {}).get("window"),
        interruption=(payload.get("receipt_context", {}) if isinstance(payload.get("receipt_context"), dict) else {}).get("interruption"),
        replay=payload.get("replay"),
        human_returned=bool(payload.get("human_returned", False)),
        presentation_cards=payload.get("presentation_cards") if isinstance(payload.get("presentation_cards"), list) else [],
        conversation_id=str(payload.get("conversation_id", "")).strip(),
    )
    if isinstance(payload.get("receipt_flags"), dict):
        canonical["receipt_flags"] = {
            **canonical.get("receipt_flags", {}),
            **payload["receipt_flags"],
        }
    if isinstance(payload.get("receipt_context"), dict):
        canonical["receipt_context"] = {
            **canonical.get("receipt_context", {}),
            **payload["receipt_context"],
        }
    if str(payload.get("review_summary", "")).strip():
        canonical["review_summary"] = str(payload.get("review_summary", "")).strip()
        canonical["receipt_brief"] = canonical["review_summary"]
    if str(payload.get("review_detail", "")).strip():
        canonical["review_detail"] = str(payload.get("review_detail", "")).strip()
    if payload.get("receipt_priority") is not None:
        try:
            canonical["receipt_priority"] = int(payload.get("receipt_priority") or canonical["receipt_priority"])
        except (TypeError, ValueError):
            pass
    return canonical


def _compact_command(row: dict[str, Any]) -> dict[str, Any]:
    args = row.get("args") if isinstance(row.get("args"), dict) else {}
    return {
        "id": str(row.get("id", "")).strip(),
        "run_id": str(row.get("run_id", "")).strip(),
        "trace_id": str(row.get("trace_id", "")).strip(),
        "ts": str(row.get("ts", "")).strip(),
        "kind": str(row.get("kind", "")).strip(),
        "status": str(row.get("status", "")).strip().lower(),
        "reason": str(row.get("reason", "")).strip(),
        "actor": str(row.get("actor", "")).strip(),
        "user": str(row.get("user", "")).strip(),
        "args": args,
        "claimed_at": str(row.get("claimed_at", "")).strip(),
        "claimed_by": str(row.get("claimed_by", "")).strip(),
        "completed_at": str(row.get("completed_at", "")).strip(),
        "detail": str(row.get("detail", "")).strip(),
        "grounding": _normalize_grounding(row.get("grounding")),
        "policy": _normalize_policy(row.get("policy"), row=row),
        "execution": _normalize_execution(
            row.get("execution") or ((row.get("result") or {}).get("execution") if isinstance(row.get("result"), dict) else None),
            row=row,
            status=str(row.get("status", "")).strip().lower(),
        ),
    }


def _present_command(row: dict[str, Any]) -> dict[str, Any]:
    compact = _compact_command(row)
    status = str(compact.get("status", "queued")).strip().lower() or "queued"
    actor = str(compact.get("claimed_by", "")).strip() or str(compact.get("actor", "")).strip()
    return {
        **compact,
        **_command_receipt_summary(
            row,
            status=status,
            actor=actor,
            human_returned=bool(status == "released" and "human" in str(row.get("detail", "")).strip().lower()),
        ),
    }


def _command_summary(row: dict[str, Any]) -> str:
    kind = str(row.get("kind", "command")).strip() or "command"
    reason = str(row.get("reason", "")).strip()
    status = str(row.get("status", "queued")).strip().lower() or "queued"
    if reason:
        return f"{kind} is {status}. {reason}".strip()
    return f"{kind} is {status}."


def _command_receipt_summary(
    row: dict[str, Any],
    *,
    status: str,
    actor: str,
    human_returned: bool = False,
) -> dict[str, Any]:
    normalized_status = str(status or row.get("status", "queued")).strip().lower() or "queued"
    grounding = _normalize_grounding(row.get("grounding"))
    policy = _normalize_policy(row.get("policy"), row=row)
    summary_text = _command_summary({**row, "status": normalized_status})
    grounding_summary = str(grounding.get("summary", "")).strip()
    if grounding_summary:
        summary_text = f"{summary_text} {grounding_summary}".strip()
    if policy.get("state") in {"approval_required", "policy_blocked"} and str(policy.get("summary", "")).strip():
        summary_text = f"{summary_text} {str(policy.get('summary', '')).strip()}".strip()
    execution = _normalize_execution(
        row.get("execution") or ((row.get("result") or {}).get("execution") if isinstance(row.get("result"), dict) else None),
        row=row,
        status=normalized_status,
    )
    result = row.get("result") if isinstance(row.get("result"), dict) else {}
    detail = str(row.get("detail", "")).strip()
    return {
        "command_id": str(row.get("id", "")).strip(),
        "actor": str(actor or "").strip(),
        "human_returned": bool(human_returned),
        **build_operator_receipt_summary(
            kind=f"orb.authority.command.{normalized_status}",
            status=normalized_status,
            summary_text=summary_text,
            detail_text=detail,
            actor=str(actor or "").strip(),
            action_kind=str(row.get("kind", "")).strip().lower(),
            command_kind=str(row.get("kind", "")).strip().lower(),
            grounding=grounding,
            policy=policy,
            execution=execution,
            authority=result.get("authority"),
            desktop_authority=result.get("desktop_authority"),
            foreground_window=result.get("foreground_window"),
            interruption=result.get("interruption"),
            replay=result.get("replay"),
            human_returned=human_returned,
            presentation_cards=[
                {"label": "Command", "value": str(row.get("kind", "unknown")).strip() or "unknown", "tone": "medium"},
                {
                    "label": "Status",
                    "value": normalized_status.replace("_", " "),
                    "tone": "high" if normalized_status in {"failed", "released"} else "medium",
                },
            ],
        ),
        "detail_text": detail,
    }



def _record_receipt(*, run_id: str, trace_id: str, kind: str, summary: dict[str, Any], detail: str, actor: str) -> dict[str, Any]:
    receipt = {
        "id": str(uuid4()),
        "ts": utc_now_iso(),
        "run_id": run_id,
        "trace_id": trace_id,
        "kind": kind,
        "actor": actor,
        "summary": summary,
        "detail": detail,
    }
    _append_jsonl(LOG_PATH, receipt)
    _append_jsonl(DECISIONS_PATH, receipt)
    _ledger.append(run_id=run_id, kind=kind, summary={"trace_id": trace_id, **summary})
    return receipt



def get_orb_authority_view(*, recent_limit: int = 8) -> dict[str, Any]:
    rows = _read_jsonl(QUEUE_PATH)
    state = _load_state()
    pending = [_compact_command(row) for row in rows if str(row.get("status", "")).strip().lower() == "queued"]
    claimed = [_compact_command(row) for row in rows if str(row.get("status", "")).strip().lower() == "claimed"]
    recent = [_present_command(row) for row in rows if str(row.get("status", "")).strip().lower() != "queued"]
    recent = list(reversed(recent[-max(1, recent_limit) :]))

    if state["live"]:
        summary = "Francis authority is live. The Orb may execute queued input commands until human return or panic stop."
        severity = "high"
    elif state["eligible"] and state["idle_seconds"] > 0:
        remaining = max(0.0, state["idle_threshold_seconds"] - state["idle_seconds"])
        summary = f"Away authority is armed. {remaining:.1f} seconds of collective inactivity remain before Francis may take control."
        severity = "medium"
    elif pending:
        summary = f"{len(pending)} queued Orb authority command(s) are waiting for lawful Away control."
        severity = "medium"
    else:
        summary = "No Orb authority commands are waiting. Human control remains primary."
        severity = "low"

    return {
        "surface": "orb_authority",
        "summary": summary,
        "severity": severity,
        "state": state,
        "pending_count": len(pending),
        "claimed_count": len(claimed),
        "pending": pending,
        "claimed": claimed,
        "recent": recent,
    }



def queue_orb_authority_command(
    *,
    kind: str,
    args: dict[str, Any] | None = None,
    reason: str = "",
    grounding: dict[str, Any] | None = None,
    policy: dict[str, Any] | None = None,
    actor: str = "hud.orb",
    user: str = "hud.operator",
    run_id: str | None = None,
    trace_id: str | None = None,
) -> dict[str, Any]:
    normalized_kind = str(kind or "").strip().lower()
    if normalized_kind not in SUPPORTED_COMMAND_KINDS:
        raise ValueError(f"Unsupported Orb authority command: {kind}")
    normalized_args = args if isinstance(args, dict) else {}
    effective_run_id = str(run_id or f"orb-authority:{uuid4()}").strip() or f"orb-authority:{uuid4()}"
    effective_trace_id = str(trace_id or effective_run_id).strip() or effective_run_id
    row = {
        "id": str(uuid4()),
        "ts": utc_now_iso(),
        "run_id": effective_run_id,
        "trace_id": effective_trace_id,
        "kind": normalized_kind,
        "args": normalized_args,
        "reason": str(reason or "").strip() or f"Execute {normalized_kind} through the Orb authority channel.",
        "actor": str(actor or "hud.orb").strip() or "hud.orb",
        "user": str(user or "hud.operator").strip() or "hud.operator",
        "status": "queued",
        "claimed_at": "",
        "claimed_by": "",
        "completed_at": "",
        "detail": "",
        "grounding": _normalize_grounding(grounding),
        "policy": _normalize_policy(policy, row={"kind": normalized_kind, "args": normalized_args, "reason": reason}),
        "execution": _normalize_execution(None, row={"kind": normalized_kind, "args": normalized_args, "status": "queued"}, status="queued"),
        "result": None,
    }
    _append_jsonl(QUEUE_PATH, row)
    receipt = _record_receipt(
        run_id=effective_run_id,
        trace_id=effective_trace_id,
        kind="orb.authority.command.queued",
        summary=_command_receipt_summary(row, status="queued", actor=row["actor"]),
        detail=_command_summary(row),
        actor=row["actor"],
    )
    return {
        "status": "ok",
        "run_id": effective_run_id,
        "trace_id": effective_trace_id,
        "receipt_id": receipt["id"],
        "command": _compact_command(row),
        "authority": get_orb_authority_view(),
    }



def record_orb_authority_state(*, state: str, eligible: bool, live: bool, idle_seconds: float, threshold_seconds: float, claimed_command_id: str = "", reason: str = "", actor: str = "electron.orb") -> dict[str, Any]:
    normalized_state = str(state or "human_active").strip().lower() or "human_active"
    if normalized_state not in AUTHORITY_STATE_VALUES:
        raise ValueError(f"Unsupported Orb authority state: {state}")
    existing = _load_state()
    updated = {
        **existing,
        "state": normalized_state,
        "eligible": bool(eligible),
        "live": bool(live),
        "idle_seconds": idle_seconds,
        "idle_threshold_seconds": threshold_seconds,
        "claimed_command_id": str(claimed_command_id or "").strip(),
        "reason": str(reason or "").strip(),
        "actor": str(actor or "electron.orb").strip() or "electron.orb",
    }
    if normalized_state == "handback":
        updated["last_human_return_at"] = utc_now_iso()
        updated["last_human_return_reason"] = updated["reason"]
        updated["last_release_at"] = updated["last_human_return_at"]
        updated["last_release_reason"] = updated["reason"]
    elif not live and updated["reason"]:
        updated["last_release_at"] = utc_now_iso()
        updated["last_release_reason"] = updated["reason"]
    saved = _save_state(updated)
    return get_orb_authority_view() | {"state": saved}



def claim_next_orb_authority_command(*, authority_live: bool, idle_seconds: float, threshold_seconds: float, actor: str = "electron.orb") -> dict[str, Any]:
    if not authority_live:
        record_orb_authority_state(
            state="idle_armed" if idle_seconds > 0 else "human_active",
            eligible=True,
            live=False,
            idle_seconds=idle_seconds,
            threshold_seconds=threshold_seconds,
            actor=actor,
            reason="Authority gate is not live yet.",
        )
        return {
            "status": "idle",
            "command": None,
            "authority": get_orb_authority_view(),
        }

    rows = _read_jsonl(QUEUE_PATH)
    for index, row in enumerate(rows):
        if str(row.get("status", "")).strip().lower() != "queued":
            continue
        rows[index] = {
            **row,
            "status": "claimed",
            "claimed_at": utc_now_iso(),
            "claimed_by": str(actor or "electron.orb").strip() or "electron.orb",
            "detail": "Claimed by the Orb shell for local execution.",
            "execution": _normalize_execution(
                row.get("execution"),
                row={**row, "status": "claimed"},
                status="claimed",
            ),
        }
        _write_jsonl(QUEUE_PATH, rows)
        command = rows[index]
        record_orb_authority_state(
            state="francis_authority",
            eligible=True,
            live=True,
            idle_seconds=idle_seconds,
            threshold_seconds=threshold_seconds,
            claimed_command_id=str(command.get("id", "")).strip(),
            actor=actor,
            reason="Francis authority is live in Away mode.",
        )
        receipt = _record_receipt(
            run_id=str(command.get("run_id", "")).strip() or f"orb-authority:{uuid4()}",
            trace_id=str(command.get("trace_id", "")).strip() or str(command.get("run_id", "")).strip() or str(uuid4()),
            kind="orb.authority.command.claimed",
            summary=_command_receipt_summary(command, status="claimed", actor=actor),
            detail=_command_summary(command),
            actor=actor,
        )
        return {
            "status": "ok",
            "receipt_id": receipt["id"],
            "command": _compact_command(command),
            "authority": get_orb_authority_view(),
        }

    record_orb_authority_state(
        state="francis_authority",
        eligible=True,
        live=True,
        idle_seconds=idle_seconds,
        threshold_seconds=threshold_seconds,
        actor=actor,
        reason="Authority is live, but no queued Orb command is waiting.",
    )
    return {
        "status": "empty",
        "command": None,
        "authority": get_orb_authority_view(),
    }



def complete_orb_authority_command(*, command_id: str, status: str, detail: str = "", result: dict[str, Any] | None = None, actor: str = "electron.orb", human_returned: bool = False) -> dict[str, Any]:
    normalized_id = str(command_id or "").strip()
    normalized_status = str(status or "").strip().lower()
    if not normalized_id:
        raise ValueError("command_id is required")
    if normalized_status not in SUPPORTED_COMPLETE_STATUSES:
        raise ValueError(f"Unsupported Orb authority completion status: {status}")

    rows = _read_jsonl(QUEUE_PATH)
    for index, row in enumerate(rows):
        if str(row.get("id", "")).strip() != normalized_id:
            continue
        rows[index] = {
            **row,
            "status": normalized_status,
            "completed_at": utc_now_iso(),
            "detail": str(detail or "").strip() or _command_summary({**row, "status": normalized_status}),
            "result": result if isinstance(result, dict) else None,
            "execution": _normalize_execution(
                (result or {}).get("execution") if isinstance(result, dict) else row.get("execution"),
                row={**row, "status": normalized_status},
                status=normalized_status,
            ),
        }
        _write_jsonl(QUEUE_PATH, rows)
        command = rows[index]
        state_reason = rows[index]["detail"]
        record_orb_authority_state(
            state="handback" if human_returned or normalized_status == "released" else "human_active" if normalized_status == "canceled" else "idle_armed",
            eligible=True,
            live=False,
            idle_seconds=0.0,
            threshold_seconds=30.0,
            claimed_command_id="",
            actor=actor,
            reason=state_reason,
        )
        receipt = _record_receipt(
            run_id=str(command.get("run_id", "")).strip() or f"orb-authority:{uuid4()}",
            trace_id=str(command.get("trace_id", "")).strip() or str(command.get("run_id", "")).strip() or str(uuid4()),
            kind=f"orb.authority.command.{normalized_status}",
            summary=_command_receipt_summary(
                command,
                status=normalized_status,
                actor=actor,
                human_returned=human_returned,
            ),
            detail=state_reason,
            actor=actor,
        )
        return {
            "status": "ok",
            "receipt_id": receipt["id"],
            "command": _compact_command(command),
            "authority": get_orb_authority_view(),
        }

    raise ValueError(f"Unknown Orb authority command: {normalized_id}")



def cancel_orb_authority_queue(
    *,
    reason: str,
    actor: str = "electron.orb",
    run_id: str | None = None,
    trace_id: str | None = None,
) -> dict[str, Any]:
    rows = _read_jsonl(QUEUE_PATH)
    changed = 0
    now = utc_now_iso()
    updated_rows: list[dict[str, Any]] = []
    for row in rows:
        status = str(row.get("status", "")).strip().lower()
        if status in {"queued", "claimed"}:
            changed += 1
            updated_rows.append(
                {
                    **row,
                    "status": "canceled",
                    "completed_at": now,
                    "detail": str(reason or "Orb authority queue was canceled.").strip() or "Orb authority queue was canceled.",
                }
            )
        else:
            updated_rows.append(row)
    _write_jsonl(QUEUE_PATH, updated_rows)
    saved = _save_state(
        {
            **_load_state(),
            "state": "human_active",
            "live": False,
            "claimed_command_id": "",
            "reason": str(reason or "").strip() or "Orb authority queue was canceled.",
            "last_release_at": now,
            "last_release_reason": str(reason or "").strip() or "Orb authority queue was canceled.",
            "actor": actor,
        }
    )
    effective_run_id = str(run_id or f"orb-authority:{uuid4()}").strip() or f"orb-authority:{uuid4()}"
    effective_trace_id = str(trace_id or effective_run_id).strip() or effective_run_id
    detail_text = str(reason or "Orb authority queue was canceled.").strip() or "Orb authority queue was canceled."
    receipt = _record_receipt(
        run_id=effective_run_id,
        trace_id=effective_trace_id,
        kind="orb.authority.queue.canceled",
        summary=build_operator_receipt_summary(
            kind="orb.authority.queue.canceled",
            status="canceled",
            summary_text=detail_text,
            detail_text=detail_text,
            actor=actor,
            action_kind="orb.authority.queue",
            command_kind="orb.authority.queue",
            authority={"state": "human_active", "summary": "Human control remained primary after queue cancellation."},
            interruption={"state": "canceled", "summary": "Queued authority work was canceled before execution.", "detail": detail_text},
            replay={"source": "orb_authority_queue", "step_count": changed, "completed_steps": 0, "steps": []},
            presentation_cards=[
                {"label": "Interruption", "value": "Queued authority work canceled", "tone": "high"},
                {"label": "Status", "value": "canceled", "tone": "high"},
                {"label": "Command", "value": f"{changed} queued command(s)", "tone": "medium"},
            ],
        )
        | {
            "canceled_count": changed,
            "actor": actor,
        },
        detail=detail_text,
        actor=actor,
    )
    return {
        "status": "ok",
        "run_id": effective_run_id,
        "trace_id": effective_trace_id,
        "receipt_id": receipt["id"],
        "canceled_count": changed,
        "authority": get_orb_authority_view() | {"state": saved},
    }
