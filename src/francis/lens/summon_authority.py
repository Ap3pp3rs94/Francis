from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from francis.governance.approval_projection import approval_projection_fields
from francis.governance.approvals import list_requests, request as create_approval_request
from francis.governance.api_permission_gate import ApiPermissionDecision, ApiPermissionGate
from francis.governance.redaction import redact_governed_display_value, redact_secret_text
from francis.kernel.paths import data_dir, repo_root
from francis.lens.host_manifest import lens_host_launch_manifest, lens_host_persistent_supervision_plan
from francis.lens.preflight import lens_summon_enablement_gate

LENS_SUMMON_AUTHORITY_SCOPE = "system.write"
LENS_SUMMON_AUTHORITY_REQUEST_ACTION = "lens.summon.action_authority"
LENS_SUMMON_AUTHORITY_ROUTE = "/lens/summon/authority"
LENS_SUMMON_AUTHORITY_REQUEST_ROUTE = "/lens/summon/authority/request"
LENS_SUMMON_AUTHORITY_REQUESTS_ROUTE = "/lens/summon/authority/requests"
LENS_SUMMON_AUTHORITY_GRANTS_ROUTE = "/lens/summon/authority/grants"
LENS_SUMMON_EXECUTE_ROUTE = "/lens/summon/execute"
LENS_SUMMON_EXECUTIONS_ROUTE = "/lens/summon/executions"
LENS_SUMMON_READINESS_ROUTE = "/lens/summon/readiness"
_APPROVAL_STATUSES = ("pending", "approved", "rejected", "emergency")
_DEFAULT_LEASE_SECONDS = 60 * 60
_MIN_LEASE_SECONDS = 60
_MAX_LEASE_SECONDS = 24 * 60 * 60
_DEFAULT_RUN_SECONDS = 5
_MAX_RUN_SECONDS = 60
_SUMMON_ACTION_RUNNER_MAX_ATTEMPTS = 3
_SUMMON_ACTION_RUNNER_RETRY_SECONDS = 0.5


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
    return max(1, min(_MAX_RUN_SECONDS, parsed))


def _record_ts(value: Any) -> float:
    if isinstance(value, bool):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _now_s() -> int:
    return int(time.time())


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _filtered_record(record: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in record.items() if value not in ("", {}, [], None)}


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
        raw = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None
    return raw if isinstance(raw, dict) else None


def _permission(actor: Any, *, route: str, method: str) -> ApiPermissionDecision:
    return ApiPermissionGate.from_env().check(
        actor_id=actor,
        required_scopes=[LENS_SUMMON_AUTHORITY_SCOPE],
        route=route,
        method=method,
    )


def _permission_readiness(actor: Any, *, route: str, method: str) -> dict[str, Any]:
    decision = _permission(actor, route=route, method=method)
    return {
        "ready": decision.allowed,
        "allowed": decision.allowed,
        "reason": decision.reason,
        "required_scope": LENS_SUMMON_AUTHORITY_SCOPE,
        "evidence": decision.evidence,
    }


def _governance(
    *,
    route: str,
    approval_request_write: bool = True,
    read_only_contract: bool = False,
) -> dict[str, Any]:
    return {
        "gate": "lens_summon_action_authority_request",
        "route": route,
        "required_scope": LENS_SUMMON_AUTHORITY_SCOPE,
        "approval_action": LENS_SUMMON_AUTHORITY_REQUEST_ACTION,
        "approval_request_write": approval_request_write,
        "authority_route": LENS_SUMMON_AUTHORITY_ROUTE,
        "request_route": LENS_SUMMON_AUTHORITY_REQUEST_ROUTE,
        "readback_route": LENS_SUMMON_AUTHORITY_REQUESTS_ROUTE,
        "grants_route": LENS_SUMMON_AUTHORITY_GRANTS_ROUTE,
        "execute_route": LENS_SUMMON_EXECUTE_ROUTE,
        "executions_route": LENS_SUMMON_EXECUTIONS_ROUTE,
        "readiness_route": LENS_SUMMON_READINESS_ROUTE,
        "decision_route": "/approvals/decision",
        "read_only_contract": read_only_contract,
        "authority_granted": False,
        "summon_execution_authority": False,
        "bounded_local_open_handoff_authority": False,
        "execution_authority": False,
        "approval_decision_authority": False,
        "memory_write": False,
        "summon_authority": False,
        "summon_anywhere_authority": False,
        "os_level_summon_authority": False,
        "hotkey_registration_authority": False,
        "tray_registration_authority": False,
        "overlay_control_authority": False,
        "local_process_launch_authority": False,
        "process_supervision_authority": False,
        "service_control_authority": False,
        "capture_authority": False,
        "new_sensing_authority": False,
        "resident_claim_authority": False,
        "mutation_authority_granted": False,
        "next_step": "operator_decides_pending_summon_action_authority_request",
    }


def _permission_denied(decision: ApiPermissionDecision, *, route: str) -> dict[str, Any]:
    return {
        "ok": False,
        "applied": False,
        "executed": False,
        "approval_requested": False,
        "status": "denied",
        "error": "api_permission_denied",
        "action": LENS_SUMMON_AUTHORITY_REQUEST_ACTION,
        "authority_granted": False,
        "summon_authority": False,
        "summon_binding": False,
        "governance": {
            **_governance(route=route, approval_request_write=False),
            "gate": "permission_gate",
            "reason": decision.reason,
            "evidence": decision.evidence,
            "permission": decision.evidence,
            "next_step": "configure_actor_scope_before_requesting_summon_action_authority",
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
            if _safe_str(record.get("action")).strip() != LENS_SUMMON_AUTHORITY_REQUEST_ACTION:
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
            if isinstance(item, dict) and _safe_str(item.get("action")).strip() == LENS_SUMMON_AUTHORITY_REQUEST_ACTION
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
        return "authority_granted", "execute_bounded_summon_handoff"
    if counts.get("pending", 0) > 0:
        return "pending_review", "operator_decide_pending_summon_action_authority_request"
    if counts.get("emergency", 0) > 0:
        return "emergency_reviewed_no_authority", "operator_review_emergency_summon_action_decision"
    if counts.get("approved", 0) > 0:
        return "approved_no_authority", "approved_request_requires_separate_summon_action_authority_grant"
    if counts.get("rejected", 0) > 0:
        return "rejected", "operator_may_request_summon_action_authority_again"
    return "none", "request_summon_action_authority_before_execution"


def _request_payload(*, actor: Any, route: str) -> dict[str, Any]:
    summon_gate = lens_summon_enablement_gate()
    persistent_plan = lens_host_persistent_supervision_plan()
    blockers = _dedupe_strs(
        [
            *_str_list(summon_gate.get("blockers")),
            "summon_action_authority_not_granted",
        ]
    )
    return {
        "request_kind": "lens.summon.action_authority.request",
        "actor": _redact_free_text(actor),
        "route": route,
        "authority_route": LENS_SUMMON_AUTHORITY_ROUTE,
        "readback_route": LENS_SUMMON_AUTHORITY_REQUESTS_ROUTE,
        "grants_route": LENS_SUMMON_AUTHORITY_GRANTS_ROUTE,
        "execute_route": LENS_SUMMON_EXECUTE_ROUTE,
        "executions_route": LENS_SUMMON_EXECUTIONS_ROUTE,
        "readiness_route": LENS_SUMMON_READINESS_ROUTE,
        "status_route": "/lens/status",
        "summon_readiness": {
            "status": _safe_str(summon_gate.get("status")).strip(),
            "ready": bool(summon_gate.get("ready")),
            "summon_binding_ready": bool(summon_gate.get("summon_binding_ready")),
            "summon_anywhere": bool(summon_gate.get("summon_anywhere")),
            "blockers": _as_list(summon_gate.get("blockers")),
            "surface_dependencies": _as_dict(summon_gate.get("surface_dependencies")),
        },
        "persistent_supervision_plan": {
            "status": _safe_str(persistent_plan.get("status")).strip(),
            "ready": bool(persistent_plan.get("persistent_supervision_ready")),
            "first_missing_required_before_enable": _safe_str(
                persistent_plan.get("first_missing_required_before_enable")
            ).strip(),
        },
        "authority_boundary": {
            "status": "blocked",
            "authority_ready": False,
            "authority_granted": False,
            "summon_execution_authority": False,
            "bounded_local_open_handoff_authority": False,
            "summon_anywhere_authority": False,
            "os_level_summon_authority": False,
            "writes_memory": False,
            "decides_approval": False,
            "claims_resident": False,
            "blockers": blockers,
        },
        "blockers": blockers,
        "governance": {
            **_governance(route=route),
            "summon_readiness_governance": _as_dict(summon_gate.get("governance")),
            "would_execute_bounded_local_open_handoff": True,
            "would_write_receipt": True,
            "would_claim_summon_anywhere": False,
            "would_register_hotkey": False,
            "would_write_memory": False,
            "would_decide_approval": False,
            "would_claim_resident": False,
        },
    }


def request_lens_summon_authority(
    *,
    actor: Any,
    reason: Any = "request Lens summon action authority review",
    route: str = LENS_SUMMON_AUTHORITY_REQUEST_ROUTE,
    method: str = "POST",
) -> dict[str, Any]:
    safe_route = _safe_str(route).strip() or LENS_SUMMON_AUTHORITY_REQUEST_ROUTE
    permission = _permission(actor, route=safe_route, method=method)
    if not permission.allowed:
        return _permission_denied(permission, route=safe_route)

    request_reason = _redact_free_text(reason) or "request Lens summon action authority review"
    payload = _request_payload(actor=actor, route=safe_route)
    approval = create_approval_request(LENS_SUMMON_AUTHORITY_REQUEST_ACTION, request_reason, payload)
    approval_item = _approval_item(approval)
    return {
        "ok": True,
        "applied": False,
        "executed": False,
        "approval_requested": True,
        "status": "approval_requested",
        "action": LENS_SUMMON_AUTHORITY_REQUEST_ACTION,
        "approval_id": _safe_str(approval_item.get("id")),
        "approval": approval_item,
        "summon_authority": payload,
        "authority_granted": False,
        "summon_binding": False,
        "summon_anywhere": False,
        "governance": {
            **_governance(route=safe_route),
            "permission": permission.evidence,
        },
    }


def lens_summon_authority_request_readback(*, limit: int = 5) -> dict[str, Any]:
    safe_limit = _safe_limit(limit)
    grants = lens_summon_authority_grant_receipts(limit=1, active_only=True)
    authority_granted = bool(grants.get("authority_granted"))
    by_status, latest, counts = _approval_items(limit=safe_limit)
    status, next_step = _readback_status(counts, authority_granted=authority_granted)
    return {
        "ok": True,
        "kind": "lens.summon.action_authority.request_readback",
        "status": status,
        "route": LENS_SUMMON_AUTHORITY_REQUESTS_ROUTE,
        "authority_route": LENS_SUMMON_AUTHORITY_ROUTE,
        "request_route": LENS_SUMMON_AUTHORITY_REQUEST_ROUTE,
        "grants_route": LENS_SUMMON_AUTHORITY_GRANTS_ROUTE,
        "execute_route": LENS_SUMMON_EXECUTE_ROUTE,
        "executions_route": LENS_SUMMON_EXECUTIONS_ROUTE,
        "limit": safe_limit,
        "action": LENS_SUMMON_AUTHORITY_REQUEST_ACTION,
        "approval_counts": counts,
        "latest": latest[0] if latest else None,
        "pending": by_status.get("pending", []),
        "approved": by_status.get("approved", []),
        "rejected": by_status.get("rejected", []),
        "emergency": by_status.get("emergency", []),
        "active_authority_grant": _as_dict(grants.get("active_latest")),
        "authority_granted": authority_granted,
        "summon_binding": False,
        "summon_anywhere": False,
        "governance": {
            **_governance(
                route=LENS_SUMMON_AUTHORITY_REQUESTS_ROUTE,
                approval_request_write=False,
                read_only_contract=True,
            ),
            "gate": "lens_summon_action_authority_request_readback",
            "authority_granted": authority_granted,
            "summon_execution_authority": authority_granted,
            "bounded_local_open_handoff_authority": authority_granted,
            "execution_authority": False,
            "approval_decision_authority": False,
            "memory_write": False,
            "mutation_authority_granted": False,
            "next_step": next_step,
        },
    }


def _summon_authority_grant_receipt_root() -> Path:
    return data_dir() / "lens" / "summon_action_authority_grants"


def _summon_execution_receipt_root() -> Path:
    return data_dir() / "lens" / "summon_action_executions"


def _summon_authority_grant_receipt_id(*, approval_id: str, actor: str, route: str, ts: int) -> str:
    seed = f"{approval_id}:{actor}:{route}:{time.time_ns()}"
    digest = hashlib.sha256(seed.encode("utf-8", errors="replace")).hexdigest()[:12]
    return f"lsag_{ts}_{digest}"


def _summon_execution_receipt_id(*, approval_id: str, actor: str, route: str, ts: int) -> str:
    seed = f"{approval_id}:{actor}:{route}:{time.time_ns()}"
    digest = hashlib.sha256(seed.encode("utf-8", errors="replace")).hexdigest()[:12]
    return f"lsae_{ts}_{digest}"


def _summon_authority_grant_receipt_path(receipt_id: Any) -> Path | None:
    cleaned = _safe_str(receipt_id).strip()
    if not cleaned or "/" in cleaned or "\\" in cleaned or ".." in cleaned:
        return None
    return _summon_authority_grant_receipt_root() / f"{cleaned}.json"


def _summon_execution_receipt_path(receipt_id: Any) -> Path | None:
    cleaned = _safe_str(receipt_id).strip()
    if not cleaned or "/" in cleaned or "\\" in cleaned or ".." in cleaned:
        return None
    return _summon_execution_receipt_root() / f"{cleaned}.json"


def _summon_authority_grant_receipt(grant_response: dict[str, Any]) -> dict[str, Any]:
    ts = _now_s()
    approval_id = _safe_str(grant_response.get("approval_id")).strip()
    actor = _safe_str(grant_response.get("actor")).strip()
    route = _safe_str(grant_response.get("route")).strip() or LENS_SUMMON_AUTHORITY_ROUTE
    lease_seconds = _safe_lease_seconds(grant_response.get("lease_seconds"))
    receipt_id = _summon_authority_grant_receipt_id(
        approval_id=approval_id,
        actor=actor,
        route=route,
        ts=ts,
    )
    return _filtered_record(
        {
            "kind": "lens.summon.action_authority.grant_receipt",
            "receipt_id": receipt_id,
            "ts": ts,
            "status": "authority_granted",
            "approval_id": approval_id,
            "actor": actor,
            "route": route,
            "authority_route": LENS_SUMMON_AUTHORITY_ROUTE,
            "request_route": LENS_SUMMON_AUTHORITY_REQUEST_ROUTE,
            "requests_route": LENS_SUMMON_AUTHORITY_REQUESTS_ROUTE,
            "grants_route": LENS_SUMMON_AUTHORITY_GRANTS_ROUTE,
            "execute_route": LENS_SUMMON_EXECUTE_ROUTE,
            "executions_route": LENS_SUMMON_EXECUTIONS_ROUTE,
            "lease_seconds": lease_seconds,
            "expires_ts": ts + lease_seconds,
            "authority_granted": True,
            "summon_action_authority": True,
            "authorities": {
                "summon_execution_authority": True,
                "bounded_local_open_handoff_authority": True,
                "local_process_launch_authority": True,
                "receipt_write_authority": True,
                "summon_authority": True,
                "summon_anywhere_authority": False,
                "os_level_summon_authority": False,
                "hotkey_registration_authority": False,
                "overlay_control_authority": False,
                "tray_registration_authority": False,
                "capture_authority": False,
                "new_sensing_authority": False,
                "memory_write": False,
                "resident_claim_authority": False,
                "approval_decision_authority": False,
                "service_control_authority": False,
            },
            "governance": {
                **_governance(
                    route=LENS_SUMMON_AUTHORITY_GRANTS_ROUTE,
                    approval_request_write=False,
                    read_only_contract=True,
                ),
                "gate": "lens_summon_action_authority_grant_receipt",
                "authority_grant_boundary": True,
                "authority_granted": True,
                "summon_execution_authority": True,
                "bounded_local_open_handoff_authority": True,
                "execution_authority": True,
                "approval_decision_authority": False,
                "memory_write": False,
                "summon_authority": True,
                "summon_anywhere_authority": False,
                "os_level_summon_authority": False,
                "hotkey_registration_authority": False,
                "tray_registration_authority": False,
                "overlay_control_authority": False,
                "local_process_launch_authority": True,
                "capture_authority": False,
                "new_sensing_authority": False,
                "service_control_authority": False,
                "resident_claim_authority": False,
                "receipt_write_authority": True,
                "mutation_authority_granted": False,
            },
        }
    )


def _record_summon_authority_grant_receipt(grant_response: dict[str, Any]) -> dict[str, Any]:
    receipt = _summon_authority_grant_receipt(grant_response)
    path = _summon_authority_grant_receipt_path(receipt.get("receipt_id"))
    if path is None:
        return {}
    try:
        _atomic_write_json(path, receipt)
    except OSError:
        return {}
    return receipt


def _read_summon_authority_grant_receipt(path: Path) -> dict[str, Any] | None:
    item = _read_json(path)
    if not isinstance(item, dict) or _safe_str(item.get("kind")).strip() != (
        "lens.summon.action_authority.grant_receipt"
    ):
        return None
    return item


def _summon_authority_grant_active(item: dict[str, Any], *, now: int | None = None) -> bool:
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


def _list_summon_authority_grant_receipts(
    *,
    limit: int,
    approval_id: str = "",
    status: str = "",
    active_only: bool = False,
) -> tuple[list[dict[str, Any]], int]:
    root = _summon_authority_grant_receipt_root()
    if not root.exists():
        return [], 0
    now = _now_s()
    items: list[dict[str, Any]] = []
    for path in root.glob("*.json"):
        item = _read_summon_authority_grant_receipt(path)
        if item is None:
            continue
        if approval_id and _safe_str(item.get("approval_id")).strip() != approval_id:
            continue
        if status and _safe_str(item.get("status")).strip() != status:
            continue
        if active_only and not _summon_authority_grant_active(item, now=now):
            continue
        items.append(item)
    items.sort(key=lambda item: (_record_ts(item.get("ts")), _safe_str(item.get("receipt_id"))), reverse=True)
    return items[:limit], len(items)


def lens_summon_authority_grant_receipts(
    *,
    limit: int = 5,
    approval_id: Any = "",
    status: Any = "",
    active_only: bool = False,
) -> dict[str, Any]:
    safe_limit = _safe_limit(limit)
    safe_approval_id = _safe_str(approval_id).strip()
    safe_status = _safe_str(status).strip()
    items, total = _list_summon_authority_grant_receipts(
        limit=safe_limit,
        approval_id=safe_approval_id,
        status=safe_status,
        active_only=active_only,
    )
    latest = items[0] if items else None
    active_latest = next((item for item in items if _summon_authority_grant_active(item)), None)
    authority_granted = bool(active_latest)
    return {
        "ok": True,
        "kind": "lens.summon.action_authority.grant_receipts",
        "status": "readback_ready" if items else "empty",
        "route": LENS_SUMMON_AUTHORITY_GRANTS_ROUTE,
        "authority_route": LENS_SUMMON_AUTHORITY_ROUTE,
        "request_route": LENS_SUMMON_AUTHORITY_REQUEST_ROUTE,
        "requests_route": LENS_SUMMON_AUTHORITY_REQUESTS_ROUTE,
        "execute_route": LENS_SUMMON_EXECUTE_ROUTE,
        "executions_route": LENS_SUMMON_EXECUTIONS_ROUTE,
        "limit": safe_limit,
        "approval_id": safe_approval_id,
        "filter_status": safe_status,
        "active_only": active_only,
        "total": total,
        "latest": latest,
        "active_latest": active_latest,
        "authority_granted": authority_granted,
        "summon_action_authority": authority_granted,
        "summon_binding": False,
        "summon_anywhere": False,
        "items": items,
        "governance": {
            **_governance(
                route=LENS_SUMMON_AUTHORITY_GRANTS_ROUTE,
                approval_request_write=False,
                read_only_contract=True,
            ),
            "gate": "lens_summon_action_authority_grant_receipts_readback",
            "authority_grant_boundary": True,
            "authority_granted": authority_granted,
            "summon_execution_authority": authority_granted,
            "bounded_local_open_handoff_authority": authority_granted,
            "execution_authority": authority_granted,
            "approval_decision_authority": False,
            "memory_write": False,
            "summon_authority": authority_granted,
            "summon_anywhere_authority": False,
            "os_level_summon_authority": False,
            "hotkey_registration_authority": False,
            "tray_registration_authority": False,
            "overlay_control_authority": False,
            "local_process_launch_authority": authority_granted,
            "capture_authority": False,
            "new_sensing_authority": False,
            "service_control_authority": False,
            "resident_claim_authority": False,
            "mutation_authority_granted": False,
            "receipt_write_authority": authority_granted,
            "next_step": (
                "execute_bounded_summon_handoff"
                if authority_granted
                else "grant_exact_approved_summon_action_authority_request"
            ),
        },
    }


def grant_lens_summon_authority(
    *,
    approval_id: Any = "",
    actor: Any = "",
    reason: Any = "attempt Lens summon action authority grant",
    route: str = LENS_SUMMON_AUTHORITY_ROUTE,
    method: str = "POST",
    record_receipt: bool = False,
    lease_seconds: Any = _DEFAULT_LEASE_SECONDS,
) -> dict[str, Any]:
    safe_route = _safe_str(route).strip() or LENS_SUMMON_AUTHORITY_ROUTE
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
        blockers.append("summon_action_authority_approval_not_found")
    elif approval_lookup_status == "wrong_action":
        blockers.append("summon_action_authority_approval_wrong_action")
    elif not approval_ready:
        blockers.append("summon_action_authority_approval_not_approved")
    if not permission.allowed:
        blockers.append("system_write_scope_not_ready")
    deduped_blockers = _dedupe_strs(blockers)
    active_authority = approval_ready and permission.allowed and not deduped_blockers
    safe_lease_seconds = _safe_lease_seconds(lease_seconds)
    status = "authority_granted" if active_authority else "blocked"
    next_step = "execute_bounded_summon_handoff" if active_authority else "select_exact_approved_summon_action_request"
    governance = {
        **_governance(
            route=safe_route,
            approval_request_write=False,
            read_only_contract=False,
        ),
        "gate": (
            "lens_summon_action_authority_grant_boundary"
            if active_authority
            else "lens_summon_action_authority_grant_denial_boundary"
        ),
        "authority_grant_boundary": True,
        "authority_granted": active_authority,
        "summon_execution_authority": active_authority,
        "bounded_local_open_handoff_authority": active_authority,
        "approval_request_write": False,
        "execution_authority": active_authority,
        "approval_decision_authority": False,
        "memory_write": False,
        "summon_authority": active_authority,
        "summon_anywhere_authority": False,
        "os_level_summon_authority": False,
        "hotkey_registration_authority": False,
        "tray_registration_authority": False,
        "overlay_control_authority": False,
        "local_process_launch_authority": active_authority,
        "process_supervision_authority": False,
        "service_control_authority": False,
        "capture_authority": False,
        "new_sensing_authority": False,
        "resident_claim_authority": False,
        "mutation_authority_granted": False,
        "receipt_write_authority": active_authority,
        "permission": permission.evidence,
        "next_step": next_step,
    }
    response: dict[str, Any] = {
        "ok": True,
        "kind": "lens.summon.action_authority.grant"
        if active_authority
        else "lens.summon.action_authority.grant_denial",
        "status": status,
        "route": safe_route,
        "method": method,
        "request_route": LENS_SUMMON_AUTHORITY_REQUEST_ROUTE,
        "requests_route": LENS_SUMMON_AUTHORITY_REQUESTS_ROUTE,
        "grants_route": LENS_SUMMON_AUTHORITY_GRANTS_ROUTE,
        "execute_route": LENS_SUMMON_EXECUTE_ROUTE,
        "executions_route": LENS_SUMMON_EXECUTIONS_ROUTE,
        "readiness_route": LENS_SUMMON_READINESS_ROUTE,
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
        "receipt_route": LENS_SUMMON_AUTHORITY_GRANTS_ROUTE,
        "receipt_written": False,
        "receipt": {},
        "applied": False,
        "executed": False,
        "approval_requested": False,
        "authority_granted": active_authority,
        "summon_action_authority": active_authority,
        "summon_binding": False,
        "summon_anywhere": False,
        "permission": permission.evidence,
        "blockers": deduped_blockers,
        "grant": {
            "reason": "approved_summon_action_authority_lease",
            "lease_seconds": safe_lease_seconds,
            "would_grant_summon_execution_authority": active_authority,
            "would_grant_bounded_local_open_handoff_authority": active_authority,
            "would_grant_local_process_launch_authority": active_authority,
            "would_grant_receipt_write_authority": active_authority,
            "would_register_hotkey": False,
            "would_claim_summon_anywhere": False,
            "would_write_memory": False,
            "would_decide_approval": False,
            "would_claim_resident": False,
            "grant_receipt_written": False,
        },
        "governance": governance,
    }
    if record_receipt and active_authority:
        receipt = _record_summon_authority_grant_receipt(response)
        if receipt:
            response["receipt_written"] = True
            response["receipt"] = receipt
            response["applied"] = True
            response["grant"]["grant_receipt_written"] = True
    elif record_receipt:
        governance["grant_receipt_write_blocker"] = "summon_action_authority_not_ready"
    return response


def _summon_execution_mode(value: Any) -> str:
    requested = _safe_str(value).strip().lower().replace("-", "_")
    if requested in {"launch", "local_open", "summon", "start"}:
        return "launch"
    return "launch"


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


def _summon_config_override_path() -> Path:
    return data_dir() / "runtime" / "lens-summon" / "summon-action-override.json"


def _write_summon_config_override() -> Path:
    source = repo_root() / "config" / "runtime" / "lens" / "summon.json"
    config = _read_json(source) or {}
    config.update(
        {
            "enabled": True,
            "binding_enabled": True,
            "register_hotkey": True,
            "startup_register": False,
            "overlay_required": False,
            "tray_required": False,
            "summon_authority": True,
            "hotkey_registration_authority": True,
            "overlay_control_authority": True,
            "local_process_launch_authority": True,
            "blocked_reason": "",
        }
    )
    path = _summon_config_override_path()
    _atomic_write_json(path, config)
    return path


def _run_lens_summon_action(*, mode: str, run_seconds: int, allow_launch: bool) -> dict[str, Any]:
    root = repo_root()
    script = root / "scripts" / "lens-summon-action.ps1"
    if not script.is_file():
        return {
            "ok": False,
            "status": "lens_summon_action_entrypoint_missing",
            "script_mode": "Launch",
            "blockers": ["lens_summon_action_entrypoint_missing"],
        }

    powershell = _powershell_path()
    if not powershell:
        return {
            "ok": False,
            "status": "powershell_runtime_missing",
            "script_mode": "Launch",
            "blockers": ["powershell_runtime_missing"],
        }

    try:
        override_path = _write_summon_config_override()
    except OSError as exc:
        return {
            "ok": False,
            "status": "summon_config_override_failed",
            "script_mode": "Launch",
            "blockers": ["summon_config_override_failed"],
            "error": _redact_free_text(str(exc)),
        }

    command = [powershell, "-NoProfile"]
    if os.name == "nt":
        command.extend(["-ExecutionPolicy", "Bypass"])
    command.extend(
        [
            "-File",
            str(script),
            "-Mode",
            "Launch",
            "-DataDir",
            str(data_dir()),
            "-RunSeconds",
            str(_safe_run_seconds(run_seconds)),
            "-ConfigOverridePath",
            str(override_path),
        ]
    )
    if allow_launch:
        command.append("-AllowLaunch")
    env = dict(os.environ)
    env.setdefault("FRANCIS_ROOT", str(root))
    env.setdefault("FRANCIS_DATA_DIR", str(data_dir()))
    attempts: list[dict[str, Any]] = []
    for attempt_number in range(1, _SUMMON_ACTION_RUNNER_MAX_ATTEMPTS + 1):
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
            attempt = {
                "ok": False,
                "status": "summon_action_timeout",
                "attempt": attempt_number,
                "returncode": None,
                "script_mode": "Launch",
                "script": "scripts/lens-summon-action.ps1",
                "runner": {},
                "blockers": ["lens_summon_action_timeout"],
                "stderr": "",
            }
            attempts.append(attempt)
            return {
                **attempt,
                "attempt_count": attempt_number,
                "attempts": attempts,
            }
        except OSError as exc:
            attempt = {
                "ok": False,
                "status": "summon_action_launch_failed",
                "attempt": attempt_number,
                "returncode": None,
                "script_mode": "Launch",
                "script": "scripts/lens-summon-action.ps1",
                "runner": {},
                "blockers": ["lens_summon_action_failed"],
                "error": _redact_free_text(str(exc)),
                "stderr": "",
            }
            attempts.append(attempt)
            return {
                **attempt,
                "attempt_count": attempt_number,
                "attempts": attempts,
            }

        payload = _parse_json_process_stdout(completed.stdout)
        runner_ok = completed.returncode == 0 and bool(payload.get("ok"))
        stderr = (completed.stderr or "").strip()
        attempt = {
            "ok": runner_ok,
            "status": _safe_str(payload.get("status")).strip() or "summon_action_failed",
            "attempt": attempt_number,
            "returncode": completed.returncode,
            "script_mode": "Launch",
            "script": "scripts/lens-summon-action.ps1",
            "runner": _display(payload),
            "blockers": _str_list(payload.get("blockers")),
            "stderr": _redact_free_text(stderr[:500]) if stderr else "",
        }
        attempts.append(attempt)
        if runner_ok or attempt_number == _SUMMON_ACTION_RUNNER_MAX_ATTEMPTS:
            return {
                **attempt,
                "attempt_count": attempt_number,
                "attempts": attempts,
            }
        time.sleep(_SUMMON_ACTION_RUNNER_RETRY_SECONDS)

    return {
        "ok": False,
        "status": "summon_action_failed",
        "attempt_count": len(attempts),
        "attempts": attempts,
        "script_mode": "Launch",
        "script": "scripts/lens-summon-action.ps1",
        "runner": {},
        "blockers": ["lens_summon_action_failed"],
        "stderr": "",
    }


def _summon_handoff_payload(runner_payload: dict[str, Any]) -> dict[str, Any]:
    bounded_handoff = _as_dict(runner_payload.get("bounded_handoff"))
    return _as_dict(bounded_handoff.get("payload"))


def _summon_bounded_handoff_ready(*, runner_ok: bool, runner_payload: dict[str, Any]) -> bool:
    bounded_handoff = _as_dict(runner_payload.get("bounded_handoff"))
    handoff_payload = _as_dict(bounded_handoff.get("payload"))
    handoff_status = _safe_str(bounded_handoff.get("status")).strip()
    payload_status = _safe_str(handoff_payload.get("status")).strip()
    return (
        runner_ok
        and handoff_status in {"local_open_ready", "opened"}
        and payload_status
        in {
            "local_open_ready",
            "opened",
        }
    )


def _write_summon_runtime_state(
    *,
    runner_ok: bool,
    runner_payload: dict[str, Any],
    allow_launch: bool,
    approval_id: str,
    active_grant_receipt_id: str,
    actor: Any,
    route: str,
) -> dict[str, Any]:
    config = _read_json(repo_root() / "config" / "runtime" / "lens" / "summon.json") or {}
    launch_manifest = lens_host_launch_manifest()
    hotkey_runtime = _as_dict(launch_manifest.get("hotkey_runtime_readback"))
    hotkey_runtime_ready = bool(hotkey_runtime.get("ready"))
    hotkey_launch_on_press = hotkey_runtime_ready and bool(hotkey_runtime.get("launch_on_hotkey"))
    handoff_payload = _summon_handoff_payload(runner_payload)
    bounded_ready = _summon_bounded_handoff_ready(runner_ok=runner_ok, runner_payload=runner_payload)
    opened = bool(handoff_payload.get("opened"))
    local_open_ready = bounded_ready or bool(handoff_payload.get("local_open_available"))
    summon_anywhere_ready = allow_launch and bounded_ready and hotkey_launch_on_press
    runtime_state = {
        "kind": "lens.summon.runtime_state",
        "status": "summon_binding_observed" if bounded_ready else "summon_binding_failed",
        "updated_at": _now_iso(),
        "approval_id": approval_id,
        "active_grant_receipt_id": active_grant_receipt_id,
        "actor": _redact_free_text(actor),
        "route": route,
        "global_hotkey": _safe_str(handoff_payload.get("global_hotkey")).strip()
        or _safe_str(config.get("global_hotkey")).strip(),
        "binding_scope": _safe_str(handoff_payload.get("binding_scope")).strip()
        or _safe_str(config.get("binding_scope")).strip()
        or "global",
        "bounded_handoff_ready": bounded_ready,
        "local_open_ready": local_open_ready,
        "opened": opened,
        "no_launch": bool(handoff_payload.get("no_launch")) or not allow_launch,
        "allow_launch": allow_launch,
        "summon_anywhere": summon_anywhere_ready,
        "os_level_summon": summon_anywhere_ready,
        "hotkey_runtime_ready": hotkey_runtime_ready,
        "hotkey_launch_on_press": hotkey_launch_on_press,
        "hotkey_runtime_pid": int(hotkey_runtime.get("pid") or 0),
        "local_open_target_url": _safe_str(handoff_payload.get("local_open_target_url")).strip(),
        "runner_status": _safe_str(runner_payload.get("status")).strip(),
        "handoff_status": _safe_str(_as_dict(runner_payload.get("bounded_handoff")).get("status")).strip(),
        "governance": {
            "execution_authority": runner_ok,
            "summon_authority": runner_ok,
            "bounded_local_open_handoff_authority": runner_ok,
            "local_process_launch_authority": allow_launch and opened,
            "hotkey_registration_authority": False,
            "overlay_control_authority": False,
            "summon_anywhere_authority": False,
            "os_level_summon_authority": False,
            "memory_write": False,
            "resident_claim_authority": False,
            "mutation_authority_granted": allow_launch and opened,
        },
    }
    _atomic_write_json(data_dir() / "runtime" / "lens-summon" / "status.json", runtime_state)
    return runtime_state


def _first_missing_gap(post_plan: dict[str, Any], *, fallback: str) -> str:
    handoff = _as_dict(post_plan.get("first_missing_requirement_handoff"))
    gap = _safe_str(handoff.get("next_smallest_truthful_gap")).strip()
    return gap or fallback


def _summon_execution_receipt(execution: dict[str, Any]) -> dict[str, Any]:
    ts = _now_s()
    approval_id = _safe_str(execution.get("approval_id")).strip()
    actor = _safe_str(execution.get("actor")).strip()
    route = _safe_str(execution.get("route")).strip() or LENS_SUMMON_EXECUTE_ROUTE
    receipt_id = _summon_execution_receipt_id(
        approval_id=approval_id,
        actor=actor,
        route=route,
        ts=ts,
    )
    summon_runtime = _as_dict(execution.get("summon_runtime_readback"))
    return _filtered_record(
        {
            "kind": "lens.summon.action.execution_receipt",
            "receipt_id": receipt_id,
            "ts": ts,
            "status": _safe_str(execution.get("status")).strip(),
            "approval_id": approval_id,
            "actor": actor,
            "route": route,
            "authority_route": LENS_SUMMON_AUTHORITY_ROUTE,
            "authority_grants_route": LENS_SUMMON_AUTHORITY_GRANTS_ROUTE,
            "executions_route": LENS_SUMMON_EXECUTIONS_ROUTE,
            "active_grant_receipt_id": _safe_str(execution.get("active_grant_receipt_id")).strip(),
            "execution": {
                "mode": _safe_str(execution.get("mode")).strip(),
                "summon_binding": bool(execution.get("summon_binding")),
                "bounded_handoff_ready": bool(execution.get("bounded_handoff_ready")),
                "local_open_ready": bool(execution.get("local_open_ready")),
                "opened": bool(execution.get("opened")),
                "allow_launch": bool(execution.get("allow_launch")),
                "summon_anywhere": bool(execution.get("summon_anywhere")),
                "os_level_summon": bool(execution.get("os_level_summon")),
                "global_hotkey": _safe_str(summon_runtime.get("global_hotkey")).strip(),
                "binding_scope": _safe_str(summon_runtime.get("binding_scope")).strip(),
                "next_smallest_truthful_gap": _safe_str(execution.get("next_smallest_truthful_gap")).strip(),
            },
            "resident_claim": {
                "resident_host_process_claimed": False,
                "resident_claim_allowed": False,
            },
            "governance": _as_dict(execution.get("governance")),
        }
    )


def _record_summon_execution_receipt(execution: dict[str, Any]) -> dict[str, Any]:
    receipt = _summon_execution_receipt(execution)
    path = _summon_execution_receipt_path(receipt.get("receipt_id"))
    if path is None:
        return {}
    try:
        _atomic_write_json(path, receipt)
    except OSError:
        return {}
    return receipt


def _read_summon_execution_receipt(path: Path) -> dict[str, Any] | None:
    item = _read_json(path)
    if not isinstance(item, dict) or _safe_str(item.get("kind")).strip() != "lens.summon.action.execution_receipt":
        return None
    return item


def _list_summon_execution_receipts(
    *,
    limit: int,
    approval_id: str = "",
    status: str = "",
) -> tuple[list[dict[str, Any]], int]:
    root = _summon_execution_receipt_root()
    if not root.exists():
        return [], 0
    items: list[dict[str, Any]] = []
    for path in root.glob("*.json"):
        item = _read_summon_execution_receipt(path)
        if item is None:
            continue
        if approval_id and _safe_str(item.get("approval_id")).strip() != approval_id:
            continue
        if status and _safe_str(item.get("status")).strip() != status:
            continue
        items.append(item)
    items.sort(key=lambda item: (_record_ts(item.get("ts")), _safe_str(item.get("receipt_id"))), reverse=True)
    return items[:limit], len(items)


def lens_summon_action_execution_receipts(
    *,
    limit: int = 5,
    approval_id: Any = "",
    status: Any = "",
) -> dict[str, Any]:
    safe_limit = _safe_limit(limit)
    safe_approval_id = _safe_str(approval_id).strip()
    safe_status = _safe_str(status).strip()
    items, total = _list_summon_execution_receipts(
        limit=safe_limit,
        approval_id=safe_approval_id,
        status=safe_status,
    )
    latest = items[0] if items else None
    latest_execution = _as_dict(_as_dict(latest).get("execution"))
    return {
        "ok": True,
        "kind": "lens.summon.action.execution_receipts",
        "status": "readback_ready" if items else "empty",
        "route": LENS_SUMMON_EXECUTIONS_ROUTE,
        "execute_route": LENS_SUMMON_EXECUTE_ROUTE,
        "authority_route": LENS_SUMMON_AUTHORITY_ROUTE,
        "authority_grants_route": LENS_SUMMON_AUTHORITY_GRANTS_ROUTE,
        "limit": safe_limit,
        "approval_id": safe_approval_id,
        "filter_status": safe_status,
        "total": total,
        "latest": latest,
        "latest_status": _safe_str(_as_dict(latest).get("status")).strip(),
        "latest_summon_binding": bool(latest_execution.get("summon_binding")),
        "latest_summon_anywhere": bool(latest_execution.get("summon_anywhere")),
        "latest_next_smallest_truthful_gap": _safe_str(latest_execution.get("next_smallest_truthful_gap")).strip(),
        "items": items,
        "governance": {
            **_governance(
                route=LENS_SUMMON_EXECUTIONS_ROUTE,
                approval_request_write=False,
                read_only_contract=True,
            ),
            "gate": "lens_summon_action_execution_receipts_readback",
            "execution_receipts_readback": True,
            "execution_authority": False,
            "approval_decision_authority": False,
            "memory_write": False,
            "mutation_authority_granted": False,
        },
    }


def execute_lens_summon_action(
    *,
    approval_id: Any = "",
    actor: Any = "",
    reason: Any = "attempt Lens summon action execution",
    route: str = LENS_SUMMON_EXECUTE_ROUTE,
    method: str = "POST",
    record_receipt: bool = False,
    mode: Any = "launch",
    run_seconds: Any = _DEFAULT_RUN_SECONDS,
    allow_launch: bool = False,
) -> dict[str, Any]:
    safe_route = _safe_str(route).strip() or LENS_SUMMON_EXECUTE_ROUTE
    safe_approval_id = _safe_str(approval_id).strip()
    safe_mode = _summon_execution_mode(mode)
    safe_run_seconds = _safe_run_seconds(run_seconds)
    permission = _permission_readiness(actor, route=safe_route, method=method)
    grants = lens_summon_authority_grant_receipts(
        limit=1,
        approval_id=safe_approval_id,
        active_only=True,
    )
    active_grant = _as_dict(grants.get("active_latest"))
    authorities = _as_dict(active_grant.get("authorities"))
    blockers: list[str] = []
    if not safe_approval_id:
        blockers.append("approval_id_required")
    if not active_grant:
        blockers.append("summon_action_authority_grant_not_active")
    if not bool(authorities.get("summon_execution_authority")):
        blockers.append("summon_execution_authority_not_granted")
    if not bool(authorities.get("bounded_local_open_handoff_authority")):
        blockers.append("bounded_local_open_handoff_authority_not_granted")
    if not bool(authorities.get("summon_authority")):
        blockers.append("summon_authority_not_granted")
    if record_receipt and not bool(authorities.get("receipt_write_authority")):
        blockers.append("receipt_write_authority_not_granted")
    if not bool(permission.get("ready")):
        blockers.append("system_write_scope_not_ready")

    deduped_blockers = _dedupe_strs(blockers)
    if deduped_blockers:
        return {
            "ok": True,
            "applied": False,
            "executed": False,
            "kind": "lens.summon.action.execution.denial",
            "status": "blocked",
            "route": safe_route,
            "method": method,
            "mode": safe_mode,
            "approval_id": safe_approval_id,
            "actor": _redact_free_text(actor),
            "reason": _redact_free_text(reason),
            "run_seconds": safe_run_seconds,
            "allow_launch": allow_launch,
            "authority_route": LENS_SUMMON_AUTHORITY_ROUTE,
            "authority_grants_route": LENS_SUMMON_AUTHORITY_GRANTS_ROUTE,
            "receipts_route": LENS_SUMMON_EXECUTIONS_ROUTE,
            "active_grant": active_grant,
            "active_grant_receipt_id": _safe_str(active_grant.get("receipt_id")).strip(),
            "authorities": authorities,
            "permission": permission,
            "blockers": deduped_blockers,
            "receipt_written": False,
            "receipt": {},
            "governance": {
                **_governance(
                    route=safe_route,
                    approval_request_write=False,
                    read_only_contract=False,
                ),
                "gate": "lens_summon_action_execution_denial",
                "execution_boundary": True,
                "authority_granted": bool(active_grant),
                "summon_execution_authority": bool(authorities.get("summon_execution_authority")),
                "bounded_local_open_handoff_authority": bool(authorities.get("bounded_local_open_handoff_authority")),
                "execution_authority": False,
                "approval_decision_authority": False,
                "local_process_launch_authority": False,
                "overlay_control_authority": False,
                "hotkey_registration_authority": False,
                "tray_registration_authority": False,
                "summon_authority": bool(authorities.get("summon_authority")),
                "summon_anywhere_authority": False,
                "os_level_summon_authority": False,
                "service_control_authority": False,
                "memory_write": False,
                "resident_claim_authority": False,
                "receipt_write_authority": False,
                "mutation_authority_granted": False,
                "next_step": "grant_summon_action_authority_before_execution",
            },
        }

    runner = _run_lens_summon_action(mode=safe_mode, run_seconds=safe_run_seconds, allow_launch=allow_launch)
    runner_ok = bool(runner.get("ok"))
    runner_payload = _as_dict(runner.get("runner"))
    runtime_state = _write_summon_runtime_state(
        runner_ok=runner_ok,
        runner_payload=runner_payload,
        allow_launch=allow_launch,
        approval_id=safe_approval_id,
        active_grant_receipt_id=_safe_str(active_grant.get("receipt_id")).strip(),
        actor=actor,
        route=safe_route,
    )
    post_manifest = lens_host_launch_manifest()
    post_plan = lens_host_persistent_supervision_plan(manifest=post_manifest)
    summon_runtime = _as_dict(post_manifest.get("summon_runtime_readback"))
    bounded_ready = bool(summon_runtime.get("bounded_handoff_ready"))
    local_open_ready = bool(summon_runtime.get("local_open_ready"))
    opened = bool(summon_runtime.get("opened"))
    summon_binding = bool(summon_runtime.get("ready"))
    summon_anywhere_ready = bool(summon_runtime.get("summon_anywhere")) and bool(summon_runtime.get("os_level_summon"))
    status = "summon_binding_observed" if runner_ok and summon_binding else "summon_action_failed"
    next_gap = _first_missing_gap(
        post_plan,
        fallback="stage6_lens_completion_audit" if summon_anywhere_ready else "summon_anywhere_runtime_readback",
    )
    response: dict[str, Any] = {
        "ok": True,
        "applied": runner_ok,
        "executed": runner_ok,
        "kind": "lens.summon.action.execution",
        "status": status,
        "route": safe_route,
        "method": method,
        "mode": safe_mode,
        "approval_id": safe_approval_id,
        "actor": _redact_free_text(actor),
        "reason": _redact_free_text(reason),
        "run_seconds": safe_run_seconds,
        "allow_launch": allow_launch,
        "authority_route": LENS_SUMMON_AUTHORITY_ROUTE,
        "authority_grants_route": LENS_SUMMON_AUTHORITY_GRANTS_ROUTE,
        "receipts_route": LENS_SUMMON_EXECUTIONS_ROUTE,
        "active_grant": active_grant,
        "active_grant_receipt_id": _safe_str(active_grant.get("receipt_id")).strip(),
        "authorities": authorities,
        "permission": permission,
        "runner": runner,
        "runner_payload": runner_payload,
        "summon_runtime_state": runtime_state,
        "summon_runtime_readback": summon_runtime,
        "post_persistent_supervision_plan": post_plan,
        "summon_binding": summon_binding,
        "summon_runtime_ready": bool(summon_runtime.get("ready")),
        "bounded_handoff_ready": bounded_ready,
        "local_open_ready": local_open_ready,
        "opened": opened,
        "no_launch": bool(summon_runtime.get("no_launch")),
        "summon_anywhere": summon_anywhere_ready,
        "os_level_summon": summon_anywhere_ready,
        "resident_claim_allowed": False,
        "next_smallest_truthful_gap": next_gap,
        "blockers": _dedupe_strs(_str_list(runner.get("blockers"))),
        "receipt_written": False,
        "receipt": {},
        "governance": {
            **_governance(
                route=safe_route,
                approval_request_write=False,
                read_only_contract=False,
            ),
            "gate": "lens_summon_action_execution",
            "execution_boundary": True,
            "authority_granted": True,
            "summon_execution_authority": True,
            "bounded_local_open_handoff_authority": True,
            "execution_authority": runner_ok,
            "approval_decision_authority": False,
            "local_process_launch_authority": allow_launch and opened,
            "overlay_control_authority": False,
            "hotkey_registration_authority": False,
            "tray_registration_authority": False,
            "summon_authority": runner_ok,
            "summon_anywhere_authority": False,
            "os_level_summon_authority": False,
            "service_control_authority": False,
            "process_supervision_authority": False,
            "memory_write": False,
            "resident_claim_authority": False,
            "capture_authority": False,
            "new_sensing_authority": False,
            "receipt_write_authority": False,
            "mutation_authority_granted": allow_launch and opened,
            "persistent_resident_claim": False,
            "next_step": (
                "continue_with_persistent_supervision_enablement_boundary"
                if summon_binding
                else "resolve_summon_action_execution_failure"
            ),
        },
    }
    if record_receipt and bool(permission.get("ready")) and bool(authorities.get("receipt_write_authority")):
        receipt = _record_summon_execution_receipt(response)
        if receipt:
            response["receipt_written"] = True
            response["receipt"] = receipt
            response["governance"]["receipt_write_authority"] = True
    elif record_receipt:
        response["governance"]["receipt_write_blocker"] = "receipt_write_authority_not_granted"
    return response
