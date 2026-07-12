"""Governed authority for bounded desktop input observation.

This authority permits observation metadata only. It never authorizes input
execution, cursor control, key values, typed text, window titles, or clipboard
content, and granting it does not start an observer.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

from francis.governance.approval_projection import approval_projection_fields
from francis.governance.approvals import (
    approved_dir,
    emergency_dir,
    list_requests,
    pending_dir,
    rejected_dir,
    request as create_approval_request,
)
from francis.governance.api_permission_gate import ApiPermissionDecision, ApiPermissionGate
from francis.governance.redaction import redact_governed_display_value, redact_secret_text
from francis.kernel.paths import data_dir

LENS_PERCEPTION_INPUT_AUTHORITY_SCOPE = "system.write"
LENS_PERCEPTION_INPUT_AUTHORITY_ACTION = "lens.perception.desktop_input_observation_authority"
LENS_PERCEPTION_INPUT_AUTHORITY_ROUTE = "/lens/perception/input/authority"
LENS_PERCEPTION_INPUT_AUTHORITY_REQUEST_ROUTE = "/lens/perception/input/authority/request"
LENS_PERCEPTION_INPUT_AUTHORITY_REQUESTS_ROUTE = "/lens/perception/input/authority/requests"
LENS_PERCEPTION_INPUT_AUTHORITY_GRANTS_ROUTE = "/lens/perception/input/authority/grants"

LENS_PERCEPTION_INPUT_OBSERVATIONS = (
    "cursor_position",
    "pointer_button_activity",
    "scroll_activity",
    "foreground_window_identity",
    "keyboard_activity_timing",
)
LENS_PERCEPTION_INPUT_FORBIDDEN_CONTENT = (
    "keyboard_content",
    "key_codes",
    "typed_characters",
    "window_titles",
    "clipboard_content",
)

_APPROVAL_STATUSES = ("pending", "approved", "rejected", "emergency")
_REQUEST_KIND = "lens.perception.desktop_input_observation_authority.request"
_RECEIPT_KIND = "lens.perception.desktop_input_observation_authority.grant_receipt"
_DEFAULT_LEASE_SECONDS = 60 * 60
_MIN_LEASE_SECONDS = 60
_MAX_LEASE_SECONDS = 24 * 60 * 60


def _safe_str(value: Any) -> str:
    try:
        return str(value if value is not None else "").strip()
    except Exception:
        return ""


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_limit(value: Any, *, default: int = 5) -> int:
    if isinstance(value, bool):
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(1, min(50, parsed))


def _safe_lease_seconds(value: Any) -> int:
    if isinstance(value, bool):
        return _DEFAULT_LEASE_SECONDS
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return _DEFAULT_LEASE_SECONDS
    return max(_MIN_LEASE_SECONDS, min(_MAX_LEASE_SECONDS, parsed))


def _record_ts(value: Any) -> float:
    if isinstance(value, bool):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _display(record: dict[str, Any]) -> dict[str, Any]:
    redacted = redact_governed_display_value(record)
    output = redacted if isinstance(redacted, dict) else {}
    output.update(approval_projection_fields(record))
    return output


def _permission(actor: Any, *, route: str, method: str) -> ApiPermissionDecision:
    return ApiPermissionGate.from_env().check(
        actor_id=actor,
        required_scopes=[LENS_PERCEPTION_INPUT_AUTHORITY_SCOPE],
        route=route,
        method=method,
    )


def _governance(
    *,
    route: str,
    read_only_contract: bool,
    approval_request_write: bool,
    authority_granted: bool = False,
) -> dict[str, Any]:
    return {
        "gate": "lens_perception_desktop_input_observation_authority",
        "route": route,
        "required_scope": LENS_PERCEPTION_INPUT_AUTHORITY_SCOPE,
        "approval_action": LENS_PERCEPTION_INPUT_AUTHORITY_ACTION,
        "authority_route": LENS_PERCEPTION_INPUT_AUTHORITY_ROUTE,
        "request_route": LENS_PERCEPTION_INPUT_AUTHORITY_REQUEST_ROUTE,
        "requests_route": LENS_PERCEPTION_INPUT_AUTHORITY_REQUESTS_ROUTE,
        "grants_route": LENS_PERCEPTION_INPUT_AUTHORITY_GRANTS_ROUTE,
        "decision_route": "/approvals/decision",
        "read_only_contract": read_only_contract,
        "approval_request_write": approval_request_write,
        "desktop_input_observation_authority": authority_granted,
        "cursor_telemetry_authority": authority_granted,
        "pointer_button_activity_authority": authority_granted,
        "scroll_activity_authority": authority_granted,
        "foreground_window_identity_authority": authority_granted,
        "keyboard_activity_timing_authority": authority_granted,
        "keyboard_content_capture_authority": False,
        "key_code_capture_authority": False,
        "window_title_capture_authority": False,
        "clipboard_read_authority": False,
        "input_execution_authority": False,
        "user_cursor_control_authority": False,
        "memory_write": False,
        "approval_decision_authority": False,
    }


def _approval_by_id(approval_id: str) -> tuple[dict[str, Any] | None, str]:
    if not approval_id or "/" in approval_id or "\\" in approval_id or ".." in approval_id:
        return None, "missing"
    for status, folder in (
        ("pending", pending_dir()),
        ("approved", approved_dir()),
        ("rejected", rejected_dir()),
        ("emergency", emergency_dir()),
    ):
        record = _read_json(folder / f"{approval_id}.json")
        if record is None:
            continue
        if _safe_str(record.get("action")) != LENS_PERCEPTION_INPUT_AUTHORITY_ACTION:
            return record, "wrong_action"
        return record, status
    return None, "not_found"


def _approval_contract_valid(record: dict[str, Any]) -> bool:
    payload = _as_dict(record.get("payload"))
    boundary = _as_dict(payload.get("authority_boundary"))
    return bool(
        payload.get("kind") == _REQUEST_KIND
        and payload.get("source") == "windows_desktop_input_events"
        and tuple(payload.get("observations") or ()) == LENS_PERCEPTION_INPUT_OBSERVATIONS
        and tuple(payload.get("forbidden_content") or ()) == LENS_PERCEPTION_INPUT_FORBIDDEN_CONTENT
        and boundary.get("starts_observation") is False
        and boundary.get("launches_process") is False
        and boundary.get("input_execution_authority") is False
        and boundary.get("keyboard_content_capture_authority") is False
        and boundary.get("user_cursor_control_authority") is False
    )


def request_lens_perception_input_authority(
    *,
    actor: Any,
    reason: Any = "request Lens desktop input observation authority review",
    route: str = LENS_PERCEPTION_INPUT_AUTHORITY_REQUEST_ROUTE,
    method: str = "POST",
) -> dict[str, Any]:
    safe_route = _safe_str(route) or LENS_PERCEPTION_INPUT_AUTHORITY_REQUEST_ROUTE
    permission = _permission(actor, route=safe_route, method=method)
    if not permission.allowed:
        return {
            "ok": False,
            "status": "denied",
            "error": "api_permission_denied",
            "action": LENS_PERCEPTION_INPUT_AUTHORITY_ACTION,
            "approval_requested": False,
            "authority_granted": False,
            "governance": {
                **_governance(route=safe_route, read_only_contract=False, approval_request_write=False),
                "gate": "permission_gate",
                "reason": permission.reason,
                "permission": permission.evidence,
            },
        }

    payload = {
        "kind": _REQUEST_KIND,
        "actor": redact_secret_text(_safe_str(actor)),
        "route": safe_route,
        "source": "windows_desktop_input_events",
        "observations": list(LENS_PERCEPTION_INPUT_OBSERVATIONS),
        "forbidden_content": list(LENS_PERCEPTION_INPUT_FORBIDDEN_CONTENT),
        "authority_boundary": {
            "starts_observation": False,
            "launches_process": False,
            "input_execution_authority": False,
            "keyboard_content_capture_authority": False,
            "key_code_capture_authority": False,
            "window_title_capture_authority": False,
            "clipboard_read_authority": False,
            "user_cursor_control_authority": False,
            "memory_write": False,
        },
        "governance": _governance(
            route=safe_route,
            read_only_contract=False,
            approval_request_write=True,
        ),
    }
    approval = create_approval_request(
        LENS_PERCEPTION_INPUT_AUTHORITY_ACTION,
        redact_secret_text(_safe_str(reason)) or "request Lens desktop input observation authority review",
        payload,
    )
    item = _display(approval)
    return {
        "ok": True,
        "kind": _REQUEST_KIND,
        "status": "approval_requested",
        "action": LENS_PERCEPTION_INPUT_AUTHORITY_ACTION,
        "approval_requested": True,
        "approval_id": _safe_str(item.get("id")),
        "approval": item,
        "authority_granted": False,
        "starts_observation": False,
        "executed": False,
        "governance": {
            **_governance(route=safe_route, read_only_contract=False, approval_request_write=True),
            "permission": permission.evidence,
        },
    }


def _receipt_root() -> Path:
    return data_dir() / "lens" / "perception_desktop_input_observation_authority_grants"


def _receipt_path(receipt_id: Any) -> Path | None:
    cleaned = _safe_str(receipt_id)
    if not cleaned or "/" in cleaned or "\\" in cleaned or ".." in cleaned:
        return None
    return _receipt_root() / f"{cleaned}.json"


def _receipt_id(*, approval_id: str, actor: str, ts: int) -> str:
    seed = f"{approval_id}:{actor}:{time.time_ns()}"
    digest = hashlib.sha256(seed.encode("utf-8", errors="replace")).hexdigest()[:12]
    return f"lpiag_{ts}_{digest}"


def _build_receipt(response: dict[str, Any]) -> dict[str, Any]:
    ts = int(time.time())
    lease_seconds = _safe_lease_seconds(response.get("lease_seconds"))
    receipt_id = _receipt_id(
        approval_id=_safe_str(response.get("approval_id")),
        actor=_safe_str(response.get("actor")),
        ts=ts,
    )
    return {
        "kind": _RECEIPT_KIND,
        "receipt_id": receipt_id,
        "ts": ts,
        "status": "authority_granted",
        "approval_id": _safe_str(response.get("approval_id")),
        "approval_action": LENS_PERCEPTION_INPUT_AUTHORITY_ACTION,
        "actor": _safe_str(response.get("actor")),
        "route": LENS_PERCEPTION_INPUT_AUTHORITY_ROUTE,
        "source": "windows_desktop_input_events",
        "observations": list(LENS_PERCEPTION_INPUT_OBSERVATIONS),
        "forbidden_content": list(LENS_PERCEPTION_INPUT_FORBIDDEN_CONTENT),
        "lease_seconds": lease_seconds,
        "expires_ts": ts + lease_seconds,
        "authority_granted": True,
        "authorities": {
            "desktop_input_observation_authority": True,
            "cursor_telemetry_authority": True,
            "pointer_button_activity_authority": True,
            "scroll_activity_authority": True,
            "foreground_window_identity_authority": True,
            "keyboard_activity_timing_authority": True,
            "receipt_write_authority": True,
            "keyboard_content_capture_authority": False,
            "key_code_capture_authority": False,
            "window_title_capture_authority": False,
            "clipboard_read_authority": False,
            "input_execution_authority": False,
            "user_cursor_control_authority": False,
            "memory_write": False,
            "approval_decision_authority": False,
        },
        "governance": _governance(
            route=LENS_PERCEPTION_INPUT_AUTHORITY_GRANTS_ROUTE,
            read_only_contract=True,
            approval_request_write=False,
            authority_granted=True,
        ),
    }


def _write_receipt(response: dict[str, Any]) -> dict[str, Any]:
    receipt = _build_receipt(response)
    path = _receipt_path(receipt.get("receipt_id"))
    if path is None:
        return {}
    _atomic_write_json(path, receipt)
    return receipt


def lens_perception_input_authority_receipt_status(receipt_id: Any, *, now: int | None = None) -> dict[str, Any]:
    clean_id = _safe_str(receipt_id)
    path = _receipt_path(clean_id)
    receipt = _read_json(path) if path is not None else None
    if receipt is None:
        return {
            "status": "not_found" if clean_id else "missing",
            "valid": False,
            "active": False,
            "receipt_id": clean_id,
            "blockers": [
                "desktop_input_observation_authority_receipt_not_found"
                if clean_id
                else "desktop_input_observation_authority_receipt_missing"
            ],
        }

    blockers: list[str] = []
    authorities = _as_dict(receipt.get("authorities"))
    approval_id = _safe_str(receipt.get("approval_id"))
    approval, approval_status = _approval_by_id(approval_id)
    if receipt.get("kind") != _RECEIPT_KIND or _safe_str(receipt.get("receipt_id")) != clean_id:
        blockers.append("desktop_input_observation_authority_receipt_invalid")
    if receipt.get("status") != "authority_granted" or receipt.get("authority_granted") is not True:
        blockers.append("desktop_input_observation_authority_receipt_invalid")
    if receipt.get("approval_action") != LENS_PERCEPTION_INPUT_AUTHORITY_ACTION:
        blockers.append("desktop_input_observation_authority_receipt_wrong_action")
    if receipt.get("route") != LENS_PERCEPTION_INPUT_AUTHORITY_ROUTE:
        blockers.append("desktop_input_observation_authority_receipt_wrong_route")
    if receipt.get("source") != "windows_desktop_input_events":
        blockers.append("desktop_input_observation_authority_receipt_wrong_source")
    if tuple(receipt.get("observations") or ()) != LENS_PERCEPTION_INPUT_OBSERVATIONS:
        blockers.append("desktop_input_observation_authority_receipt_scope_invalid")
    if tuple(receipt.get("forbidden_content") or ()) != LENS_PERCEPTION_INPUT_FORBIDDEN_CONTENT:
        blockers.append("desktop_input_observation_authority_receipt_scope_invalid")
    if not all(
        authorities.get(name) is True
        for name in (
            "desktop_input_observation_authority",
            "cursor_telemetry_authority",
            "pointer_button_activity_authority",
            "scroll_activity_authority",
            "foreground_window_identity_authority",
            "keyboard_activity_timing_authority",
            "receipt_write_authority",
        )
    ):
        blockers.append("desktop_input_observation_authority_receipt_scope_invalid")
    if any(
        authorities.get(name) is not False
        for name in (
            "keyboard_content_capture_authority",
            "key_code_capture_authority",
            "window_title_capture_authority",
            "clipboard_read_authority",
            "input_execution_authority",
            "user_cursor_control_authority",
            "memory_write",
            "approval_decision_authority",
        )
    ):
        blockers.append("desktop_input_observation_authority_receipt_overbroad")
    if not approval or approval_status != "approved":
        blockers.append("desktop_input_observation_authority_approval_not_approved")
    elif not _approval_contract_valid(approval):
        blockers.append("desktop_input_observation_authority_approval_contract_invalid")
    expires_ts = int(_record_ts(receipt.get("expires_ts")))
    if expires_ts <= 0:
        blockers.append("desktop_input_observation_authority_receipt_expiry_invalid")
    elif expires_ts <= (int(time.time()) if now is None else int(now)):
        blockers.append("desktop_input_observation_authority_receipt_expired")
    blockers = sorted(set(blockers))
    return {
        "status": "active" if not blockers else "blocked",
        "valid": not blockers,
        "active": not blockers,
        "receipt_id": clean_id,
        "approval_id": approval_id,
        "approval_status": approval_status,
        "expires_ts": expires_ts or None,
        "blockers": blockers,
        "authorities": authorities,
    }


def lens_perception_input_authority_grant_receipts(*, limit: int = 5, active_only: bool = False) -> dict[str, Any]:
    safe_limit = _safe_limit(limit)
    items: list[dict[str, Any]] = []
    root = _receipt_root()
    if root.exists():
        for path in root.glob("*.json"):
            receipt = _read_json(path)
            if receipt is None or receipt.get("kind") != _RECEIPT_KIND:
                continue
            validation = lens_perception_input_authority_receipt_status(receipt.get("receipt_id"))
            if active_only and validation.get("active") is not True:
                continue
            items.append({**receipt, "validation": validation})
    items.sort(key=lambda item: (_record_ts(item.get("ts")), _safe_str(item.get("receipt_id"))), reverse=True)
    total = len(items)
    items = items[:safe_limit]
    active_latest = next((item for item in items if _as_dict(item.get("validation")).get("active") is True), None)
    return {
        "ok": True,
        "kind": "lens.perception.desktop_input_observation_authority.grant_receipts",
        "status": "readback_ready" if items else "empty",
        "route": LENS_PERCEPTION_INPUT_AUTHORITY_GRANTS_ROUTE,
        "authority_route": LENS_PERCEPTION_INPUT_AUTHORITY_ROUTE,
        "request_route": LENS_PERCEPTION_INPUT_AUTHORITY_REQUEST_ROUTE,
        "total": total,
        "latest": items[0] if items else None,
        "active_latest": active_latest,
        "authority_granted": active_latest is not None,
        "items": items,
        "governance": _governance(
            route=LENS_PERCEPTION_INPUT_AUTHORITY_GRANTS_ROUTE,
            read_only_contract=True,
            approval_request_write=False,
            authority_granted=active_latest is not None,
        ),
    }


def _approval_items(*, limit: int) -> tuple[dict[str, list[dict[str, Any]]], dict[str, int]]:
    by_status: dict[str, list[dict[str, Any]]] = {}
    counts: dict[str, int] = {}
    for status in _APPROVAL_STATUSES:
        try:
            records = list_requests(status=status, limit=5000)
        except Exception:
            records = []
        items = [
            _display(record)
            for record in records
            if isinstance(record, dict) and record.get("action") == LENS_PERCEPTION_INPUT_AUTHORITY_ACTION
        ]
        items.sort(
            key=lambda item: (_record_ts(item.get("decided_ts") or item.get("ts")), _safe_str(item.get("id"))),
            reverse=True,
        )
        counts[status] = len(items)
        by_status[status] = items[:limit]
    return by_status, counts


def lens_perception_input_authority_request_readback(*, limit: int = 5) -> dict[str, Any]:
    safe_limit = _safe_limit(limit)
    by_status, counts = _approval_items(limit=safe_limit)
    grants = lens_perception_input_authority_grant_receipts(limit=1, active_only=True)
    authority_granted = grants.get("authority_granted") is True
    if authority_granted:
        status = "authority_granted"
        next_step = "enable_observer_only_through_a_separately_governed_execution_handoff"
    elif counts.get("pending", 0):
        status = "pending_review"
        next_step = "operator_decide_pending_desktop_input_observation_authority_request"
    elif counts.get("approved", 0):
        status = "approved_no_authority"
        next_step = "grant_exact_approved_desktop_input_observation_authority_request"
    elif counts.get("rejected", 0):
        status = "rejected"
        next_step = "operator_may_request_desktop_input_observation_authority_again"
    else:
        status = "none"
        next_step = "request_desktop_input_observation_authority"
    latest = sorted(
        [item for items in by_status.values() for item in items],
        key=lambda item: (_record_ts(item.get("decided_ts") or item.get("ts")), _safe_str(item.get("id"))),
        reverse=True,
    )
    return {
        "ok": True,
        "kind": "lens.perception.desktop_input_observation_authority.request_readback",
        "status": status,
        "route": LENS_PERCEPTION_INPUT_AUTHORITY_REQUESTS_ROUTE,
        "authority_route": LENS_PERCEPTION_INPUT_AUTHORITY_ROUTE,
        "request_route": LENS_PERCEPTION_INPUT_AUTHORITY_REQUEST_ROUTE,
        "grants_route": LENS_PERCEPTION_INPUT_AUTHORITY_GRANTS_ROUTE,
        "action": LENS_PERCEPTION_INPUT_AUTHORITY_ACTION,
        "approval_counts": counts,
        "latest": latest[0] if latest else None,
        "pending": by_status.get("pending", []),
        "approved": by_status.get("approved", []),
        "rejected": by_status.get("rejected", []),
        "emergency": by_status.get("emergency", []),
        "active_authority_grant": _as_dict(grants.get("active_latest")),
        "authority_granted": authority_granted,
        "governance": {
            **_governance(
                route=LENS_PERCEPTION_INPUT_AUTHORITY_REQUESTS_ROUTE,
                read_only_contract=True,
                approval_request_write=False,
                authority_granted=authority_granted,
            ),
            "next_step": next_step,
        },
    }


def grant_lens_perception_input_authority(
    *,
    approval_id: Any = "",
    actor: Any = "",
    reason: Any = "attempt Lens desktop input observation authority grant",
    route: str = LENS_PERCEPTION_INPUT_AUTHORITY_ROUTE,
    method: str = "POST",
    record_receipt: bool = False,
    lease_seconds: Any = _DEFAULT_LEASE_SECONDS,
) -> dict[str, Any]:
    safe_route = _safe_str(route) or LENS_PERCEPTION_INPUT_AUTHORITY_ROUTE
    safe_approval_id = _safe_str(approval_id)
    approval, lookup_status = _approval_by_id(safe_approval_id)
    approval_status = _safe_str(_as_dict(approval).get("status")) if approval else lookup_status
    approval_ready = bool(approval) and approval_status == "approved" and _approval_contract_valid(_as_dict(approval))
    permission = _permission(actor, route=safe_route, method=method)
    blockers: list[str] = []
    if not safe_approval_id:
        blockers.append("approval_id_required")
    elif lookup_status == "not_found":
        blockers.append("desktop_input_observation_authority_approval_not_found")
    elif lookup_status == "wrong_action":
        blockers.append("desktop_input_observation_authority_approval_wrong_action")
    elif approval_status != "approved":
        blockers.append("desktop_input_observation_authority_approval_not_approved")
    elif not _approval_contract_valid(_as_dict(approval)):
        blockers.append("desktop_input_observation_authority_approval_contract_invalid")
    if not permission.allowed:
        blockers.append("system_write_scope_not_ready")
    blockers = sorted(set(blockers))
    authority_granted = approval_ready and permission.allowed and not blockers
    safe_lease_seconds = _safe_lease_seconds(lease_seconds)
    response: dict[str, Any] = {
        "ok": True,
        "kind": (
            "lens.perception.desktop_input_observation_authority.grant"
            if authority_granted
            else "lens.perception.desktop_input_observation_authority.grant_denial"
        ),
        "status": "authority_granted" if authority_granted else "blocked",
        "route": safe_route,
        "action": LENS_PERCEPTION_INPUT_AUTHORITY_ACTION,
        "approval_id": safe_approval_id,
        "approval": {
            "required": True,
            "found": bool(approval),
            "status": approval_status,
            "approved": approval_ready,
            "item": _display(_as_dict(approval)) if approval else {},
        },
        "actor": redact_secret_text(_safe_str(actor)),
        "reason": redact_secret_text(_safe_str(reason)),
        "lease_seconds": safe_lease_seconds,
        "authority_granted": authority_granted,
        "desktop_input_observation_authority": authority_granted,
        "receipt_write_authority": authority_granted,
        "applied": False,
        "executed": False,
        "starts_observation": False,
        "launches_process": False,
        "receipt_written": False,
        "receipt": {},
        "blockers": blockers,
        "governance": {
            **_governance(
                route=safe_route,
                read_only_contract=False,
                approval_request_write=False,
                authority_granted=authority_granted,
            ),
            "permission": permission.evidence,
            "next_step": (
                "enable_observer_only_through_a_separately_governed_execution_handoff"
                if authority_granted
                else "select_exact_approved_desktop_input_observation_authority_request"
            ),
        },
    }
    if record_receipt and authority_granted:
        try:
            receipt = _write_receipt(response)
        except OSError:
            receipt = {}
        if receipt:
            response["receipt_written"] = True
            response["receipt"] = receipt
            response["applied"] = True
    return response


def _read_json(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig", errors="replace"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / f".{os.getpid():x}.{time.time_ns():x}.tmp"
    try:
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


__all__ = [
    "LENS_PERCEPTION_INPUT_AUTHORITY_ACTION",
    "LENS_PERCEPTION_INPUT_AUTHORITY_GRANTS_ROUTE",
    "LENS_PERCEPTION_INPUT_AUTHORITY_REQUEST_ROUTE",
    "LENS_PERCEPTION_INPUT_AUTHORITY_REQUESTS_ROUTE",
    "LENS_PERCEPTION_INPUT_AUTHORITY_ROUTE",
    "LENS_PERCEPTION_INPUT_FORBIDDEN_CONTENT",
    "LENS_PERCEPTION_INPUT_OBSERVATIONS",
    "grant_lens_perception_input_authority",
    "lens_perception_input_authority_grant_receipts",
    "lens_perception_input_authority_receipt_status",
    "lens_perception_input_authority_request_readback",
    "request_lens_perception_input_authority",
]
