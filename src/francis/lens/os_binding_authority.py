from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from francis.governance.approval_projection import approval_projection_fields
from francis.governance.approvals import list_requests, request as create_approval_request
from francis.governance.api_permission_gate import ApiPermissionDecision, ApiPermissionGate
from francis.governance.redaction import redact_governed_display_value, redact_secret_text
from francis.kernel.paths import data_dir, repo_root
from francis.lens.errors import lens_error_code
from francis.lens.preflight import lens_os_binding_implementation_plan, lens_os_binding_readiness

LENS_OS_BINDING_AUTHORITY_SCOPE = "system.write"
LENS_OS_BINDING_AUTHORITY_REQUEST_ACTION = "lens.os_binding.command_palette_binding_authority"
LENS_OS_BINDING_AUTHORITY_ROUTE = "/lens/os-binding/authority"
LENS_OS_BINDING_AUTHORITY_REQUEST_ROUTE = "/lens/os-binding/authority/request"
LENS_OS_BINDING_AUTHORITY_REQUESTS_ROUTE = "/lens/os-binding/authority/requests"
LENS_OS_BINDING_AUTHORITY_GRANTS_ROUTE = "/lens/os-binding/authority/grants"
LENS_OS_BINDING_EXECUTE_ROUTE = "/lens/os-binding/execute"
LENS_OS_BINDING_EXECUTIONS_ROUTE = "/lens/os-binding/executions"
LENS_OS_BINDING_DENIALS_ROUTE = "/lens/os-binding/denials"
LENS_OS_BINDING_EXECUTION_READINESS_ROUTE = "/lens/os-binding/execution/readiness"
LENS_OS_BINDING_READINESS_ROUTE = "/lens/os-binding/readiness"
LENS_OS_BINDING_PLAN_ROUTE = "/lens/os-binding/plan"
_APPROVAL_STATUSES = ("pending", "approved", "rejected", "emergency")
_DEFAULT_LEASE_SECONDS = 60 * 60
_MIN_LEASE_SECONDS = 60
_MAX_LEASE_SECONDS = 24 * 60 * 60
_DEFAULT_RUN_SECONDS = 5 * 60
_MAX_RUN_SECONDS = 60 * 60


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


def _safe_lease_seconds(value: Any) -> int:
    if isinstance(value, bool):
        return _DEFAULT_LEASE_SECONDS
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return _DEFAULT_LEASE_SECONDS
    return max(_MIN_LEASE_SECONDS, min(_MAX_LEASE_SECONDS, parsed))


def _safe_run_seconds(value: Any) -> int:
    if isinstance(value, bool):
        return _DEFAULT_RUN_SECONDS
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return _DEFAULT_RUN_SECONDS
    return max(0, min(_MAX_RUN_SECONDS, parsed))


def _record_ts(value: Any) -> float:
    if isinstance(value, bool):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _now_s() -> int:
    return int(time.time())


def _filtered_record(record: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in record.items() if value not in ("", {}, [], None)}


def _os_binding_authority_grant_receipt_root() -> Path:
    return data_dir() / "lens" / "os_binding_authority_grants"


def _os_binding_execution_denial_receipt_root() -> Path:
    return data_dir() / "lens" / "os_binding_execution_denials"


def _os_binding_execution_receipt_root() -> Path:
    return data_dir() / "lens" / "os_binding_executions"


def _os_binding_authority_grant_receipt_id(*, approval_id: str, actor: str, route: str, ts: int) -> str:
    seed = f"{approval_id}:{actor}:{route}:{time.time_ns()}"
    digest = hashlib.sha256(seed.encode("utf-8", errors="replace")).hexdigest()[:12]
    return f"losbag_{ts}_{digest}"


def _os_binding_execution_denial_receipt_id(*, approval_id: str, actor: str, route: str, ts: int) -> str:
    seed = f"{approval_id}:{actor}:{route}:{time.time_ns()}"
    digest = hashlib.sha256(seed.encode("utf-8", errors="replace")).hexdigest()[:12]
    return f"losbed_{ts}_{digest}"


def _os_binding_execution_receipt_id(*, approval_id: str, actor: str, route: str, ts: int) -> str:
    seed = f"{approval_id}:{actor}:{route}:{time.time_ns()}"
    digest = hashlib.sha256(seed.encode("utf-8", errors="replace")).hexdigest()[:12]
    return f"losbe_{ts}_{digest}"


def _os_binding_authority_grant_receipt_path(receipt_id: Any) -> Path | None:
    cleaned = _safe_str(receipt_id).strip()
    if not cleaned or "/" in cleaned or "\\" in cleaned or ".." in cleaned:
        return None
    return _os_binding_authority_grant_receipt_root() / f"{cleaned}.json"


def _os_binding_execution_denial_receipt_path(receipt_id: Any) -> Path | None:
    cleaned = _safe_str(receipt_id).strip()
    if not cleaned or "/" in cleaned or "\\" in cleaned or ".." in cleaned:
        return None
    return _os_binding_execution_denial_receipt_root() / f"{cleaned}.json"


def _os_binding_execution_receipt_path(receipt_id: Any) -> Path | None:
    cleaned = _safe_str(receipt_id).strip()
    if not cleaned or "/" in cleaned or "\\" in cleaned or ".." in cleaned:
        return None
    return _os_binding_execution_receipt_root() / f"{cleaned}.json"


def _atomic_write_json(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    os.replace(tmp, path)


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None
    return raw if isinstance(raw, dict) else None


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
        "grants_route": LENS_OS_BINDING_AUTHORITY_GRANTS_ROUTE,
        "execute_route": LENS_OS_BINDING_EXECUTE_ROUTE,
        "executions_route": LENS_OS_BINDING_EXECUTIONS_ROUTE,
        "denials_route": LENS_OS_BINDING_DENIALS_ROUTE,
        "execution_readiness_route": LENS_OS_BINDING_EXECUTION_READINESS_ROUTE,
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


def _approval_by_id(approval_id: str) -> tuple[dict[str, Any] | None, str]:
    requested_id = approval_id.strip()
    if not requested_id:
        return None, "missing"
    for status in _APPROVAL_STATUSES:
        for record in list_requests(status=status, limit=5000):
            if not isinstance(record, dict) or _safe_str(record.get("id")).strip() != requested_id:
                continue
            if _safe_str(record.get("action")).strip() != LENS_OS_BINDING_AUTHORITY_REQUEST_ACTION:
                return record, "wrong_action"
            return record, status
    return None, "not_found"


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


def _readback_status(counts: dict[str, int], *, authority_granted: bool = False) -> tuple[str, str]:
    if authority_granted:
        return "authority_granted", "review_os_binding_implementation_plan_before_command_palette_binding"
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
    readiness = lens_os_binding_readiness(
        authority_request_readback=lens_os_binding_authority_request_readback(),
    )
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
        "grants_route": LENS_OS_BINDING_AUTHORITY_GRANTS_ROUTE,
        "execute_route": LENS_OS_BINDING_EXECUTE_ROUTE,
        "denials_route": LENS_OS_BINDING_DENIALS_ROUTE,
        "execution_readiness_route": LENS_OS_BINDING_EXECUTION_READINESS_ROUTE,
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
        "grants_route": LENS_OS_BINDING_AUTHORITY_GRANTS_ROUTE,
        "execute_route": LENS_OS_BINDING_EXECUTE_ROUTE,
        "denials_route": LENS_OS_BINDING_DENIALS_ROUTE,
        "execution_readiness_route": LENS_OS_BINDING_EXECUTION_READINESS_ROUTE,
        "readiness_route": LENS_OS_BINDING_READINESS_ROUTE,
        "plan_route": LENS_OS_BINDING_PLAN_ROUTE,
        "method": "POST",
        "action": LENS_OS_BINDING_AUTHORITY_REQUEST_ACTION,
        "creates_approval_request": True,
        "grants_authority": False,
        "requires_separate_approved_request": True,
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


def _os_binding_authority_grant_receipt(grant_response: dict[str, Any]) -> dict[str, Any]:
    ts = _now_s()
    approval_id = _safe_str(grant_response.get("approval_id")).strip()
    actor = _safe_str(grant_response.get("actor")).strip()
    route = _safe_str(grant_response.get("route")).strip() or LENS_OS_BINDING_AUTHORITY_ROUTE
    lease_seconds = _safe_lease_seconds(grant_response.get("lease_seconds"))
    receipt_id = _os_binding_authority_grant_receipt_id(
        approval_id=approval_id,
        actor=actor,
        route=route,
        ts=ts,
    )
    return _filtered_record(
        {
            "kind": "lens.os_binding.command_palette_binding_authority.grant_receipt",
            "receipt_id": receipt_id,
            "ts": ts,
            "status": "authority_granted",
            "approval_id": approval_id,
            "actor": actor,
            "route": route,
            "authority_route": LENS_OS_BINDING_AUTHORITY_ROUTE,
            "request_route": LENS_OS_BINDING_AUTHORITY_REQUEST_ROUTE,
            "requests_route": LENS_OS_BINDING_AUTHORITY_REQUESTS_ROUTE,
            "grants_route": LENS_OS_BINDING_AUTHORITY_GRANTS_ROUTE,
            "executions_route": LENS_OS_BINDING_EXECUTIONS_ROUTE,
            "lease_seconds": lease_seconds,
            "expires_ts": ts + lease_seconds,
            "authority_granted": True,
            "os_level_command_palette_binding_authority": True,
            "hotkey_registration_authority": True,
            "local_process_launch_authority": True,
            "os_level_command_palette": False,
            "summon_anywhere": False,
            "opens_palette": False,
            "registers_hotkey": False,
            "launches_process": False,
            "controls_overlay": False,
            "governance": {
                **_governance(
                    route=LENS_OS_BINDING_AUTHORITY_GRANTS_ROUTE,
                    approval_request_write=False,
                    read_only_contract=True,
                ),
                "gate": "lens_os_binding_command_palette_authority_grant_receipt",
                "authority_grant_boundary": True,
                "authority_granted": True,
                "os_level_command_palette_binding_authority": True,
                "execution_authority": False,
                "approval_decision_authority": False,
                "memory_write": False,
                "summon_authority": False,
                "hotkey_registration_authority": True,
                "tray_registration_authority": False,
                "overlay_control_authority": False,
                "local_process_launch_authority": True,
                "process_supervision_authority": False,
                "service_control_authority": False,
                "window_management_authority": False,
                "capture_authority": False,
                "resident_claim_authority": False,
                "mutation_authority_granted": False,
                "receipt_write_authority": True,
            },
            "authorities": {
                "os_level_command_palette_binding_authority": True,
                "hotkey_registration_authority": True,
                "local_process_launch_authority": True,
                "receipt_write_authority": True,
                "summon_authority": False,
                "overlay_control_authority": False,
                "tray_registration_authority": False,
                "approval_decision_authority": False,
                "memory_write": False,
                "resident_claim_authority": False,
            },
        }
    )


def _record_os_binding_authority_grant_receipt(grant_response: dict[str, Any]) -> dict[str, Any]:
    receipt = _os_binding_authority_grant_receipt(grant_response)
    path = _os_binding_authority_grant_receipt_path(receipt.get("receipt_id"))
    if path is None:
        return {}
    try:
        _atomic_write_json(path, receipt)
    except OSError:
        return {}
    return receipt


def _read_os_binding_authority_grant_receipt(path: Path) -> dict[str, Any] | None:
    item = _read_json(path)
    if not isinstance(item, dict) or _safe_str(item.get("kind")).strip() != (
        "lens.os_binding.command_palette_binding_authority.grant_receipt"
    ):
        return None
    return item


def _os_binding_authority_grant_active(item: dict[str, Any], *, now: int | None = None) -> bool:
    if _safe_str(item.get("status")).strip() != "authority_granted":
        return False
    if not bool(item.get("authority_granted")):
        return False
    raw_expires_ts = item.get("expires_ts")
    if raw_expires_ts is None:
        return False
    try:
        expires_ts = int(raw_expires_ts)
    except (TypeError, ValueError):
        return False
    return expires_ts > (now if now is not None else _now_s())


def _list_os_binding_authority_grant_receipts(
    *,
    limit: int,
    approval_id: str = "",
    status: str = "",
    active_only: bool = False,
) -> tuple[list[dict[str, Any]], int]:
    root = _os_binding_authority_grant_receipt_root()
    if not root.exists():
        return [], 0
    now = _now_s()
    items: list[dict[str, Any]] = []
    for path in root.glob("*.json"):
        item = _read_os_binding_authority_grant_receipt(path)
        if item is None:
            continue
        if approval_id and _safe_str(item.get("approval_id")).strip() != approval_id:
            continue
        if status and _safe_str(item.get("status")).strip() != status:
            continue
        if active_only and not _os_binding_authority_grant_active(item, now=now):
            continue
        items.append(item)
    items.sort(key=lambda item: (_record_ts(item.get("ts")), _safe_str(item.get("receipt_id"))), reverse=True)
    return items[:limit], len(items)


def lens_os_binding_authority_grant_receipts(
    *,
    limit: int = 5,
    approval_id: Any = "",
    status: Any = "",
    active_only: bool = False,
) -> dict[str, Any]:
    safe_limit = _safe_limit(limit)
    safe_approval_id = _safe_str(approval_id).strip()
    safe_status = _safe_str(status).strip()
    items, total = _list_os_binding_authority_grant_receipts(
        limit=safe_limit,
        approval_id=safe_approval_id,
        status=safe_status,
        active_only=active_only,
    )
    latest = items[0] if items else None
    active_latest = next((item for item in items if _os_binding_authority_grant_active(item)), None)
    authority_granted = bool(active_latest)
    return {
        "ok": True,
        "kind": "lens.os_binding.command_palette_binding_authority.grant_receipts",
        "status": "readback_ready" if items else "empty",
        "route": LENS_OS_BINDING_AUTHORITY_GRANTS_ROUTE,
        "authority_route": LENS_OS_BINDING_AUTHORITY_ROUTE,
        "request_route": LENS_OS_BINDING_AUTHORITY_REQUEST_ROUTE,
        "requests_route": LENS_OS_BINDING_AUTHORITY_REQUESTS_ROUTE,
        "limit": safe_limit,
        "approval_id": safe_approval_id,
        "filter_status": safe_status,
        "active_only": active_only,
        "total": total,
        "latest": latest,
        "active_latest": active_latest,
        "authority_granted": authority_granted,
        "os_level_command_palette_binding_authority": authority_granted,
        "hotkey_registration_authority": authority_granted,
        "local_process_launch_authority": authority_granted,
        "os_level_command_palette": False,
        "summon_anywhere": False,
        "opens_palette": False,
        "registers_hotkey": False,
        "launches_process": False,
        "controls_overlay": False,
        "items": items,
        "governance": {
            **_governance(
                route=LENS_OS_BINDING_AUTHORITY_GRANTS_ROUTE,
                approval_request_write=False,
                read_only_contract=True,
            ),
            "gate": "lens_os_binding_command_palette_authority_grant_receipts_readback",
            "authority_grant_boundary": True,
            "authority_granted": authority_granted,
            "os_level_command_palette_binding_authority": authority_granted,
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
            "receipt_write_authority": authority_granted,
            "next_step": (
                "review_os_binding_implementation_plan_before_command_palette_binding"
                if authority_granted
                else "grant_exact_approved_os_binding_command_palette_authority_request"
            ),
        },
    }


def grant_lens_os_binding_authority(
    *,
    approval_id: Any = "",
    actor: Any = "",
    reason: Any = "attempt Lens OS-binding command palette authority grant",
    route: str = LENS_OS_BINDING_AUTHORITY_ROUTE,
    method: str = "POST",
    record_receipt: bool = False,
    lease_seconds: Any = _DEFAULT_LEASE_SECONDS,
) -> dict[str, Any]:
    safe_route = _safe_str(route).strip() or LENS_OS_BINDING_AUTHORITY_ROUTE
    safe_approval_id = _safe_str(approval_id).strip()
    approval, approval_lookup_status = _approval_by_id(safe_approval_id)
    approval = _as_dict(approval)
    approval_status = _safe_str(approval.get("status")).strip() if approval else approval_lookup_status
    approval_ready = bool(approval) and approval_status == "approved"
    permission = _permission(actor, route=safe_route, method=method)
    blockers: list[str] = []
    if not safe_approval_id:
        blockers.append("approval_id_required")
    elif approval_lookup_status == "not_found":
        blockers.append("os_binding_authority_approval_not_found")
    elif approval_lookup_status == "wrong_action":
        blockers.append("os_binding_authority_approval_wrong_action")
    elif not approval_ready:
        blockers.append("os_binding_authority_approval_not_approved")
    if not permission.allowed:
        blockers.append("system_write_scope_not_ready")
    deduped_blockers = _dedupe_strs(blockers)
    active_authority = approval_ready and permission.allowed and not deduped_blockers
    safe_lease_seconds = _safe_lease_seconds(lease_seconds)
    status = "authority_granted" if active_authority else "blocked"
    next_step = (
        "review_os_binding_implementation_plan_before_command_palette_binding"
        if active_authority
        else "select_exact_approved_os_binding_command_palette_authority_request"
    )
    governance = {
        **_governance(
            route=safe_route,
            approval_request_write=False,
            read_only_contract=False,
        ),
        "gate": (
            "lens_os_binding_command_palette_authority_grant_boundary"
            if active_authority
            else "lens_os_binding_command_palette_authority_grant_denial_boundary"
        ),
        "authority_grant_boundary": True,
        "authority_granted": active_authority,
        "os_level_command_palette_binding_authority": active_authority,
        "approval_request_write": False,
        "execution_authority": False,
        "approval_decision_authority": False,
        "memory_write": False,
        "summon_authority": False,
        "hotkey_registration_authority": active_authority,
        "tray_registration_authority": False,
        "overlay_control_authority": False,
        "local_process_launch_authority": active_authority,
        "process_supervision_authority": False,
        "service_control_authority": False,
        "window_management_authority": False,
        "capture_authority": False,
        "resident_claim_authority": False,
        "mutation_authority_granted": False,
        "receipt_write_authority": active_authority,
        "permission": permission.evidence,
        "next_step": next_step,
    }
    response: dict[str, Any] = {
        "ok": True,
        "kind": (
            "lens.os_binding.command_palette_binding_authority.grant"
            if active_authority
            else "lens.os_binding.command_palette_binding_authority.grant_denial"
        ),
        "status": status,
        "route": safe_route,
        "method": method,
        "request_route": LENS_OS_BINDING_AUTHORITY_REQUEST_ROUTE,
        "requests_route": LENS_OS_BINDING_AUTHORITY_REQUESTS_ROUTE,
        "grants_route": LENS_OS_BINDING_AUTHORITY_GRANTS_ROUTE,
        "execute_route": LENS_OS_BINDING_EXECUTE_ROUTE,
        "executions_route": LENS_OS_BINDING_EXECUTIONS_ROUTE,
        "denials_route": LENS_OS_BINDING_DENIALS_ROUTE,
        "execution_readiness_route": LENS_OS_BINDING_EXECUTION_READINESS_ROUTE,
        "readiness_route": LENS_OS_BINDING_READINESS_ROUTE,
        "plan_route": LENS_OS_BINDING_PLAN_ROUTE,
        "approval_id": safe_approval_id,
        "approval": {
            "required": True,
            "found": bool(approval),
            "status": approval_status,
            "approved": approval_ready,
            "item": _approval_item(approval) if approval else {},
        },
        "actor": _redact_free_text(actor),
        "reason": _redact_free_text(reason),
        "lease_seconds": safe_lease_seconds,
        "receipt_route": LENS_OS_BINDING_AUTHORITY_GRANTS_ROUTE,
        "receipt_written": False,
        "receipt": {},
        "applied": False,
        "executed": False,
        "approval_requested": False,
        "authority_granted": active_authority,
        "os_level_command_palette_binding_authority": active_authority,
        "hotkey_registration_authority": active_authority,
        "local_process_launch_authority": active_authority,
        "os_level_command_palette": False,
        "summon_anywhere": False,
        "opens_palette": False,
        "registers_hotkey": False,
        "launches_process": False,
        "controls_overlay": False,
        "permission": permission.evidence,
        "blockers": deduped_blockers,
        "grant": {
            "reason": "approved_os_binding_command_palette_authority_lease",
            "lease_seconds": safe_lease_seconds,
            "would_grant_os_level_command_palette_binding_authority": active_authority,
            "would_grant_hotkey_registration_authority": active_authority,
            "would_grant_local_process_launch_authority": active_authority,
            "would_grant_receipt_write_authority": active_authority,
            "would_open_palette": False,
            "would_register_hotkey": False,
            "would_summon": False,
            "would_launch_process": False,
            "would_control_overlay": False,
            "would_write_memory": False,
            "would_decide_approval": False,
            "would_claim_resident": False,
            "grant_receipt_written": False,
        },
        "authorities": {
            "os_level_command_palette_binding_authority": active_authority,
            "hotkey_registration_authority": active_authority,
            "local_process_launch_authority": active_authority,
            "receipt_write_authority": active_authority,
            "summon_authority": False,
            "overlay_control_authority": False,
            "tray_registration_authority": False,
            "approval_decision_authority": False,
            "memory_write": False,
            "resident_claim_authority": False,
        },
        "governance": governance,
    }
    if record_receipt and active_authority:
        receipt = _record_os_binding_authority_grant_receipt(response)
        if receipt:
            response["receipt_written"] = True
            response["receipt"] = receipt
            response["applied"] = True
            response["grant"]["grant_receipt_written"] = True
    elif record_receipt:
        governance["grant_receipt_write_blocker"] = "os_binding_command_palette_authority_not_ready"
    return response


def _os_binding_execution_denial_status(
    *,
    permission_allowed: bool,
    authority_granted: bool,
) -> tuple[str, str]:
    if not permission_allowed:
        return "blocked", "configure_actor_scope_before_attempting_os_binding_command_palette_execution"
    if not authority_granted:
        return "denied_no_os_binding_authority", "grant_os_binding_command_palette_authority_before_execution"
    return "denied_no_os_binding_execution_boundary", "implement_os_binding_command_palette_execution_boundary"


def _os_binding_execution_denial_receipt(denial: dict[str, Any]) -> dict[str, Any]:
    ts = _now_s()
    approval_id = _safe_str(denial.get("approval_id")).strip()
    actor = _safe_str(denial.get("actor")).strip()
    route = _safe_str(denial.get("route")).strip() or LENS_OS_BINDING_EXECUTE_ROUTE
    receipt_id = _os_binding_execution_denial_receipt_id(
        approval_id=approval_id,
        actor=actor,
        route=route,
        ts=ts,
    )
    permission = _as_dict(denial.get("permission"))
    execution_denial = _as_dict(denial.get("denial"))
    plan = _as_dict(denial.get("plan"))
    readiness = _as_dict(denial.get("readiness"))
    active_grant_receipt_id = _safe_str(denial.get("active_grant_receipt_id")).strip()
    authority_granted = bool(denial.get("authority_granted"))
    return _filtered_record(
        {
            "kind": "lens.os_binding.command_palette_binding.denial.receipt",
            "receipt_id": receipt_id,
            "id": receipt_id,
            "status": _safe_str(denial.get("status")).strip(),
            "route": route,
            "method": _safe_str(denial.get("method")).strip() or "POST",
            "source_kind": _safe_str(denial.get("kind")).strip(),
            "source_route": route,
            "approval_id": approval_id,
            "active_grant_receipt_id": active_grant_receipt_id,
            "actor": actor,
            "reason": _safe_str(denial.get("reason")).strip(),
            "created_ts": ts,
            "blockers": _str_list(denial.get("blockers")),
            "permission": {
                "ready": bool(permission.get("ready")),
                "allowed": bool(permission.get("allowed")),
                "reason": _safe_str(permission.get("reason")).strip(),
                "required_scope": _safe_str(permission.get("required_scope")).strip(),
            },
            "readiness": {
                "status": _safe_str(readiness.get("status")).strip(),
                "ready": bool(readiness.get("ready")),
                "os_binding_ready": bool(readiness.get("os_binding_ready")),
                "os_level_command_palette": bool(readiness.get("os_level_command_palette")),
                "summon_anywhere": bool(readiness.get("summon_anywhere")),
            },
            "plan": {
                "status": _safe_str(plan.get("status")).strip(),
                "plan_available": bool(plan.get("plan_available")),
                "implementation_ready": bool(plan.get("implementation_ready")),
                "execution_ready": bool(plan.get("execution_ready")),
            },
            "execution": {
                "applied": bool(denial.get("applied")),
                "executed": bool(denial.get("executed")),
                "would_open_palette": bool(execution_denial.get("would_open_palette")),
                "would_register_hotkey": bool(execution_denial.get("would_register_hotkey")),
                "would_summon": bool(execution_denial.get("would_summon")),
                "would_launch_process": bool(execution_denial.get("would_launch_process")),
                "would_control_overlay": bool(execution_denial.get("would_control_overlay")),
                "would_write_memory": bool(execution_denial.get("would_write_memory")),
                "would_decide_approval": bool(execution_denial.get("would_decide_approval")),
                "would_claim_resident": bool(execution_denial.get("would_claim_resident")),
            },
            "denial": execution_denial,
            "governance": {
                "gate": "lens_os_binding_command_palette_execution_denial_receipt",
                "denial_boundary": True,
                "execution_boundary": True,
                "authority_granted": authority_granted,
                "os_level_command_palette_binding_authority": authority_granted,
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
                "denial_receipt_write_authority": True,
                "receipt_write_authority": False,
                "mutation_authority_granted": False,
            },
        }
    )


def _record_os_binding_execution_denial_receipt(denial: dict[str, Any]) -> dict[str, Any]:
    receipt = _os_binding_execution_denial_receipt(denial)
    path = _os_binding_execution_denial_receipt_path(receipt.get("receipt_id"))
    if path is None:
        return {}
    try:
        _atomic_write_json(path, receipt)
    except OSError:
        return {}
    return receipt


def _read_os_binding_execution_denial_receipt(path: Path) -> dict[str, Any] | None:
    item = _read_json(path)
    if not isinstance(item, dict) or _safe_str(item.get("kind")).strip() != (
        "lens.os_binding.command_palette_binding.denial.receipt"
    ):
        return None
    return item


def _list_os_binding_execution_denial_receipts(
    *,
    limit: int,
    approval_id: str = "",
    status: str = "",
) -> tuple[list[dict[str, Any]], int]:
    root = _os_binding_execution_denial_receipt_root()
    if not root.exists():
        return [], 0
    items: list[dict[str, Any]] = []
    for path in root.glob("*.json"):
        item = _read_os_binding_execution_denial_receipt(path)
        if item is None:
            continue
        if approval_id and _safe_str(item.get("approval_id")).strip() != approval_id:
            continue
        if status and _safe_str(item.get("status")).strip() != status:
            continue
        items.append(item)
    items.sort(key=lambda item: (_record_ts(item.get("created_ts")), _safe_str(item.get("receipt_id"))), reverse=True)
    return items[:limit], len(items)


def lens_os_binding_execution_denial_receipts(
    *,
    limit: int = 5,
    approval_id: Any = "",
    status: Any = "",
) -> dict[str, Any]:
    safe_limit = _safe_limit(limit)
    safe_approval_id = _safe_str(approval_id).strip()
    safe_status = _safe_str(status).strip()
    items, total = _list_os_binding_execution_denial_receipts(
        limit=safe_limit,
        approval_id=safe_approval_id,
        status=safe_status,
    )
    latest = items[0] if items else None
    return {
        "ok": True,
        "kind": "lens.os_binding.command_palette_binding.denial_receipts",
        "status": "readback_ready" if items else "empty",
        "route": LENS_OS_BINDING_DENIALS_ROUTE,
        "execute_route": LENS_OS_BINDING_EXECUTE_ROUTE,
        "plan_route": LENS_OS_BINDING_PLAN_ROUTE,
        "readiness_route": LENS_OS_BINDING_READINESS_ROUTE,
        "authority_route": LENS_OS_BINDING_AUTHORITY_ROUTE,
        "grants_route": LENS_OS_BINDING_AUTHORITY_GRANTS_ROUTE,
        "execution_readiness_route": LENS_OS_BINDING_EXECUTION_READINESS_ROUTE,
        "limit": safe_limit,
        "approval_id": safe_approval_id,
        "filter_status": safe_status,
        "total": total,
        "latest": latest,
        "items": items,
        "governance": {
            **_governance(
                route=LENS_OS_BINDING_DENIALS_ROUTE,
                approval_request_write=False,
                read_only_contract=True,
            ),
            "gate": "lens_os_binding_command_palette_execution_denial_receipts_readback",
            "denial_boundary": True,
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
            "denial_receipt_write_authority": False,
            "receipt_write_authority": False,
            "mutation_authority_granted": False,
            "next_step": "review_os_binding_denial_receipts_before_adding_execution_authority",
        },
    }


def _execution_mode(value: Any) -> str:
    requested = _safe_str(value).strip().lower().replace("-", "_")
    if requested in {"stop", "hotkey_stop", "stop_hotkey"}:
        return "stop"
    return "bind"


def _powershell_path() -> str:
    return shutil.which("pwsh") or shutil.which("powershell") or ""


def _parse_json_process_stdout(stdout: str) -> dict[str, Any]:
    cleaned = stdout.strip()
    if not cleaned:
        return {}
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start < 0 or end <= start:
            return {}
        try:
            payload = json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError:
            return {}
    return payload if isinstance(payload, dict) else {}


def _write_hotkey_binding_config_override(*, allow_launch: bool = False, global_hotkey: str = "") -> Path:
    source_path = repo_root() / "config" / "runtime" / "lens" / "summon.json"
    payload = _read_json(source_path) or {}
    override: dict[str, Any] = {
        "enabled": True,
        "binding_enabled": True,
        "register_hotkey": True,
        "startup_register": False,
        "blocked_reason": "",
        "summon_authority": allow_launch,
        "hotkey_registration_authority": True,
        "overlay_control_authority": allow_launch,
        "local_process_launch_authority": True,
    }
    safe_global_hotkey = _safe_str(global_hotkey).strip()
    if safe_global_hotkey:
        override["global_hotkey"] = safe_global_hotkey
    payload.update(override)
    override_path = data_dir() / "runtime" / "lens-hotkey" / "os-binding-summon-override.json"
    _atomic_write_json(override_path, payload)
    return override_path


def _run_lens_os_binding_hotkey_action(
    *,
    mode: str,
    run_seconds: int,
    allow_launch: bool = False,
    global_hotkey: str = "",
) -> dict[str, Any]:
    script_mode = "Stop" if mode == "stop" else "Start"
    root = repo_root()
    script = root / "scripts" / "lens-hotkey-binding.ps1"
    if not script.is_file():
        return {
            "ok": False,
            "status": "lens_hotkey_binding_entrypoint_missing",
            "script_mode": script_mode,
            "blockers": ["lens_hotkey_binding_entrypoint_missing"],
            "script": "scripts/lens-hotkey-binding.ps1",
        }
    powershell = _powershell_path()
    if not powershell:
        return {
            "ok": False,
            "status": "powershell_runtime_missing",
            "script_mode": script_mode,
            "blockers": ["powershell_runtime_missing"],
            "script": "scripts/lens-hotkey-binding.ps1",
        }

    command = [powershell, "-NoProfile"]
    if os.name == "nt":
        command.extend(["-ExecutionPolicy", "Bypass"])
    command.extend(
        [
            "-File",
            str(script),
            "-Mode",
            script_mode,
            "-DataDir",
            str(data_dir()),
            "-RunSeconds",
            str(_safe_run_seconds(run_seconds)),
        ]
    )
    if not allow_launch:
        command.append("-NoLaunch")
    if script_mode == "Start":
        override_path = _write_hotkey_binding_config_override(
            allow_launch=allow_launch,
            global_hotkey=global_hotkey,
        )
        command.extend(["-StartupTimeoutSeconds", "30", "-ConfigOverridePath", str(override_path)])
    env = dict(os.environ)
    env.setdefault("FRANCIS_ROOT", str(root))
    env.setdefault("FRANCIS_DATA_DIR", str(data_dir()))
    try:
        completed = subprocess.run(
            command,
            cwd=str(root),
            env=env,
            text=True,
            capture_output=True,
            timeout=120,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "status": "hotkey_binding_timeout",
            "script_mode": script_mode,
            "blockers": ["lens_hotkey_binding_execution_timeout"],
            "script": "scripts/lens-hotkey-binding.ps1",
        }
    except OSError as exc:
        return {
            "ok": False,
            "status": "hotkey_binding_launch_failed",
            "script_mode": script_mode,
            "blockers": ["lens_hotkey_binding_execution_failed"],
            "error": lens_error_code(exc, surface="lens_hotkey_binding_execution"),
            "script": "scripts/lens-hotkey-binding.ps1",
        }

    payload = _parse_json_process_stdout(completed.stdout)
    runner_ok = completed.returncode == 0 and bool(payload.get("ok"))
    stderr = (completed.stderr or "").strip()
    return {
        "ok": runner_ok,
        "status": _safe_str(payload.get("status")).strip() or "hotkey_binding_failed",
        "returncode": completed.returncode,
        "script_mode": script_mode,
        "script": "scripts/lens-hotkey-binding.ps1",
        "runner": redact_governed_display_value(payload),
        "blockers": _str_list(payload.get("blockers")),
        "stderr": _redact_free_text(stderr[:500]) if stderr else "",
    }


def _authority_receipt_id(grant: dict[str, Any]) -> str:
    return _safe_str(grant.get("receipt_id")).strip()


def _grant_authorities(grant: dict[str, Any]) -> dict[str, Any]:
    authorities = _as_dict(grant.get("authorities"))
    if authorities:
        return authorities
    return _as_dict(grant.get("governance"))


def _active_summon_launch_authority_grant(approval_id: Any) -> dict[str, Any]:
    safe_approval_id = _safe_str(approval_id).strip()
    if not safe_approval_id:
        return {}
    from francis.lens.summon_authority import lens_summon_authority_grant_receipts

    grants = lens_summon_authority_grant_receipts(limit=1, approval_id=safe_approval_id, active_only=True)
    return _as_dict(grants.get("active_latest"))


def _active_overlay_launch_authority_grant(approval_id: Any) -> dict[str, Any]:
    safe_approval_id = _safe_str(approval_id).strip()
    if not safe_approval_id:
        return {}
    from francis.lens.overlay_authority import lens_overlay_authority_grant_receipts

    grants = lens_overlay_authority_grant_receipts(limit=1, approval_id=safe_approval_id, active_only=True)
    return _as_dict(grants.get("active_latest"))


def _hotkey_execution_status(
    *,
    mode: str,
    runner_ok: bool,
    runner_status: str,
    hotkey_ready: bool,
) -> str:
    if mode == "stop":
        if runner_ok and not hotkey_ready:
            return "global_hotkey_binding_stopped"
        return "global_hotkey_binding_stop_incomplete"
    if runner_ok and hotkey_ready:
        return "global_hotkey_binding_already_running" if runner_status == "already_running" else "global_hotkey_bound"
    return "global_hotkey_binding_failed"


def _execution_receipt(execution: dict[str, Any]) -> dict[str, Any]:
    ts = _now_s()
    approval_id = _safe_str(execution.get("approval_id")).strip()
    actor = _safe_str(execution.get("actor")).strip()
    route = _safe_str(execution.get("route")).strip() or LENS_OS_BINDING_EXECUTE_ROUTE
    receipt_id = _os_binding_execution_receipt_id(
        approval_id=approval_id,
        actor=actor,
        route=route,
        ts=ts,
    )
    hotkey_runtime = _as_dict(execution.get("hotkey_runtime_readback"))
    return _filtered_record(
        {
            "kind": "lens.os_binding.command_palette_binding.execution_receipt",
            "receipt_id": receipt_id,
            "ts": ts,
            "status": _safe_str(execution.get("status")).strip(),
            "approval_id": approval_id,
            "actor": actor,
            "route": route,
            "authority_route": LENS_OS_BINDING_AUTHORITY_ROUTE,
            "authority_grants_route": LENS_OS_BINDING_AUTHORITY_GRANTS_ROUTE,
            "executions_route": LENS_OS_BINDING_EXECUTIONS_ROUTE,
            "active_grant_receipt_id": _safe_str(execution.get("active_grant_receipt_id")).strip(),
            "summon_authority_grant_receipt_id": _safe_str(execution.get("summon_authority_grant_receipt_id")).strip(),
            "overlay_authority_grant_receipt_id": _safe_str(
                execution.get("overlay_authority_grant_receipt_id")
            ).strip(),
            "execution": {
                "mode": _safe_str(execution.get("mode")).strip(),
                "allow_launch": bool(execution.get("allow_launch")),
                "global_hotkey_binding": bool(execution.get("global_hotkey_binding")),
                "global_hotkey": _safe_str(execution.get("global_hotkey")).strip(),
                "hotkey_runtime_ready": bool(execution.get("hotkey_runtime_ready")),
                "hotkey_runtime_pid": int(hotkey_runtime.get("pid") or 0),
                "launch_on_hotkey": bool(hotkey_runtime.get("launch_on_hotkey")),
                "stop_command": _safe_str(execution.get("stop_command")).strip(),
                "next_smallest_truthful_gap": _safe_str(execution.get("next_smallest_truthful_gap")).strip(),
            },
            "governance": _as_dict(execution.get("governance")),
        }
    )


def _record_execution_receipt(execution: dict[str, Any]) -> dict[str, Any]:
    receipt = _execution_receipt(execution)
    path = _os_binding_execution_receipt_path(receipt.get("receipt_id"))
    if path is None:
        return {}
    try:
        _atomic_write_json(path, receipt)
    except OSError:
        return {}
    return receipt


def _read_execution_receipt(path: Path) -> dict[str, Any] | None:
    item = _read_json(path)
    if not isinstance(item, dict) or _safe_str(item.get("kind")).strip() != (
        "lens.os_binding.command_palette_binding.execution_receipt"
    ):
        return None
    return item


def _list_execution_receipts(
    *,
    limit: int,
    approval_id: str = "",
    status: str = "",
) -> tuple[list[dict[str, Any]], int]:
    root = _os_binding_execution_receipt_root()
    if not root.exists():
        return [], 0
    items: list[dict[str, Any]] = []
    for path in root.glob("*.json"):
        item = _read_execution_receipt(path)
        if item is None:
            continue
        if approval_id and _safe_str(item.get("approval_id")).strip() != approval_id:
            continue
        if status and _safe_str(item.get("status")).strip() != status:
            continue
        items.append(item)
    items.sort(key=lambda item: (_record_ts(item.get("ts")), _safe_str(item.get("receipt_id"))), reverse=True)
    return items[:limit], len(items)


def lens_os_binding_execution_receipts(
    *,
    limit: int = 5,
    approval_id: Any = "",
    status: Any = "",
) -> dict[str, Any]:
    safe_limit = _safe_limit(limit)
    safe_approval_id = _safe_str(approval_id).strip()
    safe_status = _safe_str(status).strip()
    items, total = _list_execution_receipts(
        limit=safe_limit,
        approval_id=safe_approval_id,
        status=safe_status,
    )
    latest = items[0] if items else None
    latest_execution = _as_dict(_as_dict(latest).get("execution"))
    return {
        "ok": True,
        "kind": "lens.os_binding.command_palette_binding.execution_receipts",
        "status": "readback_ready" if items else "empty",
        "route": LENS_OS_BINDING_EXECUTIONS_ROUTE,
        "execute_route": LENS_OS_BINDING_EXECUTE_ROUTE,
        "authority_route": LENS_OS_BINDING_AUTHORITY_ROUTE,
        "authority_grants_route": LENS_OS_BINDING_AUTHORITY_GRANTS_ROUTE,
        "limit": safe_limit,
        "approval_id": safe_approval_id,
        "filter_status": safe_status,
        "total": total,
        "latest": latest,
        "latest_status": _safe_str(_as_dict(latest).get("status")).strip(),
        "latest_global_hotkey_binding": bool(latest_execution.get("global_hotkey_binding")),
        "latest_next_smallest_truthful_gap": _safe_str(latest_execution.get("next_smallest_truthful_gap")).strip(),
        "items": items,
        "governance": {
            **_governance(
                route=LENS_OS_BINDING_EXECUTIONS_ROUTE,
                approval_request_write=False,
                read_only_contract=True,
            ),
            "gate": "lens_os_binding_command_palette_execution_receipts_readback",
            "execution_receipts_readback": True,
            "execution_authority": False,
            "approval_decision_authority": False,
            "memory_write": False,
            "mutation_authority_granted": False,
        },
    }


def deny_lens_os_binding_execution(
    *,
    actor: Any = "",
    reason: Any = "attempt Lens OS-binding command palette execution",
    route: str = LENS_OS_BINDING_EXECUTE_ROUTE,
    method: str = "POST",
    record_receipt: bool = False,
) -> dict[str, Any]:
    safe_route = _safe_str(route).strip() or LENS_OS_BINDING_EXECUTE_ROUTE
    safe_method = _safe_str(method).strip() or "POST"
    permission = _permission(actor, route=safe_route, method=safe_method)
    permission_payload = {
        "ready": permission.allowed,
        "allowed": permission.allowed,
        "reason": permission.reason,
        "required_scope": LENS_OS_BINDING_AUTHORITY_SCOPE,
        "evidence": permission.evidence,
    }
    authority_readback = lens_os_binding_authority_request_readback(limit=5)
    active_grant_receipt_id = _safe_str(authority_readback.get("active_grant_receipt_id")).strip()
    authority_granted = bool(authority_readback.get("authority_granted"))
    readiness = lens_os_binding_readiness(authority_request_readback=authority_readback)
    plan = lens_os_binding_implementation_plan(authority_request_readback=authority_readback)
    active_grant = _as_dict(lens_os_binding_authority_grant_receipts(limit=1, active_only=True).get("active_latest"))
    approval_id = _safe_str(active_grant.get("approval_id")).strip()
    blockers = _dedupe_strs(
        [
            *_str_list(readiness.get("blockers")),
            *_str_list(plan.get("blockers")),
            *([] if authority_granted else ["os_level_command_palette_binding_authority_not_granted"]),
            "os_binding_execution_boundary_not_implemented",
            *([] if authority_granted else ["hotkey_registration_authority_not_granted"]),
            *([] if authority_granted else ["receipt_write_authority_not_granted"]),
            *([] if permission.allowed else ["system_write_scope_not_ready"]),
        ]
    )
    status, next_step = _os_binding_execution_denial_status(
        permission_allowed=permission.allowed,
        authority_granted=authority_granted,
    )
    denial_reason = (
        "os_binding_execution_boundary_not_implemented"
        if authority_granted
        else "os_level_command_palette_binding_authority_not_granted"
    )
    response: dict[str, Any] = {
        "ok": True,
        "kind": "lens.os_binding.command_palette_binding.execution_denial",
        "status": status,
        "route": safe_route,
        "method": safe_method,
        "plan_route": LENS_OS_BINDING_PLAN_ROUTE,
        "readiness_route": LENS_OS_BINDING_READINESS_ROUTE,
        "authority_route": LENS_OS_BINDING_AUTHORITY_ROUTE,
        "authority_grants_route": LENS_OS_BINDING_AUTHORITY_GRANTS_ROUTE,
        "execution_readiness_route": LENS_OS_BINDING_EXECUTION_READINESS_ROUTE,
        "receipt_route": LENS_OS_BINDING_DENIALS_ROUTE,
        "approval_id": approval_id,
        "active_grant_receipt_id": active_grant_receipt_id,
        "actor": _redact_free_text(actor),
        "reason": _redact_free_text(reason),
        "receipt_written": False,
        "receipt": {},
        "permission": permission_payload,
        "readiness": readiness,
        "plan": plan,
        "blockers": blockers,
        "applied": False,
        "executed": False,
        "authority_granted": authority_granted,
        "os_level_command_palette_binding_authority": authority_granted,
        "os_level_command_palette": False,
        "summon_anywhere": False,
        "opens_palette": False,
        "registers_hotkey": False,
        "launches_process": False,
        "controls_overlay": False,
        "denial": {
            "reason": denial_reason,
            "next_step": next_step,
            "message": (
                "Lens OS-binding command palette execution is denied until an active governed "
                "command-palette binding authority grant exists."
            ),
            "would_open_palette": False,
            "would_register_hotkey": False,
            "would_summon": False,
            "would_launch_process": False,
            "would_control_overlay": False,
            "would_write_memory": False,
            "would_decide_approval": False,
            "would_claim_resident": False,
            "denial_receipt_written": False,
        },
        "governance": {
            **_governance(
                route=safe_route,
                approval_request_write=False,
                read_only_contract=False,
            ),
            "gate": "lens_os_binding_command_palette_execution_denial",
            "execution_boundary": True,
            "denial_boundary": True,
            "authority_granted": authority_granted,
            "os_level_command_palette_binding_authority": authority_granted,
            "execution_authority": False,
            "approval_decision_authority": False,
            "memory_write": False,
            "summon_authority": False,
            "hotkey_registration_authority": authority_granted,
            "tray_registration_authority": False,
            "overlay_control_authority": False,
            "local_process_launch_authority": authority_granted,
            "process_supervision_authority": False,
            "service_control_authority": False,
            "window_management_authority": False,
            "capture_authority": False,
            "resident_claim_authority": False,
            "receipt_write_authority": False,
            "denial_receipt_write_authority": False,
            "mutation_authority_granted": False,
            "permission": permission_payload,
            "next_step": next_step,
        },
    }
    if (
        record_receipt
        and permission.allowed
        and status
        in {
            "denied_no_os_binding_authority",
            "denied_no_os_binding_execution_boundary",
        }
    ):
        receipt = _record_os_binding_execution_denial_receipt(response)
        if receipt:
            response["receipt_written"] = True
            response["receipt"] = receipt
            response["denial"]["denial_receipt_written"] = True
            response["governance"]["denial_receipt_write_authority"] = True
    elif record_receipt:
        response["governance"]["denial_receipt_write_blocker"] = "os_binding_execution_not_ready"
    return response


def execute_lens_os_binding(
    *,
    approval_id: Any = "",
    summon_approval_id: Any = "",
    overlay_approval_id: Any = "",
    actor: Any = "",
    reason: Any = "attempt Lens OS-binding command palette execution",
    route: str = LENS_OS_BINDING_EXECUTE_ROUTE,
    method: str = "POST",
    record_receipt: bool = False,
    mode: Any = "bind",
    run_seconds: Any = _DEFAULT_RUN_SECONDS,
    allow_launch: bool = False,
    global_hotkey: Any = "",
) -> dict[str, Any]:
    safe_route = _safe_str(route).strip() or LENS_OS_BINDING_EXECUTE_ROUTE
    safe_method = _safe_str(method).strip() or "POST"
    safe_approval_id = _safe_str(approval_id).strip()
    safe_summon_approval_id = _safe_str(summon_approval_id).strip()
    safe_overlay_approval_id = _safe_str(overlay_approval_id).strip()
    safe_mode = _execution_mode(mode)
    safe_run_seconds = _safe_run_seconds(run_seconds)
    safe_allow_launch = bool(allow_launch) and safe_mode == "bind"
    safe_global_hotkey = _safe_str(global_hotkey).strip()
    permission = _permission(actor, route=safe_route, method=safe_method)
    permission_payload = {
        "ready": permission.allowed,
        "allowed": permission.allowed,
        "reason": permission.reason,
        "required_scope": LENS_OS_BINDING_AUTHORITY_SCOPE,
        "evidence": permission.evidence,
    }
    grants = lens_os_binding_authority_grant_receipts(
        limit=1,
        approval_id=safe_approval_id,
        active_only=True,
    )
    active_grant = _as_dict(grants.get("active_latest"))
    authorities = _as_dict(active_grant.get("authorities"))
    if not authorities and active_grant:
        authorities = {
            "os_level_command_palette_binding_authority": bool(
                active_grant.get("os_level_command_palette_binding_authority")
            ),
            "hotkey_registration_authority": bool(active_grant.get("hotkey_registration_authority")),
            "local_process_launch_authority": bool(active_grant.get("local_process_launch_authority")),
            "receipt_write_authority": bool(active_grant.get("governance", {}).get("receipt_write_authority")),
        }
    summon_authority_grant = _active_summon_launch_authority_grant(safe_summon_approval_id) if safe_allow_launch else {}
    overlay_authority_grant = (
        _active_overlay_launch_authority_grant(safe_overlay_approval_id) if safe_allow_launch else {}
    )
    summon_authorities = _grant_authorities(summon_authority_grant)
    overlay_authorities = _grant_authorities(overlay_authority_grant)
    hotkey_launch_on_press_authority = (
        safe_allow_launch
        and bool(summon_authorities.get("summon_execution_authority"))
        and bool(summon_authorities.get("bounded_local_open_handoff_authority"))
        and bool(summon_authorities.get("summon_authority"))
        and bool(overlay_authorities.get("overlay_window_execution_authority"))
        and bool(overlay_authorities.get("overlay_control_authority"))
        and bool(overlay_authorities.get("window_management_authority"))
    )
    blockers: list[str] = []
    if not safe_approval_id:
        blockers.append("approval_id_required")
    if not active_grant:
        blockers.append("os_binding_authority_grant_not_active")
    if not bool(authorities.get("os_level_command_palette_binding_authority")):
        blockers.append("os_level_command_palette_binding_authority_not_granted")
    if safe_mode == "bind":
        if not bool(authorities.get("hotkey_registration_authority")):
            blockers.append("hotkey_registration_authority_not_granted")
        if not bool(authorities.get("local_process_launch_authority")):
            blockers.append("local_process_launch_authority_not_granted")
    if record_receipt and not bool(authorities.get("receipt_write_authority")):
        blockers.append("receipt_write_authority_not_granted")
    if not permission.allowed:
        blockers.append("system_write_scope_not_ready")
    if safe_allow_launch:
        if not safe_summon_approval_id:
            blockers.append("summon_approval_id_required_for_launch_on_hotkey")
        if safe_summon_approval_id and not summon_authority_grant:
            blockers.append("summon_action_authority_grant_not_active_for_launch_on_hotkey")
        if not bool(summon_authorities.get("summon_execution_authority")):
            blockers.append("summon_execution_authority_not_granted_for_launch_on_hotkey")
        if not bool(summon_authorities.get("bounded_local_open_handoff_authority")):
            blockers.append("bounded_local_open_handoff_authority_not_granted_for_launch_on_hotkey")
        if not bool(summon_authorities.get("summon_authority")):
            blockers.append("summon_authority_not_granted_for_launch_on_hotkey")
        if not safe_overlay_approval_id:
            blockers.append("overlay_approval_id_required_for_launch_on_hotkey")
        if safe_overlay_approval_id and not overlay_authority_grant:
            blockers.append("overlay_window_authority_grant_not_active_for_launch_on_hotkey")
        if not bool(overlay_authorities.get("overlay_window_execution_authority")):
            blockers.append("overlay_window_execution_authority_not_granted_for_launch_on_hotkey")
        if not bool(overlay_authorities.get("overlay_control_authority")):
            blockers.append("overlay_control_authority_not_granted_for_launch_on_hotkey")
        if not bool(overlay_authorities.get("window_management_authority")):
            blockers.append("window_management_authority_not_granted_for_launch_on_hotkey")

    deduped_blockers = _dedupe_strs(blockers)
    if deduped_blockers:
        return {
            "ok": True,
            "applied": False,
            "executed": False,
            "kind": "lens.os_binding.command_palette_binding.execution_denial",
            "status": "blocked",
            "route": safe_route,
            "method": safe_method,
            "mode": safe_mode,
            "approval_id": safe_approval_id,
            "actor": _redact_free_text(actor),
            "reason": _redact_free_text(reason),
            "run_seconds": safe_run_seconds,
            "allow_launch": safe_allow_launch,
            "requested_allow_launch": bool(allow_launch),
            "authority_route": LENS_OS_BINDING_AUTHORITY_ROUTE,
            "authority_grants_route": LENS_OS_BINDING_AUTHORITY_GRANTS_ROUTE,
            "executions_route": LENS_OS_BINDING_EXECUTIONS_ROUTE,
            "denials_route": LENS_OS_BINDING_DENIALS_ROUTE,
            "active_grant": active_grant,
            "active_grant_receipt_id": _safe_str(active_grant.get("receipt_id")).strip(),
            "authorities": authorities,
            "summon_approval_id": safe_summon_approval_id,
            "summon_authority_grant": summon_authority_grant,
            "summon_authority_grant_receipt_id": _authority_receipt_id(summon_authority_grant),
            "summon_authorities": summon_authorities,
            "overlay_approval_id": safe_overlay_approval_id,
            "overlay_authority_grant": overlay_authority_grant,
            "overlay_authority_grant_receipt_id": _authority_receipt_id(overlay_authority_grant),
            "overlay_authorities": overlay_authorities,
            "permission": permission_payload,
            "blockers": deduped_blockers,
            "receipt_written": False,
            "receipt": {},
            "authority_granted": bool(active_grant),
            "os_level_command_palette_binding_authority": bool(
                authorities.get("os_level_command_palette_binding_authority")
            ),
            "os_level_command_palette": False,
            "summon_anywhere": False,
            "registers_hotkey": False,
            "launch_on_hotkey": False,
            "launches_process": False,
            "controls_overlay": False,
            "governance": {
                **_governance(
                    route=safe_route,
                    approval_request_write=False,
                    read_only_contract=False,
                ),
                "gate": "lens_os_binding_command_palette_execution_denial",
                "execution_boundary": True,
                "authority_granted": bool(active_grant),
                "os_level_command_palette_binding_authority": bool(
                    authorities.get("os_level_command_palette_binding_authority")
                ),
                "execution_authority": False,
                "approval_decision_authority": False,
                "memory_write": False,
                "summon_authority": safe_allow_launch and bool(summon_authorities.get("summon_authority")),
                "hotkey_registration_authority": bool(authorities.get("hotkey_registration_authority")),
                "hotkey_launch_on_press_authority": hotkey_launch_on_press_authority,
                "tray_registration_authority": False,
                "overlay_control_authority": safe_allow_launch
                and bool(overlay_authorities.get("overlay_control_authority")),
                "window_management_authority": safe_allow_launch
                and bool(overlay_authorities.get("window_management_authority")),
                "local_process_launch_authority": bool(authorities.get("local_process_launch_authority")),
                "receipt_write_authority": False,
                "process_supervision_authority": False,
                "service_control_authority": False,
                "resident_claim_authority": False,
                "mutation_authority_granted": False,
                "next_step": "grant_os_binding_hotkey_authority_before_execution",
            },
        }

    if safe_global_hotkey:
        runner = _run_lens_os_binding_hotkey_action(
            mode=safe_mode,
            run_seconds=safe_run_seconds,
            allow_launch=safe_allow_launch,
            global_hotkey=safe_global_hotkey,
        )
    else:
        runner = _run_lens_os_binding_hotkey_action(
            mode=safe_mode,
            run_seconds=safe_run_seconds,
            allow_launch=safe_allow_launch,
        )
    runner_ok = bool(runner.get("ok"))
    runner_status = _safe_str(runner.get("status")).strip()
    authority_readback = lens_os_binding_authority_request_readback(limit=5)
    readiness = lens_os_binding_readiness(authority_request_readback=authority_readback)
    global_hotkey = _readiness_requirement(readiness, "global_hotkey_binding")
    hotkey_runtime = _as_dict(global_hotkey.get("hotkey_runtime_readback"))
    hotkey_ready = bool(global_hotkey.get("runtime_ready")) or bool(hotkey_runtime.get("ready"))
    status = _hotkey_execution_status(
        mode=safe_mode,
        runner_ok=runner_ok,
        runner_status=runner_status,
        hotkey_ready=hotkey_ready,
    )
    next_gap = "summon_binding" if safe_mode == "bind" and hotkey_ready else "os_level_command_palette_binding"
    response: dict[str, Any] = {
        "ok": True,
        "applied": runner_ok,
        "executed": runner_ok,
        "kind": "lens.os_binding.command_palette_binding.execution",
        "status": status,
        "route": safe_route,
        "method": safe_method,
        "mode": safe_mode,
        "approval_id": safe_approval_id,
        "actor": _redact_free_text(actor),
        "reason": _redact_free_text(reason),
        "run_seconds": safe_run_seconds,
        "allow_launch": safe_allow_launch,
        "requested_allow_launch": bool(allow_launch),
        "global_hotkey": safe_global_hotkey or _safe_str(hotkey_runtime.get("global_hotkey")).strip(),
        "requested_global_hotkey": safe_global_hotkey,
        "authority_route": LENS_OS_BINDING_AUTHORITY_ROUTE,
        "authority_grants_route": LENS_OS_BINDING_AUTHORITY_GRANTS_ROUTE,
        "executions_route": LENS_OS_BINDING_EXECUTIONS_ROUTE,
        "denials_route": LENS_OS_BINDING_DENIALS_ROUTE,
        "active_grant": active_grant,
        "active_grant_receipt_id": _safe_str(active_grant.get("receipt_id")).strip(),
        "authorities": authorities,
        "summon_approval_id": safe_summon_approval_id,
        "summon_authority_grant": summon_authority_grant,
        "summon_authority_grant_receipt_id": _authority_receipt_id(summon_authority_grant),
        "summon_authorities": summon_authorities,
        "overlay_approval_id": safe_overlay_approval_id,
        "overlay_authority_grant": overlay_authority_grant,
        "overlay_authority_grant_receipt_id": _authority_receipt_id(overlay_authority_grant),
        "overlay_authorities": overlay_authorities,
        "permission": permission_payload,
        "runner": runner,
        "runner_payload": _as_dict(runner.get("runner")),
        "readiness": readiness,
        "hotkey_runtime_readback": hotkey_runtime,
        "global_hotkey_binding": hotkey_ready,
        "hotkey_runtime_ready": hotkey_ready,
        "hotkey_bound": bool(hotkey_runtime.get("hotkey_bound")),
        "hotkey_runtime_pid": int(hotkey_runtime.get("pid") or 0),
        "launch_on_hotkey": bool(hotkey_runtime.get("launch_on_hotkey")),
        "stop_command": "scripts/lens-hotkey-binding.ps1 -Mode Stop" if safe_mode == "bind" and hotkey_ready else "",
        "next_smallest_truthful_gap": next_gap,
        "blockers": _dedupe_strs(_str_list(runner.get("blockers"))),
        "receipt_written": False,
        "receipt": {},
        "authority_granted": True,
        "os_level_command_palette_binding_authority": True,
        "os_level_command_palette": hotkey_ready,
        "summon_anywhere": False,
        "registers_hotkey": runner_ok and safe_mode == "bind",
        "launches_process": runner_ok and safe_mode == "bind",
        "controls_overlay": False,
        "governance": {
            **_governance(
                route=safe_route,
                approval_request_write=False,
                read_only_contract=False,
            ),
            "gate": "lens_os_binding_command_palette_execution",
            "execution_boundary": True,
            "authority_granted": True,
            "os_level_command_palette_binding_authority": True,
            "execution_authority": runner_ok,
            "approval_decision_authority": False,
            "memory_write": False,
            "summon_authority": hotkey_launch_on_press_authority and bool(summon_authorities.get("summon_authority")),
            "hotkey_registration_authority": runner_ok and safe_mode == "bind",
            "hotkey_launch_on_press_authority": hotkey_launch_on_press_authority,
            "tray_registration_authority": False,
            "overlay_control_authority": hotkey_launch_on_press_authority
            and bool(overlay_authorities.get("overlay_control_authority")),
            "window_management_authority": hotkey_launch_on_press_authority
            and bool(overlay_authorities.get("window_management_authority")),
            "local_process_launch_authority": runner_ok and safe_mode == "bind",
            "receipt_write_authority": False,
            "process_supervision_authority": False,
            "service_control_authority": False,
            "resident_claim_authority": False,
            "mutation_authority_granted": runner_ok,
            "next_step": (
                "continue_with_summon_anywhere_runtime_readback_after_launch_hotkey_binding"
                if safe_allow_launch and hotkey_ready
                else "continue_with_summon_binding_after_global_hotkey_binding"
                if safe_mode == "bind" and hotkey_ready
                else "resolve_global_hotkey_binding_execution_failure"
            ),
        },
    }
    if record_receipt and bool(permission_payload.get("ready")) and bool(authorities.get("receipt_write_authority")):
        receipt = _record_execution_receipt(response)
        if receipt:
            response["receipt_written"] = True
            response["receipt"] = receipt
            response["governance"]["receipt_write_authority"] = True
    elif record_receipt:
        response["governance"]["receipt_write_blocker"] = "receipt_write_authority_not_granted"
    return response


def _execution_readiness_requirement(
    requirement_id: str,
    *,
    label: str,
    ready: bool,
    route: str,
    blockers: list[str],
    authority_required: str = "",
    authority_granted: bool = False,
    evidence: list[str] | None = None,
    readback_ready: bool = False,
) -> dict[str, Any]:
    return {
        "id": requirement_id,
        "label": label,
        "ready": ready,
        "status": "ready" if ready else "blocked",
        "route": route,
        "evidence": evidence or [route],
        "blockers": [] if ready else _dedupe_strs(blockers),
        "authority_required": authority_required,
        "authority_granted": authority_granted,
        "readback_ready": readback_ready,
    }


_OS_BINDING_EXECUTION_BOUNDARY_PREREQUISITES = [
    "system_write_permission",
    "os_binding_readiness_readback",
    "os_binding_implementation_plan",
    "os_binding_authority_grant",
    "os_binding_execution_denial_boundary",
    "os_binding_denial_receipts",
    "global_hotkey_binding",
    "summon_binding",
    "resident_host",
    "tray_presence",
    "overlay_window",
]

_OS_BINDING_EXECUTION_SURFACE_PREREQUISITES = [
    "global_hotkey_binding",
    "summon_binding",
    "resident_host",
    "tray_presence",
    "overlay_window",
]


def _readiness_blocker_group(readiness: dict[str, Any], group: str) -> list[str]:
    return _str_list(_as_dict(readiness.get("blocker_groups")).get(group))


def _readiness_requirement(readiness: dict[str, Any], requirement_id: str) -> dict[str, Any]:
    for item in _as_list(readiness.get("requirements")):
        requirement = _as_dict(item)
        if _safe_str(requirement.get("id")).strip() == requirement_id:
            return requirement
    return {}


def lens_os_binding_execution_readiness_audit(
    *,
    actor: Any = "",
    limit: int = 5,
    authority_request_readback: dict[str, Any] | None = None,
    readiness: dict[str, Any] | None = None,
    plan: dict[str, Any] | None = None,
    execution_denial: dict[str, Any] | None = None,
    denial_receipts: dict[str, Any] | None = None,
) -> dict[str, Any]:
    safe_limit = _safe_limit(limit)
    authority_readback = (
        authority_request_readback
        if isinstance(authority_request_readback, dict)
        else lens_os_binding_authority_request_readback(limit=safe_limit)
    )
    readiness_payload = (
        readiness
        if isinstance(readiness, dict)
        else lens_os_binding_readiness(authority_request_readback=authority_readback)
    )
    plan_payload = (
        plan
        if isinstance(plan, dict)
        else lens_os_binding_implementation_plan(authority_request_readback=authority_readback)
    )
    denial_payload = (
        execution_denial
        if isinstance(execution_denial, dict)
        else deny_lens_os_binding_execution(
            actor=actor,
            reason="audit Lens OS-binding command palette execution readiness",
            route=LENS_OS_BINDING_EXECUTE_ROUTE,
            method="POST",
            record_receipt=False,
        )
    )
    approval_id = _safe_str(denial_payload.get("approval_id")).strip()
    denial_readback = (
        denial_receipts
        if isinstance(denial_receipts, dict)
        else lens_os_binding_execution_denial_receipts(limit=safe_limit, approval_id=approval_id)
    )
    permission = _as_dict(denial_payload.get("permission"))
    permission_allowed = bool(permission.get("allowed"))
    authority_granted = bool(authority_readback.get("authority_granted")) or bool(
        denial_payload.get("authority_granted")
    )
    active_grant_receipt_id = _safe_str(
        authority_readback.get("active_grant_receipt_id") or denial_payload.get("active_grant_receipt_id")
    ).strip()
    denial_status = _safe_str(denial_payload.get("status")).strip()
    denial_boundary_observed = (
        _safe_str(denial_payload.get("kind")).strip() == "lens.os_binding.command_palette_binding.execution_denial"
        and denial_status
        in {
            "blocked",
            "denied_no_os_binding_authority",
            "denied_no_os_binding_execution_boundary",
        }
        and not bool(denial_payload.get("applied"))
        and not bool(denial_payload.get("executed"))
    )
    denial_receipt_readback_ready = _safe_str(denial_readback.get("kind")).strip() == (
        "lens.os_binding.command_palette_binding.denial_receipts"
    ) and _safe_str(denial_readback.get("status")).strip() in {"empty", "readback_ready"}
    raw_denial_receipt_total = denial_readback.get("total")
    if isinstance(raw_denial_receipt_total, bool):
        denial_receipt_total = len(_as_list(denial_readback.get("items")))
    elif isinstance(raw_denial_receipt_total, int):
        denial_receipt_total = raw_denial_receipt_total
    elif isinstance(raw_denial_receipt_total, str) and raw_denial_receipt_total.strip():
        try:
            denial_receipt_total = int(raw_denial_receipt_total)
        except ValueError:
            denial_receipt_total = len(_as_list(denial_readback.get("items")))
    else:
        denial_receipt_total = len(_as_list(denial_readback.get("items")))
    denial_receipt_total = max(0, denial_receipt_total)
    global_hotkey_readiness = _readiness_requirement(readiness_payload, "global_hotkey_binding")
    hotkey_runtime = _as_dict(global_hotkey_readiness.get("hotkey_runtime_readback"))
    hotkey_runtime_ready = bool(global_hotkey_readiness.get("runtime_ready")) or bool(hotkey_runtime.get("ready"))
    overlay_window_readiness = _readiness_requirement(readiness_payload, "overlay_window")
    overlay_runtime = _as_dict(overlay_window_readiness.get("overlay_runtime_readback"))
    overlay_runtime_ready = bool(overlay_window_readiness.get("runtime_ready")) or bool(overlay_runtime.get("ready"))
    requirements = [
        _execution_readiness_requirement(
            "system_write_permission",
            label="System-write actor scope",
            ready=permission_allowed,
            route=LENS_OS_BINDING_EXECUTE_ROUTE,
            blockers=[] if permission_allowed else ["system_write_scope_not_ready"],
            authority_required=LENS_OS_BINDING_AUTHORITY_SCOPE,
            authority_granted=permission_allowed,
            evidence=[LENS_OS_BINDING_EXECUTE_ROUTE, LENS_OS_BINDING_EXECUTION_READINESS_ROUTE],
            readback_ready=bool(permission),
        ),
        _execution_readiness_requirement(
            "os_binding_readiness_readback",
            label="OS-binding readiness readback",
            ready=_safe_str(readiness_payload.get("kind")).strip() == "lens.os_binding.readiness",
            route=LENS_OS_BINDING_READINESS_ROUTE,
            blockers=[],
            evidence=[LENS_OS_BINDING_READINESS_ROUTE],
            readback_ready=True,
        ),
        _execution_readiness_requirement(
            "os_binding_implementation_plan",
            label="OS-binding implementation plan",
            ready=bool(plan_payload.get("plan_available")),
            route=LENS_OS_BINDING_PLAN_ROUTE,
            blockers=_str_list(plan_payload.get("blockers")),
            evidence=[LENS_OS_BINDING_PLAN_ROUTE],
            readback_ready=_safe_str(plan_payload.get("kind")).strip() == "lens.os_binding.implementation_plan",
        ),
        _execution_readiness_requirement(
            "os_binding_authority_grant",
            label="OS-binding authority grant",
            ready=authority_granted,
            route=LENS_OS_BINDING_AUTHORITY_GRANTS_ROUTE,
            blockers=[] if authority_granted else ["os_level_command_palette_binding_authority_not_granted"],
            authority_required="os_level_command_palette_binding_authority",
            authority_granted=authority_granted,
            evidence=[
                LENS_OS_BINDING_AUTHORITY_REQUESTS_ROUTE,
                LENS_OS_BINDING_AUTHORITY_GRANTS_ROUTE,
            ],
            readback_ready=bool(authority_readback),
        ),
        _execution_readiness_requirement(
            "os_binding_execution_denial_boundary",
            label="OS-binding execution denial boundary",
            ready=denial_boundary_observed,
            route=LENS_OS_BINDING_EXECUTE_ROUTE,
            blockers=[] if denial_boundary_observed else ["os_binding_execution_denial_boundary_missing"],
            evidence=[LENS_OS_BINDING_EXECUTE_ROUTE],
            readback_ready=denial_boundary_observed,
        ),
        _execution_readiness_requirement(
            "os_binding_denial_receipts",
            label="OS-binding denial receipt readback",
            ready=denial_receipt_readback_ready,
            route=LENS_OS_BINDING_DENIALS_ROUTE,
            blockers=[] if denial_receipt_readback_ready else ["os_binding_denial_receipts_readback_missing"],
            evidence=[LENS_OS_BINDING_DENIALS_ROUTE],
            readback_ready=denial_receipt_readback_ready,
        ),
        _execution_readiness_requirement(
            "global_hotkey_binding",
            label="Global hotkey binding",
            ready=hotkey_runtime_ready,
            route=LENS_OS_BINDING_PLAN_ROUTE,
            blockers=[]
            if hotkey_runtime_ready
            else (
                _readiness_blocker_group(readiness_payload, "global_hotkey_binding")
                or ["global_hotkey_binding_missing"]
            ),
            authority_required="hotkey_registration_authority",
            authority_granted=authority_granted,
            evidence=[LENS_OS_BINDING_READINESS_ROUTE, LENS_OS_BINDING_PLAN_ROUTE],
            readback_ready=True,
        ),
        _execution_readiness_requirement(
            "summon_binding",
            label="Summon binding",
            ready=False,
            route=LENS_OS_BINDING_PLAN_ROUTE,
            blockers=_readiness_blocker_group(readiness_payload, "summon_binding") or ["summon_binding_missing"],
            authority_required="summon_authority",
            evidence=[LENS_OS_BINDING_READINESS_ROUTE, LENS_OS_BINDING_PLAN_ROUTE],
            readback_ready=True,
        ),
        _execution_readiness_requirement(
            "resident_host",
            label="Resident host",
            ready=False,
            route="/lens/host",
            blockers=_readiness_blocker_group(readiness_payload, "resident_host") or ["resident_host_process_missing"],
            evidence=[LENS_OS_BINDING_READINESS_ROUTE, "/lens/host"],
            readback_ready=True,
        ),
        _execution_readiness_requirement(
            "tray_presence",
            label="Tray presence",
            ready=False,
            route="/lens/tray",
            blockers=_readiness_blocker_group(readiness_payload, "tray_presence")
            or ["lens_tray_presence_disabled_pending_authority"],
            authority_required="tray_registration_authority",
            evidence=[LENS_OS_BINDING_READINESS_ROUTE, "/lens/tray"],
            readback_ready=True,
        ),
        _execution_readiness_requirement(
            "overlay_window",
            label="Overlay window",
            ready=False,
            route="/lens/overlay",
            blockers=_readiness_blocker_group(readiness_payload, "overlay_window")
            or ["lens_overlay_window_not_implemented"],
            authority_required="overlay_control_authority",
            evidence=[LENS_OS_BINDING_READINESS_ROUTE, "/lens/overlay"],
            readback_ready=True,
        ),
    ]
    for requirement in requirements:
        if _safe_str(requirement.get("id")).strip() == "global_hotkey_binding":
            requirement.update(
                {
                    "runtime_ready": hotkey_runtime_ready,
                    "runtime_requirement_state": _safe_str(
                        global_hotkey_readiness.get("runtime_requirement_state")
                        or hotkey_runtime.get("requirement_state")
                        or "missing"
                    ),
                    "runtime_blocker": _safe_str(
                        global_hotkey_readiness.get("runtime_blocker") or hotkey_runtime.get("blocker")
                    ),
                    "hotkey_runtime_readback": hotkey_runtime,
                }
            )
        if _safe_str(requirement.get("id")).strip() == "overlay_window":
            requirement.update(
                {
                    "runtime_ready": overlay_runtime_ready,
                    "runtime_requirement_state": _safe_str(
                        overlay_window_readiness.get("runtime_requirement_state")
                        or overlay_runtime.get("requirement_state")
                        or "missing"
                    ),
                    "runtime_blocker": _safe_str(
                        overlay_window_readiness.get("runtime_blocker") or overlay_runtime.get("blocker")
                    ),
                    "overlay_runtime_readback": overlay_runtime,
                }
            )
    blocked_requirements = [_safe_str(item.get("id")).strip() for item in requirements if not bool(item.get("ready"))]
    blocked_execution_prerequisites = [
        item for item in _OS_BINDING_EXECUTION_BOUNDARY_PREREQUISITES if item in blocked_requirements
    ]
    blocked_surface_prerequisites = [
        item for item in _OS_BINDING_EXECUTION_SURFACE_PREREQUISITES if item in blocked_requirements
    ]
    execution_prerequisites_ready = not blocked_execution_prerequisites
    execution_boundary_next_gap = (
        "os_binding_command_palette_execution_boundary"
        if execution_prerequisites_ready
        else "os_binding_execution_prerequisites"
    )
    execution_boundary_next_step = (
        "implement_os_binding_command_palette_execution_boundary_after_prerequisites"
        if execution_prerequisites_ready
        else "resolve_os_binding_execution_prerequisites_before_execution_boundary"
    )
    execution_boundary_handoff = {
        "status": "blocked_by_execution_boundary" if execution_prerequisites_ready else "blocked_by_prerequisites",
        "route": LENS_OS_BINDING_EXECUTE_ROUTE,
        "readiness_route": LENS_OS_BINDING_EXECUTION_READINESS_ROUTE,
        "plan_route": LENS_OS_BINDING_PLAN_ROUTE,
        "denials_route": LENS_OS_BINDING_DENIALS_ROUTE,
        "next_step": execution_boundary_next_step,
        "next_smallest_truthful_gap": execution_boundary_next_gap,
        "required_before_execution_boundary": list(_OS_BINDING_EXECUTION_BOUNDARY_PREREQUISITES),
        "blocked_requirements": blocked_execution_prerequisites,
        "blocked_surface_prerequisites": blocked_surface_prerequisites,
        "authority_required": "os_level_command_palette_binding_authority",
        "read_only_contract": True,
        "would_execute": False,
        "would_open_palette": False,
        "would_register_hotkey": False,
        "would_summon": False,
        "would_control_overlay": False,
        "would_launch_process": False,
        "would_write_memory": False,
    }
    blockers = _dedupe_strs(
        [
            *_str_list(readiness_payload.get("blockers")),
            *_str_list(plan_payload.get("blockers")),
            *_str_list(denial_payload.get("blockers")),
            *[blocker for requirement in requirements for blocker in _str_list(_as_dict(requirement).get("blockers"))],
        ]
    )
    if not hotkey_runtime_ready:
        blockers.append("os_binding_execution_boundary_not_implemented")
    blockers = _dedupe_strs(blockers)
    execution_ready = permission_allowed and authority_granted and hotkey_runtime_ready
    return {
        "ok": True,
        "kind": "lens.os_binding.command_palette_binding.execution_readiness",
        "status": "ready" if execution_ready else "blocked",
        "route": LENS_OS_BINDING_EXECUTION_READINESS_ROUTE,
        "execute_route": LENS_OS_BINDING_EXECUTE_ROUTE,
        "denials_route": LENS_OS_BINDING_DENIALS_ROUTE,
        "plan_route": LENS_OS_BINDING_PLAN_ROUTE,
        "readiness_route": LENS_OS_BINDING_READINESS_ROUTE,
        "authority_route": LENS_OS_BINDING_AUTHORITY_ROUTE,
        "authority_requests_route": LENS_OS_BINDING_AUTHORITY_REQUESTS_ROUTE,
        "authority_grants_route": LENS_OS_BINDING_AUTHORITY_GRANTS_ROUTE,
        "ready": execution_ready,
        "execution_ready": execution_ready,
        "os_binding_ready": bool(readiness_payload.get("os_binding_ready")),
        "os_level_command_palette": hotkey_runtime_ready,
        "summon_anywhere": False,
        "permission": permission,
        "permission_allowed": permission_allowed,
        "authority_granted": authority_granted,
        "os_level_command_palette_binding_authority": authority_granted,
        "active_grant_receipt_id": active_grant_receipt_id,
        "denial_boundary_observed": denial_boundary_observed,
        "denial_status": denial_status,
        "denial_receipt_readback_ready": denial_receipt_readback_ready,
        "denial_receipt_total": denial_receipt_total,
        "latest_denial_receipt_id": _safe_str(_as_dict(denial_readback.get("latest")).get("receipt_id")).strip(),
        "requirements_total": len(requirements),
        "requirements_ready_total": len(requirements) - len(blocked_requirements),
        "requirements_blocked_total": len(blocked_requirements),
        "blocked_requirements": blocked_requirements,
        "required_before_execution_boundary": list(_OS_BINDING_EXECUTION_BOUNDARY_PREREQUISITES),
        "blocked_execution_prerequisites": blocked_execution_prerequisites,
        "blocked_surface_prerequisites": blocked_surface_prerequisites,
        "execution_prerequisites_ready": execution_prerequisites_ready,
        "execution_boundary_handoff": execution_boundary_handoff,
        "requirements": requirements,
        "blockers": blockers,
        "next_smallest_truthful_gap": execution_boundary_next_gap,
        "authority_request_readback": authority_readback,
        "readiness": readiness_payload,
        "plan": plan_payload,
        "execution_denial": {
            "kind": _safe_str(denial_payload.get("kind")).strip(),
            "status": denial_status,
            "route": _safe_str(denial_payload.get("route")).strip(),
            "receipt_written": bool(denial_payload.get("receipt_written")),
            "applied": bool(denial_payload.get("applied")),
            "executed": bool(denial_payload.get("executed")),
            "blockers": _str_list(denial_payload.get("blockers")),
        },
        "denial_receipts": denial_readback,
        "governance": {
            **_governance(
                route=LENS_OS_BINDING_EXECUTION_READINESS_ROUTE,
                approval_request_write=False,
                read_only_contract=True,
            ),
            "gate": "lens_os_binding_command_palette_execution_readiness_audit",
            "authority_granted": authority_granted,
            "os_level_command_palette_binding_authority": authority_granted,
            "execution_boundary": execution_ready,
            "denial_boundary": True,
            "execution_authority": False,
            "approval_decision_authority": False,
            "memory_write": False,
            "summon_authority": False,
            "hotkey_registration_authority": authority_granted,
            "tray_registration_authority": False,
            "overlay_control_authority": False,
            "local_process_launch_authority": authority_granted,
            "process_supervision_authority": False,
            "service_control_authority": False,
            "window_management_authority": False,
            "capture_authority": False,
            "resident_claim_authority": False,
            "receipt_write_authority": False,
            "denial_receipt_write_authority": False,
            "mutation_authority_granted": False,
            "next_step": execution_boundary_next_step,
        },
        "message": (
            "Lens OS-binding execution readiness is read-only. Authority grants and denial receipts are visible, "
            "but the hotkey, summon, tray, overlay, resident-host, and execution boundaries are still blocked."
        ),
    }


def lens_os_binding_authority_request_readback(*, limit: int = 5) -> dict[str, Any]:
    safe_limit = _safe_limit(limit)
    by_status, latest_items, counts = _approval_items(limit=safe_limit)
    total = sum(counts.values())
    grants = lens_os_binding_authority_grant_receipts(limit=1, active_only=True)
    active_grant = _as_dict(grants.get("active_latest"))
    active_grant_id = _safe_str(active_grant.get("receipt_id")).strip()
    active_grant_approval_id = _safe_str(active_grant.get("approval_id")).strip()
    authority_granted = bool(active_grant)
    status, next_step = _readback_status(counts, authority_granted=authority_granted)
    latest = latest_items[0] if latest_items else None
    return {
        "ok": True,
        "kind": "lens.os_binding.command_palette_binding_authority.request_readback",
        "status": status,
        "readback_ready": True,
        "route": LENS_OS_BINDING_AUTHORITY_REQUESTS_ROUTE,
        "authority_route": LENS_OS_BINDING_AUTHORITY_ROUTE,
        "request_route": LENS_OS_BINDING_AUTHORITY_REQUEST_ROUTE,
        "grants_route": LENS_OS_BINDING_AUTHORITY_GRANTS_ROUTE,
        "execute_route": LENS_OS_BINDING_EXECUTE_ROUTE,
        "denials_route": LENS_OS_BINDING_DENIALS_ROUTE,
        "execution_readiness_route": LENS_OS_BINDING_EXECUTION_READINESS_ROUTE,
        "readiness_route": LENS_OS_BINDING_READINESS_ROUTE,
        "plan_route": LENS_OS_BINDING_PLAN_ROUTE,
        "active_grant_receipt_id": active_grant_id,
        "active_grant_approval_id": active_grant_approval_id,
        "active_approval_id": active_grant_approval_id,
        "active_authority_grant": active_grant,
        "decision_route": "/approvals/decision",
        "approval_action": LENS_OS_BINDING_AUTHORITY_REQUEST_ACTION,
        "authority_required": "os_level_command_palette_binding_authority",
        "pending_count": counts.get("pending", 0),
        "approved_count": counts.get("approved", 0),
        "rejected_count": counts.get("rejected", 0),
        "emergency_count": counts.get("emergency", 0),
        "total_count": total,
        "latest": latest,
        "items": latest_items,
        "by_status": by_status,
        "authority_granted": authority_granted,
        "os_level_command_palette_binding_authority": authority_granted,
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
            "authority_grant_receipts_route": LENS_OS_BINDING_AUTHORITY_GRANTS_ROUTE,
            "active_grant_receipt_id": active_grant_id,
            "active_grant_approval_id": active_grant_approval_id,
            "authority_granted": authority_granted,
            "os_level_command_palette_binding_authority": authority_granted,
            "next_step": next_step,
        },
    }
