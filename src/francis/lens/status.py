from __future__ import annotations

import time
from typing import Any

from francis.governance.approval_projection import approval_projection_fields
from francis.governance.approvals import list_requests
from francis.governance.redaction import redact_governed_display_value
from francis.lens.activation import (
    deny_lens_host_activation_execution,
    deny_lens_host_persistent_supervision_enablement,
    deny_lens_host_persistent_supervision_enablement_execution,
    deny_lens_host_supervision_authority_grant,
    deny_lens_resident_runtime_activation_execution,
    grant_lens_resident_runtime_execution_authority,
    grant_lens_host_persistent_supervision_enablement_execution_authority,
    grant_lens_host_persistent_supervision_enablement_authority,
    lens_host_activation_denial_receipts,
    lens_host_activation_authority_grant_receipts,
    lens_host_activation_execution_preflight,
    lens_host_activation_execution_plan,
    lens_host_activation_readback,
    lens_host_activation_request_contract,
    lens_host_persistent_supervision_enablement_execution_authority_grant_receipts,
    lens_host_persistent_supervision_enablement_execution_receipts,
    lens_host_persistent_supervision_enablement_execution_readiness_audit,
    lens_host_persistent_supervision_enablement_execution_request_contract,
    lens_host_persistent_supervision_enablement_execution_request_readback,
    lens_host_persistent_supervision_enablement_authority_readiness_audit,
    lens_host_persistent_supervision_enablement_authority_grant_receipts,
    lens_host_persistent_supervision_enablement_authority_request_contract,
    lens_host_persistent_supervision_enablement_authority_request_readback,
    lens_host_supervision_authority_denial_receipts,
    lens_host_supervision_authority_grant_receipts,
    lens_host_supervision_authority_request_contract,
    lens_host_supervision_authority_request_readback,
    lens_host_supervision_authority_readiness_audit,
    lens_resident_runtime_activation_denial_receipts,
    lens_resident_runtime_activation_execution_receipts,
    lens_resident_runtime_authority_grant_denial_receipts,
    lens_resident_runtime_authority_grant_readiness_audit,
    lens_resident_runtime_execution_authority_grant_receipts,
    lens_resident_runtime_execution_authority_request_contract,
    lens_resident_runtime_execution_authority_request_readback,
    lens_resident_runtime_execution_policy_contract,
    lens_resident_runtime_activation_preflight,
    lens_resident_runtime_activation_plan,
    lens_resident_surface_activation_boundary,
)
from francis.lens.host_manifest import (
    lens_host_launch_manifest,
    lens_host_persistent_supervision_enablement_preflight,
    lens_host_persistent_supervision_plan,
    lens_host_supervision_authority_preflight,
    lens_host_supervision_gate,
)
from francis.lens.host_runtime_plan import (
    deny_lens_host_runtime_loop_execution,
    lens_host_runtime_implementation_plan,
    lens_host_runtime_loop_contract,
    lens_host_runtime_loop_denial_receipts,
    lens_host_runtime_loop_readiness_audit,
)
from francis.lens.os_binding_authority import (
    lens_os_binding_authority_request_readback,
    lens_os_binding_execution_receipts,
    lens_os_binding_execution_readiness_audit,
)
from francis.lens.overlay_authority import (
    lens_overlay_authority_request_readback,
    lens_overlay_window_execution_receipts,
)
from francis.lens.preflight import (
    lens_os_binding_readiness,
    lens_overlay_enablement_gate,
    lens_preflight,
    lens_summon_enablement_gate,
    lens_tray_enablement_gate,
)
from francis.lens.summon_authority import (
    lens_summon_action_execution_receipts,
    lens_summon_authority_request_readback,
)
from francis.lens.tray_authority import (
    lens_tray_authority_request_readback,
    lens_tray_presence_execution_receipts,
)
from francis.reactor import reactor_operator_visibility_summary
from francis.world_state.operator_mode import snapshot as operator_mode_snapshot
from francis.world_state.snapshot import (
    observer_incident_snapshot,
    observer_readiness,
    observer_scan_history,
    observer_summary,
)


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""


def _safe_int(value: Any, *, default: int = 0, minimum: int = 0, maximum: int = 5000) -> int:
    if isinstance(value, bool):
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, parsed))


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _runtime_loop_requirement_readback(
    runtime_loop_readiness: dict[str, Any], *, ready: bool | None = None
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for value in _as_list(runtime_loop_readiness.get("requirements")):
        requirement = _as_dict(value)
        requirement_id = _safe_str(requirement.get("id")).strip()
        if not requirement_id:
            continue
        requirement_ready = bool(requirement.get("ready"))
        if ready is not None and requirement_ready is not ready:
            continue
        items.append(
            {
                "id": requirement_id,
                "label": _safe_str(requirement.get("label")).strip(),
                "status": _safe_str(requirement.get("status")).strip() or ("ready" if requirement_ready else "blocked"),
                "route": _safe_str(requirement.get("route")).strip(),
                "ready": requirement_ready,
                "authority_required": _safe_str(requirement.get("authority_required")).strip(),
                "authority_granted": bool(requirement.get("authority_granted")),
                "blockers": [_safe_str(item).strip() for item in _as_list(requirement.get("blockers"))],
            }
        )
    return items


def _approval_item(record: dict[str, Any]) -> dict[str, Any]:
    item = dict(record) if isinstance(record, dict) else {}
    display = redact_governed_display_value(item)
    out = display if isinstance(display, dict) else {}
    out.update(approval_projection_fields(item))
    return out


def _approval_surface(*, limit: int) -> dict[str, Any]:
    try:
        pending = list_requests(status="pending", limit=5000)
    except Exception as exc:
        return {
            "status": "unavailable",
            "pending_count": 0,
            "items": [],
            "route": "/approvals/list?status=pending",
            "error": _safe_str(exc),
        }

    items = [_approval_item(item) for item in pending[:limit] if isinstance(item, dict)]
    pending_count = len(pending)
    return {
        "status": "attention" if pending_count else "clear",
        "pending_count": pending_count,
        "items": items,
        "route": "/approvals/list?status=pending",
        "decision_route": "/approvals/decision",
    }


def _operator_surface() -> dict[str, Any]:
    try:
        payload = operator_mode_snapshot()
    except Exception as exc:
        return {
            "available": False,
            "error": _safe_str(exc),
            "control_mode": {},
            "available_modes": [],
            "focus": {},
            "posture": {},
            "continuity": {},
            "backlog": {},
            "environment": {},
        }

    if not bool(payload.get("ok")):
        return {
            "available": False,
            "error": _safe_str(payload.get("error") or "operator_mode_unavailable"),
            "control_mode": {},
            "available_modes": [],
            "focus": {},
            "posture": {},
            "continuity": {},
            "backlog": {},
            "environment": {},
        }

    return {
        "available": True,
        "control_mode": _as_dict(payload.get("control_mode")),
        "available_modes": [dict(item) for item in _as_list(payload.get("available_modes")) if isinstance(item, dict)],
        "focus": _as_dict(payload.get("focus")),
        "posture": _as_dict(payload.get("posture")),
        "continuity": _as_dict(payload.get("continuity")),
        "backlog": _as_dict(payload.get("backlog")),
        "environment": _as_dict(payload.get("environment")),
    }


def _incident_surface(*, limit: int, reactor: dict[str, Any]) -> dict[str, Any]:
    try:
        snapshot = observer_incident_snapshot()
        summary = observer_summary(snapshot, focus_limit=limit)
        recent_scans = observer_scan_history(limit=3)
        readiness = observer_readiness(snapshot, recent_scans=recent_scans)
    except Exception as exc:
        summary = {
            "headline": "Observer incident readback unavailable.",
            "decision": "unknown",
            "counts": {"active": 0},
            "focus": [],
            "anomaly": {},
        }
        readiness = {"status": "unavailable", "error": _safe_str(exc)}

    reactor_attention = _as_dict(reactor.get("attention"))
    reactor_review_total = _safe_int(reactor.get("review_queue_total"))
    active_observer_count = _safe_int(_as_dict(summary.get("counts")).get("active"))
    status = "attention" if active_observer_count or reactor_review_total else "clear"

    return {
        "status": status,
        "observer_headline": _safe_str(summary.get("headline")),
        "observer_decision": _safe_str(summary.get("decision")),
        "observer_counts": _as_dict(summary.get("counts")),
        "observer_focus": [dict(item) for item in _as_list(summary.get("focus")) if isinstance(item, dict)][:limit],
        "observer_readiness": readiness,
        "reactor_review_queue_total": reactor_review_total,
        "reactor_attention": reactor_attention,
        "route": "/system/observer",
        "reactor_route": "/reactor/operator_visibility/summary",
    }


def _mission_surface(operator: dict[str, Any]) -> dict[str, Any]:
    continuity = _as_dict(operator.get("continuity"))
    counts = _as_dict(continuity.get("mission_counts"))
    focus = [dict(item) for item in _as_list(continuity.get("focus")) if isinstance(item, dict)]
    latest_receipts = [dict(item) for item in _as_list(continuity.get("memory_receipts")) if isinstance(item, dict)]
    return {
        "headline": _safe_str(continuity.get("headline")),
        "counts": counts,
        "focus": focus,
        "handoff_focus": _as_dict(continuity.get("handoff_focus")),
        "handoff_focus_source": _safe_str(continuity.get("handoff_focus_source")),
        "memory_receipt_count": len(latest_receipts),
        "latest_memory_receipts": latest_receipts,
        "route": "/continuity/briefing",
        "mission_route": "/missions/list",
    }


def _reactor_surface(*, limit: int) -> dict[str, Any]:
    try:
        return reactor_operator_visibility_summary(limit=limit)
    except Exception as exc:
        return {
            "ok": False,
            "status": "unavailable",
            "kind": "reactor.operator_visibility.summary",
            "error": _safe_str(exc),
            "attention": {},
            "readback_surfaces": {},
            "governance": {},
        }


def _badge(label: str, value: Any, *, severity: str = "neutral") -> dict[str, Any]:
    return {"label": label, "value": value, "severity": severity}


def _hud_runtime_surface() -> dict[str, Any]:
    blockers = [
        "resident_overlay_runtime_missing",
        "global_hotkey_binding_missing",
        "tray_host_missing",
        "always_on_top_window_missing",
    ]
    return {
        "status": "readback_only",
        "claim": "chat_ui_hud_readback_only",
        "surface": "chat_ui.system_orb",
        "route": "/lens/hud",
        "window_host": "chat_ui",
        "resident_overlay": False,
        "always_on_top": False,
        "global_hotkey": False,
        "tray_presence": False,
        "os_level": False,
        "blockers": blockers,
        "message": "HUD readback exists through chat UI; resident OS overlay runtime is not implemented here.",
        "governance": {
            "read_only_contract": True,
            "execution_authority": False,
            "approval_decision_authority": False,
            "memory_write": False,
            "overlay_control_authority": False,
            "summon_authority": False,
            "capture_authority": False,
            "new_sensing_authority": False,
            "mutation_authority_granted": False,
        },
    }


def _resident_host_surface(*, hud: dict[str, Any], command_palette: dict[str, Any], limit: int = 5) -> dict[str, Any]:
    launch_manifest = lens_host_launch_manifest()
    runtime_implementation_plan = lens_host_runtime_implementation_plan(manifest=launch_manifest)
    runtime_loop_contract = lens_host_runtime_loop_contract(
        manifest=launch_manifest,
        runtime_plan=runtime_implementation_plan,
    )
    runtime_loop_execution_denial = deny_lens_host_runtime_loop_execution(
        runtime_loop=runtime_loop_contract,
    )
    runtime_loop_denial_receipts = lens_host_runtime_loop_denial_receipts(limit=limit)
    runtime_loop_readiness = lens_host_runtime_loop_readiness_audit(
        limit=limit,
        manifest=launch_manifest,
        runtime_plan=runtime_implementation_plan,
        runtime_loop=runtime_loop_contract,
        execution_denial=runtime_loop_execution_denial,
        denial_receipts=runtime_loop_denial_receipts,
    )
    supervision_gate = lens_host_supervision_gate(manifest=launch_manifest)
    persistent_supervision_plan = lens_host_persistent_supervision_plan(manifest=launch_manifest)
    persistent_supervision_enablement = lens_host_persistent_supervision_enablement_preflight(manifest=launch_manifest)
    persistent_supervision_enablement_denial = deny_lens_host_persistent_supervision_enablement()
    persistent_supervision_enablement_authority_request = (
        lens_host_persistent_supervision_enablement_authority_request_contract()
    )
    persistent_supervision_enablement_authority_requests = (
        lens_host_persistent_supervision_enablement_authority_request_readback(limit=limit)
    )
    persistent_supervision_enablement_authority_grant = grant_lens_host_persistent_supervision_enablement_authority()
    persistent_supervision_enablement_authority_grants = (
        lens_host_persistent_supervision_enablement_authority_grant_receipts(limit=limit)
    )
    persistent_supervision_enablement_authority_readiness = (
        lens_host_persistent_supervision_enablement_authority_readiness_audit(limit=limit)
    )
    persistent_supervision_enablement_execution_request = (
        lens_host_persistent_supervision_enablement_execution_request_contract()
    )
    persistent_supervision_enablement_execution_requests = (
        lens_host_persistent_supervision_enablement_execution_request_readback(limit=limit)
    )
    persistent_supervision_enablement_execution_denial = deny_lens_host_persistent_supervision_enablement_execution()
    persistent_supervision_enablement_execution_receipts = (
        lens_host_persistent_supervision_enablement_execution_receipts(limit=limit)
    )
    persistent_supervision_enablement_execution_readiness = (
        lens_host_persistent_supervision_enablement_execution_readiness_audit(limit=limit)
    )
    persistent_supervision_enablement_execution_authority_grant = (
        grant_lens_host_persistent_supervision_enablement_execution_authority()
    )
    persistent_supervision_enablement_execution_authority_grants = (
        lens_host_persistent_supervision_enablement_execution_authority_grant_receipts(limit=limit)
    )
    supervision_authority_preflight = lens_host_supervision_authority_preflight(manifest=launch_manifest)
    supervision_authority_request = lens_host_supervision_authority_request_contract()
    supervision_authority_requests = lens_host_supervision_authority_request_readback(limit=limit)
    supervision_authority_denial = deny_lens_host_supervision_authority_grant()
    supervision_authority_denial_receipts = lens_host_supervision_authority_denial_receipts(limit=limit)
    supervision_authority_grant_receipts = lens_host_supervision_authority_grant_receipts(limit=limit)
    supervision_authority_readiness = lens_host_supervision_authority_readiness_audit(limit=limit)
    activation_request = lens_host_activation_request_contract()
    activation_state = lens_host_activation_readback(limit=limit)
    activation_authority_grant_receipts = lens_host_activation_authority_grant_receipts(limit=limit)
    activation_execution_preflight = lens_host_activation_execution_preflight()
    activation_execution_plan = lens_host_activation_execution_plan()
    resident_runtime_preflight = lens_resident_runtime_activation_preflight()
    resident_runtime_policy = lens_resident_runtime_execution_policy_contract()
    resident_runtime_authority_request = lens_resident_runtime_execution_authority_request_contract()
    resident_runtime_authority_requests = lens_resident_runtime_execution_authority_request_readback(limit=limit)
    resident_runtime_authority_grant = grant_lens_resident_runtime_execution_authority()
    resident_runtime_authority_grant_receipts = lens_resident_runtime_execution_authority_grant_receipts(limit=limit)
    resident_runtime_plan = lens_resident_runtime_activation_plan()
    resident_runtime_denial = deny_lens_resident_runtime_activation_execution()
    resident_runtime_denial_receipts = lens_resident_runtime_activation_denial_receipts(limit=limit)
    resident_runtime_execution_receipts = lens_resident_runtime_activation_execution_receipts(limit=limit)
    activation_execution_denial = deny_lens_host_activation_execution()
    activation_denial_receipts = lens_host_activation_denial_receipts(limit=limit)
    resident_runtime_authority_grant_denial_receipts = lens_resident_runtime_authority_grant_denial_receipts(
        limit=limit
    )
    resident_runtime_authority_grant_readiness = lens_resident_runtime_authority_grant_readiness_audit(limit=limit)
    status_runner_present = _safe_str(launch_manifest.get("status")).strip() == "status_runner_present"
    service_install = _as_dict(launch_manifest.get("service_install"))
    service_config_present = bool(service_install.get("config_exists"))
    service_readback = _as_dict(launch_manifest.get("service_readback"))
    service_plan = _as_dict(launch_manifest.get("service_plan"))
    process_readback = _as_dict(launch_manifest.get("process_readback"))
    tray_runtime_readback = _as_dict(launch_manifest.get("tray_runtime_readback"))
    hotkey_runtime_readback = _as_dict(launch_manifest.get("hotkey_runtime_readback"))
    overlay_runtime_readback = _as_dict(launch_manifest.get("overlay_runtime_readback"))
    supervisor_readback = _as_dict(launch_manifest.get("supervisor_readback"))
    supervision_readiness = _as_dict(launch_manifest.get("supervision_readiness"))
    process_alive = bool(process_readback.get("process_alive"))
    tray_runtime_ready = bool(tray_runtime_readback.get("ready"))
    hotkey_runtime_ready = bool(hotkey_runtime_readback.get("ready"))
    overlay_runtime_ready = bool(overlay_runtime_readback.get("ready"))
    service_blocked_reason = (
        _safe_str(service_plan.get("blocked_reason")).strip()
        or _safe_str(service_install.get("blocked_reason")).strip()
        or "lens_host_persistent_supervision_prerequisites_pending"
    )
    blockers = [service_blocked_reason]
    if not tray_runtime_ready:
        blockers.append("tray_host_missing")
    if not hotkey_runtime_ready:
        blockers.append("global_hotkey_binding_missing")
    if not overlay_runtime_ready:
        blockers.extend(["always_on_top_window_missing", "overlay_window_missing"])
    blockers.append("summon_binding_missing")
    if not process_alive:
        blockers.insert(1, "resident_host_process_missing")
    if not status_runner_present:
        blockers.insert(0, "lens_host_entrypoint_missing")
    if not service_config_present:
        insert_at = 1 if not status_runner_present else 0
        blockers.insert(insert_at, "lens_host_service_config_missing")
    components = [
        {
            "id": "host_status_runner",
            "label": "Host status runner",
            "status": "present" if status_runner_present else "missing",
            "required_for": ["launch_readiness_readback"],
        },
        {
            "id": "host_service_config",
            "label": "Host service config",
            "status": "present_disabled" if service_config_present else "missing",
            "required_for": ["startup_supervision"],
        },
        {
            "id": "host_service_readback",
            "label": "Host service status readback",
            "status": "readback_ready" if service_readback.get("readback_ready") else "missing",
            "required_for": ["startup_supervision"],
        },
        {
            "id": "host_service_plan",
            "label": "Host service dry-run plan",
            "status": _safe_str(service_plan.get("status")).strip() or "missing",
            "required_for": ["startup_supervision"],
        },
        {
            "id": "host_process_readback",
            "label": "Host process readback",
            "status": "readback_ready",
            "required_for": ["resident_presence", "startup_supervision"],
        },
        {
            "id": "host_process",
            "label": "Resident host process",
            "status": "foreground_observed" if process_alive else "missing",
            "required_for": ["resident_presence", "startup_supervision"],
        },
        {
            "id": "host_supervisor_readback",
            "label": "Host supervisor readback",
            "status": _safe_str(supervisor_readback.get("status")).strip() or "missing",
            "host_mode": _safe_str(supervisor_readback.get("host_mode")).strip(),
            "freshness_status": _safe_str(supervisor_readback.get("freshness_status")).strip() or "missing",
            "state_age_seconds": supervisor_readback.get("state_age_seconds"),
            "state_stale": bool(supervisor_readback.get("state_stale")),
            "required_for": ["startup_supervision", "resident_presence"],
        },
        {
            "id": "tray_presence",
            "label": "Tray or equivalent presence",
            "status": "running" if tray_runtime_ready else "missing",
            "required_for": ["operator_visibility", "lifecycle_control"],
        },
        {
            "id": "global_hotkey",
            "label": "Global summon hotkey",
            "status": "running" if hotkey_runtime_ready else "missing",
            "required_for": ["summon_anywhere"],
        },
        {
            "id": "overlay_window",
            "label": "Always-on-top Lens window",
            "status": "running" if overlay_runtime_ready else "missing",
            "required_for": ["hud_layer_runtime", "in_place_assistance"],
        },
        {
            "id": "command_palette_bridge",
            "label": "Native command palette bridge",
            "status": "missing",
            "required_for": ["os_level_command_palette"],
        },
    ]
    return {
        "ok": True,
        "kind": "lens.resident_host",
        "status": "not_implemented",
        "contract_status": "readback_ready",
        "availability": "backend_readback_only",
        "route": "/lens/host",
        "activation_request_route": _safe_str(activation_request.get("route")).strip(),
        "activation_request": activation_request,
        "activation_readback_route": _safe_str(activation_state.get("route")).strip(),
        "activation_state": activation_state,
        "activation_authority_grants_route": _safe_str(activation_authority_grant_receipts.get("route")).strip(),
        "activation_authority_grants": activation_authority_grant_receipts,
        "activation_execution_preflight_route": _safe_str(activation_execution_preflight.get("route")).strip(),
        "activation_execution_preflight": activation_execution_preflight,
        "activation_execution_plan_route": _safe_str(activation_execution_plan.get("route")).strip(),
        "activation_execution_plan": activation_execution_plan,
        "resident_runtime_preflight_route": _safe_str(resident_runtime_preflight.get("route")).strip(),
        "resident_runtime_preflight": resident_runtime_preflight,
        "resident_runtime_policy_route": _safe_str(resident_runtime_policy.get("route")).strip(),
        "resident_runtime_policy": resident_runtime_policy,
        "resident_runtime_authority_request_route": _safe_str(resident_runtime_authority_request.get("route")).strip(),
        "resident_runtime_authority_request": resident_runtime_authority_request,
        "resident_runtime_authority_requests_route": _safe_str(
            resident_runtime_authority_requests.get("route")
        ).strip(),
        "resident_runtime_authority_requests": resident_runtime_authority_requests,
        "resident_runtime_authority_grant_route": _safe_str(resident_runtime_authority_grant.get("route")).strip(),
        "resident_runtime_authority_grant": resident_runtime_authority_grant,
        "resident_runtime_authority_grant_receipts_route": _safe_str(
            resident_runtime_authority_grant_receipts.get("route")
        ).strip(),
        "resident_runtime_authority_grant_receipts": resident_runtime_authority_grant_receipts,
        "resident_runtime_authority_grant_denial_receipts_route": _safe_str(
            resident_runtime_authority_grant_denial_receipts.get("route")
        ).strip(),
        "resident_runtime_authority_grant_denial_receipts": resident_runtime_authority_grant_denial_receipts,
        "resident_runtime_authority_grant_readiness_route": _safe_str(
            resident_runtime_authority_grant_readiness.get("route")
        ).strip(),
        "resident_runtime_authority_grant_readiness": resident_runtime_authority_grant_readiness,
        "resident_runtime_plan_route": _safe_str(resident_runtime_plan.get("route")).strip(),
        "resident_runtime_plan": resident_runtime_plan,
        "resident_runtime_denial_route": _safe_str(resident_runtime_denial.get("route")).strip(),
        "resident_runtime_denial": resident_runtime_denial,
        "resident_runtime_denial_receipts_route": _safe_str(resident_runtime_denial_receipts.get("route")).strip(),
        "resident_runtime_denial_receipts": resident_runtime_denial_receipts,
        "resident_runtime_execution_receipts_route": _safe_str(
            resident_runtime_execution_receipts.get("route")
        ).strip(),
        "resident_runtime_execution_receipts": resident_runtime_execution_receipts,
        "activation_execution_denial_route": _safe_str(activation_execution_denial.get("route")).strip(),
        "activation_execution_denial": activation_execution_denial,
        "activation_denial_receipts_route": _safe_str(activation_denial_receipts.get("route")).strip(),
        "activation_denial_receipts": activation_denial_receipts,
        "launch_manifest_route": _safe_str(launch_manifest.get("route")).strip() or "/lens/host/manifest",
        "launch_manifest": launch_manifest,
        "runtime_implementation_plan_route": _safe_str(runtime_implementation_plan.get("route")).strip(),
        "runtime_implementation_plan": runtime_implementation_plan,
        "runtime_loop_contract_route": _safe_str(runtime_loop_contract.get("route")).strip(),
        "runtime_loop_contract": runtime_loop_contract,
        "runtime_loop_execution_denial_route": _safe_str(runtime_loop_execution_denial.get("route")).strip(),
        "runtime_loop_execution_denial": runtime_loop_execution_denial,
        "runtime_loop_denial_receipts_route": _safe_str(runtime_loop_denial_receipts.get("route")).strip(),
        "runtime_loop_denial_receipts": runtime_loop_denial_receipts,
        "runtime_loop_readiness_route": _safe_str(runtime_loop_readiness.get("route")).strip(),
        "runtime_loop_readiness": runtime_loop_readiness,
        "supervision_gate_route": _safe_str(supervision_gate.get("route")).strip(),
        "supervision_gate": supervision_gate,
        "persistent_supervision_plan_route": _safe_str(persistent_supervision_plan.get("route")).strip(),
        "persistent_supervision_plan": persistent_supervision_plan,
        "persistent_supervision_enablement_route": _safe_str(persistent_supervision_enablement.get("route")).strip(),
        "persistent_supervision_enablement": persistent_supervision_enablement,
        "persistent_supervision_enablement_denial_route": _safe_str(
            persistent_supervision_enablement_denial.get("route")
        ).strip(),
        "persistent_supervision_enablement_denial": persistent_supervision_enablement_denial,
        "persistent_supervision_enablement_authority_request_route": _safe_str(
            persistent_supervision_enablement_authority_request.get("route")
        ).strip(),
        "persistent_supervision_enablement_authority_request": persistent_supervision_enablement_authority_request,
        "persistent_supervision_enablement_authority_requests_route": _safe_str(
            persistent_supervision_enablement_authority_requests.get("route")
        ).strip(),
        "persistent_supervision_enablement_authority_requests": persistent_supervision_enablement_authority_requests,
        "persistent_supervision_enablement_authority_grant_route": _safe_str(
            persistent_supervision_enablement_authority_grant.get("route")
        ).strip(),
        "persistent_supervision_enablement_authority_grant": persistent_supervision_enablement_authority_grant,
        "persistent_supervision_enablement_authority_grants_route": _safe_str(
            persistent_supervision_enablement_authority_grants.get("route")
        ).strip(),
        "persistent_supervision_enablement_authority_grants": persistent_supervision_enablement_authority_grants,
        "persistent_supervision_enablement_authority_readiness_route": _safe_str(
            persistent_supervision_enablement_authority_readiness.get("route")
        ).strip(),
        "persistent_supervision_enablement_authority_readiness": (
            persistent_supervision_enablement_authority_readiness
        ),
        "persistent_supervision_enablement_execution_route": _safe_str(
            persistent_supervision_enablement_execution_request.get("boundary_route")
        ).strip(),
        "persistent_supervision_enablement_execution_request_route": _safe_str(
            persistent_supervision_enablement_execution_request.get("route")
        ).strip(),
        "persistent_supervision_enablement_execution_request": persistent_supervision_enablement_execution_request,
        "persistent_supervision_enablement_execution_requests_route": _safe_str(
            persistent_supervision_enablement_execution_requests.get("route")
        ).strip(),
        "persistent_supervision_enablement_execution_requests": persistent_supervision_enablement_execution_requests,
        "persistent_supervision_enablement_execution_denial_route": _safe_str(
            persistent_supervision_enablement_execution_denial.get("route")
        ).strip(),
        "persistent_supervision_enablement_execution_denial": persistent_supervision_enablement_execution_denial,
        "persistent_supervision_enablement_execution_apply_route": _safe_str(
            persistent_supervision_enablement_execution_denial.get("apply_route")
        ).strip(),
        "persistent_supervision_enablement_execution_receipts_route": _safe_str(
            persistent_supervision_enablement_execution_receipts.get("route")
        ).strip(),
        "persistent_supervision_enablement_execution_receipts": persistent_supervision_enablement_execution_receipts,
        "persistent_supervision_enablement_execution_readiness_route": _safe_str(
            persistent_supervision_enablement_execution_readiness.get("route")
        ).strip(),
        "persistent_supervision_enablement_execution_readiness": persistent_supervision_enablement_execution_readiness,
        "persistent_supervision_enablement_execution_authority_grant_route": _safe_str(
            persistent_supervision_enablement_execution_authority_grant.get("route")
        ).strip(),
        "persistent_supervision_enablement_execution_authority_grant": (
            persistent_supervision_enablement_execution_authority_grant
        ),
        "persistent_supervision_enablement_execution_authority_grants_route": _safe_str(
            persistent_supervision_enablement_execution_authority_grants.get("route")
        ).strip(),
        "persistent_supervision_enablement_execution_authority_grants": (
            persistent_supervision_enablement_execution_authority_grants
        ),
        "supervision_authority_request_route": _safe_str(supervision_authority_request.get("route")).strip(),
        "supervision_authority_request": supervision_authority_request,
        "supervision_authority_requests_route": _safe_str(supervision_authority_requests.get("route")).strip(),
        "supervision_authority_requests": supervision_authority_requests,
        "supervision_authority_preflight_route": _safe_str(supervision_authority_preflight.get("route")).strip(),
        "supervision_authority_preflight": supervision_authority_preflight,
        "supervision_authority_denial_route": _safe_str(supervision_authority_denial.get("route")).strip(),
        "supervision_authority_denial": supervision_authority_denial,
        "supervision_authority_denial_receipts_route": _safe_str(
            supervision_authority_denial_receipts.get("route")
        ).strip(),
        "supervision_authority_denial_receipts": supervision_authority_denial_receipts,
        "supervision_authority_grant_receipts_route": _safe_str(
            supervision_authority_grant_receipts.get("route")
        ).strip(),
        "supervision_authority_grant_receipts": supervision_authority_grant_receipts,
        "supervision_authority_readiness_route": _safe_str(supervision_authority_readiness.get("route")).strip(),
        "supervision_authority_readiness": supervision_authority_readiness,
        "status_route": "/lens/status",
        "local_hud_route": _safe_str(hud.get("route")).strip() or "/lens/hud",
        "local_palette_route": _safe_str(command_palette.get("route")).strip() or "/lens/status",
        "handoff_target": "chat_ui.system_orb",
        "status_runner_present": status_runner_present,
        "service_config_present": service_config_present,
        "service_config_path": _safe_str(service_install.get("config_path")).strip(),
        "service_readback": service_readback,
        "service_readback_ready": bool(service_readback.get("readback_ready")),
        "service_plan": service_plan,
        "service_plan_ready": bool(service_plan.get("ready")),
        "process_readback": process_readback,
        "process_readback_ready": bool(process_readback.get("readback_ready")),
        "tray_runtime_readback": tray_runtime_readback,
        "tray_runtime_readback_ready": tray_runtime_ready,
        "hotkey_runtime_readback": hotkey_runtime_readback,
        "hotkey_runtime_readback_ready": hotkey_runtime_ready,
        "overlay_runtime_readback": overlay_runtime_readback,
        "overlay_runtime_readback_ready": overlay_runtime_ready,
        "supervisor_readback": supervisor_readback,
        "supervisor_readback_ready": bool(supervisor_readback.get("readback_ready")),
        "supervisor_freshness_status": _safe_str(supervisor_readback.get("freshness_status")).strip() or "missing",
        "supervisor_state_age_seconds": supervisor_readback.get("state_age_seconds"),
        "supervisor_state_stale": bool(supervisor_readback.get("state_stale")),
        "fresh_supervisor_readback": bool(supervisor_readback.get("fresh_readback")),
        "bounded_supervisor_observed": bool(supervisor_readback.get("bounded_supervisor_observed")),
        "supervised_session_completed": bool(supervisor_readback.get("supervised_session_completed")),
        "resident_runtime_candidate_supervised": bool(supervisor_readback.get("resident_runtime_candidate_supervised")),
        "fresh_bounded_supervisor_observed": bool(supervisor_readback.get("fresh_bounded_supervisor_observed")),
        "fresh_supervised_session_completed": bool(supervisor_readback.get("fresh_supervised_session_completed")),
        "fresh_resident_runtime_candidate_supervised": bool(
            supervisor_readback.get("fresh_resident_runtime_candidate_supervised")
        ),
        "resident_supervised_runtime": False,
        "supervision_readiness": supervision_readiness,
        "foreground_session": _as_dict(launch_manifest.get("foreground_session")),
        "resident": False,
        "process_supervision": False,
        "startup_integration": False,
        "tray_presence": tray_runtime_ready,
        "global_hotkey": hotkey_runtime_ready,
        "always_on_top_overlay": overlay_runtime_ready,
        "overlay_window": overlay_runtime_ready,
        "command_palette_binding": False,
        "summon_anywhere": False,
        "components": components,
        "blockers": blockers,
        "message": "Resident Lens host is not implemented; this route preserves the launch and readiness contract only.",
        "governance": {
            "read_only_contract": True,
            "execution_authority": False,
            "approval_decision_authority": False,
            "memory_write": False,
            "overlay_control_authority": False,
            "summon_authority": False,
            "capture_authority": False,
            "new_sensing_authority": False,
            "local_process_launch_authority": False,
            "service_control_authority": False,
            "mutation_authority_granted": False,
        },
    }


def _hud_surface(
    *,
    mode: dict[str, Any],
    scope: dict[str, Any],
    approvals: dict[str, Any],
    incidents: dict[str, Any],
    missions: dict[str, Any],
    reactor: dict[str, Any],
) -> dict[str, Any]:
    pending_approvals = _safe_int(approvals.get("pending_count"))
    active_incidents = _safe_int(_as_dict(incidents.get("observer_counts")).get("active"))
    review_queue_total = _safe_int(reactor.get("review_queue_total"))
    mode_id = _safe_str(mode.get("id")).strip() or "unknown"
    focus = _as_dict(scope.get("focus"))
    headline = _safe_str(focus.get("reason")).strip()
    if not headline:
        headline = _safe_str(missions.get("headline")).strip() or "Lens has no active focus."

    badges = [
        _badge("mode", mode_id, severity="attention" if mode_id in {"pilot", "away"} else "neutral"),
        _badge("writes", _safe_str(mode.get("writes")).strip() or "unknown"),
        _badge("approvals", pending_approvals, severity="attention" if pending_approvals else "neutral"),
        _badge("incidents", active_incidents, severity="attention" if active_incidents else "neutral"),
        _badge("reactor review", review_queue_total, severity="attention" if review_queue_total else "neutral"),
    ]
    runtime = _hud_runtime_surface()

    return {
        "status": "attention" if pending_approvals or active_incidents or review_queue_total else "ready",
        "headline": headline,
        "primary_plane": _safe_str(focus.get("plane_id")).strip() or "P1_INTERFACE",
        "primary_plane_label": _safe_str(focus.get("label")).strip() or "Interface",
        "badges": badges,
        "readback_ready": True,
        "runtime_status": runtime["status"],
        "resident_overlay": runtime["resident_overlay"],
        "runtime": runtime,
        "route": "/lens/hud",
    }


def _pilot_indicator(mode: dict[str, Any]) -> dict[str, Any]:
    mode_id = _safe_str(mode.get("id")).strip().lower()
    active = mode_id == "pilot"
    return {
        "active": active,
        "status": "active" if active else "standby",
        "mode": mode_id or "unknown",
        "message": (
            "Pilot is declared and visible; existing approval gates still constrain takeover."
            if active
            else "Pilot is not active; indicator is available as read-only groundwork."
        ),
        "route": "/system/operator_mode",
    }


def _palette_command(
    command_id: str,
    label: str,
    description: str,
    group: str,
    *,
    route: str = "",
    method: str = "GET",
    surface: str = "",
    action: str = "open_surface",
    keywords: str = "",
    mutates: bool = False,
    write_guard: str = "",
    target_mode: str = "",
    receipt_kind: str = "",
    attention_count: int = 0,
) -> dict[str, Any]:
    return {
        "id": command_id,
        "label": label,
        "description": description,
        "group": group,
        "keywords": keywords,
        "status": "available",
        "action": action,
        "route": route,
        "method": method,
        "surface": surface,
        "mutates": mutates,
        "requires_confirmation": mutates,
        "write_guard": write_guard,
        "target_mode": target_mode,
        "receipt_kind": receipt_kind,
        "attention_count": attention_count,
        "execution_authority": False,
        "approval_decision_authority": False,
        "memory_write": False,
    }


def _command_palette_surface(*, approvals: dict[str, Any]) -> dict[str, Any]:
    pending_approvals = _safe_int(approvals.get("pending_count"))
    url_entrypoint = {
        "kind": "lens.command_palette.url_entrypoint",
        "status": "ready",
        "route": "/?francis_lens=command_palette",
        "accepted_query": {
            "francis_lens": "command_palette",
            "lens_palette": "open",
        },
        "local_surface": "chat_ui.command_palette",
        "opens_palette_in_chat_ui": True,
        "requires_running_chat_ui": True,
        "os_level_command_palette": False,
        "summon_anywhere": False,
        "global_hotkey": False,
        "tray_presence": False,
        "overlay_window": False,
        "execution_authority": False,
        "approval_decision_authority": False,
        "memory_write": False,
        "message": (
            "A running chat UI can open the command palette from this URL intent; "
            "global hotkey, tray, overlay, and summon-anywhere are still blocked."
        ),
    }
    commands = [
        _palette_command(
            "nav.briefing",
            "Request Continuity Briefing",
            "Open the shift briefing and return-to-work recommendations.",
            "Navigation",
            route="/continuity/briefing",
            surface="chat_ui.shift_briefing",
            keywords="briefing continuity mission return to work handoff",
        ),
        _palette_command(
            "nav.takeover",
            "Open Takeover Feed",
            "Inspect active Pilot scope, live execution, and hand-back guidance.",
            "Navigation",
            route="/operations/list",
            surface="chat_ui.takeover_feed",
            keywords="takeover pilot delegated execution interrupt hand back",
        ),
        _palette_command(
            "nav.telemetry",
            "Open Telemetry Status",
            "Inspect visible sensing posture and continuation state.",
            "Navigation",
            route="/system/operator_mode",
            surface="chat_ui.telemetry_status",
            keywords="telemetry away sensing continuation status posture",
        ),
        _palette_command(
            "nav.approvals",
            "Open Approvals",
            "Review the approval queue and make governance decisions.",
            "Navigation",
            route="/approvals/list?status=pending",
            surface="chat_ui.approvals",
            keywords="approval review queue governance",
            attention_count=pending_approvals,
        ),
        _palette_command(
            "nav.operations",
            "Open Operations",
            "Inspect queued, blocked, and running task activity.",
            "Navigation",
            route="/operations/list",
            surface="chat_ui.operations",
            keywords="operations tasks backlog execution",
        ),
        _palette_command(
            "nav.orb",
            "Open ORB",
            "Inspect the canonical flow, incidents, and runtime posture.",
            "Navigation",
            route="/system/orb",
            surface="chat_ui.orb",
            keywords="orb system incidents runtime",
        ),
        _palette_command(
            "nav.continuity-ledger",
            "Open Continuity Ledger",
            "Inspect raw local continuity receipts without treating them as synthesized memory.",
            "Navigation",
            route="/continuity/ledger",
            surface="chat_ui.continuity_ledger",
            keywords="continuity ledger receipts memory trace audit",
        ),
        _palette_command(
            "nav.plugins",
            "Open Plugins",
            "Inspect plugins, tools, and governance outcomes.",
            "Navigation",
            route="/plugins/list",
            surface="chat_ui.plugins",
            keywords="plugins tools browser",
        ),
        _palette_command(
            "nav.settings",
            "Open Settings",
            "Adjust console preferences and voice settings.",
            "Navigation",
            route="/system/config",
            surface="chat_ui.settings",
            keywords="settings preferences voice",
        ),
        _palette_command(
            "chat.new",
            "Start New Chat",
            "Open a fresh Francis conversation.",
            "Chat",
            surface="chat_ui.chat",
            action="create_local_conversation",
            keywords="new chat session",
        ),
        _palette_command(
            "mode.observe",
            "Switch to Observe",
            "Declare read-only posture with no claimed write authority.",
            "Control",
            route="/system/operator_mode",
            method="POST",
            action="declare_control_mode",
            keywords="observe readonly mode",
            mutates=True,
            write_guard="system.write plus operator posture",
            target_mode="observe",
        ),
        _palette_command(
            "mode.assist",
            "Switch to Assist",
            "Return to collaborative operator posture.",
            "Control",
            route="/system/operator_mode",
            method="POST",
            action="declare_control_mode",
            keywords="assist collaborative mode",
            mutates=True,
            write_guard="system.write plus operator posture",
            target_mode="assist",
        ),
        _palette_command(
            "mode.pilot",
            "Switch to Pilot",
            "Declare takeover posture and light the pilot indicator.",
            "Control",
            route="/system/operator_mode",
            method="POST",
            action="declare_control_mode",
            keywords="pilot takeover active indicator",
            mutates=True,
            write_guard="system.write plus operator posture",
            target_mode="pilot",
        ),
        _palette_command(
            "mode.away",
            "Switch to Away",
            "Declare away posture for continuity while you step out.",
            "Control",
            route="/system/operator_mode",
            method="POST",
            action="declare_control_mode",
            keywords="away night shift mode",
            mutates=True,
            write_guard="system.write plus operator posture",
            target_mode="away",
        ),
        _palette_command(
            "observer.scan",
            "Record Observer Scan",
            "Trigger an explicit receipted observer scan and refresh the continuity surfaces.",
            "Control",
            route="/system/observer/scan",
            method="POST",
            action="record_observer_scan",
            keywords="observer scan receipt continuity observability",
            mutates=True,
            write_guard="explicit operator action plus system.write",
            receipt_kind="observer.scan",
        ),
        _palette_command(
            "lens.host.activation.request",
            "Request Lens Host Activation",
            "Create an approval request for a bounded foreground Lens host session without launching it.",
            "Control",
            route="/lens/host/activation/request",
            method="POST",
            action="request_lens_host_activation",
            keywords="lens host foreground activation approval request",
            mutates=True,
            write_guard="system.write approval request; no launch authority",
            receipt_kind="lens.host.activation.request",
        ),
        _palette_command(
            "lens.host.supervision_authority.request",
            "Request Lens Host Supervision",
            "Create an approval request for resident host supervision authority without granting it.",
            "Control",
            route="/lens/host/supervision/authority/request",
            method="POST",
            action="request_lens_host_supervision_authority",
            keywords="lens host supervision authority approval request resident",
            mutates=True,
            write_guard="system.write approval request; no supervision authority",
            receipt_kind="lens.host.supervision_authority.request",
        ),
        _palette_command(
            "lens.resident_runtime.execution_authority.request",
            "Request Resident Runtime Authority",
            "Create an approval request for resident runtime execution authority without launching or claiming resident state.",
            "Control",
            route="/lens/resident-runtime/authority-grant/request",
            method="POST",
            action="request_lens_resident_runtime_execution_authority",
            keywords="lens resident runtime execution authority approval request grant",
            mutates=True,
            write_guard="system.write approval request; no runtime execution, service control, memory write, or resident claim",
            receipt_kind="lens.resident_runtime.execution_authority.request",
        ),
        _palette_command(
            "lens.host.persistent_supervision_enablement_authority.request",
            "Request Persistent Supervision Review",
            "Create an approval request for persistent supervision enablement authority without changing service config.",
            "Control",
            route="/lens/host/persistent-supervision/enablement/authority/request",
            method="POST",
            action="request_lens_host_persistent_supervision_enablement_authority",
            keywords="lens host persistent supervision enablement authority approval request service config",
            mutates=True,
            write_guard="system.write approval request; no service config or execution authority",
            receipt_kind="lens.host.persistent_supervision_enablement_authority.request",
        ),
        _palette_command(
            "lens.host.persistent_supervision_enablement_execution_authority.request",
            "Request Persistent Supervision Execution Review",
            "Create an approval request for persistent supervision execution authority without changing service config.",
            "Control",
            route="/lens/host/persistent-supervision/enablement/execution/request",
            method="POST",
            action="request_lens_host_persistent_supervision_enablement_execution_authority",
            keywords="lens host persistent supervision execution authority approval request service config",
            mutates=True,
            write_guard="system.write approval request; requires enablement authority; no service config mutation",
            receipt_kind="lens.host.persistent_supervision_enablement_execution_authority.request",
        ),
        _palette_command(
            "lens.host.persistent_supervision_enablement_execution_authority.grant",
            "Grant Persistent Supervision Execution",
            "Lease persistent supervision execution authority from an approved request without mutating service config.",
            "Control",
            route="/lens/host/persistent-supervision/enablement/execution/authority",
            method="POST",
            action="grant_lens_host_persistent_supervision_enablement_execution_authority",
            keywords="lens host persistent supervision execution authority grant service config receipt",
            mutates=True,
            write_guard=(
                "system.write plus exact approved execution authority request and active enablement grant; "
                "writes authority receipt only"
            ),
            receipt_kind="lens.host.persistent_supervision_enablement_execution_authority.grant.receipt",
        ),
    ]
    group_counts: dict[str, int] = {}
    for command in commands:
        group = _safe_str(command.get("group")).strip() or "Other"
        group_counts[group] = group_counts.get(group, 0) + 1

    return {
        "status": "readback_ready",
        "availability": "chat_ui_only",
        "summon_anywhere": False,
        "url_entrypoint_ready": True,
        "url_entrypoint": url_entrypoint,
        "message": (
            "Palette command readback and chat-UI URL entrypoint exist; OS-wide summon, global hotkey, "
            "tray, and overlay binding are not implemented here."
        ),
        "route": "/lens/status",
        "local_surface": "chat_ui.command_palette",
        "command_total": len(commands),
        "groups": group_counts,
        "commands": commands,
        "governance": {
            "read_only_contract": True,
            "execution_authority": False,
            "approval_decision_authority": False,
            "memory_write": False,
            "overlay_control_authority": False,
            "summon_authority": False,
            "mutation_authority_granted": False,
        },
    }


def _stage6_blockers(*values: Any, limit: int = 8) -> list[str]:
    blockers: list[str] = []
    for value in values:
        for item in _as_list(value):
            blocker = _safe_str(item).strip()
            if blocker and blocker not in blockers:
                blockers.append(blocker)
            if len(blockers) >= limit:
                return blockers
    return blockers


def _stage6_summon_handoff(
    *,
    summon_enablement_gate: dict[str, Any],
    next_smallest_truthful_gap: str,
) -> dict[str, Any]:
    first_handoff = _as_dict(summon_enablement_gate.get("first_blocker_family_handoff"))
    first_family = _safe_str(summon_enablement_gate.get("first_blocker_family")).strip()
    if first_handoff:
        family_id = first_family or _safe_str(first_handoff.get("id")).strip()
        audit_handoff = (
            {
                "next_step": "consume_resident_host_process_supervision_handoff_before_stage6_closure",
                "proof_script": (
                    "scripts/lens-summon-resident-host-blocker-proof.ps1 -Mode Status -ConsumeProcessSupervisionHandoff"
                ),
                "previous_next_smallest_truthful_gap": "resident_host_process_not_supervised",
                "next_smallest_truthful_gap": "stage6_lens_completion_audit",
                "authority_required": "process_supervision_authority",
                "authority_granted": False,
                "read_only_contract": True,
                "diagnostic_only": True,
                "would_execute": False,
                "would_mutate": False,
            }
            if family_id == "resident_host"
            else {}
        )
        family_chain_handoff = {
            "next_step": "consume_summon_anywhere_family_chain_proof_before_stage6_closure",
            "proof_script": "scripts/lens-summon-anywhere-family-chain-proof.ps1 -Mode Status",
            "previous_next_smallest_truthful_gap": "summon_anywhere_blockers",
            "next_smallest_truthful_gap": "stage6_lens_completion_audit",
            "blocked_families": [
                "resident_host",
                "tray_presence",
                "overlay_window",
                "global_hotkey_binding",
                "summon_binding",
                "authority",
            ],
            "authority_required": "resident_runtime_execution_authority",
            "authority_granted": False,
            "read_only_contract": True,
            "diagnostic_only": True,
            "would_execute": False,
            "would_mutate": False,
        }
        return {
            "next_step": "resolve_summon_anywhere_blockers_before_stage6_closure",
            "readiness_route": "/lens/summon/readiness",
            "summon_route": "/lens/summon",
            "preflight_route": "/lens/preflight",
            "status_route": "/lens/status",
            "proof_script": "scripts/lens-summon-preflight.ps1 -Mode Status",
            "first_blocker_family": family_id,
            "first_blocker_family_handoff": first_handoff,
            "first_blocker_family_next_smallest_truthful_gap": _safe_str(
                first_handoff.get("next_smallest_truthful_gap")
            ).strip(),
            "first_blocker_family_completion_audit_handoff": audit_handoff,
            "summon_anywhere_family_chain_completion_audit_handoff": family_chain_handoff,
            "authority_required": _safe_str(first_handoff.get("authority_required")).strip(),
            "authority_granted": bool(first_handoff.get("authority_granted")),
            "next_smallest_truthful_gap": next_smallest_truthful_gap,
            "read_only_contract": True,
        }
    return {
        "next_step": "resolve_os_level_command_palette_binding_before_stage6_closure",
        "readiness_route": "/lens/os-binding/readiness",
        "plan_route": "/lens/os-binding/plan",
        "authority_request_route": "/lens/os-binding/authority/request",
        "authority_requests_route": "/lens/os-binding/authority/requests",
        "authority_grant_route": "/lens/os-binding/authority",
        "authority_grants_route": "/lens/os-binding/authority/grants",
        "execute_route": "/lens/os-binding/execute",
        "denials_route": "/lens/os-binding/denials",
        "execution_readiness_route": "/lens/os-binding/execution/readiness",
        "proof_script": "scripts/lens-command-palette-os-binding-proof.ps1 -Mode Status",
        "authority_required": "os_level_command_palette_binding_authority",
        "authority_granted": False,
        "next_smallest_truthful_gap": next_smallest_truthful_gap,
        "read_only_contract": True,
    }


def _stage6_closure_criterion(
    criterion_id: str,
    *,
    label: str,
    ready: bool,
    status: str,
    evidence: list[str],
    blockers: list[str] | None = None,
    basis: str = "",
    next_smallest_truthful_gap: str = "",
    handoff: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": criterion_id,
        "label": label,
        "ready": ready,
        "status": status,
        "evidence": evidence,
        "blockers": blockers or [],
        "basis": basis,
        "next_smallest_truthful_gap": next_smallest_truthful_gap,
        "handoff": handoff or {},
    }


def _stage6_next_handoff_readback(
    *,
    closure_readback: dict[str, Any],
    resident_host: dict[str, Any],
) -> dict[str, Any]:
    blocked_criteria = [_safe_str(item).strip() for item in _as_list(closure_readback.get("blocked_criteria"))]
    criteria = [_as_dict(item) for item in _as_list(closure_readback.get("criteria"))]
    criteria_by_id = {_safe_str(item.get("id")).strip(): item for item in criteria}
    first_blocked_criterion = blocked_criteria[0] if blocked_criteria else ""
    first_criterion = criteria_by_id.get(first_blocked_criterion, {})
    criterion_handoff = _as_dict(first_criterion.get("handoff"))
    stage_next_gap = _safe_str(closure_readback.get("next_smallest_truthful_gap")).strip()
    criterion_next_gap = _safe_str(first_criterion.get("next_smallest_truthful_gap")).strip()

    next_gap = criterion_next_gap or stage_next_gap or "stage6_lens_completion_audit"
    recommended_next_slice = _safe_str(criterion_handoff.get("next_step")).strip() or next_gap
    recommended_handoff_source = "closure_readback"
    recommended_handoff = criterion_handoff
    recommended_proof_script = _safe_str(criterion_handoff.get("proof_script")).strip()
    recommended_route = (
        _safe_str(criterion_handoff.get("route")).strip() or _safe_str(criterion_handoff.get("status_route")).strip()
    )
    recommended_readiness_route = _safe_str(criterion_handoff.get("readiness_route")).strip()
    authority_required = _safe_str(criterion_handoff.get("authority_required")).strip()

    persistent_plan = _as_dict(resident_host.get("persistent_supervision_plan"))
    persistent_enablement = _as_dict(resident_host.get("persistent_supervision_enablement"))
    enablement_authority_readiness = _as_dict(
        resident_host.get("persistent_supervision_enablement_authority_readiness")
    )
    enablement_execution_readiness = _as_dict(
        resident_host.get("persistent_supervision_enablement_execution_readiness")
    )
    missing_required = [
        _safe_str(item).strip() for item in _as_list(persistent_plan.get("missing_required_before_enable"))
    ]
    enablement_missing_required = [
        _safe_str(item).strip() for item in _as_list(persistent_enablement.get("missing_required_before_enable"))
    ]
    first_missing = (
        _safe_str(persistent_plan.get("first_missing_required_before_enable")).strip()
        or _safe_str(persistent_enablement.get("first_missing_required_before_enable")).strip()
    )
    first_missing_handoff = _as_dict(persistent_plan.get("first_missing_requirement_handoff")) or _as_dict(
        persistent_enablement.get("first_missing_requirement_handoff")
    )
    activation_state = _as_dict(resident_host.get("activation_state"))
    activation_execution_handoff = _as_dict(activation_state.get("latest_execution_handoff"))
    activation_execution_handoff_ready = (
        bool(activation_state.get("latest_execution_handoff_observed"))
        and bool(activation_execution_handoff)
        and _safe_str(activation_execution_handoff.get("id")).strip() == "resident_host_process"
        and bool(activation_execution_handoff.get("read_only_contract"))
        and bool(activation_execution_handoff.get("diagnostic_only"))
        and not bool(activation_execution_handoff.get("would_execute"))
        and not bool(activation_execution_handoff.get("would_mutate"))
    )
    first_missing_handoff_ready = (
        bool(first_missing)
        and _safe_str(first_missing_handoff.get("id")).strip() == first_missing
        and bool(first_missing_handoff.get("read_only_contract"))
        and bool(first_missing_handoff.get("diagnostic_only"))
        and not bool(first_missing_handoff.get("would_execute"))
        and not bool(first_missing_handoff.get("would_mutate"))
    )
    first_missing_handoff_is_live_unsupervised_process = (
        _safe_str(first_missing_handoff.get("blocker")).strip() == "resident_host_process_not_supervised"
        and _safe_str(first_missing_handoff.get("requirement_state")).strip() == "foreground_observed_not_supervised"
    )
    enablement_authority_blockers = [
        _safe_str(item).strip() for item in _as_list(enablement_authority_readiness.get("blockers"))
    ]
    enablement_execution_blockers = [
        _safe_str(item).strip() for item in _as_list(enablement_execution_readiness.get("blockers"))
    ]
    enablement_execution_receipts = _as_dict(resident_host.get("persistent_supervision_enablement_execution_receipts"))
    enablement_execution_receipt_latest = _as_dict(enablement_execution_receipts.get("latest"))
    enablement_execution_receipt_post_plan = _as_dict(enablement_execution_receipt_latest.get("post_plan"))
    enablement_execution_receipt_status = _safe_str(enablement_execution_receipt_latest.get("status")).strip()
    enablement_execution_receipt_gap = _safe_str(
        enablement_execution_receipt_post_plan.get("next_smallest_truthful_gap")
    ).strip()
    enablement_receipt_review_observed = (
        _safe_str(enablement_execution_receipts.get("kind")).strip()
        == "lens.host.persistent_supervision_enablement_execution.receipts"
        and _safe_str(enablement_execution_receipts.get("status")).strip() == "readback_ready"
        and int(enablement_execution_receipts.get("total") or 0) > 0
        and enablement_execution_receipt_status in {"service_config_updated", "service_config_already_enabled"}
        and bool(enablement_execution_receipts.get("persistent_supervision_enablement_allowed"))
        and bool(enablement_execution_receipts.get("persistent_supervision_ready"))
        and not bool(enablement_execution_receipts.get("resident_claim_allowed"))
        and enablement_execution_receipt_gap == "persistent_supervision_execution_boundary"
    )
    enablement_receipt_review_handoff: dict[str, Any] = {}
    if enablement_receipt_review_observed:
        enablement_receipt_review_handoff = {
            "status": "receipt_reviewed",
            "previous_next_smallest_truthful_gap": "persistent_supervision_execution_boundary",
            "next_smallest_truthful_gap": "persistent_supervision_resident_claim_authority_boundary",
            "next_step": "review_persistent_supervision_resident_claim_boundary_without_runtime_start",
            "proof_script": "scripts/lens-persistent-supervision-resident-claim-boundary-proof.ps1 -Mode Status",
            "route": _safe_str(enablement_execution_receipts.get("route")).strip()
            or "/lens/host/persistent-supervision/enablement/executions",
            "readiness_route": _safe_str(enablement_execution_receipts.get("readiness_route")).strip()
            or "/lens/host/persistent-supervision/enablement/execution/readiness",
            "execution_route": _safe_str(enablement_execution_receipts.get("execution_route")).strip()
            or "/lens/host/persistent-supervision/enablement/execution",
            "latest_receipt_id": _safe_str(enablement_execution_receipt_latest.get("receipt_id")).strip()
            or _safe_str(enablement_execution_receipt_latest.get("id")).strip(),
            "latest_receipt_status": enablement_execution_receipt_status,
            "post_plan_next_smallest_truthful_gap": enablement_execution_receipt_gap,
            "authority_required": "resident_claim_authority",
            "authority_granted": False,
            "read_only_contract": True,
            "diagnostic_only": True,
            "would_execute": False,
            "would_mutate": False,
        }
    enablement_authority_handoff_observed = (
        _safe_str(enablement_authority_readiness.get("kind")).strip()
        == "lens.host.persistent_supervision_enablement_authority.readiness_audit"
        and _safe_str(enablement_authority_readiness.get("status")).strip() == "blocked"
        and bool(enablement_authority_readiness.get("boundary_observed"))
        and bool(enablement_authority_readiness.get("grant_boundary_observed"))
        and bool(enablement_authority_readiness.get("grant_receipt_readback_ready"))
        and not bool(enablement_authority_readiness.get("enablement_authority_granted"))
        and "persistent_supervision_enablement_authority_not_granted" in enablement_authority_blockers
        and _safe_str(enablement_execution_readiness.get("kind")).strip()
        == "lens.host.persistent_supervision_enablement.execution_readiness_audit"
        and _safe_str(enablement_execution_readiness.get("status")).strip() == "blocked"
        and bool(enablement_execution_readiness.get("boundary_observed"))
        and not bool(enablement_execution_readiness.get("persistent_supervision_execution_authority"))
        and "persistent_supervision_execution_authority_not_granted" in enablement_execution_blockers
        and not first_missing_handoff_is_live_unsupervised_process
    )
    enablement_authority_handoff: dict[str, Any] = {}
    if enablement_authority_handoff_observed:
        enablement_authority_handoff = {
            "id": "persistent_supervision_enablement_authority",
            "status": "blocked",
            "previous_next_smallest_truthful_gap": "persistent_supervision_authority_not_granted",
            "consumed_audit_next_smallest_truthful_gap": "persistent_supervision_enablement_denial_boundary",
            "next_smallest_truthful_gap": "persistent_supervision_enablement_authority_not_granted",
            "next_step": "prove_persistent_supervision_enablement_authority_after_candidate_handoff",
            "proof_script": "scripts/lens-persistent-supervision-enablement-authority-proof.ps1 -Mode Status",
            "route": _safe_str(enablement_authority_readiness.get("enablement_route")).strip()
            or "/lens/host/persistent-supervision/enablement",
            "request_route": _safe_str(enablement_authority_readiness.get("request_route")).strip(),
            "grant_route": _safe_str(enablement_authority_readiness.get("authority_route")).strip(),
            "grants_route": _safe_str(enablement_authority_readiness.get("grants_route")).strip(),
            "readiness_route": _safe_str(enablement_authority_readiness.get("route")).strip(),
            "execution_readiness_route": _safe_str(enablement_execution_readiness.get("route")).strip(),
            "acceptance_criterion": "system_resident_presence",
            "authority_required": "persistent_supervision_enablement_authority",
            "authority_granted": False,
            "enablement_denial_observed": bool(enablement_authority_readiness.get("boundary_observed")),
            "execution_denial_observed": bool(enablement_execution_readiness.get("boundary_observed")),
            "persistent_supervision_enablement_authority": bool(
                enablement_authority_readiness.get("enablement_authority_granted")
            ),
            "service_config_write_authority": bool(
                enablement_authority_readiness.get("service_config_write_authority")
            ),
            "persistent_supervision_execution_authority": bool(
                enablement_execution_readiness.get("persistent_supervision_execution_authority")
            ),
            "receipt_write_authority": bool(enablement_execution_readiness.get("receipt_write_authority")),
            "resident_claim_authority": bool(enablement_execution_readiness.get("resident_claim_authority")),
            "resident_claim_allowed": bool(enablement_execution_readiness.get("resident_claim_allowed")),
            "service_config_updated": bool(enablement_authority_readiness.get("service_config_updated")),
            "applied": False,
            "executed": bool(enablement_execution_readiness.get("executed")),
            "read_only_contract": True,
            "diagnostic_only": True,
            "would_execute": False,
            "would_mutate": False,
            "blockers": sorted(set(enablement_authority_blockers + enablement_execution_blockers)),
        }
    prerequisites_observed = (
        bool(missing_required)
        and bool(enablement_missing_required)
        and not bool(persistent_plan.get("required_before_enable_ready", True))
        and not bool(persistent_enablement.get("required_before_enable_ready", True))
    )
    prerequisites_handoff: dict[str, Any] = {}
    if prerequisites_observed:
        prerequisites_handoff = {
            "id": "persistent_supervision_required_prerequisites",
            "status": "blocked",
            "next_step": "resolve_persistent_supervision_required_prerequisites_before_enablement",
            "proof_script": "scripts/lens-persistent-supervision-prerequisites-proof.ps1 -Mode Status",
            "route": "/lens/host/persistent-supervision",
            "readiness_route": "/lens/host/persistent-supervision/enablement",
            "next_smallest_truthful_gap": "persistent_supervision_required_prerequisites_missing",
            "missing_required_before_enable": missing_required,
            "first_missing_required_before_enable": first_missing,
            "first_missing_requirement_handoff": first_missing_handoff,
            "blockers": missing_required,
            "acceptance_criterion": "system_resident_presence",
            "authority_required": "resident_host_process_tray_hotkey_overlay_and_summon_prerequisites",
            "authority_granted": False,
            "read_only_contract": True,
            "diagnostic_only": True,
            "would_execute": False,
            "would_mutate": False,
        }
        recommended_handoff_source = "persistent_supervision_required_prerequisites_handoff"
        recommended_handoff = prerequisites_handoff
        next_gap = "persistent_supervision_required_prerequisites_missing"
        recommended_next_slice = "resolve_persistent_supervision_required_prerequisites_before_enablement"
        recommended_proof_script = "scripts/lens-persistent-supervision-prerequisites-proof.ps1 -Mode Status"
        recommended_route = "/lens/host/persistent-supervision"
        recommended_readiness_route = "/lens/host/persistent-supervision/enablement"
        authority_required = "resident_host_process_tray_hotkey_overlay_and_summon_prerequisites"

    if first_missing_handoff_ready:
        first_missing_next_gap = _safe_str(first_missing_handoff.get("next_smallest_truthful_gap")).strip()
        first_missing_next_slice = _safe_str(first_missing_handoff.get("next_step")).strip()
        if first_missing_next_gap:
            recommended_handoff_source = "persistent_supervision_first_missing_requirement_handoff"
            recommended_handoff = first_missing_handoff
            next_gap = first_missing_next_gap
        if first_missing_next_slice:
            recommended_next_slice = first_missing_next_slice
        recommended_proof_script = (
            _safe_str(first_missing_handoff.get("proof_script")).strip() or recommended_proof_script
        )
        recommended_route = _safe_str(first_missing_handoff.get("route")).strip() or recommended_route
        recommended_readiness_route = (
            _safe_str(first_missing_handoff.get("readiness_route")).strip() or recommended_readiness_route
        )
        authority_required = _safe_str(first_missing_handoff.get("authority_required")).strip() or authority_required

    if enablement_authority_handoff_observed:
        recommended_handoff_source = "persistent_supervision_enablement_authority_denial_handoff"
        recommended_handoff = enablement_authority_handoff
        next_gap = _safe_str(enablement_authority_handoff.get("next_smallest_truthful_gap")).strip()
        recommended_next_slice = _safe_str(enablement_authority_handoff.get("next_step")).strip()
        recommended_proof_script = _safe_str(enablement_authority_handoff.get("proof_script")).strip()
        recommended_route = _safe_str(enablement_authority_handoff.get("route")).strip()
        recommended_readiness_route = _safe_str(enablement_authority_handoff.get("readiness_route")).strip()
        authority_required = _safe_str(enablement_authority_handoff.get("authority_required")).strip()

    if activation_execution_handoff_ready:
        activation_next_gap = _safe_str(activation_execution_handoff.get("next_smallest_truthful_gap")).strip()
        activation_next_slice = _safe_str(activation_execution_handoff.get("next_step")).strip()
        if activation_next_gap:
            recommended_handoff_source = "activation_execution_handoff"
            recommended_handoff = activation_execution_handoff
            next_gap = activation_next_gap
        if activation_next_slice:
            recommended_next_slice = activation_next_slice
        recommended_proof_script = (
            _safe_str(activation_execution_handoff.get("proof_script")).strip() or recommended_proof_script
        )
        recommended_route = _safe_str(activation_execution_handoff.get("route")).strip() or recommended_route
        recommended_readiness_route = (
            _safe_str(activation_execution_handoff.get("readiness_route")).strip() or recommended_readiness_route
        )
        authority_required = (
            _safe_str(activation_execution_handoff.get("authority_required")).strip() or authority_required
        )

    resident_candidate_observed = (
        bool(resident_host.get("fresh_resident_runtime_candidate_supervised"))
        and bool(resident_host.get("resident_runtime_candidate_supervised"))
        and next_gap == "resident_supervision_not_persistent"
    )
    resident_candidate_handoff: dict[str, Any] = {}
    if resident_candidate_observed:
        resident_candidate_handoff = {
            "id": "resident_runtime_candidate",
            "status": "observed_not_persistent",
            "previous_next_smallest_truthful_gap": "resident_host_process_not_supervised",
            "next_smallest_truthful_gap": "resident_supervision_not_persistent",
            "recommended_next_slice": "resolve_resident_supervision_persistence_before_persistent_supervision_enablement",
            "proof_script": "scripts/lens-resident-supervision-persistence-boundary-proof.ps1 -Mode Status",
            "route": "/lens/host",
            "readiness_route": "/lens/host/runtime-loop/readiness",
            "acceptance_criterion": "system_resident_presence",
            "authority_required": "persistent_process_supervision_authority",
            "authority_granted": False,
            "read_only_contract": True,
            "diagnostic_only": True,
            "would_execute": False,
            "would_mutate": False,
        }
        recommended_handoff_source = "resident_runtime_candidate_handoff"
        recommended_handoff = resident_candidate_handoff
        recommended_next_slice = _safe_str(resident_candidate_handoff.get("recommended_next_slice")).strip()
        recommended_proof_script = _safe_str(resident_candidate_handoff.get("proof_script")).strip()
        recommended_route = _safe_str(resident_candidate_handoff.get("route")).strip()
        recommended_readiness_route = _safe_str(resident_candidate_handoff.get("readiness_route")).strip()
        authority_required = _safe_str(resident_candidate_handoff.get("authority_required")).strip()

    if enablement_receipt_review_observed:
        recommended_handoff_source = "persistent_supervision_enablement_receipt_review_handoff"
        recommended_handoff = enablement_receipt_review_handoff
        next_gap = _safe_str(enablement_receipt_review_handoff.get("next_smallest_truthful_gap")).strip()
        recommended_next_slice = _safe_str(enablement_receipt_review_handoff.get("next_step")).strip()
        recommended_proof_script = _safe_str(enablement_receipt_review_handoff.get("proof_script")).strip()
        recommended_route = _safe_str(enablement_receipt_review_handoff.get("route")).strip()
        recommended_readiness_route = _safe_str(enablement_receipt_review_handoff.get("readiness_route")).strip()
        authority_required = _safe_str(enablement_receipt_review_handoff.get("authority_required")).strip()

    recommended_first_missing_authority_required = _safe_str(first_missing_handoff.get("authority_required")).strip()
    first_missing_handoff_next_gap = _safe_str(first_missing_handoff.get("next_smallest_truthful_gap")).strip()
    if first_missing_handoff_ready:
        if first_missing_handoff_next_gap == "resident_host_process_not_supervised":
            recommended_first_missing_authority_required = "process_supervision_authority"
        elif first_missing_handoff_next_gap == "resident_supervision_not_persistent":
            recommended_first_missing_authority_required = "persistent_process_supervision_authority"

    return {
        "kind": "lens.stage6.next_handoff.readback",
        "status": "readback_ready",
        "ready_to_close": bool(closure_readback.get("ready_to_close")),
        "stage_next_smallest_truthful_gap": stage_next_gap,
        "next_smallest_truthful_gap": next_gap,
        "recommended_next_slice": recommended_next_slice,
        "recommended_handoff_source": recommended_handoff_source,
        "recommended_proof_script": recommended_proof_script,
        "recommended_route": recommended_route,
        "recommended_readiness_route": recommended_readiness_route,
        "recommended_request_route": _safe_str(recommended_handoff.get("request_route")).strip()
        or _safe_str(recommended_handoff.get("authority_request_route")).strip(),
        "recommended_requests_route": _safe_str(recommended_handoff.get("requests_route")).strip()
        or _safe_str(recommended_handoff.get("authority_requests_route")).strip(),
        "recommended_grant_route": _safe_str(recommended_handoff.get("grant_route")).strip()
        or _safe_str(recommended_handoff.get("authority_route")).strip(),
        "recommended_grants_route": _safe_str(recommended_handoff.get("grants_route")).strip()
        or _safe_str(recommended_handoff.get("authority_grants_route")).strip(),
        "recommended_denials_route": _safe_str(recommended_handoff.get("denials_route")).strip()
        or _safe_str(recommended_handoff.get("authority_denials_route")).strip(),
        "recommended_execution_readiness_route": _safe_str(recommended_handoff.get("execution_readiness_route")).strip()
        or _safe_str(recommended_handoff.get("execution_route")).strip(),
        "authority_required": authority_required,
        "authority_granted": bool(recommended_handoff.get("authority_granted")),
        "recommended_prerequisites_handoff_source": (
            "persistent_supervision_required_prerequisites_handoff" if prerequisites_observed else ""
        ),
        "recommended_prerequisites_next_slice": _safe_str(prerequisites_handoff.get("next_step")).strip(),
        "recommended_prerequisites_proof_script": _safe_str(prerequisites_handoff.get("proof_script")).strip(),
        "recommended_prerequisites_route": _safe_str(prerequisites_handoff.get("route")).strip(),
        "recommended_prerequisites_readiness_route": _safe_str(prerequisites_handoff.get("readiness_route")).strip(),
        "recommended_prerequisites_authority_required": _safe_str(
            prerequisites_handoff.get("authority_required")
        ).strip(),
        "recommended_prerequisites_authority_granted": bool(prerequisites_handoff.get("authority_granted")),
        "recommended_first_missing_handoff_source": (
            "persistent_supervision_first_missing_requirement_handoff" if first_missing_handoff_ready else ""
        ),
        "recommended_first_missing_next_slice": _safe_str(first_missing_handoff.get("next_step")).strip(),
        "recommended_first_missing_proof_script": _safe_str(first_missing_handoff.get("proof_script")).strip(),
        "recommended_first_missing_route": _safe_str(first_missing_handoff.get("route")).strip(),
        "recommended_first_missing_readiness_route": _safe_str(first_missing_handoff.get("readiness_route")).strip(),
        "recommended_first_missing_authority_required": recommended_first_missing_authority_required,
        "recommended_first_missing_authority_granted": bool(first_missing_handoff.get("authority_granted")),
        "first_blocked_criterion": first_blocked_criterion,
        "first_blocked_criterion_next_smallest_truthful_gap": criterion_next_gap,
        "persistent_supervision_required_prerequisites_observed": prerequisites_observed,
        "persistent_supervision_missing_required_before_enable": missing_required,
        "persistent_supervision_first_missing_required_before_enable": first_missing,
        "persistent_supervision_first_missing_requirement_handoff": first_missing_handoff,
        "persistent_supervision_required_prerequisites_handoff": prerequisites_handoff,
        "activation_execution_handoff_observed": activation_execution_handoff_ready,
        "activation_execution_handoff": activation_execution_handoff if activation_execution_handoff_ready else {},
        "persistent_supervision_enablement_authority_handoff_observed": enablement_authority_handoff_observed,
        "persistent_supervision_enablement_authority_handoff": enablement_authority_handoff,
        "persistent_supervision_enablement_receipt_review_handoff_observed": enablement_receipt_review_observed,
        "persistent_supervision_enablement_receipt_review_handoff": enablement_receipt_review_handoff,
        "resident_runtime_candidate_handoff_observed": resident_candidate_observed,
        "resident_runtime_candidate_handoff": resident_candidate_handoff,
        "governance": {
            "read_only_contract": True,
            "diagnostic_only": True,
            "uses_lens_status_readback": True,
            "execution_authority": False,
            "approval_decision_authority": False,
            "local_process_launch_authority": False,
            "process_supervision_authority": False,
            "process_restart_authority": False,
            "service_install_authority": False,
            "service_control_authority": False,
            "hotkey_registration_authority": False,
            "tray_registration_authority": False,
            "overlay_control_authority": False,
            "summon_authority": False,
            "memory_write": False,
            "receipt_write_authority": False,
            "resident_claim_authority": False,
            "mutation_authority_granted": False,
        },
    }


_STAGE6_PREREQUISITE_ORDER = [
    "resident_host_process",
    "tray_presence",
    "global_hotkey_binding",
    "overlay_window",
    "summon_binding",
]

_STAGE6_PREREQUISITE_FAMILY = {
    "resident_host_process": "resident_host",
    "tray_presence": "tray_presence",
    "global_hotkey_binding": "global_hotkey_binding",
    "overlay_window": "overlay_window",
    "summon_binding": "summon_binding",
}

_STAGE6_PREREQUISITE_PROOF = {
    "resident_host_process": "scripts/lens-resident-host-runtime-boundary-proof.ps1 -Mode Status",
    "tray_presence": "scripts/lens-summon-tray-presence-blocker-proof.ps1 -Mode Status",
    "global_hotkey_binding": "scripts/lens-summon-global-hotkey-binding-blocker-proof.ps1 -Mode Status",
    "overlay_window": "scripts/lens-summon-overlay-window-blocker-proof.ps1 -Mode Status",
    "summon_binding": "scripts/lens-summon-binding-blocker-proof.ps1 -Mode Status",
}

_STAGE6_PREREQUISITE_READINESS_ROUTE = {
    "resident_host_process": "/lens/host/runtime-loop/readiness",
    "tray_presence": "/lens/tray/readiness",
    "global_hotkey_binding": "/lens/summon/readiness",
    "overlay_window": "/lens/overlay/readiness",
    "summon_binding": "/lens/summon/readiness",
}

_STAGE6_PREREQUISITE_DEFAULT_GAP = {
    "resident_host_process": "resident_host_process_not_supervised",
    "tray_presence": "summon_tray_presence_blocker_boundary",
    "global_hotkey_binding": "os_level_command_palette_binding",
    "overlay_window": "summon_overlay_window_blocker_boundary",
    "summon_binding": "summon_anywhere_blockers",
}


def _stage6_action(
    action_id: str,
    *,
    route: str,
    approval_action: str,
    requires: list[str],
    live_effect: str,
    mode: str = "",
) -> dict[str, Any]:
    return {
        "id": action_id,
        "route": route,
        "method": "POST",
        "approval_action": approval_action,
        "requires": requires,
        "mode": mode,
        "live_effect": live_effect,
        "operator_supplied_values_required": True,
        "script_would_execute": False,
        "script_would_mutate": False,
    }


def _stage6_await_action(action_id: str, *, route: str, approval_action: str) -> dict[str, Any]:
    return {
        "id": action_id,
        "route": route,
        "method": "GET",
        "approval_action": approval_action,
        "requires": ["operator approval decision"],
        "mode": "await_approval",
        "live_effect": "wait for approval decision",
        "operator_supplied_values_required": False,
        "script_would_execute": False,
        "script_would_mutate": False,
    }


def _stage6_active_approval_id(readback: dict[str, Any]) -> str:
    for key in ("active_authority_grant", "active_latest", "active_grant"):
        active = _as_dict(readback.get(key))
        approval_id = _safe_str(active.get("approval_id")).strip()
        if approval_id:
            return approval_id
    return (
        _safe_str(readback.get("active_approval_id")).strip()
        or _safe_str(readback.get("active_grant_approval_id")).strip()
    )


def _stage6_active_grant_receipt_id(readback: dict[str, Any]) -> str:
    for key in ("active_authority_grant", "active_latest", "active_grant"):
        active = _as_dict(readback.get(key))
        receipt_id = _safe_str(active.get("receipt_id")).strip()
        if receipt_id:
            return receipt_id
    return _safe_str(readback.get("active_grant_receipt_id")).strip()


def _stage6_approved_count(readback: dict[str, Any]) -> int:
    explicit = _safe_int(readback.get("approved_count"), default=-1, minimum=-1)
    if explicit >= 0:
        return explicit
    return sum(
        1 for item in _as_list(readback.get("items")) if _safe_str(_as_dict(item).get("status")).strip() == "approved"
    )


def _stage6_pending_count(readback: dict[str, Any]) -> int:
    explicit = _safe_int(readback.get("pending_count"), default=-1, minimum=-1)
    if explicit >= 0:
        return explicit
    return sum(
        1 for item in _as_list(readback.get("items")) if _safe_str(_as_dict(item).get("status")).strip() == "pending"
    )


def _stage6_latest_approved_id(readback: dict[str, Any]) -> str:
    for item in _as_list(readback.get("items")):
        candidate = _as_dict(item)
        if _safe_str(candidate.get("status")).strip() == "approved":
            approval_id = _safe_str(candidate.get("id")).strip()
            if approval_id:
                return approval_id
    latest = _as_dict(readback.get("latest"))
    if _safe_str(latest.get("status")).strip() == "approved":
        return _safe_str(latest.get("id")).strip()
    return _safe_str(readback.get("latest_approval_id")).strip()


def _stage6_authority_state(readback: dict[str, Any], authority_field: str = "") -> dict[str, Any]:
    return {
        "status": _safe_str(readback.get("status")).strip(),
        "route": _safe_str(readback.get("route")).strip(),
        "authority_route": _safe_str(readback.get("authority_route")).strip(),
        "request_route": _safe_str(readback.get("request_route")).strip(),
        "grants_route": _safe_str(readback.get("grants_route")).strip(),
        "execute_route": _safe_str(readback.get("execute_route")).strip(),
        "action": _safe_str(readback.get("action")).strip(),
        "authority_granted": bool(readback.get(authority_field))
        if authority_field
        else bool(readback.get("authority_granted")),
        "active_grant_receipt_id": _stage6_active_grant_receipt_id(readback),
        "active_approval_id": _stage6_active_approval_id(readback),
    }


def _stage6_resident_prerequisite_actions(handoff: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        _stage6_action(
            "request_resident_runtime_execution_authority",
            route=_safe_str(handoff.get("resident_runtime_authority_request_route")).strip()
            or "/lens/resident-runtime/authority-grant/request",
            approval_action="lens.resident_runtime.execution_authority",
            requires=["actor with system.write scope"],
            live_effect="approval request receipt only",
        ),
        _stage6_action(
            "grant_resident_runtime_execution_authority",
            route=_safe_str(handoff.get("resident_runtime_authority_route")).strip()
            or "/lens/resident-runtime/authority-grant",
            approval_action="lens.resident_runtime.execution_authority",
            requires=["exact approved resident runtime authority approval_id"],
            live_effect="resident runtime authority grant receipt",
        ),
        _stage6_action(
            "request_host_supervision_authority",
            route=_safe_str(handoff.get("supervision_authority_request_route")).strip()
            or "/lens/host/supervision/authority/request",
            approval_action="lens.host.supervision_authority",
            requires=["actor with system.write scope"],
            live_effect="host supervision authority request receipt only",
        ),
        _stage6_action(
            "grant_host_supervision_authority",
            route=_safe_str(handoff.get("supervision_authority_route")).strip() or "/lens/host/supervision/authority",
            approval_action="lens.host.supervision_authority",
            requires=["exact approved host supervision authority approval_id"],
            live_effect="host supervision authority grant receipt",
        ),
        _stage6_action(
            "execute_supervised_resident_host_start",
            route=_safe_str(handoff.get("resident_runtime_execute_route")).strip() or "/lens/resident-runtime/execute",
            approval_action="lens.resident_runtime.execution_authority",
            requires=[
                "resident runtime authority grant",
                "host supervision authority grant",
                "actor with system.write scope",
            ],
            mode="resident_start",
            live_effect="bounded supervised resident host lease",
        ),
    ]


def _stage6_surface_prerequisite_actions(requirement_id: str, readback: dict[str, Any]) -> list[dict[str, Any]]:
    defaults = {
        "tray_presence": (
            "lens.tray.presence_authority",
            "/lens/tray/authority/request",
            "/lens/tray/authority",
            "/lens/tray/execute",
            "start",
            "bounded tray presence lease",
        ),
        "global_hotkey_binding": (
            "lens.os_binding.command_palette_binding_authority",
            "/lens/os-binding/authority/request",
            "/lens/os-binding/authority",
            "/lens/os-binding/execute",
            "bind",
            "bounded global hotkey binding lease",
        ),
        "overlay_window": (
            "lens.overlay.window_authority",
            "/lens/overlay/authority/request",
            "/lens/overlay/authority",
            "/lens/overlay/execute",
            "start",
            "bounded overlay window lease",
        ),
        "summon_binding": (
            "lens.summon.action_authority",
            "/lens/summon/authority/request",
            "/lens/summon/authority",
            "/lens/summon/execute",
            "execute",
            "bounded summon handoff without summon-anywhere claim",
        ),
    }
    approval_action, request_route, authority_route, execute_route, execute_mode, live_effect = defaults.get(
        requirement_id,
        ("", "", "", "", "", ""),
    )
    approval_action = _safe_str(readback.get("action")).strip() or approval_action
    request_route = _safe_str(readback.get("request_route")).strip() or request_route
    authority_route = _safe_str(readback.get("authority_route")).strip() or authority_route
    execute_route = _safe_str(readback.get("execute_route")).strip() or execute_route
    return [
        _stage6_action(
            f"request_{requirement_id}_authority",
            route=request_route,
            approval_action=approval_action,
            requires=["actor with system.write scope"],
            live_effect="approval request receipt only",
        ),
        _stage6_action(
            f"grant_{requirement_id}_authority",
            route=authority_route,
            approval_action=approval_action,
            requires=[f"exact approved {approval_action} approval_id"],
            live_effect="authority grant receipt",
        ),
        _stage6_action(
            f"execute_{requirement_id}",
            route=execute_route,
            approval_action=approval_action,
            requires=["active authority grant", "actor with system.write scope"],
            mode=execute_mode,
            live_effect=live_effect,
        ),
    ]


def _stage6_next_prerequisite_action(
    requirement_id: str,
    *,
    actions: list[dict[str, Any]],
    status_readbacks: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    if requirement_id == "resident_host_process":
        resident_grants = status_readbacks["resident_runtime_authority_grant_receipts"]
        host_grants = status_readbacks["supervision_authority_grant_receipts"]
        resident_requests = status_readbacks["resident_runtime_authority_requests"]
        host_requests = status_readbacks["supervision_authority_requests"]
        if not bool(resident_grants.get("authority_granted")):
            if _stage6_approved_count(resident_requests) > 0:
                grant_action = dict(actions[1])
                grant_action["approved_approval_id"] = _stage6_latest_approved_id(resident_requests)
                return grant_action
            if _stage6_pending_count(resident_requests) > 0:
                return _stage6_await_action(
                    "await_resident_runtime_execution_authority_approval",
                    route="/lens/resident-runtime/authority-grant/requests",
                    approval_action="lens.resident_runtime.execution_authority",
                )
            return actions[0]
        if not bool(host_grants.get("authority_granted")):
            if _stage6_approved_count(host_requests) > 0:
                grant_action = dict(actions[3])
                grant_action["approved_approval_id"] = _stage6_latest_approved_id(host_requests)
                return grant_action
            if _stage6_pending_count(host_requests) > 0:
                return _stage6_await_action(
                    "await_host_supervision_authority_approval",
                    route="/lens/host/supervision/authority/requests",
                    approval_action="lens.host.supervision_authority",
                )
            return actions[2]
        execute_action = dict(actions[-1])
        execute_action["active_approval_id"] = _stage6_active_approval_id(resident_grants)
        execute_action["host_supervision_active_approval_id"] = _stage6_active_approval_id(host_grants)
        return execute_action

    readback_key = {
        "tray_presence": "tray_authority_requests",
        "global_hotkey_binding": "os_binding_authority_requests",
        "overlay_window": "overlay_authority_requests",
        "summon_binding": "summon_authority_requests",
    }.get(requirement_id, "")
    readback = status_readbacks.get(readback_key, {})
    if bool(readback.get("authority_granted")):
        execute_action = dict(actions[-1])
        execute_action["active_approval_id"] = _stage6_active_approval_id(readback)
        return execute_action
    if _stage6_approved_count(readback) > 0:
        grant_action = dict(actions[1])
        grant_action["approved_approval_id"] = _stage6_latest_approved_id(readback)
        return grant_action
    if _stage6_pending_count(readback) > 0:
        return _stage6_await_action(
            f"await_{requirement_id}_authority_approval",
            route=_safe_str(readback.get("route")).strip() or actions[0]["route"],
            approval_action=_safe_str(readback.get("action")).strip() or actions[0]["approval_action"],
        )
    return actions[0]


def _stage6_prerequisite_operator_command(action: dict[str, Any]) -> dict[str, Any]:
    action_id = _safe_str(action.get("id")).strip()
    approval_id = (
        _safe_str(action.get("approved_approval_id")).strip() or _safe_str(action.get("active_approval_id")).strip()
    )
    approval_arg = approval_id or "<approval_id>"
    if action_id.startswith("request_"):
        return {
            "command": ".\\scripts\\lens-stage6-prerequisite-bringup-plan.ps1 -Mode RequestNext -Actor <actor> -ConfirmRequest",
            "mode": "RequestNext",
            "requires_confirmation": True,
            "requires_approval_id": False,
            "requires_operator_approval_decision": False,
        }
    if action_id.startswith("grant_"):
        return {
            "command": (
                ".\\scripts\\lens-stage6-prerequisite-bringup-plan.ps1 "
                f"-Mode GrantNext -Actor <actor> -ApprovalId {approval_arg} -ConfirmGrant"
            ),
            "mode": "GrantNext",
            "requires_confirmation": True,
            "requires_approval_id": True,
            "requires_operator_approval_decision": True,
        }
    if action_id.startswith("execute_") or action_id.startswith("apply_"):
        return {
            "command": (
                ".\\scripts\\lens-stage6-prerequisite-bringup-plan.ps1 "
                f"-Mode ExecuteNext -Actor <actor> -ApprovalId {approval_arg} -RunSeconds 2 -ConfirmExecute"
            ),
            "mode": "ExecuteNext",
            "requires_confirmation": True,
            "requires_approval_id": True,
            "requires_operator_approval_decision": False,
        }
    if action_id.startswith("await_"):
        return {
            "command": ".\\scripts\\lens-stage6-prerequisite-bringup-plan.ps1 -Mode Status",
            "mode": "Status",
            "requires_confirmation": False,
            "requires_approval_id": False,
            "requires_operator_approval_decision": True,
        }
    return {
        "command": ".\\scripts\\lens-stage6-prerequisite-bringup-plan.ps1 -Mode Status",
        "mode": "Status",
        "requires_confirmation": False,
        "requires_approval_id": False,
        "requires_operator_approval_decision": False,
    }


def _stage6_operator_sequence_with_commands(
    actions: list[dict[str, Any]],
    *,
    current_action: dict[str, Any],
) -> list[dict[str, Any]]:
    sequence: list[dict[str, Any]] = []
    current_id = _safe_str(current_action.get("id")).strip()
    current_route = _safe_str(current_action.get("route")).strip()
    for action in actions:
        item = dict(action)
        available_now = (
            bool(current_id)
            and bool(current_route)
            and _safe_str(item.get("id")).strip() == current_id
            and _safe_str(item.get("route")).strip() == current_route
        )
        operator_command = _stage6_prerequisite_operator_command(item)
        operator_command["available_now"] = available_now
        operator_command["preview_only"] = not available_now
        operator_command["availability_reason"] = (
            "current_next_operator_action" if available_now else "future_step_waiting_on_prior_prerequisites"
        )
        item["operator_command"] = operator_command
        sequence.append(item)
    return sequence


def _stage6_prerequisite_step(
    requirement_id: str,
    *,
    dependency: dict[str, Any],
    first_missing_handoff: dict[str, Any],
    status_readbacks: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    is_first_missing = requirement_id == _safe_str(first_missing_handoff.get("id")).strip()
    ready = bool(dependency.get("ready"))
    if requirement_id == "resident_host_process":
        authority_state: dict[str, Any] = {
            "resident_runtime": _stage6_authority_state(
                status_readbacks["resident_runtime_authority_grant_receipts"],
                "resident_runtime_execution_authority",
            ),
            "host_supervision": _stage6_authority_state(
                status_readbacks["supervision_authority_grant_receipts"],
                "host_supervision_authority",
            ),
        }
        actions = _stage6_resident_prerequisite_actions(first_missing_handoff if is_first_missing else {})
    else:
        readback_key = {
            "tray_presence": "tray_authority_requests",
            "global_hotkey_binding": "os_binding_authority_requests",
            "overlay_window": "overlay_authority_requests",
            "summon_binding": "summon_authority_requests",
        }.get(requirement_id, "")
        readback = status_readbacks.get(readback_key, {})
        authority_state = _stage6_authority_state(readback)
        actions = _stage6_surface_prerequisite_actions(requirement_id, readback)
    return {
        "id": requirement_id,
        "family": _safe_str(dependency.get("family")).strip()
        or _STAGE6_PREREQUISITE_FAMILY.get(requirement_id, requirement_id),
        "route": _safe_str(dependency.get("route")).strip()
        or ("/lens/host" if requirement_id == "resident_host_process" else ""),
        "readiness_route": _safe_str(dependency.get("readiness_route")).strip()
        or _STAGE6_PREREQUISITE_READINESS_ROUTE.get(requirement_id, ""),
        "ready": ready,
        "status": "ready" if ready else "blocked",
        "requirement_state": _safe_str(dependency.get("requirement_state")).strip(),
        "blocker": _safe_str(dependency.get("blocker")).strip(),
        "blocked_reason": _safe_str(dependency.get("blocked_reason")).strip(),
        "proof_script": (
            _safe_str(first_missing_handoff.get("proof_script")).strip()
            if is_first_missing
            else _STAGE6_PREREQUISITE_PROOF.get(requirement_id, "")
        ),
        "next_smallest_truthful_gap": (
            _safe_str(first_missing_handoff.get("next_smallest_truthful_gap")).strip()
            if is_first_missing
            else _STAGE6_PREREQUISITE_DEFAULT_GAP.get(requirement_id, "")
        ),
        "authority_state": authority_state,
        "actions": actions,
        "next_operator_action": _stage6_next_prerequisite_action(
            requirement_id,
            actions=actions,
            status_readbacks=status_readbacks,
        ),
        "script_would_execute": False,
        "script_would_mutate": False,
    }


def _stage6_persistent_supervision_enablement_steps(handoff: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        _stage6_action(
            "request_persistent_supervision_enablement_authority",
            route=_safe_str(handoff.get("persistent_supervision_enablement_authority_request_route")).strip()
            or "/lens/host/persistent-supervision/enablement/authority/request",
            approval_action="lens.host.persistent_supervision_enablement_authority",
            requires=["all required prerequisite surfaces ready", "actor with system.write scope"],
            live_effect="persistent supervision enablement authority request receipt only",
        ),
        _stage6_action(
            "grant_persistent_supervision_enablement_authority",
            route=_safe_str(handoff.get("persistent_supervision_enablement_authority_route")).strip()
            or "/lens/host/persistent-supervision/enablement/authority",
            approval_action="lens.host.persistent_supervision_enablement_authority",
            requires=["exact approved persistent supervision enablement authority approval_id"],
            live_effect="persistent supervision enablement authority grant receipt",
        ),
        _stage6_action(
            "request_persistent_supervision_execution_authority",
            route=_safe_str(handoff.get("persistent_supervision_enablement_execution_request_route")).strip()
            or "/lens/host/persistent-supervision/enablement/execution/request",
            approval_action="lens.host.persistent_supervision_enablement_execution_authority",
            requires=["persistent supervision enablement authority grant", "actor with system.write scope"],
            live_effect="persistent supervision execution authority request receipt only",
        ),
        _stage6_action(
            "grant_persistent_supervision_execution_authority",
            route=_safe_str(handoff.get("persistent_supervision_enablement_execution_authority_route")).strip()
            or "/lens/host/persistent-supervision/enablement/execution/authority",
            approval_action="lens.host.persistent_supervision_enablement_execution_authority",
            requires=["exact approved persistent supervision execution authority approval_id"],
            live_effect="persistent supervision execution authority grant receipt",
        ),
        _stage6_action(
            "apply_persistent_supervision_enablement",
            route="/lens/host/persistent-supervision/enablement/execution/apply",
            approval_action="lens.host.persistent_supervision_enablement_execution_authority",
            requires=[
                "all prerequisite surfaces ready",
                "persistent supervision enablement authority grant",
                "persistent supervision execution authority grant",
                "actor with system.write scope",
            ],
            live_effect="persistent supervision service config update and execution receipt",
        ),
    ]


def _stage6_persistent_supervision_enablement_execution_applied(readback: dict[str, Any]) -> bool:
    latest = _as_dict(readback.get("latest"))
    latest_status = _safe_str(latest.get("status")).strip()
    return (
        latest_status in {"service_config_updated", "service_config_already_enabled"}
        and bool(readback.get("persistent_supervision_enablement_allowed"))
        and bool(readback.get("persistent_supervision_ready"))
    )


def _stage6_persistent_supervision_enablement_execution_review_action(readback: dict[str, Any]) -> dict[str, Any]:
    latest = _as_dict(readback.get("latest"))
    return {
        "id": "review_persistent_supervision_enablement_receipt",
        "route": _safe_str(readback.get("route")).strip() or "/lens/host/persistent-supervision/enablement/executions",
        "method": "GET",
        "approval_action": "lens.host.persistent_supervision_enablement_execution_authority",
        "requires": ["persistent supervision enablement execution receipt readback"],
        "mode": "readback",
        "live_effect": "persistent supervision enablement execution receipt is recorded; review resident claim boundary next",
        "operator_supplied_values_required": False,
        "script_would_execute": False,
        "script_would_mutate": False,
        "latest_receipt_id": _safe_str(latest.get("receipt_id")).strip(),
    }


def _stage6_next_persistent_supervision_enablement_action(
    *,
    actions: list[dict[str, Any]],
    status_readbacks: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    enablement_requests = status_readbacks["persistent_supervision_enablement_authority_requests"]
    enablement_grants = status_readbacks["persistent_supervision_enablement_authority_grants"]
    execution_requests = status_readbacks["persistent_supervision_enablement_execution_requests"]
    execution_grants = status_readbacks["persistent_supervision_enablement_execution_authority_grants"]
    execution_receipts = status_readbacks["persistent_supervision_enablement_execution_receipts"]

    if _stage6_persistent_supervision_enablement_execution_applied(execution_receipts):
        return _stage6_persistent_supervision_enablement_execution_review_action(execution_receipts)

    if not bool(enablement_grants.get("authority_granted")):
        if _stage6_approved_count(enablement_requests) > 0:
            grant_action = dict(actions[1])
            grant_action["approved_approval_id"] = _stage6_latest_approved_id(enablement_requests)
            return grant_action
        if _stage6_pending_count(enablement_requests) > 0:
            return _stage6_await_action(
                "await_persistent_supervision_enablement_authority_approval",
                route=_safe_str(enablement_requests.get("route")).strip()
                or "/lens/host/persistent-supervision/enablement/authority/requests",
                approval_action="lens.host.persistent_supervision_enablement_authority",
            )
        return actions[0]

    if not bool(execution_grants.get("authority_granted")):
        if _stage6_approved_count(execution_requests) > 0:
            grant_action = dict(actions[3])
            grant_action["approved_approval_id"] = _stage6_latest_approved_id(execution_requests)
            return grant_action
        if _stage6_pending_count(execution_requests) > 0:
            return _stage6_await_action(
                "await_persistent_supervision_execution_authority_approval",
                route=_safe_str(execution_requests.get("route")).strip()
                or "/lens/host/persistent-supervision/enablement/execution/requests",
                approval_action="lens.host.persistent_supervision_enablement_execution_authority",
            )
        return actions[2]

    apply_action = dict(actions[-1])
    apply_action["active_approval_id"] = _stage6_active_approval_id(execution_grants)
    apply_action["enablement_active_approval_id"] = _stage6_active_approval_id(enablement_grants)
    return apply_action


def _stage6_prerequisite_bringup_readback(
    *,
    closure_readback: dict[str, Any],
    resident_host: dict[str, Any],
    os_binding_authority_requests: dict[str, Any],
    tray_authority_requests: dict[str, Any],
    overlay_authority_requests: dict[str, Any],
    summon_authority_requests: dict[str, Any],
) -> dict[str, Any]:
    persistent_plan = _as_dict(resident_host.get("persistent_supervision_plan"))
    persistent_enablement = _as_dict(resident_host.get("persistent_supervision_enablement"))
    dependencies = [_as_dict(item) for item in _as_list(persistent_plan.get("enablement_dependency_readback"))]
    dependency_by_id = {_safe_str(item.get("id")).strip(): item for item in dependencies}
    required_before_enable = [
        _safe_str(item).strip() for item in _as_list(persistent_plan.get("required_before_enable"))
    ] or list(_STAGE6_PREREQUISITE_ORDER)
    ordered_requirement_ids = [
        requirement_id for requirement_id in _STAGE6_PREREQUISITE_ORDER if requirement_id in required_before_enable
    ]
    ordered_requirement_ids.extend(
        requirement_id
        for requirement_id in required_before_enable
        if requirement_id and requirement_id not in ordered_requirement_ids
    )
    first_missing_handoff = _as_dict(persistent_plan.get("first_missing_requirement_handoff")) or _as_dict(
        persistent_enablement.get("first_missing_requirement_handoff")
    )
    status_readbacks = {
        "resident_runtime_authority_requests": _as_dict(resident_host.get("resident_runtime_authority_requests")),
        "resident_runtime_authority_grant_receipts": _as_dict(
            resident_host.get("resident_runtime_authority_grant_receipts")
        ),
        "supervision_authority_requests": _as_dict(resident_host.get("supervision_authority_requests")),
        "supervision_authority_grant_receipts": _as_dict(resident_host.get("supervision_authority_grant_receipts")),
        "os_binding_authority_requests": os_binding_authority_requests,
        "tray_authority_requests": tray_authority_requests,
        "overlay_authority_requests": overlay_authority_requests,
        "summon_authority_requests": summon_authority_requests,
        "persistent_supervision_enablement_authority_requests": _as_dict(
            resident_host.get("persistent_supervision_enablement_authority_requests")
        ),
        "persistent_supervision_enablement_authority_grants": _as_dict(
            resident_host.get("persistent_supervision_enablement_authority_grants")
        ),
        "persistent_supervision_enablement_execution_requests": _as_dict(
            resident_host.get("persistent_supervision_enablement_execution_requests")
        ),
        "persistent_supervision_enablement_execution_authority_grants": _as_dict(
            resident_host.get("persistent_supervision_enablement_execution_authority_grants")
        ),
        "persistent_supervision_enablement_execution_receipts": _as_dict(
            resident_host.get("persistent_supervision_enablement_execution_receipts")
        ),
    }
    ordered_steps = [
        _stage6_prerequisite_step(
            requirement_id,
            dependency=dependency_by_id.get(requirement_id, {}),
            first_missing_handoff=first_missing_handoff,
            status_readbacks=status_readbacks,
        )
        for requirement_id in ordered_requirement_ids
    ]
    missing_required = [
        _safe_str(item).strip() for item in _as_list(persistent_plan.get("missing_required_before_enable"))
    ]
    enablement_steps = _stage6_persistent_supervision_enablement_steps(first_missing_handoff)
    execution_receipts = status_readbacks["persistent_supervision_enablement_execution_receipts"]
    enablement_execution_applied = _stage6_persistent_supervision_enablement_execution_applied(execution_receipts)
    effective_missing_required = [] if enablement_execution_applied else missing_required
    missing_steps = [item for item in ordered_steps if _safe_str(item.get("id")).strip() in effective_missing_required]
    applied_receipt_post_plan = _as_dict(_as_dict(execution_receipts.get("latest")).get("post_plan"))
    applied_receipt_next_gap = _safe_str(applied_receipt_post_plan.get("next_smallest_truthful_gap")).strip()
    next_operator_action = (
        _as_dict(missing_steps[0].get("next_operator_action"))
        if missing_steps
        else _stage6_next_persistent_supervision_enablement_action(
            actions=enablement_steps,
            status_readbacks=status_readbacks,
        )
    )
    current_gap = (
        "persistent_supervision_required_prerequisites_missing"
        if missing_steps
        else applied_receipt_next_gap
        if enablement_execution_applied and applied_receipt_next_gap
        else _safe_str(persistent_plan.get("next_smallest_truthful_gap")).strip()
        or "persistent_supervision_enablement_sequence_ready"
    )
    current_gap_basis = (
        "missing_required_before_enable"
        if missing_steps
        else "persistent_supervision_enablement_execution_receipt.post_plan.next_smallest_truthful_gap"
        if enablement_execution_applied and applied_receipt_next_gap
        else ("persistent_supervision_plan.next_smallest_truthful_gap")
    )
    first_missing_step = missing_steps[0] if missing_steps else {}
    first_missing_requirement = _safe_str(first_missing_step.get("id")).strip()
    first_missing_truthful_gap = _safe_str(first_missing_step.get("next_smallest_truthful_gap")).strip()
    next_operator_action_requirement = (
        first_missing_requirement
        if missing_steps
        else "persistent_supervision_enablement_receipt"
        if enablement_execution_applied
        else "persistent_supervision_enablement"
    )
    operator_sequence = _stage6_operator_sequence_with_commands(
        [_as_dict(item.get("next_operator_action")) for item in missing_steps] or [next_operator_action],
        current_action=next_operator_action,
    )
    available_now_count = sum(
        1 for item in operator_sequence if bool(_as_dict(item.get("operator_command")).get("available_now"))
    )
    preview_only_count = sum(
        1 for item in operator_sequence if bool(_as_dict(item.get("operator_command")).get("preview_only"))
    )
    command_availability_truthful = (
        bool(operator_sequence)
        and available_now_count == 1
        and available_now_count + preview_only_count == len(operator_sequence)
    )
    next_operator_command = _stage6_prerequisite_operator_command(next_operator_action)
    next_operator_action_id = _safe_str(next_operator_action.get("id")).strip()
    recommended_next_slice = (
        f"run_stage6_prerequisite_bringup_{next_operator_action_id}"
        if next_operator_action_id
        else "run_stage6_prerequisite_bringup_plan_status"
    )
    authority_required = "none_readback_only"
    if (
        bool(next_operator_command.get("requires_approval_id"))
        or bool(next_operator_command.get("requires_confirmation"))
        or bool(next_operator_action.get("operator_supplied_values_required"))
    ):
        authority_required = (
            _safe_str(next_operator_action.get("approval_action")).strip() or "operator_supplied_authority"
        )
    return {
        "ok": True,
        "kind": "lens.stage6.prerequisite_bringup.plan",
        "status": "blocked"
        if missing_steps
        else "persistent_supervision_enablement_applied"
        if enablement_execution_applied
        else "ready",
        "mode": "status",
        "stage": "Stage 6 / Lens MVP",
        "stage_state": "active" if not bool(closure_readback.get("ready_to_close")) else "ready_to_close",
        "ready_to_close": bool(closure_readback.get("ready_to_close")),
        "acceptance_criterion": "system_resident_presence",
        "closure_next_smallest_truthful_gap": _safe_str(closure_readback.get("next_smallest_truthful_gap")).strip(),
        "persistent_supervision_next_smallest_truthful_gap": _safe_str(
            persistent_plan.get("next_smallest_truthful_gap")
        ).strip(),
        "current_truthful_gap": current_gap,
        "current_truthful_gap_basis": current_gap_basis,
        "current_first_missing_requirement": first_missing_requirement,
        "current_first_missing_truthful_gap": first_missing_truthful_gap,
        "raw_persistent_supervision_next_smallest_truthful_gap": _safe_str(
            persistent_plan.get("next_smallest_truthful_gap")
        ).strip(),
        "next_smallest_truthful_gap": current_gap,
        "next_smallest_truthful_gap_basis": current_gap_basis,
        "recommended_next_slice": recommended_next_slice,
        "recommended_proof_script": "scripts/lens-stage6-prerequisite-bringup-plan.ps1 -Mode Status",
        "authority_required": authority_required,
        "authority_granted": False,
        "operator_supplied_values_required": bool(next_operator_action.get("operator_supplied_values_required")),
        "requires_confirmation": bool(next_operator_command.get("requires_confirmation")),
        "requires_approval_id": bool(next_operator_command.get("requires_approval_id")),
        "requires_operator_approval_decision": bool(next_operator_command.get("requires_operator_approval_decision")),
        "would_execute": False,
        "would_mutate": False,
        "required_before_enable": required_before_enable,
        "missing_required_before_enable": effective_missing_required,
        "required_before_enable_ready": enablement_execution_applied
        or bool(persistent_plan.get("required_before_enable_ready")),
        "first_missing_required_before_enable": ""
        if enablement_execution_applied
        else _safe_str(persistent_plan.get("first_missing_required_before_enable")).strip(),
        "first_missing_requirement_handoff": first_missing_handoff,
        "ordered_prerequisite_steps": ordered_steps,
        "persistent_supervision_enablement_steps": enablement_steps,
        "next_operator_action": next_operator_action,
        "next_operator_action_requirement": next_operator_action_requirement,
        "next_operator_command": next_operator_command,
        "operator_sequence": operator_sequence,
        "operator_sequence_command_availability": {
            "available_now_count": available_now_count,
            "preview_only_count": preview_only_count,
            "sequence_length": len(operator_sequence),
            "truthful": command_availability_truthful,
        },
        "checks": [
            {
                "id": "stage6_status_readback",
                "status": "active" if not bool(closure_readback.get("ready_to_close")) else "ready_to_close",
                "passed": not bool(closure_readback.get("ready_to_close")),
                "evidence": "/lens/status stage6_readiness",
                "reason": "The bring-up plan is only valid against the active Stage 6 Lens posture.",
            },
            {
                "id": "required_prerequisite_chain",
                "status": "ready" if bool(required_before_enable) else "missing",
                "passed": bool(required_before_enable),
                "evidence": "/lens/status resident_host.persistent_supervision_plan.required_before_enable",
                "reason": "The plan must cover every surface required before persistent supervision enablement.",
            },
            {
                "id": "first_missing_handoff_bounded",
                "status": "readback_only" if bool(first_missing_handoff) else "missing",
                "passed": (
                    not bool(first_missing_handoff)
                    or (
                        bool(first_missing_handoff.get("read_only_contract"))
                        and bool(first_missing_handoff.get("diagnostic_only"))
                        and not bool(first_missing_handoff.get("would_execute"))
                        and not bool(first_missing_handoff.get("would_mutate"))
                    )
                ),
                "evidence": "first_missing_requirement_handoff",
                "reason": "The first missing prerequisite handoff must remain read-only and non-mutating.",
            },
            {
                "id": "operator_sequence_command_availability",
                "status": "truthful" if command_availability_truthful else "inconsistent",
                "passed": command_availability_truthful,
                "evidence": "stage6_readiness.prerequisite_bringup.operator_sequence.operator_command",
                "reason": "Exactly one operator-sequence command may be available now; all future steps must remain preview-only.",
            },
            {
                "id": "status_mode_side_effects_denied",
                "status": "readback_only",
                "passed": True,
                "evidence": "stage6_readiness.prerequisite_bringup.mode=status",
                "reason": "Status projection never creates requests, grants authority, executes actions, or claims residency.",
            },
        ],
        "evidence": [
            "/lens/status",
            "/lens/status resident_host.persistent_supervision_plan",
            "/lens/status resident_host.persistent_supervision_enablement",
            "/lens/status stage6_readiness.closure_readback",
        ],
        "governance": {
            "read_only_contract": True,
            "diagnostic_only": True,
            "plan_only": True,
            "uses_lens_status_readback": True,
            "requires_explicit_operator_execution": True,
            "request_next_mode_available": True,
            "grant_next_mode_available": True,
            "execute_next_mode_available": True,
            "run_mode_available": False,
            "approval_request_write": False,
            "authority_grant_receipt_write": False,
            "execution_receipt_write": False,
            "would_request_authority": False,
            "would_grant_authority": False,
            "authority_granted": False,
            "would_execute": False,
            "would_mutate": False,
            "execution_authority": False,
            "approval_decision_authority": False,
            "local_process_launch_authority": False,
            "process_supervision_authority": False,
            "process_restart_authority": False,
            "service_install_authority": False,
            "service_control_authority": False,
            "tray_registration_authority": False,
            "hotkey_registration_authority": False,
            "overlay_control_authority": False,
            "summon_authority": False,
            "memory_write": False,
            "receipt_write_authority": False,
            "resident_claim_authority": False,
            "mutation_authority_granted": False,
        },
    }


def _stage6_closure_readback(
    *,
    mode: dict[str, Any],
    hud: dict[str, Any],
    resident_host: dict[str, Any],
    command_palette: dict[str, Any],
    pilot_indicator: dict[str, Any],
    os_binding_readiness: dict[str, Any],
    summon_enablement_gate: dict[str, Any],
    tray_enablement_gate: dict[str, Any],
    overlay_enablement_gate: dict[str, Any],
    resident_surface_activation: dict[str, Any],
) -> dict[str, Any]:
    hud_runtime = _as_dict(hud.get("runtime"))
    mode_ready = bool(_safe_str(mode.get("id")).strip() or _safe_str(mode.get("label")).strip())
    pilot_ready = bool(
        _safe_str(pilot_indicator.get("status")).strip() or _safe_str(pilot_indicator.get("route")).strip()
    )
    os_binding_ready = bool(os_binding_readiness.get("ready"))
    summon_ready = (
        bool(command_palette.get("summon_anywhere")) and bool(summon_enablement_gate.get("ready")) and os_binding_ready
    )
    helpful_ready = bool(resident_surface_activation.get("resident_surface_ready")) and bool(
        resident_surface_activation.get("operator_experience_proof")
    )
    system_resident_ready = (
        bool(resident_host.get("resident"))
        and bool(hud_runtime.get("resident_overlay"))
        and os_binding_ready
        and bool(summon_enablement_gate.get("summon_anywhere"))
        and bool(tray_enablement_gate.get("tray_presence"))
        and bool(overlay_enablement_gate.get("overlay_window"))
        and bool(resident_surface_activation.get("resident_claim_allowed"))
    )
    summon_blockers = _stage6_blockers(
        ["summon_anywhere_missing"] if not summon_ready else [],
        os_binding_readiness.get("blockers"),
        resident_host.get("blockers"),
        summon_enablement_gate.get("blockers"),
    )
    helpful_blockers = _stage6_blockers(
        resident_surface_activation.get("blockers"),
        hud_runtime.get("blockers"),
        ["operator_experience_proof_missing"]
        if not bool(resident_surface_activation.get("operator_experience_proof"))
        else [],
    )
    system_blockers = _stage6_blockers(
        resident_host.get("blockers"),
        hud_runtime.get("blockers"),
        os_binding_readiness.get("blockers"),
        summon_enablement_gate.get("blockers"),
        tray_enablement_gate.get("blockers"),
        overlay_enablement_gate.get("blockers"),
        resident_surface_activation.get("blockers"),
    )
    summon_next_gap = (
        _safe_str(summon_enablement_gate.get("next_smallest_truthful_gap")).strip()
        or _safe_str(os_binding_readiness.get("next_smallest_truthful_gap")).strip()
        or "summon_anywhere_blockers"
    )
    summon_handoff = _stage6_summon_handoff(
        summon_enablement_gate=summon_enablement_gate,
        next_smallest_truthful_gap=summon_next_gap,
    )
    helpful_next_gap = (
        _safe_str(resident_surface_activation.get("next_smallest_truthful_gap")).strip()
        or "resident_surface_operator_experience_proof"
    )
    resident_runtime_authority_grant_readiness = _as_dict(
        resident_surface_activation.get("resident_runtime_authority_grant_readiness")
    )
    resident_runtime_authority_grant_handoff = _as_dict(
        resident_surface_activation.get("resident_runtime_authority_grant_handoff")
    )
    runtime_loop_readiness = _as_dict(resident_host.get("runtime_loop_readiness"))
    supervision_authority_readiness = _as_dict(resident_host.get("supervision_authority_readiness"))
    supervision_authority_governance = _as_dict(supervision_authority_readiness.get("governance"))
    system_next_gap = _safe_str(runtime_loop_readiness.get("next_smallest_truthful_gap")).strip()
    if not system_next_gap:
        if "resident_surface_runtime_not_supervised" in system_blockers:
            system_next_gap = "supervised_resident_runtime_boundary"
        elif "resident_host_process_missing" in system_blockers:
            system_next_gap = "resident_host_supervision_boundary"
        else:
            system_next_gap = "resident_presence_authority_boundary"
    criteria = [
        _stage6_closure_criterion(
            "summon_anywhere",
            label="Summon anywhere",
            ready=summon_ready,
            status="ready" if summon_ready else "blocked",
            evidence=["/lens/os-binding/readiness", "/lens/summon", "/lens/status"],
            blockers=summon_blockers,
            basis="OS-wide summon requires a resident host plus explicit hotkey/summon authority.",
            next_smallest_truthful_gap="" if summon_ready else summon_next_gap,
            handoff={} if summon_ready else summon_handoff,
        ),
        _stage6_closure_criterion(
            "helpful_not_noisy",
            label="Helpful, not noisy",
            ready=helpful_ready,
            status="ready" if helpful_ready else "blocked",
            evidence=["/lens/resident-surface", "/lens/resident-surface/activation", "/lens/status"],
            blockers=helpful_blockers,
            basis="A calm Lens needs a supervised resident surface and live operator proof before the claim is real.",
            next_smallest_truthful_gap="" if helpful_ready else helpful_next_gap,
            handoff={}
            if helpful_ready
            else {
                "next_step": "prove_resident_surface_operator_experience_before_helpful_not_noisy_claim",
                "readiness_route": "/lens/resident-surface/activation",
                "surface_route": "/lens/resident-surface",
                "host_route": "/lens/host",
                "runtime_loop_readiness_route": "/lens/host/runtime-loop/readiness",
                "proof_script": "scripts/lens-resident-surface-proof.ps1 -Mode Status",
                "checkpoint_proof_handoff": {
                    "next_step": "consume_resident_surface_foreground_runtime_proof_before_helpful_not_noisy_claim",
                    "proof_script": "scripts/lens-stage6-checkpoint.ps1 -Mode Status",
                    "child_proof_script": "scripts/lens-resident-surface-proof.ps1 -Mode Status",
                    "previous_next_smallest_truthful_gap": "resident_surface_runtime_missing",
                    "next_smallest_truthful_gap": "resident_surface_runtime_not_supervised",
                    "authority_required": "process_supervision_authority",
                    "authority_granted": False,
                    "read_only_contract": True,
                    "diagnostic_only": True,
                    "would_execute": False,
                    "would_mutate": False,
                },
                "authority_required": "resident_runtime_execution_authority",
                "authority_granted": False,
                "resident_runtime_authority_grant_readiness_route": (
                    "/lens/resident-runtime/authority-grant/readiness"
                ),
                "resident_runtime_authority_grant_next_smallest_truthful_gap": _safe_str(
                    resident_runtime_authority_grant_readiness.get("next_smallest_truthful_gap")
                ).strip(),
                "resident_runtime_authority_grant_first_blocked_requirement": _safe_str(
                    resident_runtime_authority_grant_readiness.get("first_blocked_requirement")
                ).strip(),
                "resident_runtime_authority_grant_first_blocked_requirement_handoff": (
                    resident_runtime_authority_grant_handoff
                ),
                "resident_runtime_authority_grant_blocked_requirements": _as_list(
                    resident_runtime_authority_grant_readiness.get("blocked_requirements")
                ),
                "resident_runtime_authority_grant_requirements_total": _safe_int(
                    resident_runtime_authority_grant_readiness.get("requirements_total")
                ),
                "resident_runtime_authority_grant_requirements_ready_total": _safe_int(
                    resident_runtime_authority_grant_readiness.get("requirements_ready_total")
                ),
                "resident_runtime_authority_grant_requirements_blocked_total": _safe_int(
                    resident_runtime_authority_grant_readiness.get("requirements_blocked_total")
                ),
                "resident_runtime_authority_grant_ready": bool(resident_runtime_authority_grant_readiness.get("ready")),
                "resident_runtime_execution_authority": bool(
                    resident_runtime_authority_grant_readiness.get("resident_runtime_execution_authority")
                ),
                "resident_claim_allowed": bool(
                    resident_runtime_authority_grant_readiness.get("resident_claim_allowed")
                ),
                "next_smallest_truthful_gap": helpful_next_gap,
                "read_only_contract": True,
                "diagnostic_only": True,
                "would_execute": False,
                "would_mutate": False,
            },
        ),
        _stage6_closure_criterion(
            "mode_visibility",
            label="Mode visibility",
            ready=mode_ready,
            status="ready" if mode_ready else "missing",
            evidence=["/system/operator_mode", "/lens/status"],
            basis="Lens status exposes the current operator mode and write posture.",
        ),
        _stage6_closure_criterion(
            "pilot_visibility_groundwork",
            label="Pilot visibility groundwork",
            ready=pilot_ready,
            status="ready" if pilot_ready else "missing",
            evidence=["/system/operator_mode", "/lens/status"],
            basis="Pilot posture is visible as a read-only indicator before takeover execution exists.",
        ),
        _stage6_closure_criterion(
            "system_resident_presence",
            label="System resident presence",
            ready=system_resident_ready,
            status="ready" if system_resident_ready else "blocked",
            evidence=["/lens/host", "/lens/tray", "/lens/overlay", "/lens/resident-runtime/plan", "/lens/status"],
            blockers=system_blockers,
            basis="Resident presence requires supervised host, tray, hotkey, overlay, and resident-claim authority.",
            next_smallest_truthful_gap="" if system_resident_ready else system_next_gap,
            handoff={}
            if system_resident_ready
            else {
                "next_step": "resolve_resident_host_runtime_loop_before_system_resident_claim",
                "runtime_loop_readiness_route": "/lens/host/runtime-loop/readiness",
                "runtime_loop_route": "/lens/host/runtime-loop",
                "host_route": "/lens/host",
                "supervision_authority_readiness_route": "/lens/host/supervision/authority/readiness",
                "persistent_supervision_route": "/lens/host/persistent-supervision",
                "resident_runtime_plan_route": "/lens/resident-runtime/plan",
                "tray_route": "/lens/tray",
                "overlay_route": "/lens/overlay",
                "authority_required": "resident_runtime_execution_authority",
                "authority_granted": bool(resident_runtime_authority_grant_readiness.get("authority_granted")),
                "supervision_authority_next_smallest_truthful_gap": _safe_str(
                    supervision_authority_readiness.get("next_smallest_truthful_gap")
                ).strip(),
                "supervision_authority_first_blocked_requirement": _safe_str(
                    supervision_authority_readiness.get("first_blocked_requirement")
                ).strip(),
                "supervision_authority_first_blocked_requirement_handoff": _as_dict(
                    supervision_authority_readiness.get("first_blocked_requirement_handoff")
                ),
                "supervision_authority_blocked_requirements": _as_list(
                    supervision_authority_readiness.get("blocked_requirements")
                ),
                "supervision_authority_requirements_total": _safe_int(
                    supervision_authority_readiness.get("requirements_total")
                ),
                "supervision_authority_requirements_ready_total": _safe_int(
                    supervision_authority_readiness.get("requirements_ready_total")
                ),
                "supervision_authority_requirements_blocked_total": _safe_int(
                    supervision_authority_readiness.get("requirements_blocked_total")
                ),
                "supervision_authority_ready": bool(supervision_authority_readiness.get("ready")),
                "supervision_authority_granted": bool(supervision_authority_readiness.get("authority_ready")),
                "process_supervision_authority": bool(
                    supervision_authority_governance.get("process_supervision_authority")
                ),
                "service_control_authority": bool(supervision_authority_governance.get("service_control_authority")),
                "resident_claim_authority": bool(supervision_authority_governance.get("resident_claim_authority")),
                "next_smallest_truthful_gap": system_next_gap,
                "read_only_contract": True,
                "diagnostic_only": True,
                "would_execute": False,
                "would_mutate": False,
            },
        ),
    ]
    ready_criteria = [item for item in criteria if bool(item.get("ready"))]
    blocked_criteria = [item for item in criteria if not bool(item.get("ready"))]
    next_gap = "stage6_lens_completion_audit"
    blocked_ids = {_safe_str(item.get("id")).strip() for item in blocked_criteria}
    if "summon_anywhere" in blocked_ids:
        next_gap = summon_next_gap
    elif "helpful_not_noisy" in blocked_ids:
        next_gap = helpful_next_gap
    elif "system_resident_presence" in blocked_ids:
        next_gap = system_next_gap
    return {
        "kind": "lens.stage6.closure_readback",
        "status": "ready_to_close" if not blocked_criteria else "blocked",
        "ready_to_close": not blocked_criteria,
        "criteria_total": len(criteria),
        "ready_total": len(ready_criteria),
        "blocked_total": len(blocked_criteria),
        "ready_criteria": [_safe_str(item.get("id")).strip() for item in ready_criteria],
        "blocked_criteria": [_safe_str(item.get("id")).strip() for item in blocked_criteria],
        "next_smallest_truthful_gap": next_gap,
        "criteria": criteria,
        "governance": {
            "read_only_contract": True,
            "execution_authority": False,
            "approval_decision_authority": False,
            "memory_write": False,
            "overlay_control_authority": False,
            "summon_authority": False,
            "resident_claim_authority": False,
            "mutation_authority_granted": False,
        },
    }


def _stage6_readiness(
    *,
    mode: dict[str, Any],
    hud: dict[str, Any],
    resident_host: dict[str, Any],
    approvals: dict[str, Any],
    incidents: dict[str, Any],
    missions: dict[str, Any],
    reactor: dict[str, Any],
    command_palette: dict[str, Any],
    preflight: dict[str, Any],
    os_binding_readiness: dict[str, Any],
    os_binding_execution_readiness: dict[str, Any],
    os_binding_authority_requests: dict[str, Any],
    summon_enablement_gate: dict[str, Any],
    summon_authority_requests: dict[str, Any],
    tray_enablement_gate: dict[str, Any],
    tray_authority_requests: dict[str, Any],
    overlay_enablement_gate: dict[str, Any],
    overlay_authority_requests: dict[str, Any],
    resident_surface_activation: dict[str, Any],
    pilot_indicator: dict[str, Any],
) -> dict[str, Any]:
    hud_runtime = _as_dict(hud.get("runtime"))
    preflight_surfaces = _as_dict(preflight.get("surfaces"))
    summon_preflight = _as_dict(preflight_surfaces.get("summon"))
    tray_preflight = _as_dict(preflight_surfaces.get("tray"))
    overlay_preflight = _as_dict(preflight_surfaces.get("overlay"))
    resident_runtime_preflight = _as_dict(resident_host.get("resident_runtime_preflight"))
    resident_runtime_policy = _as_dict(resident_host.get("resident_runtime_policy"))
    resident_runtime_authority_requests = _as_dict(resident_host.get("resident_runtime_authority_requests"))
    resident_runtime_authority_grant = _as_dict(resident_host.get("resident_runtime_authority_grant"))
    resident_runtime_authority_grant_receipts = _as_dict(resident_host.get("resident_runtime_authority_grant_receipts"))
    resident_runtime_authority_grant_denial_receipts = _as_dict(
        resident_host.get("resident_runtime_authority_grant_denial_receipts")
    )
    resident_runtime_authority_grant_readiness = _as_dict(
        resident_host.get("resident_runtime_authority_grant_readiness")
    )
    resident_runtime_denial_receipts = _as_dict(resident_host.get("resident_runtime_denial_receipts"))
    resident_runtime_execution_receipts = _as_dict(resident_host.get("resident_runtime_execution_receipts"))
    runtime_loop_denial_receipts = _as_dict(resident_host.get("runtime_loop_denial_receipts"))
    runtime_loop_readiness = _as_dict(resident_host.get("runtime_loop_readiness"))
    runtime_loop_requirement_readback = _runtime_loop_requirement_readback(runtime_loop_readiness)
    runtime_loop_blocked_requirement_readback = _runtime_loop_requirement_readback(runtime_loop_readiness, ready=False)
    first_runtime_loop_blocked_requirement = (
        _safe_str(runtime_loop_blocked_requirement_readback[0].get("id")).strip()
        if runtime_loop_blocked_requirement_readback
        else ""
    )
    persistent_supervision_enablement_authority_readiness = _as_dict(
        resident_host.get("persistent_supervision_enablement_authority_readiness")
    )
    persistent_supervision_enablement_authority_grants = _as_dict(
        resident_host.get("persistent_supervision_enablement_authority_grants")
    )
    persistent_supervision_enablement_execution_readiness = _as_dict(
        resident_host.get("persistent_supervision_enablement_execution_readiness")
    )
    persistent_supervision_enablement_execution_authority_grants = _as_dict(
        resident_host.get("persistent_supervision_enablement_execution_authority_grants")
    )
    persistent_supervision_enablement_execution_receipts = _as_dict(
        resident_host.get("persistent_supervision_enablement_execution_receipts")
    )
    persistent_supervision_enablement_execution_denial = _as_dict(
        resident_host.get("persistent_supervision_enablement_execution_denial")
    )
    supervision_authority_denial = _as_dict(resident_host.get("supervision_authority_denial"))
    supervision_authority_denial_receipts = _as_dict(resident_host.get("supervision_authority_denial_receipts"))
    supervision_authority_grant_receipts = _as_dict(resident_host.get("supervision_authority_grant_receipts"))
    supervision_authority_preflight = _as_dict(resident_host.get("supervision_authority_preflight"))
    supervision_authority_readiness = _as_dict(resident_host.get("supervision_authority_readiness"))
    os_binding_authority_summary = _as_dict(os_binding_readiness.get("authority_request_readback"))

    def _os_binding_authority_value(key: str) -> Any:
        if key in os_binding_authority_summary:
            return os_binding_authority_summary.get(key)
        return os_binding_authority_requests.get(key)

    os_binding_authority_latest_approval_id = (
        _safe_str(os_binding_authority_summary.get("latest_approval_id")).strip()
        or _safe_str(_as_dict(os_binding_authority_requests.get("latest")).get("id")).strip()
        or _safe_str(os_binding_authority_requests.get("latest_approval_id")).strip()
    )
    os_binding_execution_denial = _as_dict(os_binding_execution_readiness.get("execution_denial"))
    closure_readback = _stage6_closure_readback(
        mode=mode,
        hud=hud,
        resident_host=resident_host,
        command_palette=command_palette,
        pilot_indicator=pilot_indicator,
        os_binding_readiness=os_binding_readiness,
        summon_enablement_gate=summon_enablement_gate,
        tray_enablement_gate=tray_enablement_gate,
        overlay_enablement_gate=overlay_enablement_gate,
        resident_surface_activation=resident_surface_activation,
    )
    ready_to_close = bool(closure_readback.get("ready_to_close"))
    next_handoff = _stage6_next_handoff_readback(closure_readback=closure_readback, resident_host=resident_host)
    prerequisite_bringup = _stage6_prerequisite_bringup_readback(
        closure_readback=closure_readback,
        resident_host=resident_host,
        os_binding_authority_requests=os_binding_authority_requests,
        tray_authority_requests=tray_authority_requests,
        overlay_authority_requests=overlay_authority_requests,
        summon_authority_requests=summon_authority_requests,
    )
    return {
        "stage": "Stage 6 / Lens MVP",
        "stage_state": "ready_to_close" if ready_to_close else "active",
        "status": _safe_str(closure_readback.get("status")).strip() or "blocked",
        "ready_to_close": ready_to_close,
        "criteria_total": _safe_int(closure_readback.get("criteria_total")),
        "ready_total": _safe_int(closure_readback.get("ready_total")),
        "blocked_total": _safe_int(closure_readback.get("blocked_total")),
        "ready_criteria": _as_list(closure_readback.get("ready_criteria")),
        "blocked_criteria": _as_list(closure_readback.get("blocked_criteria")),
        "next_smallest_truthful_gap": _safe_str(closure_readback.get("next_smallest_truthful_gap")).strip()
        or "stage6_lens_completion_audit",
        "claim": "backend_readback_contract_only",
        "next_handoff": next_handoff,
        "prerequisite_bringup": prerequisite_bringup,
        "closure_readback": closure_readback,
        "criteria": [
            {
                "id": "resident_host_runtime",
                "status": "not_implemented",
                "evidence": ["/lens/host", "/lens/status"],
                "resident": bool(resident_host.get("resident")),
                "blockers": _as_list(resident_host.get("blockers")),
            },
            {
                "id": "hud_layer_runtime",
                "status": "readback_only",
                "evidence": ["/lens/hud", "/lens/status"],
                "resident_overlay": bool(hud_runtime.get("resident_overlay")),
                "blockers": _as_list(hud_runtime.get("blockers")),
            },
            {
                "id": "command_palette_commands",
                "status": "readback_ready" if _as_list(command_palette.get("commands")) else "missing",
                "evidence": ["/lens/status"],
                "command_count": _safe_int(command_palette.get("command_total")),
                "url_entrypoint_ready": bool(command_palette.get("url_entrypoint_ready")),
                "url_entrypoint": _as_dict(command_palette.get("url_entrypoint")),
            },
            {
                "id": "os_binding_readiness",
                "status": _safe_str(os_binding_readiness.get("status")).strip() or "missing",
                "audit_status": _safe_str(os_binding_readiness.get("audit_status")).strip(),
                "evidence": [
                    "/lens/os-binding/readiness",
                    "/lens/os-binding/execution/readiness",
                    "/lens/os-binding/authority/requests",
                    "/lens/os-binding/authority/request",
                    "/lens/os-binding/denials",
                    "/lens/summon",
                    "/lens/status",
                ],
                "ready": bool(os_binding_readiness.get("ready")),
                "os_binding_ready": bool(os_binding_readiness.get("os_binding_ready")),
                "os_level_command_palette": bool(os_binding_readiness.get("os_level_command_palette")),
                "summon_anywhere": bool(os_binding_readiness.get("summon_anywhere")),
                "execution_readiness_status": _safe_str(os_binding_execution_readiness.get("status")).strip()
                or "missing",
                "execution_readiness_ready": bool(os_binding_execution_readiness.get("ready")),
                "execution_boundary_observed": bool(os_binding_execution_readiness.get("denial_boundary_observed")),
                "execution_denial_status": _safe_str(os_binding_execution_readiness.get("denial_status")).strip(),
                "execution_denial_receipt_readback_ready": bool(
                    os_binding_execution_readiness.get("denial_receipt_readback_ready")
                ),
                "execution_denial_receipt_total": _safe_int(os_binding_execution_readiness.get("denial_receipt_total")),
                "latest_execution_denial_receipt_id": _safe_str(
                    os_binding_execution_readiness.get("latest_denial_receipt_id")
                ).strip(),
                "execution_blocked_requirements": _as_list(os_binding_execution_readiness.get("blocked_requirements")),
                "execution_next_smallest_truthful_gap": _safe_str(
                    os_binding_execution_readiness.get("next_smallest_truthful_gap")
                ).strip()
                or "os_binding_command_palette_execution_boundary",
                "execution_denial": os_binding_execution_denial,
                "authority_request_readback_status": _safe_str(_os_binding_authority_value("status")).strip()
                or "missing",
                "authority_request_readback_ready": bool(_os_binding_authority_value("readback_ready")),
                "authority_route": _safe_str(os_binding_authority_requests.get("authority_route")).strip()
                or "/lens/os-binding/authority",
                "authority_request_route": _safe_str(os_binding_authority_requests.get("request_route")).strip()
                or "/lens/os-binding/authority/request",
                "authority_requests_route": _safe_str(os_binding_authority_requests.get("route")).strip()
                or "/lens/os-binding/authority/requests",
                "authority_grants_route": _safe_str(os_binding_authority_requests.get("grants_route")).strip()
                or "/lens/os-binding/authority/grants",
                "active_grant_receipt_id": _safe_str(_os_binding_authority_value("active_grant_receipt_id")).strip(),
                "authority_grant_consumed": bool(os_binding_readiness.get("authority_grant_consumed")),
                "authority_request_pending_count": _safe_int(_os_binding_authority_value("pending_count")),
                "authority_request_approved_count": _safe_int(_os_binding_authority_value("approved_count")),
                "authority_request_rejected_count": _safe_int(_os_binding_authority_value("rejected_count")),
                "authority_request_emergency_count": _safe_int(_os_binding_authority_value("emergency_count")),
                "authority_request_total_count": _safe_int(_os_binding_authority_value("total_count")),
                "authority_request_latest_approval_id": os_binding_authority_latest_approval_id,
                "authority_granted": bool(_os_binding_authority_value("authority_granted")),
                "os_level_command_palette_binding_authority": bool(
                    _os_binding_authority_value("os_level_command_palette_binding_authority")
                ),
                "first_blocker_family": _safe_str(os_binding_readiness.get("first_blocker_family")).strip(),
                "next_smallest_truthful_gap": _safe_str(os_binding_readiness.get("next_smallest_truthful_gap")).strip()
                or "os_level_command_palette_binding",
                "requirements_total": _safe_int(os_binding_readiness.get("requirements_total")),
                "requirements_ready_total": _safe_int(os_binding_readiness.get("requirements_ready_total")),
                "requirements_blocked_total": _safe_int(os_binding_readiness.get("requirements_blocked_total")),
                "blocked_requirements": _as_list(os_binding_readiness.get("blocked_requirements")),
                "blockers": _as_list(os_binding_readiness.get("blockers")),
                "blocker_groups": _as_dict(os_binding_readiness.get("blocker_groups")),
                "execution_authority": False,
                "approval_decision_authority": False,
                "local_process_launch_authority": False,
                "process_supervision_authority": False,
                "service_control_authority": False,
                "hotkey_registration_authority": False,
                "tray_registration_authority": False,
                "overlay_control_authority": False,
                "summon_authority": False,
                "memory_write": False,
                "resident_claim_authority": False,
            },
            {
                "id": "mode_visibility",
                "status": "readback_ready" if mode else "missing",
                "evidence": ["/system/operator_mode", "/lens/status"],
            },
            {
                "id": "approvals_view",
                "status": "readback_ready",
                "evidence": ["/approvals/list?status=pending", "/lens/status"],
                "pending_count": _safe_int(approvals.get("pending_count")),
            },
            {
                "id": "incident_view",
                "status": "readback_ready",
                "evidence": ["/system/observer", "/reactor/operator_visibility/summary", "/lens/status"],
                "observer_active_count": _safe_int(_as_dict(incidents.get("observer_counts")).get("active")),
                "reactor_review_queue_total": _safe_int(reactor.get("review_queue_total")),
            },
            {
                "id": "mission_feed",
                "status": "readback_ready",
                "evidence": ["/continuity/briefing", "/missions/list", "/lens/status"],
                "mission_counts": _as_dict(missions.get("counts")),
            },
            {
                "id": "receipt_visibility",
                "status": "readback_ready",
                "evidence": ["/continuity/ledger", "/reactor/operator_visibility/summary", "/lens/status"],
                "reactor_readback_surfaces": _as_dict(reactor.get("readback_surfaces")),
            },
            {
                "id": "host_activation_request_boundary",
                "status": "approval_request_ready"
                if _as_dict(resident_host.get("activation_request")).get("creates_approval_request")
                else "missing",
                "evidence": ["/lens/host/activation/request", "/approvals/list?status=pending", "/lens/status"],
                "execution_authority": False,
                "approval_decision_authority": False,
                "local_process_launch_authority": False,
            },
            {
                "id": "host_activation_approval_readback",
                "status": _safe_str(_as_dict(resident_host.get("activation_state")).get("status")).strip() or "missing",
                "evidence": ["/lens/host/activation", "/approvals/list?status=pending", "/lens/status"],
                "pending_count": _safe_int(_as_dict(resident_host.get("activation_state")).get("pending_count")),
                "approved_count": _safe_int(_as_dict(resident_host.get("activation_state")).get("approved_count")),
                "execution_authority": False,
                "approval_decision_authority": False,
                "local_process_launch_authority": False,
            },
            {
                "id": "host_activation_execution_preflight",
                "status": _safe_str(_as_dict(resident_host.get("activation_execution_preflight")).get("status")).strip()
                or "missing",
                "evidence": ["/lens/host/activation/preflight", "/lens/host/activation", "/lens/status"],
                "ready": bool(_as_dict(resident_host.get("activation_execution_preflight")).get("ready")),
                "blockers": _as_list(_as_dict(resident_host.get("activation_execution_preflight")).get("blockers")),
                "execution_authority": False,
                "approval_decision_authority": False,
                "local_process_launch_authority": False,
            },
            {
                "id": "host_activation_execution_plan",
                "status": _safe_str(_as_dict(resident_host.get("activation_execution_plan")).get("status")).strip()
                or "missing",
                "evidence": ["/lens/host/activation/plan", "/lens/host/activation/preflight", "/lens/status"],
                "plan_available": bool(_as_dict(resident_host.get("activation_execution_plan")).get("plan_available")),
                "execution_ready": bool(
                    _as_dict(resident_host.get("activation_execution_plan")).get("execution_ready")
                ),
                "blockers": _as_list(_as_dict(resident_host.get("activation_execution_plan")).get("blockers")),
                "execution_authority": False,
                "approval_decision_authority": False,
                "local_process_launch_authority": False,
            },
            {
                "id": "host_activation_execution_denial_boundary",
                "status": _safe_str(_as_dict(resident_host.get("activation_execution_denial")).get("status")).strip()
                or "missing",
                "evidence": ["/lens/host/activation/execute", "/lens/host/activation/plan", "/lens/status"],
                "applied": bool(_as_dict(resident_host.get("activation_execution_denial")).get("applied")),
                "executed": bool(_as_dict(resident_host.get("activation_execution_denial")).get("executed")),
                "blockers": _as_list(_as_dict(resident_host.get("activation_execution_denial")).get("blockers")),
                "execution_authority": False,
                "approval_decision_authority": False,
                "local_process_launch_authority": False,
                "receipt_write_authority": False,
            },
            {
                "id": "host_activation_denial_receipt_readback",
                "status": _safe_str(_as_dict(resident_host.get("activation_denial_receipts")).get("status")).strip()
                or "missing",
                "evidence": ["/lens/host/activation/denials", "/lens/host/activation/execute", "/lens/status"],
                "receipt_count": _safe_int(_as_dict(resident_host.get("activation_denial_receipts")).get("total")),
                "latest_receipt_id": _safe_str(
                    _as_dict(_as_dict(resident_host.get("activation_denial_receipts")).get("latest")).get("receipt_id")
                ).strip(),
                "execution_authority": False,
                "approval_decision_authority": False,
                "local_process_launch_authority": False,
                "memory_write": False,
            },
            {
                "id": "resident_surface_activation_boundary",
                "status": "blocked_readback_ready"
                if bool(resident_surface_activation.get("boundary_ready"))
                else "missing",
                "evidence": [
                    "/lens/resident-surface/activation",
                    "/lens/resident-runtime/preflight",
                    "/lens/resident-runtime/policy",
                    "/lens/resident-runtime/authority-grant",
                    "/lens/resident-runtime/plan",
                    "/lens/host/activation/plan",
                    "/lens/preflight",
                    "/lens/status",
                ],
                "activation_ready": bool(resident_surface_activation.get("activation_ready")),
                "resident_surface_ready": bool(resident_surface_activation.get("resident_surface_ready")),
                "resident_claim_allowed": bool(resident_surface_activation.get("resident_claim_allowed")),
                "execution_authority": False,
                "approval_decision_authority": False,
                "local_process_launch_authority": False,
                "overlay_control_authority": False,
                "summon_authority": False,
                "memory_write": False,
            },
            {
                "id": "resident_runtime_authority_grant_preflight",
                "status": _safe_str(resident_runtime_preflight.get("status")).strip() or "missing",
                "evidence": ["/lens/resident-runtime/preflight", "/lens/host/activation/preflight", "/lens/status"],
                "ready": bool(resident_runtime_preflight.get("ready")),
                "grant_ready": bool(resident_runtime_preflight.get("grant_ready")),
                "authority_grant_ready": bool(resident_runtime_preflight.get("authority_grant_ready")),
                "runtime_ready": bool(resident_runtime_preflight.get("runtime_ready")),
                "resident_claim_allowed": bool(resident_runtime_preflight.get("resident_claim_allowed")),
                "blockers": _as_list(resident_runtime_preflight.get("blockers")),
                "execution_authority": False,
                "approval_decision_authority": False,
                "local_process_launch_authority": False,
                "process_supervision_authority": False,
                "process_restart_authority": False,
                "service_install_authority": False,
                "service_control_authority": False,
                "tray_registration_authority": False,
                "hotkey_registration_authority": False,
                "overlay_control_authority": False,
                "memory_write": False,
                "receipt_write_authority": False,
                "resident_claim_authority": False,
            },
            {
                "id": "resident_runtime_execution_policy_contract",
                "status": _safe_str(resident_runtime_policy.get("status")).strip() or "missing",
                "evidence": [
                    "/lens/resident-runtime/policy",
                    "/lens/resident-runtime/preflight",
                    "/lens/resident-runtime/authority-grant",
                    "/lens/status",
                ],
                "ready": bool(resident_runtime_policy.get("ready")),
                "policy_contract_ready": bool(resident_runtime_policy.get("policy_contract_ready")),
                "execution_policy_ready": bool(resident_runtime_policy.get("execution_policy_ready")),
                "grant_ready": bool(resident_runtime_policy.get("grant_ready")),
                "runtime_ready": bool(resident_runtime_policy.get("runtime_ready")),
                "resident_claim_allowed": bool(resident_runtime_policy.get("resident_claim_allowed")),
                "blockers": _as_list(resident_runtime_policy.get("blockers")),
                "execution_authority": False,
                "approval_decision_authority": False,
                "local_process_launch_authority": False,
                "process_supervision_authority": False,
                "process_restart_authority": False,
                "service_install_authority": False,
                "service_control_authority": False,
                "tray_registration_authority": False,
                "hotkey_registration_authority": False,
                "overlay_control_authority": False,
                "memory_write": False,
                "receipt_write_authority": False,
                "resident_claim_authority": False,
            },
            {
                "id": "resident_runtime_execution_authority_request_readback",
                "status": _safe_str(resident_runtime_authority_requests.get("status")).strip() or "missing",
                "evidence": [
                    "/lens/resident-runtime/authority-grant/requests",
                    "/lens/resident-runtime/authority-grant/request",
                    "/lens/status",
                ],
                "pending_count": _safe_int(resident_runtime_authority_requests.get("pending_count")),
                "approved_count": _safe_int(resident_runtime_authority_requests.get("approved_count")),
                "receipt_count": _safe_int(resident_runtime_authority_requests.get("total_count")),
                "latest_approval_id": _safe_str(
                    _as_dict(resident_runtime_authority_requests.get("latest")).get("id")
                ).strip(),
                "authority_granted": bool(resident_runtime_authority_requests.get("authority_granted")),
                "resident_claim_allowed": bool(resident_runtime_authority_requests.get("resident_claim_allowed")),
                "execution_authority": False,
                "approval_decision_authority": False,
                "local_process_launch_authority": False,
                "process_supervision_authority": False,
                "process_restart_authority": False,
                "service_install_authority": False,
                "service_control_authority": False,
                "tray_registration_authority": False,
                "hotkey_registration_authority": False,
                "overlay_control_authority": False,
                "memory_write": False,
                "receipt_write_authority": False,
                "resident_claim_authority": False,
            },
            {
                "id": "resident_runtime_execution_authority_grant_boundary",
                "status": _safe_str(resident_runtime_authority_grant.get("status")).strip() or "missing",
                "evidence": [
                    "/lens/resident-runtime/authority-grant",
                    "/lens/resident-runtime/authority-grant/grants",
                    "/lens/resident-runtime/policy",
                    "/lens/status",
                ],
                "boundary_ready": bool(resident_runtime_authority_grant.get("boundary_ready")),
                "applied": bool(resident_runtime_authority_grant.get("applied")),
                "executed": bool(resident_runtime_authority_grant.get("executed")),
                "authority_granted": bool(resident_runtime_authority_grant.get("authority_granted")),
                "grant_ready": bool(resident_runtime_authority_grant.get("grant_ready")),
                "authority_grant_ready": bool(resident_runtime_authority_grant.get("authority_grant_ready")),
                "resident_runtime_execution_authority": bool(
                    resident_runtime_authority_grant.get("resident_runtime_execution_authority")
                ),
                "runtime_ready": bool(resident_runtime_authority_grant.get("runtime_ready")),
                "resident_claim_allowed": bool(resident_runtime_authority_grant.get("resident_claim_allowed")),
                "blockers": _as_list(resident_runtime_authority_grant.get("blockers")),
                "execution_authority": False,
                "approval_decision_authority": False,
                "local_process_launch_authority": False,
                "process_supervision_authority": False,
                "process_restart_authority": False,
                "service_install_authority": False,
                "service_control_authority": False,
                "tray_registration_authority": False,
                "hotkey_registration_authority": False,
                "overlay_control_authority": False,
                "memory_write": False,
                "receipt_write_authority": False,
                "resident_claim_authority": False,
            },
            {
                "id": "resident_runtime_authority_grant_receipt_readback",
                "status": _safe_str(resident_runtime_authority_grant_receipts.get("status")).strip() or "missing",
                "evidence": [
                    "/lens/resident-runtime/authority-grant/grants",
                    "/lens/resident-runtime/authority-grant",
                    "/lens/status",
                ],
                "receipt_count": _safe_int(resident_runtime_authority_grant_receipts.get("total")),
                "latest_receipt_id": _safe_str(
                    _as_dict(resident_runtime_authority_grant_receipts.get("latest")).get("receipt_id")
                ).strip(),
                "active_receipt_id": _safe_str(
                    _as_dict(resident_runtime_authority_grant_receipts.get("active_latest")).get("receipt_id")
                ).strip(),
                "authority_granted": bool(resident_runtime_authority_grant_receipts.get("authority_granted")),
                "resident_runtime_execution_authority": bool(
                    resident_runtime_authority_grant_receipts.get("resident_runtime_execution_authority")
                ),
                "resident_claim_allowed": bool(resident_runtime_authority_grant_receipts.get("resident_claim_allowed")),
                "execution_authority": False,
                "approval_decision_authority": False,
                "local_process_launch_authority": False,
                "process_supervision_authority": False,
                "process_restart_authority": False,
                "service_install_authority": False,
                "service_control_authority": False,
                "tray_registration_authority": False,
                "hotkey_registration_authority": False,
                "overlay_control_authority": False,
                "memory_write": False,
                "resident_claim_authority": False,
                "denial_receipt_write_authority": False,
                "receipt_write_authority": False,
            },
            {
                "id": "resident_runtime_authority_grant_denial_receipt_readback",
                "status": _safe_str(resident_runtime_authority_grant_denial_receipts.get("status")).strip()
                or "missing",
                "evidence": [
                    "/lens/resident-runtime/authority-grant/denials",
                    "/lens/resident-runtime/authority-grant",
                    "/lens/status",
                ],
                "receipt_count": _safe_int(resident_runtime_authority_grant_denial_receipts.get("total")),
                "latest_receipt_id": _safe_str(
                    _as_dict(resident_runtime_authority_grant_denial_receipts.get("latest")).get("receipt_id")
                ).strip(),
                "execution_authority": False,
                "approval_decision_authority": False,
                "local_process_launch_authority": False,
                "process_supervision_authority": False,
                "process_restart_authority": False,
                "service_install_authority": False,
                "service_control_authority": False,
                "tray_registration_authority": False,
                "hotkey_registration_authority": False,
                "overlay_control_authority": False,
                "memory_write": False,
                "resident_claim_authority": False,
                "denial_receipt_write_authority": False,
                "receipt_write_authority": False,
            },
            {
                "id": "resident_runtime_authority_grant_readiness_audit",
                "status": _safe_str(resident_runtime_authority_grant_readiness.get("status")).strip() or "missing",
                "audit_status": _safe_str(resident_runtime_authority_grant_readiness.get("audit_status")).strip(),
                "evidence": [
                    "/lens/resident-runtime/authority-grant/readiness",
                    "/lens/resident-runtime/authority-grant/grants",
                    "/lens/resident-runtime/authority-grant/denials",
                    "/lens/resident-runtime/authority-grant",
                    "/lens/resident-runtime/policy",
                    "/lens/resident-runtime/plan",
                    "/lens/status",
                ],
                "ready": bool(resident_runtime_authority_grant_readiness.get("ready")),
                "grant_ready": bool(resident_runtime_authority_grant_readiness.get("grant_ready")),
                "authority_grant_ready": bool(resident_runtime_authority_grant_readiness.get("authority_grant_ready")),
                "runtime_ready": bool(resident_runtime_authority_grant_readiness.get("runtime_ready")),
                "resident_claim_allowed": bool(
                    resident_runtime_authority_grant_readiness.get("resident_claim_allowed")
                ),
                "boundary_observed": bool(resident_runtime_authority_grant_readiness.get("boundary_observed")),
                "authority_granted": bool(resident_runtime_authority_grant_readiness.get("authority_granted")),
                "resident_runtime_execution_authority": bool(
                    resident_runtime_authority_grant_readiness.get("resident_runtime_execution_authority")
                ),
                "grant_receipt_readback_ready": bool(
                    resident_runtime_authority_grant_readiness.get("grant_receipt_readback_ready")
                ),
                "denial_receipt_readback_ready": bool(
                    resident_runtime_authority_grant_readiness.get("denial_receipt_readback_ready")
                ),
                "requirements_total": _safe_int(resident_runtime_authority_grant_readiness.get("requirements_total")),
                "requirements_ready_total": _safe_int(
                    resident_runtime_authority_grant_readiness.get("requirements_ready_total")
                ),
                "requirements_blocked_total": _safe_int(
                    resident_runtime_authority_grant_readiness.get("requirements_blocked_total")
                ),
                "blocked_requirements": _as_list(
                    resident_runtime_authority_grant_readiness.get("blocked_requirements")
                ),
                "blockers": _as_list(resident_runtime_authority_grant_readiness.get("blockers")),
                "execution_authority": False,
                "approval_decision_authority": False,
                "local_process_launch_authority": False,
                "process_supervision_authority": False,
                "process_restart_authority": False,
                "service_install_authority": False,
                "service_control_authority": False,
                "tray_registration_authority": False,
                "hotkey_registration_authority": False,
                "overlay_control_authority": False,
                "memory_write": False,
                "resident_claim_authority": False,
                "denial_receipt_write_authority": False,
                "receipt_write_authority": False,
            },
            {
                "id": "resident_runtime_activation_plan",
                "status": _safe_str(_as_dict(resident_host.get("resident_runtime_plan")).get("status")).strip()
                or "missing",
                "evidence": [
                    "/lens/resident-runtime/plan",
                    "/lens/host/supervision",
                    "/lens/summon",
                    "/lens/tray",
                    "/lens/overlay",
                    "/lens/status",
                ],
                "plan_available": bool(_as_dict(resident_host.get("resident_runtime_plan")).get("plan_available")),
                "runtime_ready": bool(_as_dict(resident_host.get("resident_runtime_plan")).get("runtime_ready")),
                "resident_claim_allowed": bool(
                    _as_dict(resident_host.get("resident_runtime_plan")).get("resident_claim_allowed")
                ),
                "blockers": _as_list(_as_dict(resident_host.get("resident_runtime_plan")).get("blockers")),
                "execution_authority": False,
                "resident_runtime_execution_authority": bool(
                    _as_dict(resident_host.get("resident_runtime_plan")).get("resident_runtime_execution_authority")
                    or _as_dict(resident_host.get("resident_runtime_plan")).get("active_authority_grant_receipt_id")
                ),
                "approval_decision_authority": False,
                "local_process_launch_authority": False,
                "process_supervision_authority": False,
                "service_install_authority": False,
                "service_control_authority": False,
                "tray_registration_authority": False,
                "hotkey_registration_authority": False,
                "overlay_control_authority": False,
                "memory_write": False,
            },
            {
                "id": "resident_runtime_authority_boundary",
                "status": _safe_str(_as_dict(resident_host.get("resident_runtime_denial")).get("status")).strip()
                or "missing",
                "evidence": ["/lens/resident-runtime/execute", "/lens/resident-runtime/plan", "/lens/status"],
                "applied": bool(_as_dict(resident_host.get("resident_runtime_denial")).get("applied")),
                "executed": bool(_as_dict(resident_host.get("resident_runtime_denial")).get("executed")),
                "blockers": _as_list(_as_dict(resident_host.get("resident_runtime_denial")).get("blockers")),
                "execution_authority": False,
                "resident_runtime_execution_authority": bool(
                    _as_dict(resident_host.get("resident_runtime_denial")).get("resident_runtime_execution_authority")
                ),
                "approval_decision_authority": False,
                "local_process_launch_authority": False,
                "process_supervision_authority": False,
                "process_restart_authority": False,
                "service_install_authority": False,
                "service_control_authority": False,
                "tray_registration_authority": False,
                "hotkey_registration_authority": False,
                "overlay_control_authority": False,
                "memory_write": False,
                "receipt_write_authority": False,
                "resident_claim_authority": False,
            },
            {
                "id": "resident_runtime_execution_receipt_readback",
                "status": _safe_str(resident_runtime_execution_receipts.get("status")).strip() or "missing",
                "evidence": [
                    "/lens/resident-runtime/executions",
                    "/lens/resident-runtime/execute",
                    "/lens/host/supervision/executions",
                    "/lens/status",
                ],
                "receipt_count": _safe_int(resident_runtime_execution_receipts.get("total")),
                "latest_receipt_id": _safe_str(
                    _as_dict(resident_runtime_execution_receipts.get("latest")).get("receipt_id")
                ).strip(),
                "latest_supervision_mode": _safe_str(
                    resident_runtime_execution_receipts.get("latest_supervision_mode")
                ).strip(),
                "latest_resident_host_process": bool(
                    resident_runtime_execution_receipts.get("latest_resident_host_process")
                ),
                "latest_resident_supervised_runtime": bool(
                    resident_runtime_execution_receipts.get("latest_resident_supervised_runtime")
                ),
                "resident_supervised_runtime_receipt_observed": bool(
                    resident_runtime_execution_receipts.get("resident_supervised_runtime_receipt_observed")
                ),
                "resident_claim_allowed": bool(resident_runtime_execution_receipts.get("resident_claim_allowed")),
                "execution_authority": False,
                "approval_decision_authority": False,
                "local_process_launch_authority": False,
                "process_supervision_authority": False,
                "process_restart_authority": False,
                "service_install_authority": False,
                "service_control_authority": False,
                "tray_registration_authority": False,
                "hotkey_registration_authority": False,
                "overlay_control_authority": False,
                "memory_write": False,
                "resident_claim_authority": False,
                "receipt_write_authority": False,
            },
            {
                "id": "resident_runtime_activation_denial_receipt_readback",
                "status": _safe_str(resident_runtime_denial_receipts.get("status")).strip() or "missing",
                "evidence": [
                    "/lens/resident-runtime/denials",
                    "/lens/resident-runtime/execute",
                    "/lens/status",
                ],
                "receipt_count": _safe_int(resident_runtime_denial_receipts.get("total")),
                "latest_receipt_id": _safe_str(
                    _as_dict(resident_runtime_denial_receipts.get("latest")).get("receipt_id")
                ).strip(),
                "execution_authority": False,
                "approval_decision_authority": False,
                "local_process_launch_authority": False,
                "process_supervision_authority": False,
                "process_restart_authority": False,
                "service_install_authority": False,
                "service_control_authority": False,
                "tray_registration_authority": False,
                "hotkey_registration_authority": False,
                "overlay_control_authority": False,
                "memory_write": False,
                "resident_claim_authority": False,
                "denial_receipt_write_authority": False,
                "receipt_write_authority": False,
            },
            {
                "id": "resident_host_runtime_loop_denial_receipt_readback",
                "status": _safe_str(runtime_loop_denial_receipts.get("status")).strip() or "missing",
                "evidence": [
                    "/lens/host/runtime-loop/denials",
                    "/lens/host/runtime-loop/execute",
                    "/lens/status",
                ],
                "receipt_count": _safe_int(runtime_loop_denial_receipts.get("total")),
                "latest_receipt_id": _safe_str(
                    _as_dict(runtime_loop_denial_receipts.get("latest")).get("receipt_id")
                ).strip(),
                "execution_authority": False,
                "resident_runtime_execution_authority": False,
                "approval_decision_authority": False,
                "local_process_launch_authority": False,
                "process_supervision_authority": False,
                "process_restart_authority": False,
                "service_install_authority": False,
                "service_control_authority": False,
                "tray_registration_authority": False,
                "hotkey_registration_authority": False,
                "overlay_control_authority": False,
                "memory_write": False,
                "resident_claim_authority": False,
                "denial_receipt_write_authority": False,
                "receipt_write_authority": False,
            },
            {
                "id": "resident_host_runtime_loop_readiness_audit",
                "status": _safe_str(runtime_loop_readiness.get("status")).strip() or "missing",
                "audit_status": _safe_str(runtime_loop_readiness.get("audit_status")).strip(),
                "evidence": [
                    "/lens/host/runtime-loop/readiness",
                    "/lens/host/runtime-loop",
                    "/lens/host/runtime-loop/execute",
                    "/lens/host/runtime-loop/denials",
                    "/lens/status",
                ],
                "next_smallest_truthful_gap": _safe_str(
                    runtime_loop_readiness.get("next_smallest_truthful_gap")
                ).strip(),
                "operator_surface_readback_ready": bool(runtime_loop_readiness.get("operator_surface_readback_ready")),
                "first_blocked_requirement": first_runtime_loop_blocked_requirement,
                "first_blocked_requirement_handoff": _as_dict(
                    runtime_loop_readiness.get("first_blocked_requirement_handoff")
                ),
                "blocked_requirement_handoffs": _as_list(runtime_loop_readiness.get("blocked_requirement_handoffs")),
                "requirement_readback": runtime_loop_requirement_readback,
                "blocked_requirement_readback": runtime_loop_blocked_requirement_readback,
                "ready": bool(runtime_loop_readiness.get("ready")),
                "loop_ready": bool(runtime_loop_readiness.get("loop_ready")),
                "execution_ready": bool(runtime_loop_readiness.get("execution_ready")),
                "resident_runtime_loop": bool(runtime_loop_readiness.get("resident_runtime_loop")),
                "resident_runtime_ready": bool(runtime_loop_readiness.get("resident_runtime_ready")),
                "resident_claim_allowed": bool(runtime_loop_readiness.get("resident_claim_allowed")),
                "runtime_plan_available": bool(runtime_loop_readiness.get("runtime_plan_available")),
                "loop_contract_readback_ready": bool(runtime_loop_readiness.get("loop_contract_readback_ready")),
                "execution_denial_boundary_observed": bool(
                    runtime_loop_readiness.get("execution_denial_boundary_observed")
                ),
                "denial_receipt_readback_ready": bool(runtime_loop_readiness.get("denial_receipt_readback_ready")),
                "requirements_total": _safe_int(runtime_loop_readiness.get("requirements_total")),
                "requirements_ready_total": _safe_int(runtime_loop_readiness.get("requirements_ready_total")),
                "requirements_blocked_total": _safe_int(runtime_loop_readiness.get("requirements_blocked_total")),
                "blocked_requirements": _as_list(runtime_loop_readiness.get("blocked_requirements")),
                "blockers": _as_list(runtime_loop_readiness.get("blockers")),
                "receipt_count": _safe_int(runtime_loop_readiness.get("receipt_count")),
                "latest_receipt_id": _safe_str(runtime_loop_readiness.get("latest_receipt_id")).strip(),
                "execution_authority": False,
                "resident_runtime_execution_authority": False,
                "approval_decision_authority": False,
                "local_process_launch_authority": False,
                "process_supervision_authority": False,
                "process_restart_authority": False,
                "service_install_authority": False,
                "service_control_authority": False,
                "tray_registration_authority": False,
                "hotkey_registration_authority": False,
                "overlay_control_authority": False,
                "memory_write": False,
                "resident_claim_authority": False,
                "denial_receipt_write_authority": False,
                "receipt_write_authority": False,
            },
            {
                "id": "resident_supervision_enablement_gate",
                "status": _safe_str(_as_dict(resident_host.get("supervision_gate")).get("status")).strip() or "missing",
                "evidence": ["/lens/host/supervision", "/lens/host/manifest", "/lens/status"],
                "ready": bool(_as_dict(resident_host.get("supervision_gate")).get("ready")),
                "resident_claim_allowed": bool(
                    _as_dict(resident_host.get("supervision_gate")).get("resident_claim_allowed")
                ),
                "process_supervision_authority": False,
                "process_restart_authority": False,
                "service_install_authority": False,
                "service_control_authority": False,
                "receipt_write_authority": False,
                "resident_claim_authority": False,
                "blockers": _as_list(_as_dict(resident_host.get("supervision_gate")).get("blockers")),
            },
            {
                "id": "persistent_supervision_enablement_denial_boundary",
                "status": _safe_str(
                    _as_dict(resident_host.get("persistent_supervision_enablement_denial")).get("status")
                ).strip()
                or "missing",
                "evidence": [
                    "/lens/host/persistent-supervision/enablement",
                    "/lens/host/persistent-supervision",
                    "/lens/status",
                ],
                "boundary_ready": bool(
                    _as_dict(resident_host.get("persistent_supervision_enablement_denial")).get("boundary_ready")
                ),
                "applied": bool(_as_dict(resident_host.get("persistent_supervision_enablement_denial")).get("applied")),
                "executed": bool(
                    _as_dict(resident_host.get("persistent_supervision_enablement_denial")).get("executed")
                ),
                "ready": bool(_as_dict(resident_host.get("persistent_supervision_enablement_denial")).get("ready")),
                "enablement_ready": bool(
                    _as_dict(resident_host.get("persistent_supervision_enablement_denial")).get("enablement_ready")
                ),
                "authority_granted": bool(
                    _as_dict(resident_host.get("persistent_supervision_enablement_denial")).get("authority_granted")
                ),
                "authority_grant_active": bool(
                    _as_dict(resident_host.get("persistent_supervision_enablement_denial")).get(
                        "authority_grant_active"
                    )
                ),
                "service_config_updated": bool(
                    _as_dict(resident_host.get("persistent_supervision_enablement_denial")).get(
                        "service_config_updated"
                    )
                ),
                "resident_claim_allowed": bool(
                    _as_dict(resident_host.get("persistent_supervision_enablement_denial")).get(
                        "resident_claim_allowed"
                    )
                ),
                "blockers": _as_list(
                    _as_dict(resident_host.get("persistent_supervision_enablement_denial")).get("blockers")
                ),
                "execution_authority": False,
                "approval_decision_authority": False,
                "local_process_launch_authority": False,
                "process_supervision_authority": False,
                "process_restart_authority": False,
                "service_install_authority": False,
                "service_control_authority": False,
                "service_config_write_authority": False,
                "receipt_write_authority": False,
                "denial_receipt_write_authority": False,
                "memory_write": False,
                "resident_claim_authority": False,
            },
            {
                "id": "persistent_supervision_enablement_authority_readiness_audit",
                "status": _safe_str(persistent_supervision_enablement_authority_readiness.get("status")).strip()
                or "missing",
                "audit_status": _safe_str(
                    persistent_supervision_enablement_authority_readiness.get("audit_status")
                ).strip(),
                "evidence": [
                    "/lens/host/persistent-supervision/enablement/authority/readiness",
                    "/lens/host/persistent-supervision/enablement/authority",
                    "/lens/host/persistent-supervision/enablement/authority/grants",
                    "/lens/host/persistent-supervision/enablement/authority/requests",
                    "/lens/host/persistent-supervision/enablement/authority/request",
                    "/lens/host/persistent-supervision/enablement",
                    "/lens/host/persistent-supervision",
                    "/lens/status",
                ],
                "ready": bool(persistent_supervision_enablement_authority_readiness.get("ready")),
                "preflight_ready": bool(persistent_supervision_enablement_authority_readiness.get("preflight_ready")),
                "approval_ready": bool(persistent_supervision_enablement_authority_readiness.get("approval_ready")),
                "request_readback_ready": bool(
                    persistent_supervision_enablement_authority_readiness.get("request_readback_ready")
                ),
                "request_pending_count": _safe_int(
                    persistent_supervision_enablement_authority_readiness.get("request_pending_count")
                ),
                "request_approved_count": _safe_int(
                    persistent_supervision_enablement_authority_readiness.get("request_approved_count")
                ),
                "request_total_count": _safe_int(
                    persistent_supervision_enablement_authority_readiness.get("request_total_count")
                ),
                "latest_request_approval_id": _safe_str(
                    persistent_supervision_enablement_authority_readiness.get("latest_request_approval_id")
                ).strip(),
                "boundary_observed": bool(
                    persistent_supervision_enablement_authority_readiness.get("boundary_observed")
                ),
                "grant_boundary_observed": bool(
                    persistent_supervision_enablement_authority_readiness.get("grant_boundary_observed")
                ),
                "grant_receipt_readback_ready": bool(
                    persistent_supervision_enablement_authority_readiness.get("grant_receipt_readback_ready")
                ),
                "authority_grant_active": bool(
                    persistent_supervision_enablement_authority_readiness.get("authority_grant_active")
                ),
                "active_grant_receipt_id": _safe_str(
                    persistent_supervision_enablement_authority_readiness.get("active_grant_receipt_id")
                ).strip(),
                "enablement_authority_granted": bool(
                    persistent_supervision_enablement_authority_readiness.get("enablement_authority_granted")
                ),
                "active_enablement_authority_grant_receipt_id": _safe_str(
                    persistent_supervision_enablement_authority_readiness.get(
                        "active_enablement_authority_grant_receipt_id"
                    )
                ).strip(),
                "enablement_ready": bool(persistent_supervision_enablement_authority_readiness.get("enablement_ready")),
                "persistent_supervision_enablement_allowed": bool(
                    persistent_supervision_enablement_authority_readiness.get(
                        "persistent_supervision_enablement_allowed"
                    )
                ),
                "service_config_updated": bool(
                    persistent_supervision_enablement_authority_readiness.get("service_config_updated")
                ),
                "authority_granted": bool(
                    persistent_supervision_enablement_authority_readiness.get("authority_granted")
                ),
                "grant_receipt_count": _safe_int(
                    persistent_supervision_enablement_authority_readiness.get("grant_receipt_count")
                ),
                "latest_grant_receipt_id": _safe_str(
                    persistent_supervision_enablement_authority_readiness.get("latest_grant_receipt_id")
                ).strip(),
                "resident_claim_allowed": bool(
                    persistent_supervision_enablement_authority_readiness.get("resident_claim_allowed")
                ),
                "requirements_total": _safe_int(
                    persistent_supervision_enablement_authority_readiness.get("requirements_total")
                ),
                "requirements_ready_total": _safe_int(
                    persistent_supervision_enablement_authority_readiness.get("requirements_ready_total")
                ),
                "requirements_blocked_total": _safe_int(
                    persistent_supervision_enablement_authority_readiness.get("requirements_blocked_total")
                ),
                "blocked_requirements": _as_list(
                    persistent_supervision_enablement_authority_readiness.get("blocked_requirements")
                ),
                "operator_surface_readback_ready": bool(
                    persistent_supervision_enablement_authority_readiness.get("operator_surface_readback_ready")
                ),
                "first_blocked_requirement": _safe_str(
                    persistent_supervision_enablement_authority_readiness.get("first_blocked_requirement")
                ).strip(),
                "first_blocked_requirement_handoff": _as_dict(
                    persistent_supervision_enablement_authority_readiness.get("first_blocked_requirement_handoff")
                ),
                "blocked_requirement_handoffs": _as_list(
                    persistent_supervision_enablement_authority_readiness.get("blocked_requirement_handoffs")
                ),
                "next_smallest_truthful_gap": _safe_str(
                    persistent_supervision_enablement_authority_readiness.get("next_smallest_truthful_gap")
                ).strip(),
                "blockers": _as_list(persistent_supervision_enablement_authority_readiness.get("blockers")),
                "execution_authority": False,
                "approval_decision_authority": False,
                "local_process_launch_authority": False,
                "process_supervision_authority": False,
                "process_restart_authority": False,
                "service_install_authority": False,
                "service_control_authority": False,
                "persistent_supervision_enablement_authority": bool(
                    _as_dict(persistent_supervision_enablement_authority_readiness.get("governance")).get(
                        "persistent_supervision_enablement_authority"
                    )
                ),
                "service_config_write_authority": False,
                "persistent_supervision_execution_authority": False,
                "receipt_write_authority": bool(
                    _as_dict(persistent_supervision_enablement_authority_readiness.get("governance")).get(
                        "receipt_write_authority"
                    )
                ),
                "denial_receipt_write_authority": False,
                "memory_write": False,
                "resident_claim_authority": False,
            },
            {
                "id": "persistent_supervision_enablement_authority_grant_receipt_readback",
                "status": _safe_str(persistent_supervision_enablement_authority_grants.get("status")).strip()
                or "missing",
                "evidence": [
                    "/lens/host/persistent-supervision/enablement/authority/grants",
                    "/lens/host/persistent-supervision/enablement/authority",
                    "/lens/status",
                ],
                "receipt_count": _safe_int(persistent_supervision_enablement_authority_grants.get("total")),
                "latest_receipt_id": _safe_str(
                    _as_dict(persistent_supervision_enablement_authority_grants.get("latest")).get("receipt_id")
                ).strip(),
                "active_receipt_id": _safe_str(
                    _as_dict(persistent_supervision_enablement_authority_grants.get("active_latest")).get("receipt_id")
                ).strip(),
                "authority_granted": bool(persistent_supervision_enablement_authority_grants.get("authority_granted")),
                "execution_authority": False,
                "approval_decision_authority": False,
                "local_process_launch_authority": False,
                "process_supervision_authority": False,
                "process_restart_authority": False,
                "service_install_authority": False,
                "service_control_authority": False,
                "persistent_supervision_enablement_authority": bool(
                    persistent_supervision_enablement_authority_grants.get("authority_granted")
                ),
                "service_config_write_authority": False,
                "persistent_supervision_execution_authority": False,
                "receipt_write_authority": False,
                "denial_receipt_write_authority": False,
                "memory_write": False,
                "resident_claim_authority": False,
            },
            {
                "id": "persistent_supervision_enablement_execution_readiness_audit",
                "status": _safe_str(persistent_supervision_enablement_execution_readiness.get("status")).strip()
                or "missing",
                "audit_status": _safe_str(
                    persistent_supervision_enablement_execution_readiness.get("audit_status")
                ).strip(),
                "evidence": [
                    "/lens/host/persistent-supervision/enablement/execution/readiness",
                    "/lens/host/persistent-supervision/enablement/execution/request",
                    "/lens/host/persistent-supervision/enablement/execution/requests",
                    "/lens/host/persistent-supervision/enablement/execution/authority",
                    "/lens/host/persistent-supervision/enablement/execution/authority/grants",
                    "/lens/host/persistent-supervision/enablement",
                    "/lens/status",
                ],
                "ready": bool(persistent_supervision_enablement_execution_readiness.get("ready")),
                "approval_ready": bool(persistent_supervision_enablement_execution_readiness.get("approval_ready")),
                "request_readback_ready": bool(
                    persistent_supervision_enablement_execution_readiness.get("request_readback_ready")
                ),
                "request_pending_count": _safe_int(
                    persistent_supervision_enablement_execution_readiness.get("request_pending_count")
                ),
                "request_approved_count": _safe_int(
                    persistent_supervision_enablement_execution_readiness.get("request_approved_count")
                ),
                "request_total_count": _safe_int(
                    persistent_supervision_enablement_execution_readiness.get("request_total_count")
                ),
                "latest_request_approval_id": _safe_str(
                    persistent_supervision_enablement_execution_readiness.get("latest_request_approval_id")
                ).strip(),
                "boundary_observed": bool(
                    persistent_supervision_enablement_execution_readiness.get("boundary_observed")
                ),
                "enablement_authority_granted": bool(
                    persistent_supervision_enablement_execution_readiness.get("enablement_authority_granted")
                ),
                "active_enablement_authority_grant_receipt_id": _safe_str(
                    persistent_supervision_enablement_execution_readiness.get(
                        "active_enablement_authority_grant_receipt_id"
                    )
                ).strip(),
                "execution_authority_granted": bool(
                    persistent_supervision_enablement_execution_readiness.get("execution_authority_granted")
                ),
                "active_execution_authority_grant_receipt_id": _safe_str(
                    persistent_supervision_enablement_execution_readiness.get(
                        "active_execution_authority_grant_receipt_id"
                    )
                ).strip(),
                "persistent_supervision_enablement_allowed": bool(
                    persistent_supervision_enablement_execution_readiness.get(
                        "persistent_supervision_enablement_allowed"
                    )
                ),
                "service_config_updated": bool(
                    persistent_supervision_enablement_execution_readiness.get("service_config_updated")
                ),
                "service_config_write_authority": bool(
                    persistent_supervision_enablement_execution_readiness.get("service_config_write_authority")
                ),
                "persistent_supervision_execution_authority": bool(
                    persistent_supervision_enablement_execution_readiness.get(
                        "persistent_supervision_execution_authority"
                    )
                ),
                "receipt_write_authority": bool(
                    persistent_supervision_enablement_execution_readiness.get("receipt_write_authority")
                ),
                "resident_claim_allowed": bool(
                    persistent_supervision_enablement_execution_readiness.get("resident_claim_allowed")
                ),
                "requirements_total": _safe_int(
                    persistent_supervision_enablement_execution_readiness.get("requirements_total")
                ),
                "requirements_ready_total": _safe_int(
                    persistent_supervision_enablement_execution_readiness.get("requirements_ready_total")
                ),
                "requirements_blocked_total": _safe_int(
                    persistent_supervision_enablement_execution_readiness.get("requirements_blocked_total")
                ),
                "blocked_requirements": _as_list(
                    persistent_supervision_enablement_execution_readiness.get("blocked_requirements")
                ),
                "operator_surface_readback_ready": bool(
                    persistent_supervision_enablement_execution_readiness.get("operator_surface_readback_ready")
                ),
                "first_blocked_requirement": _safe_str(
                    persistent_supervision_enablement_execution_readiness.get("first_blocked_requirement")
                ).strip(),
                "first_blocked_requirement_handoff": _as_dict(
                    persistent_supervision_enablement_execution_readiness.get("first_blocked_requirement_handoff")
                ),
                "blocked_requirement_handoffs": _as_list(
                    persistent_supervision_enablement_execution_readiness.get("blocked_requirement_handoffs")
                ),
                "next_smallest_truthful_gap": _safe_str(
                    persistent_supervision_enablement_execution_readiness.get("next_smallest_truthful_gap")
                ).strip(),
                "blockers": _as_list(persistent_supervision_enablement_execution_readiness.get("blockers")),
                "execution_authority": False,
                "approval_decision_authority": False,
                "local_process_launch_authority": False,
                "process_supervision_authority": False,
                "process_restart_authority": False,
                "service_install_authority": False,
                "service_control_authority": False,
                "persistent_supervision_enablement_authority": bool(
                    _as_dict(persistent_supervision_enablement_execution_readiness.get("governance")).get(
                        "persistent_supervision_enablement_authority"
                    )
                ),
                "denial_receipt_write_authority": False,
                "memory_write": False,
                "resident_claim_authority": False,
            },
            {
                "id": "persistent_supervision_enablement_execution_authority_grant_receipt_readback",
                "status": _safe_str(persistent_supervision_enablement_execution_authority_grants.get("status")).strip()
                or "missing",
                "evidence": [
                    "/lens/host/persistent-supervision/enablement/execution/authority/grants",
                    "/lens/host/persistent-supervision/enablement/execution/requests",
                    "/lens/status",
                ],
                "receipt_count": _safe_int(persistent_supervision_enablement_execution_authority_grants.get("total")),
                "active_receipt_id": _safe_str(
                    _as_dict(persistent_supervision_enablement_execution_authority_grants.get("active_latest")).get(
                        "receipt_id"
                    )
                ).strip(),
                "authority_granted": bool(
                    persistent_supervision_enablement_execution_authority_grants.get("authority_granted")
                ),
                "service_config_write_authority": bool(
                    persistent_supervision_enablement_execution_authority_grants.get("service_config_write_authority")
                ),
                "persistent_supervision_execution_authority": bool(
                    persistent_supervision_enablement_execution_authority_grants.get(
                        "persistent_supervision_execution_authority"
                    )
                ),
                "execution_authority": False,
                "approval_decision_authority": False,
                "local_process_launch_authority": False,
                "process_supervision_authority": False,
                "process_restart_authority": False,
                "service_install_authority": False,
                "service_control_authority": False,
                "receipt_write_authority": False,
                "denial_receipt_write_authority": False,
                "memory_write": False,
                "resident_claim_authority": False,
            },
            {
                "id": "persistent_supervision_enablement_execution_receipt_readback",
                "status": _safe_str(persistent_supervision_enablement_execution_receipts.get("status")).strip()
                or "missing",
                "evidence": [
                    "/lens/host/persistent-supervision/enablement/executions",
                    "/lens/host/persistent-supervision/enablement/execution",
                    "/lens/status",
                ],
                "receipt_count": _safe_int(persistent_supervision_enablement_execution_receipts.get("total")),
                "latest_receipt_id": _safe_str(
                    _as_dict(persistent_supervision_enablement_execution_receipts.get("latest")).get("receipt_id")
                ).strip(),
                "service_config_updated": bool(
                    persistent_supervision_enablement_execution_receipts.get("service_config_updated")
                ),
                "persistent_supervision_enablement_allowed": bool(
                    persistent_supervision_enablement_execution_receipts.get(
                        "persistent_supervision_enablement_allowed"
                    )
                ),
                "persistent_supervision_ready": bool(
                    persistent_supervision_enablement_execution_receipts.get("persistent_supervision_ready")
                ),
                "resident_claim_allowed": bool(
                    persistent_supervision_enablement_execution_receipts.get("resident_claim_allowed")
                ),
                "execution_authority": False,
                "approval_decision_authority": False,
                "local_process_launch_authority": False,
                "process_supervision_authority": False,
                "process_restart_authority": False,
                "service_install_authority": False,
                "service_control_authority": False,
                "service_config_write_authority": False,
                "persistent_supervision_execution_authority": False,
                "receipt_write_authority": False,
                "denial_receipt_write_authority": False,
                "memory_write": False,
                "resident_claim_authority": False,
            },
            {
                "id": "persistent_supervision_enablement_execution_denial_boundary",
                "status": _safe_str(persistent_supervision_enablement_execution_denial.get("status")).strip()
                or "missing",
                "evidence": [
                    "/lens/host/persistent-supervision/enablement/execution",
                    "/lens/host/persistent-supervision/enablement/execution/readiness",
                    "/lens/status",
                ],
                "boundary_ready": bool(persistent_supervision_enablement_execution_denial.get("boundary_ready")),
                "applied": bool(persistent_supervision_enablement_execution_denial.get("applied")),
                "executed": bool(persistent_supervision_enablement_execution_denial.get("executed")),
                "ready": bool(persistent_supervision_enablement_execution_denial.get("ready")),
                "approval_ready": bool(
                    _as_dict(persistent_supervision_enablement_execution_denial.get("approval")).get("ready")
                ),
                "enablement_authority_granted": bool(
                    persistent_supervision_enablement_execution_denial.get(
                        "persistent_supervision_enablement_authority_granted"
                    )
                ),
                "active_enablement_authority_grant_receipt_id": _safe_str(
                    persistent_supervision_enablement_execution_denial.get(
                        "active_enablement_authority_grant_receipt_id"
                    )
                ).strip(),
                "authority_granted": bool(persistent_supervision_enablement_execution_denial.get("authority_granted")),
                "active_execution_authority_grant_receipt_id": _safe_str(
                    persistent_supervision_enablement_execution_denial.get(
                        "active_execution_authority_grant_receipt_id"
                    )
                ).strip(),
                "persistent_supervision_enablement_allowed": bool(
                    persistent_supervision_enablement_execution_denial.get("persistent_supervision_enablement_allowed")
                ),
                "service_config_updated": bool(
                    persistent_supervision_enablement_execution_denial.get("service_config_updated")
                ),
                "resident_claim_allowed": bool(
                    persistent_supervision_enablement_execution_denial.get("resident_claim_allowed")
                ),
                "blockers": _as_list(persistent_supervision_enablement_execution_denial.get("blockers")),
                "execution_authority": False,
                "approval_decision_authority": False,
                "local_process_launch_authority": False,
                "process_supervision_authority": False,
                "process_restart_authority": False,
                "service_install_authority": False,
                "service_control_authority": False,
                "persistent_supervision_enablement_authority": bool(
                    _as_dict(persistent_supervision_enablement_execution_denial.get("governance")).get(
                        "persistent_supervision_enablement_authority"
                    )
                ),
                "service_config_write_authority": bool(
                    persistent_supervision_enablement_execution_denial.get("service_config_write_authority")
                ),
                "persistent_supervision_execution_authority": bool(
                    persistent_supervision_enablement_execution_denial.get("persistent_supervision_execution_authority")
                ),
                "receipt_write_authority": bool(
                    persistent_supervision_enablement_execution_denial.get("receipt_write_authority")
                ),
                "denial_receipt_write_authority": False,
                "memory_write": False,
                "resident_claim_authority": False,
            },
            {
                "id": "resident_host_supervision_authority_preflight",
                "status": _safe_str(supervision_authority_preflight.get("status")).strip() or "missing",
                "evidence": [
                    "/lens/host/supervision/authority",
                    "/lens/host/supervision",
                    "/lens/host/manifest",
                    "/lens/status",
                ],
                "ready": bool(supervision_authority_preflight.get("ready")),
                "preflight_ready": bool(supervision_authority_preflight.get("preflight_ready")),
                "authority_ready": bool(supervision_authority_preflight.get("authority_ready")),
                "resident_claim_allowed": bool(supervision_authority_preflight.get("resident_claim_allowed")),
                "requirements_total": _safe_int(supervision_authority_preflight.get("requirements_total")),
                "requirements_ready_total": _safe_int(supervision_authority_preflight.get("requirements_ready_total")),
                "requirements_blocked_total": _safe_int(
                    supervision_authority_preflight.get("requirements_blocked_total")
                ),
                "blocked_requirements": _as_list(supervision_authority_preflight.get("blocked_requirements")),
                "blockers": _as_list(supervision_authority_preflight.get("blockers")),
                "execution_authority": False,
                "approval_decision_authority": False,
                "local_process_launch_authority": False,
                "process_supervision_authority": False,
                "process_restart_authority": False,
                "service_install_authority": False,
                "service_control_authority": False,
                "tray_registration_authority": False,
                "hotkey_registration_authority": False,
                "overlay_control_authority": False,
                "memory_write": False,
                "receipt_write_authority": False,
                "resident_claim_authority": False,
            },
            {
                "id": "resident_host_supervision_authority_denial_boundary",
                "status": _safe_str(supervision_authority_denial.get("status")).strip() or "missing",
                "evidence": [
                    "/lens/host/supervision/authority",
                    "/lens/host/supervision",
                    "/lens/host/manifest",
                    "/lens/status",
                ],
                "boundary_ready": bool(supervision_authority_denial.get("boundary_ready")),
                "applied": bool(supervision_authority_denial.get("applied")),
                "executed": bool(supervision_authority_denial.get("executed")),
                "authority_granted": bool(supervision_authority_denial.get("authority_granted")),
                "ready": bool(supervision_authority_denial.get("ready")),
                "supervision_ready": bool(supervision_authority_denial.get("supervision_ready")),
                "authority_ready": bool(supervision_authority_denial.get("authority_ready")),
                "resident_claim_allowed": bool(supervision_authority_denial.get("resident_claim_allowed")),
                "blockers": _as_list(supervision_authority_denial.get("blockers")),
                "execution_authority": False,
                "approval_decision_authority": False,
                "local_process_launch_authority": False,
                "process_supervision_authority": False,
                "process_restart_authority": False,
                "service_install_authority": False,
                "service_control_authority": False,
                "tray_registration_authority": False,
                "hotkey_registration_authority": False,
                "overlay_control_authority": False,
                "memory_write": False,
                "receipt_write_authority": False,
                "denial_receipt_write_authority": False,
                "resident_claim_authority": False,
            },
            {
                "id": "resident_host_supervision_authority_denial_receipt_readback",
                "status": _safe_str(supervision_authority_denial_receipts.get("status")).strip() or "missing",
                "evidence": [
                    "/lens/host/supervision/authority/denials",
                    "/lens/host/supervision/authority",
                    "/lens/status",
                ],
                "receipt_count": _safe_int(supervision_authority_denial_receipts.get("total")),
                "latest_receipt_id": _safe_str(
                    _as_dict(supervision_authority_denial_receipts.get("latest")).get("receipt_id")
                ).strip(),
                "execution_authority": False,
                "approval_decision_authority": False,
                "local_process_launch_authority": False,
                "process_supervision_authority": False,
                "process_restart_authority": False,
                "service_install_authority": False,
                "service_control_authority": False,
                "tray_registration_authority": False,
                "hotkey_registration_authority": False,
                "overlay_control_authority": False,
                "memory_write": False,
                "resident_claim_authority": False,
                "denial_receipt_write_authority": False,
                "receipt_write_authority": False,
            },
            {
                "id": "resident_host_supervision_authority_grant_receipt_readback",
                "status": _safe_str(supervision_authority_grant_receipts.get("status")).strip() or "missing",
                "evidence": [
                    "/lens/host/supervision/authority/grants",
                    "/lens/host/supervision/authority",
                    "/lens/status",
                ],
                "receipt_count": _safe_int(supervision_authority_grant_receipts.get("total")),
                "latest_receipt_id": _safe_str(
                    _as_dict(supervision_authority_grant_receipts.get("latest")).get("receipt_id")
                ).strip(),
                "active_receipt_id": _safe_str(
                    _as_dict(supervision_authority_grant_receipts.get("active_latest")).get("receipt_id")
                ).strip(),
                "authority_granted": bool(supervision_authority_grant_receipts.get("authority_granted")),
                "execution_authority": False,
                "approval_decision_authority": False,
                "local_process_launch_authority": False,
                "process_supervision_authority": False,
                "process_restart_authority": False,
                "service_install_authority": False,
                "service_control_authority": False,
                "tray_registration_authority": False,
                "hotkey_registration_authority": False,
                "overlay_control_authority": False,
                "memory_write": False,
                "resident_claim_authority": False,
                "denial_receipt_write_authority": False,
                "receipt_write_authority": False,
            },
            {
                "id": "resident_host_supervision_authority_readiness_audit",
                "status": _safe_str(supervision_authority_readiness.get("status")).strip() or "missing",
                "audit_status": _safe_str(supervision_authority_readiness.get("audit_status")).strip(),
                "evidence": [
                    "/lens/host/supervision/authority/readiness",
                    "/lens/host/supervision/authority/requests",
                    "/lens/host/supervision/authority/grants",
                    "/lens/host/supervision/authority/denials",
                    "/lens/host/supervision/authority",
                    "/lens/host/supervision",
                    "/lens/host/manifest",
                    "/lens/status",
                ],
                "ready": bool(supervision_authority_readiness.get("ready")),
                "preflight_ready": bool(supervision_authority_readiness.get("preflight_ready")),
                "authority_ready": bool(supervision_authority_readiness.get("authority_ready")),
                "supervision_ready": bool(supervision_authority_readiness.get("supervision_ready")),
                "resident_claim_allowed": bool(supervision_authority_readiness.get("resident_claim_allowed")),
                "boundary_observed": bool(supervision_authority_readiness.get("boundary_observed")),
                "request_readback_ready": bool(supervision_authority_readiness.get("request_readback_ready")),
                "request_pending_count": _safe_int(supervision_authority_readiness.get("request_pending_count")),
                "request_approved_count": _safe_int(supervision_authority_readiness.get("request_approved_count")),
                "request_total_count": _safe_int(supervision_authority_readiness.get("request_total_count")),
                "latest_request_approval_id": _safe_str(
                    supervision_authority_readiness.get("latest_request_approval_id")
                ).strip(),
                "denial_receipt_readback_ready": bool(
                    supervision_authority_readiness.get("denial_receipt_readback_ready")
                ),
                "grant_receipt_readback_ready": bool(
                    supervision_authority_readiness.get("grant_receipt_readback_ready")
                ),
                "receipt_count": _safe_int(supervision_authority_readiness.get("receipt_count")),
                "latest_receipt_id": _safe_str(supervision_authority_readiness.get("latest_receipt_id")).strip(),
                "grant_receipt_count": _safe_int(supervision_authority_readiness.get("grant_receipt_count")),
                "latest_grant_receipt_id": _safe_str(
                    supervision_authority_readiness.get("latest_grant_receipt_id")
                ).strip(),
                "active_grant_receipt_id": _safe_str(
                    supervision_authority_readiness.get("active_grant_receipt_id")
                ).strip(),
                "requirements_total": _safe_int(supervision_authority_readiness.get("requirements_total")),
                "requirements_ready_total": _safe_int(supervision_authority_readiness.get("requirements_ready_total")),
                "requirements_blocked_total": _safe_int(
                    supervision_authority_readiness.get("requirements_blocked_total")
                ),
                "blocked_requirements": _as_list(supervision_authority_readiness.get("blocked_requirements")),
                "operator_surface_readback_ready": bool(
                    supervision_authority_readiness.get("operator_surface_readback_ready")
                ),
                "first_blocked_requirement": _safe_str(
                    supervision_authority_readiness.get("first_blocked_requirement")
                ).strip(),
                "first_blocked_requirement_handoff": _as_dict(
                    supervision_authority_readiness.get("first_blocked_requirement_handoff")
                ),
                "blocked_requirement_handoffs": _as_list(
                    supervision_authority_readiness.get("blocked_requirement_handoffs")
                ),
                "blockers": _as_list(supervision_authority_readiness.get("blockers")),
                "next_smallest_truthful_gap": _safe_str(
                    supervision_authority_readiness.get("next_smallest_truthful_gap")
                ).strip(),
                "execution_authority": False,
                "approval_decision_authority": False,
                "local_process_launch_authority": False,
                "process_supervision_authority": bool(
                    _as_dict(supervision_authority_readiness.get("governance")).get("process_supervision_authority")
                ),
                "process_restart_authority": bool(
                    _as_dict(supervision_authority_readiness.get("governance")).get("process_restart_authority")
                ),
                "service_install_authority": bool(
                    _as_dict(supervision_authority_readiness.get("governance")).get("service_install_authority")
                ),
                "service_control_authority": bool(
                    _as_dict(supervision_authority_readiness.get("governance")).get("service_control_authority")
                ),
                "tray_registration_authority": False,
                "hotkey_registration_authority": False,
                "overlay_control_authority": False,
                "summon_authority": False,
                "memory_write": False,
                "resident_claim_authority": bool(
                    _as_dict(supervision_authority_readiness.get("governance")).get("resident_claim_authority")
                ),
                "denial_receipt_write_authority": False,
                "receipt_write_authority": bool(
                    _as_dict(supervision_authority_readiness.get("governance")).get("receipt_write_authority")
                ),
            },
            {
                "id": "summon_anywhere",
                "status": "not_implemented",
                "evidence": ["/lens/summon", "/lens/host", "/lens/preflight", "/lens/status"],
                "blockers": [
                    item
                    for item in _as_list(resident_host.get("blockers"))
                    if item
                    in {"resident_host_process_missing", "global_hotkey_binding_missing", "summon_binding_missing"}
                ],
            },
            {
                "id": "summon_enablement_gate",
                "status": _safe_str(summon_enablement_gate.get("status")).strip() or "missing",
                "evidence": ["/lens/summon", "/lens/preflight", "/lens/status"],
                "ready": bool(summon_enablement_gate.get("ready")),
                "summon_anywhere": bool(summon_enablement_gate.get("summon_anywhere")),
                "acceptance_criterion": _safe_str(summon_enablement_gate.get("acceptance_criterion")).strip()
                or "summon_anywhere",
                "next_smallest_truthful_gap": _safe_str(
                    summon_enablement_gate.get("next_smallest_truthful_gap")
                ).strip()
                or "summon_anywhere_blockers",
                "first_blocker_family": _safe_str(summon_enablement_gate.get("first_blocker_family")).strip(),
                "blocked_families": _as_list(summon_enablement_gate.get("blocked_families")),
                "first_blocker_family_handoff_observed": bool(
                    summon_enablement_gate.get("first_blocker_family_handoff_observed")
                ),
                "first_blocker_family_handoff": _as_dict(summon_enablement_gate.get("first_blocker_family_handoff")),
                "blocked_family_handoffs": _as_list(summon_enablement_gate.get("blocked_family_handoffs")),
                "operator_surface_readback_ready": bool(summon_enablement_gate.get("operator_surface_readback_ready")),
                "global_hotkey": _safe_str(summon_enablement_gate.get("global_hotkey")).strip(),
                "blockers": _as_list(summon_enablement_gate.get("blockers")),
                "blocker_groups": _as_dict(summon_enablement_gate.get("blocker_groups")),
                "blocker_family_readback": _as_list(summon_enablement_gate.get("blocker_family_readback")),
                "execution_authority": False,
                "approval_decision_authority": False,
                "local_process_launch_authority": False,
                "hotkey_registration_authority": False,
                "summon_authority": False,
                "overlay_control_authority": False,
            },
            {
                "id": "tray_enablement_gate",
                "status": _safe_str(tray_enablement_gate.get("status")).strip() or "missing",
                "evidence": ["/lens/tray", "/lens/preflight", "/lens/status"],
                "ready": bool(tray_enablement_gate.get("ready")),
                "tray_presence": bool(tray_enablement_gate.get("tray_presence")),
                "presence_name": _safe_str(tray_enablement_gate.get("presence_name")).strip(),
                "blockers": _as_list(tray_enablement_gate.get("blockers")),
                "execution_authority": False,
                "approval_decision_authority": False,
                "local_process_launch_authority": False,
                "service_control_authority": False,
                "tray_registration_authority": False,
                "tray_icon_authority": False,
                "notification_authority": False,
            },
            {
                "id": "overlay_enablement_gate",
                "status": _safe_str(overlay_enablement_gate.get("status")).strip() or "missing",
                "evidence": ["/lens/overlay", "/lens/preflight", "/lens/status"],
                "ready": bool(overlay_enablement_gate.get("ready")),
                "overlay_window": bool(overlay_enablement_gate.get("overlay_window")),
                "overlay_name": _safe_str(overlay_enablement_gate.get("overlay_name")).strip(),
                "blockers": _as_list(overlay_enablement_gate.get("blockers")),
                "execution_authority": False,
                "approval_decision_authority": False,
                "local_process_launch_authority": False,
                "service_control_authority": False,
                "window_management_authority": False,
                "overlay_control_authority": False,
                "capture_authority": False,
                "hotkey_registration_authority": False,
                "tray_registration_authority": False,
            },
            {
                "id": "summon_preflight",
                "status": _safe_str(summon_preflight.get("status")).strip() or "missing",
                "evidence": ["/lens/preflight", "config/runtime/lens/summon.json"],
                "acceptance_criterion": _safe_str(summon_preflight.get("acceptance_criterion")).strip()
                or "summon_anywhere",
                "next_smallest_truthful_gap": _safe_str(summon_preflight.get("next_smallest_truthful_gap")).strip()
                or "summon_anywhere_blockers",
                "global_hotkey": _safe_str(summon_preflight.get("global_hotkey")).strip(),
                "blockers": _as_list(summon_preflight.get("blockers")),
                "blocker_groups": _as_dict(summon_preflight.get("blocker_groups")),
            },
            {
                "id": "tray_preflight",
                "status": _safe_str(tray_preflight.get("status")).strip() or "missing",
                "evidence": ["/lens/preflight", "config/runtime/lens/tray.json"],
                "blockers": _as_list(tray_preflight.get("blockers")),
            },
            {
                "id": "overlay_preflight",
                "status": _safe_str(overlay_preflight.get("status")).strip() or "missing",
                "evidence": ["/lens/preflight", "config/runtime/lens/overlay.json"],
                "blockers": _as_list(overlay_preflight.get("blockers")),
            },
        ],
    }


def _resident_surface_readback_from_status(status: dict[str, Any]) -> dict[str, Any]:
    mode = _as_dict(status.get("mode"))
    scope = _as_dict(status.get("scope"))
    hud = _as_dict(status.get("hud"))
    resident_host = _as_dict(status.get("resident_host"))
    approvals = _as_dict(status.get("approvals_view"))
    incidents = _as_dict(status.get("incident_view"))
    missions = _as_dict(status.get("mission_feed"))
    command_palette = _as_dict(status.get("command_palette"))
    reactor = _as_dict(status.get("reactor"))
    preflight = _as_dict(status.get("preflight"))
    summon_enablement_gate = _as_dict(status.get("summon_enablement_gate"))
    tray_enablement_gate = _as_dict(status.get("tray_enablement_gate"))
    overlay_enablement_gate = _as_dict(status.get("overlay_enablement_gate"))
    resident_surface_activation = _as_dict(status.get("resident_surface_activation"))
    hud_runtime = _as_dict(hud.get("runtime"))
    resident_surface_runtime = _resident_surface_runtime_from_host(resident_host)

    blockers: list[str] = []
    for source in (
        resident_surface_runtime.get("blockers"),
        hud_runtime.get("blockers"),
        resident_host.get("blockers"),
        resident_surface_activation.get("blockers"),
        summon_enablement_gate.get("blockers"),
        tray_enablement_gate.get("blockers"),
        overlay_enablement_gate.get("blockers"),
    ):
        for blocker in _as_list(source):
            blocker_id = _safe_str(blocker).strip()
            if blocker_id and blocker_id not in blockers:
                blockers.append(blocker_id)
    if bool(resident_surface_runtime.get("foreground_runtime_observed")):
        blockers = [blocker for blocker in blockers if blocker != "resident_surface_runtime_missing"]
    elif "resident_surface_runtime_missing" not in blockers:
        blockers.insert(0, "resident_surface_runtime_missing")

    surface_sections = [
        {
            "id": "mode_and_scope",
            "label": "Mode and scope",
            "status": "readback_ready" if mode else "missing",
            "route": "/system/operator_mode",
        },
        {
            "id": "hud_summary",
            "label": "HUD summary",
            "status": _safe_str(hud.get("runtime_status")).strip() or "missing",
            "route": "/lens/hud",
        },
        {
            "id": "approval_queue",
            "label": "Approval queue",
            "status": _safe_str(approvals.get("status")).strip() or "missing",
            "route": _safe_str(approvals.get("route")).strip() or "/approvals/list?status=pending",
            "count": _safe_int(approvals.get("pending_count")),
        },
        {
            "id": "mission_feed",
            "label": "Mission feed",
            "status": "readback_ready",
            "route": _safe_str(missions.get("route")).strip() or "/continuity/briefing",
            "counts": _as_dict(missions.get("counts")),
        },
        {
            "id": "incident_feed",
            "label": "Incident feed",
            "status": _safe_str(incidents.get("status")).strip() or "missing",
            "route": _safe_str(incidents.get("route")).strip() or "/system/observer",
        },
        {
            "id": "command_palette",
            "label": "Command palette",
            "status": _safe_str(command_palette.get("status")).strip() or "missing",
            "route": _safe_str(command_palette.get("route")).strip() or "/lens/status",
            "command_total": _safe_int(command_palette.get("command_total")),
        },
        {
            "id": "resident_host",
            "label": "Resident host",
            "status": _safe_str(resident_host.get("status")).strip() or "missing",
            "route": _safe_str(resident_host.get("route")).strip() or "/lens/host",
        },
        {
            "id": "activation_boundary",
            "label": "Resident surface activation boundary",
            "status": _safe_str(resident_surface_activation.get("status")).strip() or "missing",
            "route": _safe_str(resident_surface_activation.get("route")).strip() or "/lens/resident-surface/activation",
        },
    ]

    return {
        "ok": True,
        "kind": "lens.resident_surface.readback",
        "status": "blocked",
        "contract_status": "readback_ready",
        "availability": "backend_readback_only",
        "route": "/lens/resident-surface",
        "status_route": "/lens/status",
        "activation_route": "/lens/resident-surface/activation",
        "host_route": "/lens/host",
        "hud_route": "/lens/hud",
        "content_contract_ready": True,
        "foreground_runtime_observed": bool(resident_surface_runtime.get("foreground_runtime_observed")),
        "resident_surface_ready": False,
        "resident_claim_allowed": False,
        "resident_overlay_runtime": bool(hud_runtime.get("resident_overlay")),
        "resident_host": bool(resident_host.get("resident")),
        "always_on_top_overlay": bool(hud_runtime.get("always_on_top")),
        "summon_anywhere": bool(command_palette.get("summon_anywhere")),
        "tray_presence": bool(hud_runtime.get("tray_presence")),
        "mode": mode,
        "scope": scope,
        "headline": _safe_str(hud.get("headline")).strip(),
        "badges": [dict(item) for item in _as_list(hud.get("badges")) if isinstance(item, dict)],
        "surface_sections": surface_sections,
        "approval_queue": {
            "status": _safe_str(approvals.get("status")).strip() or "missing",
            "pending_count": _safe_int(approvals.get("pending_count")),
            "route": _safe_str(approvals.get("route")).strip() or "/approvals/list?status=pending",
        },
        "mission_feed": {
            "headline": _safe_str(missions.get("headline")).strip(),
            "counts": _as_dict(missions.get("counts")),
            "route": _safe_str(missions.get("route")).strip() or "/continuity/briefing",
        },
        "incident_feed": {
            "status": _safe_str(incidents.get("status")).strip() or "missing",
            "route": _safe_str(incidents.get("route")).strip() or "/system/observer",
            "reactor_route": _safe_str(incidents.get("reactor_route")).strip()
            or "/reactor/operator_visibility/summary",
        },
        "command_palette": {
            "status": _safe_str(command_palette.get("status")).strip() or "missing",
            "availability": _safe_str(command_palette.get("availability")).strip() or "chat_ui_only",
            "route": _safe_str(command_palette.get("route")).strip() or "/lens/status",
            "command_total": _safe_int(command_palette.get("command_total")),
            "summon_anywhere": bool(command_palette.get("summon_anywhere")),
        },
        "resident_runtime": {
            "preflight_route": "/lens/resident-runtime/preflight",
            "policy_route": "/lens/resident-runtime/policy",
            "authority_grant_route": "/lens/resident-runtime/authority-grant",
            "plan_route": "/lens/resident-runtime/plan",
            "execute_route": "/lens/resident-runtime/execute",
            "ready": False,
        },
        "resident_surface_runtime": resident_surface_runtime,
        "enablement_gates": {
            "preflight": preflight,
            "summon": summon_enablement_gate,
            "tray": tray_enablement_gate,
            "overlay": overlay_enablement_gate,
        },
        "activation_boundary": resident_surface_activation,
        "reactor_readback_surfaces": _as_dict(reactor.get("readback_surfaces")),
        "blockers": blockers,
        "next_smallest_truthful_gap": "resident_surface_runtime_missing",
        "message": "Resident surface content is readable from backend truth, but no resident runtime or OS surface is active.",
        "governance": {
            "gate": "lens_resident_surface_readback",
            "read_only_contract": True,
            "execution_authority": False,
            "approval_decision_authority": False,
            "memory_write": False,
            "overlay_control_authority": False,
            "summon_authority": False,
            "capture_authority": False,
            "local_process_launch_authority": False,
            "process_supervision_authority": False,
            "service_control_authority": False,
            "hotkey_registration_authority": False,
            "tray_registration_authority": False,
            "resident_claim_authority": False,
            "mutation_authority_granted": False,
        },
    }


def _resident_surface_runtime_from_host(resident_host: dict[str, Any]) -> dict[str, Any]:
    process_readback = _as_dict(resident_host.get("process_readback"))
    supervisor_readback = _as_dict(resident_host.get("supervisor_readback"))
    foreground_session = _as_dict(resident_host.get("foreground_session"))
    process_alive = bool(process_readback.get("process_alive"))
    state_status = _safe_str(process_readback.get("state_status")).strip()
    supervisor_status = _safe_str(supervisor_readback.get("status")).strip()
    supervisor_freshness_status = _safe_str(supervisor_readback.get("freshness_status")).strip() or "missing"
    foreground_observed = process_alive and state_status == "foreground_running"
    blockers = (
        ["resident_surface_runtime_not_supervised", "resident_surface_not_resident"]
        if foreground_observed
        else ["resident_surface_runtime_missing"]
    )
    return {
        "ok": True,
        "kind": "lens.resident_surface.runtime_readback",
        "status": "foreground_runtime_observed" if foreground_observed else "missing",
        "readback_ready": True,
        "source": "lens_host_process_readback",
        "host_route": "/lens/host",
        "manifest_route": "/lens/host/manifest",
        "runtime_state_path": _safe_str(process_readback.get("runtime_state_path")).strip(),
        "runtime_state_exists": bool(process_readback.get("state_exists")),
        "runtime_state_status": state_status,
        "runtime_state_updated_at": _safe_str(process_readback.get("state_updated_at")).strip(),
        "pid_path": _safe_str(process_readback.get("pid_path")).strip(),
        "pid_present": bool(process_readback.get("pid_present")),
        "pid": _safe_int(process_readback.get("pid"), maximum=999999),
        "process_alive": process_alive,
        "process_alive_check": _safe_str(process_readback.get("process_alive_check")).strip(),
        "foreground_runtime_observed": foreground_observed,
        "foreground_session_supported": bool(foreground_session.get("supported")),
        "foreground_session_only": foreground_observed,
        "supervisor_readback_status": supervisor_status,
        "supervisor_freshness_status": supervisor_freshness_status,
        "supervisor_state_age_seconds": supervisor_readback.get("state_age_seconds"),
        "supervisor_state_stale": bool(supervisor_readback.get("state_stale")),
        "fresh_supervisor_readback": bool(supervisor_readback.get("fresh_readback")),
        "bounded_supervisor_observed": bool(supervisor_readback.get("bounded_supervisor_observed")),
        "supervised_session_completed": bool(supervisor_readback.get("supervised_session_completed")),
        "resident_runtime_candidate_supervised": bool(supervisor_readback.get("resident_runtime_candidate_supervised")),
        "fresh_bounded_supervisor_observed": bool(supervisor_readback.get("fresh_bounded_supervisor_observed")),
        "fresh_supervised_session_completed": bool(supervisor_readback.get("fresh_supervised_session_completed")),
        "fresh_resident_runtime_candidate_supervised": bool(
            supervisor_readback.get("fresh_resident_runtime_candidate_supervised")
        ),
        "resident_supervised_runtime": False,
        "runtime_ready": False,
        "resident_surface_ready": False,
        "resident_claim_allowed": False,
        "resident_overlay_runtime": False,
        "blockers": blockers,
        "message": (
            "A bounded foreground Lens host process is observable but not resident or supervised."
            if foreground_observed
            else "No Lens foreground or resident surface runtime is currently observed."
        ),
        "governance": {
            "gate": "lens_resident_surface_runtime_readback",
            "read_only_contract": True,
            "execution_authority": False,
            "approval_decision_authority": False,
            "memory_write": False,
            "overlay_control_authority": False,
            "summon_authority": False,
            "capture_authority": False,
            "local_process_launch_authority": False,
            "process_supervision_authority": False,
            "service_control_authority": False,
            "hotkey_registration_authority": False,
            "tray_registration_authority": False,
            "resident_claim_authority": False,
            "mutation_authority_granted": False,
        },
    }


def lens_status(*, limit: int = 5) -> dict[str, Any]:
    safe_limit = _safe_int(limit, default=5, minimum=1, maximum=50)
    operator = _operator_surface()
    reactor = _reactor_surface(limit=safe_limit)
    approvals = _approval_surface(limit=safe_limit)
    incidents = _incident_surface(limit=safe_limit, reactor=reactor)
    missions = _mission_surface(operator)
    mode = _as_dict(operator.get("control_mode"))
    scope = {
        "environment": _as_dict(operator.get("environment")),
        "posture": _as_dict(operator.get("posture")),
        "focus": _as_dict(operator.get("focus")),
        "backlog": _as_dict(operator.get("backlog")),
    }
    hud = _hud_surface(
        mode=mode,
        scope=scope,
        approvals=approvals,
        incidents=incidents,
        missions=missions,
        reactor=reactor,
    )
    command_palette = _command_palette_surface(approvals=approvals)
    resident_host = _resident_host_surface(hud=hud, command_palette=command_palette, limit=safe_limit)
    preflight = lens_preflight()
    os_binding_authority_requests = lens_os_binding_authority_request_readback(limit=safe_limit)
    os_binding_readiness = lens_os_binding_readiness(
        preflight=preflight,
        authority_request_readback=os_binding_authority_requests,
    )
    os_binding_execution_readiness = lens_os_binding_execution_readiness_audit(
        limit=safe_limit,
        authority_request_readback=os_binding_authority_requests,
        readiness=os_binding_readiness,
    )
    os_binding_execution_receipts = lens_os_binding_execution_receipts(limit=safe_limit)
    summon_enablement_gate = lens_summon_enablement_gate(preflight=preflight)
    summon_authority_requests = lens_summon_authority_request_readback(limit=safe_limit)
    summon_execution_receipts = lens_summon_action_execution_receipts(limit=safe_limit)
    tray_enablement_gate = lens_tray_enablement_gate(preflight=preflight)
    tray_authority_requests = lens_tray_authority_request_readback(limit=safe_limit)
    tray_execution_receipts = lens_tray_presence_execution_receipts(limit=safe_limit)
    overlay_enablement_gate = lens_overlay_enablement_gate(preflight=preflight)
    overlay_authority_requests = lens_overlay_authority_request_readback(limit=safe_limit)
    overlay_execution_receipts = lens_overlay_window_execution_receipts(limit=safe_limit)
    resident_surface_activation = lens_resident_surface_activation_boundary(limit=safe_limit)
    pilot_indicator = _pilot_indicator(mode)
    resident_runtime_preflight = _as_dict(resident_host.get("resident_runtime_preflight"))
    resident_runtime_policy = _as_dict(resident_host.get("resident_runtime_policy"))
    resident_runtime_authority_grant = _as_dict(resident_host.get("resident_runtime_authority_grant"))
    resident_runtime_authority_grant_denial_receipts = _as_dict(
        resident_host.get("resident_runtime_authority_grant_denial_receipts")
    )
    resident_runtime_authority_grant_readiness = _as_dict(
        resident_host.get("resident_runtime_authority_grant_readiness")
    )
    resident_runtime_denial_receipts = _as_dict(resident_host.get("resident_runtime_denial_receipts"))
    resident_runtime_execution_receipts = _as_dict(resident_host.get("resident_runtime_execution_receipts"))
    runtime_loop_denial_receipts = _as_dict(resident_host.get("runtime_loop_denial_receipts"))
    runtime_loop_readiness = _as_dict(resident_host.get("runtime_loop_readiness"))
    supervision_authority_denial_receipts = _as_dict(resident_host.get("supervision_authority_denial_receipts"))
    supervision_authority_grant_receipts = _as_dict(resident_host.get("supervision_authority_grant_receipts"))
    supervision_authority_readiness = _as_dict(resident_host.get("supervision_authority_readiness"))
    resident_runtime_plan = _as_dict(resident_host.get("resident_runtime_plan"))

    payload = {
        "ok": True,
        "kind": "lens.status",
        "subsystem": "lens",
        "status": hud["status"],
        "generated_at": time.time(),
        "limit": safe_limit,
        "read_only": True,
        "mode": mode,
        "available_modes": operator.get("available_modes", []),
        "scope": scope,
        "hud": hud,
        "resident_host": resident_host,
        "preflight": preflight,
        "os_binding_readiness": os_binding_readiness,
        "os_binding_execution_readiness": os_binding_execution_readiness,
        "os_binding_execution_receipts": os_binding_execution_receipts,
        "os_binding_authority_requests": os_binding_authority_requests,
        "summon_enablement_gate": summon_enablement_gate,
        "summon_authority_requests": summon_authority_requests,
        "summon_execution_receipts": summon_execution_receipts,
        "tray_enablement_gate": tray_enablement_gate,
        "tray_authority_requests": tray_authority_requests,
        "tray_execution_receipts": tray_execution_receipts,
        "overlay_enablement_gate": overlay_enablement_gate,
        "overlay_authority_requests": overlay_authority_requests,
        "overlay_execution_receipts": overlay_execution_receipts,
        "resident_runtime_preflight": resident_runtime_preflight,
        "resident_runtime_policy": resident_runtime_policy,
        "resident_runtime_authority_requests": _as_dict(resident_host.get("resident_runtime_authority_requests")),
        "resident_runtime_authority_grant": resident_runtime_authority_grant,
        "resident_runtime_authority_grant_receipts": _as_dict(
            resident_host.get("resident_runtime_authority_grant_receipts")
        ),
        "resident_runtime_authority_grant_denial_receipts": resident_runtime_authority_grant_denial_receipts,
        "resident_runtime_authority_grant_readiness": resident_runtime_authority_grant_readiness,
        "resident_runtime_denial_receipts": resident_runtime_denial_receipts,
        "resident_runtime_execution_receipts": resident_runtime_execution_receipts,
        "runtime_loop_denial_receipts": runtime_loop_denial_receipts,
        "runtime_loop_readiness": runtime_loop_readiness,
        "supervision_authority_denial_receipts": supervision_authority_denial_receipts,
        "supervision_authority_grant_receipts": supervision_authority_grant_receipts,
        "supervision_authority_readiness": supervision_authority_readiness,
        "resident_runtime_plan": resident_runtime_plan,
        "resident_runtime_denial": _as_dict(resident_host.get("resident_runtime_denial")),
        "resident_surface_activation": resident_surface_activation,
        "command_palette": command_palette,
        "mode_selector": {
            "status": "readback_ready",
            "active_mode": _safe_str(mode.get("id")).strip(),
            "available_modes": operator.get("available_modes", []),
            "mutation_route": "/system/operator_mode",
            "write_guard": "system.write plus operator posture",
        },
        "approvals_view": approvals,
        "incident_view": incidents,
        "mission_feed": missions,
        "pilot_indicator": pilot_indicator,
        "receipts": {
            "status": "readback_ready",
            "continuity_ledger_route": "/continuity/ledger",
            "reactor_operator_visibility_route": "/reactor/operator_visibility/summary",
            "lens_host_activation_denials_route": "/lens/host/activation/denials",
            "lens_host_runtime_loop_denials_route": "/lens/host/runtime-loop/denials",
            "lens_host_runtime_loop_readiness_route": "/lens/host/runtime-loop/readiness",
            "lens_os_binding_readiness_route": "/lens/os-binding/readiness",
            "lens_os_binding_authority_route": "/lens/os-binding/authority",
            "lens_os_binding_authority_request_route": "/lens/os-binding/authority/request",
            "lens_os_binding_authority_requests_route": "/lens/os-binding/authority/requests",
            "lens_os_binding_execution_readiness_route": "/lens/os-binding/execution/readiness",
            "lens_host_supervision_authority_request_route": "/lens/host/supervision/authority/request",
            "lens_host_supervision_authority_requests_route": "/lens/host/supervision/authority/requests",
            "lens_host_supervision_authority_preflight_route": "/lens/host/supervision/authority",
            "lens_host_supervision_authority_denial_route": "/lens/host/supervision/authority",
            "lens_host_supervision_authority_denials_route": "/lens/host/supervision/authority/denials",
            "lens_host_supervision_authority_grants_route": "/lens/host/supervision/authority/grants",
            "lens_host_supervision_authority_readiness_route": "/lens/host/supervision/authority/readiness",
            "lens_host_persistent_supervision_enablement_authority_route": (
                "/lens/host/persistent-supervision/enablement/authority"
            ),
            "lens_host_persistent_supervision_enablement_authority_request_route": (
                "/lens/host/persistent-supervision/enablement/authority/request"
            ),
            "lens_host_persistent_supervision_enablement_authority_requests_route": (
                "/lens/host/persistent-supervision/enablement/authority/requests"
            ),
            "lens_host_persistent_supervision_enablement_authority_grants_route": (
                "/lens/host/persistent-supervision/enablement/authority/grants"
            ),
            "lens_host_persistent_supervision_enablement_authority_readiness_route": (
                "/lens/host/persistent-supervision/enablement/authority/readiness"
            ),
            "lens_host_persistent_supervision_enablement_execution_route": (
                "/lens/host/persistent-supervision/enablement/execution"
            ),
            "lens_host_persistent_supervision_enablement_execution_request_route": (
                "/lens/host/persistent-supervision/enablement/execution/request"
            ),
            "lens_host_persistent_supervision_enablement_execution_requests_route": (
                "/lens/host/persistent-supervision/enablement/execution/requests"
            ),
            "lens_host_persistent_supervision_enablement_execution_authority_route": (
                "/lens/host/persistent-supervision/enablement/execution/authority"
            ),
            "lens_host_persistent_supervision_enablement_execution_authority_grants_route": (
                "/lens/host/persistent-supervision/enablement/execution/authority/grants"
            ),
            "lens_host_persistent_supervision_enablement_execution_readiness_route": (
                "/lens/host/persistent-supervision/enablement/execution/readiness"
            ),
            "lens_resident_runtime_authority_grant_request_route": ("/lens/resident-runtime/authority-grant/request"),
            "lens_resident_runtime_authority_grant_requests_route": ("/lens/resident-runtime/authority-grant/requests"),
            "lens_resident_runtime_authority_grant_grants_route": ("/lens/resident-runtime/authority-grant/grants"),
            "lens_resident_runtime_authority_grant_denials_route": ("/lens/resident-runtime/authority-grant/denials"),
            "lens_resident_runtime_authority_grant_readiness_route": (
                "/lens/resident-runtime/authority-grant/readiness"
            ),
            "lens_resident_runtime_denials_route": "/lens/resident-runtime/denials",
            "lens_resident_runtime_executions_route": "/lens/resident-runtime/executions",
            "lens_tray_authority_request_route": "/lens/tray/authority/request",
            "lens_tray_authority_requests_route": "/lens/tray/authority/requests",
            "lens_tray_authority_route": "/lens/tray/authority",
            "lens_tray_authority_grants_route": "/lens/tray/authority/grants",
            "lens_tray_executions_route": "/lens/tray/executions",
            "lens_tray_execute_route": "/lens/tray/execute",
            "lens_overlay_authority_request_route": "/lens/overlay/authority/request",
            "lens_overlay_authority_requests_route": "/lens/overlay/authority/requests",
            "lens_overlay_authority_route": "/lens/overlay/authority",
            "lens_overlay_authority_grants_route": "/lens/overlay/authority/grants",
            "lens_overlay_executions_route": "/lens/overlay/executions",
            "lens_overlay_execute_route": "/lens/overlay/execute",
            "lens_summon_authority_request_route": "/lens/summon/authority/request",
            "lens_summon_authority_requests_route": "/lens/summon/authority/requests",
            "lens_summon_authority_route": "/lens/summon/authority",
            "lens_summon_authority_grants_route": "/lens/summon/authority/grants",
            "lens_summon_executions_route": "/lens/summon/executions",
            "lens_summon_execute_route": "/lens/summon/execute",
            "lens_resident_surface_route": "/lens/resident-surface",
            "lens_resident_surface_activation_route": "/lens/resident-surface/activation",
            "reactor_readback_surfaces": _as_dict(reactor.get("readback_surfaces")),
        },
        "reactor": reactor,
        "stage6_readiness": _stage6_readiness(
            mode=mode,
            hud=hud,
            resident_host=resident_host,
            approvals=approvals,
            incidents=incidents,
            missions=missions,
            reactor=reactor,
            command_palette=command_palette,
            preflight=preflight,
            os_binding_readiness=os_binding_readiness,
            os_binding_execution_readiness=os_binding_execution_readiness,
            os_binding_authority_requests=os_binding_authority_requests,
            summon_enablement_gate=summon_enablement_gate,
            summon_authority_requests=summon_authority_requests,
            tray_enablement_gate=tray_enablement_gate,
            tray_authority_requests=tray_authority_requests,
            overlay_enablement_gate=overlay_enablement_gate,
            overlay_authority_requests=overlay_authority_requests,
            resident_surface_activation=resident_surface_activation,
            pilot_indicator=pilot_indicator,
        ),
        "governance": {
            "gate": "lens_readback_only",
            "execution_authority": False,
            "approval_decision_authority": False,
            "memory_write": False,
            "overlay_control_authority": False,
            "capture_authority": False,
            "new_sensing_authority": False,
        },
    }
    payload["resident_surface"] = _resident_surface_readback_from_status(payload)
    return payload


def lens_resident_surface_readback(*, limit: int = 5) -> dict[str, Any]:
    status = lens_status(limit=limit)
    return dict(_as_dict(status.get("resident_surface")))


def lens_host_status(*, limit: int = 5) -> dict[str, Any]:
    status = lens_status(limit=limit)
    host = dict(_as_dict(status.get("resident_host")))
    host["generated_at"] = status.get("generated_at")
    host["limit"] = status.get("limit")
    return host
