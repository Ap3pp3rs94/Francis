from __future__ import annotations

import time
from typing import Any

from francis.governance.approval_projection import approval_projection_fields
from francis.governance.approvals import list_requests
from francis.governance.redaction import redact_governed_display_value
from francis.lens.host_manifest import lens_host_launch_manifest
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


def _resident_host_surface(*, hud: dict[str, Any], command_palette: dict[str, Any]) -> dict[str, Any]:
    launch_manifest = lens_host_launch_manifest()
    status_runner_present = _safe_str(launch_manifest.get("status")).strip() == "status_runner_present"
    service_install = _as_dict(launch_manifest.get("service_install"))
    service_config_present = bool(service_install.get("config_exists"))
    process_readback = _as_dict(launch_manifest.get("process_readback"))
    blockers = [
        "lens_host_runtime_not_implemented",
        "resident_host_process_missing",
        "tray_host_missing",
        "global_hotkey_binding_missing",
        "always_on_top_window_missing",
        "overlay_window_missing",
        "summon_binding_missing",
    ]
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
            "id": "host_process_readback",
            "label": "Host process readback",
            "status": "readback_ready",
            "required_for": ["resident_presence", "startup_supervision"],
        },
        {
            "id": "host_process",
            "label": "Resident host process",
            "status": "missing",
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
        "launch_manifest_route": _safe_str(launch_manifest.get("route")).strip() or "/lens/host/manifest",
        "launch_manifest": launch_manifest,
        "status_route": "/lens/status",
        "local_hud_route": _safe_str(hud.get("route")).strip() or "/lens/hud",
        "local_palette_route": _safe_str(command_palette.get("route")).strip() or "/lens/status",
        "handoff_target": "chat_ui.system_orb",
        "status_runner_present": status_runner_present,
        "service_config_present": service_config_present,
        "service_config_path": _safe_str(service_install.get("config_path")).strip(),
        "process_readback": process_readback,
        "process_readback_ready": bool(process_readback.get("readback_ready")),
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
) -> dict[str, Any]:
    hud_runtime = _as_dict(hud.get("runtime"))
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
                "id": "summon_anywhere",
                "status": "not_implemented",
                "evidence": ["/lens/host", "/lens/status"],
                "blockers": [
                    item
                    for item in _as_list(resident_host.get("blockers"))
                    if item
                    in {"resident_host_process_missing", "global_hotkey_binding_missing", "summon_binding_missing"}
                ],
            },
        ],
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
    resident_host = _resident_host_surface(hud=hud, command_palette=command_palette)

    return {
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


def lens_host_status(*, limit: int = 5) -> dict[str, Any]:
    status = lens_status(limit=limit)
    host = dict(_as_dict(status.get("resident_host")))
    host["generated_at"] = status.get("generated_at")
    host["limit"] = status.get("limit")
    return host
