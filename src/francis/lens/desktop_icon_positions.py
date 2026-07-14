"""Bounded desktop icon position capture for Lens desktop organization.

The public capture functions in this module are evidence capture/readback
helpers. They do not move icons, send input, run shell commands, or read file
contents. Production Win32 capture is explicitly environment-gated because
enumerating Explorer's desktop ListView requires cross-process readback
mechanics.
"""

from __future__ import annotations

import ctypes
import json
import os
import time
from typing import Any

from francis.kernel.paths import data_dir
from francis.lens.desktop_organization import (
    LENS_DESKTOP_ICON_POSITION_EVIDENCE_KIND,
    lens_desktop_icon_position_evidence,
    lens_desktop_icon_semantic_targets,
)

LENS_DESKTOP_ICON_POSITION_CAPTURE_KIND = "lens.orb.desktop_organization.position_capture"
LENS_DESKTOP_ICON_POSITION_CAPTURE_ENV = "FRANCIS_LENS_DESKTOP_ICON_POSITION_CAPTURE_ENABLE"
LENS_DESKTOP_ICON_POSITION_APPLY_KIND = "lens.orb.desktop_organization.position_apply"
LENS_DESKTOP_ICON_POSITION_APPLY_ENV = "FRANCIS_LENS_DESKTOP_ORGANIZATION_SHELL_ADAPTER_ENABLE"
LENS_DESKTOP_ICON_POSITION_EVIDENCE_RELATIVE_PATH = "runtime/lens-perception/desktop-icon-position-evidence.json"

_MAX_ITEMS = 80
_ICON_WIDTH = 96
_ICON_HEIGHT = 96
_SOURCE = "shell_desktop_listview_snapshot"


def capture_desktop_icon_position_evidence(
    *,
    limit: Any = _MAX_ITEMS,
    roots: Any = None,
    semantic_readback: dict[str, Any] | None = None,
    listview_items: Any = None,
    write_evidence: bool = True,
) -> dict[str, Any]:
    """Capture and persist bounded desktop icon position evidence."""

    safe_limit = _safe_int(limit, default=_MAX_ITEMS, lower=1, upper=_MAX_ITEMS)
    semantic = semantic_readback or lens_desktop_icon_semantic_targets(limit=safe_limit, roots=roots)
    semantic_targets = _target_items(semantic.get("semantic_targets"))
    blockers = _string_items(semantic.get("blockers"))
    injected_items = listview_items is not None
    capture_enabled = injected_items or os.getenv(LENS_DESKTOP_ICON_POSITION_CAPTURE_ENV, "").strip() == "1"

    if not capture_enabled:
        return _capture_response(
            status="blocked",
            blockers=[*blockers, "desktop_icon_position_capture_disabled"],
            semantic=semantic,
            evidence={},
            write_attempted=False,
            write_succeeded=False,
        )

    try:
        observed_items = (
            _normalized_listview_items(listview_items, limit=safe_limit)
            if injected_items
            else _win32_desktop_listview_items(limit=safe_limit)
        )
    except Exception as exc:
        return _capture_response(
            status="blocked",
            blockers=[*blockers, _safe_text(exc, limit=160) or "desktop_icon_position_capture_failed"],
            semantic=semantic,
            evidence={},
            write_attempted=False,
            write_succeeded=False,
        )

    evidence_targets: list[dict[str, Any]] = []
    used_observed_indexes: set[int] = set()
    for target in semantic_targets:
        match_index, match = _match_observed_item(target, observed_items, used_observed_indexes)
        if match_index is None or match is None:
            blockers.append("desktop_icon_position_capture_target_unmatched")
            continue
        used_observed_indexes.add(match_index)
        evidence_targets.append(
            {
                "target_id": _safe_text(target.get("target_id"), limit=120),
                "stable_identity_digest": _safe_text(target.get("stable_identity_digest"), limit=64),
                "desktop_position_index": _safe_int(match.get("index"), default=match_index, lower=0, upper=_MAX_ITEMS),
                "current_rect": _rect_from_observed(match),
            }
        )

    captured_at = time.time()
    evidence = {
        "kind": LENS_DESKTOP_ICON_POSITION_EVIDENCE_KIND,
        "evidence_id": f"desktop-icon-pos-{int(captured_at * 1000)}",
        "source": _SOURCE,
        "captured_at": captured_at,
        "source_item_count": len(observed_items),
        "matched_target_count": len(evidence_targets),
        "targets": evidence_targets,
        "raw_paths_stored": False,
        "raw_labels_stored": False,
        "file_contents_read": False,
        "input_execution_authority": False,
        "desktop_effect_performed": False,
    }
    if not evidence_targets:
        blockers.append("desktop_icon_position_capture_no_matches")

    write_attempted = bool(write_evidence and evidence_targets)
    write_succeeded = False
    if write_attempted:
        try:
            _write_position_evidence(evidence)
            write_succeeded = True
        except OSError:
            blockers.append("desktop_icon_position_evidence_write_failed")

    status = "ready" if evidence_targets and not blockers and (write_succeeded or not write_attempted) else "blocked"
    return _capture_response(
        status=status,
        blockers=blockers,
        semantic=semantic,
        evidence=evidence,
        write_attempted=write_attempted,
        write_succeeded=write_succeeded,
    )


def apply_desktop_icon_plan(plan: dict[str, Any]) -> dict[str, Any]:
    """Fail closed until desktop mutation is bound to visible Orb actions."""

    _ = plan
    return _apply_blocked("desktop_icon_position_apply_requires_orb_bound_actuator")


def apply_desktop_icon_position_item(
    *,
    target_id: Any,
    desktop_position_index: Any,
    to_rect: Any,
) -> dict[str, Any]:
    """Move one desktop icon through the bounded Explorer shell adapter."""

    safe_target_id = _safe_text(target_id, limit=120)
    safe_index = _safe_int(desktop_position_index, default=-1, lower=-1, upper=_MAX_ITEMS)
    destination = _rect_from_observed(to_rect if isinstance(to_rect, dict) else {})
    blockers: list[str] = []
    if os.getenv(LENS_DESKTOP_ICON_POSITION_APPLY_ENV, "").strip() != "1":
        blockers.append("desktop_icon_position_shell_adapter_env_gate_required")
    if not safe_target_id:
        blockers.append("desktop_icon_position_shell_adapter_target_required")
    if safe_index < 0:
        blockers.append("desktop_icon_position_shell_adapter_index_required")
    if destination["width"] <= 0 or destination["height"] <= 0:
        blockers.append("desktop_icon_position_shell_adapter_destination_required")
    if blockers:
        return _single_apply_response(
            status="denied",
            target_id=safe_target_id,
            desktop_position_index=safe_index,
            to_rect=destination,
            blockers=blockers,
            desktop_effect_performed=False,
        )

    try:
        _win32_set_desktop_listview_item_position(index=safe_index, to_rect=destination)
    except Exception as exc:
        return _single_apply_response(
            status="blocked",
            target_id=safe_target_id,
            desktop_position_index=safe_index,
            to_rect=destination,
            blockers=[_safe_text(exc, limit=160) or "desktop_icon_position_shell_adapter_failed"],
            desktop_effect_performed=False,
        )

    return _single_apply_response(
        status="applied",
        target_id=safe_target_id,
        desktop_position_index=safe_index,
        to_rect=destination,
        blockers=[],
        desktop_effect_performed=True,
    )


def _apply_blocked(reason: str) -> dict[str, Any]:
    return {
        "kind": LENS_DESKTOP_ICON_POSITION_APPLY_KIND,
        "status": "blocked",
        "ok": False,
        "moved_target_count": 0,
        "confirmed_target_count": 0,
        "moved_targets": [],
        "confirmed_targets": [],
        "blockers": [reason],
        "uses_user_os_cursor": False,
        "physical_input_performed": False,
        "desktop_effect_performed": False,
        "desktop_effect_confirmed": False,
    }


def _single_apply_response(
    *,
    status: str,
    target_id: str,
    desktop_position_index: int,
    to_rect: dict[str, int],
    blockers: list[str],
    desktop_effect_performed: bool,
) -> dict[str, Any]:
    return {
        "kind": LENS_DESKTOP_ICON_POSITION_APPLY_KIND,
        "status": status,
        "ok": status == "applied",
        "target_id": target_id,
        "desktop_position_index": desktop_position_index,
        "to_rect": to_rect,
        "moved_target_count": 1 if status == "applied" else 0,
        "confirmed_target_count": 0,
        "moved_targets": [{"target_id": target_id, "to_rect": to_rect}] if status == "applied" else [],
        "confirmed_targets": [],
        "blockers": _dedupe(blockers),
        "uses_user_os_cursor": False,
        "physical_input_performed": False,
        "desktop_effect_performed": desktop_effect_performed,
        "desktop_effect_confirmed": False,
        "governance": {
            "env_gate": LENS_DESKTOP_ICON_POSITION_APPLY_ENV,
            "desktop_shell_adapter": True,
            "single_item_only": True,
            "visible_orb_cursor_required": True,
            "batch_desktop_mutation": False,
            "uses_user_os_cursor": False,
            "physical_input_performed": False,
            "shell": False,
            "subprocess": False,
            "network_client": False,
            "daemon": False,
        },
    }


def _capture_response(
    *,
    status: str,
    blockers: list[str],
    semantic: dict[str, Any],
    evidence: dict[str, Any],
    write_attempted: bool,
    write_succeeded: bool,
) -> dict[str, Any]:
    position_readback = lens_desktop_icon_position_evidence(
        semantic_readback=semantic,
        position_evidence=evidence,
    )
    return {
        "kind": LENS_DESKTOP_ICON_POSITION_CAPTURE_KIND,
        "status": status,
        "ok": status == "ready",
        "capture_enabled": "desktop_icon_position_capture_disabled" not in blockers,
        "blockers": _dedupe([*blockers, *_string_items(position_readback.get("blockers"))]),
        "evidence_id": _safe_text(evidence.get("evidence_id"), limit=160),
        "matched_target_count": int(evidence.get("matched_target_count") or 0),
        "write_attempted": write_attempted,
        "write_succeeded": write_succeeded,
        "evidence_path": LENS_DESKTOP_ICON_POSITION_EVIDENCE_RELATIVE_PATH if write_succeeded else "",
        "position_readback": position_readback,
        "governance": {
            "api_permission_gate": True,
            "env_gate": LENS_DESKTOP_ICON_POSITION_CAPTURE_ENV,
            "desktop_listview_metadata_only": True,
            "raw_paths_stored": False,
            "raw_labels_stored": False,
            "file_contents_read": False,
            "input_execution_authority": False,
            "uses_user_os_cursor": False,
            "physical_input_performed": False,
            "desktop_effect_performed": False,
            "filesystem_write_scope": "data/runtime/lens-perception/desktop-icon-position-evidence.json",
            "shell": False,
            "subprocess": False,
            "network_client": False,
            "daemon": False,
        },
    }


def _write_position_evidence(evidence: dict[str, Any]) -> None:
    path = data_dir() / LENS_DESKTOP_ICON_POSITION_EVIDENCE_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{os.getpid():x}.{time.time_ns():x}.tmp")
    try:
        temporary.write_text(
            json.dumps(evidence, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _normalized_listview_items(value: Any, *, limit: int) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    items: list[dict[str, Any]] = []
    for raw in value[:limit]:
        item = raw if isinstance(raw, dict) else {}
        label = _safe_text(item.get("label") or item.get("text") or item.get("name"), limit=120)
        rect = _rect_from_observed(item)
        if label and rect["width"] > 0 and rect["height"] > 0:
            items.append({"label": label, "current_rect": rect})
    return items


def _match_observed_item(
    target: dict[str, Any],
    observed_items: list[dict[str, Any]],
    used_indexes: set[int],
) -> tuple[int | None, dict[str, Any] | None]:
    candidates = _label_candidates(target)
    matches: list[tuple[int, dict[str, Any]]] = []
    for index, item in enumerate(observed_items):
        if index in used_indexes:
            continue
        label = _normalize_label(item.get("label"))
        if label in candidates:
            matches.append((index, item))
    if len(matches) != 1:
        return None, None
    return matches[0]


def _label_candidates(target: dict[str, Any]) -> set[str]:
    label = _safe_text(target.get("label_summary"), limit=120)
    extension = _safe_text(target.get("extension_summary"), limit=32)
    candidates = {_normalize_label(label)}
    if extension and label:
        candidates.add(_normalize_label(f"{label}{extension}"))
    return {candidate for candidate in candidates if candidate}


def _normalize_label(value: Any) -> str:
    return _safe_text(value, limit=160).casefold()


def _rect_from_observed(item: dict[str, Any]) -> dict[str, int]:
    raw_rect = item.get("current_rect") if isinstance(item.get("current_rect"), dict) else item
    rect = raw_rect if isinstance(raw_rect, dict) else {}
    left = _safe_int(
        rect.get("left"),
        default=_safe_int(rect.get("x"), default=0, lower=-100_000, upper=100_000),
        lower=-100_000,
        upper=100_000,
    )
    top = _safe_int(
        rect.get("top"),
        default=_safe_int(rect.get("y"), default=0, lower=-100_000, upper=100_000),
        lower=-100_000,
        upper=100_000,
    )
    width = _safe_int(rect.get("width"), default=_ICON_WIDTH, lower=0, upper=100_000)
    height = _safe_int(rect.get("height"), default=_ICON_HEIGHT, lower=0, upper=100_000)
    return {"left": left, "top": top, "width": width, "height": height}


def _win32_desktop_listview_items(*, limit: int) -> list[dict[str, Any]]:
    if os.name != "nt":
        raise RuntimeError("desktop_icon_position_capture_requires_windows")
    try:
        import win32gui  # type: ignore[import-not-found]
        import win32process  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError("desktop_icon_position_capture_requires_pywin32") from exc

    hwnd = _desktop_listview_hwnd(win32gui)
    if not hwnd:
        raise RuntimeError("desktop_listview_not_found")
    count = min(int(win32gui.SendMessage(hwnd, 0x1004, 0, 0)), limit)
    _thread_id, process_id = win32process.GetWindowThreadProcessId(hwnd)
    return _read_listview_items(hwnd=hwnd, process_id=int(process_id), count=count, win32gui=win32gui)


def _win32_set_desktop_listview_item_position(*, index: int, to_rect: dict[str, int]) -> None:
    if os.name != "nt":
        raise RuntimeError("desktop_icon_position_shell_adapter_requires_windows")
    try:
        import win32gui  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError("desktop_icon_position_shell_adapter_requires_pywin32") from exc

    hwnd = _desktop_listview_hwnd(win32gui)
    if not hwnd:
        raise RuntimeError("desktop_listview_not_found")
    client_x, client_y = win32gui.ScreenToClient(hwnd, (int(to_rect["left"]), int(to_rect["top"])))
    win32gui.SendMessage(hwnd, 0x100F, int(index), _make_lparam(client_x, client_y))
    time.sleep(0.2)


def _desktop_listview_hwnd(win32gui: Any) -> int:
    def listview_from_shell(parent: int) -> int:
        shell = int(win32gui.FindWindowEx(parent, 0, "SHELLDLL_DefView", None))
        return int(win32gui.FindWindowEx(shell, 0, "SysListView32", None)) if shell else 0

    progman = int(win32gui.FindWindow("Progman", None))
    listview = listview_from_shell(progman) if progman else 0
    if listview:
        return listview

    found = 0

    def collect(hwnd: int, _extra: object) -> None:
        nonlocal found
        if found:
            return
        class_name = _safe_text(win32gui.GetClassName(hwnd), limit=120)
        if class_name == "WorkerW":
            found = listview_from_shell(hwnd)

    win32gui.EnumWindows(collect, None)
    return found


def _read_listview_items(*, hwnd: int, process_id: int, count: int, win32gui: Any) -> list[dict[str, Any]]:
    kernel32 = _kernel32()
    process = kernel32.OpenProcess(0x0438, False, process_id)
    if not process:
        raise RuntimeError("desktop_listview_process_open_failed")
    try:
        return [_read_listview_item(hwnd, process, index, win32gui) for index in range(count)]
    finally:
        kernel32.CloseHandle(process)


def _read_listview_item(hwnd: int, process: int, index: int, win32gui: Any) -> dict[str, Any]:
    kernel32 = _kernel32()
    remote_point = kernel32.VirtualAllocEx(process, None, ctypes.sizeof(_Point), 0x3000, 0x04)
    text_chars = 260
    text_bytes = text_chars * 2
    remote_text = kernel32.VirtualAllocEx(process, None, text_bytes, 0x3000, 0x04)
    remote_item = kernel32.VirtualAllocEx(process, None, ctypes.sizeof(_LvItemW), 0x3000, 0x04)
    try:
        if not remote_point or not remote_text or not remote_item:
            raise RuntimeError("desktop_listview_remote_alloc_failed")
        win32gui.SendMessage(hwnd, 0x1010, index, remote_point)
        point = _Point()
        _read_process_memory(kernel32, process, remote_point, ctypes.byref(point), ctypes.sizeof(point))

        item = _LvItemW()
        item.mask = 0x0001
        item.iSubItem = 0
        item.pszText = remote_text
        item.cchTextMax = text_chars
        _write_process_memory(kernel32, process, remote_item, ctypes.byref(item), ctypes.sizeof(item))
        win32gui.SendMessage(hwnd, 0x1073, index, remote_item)
        text_buffer = ctypes.create_string_buffer(text_bytes)
        _read_process_memory(kernel32, process, remote_text, text_buffer, text_bytes)
        label = text_buffer.raw.decode("utf-16-le", errors="ignore").split("\x00", 1)[0]
        screen_x, screen_y = win32gui.ClientToScreen(hwnd, (int(point.x), int(point.y)))
        return {
            "index": index,
            "label": label,
            "current_rect": _bounded_rect(left=screen_x, top=screen_y),
        }
    finally:
        for remote in (remote_point, remote_text, remote_item):
            if remote:
                kernel32.VirtualFreeEx(process, remote, 0, 0x8000)


class _Point(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class _LvItemW(ctypes.Structure):
    _fields_ = [
        ("mask", ctypes.c_uint),
        ("iItem", ctypes.c_int),
        ("iSubItem", ctypes.c_int),
        ("state", ctypes.c_uint),
        ("stateMask", ctypes.c_uint),
        ("pszText", ctypes.c_void_p),
        ("cchTextMax", ctypes.c_int),
        ("iImage", ctypes.c_int),
        ("lParam", ctypes.c_ssize_t),
        ("iIndent", ctypes.c_int),
        ("iGroupId", ctypes.c_int),
        ("cColumns", ctypes.c_uint),
        ("puColumns", ctypes.c_void_p),
        ("piColFmt", ctypes.c_void_p),
        ("iGroup", ctypes.c_int),
    ]


def _kernel32() -> Any:
    kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
    kernel32.OpenProcess.argtypes = [ctypes.c_uint, ctypes.c_bool, ctypes.c_uint]
    kernel32.OpenProcess.restype = ctypes.c_void_p
    kernel32.VirtualAllocEx.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint, ctypes.c_uint]
    kernel32.VirtualAllocEx.restype = ctypes.c_void_p
    kernel32.VirtualFreeEx.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint]
    kernel32.VirtualFreeEx.restype = ctypes.c_bool
    kernel32.ReadProcessMemory.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_size_t,
        ctypes.POINTER(ctypes.c_size_t),
    ]
    kernel32.ReadProcessMemory.restype = ctypes.c_bool
    kernel32.WriteProcessMemory.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_size_t,
        ctypes.POINTER(ctypes.c_size_t),
    ]
    kernel32.WriteProcessMemory.restype = ctypes.c_bool
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel32.CloseHandle.restype = ctypes.c_bool
    return kernel32


def _read_process_memory(kernel32: Any, process: int, remote: int, buffer: Any, size: int) -> None:
    read = ctypes.c_size_t(0)
    if not kernel32.ReadProcessMemory(process, remote, buffer, size, ctypes.byref(read)):
        raise RuntimeError("desktop_listview_read_failed")


def _write_process_memory(kernel32: Any, process: int, remote: int, buffer: Any, size: int) -> None:
    written = ctypes.c_size_t(0)
    if not kernel32.WriteProcessMemory(process, remote, buffer, size, ctypes.byref(written)):
        raise RuntimeError("desktop_listview_write_failed")


def _confirmed_targets(
    moved: list[dict[str, Any]],
    after: list[dict[str, Any]],
    steps: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    confirmed: list[dict[str, Any]] = []
    by_target_id = {
        _safe_text(_target_for_step(step).get("target_id"), limit=120): step
        for step in steps
        if _safe_text(_target_for_step(step).get("target_id"), limit=120)
    }
    used: set[int] = set()
    for moved_target in moved:
        target_id = _safe_text(moved_target.get("target_id"), limit=120)
        step = by_target_id.get(target_id, {})
        match_index, match = _match_observed_item(_target_for_step(step), after, used)
        if match_index is None or match is None:
            continue
        used.add(match_index)
        raw_expected = moved_target.get("to_rect")
        expected: dict[str, Any] = raw_expected if isinstance(raw_expected, dict) else {}
        actual = _rect_from_observed(match)
        expected_left = _safe_int(expected.get("left"), default=-999999, lower=-1_000_000, upper=1_000_000)
        expected_top = _safe_int(expected.get("top"), default=-999999, lower=-1_000_000, upper=1_000_000)
        if abs(actual["left"] - expected_left) <= 2 and abs(actual["top"] - expected_top) <= 2:
            confirmed.append({"target_id": target_id, "current_rect": actual})
    return confirmed


def _plan_steps(plan: dict[str, Any]) -> list[dict[str, Any]]:
    steps = plan.get("steps")
    if not isinstance(steps, list):
        return []
    return [step for step in steps if isinstance(step, dict)]


def _target_for_step(step: dict[str, Any]) -> dict[str, Any]:
    target = step.get("semantic_target")
    return target if isinstance(target, dict) else {}


def _make_lparam(x: int, y: int) -> int:
    return (int(y) & 0xFFFF) << 16 | (int(x) & 0xFFFF)


def _bounded_rect(*, left: Any, top: Any) -> dict[str, int]:
    return {
        "left": _safe_int(left, default=0, lower=-100_000, upper=100_000),
        "top": _safe_int(top, default=0, lower=-100_000, upper=100_000),
        "width": _ICON_WIDTH,
        "height": _ICON_HEIGHT,
    }


def _target_items(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _safe_text(value: Any, *, limit: int) -> str:
    if value is None:
        return ""
    try:
        text = str(value).strip()
    except Exception:
        return ""
    return text[:limit]


def _safe_int(value: Any, *, default: int, lower: int, upper: int) -> int:
    if isinstance(value, bool):
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(lower, min(parsed, upper))


def _string_items(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_safe_text(item, limit=160) for item in value if _safe_text(item, limit=160)]


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


__all__ = [
    "LENS_DESKTOP_ICON_POSITION_CAPTURE_ENV",
    "LENS_DESKTOP_ICON_POSITION_APPLY_ENV",
    "LENS_DESKTOP_ICON_POSITION_APPLY_KIND",
    "LENS_DESKTOP_ICON_POSITION_CAPTURE_KIND",
    "LENS_DESKTOP_ICON_POSITION_EVIDENCE_RELATIVE_PATH",
    "apply_desktop_icon_position_item",
    "apply_desktop_icon_plan",
    "capture_desktop_icon_position_evidence",
]
