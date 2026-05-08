from __future__ import annotations

import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from francis.kernel.paths import data_dir, repo_root


SUPERVISOR_READBACK_FRESH_SECONDS = 15 * 60


def _runtime_file_exists(relative_path: str) -> bool:
    try:
        return (repo_root() / Path(relative_path)).is_file()
    except OSError:
        return False


def _json_dict_from_path(path: Path) -> dict[str, Any]:
    try:
        if not path.is_file():
            return {}
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
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
    process_blockers = set(_as_str_list(blocker_groups.get("process_readback")))
    surface_blockers = set(_as_str_list(blocker_groups.get("surface_dependencies")))
    process_readback = _as_dict(launch_manifest.get("process_readback"))
    missing_by_requirement = {
        "resident_host_process": (
            "resident_host_process_missing" in process_blockers
            or "resident_host_not_supervised" in process_blockers
            or not bool(process_readback.get("process_alive"))
        ),
        "tray_presence": "tray_host_missing" in surface_blockers,
        "global_hotkey_binding": "global_hotkey_binding_missing" in surface_blockers,
        "overlay_window": "overlay_window_missing" in surface_blockers,
        "summon_binding": "summon_binding_missing" in surface_blockers,
    }
    return [item for item in required_before_enable if missing_by_requirement.get(item, False)]


def _lens_host_resident_process_requirement_readback(
    *,
    launch_manifest: dict[str, Any],
    missing: bool,
) -> dict[str, Any]:
    process_readback = _as_dict(launch_manifest.get("process_readback"))
    process_alive = bool(process_readback.get("process_alive"))
    blocked_reason = str(process_readback.get("blocked_reason") or "")
    if not missing:
        return {
            "requirement_state": "ready",
            "process_alive": process_alive,
            "blocked_reason": "",
        }
    if process_alive:
        return {
            "requirement_state": "foreground_observed_not_supervised",
            "process_alive": True,
            "blocked_reason": blocked_reason or "resident_host_not_supervised",
            "blocker": "resident_host_process_not_supervised",
        }
    return {
        "requirement_state": "missing",
        "process_alive": False,
        "blocked_reason": blocked_reason or "resident_host_process_missing",
        "blocker": "resident_host_process_missing",
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
        dependencies.append(
            {
                **extra_readback,
                "id": item,
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
    state_exists = _path_exists(state_file)
    state_payload = _json_dict_from_path(state_file) if state_exists else {}
    state_status = str(state_payload.get("status") or "")
    mode = str(state_payload.get("mode") or "")
    host_mode = str(state_payload.get("host_mode") or "")
    observed_pid = _safe_pid(state_payload.get("observed_pid"))
    observed_state = str(state_payload.get("observed_state") or "")
    bounded_supervisor_observed = state_status in {
        "observing",
        "observation_completed",
        "supervising",
        "supervised_session_completed",
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
    if resident_runtime_candidate_supervised:
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
        "observed_pid": observed_pid,
        "observed_state": observed_state,
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
        "resident_supervised_runtime": False,
        "resident_claim_allowed": False,
        "process_supervision_authority": False,
        "process_restart_authority": False,
        "service_control_authority": False,
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
    host_process_blocker = "resident_host_process_not_supervised" if process_alive else "resident_host_process_missing"
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
        "resident_host_process_state": "foreground_observed_not_supervised" if process_alive else "missing",
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
        "resident_supervised_runtime": False,
        "resident_host_supervised": False,
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
            "service_readback": service_readback,
            "supervision_readiness": supervision_readiness,
        },
        "next_smallest_truthful_gap": next_gap,
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
    service_config = "config/runtime/services/lens-host.json"
    entrypoint_exists = _runtime_file_exists(entrypoint)
    service_config_payload = _runtime_json_dict(service_config)
    required_before_enable = _lens_host_required_before_enable(service_config_payload)
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
    supervisor_readback = _lens_host_supervisor_readback()
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
            "lens_host_entrypoint_missing",
            "lens_host_service_config_missing",
        ),
        "process_readback": process_readback_blockers,
        "service_plan": service_plan_blockers,
        "supervision": supervision_blockers,
        "surface_dependencies": _select_blockers(
            blockers,
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
                "blockers": runtime_blockers or ["lens_host_runtime_not_implemented"],
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
