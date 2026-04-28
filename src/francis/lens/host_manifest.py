from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from francis.kernel.paths import data_dir, repo_root


def _runtime_file_exists(relative_path: str) -> bool:
    try:
        return (repo_root() / Path(relative_path)).is_file()
    except OSError:
        return False


def _json_dict_from_path(path: Path) -> dict[str, Any]:
    try:
        if not path.is_file():
            return {}
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _runtime_json_dict(relative_path: str) -> dict[str, Any]:
    return _json_dict_from_path(repo_root() / Path(relative_path))


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


def _pid_from_file(path: Path) -> int:
    try:
        return _safe_pid(path.read_text(encoding="utf-8").strip())
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
    state_exists = _path_exists(state_file)
    pid_present = _path_exists(pid_file)
    pid = _pid_from_file(pid_file) if pid_present else 0
    process_alive, process_alive_check = _process_alive_readback(pid)
    state_payload = _json_dict_from_path(state_file) if state_exists else {}
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
        "state_status": str(state_payload.get("status") or ""),
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


def _lens_host_service_readback(service_config_payload: dict[str, Any]) -> dict[str, Any]:
    service_name = str(service_config_payload.get("service_name") or "Francis-LensHost")
    return {
        "status": "not_checked_by_api",
        "readback_ready": True,
        "service_name": service_name,
        "installed": False,
        "windows_service": True,
        "host_query": "runner_only",
        "install_supported": False,
        "start_supported": False,
        "stop_supported": False,
        "restart_supported": False,
        "install_authority": False,
        "service_install_authority": False,
        "service_control_authority": False,
        "blocked_reason": "lens_host_service_status_runner_required",
    }


def _as_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


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
    blocked_reason = str(service_config_payload.get("blocked_reason") or "lens_host_runtime_not_implemented")
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
        "source": "config/runtime/services/lens-host.json",
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


def _lens_host_supervision_readiness(
    *,
    entrypoint_exists: bool,
    service_manager: str,
    service_manager_exists: bool,
    service_config_exists: bool,
    service_config_payload: dict[str, Any],
    process_readback: dict[str, Any],
) -> dict[str, Any]:
    supervision_enabled = bool(service_config_payload.get("process_supervision_enabled"))
    install_authority = bool(
        service_config_payload.get("install_authority") or service_config_payload.get("service_install_authority")
    )
    service_control_authority = bool(service_config_payload.get("service_control_authority"))
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
    ]
    blocked_by = [str(item["id"]) for item in prerequisites if not bool(item["ready"])]
    return {
        "status": "blocked" if blocked_by else "ready",
        "ready": not blocked_by,
        "mode": str(service_config_payload.get("supervision_mode") or "windows_service"),
        "service_manager": service_manager,
        "service_manager_exists": service_manager_exists,
        "process_supervision_enabled": supervision_enabled,
        "service_install_authority": install_authority,
        "service_control_authority": service_control_authority,
        "resident_claim_allowed": False,
        "next_allowed_transition": "foreground_status_session_only" if blocked_by else "operator_review_required",
        "blocked_by": blocked_by,
        "blocked_reason": str(
            service_config_payload.get("supervision_blocked_reason") or "resident_supervision_disabled"
        ),
        "prerequisites": prerequisites,
    }


def lens_host_launch_manifest() -> dict[str, Any]:
    entrypoint = "scripts/lens-host.ps1"
    service_config = "config/runtime/services/lens-host.json"
    entrypoint_exists = _runtime_file_exists(entrypoint)
    service_config_payload = _runtime_json_dict(service_config)
    service_config_exists = bool(service_config_payload)
    service_manager = str(service_config_payload.get("manager") or "scripts/service-install.ps1")
    service_manager_exists = _runtime_file_exists(service_manager)
    service_readback = _lens_host_service_readback(service_config_payload)
    service_plan = _lens_host_service_plan(
        entrypoint_exists=entrypoint_exists,
        service_manager=service_manager,
        service_manager_exists=service_manager_exists,
        service_config_exists=service_config_exists,
        service_config_payload=service_config_payload,
    )
    process_readback = _lens_host_process_readback()
    supervision_readiness = _lens_host_supervision_readiness(
        entrypoint_exists=entrypoint_exists,
        service_manager=service_manager,
        service_manager_exists=service_manager_exists,
        service_config_exists=service_config_exists,
        service_config_payload=service_config_payload,
        process_readback=process_readback,
    )
    foreground_supported = bool(service_config_payload.get("foreground_session_enabled"))
    blockers = [
        "lens_host_runtime_not_implemented",
        "tray_host_missing",
        "global_hotkey_binding_missing",
        "overlay_window_missing",
        "summon_binding_missing",
    ]
    if not entrypoint_exists:
        blockers.insert(0, "lens_host_entrypoint_missing")
    if not service_config_exists:
        insert_at = 1 if not entrypoint_exists else 0
        blockers.insert(insert_at, "lens_host_service_config_missing")

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
        "service_install": {
            "manager": service_manager,
            "manager_exists": service_manager_exists,
            "config_path": service_config,
            "config_exists": service_config_exists,
            "config_status": "present_disabled" if service_config_exists else "missing",
            "service_name": str(service_config_payload.get("service_name") or ""),
            "installable": False,
            "blocked_reason": str(service_config_payload.get("blocked_reason") or "lens_host_runtime_not_implemented"),
            "install_authority": False,
            "start_after_install": False,
            "auto_start": False,
        },
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
                "path": service_config,
                "status": "present_disabled" if service_config_exists else "missing",
            },
            {
                "id": "host_service_readback",
                "service_name": service_readback["service_name"],
                "status": "readback_ready",
            },
            {
                "id": "host_service_plan",
                "path": service_config,
                "status": service_plan["status"],
            },
            {
                "id": "host_process_readback",
                "path": process_readback["runtime_state_path"],
                "status": "readback_ready",
            },
            {
                "id": "host_readiness",
                "route": "/lens/host",
                "status": "readback_ready",
            },
            {
                "id": "tray_presence",
                "status": "missing",
            },
            {
                "id": "global_hotkey",
                "status": "missing",
            },
            {
                "id": "overlay_window",
                "status": "missing",
            },
        ],
        "blockers": blockers,
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
