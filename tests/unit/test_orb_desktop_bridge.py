from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

from francis.input_actuator import orb_desktop_bridge

pytestmark = pytest.mark.unit


class FakeWin32Gui:
    def __init__(self, windows: dict[int, dict[str, Any]]) -> None:
        self.windows = windows
        self.posts: list[tuple[int, int, int, int]] = []

    def IsWindowVisible(self, hwnd: int) -> bool:
        return bool(self.windows[hwnd].get("visible", True))

    def IsWindowEnabled(self, hwnd: int) -> bool:
        return bool(self.windows[hwnd].get("enabled", True))

    def GetWindowText(self, hwnd: int) -> str:
        return str(self.windows[hwnd].get("text", self.windows[hwnd].get("title", "")))

    def GetClassName(self, hwnd: int) -> str:
        return str(self.windows[hwnd].get("class_name", "Window"))

    def GetWindowRect(self, hwnd: int) -> tuple[int, int, int, int]:
        return tuple(self.windows[hwnd].get("rect", (0, 0, 100, 100)))  # type: ignore[return-value]

    def EnumWindows(self, callback: Any, extra: Any) -> None:
        for hwnd in self.windows:
            if not self.windows[hwnd].get("child", False):
                callback(hwnd, extra)

    def FindWindow(self, class_name: str, _title: Any) -> int:
        for hwnd, window in self.windows.items():
            if window.get("child", False):
                continue
            if str(window.get("class_name", "")) == class_name:
                return hwnd
        return 0

    def FindWindowEx(self, parent: int, _after: int, class_name: str, _title: Any) -> int:
        for hwnd, window in self.windows.items():
            if int(window.get("parent", 0)) == parent and str(window.get("class_name", "")) == class_name:
                return hwnd
        return 0

    def ScreenToClient(self, hwnd: int, point: tuple[int, int]) -> tuple[int, int]:
        left, top, _right, _bottom = self.GetWindowRect(hwnd)
        return point[0] - left, point[1] - top

    def ChildWindowFromPoint(self, hwnd: int, _point: tuple[int, int]) -> int:
        child = int(self.windows[hwnd].get("child_hwnd", 0))
        return child or hwnd

    def PostMessage(self, hwnd: int, message: int, wparam: int, lparam: int) -> bool:
        self.posts.append((hwnd, message, wparam, lparam))
        if message == 0x0102:
            self.windows[hwnd]["text"] = str(self.windows[hwnd].get("text", "")) + chr(wparam)
        return True


def _state_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FRANCIS_ORB_OPERATOR_STATE_DIR", str(tmp_path / "orb_operator"))
    monkeypatch.delenv("FRANCIS_ORB_DESKTOP_BRIDGE_ENABLE", raising=False)
    monkeypatch.delenv("FRANCIS_ORB_DESKTOP_BRIDGE_BACKEND", raising=False)


def _install_fake_win32gui(monkeypatch: pytest.MonkeyPatch, windows: dict[int, dict[str, Any]]) -> FakeWin32Gui:
    fake = FakeWin32Gui(windows)
    monkeypatch.setitem(sys.modules, "win32gui", fake)
    monkeypatch.setattr(orb_desktop_bridge, "_win32_platform_supported", lambda: True)
    return fake


def test_disabled_bridge_writes_blocked_receipt_without_win32_lookup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _state_env(tmp_path, monkeypatch)
    text = "raw disabled bridge secret"

    result = orb_desktop_bridge.perform_orb_desktop_action(
        input_kind="keyboard.type",
        payload={"x": 10, "y": 20, "text": text},
        actor="test",
        objective="disabled bridge remains visible only",
        session_id="disabled-bridge",
    )

    receipt_text = Path(result["receipt_path"]).read_text(encoding="utf-8")
    assert result["ok"] is False
    assert result["status"] == "blocked_bridge_disabled"
    assert result["desktop_action_sent"] is False
    assert result["desktop_effect_performed"] is False
    assert result["desktop_effect_confirmed"] is False
    assert result["target_observer_status"] == ""
    assert text not in receipt_text


def test_keyboard_type_confirms_target_side_state_change_and_redacts_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _state_env(tmp_path, monkeypatch)
    monkeypatch.setenv("FRANCIS_ORB_DESKTOP_BRIDGE_ENABLE", "1")
    text = "raw bridge confirmation secret"
    fake = _install_fake_win32gui(
        monkeypatch,
        {
            100: {
                "title": "Safe Scratchpad",
                "class_name": "SafeWindow",
                "rect": (0, 0, 300, 240),
                "child_hwnd": 101,
            },
            101: {
                "child": True,
                "text": "",
                "class_name": "Edit",
                "rect": (0, 0, 300, 240),
            },
        },
    )

    result = orb_desktop_bridge.perform_orb_desktop_action(
        input_kind="keyboard.type",
        payload={"x": 10, "y": 20, "text": text},
        actor="test",
        objective="confirm typed target-side state",
        session_id="confirmed-type",
    )

    receipt_text = Path(result["receipt_path"]).read_text(encoding="utf-8")
    assert result["ok"] is True
    assert result["status"] == "desktop_action_confirmed"
    assert result["desktop_action_sent"] is True
    assert result["desktop_effect_performed"] is True
    assert result["desktop_effect_confirmed"] is True
    assert result["target_observer_status"] == "confirmed_target_state_changed"
    assert result["target_state_changed"] is True
    assert result["target_observation_before"]["text_length"] == 0
    assert result["target_observation_after"]["text_length"] == len(text)
    assert result["target_observation_after"]["raw_text_stored"] is False
    assert fake.windows[101]["text"] == text
    assert text not in receipt_text


def test_keyboard_type_filters_overlapping_windows_to_expected_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _state_env(tmp_path, monkeypatch)
    monkeypatch.setenv("FRANCIS_ORB_DESKTOP_BRIDGE_ENABLE", "1")
    text = "approved target only"
    fake = _install_fake_win32gui(
        monkeypatch,
        {
            100: {
                "title": "Unapproved Overlapping Window",
                "class_name": "ConsoleWindowClass",
                "rect": (0, 0, 300, 240),
            },
            200: {
                "title": "Approved Safe Target",
                "class_name": "SafeWindow",
                "rect": (0, 0, 300, 240),
                "child_hwnd": 201,
            },
            201: {
                "child": True,
                "text": "",
                "class_name": "Edit",
                "rect": (0, 0, 300, 240),
            },
        },
    )

    result = orb_desktop_bridge.perform_orb_desktop_action(
        input_kind="keyboard.type",
        payload={
            "x": 10,
            "y": 20,
            "text": text,
            "expected_target_title": "Approved Safe Target",
        },
        actor="test",
        objective="target only the explicitly approved overlapping window",
        session_id="expected-target-title",
    )

    assert result["status"] == "desktop_action_confirmed"
    assert result["target"]["title"] == "Approved Safe Target"
    assert fake.windows[100].get("text", "") == ""
    assert fake.windows[201]["text"] == text
    assert {post[0] for post in fake.posts} == {201}
    assert result["public_action"]["expected_target_title_present"] is True
    assert "expected_target_title" not in result["public_action"]


def test_mouse_click_does_not_claim_confirmation_without_observed_state_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _state_env(tmp_path, monkeypatch)
    monkeypatch.setenv("FRANCIS_ORB_DESKTOP_BRIDGE_ENABLE", "1")
    fake = _install_fake_win32gui(
        monkeypatch,
        {
            100: {
                "title": "Safe Button Surface",
                "text": "unchanged",
                "class_name": "SafeWindow",
                "rect": (0, 0, 300, 240),
            },
        },
    )

    result = orb_desktop_bridge.perform_orb_desktop_action(
        input_kind="mouse.click",
        payload={"x": 10, "y": 20, "button": "left", "clicks": 1},
        actor="test",
        objective="do not overclaim click effect",
        session_id="unconfirmed-click",
    )

    assert result["ok"] is True
    assert result["status"] == "desktop_action_sent"
    assert result["desktop_action_sent"] is True
    assert result["desktop_effect_performed"] is True
    assert result["desktop_effect_confirmed"] is False
    assert result["target_observer_status"] == "observed_no_target_state_change"
    assert result["target_state_changed"] is False
    assert fake.posts


def test_user_mouse_drag_backend_records_physical_cursor_use(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _state_env(tmp_path, monkeypatch)
    monkeypatch.setenv("FRANCIS_ORB_DESKTOP_BRIDGE_ENABLE", "1")
    monkeypatch.setenv("FRANCIS_ORB_DESKTOP_BRIDGE_BACKEND", "win32_user_mouse_drag")
    fake = _install_fake_win32gui(
        monkeypatch,
        {
            100: {
                "title": "Safe Desktop Surface",
                "text": "unchanged",
                "class_name": "SafeWindow",
                "rect": (0, 0, 300, 240),
            },
        },
    )
    drags: list[dict[str, object]] = []

    def fake_drag(payload: dict[str, object]) -> None:
        drags.append(payload)

    monkeypatch.setattr(orb_desktop_bridge, "_drag_user_mouse", fake_drag)

    result = orb_desktop_bridge.perform_orb_desktop_action(
        input_kind="mouse.drag",
        payload={"x": 10, "y": 20, "target_x": 60, "target_y": 80, "button": "left"},
        actor="test",
        objective="perform a real click hold drag gesture",
        session_id="user-mouse-drag",
    )

    assert result["ok"] is True
    assert result["status"] == "desktop_action_sent"
    assert result["backend"] == "win32_user_mouse_drag"
    assert result["desktop_action_sent"] is True
    assert result["desktop_effect_performed"] is True
    assert result["desktop_effect_confirmed"] is False
    assert result["uses_user_os_cursor"] is True
    assert result["user_mouse_taken"] is True
    assert result["physical_input_performed"] is True
    assert result["governance"]["uses_user_os_cursor"] is True
    assert result["governance"]["physical_input_performed"] is True
    assert result["message_delivery"] == "sent_via_win32_user_mouse_drag"
    assert drags == [{"x": 10, "y": 20, "target_x": 60, "target_y": 80, "button": "left"}]
    assert fake.posts == []


def test_user_mouse_drag_backend_targets_desktop_shell_when_required(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _state_env(tmp_path, monkeypatch)
    monkeypatch.setenv("FRANCIS_ORB_DESKTOP_BRIDGE_ENABLE", "1")
    monkeypatch.setenv("FRANCIS_ORB_DESKTOP_BRIDGE_BACKEND", "win32_user_mouse_drag")
    fake = _install_fake_win32gui(
        monkeypatch,
        {
            100: {"class_name": "Progman", "rect": (0, 0, 900, 700), "text": ""},
            101: {"child": True, "parent": 100, "class_name": "SHELLDLL_DefView", "rect": (0, 0, 900, 700)},
            102: {
                "child": True,
                "parent": 101,
                "class_name": "SysListView32",
                "text": "desktop-shell",
                "rect": (0, 0, 900, 700),
            },
            200: {"title": "Covered Window", "class_name": "SafeWindow", "rect": (0, 0, 900, 700)},
        },
    )
    drags: list[dict[str, object]] = []

    monkeypatch.setattr(
        orb_desktop_bridge,
        "_expose_desktop_shell_for_drag",
        lambda: {"ok": True, "performed": True, "method": "test"},
    )
    monkeypatch.setattr(
        orb_desktop_bridge,
        "_desktop_shell_listview_items",
        lambda *, limit: [
            {
                "index": 4,
                "label": "Approved Icon",
                "current_rect": {"left": 26, "top": 104, "width": 96, "height": 96},
            }
        ],
    )

    def fake_drag(payload: dict[str, object]) -> None:
        drags.append(payload)

    monkeypatch.setattr(orb_desktop_bridge, "_drag_user_mouse", fake_drag)

    result = orb_desktop_bridge.perform_orb_desktop_action(
        input_kind="mouse.drag",
        payload={
            "x": 74,
            "y": 152,
            "target_x": 266,
            "target_y": 152,
            "button": "left",
            "desktop_shell_target_required": True,
            "semantic_target_id": "desktop-icon-a",
            "desktop_position_index": 4,
        },
        actor="test",
        objective="perform a desktop shell click hold drag",
        session_id="desktop-shell-drag",
    )

    assert result["ok"] is True
    assert result["backend"] == "win32_user_mouse_drag"
    assert result["desktop_shell_target_required"] is True
    assert result["desktop_shell_exposure"] == {"ok": True, "performed": True, "method": "test"}
    assert result["target"]["class_name"] == "SysListView32"
    assert result["target"]["title"] == "Windows Desktop"
    assert result["uses_user_os_cursor"] is True
    assert result["physical_input_performed"] is True
    assert drags
    assert fake.posts == []


def test_user_mouse_drag_backend_denies_when_shell_point_is_not_approved_item(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _state_env(tmp_path, monkeypatch)
    monkeypatch.setenv("FRANCIS_ORB_DESKTOP_BRIDGE_ENABLE", "1")
    monkeypatch.setenv("FRANCIS_ORB_DESKTOP_BRIDGE_BACKEND", "win32_user_mouse_drag")
    _install_fake_win32gui(
        monkeypatch,
        {
            100: {"class_name": "Progman", "rect": (0, 0, 900, 700), "text": ""},
            101: {"child": True, "parent": 100, "class_name": "SHELLDLL_DefView", "rect": (0, 0, 900, 700)},
            102: {
                "child": True,
                "parent": 101,
                "class_name": "SysListView32",
                "text": "desktop-shell",
                "rect": (0, 0, 900, 700),
            },
        },
    )
    monkeypatch.setattr(
        orb_desktop_bridge,
        "_expose_desktop_shell_for_drag",
        lambda: {"ok": True, "performed": True, "method": "test"},
    )
    monkeypatch.setattr(
        orb_desktop_bridge,
        "_desktop_shell_listview_items",
        lambda *, limit: [
            {
                "index": 4,
                "label": "Approved Icon",
                "current_rect": {"left": 300, "top": 300, "width": 96, "height": 96},
            }
        ],
    )
    drags: list[dict[str, object]] = []
    monkeypatch.setattr(orb_desktop_bridge, "_drag_user_mouse", lambda payload: drags.append(payload))

    result = orb_desktop_bridge.perform_orb_desktop_action(
        input_kind="mouse.drag",
        payload={
            "x": 74,
            "y": 136,
            "target_x": 362,
            "target_y": 136,
            "button": "left",
            "desktop_shell_target_required": True,
            "semantic_target_id": "desktop-icon-a",
            "desktop_position_index": 4,
        },
        actor="test",
        objective="deny mismatched shell target before mouse input",
        session_id="desktop-shell-drag-mismatch",
    )

    assert result["ok"] is False
    assert result["status"] == "blocked_desktop_shell_target_mismatch"
    assert result["desktop_action_sent"] is False
    assert result["physical_input_performed"] is False
    assert result["desktop_shell_target_check"]["ok"] is False
    assert result["desktop_shell_target_check"]["error"] == "desktop_shell_start_point_not_on_approved_item"
    assert drags == []


def test_target_resolution_excludes_francis_overlay_and_claude_windows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _state_env(tmp_path, monkeypatch)
    monkeypatch.setenv("FRANCIS_ORB_DESKTOP_BRIDGE_ENABLE", "1")
    fake = _install_fake_win32gui(
        monkeypatch,
        {
            100: {
                "title": "Francis Lens Overlay",
                "class_name": "OverlayWindow",
                "rect": (0, 0, 300, 240),
            },
            200: {
                "title": "Claude",
                "class_name": "Chrome_WidgetWin_1",
                "rect": (0, 0, 300, 240),
            },
        },
    )

    result = orb_desktop_bridge.perform_orb_desktop_action(
        input_kind="mouse.click",
        payload={"x": 10, "y": 20, "button": "left", "clicks": 1},
        actor="test",
        objective="blocked unsafe targets",
        session_id="blocked-targets",
    )

    assert result["ok"] is False
    assert result["status"] == "blocked_no_target_window"
    assert result["desktop_action_sent"] is False
    assert result["desktop_effect_confirmed"] is False
    assert fake.posts == []
