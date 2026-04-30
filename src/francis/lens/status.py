from __future__ import annotations

import time
from typing import Any

from francis.governance.approval_projection import approval_projection_fields
from francis.governance.approvals import list_requests
from francis.governance.redaction import redact_governed_display_value
from francis.lens.activation import (
    deny_lens_host_activation_execution,
    deny_lens_host_supervision_authority_grant,
    deny_lens_resident_runtime_activation_execution,
    deny_lens_resident_runtime_execution_authority_grant,
    lens_host_activation_denial_receipts,
    lens_host_activation_execution_preflight,
    lens_host_activation_execution_plan,
    lens_host_activation_readback,
    lens_host_activation_request_contract,
    lens_host_supervision_authority_denial_receipts,
    lens_host_supervision_authority_grant_receipts,
    lens_host_supervision_authority_request_contract,
    lens_host_supervision_authority_request_readback,
    lens_host_supervision_authority_readiness_audit,
    lens_resident_runtime_activation_denial_receipts,
    lens_resident_runtime_authority_grant_denial_receipts,
    lens_resident_runtime_authority_grant_readiness_audit,
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
from francis.lens.preflight import (
    lens_overlay_enablement_gate,
    lens_preflight,
    lens_summon_enablement_gate,
    lens_tray_enablement_gate,
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
    supervision_gate = lens_host_supervision_gate(manifest=launch_manifest)
    persistent_supervision_plan = lens_host_persistent_supervision_plan(manifest=launch_manifest)
    persistent_supervision_enablement = lens_host_persistent_supervision_enablement_preflight(manifest=launch_manifest)
    supervision_authority_preflight = lens_host_supervision_authority_preflight(manifest=launch_manifest)
    supervision_authority_request = lens_host_supervision_authority_request_contract()
    supervision_authority_requests = lens_host_supervision_authority_request_readback(limit=limit)
    supervision_authority_denial = deny_lens_host_supervision_authority_grant()
    supervision_authority_denial_receipts = lens_host_supervision_authority_denial_receipts(limit=limit)
    supervision_authority_grant_receipts = lens_host_supervision_authority_grant_receipts(limit=limit)
    supervision_authority_readiness = lens_host_supervision_authority_readiness_audit(limit=limit)
    activation_request = lens_host_activation_request_contract()
    activation_state = lens_host_activation_readback(limit=limit)
    activation_execution_preflight = lens_host_activation_execution_preflight()
    activation_execution_plan = lens_host_activation_execution_plan()
    resident_runtime_preflight = lens_resident_runtime_activation_preflight()
    resident_runtime_policy = lens_resident_runtime_execution_policy_contract()
    resident_runtime_authority_grant = deny_lens_resident_runtime_execution_authority_grant()
    resident_runtime_plan = lens_resident_runtime_activation_plan()
    resident_runtime_denial = deny_lens_resident_runtime_activation_execution()
    resident_runtime_denial_receipts = lens_resident_runtime_activation_denial_receipts(limit=limit)
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
    supervision_readiness = _as_dict(launch_manifest.get("supervision_readiness"))
    process_alive = bool(process_readback.get("process_alive"))
    blockers = [
        "lens_host_runtime_not_implemented",
        "tray_host_missing",
        "global_hotkey_binding_missing",
        "always_on_top_window_missing",
        "overlay_window_missing",
        "summon_binding_missing",
    ]
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
            "id": "tray_presence",
            "label": "Tray or equivalent presence",
            "status": "missing",
            "required_for": ["operator_visibility", "lifecycle_control"],
        },
        {
            "id": "global_hotkey",
            "label": "Global summon hotkey",
            "status": "missing",
            "required_for": ["summon_anywhere"],
        },
        {
            "id": "overlay_window",
            "label": "Always-on-top Lens window",
            "status": "missing",
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
        "activation_execution_preflight_route": _safe_str(activation_execution_preflight.get("route")).strip(),
        "activation_execution_preflight": activation_execution_preflight,
        "activation_execution_plan_route": _safe_str(activation_execution_plan.get("route")).strip(),
        "activation_execution_plan": activation_execution_plan,
        "resident_runtime_preflight_route": _safe_str(resident_runtime_preflight.get("route")).strip(),
        "resident_runtime_preflight": resident_runtime_preflight,
        "resident_runtime_policy_route": _safe_str(resident_runtime_policy.get("route")).strip(),
        "resident_runtime_policy": resident_runtime_policy,
        "resident_runtime_authority_grant_route": _safe_str(resident_runtime_authority_grant.get("route")).strip(),
        "resident_runtime_authority_grant": resident_runtime_authority_grant,
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
        "activation_execution_denial_route": _safe_str(activation_execution_denial.get("route")).strip(),
        "activation_execution_denial": activation_execution_denial,
        "activation_denial_receipts_route": _safe_str(activation_denial_receipts.get("route")).strip(),
        "activation_denial_receipts": activation_denial_receipts,
        "launch_manifest_route": _safe_str(launch_manifest.get("route")).strip() or "/lens/host/manifest",
        "launch_manifest": launch_manifest,
        "supervision_gate_route": _safe_str(supervision_gate.get("route")).strip(),
        "supervision_gate": supervision_gate,
        "persistent_supervision_plan_route": _safe_str(persistent_supervision_plan.get("route")).strip(),
        "persistent_supervision_plan": persistent_supervision_plan,
        "persistent_supervision_enablement_route": _safe_str(persistent_supervision_enablement.get("route")).strip(),
        "persistent_supervision_enablement": persistent_supervision_enablement,
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
        "supervision_readiness": supervision_readiness,
        "foreground_session": _as_dict(launch_manifest.get("foreground_session")),
        "resident": False,
        "process_supervision": False,
        "startup_integration": False,
        "tray_presence": False,
        "global_hotkey": False,
        "always_on_top_overlay": False,
        "overlay_window": False,
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
    ]
    group_counts: dict[str, int] = {}
    for command in commands:
        group = _safe_str(command.get("group")).strip() or "Other"
        group_counts[group] = group_counts.get(group, 0) + 1

    return {
        "status": "readback_ready",
        "availability": "chat_ui_only",
        "summon_anywhere": False,
        "message": "Palette command readback exists; OS-wide summon and overlay binding are not implemented here.",
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
    summon_enablement_gate: dict[str, Any],
    tray_enablement_gate: dict[str, Any],
    overlay_enablement_gate: dict[str, Any],
    resident_surface_activation: dict[str, Any],
) -> dict[str, Any]:
    hud_runtime = _as_dict(hud.get("runtime"))
    preflight_surfaces = _as_dict(preflight.get("surfaces"))
    summon_preflight = _as_dict(preflight_surfaces.get("summon"))
    tray_preflight = _as_dict(preflight_surfaces.get("tray"))
    overlay_preflight = _as_dict(preflight_surfaces.get("overlay"))
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
    supervision_authority_denial = _as_dict(resident_host.get("supervision_authority_denial"))
    supervision_authority_denial_receipts = _as_dict(resident_host.get("supervision_authority_denial_receipts"))
    supervision_authority_grant_receipts = _as_dict(resident_host.get("supervision_authority_grant_receipts"))
    supervision_authority_preflight = _as_dict(resident_host.get("supervision_authority_preflight"))
    supervision_authority_readiness = _as_dict(resident_host.get("supervision_authority_readiness"))
    return {
        "stage": "Stage 6 / Lens MVP",
        "claim": "backend_readback_contract_only",
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
                "id": "resident_runtime_execution_authority_grant_boundary",
                "status": _safe_str(resident_runtime_authority_grant.get("status")).strip() or "missing",
                "evidence": [
                    "/lens/resident-runtime/authority-grant",
                    "/lens/resident-runtime/policy",
                    "/lens/status",
                ],
                "boundary_ready": bool(resident_runtime_authority_grant.get("boundary_ready")),
                "applied": bool(resident_runtime_authority_grant.get("applied")),
                "executed": bool(resident_runtime_authority_grant.get("executed")),
                "authority_granted": bool(resident_runtime_authority_grant.get("authority_granted")),
                "grant_ready": bool(resident_runtime_authority_grant.get("grant_ready")),
                "authority_grant_ready": bool(resident_runtime_authority_grant.get("authority_grant_ready")),
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
                "blockers": _as_list(supervision_authority_readiness.get("blockers")),
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
                "global_hotkey": _safe_str(summon_enablement_gate.get("global_hotkey")).strip(),
                "blockers": _as_list(summon_enablement_gate.get("blockers")),
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
                "global_hotkey": _safe_str(summon_preflight.get("global_hotkey")).strip(),
                "blockers": _as_list(summon_preflight.get("blockers")),
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
    foreground_session = _as_dict(resident_host.get("foreground_session"))
    process_alive = bool(process_readback.get("process_alive"))
    state_status = _safe_str(process_readback.get("state_status")).strip()
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
    summon_enablement_gate = lens_summon_enablement_gate(preflight=preflight)
    tray_enablement_gate = lens_tray_enablement_gate(preflight=preflight)
    overlay_enablement_gate = lens_overlay_enablement_gate(preflight=preflight)
    resident_surface_activation = lens_resident_surface_activation_boundary(limit=safe_limit)
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
        "summon_enablement_gate": summon_enablement_gate,
        "tray_enablement_gate": tray_enablement_gate,
        "overlay_enablement_gate": overlay_enablement_gate,
        "resident_runtime_preflight": resident_runtime_preflight,
        "resident_runtime_policy": resident_runtime_policy,
        "resident_runtime_authority_grant": resident_runtime_authority_grant,
        "resident_runtime_authority_grant_denial_receipts": resident_runtime_authority_grant_denial_receipts,
        "resident_runtime_authority_grant_readiness": resident_runtime_authority_grant_readiness,
        "resident_runtime_denial_receipts": resident_runtime_denial_receipts,
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
        "pilot_indicator": _pilot_indicator(mode),
        "receipts": {
            "status": "readback_ready",
            "continuity_ledger_route": "/continuity/ledger",
            "reactor_operator_visibility_route": "/reactor/operator_visibility/summary",
            "lens_host_activation_denials_route": "/lens/host/activation/denials",
            "lens_host_supervision_authority_request_route": "/lens/host/supervision/authority/request",
            "lens_host_supervision_authority_requests_route": "/lens/host/supervision/authority/requests",
            "lens_host_supervision_authority_preflight_route": "/lens/host/supervision/authority",
            "lens_host_supervision_authority_denial_route": "/lens/host/supervision/authority",
            "lens_host_supervision_authority_denials_route": "/lens/host/supervision/authority/denials",
            "lens_host_supervision_authority_grants_route": "/lens/host/supervision/authority/grants",
            "lens_host_supervision_authority_readiness_route": "/lens/host/supervision/authority/readiness",
            "lens_resident_runtime_authority_grant_denials_route": ("/lens/resident-runtime/authority-grant/denials"),
            "lens_resident_runtime_authority_grant_readiness_route": (
                "/lens/resident-runtime/authority-grant/readiness"
            ),
            "lens_resident_runtime_denials_route": "/lens/resident-runtime/denials",
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
            summon_enablement_gate=summon_enablement_gate,
            tray_enablement_gate=tray_enablement_gate,
            overlay_enablement_gate=overlay_enablement_gate,
            resident_surface_activation=resident_surface_activation,
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
