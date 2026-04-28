from __future__ import annotations

from pathlib import Path
from typing import Any

from francis.kernel.paths import repo_root


def _runtime_file_exists(relative_path: str) -> bool:
    try:
        return (repo_root() / Path(relative_path)).is_file()
    except OSError:
        return False


def lens_host_launch_manifest() -> dict[str, Any]:
    entrypoint = "scripts/lens-host.ps1"
    service_config = "data/config/services/lens-host.json"
    entrypoint_exists = _runtime_file_exists(entrypoint)
    blockers = [
        "lens_host_runtime_not_implemented",
        "lens_host_service_config_missing",
        "tray_host_missing",
        "global_hotkey_binding_missing",
        "overlay_window_missing",
        "summon_binding_missing",
    ]
    if not entrypoint_exists:
        blockers.insert(0, "lens_host_entrypoint_missing")

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
            "executable": False,
            "reason": "Foreground Lens host runtime is not implemented.",
        },
        "service_install": {
            "manager": "scripts/service-install.ps1",
            "config_path": service_config,
            "config_exists": False,
            "install_authority": False,
            "start_after_install": False,
        },
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
            "mutation_authority_granted": False,
        },
    }
