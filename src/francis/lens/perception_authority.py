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

LENS_PERCEPTION_AUTHORITY_SCOPE = "system.write"
LENS_PERCEPTION_AUTHORITY_ACTION = "lens.perception.desktop_capture_authority"
LENS_PERCEPTION_AUTHORITY_ROUTE = "/lens/perception/authority"
LENS_PERCEPTION_AUTHORITY_REQUEST_ROUTE = "/lens/perception/authority/request"
LENS_PERCEPTION_AUTHORITY_REQUESTS_ROUTE = "/lens/perception/authority/requests"
LENS_PERCEPTION_AUTHORITY_GRANTS_ROUTE = "/lens/perception/authority/grants"

_APPROVAL_STATUSES = ("pending", "approved", "rejected", "emergency")
_GRANT_RECEIPT_KIND = "lens.perception.desktop_capture_authority.grant_receipt"
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


def _redact_free_text(value: Any) -> str:
    return redact_secret_text(_safe_str(value))


def _display(record: dict[str, Any]) -> dict[str, Any]:
    redacted = redact_governed_display_value(record)
    return redacted if isinstance(redacted, dict) else {}


def _atomic_write_json(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    os.replace(tmp, path)


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig", errors="replace"))
    except (OSError, json.JSONDecodeError):
        return None
    return raw if isinstance(raw, dict) else None


def _permission(actor: Any, *, route: str, method: str) -> ApiPermissionDecision:
    return ApiPermissionGate.from_env().check(
        actor_id=actor,
        required_scopes=[LENS_PERCEPTION_AUTHORITY_SCOPE],
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
        "gate": "lens_perception_desktop_capture_authority",
        "route": route,
        "required_scope": LENS_PERCEPTION_AUTHORITY_SCOPE,
        "approval_action": LENS_PERCEPTION_AUTHORITY_ACTION,
        "authority_route": LENS_PERCEPTION_AUTHORITY_ROUTE,
        "request_route": LENS_PERCEPTION_AUTHORITY_REQUEST_ROUTE,
        "requests_route": LENS_PERCEPTION_AUTHORITY_REQUESTS_ROUTE,
        "grants_route": LENS_PERCEPTION_AUTHORITY_GRANTS_ROUTE,
        "decision_route": "/approvals/decision",
        "read_only_contract": read_only_contract,
        "approval_request_write": approval_request_write,
        "authority_granted": authority_granted,
        "desktop_capture_authority": authority_granted,
        "capture_authority": authority_granted,
        "new_sensing_authority": authority_granted,
        "receipt_write_authority": authority_granted,
        "execution_authority": False,
        "process_launch_authority": False,
        "process_supervision_authority": False,
        "camera_capture_authority": False,
        "microphone_capture_authority": False,
        "keyboard_capture_authority": False,
        "user_mouse_capture_authority": False,
        "input_execution_authority": False,
        "memory_write": False,
        "approval_decision_authority": False,
        "mutation_authority_granted": False,
    }


def _permission_denied(decision: ApiPermissionDecision, *, route: str) -> dict[str, Any]:
    return {
        "ok": False,
        "status": "denied",
        "error": "api_permission_denied",
        "action": LENS_PERCEPTION_AUTHORITY_ACTION,
        "approval_requested": False,
        "authority_granted": False,
        "desktop_capture_authority": False,
        "applied": False,
        "executed": False,
        "governance": {
            **_governance(
                route=route,
                read_only_contract=False,
                approval_request_write=False,
            ),
            "gate": "permission_gate",
            "reason": decision.reason,
            "permission": decision.evidence,
        },
    }


def _approval_item(record: dict[str, Any]) -> dict[str, Any]:
    item = dict(record) if isinstance(record, dict) else {}
    output = _display(item)
    output.update(approval_projection_fields(item))
    return output


def _approval_by_id(approval_id: str) -> tuple[dict[str, Any] | None, str]:
    if not approval_id or "/" in approval_id or "\\" in approval_id or ".." in approval_id:
        return None, "missing"
    approval_folders = (
        ("pending", pending_dir()),
        ("approved", approved_dir()),
        ("rejected", rejected_dir()),
        ("emergency", emergency_dir()),
    )
    for status, folder in approval_folders:
        record = _read_json(folder / f"{approval_id}.json")
        if record is None:
            continue
        if _safe_str(record.get("action")) != LENS_PERCEPTION_AUTHORITY_ACTION:
            return record, "wrong_action"
        return record, status
    return None, "not_found"


def _approval_items(*, limit: int) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]], dict[str, int]]:
    by_status: dict[str, list[dict[str, Any]]] = {}
    all_items: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    for status in _APPROVAL_STATUSES:
        try:
            records = list_requests(status=status, limit=5000)
        except Exception:
            records = []
        items = [
            _approval_item(item)
            for item in records
            if isinstance(item, dict) and _safe_str(item.get("action")) == LENS_PERCEPTION_AUTHORITY_ACTION
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


def request_lens_perception_authority(
    *,
    actor: Any,
    reason: Any = "request Lens desktop perception capture authority review",
    route: str = LENS_PERCEPTION_AUTHORITY_REQUEST_ROUTE,
    method: str = "POST",
) -> dict[str, Any]:
    safe_route = _safe_str(route) or LENS_PERCEPTION_AUTHORITY_REQUEST_ROUTE
    permission = _permission(actor, route=safe_route, method=method)
    if not permission.allowed:
        return _permission_denied(permission, route=safe_route)

    payload = {
        "kind": "lens.perception.desktop_capture_authority.request",
        "actor": _redact_free_text(actor),
        "route": safe_route,
        "plane": "desktop",
        "source": "desktop_ring_buffer",
        "authority_boundary": {
            "desktop_capture_authority": False,
            "capture_authority": False,
            "new_sensing_authority": False,
            "starts_capture": False,
            "launches_process": False,
            "camera_capture_authority": False,
            "keyboard_content_capture_authority": False,
            "user_mouse_capture_authority": False,
        },
        "governance": _governance(
            route=safe_route,
            read_only_contract=False,
            approval_request_write=True,
        ),
    }
    approval = create_approval_request(
        LENS_PERCEPTION_AUTHORITY_ACTION,
        _redact_free_text(reason) or "request Lens desktop perception capture authority review",
        payload,
    )
    approval_item = _approval_item(approval)
    return {
        "ok": True,
        "kind": "lens.perception.desktop_capture_authority.request",
        "status": "approval_requested",
        "action": LENS_PERCEPTION_AUTHORITY_ACTION,
        "approval_requested": True,
        "approval_id": _safe_str(approval_item.get("id")),
        "approval": approval_item,
        "authority_granted": False,
        "desktop_capture_authority": False,
        "applied": False,
        "executed": False,
        "governance": {
            **_governance(
                route=safe_route,
                read_only_contract=False,
                approval_request_write=True,
            ),
            "permission": permission.evidence,
        },
    }


def _grant_receipt_root() -> Path:
    return data_dir() / "lens" / "perception_desktop_capture_authority_grants"


def _grant_receipt_path(receipt_id: Any) -> Path | None:
    cleaned = _safe_str(receipt_id)
    if not cleaned or "/" in cleaned or "\\" in cleaned or ".." in cleaned:
        return None
    return _grant_receipt_root() / f"{cleaned}.json"


def _grant_receipt_id(*, approval_id: str, actor: str, ts: int) -> str:
    seed = f"{approval_id}:{actor}:{time.time_ns()}"
    digest = hashlib.sha256(seed.encode("utf-8", errors="replace")).hexdigest()[:12]
    return f"lpcag_{ts}_{digest}"


def _build_grant_receipt(response: dict[str, Any]) -> dict[str, Any]:
    ts = int(time.time())
    approval_id = _safe_str(response.get("approval_id"))
    actor = _safe_str(response.get("actor"))
    lease_seconds = _safe_lease_seconds(response.get("lease_seconds"))
    return {
        "kind": _GRANT_RECEIPT_KIND,
        "receipt_id": _grant_receipt_id(approval_id=approval_id, actor=actor, ts=ts),
        "ts": ts,
        "status": "authority_granted",
        "approval_id": approval_id,
        "approval_action": LENS_PERCEPTION_AUTHORITY_ACTION,
        "actor": actor,
        "route": LENS_PERCEPTION_AUTHORITY_ROUTE,
        "requests_route": LENS_PERCEPTION_AUTHORITY_REQUESTS_ROUTE,
        "grants_route": LENS_PERCEPTION_AUTHORITY_GRANTS_ROUTE,
        "plane": "desktop",
        "source": "desktop_ring_buffer",
        "lease_seconds": lease_seconds,
        "expires_ts": ts + lease_seconds,
        "authority_granted": True,
        "authorities": {
            "desktop_capture_authority": True,
            "capture_authority": True,
            "new_sensing_authority": True,
            "receipt_write_authority": True,
            "execution_authority": False,
            "process_launch_authority": False,
            "process_supervision_authority": False,
            "camera_capture_authority": False,
            "microphone_capture_authority": False,
            "keyboard_capture_authority": False,
            "user_mouse_capture_authority": False,
            "input_execution_authority": False,
            "memory_write": False,
            "approval_decision_authority": False,
        },
        "governance": _governance(
            route=LENS_PERCEPTION_AUTHORITY_GRANTS_ROUTE,
            read_only_contract=True,
            approval_request_write=False,
            authority_granted=True,
        ),
    }


def _record_grant_receipt(response: dict[str, Any]) -> dict[str, Any]:
    receipt = _build_grant_receipt(response)
    path = _grant_receipt_path(receipt.get("receipt_id"))
    if path is None:
        return {}
    try:
        _atomic_write_json(path, receipt)
    except OSError:
        return {}
    return receipt


def _read_grant_receipt(path: Path) -> dict[str, Any] | None:
    receipt = _read_json(path)
    if not isinstance(receipt, dict) or _safe_str(receipt.get("kind")) != _GRANT_RECEIPT_KIND:
        return None
    return receipt


def lens_perception_desktop_authority_receipt_status(
    receipt_id: Any,
    *,
    now: int | None = None,
) -> dict[str, Any]:
    clean_receipt_id = _safe_str(receipt_id)
    path = _grant_receipt_path(clean_receipt_id)
    if path is None:
        return {
            "status": "missing",
            "valid": False,
            "active": False,
            "receipt_id": clean_receipt_id,
            "blockers": ["desktop_capture_authority_receipt_missing"],
        }
    receipt = _read_grant_receipt(path)
    if receipt is None:
        return {
            "status": "not_found",
            "valid": False,
            "active": False,
            "receipt_id": clean_receipt_id,
            "blockers": ["desktop_capture_authority_receipt_not_found"],
        }

    blockers: list[str] = []
    authorities = _as_dict(receipt.get("authorities"))
    approval_id = _safe_str(receipt.get("approval_id"))
    approval, approval_status = _approval_by_id(approval_id)
    if _safe_str(receipt.get("receipt_id")) != clean_receipt_id:
        blockers.append("desktop_capture_authority_receipt_id_mismatch")
    if _safe_str(receipt.get("status")) != "authority_granted" or receipt.get("authority_granted") is not True:
        blockers.append("desktop_capture_authority_receipt_invalid")
    if _safe_str(receipt.get("approval_action")) != LENS_PERCEPTION_AUTHORITY_ACTION:
        blockers.append("desktop_capture_authority_receipt_wrong_action")
    if _safe_str(receipt.get("plane")) != "desktop":
        blockers.append("desktop_capture_authority_receipt_wrong_plane")
    if _safe_str(receipt.get("source")) != "desktop_ring_buffer":
        blockers.append("desktop_capture_authority_receipt_wrong_source")
    if _safe_str(receipt.get("route")) != LENS_PERCEPTION_AUTHORITY_ROUTE:
        blockers.append("desktop_capture_authority_receipt_wrong_route")
    if not all(
        authorities.get(name) is True
        for name in (
            "desktop_capture_authority",
            "capture_authority",
            "new_sensing_authority",
            "receipt_write_authority",
        )
    ):
        blockers.append("desktop_capture_authority_receipt_scope_invalid")
    if any(
        authorities.get(name) is not False
        for name in (
            "execution_authority",
            "process_launch_authority",
            "process_supervision_authority",
            "camera_capture_authority",
            "microphone_capture_authority",
            "keyboard_capture_authority",
            "user_mouse_capture_authority",
            "input_execution_authority",
            "memory_write",
            "approval_decision_authority",
        )
    ):
        blockers.append("desktop_capture_authority_receipt_overbroad")
    if not approval or approval_status != "approved":
        blockers.append("desktop_capture_authority_approval_not_approved")
    expires_ts = int(_record_ts(receipt.get("expires_ts")))
    if expires_ts <= 0:
        blockers.append("desktop_capture_authority_receipt_expiry_invalid")
    elif expires_ts <= (int(time.time()) if now is None else int(now)):
        blockers.append("desktop_capture_authority_receipt_expired")

    valid = not blockers
    return {
        "status": "active" if valid else "blocked",
        "valid": valid,
        "active": valid,
        "receipt_id": clean_receipt_id,
        "approval_id": approval_id,
        "approval_status": approval_status,
        "plane": _safe_str(receipt.get("plane")) or "unknown",
        "expires_ts": expires_ts or None,
        "blockers": sorted(set(blockers)),
    }


def _list_grant_receipts(
    *,
    limit: int,
    approval_id: str,
    status: str,
    active_only: bool,
) -> tuple[list[dict[str, Any]], int]:
    root = _grant_receipt_root()
    if not root.exists():
        return [], 0
    items: list[dict[str, Any]] = []
    for path in root.glob("*.json"):
        receipt = _read_grant_receipt(path)
        if receipt is None:
            continue
        if approval_id and _safe_str(receipt.get("approval_id")) != approval_id:
            continue
        if status and _safe_str(receipt.get("status")) != status:
            continue
        receipt_status = lens_perception_desktop_authority_receipt_status(receipt.get("receipt_id"))
        if active_only and not receipt_status.get("active"):
            continue
        items.append({**receipt, "validation": receipt_status})
    items.sort(key=lambda item: (_record_ts(item.get("ts")), _safe_str(item.get("receipt_id"))), reverse=True)
    return items[:limit], len(items)


def lens_perception_authority_grant_receipts(
    *,
    limit: int = 5,
    approval_id: Any = "",
    status: Any = "",
    active_only: bool = False,
) -> dict[str, Any]:
    safe_limit = _safe_limit(limit)
    items, total = _list_grant_receipts(
        limit=safe_limit,
        approval_id=_safe_str(approval_id),
        status=_safe_str(status),
        active_only=active_only,
    )
    active_latest = next((item for item in items if _as_dict(item.get("validation")).get("active")), None)
    authority_granted = active_latest is not None
    return {
        "ok": True,
        "kind": "lens.perception.desktop_capture_authority.grant_receipts",
        "status": "readback_ready" if items else "empty",
        "route": LENS_PERCEPTION_AUTHORITY_GRANTS_ROUTE,
        "authority_route": LENS_PERCEPTION_AUTHORITY_ROUTE,
        "request_route": LENS_PERCEPTION_AUTHORITY_REQUEST_ROUTE,
        "requests_route": LENS_PERCEPTION_AUTHORITY_REQUESTS_ROUTE,
        "limit": safe_limit,
        "total": total,
        "latest": items[0] if items else None,
        "active_latest": active_latest,
        "authority_granted": authority_granted,
        "desktop_capture_authority": authority_granted,
        "items": items,
        "governance": _governance(
            route=LENS_PERCEPTION_AUTHORITY_GRANTS_ROUTE,
            read_only_contract=True,
            approval_request_write=False,
            authority_granted=authority_granted,
        ),
    }


def lens_perception_authority_request_readback(*, limit: int = 5) -> dict[str, Any]:
    safe_limit = _safe_limit(limit)
    by_status, latest, counts = _approval_items(limit=safe_limit)
    grants = lens_perception_authority_grant_receipts(limit=1, active_only=True)
    authority_granted = grants.get("authority_granted") is True
    if authority_granted:
        status = "authority_granted"
        next_step = "start_desktop_capture_only_through_a_separately_governed_execution_path"
    elif counts.get("pending", 0):
        status = "pending_review"
        next_step = "operator_decide_pending_desktop_capture_authority_request"
    elif counts.get("approved", 0):
        status = "approved_no_authority"
        next_step = "grant_exact_approved_desktop_capture_authority_request"
    elif counts.get("rejected", 0):
        status = "rejected"
        next_step = "operator_may_request_desktop_capture_authority_again"
    else:
        status = "none"
        next_step = "request_desktop_capture_authority"
    return {
        "ok": True,
        "kind": "lens.perception.desktop_capture_authority.request_readback",
        "status": status,
        "route": LENS_PERCEPTION_AUTHORITY_REQUESTS_ROUTE,
        "authority_route": LENS_PERCEPTION_AUTHORITY_ROUTE,
        "request_route": LENS_PERCEPTION_AUTHORITY_REQUEST_ROUTE,
        "grants_route": LENS_PERCEPTION_AUTHORITY_GRANTS_ROUTE,
        "action": LENS_PERCEPTION_AUTHORITY_ACTION,
        "approval_counts": counts,
        "latest": latest[0] if latest else None,
        "pending": by_status.get("pending", []),
        "approved": by_status.get("approved", []),
        "rejected": by_status.get("rejected", []),
        "emergency": by_status.get("emergency", []),
        "active_authority_grant": _as_dict(grants.get("active_latest")),
        "authority_granted": authority_granted,
        "desktop_capture_authority": authority_granted,
        "governance": {
            **_governance(
                route=LENS_PERCEPTION_AUTHORITY_REQUESTS_ROUTE,
                read_only_contract=True,
                approval_request_write=False,
                authority_granted=authority_granted,
            ),
            "next_step": next_step,
        },
    }


def grant_lens_perception_authority(
    *,
    approval_id: Any = "",
    actor: Any = "",
    reason: Any = "attempt Lens desktop perception capture authority grant",
    route: str = LENS_PERCEPTION_AUTHORITY_ROUTE,
    method: str = "POST",
    record_receipt: bool = False,
    lease_seconds: Any = _DEFAULT_LEASE_SECONDS,
) -> dict[str, Any]:
    safe_route = _safe_str(route) or LENS_PERCEPTION_AUTHORITY_ROUTE
    safe_approval_id = _safe_str(approval_id)
    approval, lookup_status = _approval_by_id(safe_approval_id)
    approval_status = _safe_str(_as_dict(approval).get("status")) if approval else lookup_status
    approval_ready = bool(approval) and approval_status == "approved"
    permission = _permission(actor, route=safe_route, method=method)
    blockers: list[str] = []
    if not safe_approval_id:
        blockers.append("approval_id_required")
    elif lookup_status == "not_found":
        blockers.append("desktop_capture_authority_approval_not_found")
    elif lookup_status == "wrong_action":
        blockers.append("desktop_capture_authority_approval_wrong_action")
    elif not approval_ready:
        blockers.append("desktop_capture_authority_approval_not_approved")
    if not permission.allowed:
        blockers.append("system_write_scope_not_ready")
    blockers = sorted(set(blockers))
    authority_granted = approval_ready and permission.allowed and not blockers
    safe_lease_seconds = _safe_lease_seconds(lease_seconds)
    response: dict[str, Any] = {
        "ok": True,
        "kind": (
            "lens.perception.desktop_capture_authority.grant"
            if authority_granted
            else "lens.perception.desktop_capture_authority.grant_denial"
        ),
        "status": "authority_granted" if authority_granted else "blocked",
        "route": safe_route,
        "action": LENS_PERCEPTION_AUTHORITY_ACTION,
        "approval_id": safe_approval_id,
        "approval": {
            "required": True,
            "found": bool(approval),
            "status": approval_status,
            "approved": approval_ready,
            "item": _approval_item(_as_dict(approval)) if approval else {},
        },
        "actor": _redact_free_text(actor),
        "reason": _redact_free_text(reason),
        "lease_seconds": safe_lease_seconds,
        "authority_granted": authority_granted,
        "desktop_capture_authority": authority_granted,
        "capture_authority": authority_granted,
        "new_sensing_authority": authority_granted,
        "receipt_write_authority": authority_granted,
        "applied": False,
        "executed": False,
        "starts_capture": False,
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
                "start_desktop_capture_only_through_a_separately_governed_execution_path"
                if authority_granted
                else "select_exact_approved_desktop_capture_authority_request"
            ),
        },
    }
    if record_receipt and authority_granted:
        receipt = _record_grant_receipt(response)
        if receipt:
            response["receipt_written"] = True
            response["receipt"] = receipt
            response["applied"] = True
    return response


__all__ = [
    "LENS_PERCEPTION_AUTHORITY_ACTION",
    "LENS_PERCEPTION_AUTHORITY_GRANTS_ROUTE",
    "LENS_PERCEPTION_AUTHORITY_REQUEST_ROUTE",
    "LENS_PERCEPTION_AUTHORITY_REQUESTS_ROUTE",
    "LENS_PERCEPTION_AUTHORITY_ROUTE",
    "grant_lens_perception_authority",
    "lens_perception_authority_grant_receipts",
    "lens_perception_authority_request_readback",
    "lens_perception_desktop_authority_receipt_status",
    "request_lens_perception_authority",
]
