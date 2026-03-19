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
    "window": {
        "title": "",
        "process": "",
        "pid": None,
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


def _normalize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    frame = payload.get("frame", {}) if isinstance(payload.get("frame"), dict) else {}
    focus = payload.get("focus", {}) if isinstance(payload.get("focus"), dict) else {}
    cursor = payload.get("cursor", {}) if isinstance(payload.get("cursor"), dict) else {}
    window = payload.get("window", {}) if isinstance(payload.get("window"), dict) else {}
    display = payload.get("display", {}) if isinstance(payload.get("display"), dict) else {}

    captured_at = str(payload.get("captured_at", "")).strip() or None
    display_id = _normalize_optional_int(payload.get("display_id"))
    idle_seconds = _normalize_dimension(payload.get("idle_seconds"))
    cursor_x = _normalize_optional_int(cursor.get("x"))
    cursor_y = _normalize_optional_int(cursor.get("y"))
    window_title = str(window.get("title", "")).strip()
    process_name = str(window.get("process", "")).strip()
    window_pid = _normalize_optional_int(window.get("pid"))

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
        "window": {
            "title": window_title,
            "process": process_name,
            "pid": window_pid,
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
    parts = []
    if title:
        parts.append(title)
    if process_name:
        parts.append(process_name)
    if pid:
        parts.append(f"pid {pid}")
    return " | ".join(parts) if parts else "No foreground window metadata"


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
    x = _normalize_optional_int(cursor.get("x"))
    y = _normalize_optional_int(cursor.get("y"))
    focus_attached = bool(str(focus.get("data_url", "")).strip())
    freshness_state = str(freshness.get("state", "idle")).strip().lower() or "idle"
    actionable = x is not None and y is not None and freshness_state in {"fresh", "cooling"}
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
    return {
        "kind": "cursor_focus",
        "label": label,
        "summary": f"{label} at {coordinate_summary}. {crop_summary}",
        "actionable": actionable,
        "confidence": "likely" if actionable and focus_attached else "medium" if actionable else "low",
    }


def _build_cards(payload: dict[str, Any], freshness: dict[str, Any], surface: dict[str, str], target: dict[str, Any]) -> list[dict[str, str]]:
    display = payload.get("display", {}) if isinstance(payload.get("display"), dict) else {}
    window = payload.get("window", {}) if isinstance(payload.get("window"), dict) else {}
    cursor = payload.get("cursor", {}) if isinstance(payload.get("cursor"), dict) else {}
    focus = payload.get("focus", {}) if isinstance(payload.get("focus"), dict) else {}
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
    freshness_state = str(freshness.get("state", "idle"))
    freshness_tone = "high" if freshness_state == "stale" else "medium" if freshness_state == "cooling" else "low"

    return [
        {"label": "Display", "value": _format_display_label(payload.get("display_id"), display), "tone": "low"},
        {"label": "Window", "value": _format_window_label(window), "tone": "medium" if window.get("title") else "low"},
        {"label": "Surface", "value": str(surface.get("label", "Application surface")).strip(), "tone": "medium"},
        {"label": "Intent", "value": str(surface.get("intent", "visible_work")).strip().replace("_", " "), "tone": "low"},
        {"label": "Cursor", "value": cursor_label, "tone": "low"},
        {"label": "Target", "value": str(target.get("label", "Active focus point")).strip(), "tone": "medium" if target.get("actionable") else "low"},
        {"label": "Focus", "value": focus_label, "tone": "medium" if str(focus.get("data_url", "")).strip() else "low"},
        {
            "label": "Retention",
            "value": "Latest frame only | active display scope",
            "tone": freshness_tone,
        },
    ]


def _build_view(payload: dict[str, Any], *, include_frame_data: bool) -> dict[str, Any]:
    normalized = _normalize_payload(payload)
    freshness = _build_freshness(normalized.get("captured_at"))
    surface = _infer_surface_contract(normalized)
    target = _build_target_contract(normalized, freshness, surface)
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
    summary = "Live desktop perception is not attached yet."
    detail_summary = (
        "Francis only reads the active display thumbnail and foreground-window metadata here. "
        "Retention stays at the latest frame unless a later action receipts it explicitly."
    )
    if state == "live":
        summary = (
            f"Francis sees {display_label}. {surface['summary']} "
            f"Foreground window: {window_label}. {cursor_label}. {freshness['summary']}"
        )
        detail_summary = (
            "Active-display thumbnail and foreground-window metadata are attached for in-place relevance. "
            f"{target['summary']} "
            + ("A focused local crop around the cursor is attached. " if focus_attached else "No focused local crop is attached yet. ")
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
            "kind": "active_display_thumbnail",
            "scope": "active_display_only",
            "retention": "latest_frame_only",
            "summary": (
                "Francis is using the active display thumbnail plus foreground-window metadata only, "
                f"classified locally as {surface['label'].lower()}."
            ),
        },
        "frame": deepcopy(normalized["frame"]),
        "focus": deepcopy(normalized["focus"]),
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
        "target": view.get("target", {}) if isinstance(view.get("target"), dict) else {},
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
