"""Approval request/readback boundary for resident Lens perception execution."""

from __future__ import annotations

from typing import Any

from francis.governance.approval_projection import approval_projection_fields
from francis.governance.approvals import list_requests, request as create_approval_request
from francis.governance.api_permission_gate import ApiPermissionDecision, ApiPermissionGate
from francis.governance.redaction import redact_governed_display_value, redact_secret_text
from francis.lens.perception_authority import lens_perception_desktop_authority_receipt_status
from francis.lens.perception_worker import (
    LENS_PERCEPTION_EXECUTION_ACTION,
    LENS_PERCEPTION_EXECUTION_REQUEST_KIND,
    lens_perception_execution_approval_status,
)

LENS_PERCEPTION_EXECUTION_SCOPE = "system.write"
LENS_PERCEPTION_EXECUTION_REQUEST_ROUTE = "/lens/perception/execution/request"
LENS_PERCEPTION_EXECUTION_REQUESTS_ROUTE = "/lens/perception/execution/requests"

_APPROVAL_STATUSES = ("pending", "approved", "rejected", "emergency")


def request_lens_perception_execution(
    *,
    authority_receipt_id: Any,
    actor: Any,
    reason: Any = "request resident Lens desktop perception execution review",
    route: str = LENS_PERCEPTION_EXECUTION_REQUEST_ROUTE,
    method: str = "POST",
) -> dict[str, Any]:
    safe_route = _safe_str(route) or LENS_PERCEPTION_EXECUTION_REQUEST_ROUTE
    safe_receipt_id = _safe_str(authority_receipt_id)
    permission = _permission(actor, route=safe_route, method=method)
    authority = lens_perception_desktop_authority_receipt_status(safe_receipt_id)
    blockers: list[str] = []
    if not permission.allowed:
        blockers.append("system_write_scope_not_ready")
    if authority.get("active") is not True:
        blockers.extend(_string_items(authority.get("blockers")) or ["desktop_capture_authority_not_active"])
    if blockers:
        return {
            "ok": True,
            "kind": "lens.perception.desktop_capture_execution.request_denial",
            "status": "blocked",
            "action": LENS_PERCEPTION_EXECUTION_ACTION,
            "route": safe_route,
            "approval_requested": False,
            "authority_receipt_id": safe_receipt_id,
            "capture_authority": authority,
            "applied": False,
            "executed": False,
            "starts_capture": False,
            "launches_process": False,
            "blockers": _dedupe(blockers),
            "governance": _governance(
                route=safe_route,
                approval_request_write=False,
                permission=permission,
            ),
        }

    payload = {
        "kind": LENS_PERCEPTION_EXECUTION_REQUEST_KIND,
        "authority_receipt_id": safe_receipt_id,
        "source": "desktop_ring_buffer",
        "mode": "resident",
        "requested_effects": {
            "desktop_capture_execution": True,
            "worker_process_launch": True,
            "runtime_state_write": True,
            "ring_buffer_write": True,
        },
        "camera_capture_authority": False,
        "microphone_capture_authority": False,
        "keyboard_capture_authority": False,
        "user_mouse_capture_authority": False,
        "input_execution_authority": False,
        "memory_write": False,
        "starts_capture": False,
        "launches_process": False,
        "approval_request_only": True,
    }
    approval = create_approval_request(
        LENS_PERCEPTION_EXECUTION_ACTION,
        redact_secret_text(_safe_str(reason)) or "request resident Lens desktop perception execution review",
        payload,
    )
    approval_item = _approval_item(approval)
    return {
        "ok": True,
        "kind": LENS_PERCEPTION_EXECUTION_REQUEST_KIND,
        "status": "approval_requested",
        "action": LENS_PERCEPTION_EXECUTION_ACTION,
        "route": safe_route,
        "approval_requested": True,
        "approval_id": _safe_str(approval_item.get("id")),
        "approval": approval_item,
        "authority_receipt_id": safe_receipt_id,
        "capture_authority": authority,
        "applied": False,
        "executed": False,
        "starts_capture": False,
        "launches_process": False,
        "blockers": [],
        "governance": _governance(
            route=safe_route,
            approval_request_write=True,
            permission=permission,
        ),
    }


def lens_perception_execution_request_readback(*, limit: int = 5) -> dict[str, Any]:
    safe_limit = max(1, min(int(limit), 50))
    by_status: dict[str, list[dict[str, Any]]] = {}
    latest: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    for status in _APPROVAL_STATUSES:
        items = [
            _approval_item(item)
            for item in list_requests(status, limit=100)
            if isinstance(item, dict) and _safe_str(item.get("action")) == LENS_PERCEPTION_EXECUTION_ACTION
        ]
        items.sort(key=lambda item: (_safe_float(item.get("ts")), _safe_str(item.get("id"))), reverse=True)
        by_status[status] = items[:safe_limit]
        counts[status] = len(items)
        latest.extend(items)
    latest.sort(key=lambda item: (_safe_float(item.get("ts")), _safe_str(item.get("id"))), reverse=True)
    latest_item = latest[0] if latest else None
    latest_payload = _as_dict(_as_dict(latest_item).get("payload"))
    latest_status = _safe_str(_as_dict(latest_item).get("status"))
    execution_validation = (
        lens_perception_execution_approval_status(
            _safe_str(_as_dict(latest_item).get("id")),
            _safe_str(latest_payload.get("authority_receipt_id")),
        )
        if latest_status == "approved"
        else {}
    )
    execution_ready = execution_validation.get("active") is True
    if execution_ready:
        status = "approved_ready_for_execution"
        next_step = "execute_exact_approved_resident_perception_request"
    elif counts.get("pending", 0):
        status = "pending_review"
        next_step = "operator_decide_pending_perception_execution_request"
    elif counts.get("approved", 0):
        status = "approved_blocked"
        next_step = "resolve_perception_execution_approval_contract"
    elif counts.get("rejected", 0):
        status = "rejected"
        next_step = "operator_may_request_perception_execution_again"
    else:
        status = "none"
        next_step = "request_perception_execution"
    return {
        "ok": True,
        "kind": "lens.perception.desktop_capture_execution.request_readback",
        "status": status,
        "route": LENS_PERCEPTION_EXECUTION_REQUESTS_ROUTE,
        "request_route": LENS_PERCEPTION_EXECUTION_REQUEST_ROUTE,
        "action": LENS_PERCEPTION_EXECUTION_ACTION,
        "approval_counts": counts,
        "latest": latest_item,
        "pending": by_status.get("pending", []),
        "approved": by_status.get("approved", []),
        "rejected": by_status.get("rejected", []),
        "emergency": by_status.get("emergency", []),
        "execution_validation": execution_validation,
        "execution_ready": execution_ready,
        "executed": False,
        "starts_capture": False,
        "launches_process": False,
        "governance": {
            **_governance(
                route=LENS_PERCEPTION_EXECUTION_REQUESTS_ROUTE,
                approval_request_write=False,
                permission=None,
            ),
            "read_only_contract": True,
            "next_step": next_step,
        },
    }


def _permission(actor: Any, *, route: str, method: str) -> ApiPermissionDecision:
    return ApiPermissionGate.from_env().check(
        actor_id=actor,
        required_scopes=[LENS_PERCEPTION_EXECUTION_SCOPE],
        route=route,
        method=method,
    )


def _governance(
    *,
    route: str,
    approval_request_write: bool,
    permission: ApiPermissionDecision | None,
) -> dict[str, Any]:
    return {
        "gate": "lens_perception_desktop_capture_execution_request",
        "route": route,
        "required_scope": LENS_PERCEPTION_EXECUTION_SCOPE,
        "approval_action": LENS_PERCEPTION_EXECUTION_ACTION,
        "request_route": LENS_PERCEPTION_EXECUTION_REQUEST_ROUTE,
        "requests_route": LENS_PERCEPTION_EXECUTION_REQUESTS_ROUTE,
        "decision_route": "/approvals/decision",
        "approval_request_write": approval_request_write,
        "permission": permission.evidence if permission is not None else {},
        "execution_authority": False,
        "process_launch_authority": False,
        "process_supervision_authority": False,
        "capture_authority": False,
        "new_sensing_authority": False,
        "camera_capture_authority": False,
        "microphone_capture_authority": False,
        "keyboard_capture_authority": False,
        "user_mouse_capture_authority": False,
        "input_execution_authority": False,
        "approval_decision_authority": False,
        "memory_write": False,
        "mutation_authority_granted": False,
    }


def _approval_item(record: dict[str, Any]) -> dict[str, Any]:
    item = redact_governed_display_value(record)
    output = item if isinstance(item, dict) else {}
    output.update(approval_projection_fields(output))
    return output


def _safe_str(value: Any) -> str:
    try:
        return str(value if value is not None else "").strip()
    except Exception:
        return ""


def _safe_float(value: Any) -> float:
    if isinstance(value, bool):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _string_items(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_safe_str(item) for item in value if _safe_str(item)]


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


__all__ = [
    "LENS_PERCEPTION_EXECUTION_REQUEST_ROUTE",
    "LENS_PERCEPTION_EXECUTION_REQUESTS_ROUTE",
    "lens_perception_execution_request_readback",
    "request_lens_perception_execution",
]
