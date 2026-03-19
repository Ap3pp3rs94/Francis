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


def _normalize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    frame = payload.get("frame", {}) if isinstance(payload.get("frame"), dict) else {}
    focus = payload.get("focus", {}) if isinstance(payload.get("focus"), dict) else {}
    cursor = payload.get("cursor", {}) if isinstance(payload.get("cursor"), dict) else {}
    window = payload.get("window", {}) if isinstance(payload.get("window"), dict) else {}
    display = payload.get("display", {}) if isinstance(payload.get("display"), dict) else {}
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
    window_bounds = window.get("bounds", {}) if isinstance(window.get("bounds"), dict) else {}
    window_x = _normalize_optional_signed_int(window_bounds.get("x")) if window_bounds.get("x") is not None else None
    window_y = _normalize_optional_signed_int(window_bounds.get("y")) if window_bounds.get("y") is not None else None

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
            "bounds": {
                "x": window_x,
                "y": window_y,
                "width": _normalize_dimension(window_bounds.get("width")),
                "height": _normalize_dimension(window_bounds.get("height")),
            },
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
    actionable = x is not None and y is not None and freshness_state in {"fresh", "cooling"}
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
        "actionable": actionable,
        "confidence": "likely"
        if actionable and focus_attached and in_window and stability_state == "settled"
        else "medium"
        if actionable and stability_state in {"settled", "tracking"} and (focus_attached or in_window)
        else "low",
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
    return target


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
        affordances.append(
            {
                "kind": "confirm_key",
                "label": "Confirm",
                "summary": "Press Enter on the active Francis control surface.",
                "command": {
                    "kind": "keyboard.key",
                    "args": {"key": "enter"},
                    "reason": "Press Enter on the active Francis control surface during Orb authority.",
                },
            }
        )
        affordances.append(
            {
                "kind": "cancel_key",
                "label": "Cancel",
                "summary": "Press Escape on the active Francis control surface.",
                "command": {
                    "kind": "keyboard.key",
                    "args": {"key": "escape"},
                    "reason": "Press Escape on the active Francis control surface during Orb authority.",
                },
            }
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
    stability_label = str(stability.get("state", "idle")).strip().replace("_", " ") or "idle"
    freshness_state = str(freshness.get("state", "idle"))
    freshness_tone = "high" if freshness_state == "stale" else "medium" if freshness_state == "cooling" else "low"

    return [
        {"label": "Display", "value": _format_display_label(payload.get("display_id"), display), "tone": "low"},
        {"label": "Window", "value": _format_window_label(window), "tone": "medium" if window.get("title") else "low"},
        {"label": "Surface", "value": str(surface.get("label", "Application surface")).strip(), "tone": "medium"},
        {"label": "Intent", "value": str(surface.get("intent", "visible_work")).strip().replace("_", " "), "tone": "low"},
        {"label": "Cursor", "value": cursor_label, "tone": "low"},
        {"label": "Target", "value": str(target.get("label", "Active focus point")).strip(), "tone": "medium" if target.get("actionable") else "low"},
        {"label": "Zone", "value": str(zone.get("label", "Active zone")).strip(), "tone": "low"},
        {"label": "Stability", "value": stability_label, "tone": "medium" if str(stability.get("state", "")).strip().lower() == "settled" else "low"},
        {"label": "Action", "value": affordance_label, "tone": "medium" if affordances else "low"},
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
        "zone": (
            view.get("target", {}).get("zone", {})
            if isinstance(view.get("target"), dict) and isinstance(view.get("target", {}).get("zone"), dict)
            else {}
        ),
        "affordances": (
            view.get("target", {}).get("affordances", [])
            if isinstance(view.get("target"), dict) and isinstance(view.get("target", {}).get("affordances"), list)
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
