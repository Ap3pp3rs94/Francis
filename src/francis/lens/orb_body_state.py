"""Read-only canonical native Orb body state for the Situation Model."""

from __future__ import annotations

import ctypes
import json
import os
from pathlib import Path
from typing import Any

from francis.kernel.paths import data_dir

_EXPECTED_VISUAL_CONTRACT = "native_cpp_orb.liquid_streamer_identity"


def lens_orb_body_runtime_readback() -> dict[str, Any]:
    native_path = data_dir() / "runtime" / "native-orb-renderer" / "status.json"
    overlay_path = data_dir() / "runtime" / "lens-overlay" / "status.json"
    native = _read_json(native_path)
    overlay = _read_json(overlay_path)
    overlay_native = _as_dict(overlay.get("native_renderer"))
    overlay_visual = _as_dict(overlay.get("orb_visual"))
    ring_color = _as_dict(overlay_visual.get("ring_color_contract"))
    renderer_pid = _safe_int(native.get("process_id"))
    overlay_pid = _safe_int(overlay.get("pid"))
    overlay_renderer_pid = _safe_int(overlay_native.get("pid"))
    renderer_alive = _process_is_alive(renderer_pid)
    overlay_alive = _process_is_alive(overlay_pid)
    blockers: list[str] = []
    if not native:
        blockers.append("lens_orb_body_native_renderer_state_missing")
    else:
        if (
            native.get("kind") != "francis.native_orb_renderer.runtime_status"
            or native.get("status") != "running"
            or native.get("active_renderer") is not True
            or native.get("renderer") != "native_cpp_orb_renderer"
        ):
            blockers.append("lens_orb_body_native_renderer_state_invalid")
        if not renderer_alive:
            blockers.append("lens_orb_body_native_renderer_process_missing")
        if (
            native.get("body_renderer_only") is not True
            or native.get("render_only") is not True
            or native.get("authority_granted") is not False
            or native.get("accepts_mutation_events") is not False
            or native.get("controls_user_os_cursor") is not False
            or native.get("can_click") is not False
            or native.get("can_drag") is not False
            or native.get("can_type") is not False
        ):
            blockers.append("lens_orb_body_native_renderer_authority_drift")
    if not overlay:
        blockers.append("lens_orb_body_overlay_state_missing")
    else:
        if overlay.get("kind") != "lens.overlay.runtime_state" or overlay.get("status") != "overlay_running":
            blockers.append("lens_orb_body_overlay_state_invalid")
        if not overlay_alive:
            blockers.append("lens_orb_body_overlay_process_missing")
        if (
            overlay_renderer_pid != renderer_pid
            or overlay_native.get("status_pid") != renderer_pid
            or overlay_native.get("pid_matches_status") is not True
            or overlay_native.get("process_alive") is not True
            or overlay_native.get("active_renderer") is not True
        ):
            blockers.append("lens_orb_body_overlay_renderer_mismatch")
        if (
            overlay_visual.get("visual_contract") != _EXPECTED_VISUAL_CONTRACT
            or ring_color.get("status") != "ready"
            or ring_color.get("visual_lock_status") != "locked"
        ):
            blockers.append("lens_orb_body_visual_contract_not_ready")
        if (
            overlay_native.get("render_only") is not True
            or overlay_native.get("authority_granted") is not False
            or overlay_native.get("controls_user_os_cursor") is not False
            or overlay_native.get("can_click") is not False
            or overlay_native.get("can_drag") is not False
            or overlay_native.get("can_type") is not False
        ):
            blockers.append("lens_orb_body_overlay_renderer_authority_drift")
    ready = not blockers
    return {
        "kind": "lens.orb.body_runtime_readback",
        "status": "ready" if ready else "missing" if not native and not overlay else "blocked",
        "ready": ready,
        "body": "francis_orb",
        "renderer": "native_cpp_orb_renderer",
        "visual_contract": _EXPECTED_VISUAL_CONTRACT,
        "renderer_pid": renderer_pid or None,
        "renderer_process_alive": renderer_alive,
        "overlay_pid": overlay_pid or None,
        "overlay_process_alive": overlay_alive,
        "pid_correlated": bool(renderer_pid and renderer_pid == overlay_renderer_pid),
        "position": {
            "x": _safe_signed_int(native.get("x")),
            "y": _safe_signed_int(native.get("y")),
            "center_x": _safe_signed_int(native.get("center_x")),
            "center_y": _safe_signed_int(native.get("center_y")),
            "size": _safe_int(native.get("size")),
            "coordinate_space": "windows_virtual_screen",
        },
        "ring_color_contract": {
            "status": str(ring_color.get("status") or "not_observed"),
            "visual_lock_status": str(ring_color.get("visual_lock_status") or ""),
            "ring_motion_contract": str(ring_color.get("ring_motion_contract") or ""),
        },
        "blockers": _dedupe(blockers),
        "governance": {
            "read_only_contract": True,
            "render_only": native.get("render_only") is True,
            "controls_user_os_cursor": False,
            "can_click": False,
            "can_drag": False,
            "can_type": False,
            "input_execution_authority": False,
            "memory_write": False,
        },
    }


def _process_is_alive(value: Any) -> bool:
    process_id = _safe_int(value)
    if process_id <= 0:
        return False
    if os.name == "nt":
        from ctypes import wintypes

        win_dll = getattr(ctypes, "WinDLL", None)
        if win_dll is None:
            return False
        kernel32 = win_dll("kernel32", use_last_error=True)
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        kernel32.GetExitCodeProcess.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL
        handle = kernel32.OpenProcess(0x1000, False, process_id)
        if not handle:
            return False
        try:
            exit_code = wintypes.DWORD()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return False
            return int(exit_code.value) == 259
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(process_id, 0)
    except OSError:
        return False
    return True


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig", errors="replace"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _safe_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _safe_signed_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


__all__ = ["lens_orb_body_runtime_readback"]
