from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from francis.kernel.paths import repo_root

from .contracts import InputActuatorError

ORB_DESKTOP_BRIDGE_STAGE = "Phase 2 / Lens Orb embodied desktop operation"
ORB_DESKTOP_BRIDGE_ENV_GATE = "FRANCIS_ORB_DESKTOP_BRIDGE_ENABLE=1"
ORB_DESKTOP_BRIDGE_BACKEND_ENV = "FRANCIS_ORB_DESKTOP_BRIDGE_BACKEND"
ORB_DESKTOP_BRIDGE_DEFAULT_BACKEND = "win32_post_message"
ORB_DESKTOP_BRIDGE_SOURCE_ID = "orb_desktop_bridge"
_MAX_COORD = 10000
_OVERLAY_TITLES = {"Francis Lens Overlay"}
_BLOCKED_TITLE_FRAGMENTS = ("claude",)
_BLOCKED_WINDOW_CLASSES = {
    "Progman",
    "Shell_TrayWnd",
    "Shell_SecondaryTrayWnd",
    "WorkerW",
}
_OBSERVER_POLL_SECONDS = 0.35
_OBSERVER_POLL_INTERVAL_SECONDS = 0.025


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _state_root() -> Path:
    override = os.environ.get("FRANCIS_ORB_OPERATOR_STATE_DIR")
    root = Path(override) if override else repo_root() / ".francis" / "orb_operator"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _receipt_dir() -> Path:
    path = _state_root() / "desktop_bridge_receipts"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _clean_text(value: Any, default: str = "") -> str:
    text = str(value if value is not None else default).strip()
    return " ".join(part.strip() for part in text.splitlines() if part.strip())


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if isinstance(value, bool):
            return int(value)
        return int(value)
    except (TypeError, ValueError):
        return default


def _bounded_coord(value: Any, name: str) -> int:
    number = _safe_int(value, -1)
    if number < 0 or number > _MAX_COORD:
        raise InputActuatorError(f"{name} coordinate out of bounds")
    return number


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _public_action(kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    if kind == "mouse.click":
        public: dict[str, Any] = {
            "kind": kind,
            "button": _clean_text(payload.get("button"), "left").lower(),
            "clicks": max(1, min(_safe_int(payload.get("clicks"), 1), 3)),
        }
        if payload.get("x") is not None and payload.get("y") is not None:
            public["x"] = _bounded_coord(payload.get("x"), "x")
            public["y"] = _bounded_coord(payload.get("y"), "y")
        return public
    if kind == "mouse.drag":
        return {
            "kind": kind,
            "button": _clean_text(payload.get("button"), "left").lower(),
            "x": _bounded_coord(payload.get("x"), "x"),
            "y": _bounded_coord(payload.get("y"), "y"),
            "target_x": _bounded_coord(payload.get("target_x"), "target_x"),
            "target_y": _bounded_coord(payload.get("target_y"), "target_y"),
        }
    if kind == "keyboard.type":
        text = str(payload.get("text", ""))
        return {"kind": kind, "text_length": len(text), "text_sha256": _hash_text(text)}
    if kind == "keyboard.hotkey":
        raw_keys = payload.get("keys")
        keys = raw_keys if isinstance(raw_keys, list) else []
        return {"kind": kind, "keys": [_clean_text(item).lower() for item in keys]}
    return {"kind": kind}


def _bridge_enabled() -> bool:
    return os.environ.get("FRANCIS_ORB_DESKTOP_BRIDGE_ENABLE", "").strip() == "1"


def _bridge_backend() -> str:
    return _clean_text(os.environ.get(ORB_DESKTOP_BRIDGE_BACKEND_ENV), ORB_DESKTOP_BRIDGE_DEFAULT_BACKEND)


@dataclass(frozen=True)
class _WindowTarget:
    hwnd: int
    title: str
    class_name: str
    rect: tuple[int, int, int, int]
    client_x: int
    client_y: int
    child_hwnd: int = 0
    child_class_name: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "hwnd": self.hwnd,
            "title": self.title[:160],
            "class_name": self.class_name[:160],
            "rect": {
                "left": self.rect[0],
                "top": self.rect[1],
                "right": self.rect[2],
                "bottom": self.rect[3],
            },
            "client_x": self.client_x,
            "client_y": self.client_y,
            "child_hwnd": self.child_hwnd,
            "child_class_name": self.child_class_name[:160],
            "target_hwnd": self.child_hwnd or self.hwnd,
        }


def perform_orb_desktop_action(
    *,
    input_kind: str,
    payload: dict[str, Any],
    actor: str,
    objective: str,
    session_id: str,
) -> dict[str, Any]:
    """Attempt a real desktop action from the Orb coordinate without moving the user's cursor."""

    safe_kind = _clean_text(input_kind)
    public_action = _public_action(safe_kind, payload)
    backend = _bridge_backend()
    base = {
        "input_kind": safe_kind,
        "public_action": public_action,
        "actor": _clean_text(actor)[:240],
        "objective": _clean_text(objective)[:500],
        "session_id": _clean_text(session_id)[:160],
        "backend": backend,
        "env_gate": ORB_DESKTOP_BRIDGE_ENV_GATE,
        "uses_user_os_cursor": False,
        "user_mouse_taken": False,
        "physical_input_performed": False,
        "raw_input": False,
    }

    if safe_kind not in {"mouse.click", "mouse.drag", "keyboard.type"}:
        return _finish_attempt(
            {
                **base,
                "ok": False,
                "status": "blocked_unsupported_orb_desktop_action",
                "desktop_action_sent": False,
                "desktop_effect_performed": False,
                "desktop_effect_confirmed": False,
                "error": f"unsupported Orb desktop action: {safe_kind}",
            }
        )

    if not _bridge_enabled():
        return _finish_attempt(
            {
                **base,
                "ok": False,
                "status": "blocked_bridge_disabled",
                "desktop_action_sent": False,
                "desktop_effect_performed": False,
                "desktop_effect_confirmed": False,
                "error": f"Orb desktop bridge requires {ORB_DESKTOP_BRIDGE_ENV_GATE}",
            }
        )

    if backend != ORB_DESKTOP_BRIDGE_DEFAULT_BACKEND:
        return _finish_attempt(
            {
                **base,
                "ok": False,
                "status": "blocked_unsupported_backend",
                "desktop_action_sent": False,
                "desktop_effect_performed": False,
                "desktop_effect_confirmed": False,
                "error": f"unsupported Orb desktop bridge backend: {backend}",
            }
        )

    if os.name != "nt":
        return _finish_attempt(
            {
                **base,
                "ok": False,
                "status": "blocked_unsupported_platform",
                "desktop_action_sent": False,
                "desktop_effect_performed": False,
                "desktop_effect_confirmed": False,
                "error": "Orb desktop bridge currently supports Windows only",
            }
        )

    try:
        result = _perform_win32_post_message(safe_kind, payload)
    except Exception as exc:
        result = {
            "ok": False,
            "status": "backend_error",
            "desktop_action_sent": False,
            "desktop_effect_performed": False,
            "desktop_effect_confirmed": False,
            "error": str(exc),
        }
    return _finish_attempt({**base, **result})


def _finish_attempt(payload: dict[str, Any]) -> dict[str, Any]:
    receipt_id = f"orb_desktop_bridge_{uuid.uuid4().hex[:12]}"
    result = {
        "ok": bool(payload.get("ok")),
        "status": _clean_text(payload.get("status"), "blocked"),
        "receipt_id": receipt_id,
        "stage": ORB_DESKTOP_BRIDGE_STAGE,
        "source_id": ORB_DESKTOP_BRIDGE_SOURCE_ID,
        "backend": _clean_text(payload.get("backend"), ORB_DESKTOP_BRIDGE_DEFAULT_BACKEND),
        "env_gate": ORB_DESKTOP_BRIDGE_ENV_GATE,
        "input_kind": _clean_text(payload.get("input_kind")),
        "public_action": payload.get("public_action") if isinstance(payload.get("public_action"), dict) else {},
        "target": payload.get("target") if isinstance(payload.get("target"), dict) else {},
        "desktop_action_sent": bool(payload.get("desktop_action_sent")),
        "desktop_effect_performed": bool(payload.get("desktop_effect_performed")),
        "desktop_effect_confirmed": bool(payload.get("desktop_effect_confirmed")),
        "target_observer_status": _clean_text(payload.get("target_observer_status")),
        "target_state_changed": bool(payload.get("target_state_changed")),
        "target_observer_polls": _safe_int(payload.get("target_observer_polls"), 0),
        "target_observation_before": (
            payload.get("target_observation_before")
            if isinstance(payload.get("target_observation_before"), dict)
            else {}
        ),
        "target_observation_after": (
            payload.get("target_observation_after") if isinstance(payload.get("target_observation_after"), dict) else {}
        ),
        "uses_user_os_cursor": False,
        "user_mouse_taken": False,
        "physical_input_performed": False,
        "raw_input": False,
        "message_delivery": _clean_text(payload.get("message_delivery")),
        "error": _clean_text(payload.get("error")),
        "governance": {
            "mode": "orb_pointer_desktop_bridge",
            "env_gate_required": True,
            "env_gate": ORB_DESKTOP_BRIDGE_ENV_GATE,
            "uses_user_os_cursor": False,
            "user_mouse_taken": False,
            "physical_input_performed": False,
            "desktop_effect_confirmed": bool(payload.get("desktop_effect_confirmed")),
            "raw_input": False,
            "receipt_written": True,
        },
    }
    receipt = {
        "ok": result["ok"],
        "kind": "francis.orb_desktop_bridge.receipt",
        "receipt_id": receipt_id,
        "stage": ORB_DESKTOP_BRIDGE_STAGE,
        "source_id": ORB_DESKTOP_BRIDGE_SOURCE_ID,
        "created_at": _utc_now(),
        "payload": {
            "input_kind": result["input_kind"],
            "public_action": result["public_action"],
            "actor": _clean_text(payload.get("actor"))[:240],
            "objective": _clean_text(payload.get("objective"))[:500],
            "session_id": _clean_text(payload.get("session_id"))[:160],
            "backend": result["backend"],
            "target": result["target"],
            "status": result["status"],
            "desktop_action_sent": result["desktop_action_sent"],
            "desktop_effect_performed": result["desktop_effect_performed"],
            "desktop_effect_confirmed": result["desktop_effect_confirmed"],
            "target_observer_status": result["target_observer_status"],
            "target_state_changed": result["target_state_changed"],
            "target_observer_polls": result["target_observer_polls"],
            "target_observation_before": result["target_observation_before"],
            "target_observation_after": result["target_observation_after"],
            "message_delivery": result["message_delivery"],
            "error": result["error"],
        },
        "governance": result["governance"],
    }
    path = _receipt_dir() / f"{receipt_id}.json"
    path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    result["receipt_path"] = str(path)
    result["receipt_written"] = True
    return result


def _perform_win32_post_message(kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    target = _target_for_payload(kind, payload)
    if target is None:
        return {
            "ok": False,
            "status": "blocked_no_target_window",
            "desktop_action_sent": False,
            "desktop_effect_performed": False,
            "desktop_effect_confirmed": False,
            "message_delivery": "not_sent",
            "error": "no non-Francis desktop window resolved at Orb coordinate",
        }

    observation_before = _observe_target_state(target)
    if kind == "mouse.click":
        _post_mouse_click(target, payload)
    elif kind == "mouse.drag":
        _post_mouse_drag(target, payload)
    elif kind == "keyboard.type":
        _post_text(target, str(payload.get("text", "")))
    else:
        raise InputActuatorError(f"unsupported Orb desktop bridge action: {kind}")

    confirmation = _confirm_target_effect(target, observation_before)
    return {
        "ok": True,
        "status": "desktop_action_confirmed" if confirmation["desktop_effect_confirmed"] else "desktop_action_sent",
        "desktop_action_sent": True,
        "desktop_effect_performed": True,
        "desktop_effect_confirmed": confirmation["desktop_effect_confirmed"],
        "target": target.to_dict(),
        "target_observer_status": confirmation["target_observer_status"],
        "target_state_changed": confirmation["target_state_changed"],
        "target_observer_polls": confirmation["target_observer_polls"],
        "target_observation_before": confirmation["target_observation_before"],
        "target_observation_after": confirmation["target_observation_after"],
        "message_delivery": "posted_to_target_window",
    }


def _target_for_payload(kind: str, payload: dict[str, Any]) -> _WindowTarget | None:
    if kind in {"mouse.click", "mouse.drag"}:
        x = _bounded_coord(payload.get("x"), "x")
        y = _bounded_coord(payload.get("y"), "y")
    else:
        x = _bounded_coord(payload.get("x"), "x")
        y = _bounded_coord(payload.get("y"), "y")
    return _resolve_target_window(x, y)


def _resolve_target_window(x: int, y: int) -> _WindowTarget | None:
    try:
        import win32gui  # type: ignore[import-not-found]
    except ImportError as exc:
        raise InputActuatorError("win32gui is required for the Orb desktop bridge") from exc

    candidates: list[int] = []

    def collect(hwnd: int, _extra: object) -> None:
        if not win32gui.IsWindowVisible(hwnd) or not win32gui.IsWindowEnabled(hwnd):
            return
        title = _clean_text(win32gui.GetWindowText(hwnd))
        class_name = _clean_text(win32gui.GetClassName(hwnd))
        if not _safe_window_target(title=title, class_name=class_name):
            return
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        if left <= x < right and top <= y < bottom:
            candidates.append(hwnd)

    win32gui.EnumWindows(collect, None)
    if not candidates:
        return None

    hwnd = candidates[0]
    title = _clean_text(win32gui.GetWindowText(hwnd))
    class_name = _clean_text(win32gui.GetClassName(hwnd))
    rect = tuple(int(item) for item in win32gui.GetWindowRect(hwnd))
    target_hwnd = hwnd
    child_hwnd = 0
    child_class = ""
    client_x, client_y = win32gui.ScreenToClient(hwnd, (x, y))
    try:
        child = int(win32gui.ChildWindowFromPoint(hwnd, (client_x, client_y)))
    except Exception:
        child = 0
    if child and child != hwnd:
        child_hwnd = child
        target_hwnd = child
        child_class = _clean_text(win32gui.GetClassName(child))
        client_x, client_y = win32gui.ScreenToClient(child, (x, y))

    return _WindowTarget(
        hwnd=hwnd,
        title=title,
        class_name=class_name,
        rect=rect,  # type: ignore[arg-type]
        client_x=int(client_x),
        client_y=int(client_y),
        child_hwnd=child_hwnd if target_hwnd != hwnd else 0,
        child_class_name=child_class,
    )


def _safe_window_target(*, title: str, class_name: str) -> bool:
    normalized_title = _clean_text(title).casefold()
    if not normalized_title:
        return False
    if title in _OVERLAY_TITLES:
        return False
    if any(fragment in normalized_title for fragment in _BLOCKED_TITLE_FRAGMENTS):
        return False
    if class_name in _BLOCKED_WINDOW_CLASSES:
        return False
    return True


def _target_hwnd(target: _WindowTarget) -> int:
    return target.child_hwnd or target.hwnd


def _observe_target_state(target: _WindowTarget) -> dict[str, Any]:
    try:
        import win32gui  # type: ignore[import-not-found]
    except ImportError as exc:
        raise InputActuatorError("win32gui is required for the Orb desktop bridge") from exc

    hwnd = _target_hwnd(target)
    try:
        text = _clean_text(win32gui.GetWindowText(hwnd))
        top_level_title = _clean_text(win32gui.GetWindowText(target.hwnd))
        class_name = _clean_text(win32gui.GetClassName(hwnd))
        rect = tuple(int(item) for item in win32gui.GetWindowRect(target.hwnd))
        visible = bool(win32gui.IsWindowVisible(target.hwnd))
        enabled = bool(win32gui.IsWindowEnabled(target.hwnd))
    except Exception as exc:
        return {
            "observable": False,
            "observer_error": _clean_text(exc)[:240],
            "text_redacted": True,
            "raw_text_stored": False,
            "observed_at": _utc_now(),
        }

    return {
        "observable": True,
        "target_hwnd": hwnd,
        "top_level_hwnd": target.hwnd,
        "class_name": class_name[:160],
        "visible": visible,
        "enabled": enabled,
        "rect": {
            "left": rect[0],
            "top": rect[1],
            "right": rect[2],
            "bottom": rect[3],
        },
        "text_length": len(text),
        "text_sha256": _hash_text(text),
        "top_level_title_length": len(top_level_title),
        "top_level_title_sha256": _hash_text(top_level_title),
        "text_redacted": True,
        "raw_text_stored": False,
        "observed_at": _utc_now(),
    }


def _target_state_changed(before: dict[str, Any], after: dict[str, Any]) -> bool:
    if not before.get("observable") or not after.get("observable"):
        return False
    comparable_fields = (
        "visible",
        "enabled",
        "text_length",
        "text_sha256",
        "top_level_title_length",
        "top_level_title_sha256",
    )
    return any(before.get(field) != after.get(field) for field in comparable_fields)


def _confirm_target_effect(target: _WindowTarget, before: dict[str, Any]) -> dict[str, Any]:
    after = _observe_target_state(target)
    polls = 1
    deadline = time.monotonic() + _OBSERVER_POLL_SECONDS
    while not _target_state_changed(before, after) and time.monotonic() < deadline:
        time.sleep(_OBSERVER_POLL_INTERVAL_SECONDS)
        polls += 1
        after = _observe_target_state(target)

    changed = _target_state_changed(before, after)
    observer_status = "confirmed_target_state_changed" if changed else "observed_no_target_state_change"
    if not before.get("observable") or not after.get("observable"):
        observer_status = "target_state_observer_unavailable"
    return {
        "desktop_effect_confirmed": changed,
        "target_state_changed": changed,
        "target_observer_status": observer_status,
        "target_observer_polls": polls,
        "target_observation_before": before,
        "target_observation_after": after,
    }


def _make_lparam(x: int, y: int) -> int:
    return (int(y) & 0xFFFF) << 16 | (int(x) & 0xFFFF)


def _post_mouse_click(target: _WindowTarget, payload: dict[str, Any]) -> None:
    try:
        import win32gui  # type: ignore[import-not-found]
    except ImportError as exc:
        raise InputActuatorError("win32gui is required for the Orb desktop bridge") from exc

    button = _clean_text(payload.get("button"), "left").lower()
    messages = {
        "left": (0x0201, 0x0202, 0x0001),
        "right": (0x0204, 0x0205, 0x0002),
        "middle": (0x0207, 0x0208, 0x0010),
    }.get(button)
    if messages is None:
        raise InputActuatorError(f"unsupported mouse button: {button}")
    down, up, wparam = messages
    lparam = _make_lparam(target.client_x, target.client_y)
    hwnd = _target_hwnd(target)
    for _ in range(max(1, min(_safe_int(payload.get("clicks"), 1), 3))):
        win32gui.PostMessage(hwnd, down, wparam, lparam)
        time.sleep(0.02)
        win32gui.PostMessage(hwnd, up, 0, lparam)
        time.sleep(0.02)


def _post_mouse_drag(target: _WindowTarget, payload: dict[str, Any]) -> None:
    try:
        import win32gui  # type: ignore[import-not-found]
    except ImportError as exc:
        raise InputActuatorError("win32gui is required for the Orb desktop bridge") from exc

    start_x = _bounded_coord(payload.get("x"), "x")
    start_y = _bounded_coord(payload.get("y"), "y")
    end_x = _bounded_coord(payload.get("target_x"), "target_x")
    end_y = _bounded_coord(payload.get("target_y"), "target_y")
    hwnd = _target_hwnd(target)
    client_start = win32gui.ScreenToClient(hwnd, (start_x, start_y))
    client_end = win32gui.ScreenToClient(hwnd, (end_x, end_y))
    down = 0x0201
    move = 0x0200
    up = 0x0202
    held = 0x0001
    win32gui.PostMessage(hwnd, down, held, _make_lparam(client_start[0], client_start[1]))
    for index in range(1, 5):
        ratio = index / 4
        x = round(client_start[0] + ((client_end[0] - client_start[0]) * ratio))
        y = round(client_start[1] + ((client_end[1] - client_start[1]) * ratio))
        win32gui.PostMessage(hwnd, move, held, _make_lparam(x, y))
        time.sleep(0.02)
    win32gui.PostMessage(hwnd, up, 0, _make_lparam(client_end[0], client_end[1]))


def _post_text(target: _WindowTarget, text: str) -> None:
    if not text:
        raise InputActuatorError("keyboard.type requires text")
    try:
        import win32gui  # type: ignore[import-not-found]
    except ImportError as exc:
        raise InputActuatorError("win32gui is required for the Orb desktop bridge") from exc

    hwnd = _target_hwnd(target)
    for character in text:
        win32gui.PostMessage(hwnd, 0x0102, ord(character), 1)
        time.sleep(0.005)
