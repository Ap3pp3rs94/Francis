from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def _write_dev_environment(repo_root: Path) -> None:
    env_root = repo_root / "config" / "environments"
    env_root.mkdir(parents=True, exist_ok=True)
    (env_root / "dev.yaml").write_text(
        """
version: 1
profile:
  id: dev
  name: Development
runtime:
  mode: dev
governance:
  approvals:
    enabled: true
    mode: policy
  trust:
    minimum_operational_trust: 0
network:
  egress:
    enabled: true
features:
  web_learning:
    enabled: true
    allow_search: true
    allow_fetch: true
    allow_ingest: false
ui:
  label: "DEV"
  banner:
    text: "DEV MODE"
""".strip(),
        encoding="utf-8",
    )


def _write_lens_host_status_runner(repo_root: Path) -> None:
    script = repo_root / "scripts" / "lens-host.ps1"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text("# Lens host status runner fixture\n", encoding="utf-8")


def _write_service_manager(repo_root: Path) -> None:
    script = repo_root / "scripts" / "service-install.ps1"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text("# Service manager fixture\n", encoding="utf-8")


def _write_lens_preflight_scripts(repo_root: Path) -> None:
    script_dir = repo_root / "scripts"
    script_dir.mkdir(parents=True, exist_ok=True)
    for name in (
        "lens-host-preflight.ps1",
        "lens-summon-preflight.ps1",
        "lens-tray-preflight.ps1",
        "lens-overlay-preflight.ps1",
    ):
        (script_dir / name).write_text("# Lens preflight fixture\n", encoding="utf-8")


def _write_lens_runtime_configs(repo_root: Path) -> None:
    config_root = repo_root / "config" / "runtime" / "lens"
    config_root.mkdir(parents=True, exist_ok=True)
    (config_root / "summon.json").write_text(
        """
{
  "kind": "lens.summon.config",
  "version": 1,
  "enabled": false,
  "summon_name": "Francis Lens Summon",
  "global_hotkey": "Ctrl+Alt+Space",
  "binding_scope": "global",
  "binding_enabled": false,
  "register_hotkey": false,
  "startup_register": false,
  "launch_target": "lens_host",
  "launch_mode": "Foreground",
  "palette_route": "/lens/status",
  "host_preflight": "scripts/lens-host-preflight.ps1",
  "host_status_runner": "scripts/lens-host.ps1",
  "overlay_required": true,
  "tray_required": true,
  "requires_explicit_enable": true,
  "summon_authority": false,
  "hotkey_registration_authority": false,
  "overlay_control_authority": false,
  "local_process_launch_authority": false,
  "blocked_reason": "lens_summon_binding_not_implemented"
}
""".strip(),
        encoding="utf-8",
    )
    (config_root / "tray.json").write_text(
        """
{
  "kind": "lens.tray.config",
  "version": 1,
  "enabled": false,
  "presence_name": "Francis Lens Tray Presence",
  "tray_scope": "user_session",
  "tray_host_enabled": false,
  "tray_icon_enabled": false,
  "startup_register": false,
  "notification_supported": false,
  "status_route": "/lens/host",
  "lens_status_route": "/lens/status",
  "launch_target": "lens_host",
  "host_preflight": "scripts/lens-host-preflight.ps1",
  "host_status_runner": "scripts/lens-host.ps1",
  "summon_preflight": "scripts/lens-summon-preflight.ps1",
  "summon_config": "config/runtime/lens/summon.json",
  "requires_explicit_enable": true,
  "tray_registration_authority": false,
  "tray_icon_authority": false,
  "notification_authority": false,
  "overlay_control_authority": false,
  "local_process_launch_authority": false,
  "service_control_authority": false,
  "summon_authority": false,
  "blocked_reason": "lens_tray_presence_not_implemented"
}
""".strip(),
        encoding="utf-8",
    )
    (config_root / "overlay.json").write_text(
        """
{
  "kind": "lens.overlay.config",
  "version": 1,
  "enabled": false,
  "overlay_name": "Francis Lens Overlay",
  "overlay_scope": "user_session",
  "window_enabled": false,
  "always_on_top": false,
  "dock_supported": false,
  "focus_supported": false,
  "click_through_supported": false,
  "capture_supported": false,
  "status_route": "/lens/status",
  "host_route": "/lens/host",
  "host_preflight": "scripts/lens-host-preflight.ps1",
  "host_status_runner": "scripts/lens-host.ps1",
  "summon_preflight": "scripts/lens-summon-preflight.ps1",
  "tray_preflight": "scripts/lens-tray-preflight.ps1",
  "requires_explicit_enable": true,
  "overlay_control_authority": false,
  "window_management_authority": false,
  "local_process_launch_authority": false,
  "capture_authority": false,
  "summon_authority": false,
  "tray_registration_authority": false,
  "blocked_reason": "lens_overlay_window_not_implemented"
}
""".strip(),
        encoding="utf-8",
    )


def _write_lens_host_service_config(repo_root: Path) -> None:
    config = repo_root / "config" / "runtime" / "services" / "lens-host.json"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(
        """
{
  "kind": "lens.host.service_config",
  "version": 1,
  "enabled": false,
  "service_name": "Francis-LensHost",
  "display_name": "Francis Lens Host",
  "description": "Disabled readiness baseline for the future resident Lens host.",
  "manager": "scripts/service-install.ps1",
  "entrypoint": "scripts/lens-host.ps1",
  "service_executable": "pwsh",
  "service_arguments": [
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    "scripts/lens-host.ps1",
    "-Mode",
    "Foreground"
  ],
  "working_dir": ".",
  "use_wrapper": true,
  "stdout": "data/logs/lens-host/stdout.log",
  "stderr": "data/logs/lens-host/stderr.log",
  "runtime_state_path": "data/runtime/lens-host/status.json",
  "pid_path": "data/runtime/lens-host/lens-host.pid",
  "status_mode": "Status",
  "foreground_mode": "Foreground",
  "foreground_session_enabled": true,
  "foreground_session_default_seconds": 0,
  "foreground_session_max_seconds": 30,
  "runtime_state_write": true,
  "start_type": "Manual",
  "auto_start": false,
  "start_after_install": false,
  "installable": false,
  "process_supervision_enabled": false,
  "supervision_readiness_gate": true,
  "supervision_mode": "windows_service",
  "supervision_ready": false,
  "supervision_blocked_reason": "resident_supervision_disabled",
  "process_supervision_readback": true,
  "service_status_readback": true,
  "service_control_authority": false,
  "install_authority": false,
  "service_install_authority": false,
  "blocked_reason": "lens_host_runtime_not_implemented"
}
""".strip(),
        encoding="utf-8",
    )


def _write_lens_host_runtime_state(data_root: Path, *, pid: int, status: str = "foreground_running") -> None:
    runtime_root = data_root / "runtime" / "lens-host"
    runtime_root.mkdir(parents=True, exist_ok=True)
    (runtime_root / "lens-host.pid").write_text(str(pid), encoding="ascii")
    (runtime_root / "status.json").write_text(
        json.dumps(
            {
                "kind": "lens.host.runtime_state",
                "status": status,
                "mode": "foreground",
                "pid": pid,
                "process_alive": status == "foreground_running",
                "resident": False,
                "service_managed": False,
                "tray_presence": False,
                "global_hotkey": False,
                "overlay_window": False,
                "summon_anywhere": False,
                "updated_at": "2026-04-28T21:30:00Z",
                "governance": {
                    "memory_write": False,
                    "service_control_authority": False,
                    "local_process_launch_authority": False,
                },
            }
        ),
        encoding="utf-8",
    )


def _criterion(body: dict[str, Any], criterion_id: str) -> dict[str, Any]:
    readiness = body.get("stage6_readiness") if isinstance(body.get("stage6_readiness"), dict) else {}
    criteria = readiness.get("criteria") if isinstance(readiness.get("criteria"), list) else []
    for item in criteria:
        if isinstance(item, dict) and item.get("id") == criterion_id:
            return item
    raise AssertionError(f"missing Stage 6 criterion: {criterion_id}")


def test_lens_status_projects_readonly_stage6_contract(monkeypatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    data_root = repo_root / "data"
    _write_dev_environment(repo_root)
    _write_lens_host_status_runner(repo_root)
    _write_service_manager(repo_root)
    _write_lens_preflight_scripts(repo_root)
    _write_lens_runtime_configs(repo_root)
    _write_lens_host_service_config(repo_root)
    monkeypatch.setenv("FRANCIS_ROOT", str(repo_root))
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_ENV_PROFILE", "dev")
    monkeypatch.setenv("FRANCIS_RUN_MODE", "api")

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())
    response = client.get("/lens/status?limit=3")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["kind"] == "lens.status"
    assert body["read_only"] is True
    assert body["governance"] == {
        "gate": "lens_readback_only",
        "execution_authority": False,
        "approval_decision_authority": False,
        "memory_write": False,
        "overlay_control_authority": False,
        "capture_authority": False,
        "new_sensing_authority": False,
    }
    assert body["command_palette"]["status"] == "readback_ready"
    assert body["command_palette"]["summon_anywhere"] is False
    assert body["command_palette"]["availability"] == "chat_ui_only"
    assert body["command_palette"]["command_total"] == len(body["command_palette"]["commands"])
    assert body["command_palette"]["command_total"] >= 15
    assert body["command_palette"]["groups"]["Navigation"] >= 8
    assert body["command_palette"]["groups"]["Control"] >= 5
    assert body["command_palette"]["governance"] == {
        "read_only_contract": True,
        "execution_authority": False,
        "approval_decision_authority": False,
        "memory_write": False,
        "overlay_control_authority": False,
        "summon_authority": False,
        "mutation_authority_granted": False,
    }
    assert body["hud"]["readback_ready"] is True
    assert body["hud"]["runtime_status"] == "readback_only"
    assert body["hud"]["resident_overlay"] is False
    assert body["hud"]["runtime"] == {
        "status": "readback_only",
        "claim": "chat_ui_hud_readback_only",
        "surface": "chat_ui.system_orb",
        "route": "/lens/hud",
        "window_host": "chat_ui",
        "resident_overlay": False,
        "always_on_top": False,
        "global_hotkey": False,
        "tray_presence": False,
        "os_level": False,
        "blockers": [
            "resident_overlay_runtime_missing",
            "global_hotkey_binding_missing",
            "tray_host_missing",
            "always_on_top_window_missing",
        ],
        "message": "HUD readback exists through chat UI; resident OS overlay runtime is not implemented here.",
        "governance": {
            "read_only_contract": True,
            "execution_authority": False,
            "approval_decision_authority": False,
            "memory_write": False,
            "overlay_control_authority": False,
            "summon_authority": False,
            "capture_authority": False,
            "new_sensing_authority": False,
            "mutation_authority_granted": False,
        },
    }
    resident_host = body["resident_host"]
    assert resident_host["kind"] == "lens.resident_host"
    assert resident_host["status"] == "not_implemented"
    assert resident_host["contract_status"] == "readback_ready"
    assert resident_host["availability"] == "backend_readback_only"
    assert resident_host["route"] == "/lens/host"
    assert resident_host["activation_request_route"] == "/lens/host/activation/request"
    assert resident_host["activation_request"] == {
        "status": "approval_request_ready",
        "route": "/lens/host/activation/request",
        "readback_route": "/lens/host/activation",
        "preflight_route": "/lens/host/activation/preflight",
        "plan_route": "/lens/host/activation/plan",
        "execute_route": "/lens/host/activation/execute",
        "method": "POST",
        "action": "lens.host.foreground_activation",
        "mode": "foreground_status_session",
        "creates_approval_request": True,
        "launches_process": False,
        "installs_service": False,
        "starts_service": False,
        "registers_hotkey": False,
        "controls_overlay": False,
        "governance": {
            "gate": "lens_host_activation_request",
            "route": "/lens/host/activation/request",
            "required_scope": "system.write",
            "approval_action": "lens.host.foreground_activation",
            "approval_request_write": True,
            "readback_route": "/lens/host/activation",
            "preflight_route": "/lens/host/activation/preflight",
            "plan_route": "/lens/host/activation/plan",
            "execute_route": "/lens/host/activation/execute",
            "read_only_contract": False,
            "activation_authority": False,
            "execution_authority": False,
            "approval_decision_authority": False,
            "memory_write": False,
            "local_process_launch_authority": False,
            "service_install_authority": False,
            "service_control_authority": False,
            "overlay_control_authority": False,
            "summon_authority": False,
            "hotkey_registration_authority": False,
            "runtime_mutation_authority_granted": False,
            "next_step": "operator_decides_pending_lens_host_activation_request",
        },
    }
    assert resident_host["activation_readback_route"] == "/lens/host/activation"
    activation_state = resident_host["activation_state"]
    assert activation_state["kind"] == "lens.host.activation.readback"
    assert activation_state["status"] == "none"
    assert activation_state["request_route"] == "/lens/host/activation/request"
    assert activation_state["decision_route"] == "/approvals/decision"
    assert activation_state["approval_action"] == "lens.host.foreground_activation"
    assert activation_state["pending_count"] == 0
    assert activation_state["approved_count"] == 0
    assert activation_state["rejected_count"] == 0
    assert activation_state["emergency_count"] == 0
    assert activation_state["total_count"] == 0
    assert activation_state["latest"] is None
    assert activation_state["items"] == []
    assert activation_state["governance"]["gate"] == "lens_host_activation_readback"
    assert activation_state["governance"]["read_only_contract"] is True
    assert activation_state["governance"]["approval_request_write"] is False
    assert activation_state["governance"]["execution_authority"] is False
    assert activation_state["governance"]["approval_decision_authority"] is False
    assert activation_state["governance"]["local_process_launch_authority"] is False
    assert resident_host["activation_execution_preflight_route"] == "/lens/host/activation/preflight"
    activation_preflight = resident_host["activation_execution_preflight"]
    assert activation_preflight["kind"] == "lens.host.activation.execution_preflight"
    assert activation_preflight["status"] == "blocked"
    assert activation_preflight["ready"] is False
    assert activation_preflight["route"] == "/lens/host/activation/preflight"
    assert activation_preflight["plan_route"] == "/lens/host/activation/plan"
    assert activation_preflight["execute_route"] == "/lens/host/activation/execute"
    assert activation_preflight["request_route"] == "/lens/host/activation/request"
    assert activation_preflight["readback_route"] == "/lens/host/activation"
    assert activation_preflight["approval"]["required"] is True
    assert activation_preflight["approval"]["found"] is False
    assert activation_preflight["permission"]["ready"] is False
    assert activation_preflight["operator_posture"]["status"] == "ready"
    assert "approval_id_required" in activation_preflight["blockers"]
    assert "system_write_scope_not_ready" in activation_preflight["blockers"]
    assert "local_process_launch_authority_not_granted" in activation_preflight["blockers"]
    assert activation_preflight["governance"]["gate"] == "lens_host_activation_execution_preflight"
    assert activation_preflight["governance"]["read_only_contract"] is True
    assert activation_preflight["governance"]["execution_authority"] is False
    assert activation_preflight["governance"]["approval_decision_authority"] is False
    assert activation_preflight["governance"]["local_process_launch_authority"] is False
    assert resident_host["activation_execution_plan_route"] == "/lens/host/activation/plan"
    activation_plan = resident_host["activation_execution_plan"]
    assert activation_plan["kind"] == "lens.host.activation.execution_plan"
    assert activation_plan["status"] == "blocked"
    assert activation_plan["plan_available"] is True
    assert activation_plan["execution_ready"] is False
    assert activation_plan["route"] == "/lens/host/activation/plan"
    assert activation_plan["execute_route"] == "/lens/host/activation/execute"
    assert activation_plan["preflight_route"] == "/lens/host/activation/preflight"
    assert activation_plan["preflight"]["kind"] == "lens.host.activation.execution_preflight"
    assert activation_plan["plan"]["would_launch_process"] is False
    assert activation_plan["plan"]["would_install_service"] is False
    assert activation_plan["plan"]["would_start_service"] is False
    assert activation_plan["plan"]["would_register_hotkey"] is False
    assert activation_plan["plan"]["would_open_overlay"] is False
    assert activation_plan["plan"]["would_write_memory"] is False
    assert activation_plan["plan"]["would_decide_approval"] is False
    plan_steps = {step["id"]: step for step in activation_plan["plan"]["steps"]}
    assert plan_steps["verify_exact_approval"]["status"] == "blocked"
    assert plan_steps["launch_foreground_status_session"]["status"] == "blocked"
    assert plan_steps["launch_foreground_status_session"]["authority_granted"] is False
    assert plan_steps["record_activation_receipt"]["authority_granted"] is False
    assert "approval_id_required" in activation_plan["blockers"]
    assert "local_process_launch_authority_not_granted" in activation_plan["blockers"]
    assert activation_plan["governance"]["gate"] == "lens_host_activation_execution_plan"
    assert activation_plan["governance"]["read_only_contract"] is True
    assert activation_plan["governance"]["plan_readback_only"] is True
    assert activation_plan["governance"]["execution_authority"] is False
    assert activation_plan["governance"]["approval_decision_authority"] is False
    assert activation_plan["governance"]["local_process_launch_authority"] is False
    assert activation_plan["governance"]["receipt_write_authority"] is False
    assert resident_host["activation_execution_denial_route"] == "/lens/host/activation/execute"
    activation_denial = resident_host["activation_execution_denial"]
    assert activation_denial["kind"] == "lens.host.activation.execution_denial"
    assert activation_denial["status"] == "blocked"
    assert activation_denial["applied"] is False
    assert activation_denial["executed"] is False
    assert activation_denial["route"] == "/lens/host/activation/execute"
    assert activation_denial["preflight_route"] == "/lens/host/activation/preflight"
    assert activation_denial["plan_route"] == "/lens/host/activation/plan"
    assert activation_denial["denial"]["would_launch_process"] is False
    assert activation_denial["denial"]["would_write_receipt"] is False
    assert "approval_id_required" in activation_denial["blockers"]
    assert "system_write_scope_not_ready" in activation_denial["blockers"]
    assert "local_process_launch_authority_not_granted" in activation_denial["blockers"]
    assert activation_denial["governance"]["gate"] == "lens_host_activation_execution_denial"
    assert activation_denial["governance"]["execution_boundary"] is True
    assert activation_denial["governance"]["denial_boundary"] is True
    assert activation_denial["governance"]["execution_authority"] is False
    assert activation_denial["governance"]["approval_decision_authority"] is False
    assert activation_denial["governance"]["local_process_launch_authority"] is False
    assert activation_denial["governance"]["receipt_write_authority"] is False
    assert resident_host["launch_manifest_route"] == "/lens/host/manifest"
    assert resident_host["status_route"] == "/lens/status"
    assert resident_host["local_hud_route"] == "/lens/hud"
    assert resident_host["local_palette_route"] == "/lens/status"
    assert resident_host["handoff_target"] == "chat_ui.system_orb"
    assert resident_host["status_runner_present"] is True
    assert resident_host["service_config_present"] is True
    assert resident_host["service_config_path"] == "config/runtime/services/lens-host.json"
    assert resident_host["service_readback_ready"] is True
    assert resident_host["service_readback"] == {
        "status": "not_checked_by_api",
        "readback_ready": True,
        "service_name": "Francis-LensHost",
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
    expected_service_plan = {
        "kind": "service_install.plan_projection",
        "status": "blocked",
        "ready": False,
        "source": "config/runtime/services/lens-host.json",
        "manager": "scripts/service-install.ps1",
        "manager_exists": True,
        "plan_mode": "Plan",
        "service_name": "Francis-LensHost",
        "service_executable": "pwsh",
        "service_arguments": [
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "scripts/lens-host.ps1",
            "-Mode",
            "Foreground",
        ],
        "planned_command": "pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/lens-host.ps1 -Mode Foreground",
        "working_directory": ".",
        "start_type": "Manual",
        "use_wrapper": True,
        "would_install": False,
        "would_start": False,
        "wrapper_would_write": False,
        "blocked_by": [
            "installable_false",
            "install_authority_false",
            "service_install_authority_false",
            "service_control_authority_false",
        ],
        "blocked_reason": "lens_host_runtime_not_implemented",
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
    assert resident_host["service_plan_ready"] is False
    assert resident_host["service_plan"] == expected_service_plan
    assert resident_host["process_readback_ready"] is True
    assert resident_host["process_readback"] == {
        "status": "missing",
        "readback_ready": True,
        "runtime_state_path": "data/runtime/lens-host/status.json",
        "state_exists": False,
        "state_status": "",
        "state_updated_at": "",
        "pid_path": "data/runtime/lens-host/lens-host.pid",
        "pid_present": False,
        "pid": 0,
        "process_alive": False,
        "process_alive_check": "not_attempted_by_api",
        "supervision_enabled": False,
        "start_supported": False,
        "stop_supported": False,
        "restart_supported": False,
        "supervision_authority": False,
        "blocked_reason": "resident_host_process_missing",
    }
    expected_supervision_readiness = {
        "status": "blocked",
        "ready": False,
        "mode": "windows_service",
        "service_manager": "scripts/service-install.ps1",
        "service_manager_exists": True,
        "process_supervision_enabled": False,
        "service_install_authority": False,
        "service_control_authority": False,
        "resident_claim_allowed": False,
        "next_allowed_transition": "foreground_status_session_only",
        "blocked_by": [
            "process_supervision_enabled",
            "service_install_authority",
            "service_control_authority",
        ],
        "blocked_reason": "resident_supervision_disabled",
        "prerequisites": [
            {
                "id": "host_entrypoint",
                "label": "Lens host entrypoint",
                "ready": True,
                "status": "ready",
                "reason": "",
            },
            {
                "id": "service_manager",
                "label": "Service manager script",
                "ready": True,
                "status": "ready",
                "reason": "",
            },
            {
                "id": "service_config",
                "label": "Lens host service config",
                "ready": True,
                "status": "present_disabled",
                "reason": "",
            },
            {
                "id": "foreground_process_readback",
                "label": "Foreground process readback",
                "ready": True,
                "status": "missing",
                "reason": "",
            },
            {
                "id": "process_supervision_enabled",
                "label": "Process supervision enabled",
                "ready": False,
                "status": "blocked",
                "reason": "disabled_in_service_config",
            },
            {
                "id": "service_install_authority",
                "label": "Service install authority",
                "ready": False,
                "status": "blocked",
                "reason": "install_authority_false",
            },
            {
                "id": "service_control_authority",
                "label": "Service control authority",
                "ready": False,
                "status": "blocked",
                "reason": "service_control_authority_false",
            },
        ],
    }
    assert resident_host["supervision_readiness"] == expected_supervision_readiness
    assert resident_host["foreground_session"] == {
        "supported": True,
        "default_seconds": 0,
        "max_seconds": 30,
        "runtime_state_write": True,
        "resident": False,
        "service_managed": False,
        "tray_presence": False,
        "global_hotkey": False,
        "overlay_window": False,
        "summon_anywhere": False,
    }
    assert resident_host["resident"] is False
    assert resident_host["process_supervision"] is False
    assert resident_host["startup_integration"] is False
    assert resident_host["tray_presence"] is False
    assert resident_host["global_hotkey"] is False
    assert resident_host["always_on_top_overlay"] is False
    assert resident_host["overlay_window"] is False
    assert resident_host["command_palette_binding"] is False
    assert resident_host["summon_anywhere"] is False
    assert [item["id"] for item in resident_host["components"]] == [
        "host_status_runner",
        "host_service_config",
        "host_service_readback",
        "host_service_plan",
        "host_process_readback",
        "host_process",
        "tray_presence",
        "global_hotkey",
        "overlay_window",
        "command_palette_bridge",
    ]
    assert resident_host["blockers"] == [
        "lens_host_runtime_not_implemented",
        "resident_host_process_missing",
        "tray_host_missing",
        "global_hotkey_binding_missing",
        "always_on_top_window_missing",
        "overlay_window_missing",
        "summon_binding_missing",
    ]
    launch_manifest = resident_host["launch_manifest"]
    assert launch_manifest["kind"] == "lens.host.launch_manifest"
    assert launch_manifest["status"] == "status_runner_present"
    assert launch_manifest["contract_status"] == "readback_ready"
    assert launch_manifest["enabled"] is False
    assert launch_manifest["launch_authority"] is False
    assert launch_manifest["auto_start"] is False
    assert launch_manifest["default_action"] == "status_readback_only"
    assert launch_manifest["route"] == "/lens/host/manifest"
    assert launch_manifest["host_route"] == "/lens/host"
    assert launch_manifest["declared_entrypoint"] == {
        "path": "scripts/lens-host.ps1",
        "exists": True,
        "purpose": "Status-only Lens host runner; future foreground tray, summon, and overlay lifecycle.",
    }
    assert launch_manifest["status_command"] == {
        "shell": "pwsh",
        "args": [
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "scripts/lens-host.ps1",
            "-Mode",
            "Status",
        ],
        "working_directory": ".",
        "executable": True,
    }
    assert launch_manifest["candidate_command"] == {
        "shell": "pwsh",
        "args": [
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "scripts/lens-host.ps1",
            "-Mode",
            "Foreground",
        ],
        "working_directory": ".",
        "executable": True,
        "reason": "Manual bounded foreground status session is available; resident service, tray, summon, and overlay remain blocked.",
    }
    assert launch_manifest["service_install"] == {
        "manager": "scripts/service-install.ps1",
        "manager_exists": True,
        "config_path": "config/runtime/services/lens-host.json",
        "config_exists": True,
        "config_status": "present_disabled",
        "service_name": "Francis-LensHost",
        "installable": False,
        "blocked_reason": "lens_host_runtime_not_implemented",
        "install_authority": False,
        "start_after_install": False,
        "auto_start": False,
    }
    assert launch_manifest["service_plan"] == expected_service_plan
    assert launch_manifest["service_readback"] == resident_host["service_readback"]
    assert launch_manifest["process_readback"] == resident_host["process_readback"]
    assert launch_manifest["supervision_readiness"] == expected_supervision_readiness
    assert launch_manifest["foreground_session"] == resident_host["foreground_session"]
    assert [item["id"] for item in launch_manifest["required_bindings"]] == [
        "api_status",
        "host_status_runner",
        "host_service_config",
        "host_service_readback",
        "host_service_plan",
        "host_process_readback",
        "host_readiness",
        "tray_presence",
        "global_hotkey",
        "overlay_window",
    ]
    assert launch_manifest["blockers"] == [
        "lens_host_runtime_not_implemented",
        "tray_host_missing",
        "global_hotkey_binding_missing",
        "overlay_window_missing",
        "summon_binding_missing",
    ]
    assert launch_manifest["governance"] == {
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
    }
    assert resident_host["governance"] == {
        "read_only_contract": True,
        "execution_authority": False,
        "approval_decision_authority": False,
        "memory_write": False,
        "overlay_control_authority": False,
        "summon_authority": False,
        "capture_authority": False,
        "new_sensing_authority": False,
        "local_process_launch_authority": False,
        "service_control_authority": False,
        "mutation_authority_granted": False,
    }
    preflight = body["preflight"]
    assert preflight["kind"] == "lens.preflight"
    assert preflight["status"] == "blocked"
    assert preflight["ready"] is False
    assert preflight["read_only"] is True
    assert preflight["route"] == "/lens/preflight"
    assert preflight["summary"]["surface_total"] == 4
    assert preflight["summary"]["ready_total"] == 0
    assert preflight["summary"]["blocked_total"] == 4
    assert preflight["governance"]["execution_authority"] is False
    assert preflight["governance"]["service_control_authority"] is False
    assert preflight["governance"]["hotkey_registration_authority"] is False
    assert preflight["governance"]["overlay_control_authority"] is False
    assert preflight["governance"]["mutation_authority_granted"] is False
    preflight_surfaces = preflight["surfaces"]
    assert preflight_surfaces["host"]["kind"] == "lens.host.api_preflight"
    assert preflight_surfaces["host"]["status"] == "blocked"
    assert preflight_surfaces["host"]["service_plan_status"] == "blocked"
    assert preflight_surfaces["summon"]["kind"] == "lens.summon.api_preflight"
    assert preflight_surfaces["summon"]["status"] == "blocked"
    assert preflight_surfaces["summon"]["global_hotkey"] == "Ctrl+Alt+Space"
    assert preflight_surfaces["summon"]["config_exists"] is True
    assert "global_hotkey_binding_disabled" in preflight_surfaces["summon"]["blockers"]
    assert "summon_authority_not_granted" in preflight_surfaces["summon"]["blockers"]
    assert preflight_surfaces["tray"]["kind"] == "lens.tray.api_preflight"
    assert preflight_surfaces["tray"]["status"] == "blocked"
    assert preflight_surfaces["tray"]["config_exists"] is True
    assert "tray_host_disabled" in preflight_surfaces["tray"]["blockers"]
    assert "tray_registration_authority_not_granted" in preflight_surfaces["tray"]["blockers"]
    assert preflight_surfaces["overlay"]["kind"] == "lens.overlay.api_preflight"
    assert preflight_surfaces["overlay"]["status"] == "blocked"
    assert preflight_surfaces["overlay"]["config_exists"] is True
    assert "overlay_window_disabled" in preflight_surfaces["overlay"]["blockers"]
    assert "overlay_control_authority_not_granted" in preflight_surfaces["overlay"]["blockers"]
    command_ids = {item["id"] for item in body["command_palette"]["commands"]}
    assert {
        "nav.briefing",
        "nav.approvals",
        "nav.orb",
        "mode.observe",
        "mode.assist",
        "mode.pilot",
        "mode.away",
        "observer.scan",
    }.issubset(command_ids)
    observer_scan = next(item for item in body["command_palette"]["commands"] if item["id"] == "observer.scan")
    assert observer_scan["route"] == "/system/observer/scan"
    assert observer_scan["method"] == "POST"
    assert observer_scan["mutates"] is True
    assert observer_scan["receipt_kind"] == "observer.scan"
    assert observer_scan["execution_authority"] is False
    activation_request_command = next(
        item for item in body["command_palette"]["commands"] if item["id"] == "lens.host.activation.request"
    )
    assert activation_request_command["route"] == "/lens/host/activation/request"
    assert activation_request_command["method"] == "POST"
    assert activation_request_command["mutates"] is True
    assert activation_request_command["write_guard"] == "system.write approval request; no launch authority"
    assert activation_request_command["execution_authority"] is False
    assert activation_request_command["approval_decision_authority"] is False
    pilot_mode = next(item for item in body["command_palette"]["commands"] if item["id"] == "mode.pilot")
    assert pilot_mode["route"] == "/system/operator_mode"
    assert pilot_mode["target_mode"] == "pilot"
    assert pilot_mode["write_guard"] == "system.write plus operator posture"
    assert body["mode_selector"]["status"] == "readback_ready"
    assert body["pilot_indicator"]["status"] == "standby"
    assert body["stage6_readiness"]["claim"] == "backend_readback_contract_only"
    assert _criterion(body, "resident_host_runtime")["status"] == "not_implemented"
    assert _criterion(body, "resident_host_runtime")["resident"] is False
    assert "lens_host_runtime_not_implemented" in _criterion(body, "resident_host_runtime")["blockers"]
    assert "resident_host_process_missing" in _criterion(body, "resident_host_runtime")["blockers"]
    assert "lens_host_service_config_missing" not in _criterion(body, "resident_host_runtime")["blockers"]
    assert _criterion(body, "hud_layer_runtime")["status"] == "readback_only"
    assert _criterion(body, "hud_layer_runtime")["resident_overlay"] is False
    assert "resident_overlay_runtime_missing" in _criterion(body, "hud_layer_runtime")["blockers"]
    assert _criterion(body, "command_palette_commands")["status"] == "readback_ready"
    assert _criterion(body, "command_palette_commands")["command_count"] == body["command_palette"]["command_total"]
    assert _criterion(body, "mode_visibility")["status"] == "readback_ready"
    assert _criterion(body, "approvals_view")["status"] == "readback_ready"
    assert _criterion(body, "incident_view")["status"] == "readback_ready"
    assert _criterion(body, "receipt_visibility")["status"] == "readback_ready"
    assert _criterion(body, "host_activation_request_boundary") == {
        "id": "host_activation_request_boundary",
        "status": "approval_request_ready",
        "evidence": ["/lens/host/activation/request", "/approvals/list?status=pending", "/lens/status"],
        "execution_authority": False,
        "approval_decision_authority": False,
        "local_process_launch_authority": False,
    }
    assert _criterion(body, "host_activation_approval_readback") == {
        "id": "host_activation_approval_readback",
        "status": "none",
        "evidence": ["/lens/host/activation", "/approvals/list?status=pending", "/lens/status"],
        "pending_count": 0,
        "approved_count": 0,
        "execution_authority": False,
        "approval_decision_authority": False,
        "local_process_launch_authority": False,
    }
    execution_preflight_criterion = _criterion(body, "host_activation_execution_preflight")
    assert execution_preflight_criterion["status"] == "blocked"
    assert execution_preflight_criterion["ready"] is False
    assert execution_preflight_criterion["evidence"] == [
        "/lens/host/activation/preflight",
        "/lens/host/activation",
        "/lens/status",
    ]
    assert "approval_id_required" in execution_preflight_criterion["blockers"]
    assert "system_write_scope_not_ready" in execution_preflight_criterion["blockers"]
    assert execution_preflight_criterion["execution_authority"] is False
    assert execution_preflight_criterion["approval_decision_authority"] is False
    assert execution_preflight_criterion["local_process_launch_authority"] is False
    execution_plan_criterion = _criterion(body, "host_activation_execution_plan")
    assert execution_plan_criterion["status"] == "blocked"
    assert execution_plan_criterion["plan_available"] is True
    assert execution_plan_criterion["execution_ready"] is False
    assert execution_plan_criterion["evidence"] == [
        "/lens/host/activation/plan",
        "/lens/host/activation/preflight",
        "/lens/status",
    ]
    assert "approval_id_required" in execution_plan_criterion["blockers"]
    assert "local_process_launch_authority_not_granted" in execution_plan_criterion["blockers"]
    assert execution_plan_criterion["execution_authority"] is False
    assert execution_plan_criterion["approval_decision_authority"] is False
    assert execution_plan_criterion["local_process_launch_authority"] is False
    execution_denial_criterion = _criterion(body, "host_activation_execution_denial_boundary")
    assert execution_denial_criterion["status"] == "blocked"
    assert execution_denial_criterion["applied"] is False
    assert execution_denial_criterion["executed"] is False
    assert execution_denial_criterion["evidence"] == [
        "/lens/host/activation/execute",
        "/lens/host/activation/plan",
        "/lens/status",
    ]
    assert "approval_id_required" in execution_denial_criterion["blockers"]
    assert "local_process_launch_authority_not_granted" in execution_denial_criterion["blockers"]
    assert execution_denial_criterion["execution_authority"] is False
    assert execution_denial_criterion["approval_decision_authority"] is False
    assert execution_denial_criterion["local_process_launch_authority"] is False
    assert execution_denial_criterion["receipt_write_authority"] is False
    assert _criterion(body, "summon_anywhere")["status"] == "not_implemented"
    assert "summon_binding_missing" in _criterion(body, "summon_anywhere")["blockers"]
    assert _criterion(body, "summon_preflight")["status"] == "blocked"
    assert _criterion(body, "summon_preflight")["global_hotkey"] == "Ctrl+Alt+Space"
    assert _criterion(body, "tray_preflight")["status"] == "blocked"
    assert _criterion(body, "overlay_preflight")["status"] == "blocked"

    hud = client.get("/lens/hud")
    assert hud.status_code == 200
    assert hud.json()["kind"] == "lens.status"
    host = client.get("/lens/host")
    assert host.status_code == 200
    host_body = host.json()
    assert host_body["kind"] == "lens.resident_host"
    assert host_body["status"] == "not_implemented"
    assert host_body["contract_status"] == "readback_ready"
    assert host_body["status_runner_present"] is True
    assert host_body["service_config_present"] is True
    assert host_body["service_readback_ready"] is True
    assert host_body["process_readback_ready"] is True
    assert host_body["resident"] is False
    assert host_body["global_hotkey"] is False
    assert host_body["summon_anywhere"] is False
    assert host_body["governance"]["local_process_launch_authority"] is False
    manifest = client.get("/lens/host/manifest")
    assert manifest.status_code == 200
    manifest_body = manifest.json()
    assert manifest_body["kind"] == "lens.host.launch_manifest"
    assert manifest_body["status"] == "status_runner_present"
    assert manifest_body["enabled"] is False
    assert manifest_body["declared_entrypoint"]["exists"] is True
    assert manifest_body["service_install"]["config_exists"] is True
    assert manifest_body["service_install"]["installable"] is False
    assert manifest_body["service_plan"] == expected_service_plan
    assert manifest_body["service_readback"]["status"] == "not_checked_by_api"
    assert manifest_body["service_readback"]["service_control_authority"] is False
    assert manifest_body["process_readback"]["status"] == "missing"
    assert manifest_body["status_command"]["executable"] is True
    assert manifest_body["candidate_command"]["executable"] is True
    assert manifest_body["governance"]["local_process_launch_authority"] is False
    assert manifest_body["governance"]["service_install_authority"] is False
    preflight_response = client.get("/lens/preflight")
    assert preflight_response.status_code == 200
    assert preflight_response.json()["kind"] == "lens.preflight"
    assert preflight_response.json()["surfaces"]["summon"] == preflight_surfaces["summon"]


def test_lens_api_observes_live_foreground_process_readback(monkeypatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    data_root = repo_root / "data"
    _write_dev_environment(repo_root)
    _write_lens_host_status_runner(repo_root)
    _write_service_manager(repo_root)
    _write_lens_preflight_scripts(repo_root)
    _write_lens_runtime_configs(repo_root)
    _write_lens_host_service_config(repo_root)
    _write_lens_host_runtime_state(data_root, pid=os.getpid())
    monkeypatch.setenv("FRANCIS_ROOT", str(repo_root))
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_ENV_PROFILE", "dev")
    monkeypatch.setenv("FRANCIS_RUN_MODE", "api")

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())
    response = client.get("/lens/status?limit=1")

    assert response.status_code == 200
    body = response.json()
    resident_host = body["resident_host"]
    process_readback = resident_host["process_readback"]
    assert process_readback["status"] == "process_observed"
    assert process_readback["state_exists"] is True
    assert process_readback["state_status"] == "foreground_running"
    assert process_readback["pid_present"] is True
    assert process_readback["pid"] == os.getpid()
    assert process_readback["process_alive"] is True
    assert process_readback["process_alive_check"] in {"posix_signal_zero", "windows_exit_code"}
    assert process_readback["blocked_reason"] == "resident_host_not_supervised"
    assert resident_host["resident"] is False
    assert resident_host["process_supervision"] is False
    assert resident_host["service_plan_ready"] is False
    assert resident_host["service_plan"]["status"] == "blocked"
    assert resident_host["service_plan"]["would_install"] is False
    assert resident_host["service_plan"]["governance"]["service_install_authority"] is False
    assert body["preflight"]["surfaces"]["tray"]["status"] == "blocked"
    assert "resident_host_process_missing" not in body["preflight"]["surfaces"]["tray"]["blockers"]
    assert body["preflight"]["surfaces"]["overlay"]["status"] == "blocked"
    assert "resident_host_process_missing" not in body["preflight"]["surfaces"]["overlay"]["blockers"]
    assert resident_host["components"][5] == {
        "id": "host_process",
        "label": "Resident host process",
        "status": "foreground_observed",
        "required_for": ["resident_presence", "startup_supervision"],
    }
    assert resident_host["supervision_readiness"]["status"] == "blocked"
    assert resident_host["supervision_readiness"]["ready"] is False
    assert resident_host["supervision_readiness"]["resident_claim_allowed"] is False
    assert resident_host["supervision_readiness"]["blocked_by"] == [
        "process_supervision_enabled",
        "service_install_authority",
        "service_control_authority",
    ]
    assert resident_host["supervision_readiness"]["prerequisites"][3]["id"] == "foreground_process_readback"
    assert resident_host["supervision_readiness"]["prerequisites"][3]["status"] == "process_observed"
    assert "resident_host_process_missing" not in resident_host["blockers"]
    assert "lens_host_runtime_not_implemented" in resident_host["blockers"]
    assert resident_host["governance"]["service_control_authority"] is False
    assert resident_host["governance"]["local_process_launch_authority"] is False

    manifest = client.get("/lens/host/manifest")
    assert manifest.status_code == 200
    manifest_body = manifest.json()
    assert manifest_body["process_readback"] == process_readback
    assert manifest_body["service_plan"] == resident_host["service_plan"]
    assert manifest_body["governance"]["local_process_launch_authority"] is False


def test_lens_status_surfaces_pending_approval_without_decision_authority(monkeypatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    data_root = repo_root / "data"
    _write_dev_environment(repo_root)
    _write_lens_host_status_runner(repo_root)
    _write_service_manager(repo_root)
    _write_lens_preflight_scripts(repo_root)
    _write_lens_runtime_configs(repo_root)
    _write_lens_host_service_config(repo_root)
    monkeypatch.setenv("FRANCIS_ROOT", str(repo_root))
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_ENV_PROFILE", "dev")
    monkeypatch.setenv("FRANCIS_RUN_MODE", "api")

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())
    approval = client.post(
        "/approvals/request",
        json={
            "action": "operations.run",
            "reason": "prove Lens pending approval readback",
            "payload": {"mission_id": "mission-lens", "risk_tier": "normal"},
        },
    )
    assert approval.status_code == 200

    response = client.get("/lens/status")

    assert response.status_code == 200
    body = response.json()
    assert body["approvals_view"]["pending_count"] == 1
    assert body["approvals_view"]["status"] == "attention"
    approvals_command = next(item for item in body["command_palette"]["commands"] if item["id"] == "nav.approvals")
    assert approvals_command["attention_count"] == 1
    assert approvals_command["route"] == "/approvals/list?status=pending"
    assert body["approvals_view"]["items"][0]["status"] == "pending"
    assert body["approvals_view"]["items"][0]["action"] == "operations.run"
    assert body["approvals_view"]["items"][0]["payload_summary"]["risk_tier"] == "normal"
    assert body["governance"]["approval_decision_authority"] is False
    approval_badge = next(item for item in body["hud"]["badges"] if item["label"] == "approvals")
    assert approval_badge["value"] == 1
    assert approval_badge["severity"] == "attention"


def test_lens_host_activation_request_requires_system_write_without_launch(monkeypatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    data_root = repo_root / "data"
    _write_dev_environment(repo_root)
    _write_lens_host_status_runner(repo_root)
    _write_service_manager(repo_root)
    _write_lens_preflight_scripts(repo_root)
    _write_lens_runtime_configs(repo_root)
    _write_lens_host_service_config(repo_root)
    monkeypatch.setenv("FRANCIS_ROOT", str(repo_root))
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_ENV_PROFILE", "dev")
    monkeypatch.setenv("FRANCIS_RUN_MODE", "api")

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())
    response = client.post(
        "/lens/host/activation/request",
        json={
            "actor": "test.lens.no_scope",
            "reason": "try to launch without scope",
            "mode": "foreground_status_session",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["status"] == "denied"
    assert body["approval_requested"] is False
    assert body["applied"] is False
    assert body["error"] == "api_permission_denied"
    assert body["governance"]["gate"] == "permission_gate"
    assert body["governance"]["required_scope"] == "system.write"
    assert body["governance"]["reason"] == "missing_scopes"
    assert body["governance"]["activation_authority"] is False
    assert body["governance"]["execution_authority"] is False
    assert body["governance"]["local_process_launch_authority"] is False
    assert client.get("/approvals/list?status=pending").json()["items"] == []
    assert not (data_root / "runtime" / "lens-host" / "status.json").exists()
    assert not (data_root / "runtime" / "lens-host" / "lens-host.pid").exists()


def test_lens_host_activation_request_creates_approval_only_receipt(monkeypatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    data_root = repo_root / "data"
    _write_dev_environment(repo_root)
    _write_lens_host_status_runner(repo_root)
    _write_service_manager(repo_root)
    _write_lens_preflight_scripts(repo_root)
    _write_lens_runtime_configs(repo_root)
    _write_lens_host_service_config(repo_root)
    monkeypatch.setenv("FRANCIS_ROOT", str(repo_root))
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_ENV_PROFILE", "dev")
    monkeypatch.setenv("FRANCIS_RUN_MODE", "api")

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())
    response = client.post(
        "/lens/host/activation/request",
        json={
            "actor": "test.system.write",
            "reason": "prove governed foreground activation request",
            "mode": "foreground_status_session",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["status"] == "approval_requested"
    assert body["approval_requested"] is True
    assert body["applied"] is False
    assert body["action"] == "lens.host.foreground_activation"
    assert body["governance"]["approval_request_write"] is True
    assert body["governance"]["activation_authority"] is False
    assert body["governance"]["execution_authority"] is False
    assert body["governance"]["approval_decision_authority"] is False
    assert body["governance"]["memory_write"] is False
    assert body["governance"]["local_process_launch_authority"] is False
    assert body["governance"]["service_install_authority"] is False
    assert body["governance"]["service_control_authority"] is False
    assert body["governance"]["runtime_mutation_authority_granted"] is False
    approval_id = str(body["approval_id"])
    assert approval_id

    pending_path = data_root / "approvals" / "pending" / f"{approval_id}.json"
    pending_payload = json.loads(pending_path.read_text(encoding="utf-8"))
    assert pending_payload["action"] == "lens.host.foreground_activation"
    assert pending_payload["reason"] == "prove governed foreground activation request"
    activation = pending_payload["payload"]
    assert activation["request_kind"] == "lens.host.activation.request"
    assert activation["mode"] == "foreground_status_session"
    assert activation["route"] == "/lens/host/activation/request"
    assert activation["host_route"] == "/lens/host"
    assert activation["manifest_route"] == "/lens/host/manifest"
    assert activation["preflight_route"] == "/lens/preflight"
    assert activation["candidate_command"]["executable"] is True
    assert activation["service_plan"]["status"] == "blocked"
    assert activation["service_plan"]["ready"] is False
    assert activation["process_readback"]["status"] == "missing"
    assert activation["process_readback"]["process_alive"] is False
    assert activation["preflight"]["status"] == "blocked"
    assert "local_process_launch_authority_not_granted" in activation["preflight"]["blockers"]
    assert "lens_host_runtime_not_implemented" in activation["blockers"]
    assert activation["governance"]["approval_request_write"] is True
    assert activation["governance"]["activation_authority"] is False
    assert activation["governance"]["execution_authority"] is False
    assert activation["governance"]["approval_decision_authority"] is False
    assert activation["governance"]["memory_write"] is False
    assert activation["governance"]["local_process_launch_authority"] is False
    assert activation["governance"]["service_install_authority"] is False
    assert activation["governance"]["service_control_authority"] is False

    listed = client.get("/approvals/list?status=pending&limit=20")
    assert listed.status_code == 200
    listed_item = next(item for item in listed.json()["items"] if item["id"] == approval_id)
    assert listed_item["action"] == "lens.host.foreground_activation"
    assert listed_item["status"] == "pending"
    assert listed_item["payload"]["request_kind"] == "lens.host.activation.request"
    assert listed_item["payload"]["governance"]["execution_authority"] is False

    lens_status = client.get("/lens/status")
    assert lens_status.status_code == 200
    status_body = lens_status.json()
    assert status_body["approvals_view"]["pending_count"] == 1
    assert status_body["resident_host"]["activation_request_route"] == "/lens/host/activation/request"
    assert not (data_root / "runtime" / "lens-host" / "status.json").exists()
    assert not (data_root / "runtime" / "lens-host" / "lens-host.pid").exists()


def test_lens_host_activation_readback_tracks_decision_without_execution(monkeypatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    data_root = repo_root / "data"
    _write_dev_environment(repo_root)
    _write_lens_host_status_runner(repo_root)
    _write_service_manager(repo_root)
    _write_lens_preflight_scripts(repo_root)
    _write_lens_runtime_configs(repo_root)
    _write_lens_host_service_config(repo_root)
    monkeypatch.setenv("FRANCIS_ROOT", str(repo_root))
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_ENV_PROFILE", "dev")
    monkeypatch.setenv("FRANCIS_RUN_MODE", "api")

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())
    requested = client.post(
        "/lens/host/activation/request",
        json={
            "actor": "test.system.write",
            "reason": "operator wants to review Lens host activation",
            "mode": "foreground_status_session",
        },
    )
    assert requested.status_code == 200
    approval_id = str(requested.json()["approval_id"])

    pending = client.get("/lens/host/activation?limit=10")
    assert pending.status_code == 200
    pending_body = pending.json()
    assert pending_body["kind"] == "lens.host.activation.readback"
    assert pending_body["status"] == "pending_review"
    assert pending_body["pending_count"] == 1
    assert pending_body["approved_count"] == 0
    assert pending_body["total_count"] == 1
    assert pending_body["latest"]["id"] == approval_id
    assert pending_body["latest"]["status"] == "pending"
    assert pending_body["latest"]["action"] == "lens.host.foreground_activation"
    assert pending_body["by_status"]["pending"][0]["id"] == approval_id
    assert pending_body["governance"]["gate"] == "lens_host_activation_readback"
    assert pending_body["governance"]["read_only_contract"] is True
    assert pending_body["governance"]["approval_request_write"] is False
    assert pending_body["governance"]["activation_authority"] is False
    assert pending_body["governance"]["execution_authority"] is False
    assert pending_body["governance"]["approval_decision_authority"] is False
    assert pending_body["governance"]["local_process_launch_authority"] is False
    assert pending_body["governance"]["next_step"] == "operator_decide_pending_lens_host_activation_request"

    pending_preflight = client.get(f"/lens/host/activation/preflight?approval_id={approval_id}&actor=test.system.write")
    assert pending_preflight.status_code == 200
    pending_preflight_body = pending_preflight.json()
    assert pending_preflight_body["kind"] == "lens.host.activation.execution_preflight"
    assert pending_preflight_body["status"] == "blocked"
    assert pending_preflight_body["ready"] is False
    assert pending_preflight_body["approval"]["found"] is True
    assert pending_preflight_body["approval"]["status"] == "pending"
    assert pending_preflight_body["approval"]["approved"] is False
    assert pending_preflight_body["permission"]["ready"] is True
    assert pending_preflight_body["operator_posture"]["ready"] is True
    assert "activation_approval_not_approved" in pending_preflight_body["blockers"]
    assert "local_process_launch_authority_not_granted" in pending_preflight_body["blockers"]
    assert pending_preflight_body["governance"]["gate"] == "lens_host_activation_execution_preflight"
    assert pending_preflight_body["governance"]["read_only_contract"] is True
    assert pending_preflight_body["governance"]["execution_authority"] is False
    assert pending_preflight_body["governance"]["local_process_launch_authority"] is False

    decided = client.post(
        "/approvals/decision",
        json={
            "id": approval_id,
            "action": "approve",
            "actor": "test.approvals.decision",
            "comment": "approved only as a review decision",
        },
    )
    assert decided.status_code == 200
    assert decided.json()["ok"] is True
    assert decided.json()["status"] == "approved"

    approved = client.get("/lens/host/activation?limit=10")
    assert approved.status_code == 200
    approved_body = approved.json()
    assert approved_body["status"] == "approved_no_execution"
    assert approved_body["pending_count"] == 0
    assert approved_body["approved_count"] == 1
    assert approved_body["rejected_count"] == 0
    assert approved_body["total_count"] == 1
    assert approved_body["latest"]["id"] == approval_id
    assert approved_body["latest"]["status"] == "approved"
    assert approved_body["latest"]["decision_actor"] == "test.approvals.decision"
    assert approved_body["by_status"]["approved"][0]["id"] == approval_id
    assert approved_body["governance"]["next_step"] == "approved_activation_requires_separate_execution_slice"
    assert approved_body["governance"]["activation_authority"] is False
    assert approved_body["governance"]["execution_authority"] is False
    assert approved_body["governance"]["local_process_launch_authority"] is False

    approved_preflight = client.get(
        f"/lens/host/activation/preflight?approval_id={approval_id}&actor=test.system.write"
    )
    assert approved_preflight.status_code == 200
    approved_preflight_body = approved_preflight.json()
    assert approved_preflight_body["status"] == "blocked"
    assert approved_preflight_body["ready"] is False
    assert approved_preflight_body["approval"]["found"] is True
    assert approved_preflight_body["approval"]["status"] == "approved"
    assert approved_preflight_body["approval"]["approved"] is True
    assert approved_preflight_body["permission"]["ready"] is True
    assert approved_preflight_body["operator_posture"]["ready"] is True
    assert approved_preflight_body["host"]["candidate_command"]["executable"] is True
    assert approved_preflight_body["host"]["process_readback"]["process_alive"] is False
    assert "activation_approval_not_approved" not in approved_preflight_body["blockers"]
    assert "system_write_scope_not_ready" not in approved_preflight_body["blockers"]
    assert "operator_posture_not_ready" not in approved_preflight_body["blockers"]
    assert "lens_preflight_blocked" in approved_preflight_body["blockers"]
    assert "local_process_launch_authority_not_granted" in approved_preflight_body["blockers"]
    assert approved_preflight_body["governance"]["execution_authority"] is False
    assert approved_preflight_body["governance"]["approval_decision_authority"] is False
    assert approved_preflight_body["governance"]["local_process_launch_authority"] is False

    approved_plan = client.get(f"/lens/host/activation/plan?approval_id={approval_id}&actor=test.system.write")
    assert approved_plan.status_code == 200
    approved_plan_body = approved_plan.json()
    assert approved_plan_body["kind"] == "lens.host.activation.execution_plan"
    assert approved_plan_body["status"] == "blocked"
    assert approved_plan_body["plan_available"] is True
    assert approved_plan_body["execution_ready"] is False
    assert approved_plan_body["preflight"]["approval"]["status"] == "approved"
    assert approved_plan_body["preflight"]["permission"]["ready"] is True
    assert approved_plan_body["preflight"]["operator_posture"]["ready"] is True
    approved_plan_steps = {step["id"]: step for step in approved_plan_body["plan"]["steps"]}
    assert approved_plan_steps["verify_exact_approval"]["status"] == "ready"
    assert approved_plan_steps["verify_actor_scope"]["status"] == "ready"
    assert approved_plan_steps["verify_operator_posture"]["status"] == "ready"
    assert approved_plan_steps["launch_foreground_status_session"]["status"] == "blocked"
    assert approved_plan_steps["launch_foreground_status_session"]["authority_granted"] is False
    assert approved_plan_steps["record_activation_receipt"]["authority_granted"] is False
    assert approved_plan_body["plan"]["would_launch_process"] is False
    assert approved_plan_body["plan"]["would_write_memory"] is False
    assert "activation_approval_not_approved" not in approved_plan_body["blockers"]
    assert "system_write_scope_not_ready" not in approved_plan_body["blockers"]
    assert "local_process_launch_authority_not_granted" in approved_plan_body["blockers"]
    assert approved_plan_body["governance"]["gate"] == "lens_host_activation_execution_plan"
    assert approved_plan_body["governance"]["read_only_contract"] is True
    assert approved_plan_body["governance"]["plan_readback_only"] is True
    assert approved_plan_body["governance"]["execution_authority"] is False
    assert approved_plan_body["governance"]["approval_decision_authority"] is False
    assert approved_plan_body["governance"]["local_process_launch_authority"] is False
    assert approved_plan_body["governance"]["receipt_write_authority"] is False

    denied_execution = client.post(
        "/lens/host/activation/execute",
        json={
            "approval_id": approval_id,
            "actor": "test.system.write",
            "reason": "operator asked to prove launch stays blocked",
        },
    )
    assert denied_execution.status_code == 200
    denied_execution_body = denied_execution.json()
    assert denied_execution_body["kind"] == "lens.host.activation.execution_denial"
    assert denied_execution_body["status"] == "denied_no_execution_authority"
    assert denied_execution_body["applied"] is False
    assert denied_execution_body["executed"] is False
    assert denied_execution_body["approval_id"] == approval_id
    assert denied_execution_body["permission"]["ready"] is True
    assert denied_execution_body["preflight"]["approval"]["approved"] is True
    assert denied_execution_body["plan"]["plan"]["would_launch_process"] is False
    assert denied_execution_body["denial"]["reason"] == "local_process_launch_authority_not_granted"
    assert denied_execution_body["denial"]["would_launch_process"] is False
    assert denied_execution_body["denial"]["would_write_receipt"] is False
    assert "activation_approval_not_approved" not in denied_execution_body["blockers"]
    assert "system_write_scope_not_ready" not in denied_execution_body["blockers"]
    assert "local_process_launch_authority_not_granted" in denied_execution_body["blockers"]
    assert denied_execution_body["governance"]["gate"] == "lens_host_activation_execution_denial"
    assert denied_execution_body["governance"]["execution_boundary"] is True
    assert denied_execution_body["governance"]["denial_boundary"] is True
    assert denied_execution_body["governance"]["execution_authority"] is False
    assert denied_execution_body["governance"]["approval_decision_authority"] is False
    assert denied_execution_body["governance"]["local_process_launch_authority"] is False
    assert denied_execution_body["governance"]["receipt_write_authority"] is False
    assert not (data_root / "runtime" / "lens-host" / "status.json").exists()
    assert not (data_root / "runtime" / "lens-host" / "lens-host.pid").exists()

    from francis.world_state.operator_mode import set_control_mode

    set_control_mode("observe", reason="prove Lens activation posture preflight", actor="test.system.write")
    observe_preflight = client.get(f"/lens/host/activation/preflight?approval_id={approval_id}&actor=test.system.write")
    assert observe_preflight.status_code == 200
    observe_preflight_body = observe_preflight.json()
    assert observe_preflight_body["status"] == "blocked"
    assert observe_preflight_body["operator_posture"]["ready"] is False
    assert observe_preflight_body["operator_posture"]["reason"] == "observe_mode_blocks_activation"
    assert "operator_posture_not_ready" in observe_preflight_body["blockers"]
    assert observe_preflight_body["governance"]["execution_authority"] is False

    lens_status = client.get("/lens/status")
    assert lens_status.status_code == 200
    status_body = lens_status.json()
    activation_state = status_body["resident_host"]["activation_state"]
    assert activation_state["status"] == "approved_no_execution"
    assert activation_state["approved_count"] == 1
    assert activation_state["pending_count"] == 0
    assert _criterion(status_body, "host_activation_approval_readback")["status"] == "approved_no_execution"
    assert _criterion(status_body, "host_activation_approval_readback")["approved_count"] == 1
    assert _criterion(status_body, "host_activation_approval_readback")["pending_count"] == 0
    assert not (data_root / "runtime" / "lens-host" / "status.json").exists()
    assert not (data_root / "runtime" / "lens-host" / "lens-host.pid").exists()
