from __future__ import annotations

import time
from typing import Any

from francis.governance.approval_projection import approval_projection_fields
from francis.governance.approvals import list_requests
from francis.governance.redaction import redact_governed_display_value
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

    return {
        "status": "attention" if pending_approvals or active_incidents or review_queue_total else "ready",
        "headline": headline,
        "primary_plane": _safe_str(focus.get("plane_id")).strip() or "P1_INTERFACE",
        "primary_plane_label": _safe_str(focus.get("label")).strip() or "Interface",
        "badges": badges,
        "readback_ready": True,
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


def _stage6_readiness(
    *,
    mode: dict[str, Any],
    approvals: dict[str, Any],
    incidents: dict[str, Any],
    missions: dict[str, Any],
    reactor: dict[str, Any],
) -> dict[str, Any]:
    return {
        "stage": "Stage 6 / Lens MVP",
        "claim": "backend_readback_contract_only",
        "criteria": [
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
                "evidence": [],
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
        "command_palette": {
            "status": "contract_ready",
            "summon_anywhere": False,
            "message": "Readback contract exists; OS-wide summon and overlay binding are not implemented here.",
            "route": "/lens/status",
        },
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
            approvals=approvals,
            incidents=incidents,
            missions=missions,
            reactor=reactor,
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
