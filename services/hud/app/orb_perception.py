from __future__ import annotations

from copy import deepcopy
from typing import Any

_DEFAULT_PERCEPTION: dict[str, Any] = {
    "surface": "orb_perception",
    "state": "idle",
    "summary": "Live desktop perception is not attached yet.",
    "captured_at": None,
    "display_id": None,
    "cursor": {"x": None, "y": None},
    "idle_seconds": 0,
    "window": {
        "title": "",
        "process": "",
    },
    "frame": {
        "width": 0,
        "height": 0,
        "data_url": "",
    },
}

_latest_perception: dict[str, Any] = deepcopy(_DEFAULT_PERCEPTION)


def get_orb_perception_view(*, include_frame_data: bool = True) -> dict[str, Any]:
    payload = deepcopy(_latest_perception)
    if not include_frame_data:
        frame = payload.get("frame", {}) if isinstance(payload.get("frame"), dict) else {}
        payload["frame"] = {
            "width": int(frame.get("width", 0) or 0),
            "height": int(frame.get("height", 0) or 0),
            "has_image": bool(frame.get("data_url")),
        }
    return payload


def record_orb_perception_view(payload: dict[str, Any]) -> dict[str, Any]:
    global _latest_perception

    frame = payload.get("frame", {}) if isinstance(payload.get("frame"), dict) else {}
    cursor = payload.get("cursor", {}) if isinstance(payload.get("cursor"), dict) else {}
    window = payload.get("window", {}) if isinstance(payload.get("window"), dict) else {}
    captured_at = str(payload.get("captured_at", "")).strip() or None
    display_id = payload.get("display_id")
    idle_seconds = int(payload.get("idle_seconds", 0) or 0)
    state = "live" if captured_at else "idle"

    cursor_x = int(cursor.get("x")) if isinstance(cursor.get("x"), (int, float)) else None
    cursor_y = int(cursor.get("y")) if isinstance(cursor.get("y"), (int, float)) else None
    window_title = str(window.get("title", "")).strip()
    process_name = str(window.get("process", "")).strip()
    frame_width = int(frame.get("width")) if isinstance(frame.get("width"), (int, float)) else 0
    frame_height = int(frame.get("height")) if isinstance(frame.get("height"), (int, float)) else 0
    summary = "Live desktop perception is not attached yet."
    if captured_at:
        summary = f"Live desktop context is attached on display {display_id or 'unknown'} at {captured_at}."
        if window_title:
            summary += f" Foreground window: {window_title}."
        if process_name:
            summary += f" Process: {process_name}."
        if cursor_x is not None and cursor_y is not None:
            summary += f" Cursor: ({cursor_x}, {cursor_y})."

    _latest_perception = {
        "surface": "orb_perception",
        "state": state,
        "summary": summary,
        "captured_at": captured_at,
        "display_id": int(display_id) if isinstance(display_id, (int, float)) else None,
        "cursor": {
            "x": cursor_x,
            "y": cursor_y,
        },
        "idle_seconds": idle_seconds,
        "window": {
            "title": window_title,
            "process": process_name,
        },
        "frame": {
            "width": frame_width,
            "height": frame_height,
            "data_url": str(frame.get("data_url", "")).strip(),
        },
    }
    return deepcopy(_latest_perception)
