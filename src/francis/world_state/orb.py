from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import yaml

from francis.kernel.paths import repo_root
from francis.world_state.operator_mode import snapshot as operator_mode_snapshot
from francis.world_state.snapshot import observer_incident_snapshot, observer_summary


_CORE_LOOP_IDS = (
    "P1_INTERFACE",
    "P4_COGNITION",
    "P3_GOVERNANCE",
    "P2_IDENTITY",
    "P7_EXECUTION",
    "P9_OBSERVABILITY",
    "P8_MEMORY",
)

_PREFERRED_GATES = (
    "permission_gate",
    "trust_gate",
    "approvals_gate",
    "audit_log",
    "sandbox_execute",
)
_PRESSURE_LEVEL_RANK = {"clear": 0, "info": 1, "warning": 2, "error": 3, "critical": 4}


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""


def _safe_int(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return 0
        try:
            return int(float(text))
        except Exception:
            return 0
    return 0


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path.as_posix())
    raw = yaml.safe_load(path.read_text(encoding="utf-8", errors="replace"))
    if not isinstance(raw, dict):
        raise ValueError(f"invalid_yaml_root:{path.as_posix()}")
    return raw


def _string_list(value: Any, *, limit: int | None = None) -> list[str]:
    if not isinstance(value, list):
        return []
    out = [_safe_str(item).strip() for item in value]
    cleaned = [item for item in out if item]
    if limit is None:
        return cleaned
    return cleaned[: max(0, int(limit))]


def _plane_summaries(plane_map: dict[str, Any]) -> list[dict[str, Any]]:
    raw_planes = plane_map.get("planes")
    if not isinstance(raw_planes, list):
        return []

    out: list[dict[str, Any]] = []
    for item in raw_planes:
        if not isinstance(item, dict):
            continue
        plane_id = _safe_str(item.get("id")).strip()
        if not plane_id:
            continue
        out.append(
            {
                "id": plane_id,
                "name": _safe_str(item.get("name")).strip(),
                "category": _safe_str(item.get("category")).strip(),
                "purpose": _safe_str(item.get("purpose")).strip(),
                "side_effects_allowed": bool(item.get("side_effects_allowed")),
                "default_risk_class": _safe_str(item.get("default_risk_class")).strip(),
                "primary_modules": _string_list(item.get("primary_modules"), limit=4),
            }
        )
    return out


def _transition_summaries(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    out: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        from_plane = _safe_str(item.get("from")).strip()
        to_plane = _safe_str(item.get("to")).strip()
        if not from_plane or not to_plane:
            continue
        out.append(
            {
                "from": from_plane,
                "to": to_plane,
                "conditions": _string_list(item.get("conditions"), limit=5),
                "reason": _safe_str(item.get("reason")).strip(),
            }
        )
    return out


def _gate_summaries(action_taxonomy: dict[str, Any]) -> list[dict[str, Any]]:
    raw_controls = action_taxonomy.get("controls")
    if not isinstance(raw_controls, list):
        return []

    by_id: dict[str, dict[str, Any]] = {}
    for item in raw_controls:
        if not isinstance(item, dict):
            continue
        control_id = _safe_str(item.get("id")).strip()
        if not control_id:
            continue
        by_id[control_id] = {
            "id": control_id,
            "description": _safe_str(item.get("description")).strip(),
        }

    ordered = [by_id[gate_id] for gate_id in _PREFERRED_GATES if gate_id in by_id]
    for control_id, summary in by_id.items():
        if control_id in _PREFERRED_GATES:
            continue
        ordered.append(summary)
    return ordered


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _pressure_rank(level: Any) -> int:
    return _PRESSURE_LEVEL_RANK.get(_safe_str(level).strip().lower(), 0)


def _presence_actionable_incident(item: dict[str, Any]) -> bool:
    category = _safe_str(item.get("category")).strip().lower()
    probe = _safe_str(item.get("probe")).strip().lower()
    return category == "governance" or probe == "task_runtime"


def _observer_presence() -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        snapshot = observer_incident_snapshot()
        incidents = _as_list(snapshot.get("incidents"))
        actionable_snapshot = {
            "incidents": [
                dict(item) for item in incidents if isinstance(item, dict) and _presence_actionable_incident(item)
            ]
        }
        return observer_summary(snapshot), observer_summary(actionable_snapshot)
    except Exception:
        empty = {
            "headline": "",
            "decision": "",
            "counts": {"active": 0, "critical": 0, "error": 0, "warning": 0, "info": 0},
            "focus": [],
            "incident_ids": [],
            "probes": [],
            "anomaly": {"score": 0, "level": "clear", "reasons": []},
        }
        return empty, empty


def _incident_pressure(backlog: dict[str, Any], observer: dict[str, Any]) -> dict[str, Any]:
    pending_approvals = _safe_int(backlog.get("pending_approvals"))
    approval_pending_tasks = _safe_int(backlog.get("approval_pending_tasks"))
    blocked_tasks = _safe_int(backlog.get("blocked_tasks"))
    blocked_missions = _safe_int(backlog.get("blocked_missions"))
    deadlettered_missions = _safe_int(backlog.get("deadlettered_missions"))

    if blocked_tasks > 0 or blocked_missions > 0 or deadlettered_missions > 0:
        level = "error"
    elif pending_approvals > 0 or approval_pending_tasks > 0:
        level = "warning"
    else:
        level = "info"

    pressure = {
        "level": level,
        "source": "backlog",
        "pending_approvals": pending_approvals,
        "approval_pending_tasks": approval_pending_tasks,
        "blocked_tasks": blocked_tasks,
        "blocked_missions": blocked_missions,
        "deadlettered_missions": deadlettered_missions,
    }

    observer_counts = _as_dict(observer.get("counts"))
    observer_anomaly = _as_dict(observer.get("anomaly"))
    observer_focus = _as_list(observer.get("focus"))
    observer_level = _safe_str(observer_anomaly.get("level")).strip().lower()
    observer_score = _safe_int(observer_anomaly.get("score"))
    observer_active = _safe_int(observer_counts.get("active"))
    observer_headline = _safe_str(observer.get("headline")).strip()
    observer_decision = _safe_str(observer.get("decision")).strip()
    observer_reasons = [
        _safe_str(item).strip() for item in observer_anomaly.get("reasons", []) if _safe_str(item).strip()
    ]
    observer_focus_item = dict(observer_focus[0]) if observer_focus and isinstance(observer_focus[0], dict) else {}
    observer_focus_title = (
        _safe_str(observer_focus_item.get("title")).strip() or _safe_str(observer_focus_item.get("id")).strip()
    )

    if observer_headline or observer_score > 0 or observer_active > 0:
        pressure["observer"] = {
            "level": observer_level or "clear",
            "score": observer_score,
            "active": observer_active,
            "decision": observer_decision,
            "headline": observer_headline,
            "reasons": observer_reasons,
            "focus_title": observer_focus_title,
        }

    if _pressure_rank(observer_level) >= _pressure_rank(level) and (observer_score > 0 or observer_active > 0):
        pressure["level"] = observer_level or pressure["level"]
        pressure["source"] = "observer"
        if observer_headline:
            pressure["headline"] = observer_headline
        if observer_reasons:
            pressure["reasons"] = observer_reasons
        if observer_decision:
            pressure["decision"] = observer_decision
        if observer_focus_title:
            pressure["focus_title"] = observer_focus_title

    return pressure


def _activity_intensity(backlog: dict[str, Any]) -> dict[str, Any]:
    running_tasks = _safe_int(backlog.get("running_tasks"))
    active_missions = _safe_int(backlog.get("active_missions"))
    queued_tasks = _safe_int(backlog.get("queued_tasks"))
    queued_missions = _safe_int(backlog.get("queued_missions"))
    blocked_missions = _safe_int(backlog.get("blocked_missions"))
    deadlettered_missions = _safe_int(backlog.get("deadlettered_missions"))
    completed_missions = _safe_int(backlog.get("completed_missions"))

    if running_tasks > 0 or active_missions > 0:
        level = "active_execution"
    elif blocked_missions > 0 or deadlettered_missions > 0:
        level = "handoff"
    elif queued_tasks > 0 or queued_missions > 0:
        level = "staged"
    elif completed_missions > 0:
        level = "handoff"
    else:
        level = "ambient"

    return {
        "level": level,
        "running_tasks": running_tasks,
        "active_missions": active_missions,
        "queued_tasks": queued_tasks,
        "queued_missions": queued_missions,
        "blocked_missions": blocked_missions,
        "deadlettered_missions": deadlettered_missions,
        "completed_missions": completed_missions,
    }


def _interjection_state(incident_pressure: dict[str, Any], focus: dict[str, Any]) -> dict[str, Any]:
    level = _safe_str(incident_pressure.get("level")).strip().lower()
    if level in {"warning", "error", "critical"}:
        observer = _as_dict(incident_pressure.get("observer"))
        reason = (
            _safe_str(focus.get("reason")).strip()
            or _safe_str(incident_pressure.get("headline")).strip()
            or _safe_str(observer.get("headline")).strip()
        )
        return {
            "state": "attention_required",
            "reason": reason,
        }
    return {
        "state": "ambient",
        "reason": "",
    }


def _handback_state(continuity: dict[str, Any]) -> dict[str, Any]:
    headline = _safe_str(continuity.get("headline")).strip()
    focus_items = [item for item in _as_list(continuity.get("focus")) if isinstance(item, dict)]
    recently_completed = [item for item in _as_list(continuity.get("recently_completed")) if isinstance(item, dict)]
    failed_preview = [item for item in _as_list(continuity.get("failed_preview")) if isinstance(item, dict)]
    deadletter_preview = [item for item in _as_list(continuity.get("deadletter_preview")) if isinstance(item, dict)]

    focus_item = dict(focus_items[0]) if focus_items else {}
    if focus_item:
        status = _safe_str(focus_item.get("status")).strip().lower()
        state = "operator_action_required" if status in {"blocked", "failed", "deadlettered"} else "continuity_ready"
    elif failed_preview:
        state = "failed_recovery"
    elif deadletter_preview:
        state = "deadletter_review"
    elif recently_completed:
        state = "completion_review"
    else:
        state = "none"

    return {
        "state": state,
        "headline": headline,
        "focus": focus_item,
        "recently_completed_count": len(recently_completed),
        "failed_count": len(failed_preview),
        "deadletter_count": len(deadletter_preview),
    }


def _render_state(
    incident_pressure: dict[str, Any], activity_intensity: dict[str, Any], handback_state: dict[str, Any]
) -> str:
    if _safe_str(activity_intensity.get("level")).strip().lower() == "active_execution":
        return "active_execution"
    if _safe_str(handback_state.get("state")).strip().lower() != "none":
        return "handback"
    if _safe_str(incident_pressure.get("level")).strip().lower() in {"warning", "error", "critical"}:
        return "handback"
    return "ambient_rest"


def _orb_live_state(operator_report: dict[str, Any]) -> dict[str, Any]:
    control_mode = _as_dict(operator_report.get("control_mode"))
    focus = _as_dict(operator_report.get("focus"))
    backlog = _as_dict(operator_report.get("backlog"))
    continuity = _as_dict(operator_report.get("continuity"))
    observer, actionable_observer = _observer_presence()

    incident_pressure = _incident_pressure(backlog, actionable_observer)
    activity_intensity = _activity_intensity(backlog)
    handback_state = _handback_state(continuity)

    return {
        "mode": {
            "id": _safe_str(control_mode.get("id")).strip(),
            "label": _safe_str(control_mode.get("label")).strip(),
            "writes": _safe_str(control_mode.get("writes")).strip(),
            "implementation_status": _safe_str(control_mode.get("implementation_status")).strip(),
        },
        "incident_pressure": incident_pressure,
        "activity_intensity": activity_intensity,
        "execution_focus": {
            "plane_id": _safe_str(focus.get("plane_id")).strip(),
            "label": _safe_str(focus.get("label")).strip(),
            "reason": _safe_str(focus.get("reason")).strip(),
        },
        "observer": observer,
        "interjection_state": _interjection_state(incident_pressure, focus),
        "handback_state": handback_state,
        "render_state": _render_state(incident_pressure, activity_intensity, handback_state),
    }


def snapshot() -> dict[str, Any]:
    root = repo_root()
    plane_map_path = root / "meta" / "plane_map.yaml"
    action_taxonomy_path = root / "meta" / "action_taxonomy.yaml"

    plane_map = _read_yaml(plane_map_path)
    action_taxonomy = _read_yaml(action_taxonomy_path)

    planes = _plane_summaries(plane_map)
    plane_by_id = {item["id"]: item for item in planes if item.get("id")}
    operator_report = operator_mode_snapshot()

    return {
        "ok": True,
        "subsystem": "orb_status",
        "generated_at": time.time(),
        "repo_root": str(root),
        "model": {
            "plane_map_id": _safe_str(
                plane_map.get("meta", {}).get("model_id") if isinstance(plane_map.get("meta"), dict) else ""
            ),
            "plane_map_version": _safe_int(plane_map.get("meta", {}).get("version"))
            if isinstance(plane_map.get("meta"), dict)
            else 0,
            "action_taxonomy_id": _safe_str(
                action_taxonomy.get("meta", {}).get("taxonomy_id")
                if isinstance(action_taxonomy.get("meta"), dict)
                else ""
            ),
            "action_taxonomy_version": _safe_int(action_taxonomy.get("meta", {}).get("version"))
            if isinstance(action_taxonomy.get("meta"), dict)
            else 0,
        },
        "core_loop": [plane_by_id[plane_id] for plane_id in _CORE_LOOP_IDS if plane_id in plane_by_id],
        "planes": planes,
        "gates": _gate_summaries(action_taxonomy),
        "transitions": {
            "allowed": _transition_summaries(plane_map.get("transitions")),
            "forbidden": _transition_summaries(plane_map.get("forbidden_transitions")),
        },
        "state": _orb_live_state(operator_report),
    }
