"""Approval request/readback boundary for resident Lens perception execution."""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

from francis.governance.approval_projection import approval_projection_fields
from francis.governance.approvals import list_requests, request as create_approval_request
from francis.governance.api_permission_gate import ApiPermissionDecision, ApiPermissionGate
from francis.governance.redaction import redact_governed_display_value, redact_secret_text
from francis.kernel.paths import data_dir
from francis.lens.perception_authority import lens_perception_desktop_authority_receipt_status
from francis.lens.perception_worker import (
    LENS_PERCEPTION_EXECUTION_ACTION,
    LENS_PERCEPTION_EXECUTION_REQUEST_KIND,
    lens_perception_execution_approval_status,
)

LENS_PERCEPTION_EXECUTION_SCOPE = "system.write"
LENS_PERCEPTION_EXECUTION_REQUEST_ROUTE = "/lens/perception/execution/request"
LENS_PERCEPTION_EXECUTION_REQUESTS_ROUTE = "/lens/perception/execution/requests"
LENS_PERCEPTION_EXECUTION_ENABLE_ROUTE = "/lens/perception/execution/enable"
LENS_PERCEPTION_EXECUTION_ENABLEMENT_ROUTE = "/lens/perception/execution/enablement"

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


def enable_lens_perception_execution(
    *,
    approval_id: Any,
    authority_receipt_id: Any,
    actor: Any,
    reason: Any = "enable approved resident Lens desktop perception execution handoff",
    route: str = LENS_PERCEPTION_EXECUTION_ENABLE_ROUTE,
    method: str = "POST",
) -> dict[str, Any]:
    safe_route = _safe_str(route) or LENS_PERCEPTION_EXECUTION_ENABLE_ROUTE
    safe_approval_id = _safe_str(approval_id)
    safe_receipt_id = _safe_str(authority_receipt_id)
    permission = _permission(actor, route=safe_route, method=method)
    authority = lens_perception_desktop_authority_receipt_status(safe_receipt_id)
    execution = lens_perception_execution_approval_status(safe_approval_id, safe_receipt_id)
    blockers: list[str] = []
    if not permission.allowed:
        blockers.append("system_write_scope_not_ready")
    if authority.get("active") is not True:
        blockers.extend(_string_items(authority.get("blockers")) or ["desktop_capture_authority_not_active"])
    if execution.get("active") is not True:
        blockers.extend(_string_items(execution.get("blockers")) or ["desktop_capture_execution_not_approved"])
    if blockers:
        return {
            "ok": True,
            "kind": "lens.perception.desktop_capture_execution.enablement_denial",
            "status": "blocked",
            "route": safe_route,
            "approval_id": safe_approval_id,
            "authority_receipt_id": safe_receipt_id,
            "applied": False,
            "executed": False,
            "starts_capture": False,
            "launches_process": False,
            "receipt_written": False,
            "blockers": _dedupe(blockers),
            "governance": _governance(
                route=safe_route,
                approval_request_write=False,
                permission=permission,
            ),
        }

    now_ns = time.time_ns()
    now = now_ns // 1_000_000_000
    enablement_receipt_id = _enablement_receipt_id(
        approval_id=safe_approval_id,
        authority_receipt_id=safe_receipt_id,
        actor=_safe_str(actor),
        issued_at_ns=now_ns,
    )
    expires_ts = int(authority.get("expires_ts") or 0)
    receipt = {
        "kind": "lens.perception.desktop_capture_execution.enablement_receipt",
        "version": 1,
        "receipt_id": enablement_receipt_id,
        "status": "enabled_for_host_consumption",
        "ts": now,
        "expires_ts": expires_ts,
        "approval_id": safe_approval_id,
        "approval_action": LENS_PERCEPTION_EXECUTION_ACTION,
        "authority_receipt_id": safe_receipt_id,
        "actor": redact_secret_text(_safe_str(actor)),
        "reason": redact_secret_text(_safe_str(reason)),
        "source": "desktop_ring_buffer",
        "mode": "resident",
        "enable_route": LENS_PERCEPTION_EXECUTION_ENABLE_ROUTE,
        "enablement_route": LENS_PERCEPTION_EXECUTION_ENABLEMENT_ROUTE,
        "applied": True,
        "executed": False,
        "starts_capture": False,
        "launches_process": False,
        "authorities": {
            "desktop_capture_authority": True,
            "execution_authority": True,
            "host_handoff_write_authority": True,
            "camera_capture_authority": False,
            "microphone_capture_authority": False,
            "keyboard_capture_authority": False,
            "user_mouse_capture_authority": False,
            "input_execution_authority": False,
            "memory_write": False,
        },
    }
    enablement = {
        "kind": "lens.perception.desktop_capture_execution.enablement",
        "version": 1,
        "status": "enabled_for_host_consumption",
        "enabled": True,
        "enabled_at": now,
        "expires_ts": expires_ts,
        "enablement_receipt_id": enablement_receipt_id,
        "approval_id": safe_approval_id,
        "authority_receipt_id": safe_receipt_id,
        "source": "desktop_ring_buffer",
        "mode": "resident",
        "worker_module": "francis.lens.perception_worker",
        "sample_rate_hz": 2.0,
        "retention_seconds": 120.0,
        "max_frames": 240,
        "camera_capture_authority": False,
        "microphone_capture_authority": False,
        "keyboard_capture_authority": False,
        "user_mouse_capture_authority": False,
        "input_execution_authority": False,
        "memory_write": False,
    }
    _atomic_write_json(_enablement_receipt_path(enablement_receipt_id), receipt)
    _atomic_write_json(_enablement_path(), enablement)
    return {
        "ok": True,
        "kind": "lens.perception.desktop_capture_execution.enablement",
        "status": "enabled_for_host_consumption",
        "route": safe_route,
        "approval_id": safe_approval_id,
        "authority_receipt_id": safe_receipt_id,
        "enablement_receipt_id": enablement_receipt_id,
        "enablement": enablement,
        "applied": True,
        "executed": False,
        "starts_capture": False,
        "launches_process": False,
        "receipt_written": True,
        "receipt": receipt,
        "blockers": ["lens_perception_worker_runtime_not_observed"],
        "governance": {
            **_governance(
                route=safe_route,
                approval_request_write=False,
                permission=permission,
            ),
            "host_handoff_write_authority": True,
            "receipt_write_authority": True,
            "mutation_authority_granted": True,
            "next_step": "resident_host_consume_perception_enablement",
        },
    }


def lens_perception_execution_enablement_readback() -> dict[str, Any]:
    enablement = _read_json(_enablement_path())
    approval_id = _safe_str(enablement.get("approval_id"))
    authority_receipt_id = _safe_str(enablement.get("authority_receipt_id"))
    enablement_receipt_id = _safe_str(enablement.get("enablement_receipt_id"))
    receipt = _read_json(_enablement_receipt_path(enablement_receipt_id))
    authority = lens_perception_desktop_authority_receipt_status(authority_receipt_id)
    execution = lens_perception_execution_approval_status(approval_id, authority_receipt_id)
    blockers: list[str] = []
    if not enablement:
        blockers.append("lens_perception_execution_enablement_missing")
    else:
        if enablement.get("kind") != "lens.perception.desktop_capture_execution.enablement":
            blockers.append("lens_perception_execution_enablement_invalid")
        if enablement.get("enabled") is not True or enablement.get("status") != "enabled_for_host_consumption":
            blockers.append("lens_perception_execution_enablement_not_active")
        if enablement.get("source") != "desktop_ring_buffer" or enablement.get("mode") != "resident":
            blockers.append("lens_perception_execution_enablement_scope_invalid")
        if any(
            enablement.get(field) is not False
            for field in (
                "camera_capture_authority",
                "microphone_capture_authority",
                "keyboard_capture_authority",
                "user_mouse_capture_authority",
                "input_execution_authority",
                "memory_write",
            )
        ):
            blockers.append("lens_perception_execution_enablement_overbroad")
    if not receipt or receipt.get("receipt_id") != enablement_receipt_id:
        blockers.append("lens_perception_execution_enablement_receipt_missing")
    else:
        if (
            receipt.get("kind") != "lens.perception.desktop_capture_execution.enablement_receipt"
            or receipt.get("status") != "enabled_for_host_consumption"
        ):
            blockers.append("lens_perception_execution_enablement_receipt_invalid")
        if (
            _safe_str(receipt.get("approval_id")) != approval_id
            or _safe_str(receipt.get("authority_receipt_id")) != authority_receipt_id
            or receipt.get("source") != "desktop_ring_buffer"
            or receipt.get("mode") != "resident"
        ):
            blockers.append("lens_perception_execution_enablement_receipt_scope_mismatch")
        receipt_authorities = _as_dict(receipt.get("authorities"))
        if any(
            receipt_authorities.get(field) is not False
            for field in (
                "camera_capture_authority",
                "microphone_capture_authority",
                "keyboard_capture_authority",
                "user_mouse_capture_authority",
                "input_execution_authority",
                "memory_write",
            )
        ):
            blockers.append("lens_perception_execution_enablement_receipt_overbroad")
        if (
            receipt_authorities.get("desktop_capture_authority") is not True
            or receipt_authorities.get("execution_authority") is not True
            or receipt_authorities.get("host_handoff_write_authority") is not True
        ):
            blockers.append("lens_perception_execution_enablement_receipt_authority_missing")
    enablement_expires_ts = int(_safe_float(enablement.get("expires_ts")))
    receipt_expires_ts = int(_safe_float(receipt.get("expires_ts")))
    if enablement and (enablement_expires_ts <= int(time.time()) or receipt_expires_ts != enablement_expires_ts):
        blockers.append("lens_perception_execution_enablement_expired_or_mismatched")
    if authority.get("active") is not True:
        blockers.extend(_string_items(authority.get("blockers")) or ["desktop_capture_authority_not_active"])
    if execution.get("active") is not True:
        blockers.extend(_string_items(execution.get("blockers")) or ["desktop_capture_execution_not_approved"])
    ready = not blockers
    return {
        "ok": True,
        "kind": "lens.perception.desktop_capture_execution.enablement_readback",
        "status": "ready_for_host_consumption" if ready else "missing" if not enablement else "blocked",
        "ready": ready,
        "route": LENS_PERCEPTION_EXECUTION_ENABLEMENT_ROUTE,
        "enable_route": LENS_PERCEPTION_EXECUTION_ENABLE_ROUTE,
        "approval_id": approval_id,
        "authority_receipt_id": authority_receipt_id,
        "enablement_receipt_id": enablement_receipt_id,
        "enablement": enablement,
        "receipt": receipt,
        "capture_authority": authority,
        "execution_validation": execution,
        "executed": False,
        "worker_runtime_observed": False,
        "blockers": _dedupe(blockers),
        "governance": {
            **_governance(
                route=LENS_PERCEPTION_EXECUTION_ENABLEMENT_ROUTE,
                approval_request_write=False,
                permission=None,
            ),
            "read_only_contract": True,
            "next_step": "resident_host_consume_perception_enablement" if ready else "resolve_enablement_blockers",
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


def _enablement_root() -> Path:
    return data_dir() / "runtime" / "lens-perception" / "execution"


def _enablement_path() -> Path:
    return _enablement_root() / "enablement.json"


def _enablement_receipt_path(receipt_id: Any) -> Path:
    cleaned = _safe_file_token(receipt_id)
    return _enablement_root() / "receipts" / f"{cleaned or '__missing__'}.json"


def _enablement_receipt_id(
    *,
    approval_id: str,
    authority_receipt_id: str,
    actor: str,
    issued_at_ns: int,
) -> str:
    material = "\0".join((approval_id, authority_receipt_id, actor, str(issued_at_ns)))
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:24]
    return f"lens-perception-execution-enable-{digest}"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig", errors="replace"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".tmp-{os.getpid()}-{time.time_ns()}.json")
    try:
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _safe_file_token(value: Any) -> str:
    cleaned = _safe_str(value)
    if not cleaned or "/" in cleaned or "\\" in cleaned or ".." in cleaned or len(cleaned) > 180:
        return ""
    return cleaned


def _string_items(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_safe_str(item) for item in value if _safe_str(item)]


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


__all__ = [
    "LENS_PERCEPTION_EXECUTION_ENABLE_ROUTE",
    "LENS_PERCEPTION_EXECUTION_ENABLEMENT_ROUTE",
    "LENS_PERCEPTION_EXECUTION_REQUEST_ROUTE",
    "LENS_PERCEPTION_EXECUTION_REQUESTS_ROUTE",
    "enable_lens_perception_execution",
    "lens_perception_execution_enablement_readback",
    "lens_perception_execution_request_readback",
    "request_lens_perception_execution",
]
