from __future__ import annotations

import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from francis.kernel.paths import data_dir, repo_root


SUPERVISOR_READBACK_FRESH_SECONDS = 15 * 60
LENS_HOST_ACTIVATION_EXECUTE_ROUTE = "/lens/host/activation/execute"
LENS_HOST_ACTIVATION_EXECUTIONS_ROUTE = "/lens/host/activation/executions"


def _runtime_file_exists(relative_path: str) -> bool:
    try:
        return (repo_root() / Path(relative_path)).is_file()
    except OSError:
        return False


def _json_dict_from_path(
    path: Path,
    *,
    transient_retries: int = 0,
    transient_delay_seconds: float = 0.05,
) -> dict[str, Any]:
    attempts = max(1, transient_retries + 1)
    for attempt in range(attempts):
        try:
            if not path.is_file():
                if attempt < attempts - 1:
                    time.sleep(transient_delay_seconds)
                    continue
                return {}
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            if attempt < attempts - 1:
                time.sleep(transient_delay_seconds)
                continue
            return {}
        return payload if isinstance(payload, dict) else {}
    return {}


def _runtime_json_dict(relative_path: str) -> dict[str, Any]:
    return _json_dict_from_path(repo_root() / Path(relative_path))


def _lens_host_service_config_path() -> Path:
    override = (os.getenv("FRANCIS_LENS_HOST_SERVICE_CONFIG_PATH") or "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return repo_root() / "config" / "runtime" / "services" / "lens-host.json"


def _lens_host_service_config_source(path: Path) -> str:
    override = (os.getenv("FRANCIS_LENS_HOST_SERVICE_CONFIG_PATH") or "").strip()
    if override:
        return str(path)
    return "config/runtime/services/lens-host.json"


def _path_exists(path: Path) -> bool:
    try:
        return path.is_file()
    except OSError:
        return False


def _safe_pid(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    try:
        pid = int(value)
    except (TypeError, ValueError):
        return 0
    return pid if pid > 0 else 0


def _orb_ring_color_contract() -> dict[str, Any]:
    return {
        "kind": "lens.overlay.orb_ring_color_contract",
        "status": "ready",
        "source": "docs/operations/ORB_VISUAL_LOCK.md",
        "render_source": "native/orb/native_orb_renderer.cpp",
        "visual_contract": "native_cpp_orb.liquid_streamer_identity",
        "renderer": "native_cpp_orb_renderer",
        "visual_lock_status": "locked",
        "state_driven_render_object": True,
        "ring_motion_contract": "native_liquid_blob_flow",
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "ring_family": {
            "material": "pearlescent_liquid_streamer_rings",
            "main_streamer_ring_count": 15,
            "fine_streamer_ring_count": 5,
            "single_identity_ring_count": 20,
            "follows_blob_flow": True,
            "independent_ring_pulses": True,
        },
        "glow_family": {
            "outer_glow_primary": "#DAEEFF",
            "outer_glow_secondary": "#FFFFFF",
            "core_primary": "#FFFFFF",
            "core_secondary": "#E6F0FC",
            "core_shadow": "#1C2E48",
            "hot_center": "#FFFFFF",
        },
    }


def _orb_visual_runtime_readback(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    orb_visual = dict(value)
    if any(
        isinstance(orb_visual.get(field), dict) and orb_visual[field]
        for field in ("ring_color_contract", "ring_contract", "color_contract", "energy_palette")
    ):
        return orb_visual
    visual_contract = str(orb_visual.get("visual_contract") or "").strip()
    renderer = str(orb_visual.get("renderer") or "").strip()
    if visual_contract == "native_cpp_orb.liquid_streamer_identity" and renderer == "native_cpp_orb_renderer":
        orb_visual["ring_color_contract"] = _orb_ring_color_contract()
    return orb_visual


def _pid_from_file(path: Path) -> int:
    try:
        return _safe_pid(path.read_text(encoding="utf-8-sig").strip())
    except OSError:
        return 0


def _windows_process_alive(pid: int) -> tuple[bool, str]:
    import ctypes
    from ctypes import wintypes

    windll_factory = getattr(ctypes, "WinDLL", None)
    if windll_factory is None:
        return False, "windows_api_unavailable"

    kernel32 = windll_factory("kernel32", use_last_error=True)
    process_query_limited_information = 0x1000
    still_active = 259

    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel32.GetExitCodeProcess.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
    if not handle:
        return False, "windows_open_process_failed"

    try:
        exit_code = wintypes.DWORD(0)
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            return False, "windows_exit_code_failed"
        return exit_code.value == still_active, "windows_exit_code"
    finally:
        kernel32.CloseHandle(handle)


def _windows_service_status_readback(service_name: str) -> dict[str, Any]:
    import ctypes
    from ctypes import wintypes

    windll_factory = getattr(ctypes, "WinDLL", None)
    if windll_factory is None:
        return {
            "status": "unavailable",
            "installed": False,
            "service_status": "",
            "display_name": "",
            "start_type": "",
            "query_error": "windows_api_unavailable",
        }

    class SERVICE_STATUS_PROCESS(ctypes.Structure):
        _fields_ = [
            ("dwServiceType", wintypes.DWORD),
            ("dwCurrentState", wintypes.DWORD),
            ("dwControlsAccepted", wintypes.DWORD),
            ("dwWin32ExitCode", wintypes.DWORD),
            ("dwServiceSpecificExitCode", wintypes.DWORD),
            ("dwCheckPoint", wintypes.DWORD),
            ("dwWaitHint", wintypes.DWORD),
            ("dwProcessId", wintypes.DWORD),
            ("dwServiceFlags", wintypes.DWORD),
        ]

    service_state_names = {
        1: "stopped",
        2: "start_pending",
        3: "stop_pending",
        4: "running",
        5: "continue_pending",
        6: "pause_pending",
        7: "paused",
    }
    error_service_does_not_exist = 1060
    sc_manager_connect = 0x0001
    service_query_status = 0x0004
    sc_status_process_info = 0

    advapi32 = windll_factory("advapi32", use_last_error=True)
    get_last_error = getattr(ctypes, "get_last_error", None)

    def last_windows_error() -> int:
        if callable(get_last_error):
            return int(get_last_error())
        return 0

    advapi32.OpenSCManagerW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD]
    advapi32.OpenSCManagerW.restype = wintypes.HANDLE
    advapi32.OpenServiceW.argtypes = [wintypes.HANDLE, wintypes.LPCWSTR, wintypes.DWORD]
    advapi32.OpenServiceW.restype = wintypes.HANDLE
    advapi32.QueryServiceStatusEx.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPBYTE,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]
    advapi32.QueryServiceStatusEx.restype = wintypes.BOOL
    advapi32.CloseServiceHandle.argtypes = [wintypes.HANDLE]
    advapi32.CloseServiceHandle.restype = wintypes.BOOL

    service_control_manager = advapi32.OpenSCManagerW(None, None, sc_manager_connect)
    if not service_control_manager:
        return {
            "status": "unavailable",
            "installed": False,
            "service_status": "",
            "display_name": "",
            "start_type": "",
            "query_error": f"windows_open_service_manager_failed:{last_windows_error()}",
        }

    service_handle = None
    try:
        service_handle = advapi32.OpenServiceW(service_control_manager, service_name, service_query_status)
        if not service_handle:
            error = last_windows_error()
            if error == error_service_does_not_exist:
                return {
                    "status": "not_installed",
                    "installed": False,
                    "service_status": "",
                    "display_name": "",
                    "start_type": "",
                    "query_error": "",
                }
            return {
                "status": "unavailable",
                "installed": False,
                "service_status": "",
                "display_name": "",
                "start_type": "",
                "query_error": f"windows_open_service_failed:{error}",
            }

        service_status = SERVICE_STATUS_PROCESS()
        bytes_needed = wintypes.DWORD(0)
        queried = advapi32.QueryServiceStatusEx(
            service_handle,
            sc_status_process_info,
            ctypes.cast(ctypes.byref(service_status), wintypes.LPBYTE),
            ctypes.sizeof(service_status),
            ctypes.byref(bytes_needed),
        )
        if not queried:
            return {
                "status": "unavailable",
                "installed": True,
                "service_status": "",
                "display_name": service_name,
                "start_type": "",
                "query_error": f"windows_query_service_status_failed:{last_windows_error()}",
            }

        status = service_state_names.get(int(service_status.dwCurrentState), "unknown")
        return {
            "status": status,
            "installed": True,
            "service_status": status.upper(),
            "display_name": service_name,
            "start_type": "",
            "query_error": "",
        }
    finally:
        if service_handle:
            advapi32.CloseServiceHandle(service_handle)
        advapi32.CloseServiceHandle(service_control_manager)


def _process_alive_readback(pid: int) -> tuple[bool, str]:
    if pid <= 0:
        return False, "not_attempted_by_api"
    if os.name == "nt":
        return _windows_process_alive(pid)
    if os.name == "posix":
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False, "posix_signal_zero"
        except PermissionError:
            return True, "posix_signal_zero"
        except OSError:
            return False, "posix_signal_zero"
        return True, "posix_signal_zero"
    return False, "unsupported_platform"


def _lens_host_process_readback() -> dict[str, Any]:
    state_file = data_dir() / "runtime" / "lens-host" / "status.json"
    pid_file = data_dir() / "runtime" / "lens-host" / "lens-host.pid"
    pid_present = _path_exists(pid_file)
    pid = _pid_from_file(pid_file) if pid_present else 0
    state_payload = _json_dict_from_path(
        state_file,
        transient_retries=4 if pid_present or state_file.parent.exists() else 0,
    )
    state_exists = bool(state_payload) or _path_exists(state_file)
    state_kind = str(state_payload.get("kind") or "")
    state_status = str(state_payload.get("status") or "")
    state_pid = _safe_pid(state_payload.get("pid"))
    state_claims_running_host = (
        state_kind == "lens.host.runtime_state"
        and state_status in {"foreground_running", "resident_running"}
        and state_pid > 0
        and state_pid == pid
    )
    if state_claims_running_host:
        process_alive, process_alive_check = _process_alive_readback(pid)
    elif not pid_present:
        process_alive, process_alive_check = False, "not_attempted_no_pid_file"
    elif not state_exists:
        process_alive, process_alive_check = False, "not_attempted_runtime_state_missing"
    elif state_kind != "lens.host.runtime_state":
        process_alive, process_alive_check = False, "not_attempted_runtime_state_kind_mismatch"
    elif state_status not in {"foreground_running", "resident_running"}:
        process_alive, process_alive_check = False, "not_attempted_runtime_state_not_running"
    else:
        process_alive, process_alive_check = False, "not_attempted_runtime_state_pid_mismatch"
    status = (
        "process_observed"
        if process_alive
        else "state_present_process_not_running"
        if state_exists or pid_present
        else "missing"
    )
    blocked_reason = "resident_host_not_supervised" if process_alive else "resident_host_process_missing"
    return {
        "status": status,
        "readback_ready": True,
        "runtime_state_path": "data/runtime/lens-host/status.json",
        "state_exists": state_exists,
        "state_kind": state_kind,
        "state_status": state_status,
        "state_pid": state_pid,
        "state_pid_matches_pid_file": state_pid > 0 and pid > 0 and state_pid == pid,
        "state_updated_at": str(state_payload.get("updated_at") or ""),
        "pid_path": "data/runtime/lens-host/lens-host.pid",
        "pid_present": pid_present,
        "pid": pid,
        "process_alive": process_alive,
        "process_alive_check": process_alive_check,
        "supervision_enabled": False,
        "start_supported": False,
        "stop_supported": False,
        "restart_supported": False,
        "supervision_authority": False,
        "blocked_reason": blocked_reason,
    }


def _lens_tray_runtime_readback() -> dict[str, Any]:
    state_file = data_dir() / "runtime" / "lens-tray" / "status.json"
    pid_file = data_dir() / "runtime" / "lens-tray" / "lens-tray.pid"
    state_exists = _path_exists(state_file)
    pid_present = _path_exists(pid_file)
    pid = _pid_from_file(pid_file) if pid_present else 0
    state_payload = _json_dict_from_path(state_file, transient_retries=4) if state_exists else {}
    state_kind = str(state_payload.get("kind") or "")
    state_status = str(state_payload.get("status") or "")
    state_pid = _safe_pid(state_payload.get("pid"))
    state_claims_running_tray = (
        state_kind == "lens.tray.runtime_state"
        and state_status == "tray_running"
        and state_pid > 0
        and state_pid == pid
    )
    if state_claims_running_tray:
        process_alive, process_alive_check = _process_alive_readback(pid)
    elif not pid_present:
        process_alive, process_alive_check = False, "not_attempted_no_pid_file"
    elif not state_exists:
        process_alive, process_alive_check = False, "not_attempted_runtime_state_missing"
    elif state_kind != "lens.tray.runtime_state":
        process_alive, process_alive_check = False, "not_attempted_runtime_state_kind_mismatch"
    elif state_status != "tray_running":
        process_alive, process_alive_check = False, "not_attempted_runtime_state_not_running"
    else:
        process_alive, process_alive_check = False, "not_attempted_runtime_state_pid_mismatch"

    tray_icon_visible = process_alive and bool(state_payload.get("tray_icon_visible"))
    requirement_state = (
        "ready"
        if tray_icon_visible
        else "process_running_no_icon_claim"
        if process_alive
        else "stale_or_unverified"
        if state_exists or pid_present
        else "missing"
    )
    blocker = (
        "" if tray_icon_visible else "tray_icon_not_observed" if process_alive else "tray_presence_runtime_missing"
    )
    return {
        "ready": tray_icon_visible,
        "status": "running" if tray_icon_visible else "missing",
        "runtime_state_path": "data/runtime/lens-tray/status.json",
        "state_exists": state_exists,
        "state_kind": state_kind,
        "state_status": state_status,
        "state_pid": state_pid,
        "state_pid_matches_pid_file": state_pid > 0 and pid > 0 and state_pid == pid,
        "state_updated_at": str(state_payload.get("updated_at") or ""),
        "pid_path": "data/runtime/lens-tray/lens-tray.pid",
        "pid_present": pid_present,
        "pid": pid,
        "process_alive": process_alive,
        "process_alive_check": process_alive_check,
        "tray_icon_visible": tray_icon_visible,
        "requirement_state": requirement_state,
        "blocker": blocker,
    }


def _lens_hotkey_runtime_readback() -> dict[str, Any]:
    summon_override_file = data_dir() / "runtime" / "lens-summon" / "summon-action-override.json"
    hotkey_override_file = data_dir() / "runtime" / "lens-hotkey" / "os-binding-summon-override.json"
    override_file = summon_override_file if _path_exists(summon_override_file) else hotkey_override_file
    override_config = _json_dict_from_path(override_file) if _path_exists(override_file) else {}
    config = override_config or _runtime_json_dict("config/runtime/lens/summon.json")
    config_source = "runtime_override" if override_config else "canonical_config"
    expected_global_hotkey = str(config.get("global_hotkey") or "")
    expected_binding_scope = str(config.get("binding_scope") or "global")
    state_file = data_dir() / "runtime" / "lens-hotkey" / "status.json"
    pid_file = data_dir() / "runtime" / "lens-hotkey" / "lens-hotkey.pid"
    state_exists = _path_exists(state_file)
    pid_present = _path_exists(pid_file)
    pid = _pid_from_file(pid_file) if pid_present else 0
    state_payload = _json_dict_from_path(state_file) if state_exists else {}
    state_kind = str(state_payload.get("kind") or "")
    state_status = str(state_payload.get("status") or "")
    state_pid = _safe_pid(state_payload.get("pid"))
    state_global_hotkey = str(state_payload.get("global_hotkey") or "")
    state_binding_scope = str(state_payload.get("binding_scope") or "")
    state_claims_bound_hotkey = (
        state_kind == "lens.hotkey.runtime_state"
        and state_status == "hotkey_bound"
        and state_pid > 0
        and state_pid == pid
        and bool(state_payload.get("hotkey_bound"))
        and state_global_hotkey == expected_global_hotkey
        and state_binding_scope == expected_binding_scope
    )
    if state_claims_bound_hotkey:
        process_alive, process_alive_check = _process_alive_readback(pid)
    elif not pid_present:
        process_alive, process_alive_check = False, "not_attempted_no_pid_file"
    elif not state_exists:
        process_alive, process_alive_check = False, "not_attempted_runtime_state_missing"
    elif state_kind != "lens.hotkey.runtime_state":
        process_alive, process_alive_check = False, "not_attempted_runtime_state_kind_mismatch"
    elif state_status != "hotkey_bound":
        process_alive, process_alive_check = False, "not_attempted_runtime_state_not_bound"
    else:
        process_alive, process_alive_check = False, "not_attempted_runtime_state_pid_or_binding_mismatch"

    hotkey_bound = process_alive and state_claims_bound_hotkey
    requirement_state = (
        "bound"
        if hotkey_bound
        else "process_running_no_bound_hotkey_claim"
        if process_alive
        else "stale_or_unverified"
        if state_exists or pid_present
        else "missing"
    )
    return {
        "ready": hotkey_bound,
        "status": "running" if hotkey_bound else "missing",
        "runtime_state_path": "data/runtime/lens-hotkey/status.json",
        "config_source": config_source,
        "config_override_path": (
            "data/runtime/lens-summon/summon-action-override.json"
            if override_config and override_file.name == "summon-action-override.json"
            else "data/runtime/lens-hotkey/os-binding-summon-override.json"
            if override_config
            else ""
        ),
        "state_exists": state_exists,
        "state_kind": state_kind,
        "state_status": state_status,
        "state_pid": state_pid,
        "state_pid_matches_pid_file": state_pid > 0 and pid > 0 and state_pid == pid,
        "state_updated_at": str(state_payload.get("updated_at") or ""),
        "pid_path": "data/runtime/lens-hotkey/lens-hotkey.pid",
        "pid_present": pid_present,
        "pid": pid,
        "process_alive": process_alive,
        "process_alive_check": process_alive_check,
        "hotkey_bound": hotkey_bound,
        "global_hotkey": state_global_hotkey,
        "expected_global_hotkey": expected_global_hotkey,
        "binding_scope": state_binding_scope,
        "expected_binding_scope": expected_binding_scope,
        "launch_on_hotkey": bool(state_payload.get("launch_on_hotkey")),
        "summon_runner": str(state_payload.get("summon_runner") or ""),
        "press_count": _safe_pid(state_payload.get("press_count")),
        "requirement_state": requirement_state,
        "blocker": "" if hotkey_bound else "global_hotkey_binding_runtime_missing",
    }


def _lens_overlay_runtime_readback() -> dict[str, Any]:
    config = _runtime_json_dict("config/runtime/lens/overlay.json")
    expected_overlay_name = str(config.get("overlay_name") or "Francis Lens Overlay")
    expected_overlay_scope = str(config.get("overlay_scope") or "user_session")
    state_file = data_dir() / "runtime" / "lens-overlay" / "status.json"
    pid_file = data_dir() / "runtime" / "lens-overlay" / "lens-overlay.pid"
    state_exists = _path_exists(state_file)
    pid_present = _path_exists(pid_file)
    pid = _pid_from_file(pid_file) if pid_present else 0
    state_payload = _json_dict_from_path(state_file) if state_exists else {}
    state_kind = str(state_payload.get("kind") or "")
    state_status = str(state_payload.get("status") or "")
    state_pid = _safe_pid(state_payload.get("pid"))
    state_overlay_name = str(state_payload.get("overlay_name") or "")
    state_overlay_scope = str(state_payload.get("overlay_scope") or "")
    state_claims_running_overlay = (
        state_kind == "lens.overlay.runtime_state"
        and state_status == "overlay_running"
        and state_pid > 0
        and state_pid == pid
        and state_overlay_name == expected_overlay_name
        and state_overlay_scope == expected_overlay_scope
    )
    if state_claims_running_overlay:
        process_alive, process_alive_check = _process_alive_readback(pid)
    elif not pid_present:
        process_alive, process_alive_check = False, "not_attempted_no_pid_file"
    elif not state_exists:
        process_alive, process_alive_check = False, "not_attempted_runtime_state_missing"
    elif state_kind != "lens.overlay.runtime_state":
        process_alive, process_alive_check = False, "not_attempted_runtime_state_kind_mismatch"
    elif state_status != "overlay_running":
        process_alive, process_alive_check = False, "not_attempted_runtime_state_not_running"
    else:
        process_alive, process_alive_check = False, "not_attempted_runtime_state_pid_or_identity_mismatch"

    overlay_window_visible = process_alive and bool(state_payload.get("overlay_window_visible"))
    always_on_top = overlay_window_visible and bool(state_payload.get("always_on_top"))
    overlay_ready = overlay_window_visible and always_on_top
    requirement_state = (
        "visible"
        if overlay_ready
        else "process_running_no_visible_overlay_claim"
        if process_alive
        else "stale_or_unverified"
        if state_exists or pid_present
        else "missing"
    )
    blocker = (
        "" if overlay_ready else "overlay_window_not_observed" if process_alive else "overlay_window_runtime_missing"
    )
    return {
        "ready": overlay_ready,
        "status": "running" if overlay_ready else "missing",
        "runtime_state_path": "data/runtime/lens-overlay/status.json",
        "state_exists": state_exists,
        "state_kind": state_kind,
        "state_status": state_status,
        "state_pid": state_pid,
        "state_pid_matches_pid_file": state_pid > 0 and pid > 0 and state_pid == pid,
        "state_updated_at": str(state_payload.get("updated_at") or ""),
        "pid_path": "data/runtime/lens-overlay/lens-overlay.pid",
        "pid_present": pid_present,
        "pid": pid,
        "process_alive": process_alive,
        "process_alive_check": process_alive_check,
        "overlay_window_visible": overlay_window_visible,
        "always_on_top": always_on_top,
        "overlay_name": state_overlay_name,
        "expected_overlay_name": expected_overlay_name,
        "overlay_scope": state_overlay_scope,
        "expected_overlay_scope": expected_overlay_scope,
        "orb_visual": _orb_visual_runtime_readback(state_payload.get("orb_visual")),
        "voice": _as_dict(state_payload.get("voice")),
        "overlay_voice": _as_dict(state_payload.get("overlay_voice")),
        "voice_provider_readiness": _as_dict(state_payload.get("voice_provider_readiness")),
        "voice_input_readiness": _as_dict(state_payload.get("voice_input_readiness")),
        "requirement_state": requirement_state,
        "blocker": blocker,
    }


def lens_overlay_runtime_readback() -> dict[str, Any]:
    """Return the bounded live overlay readback without composing the full host manifest."""

    return _lens_overlay_runtime_readback()


def _lens_summon_runtime_readback() -> dict[str, Any]:
    override_file = data_dir() / "runtime" / "lens-summon" / "summon-action-override.json"
    hotkey_override_file = data_dir() / "runtime" / "lens-hotkey" / "os-binding-summon-override.json"
    override_config = _json_dict_from_path(override_file) if _path_exists(override_file) else {}
    if not override_config and _path_exists(hotkey_override_file):
        override_config = _json_dict_from_path(hotkey_override_file)
        override_file = hotkey_override_file
    config = override_config or _runtime_json_dict("config/runtime/lens/summon.json")
    config_source = "runtime_override" if override_config else "canonical_config"
    expected_global_hotkey = str(config.get("global_hotkey") or "")
    expected_binding_scope = str(config.get("binding_scope") or "global")
    state_file = data_dir() / "runtime" / "lens-summon" / "status.json"
    state_exists = _path_exists(state_file)
    state_payload = _json_dict_from_path(state_file) if state_exists else {}
    state_kind = str(state_payload.get("kind") or "")
    state_status = str(state_payload.get("status") or "")
    state_global_hotkey = str(state_payload.get("global_hotkey") or "")
    state_binding_scope = str(state_payload.get("binding_scope") or "")
    state_claims_bounded_handoff = (
        state_kind == "lens.summon.runtime_state"
        and state_status == "summon_binding_observed"
        and bool(state_payload.get("bounded_handoff_ready"))
        and state_global_hotkey == expected_global_hotkey
        and state_binding_scope == expected_binding_scope
    )
    state_claims_native_handoff = (
        state_kind == "lens.summon.local_launcher"
        and state_status in {"native_surface_opened", "local_open_ready", "opened"}
        and bool(state_payload.get("native_handoff_ready"))
        and bool(state_payload.get("summon_binding_target_ready"))
        and bool(state_payload.get("local_binding_ready"))
        and bool(state_payload.get("summon_anywhere"))
        and bool(state_payload.get("os_level_summon"))
        and state_global_hotkey == expected_global_hotkey
        and state_binding_scope == expected_binding_scope
    )
    handoff_ready = state_claims_bounded_handoff or state_claims_native_handoff
    requirement_state = (
        "bounded_handoff_observed"
        if state_claims_bounded_handoff
        else "native_handoff_observed"
        if state_claims_native_handoff
        else "stale_or_unverified"
        if state_exists
        else "missing"
    )
    return {
        "ready": handoff_ready,
        "status": "observed" if handoff_ready else "missing",
        "runtime_state_path": "data/runtime/lens-summon/status.json",
        "config_source": config_source,
        "config_override_path": (
            "data/runtime/lens-summon/summon-action-override.json"
            if override_config and override_file.name == "summon-action-override.json"
            else "data/runtime/lens-hotkey/os-binding-summon-override.json"
            if override_config
            else ""
        ),
        "state_exists": state_exists,
        "state_kind": state_kind,
        "state_status": state_status,
        "state_updated_at": str(state_payload.get("updated_at") or ""),
        "global_hotkey": state_global_hotkey,
        "expected_global_hotkey": expected_global_hotkey,
        "binding_scope": state_binding_scope,
        "expected_binding_scope": expected_binding_scope,
        "bounded_handoff_ready": bool(state_payload.get("bounded_handoff_ready"))
        or bool(state_payload.get("native_handoff_ready")),
        "native_handoff_ready": bool(state_payload.get("native_handoff_ready")),
        "native_surface_ready": bool(state_payload.get("native_surface_ready")),
        "summon_binding_target_ready": bool(state_payload.get("summon_binding_target_ready")),
        "local_binding_ready": bool(state_payload.get("local_binding_ready")),
        "local_open_ready": bool(state_payload.get("local_open_ready"))
        or bool(state_payload.get("local_binding_ready")),
        "opened": bool(state_payload.get("opened")),
        "native_request_consumed": bool(state_payload.get("native_request_consumed")),
        "no_launch": bool(state_payload.get("no_launch")),
        "summon_anywhere": bool(state_payload.get("summon_anywhere")),
        "os_level_summon": bool(state_payload.get("os_level_summon")),
        "requirement_state": requirement_state,
        "blocker": "" if handoff_ready else "summon_binding_runtime_missing",
    }


def _lens_host_activation_execution_receipt_root() -> Path:
    return data_dir() / "lens" / "host_activation_executions"


def _lens_host_supervision_execution_receipt_root() -> Path:
    return data_dir() / "lens" / "host_supervision_executions"


def _lens_host_activation_execution_receipts() -> list[dict[str, Any]]:
    root = _lens_host_activation_execution_receipt_root()
    try:
        paths = list(root.glob("*.json"))
    except OSError:
        return []
    receipts: list[dict[str, Any]] = []
    for path in paths:
        item = _json_dict_from_path(path)
        if not item:
            continue
        kind = str(item.get("kind") or "").strip()
        if kind and kind != "lens.host.activation.execution.receipt":
            continue
        receipts.append(item)
    receipts.sort(
        key=lambda item: (_record_ts(item.get("created_ts")), str(item.get("receipt_id") or "")),
        reverse=True,
    )
    return receipts


def _lens_host_supervision_execution_receipts() -> list[dict[str, Any]]:
    root = _lens_host_supervision_execution_receipt_root()
    try:
        paths = list(root.glob("*.json"))
    except OSError:
        return []
    receipts: list[dict[str, Any]] = []
    for path in paths:
        item = _json_dict_from_path(path)
        if not item:
            continue
        kind = str(item.get("kind") or "").strip()
        if kind and kind != "lens.host.supervision.execution.receipt":
            continue
        receipts.append(item)
    receipts.sort(
        key=lambda item: (_record_ts(item.get("created_ts")), str(item.get("receipt_id") or "")),
        reverse=True,
    )
    return receipts


def _lens_host_activation_execution_readback() -> dict[str, Any]:
    receipts = _lens_host_activation_execution_receipts()
    latest = receipts[0] if receipts else {}
    latest_execution = _as_dict(latest.get("execution"))
    latest_resident_claim = _as_dict(latest.get("resident_claim"))
    latest_governance = _as_dict(latest.get("governance"))
    bounded_process_launch = bool(
        latest_execution.get("bounded_process_launch") or latest_governance.get("bounded_process_launch")
    )
    resident_host_process_claimed = bool(latest_resident_claim.get("resident_host_process_claimed"))
    return {
        "status": "readback_ready" if latest else "empty",
        "readback_ready": True,
        "route": LENS_HOST_ACTIVATION_EXECUTIONS_ROUTE,
        "execute_route": LENS_HOST_ACTIVATION_EXECUTE_ROUTE,
        "receipt_root": "data/lens/host_activation_executions",
        "receipt_count": len(receipts),
        "latest_receipt_id": str(latest.get("receipt_id") or ""),
        "latest_status": str(latest.get("status") or ""),
        "latest_created_ts": _record_ts(latest.get("created_ts")),
        "latest_runner_status": str(latest_execution.get("runner_status") or ""),
        "latest_observed_process": bool(latest_execution.get("observed_process")),
        "latest_observed_pid": _safe_pid(latest_execution.get("observed_pid")),
        "latest_runtime_state_path": str(latest_execution.get("runtime_state_path") or ""),
        "bounded_activation_execution_observed": bounded_process_launch,
        "resident_host_process_claimed": resident_host_process_claimed,
        "resident_claim_allowed": False,
        "resident_claim_authority": bool(latest_governance.get("resident_claim_authority")),
        "evidence_only": True,
        "does_not_satisfy_resident_host_process": True,
    }


def _lens_host_supervision_execution_readback() -> dict[str, Any]:
    receipts = _lens_host_supervision_execution_receipts()
    latest = receipts[0] if receipts else {}
    latest_execution = _as_dict(latest.get("execution"))
    latest_resident_claim = _as_dict(latest.get("resident_claim"))
    candidate_supervised = bool(latest_execution.get("resident_runtime_candidate_supervised"))
    resident_supervised_runtime = bool(latest_execution.get("resident_supervised_runtime"))
    resident_host_process = bool(latest_execution.get("resident_host_process"))
    next_gap = str(latest_execution.get("next_smallest_truthful_gap") or "").strip()
    supervision_mode = str(latest_execution.get("supervision_mode") or "bounded_candidate").strip()
    candidate_receipt_observed = (
        bool(latest)
        and candidate_supervised
        and not resident_supervised_runtime
        and next_gap == "resident_supervision_not_persistent"
        and not bool(latest_resident_claim.get("resident_host_process_claimed"))
    )
    supervised_runtime_receipt_observed = (
        bool(latest)
        and supervision_mode == "resident_start"
        and resident_host_process
        and resident_supervised_runtime
        and not bool(latest_resident_claim.get("resident_host_process_claimed"))
    )
    return {
        "status": "readback_ready" if latest else "empty",
        "readback_ready": True,
        "route": "/lens/host/supervision/executions",
        "execute_route": "/lens/host/supervision/execute",
        "receipt_root": "data/lens/host_supervision_executions",
        "receipt_count": len(receipts),
        "latest_receipt_id": str(latest.get("receipt_id") or ""),
        "latest_status": str(latest.get("status") or ""),
        "latest_created_ts": _record_ts(latest.get("created_ts")),
        "latest_bounded_supervised_session": bool(latest_execution.get("bounded_supervised_session")),
        "latest_temporary_host_process_observed": bool(latest_execution.get("temporary_host_process_observed")),
        "latest_supervision_mode": supervision_mode,
        "latest_resident_host_process": resident_host_process,
        "latest_resident_runtime_candidate_supervised": candidate_supervised,
        "latest_resident_supervised_runtime": resident_supervised_runtime,
        "latest_stop_command": str(latest_execution.get("stop_command") or ""),
        "latest_next_smallest_truthful_gap": next_gap,
        "resident_runtime_candidate_receipt_observed": candidate_receipt_observed,
        "resident_supervised_runtime_receipt_observed": supervised_runtime_receipt_observed,
        "resident_claim_allowed": False,
        "resident_claim_authority": False,
        "evidence_only": True,
        "does_not_satisfy_resident_host_process": not supervised_runtime_receipt_observed,
    }


def _lens_host_activation_execution_requirement_readback(launch_manifest: dict[str, Any]) -> dict[str, Any]:
    readback = _as_dict(launch_manifest.get("activation_execution_readback"))
    return {
        "activation_execution_route": str(readback.get("route") or LENS_HOST_ACTIVATION_EXECUTIONS_ROUTE),
        "activation_execution_execute_route": str(readback.get("execute_route") or LENS_HOST_ACTIVATION_EXECUTE_ROUTE),
        "activation_execution_readback_status": str(readback.get("status") or "empty"),
        "activation_execution_receipt_count": _safe_pid(readback.get("receipt_count")),
        "activation_execution_receipt_id": str(readback.get("latest_receipt_id") or ""),
        "activation_execution_status": str(readback.get("latest_status") or ""),
        "activation_execution_runner_status": str(readback.get("latest_runner_status") or ""),
        "activation_execution_observed_process": bool(readback.get("latest_observed_process")),
        "activation_execution_observed_pid": _safe_pid(readback.get("latest_observed_pid")),
        "bounded_activation_execution_observed": bool(readback.get("bounded_activation_execution_observed")),
        "resident_host_process_claimed": bool(readback.get("resident_host_process_claimed")),
        "resident_claim_allowed": False,
        "resident_claim_authority": bool(readback.get("resident_claim_authority")),
        "activation_execution_evidence_only": True,
        "activation_execution_does_not_satisfy_resident_host_process": True,
    }


def _lens_host_supervision_execution_requirement_readback(launch_manifest: dict[str, Any]) -> dict[str, Any]:
    readback = _as_dict(launch_manifest.get("supervision_execution_readback"))
    return {
        "supervision_execution_route": str(readback.get("route") or "/lens/host/supervision/executions"),
        "supervision_execution_execute_route": str(readback.get("execute_route") or "/lens/host/supervision/execute"),
        "supervision_execution_readback_status": str(readback.get("status") or "empty"),
        "supervision_execution_receipt_count": _safe_pid(readback.get("receipt_count")),
        "supervision_execution_receipt_id": str(readback.get("latest_receipt_id") or ""),
        "supervision_execution_status": str(readback.get("latest_status") or ""),
        "supervision_execution_mode": str(readback.get("latest_supervision_mode") or ""),
        "supervision_execution_resident_host_process": bool(readback.get("latest_resident_host_process")),
        "supervision_execution_bounded_session": bool(readback.get("latest_bounded_supervised_session")),
        "supervision_execution_temporary_host_process_observed": bool(
            readback.get("latest_temporary_host_process_observed")
        ),
        "supervision_execution_resident_runtime_candidate_supervised": bool(
            readback.get("latest_resident_runtime_candidate_supervised")
        ),
        "supervision_execution_resident_supervised_runtime": bool(readback.get("latest_resident_supervised_runtime")),
        "supervision_execution_next_smallest_truthful_gap": str(
            readback.get("latest_next_smallest_truthful_gap") or ""
        ),
        "supervision_execution_receipt_observed": bool(readback.get("resident_runtime_candidate_receipt_observed")),
        "supervision_execution_supervised_runtime_receipt_observed": bool(
            readback.get("resident_supervised_runtime_receipt_observed")
        ),
        "supervision_execution_stop_command": str(readback.get("latest_stop_command") or ""),
        "supervision_execution_evidence_only": True,
        "supervision_execution_does_not_satisfy_resident_host_process": bool(
            readback.get("does_not_satisfy_resident_host_process")
        ),
    }


def _lens_host_service_readback(service_config_payload: dict[str, Any]) -> dict[str, Any]:
    service_name = str(service_config_payload.get("service_name") or "Francis-LensHost")
    readback_declared = bool(service_config_payload.get("service_status_readback"))
    platform_supported = os.name == "nt"
    status = "not_checked_by_api"
    installed = False
    service_status = ""
    display_name = ""
    start_type = ""
    query_error = ""

    if not readback_declared:
        blocked_reason = "lens_host_service_status_runner_required"
    elif not platform_supported:
        status = "unsupported_platform"
        blocked_reason = "windows_service_readback_unavailable"
    else:
        service_query = _windows_service_status_readback(service_name)
        status = str(service_query.get("status") or "unavailable")
        installed = bool(service_query.get("installed"))
        service_status = str(service_query.get("service_status") or "")
        display_name = str(service_query.get("display_name") or "")
        start_type = str(service_query.get("start_type") or "")
        query_error = str(service_query.get("query_error") or "")
        if status == "not_installed":
            blocked_reason = "lens_host_service_not_installed"
        elif status == "unavailable":
            blocked_reason = "windows_service_readback_unavailable"
        else:
            blocked_reason = "service_control_authority_not_granted"

    return {
        "status": status,
        "readback_ready": True,
        "service_name": service_name,
        "installed": installed,
        "windows_service": True,
        "platform_supported": platform_supported,
        "service_status_readback": readback_declared,
        "host_query": "windows_service_status" if readback_declared else "runner_only",
        "service_status": service_status,
        "display_name": display_name,
        "start_type": start_type,
        "query_error": query_error,
        "install_supported": False,
        "start_supported": False,
        "stop_supported": False,
        "restart_supported": False,
        "install_authority": False,
        "service_install_authority": False,
        "service_control_authority": False,
        "blocked_reason": blocked_reason,
    }


def _as_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _select_blockers(blockers: list[str], *candidates: str) -> list[str]:
    return [candidate for candidate in candidates if candidate in blockers]


def _ordered_unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        item = str(value or "").strip()
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _lens_host_required_before_enable(service_config_payload: dict[str, Any]) -> list[str]:
    return _ordered_unique(_as_str_list(service_config_payload.get("required_before_enable")))


def _lens_host_missing_required_before_enable(
    required_before_enable: list[str],
    *,
    launch_manifest: dict[str, Any],
) -> list[str]:
    blocker_groups = _as_dict(launch_manifest.get("blocker_groups"))
    surface_blockers = set(_as_str_list(blocker_groups.get("surface_dependencies")))
    process_readback = _as_dict(launch_manifest.get("process_readback"))
    supervisor_readback = _as_dict(launch_manifest.get("supervisor_readback"))
    tray_runtime_readback = _as_dict(launch_manifest.get("tray_runtime_readback"))
    hotkey_runtime_readback = _as_dict(launch_manifest.get("hotkey_runtime_readback"))
    overlay_runtime_readback = _as_dict(launch_manifest.get("overlay_runtime_readback"))
    summon_runtime_readback = _as_dict(launch_manifest.get("summon_runtime_readback"))
    process_alive = bool(process_readback.get("process_alive"))
    resident_supervised_runtime = (
        process_alive
        and bool(supervisor_readback.get("fresh_readback"))
        and bool(supervisor_readback.get("resident_supervised_runtime"))
    )
    resident_host_process_ready = resident_supervised_runtime
    tray_presence_ready = bool(tray_runtime_readback.get("ready")) or "tray_host_missing" not in surface_blockers
    hotkey_binding_ready = (
        bool(hotkey_runtime_readback.get("ready")) or "global_hotkey_binding_missing" not in surface_blockers
    )
    overlay_window_ready = (
        bool(overlay_runtime_readback.get("ready")) or "overlay_window_missing" not in surface_blockers
    )
    missing_by_requirement = {
        "resident_host_process": not resident_host_process_ready,
        "tray_presence": not tray_presence_ready,
        "global_hotkey_binding": not hotkey_binding_ready,
        "overlay_window": not overlay_window_ready,
        "summon_binding": not bool(summon_runtime_readback.get("ready"))
        and "summon_binding_missing" in surface_blockers,
    }
    return [item for item in required_before_enable if missing_by_requirement.get(item, False)]


def _lens_host_prerequisite_handoff(dependency: dict[str, Any]) -> dict[str, Any]:
    requirement_id = str(dependency.get("id") or "").strip()
    if not requirement_id:
        return {}
    blocker = str(dependency.get("blocker") or "")
    families = {
        "resident_host_process": "resident_host",
        "tray_presence": "tray_presence",
        "global_hotkey_binding": "global_hotkey_binding",
        "overlay_window": "overlay_window",
        "summon_binding": "summon_binding",
    }
    proof_scripts = {
        "resident_host_process": "scripts/lens-resident-host-runtime-boundary-proof.ps1 -Mode Status",
        "tray_presence": "scripts/lens-summon-tray-presence-blocker-proof.ps1 -Mode Status",
        "global_hotkey_binding": "scripts/lens-summon-global-hotkey-binding-blocker-proof.ps1 -Mode Status",
        "overlay_window": "scripts/lens-summon-overlay-window-blocker-proof.ps1 -Mode Status",
        "summon_binding": "scripts/lens-summon-binding-blocker-proof.ps1 -Mode Status",
    }
    readiness_routes = {
        "resident_host_process": "/lens/host/runtime-loop/readiness",
        "tray_presence": "/lens/tray/readiness",
        "global_hotkey_binding": "/lens/summon/readiness",
        "overlay_window": "/lens/overlay/readiness",
        "summon_binding": "/lens/summon/readiness",
    }
    next_gaps = {
        "resident_host_process": "resident_host_process_not_supervised",
        "tray_presence": "summon_tray_presence_blocker_boundary",
        "global_hotkey_binding": "os_level_command_palette_binding",
        "overlay_window": "summon_overlay_window_blocker_boundary",
        "summon_binding": "summon_anywhere_blockers",
    }
    next_steps = {
        "resident_host_process": "resolve_resident_host_process_before_persistent_supervision_enablement",
        "tray_presence": "resolve_tray_presence_before_persistent_supervision_enablement",
        "global_hotkey_binding": "resolve_global_hotkey_binding_before_persistent_supervision_enablement",
        "overlay_window": "resolve_overlay_window_before_persistent_supervision_enablement",
        "summon_binding": "resolve_summon_binding_before_persistent_supervision_enablement",
    }
    surface_readback_keys = (
        "preflight_script",
        "config_path",
        "config_exists",
        "family_blockers",
        "authority_blockers",
        "host_dependency_blockers",
        "surface_dependency_blockers",
        "palette_route",
        "status_route",
        "host_route",
        "required_before_enable",
    )
    authority_readback: dict[str, Any]
    if requirement_id == "resident_host_process" and blocker == "resident_supervision_not_persistent":
        next_gap = "resident_supervision_not_persistent"
        next_step = "resolve_resident_supervision_persistence_before_persistent_supervision_enablement"
        proof_script = "scripts/lens-resident-supervision-persistence-boundary-proof.ps1 -Mode Status"
        authority_required = "persistent_process_supervision_authority"
        authority_readback = {
            "authority_route": "/lens/host/supervision/authority",
            "authority_request_route": "/lens/host/supervision/authority/request",
            "authority_requests_route": "/lens/host/supervision/authority/requests",
            "authority_readiness_route": "/lens/host/supervision/authority/readiness",
            "authority_grants_route": "/lens/host/supervision/authority/grants",
            "authority_denials_route": "/lens/host/supervision/authority/denials",
            "approval_action": "lens.host.supervision_authority",
            "persistent_supervision_route": "/lens/host/persistent-supervision",
            "persistent_supervision_enablement_route": "/lens/host/persistent-supervision/enablement",
            "persistent_supervision_enablement_authority_route": (
                "/lens/host/persistent-supervision/enablement/authority"
            ),
            "persistent_supervision_enablement_authority_request_route": (
                "/lens/host/persistent-supervision/enablement/authority/request"
            ),
            "persistent_supervision_enablement_authority_requests_route": (
                "/lens/host/persistent-supervision/enablement/authority/requests"
            ),
            "persistent_supervision_enablement_authority_readiness_route": (
                "/lens/host/persistent-supervision/enablement/authority/readiness"
            ),
            "persistent_supervision_enablement_authority_grants_route": (
                "/lens/host/persistent-supervision/enablement/authority/grants"
            ),
            "persistent_supervision_enablement_execution_route": (
                "/lens/host/persistent-supervision/enablement/execution"
            ),
            "persistent_supervision_enablement_execution_request_route": (
                "/lens/host/persistent-supervision/enablement/execution/request"
            ),
            "persistent_supervision_enablement_execution_requests_route": (
                "/lens/host/persistent-supervision/enablement/execution/requests"
            ),
            "persistent_supervision_enablement_execution_readiness_route": (
                "/lens/host/persistent-supervision/enablement/execution/readiness"
            ),
            "persistent_supervision_enablement_execution_authority_route": (
                "/lens/host/persistent-supervision/enablement/execution/authority"
            ),
            "persistent_supervision_enablement_execution_authority_grants_route": (
                "/lens/host/persistent-supervision/enablement/execution/authority/grants"
            ),
            "persistent_supervision_enablement_executions_route": (
                "/lens/host/persistent-supervision/enablement/executions"
            ),
            "persistent_supervision_next_smallest_truthful_gap": "persistent_supervision_authority_not_granted",
            "persistent_supervision_enablement_authority_action": (
                "lens.host.persistent_supervision_enablement_authority"
            ),
            "persistent_supervision_enablement_execution_action": (
                "lens.host.persistent_supervision_enablement_execution_authority"
            ),
            "persistent_supervision_authority_scope": "system.write",
        }
    elif requirement_id == "resident_host_process":
        next_gap = next_gaps.get(requirement_id, blocker)
        if blocker == "resident_host_process_not_supervised":
            next_step = "consume_resident_host_process_supervision_handoff_before_stage6_closure"
            proof_script = "scripts/lens-resident-host-process-supervision-blocker-proof.ps1 -Mode Status"
        else:
            next_step = next_steps.get(requirement_id, "resolve_resident_host_process_before_persistent_supervision")
            proof_script = proof_scripts.get(requirement_id, "")
        authority_required = "resident_host_process_tray_hotkey_overlay_and_summon_prerequisites"
        authority_readback = {
            "authority_route": "/lens/host/activation/authority",
            "authority_request_route": "/lens/host/activation/request",
            "authority_readback_route": "/lens/host/activation",
            "authority_preflight_route": "/lens/host/activation/preflight",
            "authority_plan_route": "/lens/host/activation/plan",
            "authority_execute_route": "/lens/host/activation/execute",
            "authority_executions_route": "/lens/host/activation/executions",
            "authority_grants_route": "/lens/host/activation/authority/grants",
            "execution_denials_route": "/lens/host/activation/denials",
            "supervision_authority_route": "/lens/host/supervision/authority",
            "supervision_authority_request_route": "/lens/host/supervision/authority/request",
            "supervision_authority_requests_route": "/lens/host/supervision/authority/requests",
            "supervision_authority_grants_route": "/lens/host/supervision/authority/grants",
            "supervision_execute_route": "/lens/host/supervision/execute",
            "supervision_executions_route": "/lens/host/supervision/executions",
            "supervision_start_mode": "resident_start",
            "supervision_stop_mode": "resident_stop",
            "resident_runtime_preflight_route": "/lens/resident-runtime/preflight",
            "resident_runtime_policy_route": "/lens/resident-runtime/policy",
            "resident_runtime_plan_route": "/lens/resident-runtime/plan",
            "resident_runtime_authority_grant_readiness_route": ("/lens/resident-runtime/authority-grant/readiness"),
            "resident_runtime_authority_request_route": "/lens/resident-runtime/authority-grant/request",
            "resident_runtime_authority_requests_route": "/lens/resident-runtime/authority-grant/requests",
            "resident_runtime_authority_route": "/lens/resident-runtime/authority-grant",
            "resident_runtime_authority_grants_route": "/lens/resident-runtime/authority-grant/grants",
            "resident_runtime_authority_denials_route": "/lens/resident-runtime/authority-grant/denials",
            "resident_runtime_execute_route": "/lens/resident-runtime/execute",
            "resident_runtime_executions_route": "/lens/resident-runtime/executions",
            "resident_runtime_execution_denials_route": "/lens/resident-runtime/denials",
            "request_route": "/lens/resident-runtime/authority-grant/request",
            "requests_route": "/lens/resident-runtime/authority-grant/requests",
            "grant_route": "/lens/resident-runtime/authority-grant",
            "grants_route": "/lens/resident-runtime/authority-grant/grants",
            "denials_route": "/lens/resident-runtime/denials",
            "execution_readiness_route": "/lens/resident-runtime/plan",
            "execution_route": "/lens/resident-runtime/execute",
            "executions_route": "/lens/resident-runtime/executions",
            "approval_action": "lens.host.foreground_activation",
            "resident_runtime_approval_action": "lens.resident_runtime.execution_authority",
            "authority_scope": "system.write",
        }
    else:
        next_gap = next_gaps.get(requirement_id, blocker)
        next_step = next_steps.get(requirement_id, f"resolve_{requirement_id}_before_persistent_supervision")
        proof_script = proof_scripts.get(requirement_id, "")
        authority_required = "resident_host_process_tray_hotkey_overlay_and_summon_prerequisites"
        authority_readback = {
            "readback_route": str(dependency.get("route") or readiness_routes.get(requirement_id, "/lens/status")),
            "preflight_route": "/lens/preflight",
        }
        for key in surface_readback_keys:
            value = dependency.get(key)
            if value not in ("", None, [], {}):
                authority_readback[key] = value
        if requirement_id == "global_hotkey_binding":
            authority_readback.update(
                {
                    "os_binding_readiness_route": "/lens/os-binding/readiness",
                    "os_binding_plan_route": "/lens/os-binding/plan",
                    "os_binding_authority_route": "/lens/os-binding/authority",
                    "os_binding_authority_request_route": "/lens/os-binding/authority/request",
                    "os_binding_authority_requests_route": "/lens/os-binding/authority/requests",
                    "os_binding_authority_grants_route": "/lens/os-binding/authority/grants",
                    "os_binding_execution_readiness_route": "/lens/os-binding/execution/readiness",
                    "os_binding_execution_denials_route": "/lens/os-binding/denials",
                    "approval_action": "lens.os_binding.command_palette_binding_authority",
                    "authority_scope": "system.write",
                }
            )
    handoff = {
        "id": requirement_id,
        "family": families.get(requirement_id, requirement_id),
        "route": str(dependency.get("route") or "/lens/status"),
        "readiness_route": str(dependency.get("readiness_route") or readiness_routes.get(requirement_id, "")),
        "proof_script": proof_script,
        "blocker": blocker,
        "requirement_state": str(dependency.get("requirement_state") or ""),
        "blocked_reason": str(dependency.get("blocked_reason") or ""),
        "next_step": next_step,
        "next_smallest_truthful_gap": next_gap,
        "acceptance_criterion": "system_resident_presence",
        "authority_required": authority_required,
        "authority_granted": False,
        "read_only_contract": True,
        "diagnostic_only": True,
        "would_execute": False,
        "would_mutate": False,
    }
    if requirement_id == "resident_host_process":
        for key in (
            "resident_runtime_candidate_supervised",
            "fresh_resident_runtime_candidate_supervised",
            "supervisor_freshness_status",
            "supervisor_state_age_seconds",
            "supervision_execution_receipt_observed",
            "supervision_execution_receipt_id",
            "supervision_execution_readback_status",
            "supervision_execution_next_smallest_truthful_gap",
            "supervision_execution_supervised_runtime_receipt_observed",
            "supervision_execution_stop_command",
        ):
            if key in dependency:
                handoff[key] = dependency[key]
    handoff.update(authority_readback)
    return handoff


def _lens_host_first_missing_prerequisite_handoff(
    enablement_dependency_readback: list[dict[str, Any]],
) -> dict[str, Any]:
    for dependency in enablement_dependency_readback:
        if not bool(dependency.get("ready")):
            return _lens_host_prerequisite_handoff(dependency)
    return {}


def _lens_host_resident_process_requirement_readback(
    *,
    launch_manifest: dict[str, Any],
    missing: bool,
) -> dict[str, Any]:
    process_readback = _as_dict(launch_manifest.get("process_readback"))
    supervisor_readback = _as_dict(launch_manifest.get("supervisor_readback"))
    activation_execution_readback = _lens_host_activation_execution_requirement_readback(launch_manifest)
    supervision_execution_readback = _lens_host_supervision_execution_requirement_readback(launch_manifest)
    process_alive = bool(process_readback.get("process_alive"))
    blocked_reason = str(process_readback.get("blocked_reason") or "")
    resident_candidate_supervised = bool(supervisor_readback.get("resident_runtime_candidate_supervised"))
    fresh_resident_candidate_supervised = bool(supervisor_readback.get("fresh_resident_runtime_candidate_supervised"))
    resident_supervised_runtime = (
        process_alive
        and bool(supervisor_readback.get("fresh_readback"))
        and bool(supervisor_readback.get("resident_supervised_runtime"))
    )
    supervision_execution_candidate_observed = bool(
        supervision_execution_readback.get("supervision_execution_receipt_observed")
    )
    durable_resident_candidate_supervised = resident_candidate_supervised or bool(
        supervision_execution_readback.get("supervision_execution_resident_runtime_candidate_supervised")
    )
    if not missing:
        return {
            **activation_execution_readback,
            **supervision_execution_readback,
            "requirement_state": "ready",
            "process_alive": process_alive,
            "blocked_reason": "",
            "resident_runtime_candidate_supervised": durable_resident_candidate_supervised,
            "fresh_resident_runtime_candidate_supervised": fresh_resident_candidate_supervised,
            "resident_supervised_runtime": resident_supervised_runtime,
            "supervisor_freshness_status": str(supervisor_readback.get("freshness_status") or ""),
            "supervisor_state_age_seconds": supervisor_readback.get("state_age_seconds"),
        }
    if (
        fresh_resident_candidate_supervised and resident_candidate_supervised
    ) or supervision_execution_candidate_observed:
        return {
            **activation_execution_readback,
            **supervision_execution_readback,
            "requirement_state": "resident_candidate_observed_not_persistent",
            "process_alive": process_alive,
            "blocked_reason": "resident_supervision_not_persistent",
            "blocker": "resident_supervision_not_persistent",
            "resident_runtime_candidate_supervised": True,
            "fresh_resident_runtime_candidate_supervised": fresh_resident_candidate_supervised,
            "resident_supervised_runtime": False,
            "resident_claim_allowed": False,
            "supervisor_freshness_status": str(supervisor_readback.get("freshness_status") or ""),
            "supervisor_state_age_seconds": supervisor_readback.get("state_age_seconds"),
            "supervision_execution_receipt_observed": supervision_execution_candidate_observed,
        }
    if process_alive:
        return {
            **activation_execution_readback,
            **supervision_execution_readback,
            "requirement_state": "foreground_observed_not_supervised",
            "process_alive": True,
            "blocked_reason": blocked_reason or "resident_host_not_supervised",
            "blocker": "resident_host_process_not_supervised",
            "resident_runtime_candidate_supervised": durable_resident_candidate_supervised,
            "fresh_resident_runtime_candidate_supervised": fresh_resident_candidate_supervised,
            "resident_supervised_runtime": False,
            "supervisor_freshness_status": str(supervisor_readback.get("freshness_status") or ""),
            "supervisor_state_age_seconds": supervisor_readback.get("state_age_seconds"),
        }
    return {
        **activation_execution_readback,
        **supervision_execution_readback,
        "requirement_state": "missing",
        "process_alive": False,
        "blocked_reason": blocked_reason or "resident_host_process_missing",
        "blocker": "resident_host_process_missing",
        "resident_runtime_candidate_supervised": durable_resident_candidate_supervised,
        "fresh_resident_runtime_candidate_supervised": fresh_resident_candidate_supervised,
        "resident_supervised_runtime": False,
    }


def _lens_host_tray_presence_requirement_readback(
    *,
    launch_manifest: dict[str, Any],
    missing: bool,
) -> dict[str, Any]:
    config_path = "config/runtime/lens/tray.json"
    config = _runtime_json_dict(config_path)
    tray_runtime_readback = _as_dict(launch_manifest.get("tray_runtime_readback"))
    config_exists = bool(config)
    tray_host_enabled = bool(config.get("tray_host_enabled"))
    tray_icon_enabled = bool(config.get("tray_icon_enabled"))
    startup_register = bool(config.get("startup_register"))
    tray_registration_authority = bool(config.get("tray_registration_authority"))
    tray_icon_authority = bool(config.get("tray_icon_authority"))
    notification_authority = bool(config.get("notification_authority"))
    tray_runtime_ready = bool(tray_runtime_readback.get("ready"))
    blocked_reason = str(config.get("blocked_reason") or "lens_tray_presence_disabled_pending_authority")
    family_blockers = []
    if not config_exists:
        family_blockers.append("lens_tray_config_missing")
    if blocked_reason:
        family_blockers.append(blocked_reason)
    if not tray_host_enabled:
        family_blockers.append("tray_host_disabled")
    if not tray_icon_enabled:
        family_blockers.append("tray_icon_disabled")
    if not startup_register:
        family_blockers.append("tray_startup_registration_disabled")
    if not tray_registration_authority:
        family_blockers.append("tray_registration_authority_not_granted")
    if not tray_icon_authority:
        family_blockers.append("tray_icon_authority_not_granted")
    if not notification_authority:
        family_blockers.append("notification_authority_not_granted")
    if missing and tray_runtime_readback and not tray_runtime_ready:
        family_blockers.append(str(tray_runtime_readback.get("blocker") or "tray_presence_runtime_missing"))

    requirement_state = "ready"
    if missing:
        if not config_exists:
            requirement_state = "config_missing"
        elif tray_runtime_readback and str(tray_runtime_readback.get("requirement_state") or "") != "missing":
            requirement_state = str(tray_runtime_readback.get("requirement_state") or "stale_or_unverified")
        elif not tray_host_enabled:
            requirement_state = "tray_host_disabled"
        elif not tray_registration_authority:
            requirement_state = "registration_authority_blocked"
        else:
            requirement_state = "tray_host_missing"

    return {
        "requirement_state": requirement_state,
        "blocked_reason": blocked_reason if missing else "",
        "config_path": config_path,
        "config_exists": config_exists,
        "presence_name": str(config.get("presence_name") or "Francis Lens Tray Presence"),
        "tray_scope": str(config.get("tray_scope") or "user_session"),
        "readiness_route": "/lens/tray/readiness",
        "tray_host_enabled": tray_host_enabled,
        "tray_icon_enabled": tray_icon_enabled,
        "startup_register": startup_register,
        "tray_registration_authority": tray_registration_authority,
        "tray_icon_authority": tray_icon_authority,
        "notification_authority": notification_authority,
        "tray_config_ready": (
            config_exists
            and bool(config.get("enabled"))
            and tray_host_enabled
            and tray_icon_enabled
            and startup_register
            and tray_registration_authority
            and tray_icon_authority
        ),
        "tray_runtime_ready": tray_runtime_ready,
        "tray_presence_source": "live_runtime_readback"
        if tray_runtime_ready
        else "enabled_config"
        if bool(config.get("enabled"))
        and tray_host_enabled
        and tray_icon_enabled
        and startup_register
        and tray_registration_authority
        and tray_icon_authority
        else "blocked_config",
        "tray_runtime_requirement_state": str(tray_runtime_readback.get("requirement_state") or "missing"),
        "tray_runtime_blocker": str(tray_runtime_readback.get("blocker") or ""),
        "tray_runtime_process_alive": bool(tray_runtime_readback.get("process_alive")),
        "tray_runtime_icon_visible": bool(tray_runtime_readback.get("tray_icon_visible")),
        "tray_runtime_pid": int(tray_runtime_readback.get("pid") or 0),
        "tray_runtime_status": str(tray_runtime_readback.get("state_status") or ""),
        "tray_runtime_status_kind": str(tray_runtime_readback.get("state_kind") or ""),
        "tray_runtime_state_exists": bool(tray_runtime_readback.get("state_exists")),
        "tray_runtime_status_pid_matches_pid_file": bool(tray_runtime_readback.get("state_pid_matches_pid_file")),
        "family_blockers": _ordered_unique(family_blockers) if missing else [],
    }


def _lens_host_global_hotkey_requirement_readback(
    *,
    launch_manifest: dict[str, Any],
    missing: bool,
) -> dict[str, Any]:
    config_path = "config/runtime/lens/summon.json"
    config = _runtime_json_dict(config_path)
    hotkey_runtime_readback = _as_dict(launch_manifest.get("hotkey_runtime_readback"))
    config_exists = bool(config)
    global_hotkey = str(config.get("global_hotkey") or "")
    binding_scope = str(config.get("binding_scope") or "global")
    palette_route = str(config.get("palette_route") or "/lens/status")
    binding_enabled = bool(config.get("binding_enabled"))
    register_hotkey = bool(config.get("register_hotkey"))
    startup_register = bool(config.get("startup_register"))
    hotkey_registration_authority = bool(config.get("hotkey_registration_authority"))
    summon_authority = bool(config.get("summon_authority"))
    hotkey_runtime_ready = bool(hotkey_runtime_readback.get("ready"))
    family_blockers = []
    if not config_exists:
        family_blockers.append("lens_summon_config_missing")
    if not global_hotkey:
        family_blockers.append("global_hotkey_not_declared")
    if not binding_enabled:
        family_blockers.append("global_hotkey_binding_disabled")
    if not register_hotkey:
        family_blockers.append("global_hotkey_registration_disabled")
    if not hotkey_registration_authority:
        family_blockers.append("hotkey_registration_authority_not_granted")
    if missing and hotkey_runtime_readback and not hotkey_runtime_ready:
        family_blockers.append(str(hotkey_runtime_readback.get("blocker") or "global_hotkey_binding_runtime_missing"))

    requirement_state = "ready"
    if missing:
        if not config_exists:
            requirement_state = "config_missing"
        elif hotkey_runtime_readback and str(hotkey_runtime_readback.get("requirement_state") or "") != "missing":
            requirement_state = str(hotkey_runtime_readback.get("requirement_state") or "stale_or_unverified")
        elif not global_hotkey:
            requirement_state = "hotkey_not_declared"
        elif not binding_enabled:
            requirement_state = "binding_disabled"
        elif not register_hotkey:
            requirement_state = "registration_disabled"
        elif not hotkey_registration_authority:
            requirement_state = "registration_authority_blocked"
        else:
            requirement_state = "global_hotkey_binding_missing"

    return {
        "requirement_state": requirement_state,
        "blocked_reason": family_blockers[0] if missing and family_blockers else "",
        "config_path": config_path,
        "config_exists": config_exists,
        "global_hotkey": global_hotkey,
        "binding_scope": binding_scope,
        "palette_route": palette_route,
        "readiness_route": "/lens/summon/readiness",
        "preflight_script": "scripts/lens-summon-preflight.ps1 -Mode Status",
        "binding_enabled": binding_enabled,
        "register_hotkey": register_hotkey,
        "startup_register": startup_register,
        "hotkey_registration_authority": hotkey_registration_authority,
        "summon_authority": summon_authority,
        "hotkey_runtime_ready": hotkey_runtime_ready,
        "hotkey_presence_source": "live_runtime_readback"
        if hotkey_runtime_ready
        else "enabled_config"
        if config_exists and binding_enabled and register_hotkey and hotkey_registration_authority
        else "blocked_config",
        "hotkey_runtime_requirement_state": str(hotkey_runtime_readback.get("requirement_state") or "missing"),
        "hotkey_runtime_blocker": str(hotkey_runtime_readback.get("blocker") or ""),
        "hotkey_runtime_process_alive": bool(hotkey_runtime_readback.get("process_alive")),
        "hotkey_runtime_bound": bool(hotkey_runtime_readback.get("hotkey_bound")),
        "hotkey_runtime_pid": int(hotkey_runtime_readback.get("pid") or 0),
        "hotkey_runtime_status": str(hotkey_runtime_readback.get("state_status") or ""),
        "hotkey_runtime_status_kind": str(hotkey_runtime_readback.get("state_kind") or ""),
        "hotkey_runtime_state_exists": bool(hotkey_runtime_readback.get("state_exists")),
        "hotkey_runtime_status_pid_matches_pid_file": bool(hotkey_runtime_readback.get("state_pid_matches_pid_file")),
        "hotkey_runtime_readback": hotkey_runtime_readback,
        "family_blockers": _ordered_unique(family_blockers) if missing else [],
    }


def _lens_host_summon_binding_requirement_readback(*, missing: bool) -> dict[str, Any]:
    config_path = "config/runtime/lens/summon.json"
    config = _runtime_json_dict(config_path)
    config_exists = bool(config)
    summon_name = str(config.get("summon_name") or "Francis Lens Summon")
    global_hotkey = str(config.get("global_hotkey") or "")
    binding_scope = str(config.get("binding_scope") or "global")
    palette_route = str(config.get("palette_route") or "/lens/status")
    host_preflight = str(config.get("host_preflight") or "scripts/lens-host-preflight.ps1")
    host_status_runner = str(config.get("host_status_runner") or "scripts/lens-host.ps1")
    summon_runner = str(config.get("summon_runner") or "scripts/lens-summon.ps1")
    local_palette_launcher = str(
        config.get("local_palette_launcher") or "scripts/lens-command-palette.ps1 -Mode LocalOpen"
    )
    launch_target = str(config.get("launch_target") or "lens_host")
    launch_mode = str(config.get("launch_mode") or "Foreground")
    blocked_reason = str(config.get("blocked_reason") or "lens_summon_binding_disabled_pending_authority")
    summon_enabled = bool(config.get("enabled"))
    binding_enabled = bool(config.get("binding_enabled"))
    register_hotkey = bool(config.get("register_hotkey"))
    startup_register = bool(config.get("startup_register"))
    overlay_required = bool(config.get("overlay_required", True))
    tray_required = bool(config.get("tray_required", True))
    summon_authority = bool(config.get("summon_authority"))
    hotkey_registration_authority = bool(config.get("hotkey_registration_authority"))
    overlay_control_authority = bool(config.get("overlay_control_authority"))
    local_process_launch_authority = bool(config.get("local_process_launch_authority"))
    summon_runtime_readback = _lens_summon_runtime_readback()
    summon_runtime_ready = bool(summon_runtime_readback.get("ready"))
    host_preflight_exists = _runtime_file_exists(host_preflight)
    host_status_runner_exists = _runtime_file_exists(host_status_runner)
    summon_runner_exists = _runtime_file_exists(summon_runner)
    family_blockers = []
    host_dependency_blockers = []
    surface_dependency_blockers = []
    authority_blockers = []

    if not config_exists:
        family_blockers.append("lens_summon_config_missing")
    if blocked_reason:
        family_blockers.append(blocked_reason)
    if not summon_authority:
        family_blockers.append("summon_authority_not_granted")
        authority_blockers.append("summon_authority_not_granted")
    if not host_preflight_exists:
        host_dependency_blockers.append("lens_host_lifecycle_preflight_missing")
    if not host_status_runner_exists:
        host_dependency_blockers.append("lens_host_status_runner_missing")
    if not summon_runner_exists:
        family_blockers.append("lens_summon_runner_missing")
    if not local_process_launch_authority:
        host_dependency_blockers.append("local_process_launch_authority_not_granted")
        authority_blockers.append("local_process_launch_authority_not_granted")
    if overlay_required:
        surface_dependency_blockers.append("overlay_window_missing")
    if tray_required:
        surface_dependency_blockers.append("tray_host_missing")
    if not hotkey_registration_authority:
        authority_blockers.append("hotkey_registration_authority_not_granted")
    if not overlay_control_authority:
        authority_blockers.append("overlay_control_authority_not_granted")

    requirement_state = "ready"
    if missing:
        if not config_exists:
            requirement_state = "config_missing"
        elif blocked_reason == "lens_summon_binding_not_implemented":
            requirement_state = "not_implemented"
        elif blocked_reason == "lens_summon_binding_disabled_pending_authority":
            requirement_state = "disabled_pending_authority"
        elif not summon_authority:
            requirement_state = "summon_authority_blocked"
        elif not local_process_launch_authority:
            requirement_state = "local_process_launch_authority_blocked"
        else:
            requirement_state = "summon_binding_missing"

    return {
        "requirement_state": requirement_state,
        "blocked_reason": family_blockers[0] if missing and family_blockers else "",
        "config_path": config_path,
        "config_exists": config_exists,
        "summon_name": summon_name,
        "global_hotkey": global_hotkey,
        "binding_scope": binding_scope,
        "palette_route": palette_route,
        "readiness_route": "/lens/summon/readiness",
        "preflight_script": "scripts/lens-summon-preflight.ps1 -Mode Status",
        "acceptance_criterion": "summon_anywhere",
        "next_smallest_truthful_gap": "summon_anywhere_blockers",
        "required_before_enable": _as_str_list(config.get("required_before_enable")),
        "host_preflight": host_preflight,
        "host_preflight_exists": host_preflight_exists,
        "host_status_runner": host_status_runner,
        "host_status_runner_exists": host_status_runner_exists,
        "summon_runner": summon_runner,
        "summon_runner_exists": summon_runner_exists,
        "local_palette_launcher": local_palette_launcher,
        "local_binding_target_ready": summon_runner_exists,
        "launch_target": launch_target,
        "launch_mode": launch_mode,
        "summon_enabled": summon_enabled,
        "binding_enabled": binding_enabled,
        "register_hotkey": register_hotkey,
        "startup_register": startup_register,
        "overlay_required": overlay_required,
        "tray_required": tray_required,
        "summon_authority": summon_authority,
        "hotkey_registration_authority": hotkey_registration_authority,
        "overlay_control_authority": overlay_control_authority,
        "local_process_launch_authority": local_process_launch_authority,
        "summon_runtime_ready": summon_runtime_ready,
        "summon_presence_source": "live_runtime_readback"
        if summon_runtime_ready
        else "enabled_config"
        if config_exists and summon_authority and local_process_launch_authority
        else "blocked_config",
        "summon_runtime_requirement_state": str(summon_runtime_readback.get("requirement_state") or "missing"),
        "summon_runtime_blocker": str(summon_runtime_readback.get("blocker") or ""),
        "summon_runtime_bounded_handoff_ready": bool(summon_runtime_readback.get("bounded_handoff_ready")),
        "summon_runtime_local_open_ready": bool(summon_runtime_readback.get("local_open_ready")),
        "summon_runtime_no_launch": bool(summon_runtime_readback.get("no_launch")),
        "summon_runtime_readback": summon_runtime_readback,
        "family_blockers": _ordered_unique(family_blockers) if missing else [],
        "host_dependency_blockers": _ordered_unique(host_dependency_blockers) if missing else [],
        "surface_dependency_blockers": _ordered_unique(surface_dependency_blockers) if missing else [],
        "authority_blockers": _ordered_unique(authority_blockers) if missing else [],
    }


def _lens_host_overlay_window_requirement_readback(
    *,
    launch_manifest: dict[str, Any],
    missing: bool,
) -> dict[str, Any]:
    config_path = "config/runtime/lens/overlay.json"
    config = _runtime_json_dict(config_path)
    overlay_runtime_readback = _as_dict(launch_manifest.get("overlay_runtime_readback"))
    config_exists = bool(config)
    overlay_name = str(config.get("overlay_name") or "Francis Lens Overlay")
    overlay_scope = str(config.get("overlay_scope") or "user_session")
    status_route = str(config.get("status_route") or "/lens/status")
    host_route = str(config.get("host_route") or "/lens/host")
    blocked_reason = str(config.get("blocked_reason") or "lens_overlay_window_not_implemented")
    overlay_enabled = bool(config.get("enabled"))
    window_enabled = bool(config.get("window_enabled"))
    always_on_top = bool(config.get("always_on_top"))
    dock_supported = bool(config.get("dock_supported"))
    focus_supported = bool(config.get("focus_supported"))
    click_through_supported = bool(config.get("click_through_supported"))
    capture_supported = bool(config.get("capture_supported"))
    overlay_control_authority = bool(config.get("overlay_control_authority"))
    window_management_authority = bool(config.get("window_management_authority"))
    local_process_launch_authority = bool(config.get("local_process_launch_authority"))
    capture_authority = bool(config.get("capture_authority"))
    summon_authority = bool(config.get("summon_authority"))
    tray_registration_authority = bool(config.get("tray_registration_authority"))
    overlay_runtime_ready = bool(overlay_runtime_readback.get("ready"))
    family_blockers = []
    if not config_exists:
        family_blockers.append("lens_overlay_config_missing")
    if blocked_reason:
        family_blockers.append(blocked_reason)
    if not window_enabled:
        family_blockers.append("overlay_window_disabled")
    if not always_on_top:
        family_blockers.append("always_on_top_disabled")
    if not dock_supported:
        family_blockers.append("overlay_dock_not_supported")
    if not focus_supported:
        family_blockers.append("overlay_focus_not_supported")
    if not click_through_supported:
        family_blockers.append("overlay_click_through_not_supported")
    if not overlay_control_authority:
        family_blockers.append("overlay_control_authority_not_granted")
    if not window_management_authority:
        family_blockers.append("window_management_authority_not_granted")
    if not local_process_launch_authority:
        family_blockers.append("local_process_launch_authority_not_granted")
    if not capture_authority:
        family_blockers.append("capture_authority_not_granted")
    if not summon_authority:
        family_blockers.append("summon_authority_not_granted")
    if not tray_registration_authority:
        family_blockers.append("tray_registration_authority_not_granted")
    if missing and overlay_runtime_readback and not overlay_runtime_ready:
        family_blockers.append(str(overlay_runtime_readback.get("blocker") or "overlay_window_runtime_missing"))

    requirement_state = "ready"
    if missing:
        if not config_exists:
            requirement_state = "config_missing"
        elif overlay_runtime_readback and str(overlay_runtime_readback.get("requirement_state") or "") != "missing":
            requirement_state = str(overlay_runtime_readback.get("requirement_state") or "stale_or_unverified")
        elif not window_enabled:
            requirement_state = "window_disabled"
        elif not overlay_control_authority:
            requirement_state = "overlay_control_authority_blocked"
        elif not window_management_authority:
            requirement_state = "window_management_authority_blocked"
        else:
            requirement_state = "overlay_window_missing"

    return {
        "requirement_state": requirement_state,
        "blocked_reason": family_blockers[0] if missing and family_blockers else "",
        "config_path": config_path,
        "config_exists": config_exists,
        "overlay_name": overlay_name,
        "overlay_scope": overlay_scope,
        "status_route": status_route,
        "host_route": host_route,
        "readiness_route": "/lens/overlay/readiness",
        "preflight_script": "scripts/lens-overlay-preflight.ps1 -Mode Status",
        "required_before_enable": _as_str_list(config.get("required_before_enable")),
        "overlay_enabled": overlay_enabled,
        "window_enabled": window_enabled,
        "always_on_top": always_on_top,
        "dock_supported": dock_supported,
        "focus_supported": focus_supported,
        "click_through_supported": click_through_supported,
        "capture_supported": capture_supported,
        "overlay_control_authority": overlay_control_authority,
        "window_management_authority": window_management_authority,
        "local_process_launch_authority": local_process_launch_authority,
        "capture_authority": capture_authority,
        "summon_authority": summon_authority,
        "tray_registration_authority": tray_registration_authority,
        "overlay_runtime_ready": overlay_runtime_ready,
        "overlay_presence_source": "live_runtime_readback"
        if overlay_runtime_ready
        else "enabled_config"
        if config_exists
        and overlay_enabled
        and window_enabled
        and always_on_top
        and overlay_control_authority
        and window_management_authority
        else "blocked_config",
        "overlay_runtime_requirement_state": str(overlay_runtime_readback.get("requirement_state") or "missing"),
        "overlay_runtime_blocker": str(overlay_runtime_readback.get("blocker") or ""),
        "overlay_runtime_process_alive": bool(overlay_runtime_readback.get("process_alive")),
        "overlay_runtime_window_visible": bool(overlay_runtime_readback.get("overlay_window_visible")),
        "overlay_runtime_always_on_top": bool(overlay_runtime_readback.get("always_on_top")),
        "overlay_runtime_pid": int(overlay_runtime_readback.get("pid") or 0),
        "overlay_runtime_status": str(overlay_runtime_readback.get("state_status") or ""),
        "overlay_runtime_status_kind": str(overlay_runtime_readback.get("state_kind") or ""),
        "overlay_runtime_state_exists": bool(overlay_runtime_readback.get("state_exists")),
        "overlay_runtime_status_pid_matches_pid_file": bool(overlay_runtime_readback.get("state_pid_matches_pid_file")),
        "overlay_runtime_readback": overlay_runtime_readback,
        "family_blockers": _ordered_unique(family_blockers) if missing else [],
    }


def _lens_host_enablement_dependency_readback(
    required_before_enable: list[str],
    *,
    launch_manifest: dict[str, Any],
) -> list[dict[str, Any]]:
    missing = set(_lens_host_missing_required_before_enable(required_before_enable, launch_manifest=launch_manifest))
    routes = {
        "resident_host_process": "/lens/host",
        "tray_presence": "/lens/tray",
        "global_hotkey_binding": "/lens/summon",
        "overlay_window": "/lens/overlay",
        "summon_binding": "/lens/summon",
    }
    blockers = {
        "resident_host_process": "resident_host_process_missing",
        "tray_presence": "tray_host_missing",
        "global_hotkey_binding": "global_hotkey_binding_missing",
        "overlay_window": "overlay_window_missing",
        "summon_binding": "summon_binding_missing",
    }
    dependencies = []
    for item in required_before_enable:
        item_missing = item in missing
        blocker = blockers.get(item, f"{item}_missing") if item_missing else ""
        extra_readback = {}
        if item == "resident_host_process":
            extra_readback = _lens_host_resident_process_requirement_readback(
                launch_manifest=launch_manifest,
                missing=item_missing,
            )
            blocker = str(extra_readback.get("blocker") or blocker) if item_missing else ""
        elif item == "tray_presence":
            extra_readback = _lens_host_tray_presence_requirement_readback(
                launch_manifest=launch_manifest,
                missing=item_missing,
            )
        elif item == "global_hotkey_binding":
            extra_readback = _lens_host_global_hotkey_requirement_readback(
                launch_manifest=launch_manifest,
                missing=item_missing,
            )
        elif item == "overlay_window":
            extra_readback = _lens_host_overlay_window_requirement_readback(
                launch_manifest=launch_manifest,
                missing=item_missing,
            )
        elif item == "summon_binding":
            extra_readback = _lens_host_summon_binding_requirement_readback(missing=item_missing)
        dependencies.append(
            {
                **extra_readback,
                "id": item,
                "family": {
                    "resident_host_process": "resident_host",
                    "tray_presence": "tray_presence",
                    "global_hotkey_binding": "global_hotkey_binding",
                    "overlay_window": "overlay_window",
                    "summon_binding": "summon_binding",
                }.get(item, item),
                "route": routes.get(item, "/lens/status"),
                "ready": not item_missing,
                "status": "blocked" if item_missing else "ready",
                "blocker": blocker,
            }
        )
    return dependencies


def _record_ts(value: Any) -> float:
    if isinstance(value, bool):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _iso_epoch_seconds(value: Any) -> float:
    raw = str(value or "").strip()
    if not raw:
        return 0.0
    if raw.endswith("Z"):
        raw = f"{raw[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return 0.0
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.timestamp()


def _age_seconds(value: Any) -> int | None:
    epoch = _iso_epoch_seconds(value)
    if epoch <= 0:
        return None
    return max(0, int(time.time() - epoch))


def _lens_host_supervisor_readback() -> dict[str, Any]:
    state_file = data_dir() / "runtime" / "lens-host-supervisor" / "status.json"
    state_payload = _json_dict_from_path(
        state_file,
        transient_retries=4 if state_file.parent.exists() else 0,
    )
    state_exists = bool(state_payload) or _path_exists(state_file)
    state_status = str(state_payload.get("status") or "")
    mode = str(state_payload.get("mode") or "")
    host_mode = str(state_payload.get("host_mode") or "")
    supervisor_pid = _safe_pid(state_payload.get("supervisor_pid"))
    observed_pid = _safe_pid(state_payload.get("observed_pid"))
    observed_state = str(state_payload.get("observed_state") or "")
    supervisor_process_alive, supervisor_process_alive_check = (
        _process_alive_readback(supervisor_pid) if supervisor_pid > 0 else (False, "not_attempted_no_supervisor_pid")
    )
    host_process_readback = _lens_host_process_readback()
    host_process_pid = _safe_pid(host_process_readback.get("pid"))
    observed_pid_matches_host_process = observed_pid > 0 and observed_pid == host_process_pid
    if observed_pid_matches_host_process:
        observed_process_alive = bool(host_process_readback.get("process_alive"))
        observed_process_alive_check = str(host_process_readback.get("process_alive_check") or "")
    elif observed_pid <= 0:
        observed_process_alive = False
        observed_process_alive_check = "not_attempted_no_observed_pid"
    else:
        observed_process_alive = False
        observed_process_alive_check = "not_attempted_observed_pid_mismatch"
    bounded_supervisor_observed = state_status in {
        "observing",
        "observation_completed",
        "supervising",
        "supervised_session_completed",
        "resident_supervising",
        "resident_supervision_probe_completed",
    }
    supervised_session_completed = state_status == "supervised_session_completed"
    observation_completed = state_status == "observation_completed"
    resident_runtime_candidate_supervised = supervised_session_completed and host_mode == "resident"
    status = state_status if state_exists and state_status else "missing"
    updated_at = str(state_payload.get("updated_at") or "")
    state_age_seconds = _age_seconds(updated_at)
    if not state_exists:
        freshness_status = "missing"
    elif state_age_seconds is None:
        freshness_status = "unknown"
    elif state_age_seconds <= SUPERVISOR_READBACK_FRESH_SECONDS:
        freshness_status = "fresh"
    else:
        freshness_status = "stale"
    state_stale = freshness_status == "stale"
    fresh_readback = freshness_status == "fresh"
    resident_supervised_runtime = (
        state_status == "resident_supervising"
        and host_mode == "resident"
        and supervisor_pid > 0
        and supervisor_process_alive
        and bool(state_payload.get("resident_supervised_runtime"))
        and observed_state == "resident_running"
        and observed_pid_matches_host_process
        and observed_process_alive
        and fresh_readback
    )
    if resident_supervised_runtime:
        blocked_reason = ""
    elif state_status == "resident_supervising" and not supervisor_process_alive:
        blocked_reason = "resident_host_supervisor_process_missing"
    elif state_status == "resident_supervising" and not observed_process_alive:
        blocked_reason = "resident_host_process_not_observed"
    elif resident_runtime_candidate_supervised:
        blocked_reason = "resident_runtime_candidate_not_persistent"
    elif supervised_session_completed:
        blocked_reason = "resident_supervision_not_persistent"
    elif bounded_supervisor_observed:
        blocked_reason = "resident_supervision_bounded_not_resident"
    elif state_exists:
        blocked_reason = "resident_supervision_observation_failed"
    else:
        blocked_reason = "resident_host_supervisor_state_missing"
    return {
        "status": status,
        "readback_ready": True,
        "runtime_state_path": "data/runtime/lens-host-supervisor/status.json",
        "state_exists": state_exists,
        "state_status": state_status,
        "mode": mode,
        "host_mode": host_mode,
        "supervisor_pid": supervisor_pid,
        "supervisor_process_alive": supervisor_process_alive,
        "supervisor_process_alive_check": supervisor_process_alive_check,
        "observed_pid": observed_pid,
        "observed_state": observed_state,
        "observed_process_alive": observed_process_alive,
        "observed_process_alive_check": observed_process_alive_check,
        "observed_pid_matches_host_process": observed_pid_matches_host_process,
        "updated_at": updated_at,
        "state_age_seconds": state_age_seconds,
        "freshness_window_seconds": SUPERVISOR_READBACK_FRESH_SECONDS,
        "freshness_status": freshness_status,
        "state_stale": state_stale,
        "fresh_readback": fresh_readback,
        "bounded_supervisor_observed": bounded_supervisor_observed,
        "observation_completed": observation_completed,
        "supervised_session_completed": supervised_session_completed,
        "resident_runtime_candidate_supervised": resident_runtime_candidate_supervised,
        "fresh_bounded_supervisor_observed": bounded_supervisor_observed and fresh_readback,
        "fresh_supervised_session_completed": supervised_session_completed and fresh_readback,
        "fresh_resident_runtime_candidate_supervised": resident_runtime_candidate_supervised and fresh_readback,
        "restarted_process": bool(state_payload.get("restarted_process")),
        "managed_service": bool(state_payload.get("managed_service")),
        "resident_supervised_runtime": resident_supervised_runtime,
        "resident_claim_allowed": False,
        "process_supervision_authority": bool(state_payload.get("process_supervision_authority"))
        and resident_supervised_runtime,
        "process_restart_authority": bool(state_payload.get("process_restart_authority"))
        and resident_supervised_runtime,
        "service_control_authority": bool(state_payload.get("service_control_authority"))
        and resident_supervised_runtime,
        "blocked_reason": blocked_reason,
        "governance": {
            "read_only_contract": True,
            "execution_authority": False,
            "approval_decision_authority": False,
            "memory_write": False,
            "local_process_launch_authority": False,
            "process_supervision_authority": False,
            "process_restart_authority": False,
            "service_install_authority": False,
            "service_control_authority": False,
            "receipt_write_authority": False,
            "resident_claim_authority": False,
            "mutation_authority_granted": False,
        },
    }


def _latest_active_host_supervision_authority_grant() -> dict[str, Any]:
    root = data_dir() / "lens" / "host_supervision_authority_grants"
    try:
        paths = list(root.glob("*.json")) if root.exists() else []
    except OSError:
        return {}

    now = time.time()
    items: list[dict[str, Any]] = []
    for path in paths:
        item = _json_dict_from_path(path)
        if not item:
            continue
        lease = _as_dict(item.get("lease"))
        authority_boundary = _as_dict(item.get("authority_boundary"))
        if (
            str(item.get("kind") or "").strip() != "lens.host.supervision_authority.grant.receipt"
            or str(item.get("status") or "").strip() != "authority_granted"
            or not bool(lease.get("active"))
            or not bool(authority_boundary.get("authority_granted"))
            or _record_ts(lease.get("expires_ts") or item.get("expires_ts")) <= now
        ):
            continue
        items.append(item)
    items.sort(key=lambda item: (_record_ts(item.get("created_ts")), str(item.get("receipt_id") or "")), reverse=True)
    return items[0] if items else {}


def _quote_command_arg(value: str) -> str:
    if any(character.isspace() for character in value) or '"' in value:
        return '"' + value.replace('"', '\\"') + '"'
    return value


def _join_command_line(executable: str, items: list[str]) -> str:
    parts: list[str] = []
    if executable.strip():
        parts.append(_quote_command_arg(executable))
    parts.extend(_quote_command_arg(item) for item in items)
    return " ".join(parts)


def _lens_host_service_plan(
    *,
    entrypoint_exists: bool,
    service_manager: str,
    service_manager_exists: bool,
    service_config_exists: bool,
    service_config_payload: dict[str, Any],
    service_config_source: str = "config/runtime/services/lens-host.json",
) -> dict[str, Any]:
    service_name = str(service_config_payload.get("service_name") or "Francis-LensHost")
    service_executable = str(service_config_payload.get("service_executable") or "")
    service_arguments = _as_str_list(service_config_payload.get("service_arguments"))
    working_directory = str(service_config_payload.get("working_dir") or "")
    start_type = str(service_config_payload.get("start_type") or "Manual")
    installable = bool(service_config_payload.get("installable"))
    install_authority = bool(service_config_payload.get("install_authority"))
    service_install_authority = bool(service_config_payload.get("service_install_authority"))
    service_control_authority = bool(service_config_payload.get("service_control_authority"))
    start_after_install = bool(service_config_payload.get("start_after_install"))
    use_wrapper = bool(service_config_payload.get("use_wrapper"))
    blocked_reason = str(
        service_config_payload.get("blocked_reason") or "lens_host_persistent_supervision_prerequisites_pending"
    )
    blocked_by = []
    if not service_config_exists:
        blocked_by.append("service_config_missing")
    if not service_manager_exists:
        blocked_by.append("service_manager_missing")
    if not entrypoint_exists:
        blocked_by.append("host_entrypoint_missing")
    if not service_executable.strip():
        blocked_by.append("service_executable_missing")
    if not installable:
        blocked_by.append("installable_false")
    if not install_authority:
        blocked_by.append("install_authority_false")
    if not service_install_authority:
        blocked_by.append("service_install_authority_false")
    if not service_control_authority:
        blocked_by.append("service_control_authority_false")
    ready = not blocked_by
    return {
        "kind": "service_install.plan_projection",
        "status": "ready" if ready else "blocked",
        "ready": ready,
        "source": service_config_source,
        "manager": service_manager,
        "manager_exists": service_manager_exists,
        "plan_mode": "Plan",
        "service_name": service_name,
        "service_executable": service_executable,
        "service_arguments": service_arguments,
        "planned_command": _join_command_line(service_executable, service_arguments),
        "working_directory": working_directory,
        "start_type": start_type,
        "use_wrapper": use_wrapper,
        "would_install": installable and install_authority and service_install_authority,
        "would_start": start_after_install,
        "wrapper_would_write": False,
        "blocked_by": blocked_by,
        "blocked_reason": blocked_reason,
        "governance": {
            "read_only_contract": True,
            "execution_authority": False,
            "approval_decision_authority": False,
            "memory_write": False,
            "local_process_launch_authority": False,
            "service_install_authority": False,
            "service_control_authority": False,
            "wrapper_write_authority": False,
            "mutation_authority_granted": False,
        },
    }


def _readiness_item(item_id: str, *, label: str, ready: bool, status: str, reason: str = "") -> dict[str, Any]:
    return {
        "id": item_id,
        "label": label,
        "ready": ready,
        "status": status,
        "reason": reason,
    }


def _required_before_enable_readiness_item(
    *,
    required_before_enable: list[str],
    missing_required_before_enable: list[str],
) -> dict[str, Any]:
    ready = not missing_required_before_enable
    return {
        **_readiness_item(
            "required_before_enable",
            label="Required Lens prerequisite surfaces",
            ready=ready,
            status="ready" if ready else "blocked",
            reason="" if ready else "persistent_supervision_required_prerequisites_missing",
        ),
        "required_before_enable": required_before_enable,
        "missing_required_before_enable": missing_required_before_enable,
    }


def _persistent_supervision_current_gap_readback(
    *,
    next_gap: str,
    missing_required_before_enable: list[str],
    first_missing_handoff: dict[str, Any],
) -> dict[str, Any]:
    raw_gap = str(next_gap or "").strip()
    if missing_required_before_enable:
        return {
            "current_truthful_gap": "persistent_supervision_required_prerequisites_missing",
            "current_truthful_gap_basis": "missing_required_before_enable",
            "current_first_missing_requirement": str(first_missing_handoff.get("id") or "").strip(),
            "current_first_missing_truthful_gap": str(
                first_missing_handoff.get("next_smallest_truthful_gap") or ""
            ).strip(),
            "raw_persistent_supervision_next_smallest_truthful_gap": raw_gap,
        }
    return {
        "current_truthful_gap": raw_gap,
        "current_truthful_gap_basis": "next_smallest_truthful_gap",
        "current_first_missing_requirement": "",
        "current_first_missing_truthful_gap": "",
        "raw_persistent_supervision_next_smallest_truthful_gap": raw_gap,
    }


def _lens_host_supervision_readiness(
    *,
    entrypoint_exists: bool,
    service_manager: str,
    service_manager_exists: bool,
    service_config_exists: bool,
    service_config_payload: dict[str, Any],
    process_readback: dict[str, Any],
) -> dict[str, Any]:
    active_authority_grant = _latest_active_host_supervision_authority_grant()
    grant_authorities = _as_dict(active_authority_grant.get("authorities"))
    authority_grant_active = bool(active_authority_grant)
    supervision_enabled = bool(service_config_payload.get("process_supervision_enabled"))
    persistent_supervision_enabled = bool(service_config_payload.get("persistent_supervision_enabled"))
    process_restart_authority = bool(
        service_config_payload.get("process_restart_authority") or grant_authorities.get("process_restart_authority")
    )
    process_supervision_authority = bool(grant_authorities.get("process_supervision_authority"))
    install_authority = bool(
        service_config_payload.get("install_authority")
        or service_config_payload.get("service_install_authority")
        or grant_authorities.get("service_install_authority")
    )
    service_control_authority = bool(
        service_config_payload.get("service_control_authority") or grant_authorities.get("service_control_authority")
    )
    receipt_write_authority = bool(
        service_config_payload.get("receipt_write_authority") or grant_authorities.get("receipt_write_authority")
    )
    resident_claim_authority = bool(
        service_config_payload.get("resident_claim_authority") or grant_authorities.get("resident_claim_authority")
    )
    foreground_readback_ready = bool(process_readback.get("readback_ready"))
    prerequisites = [
        _readiness_item(
            "host_entrypoint",
            label="Lens host entrypoint",
            ready=entrypoint_exists,
            status="ready" if entrypoint_exists else "missing",
            reason="" if entrypoint_exists else "scripts/lens-host.ps1 is missing",
        ),
        _readiness_item(
            "service_manager",
            label="Service manager script",
            ready=service_manager_exists,
            status="ready" if service_manager_exists else "missing",
            reason="" if service_manager_exists else f"{service_manager} is missing",
        ),
        _readiness_item(
            "service_config",
            label="Lens host service config",
            ready=service_config_exists,
            status="present_disabled" if service_config_exists else "missing",
            reason="" if service_config_exists else "config/runtime/services/lens-host.json is missing",
        ),
        _readiness_item(
            "foreground_process_readback",
            label="Foreground process readback",
            ready=foreground_readback_ready,
            status=str(process_readback.get("status") or "missing"),
            reason="" if foreground_readback_ready else "process readback is not available",
        ),
        _readiness_item(
            "process_supervision_enabled",
            label="Process supervision enabled",
            ready=supervision_enabled,
            status="ready" if supervision_enabled else "blocked",
            reason="" if supervision_enabled else "disabled_in_service_config",
        ),
        _readiness_item(
            "persistent_supervision_enabled",
            label="Persistent supervision enabled",
            ready=persistent_supervision_enabled,
            status="ready" if persistent_supervision_enabled else "blocked",
            reason="" if persistent_supervision_enabled else "persistent_supervision_disabled",
        ),
        _readiness_item(
            "process_restart_authority",
            label="Process restart authority",
            ready=process_restart_authority,
            status="ready" if process_restart_authority else "blocked",
            reason="" if process_restart_authority else "process_restart_authority_false",
        ),
        _readiness_item(
            "service_install_authority",
            label="Service install authority",
            ready=install_authority,
            status="ready" if install_authority else "blocked",
            reason="" if install_authority else "install_authority_false",
        ),
        _readiness_item(
            "service_control_authority",
            label="Service control authority",
            ready=service_control_authority,
            status="ready" if service_control_authority else "blocked",
            reason="" if service_control_authority else "service_control_authority_false",
        ),
        _readiness_item(
            "receipt_write_authority",
            label="Resident supervision receipt authority",
            ready=receipt_write_authority,
            status="ready" if receipt_write_authority else "blocked",
            reason="" if receipt_write_authority else "receipt_write_authority_false",
        ),
        _readiness_item(
            "resident_claim_authority",
            label="Resident claim authority",
            ready=resident_claim_authority,
            status="ready" if resident_claim_authority else "blocked",
            reason="" if resident_claim_authority else "resident_claim_authority_false",
        ),
    ]
    blocked_by = [str(item["id"]) for item in prerequisites if not bool(item["ready"])]
    return {
        "status": "blocked" if blocked_by else "ready",
        "ready": not blocked_by,
        "mode": str(service_config_payload.get("supervision_mode") or "windows_service"),
        "service_manager": service_manager,
        "service_manager_exists": service_manager_exists,
        "process_supervision_enabled": supervision_enabled,
        "persistent_supervision_enabled": persistent_supervision_enabled,
        "process_supervision_authority": process_supervision_authority,
        "process_restart_authority": process_restart_authority,
        "service_install_authority": install_authority,
        "service_control_authority": service_control_authority,
        "receipt_write_authority": receipt_write_authority,
        "resident_claim_authority": resident_claim_authority,
        "authority_grant_active": authority_grant_active,
        "authority_grant_route": "/lens/host/supervision/authority",
        "authority_grants_route": "/lens/host/supervision/authority/grants",
        "authority_grant": active_authority_grant,
        "resident_claim_allowed": False,
        "next_allowed_transition": "foreground_status_session_only" if blocked_by else "operator_review_required",
        "blocked_by": blocked_by,
        "blocked_reason": str(
            service_config_payload.get("supervision_blocked_reason") or "resident_supervision_disabled"
        ),
        "prerequisites": prerequisites,
    }


def lens_host_supervision_gate(*, manifest: dict[str, Any] | None = None) -> dict[str, Any]:
    launch_manifest = manifest if isinstance(manifest, dict) else lens_host_launch_manifest()
    supervision = launch_manifest.get("supervision_readiness")
    supervision_readiness = supervision if isinstance(supervision, dict) else {}
    service_plan = launch_manifest.get("service_plan")
    service_plan = service_plan if isinstance(service_plan, dict) else {}
    service_readback = launch_manifest.get("service_readback")
    service_readback = service_readback if isinstance(service_readback, dict) else {}
    process_readback = launch_manifest.get("process_readback")
    process_readback = process_readback if isinstance(process_readback, dict) else {}
    supervisor_readback = launch_manifest.get("supervisor_readback")
    supervisor_readback = supervisor_readback if isinstance(supervisor_readback, dict) else {}
    required_bindings = launch_manifest.get("required_bindings")
    required_binding_items = (
        [item for item in required_bindings if isinstance(item, dict)] if isinstance(required_bindings, list) else []
    )
    prerequisites = supervision_readiness.get("prerequisites")
    prerequisite_items = (
        [item for item in prerequisites if isinstance(item, dict)] if isinstance(prerequisites, list) else []
    )
    service_plan_blockers = _as_str_list(service_plan.get("blocked_by"))
    supervision_blockers = _as_str_list(supervision_readiness.get("blocked_by"))
    supervision_blocker_reasons = [
        str(item.get("reason")) for item in prerequisite_items if str(item.get("reason") or "").strip()
    ]
    manifest_blockers = _as_str_list(launch_manifest.get("blockers"))
    blocked_by = sorted(
        {
            *service_plan_blockers,
            *supervision_blockers,
            *supervision_blocker_reasons,
            *manifest_blockers,
        }
    )
    supervisor_freshness_status = str(supervisor_readback.get("freshness_status") or "").strip()
    if supervisor_freshness_status == "stale":
        blocked_by = sorted({*blocked_by, "host_supervisor_readback_stale"})
    elif supervisor_freshness_status == "unknown":
        blocked_by = sorted({*blocked_by, "host_supervisor_readback_freshness_unknown"})
    supervision_ready = bool(supervision_readiness.get("ready"))
    process_alive = bool(process_readback.get("process_alive"))
    resident_supervised_runtime = bool(supervisor_readback.get("resident_supervised_runtime")) and process_alive
    host_process_blocker = (
        ""
        if resident_supervised_runtime
        else "resident_host_process_not_supervised"
        if process_alive
        else "resident_host_process_missing"
    )
    if host_process_blocker:
        blocked_by = sorted({*blocked_by, host_process_blocker})
    service_managed = bool(service_readback.get("installed")) and bool(
        supervision_readiness.get("service_control_authority")
    )
    resident_claim_allowed = (
        supervision_ready
        and process_alive
        and service_managed
        and bool(supervision_readiness.get("resident_claim_allowed"))
    )
    return {
        "ok": True,
        "kind": "lens.host.supervision_enablement_gate",
        "status": "ready_for_operator_review" if resident_claim_allowed else "blocked",
        "route": "/lens/host/supervision",
        "host_route": "/lens/host",
        "manifest_route": "/lens/host/manifest",
        "preflight_route": "/lens/preflight",
        "ready": resident_claim_allowed,
        "supervision_ready": supervision_ready,
        "resident_claim_allowed": resident_claim_allowed,
        "resident_host_process": process_alive,
        "foreground_process_observed": process_alive,
        "resident_host_process_state": (
            "resident_supervised"
            if resident_supervised_runtime
            else "foreground_observed_not_supervised"
            if process_alive
            else "missing"
        ),
        "resident_host_process_blocker": host_process_blocker,
        "supervisor_readback_ready": bool(supervisor_readback.get("readback_ready")),
        "supervisor_freshness_status": supervisor_freshness_status,
        "supervisor_state_age_seconds": supervisor_readback.get("state_age_seconds"),
        "supervisor_state_stale": bool(supervisor_readback.get("state_stale")),
        "fresh_supervisor_readback": bool(supervisor_readback.get("fresh_readback")),
        "bounded_supervisor_observed": bool(supervisor_readback.get("bounded_supervisor_observed")),
        "supervised_session_completed": bool(supervisor_readback.get("supervised_session_completed")),
        "resident_runtime_candidate_supervised": bool(supervisor_readback.get("resident_runtime_candidate_supervised")),
        "fresh_bounded_supervisor_observed": bool(supervisor_readback.get("fresh_bounded_supervisor_observed")),
        "fresh_supervised_session_completed": bool(supervisor_readback.get("fresh_supervised_session_completed")),
        "fresh_resident_runtime_candidate_supervised": bool(
            supervisor_readback.get("fresh_resident_runtime_candidate_supervised")
        ),
        "resident_supervised_runtime": resident_supervised_runtime,
        "resident_host_supervised": resident_supervised_runtime,
        "service_installed": bool(service_readback.get("installed")),
        "service_managed": service_managed,
        "process_supervision_enabled": bool(supervision_readiness.get("process_supervision_enabled")),
        "persistent_supervision_enabled": bool(supervision_readiness.get("persistent_supervision_enabled")),
        "process_restart_authority": bool(supervision_readiness.get("process_restart_authority")),
        "process_restart_supported": bool(process_readback.get("restart_supported")),
        "service_plan_ready": bool(service_plan.get("ready")),
        "would_install_service": bool(service_plan.get("would_install")),
        "would_start_service": bool(service_plan.get("would_start")),
        "would_supervise_process": False,
        "would_restart_process": False,
        "next_allowed_transition": str(
            supervision_readiness.get("next_allowed_transition") or "foreground_status_session_only"
        ),
        "blockers": blocked_by,
        "prerequisites": prerequisite_items,
        "required_bindings": required_binding_items,
        "process_readback": process_readback,
        "supervisor_readback": supervisor_readback,
        "service_readback": service_readback,
        "service_plan": service_plan,
        "supervision_readiness": supervision_readiness,
        "governance": {
            "read_only_contract": True,
            "execution_authority": False,
            "approval_decision_authority": False,
            "memory_write": False,
            "local_process_launch_authority": False,
            "process_supervision_authority": False,
            "process_restart_authority": False,
            "service_install_authority": False,
            "service_control_authority": False,
            "receipt_write_authority": False,
            "denial_receipt_write_authority": False,
            "resident_claim_authority": False,
            "overlay_control_authority": False,
            "summon_authority": False,
            "hotkey_registration_authority": False,
            "tray_registration_authority": False,
            "mutation_authority_granted": False,
        },
        "message": (
            "Resident Lens supervision enablement is read-only and blocked until process supervision, "
            "restart, service install, service control, receipt write, and resident claim authority are explicitly granted."
        ),
    }


def lens_host_persistent_supervision_plan(*, manifest: dict[str, Any] | None = None) -> dict[str, Any]:
    launch_manifest = manifest if isinstance(manifest, dict) else lens_host_launch_manifest()
    required_before_enable = _as_str_list(launch_manifest.get("required_before_enable"))
    missing_required_before_enable = _lens_host_missing_required_before_enable(
        required_before_enable,
        launch_manifest=launch_manifest,
    )
    service_install = launch_manifest.get("service_install")
    service_install = service_install if isinstance(service_install, dict) else {}
    declared_entrypoint = launch_manifest.get("declared_entrypoint")
    declared_entrypoint = declared_entrypoint if isinstance(declared_entrypoint, dict) else {}
    supervision_readiness = launch_manifest.get("supervision_readiness")
    supervision_readiness = supervision_readiness if isinstance(supervision_readiness, dict) else {}
    service_plan = launch_manifest.get("service_plan")
    service_plan = service_plan if isinstance(service_plan, dict) else {}
    process_readback = launch_manifest.get("process_readback")
    process_readback = process_readback if isinstance(process_readback, dict) else {}
    activation_execution_readback = _as_dict(launch_manifest.get("activation_execution_readback"))
    service_readback = launch_manifest.get("service_readback")
    service_readback = service_readback if isinstance(service_readback, dict) else {}

    service_config_ready = bool(service_install.get("config_exists"))
    host_entrypoint_ready = bool(declared_entrypoint.get("exists"))
    service_manager_ready = bool(service_install.get("manager_exists"))
    process_supervision_enabled = bool(supervision_readiness.get("process_supervision_enabled"))
    persistent_supervision_enabled = bool(supervision_readiness.get("persistent_supervision_enabled"))
    process_restart_authority = bool(supervision_readiness.get("process_restart_authority"))
    service_install_authority = bool(supervision_readiness.get("service_install_authority"))
    service_control_authority = bool(supervision_readiness.get("service_control_authority"))
    receipt_write_authority = bool(supervision_readiness.get("receipt_write_authority"))
    resident_claim_authority = bool(supervision_readiness.get("resident_claim_authority"))

    enablement_dependency_readback = _lens_host_enablement_dependency_readback(
        required_before_enable,
        launch_manifest=launch_manifest,
    )
    first_missing_handoff = _lens_host_first_missing_prerequisite_handoff(enablement_dependency_readback)
    requirements = [
        _readiness_item(
            "service_config",
            label="Lens host service config",
            ready=service_config_ready,
            status="ready" if service_config_ready else "missing",
            reason="" if service_config_ready else "service_config_missing",
        ),
        _readiness_item(
            "host_entrypoint",
            label="Lens host entrypoint",
            ready=host_entrypoint_ready,
            status="ready" if host_entrypoint_ready else "missing",
            reason="" if host_entrypoint_ready else "host_entrypoint_missing",
        ),
        _readiness_item(
            "service_manager",
            label="Service manager script",
            ready=service_manager_ready,
            status="ready" if service_manager_ready else "missing",
            reason="" if service_manager_ready else "service_manager_missing",
        ),
        _readiness_item(
            "process_supervision_enabled",
            label="Process supervision enabled",
            ready=process_supervision_enabled,
            status="ready" if process_supervision_enabled else "blocked",
            reason="" if process_supervision_enabled else "process_supervision_disabled",
        ),
        _readiness_item(
            "persistent_supervision_enabled",
            label="Persistent supervision enabled",
            ready=persistent_supervision_enabled,
            status="ready" if persistent_supervision_enabled else "blocked",
            reason="" if persistent_supervision_enabled else "persistent_supervision_disabled",
        ),
        _readiness_item(
            "process_restart_authority",
            label="Process restart authority",
            ready=process_restart_authority,
            status="ready" if process_restart_authority else "blocked",
            reason="" if process_restart_authority else "process_restart_authority_not_granted",
        ),
        _readiness_item(
            "service_install_authority",
            label="Service install authority",
            ready=service_install_authority,
            status="ready" if service_install_authority else "blocked",
            reason="" if service_install_authority else "service_install_authority_not_granted",
        ),
        _readiness_item(
            "service_control_authority",
            label="Service control authority",
            ready=service_control_authority,
            status="ready" if service_control_authority else "blocked",
            reason="" if service_control_authority else "service_control_authority_not_granted",
        ),
        _readiness_item(
            "receipt_write_authority",
            label="Persistent supervision receipt authority",
            ready=receipt_write_authority,
            status="ready" if receipt_write_authority else "blocked",
            reason="" if receipt_write_authority else "receipt_write_authority_not_granted",
        ),
        _readiness_item(
            "resident_claim_authority",
            label="Resident claim authority",
            ready=resident_claim_authority,
            status="ready" if resident_claim_authority else "blocked",
            reason="" if resident_claim_authority else "resident_claim_authority_not_granted",
        ),
    ]
    blocked_requirements = [str(item["id"]) for item in requirements if not bool(item.get("ready"))]
    authority_requirement_ids = {
        "process_restart_authority",
        "service_install_authority",
        "service_control_authority",
        "receipt_write_authority",
        "resident_claim_authority",
    }
    authority_blocked = any(item in authority_requirement_ids for item in blocked_requirements)
    enablement_toggle_blocked = any(
        item in {"process_supervision_enabled", "persistent_supervision_enabled"} for item in blocked_requirements
    )
    if not authority_blocked and not enablement_toggle_blocked:
        requirements.append(
            _required_before_enable_readiness_item(
                required_before_enable=required_before_enable,
                missing_required_before_enable=missing_required_before_enable,
            )
        )
        blocked_requirements = [str(item["id"]) for item in requirements if not bool(item.get("ready"))]
    blockers = sorted({str(item.get("reason")) for item in requirements if str(item.get("reason") or "").strip()})
    ready = not blocked_requirements
    next_gap = "persistent_supervision_execution_boundary" if ready else "persistent_supervision_authority_not_granted"
    if "required_before_enable" in blocked_requirements:
        next_gap = "persistent_supervision_required_prerequisites_missing"
    elif not ready and not authority_blocked:
        next_gap = "persistent_supervision_enablement_disabled"
    current_gap = _persistent_supervision_current_gap_readback(
        next_gap=next_gap,
        missing_required_before_enable=missing_required_before_enable,
        first_missing_handoff=first_missing_handoff,
    )
    return {
        "ok": True,
        "kind": "lens.host.persistent_supervision_plan",
        "status": "ready_for_operator_review" if ready else "blocked",
        "route": "/lens/host/persistent-supervision",
        "host_route": "/lens/host",
        "manifest_route": "/lens/host/manifest",
        "supervision_route": "/lens/host/supervision",
        "authority_route": "/lens/host/supervision/authority",
        "service_name": str(service_install.get("service_name") or ""),
        "service_manager": str(service_install.get("manager") or "scripts/service-install.ps1"),
        "service_manager_present": service_manager_ready,
        "service_config_present": service_config_ready,
        "host_entrypoint_present": host_entrypoint_ready,
        "plan_available": True,
        "ready": ready,
        "persistent_supervision_ready": ready,
        "resident_claim_allowed": False,
        "requirements": requirements,
        "requirements_total": len(requirements),
        "requirements_ready_total": len(requirements) - len(blocked_requirements),
        "requirements_blocked_total": len(blocked_requirements),
        "blocked_requirements": blocked_requirements,
        "required_before_enable": required_before_enable,
        "missing_required_before_enable": missing_required_before_enable,
        "required_before_enable_ready": not missing_required_before_enable,
        "enablement_dependency_readback": enablement_dependency_readback,
        "first_missing_required_before_enable": str(first_missing_handoff.get("id") or ""),
        "first_missing_requirement_handoff": first_missing_handoff,
        "blockers": blockers,
        "plan": {
            "mode": "persistent_supervised_resident_host",
            "service_name": str(service_install.get("service_name") or ""),
            "would_install_service": False,
            "would_update_service": False,
            "would_start_service": False,
            "would_supervise_process": False,
            "would_restart_process": False,
            "would_write_receipt": False,
            "would_write_memory": False,
            "would_claim_resident": False,
        },
        "source_readbacks": {
            "manifest": {
                "route": "/lens/host/manifest",
                "status": str(launch_manifest.get("status") or ""),
            },
            "service_plan": service_plan,
            "process_readback": process_readback,
            "activation_execution_readback": activation_execution_readback,
            "service_readback": service_readback,
            "supervision_readiness": supervision_readiness,
        },
        "next_smallest_truthful_gap": next_gap,
        **current_gap,
        "governance": {
            "read_only_contract": True,
            "diagnostic_only": True,
            "execution_authority": False,
            "approval_decision_authority": False,
            "memory_write": False,
            "local_process_launch_authority": False,
            "process_supervision_authority": False,
            "process_restart_authority": False,
            "service_install_authority": False,
            "service_control_authority": False,
            "receipt_write_authority": False,
            "resident_claim_authority": False,
            "mutation_authority_granted": False,
        },
        "message": (
            "Persistent Lens host supervision is planned but blocked; this readback does not install, start, "
            "supervise, restart, write receipts, write memory, or claim a resident host."
        ),
    }


def lens_host_persistent_supervision_enablement_preflight(
    *,
    manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    launch_manifest = manifest if isinstance(manifest, dict) else lens_host_launch_manifest()
    required_before_enable = _as_str_list(launch_manifest.get("required_before_enable"))
    missing_required_before_enable = _lens_host_missing_required_before_enable(
        required_before_enable,
        launch_manifest=launch_manifest,
    )
    persistent_plan = lens_host_persistent_supervision_plan(manifest=launch_manifest)
    source_readbacks = _as_dict(persistent_plan.get("source_readbacks"))
    supervision_readiness = _as_dict(source_readbacks.get("supervision_readiness"))
    active_grant = _as_dict(supervision_readiness.get("authority_grant"))
    service_plan = _as_dict(source_readbacks.get("service_plan"))
    process_supervision_enabled = bool(supervision_readiness.get("process_supervision_enabled"))
    persistent_supervision_enabled = bool(supervision_readiness.get("persistent_supervision_enabled"))
    authority_grant_active = bool(supervision_readiness.get("authority_grant_active"))
    receipt_id = str(active_grant.get("receipt_id") or "")
    enablement_dependency_readback = _lens_host_enablement_dependency_readback(
        required_before_enable,
        launch_manifest=launch_manifest,
    )
    first_missing_handoff = _lens_host_first_missing_prerequisite_handoff(enablement_dependency_readback)
    requirements = [
        _readiness_item(
            "persistent_supervision_plan",
            label="Persistent supervision plan",
            ready=bool(persistent_plan.get("plan_available")),
            status="ready" if bool(persistent_plan.get("plan_available")) else "missing",
            reason="" if bool(persistent_plan.get("plan_available")) else "persistent_supervision_plan_missing",
        ),
        _readiness_item(
            "active_host_supervision_authority_grant",
            label="Active host supervision authority grant",
            ready=authority_grant_active,
            status="ready" if authority_grant_active else "blocked",
            reason="" if authority_grant_active else "host_supervision_authority_grant_not_active",
        ),
        _readiness_item(
            "process_supervision_enabled",
            label="Process supervision enabled",
            ready=process_supervision_enabled,
            status="ready" if process_supervision_enabled else "blocked",
            reason="" if process_supervision_enabled else "process_supervision_disabled",
        ),
        _readiness_item(
            "persistent_supervision_enabled",
            label="Persistent supervision enabled",
            ready=persistent_supervision_enabled,
            status="ready" if persistent_supervision_enabled else "blocked",
            reason="" if persistent_supervision_enabled else "persistent_supervision_disabled",
        ),
    ]
    blocked_requirements = [str(item["id"]) for item in requirements if not bool(item.get("ready"))]
    enablement_toggle_blocked = any(
        item in {"process_supervision_enabled", "persistent_supervision_enabled"} for item in blocked_requirements
    )
    if authority_grant_active and not enablement_toggle_blocked:
        requirements.append(
            _required_before_enable_readiness_item(
                required_before_enable=required_before_enable,
                missing_required_before_enable=missing_required_before_enable,
            )
        )
        blocked_requirements = [str(item["id"]) for item in requirements if not bool(item.get("ready"))]
    blockers = sorted({str(item.get("reason")) for item in requirements if str(item.get("reason") or "").strip()})
    enablement_ready = not blocked_requirements
    if enablement_ready:
        next_gap = "persistent_supervision_execution_boundary"
    elif "required_before_enable" in blocked_requirements:
        next_gap = "persistent_supervision_required_prerequisites_missing"
    elif authority_grant_active:
        next_gap = "persistent_supervision_enablement_disabled"
    else:
        next_gap = "persistent_supervision_authority_not_granted"
    current_gap = _persistent_supervision_current_gap_readback(
        next_gap=next_gap,
        missing_required_before_enable=missing_required_before_enable,
        first_missing_handoff=first_missing_handoff,
    )
    return {
        "ok": True,
        "kind": "lens.host.persistent_supervision_enablement.preflight",
        "status": "ready_for_operator_review" if enablement_ready else "blocked",
        "route": "/lens/host/persistent-supervision/enablement",
        "plan_route": "/lens/host/persistent-supervision",
        "host_route": "/lens/host",
        "manifest_route": "/lens/host/manifest",
        "authority_route": "/lens/host/supervision/authority",
        "authority_grants_route": "/lens/host/supervision/authority/grants",
        "service_name": str(persistent_plan.get("service_name") or ""),
        "preflight_ready": True,
        "ready": enablement_ready,
        "enablement_ready": enablement_ready,
        "persistent_supervision_ready": bool(persistent_plan.get("persistent_supervision_ready")),
        "resident_claim_allowed": False,
        "authority_grant_active": authority_grant_active,
        "active_grant_receipt_id": receipt_id,
        "process_supervision_enabled": process_supervision_enabled,
        "persistent_supervision_enabled": persistent_supervision_enabled,
        "required_before_enable": required_before_enable,
        "missing_required_before_enable": missing_required_before_enable,
        "required_before_enable_ready": not missing_required_before_enable,
        "enablement_dependency_readback": enablement_dependency_readback,
        "first_missing_required_before_enable": str(first_missing_handoff.get("id") or ""),
        "first_missing_requirement_handoff": first_missing_handoff,
        "requirements": requirements,
        "requirements_total": len(requirements),
        "requirements_ready_total": len(requirements) - len(blocked_requirements),
        "requirements_blocked_total": len(blocked_requirements),
        "blocked_requirements": blocked_requirements,
        "blockers": blockers,
        "plan": {
            "mode": "persistent_supervision_enablement_preflight",
            "service_name": str(persistent_plan.get("service_name") or ""),
            "would_update_service_config": False,
            "would_enable_process_supervision": False,
            "would_enable_persistent_supervision": False,
            "would_install_service": False,
            "would_update_service": False,
            "would_start_service": False,
            "would_supervise_process": False,
            "would_restart_process": False,
            "would_write_receipt": False,
            "would_write_memory": False,
            "would_claim_resident": False,
        },
        "source_readbacks": {
            "persistent_supervision_plan": persistent_plan,
            "service_plan": service_plan,
            "supervision_readiness": supervision_readiness,
        },
        "next_smallest_truthful_gap": next_gap,
        **current_gap,
        "governance": {
            "read_only_contract": True,
            "preflight_only": True,
            "execution_authority": False,
            "approval_decision_authority": False,
            "memory_write": False,
            "local_process_launch_authority": False,
            "process_supervision_authority": False,
            "process_restart_authority": False,
            "service_install_authority": False,
            "service_control_authority": False,
            "receipt_write_authority": False,
            "resident_claim_authority": False,
            "service_config_write_authority": False,
            "mutation_authority_granted": False,
        },
        "message": (
            "Persistent Lens host supervision enablement is a read-only preflight; this route does not "
            "update config, install, start, supervise, restart, write receipts, write memory, or claim a resident host."
        ),
    }


def lens_host_supervision_authority_preflight(*, manifest: dict[str, Any] | None = None) -> dict[str, Any]:
    launch_manifest = manifest if isinstance(manifest, dict) else lens_host_launch_manifest()
    supervision_gate = lens_host_supervision_gate(manifest=launch_manifest)
    supervision_readiness = launch_manifest.get("supervision_readiness")
    supervision_readiness = supervision_readiness if isinstance(supervision_readiness, dict) else {}
    service_plan = launch_manifest.get("service_plan")
    service_plan = service_plan if isinstance(service_plan, dict) else {}
    process_readback = launch_manifest.get("process_readback")
    process_readback = process_readback if isinstance(process_readback, dict) else {}
    service_readback = launch_manifest.get("service_readback")
    service_readback = service_readback if isinstance(service_readback, dict) else {}
    prerequisites = supervision_readiness.get("prerequisites")
    prerequisite_items = (
        [item for item in prerequisites if isinstance(item, dict)] if isinstance(prerequisites, list) else []
    )
    authority_requirements = [
        _readiness_item(
            "process_supervision_authority",
            label="Process supervision authority",
            ready=bool(supervision_readiness.get("process_supervision_authority")),
            status="ready" if bool(supervision_readiness.get("process_supervision_authority")) else "blocked",
            reason=""
            if bool(supervision_readiness.get("process_supervision_authority"))
            else "process_supervision_authority_not_granted",
        ),
        _readiness_item(
            "process_restart_authority",
            label="Process restart authority",
            ready=bool(supervision_readiness.get("process_restart_authority")),
            status="ready" if bool(supervision_readiness.get("process_restart_authority")) else "blocked",
            reason=""
            if bool(supervision_readiness.get("process_restart_authority"))
            else "process_restart_authority_not_granted",
        ),
        _readiness_item(
            "service_install_authority",
            label="Service install authority",
            ready=bool(supervision_readiness.get("service_install_authority")),
            status="ready" if bool(supervision_readiness.get("service_install_authority")) else "blocked",
            reason=""
            if bool(supervision_readiness.get("service_install_authority"))
            else "service_install_authority_not_granted",
        ),
        _readiness_item(
            "service_control_authority",
            label="Service control authority",
            ready=bool(supervision_readiness.get("service_control_authority")),
            status="ready" if bool(supervision_readiness.get("service_control_authority")) else "blocked",
            reason=""
            if bool(supervision_readiness.get("service_control_authority"))
            else "service_control_authority_not_granted",
        ),
        _readiness_item(
            "resident_claim_authority",
            label="Resident claim authority",
            ready=bool(supervision_readiness.get("resident_claim_authority")),
            status="ready" if bool(supervision_readiness.get("resident_claim_authority")) else "blocked",
            reason=""
            if bool(supervision_readiness.get("resident_claim_authority"))
            else "resident_claim_authority_not_granted",
        ),
        _readiness_item(
            "receipt_write_authority",
            label="Resident supervision receipt authority",
            ready=bool(supervision_readiness.get("receipt_write_authority")),
            status="ready" if bool(supervision_readiness.get("receipt_write_authority")) else "blocked",
            reason=""
            if bool(supervision_readiness.get("receipt_write_authority"))
            else "receipt_write_authority_not_granted",
        ),
    ]
    requirements = [
        *prerequisite_items,
        _readiness_item(
            "service_plan_ready",
            label="Service plan readiness",
            ready=bool(service_plan.get("ready")),
            status=str(service_plan.get("status") or "missing"),
            reason=str(service_plan.get("blocked_reason") or ""),
        ),
        *authority_requirements,
    ]
    blocked_requirements = [str(item["id"]) for item in requirements if not bool(item.get("ready"))]
    blocker_reasons = [str(item.get("reason")) for item in requirements if str(item.get("reason") or "").strip()]
    blockers = sorted(
        {
            *_as_str_list(supervision_gate.get("blockers")),
            *_as_str_list(service_plan.get("blocked_by")),
            *blocker_reasons,
            "resident_host_supervision_authority_not_granted",
        }
    )
    return {
        "ok": True,
        "kind": "lens.host.supervision_authority.preflight",
        "status": "blocked",
        "route": "/lens/host/supervision/authority",
        "host_route": "/lens/host",
        "supervision_route": "/lens/host/supervision",
        "manifest_route": "/lens/host/manifest",
        "ready": False,
        "preflight_ready": True,
        "authority_ready": False,
        "supervision_ready": bool(supervision_readiness.get("ready")),
        "resident_claim_allowed": False,
        "resident_host_process": bool(process_readback.get("process_alive")),
        "resident_host_supervised": False,
        "service_installed": bool(service_readback.get("installed")),
        "service_managed": False,
        "service_plan_ready": bool(service_plan.get("ready")),
        "would_supervise_process": False,
        "would_restart_process": False,
        "would_install_service": False,
        "would_start_service": False,
        "requirements": requirements,
        "requirements_total": len(requirements),
        "requirements_ready_total": len(requirements) - len(blocked_requirements),
        "requirements_blocked_total": len(blocked_requirements),
        "blocked_requirements": blocked_requirements,
        "blockers": blockers,
        "source_readbacks": {
            "manifest": {
                "route": "/lens/host/manifest",
                "status": str(launch_manifest.get("status") or ""),
            },
            "supervision_gate": {
                "route": "/lens/host/supervision",
                "status": str(supervision_gate.get("status") or ""),
                "ready": bool(supervision_gate.get("ready")),
            },
            "service_plan": service_plan,
            "process_readback": process_readback,
            "service_readback": service_readback,
            "supervision_readiness": supervision_readiness,
        },
        "governance": {
            "read_only_contract": True,
            "preflight_only": True,
            "execution_authority": False,
            "approval_decision_authority": False,
            "memory_write": False,
            "local_process_launch_authority": False,
            "process_supervision_authority": False,
            "process_restart_authority": False,
            "service_install_authority": False,
            "service_control_authority": False,
            "resident_claim_authority": False,
            "overlay_control_authority": False,
            "summon_authority": False,
            "hotkey_registration_authority": False,
            "tray_registration_authority": False,
            "receipt_write_authority": False,
            "mutation_authority_granted": False,
        },
        "next_step": "implement_resident_host_supervision_authority_denial_boundary",
    }


def lens_host_launch_manifest() -> dict[str, Any]:
    entrypoint = "scripts/lens-host.ps1"
    service_config_path = _lens_host_service_config_path()
    service_config_source = _lens_host_service_config_source(service_config_path)
    entrypoint_exists = _runtime_file_exists(entrypoint)
    service_config_payload = _json_dict_from_path(service_config_path)
    required_before_enable = _lens_host_required_before_enable(service_config_payload)
    service_config_exists = bool(service_config_payload)
    service_manager = str(service_config_payload.get("manager") or "scripts/service-install.ps1")
    service_manager_exists = _runtime_file_exists(service_manager)
    service_readback = _lens_host_service_readback(service_config_payload)
    activation_execution_readback = _lens_host_activation_execution_readback()
    service_plan = _lens_host_service_plan(
        entrypoint_exists=entrypoint_exists,
        service_manager=service_manager,
        service_manager_exists=service_manager_exists,
        service_config_exists=service_config_exists,
        service_config_payload=service_config_payload,
        service_config_source=service_config_source,
    )
    process_readback = _lens_host_process_readback()
    tray_runtime_readback = _lens_tray_runtime_readback()
    hotkey_runtime_readback = _lens_hotkey_runtime_readback()
    overlay_runtime_readback = _lens_overlay_runtime_readback()
    summon_runtime_readback = _lens_summon_runtime_readback()
    supervisor_readback = _lens_host_supervisor_readback()
    supervision_execution_readback = _lens_host_supervision_execution_readback()
    supervision_readiness = _lens_host_supervision_readiness(
        entrypoint_exists=entrypoint_exists,
        service_manager=service_manager,
        service_manager_exists=service_manager_exists,
        service_config_exists=service_config_exists,
        service_config_payload=service_config_payload,
        process_readback=process_readback,
    )
    foreground_supported = bool(service_config_payload.get("foreground_session_enabled"))
    runtime_blocker = str(
        service_config_payload.get("blocked_reason") or "lens_host_persistent_supervision_prerequisites_pending"
    )
    if not entrypoint_exists:
        runtime_blocker = "lens_host_runtime_not_implemented"
    surface_dependency_blockers = []
    if not bool(tray_runtime_readback.get("ready")):
        surface_dependency_blockers.append("tray_host_missing")
    if not bool(hotkey_runtime_readback.get("ready")):
        surface_dependency_blockers.append("global_hotkey_binding_missing")
    if not bool(overlay_runtime_readback.get("ready")):
        surface_dependency_blockers.append("overlay_window_missing")
    if not bool(summon_runtime_readback.get("ready")):
        surface_dependency_blockers.append("summon_binding_missing")
    blockers = [runtime_blocker, *surface_dependency_blockers]
    if not entrypoint_exists:
        blockers.insert(0, "lens_host_entrypoint_missing")
    if not service_config_exists:
        insert_at = 1 if not entrypoint_exists else 0
        blockers.insert(insert_at, "lens_host_service_config_missing")
    process_readback_blockers = _select_blockers(
        [str(process_readback.get("blocked_reason") or "")],
        "resident_host_process_missing",
        "resident_host_not_supervised",
    )
    service_plan_blockers = _as_str_list(service_plan.get("blocked_by"))
    supervision_blockers = _as_str_list(supervision_readiness.get("blocked_by"))
    authority_candidates = sorted({*service_plan_blockers, *supervision_blockers})
    blocker_groups = {
        "runtime": _select_blockers(
            blockers,
            "lens_host_runtime_not_implemented",
            "lens_host_persistent_supervision_prerequisites_pending",
            "lens_host_entrypoint_missing",
            "lens_host_service_config_missing",
        ),
        "process_readback": process_readback_blockers,
        "service_plan": service_plan_blockers,
        "supervision": supervision_blockers,
        "surface_dependencies": _select_blockers(
            surface_dependency_blockers,
            "tray_host_missing",
            "global_hotkey_binding_missing",
            "overlay_window_missing",
            "summon_binding_missing",
        ),
        "authority": _select_blockers(
            authority_candidates,
            "install_authority_false",
            "service_install_authority_false",
            "service_control_authority_false",
            "process_restart_authority",
            "service_install_authority",
            "service_control_authority",
            "receipt_write_authority",
            "resident_claim_authority",
        ),
    }

    return {
        "ok": True,
        "kind": "lens.host.launch_manifest",
        "status": "status_runner_present" if entrypoint_exists else "entrypoint_missing",
        "contract_status": "readback_ready",
        "enabled": False,
        "launch_authority": False,
        "auto_start": False,
        "default_action": "status_readback_only",
        "route": "/lens/host/manifest",
        "host_route": "/lens/host",
        "runtime_boundary_route": "/lens/host/runtime-boundary",
        "declared_entrypoint": {
            "path": entrypoint,
            "exists": entrypoint_exists,
            "purpose": "Status-only Lens host runner; future foreground tray, summon, and overlay lifecycle.",
        },
        "status_command": {
            "shell": "pwsh",
            "args": [
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                entrypoint,
                "-Mode",
                "Status",
            ],
            "working_directory": ".",
            "executable": entrypoint_exists,
        },
        "candidate_command": {
            "shell": "pwsh",
            "args": [
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                entrypoint,
                "-Mode",
                "Foreground",
            ],
            "working_directory": ".",
            "executable": entrypoint_exists and foreground_supported,
            "reason": (
                "Manual bounded foreground status session is available; resident service, tray, summon, and overlay remain blocked."
                if entrypoint_exists and foreground_supported
                else "Foreground Lens host runtime is not implemented."
            ),
        },
        "resident_command": {
            "shell": "pwsh",
            "args": [
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                entrypoint,
                "-Mode",
                "Resident",
            ],
            "working_directory": ".",
            "executable": entrypoint_exists,
            "authority_granted": False,
            "resident_claim_allowed": False,
            "reason": (
                "Manual resident runtime candidate is available; service supervision, tray, summon, "
                "overlay, and resident claim remain blocked."
                if entrypoint_exists
                else "Resident Lens host runtime candidate entrypoint is missing."
            ),
        },
        "service_install": {
            "manager": service_manager,
            "manager_exists": service_manager_exists,
            "config_path": service_config_source,
            "config_exists": service_config_exists,
            "config_status": "present_disabled" if service_config_exists else "missing",
            "service_name": str(service_config_payload.get("service_name") or ""),
            "installable": False,
            "blocked_reason": str(
                service_config_payload.get("blocked_reason") or "lens_host_persistent_supervision_prerequisites_pending"
            ),
            "install_authority": False,
            "start_after_install": False,
            "auto_start": False,
        },
        "required_before_enable": required_before_enable,
        "service_plan": service_plan,
        "foreground_session": {
            "supported": foreground_supported,
            "default_seconds": int(service_config_payload.get("foreground_session_default_seconds") or 0),
            "max_seconds": int(service_config_payload.get("foreground_session_max_seconds") or 0),
            "runtime_state_write": bool(service_config_payload.get("runtime_state_write")),
            "resident": False,
            "service_managed": False,
            "tray_presence": False,
            "global_hotkey": False,
            "overlay_window": False,
            "summon_anywhere": False,
        },
        "service_readback": service_readback,
        "process_readback": process_readback,
        "tray_runtime_readback": tray_runtime_readback,
        "hotkey_runtime_readback": hotkey_runtime_readback,
        "overlay_runtime_readback": overlay_runtime_readback,
        "summon_runtime_readback": summon_runtime_readback,
        "activation_execution_readback": activation_execution_readback,
        "supervision_execution_readback": supervision_execution_readback,
        "supervisor_readback": supervisor_readback,
        "supervision_readiness": supervision_readiness,
        "required_bindings": [
            {
                "id": "api_status",
                "route": "/lens/status",
                "status": "readback_ready",
            },
            {
                "id": "host_status_runner",
                "path": entrypoint,
                "status": "present" if entrypoint_exists else "missing",
            },
            {
                "id": "host_service_config",
                "path": service_config_source,
                "status": "present_disabled" if service_config_exists else "missing",
            },
            {
                "id": "host_service_readback",
                "service_name": service_readback["service_name"],
                "status": "readback_ready",
            },
            {
                "id": "host_service_plan",
                "path": service_config_source,
                "status": service_plan["status"],
            },
            {
                "id": "host_process_readback",
                "path": process_readback["runtime_state_path"],
                "status": "readback_ready",
            },
            {
                "id": "host_activation_execution_receipts",
                "route": activation_execution_readback["route"],
                "status": activation_execution_readback["status"],
                "receipt_count": activation_execution_readback["receipt_count"],
                "latest_receipt_id": activation_execution_readback["latest_receipt_id"],
            },
            {
                "id": "host_supervision_execution_receipts",
                "route": supervision_execution_readback["route"],
                "status": supervision_execution_readback["status"],
                "receipt_count": supervision_execution_readback["receipt_count"],
                "latest_receipt_id": supervision_execution_readback["latest_receipt_id"],
            },
            {
                "id": "host_supervisor_readback",
                "path": supervisor_readback["runtime_state_path"],
                "status": supervisor_readback["status"],
                "host_mode": supervisor_readback["host_mode"],
                "freshness_status": supervisor_readback["freshness_status"],
                "state_age_seconds": supervisor_readback["state_age_seconds"],
                "state_stale": supervisor_readback["state_stale"],
            },
            {
                "id": "host_readiness",
                "route": "/lens/host",
                "status": "readback_ready",
            },
            {
                "id": "tray_presence",
                "status": "observed" if bool(tray_runtime_readback.get("ready")) else "missing",
            },
            {
                "id": "global_hotkey",
                "status": "observed" if bool(hotkey_runtime_readback.get("ready")) else "missing",
            },
            {
                "id": "overlay_window",
                "status": "observed" if bool(overlay_runtime_readback.get("ready")) else "missing",
            },
            {
                "id": "summon_binding",
                "status": "observed" if bool(summon_runtime_readback.get("ready")) else "missing",
            },
        ],
        "blockers": blockers,
        "blocker_groups": blocker_groups,
        "governance": {
            "read_only_contract": True,
            "execution_authority": False,
            "approval_decision_authority": False,
            "memory_write": False,
            "overlay_control_authority": False,
            "summon_authority": False,
            "capture_authority": False,
            "new_sensing_authority": False,
            "local_process_launch_authority": False,
            "service_install_authority": False,
            "service_control_authority": False,
            "mutation_authority_granted": False,
        },
    }


def lens_host_runtime_boundary(*, manifest: dict[str, Any] | None = None) -> dict[str, Any]:
    launch_manifest = manifest if isinstance(manifest, dict) else lens_host_launch_manifest()
    declared_entrypoint = _as_dict(launch_manifest.get("declared_entrypoint"))
    status_command = _as_dict(launch_manifest.get("status_command"))
    candidate_command = _as_dict(launch_manifest.get("candidate_command"))
    resident_command = _as_dict(launch_manifest.get("resident_command"))
    foreground_session = _as_dict(launch_manifest.get("foreground_session"))
    process_readback = _as_dict(launch_manifest.get("process_readback"))
    blocker_groups = _as_dict(launch_manifest.get("blocker_groups"))

    runtime_blockers = _as_str_list(blocker_groups.get("runtime"))
    surface_dependency_blockers = _as_str_list(blocker_groups.get("surface_dependencies"))
    process_alive = bool(process_readback.get("process_alive"))
    process_blocker = "resident_host_process_not_supervised" if process_alive else "resident_host_process_missing"
    blockers = _ordered_unique([*runtime_blockers, process_blocker])
    diagnostic_status_runner_ready = bool(declared_entrypoint.get("exists")) and bool(status_command.get("executable"))
    bounded_foreground_session_available = bool(foreground_session.get("supported")) and bool(
        candidate_command.get("executable")
    )
    resident_runtime_candidate_available = bool(resident_command.get("executable"))
    bounded_launch_proof_available = bool(declared_entrypoint.get("exists")) and bounded_foreground_session_available
    runtime_state_write_configured = bool(foreground_session.get("runtime_state_write"))

    return {
        "ok": True,
        "kind": "lens.host.runtime_boundary",
        "status": "blocked",
        "route": "/lens/host/runtime-boundary",
        "host_route": "/lens/host",
        "manifest_route": "/lens/host/manifest",
        "ready": False,
        "runtime_ready": False,
        "resident_runtime": False,
        "resident": False,
        "diagnostic_status_runner_ready": diagnostic_status_runner_ready,
        "bounded_foreground_session_available": bounded_foreground_session_available,
        "bounded_launch_available": bounded_foreground_session_available,
        "resident_runtime_candidate_available": resident_runtime_candidate_available,
        "bounded_launch_proof_available": bounded_launch_proof_available,
        "bounded_launch_proof_script": "scripts/lens-host-launch-proof.ps1 -Mode Status",
        "runtime_state_write_configured": runtime_state_write_configured,
        "foreground_process_observed": process_alive,
        "resident_host_process_state": "foreground_observed_not_supervised" if process_alive else "missing",
        "resident_host_process_blocker": process_blocker,
        "service_managed": False,
        "process_supervision": False,
        "tray_presence": False,
        "global_hotkey": False,
        "overlay_window": False,
        "summon_anywhere": False,
        "runtime_blockers": runtime_blockers,
        "surface_dependency_blockers": surface_dependency_blockers,
        "blockers": blockers,
        "blocker_groups": {
            "runtime": runtime_blockers,
            "process_readback": [process_blocker],
            "surface_dependencies": surface_dependency_blockers,
        },
        "process_readback": process_readback,
        "foreground_session": foreground_session,
        "boundaries": {
            "diagnostic_status_runner": {
                "status": "ready" if diagnostic_status_runner_ready else "missing",
                "ready": diagnostic_status_runner_ready,
                "scope": "status_readback_only",
                "resident_runtime": False,
                "would_launch": False,
                "authority_granted": False,
            },
            "bounded_foreground_session": {
                "status": "available" if bounded_foreground_session_available else "blocked",
                "ready": bounded_foreground_session_available,
                "resident_runtime": False,
                "service_managed": False,
                "max_seconds": int(foreground_session.get("max_seconds") or 0),
                "would_launch": False,
                "authority_granted": False,
            },
            "resident_runtime_candidate": {
                "status": "available" if resident_runtime_candidate_available else "blocked",
                "ready": resident_runtime_candidate_available,
                "scope": "manual_process_runtime_candidate_only",
                "host_script": "scripts/lens-host.ps1 -Mode Resident",
                "resident_runtime": False,
                "service_managed": False,
                "process_supervision": False,
                "would_launch_from_api": False,
                "would_install_service": False,
                "authority_granted": False,
                "resident_claim_allowed": False,
            },
            "bounded_launch_proof": {
                "status": "available" if bounded_launch_proof_available else "blocked",
                "ready": bounded_launch_proof_available,
                "scope": "readback_to_existing_bounded_diagnostic_launch_proof",
                "proof_script": "scripts/lens-host-launch-proof.ps1 -Mode Status",
                "host_script": "scripts/lens-host.ps1 -Mode Launch",
                "resident_runtime": False,
                "would_launch_from_api": False,
                "would_launch_from_status_route": False,
                "authority_granted": False,
                "product_execution_authority": False,
                "api_local_process_launch_authority": False,
                "resident_claim_allowed": False,
            },
            "resident_runtime": {
                "status": "blocked",
                "ready": False,
                "resident": False,
                "service_managed": False,
                "process_supervision": False,
                "blockers": runtime_blockers or ["lens_host_persistent_supervision_prerequisites_pending"],
            },
        },
        "evidence": [
            "/lens/host/runtime-boundary",
            "/lens/host/manifest",
            "/lens/host",
            "scripts/lens-host.ps1 -Mode Status",
            "scripts/lens-host.ps1 -Mode Launch",
            "scripts/lens-host.ps1 -Mode Resident",
            "scripts/lens-host-launch-proof.ps1 -Mode Status",
        ],
        "governance": {
            "read_only_contract": True,
            "execution_authority": False,
            "approval_decision_authority": False,
            "memory_write": False,
            "local_process_launch_authority": False,
            "diagnostic_launch_authority": False,
            "process_supervision_authority": False,
            "process_restart_authority": False,
            "service_install_authority": False,
            "service_control_authority": False,
            "receipt_write_authority": False,
            "resident_claim_authority": False,
            "overlay_control_authority": False,
            "summon_authority": False,
            "hotkey_registration_authority": False,
            "tray_registration_authority": False,
            "mutation_authority_granted": False,
        },
        "next_smallest_truthful_gap": "resident_host_runtime_implementation_plan",
        "message": (
            "Lens has a diagnostic host runner, bounded foreground session readback, and a manual resident "
            "runtime candidate, but no supervised resident host, tray, hotkey, overlay, summon, or "
            "resident-claim authority."
        ),
    }
