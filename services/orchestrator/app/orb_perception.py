from __future__ import annotations
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

_DEFAULT_PERCEPTION: dict[str, Any] = {
    "captured_at": None,
    "display_id": None,
    "display": {
        "width": 0,
        "height": 0,
    },
    "cursor": {"x": None, "y": None},
    "idle_seconds": 0,
    "target_stability": {
        "state": "idle",
        "dwell_ms": 0,
        "travel_px": 0,
        "sample_count": 0,
    },
    "window": {
        "title": "",
        "process": "",
        "pid": None,
        "bounds": {
            "x": None,
            "y": None,
            "width": 0,
            "height": 0,
        },
    },
    "frame": {
        "width": 0,
        "height": 0,
        "data_url": "",
    },
    "focus": {
        "width": 0,
        "height": 0,
        "data_url": "",
    },
    "accessibility": {
        "available": False,
        "attached": False,
        "status": "unavailable",
        "label": "",
        "name": "",
        "automation_id": "",
        "control_type": "",
        "localized_control_type": "",
        "class_name": "",
        "process_id": None,
        "has_keyboard_focus": False,
        "enabled": False,
        "offscreen": False,
        "bounds": {
            "x": None,
            "y": None,
            "width": 0,
            "height": 0,
        },
    },
    "environment": {
        "source_priority": [],
        "primary_source": "",
        "sources": {
            "accessibility": {},
            "window_metadata": {},
            "visual_focus": {},
            "display_capture": {},
        },
        "grounding": {
            "state": "weak",
            "score": 0.0,
            "summary": "",
            "detail": "",
            "in_window": False,
            "on_display": False,
            "continuity_state": "unavailable",
            "invalidation_reason": "",
        },
    },
}

_latest_perception: dict[str, Any] = deepcopy(_DEFAULT_PERCEPTION)


def _parse_iso_timestamp(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _normalize_dimension(value: Any) -> int:
    return max(0, int(value or 0)) if isinstance(value, (int, float)) else 0


def _normalize_optional_int(value: Any) -> int | None:
    if not isinstance(value, (int, float)):
        return None
    number = int(value)
    return number if number >= 0 else None


def _normalize_optional_signed_int(value: Any) -> int | None:
    if not isinstance(value, (int, float)):
        return None
    return int(value)


def _normalize_ratio(value: Any) -> float:
    if not isinstance(value, (int, float)):
        return 0.0
    return round(max(0.0, min(1.0, float(value))), 3)


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_bounds(value: Any) -> dict[str, Any]:
    raw = value if isinstance(value, dict) else {}
    return {
        "x": _normalize_optional_signed_int(raw.get("x")) if raw.get("x") is not None else None,
        "y": _normalize_optional_signed_int(raw.get("y")) if raw.get("y") is not None else None,
        "width": _normalize_dimension(raw.get("width")),
        "height": _normalize_dimension(raw.get("height")),
    }


def _normalize_accessibility_payload(value: Any) -> dict[str, Any]:
    record = value if isinstance(value, dict) else {}
    bounds = _normalize_bounds(record.get("bounds"))
    available = bool(record.get("available", False))
    attached = bool(record.get("attached", False)) and bounds["width"] > 0 and bounds["height"] > 0
    status = _normalize_text(record.get("status")).lower() or ("attached" if attached else "idle" if available else "unavailable")
    control_type = _normalize_text(record.get("control_type") or record.get("controlType")).lower()
    return {
        "available": available,
        "attached": attached,
        "status": status,
        "label": _normalize_text(record.get("label") or record.get("name")),
        "name": _normalize_text(record.get("name")),
        "automation_id": _normalize_text(record.get("automation_id") or record.get("automationId")),
        "control_type": control_type,
        "localized_control_type": _normalize_text(record.get("localized_control_type") or record.get("localizedControlType")),
        "class_name": _normalize_text(record.get("class_name") or record.get("className")),
        "process_id": _normalize_optional_int(record.get("process_id") if record.get("process_id") is not None else record.get("processId")),
        "has_keyboard_focus": bool(record.get("has_keyboard_focus") if record.get("has_keyboard_focus") is not None else record.get("hasKeyboardFocus")),
        "enabled": bool(record.get("enabled", False)),
        "offscreen": bool(record.get("offscreen", False)),
        "bounds": bounds,
    }


def _normalize_environment_source(value: Any) -> dict[str, Any]:
    record = value if isinstance(value, dict) else {}
    return {
        "attached": bool(record.get("attached", False)),
        "available": bool(record.get("available", False)),
        "summary": _normalize_text(record.get("summary")),
        "label": _normalize_text(record.get("label")),
        "control_type": _normalize_text(record.get("control_type") or record.get("controlType")).lower(),
        "process_match": bool(record.get("process_match") if record.get("process_match") is not None else record.get("processMatch")),
        "in_window": bool(record.get("in_window") if record.get("in_window") is not None else record.get("inWindow")),
        "cursor_inside": bool(record.get("cursor_inside") if record.get("cursor_inside") is not None else record.get("cursorInside")),
        "cursor_distance_px": _normalize_dimension(record.get("cursor_distance_px") if record.get("cursor_distance_px") is not None else record.get("cursorDistancePx")),
        "on_display": bool(record.get("on_display") if record.get("on_display") is not None else record.get("onDisplay")),
        "overlap_ratio": _normalize_ratio(record.get("overlap_ratio") if record.get("overlap_ratio") is not None else record.get("overlapRatio")),
        "continuity_state": _normalize_text(record.get("continuity_state") or record.get("continuityState")).lower(),
    }


def _normalize_environment_payload(value: Any) -> dict[str, Any]:
    record = value if isinstance(value, dict) else {}
    raw_sources = record.get("sources", {}) if isinstance(record.get("sources"), dict) else {}
    raw_priority = record.get("source_priority") if isinstance(record.get("source_priority"), list) else record.get("sourcePriority")
    source_priority = [
        _normalize_text(item).lower()
        for item in (raw_priority if isinstance(raw_priority, list) else [])
        if _normalize_text(item)
    ]
    grounding = record.get("grounding", {}) if isinstance(record.get("grounding"), dict) else {}
    grounding_state = _normalize_text(grounding.get("state")).lower()
    if grounding_state not in {"grounded", "tracking", "weak", "stale", "detached", "reassess"}:
        grounding_state = "weak"
    on_display_value = grounding.get("on_display") if grounding.get("on_display") is not None else grounding.get("onDisplay")
    return {
        "source_priority": source_priority,
        "primary_source": _normalize_text(record.get("primary_source") or record.get("primarySource")).lower(),
        "sources": {
            "accessibility": _normalize_environment_source(raw_sources.get("accessibility")),
            "window_metadata": _normalize_environment_source(raw_sources.get("window_metadata") or raw_sources.get("windowMetadata")),
            "visual_focus": _normalize_environment_source(raw_sources.get("visual_focus") or raw_sources.get("visualFocus")),
            "display_capture": _normalize_environment_source(raw_sources.get("display_capture") or raw_sources.get("displayCapture")),
        },
        "grounding": {
            "state": grounding_state,
            "score": _normalize_ratio(grounding.get("score")),
            "summary": _normalize_text(grounding.get("summary")),
            "detail": _normalize_text(grounding.get("detail")),
            "in_window": bool(grounding.get("in_window") if grounding.get("in_window") is not None else grounding.get("inWindow")),
            "on_display": True if on_display_value is None else bool(on_display_value),
            "continuity_state": _normalize_text(grounding.get("continuity_state") or grounding.get("continuityState")).lower() or "unavailable",
            "invalidation_reason": _normalize_text(grounding.get("invalidation_reason") or grounding.get("invalidationReason")).lower(),
        },
    }


def _bounds_contains(bounds: dict[str, Any], x: int | None, y: int | None) -> bool:
    bound_x = bounds.get("x")
    bound_y = bounds.get("y")
    width = _normalize_dimension(bounds.get("width"))
    height = _normalize_dimension(bounds.get("height"))
    return bool(
        x is not None
        and y is not None
        and bound_x is not None
        and bound_y is not None
        and width > 0
        and height > 0
        and bound_x <= x <= bound_x + width
        and bound_y <= y <= bound_y + height
    )


def _bounds_area(bounds: dict[str, Any]) -> int:
    return _normalize_dimension(bounds.get("width")) * _normalize_dimension(bounds.get("height"))


def _bounds_overlap_ratio(subject: dict[str, Any], container: dict[str, Any]) -> float:
    subject_area = _bounds_area(subject)
    if subject_area <= 0:
        return 0.0
    subject_x = subject.get("x")
    subject_y = subject.get("y")
    container_x = container.get("x")
    container_y = container.get("y")
    if subject_x is None or subject_y is None or container_x is None or container_y is None:
        return 0.0
    overlap_width = max(
        0,
        min(subject_x + _normalize_dimension(subject.get("width")), container_x + _normalize_dimension(container.get("width")))
        - max(subject_x, container_x),
    )
    overlap_height = max(
        0,
        min(subject_y + _normalize_dimension(subject.get("height")), container_y + _normalize_dimension(container.get("height")))
        - max(subject_y, container_y),
    )
    return _normalize_ratio((overlap_width * overlap_height) / subject_area)


def _normalize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    frame = payload.get("frame", {}) if isinstance(payload.get("frame"), dict) else {}
    focus = payload.get("focus", {}) if isinstance(payload.get("focus"), dict) else {}
    cursor = payload.get("cursor", {}) if isinstance(payload.get("cursor"), dict) else {}
    window = payload.get("window", {}) if isinstance(payload.get("window"), dict) else {}
    display = payload.get("display", {}) if isinstance(payload.get("display"), dict) else {}
    accessibility = payload.get("accessibility", {}) if isinstance(payload.get("accessibility"), dict) else {}
    environment = payload.get("environment", {}) if isinstance(payload.get("environment"), dict) else {}
    target_stability = (
        payload.get("target_stability", {})
        if isinstance(payload.get("target_stability"), dict)
        else {}
    )

    captured_at = str(payload.get("captured_at", "")).strip() or None
    display_id = _normalize_optional_int(payload.get("display_id"))
    idle_seconds = _normalize_dimension(payload.get("idle_seconds"))
    cursor_x = _normalize_optional_int(cursor.get("x"))
    cursor_y = _normalize_optional_int(cursor.get("y"))
    window_title = str(window.get("title", "")).strip()
    process_name = str(window.get("process", "")).strip()
    window_pid = _normalize_optional_int(window.get("pid"))
    window_bounds = _normalize_bounds(window.get("bounds"))

    return {
        "captured_at": captured_at,
        "display_id": display_id,
        "display": {
            "width": _normalize_dimension(display.get("width")),
            "height": _normalize_dimension(display.get("height")),
        },
        "cursor": {
            "x": cursor_x,
            "y": cursor_y,
        },
        "idle_seconds": idle_seconds,
        "target_stability": {
            "state": str(target_stability.get("state", "idle")).strip().lower() or "idle",
            "dwell_ms": _normalize_dimension(target_stability.get("dwell_ms")),
            "travel_px": _normalize_dimension(target_stability.get("travel_px")),
            "sample_count": _normalize_dimension(target_stability.get("sample_count")),
        },
        "window": {
            "title": window_title,
            "process": process_name,
            "pid": window_pid,
            "bounds": window_bounds,
        },
        "frame": {
            "width": _normalize_dimension(frame.get("width")),
            "height": _normalize_dimension(frame.get("height")),
            "data_url": str(frame.get("data_url", "")).strip(),
        },
        "focus": {
            "width": _normalize_dimension(focus.get("width")),
            "height": _normalize_dimension(focus.get("height")),
            "data_url": str(focus.get("data_url", "")).strip(),
        },
        "accessibility": _normalize_accessibility_payload(accessibility),
        "environment": _normalize_environment_payload(environment),
    }


def _build_freshness(captured_at: str | None) -> dict[str, Any]:
    parsed = _parse_iso_timestamp(captured_at)
    if parsed is None:
        return {
            "state": "idle",
            "age_ms": None,
            "summary": "No active visual perception frame is attached.",
        }

    age_ms = max(0, int((datetime.now(UTC) - parsed).total_seconds() * 1000))
    if age_ms <= 2500:
        state = "fresh"
    elif age_ms <= 15000:
        state = "cooling"
    else:
        state = "stale"

    if age_ms < 1000:
        age_summary = "under 1s old"
    else:
        age_summary = f"{age_ms / 1000:.1f}s old"

    return {
        "state": state,
        "age_ms": age_ms,
        "summary": f"Latest active-display perception frame is {age_summary}.",
    }


def _format_display_label(display_id: int | None, display: dict[str, Any]) -> str:
    width = _normalize_dimension(display.get("width"))
    height = _normalize_dimension(display.get("height"))
    label = f"Display {display_id}" if display_id is not None else "Active display"
    if width > 0 and height > 0:
        return f"{label} | {width}x{height}"
    return label


def _format_window_label(window: dict[str, Any]) -> str:
    title = str(window.get("title", "")).strip()
    process_name = str(window.get("process", "")).strip()
    pid = _normalize_optional_int(window.get("pid"))
    bounds = window.get("bounds", {}) if isinstance(window.get("bounds"), dict) else {}
    width = _normalize_dimension(bounds.get("width"))
    height = _normalize_dimension(bounds.get("height"))
    parts = []
    if title:
        parts.append(title)
    if process_name:
        parts.append(process_name)
    if pid:
        parts.append(f"pid {pid}")
    if width > 0 and height > 0:
        parts.append(f"{width}x{height}")
    return " | ".join(parts) if parts else "No foreground window metadata"


def _clamp_ratio(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _confidence_score(value: Any) -> float:
    normalized = str(value or "").strip().lower()
    if normalized in {"high", "likely", "locked"}:
        return 0.92
    if normalized in {"medium", "tracking"}:
        return 0.64
    if normalized in {"low", "weak"}:
        return 0.28
    return 0.18


def _stability_score(value: Any) -> float:
    normalized = str(value or "").strip().lower()
    if normalized == "settled":
        return 0.94
    if normalized == "tracking":
        return 0.62
    if normalized == "transient":
        return 0.2
    return 0.08


def _freshness_score(value: Any) -> float:
    normalized = str(value or "").strip().lower()
    if normalized == "fresh":
        return 1.0
    if normalized == "cooling":
        return 0.72
    return 0.18


def _build_target_grounding_contract(
    *,
    payload: dict[str, Any],
    freshness: dict[str, Any],
    target: dict[str, Any],
    focus_attached: bool,
) -> dict[str, Any]:
    window = payload.get("window", {}) if isinstance(payload.get("window"), dict) else {}
    window_bounds = window.get("bounds", {}) if isinstance(window.get("bounds"), dict) else {}
    accessibility = payload.get("accessibility", {}) if isinstance(payload.get("accessibility"), dict) else {}
    accessibility_bounds = accessibility.get("bounds", {}) if isinstance(accessibility.get("bounds"), dict) else {}
    environment = payload.get("environment", {}) if isinstance(payload.get("environment"), dict) else {}
    environment_grounding = environment.get("grounding", {}) if isinstance(environment.get("grounding"), dict) else {}
    environment_sources = environment.get("sources", {}) if isinstance(environment.get("sources"), dict) else {}
    target_window = target.get("window", {}) if isinstance(target.get("window"), dict) else {}
    target_stability = target.get("stability", {}) if isinstance(target.get("stability"), dict) else {}
    freshness_state = _normalize_text(freshness.get("state")).lower() or "idle"
    stability_state = _normalize_text(target_stability.get("state")).lower() or "idle"
    frame = payload.get("frame", {}) if isinstance(payload.get("frame"), dict) else {}
    x = _normalize_optional_int((payload.get("cursor", {}) if isinstance(payload.get("cursor"), dict) else {}).get("x"))
    y = _normalize_optional_int((payload.get("cursor", {}) if isinstance(payload.get("cursor"), dict) else {}).get("y"))
    environment_state = _normalize_text(environment_grounding.get("state")).lower() or "weak"
    environment_score = _normalize_ratio(environment_grounding.get("score"))
    source_priority = [
        _normalize_text(item).lower()
        for item in environment.get("source_priority", [])
        if isinstance(environment.get("source_priority"), list) and _normalize_text(item)
    ]
    primary_source = _normalize_text(environment.get("primary_source")).lower()
    if not source_priority:
        for name in ("accessibility", "window_metadata", "visual_focus", "display_capture"):
            source = environment_sources.get(name, {}) if isinstance(environment_sources.get(name), dict) else {}
            if bool(source.get("attached")) or bool(source.get("available")):
                source_priority.append(name)

    accessibility_attached = bool(accessibility.get("attached"))
    accessibility_process_id = _normalize_optional_int(accessibility.get("process_id"))
    window_pid = _normalize_optional_int(window.get("pid"))
    accessibility_process_match = bool(
        accessibility_attached
        and (window_pid is None or accessibility_process_id is None or window_pid == accessibility_process_id)
    )
    cursor_in_accessibility = _bounds_contains(accessibility_bounds, x, y)
    accessibility_in_window = bool(
        accessibility.get("attached")
        and _bounds_overlap_ratio(accessibility_bounds, window_bounds) >= 0.55
    )
    in_window = bool(target_window.get("in_bounds"))
    frame_attached = bool(_normalize_text(frame.get("data_url")))
    if not source_priority:
        if accessibility_attached and accessibility_process_match and (cursor_in_accessibility or accessibility_in_window):
            source_priority.append("accessibility")
        if _bounds_area(window_bounds) > 0:
            source_priority.append("window_metadata")
        if focus_attached:
            source_priority.append("visual_focus")
        if frame_attached:
            source_priority.append("display_capture")
    if not primary_source and source_priority:
        primary_source = source_priority[0]
    if environment_score <= 0:
        environment_score = _normalize_ratio(
            (0.34 if in_window else 0.08 if _bounds_area(window_bounds) > 0 else 0.0)
            + (0.22 if focus_attached else 0.0)
            + (
                0.26
                if accessibility_attached and accessibility_process_match and (cursor_in_accessibility or accessibility_in_window)
                else 0.0
            )
            + (0.08 if frame_attached else 0.0)
        )
    on_display = bool(environment_grounding.get("on_display", True))
    if not on_display and environment_state not in {"stale", "detached"}:
        environment_state = "detached"

    hybrid_score = _normalize_ratio(
        environment_score * 0.52
        + _stability_score(stability_state) * 0.22
        + _freshness_score(freshness_state) * 0.16
        + (0.08 if focus_attached else 0.0)
        + (0.08 if accessibility_attached and accessibility_process_match else 0.0)
    )

    if freshness_state == "stale":
        state = "stale"
        invalidation_reason = "stale_frame"
    elif environment_state == "detached" or (
        window_bounds.get("width", 0) > 0
        and not in_window
        and not cursor_in_accessibility
    ):
        state = "detached"
        invalidation_reason = _normalize_text(environment_grounding.get("invalidation_reason")).lower() or "cursor_left_foreground_window"
    elif (
        hybrid_score >= 0.78
        and stability_state == "settled"
        and (in_window or cursor_in_accessibility or accessibility_in_window)
        and (focus_attached or (accessibility_attached and accessibility_process_match))
    ):
        state = "grounded"
        invalidation_reason = ""
    elif (
        hybrid_score >= 0.52
        and stability_state in {"settled", "tracking"}
        and (in_window or cursor_in_accessibility or accessibility_in_window)
    ):
        state = "tracking"
        invalidation_reason = ""
    elif environment_state == "reassess" or stability_state == "transient" or hybrid_score >= 0.34:
        state = "reassess"
        invalidation_reason = _normalize_text(environment_grounding.get("invalidation_reason")).lower() or (
            "transient_cursor" if stability_state == "transient" else "grounding_not_settled"
        )
    else:
        state = "weak"
        invalidation_reason = _normalize_text(environment_grounding.get("invalidation_reason")).lower() or "weak_environment_evidence"

    if state == "grounded":
        summary = "Accessibility, window, and visual evidence align on the current target."
        detail = (
            f"Francis has a stable foreground target with {primary_source.replace('_', ' ') or 'hybrid'} evidence "
            "anchoring the lock."
        )
    elif state == "tracking":
        summary = "Foreground evidence plausibly tracks the current target."
        detail = (
            f"Francis sees enough environmental evidence to follow the target through {primary_source.replace('_', ' ') or 'window metadata'}, "
            "but it is not fully concrete yet."
        )
    elif state == "detached":
        summary = "The current target drifted outside the grounded foreground path."
        detail = "Cursor, window, or focused control evidence is detached from the active target region."
    elif state == "stale":
        summary = "The latest perception frame is stale."
        detail = "Francis will not promote a stale visual target into lock until a fresher frame arrives."
    elif state == "reassess":
        summary = "Environmental evidence is present, but Francis should reassess before locking."
        detail = "The target remains visible, but the current evidence is still in motion or only partially grounded."
    else:
        summary = "Environmental grounding is weak."
        detail = "Francis is holding below hard lock because the current target evidence is shallow."

    return {
        "state": state,
        "score": hybrid_score,
        "summary": summary,
        "detail": detail,
        "source_priority": source_priority,
        "primary_source": primary_source,
        "invalidation_reason": invalidation_reason,
        "in_window": in_window,
        "on_display": on_display,
        "accessibility_attached": accessibility_attached,
        "accessibility_process_match": accessibility_process_match,
        "cursor_in_accessibility": cursor_in_accessibility,
        "accessibility_in_window": accessibility_in_window,
        "control_ready": bool(
            state == "grounded"
            and stability_state == "settled"
            and freshness_state in {"fresh", "cooling"}
            and (in_window or cursor_in_accessibility or accessibility_in_window)
        ),
    }


def _infer_surface_contract(payload: dict[str, Any]) -> dict[str, str]:
    window = payload.get("window", {}) if isinstance(payload.get("window"), dict) else {}
    process_name = str(window.get("process", "")).strip().lower()
    title = str(window.get("title", "")).strip()
    lowered_title = title.lower()

    if process_name in {"code.exe", "cursor.exe", "devenv.exe", "pycharm64.exe", "idea64.exe"}:
        return {
            "kind": "editor",
            "intent": "code_editing",
            "label": "Editor surface",
            "summary": f"Foreground work looks like a code editor: {title or process_name}.",
            "confidence": "likely",
        }
    if process_name in {"windows terminal.exe", "wt.exe", "powershell.exe", "cmd.exe", "bash.exe"}:
        return {
            "kind": "terminal",
            "intent": "command_entry",
            "label": "Terminal surface",
            "summary": f"Foreground work looks like a terminal session: {title or process_name}.",
            "confidence": "likely",
        }
    if process_name in {"chrome.exe", "msedge.exe", "firefox.exe", "brave.exe"}:
        return {
            "kind": "browser",
            "intent": "web_navigation",
            "label": "Browser surface",
            "summary": f"Foreground work looks like a browser tab: {title or process_name}.",
            "confidence": "likely",
        }
    if process_name in {"explorer.exe"}:
        return {
            "kind": "files",
            "intent": "file_navigation",
            "label": "File surface",
            "summary": f"Foreground work looks like file navigation: {title or process_name}.",
            "confidence": "likely",
        }
    if "francis" in lowered_title or process_name in {"electron.exe"}:
        return {
            "kind": "francis",
            "intent": "operator_control",
            "label": "Francis surface",
            "summary": f"Foreground work appears to be a Francis control surface: {title or process_name}.",
            "confidence": "medium",
        }
    return {
        "kind": "application",
        "intent": "visible_work",
        "label": "Application surface",
        "summary": f"Foreground work is visible through {title or process_name or 'the active application'}.",
        "confidence": "medium" if title or process_name else "low",
    }


def _build_target_contract(payload: dict[str, Any], freshness: dict[str, Any], surface: dict[str, str]) -> dict[str, Any]:
    cursor = payload.get("cursor", {}) if isinstance(payload.get("cursor"), dict) else {}
    focus = payload.get("focus", {}) if isinstance(payload.get("focus"), dict) else {}
    window = payload.get("window", {}) if isinstance(payload.get("window"), dict) else {}
    window_bounds = window.get("bounds", {}) if isinstance(window.get("bounds"), dict) else {}
    x = _normalize_optional_int(cursor.get("x"))
    y = _normalize_optional_int(cursor.get("y"))
    stability = payload.get("target_stability", {}) if isinstance(payload.get("target_stability"), dict) else {}
    stability_state = str(stability.get("state", "idle")).strip().lower() or "idle"
    dwell_ms = _normalize_dimension(stability.get("dwell_ms"))
    travel_px = _normalize_dimension(stability.get("travel_px"))
    focus_attached = bool(str(focus.get("data_url", "")).strip())
    freshness_state = str(freshness.get("state", "idle")).strip().lower() or "idle"
    window_x = window_bounds.get("x") if isinstance(window_bounds.get("x"), int) else None
    window_y = window_bounds.get("y") if isinstance(window_bounds.get("y"), int) else None
    window_width = _normalize_dimension(window_bounds.get("width"))
    window_height = _normalize_dimension(window_bounds.get("height"))
    cursor_window_x = x - window_x if x is not None and window_x is not None else None
    cursor_window_y = y - window_y if y is not None and window_y is not None else None
    in_window = bool(
        cursor_window_x is not None
        and cursor_window_y is not None
        and 0 <= cursor_window_x <= max(1, window_width)
        and 0 <= cursor_window_y <= max(1, window_height)
    )
    label_map = {
        "editor": "Editor focus point",
        "terminal": "Terminal focus point",
        "browser": "Browser focus point",
        "files": "File focus point",
        "francis": "Francis focus point",
        "application": "Active focus point",
    }
    label = label_map.get(str(surface.get("kind", "")).strip().lower(), "Active focus point")
    coordinate_summary = f"({x}, {y})" if x is not None and y is not None else "unresolved coordinates"
    crop_summary = "Local focus crop is attached." if focus_attached else "No local focus crop is attached."
    stability_summary = (
        f" Cursor target is settled after {dwell_ms}ms with {travel_px}px of recent travel."
        if stability_state == "settled"
        else f" Cursor target is still tracking with {travel_px}px of recent travel."
        if stability_state == "tracking"
        else f" Cursor target is transient with {travel_px}px of recent travel."
        if stability_state == "transient"
        else " Cursor target stability is not attached yet."
    )
    window_summary = (
        f" Cursor is inside the foreground window at ({cursor_window_x}, {cursor_window_y})."
        if in_window and cursor_window_x is not None and cursor_window_y is not None
        else " Cursor is not mapped cleanly into the foreground window."
        if window_width > 0 and window_height > 0
        else " Foreground-window bounds are unavailable."
    )
    target = {
        "kind": "cursor_focus",
        "label": label,
        "summary": f"{label} at {coordinate_summary}. {crop_summary}{stability_summary}{window_summary}",
        "actionable": False,
        "confidence": "low",
        "stability": {
            "state": stability_state,
            "dwell_ms": dwell_ms,
            "travel_px": travel_px,
            "sample_count": _normalize_dimension(stability.get("sample_count")),
            "summary": stability_summary.strip(),
        },
        "window": {
            "x": cursor_window_x,
            "y": cursor_window_y,
            "in_bounds": in_window,
        },
    }
    grounding = _build_target_grounding_contract(
        payload=payload,
        freshness=freshness,
        target=target,
        focus_attached=focus_attached,
    )
    actionable = bool(
        x is not None
        and y is not None
        and freshness_state in {"fresh", "cooling"}
        and grounding["state"] not in {"stale", "detached"}
        and (in_window or grounding["cursor_in_accessibility"] or grounding["accessibility_in_window"])
    )
    confidence = (
        "likely"
        if grounding["state"] == "grounded"
        else "medium"
        if grounding["state"] == "tracking"
        else "low"
    )
    target = {
        "kind": "cursor_focus",
        "label": label,
        "summary": (
            f"{label} at {coordinate_summary}. {crop_summary}{stability_summary}{window_summary} "
            f"{grounding['summary']}"
        ).strip(),
        "actionable": actionable,
        "confidence": confidence,
        "stability": {
            "state": stability_state,
            "dwell_ms": dwell_ms,
            "travel_px": travel_px,
            "sample_count": _normalize_dimension(stability.get("sample_count")),
            "summary": stability_summary.strip(),
        },
        "window": {
            "x": cursor_window_x,
            "y": cursor_window_y,
            "in_bounds": in_window,
        },
        "grounding": grounding,
    }
    zone = _infer_target_zone(payload, surface, target)
    affordances = _build_target_affordances(surface=surface, target=target, zone=zone, x=x, y=y)
    affordance_summary = (
        f" Suggested actions: {', '.join(str(item.get('label', '')).strip() for item in affordances if isinstance(item, dict) and str(item.get('label', '')).strip())}."
        if affordances
        else ""
    )
    target["summary"] = f"{target['summary']} {zone['summary']}{affordance_summary}".strip()
    target["zone"] = zone
    target["affordances"] = affordances
    target["attention"] = _build_target_attention_contract(
        target=target,
        surface=surface,
        zone=zone,
        affordances=affordances,
        freshness_state=freshness_state,
        focus_attached=focus_attached,
    )
    return target


def _build_target_attention_contract(
    *,
    target: dict[str, Any],
    surface: dict[str, str],
    zone: dict[str, Any],
    affordances: list[dict[str, Any]],
    freshness_state: str,
    focus_attached: bool,
) -> dict[str, Any]:
    target_window = target.get("window", {}) if isinstance(target.get("window"), dict) else {}
    target_stability = target.get("stability", {}) if isinstance(target.get("stability"), dict) else {}
    target_grounding = target.get("grounding", {}) if isinstance(target.get("grounding"), dict) else {}
    target_label = str(target.get("label", "active focus point")).strip() or "active focus point"
    zone_label = str(zone.get("label", "active zone")).strip() or "active zone"
    surface_label = str(surface.get("label", "application surface")).strip() or "application surface"
    confidence = str(target.get("confidence", "low")).strip().lower() or "low"
    stability_state = str(target_stability.get("state", "idle")).strip().lower() or "idle"
    grounding_state = str(target_grounding.get("state", "weak")).strip().lower() or "weak"
    grounding_score = _normalize_ratio(target_grounding.get("score"))
    actionable = bool(target.get("actionable"))
    in_window = bool(target_window.get("in_bounds"))
    primary_affordance = next(
        (
            row
            for row in affordances
            if isinstance(row, dict) and str(row.get("label", "")).strip()
        ),
        None,
    )
    action_label = (
        str(primary_affordance.get("label", "")).strip()
        if isinstance(primary_affordance, dict)
        else ""
    )
    focal_label = action_label or zone_label or target_label
    confidence_score = _confidence_score(confidence)
    stability_score = _stability_score(stability_state)
    freshness_score = _freshness_score(freshness_state)
    focus_bonus = 0.12 if focus_attached else 0.0
    window_bonus = 0.16 if in_window else -0.08
    actionable_bonus = 0.14 if actionable else -0.12
    attention_strength = _clamp_ratio(
        confidence_score * 0.22
        + stability_score * 0.2
        + freshness_score * 0.12
        + grounding_score * 0.28
        + focus_bonus
        + window_bonus
        + actionable_bonus
    )
    lock_strength = _clamp_ratio(
        confidence_score * 0.26
        + stability_score * 0.22
        + grounding_score * 0.34
        + (0.12 if in_window else -0.1)
        + (0.08 if focus_attached else 0.0)
        + (0.06 if actionable else -0.12)
    )
    uncertainty = _clamp_ratio(
        1.0
        - (
            confidence_score * 0.22
            + stability_score * 0.16
            + freshness_score * 0.1
            + grounding_score * 0.34
            + (0.1 if in_window else -0.08)
            + (0.08 if actionable else -0.12)
        )
    )

    if grounding_state == "grounded" and actionable and stability_state == "settled" and confidence in {"likely", "high"}:
        state = "target_lock"
        salience = "high"
        summary = f"Locked on {focal_label.lower()}."
        detail = (
            f"{target_label} is stable inside the foreground {surface_label.lower()}, "
            f"so Francis is compressing onto {focal_label.lower()}."
        )
    elif grounding_state == "tracking" and confidence in {"likely", "medium", "high"} and stability_state in {"tracking", "settled"}:
        state = "investigate"
        salience = "high" if attention_strength >= 0.72 else "medium"
        summary = f"Investigating {focal_label.lower()}."
        detail = (
            f"{target_label} matters inside the foreground {surface_label.lower()}, "
            "and Francis is narrowing the attention arc while confidence settles."
        )
    elif actionable or grounding_state in {"reassess", "weak", "detached", "stale"}:
        state = "reassess"
        salience = "medium" if attention_strength >= 0.38 else "low"
        if grounding_state == "stale":
            reason = "the latest perception frame is stale"
        elif grounding_state == "detached":
            reason = "the focus point is detached from the foreground window"
        elif grounding_state == "weak":
            reason = "environment evidence is still too weak"
        elif stability_state == "transient":
            reason = "the cursor is still transient"
        elif not in_window:
            reason = "the focus point drifted outside the foreground window"
        else:
            reason = "confidence is not grounded yet"
        summary = f"Reassessing {focal_label.lower()}."
        detail = f"Francis is easing off {focal_label.lower()} because {reason}."
    else:
        state = "idle"
        salience = "low"
        summary = "No grounded target is attached yet."
        detail = "Francis is holding ambient attention until a stable focus point appears."

    if state == "target_lock":
        uncertainty = min(uncertainty, 0.22)
    elif state == "investigate":
        uncertainty = max(uncertainty, 0.28)
    elif state == "reassess":
        uncertainty = max(uncertainty, 0.56)

    return {
        "state": state,
        "salience": salience,
        "strength": round(attention_strength, 3),
        "lock_strength": round(lock_strength, 3),
        "uncertainty": round(uncertainty, 3),
        "summary": summary,
        "detail": detail,
        "focus_label": focal_label,
        "confidence": confidence,
        "stability": stability_state,
    }


def _infer_target_zone(payload: dict[str, Any], surface: dict[str, str], target: dict[str, Any]) -> dict[str, Any]:
    cursor = payload.get("cursor", {}) if isinstance(payload.get("cursor"), dict) else {}
    display = payload.get("display", {}) if isinstance(payload.get("display"), dict) else {}
    target_window = target.get("window", {}) if isinstance(target.get("window"), dict) else {}
    width = max(1, _normalize_dimension(display.get("width")))
    height = max(1, _normalize_dimension(display.get("height")))
    x = _normalize_optional_int(cursor.get("x"))
    y = _normalize_optional_int(cursor.get("y"))
    window_x = _normalize_optional_int(target_window.get("x"))
    window_y = _normalize_optional_int(target_window.get("y"))
    in_window = bool(target_window.get("in_bounds"))
    window = payload.get("window", {}) if isinstance(payload.get("window"), dict) else {}
    window_bounds = window.get("bounds", {}) if isinstance(window.get("bounds"), dict) else {}
    window_width = max(1, _normalize_dimension(window_bounds.get("width")))
    window_height = max(1, _normalize_dimension(window_bounds.get("height")))
    x_ratio = (window_x / window_width) if in_window and window_x is not None else (x / width) if x is not None else 0.5
    y_ratio = (window_y / window_height) if in_window and window_y is not None else (y / height) if y is not None else 0.5
    surface_kind = str(surface.get("kind", "")).strip().lower() or "application"

    zone_kind = "application_content"
    zone_label = "Application content"
    zone_summary = "The cursor is inside the active application content region."

    if surface_kind == "editor":
        if y_ratio <= 0.1:
            zone_kind = "editor_tabstrip"
            zone_label = "Editor tab strip"
            zone_summary = "The cursor is near the editor tab strip and top-level editor controls."
        elif x_ratio <= 0.12:
            zone_kind = "editor_gutter"
            zone_label = "Editor gutter"
            zone_summary = "The cursor is near the editor gutter where line-focused actions usually land."
        else:
            zone_kind = "editor_body"
            zone_label = "Editor body"
            zone_summary = "The cursor is over the main editor body where code editing happens."
    elif surface_kind == "terminal":
        if y_ratio >= 0.72:
            zone_kind = "terminal_input"
            zone_label = "Terminal input line"
            zone_summary = "The cursor is near the terminal input line where command submission is most likely."
        else:
            zone_kind = "terminal_transcript"
            zone_label = "Terminal transcript"
            zone_summary = "The cursor is over terminal output history rather than the live input edge."
    elif surface_kind == "browser":
        if y_ratio <= 0.14:
            zone_kind = "browser_chrome"
            zone_label = "Browser chrome"
            zone_summary = "The cursor is near the browser chrome where navigation controls usually live."
        else:
            zone_kind = "browser_content"
            zone_label = "Browser content"
            zone_summary = "The cursor is over the main browser content area."
    elif surface_kind == "files":
        if x_ratio <= 0.22:
            zone_kind = "file_sidebar"
            zone_label = "File sidebar"
            zone_summary = "The cursor is near the file-navigation sidebar."
        else:
            zone_kind = "file_list"
            zone_label = "File list"
            zone_summary = "The cursor is over the primary file list where open/select actions usually land."
    elif surface_kind == "francis":
        if y_ratio <= 0.12:
            zone_kind = "francis_header"
            zone_label = "Francis header"
            zone_summary = "The cursor is near the Francis control header."
        elif y_ratio <= 0.28:
            zone_kind = "francis_action_row"
            zone_label = "Francis action row"
            zone_summary = "The cursor is near primary Francis action controls."
        elif x_ratio <= 0.3:
            zone_kind = "francis_navigation"
            zone_label = "Francis navigation rail"
            zone_summary = "The cursor is near Francis navigation and surface selection controls."
        elif y_ratio >= 0.8:
            zone_kind = "francis_footer_actions"
            zone_label = "Francis footer actions"
            zone_summary = "The cursor is near Francis footer actions and confirmation controls."
        else:
            zone_kind = "francis_workspace"
            zone_label = "Francis workspace panel"
            zone_summary = "The cursor is over a Francis workspace control panel."
    else:
        if y_ratio <= 0.15:
            zone_kind = "application_header"
            zone_label = "Application header"
            zone_summary = "The cursor is near the active application header."

    return {
        "kind": zone_kind,
        "label": zone_label,
        "summary": zone_summary,
        "confidence": str(target.get("confidence", "medium")).strip() or "medium",
    }


def _build_target_affordances(
    *,
    surface: dict[str, str],
    target: dict[str, Any],
    zone: dict[str, Any],
    x: int | None,
    y: int | None,
) -> list[dict[str, Any]]:
    actionable = bool(target.get("actionable"))
    if not actionable or x is None or y is None:
        return []

    surface_kind = str(surface.get("kind", "")).strip().lower() or "application"
    zone_kind = str(zone.get("kind", "")).strip().lower() or "application_content"
    target_label = str(target.get("label", "active focus point")).strip() or "active focus point"
    zone_label = str(zone.get("label", "active zone")).strip() or "active zone"
    affordances: list[dict[str, Any]] = [
        {
            "kind": "focus_click",
            "label": "Focus Click",
            "summary": f"Left-click the {target_label.lower()} inside the {zone_label.lower()}.",
            "command": {
                "kind": "mouse.click",
                "args": {"x": x, "y": y, "button": "left", "coordinate_space": "display"},
                "reason": f"Left-click the {target_label.lower()} inside the {zone_label.lower()} during Orb authority.",
            },
        }
    ]

    if surface_kind == "editor":
        affordances.append(
            {
                "kind": "save_shortcut",
                "label": "Save",
                "summary": "Press Ctrl+S on the active editor surface.",
                "command": {
                    "kind": "keyboard.shortcut",
                    "args": {"keys": ["ctrl", "s"]},
                    "reason": "Press Ctrl+S on the active editor surface during Orb authority.",
                },
            }
        )
    elif surface_kind == "terminal" and zone_kind == "terminal_input":
        affordances.insert(
            0,
            {
                "kind": "submit_key",
                "label": "Submit",
                "summary": "Press Enter on the live terminal input line.",
                "command": {
                    "kind": "keyboard.key",
                    "args": {"key": "enter"},
                    "reason": "Press Enter on the live terminal input line during Orb authority.",
                },
            },
        )
        affordances.append(
            {
                "kind": "cancel_key",
                "label": "Cancel",
                "summary": "Press Escape on the active terminal surface.",
                "command": {
                    "kind": "keyboard.key",
                    "args": {"key": "escape"},
                    "reason": "Press Escape on the active terminal surface during Orb authority.",
                },
            }
        )
    elif surface_kind == "files" and zone_kind == "file_list":
        affordances.insert(
            0,
            {
                "kind": "open_key",
                "label": "Open",
                "summary": "Press Enter on the selected file item.",
                "command": {
                    "kind": "keyboard.key",
                    "args": {"key": "enter"},
                    "reason": "Press Enter on the selected file item during Orb authority.",
                },
            },
        )
    elif surface_kind == "francis":
        if zone_kind == "francis_navigation":
            affordances.insert(
                0,
                {
                    "kind": "open_key",
                    "label": "Open",
                    "summary": "Press Enter on the selected Francis navigation control.",
                    "command": {
                        "kind": "keyboard.key",
                        "args": {"key": "enter"},
                        "reason": "Press Enter on the selected Francis navigation control during Orb authority.",
                    },
                },
            )
            affordances.append(
                {
                    "kind": "cancel_key",
                    "label": "Cancel",
                    "summary": "Press Escape on the Francis navigation surface.",
                    "command": {
                        "kind": "keyboard.key",
                        "args": {"key": "escape"},
                        "reason": "Press Escape on the Francis navigation surface during Orb authority.",
                    },
                },
            )
        elif zone_kind in {"francis_action_row", "francis_footer_actions"}:
            zone_phrase = "primary Francis action controls" if zone_kind == "francis_action_row" else "Francis footer action controls"
            affordances.insert(
                0,
                {
                    "kind": "confirm_key",
                    "label": "Confirm",
                    "summary": f"Press Enter on the {zone_phrase}.",
                    "command": {
                        "kind": "keyboard.key",
                        "args": {"key": "enter"},
                        "reason": f"Press Enter on the {zone_phrase} during Orb authority.",
                    },
                },
            )
            affordances.append(
                {
                    "kind": "cancel_key",
                    "label": "Cancel",
                    "summary": f"Press Escape on the {zone_phrase}.",
                    "command": {
                        "kind": "keyboard.key",
                        "args": {"key": "escape"},
                        "reason": f"Press Escape on the {zone_phrase} during Orb authority.",
                    },
                },
            )
        elif zone_kind == "francis_workspace":
            affordances.append(
                {
                    "kind": "confirm_key",
                    "label": "Confirm",
                    "summary": "Press Enter on the active Francis workspace control.",
                    "command": {
                        "kind": "keyboard.key",
                        "args": {"key": "enter"},
                        "reason": "Press Enter on the active Francis workspace control during Orb authority.",
                    },
                },
            )
            affordances.append(
                {
                    "kind": "cancel_key",
                    "label": "Cancel",
                    "summary": "Press Escape on the active Francis workspace control.",
                    "command": {
                        "kind": "keyboard.key",
                        "args": {"key": "escape"},
                        "reason": "Press Escape on the active Francis workspace control during Orb authority.",
                    },
                },
            )
    elif surface_kind == "browser" and zone_kind == "browser_content":
        affordances.append(
            {
                "kind": "cancel_key",
                "label": "Escape",
                "summary": "Press Escape on the active browser surface.",
                "command": {
                    "kind": "keyboard.key",
                    "args": {"key": "escape"},
                    "reason": "Press Escape on the active browser surface during Orb authority.",
                },
            }
        )

    return affordances[:4]


def _build_cards(payload: dict[str, Any], freshness: dict[str, Any], surface: dict[str, str], target: dict[str, Any]) -> list[dict[str, str]]:
    display = payload.get("display", {}) if isinstance(payload.get("display"), dict) else {}
    window = payload.get("window", {}) if isinstance(payload.get("window"), dict) else {}
    cursor = payload.get("cursor", {}) if isinstance(payload.get("cursor"), dict) else {}
    focus = payload.get("focus", {}) if isinstance(payload.get("focus"), dict) else {}
    accessibility = payload.get("accessibility", {}) if isinstance(payload.get("accessibility"), dict) else {}
    environment = payload.get("environment", {}) if isinstance(payload.get("environment"), dict) else {}
    focus_label = (
        f"{_normalize_dimension(focus.get('width'))}x{_normalize_dimension(focus.get('height'))} local crop"
        if str(focus.get("data_url", "")).strip()
        else "No local focus crop"
    )
    cursor_x = _normalize_optional_int(cursor.get("x"))
    cursor_y = _normalize_optional_int(cursor.get("y"))
    cursor_label = (
        f"({cursor_x}, {cursor_y})"
        if cursor_x is not None and cursor_y is not None
        else "Cursor unavailable"
    )
    zone = target.get("zone", {}) if isinstance(target.get("zone"), dict) else {}
    affordances = target.get("affordances", []) if isinstance(target.get("affordances"), list) else []
    affordance_label = ", ".join(
        str(item.get("label", "")).strip()
        for item in affordances[:2]
        if isinstance(item, dict) and str(item.get("label", "")).strip()
    ) or "No suggested surface actions"
    stability = target.get("stability", {}) if isinstance(target.get("stability"), dict) else {}
    grounding = target.get("grounding", {}) if isinstance(target.get("grounding"), dict) else {}
    stability_label = str(stability.get("state", "idle")).strip().replace("_", " ") or "idle"
    grounding_label = str(grounding.get("state", "weak")).strip().replace("_", " ") or "weak"
    sources_label = ", ".join(
        str(item).replace("_", " ")
        for item in grounding.get("source_priority", [])
        if isinstance(grounding.get("source_priority"), list) and str(item).strip()
    ) or ", ".join(
        label.replace("_", " ")
        for label, row in (environment.get("sources", {}) if isinstance(environment.get("sources"), dict) else {}).items()
        if isinstance(row, dict) and bool(row.get("attached"))
    ) or "Window metadata only"
    accessibility_label = (
        str(accessibility.get("label", "")).strip()
        or str(accessibility.get("localized_control_type", "")).strip()
        or "No focused control"
    )
    freshness_state = str(freshness.get("state", "idle"))
    freshness_tone = "high" if freshness_state == "stale" else "medium" if freshness_state == "cooling" else "low"

    return [
        {"label": "Display", "value": _format_display_label(payload.get("display_id"), display), "tone": "low"},
        {"label": "Window", "value": _format_window_label(window), "tone": "medium" if window.get("title") else "low"},
        {"label": "Surface", "value": str(surface.get("label", "Application surface")).strip(), "tone": "medium"},
        {"label": "Intent", "value": str(surface.get("intent", "visible_work")).strip().replace("_", " "), "tone": "low"},
        {"label": "Cursor", "value": cursor_label, "tone": "low"},
        {"label": "Target", "value": str(target.get("label", "Active focus point")).strip(), "tone": "medium" if target.get("actionable") else "low"},
        {
            "label": "Grounding",
            "value": grounding_label,
            "tone": "medium" if grounding_label == "grounded" else "low" if grounding_label in {"weak", "reassess"} else "high",
        },
        {"label": "Sources", "value": sources_label, "tone": "low"},
        {"label": "Zone", "value": str(zone.get("label", "Active zone")).strip(), "tone": "low"},
        {"label": "Stability", "value": stability_label, "tone": "medium" if str(stability.get("state", "")).strip().lower() == "settled" else "low"},
        {"label": "Action", "value": affordance_label, "tone": "medium" if affordances else "low"},
        {
            "label": "Focused Control",
            "value": accessibility_label,
            "tone": "medium" if bool(accessibility.get("attached")) else "low",
        },
        {"label": "Focus", "value": focus_label, "tone": "medium" if str(focus.get("data_url", "")).strip() else "low"},
        {
            "label": "Retention",
            "value": "Latest frame only | active display + focused control scope",
            "tone": freshness_tone,
        },
    ]


def _build_view(payload: dict[str, Any], *, include_frame_data: bool) -> dict[str, Any]:
    normalized = _normalize_payload(payload)
    freshness = _build_freshness(normalized.get("captured_at"))
    surface = _infer_surface_contract(normalized)
    target = _build_target_contract(normalized, freshness, surface)
    environment = normalized["environment"]
    accessibility = normalized["accessibility"]
    state = "live" if normalized.get("captured_at") else "idle"
    window_label = _format_window_label(normalized["window"])
    display_label = _format_display_label(normalized.get("display_id"), normalized["display"])
    cursor = normalized["cursor"]
    cursor_label = (
        f"Cursor at ({cursor['x']}, {cursor['y']})"
        if cursor.get("x") is not None and cursor.get("y") is not None
        else "Cursor location is not attached"
    )
    focus_attached = bool(normalized["focus"]["data_url"])
    source_priority = ", ".join(
        str(item).replace("_", " ")
        for item in environment.get("source_priority", [])
        if isinstance(environment.get("source_priority"), list) and str(item).strip()
    ) or "window metadata"
    summary = "Live desktop perception is not attached yet."
    detail_summary = (
        "Francis combines the active display thumbnail, foreground-window metadata, and focused accessibility evidence when available. "
        "Retention stays at the latest frame unless a later action receipts it explicitly."
    )
    if state == "live":
        summary = (
            f"Francis sees {display_label}. {surface['summary']} "
            f"Foreground window: {window_label}. {cursor_label}. {freshness['summary']}"
        )
        detail_summary = (
            "Active-display thumbnail, foreground-window metadata, and focused accessibility evidence are attached for in-place relevance. "
            f"{target['summary']} "
            + ("A focused local crop around the cursor is attached. " if focus_attached else "No focused local crop is attached yet. ")
            + (
                f"Focused control: {accessibility['label'] or accessibility['localized_control_type']}. "
                if accessibility.get("attached")
                else ""
            )
            + "Retention remains latest-frame only unless a governed receipt stores evidence."
        )

    view = {
        "surface": "orb_perception",
        "state": state,
        "summary": summary,
        "detail_summary": detail_summary,
        "captured_at": normalized.get("captured_at"),
        "display_id": normalized.get("display_id"),
        "display": deepcopy(normalized["display"]),
        "cursor": deepcopy(normalized["cursor"]),
        "idle_seconds": normalized.get("idle_seconds", 0),
        "window": deepcopy(normalized["window"]),
        "freshness": freshness,
        "active_surface": surface,
        "target": target,
        "sensing": {
            "kind": "hybrid_environment",
            "scope": "active_display_plus_foreground",
            "retention": "latest_frame_only",
            "source_priority": deepcopy(environment.get("source_priority", [])),
            "summary": (
                "Francis is using the active display thumbnail, foreground-window metadata, "
                "and the focused accessibility element when available, "
                f"classified locally as {surface['label'].lower()} with {source_priority} priority."
            ),
        },
        "frame": deepcopy(normalized["frame"]),
        "focus": deepcopy(normalized["focus"]),
        "accessibility": deepcopy(accessibility),
        "environment": deepcopy(environment),
        "cards": _build_cards(normalized, freshness, surface, target),
    }
    if not include_frame_data:
        view["frame"] = {
            "width": int(normalized["frame"].get("width", 0) or 0),
            "height": int(normalized["frame"].get("height", 0) or 0),
            "has_image": bool(normalized["frame"].get("data_url")),
        }
        view["focus"] = {
            "width": int(normalized["focus"].get("width", 0) or 0),
            "height": int(normalized["focus"].get("height", 0) or 0),
            "has_image": bool(normalized["focus"].get("data_url")),
        }
    return view


def get_orb_perception_view(*, include_frame_data: bool = True) -> dict[str, Any]:
    return _build_view(_latest_perception, include_frame_data=include_frame_data)


def resolve_orb_focus_target(*, max_age_ms: int = 2500) -> dict[str, Any] | None:
    view = get_orb_perception_view(include_frame_data=False)
    if str(view.get("state", "idle")).strip().lower() != "live":
        return None
    freshness = view.get("freshness", {}) if isinstance(view.get("freshness"), dict) else {}
    age_ms = freshness.get("age_ms")
    if not isinstance(age_ms, int) or age_ms > max(250, int(max_age_ms)):
        return None
    target = view.get("target", {}) if isinstance(view.get("target"), dict) else {}
    grounding = target.get("grounding", {}) if isinstance(target.get("grounding"), dict) else {}
    grounding_state = str(grounding.get("state", "")).strip().lower()
    if grounding_state in {"stale", "detached"}:
        return None
    cursor = view.get("cursor", {}) if isinstance(view.get("cursor"), dict) else {}
    x = _normalize_optional_int(cursor.get("x"))
    y = _normalize_optional_int(cursor.get("y"))
    if x is None or y is None:
        return None
    return {
        "x": x,
        "y": y,
        "display_id": _normalize_optional_int(view.get("display_id")),
        "captured_at": str(view.get("captured_at", "")).strip() or None,
        "surface": view.get("active_surface", {}) if isinstance(view.get("active_surface"), dict) else {},
        "target": target,
        "zone": (
            target.get("zone", {})
            if isinstance(target.get("zone"), dict)
            else {}
        ),
        "affordances": (
            target.get("affordances", [])
            if isinstance(target.get("affordances"), list)
            else []
        ),
        "freshness": {
            "state": str(freshness.get("state", "")).strip() or "idle",
            "age_ms": age_ms,
            "summary": str(freshness.get("summary", "")).strip(),
        },
    }

def record_orb_perception_view(payload: dict[str, Any]) -> dict[str, Any]:
    global _latest_perception

    normalized = _normalize_payload(payload if isinstance(payload, dict) else {})
    _latest_perception = normalized
    return _build_view(_latest_perception, include_frame_data=True)
