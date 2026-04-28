from __future__ import annotations

from typing import Any


def lens_host_launch_manifest() -> dict[str, Any]:
    entrypoint = "scripts/lens-host.ps1"
    service_config = "data/config/services/lens-host.json"
    return {
        "ok": True,
        "kind": "lens.host.launch_manifest",
        "status": "entrypoint_missing",
        "contract_status": "readback_ready",
        "enabled": False,
        "launch_authority": False,
        "auto_start": False,
        "default_action": "manual_review_required",
        "route": "/lens/host/manifest",
        "host_route": "/lens/host",
        "declared_entrypoint": {
            "path": entrypoint,
            "exists": False,
            "purpose": "Future foreground Lens host runner for tray, summon, and overlay lifecycle.",
        },
        "candidate_command": {
            "shell": "pwsh",
            "args": [
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                entrypoint,
                "--mode",
                "foreground",
            ],
            "working_directory": ".",
            "executable": False,
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
        "blockers": [
            "lens_host_entrypoint_missing",
            "lens_host_service_config_missing",
            "tray_host_missing",
            "global_hotkey_binding_missing",
            "overlay_window_missing",
            "summon_binding_missing",
        ],
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
