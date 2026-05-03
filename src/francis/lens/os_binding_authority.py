from __future__ import annotations

from typing import Any

from francis.governance.approval_projection import approval_projection_fields
from francis.governance.approvals import list_requests, request as create_approval_request
from francis.governance.api_permission_gate import ApiPermissionDecision, ApiPermissionGate
from francis.governance.redaction import redact_governed_display_value, redact_secret_text
from francis.lens.preflight import lens_os_binding_implementation_plan, lens_os_binding_readiness

LENS_OS_BINDING_AUTHORITY_SCOPE = "system.write"
LENS_OS_BINDING_AUTHORITY_REQUEST_ACTION = "lens.os_binding.command_palette_binding_authority"
LENS_OS_BINDING_AUTHORITY_ROUTE = "/lens/os-binding/authority"
LENS_OS_BINDING_AUTHORITY_REQUEST_ROUTE = "/lens/os-binding/authority/request"
LENS_OS_BINDING_AUTHORITY_REQUESTS_ROUTE = "/lens/os-binding/authority/requests"
LENS_OS_BINDING_READINESS_ROUTE = "/lens/os-binding/readiness"
LENS_OS_BINDING_PLAN_ROUTE = "/lens/os-binding/plan"
_APPROVAL_STATUSES = ("pending", "approved", "rejected", "emergency")


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""


def _redact_free_text(value: Any) -> str:
    return redact_secret_text(_safe_str(value).strip())


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _str_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [_safe_str(item).strip() for item in value if _safe_str(item).strip()]
    if isinstance(value, str):
        item = value.strip()
        return [item] if item else []
    return []


def _dedupe_strs(values: list[Any]) -> list[str]:
    return sorted({_safe_str(item).strip() for item in values if _safe_str(item).strip()})


def _safe_limit(value: Any, *, default: int = 5) -> int:
    if isinstance(value, bool):
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(1, min(50, parsed))


def _record_ts(value: Any) -> float:
    if isinstance(value, bool):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _permission(actor: Any, *, route: str, method: str) -> ApiPermissionDecision:
    return ApiPermissionGate.from_env().check(
        actor_id=actor,
        required_scopes=[LENS_OS_BINDING_AUTHORITY_SCOPE],
        route=route,
        method=method,
    )


def _governance(
    *,
    route: str,
    approval_request_write: bool = True,
    read_only_contract: bool = False,
) -> dict[str, Any]:
    return {
        "gate": "lens_os_binding_command_palette_authority_request",
        "route": route,
        "required_scope": LENS_OS_BINDING_AUTHORITY_SCOPE,
        "approval_action": LENS_OS_BINDING_AUTHORITY_REQUEST_ACTION,
        "approval_request_write": approval_request_write,
        "authority_route": LENS_OS_BINDING_AUTHORITY_ROUTE,
        "request_route": LENS_OS_BINDING_AUTHORITY_REQUEST_ROUTE,
        "readback_route": LENS_OS_BINDING_AUTHORITY_REQUESTS_ROUTE,
        "readiness_route": LENS_OS_BINDING_READINESS_ROUTE,
        "plan_route": LENS_OS_BINDING_PLAN_ROUTE,
        "decision_route": "/approvals/decision",
        "read_only_contract": read_only_contract,
        "authority_granted": False,
        "os_level_command_palette_binding_authority": False,
        "execution_authority": False,
        "approval_decision_authority": False,
        "memory_write": False,
        "summon_authority": False,
        "hotkey_registration_authority": False,
        "tray_registration_authority": False,
        "overlay_control_authority": False,
        "local_process_launch_authority": False,
        "process_supervision_authority": False,
        "service_control_authority": False,
        "window_management_authority": False,
        "capture_authority": False,
        "resident_claim_authority": False,
        "mutation_authority_granted": False,
        "next_step": "operator_decides_pending_os_binding_command_palette_authority_request",
    }


def _permission_denied(decision: ApiPermissionDecision, *, route: str) -> dict[str, Any]:
    return {
        "ok": False,
        "applied": False,
        "executed": False,
        "approval_requested": False,
        "status": "denied",
        "error": "api_permission_denied",
        "action": LENS_OS_BINDING_AUTHORITY_REQUEST_ACTION,
        "authority_granted": False,
        "os_level_command_palette_binding_authority": False,
        "os_level_command_palette": False,
        "summon_anywhere": False,
        "opens_palette": False,
        "registers_hotkey": False,
        "launches_process": False,
        "controls_overlay": False,
        "governance": {
            **_governance(route=route, approval_request_write=False),
            "gate": "permission_gate",
            "reason": decision.reason,
            "evidence": decision.evidence,
            "permission": decision.evidence,
            "next_step": "configure_actor_scope_before_requesting_os_binding_command_palette_authority",
        },
    }


def _approval_item(record: dict[str, Any]) -> dict[str, Any]:
    item = dict(record) if isinstance(record, dict) else {}
    redacted = redact_governed_display_value(item)
    out = redacted if isinstance(redacted, dict) else {}
    out.update(approval_projection_fields(item))
    return out


def _approval_items(*, limit: int) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]], dict[str, int]]:
    by_status: dict[str, list[dict[str, Any]]] = {}
    counts: dict[str, int] = {}
    all_items: list[dict[str, Any]] = []
    for status in _APPROVAL_STATUSES:
        try:
            records = list_requests(status=status, limit=5000)
        except Exception:
            records = []
        items = [
            _approval_item(item)
            for item in records
            if isinstance(item, dict)
            and _safe_str(item.get("action")).strip() == LENS_OS_BINDING_AUTHORITY_REQUEST_ACTION
        ]
        items.sort(
            key=lambda item: (_record_ts(item.get("decided_ts") or item.get("ts")), _safe_str(item.get("id"))),
            reverse=True,
        )
        counts[status] = len(items)
        by_status[status] = items[:limit]
        all_items.extend(items)
    all_items.sort(
        key=lambda item: (_record_ts(item.get("decided_ts") or item.get("ts")), _safe_str(item.get("id"))),
        reverse=True,
    )
    return by_status, all_items[:limit], counts


def _readback_status(counts: dict[str, int]) -> tuple[str, str]:
    if counts.get("pending", 0) > 0:
        return "pending_review", "operator_decide_pending_os_binding_command_palette_authority_request"
    if counts.get("emergency", 0) > 0:
        return "emergency_reviewed_no_authority", "operator_review_emergency_os_binding_decision"
    if counts.get("approved", 0) > 0:
        return "approved_no_authority", "approved_request_requires_separate_os_binding_authority_grant_slice"
    if counts.get("rejected", 0) > 0:
        return "rejected", "operator_may_request_os_binding_command_palette_authority_again"
    return "none", "request_os_binding_command_palette_authority_before_binding"


def _request_payload(*, actor: Any, route: str) -> dict[str, Any]:
    readiness = lens_os_binding_readiness()
    plan = lens_os_binding_implementation_plan()
    readiness_governance = _as_dict(readiness.get("governance"))
    plan_body = _as_dict(plan.get("plan"))
    blockers = _dedupe_strs(
        [
            *_str_list(readiness.get("blockers")),
            *_str_list(plan.get("blockers")),
            "os_level_command_palette_binding_authority_not_granted",
        ]
    )
    return {
        "request_kind": "lens.os_binding.command_palette_binding_authority.request",
        "actor": _redact_free_text(actor),
        "route": route,
        "authority_route": LENS_OS_BINDING_AUTHORITY_ROUTE,
        "readback_route": LENS_OS_BINDING_AUTHORITY_REQUESTS_ROUTE,
        "readiness_route": LENS_OS_BINDING_READINESS_ROUTE,
        "plan_route": LENS_OS_BINDING_PLAN_ROUTE,
        "status_route": "/lens/status",
        "summon_route": "/lens/summon",
        "readiness": {
            "status": _safe_str(readiness.get("status")).strip(),
            "ready": bool(readiness.get("ready")),
            "os_binding_ready": bool(readiness.get("os_binding_ready")),
            "os_level_command_palette": bool(readiness.get("os_level_command_palette")),
            "summon_anywhere": bool(readiness.get("summon_anywhere")),
            "next_smallest_truthful_gap": _safe_str(readiness.get("next_smallest_truthful_gap")).strip(),
            "blocked_requirements": _as_list(readiness.get("blocked_requirements")),
            "blockers": _as_list(readiness.get("blockers")),
            "blocker_groups": _as_dict(readiness.get("blocker_groups")),
        },
        "implementation_plan": {
            "status": _safe_str(plan.get("status")).strip(),
            "plan_available": bool(plan.get("plan_available")),
            "implementation_ready": bool(plan.get("implementation_ready")),
            "execution_ready": bool(plan.get("execution_ready")),
            "blocked_requirements": _as_list(plan.get("blocked_requirements")),
            "blockers": _as_list(plan.get("blockers")),
            "blocker_groups": _as_dict(plan.get("blocker_groups")),
        },
        "authority_boundary": {
            "status": "blocked",
            "authority_ready": False,
            "authority_granted": False,
            "os_level_command_palette_binding_authority": False,
            "opens_palette": False,
            "registers_hotkey": False,
            "summons": False,
            "launches_process": False,
            "controls_overlay": False,
            "writes_memory": False,
            "decides_approval": False,
            "claims_resident": False,
            "blockers": blockers,
        },
        "blockers": blockers,
        "governance": {
            **_governance(route=route),
            "readiness_governance": readiness_governance,
            "would_open_palette": bool(plan_body.get("would_open_palette")),
            "would_register_hotkey": bool(plan_body.get("would_register_hotkey")),
            "would_summon": bool(plan_body.get("would_summon")),
            "would_launch_process": bool(plan_body.get("would_launch_process")),
            "would_open_overlay": bool(plan_body.get("would_open_overlay")),
            "would_write_memory": bool(plan_body.get("would_write_memory")),
            "would_decide_approval": bool(plan_body.get("would_decide_approval")),
            "would_claim_resident": bool(plan_body.get("would_claim_resident")),
        },
    }


def lens_os_binding_authority_request_contract() -> dict[str, Any]:
    return {
        "ok": True,
        "kind": "lens.os_binding.command_palette_binding_authority.contract",
        "status": "approval_request_ready",
        "route": LENS_OS_BINDING_AUTHORITY_ROUTE,
        "request_route": LENS_OS_BINDING_AUTHORITY_REQUEST_ROUTE,
        "readback_route": LENS_OS_BINDING_AUTHORITY_REQUESTS_ROUTE,
        "readiness_route": LENS_OS_BINDING_READINESS_ROUTE,
        "plan_route": LENS_OS_BINDING_PLAN_ROUTE,
        "method": "POST",
        "action": LENS_OS_BINDING_AUTHORITY_REQUEST_ACTION,
        "creates_approval_request": True,
        "grants_authority": False,
        "opens_palette": False,
        "registers_hotkey": False,
        "summons": False,
        "launches_process": False,
        "controls_overlay": False,
        "writes_receipt": False,
        "writes_memory": False,
        "decides_approval": False,
        "claims_resident": False,
        "governance": _governance(route=LENS_OS_BINDING_AUTHORITY_ROUTE, read_only_contract=True),
    }


def request_lens_os_binding_authority(
    *,
    actor: Any,
    reason: Any = "request Lens OS-binding command palette authority review",
    route: str = LENS_OS_BINDING_AUTHORITY_REQUEST_ROUTE,
    method: str = "POST",
) -> dict[str, Any]:
    safe_route = _safe_str(route).strip() or LENS_OS_BINDING_AUTHORITY_REQUEST_ROUTE
    permission = _permission(actor, route=safe_route, method=method)
    if not permission.allowed:
        return _permission_denied(permission, route=safe_route)

    request_reason = _redact_free_text(reason) or "request Lens OS-binding command palette authority review"
    payload = _request_payload(actor=actor, route=safe_route)
    approval = create_approval_request(LENS_OS_BINDING_AUTHORITY_REQUEST_ACTION, request_reason, payload)
    approval_item = _approval_item(approval)
    return {
        "ok": True,
        "applied": False,
        "executed": False,
        "approval_requested": True,
        "status": "approval_requested",
        "action": LENS_OS_BINDING_AUTHORITY_REQUEST_ACTION,
        "approval_id": _safe_str(approval_item.get("id")),
        "approval": approval_item,
        "os_binding_authority": payload,
        "authority_granted": False,
        "os_level_command_palette_binding_authority": False,
        "os_level_command_palette": False,
        "summon_anywhere": False,
        "opens_palette": False,
        "registers_hotkey": False,
        "launches_process": False,
        "controls_overlay": False,
        "governance": {
            **_governance(route=safe_route),
            "permission": permission.evidence,
        },
    }


def lens_os_binding_authority_request_readback(*, limit: int = 5) -> dict[str, Any]:
    safe_limit = _safe_limit(limit)
    by_status, latest_items, counts = _approval_items(limit=safe_limit)
    total = sum(counts.values())
    status, next_step = _readback_status(counts)
    latest = latest_items[0] if latest_items else None
    return {
        "ok": True,
        "kind": "lens.os_binding.command_palette_binding_authority.request_readback",
        "status": status,
        "route": LENS_OS_BINDING_AUTHORITY_REQUESTS_ROUTE,
        "authority_route": LENS_OS_BINDING_AUTHORITY_ROUTE,
        "request_route": LENS_OS_BINDING_AUTHORITY_REQUEST_ROUTE,
        "readiness_route": LENS_OS_BINDING_READINESS_ROUTE,
        "plan_route": LENS_OS_BINDING_PLAN_ROUTE,
        "decision_route": "/approvals/decision",
        "approval_action": LENS_OS_BINDING_AUTHORITY_REQUEST_ACTION,
        "pending_count": counts.get("pending", 0),
        "approved_count": counts.get("approved", 0),
        "rejected_count": counts.get("rejected", 0),
        "emergency_count": counts.get("emergency", 0),
        "total_count": total,
        "latest": latest,
        "items": latest_items,
        "by_status": by_status,
        "authority_granted": False,
        "os_level_command_palette_binding_authority": False,
        "os_level_command_palette": False,
        "summon_anywhere": False,
        "opens_palette": False,
        "registers_hotkey": False,
        "launches_process": False,
        "controls_overlay": False,
        "governance": {
            **_governance(
                route=LENS_OS_BINDING_AUTHORITY_REQUESTS_ROUTE,
                approval_request_write=False,
                read_only_contract=True,
            ),
            "gate": "lens_os_binding_command_palette_authority_request_readback",
            "next_step": next_step,
        },
    }
