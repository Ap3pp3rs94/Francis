from __future__ import annotations

from typing import Any, TypedDict
from uuid import uuid4

from fastapi import HTTPException
from fastapi.testclient import TestClient

from services.orchestrator.app.lens_snapshot import build_lens_snapshot

DEFAULT_ROLE = "architect"
DEFAULT_USER = "hud.operator"


class ExecuteVia(TypedDict, total=False):
    endpoint: str
    payload: dict[str, Any]


class ActionChip(TypedDict, total=False):
    kind: str
    label: str
    enabled: bool
    risk_tier: str
    trust_badge: str
    reason: str
    policy_reason: str
    requires_confirmation: bool
    policy_state: str
    policy_scope: str
    policy_summary: str
    policy_detail: str
    execute_via: ExecuteVia


REQUIRED_ACTION_FIELDS: dict[str, list[str]] = {
    "mission.tick": ["mission_id"],
    "apprenticeship.session.create": ["title"],
    "apprenticeship.step.record": ["session_id", "action", "intent"],
    "apprenticeship.generalize": ["session_id"],
    "apprenticeship.skillize": ["session_id"],
    "control.takeover.request": ["objective"],
    "control.remote.takeover.request": ["objective"],
    "control.takeover.session": ["session_id"],
    "control.remote.approval.approve": ["approval_id"],
    "control.remote.approval.reject": ["approval_id"],
}


def _get_orchestrator_app():
    from apps.api.main import app as orchestrator_app

    return orchestrator_app


def _json_or_text(response) -> dict[str, Any]:
    try:
        payload = response.json()
    except Exception:
        payload = {"detail": response.text}
    return payload if isinstance(payload, dict) else {"detail": payload}


def _call_orchestrator(
    *,
    method: str,
    path: str,
    params: dict[str, Any] | None = None,
    payload: dict[str, Any] | None = None,
    role: str = DEFAULT_ROLE,
    user: str = DEFAULT_USER,
    trace_id: str | None = None,
) -> dict[str, Any]:
    headers = {
        "x-francis-role": str(role or DEFAULT_ROLE).strip().lower() or DEFAULT_ROLE,
        "x-francis-user": str(user or DEFAULT_USER).strip() or DEFAULT_USER,
        "x-trace-id": str(trace_id or uuid4()),
    }
    with TestClient(_get_orchestrator_app()) as client:
        response = client.request(method=method, url=path, params=params, json=payload, headers=headers)
    body = _json_or_text(response)
    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=body.get("detail", body))
    return body


def get_lens_actions(
    *,
    max_actions: int = 8,
    role: str = DEFAULT_ROLE,
    user: str = DEFAULT_USER,
    snapshot: dict[str, Any] | None = None,
    approval_snapshot: Any | None = None,
) -> dict[str, Any]:
    from services.orchestrator.app.routes.lens import build_lens_actions_payload

    return build_lens_actions_payload(
        max_actions=max_actions,
        role=role,
        user=user,
        snapshot=snapshot,
        approval_snapshot=approval_snapshot,
    )


def _normalize_policy_scope(value: object) -> str:
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


def _derive_policy_scope(chip: dict[str, Any]) -> str:
    explicit = _normalize_policy_scope(chip.get("policy_scope"))
    if explicit != "observation" or str(chip.get("policy_scope", "")).strip():
        return explicit

    kind = str(chip.get("kind", "")).strip().lower()
    args = chip.get("args", {}) if isinstance(chip.get("args"), dict) else {}
    reason_text = " ".join(
        part
        for part in (
            str(chip.get("policy_reason", "")).strip(),
            str(chip.get("reason", "")).strip(),
            str(chip.get("label", "")).strip(),
        )
        if part
    ).lower()

    if bool(args.get("cross_app")) or bool(args.get("transfer")):
        return "cross_app_transfer"
    if str(args.get("source_app", "")).strip() and str(args.get("target_app", "")).strip():
        return "cross_app_transfer"
    if _text_contains_any(reason_text, ("clipboard", "cross-app", "cross app", "handoff", "transfer")):
        return "cross_app_transfer"
    if bool(args.get("sensitive")) or _text_contains_any(
        reason_text,
        ("secret", "token", "credential", "password", "approval", "inbox", "payment", "personal"),
    ):
        return "sensitive"
    if kind.startswith("mouse.drag") or ".drag" in kind:
        return "drag"
    if kind.startswith("mouse.click") or ".click" in kind or kind.endswith("focus_click"):
        return "click"
    if kind.startswith("keyboard.") or ".type" in kind or ".shortcut" in kind:
        return "typing"
    if _text_contains_any(kind, (".delete", ".remove", ".revoke", ".quarantine", ".panic", ".kill", ".destroy")):
        return "destructive"
    if _text_contains_any(kind, (".move", ".open", ".navigate", ".focus", ".switch", ".reveal", ".show")):
        return "navigation"
    return "observation"


def _build_action_policy(chip: dict[str, Any]) -> dict[str, str | bool]:
    explicit_state = str(chip.get("policy_state", "")).strip().lower()
    requires_confirmation = bool(chip.get("requires_confirmation", False))
    enabled = bool(chip.get("enabled", False))
    policy_reason = str(chip.get("policy_reason") or chip.get("reason") or "").strip()
    risk_tier = str(chip.get("risk_tier", "low")).strip().lower() or "low"
    scope = _derive_policy_scope(chip)
    scope_label = _policy_scope_label(scope)

    if explicit_state in {"approval_required", "policy_blocked", "allowed", "observe_only"}:
        state = explicit_state
    elif requires_confirmation:
        state = "approval_required"
    elif not enabled and policy_reason:
        state = "policy_blocked"
    elif enabled:
        state = "allowed"
    else:
        state = "observe_only"

    if state == "approval_required":
        summary = "Waiting approval"
        detail = policy_reason or f"{scope_label} action is held until approval is granted."
    elif state == "policy_blocked":
        summary = "Blocked by policy"
        detail = policy_reason or f"{scope_label} action is outside the current governed boundary."
    elif state == "allowed":
        summary = f"{scope_label} allowed"
        detail = policy_reason or f"{scope_label} action is inside the current approved scope."
    else:
        summary = "Observe only"
        detail = policy_reason or "No mutating action is armed."

    return {
        "policy_state": state,
        "policy_scope": scope,
        "policy_summary": summary,
        "policy_detail": detail,
        "requires_confirmation": requires_confirmation,
        "risk_tier": risk_tier,
    }


def compact_action_chip(chip: dict[str, Any]) -> ActionChip:
    policy = _build_action_policy(chip)
    return {
        "kind": str(chip.get("kind", "")).strip(),
        "label": str(chip.get("label", "")).strip(),
        "enabled": bool(chip.get("enabled", False)),
        "risk_tier": str(chip.get("risk_tier", "")).strip(),
        "trust_badge": str(chip.get("trust_badge", "")).strip(),
        "reason": str(chip.get("reason", "")).strip(),
        "policy_reason": str(chip.get("policy_reason", "")).strip(),
        "requires_confirmation": bool(chip.get("requires_confirmation", False)),
        "policy_state": str(policy.get("policy_state", "")).strip(),
        "policy_scope": str(policy.get("policy_scope", "")).strip(),
        "policy_summary": str(policy.get("policy_summary", "")).strip(),
        "policy_detail": str(policy.get("policy_detail", "")).strip(),
        "execute_via": chip.get("execute_via", {}),
    }


def _find_matching_chip(actions_payload: dict[str, Any], kind: str) -> dict[str, Any] | None:
    for chip in actions_payload.get("action_chips", []):
        if str(chip.get("kind", "")).strip().lower() == kind:
            return chip
    return None


def _required_fallbacks(kind: str, args: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(args)
    missions = snapshot.get("missions", {}) if isinstance(snapshot.get("missions"), dict) else {}
    approvals = snapshot.get("approvals", {}) if isinstance(snapshot.get("approvals"), dict) else {}
    active_missions = missions.get("active", []) if isinstance(missions.get("active"), list) else []
    pending_approvals = approvals.get("pending", []) if isinstance(approvals.get("pending"), list) else []
    objective = snapshot.get("objective", {}) if isinstance(snapshot.get("objective"), dict) else {}
    apprenticeship = snapshot.get("apprenticeship", {}) if isinstance(snapshot.get("apprenticeship"), dict) else {}
    recent_sessions = apprenticeship.get("recent_sessions", []) if isinstance(apprenticeship.get("recent_sessions"), list) else []

    if normalized.get("mission_id") in {"", "<required>", None} and active_missions:
        mission_id = str(active_missions[0].get("id", "")).strip()
        if mission_id:
            normalized["mission_id"] = mission_id

    if normalized.get("objective") in {"", "<required>", None}:
        label = str(objective.get("label", "")).strip()
        if label:
            normalized["objective"] = label

    if normalized.get("approval_id") in {"", "<required>", None} and pending_approvals:
        approval_id = str(pending_approvals[0].get("id", "")).strip()
        if approval_id:
            normalized["approval_id"] = approval_id
    if normalized.get("session_id") in {"", "<required>", None} and recent_sessions:
        session_id = str(recent_sessions[0].get("id", "")).strip()
        if session_id:
            normalized["session_id"] = session_id

    if kind == "control.panic":
        normalized["reason"] = str(normalized.get("reason", "")).strip() or "HUD operator panic"
    elif kind == "control.resume":
        normalized["reason"] = str(normalized.get("reason", "")).strip() or "HUD operator resume"
        normalized["mode"] = str(normalized.get("mode", "")).strip().lower() or str(
            snapshot.get("control", {}).get("mode", "pilot")
        )
    elif kind in {"control.takeover.request", "control.remote.takeover.request"}:
        normalized["reason"] = str(normalized.get("reason", "")).strip() or "HUD requested pilot transfer"
    elif kind in {"control.takeover.confirm", "control.remote.takeover.confirm"}:
        normalized["confirm"] = bool(normalized.get("confirm", True))
        normalized["mode"] = str(normalized.get("mode", "")).strip().lower() or "pilot"
        normalized["reason"] = str(normalized.get("reason", "")).strip() or "HUD confirmed pilot transfer"
    elif kind in {"control.takeover.handback", "control.remote.takeover.handback"}:
        normalized["summary"] = (
            str(normalized.get("summary", "")).strip()
            or f"HUD handback for {str(objective.get('label', 'current objective')).strip()}."
        )
        normalized["verification"] = (
            normalized.get("verification") if isinstance(normalized.get("verification"), dict) else {"hud": "verified"}
        )
        normalized["mode"] = str(normalized.get("mode", "")).strip().lower() or "assist"
    elif kind == "control.remote.approval.approve":
        normalized["note"] = str(normalized.get("note", "")).strip() or "Approved from HUD Lens."
    elif kind == "control.remote.approval.reject":
        normalized["note"] = str(normalized.get("note", "")).strip() or "Rejected from HUD Lens."
    elif kind == "apprenticeship.session.create":
        normalized["objective"] = str(normalized.get("objective", "")).strip() or str(objective.get("label", "")).strip()
        normalized["tags"] = [str(tag).strip().lower() for tag in normalized.get("tags", []) if str(tag).strip()]
    elif kind == "apprenticeship.step.record":
        normalized["step_kind"] = str(normalized.get("step_kind", "")).strip().lower() or "command"

    return normalized


def _validate_required_args(kind: str, args: dict[str, Any]) -> None:
    for field in REQUIRED_ACTION_FIELDS.get(kind, []):
        value = args.get(field)
        if value in {"", "<required>", None}:
            raise HTTPException(status_code=400, detail=f"{field} is required for {kind}")


def _merge_execution_snapshot(execution: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
    result = execution.get("result", {}) if isinstance(execution.get("result"), dict) else {}
    after = result.get("after", {}) if isinstance(result.get("after"), dict) else {}
    control = snapshot.get("control", {}) if isinstance(snapshot.get("control"), dict) else {}
    if not after or not control:
        return snapshot

    merged_control = dict(control)
    for key in ("mode", "kill_switch", "scopes", "updated_at"):
        if key in after:
            merged_control[key] = after[key]
    return {**snapshot, "control": merged_control}


def execute_lens_action(
    *,
    kind: str,
    args: dict[str, Any] | None = None,
    dry_run: bool = False,
    role: str = DEFAULT_ROLE,
    user: str = DEFAULT_USER,
    trace_id: str | None = None,
) -> dict[str, Any]:
    normalized_kind = str(kind or "").strip().lower()
    provided_args = args if isinstance(args, dict) else {}
    actions_payload = get_lens_actions(role=role, user=user)
    chip = _find_matching_chip(actions_payload, normalized_kind)
    base_args: dict[str, Any] = {}
    if chip is not None:
        execute_via = chip.get("execute_via", {})
        payload = execute_via.get("payload", {}) if isinstance(execute_via, dict) else {}
        candidate_args = payload.get("args", {}) if isinstance(payload, dict) else {}
        if isinstance(candidate_args, dict):
            base_args = dict(candidate_args)

    snapshot = build_lens_snapshot()
    merged_args = {**base_args, **provided_args}
    enriched_args = _required_fallbacks(normalized_kind, merged_args, snapshot)
    _validate_required_args(normalized_kind, enriched_args)
    execution = _call_orchestrator(
        method="POST",
        path="/lens/actions/execute",
        payload={"kind": normalized_kind, "args": enriched_args, "dry_run": bool(dry_run)},
        role=role,
        user=user,
        trace_id=trace_id,
    )
    snapshot = _merge_execution_snapshot(execution, build_lens_snapshot())
    return {
        "execution": execution,
        "actions": get_lens_actions(role=role, user=user),
        "snapshot": snapshot,
    }
