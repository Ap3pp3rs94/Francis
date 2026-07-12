"""Bounded desktop input-observation stream for the Lens Situation Model."""

from __future__ import annotations

import ctypes
import json
import math
import os
import platform
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from francis.kernel.paths import data_dir
from francis.lens.perception_input_authority import lens_perception_input_authority_receipt_status

LENS_INPUT_EVENT_STREAM_KIND = "lens.perception.desktop_input_event_stream"
LENS_INPUT_EVENT_STREAM_VERSION = 1
LENS_INPUT_EVENT_STREAM_ROUTE = "/lens/perception/input"

_MAX_STATE_AGE_SECONDS = 2.5
_DEFAULT_RETENTION_SECONDS = 10.0
_DEFAULT_POINTER_ACTIVE_SECONDS = 1.5
_ALLOWED_BUTTONS = ("left", "right", "middle", "x1", "x2")
_BUTTON_VKEYS = {"left": 0x01, "right": 0x02, "middle": 0x04, "x1": 0x05, "x2": 0x06}
_EVENT_FIELDS = {
    "cursor_position": {"event_id", "ts", "kind", "x", "y"},
    "cursor_move": {"event_id", "ts", "kind", "from_x", "from_y", "x", "y"},
    "focus_change": {"event_id", "ts", "kind", "window_id", "process_id"},
    "pointer_button": {
        "event_id",
        "ts",
        "kind",
        "button",
        "state",
        "x",
        "y",
        "window_id",
        "process_id",
    },
    "scroll": {
        "event_id",
        "ts",
        "kind",
        "delta_x",
        "delta_y",
        "x",
        "y",
        "window_id",
        "process_id",
    },
    "keyboard_activity": {"event_id", "ts", "kind", "active", "window_id", "process_id"},
}
_GESTURE_FIELDS = {
    "pointer_click": {
        "gesture_id",
        "ts",
        "kind",
        "button",
        "x",
        "y",
        "window_id",
        "process_id",
    },
    "scroll": {
        "gesture_id",
        "ts",
        "kind",
        "delta_x",
        "delta_y",
        "x",
        "y",
        "window_id",
        "process_id",
    },
    "focus_change": {"gesture_id", "ts", "kind", "window_id", "process_id"},
    "typing_activity": {"gesture_id", "ts", "kind", "window_id", "process_id"},
}

AuthorityStatusProvider = Callable[..., dict[str, Any]]


@dataclass(frozen=True, slots=True)
class DesktopInputObservation:
    observed_at: float
    cursor_x: int
    cursor_y: int
    foreground_window_id: int = 0
    foreground_process_id: int = 0
    buttons_down: tuple[str, ...] = ()
    scroll_delta_x: int = 0
    scroll_delta_y: int = 0
    keyboard_activity: bool = False
    scroll_source_connected: bool = False
    keyboard_activity_source_connected: bool = False

    def __post_init__(self) -> None:
        if not math.isfinite(self.observed_at) or self.observed_at < 0.0:
            raise ValueError("lens_input_observation_time_invalid")
        if not -1_000_000 <= self.cursor_x <= 1_000_000 or not -1_000_000 <= self.cursor_y <= 1_000_000:
            raise ValueError("lens_input_observation_cursor_invalid")
        if self.foreground_window_id < 0 or self.foreground_process_id < 0:
            raise ValueError("lens_input_observation_foreground_identity_invalid")
        if any(button not in _ALLOWED_BUTTONS for button in self.buttons_down):
            raise ValueError("lens_input_observation_button_invalid")
        if len(set(self.buttons_down)) != len(self.buttons_down):
            raise ValueError("lens_input_observation_button_duplicate")
        if not -120_000 <= self.scroll_delta_x <= 120_000 or not -120_000 <= self.scroll_delta_y <= 120_000:
            raise ValueError("lens_input_observation_scroll_invalid")


class DesktopInputObservationSource(Protocol):
    def observe(self) -> DesktopInputObservation: ...


class _Point(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class Win32DesktopInputObservationSource:
    """Observe pointer and foreground identity without keyboard or title APIs."""

    def observe(self) -> DesktopInputObservation:
        if platform.system() != "Windows":
            raise OSError("lens_input_observation_platform_unsupported")
        user32 = ctypes.windll.user32  # type: ignore[attr-defined]
        point = _Point()
        if not user32.GetCursorPos(ctypes.byref(point)):
            raise OSError("lens_input_observation_cursor_unavailable")
        window_id = int(user32.GetForegroundWindow() or 0)
        process_id = ctypes.c_ulong(0)
        if window_id:
            user32.GetWindowThreadProcessId(window_id, ctypes.byref(process_id))
        buttons = tuple(
            button
            for button, virtual_key in _BUTTON_VKEYS.items()
            if int(user32.GetAsyncKeyState(virtual_key)) & 0x8000
        )
        return DesktopInputObservation(
            observed_at=time.time(),
            cursor_x=int(point.x),
            cursor_y=int(point.y),
            foreground_window_id=window_id,
            foreground_process_id=int(process_id.value),
            buttons_down=buttons,
        )


class LensInputEventStream:
    def __init__(
        self,
        *,
        authority_receipt_id: str,
        retention_seconds: float = _DEFAULT_RETENTION_SECONDS,
        max_events: int = 2_048,
        pointer_active_seconds: float = _DEFAULT_POINTER_ACTIVE_SECONDS,
        authority_status: AuthorityStatusProvider = lens_perception_input_authority_receipt_status,
        clock: Callable[[], float] = time.time,
    ) -> None:
        receipt_id = str(authority_receipt_id or "").strip()
        if not receipt_id or "/" in receipt_id or "\\" in receipt_id or ".." in receipt_id:
            raise ValueError("lens_input_observation_authority_receipt_invalid")
        if not math.isfinite(retention_seconds) or not 1.0 <= retention_seconds <= 30.0:
            raise ValueError("lens_input_event_retention_invalid")
        if not 1 <= max_events <= 4_096:
            raise ValueError("lens_input_event_max_events_invalid")
        if not math.isfinite(pointer_active_seconds) or not 0.1 <= pointer_active_seconds <= 5.0:
            raise ValueError("lens_input_pointer_activity_window_invalid")
        self.authority_receipt_id = receipt_id
        self.retention_seconds = float(retention_seconds)
        self.max_events = int(max_events)
        self.pointer_active_seconds = float(pointer_active_seconds)
        self._authority_status = authority_status
        self._clock = clock
        self._previous: DesktopInputObservation | None = None
        self._events: list[dict[str, Any]] = []
        self._gestures: list[dict[str, Any]] = []
        self._event_sequence = 0
        self._gesture_sequence = 0
        self._last_pointer_activity_at: float | None = None

    def sample_once(self, source: DesktopInputObservationSource) -> dict[str, Any]:
        authority_checked_at = float(self._clock())
        authority = self._authority_status(self.authority_receipt_id, now=int(authority_checked_at))
        blockers = _authority_blockers(authority)
        if blockers:
            return _blocked_readback(self.authority_receipt_id, blockers, authority)
        try:
            observation = source.observe()
        except (OSError, ValueError) as exc:
            code = str(exc).strip() or "lens_input_observation_source_failed"
            return self._write_state(
                observation=None,
                authority=authority,
                state="blocked",
                blockers=[code],
                updated_at=authority_checked_at,
            )
        return self.observe(observation, authority=authority)

    def observe(
        self,
        observation: DesktopInputObservation,
        *,
        authority: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        authority_state = authority or self._authority_status(
            self.authority_receipt_id,
            now=int(observation.observed_at),
        )
        blockers = _authority_blockers(authority_state)
        if blockers:
            return _blocked_readback(self.authority_receipt_id, blockers, authority_state)

        previous = self._previous
        if previous is None:
            self._append_event(
                observation.observed_at,
                "cursor_position",
                x=observation.cursor_x,
                y=observation.cursor_y,
            )
        elif (previous.cursor_x, previous.cursor_y) != (observation.cursor_x, observation.cursor_y):
            self._append_event(
                observation.observed_at,
                "cursor_move",
                from_x=previous.cursor_x,
                from_y=previous.cursor_y,
                x=observation.cursor_x,
                y=observation.cursor_y,
            )
            self._last_pointer_activity_at = observation.observed_at

        previous_window = previous.foreground_window_id if previous is not None else 0
        if observation.foreground_window_id != previous_window:
            self._append_event(
                observation.observed_at,
                "focus_change",
                window_id=observation.foreground_window_id,
                process_id=observation.foreground_process_id,
            )
            self._append_gesture(
                observation.observed_at,
                "focus_change",
                window_id=observation.foreground_window_id,
                process_id=observation.foreground_process_id,
            )

        previous_buttons = set(previous.buttons_down if previous is not None else ())
        current_buttons = set(observation.buttons_down)
        for button in _ALLOWED_BUTTONS:
            if (button in previous_buttons) == (button in current_buttons):
                continue
            state = "down" if button in current_buttons else "up"
            fields = _target_fields(observation)
            self._append_event(observation.observed_at, "pointer_button", button=button, state=state, **fields)
            self._last_pointer_activity_at = observation.observed_at
            if state == "up":
                self._append_gesture(observation.observed_at, "pointer_click", button=button, **fields)

        if observation.scroll_delta_x or observation.scroll_delta_y:
            fields = _target_fields(observation)
            scroll = {
                "delta_x": observation.scroll_delta_x,
                "delta_y": observation.scroll_delta_y,
                **fields,
            }
            self._append_event(observation.observed_at, "scroll", **scroll)
            self._append_gesture(observation.observed_at, "scroll", **scroll)
            self._last_pointer_activity_at = observation.observed_at

        if observation.keyboard_activity:
            target = {
                "window_id": observation.foreground_window_id,
                "process_id": observation.foreground_process_id,
            }
            self._append_event(observation.observed_at, "keyboard_activity", active=True, **target)
            self._append_gesture(observation.observed_at, "typing_activity", **target)

        self._previous = observation
        self._prune(observation.observed_at)
        source_blockers: list[str] = []
        if not observation.scroll_source_connected:
            source_blockers.append("lens_input_scroll_source_not_connected")
        if not observation.keyboard_activity_source_connected:
            source_blockers.append("lens_keyboard_activity_source_not_connected")
        return self._write_state(
            observation=observation,
            authority=authority_state,
            state="observing",
            blockers=source_blockers,
            updated_at=observation.observed_at,
        )

    def _append_event(self, observed_at: float, kind: str, **fields: Any) -> None:
        self._event_sequence += 1
        self._events.append({"event_id": f"input-{self._event_sequence}", "ts": observed_at, "kind": kind, **fields})

    def _append_gesture(self, observed_at: float, kind: str, **fields: Any) -> None:
        self._gesture_sequence += 1
        self._gestures.append(
            {"gesture_id": f"gesture-{self._gesture_sequence}", "ts": observed_at, "kind": kind, **fields}
        )

    def _prune(self, observed_at: float) -> None:
        cutoff = observed_at - self.retention_seconds
        self._events = [item for item in self._events if _number(item.get("ts"), -1.0) >= cutoff][-self.max_events :]
        self._gestures = [item for item in self._gestures if _number(item.get("ts"), -1.0) >= cutoff][
            -self.max_events :
        ]

    def _write_state(
        self,
        *,
        observation: DesktopInputObservation | None,
        authority: dict[str, Any],
        state: str,
        blockers: list[str],
        updated_at: float,
    ) -> dict[str, Any]:
        pointer_age = (
            updated_at - self._last_pointer_activity_at if self._last_pointer_activity_at is not None else None
        )
        pointer_active = bool(pointer_age is not None and 0.0 <= pointer_age <= self.pointer_active_seconds)
        current = (
            {
                "cursor": {"x": observation.cursor_x, "y": observation.cursor_y},
                "buttons_down": list(observation.buttons_down),
                "foreground": {
                    "window_id": observation.foreground_window_id,
                    "process_id": observation.foreground_process_id,
                },
                "keyboard_activity": observation.keyboard_activity,
            }
            if observation is not None
            else {}
        )
        payload = {
            "kind": LENS_INPUT_EVENT_STREAM_KIND,
            "version": LENS_INPUT_EVENT_STREAM_VERSION,
            "status": state,
            "route": LENS_INPUT_EVENT_STREAM_ROUTE,
            "updated_at": updated_at,
            "authority_receipt_id": self.authority_receipt_id,
            "authority": authority,
            "retention_seconds": self.retention_seconds,
            "event_count": len(self._events),
            "gesture_count": len(self._gestures),
            "events": self._events,
            "gestures": self._gestures,
            "current": current,
            "pointer_activity": {
                "active": pointer_active,
                "age_seconds": round(pointer_age, 3) if pointer_age is not None else None,
                "orb_yield_required": pointer_active,
            },
            "capabilities": {
                "cursor_position": True,
                "pointer_button_activity": True,
                "foreground_window_identity": True,
                "scroll_activity": bool(observation and observation.scroll_source_connected),
                "keyboard_activity_timing": bool(observation and observation.keyboard_activity_source_connected),
            },
            "blockers": _dedupe(blockers),
            "governance": {
                "runtime_state_only": True,
                "observation_only": True,
                "desktop_input_observation_authority": True,
                "keyboard_content_captured": False,
                "key_codes_captured": False,
                "typed_characters_captured": False,
                "window_titles_captured": False,
                "clipboard_content_captured": False,
                "input_execution_authority": False,
                "user_cursor_control_authority": False,
                "memory_write": False,
            },
        }
        _atomic_write_json(_state_path(), payload)
        return lens_input_event_stream_readback(now=updated_at, authority_status=self._authority_status)


def lens_input_event_stream_readback(
    *,
    now: float | None = None,
    authority_status: AuthorityStatusProvider = lens_perception_input_authority_receipt_status,
) -> dict[str, Any]:
    observed_at = time.time() if now is None else float(now)
    payload = _read_json(_state_path())
    updated_at = _safe_float(payload.get("updated_at"))
    age_seconds = observed_at - updated_at if updated_at is not None else None
    fresh = bool(age_seconds is not None and 0.0 <= age_seconds <= _MAX_STATE_AGE_SECONDS)
    authority_receipt_id = str(payload.get("authority_receipt_id") or "")
    authority = authority_status(authority_receipt_id, now=int(observed_at)) if authority_receipt_id else {}
    blockers: list[str] = []
    if not payload:
        blockers.append("lens_input_event_stream_state_missing")
    else:
        if (
            payload.get("kind") != LENS_INPUT_EVENT_STREAM_KIND
            or payload.get("version") != LENS_INPUT_EVENT_STREAM_VERSION
        ):
            blockers.append("lens_input_event_stream_contract_invalid")
        if payload.get("status") != "observing":
            blockers.append("lens_input_event_stream_not_observing")
        if not fresh:
            blockers.append("lens_input_event_stream_state_stale")
        blockers.extend(_authority_blockers(authority))
        if not _items_valid(payload.get("events"), _EVENT_FIELDS) or not _items_valid(
            payload.get("gestures"), _GESTURE_FIELDS
        ):
            blockers.append("lens_input_event_stream_content_contract_invalid")
        governance = _as_dict(payload.get("governance"))
        if (
            governance.get("runtime_state_only") is not True
            or governance.get("observation_only") is not True
            or governance.get("desktop_input_observation_authority") is not True
        ):
            blockers.append("lens_input_event_stream_governance_invalid")
        if any(
            governance.get(name) is not False
            for name in (
                "keyboard_content_captured",
                "key_codes_captured",
                "typed_characters_captured",
                "window_titles_captured",
                "clipboard_content_captured",
                "input_execution_authority",
                "user_cursor_control_authority",
                "memory_write",
            )
        ):
            blockers.append("lens_input_event_stream_overbroad")
    blockers = _dedupe(blockers)
    ready = not blockers
    return {
        "kind": "lens.perception.desktop_input_event_stream_readback",
        "status": "ready" if ready else "missing" if not payload else "blocked",
        "route": LENS_INPUT_EVENT_STREAM_ROUTE,
        "ready": ready,
        "fresh": fresh,
        "updated_at": updated_at,
        "age_seconds": round(age_seconds, 3) if age_seconds is not None else None,
        "authority_receipt_id": authority_receipt_id,
        "authority": authority,
        "retention_seconds": payload.get("retention_seconds"),
        "event_count": int(payload.get("event_count") or 0),
        "gesture_count": int(payload.get("gesture_count") or 0),
        "events": payload.get("events") if isinstance(payload.get("events"), list) else [],
        "gestures": payload.get("gestures") if isinstance(payload.get("gestures"), list) else [],
        "current": _as_dict(payload.get("current")),
        "pointer_activity": _as_dict(payload.get("pointer_activity")),
        "capabilities": _as_dict(payload.get("capabilities")),
        "source_blockers": _string_items(payload.get("blockers")),
        "blockers": blockers,
        "governance": {
            "read_only_contract": True,
            "runtime_state_only": True,
            "keyboard_content_captured": False,
            "key_codes_captured": False,
            "typed_characters_captured": False,
            "window_titles_captured": False,
            "clipboard_content_captured": False,
            "input_execution_authority": False,
            "user_cursor_control_authority": False,
            "memory_write": False,
        },
    }


def _authority_blockers(authority: dict[str, Any]) -> list[str]:
    blockers = _string_items(authority.get("blockers"))
    authorities = _as_dict(authority.get("authorities"))
    if authority.get("active") is not True:
        blockers.append("desktop_input_observation_authority_not_active")
    if authority.get("active") is True and authorities.get("desktop_input_observation_authority") is not True:
        blockers.append("desktop_input_observation_authority_scope_invalid")
    return _dedupe(blockers)


def _blocked_readback(receipt_id: str, blockers: list[str], authority: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": "lens.perception.desktop_input_event_stream_readback",
        "status": "blocked",
        "route": LENS_INPUT_EVENT_STREAM_ROUTE,
        "ready": False,
        "fresh": False,
        "authority_receipt_id": receipt_id,
        "authority": authority,
        "events": [],
        "gestures": [],
        "current": {},
        "pointer_activity": {"active": False, "orb_yield_required": False},
        "blockers": _dedupe(blockers),
        "governance": {
            "read_only_contract": True,
            "keyboard_content_captured": False,
            "input_execution_authority": False,
            "user_cursor_control_authority": False,
        },
    }


def _target_fields(observation: DesktopInputObservation) -> dict[str, int]:
    return {
        "x": observation.cursor_x,
        "y": observation.cursor_y,
        "window_id": observation.foreground_window_id,
        "process_id": observation.foreground_process_id,
    }


def _items_valid(value: Any, fields_by_kind: dict[str, set[str]]) -> bool:
    if not isinstance(value, list):
        return False
    for item in value:
        if not isinstance(item, dict):
            return False
        allowed = fields_by_kind.get(str(item.get("kind") or ""))
        if allowed is None or set(item) != allowed:
            return False
    return True


def _state_path() -> Path:
    return data_dir() / "runtime" / "lens-perception" / "input-events.json"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig", errors="replace"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / f".{os.getpid():x}.{time.time_ns():x}.tmp"
    try:
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _safe_float(value: Any, default: float | None = None) -> float | None:
    if isinstance(value, bool):
        return default
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if math.isfinite(parsed) else default


def _number(value: Any, default: float) -> float:
    parsed = _safe_float(value)
    return default if parsed is None else parsed


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _string_items(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


__all__ = [
    "DesktopInputObservation",
    "LensInputEventStream",
    "Win32DesktopInputObservationSource",
    "lens_input_event_stream_readback",
]
