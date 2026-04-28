from __future__ import annotations

from typing import Any

from francis.governance.approval_projection import approval_projection_fields
from francis.governance.approvals import request as create_approval_request
from francis.governance.api_permission_gate import ApiPermissionDecision, ApiPermissionGate
from francis.governance.redaction import redact_governed_display_value, redact_secret_text
from francis.lens.host_manifest import lens_host_launch_manifest
from francis.lens.preflight import lens_preflight

LENS_HOST_ACTIVATION_ACTION = "lens.host.foreground_activation"
LENS_HOST_ACTIVATION_ROUTE = "/lens/host/activation/request"
LENS_HOST_ACTIVATION_SCOPE = "system.write"

_DEFAULT_REASON = "request Lens host foreground activation"
_DEFAULT_MODE = "foreground_status_session"
_ALLOWED_MODES = {_DEFAULT_MODE}


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


def _activation_mode(value: Any) -> str:
    mode = _safe_str(value).strip().lower()
    return mode if mode in _ALLOWED_MODES else _DEFAULT_MODE


def _activation_governance(*, route: str) -> dict[str, Any]:
    return {
        "gate": "lens_host_activation_request",
        "route": route,
        "required_scope": LENS_HOST_ACTIVATION_SCOPE,
        "approval_action": LENS_HOST_ACTIVATION_ACTION,
        "approval_request_write": True,
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
