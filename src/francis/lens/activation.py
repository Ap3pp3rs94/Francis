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
from francis.lens.host_manifest import lens_host_launch_manifest
from francis.lens.preflight import lens_preflight
from francis.world_state.operator_mode import snapshot as operator_mode_snapshot

LENS_HOST_ACTIVATION_ACTION = "lens.host.foreground_activation"
LENS_HOST_ACTIVATION_ROUTE = "/lens/host/activation/request"
LENS_HOST_ACTIVATION_READBACK_ROUTE = "/lens/host/activation"
LENS_HOST_ACTIVATION_PREFLIGHT_ROUTE = "/lens/host/activation/preflight"
LENS_HOST_ACTIVATION_PLAN_ROUTE = "/lens/host/activation/plan"
LENS_HOST_ACTIVATION_EXECUTE_ROUTE = "/lens/host/activation/execute"
LENS_HOST_ACTIVATION_DENIALS_ROUTE = "/lens/host/activation/denials"
LENS_RESIDENT_SURFACE_ACTIVATION_ROUTE = "/lens/resident-surface/activation"
LENS_HOST_ACTIVATION_SCOPE = "system.write"

_DEFAULT_REASON = "request Lens host foreground activation"
_DEFAULT_MODE = "foreground_status_session"
_ALLOWED_MODES = {_DEFAULT_MODE}
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


def _now_s() -> int:
    return int(time.time())


def _filtered_record(record: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in record.items() if value not in ("", {}, [], None)}


def _display(record: dict[str, Any]) -> dict[str, Any]:
    redacted = redact_governed_display_value(record)
    return redacted if isinstance(redacted, dict) else {}


def _activation_denial_receipt_root() -> Path:
    return data_dir() / "lens" / "host_activation_denials"


def _activation_denial_receipt_id(*, approval_id: str, actor: str, route: str, ts: int) -> str:
    seed = f"{approval_id}:{actor}:{route}:{time.time_ns()}"
    digest = hashlib.sha256(seed.encode("utf-8", errors="replace")).hexdigest()[:12]
    return f"lad_{ts}_{digest}"


def _activation_denial_receipt_path(receipt_id: Any) -> Path | None:
    cleaned = _safe_str(receipt_id).strip()
    if not cleaned or "/" in cleaned or "\\" in cleaned or ".." in cleaned:
        return None
    return _activation_denial_receipt_root() / f"{cleaned}.json"


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


def _activation_mode(value: Any) -> str:
    mode = _safe_str(value).strip().lower()
    return mode if mode in _ALLOWED_MODES else _DEFAULT_MODE


def _activation_governance(
    *,
    route: str,
    approval_request_write: bool = True,
    read_only_contract: bool = False,
) -> dict[str, Any]:
    return {
        "gate": "lens_host_activation_request",
        "route": route,
        "required_scope": LENS_HOST_ACTIVATION_SCOPE,
        "approval_action": LENS_HOST_ACTIVATION_ACTION,
        "approval_request_write": approval_request_write,
        "readback_route": LENS_HOST_ACTIVATION_READBACK_ROUTE,
        "preflight_route": LENS_HOST_ACTIVATION_PREFLIGHT_ROUTE,
        "plan_route": LENS_HOST_ACTIVATION_PLAN_ROUTE,
        "execute_route": LENS_HOST_ACTIVATION_EXECUTE_ROUTE,
        "denials_route": LENS_HOST_ACTIVATION_DENIALS_ROUTE,
        "read_only_contract": read_only_contract,
        "activation_authority": False,
        "execution_authority": False,
        "approval_decision_authority": False,
        "memory_write": False,
        "local_process_launch_authority": False,
        "service_install_authority": False,
        "service_control_authority": False,
        "overlay_control_authority": False,
        "summon_authority": False,
        "hotkey_registration_authority": False,
        "runtime_mutation_authority_granted": False,
        "next_step": "operator_decides_pending_lens_host_activation_request",
    }


def lens_host_activation_request_contract() -> dict[str, Any]:
    return {
        "status": "approval_request_ready",
        "route": LENS_HOST_ACTIVATION_ROUTE,
        "readback_route": LENS_HOST_ACTIVATION_READBACK_ROUTE,
        "preflight_route": LENS_HOST_ACTIVATION_PREFLIGHT_ROUTE,
        "plan_route": LENS_HOST_ACTIVATION_PLAN_ROUTE,
        "execute_route": LENS_HOST_ACTIVATION_EXECUTE_ROUTE,
        "denials_route": LENS_HOST_ACTIVATION_DENIALS_ROUTE,
        "method": "POST",
        "action": LENS_HOST_ACTIVATION_ACTION,
        "mode": _DEFAULT_MODE,
        "creates_approval_request": True,
        "launches_process": False,
        "installs_service": False,
        "starts_service": False,
        "registers_hotkey": False,
        "controls_overlay": False,
        "governance": _activation_governance(route=LENS_HOST_ACTIVATION_ROUTE),
    }


def _permission(actor: Any, *, route: str, method: str) -> ApiPermissionDecision:
    return ApiPermissionGate.from_env().check(
        actor_id=actor,
        required_scopes=[LENS_HOST_ACTIVATION_SCOPE],
        route=route,
        method=method,
    )


def _permission_readiness(actor: Any, *, route: str, method: str) -> dict[str, Any]:
    decision = _permission(actor, route=route, method=method)
    return {
        "ready": decision.allowed,
        "allowed": decision.allowed,
        "reason": decision.reason,
        "required_scope": LENS_HOST_ACTIVATION_SCOPE,
        "evidence": decision.evidence,
    }


def _permission_denied(decision: ApiPermissionDecision, *, route: str) -> dict[str, Any]:
    return {
        "ok": False,
        "applied": False,
        "approval_requested": False,
        "status": "denied",
        "error": "api_permission_denied",
        "governance": {
            "gate": "permission_gate",
            "route": route,
            "required_scope": LENS_HOST_ACTIVATION_SCOPE,
            "reason": decision.reason,
            "next_step": "configure_actor_scope_before_requesting_lens_host_activation",
            "evidence": decision.evidence,
            "activation_authority": False,
            "execution_authority": False,
            "approval_decision_authority": False,
            "local_process_launch_authority": False,
            "service_control_authority": False,
        },
    }


def _approval_item(record: dict[str, Any]) -> dict[str, Any]:
    item = dict(record) if isinstance(record, dict) else {}
    redacted = redact_governed_display_value(item)
    out = redacted if isinstance(redacted, dict) else {}
    out.update(approval_projection_fields(item))
    return out


def _activation_approval_items(
    *, limit: int
) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]], dict[str, int]]:
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
            if isinstance(item, dict) and _safe_str(item.get("action")).strip() == LENS_HOST_ACTIVATION_ACTION
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


def _activation_approval_by_id(approval_id: Any) -> tuple[dict[str, Any] | None, str]:
    requested_id = _safe_str(approval_id).strip()
    if not requested_id:
        return None, "missing"

    for status in _APPROVAL_STATUSES:
        try:
            records = list_requests(status=status, limit=5000)
        except Exception:
            records = []
        for record in records:
            if not isinstance(record, dict):
                continue
            if _safe_str(record.get("id")).strip() != requested_id:
                continue
            if _safe_str(record.get("action")).strip() != LENS_HOST_ACTIVATION_ACTION:
                return None, "wrong_action"
            return _approval_item(record), status
    return None, "not_found"


def _activation_readback_status(counts: dict[str, int]) -> tuple[str, str]:
    if counts.get("pending", 0) > 0:
        return "pending_review", "operator_decide_pending_lens_host_activation_request"
    if counts.get("emergency", 0) > 0:
        return "emergency_reviewed_no_execution", "operator_review_emergency_activation_decision"
    if counts.get("approved", 0) > 0:
        return "approved_no_execution", "approved_activation_requires_separate_execution_slice"
    if counts.get("rejected", 0) > 0:
        return "rejected", "operator_may_request_lens_host_activation_again"
    return "none", "request_lens_host_activation_before_runtime_start"


def lens_host_activation_readback(*, limit: int = 5) -> dict[str, Any]:
    safe_limit = _safe_limit(limit)
    by_status, latest_items, counts = _activation_approval_items(limit=safe_limit)
    total = sum(counts.values())
    status, next_step = _activation_readback_status(counts)
    latest = latest_items[0] if latest_items else None
    return {
        "ok": True,
        "kind": "lens.host.activation.readback",
        "status": status,
        "route": LENS_HOST_ACTIVATION_READBACK_ROUTE,
        "request_route": LENS_HOST_ACTIVATION_ROUTE,
        "decision_route": "/approvals/decision",
        "approval_action": LENS_HOST_ACTIVATION_ACTION,
        "pending_count": counts.get("pending", 0),
        "approved_count": counts.get("approved", 0),
        "rejected_count": counts.get("rejected", 0),
        "emergency_count": counts.get("emergency", 0),
        "total_count": total,
        "latest": latest,
        "items": latest_items,
        "by_status": by_status,
        "governance": {
            **_activation_governance(
                route=LENS_HOST_ACTIVATION_READBACK_ROUTE,
                approval_request_write=False,
                read_only_contract=True,
            ),
            "gate": "lens_host_activation_readback",
            "read_only_contract": True,
            "next_step": next_step,
        },
    }


def _operator_posture_readiness() -> dict[str, Any]:
    try:
        state = operator_mode_snapshot()
    except Exception as exc:
        return {
            "ready": False,
            "status": "unavailable",
            "reason": _safe_str(exc),
            "control_mode": {},
            "posture": {},
        }

    if not bool(state.get("ok")):
        return {
            "ready": False,
            "status": "unavailable",
            "reason": _safe_str(state.get("error") or "operator_mode_unavailable"),
            "control_mode": {},
            "posture": {},
        }

    control_mode = _as_dict(state.get("control_mode"))
    posture = _as_dict(state.get("posture"))
    control_mode_id = _safe_str(control_mode.get("id")).strip().lower()
    control_writes = _safe_str(control_mode.get("writes")).strip().lower()
    posture_writes = _safe_str(posture.get("writes")).strip().lower()
    blocked_reason = ""
    if control_mode_id == "observe" or control_writes == "blocked":
        blocked_reason = "observe_mode_blocks_activation"
    elif posture_writes == "blocked":
        blocked_reason = "operator_posture_blocks_activation"

    return {
        "ready": not blocked_reason,
        "status": "ready" if not blocked_reason else "blocked",
        "reason": blocked_reason,
        "control_mode": {
            "id": control_mode_id,
            "writes": control_writes,
            "implementation_status": _safe_str(control_mode.get("implementation_status")).strip(),
        },
        "posture": {
            "writes": posture_writes,
            "governance_mode": _safe_str(posture.get("governance_mode")).strip(),
            "trust_posture": _safe_str(posture.get("trust_posture")).strip(),
        },
    }


def _activation_preflight_status(blockers: list[str]) -> tuple[str, str]:
    if not blockers:
        return "ready_for_execution_slice", "implement_separate_lens_host_execution_slice"
    if "approval_id_required" in blockers:
        return "blocked", "select_exact_approved_activation_request"
    if "activation_approval_not_approved" in blockers:
        return "blocked", "approve_exact_lens_host_activation_request"
    if "system_write_scope_not_ready" in blockers:
        return "blocked", "configure_actor_scope_before_lens_host_activation"
    if "operator_posture_not_ready" in blockers:
        return "blocked", "switch_operator_posture_before_lens_host_activation"
    return "blocked", "remove_lens_host_activation_blockers_before_execution"


def lens_host_activation_execution_preflight(*, approval_id: Any = "", actor: Any = "") -> dict[str, Any]:
    requested_id = _safe_str(approval_id).strip()
    approval, approval_lookup_status = _activation_approval_by_id(requested_id)
    approval_status = _safe_str(_as_dict(approval).get("status")).strip() if approval else approval_lookup_status
    approval_ready = bool(approval) and approval_status == "approved"
    permission = _permission_readiness(actor, route=LENS_HOST_ACTIVATION_PREFLIGHT_ROUTE, method="GET")
    posture = _operator_posture_readiness()
    manifest = lens_host_launch_manifest()
    preflight = lens_preflight()
    candidate_command = _as_dict(manifest.get("candidate_command"))
    foreground_session = _as_dict(manifest.get("foreground_session"))
    process_readback = _as_dict(manifest.get("process_readback"))
    service_plan = _as_dict(manifest.get("service_plan"))

    blockers: list[str] = []
    if not requested_id:
        blockers.append("approval_id_required")
    elif approval_lookup_status == "not_found":
        blockers.append("activation_approval_not_found")
    elif approval_lookup_status == "wrong_action":
        blockers.append("activation_approval_wrong_action")
    elif not approval_ready:
        blockers.append("activation_approval_not_approved")

    if not bool(permission.get("ready")):
        blockers.append("system_write_scope_not_ready")
    if not bool(posture.get("ready")):
        blockers.append("operator_posture_not_ready")
    if not bool(candidate_command.get("executable")):
        blockers.append("lens_host_foreground_command_unavailable")
    if not bool(foreground_session.get("supported")):
        blockers.append("foreground_session_not_supported")
    if bool(process_readback.get("process_alive")):
        blockers.append("lens_host_process_already_observed")
    if _safe_str(preflight.get("status")).strip() != "ready":
        blockers.append("lens_preflight_blocked")
    blockers.extend(_str_list(preflight.get("blockers")))
    blockers.append("local_process_launch_authority_not_granted")

    deduped_blockers = sorted({blocker for blocker in blockers if blocker})
    status, next_step = _activation_preflight_status(deduped_blockers)
    return {
        "ok": True,
        "kind": "lens.host.activation.execution_preflight",
        "status": status,
        "ready": not deduped_blockers,
        "route": LENS_HOST_ACTIVATION_PREFLIGHT_ROUTE,
        "plan_route": LENS_HOST_ACTIVATION_PLAN_ROUTE,
        "execute_route": LENS_HOST_ACTIVATION_EXECUTE_ROUTE,
        "request_route": LENS_HOST_ACTIVATION_ROUTE,
        "readback_route": LENS_HOST_ACTIVATION_READBACK_ROUTE,
        "approval_id": requested_id,
        "approval": {
            "required": True,
            "found": bool(approval),
            "status": approval_status,
            "approved": approval_ready,
            "item": approval,
        },
        "permission": permission,
        "operator_posture": posture,
        "host": {
            "candidate_command": candidate_command,
            "foreground_session": foreground_session,
            "process_readback": {
                "status": _safe_str(process_readback.get("status")),
                "process_alive": bool(process_readback.get("process_alive")),
                "pid_present": bool(process_readback.get("pid_present")),
                "supervision_enabled": bool(process_readback.get("supervision_enabled")),
            },
            "service_plan": {
                "status": _safe_str(service_plan.get("status")),
                "ready": bool(service_plan.get("ready")),
                "blocked_by": _as_list(service_plan.get("blocked_by")),
            },
            "preflight": {
                "status": _safe_str(preflight.get("status")),
                "ready": bool(preflight.get("ready")),
                "blockers": _as_list(preflight.get("blockers")),
            },
        },
        "blockers": deduped_blockers,
        "governance": {
            **_activation_governance(
                route=LENS_HOST_ACTIVATION_PREFLIGHT_ROUTE,
                approval_request_write=False,
                read_only_contract=True,
            ),
            "gate": "lens_host_activation_execution_preflight",
            "next_step": next_step,
        },
    }


def _step_status(blockers: list[str], blocker_ids: set[str]) -> str:
    return "blocked" if blocker_ids.intersection(blockers) else "ready"


def _plan_step(
    step_id: str,
    *,
    label: str,
    status: str,
    source: str,
    authority_required: str = "",
    authority_granted: bool = False,
) -> dict[str, Any]:
    return {
        "id": step_id,
        "label": label,
        "status": status,
        "source": source,
        "authority_required": authority_required,
        "authority_granted": authority_granted,
    }


def _activation_execution_plan_status(blockers: list[str]) -> tuple[str, str]:
    if "approval_id_required" in blockers:
        return "blocked", "select_exact_approved_activation_request"
    if "activation_approval_not_found" in blockers or "activation_approval_wrong_action" in blockers:
        return "blocked", "select_matching_lens_host_activation_request"
    if "activation_approval_not_approved" in blockers:
        return "blocked", "approve_exact_lens_host_activation_request"
    if "system_write_scope_not_ready" in blockers:
        return "blocked", "configure_actor_scope_before_lens_host_activation"
    if "operator_posture_not_ready" in blockers:
        return "blocked", "switch_operator_posture_before_lens_host_activation"
    return "blocked", "implement_lens_host_execution_authority_in_separate_slice"


def lens_host_activation_execution_plan(*, approval_id: Any = "", actor: Any = "") -> dict[str, Any]:
    preflight = lens_host_activation_execution_preflight(approval_id=approval_id, actor=actor)
    blockers = _str_list(preflight.get("blockers"))
    host = _as_dict(preflight.get("host"))
    candidate_command = _as_dict(host.get("candidate_command"))
    foreground_session = _as_dict(host.get("foreground_session"))
    process_readback = _as_dict(host.get("process_readback"))
    service_plan = _as_dict(host.get("service_plan"))
    status, next_step = _activation_execution_plan_status(blockers)
    steps = [
        _plan_step(
            "verify_exact_approval",
            label="Verify exact Lens host activation approval",
            status=_step_status(
                blockers,
                {
                    "approval_id_required",
                    "activation_approval_not_found",
                    "activation_approval_wrong_action",
                    "activation_approval_not_approved",
                },
            ),
            source=LENS_HOST_ACTIVATION_READBACK_ROUTE,
        ),
        _plan_step(
            "verify_actor_scope",
            label="Verify actor has system.write for Lens activation",
            status=_step_status(blockers, {"system_write_scope_not_ready"}),
            source=LENS_HOST_ACTIVATION_PREFLIGHT_ROUTE,
        ),
        _plan_step(
            "verify_operator_posture",
            label="Verify operator posture allows writes",
            status=_step_status(blockers, {"operator_posture_not_ready"}),
            source="operator_mode_snapshot",
        ),
        _plan_step(
            "verify_host_command",
            label="Verify bounded foreground Lens host command",
            status=_step_status(
                blockers,
                {
                    "lens_host_foreground_command_unavailable",
                    "foreground_session_not_supported",
                    "lens_preflight_blocked",
                },
            ),
            source="/lens/host/manifest",
        ),
        _plan_step(
            "verify_no_existing_host_process",
            label="Verify no Lens host process is already observed",
            status=_step_status(blockers, {"lens_host_process_already_observed"}),
            source="/lens/host/manifest",
        ),
        _plan_step(
            "launch_foreground_status_session",
            label="Launch bounded foreground Lens host status session",
            status="blocked",
            source="future_execution_slice",
            authority_required="local_process_launch",
            authority_granted=False,
        ),
        _plan_step(
            "record_activation_receipt",
            label="Record activation receipt after launch",
            status="blocked",
            source="future_receipt_slice",
            authority_required="receipt_write",
            authority_granted=False,
        ),
    ]
    return {
        "ok": True,
        "kind": "lens.host.activation.execution_plan",
        "status": status,
        "plan_available": True,
        "execution_ready": False,
        "route": LENS_HOST_ACTIVATION_PLAN_ROUTE,
        "execute_route": LENS_HOST_ACTIVATION_EXECUTE_ROUTE,
        "preflight_route": LENS_HOST_ACTIVATION_PREFLIGHT_ROUTE,
        "request_route": LENS_HOST_ACTIVATION_ROUTE,
        "readback_route": LENS_HOST_ACTIVATION_READBACK_ROUTE,
        "approval_id": _safe_str(preflight.get("approval_id")).strip(),
        "actor": _redact_free_text(actor),
        "preflight": preflight,
        "plan": {
            "mode": _DEFAULT_MODE,
            "launch_kind": "foreground_status_session",
            "steps": steps,
            "candidate_command": candidate_command,
            "foreground_session": foreground_session,
            "process_readback": process_readback,
            "service_plan": service_plan,
            "would_launch_process": False,
            "would_install_service": False,
            "would_start_service": False,
            "would_register_hotkey": False,
            "would_open_overlay": False,
            "would_write_memory": False,
            "would_decide_approval": False,
        },
        "blockers": blockers,
        "governance": {
            **_activation_governance(
                route=LENS_HOST_ACTIVATION_PLAN_ROUTE,
                approval_request_write=False,
                read_only_contract=True,
            ),
            "gate": "lens_host_activation_execution_plan",
            "read_only_contract": True,
            "plan_readback_only": True,
            "execution_authority": False,
            "approval_decision_authority": False,
            "local_process_launch_authority": False,
            "receipt_write_authority": False,
            "next_step": next_step,
        },
    }


def _execution_denial_status(blockers: list[str]) -> tuple[str, str]:
    if "approval_id_required" in blockers:
        return "blocked", "select_exact_approved_activation_request"
    if "activation_approval_not_found" in blockers or "activation_approval_wrong_action" in blockers:
        return "blocked", "select_matching_lens_host_activation_request"
    if "activation_approval_not_approved" in blockers:
        return "blocked", "approve_exact_lens_host_activation_request"
    if "system_write_scope_not_ready" in blockers:
        return "blocked", "configure_actor_scope_before_lens_host_activation"
    if "operator_posture_not_ready" in blockers:
        return "blocked", "switch_operator_posture_before_lens_host_activation"
    return "denied_no_execution_authority", "implement_lens_host_execution_authority_in_separate_slice"


def _activation_denial_receipt(denial: dict[str, Any]) -> dict[str, Any]:
    ts = _now_s()
    approval_id = _safe_str(denial.get("approval_id")).strip()
    actor = _safe_str(denial.get("actor")).strip()
    route = _safe_str(denial.get("route")).strip() or LENS_HOST_ACTIVATION_EXECUTE_ROUTE
    receipt_id = _activation_denial_receipt_id(approval_id=approval_id, actor=actor, route=route, ts=ts)
    preflight = _as_dict(denial.get("preflight"))
    approval = _as_dict(preflight.get("approval"))
    permission = _as_dict(denial.get("permission"))
    plan = _as_dict(denial.get("plan"))
    plan_body = _as_dict(plan.get("plan"))
    return _filtered_record(
        {
            "kind": "lens.host.activation.denial.receipt",
            "receipt_id": receipt_id,
            "id": receipt_id,
            "status": _safe_str(denial.get("status")).strip(),
            "route": route,
            "method": _safe_str(denial.get("method")).strip() or "POST",
            "source_kind": _safe_str(denial.get("kind")).strip(),
            "source_route": route,
            "approval_id": approval_id,
            "actor": actor,
            "reason": _safe_str(denial.get("reason")).strip(),
            "created_ts": ts,
            "blockers": _str_list(denial.get("blockers")),
            "approval": {
                "required": bool(approval.get("required")),
                "found": bool(approval.get("found")),
                "status": _safe_str(approval.get("status")).strip(),
                "approved": bool(approval.get("approved")),
            },
            "permission": {
                "ready": bool(permission.get("ready")),
                "allowed": bool(permission.get("allowed")),
                "reason": _safe_str(permission.get("reason")).strip(),
                "required_scope": _safe_str(permission.get("required_scope")).strip(),
            },
            "execution": {
                "applied": bool(denial.get("applied")),
                "executed": bool(denial.get("executed")),
                "would_launch_process": bool(plan_body.get("would_launch_process")),
                "would_install_service": bool(plan_body.get("would_install_service")),
                "would_start_service": bool(plan_body.get("would_start_service")),
                "would_register_hotkey": bool(plan_body.get("would_register_hotkey")),
                "would_open_overlay": bool(plan_body.get("would_open_overlay")),
                "would_write_memory": bool(plan_body.get("would_write_memory")),
                "would_decide_approval": bool(plan_body.get("would_decide_approval")),
            },
            "denial": _as_dict(denial.get("denial")),
            "governance": {
                "gate": "lens_host_activation_denial_receipt",
                "denial_boundary": True,
                "execution_authority": False,
                "approval_decision_authority": False,
                "activation_authority": False,
                "local_process_launch_authority": False,
                "service_install_authority": False,
                "service_control_authority": False,
                "overlay_control_authority": False,
                "summon_authority": False,
                "hotkey_registration_authority": False,
                "memory_write": False,
                "denial_receipt_write_authority": True,
                "receipt_write_authority": False,
            },
        }
    )


def _record_activation_denial_receipt(denial: dict[str, Any]) -> dict[str, Any]:
    receipt = _activation_denial_receipt(denial)
    path = _activation_denial_receipt_path(receipt.get("receipt_id"))
    if path is None:
        return {}
    receipt["path"] = str(path)
    display = _display(receipt)
    _atomic_write_json(path, display)
    return display


def _read_activation_denial_receipt(path: Path) -> dict[str, Any] | None:
    raw = _read_json(path)
    return _display(raw) if raw is not None else None


def _matches_filter(item: dict[str, Any], *, approval_id: str, status: str) -> bool:
    if approval_id and _safe_str(item.get("approval_id")).strip() != approval_id:
        return False
    if status and _safe_str(item.get("status")).strip() != status:
        return False
    return True


def _list_activation_denial_receipts(
    *,
    limit: int,
    approval_id: str = "",
    status: str = "",
) -> tuple[list[dict[str, Any]], int]:
    root = _activation_denial_receipt_root()
    if not root.exists():
        return [], 0
    items: list[dict[str, Any]] = []
    for path in root.glob("*.json"):
        item = _read_activation_denial_receipt(path)
        if not item:
            continue
        if not _matches_filter(item, approval_id=approval_id, status=status):
            continue
        items.append(item)
    items.sort(
        key=lambda item: (_record_ts(item.get("created_ts")), _safe_str(item.get("receipt_id"))),
        reverse=True,
    )
    return items[:limit], len(items)


def lens_host_activation_denial_receipts(
    *,
    limit: int = 5,
    approval_id: Any = "",
    status: Any = "",
) -> dict[str, Any]:
    safe_limit = _safe_limit(limit)
    safe_approval_id = _safe_str(approval_id).strip()
    safe_status = _safe_str(status).strip()
    items, total = _list_activation_denial_receipts(
        limit=safe_limit,
        approval_id=safe_approval_id,
        status=safe_status,
    )
    latest = items[0] if items else None
    return {
        "ok": True,
        "kind": "lens.host.activation.denial_receipts",
        "status": "readback_ready" if items else "empty",
        "route": LENS_HOST_ACTIVATION_DENIALS_ROUTE,
        "execute_route": LENS_HOST_ACTIVATION_EXECUTE_ROUTE,
        "limit": safe_limit,
        "approval_id": safe_approval_id,
        "filter_status": safe_status,
        "total": total,
        "latest": latest,
        "items": items,
        "governance": {
            **_activation_governance(
                route=LENS_HOST_ACTIVATION_DENIALS_ROUTE,
                approval_request_write=False,
                read_only_contract=True,
            ),
            "gate": "lens_host_activation_denial_receipts_readback",
            "read_only_contract": True,
            "denial_receipt_write_authority": False,
            "receipt_write_authority": False,
            "next_step": "review_denial_receipts_before_adding_execution_authority",
        },
    }


def _surface_component(
    component_id: str,
    *,
    label: str,
    route: str,
    status: Any,
    ready: Any,
    blockers: Any = None,
    required_before_enable: Any = None,
) -> dict[str, Any]:
    return {
        "id": component_id,
        "label": label,
        "route": route,
        "status": _safe_str(status).strip() or "missing",
        "ready": bool(ready),
        "blockers": _str_list(blockers),
        "required_before_enable": _str_list(required_before_enable),
    }


def lens_resident_surface_activation_boundary(
    *,
    approval_id: Any = "",
    actor: Any = "",
    limit: int = 5,
) -> dict[str, Any]:
    safe_limit = _safe_limit(limit)
    safe_approval_id = _safe_str(approval_id).strip()
    activation_state = lens_host_activation_readback(limit=safe_limit)
    execution_preflight = lens_host_activation_execution_preflight(approval_id=safe_approval_id, actor=actor)
    execution_plan = lens_host_activation_execution_plan(approval_id=safe_approval_id, actor=actor)
    execution_denial = deny_lens_host_activation_execution(
        approval_id=safe_approval_id,
        actor=actor,
        reason="prove resident surface activation boundary",
        route=LENS_HOST_ACTIVATION_EXECUTE_ROUTE,
        method="POST",
        record_receipt=False,
    )
    preflight = lens_preflight()
    surfaces = _as_dict(preflight.get("surfaces"))
    host_surface = _as_dict(surfaces.get("host"))
    summon_surface = _as_dict(surfaces.get("summon"))
    tray_surface = _as_dict(surfaces.get("tray"))
    overlay_surface = _as_dict(surfaces.get("overlay"))
    plan_body = _as_dict(execution_plan.get("plan"))
    denial = _as_dict(execution_denial.get("denial"))
    approval = _as_dict(execution_preflight.get("approval"))
    blockers = _dedupe_strs(
        [
            *_str_list(preflight.get("blockers")),
            *_str_list(execution_plan.get("blockers")),
            *_str_list(execution_denial.get("blockers")),
            "resident_surface_missing",
            "live_operator_experience_proof_missing",
        ]
    )
    components = [
        _surface_component(
            "host_activation_preflight",
            label="Host activation preflight",
            route=LENS_HOST_ACTIVATION_PREFLIGHT_ROUTE,
            status=execution_preflight.get("status"),
            ready=execution_preflight.get("ready"),
            blockers=execution_preflight.get("blockers"),
        ),
        _surface_component(
            "host_activation_plan",
            label="Host activation execution plan",
            route=LENS_HOST_ACTIVATION_PLAN_ROUTE,
            status=execution_plan.get("status"),
            ready=execution_plan.get("execution_ready"),
            blockers=execution_plan.get("blockers"),
        ),
        _surface_component(
            "host_activation_denial",
            label="Host activation execution denial",
            route=LENS_HOST_ACTIVATION_EXECUTE_ROUTE,
            status=execution_denial.get("status"),
            ready=execution_denial.get("executed"),
            blockers=execution_denial.get("blockers"),
        ),
        _surface_component(
            "host_preflight",
            label="Resident host preflight",
            route="/lens/preflight",
            status=host_surface.get("status"),
            ready=host_surface.get("ready"),
            blockers=host_surface.get("blockers"),
            required_before_enable=host_surface.get("required_before_enable"),
        ),
        _surface_component(
            "summon_preflight",
            label="Summon hotkey preflight",
            route="/lens/preflight",
            status=summon_surface.get("status"),
            ready=summon_surface.get("ready"),
            blockers=summon_surface.get("blockers"),
            required_before_enable=summon_surface.get("required_before_enable"),
        ),
        _surface_component(
            "tray_preflight",
            label="Tray presence preflight",
            route="/lens/preflight",
            status=tray_surface.get("status"),
            ready=tray_surface.get("ready"),
            blockers=tray_surface.get("blockers"),
            required_before_enable=tray_surface.get("required_before_enable"),
        ),
        _surface_component(
            "overlay_preflight",
            label="Overlay window preflight",
            route="/lens/preflight",
            status=overlay_surface.get("status"),
            ready=overlay_surface.get("ready"),
            blockers=overlay_surface.get("blockers"),
            required_before_enable=overlay_surface.get("required_before_enable"),
        ),
    ]
    return {
        "ok": True,
        "kind": "lens.resident_surface.activation_boundary",
        "status": "blocked",
        "route": LENS_RESIDENT_SURFACE_ACTIVATION_ROUTE,
        "approval_id": safe_approval_id,
        "actor": _redact_free_text(actor),
        "boundary_ready": True,
        "activation_ready": False,
        "resident_surface_ready": False,
        "ready_for_lens_resident_claim": False,
        "resident_claim_allowed": False,
        "execution_ready": False,
        "executed": False,
        "applied": False,
        "operator_experience_proof": False,
        "approval": {
            "readback_route": LENS_HOST_ACTIVATION_READBACK_ROUTE,
            "status": _safe_str(activation_state.get("status")).strip(),
            "selected_status": _safe_str(approval.get("status")).strip(),
            "selected_approved": bool(approval.get("approved")),
            "pending_count": activation_state.get("pending_count", 0),
            "approved_count": activation_state.get("approved_count", 0),
        },
        "execution": {
            "preflight_route": LENS_HOST_ACTIVATION_PREFLIGHT_ROUTE,
            "plan_route": LENS_HOST_ACTIVATION_PLAN_ROUTE,
            "execute_route": LENS_HOST_ACTIVATION_EXECUTE_ROUTE,
            "preflight_status": _safe_str(execution_preflight.get("status")).strip(),
            "plan_status": _safe_str(execution_plan.get("status")).strip(),
            "denial_status": _safe_str(execution_denial.get("status")).strip(),
            "would_launch_process": bool(plan_body.get("would_launch_process")),
            "would_install_service": bool(plan_body.get("would_install_service")),
            "would_start_service": bool(plan_body.get("would_start_service")),
            "would_register_hotkey": bool(plan_body.get("would_register_hotkey")),
            "would_open_overlay": bool(plan_body.get("would_open_overlay")),
            "would_write_memory": bool(plan_body.get("would_write_memory")),
            "would_decide_approval": bool(plan_body.get("would_decide_approval")),
            "denial_reason": _safe_str(denial.get("reason")).strip(),
        },
        "surface": {
            "preflight_route": "/lens/preflight",
            "status": _safe_str(preflight.get("status")).strip(),
            "ready": bool(preflight.get("ready")),
            "host_status": _safe_str(host_surface.get("status")).strip(),
            "summon_status": _safe_str(summon_surface.get("status")).strip(),
            "tray_status": _safe_str(tray_surface.get("status")).strip(),
            "overlay_status": _safe_str(overlay_surface.get("status")).strip(),
        },
        "components": components,
        "blockers": blockers,
        "next_smallest_truthful_gap": "live_operator_experience_proof",
        "governance": {
            **_activation_governance(
                route=LENS_RESIDENT_SURFACE_ACTIVATION_ROUTE,
                approval_request_write=False,
                read_only_contract=True,
            ),
            "gate": "lens_resident_surface_activation_boundary",
            "boundary_only": True,
            "read_only_contract": True,
            "activation_authority": False,
            "execution_authority": False,
            "approval_decision_authority": False,
            "local_process_launch_authority": False,
            "service_install_authority": False,
            "service_control_authority": False,
            "tray_registration_authority": False,
            "tray_icon_authority": False,
            "hotkey_registration_authority": False,
            "overlay_control_authority": False,
            "summon_authority": False,
            "capture_authority": False,
            "memory_write": False,
            "receipt_write_authority": False,
            "denial_receipt_write_authority": False,
            "runtime_mutation_authority_granted": False,
            "next_step": "prove_live_operator_experience_before_stage_6_closure",
        },
    }


def deny_lens_host_activation_execution(
    *,
    approval_id: Any = "",
    actor: Any = "",
    reason: Any = "attempt Lens host foreground activation",
    route: str = LENS_HOST_ACTIVATION_EXECUTE_ROUTE,
    method: str = "POST",
    record_receipt: bool = False,
) -> dict[str, Any]:
    safe_route = _safe_str(route).strip() or LENS_HOST_ACTIVATION_EXECUTE_ROUTE
    permission = _permission_readiness(actor, route=safe_route, method=method)
    plan = lens_host_activation_execution_plan(approval_id=approval_id, actor=actor)
    preflight = _as_dict(plan.get("preflight"))
    blockers = _str_list(plan.get("blockers"))
    if not bool(permission.get("ready")) and "system_write_scope_not_ready" not in blockers:
        blockers.append("system_write_scope_not_ready")
    if "local_process_launch_authority_not_granted" not in blockers:
        blockers.append("local_process_launch_authority_not_granted")
    deduped_blockers = sorted({blocker for blocker in blockers if blocker})
    status, next_step = _execution_denial_status(deduped_blockers)
    response: dict[str, Any] = {
        "ok": True,
        "applied": False,
        "executed": False,
        "kind": "lens.host.activation.execution_denial",
        "status": status,
        "route": safe_route,
        "method": method,
        "request_route": LENS_HOST_ACTIVATION_ROUTE,
        "readback_route": LENS_HOST_ACTIVATION_READBACK_ROUTE,
        "preflight_route": LENS_HOST_ACTIVATION_PREFLIGHT_ROUTE,
        "plan_route": LENS_HOST_ACTIVATION_PLAN_ROUTE,
        "approval_id": _safe_str(plan.get("approval_id")).strip(),
        "actor": _redact_free_text(actor),
        "reason": _redact_free_text(reason),
        "receipt_route": LENS_HOST_ACTIVATION_DENIALS_ROUTE,
        "receipt_written": False,
        "receipt": {},
        "permission": permission,
        "preflight": preflight,
        "plan": plan,
        "blockers": deduped_blockers,
        "denial": {
            "reason": "local_process_launch_authority_not_granted",
            "message": "Lens host activation execution is blocked until explicit local process launch authority exists.",
            "would_launch_process": False,
            "would_write_receipt": False,
            "would_install_service": False,
            "would_start_service": False,
            "would_register_hotkey": False,
            "would_open_overlay": False,
            "denial_receipt_written": False,
        },
        "governance": {
            **_activation_governance(
                route=safe_route,
                approval_request_write=False,
                read_only_contract=False,
            ),
            "gate": "lens_host_activation_execution_denial",
            "execution_boundary": True,
            "denial_boundary": True,
            "execution_authority": False,
            "approval_decision_authority": False,
            "local_process_launch_authority": False,
            "receipt_write_authority": False,
            "denial_receipt_write_authority": False,
            "next_step": next_step,
        },
    }
    if record_receipt and bool(permission.get("ready")):
        receipt = _record_activation_denial_receipt(response)
        if receipt:
            response["receipt_written"] = True
            response["receipt"] = receipt
            response["denial"]["denial_receipt_written"] = True
            response["governance"]["denial_receipt_write_authority"] = True
    elif record_receipt:
        response["governance"]["denial_receipt_write_blocker"] = "system_write_scope_not_ready"
    return response


def _activation_payload(*, actor: Any, mode: str, route: str) -> dict[str, Any]:
    manifest = lens_host_launch_manifest()
    preflight = lens_preflight()
    service_plan = _as_dict(manifest.get("service_plan"))
    process_readback = _as_dict(manifest.get("process_readback"))
    governance = _activation_governance(route=route)
    return {
        "request_kind": "lens.host.activation.request",
        "mode": mode,
        "actor": _redact_free_text(actor),
        "route": route,
        "host_route": "/lens/host",
        "manifest_route": "/lens/host/manifest",
        "preflight_route": "/lens/preflight",
        "candidate_command": _as_dict(manifest.get("candidate_command")),
        "foreground_session": _as_dict(manifest.get("foreground_session")),
        "service_plan": {
            "status": _safe_str(service_plan.get("status")),
            "ready": bool(service_plan.get("ready")),
            "planned_command": _safe_str(service_plan.get("planned_command")),
            "blocked_by": _as_list(service_plan.get("blocked_by")),
            "governance": _as_dict(service_plan.get("governance")),
        },
        "process_readback": {
            "status": _safe_str(process_readback.get("status")),
            "pid_present": bool(process_readback.get("pid_present")),
            "process_alive": bool(process_readback.get("process_alive")),
            "supervision_enabled": bool(process_readback.get("supervision_enabled")),
        },
        "preflight": {
            "status": _safe_str(preflight.get("status")),
            "ready": bool(preflight.get("ready")),
            "blockers": _as_list(preflight.get("blockers")),
        },
        "blockers": _as_list(manifest.get("blockers")),
        "governance": governance,
    }


def request_lens_host_activation(
    *,
    actor: Any,
    reason: Any = _DEFAULT_REASON,
    mode: Any = _DEFAULT_MODE,
    route: str = LENS_HOST_ACTIVATION_ROUTE,
    method: str = "POST",
) -> dict[str, Any]:
    safe_route = _safe_str(route).strip() or LENS_HOST_ACTIVATION_ROUTE
    permission = _permission(actor, route=safe_route, method=method)
    if not permission.allowed:
        return _permission_denied(permission, route=safe_route)

    safe_mode = _activation_mode(mode)
    request_reason = _redact_free_text(reason) or _DEFAULT_REASON
    activation = _activation_payload(actor=actor, mode=safe_mode, route=safe_route)
    approval = create_approval_request(LENS_HOST_ACTIVATION_ACTION, request_reason, activation)
    approval_item = _approval_item(approval)
    return {
        "ok": True,
        "applied": False,
        "approval_requested": True,
        "status": "approval_requested",
        "action": LENS_HOST_ACTIVATION_ACTION,
        "approval_id": _safe_str(approval_item.get("id")),
        "approval": approval_item,
        "activation": activation,
        "governance": {
            **_activation_governance(route=safe_route),
            "permission": permission.evidence,
        },
    }
