from __future__ import annotations

import json
import os
from datetime import UTC, datetime
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
  "blocked_reason": "lens_summon_binding_not_implemented",
  "required_before_enable": [
    "resident_host_process",
    "tray_presence",
    "overlay_window",
    "global_hotkey_binding",
    "summon_binding"
  ]
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
  "blocked_reason": "lens_tray_presence_not_implemented",
  "required_before_enable": [
    "resident_host_process",
    "tray_icon",
    "user_session_presence",
    "global_hotkey_binding",
    "overlay_window",
    "summon_binding"
  ]
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
  "blocked_reason": "lens_overlay_window_not_implemented",
  "required_before_enable": [
    "resident_host_process",
    "tray_presence",
    "overlay_window",
    "always_on_top_policy",
    "global_hotkey_binding",
    "summon_binding"
  ]
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
  "persistent_supervision_enabled": false,
  "process_restart_authority": false,
  "supervision_readiness_gate": true,
  "supervision_mode": "windows_service",
  "supervision_ready": false,
  "supervision_blocked_reason": "resident_supervision_disabled",
  "process_supervision_readback": true,
  "service_status_readback": true,
  "service_control_authority": false,
  "receipt_write_authority": false,
  "resident_claim_authority": false,
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


def _write_lens_host_supervisor_state(
    data_root: Path,
    *,
    observed_pid: int,
    status: str = "supervised_session_completed",
    updated_at: str | None = None,
) -> None:
    runtime_root = data_root / "runtime" / "lens-host-supervisor"
    runtime_root.mkdir(parents=True, exist_ok=True)
    observed_at = updated_at or datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    (runtime_root / "status.json").write_text(
        json.dumps(
            {
                "kind": "lens.host.supervisor_state",
                "status": status,
                "mode": "supervise_once",
                "observed_pid": observed_pid,
                "observed_state": "foreground_stopped",
                "restarted_process": False,
                "managed_service": False,
                "updated_at": observed_at,
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
    closure = body["stage6_readiness"]["closure_readback"]
    assert closure["kind"] == "lens.stage6.closure_readback"
    assert closure["status"] == "blocked"
    assert closure["ready_to_close"] is False
    assert closure["criteria_total"] == 5
    assert closure["ready_total"] == 2
    assert closure["blocked_total"] == 3
    assert closure["ready_criteria"] == ["mode_visibility", "pilot_visibility_groundwork"]
    assert closure["blocked_criteria"] == [
        "summon_anywhere",
        "helpful_not_noisy",
        "system_resident_presence",
    ]
    assert closure["next_smallest_truthful_gap"] in {
        "resident_host_supervision_boundary",
        "supervised_resident_runtime_boundary",
        "resident_presence_authority_boundary",
    }
    closure_criteria = {item["id"]: item for item in closure["criteria"]}
    assert closure_criteria["summon_anywhere"]["ready"] is False
    assert "summon_anywhere_missing" in closure_criteria["summon_anywhere"]["blockers"]
    assert closure_criteria["mode_visibility"]["ready"] is True
    assert closure_criteria["pilot_visibility_groundwork"]["ready"] is True
    assert closure_criteria["system_resident_presence"]["ready"] is False
    assert closure["governance"]["execution_authority"] is False
    assert closure["governance"]["resident_claim_authority"] is False
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
    resident_surface = body["resident_surface"]
    assert resident_surface["kind"] == "lens.resident_surface.readback"
    assert resident_surface["status"] == "blocked"
    assert resident_surface["contract_status"] == "readback_ready"
    assert resident_surface["availability"] == "backend_readback_only"
    assert resident_surface["route"] == "/lens/resident-surface"
    assert resident_surface["status_route"] == "/lens/status"
    assert resident_surface["activation_route"] == "/lens/resident-surface/activation"
    assert resident_surface["host_route"] == "/lens/host"
    assert resident_surface["hud_route"] == "/lens/hud"
    assert resident_surface["content_contract_ready"] is True
    assert resident_surface["foreground_runtime_observed"] is False
    assert resident_surface["resident_surface_ready"] is False
    assert resident_surface["resident_claim_allowed"] is False
    assert resident_surface["resident_overlay_runtime"] is False
    assert resident_surface["resident_host"] is False
    assert resident_surface["always_on_top_overlay"] is False
    assert resident_surface["summon_anywhere"] is False
    assert resident_surface["tray_presence"] is False
    assert resident_surface["approval_queue"]["route"] == "/approvals/list?status=pending"
    assert resident_surface["mission_feed"]["route"] == "/continuity/briefing"
    assert resident_surface["incident_feed"]["reactor_route"] == "/reactor/operator_visibility/summary"
    assert resident_surface["command_palette"]["route"] == "/lens/status"
    assert resident_surface["command_palette"]["summon_anywhere"] is False
    assert resident_surface["resident_runtime"] == {
        "preflight_route": "/lens/resident-runtime/preflight",
        "policy_route": "/lens/resident-runtime/policy",
        "authority_grant_route": "/lens/resident-runtime/authority-grant",
        "plan_route": "/lens/resident-runtime/plan",
        "execute_route": "/lens/resident-runtime/execute",
        "ready": False,
    }
    resident_surface_runtime = resident_surface["resident_surface_runtime"]
    assert resident_surface_runtime["kind"] == "lens.resident_surface.runtime_readback"
    assert resident_surface_runtime["status"] == "missing"
    assert resident_surface_runtime["foreground_runtime_observed"] is False
    assert resident_surface_runtime["runtime_ready"] is False
    assert resident_surface_runtime["resident_surface_ready"] is False
    assert resident_surface_runtime["resident_claim_allowed"] is False
    assert resident_surface_runtime["blockers"] == ["resident_surface_runtime_missing"]
    assert resident_surface_runtime["governance"]["execution_authority"] is False
    assert resident_surface_runtime["governance"]["process_supervision_authority"] is False
    surface_sections = {item["id"]: item for item in resident_surface["surface_sections"]}
    assert surface_sections["mode_and_scope"]["route"] == "/system/operator_mode"
    assert surface_sections["hud_summary"]["route"] == "/lens/hud"
    assert surface_sections["approval_queue"]["route"] == "/approvals/list?status=pending"
    assert surface_sections["mission_feed"]["route"] == "/continuity/briefing"
    assert surface_sections["incident_feed"]["route"] == "/system/observer"
    assert surface_sections["command_palette"]["route"] == "/lens/status"
    assert surface_sections["resident_host"]["route"] == "/lens/host"
    assert surface_sections["activation_boundary"]["route"] == "/lens/resident-surface/activation"
    assert resident_surface["activation_boundary"]["kind"] == "lens.resident_surface.activation_boundary"
    assert resident_surface["enablement_gates"]["summon"]["kind"] == "lens.summon.enablement_gate"
    assert resident_surface["enablement_gates"]["tray"]["kind"] == "lens.tray.enablement_gate"
    assert resident_surface["enablement_gates"]["overlay"]["kind"] == "lens.overlay.enablement_gate"
    assert "resident_surface_runtime_missing" in resident_surface["blockers"]
    assert "resident_surface_missing" not in resident_surface["blockers"]
    assert "resident_overlay_runtime_missing" in resident_surface["blockers"]
    assert "resident_host_process_missing" in resident_surface["blockers"]
    assert resident_surface["next_smallest_truthful_gap"] == "resident_surface_runtime_missing"
    assert resident_surface["governance"] == {
        "gate": "lens_resident_surface_readback",
        "read_only_contract": True,
        "execution_authority": False,
        "approval_decision_authority": False,
        "memory_write": False,
        "overlay_control_authority": False,
        "summon_authority": False,
        "capture_authority": False,
        "local_process_launch_authority": False,
        "process_supervision_authority": False,
        "service_control_authority": False,
        "hotkey_registration_authority": False,
        "tray_registration_authority": False,
        "resident_claim_authority": False,
        "mutation_authority_granted": False,
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
        "denials_route": "/lens/host/activation/denials",
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
            "denials_route": "/lens/host/activation/denials",
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
    assert activation_denial["governance"]["denial_receipt_write_authority"] is False
    assert activation_denial["receipt_written"] is False
    assert activation_denial["receipt_route"] == "/lens/host/activation/denials"
    assert activation_denial["receipt"] == {}
    assert resident_host["resident_runtime_denial_route"] == "/lens/resident-runtime/execute"
    resident_runtime_denial = resident_host["resident_runtime_denial"]
    assert resident_runtime_denial["kind"] == "lens.resident_runtime.activation.execution_denial"
    assert resident_runtime_denial["status"] == "blocked"
    assert resident_runtime_denial["applied"] is False
    assert resident_runtime_denial["executed"] is False
    assert resident_runtime_denial["route"] == "/lens/resident-runtime/execute"
    assert resident_runtime_denial["plan_route"] == "/lens/resident-runtime/plan"
    assert resident_runtime_denial["receipt_route"] == "/lens/resident-runtime/denials"
    assert resident_runtime_denial["surface_route"] == "/lens/resident-surface/activation"
    assert resident_runtime_denial["denial"]["reason"] == "resident_runtime_execution_authority_not_granted"
    assert resident_runtime_denial["denial"]["would_launch_process"] is False
    assert resident_runtime_denial["denial"]["would_supervise_process"] is False
    assert resident_runtime_denial["denial"]["would_restart_process"] is False
    assert resident_runtime_denial["denial"]["would_install_service"] is False
    assert resident_runtime_denial["denial"]["would_start_service"] is False
    assert resident_runtime_denial["denial"]["would_register_tray"] is False
    assert resident_runtime_denial["denial"]["would_register_hotkey"] is False
    assert resident_runtime_denial["denial"]["would_open_overlay"] is False
    assert resident_runtime_denial["denial"]["would_write_memory"] is False
    assert resident_runtime_denial["denial"]["would_write_receipt"] is False
    assert resident_runtime_denial["denial"]["would_claim_resident"] is False
    assert resident_runtime_denial["denial"]["denial_receipt_written"] is False
    assert resident_runtime_denial["receipt_written"] is False
    assert resident_runtime_denial["receipt"] == {}
    assert "approval_id_required" in resident_runtime_denial["blockers"]
    assert "system_write_scope_not_ready" in resident_runtime_denial["blockers"]
    assert "resident_runtime_execution_authority_not_granted" in resident_runtime_denial["blockers"]
    assert "process_supervision_authority_not_granted" in resident_runtime_denial["blockers"]
    assert "service_control_authority_not_granted" in resident_runtime_denial["blockers"]
    assert "tray_registration_authority_not_granted" in resident_runtime_denial["blockers"]
    assert "hotkey_registration_authority_not_granted" in resident_runtime_denial["blockers"]
    assert "overlay_control_authority_not_granted" in resident_runtime_denial["blockers"]
    assert resident_runtime_denial["governance"]["gate"] == "lens_resident_runtime_activation_execution_denial"
    assert resident_runtime_denial["governance"]["execution_boundary"] is True
    assert resident_runtime_denial["governance"]["resident_runtime_boundary"] is True
    assert resident_runtime_denial["governance"]["execution_authority"] is False
    assert resident_runtime_denial["governance"]["approval_decision_authority"] is False
    assert resident_runtime_denial["governance"]["local_process_launch_authority"] is False
    assert resident_runtime_denial["governance"]["process_supervision_authority"] is False
    assert resident_runtime_denial["governance"]["service_control_authority"] is False
    assert resident_runtime_denial["governance"]["hotkey_registration_authority"] is False
    assert resident_runtime_denial["governance"]["overlay_control_authority"] is False
    assert resident_runtime_denial["governance"]["memory_write"] is False
    assert resident_runtime_denial["governance"]["receipt_write_authority"] is False
    assert resident_runtime_denial["governance"]["resident_claim_authority"] is False
    assert resident_host["resident_runtime_denial_receipts_route"] == "/lens/resident-runtime/denials"
    resident_runtime_denial_receipts = resident_host["resident_runtime_denial_receipts"]
    assert resident_runtime_denial_receipts["kind"] == "lens.resident_runtime.activation.denial_receipts"
    assert resident_runtime_denial_receipts["status"] == "empty"
    assert resident_runtime_denial_receipts["route"] == "/lens/resident-runtime/denials"
    assert resident_runtime_denial_receipts["execute_route"] == "/lens/resident-runtime/execute"
    assert resident_runtime_denial_receipts["plan_route"] == "/lens/resident-runtime/plan"
    assert resident_runtime_denial_receipts["total"] == 0
    assert resident_runtime_denial_receipts["latest"] is None
    assert resident_runtime_denial_receipts["items"] == []
    assert resident_runtime_denial_receipts["governance"]["gate"] == (
        "lens_resident_runtime_activation_denial_receipts_readback"
    )
    assert resident_runtime_denial_receipts["governance"]["read_only_contract"] is True
    assert resident_runtime_denial_receipts["governance"]["denial_receipt_write_authority"] is False
    assert resident_runtime_denial_receipts["governance"]["execution_authority"] is False
    assert resident_runtime_denial_receipts["governance"]["approval_decision_authority"] is False
    assert resident_runtime_denial_receipts["governance"]["process_supervision_authority"] is False
    assert resident_runtime_denial_receipts["governance"]["service_control_authority"] is False
    assert resident_runtime_denial_receipts["governance"]["memory_write"] is False
    assert resident_host["activation_denial_receipts_route"] == "/lens/host/activation/denials"
    activation_denial_receipts = resident_host["activation_denial_receipts"]
    assert activation_denial_receipts["kind"] == "lens.host.activation.denial_receipts"
    assert activation_denial_receipts["status"] == "empty"
    assert activation_denial_receipts["route"] == "/lens/host/activation/denials"
    assert activation_denial_receipts["execute_route"] == "/lens/host/activation/execute"
    assert activation_denial_receipts["total"] == 0
    assert activation_denial_receipts["latest"] is None
    assert activation_denial_receipts["items"] == []
    assert activation_denial_receipts["governance"]["gate"] == "lens_host_activation_denial_receipts_readback"
    assert activation_denial_receipts["governance"]["read_only_contract"] is True
    assert activation_denial_receipts["governance"]["denial_receipt_write_authority"] is False
    assert activation_denial_receipts["governance"]["execution_authority"] is False
    assert activation_denial_receipts["governance"]["approval_decision_authority"] is False
    assert activation_denial_receipts["governance"]["local_process_launch_authority"] is False
    assert activation_denial_receipts["governance"]["memory_write"] is False
    assert resident_host["supervision_authority_denial_receipts_route"] == ("/lens/host/supervision/authority/denials")
    supervision_authority_denial_receipts = resident_host["supervision_authority_denial_receipts"]
    assert supervision_authority_denial_receipts["kind"] == "lens.host.supervision_authority.denial_receipts"
    assert supervision_authority_denial_receipts["status"] == "empty"
    assert supervision_authority_denial_receipts["route"] == "/lens/host/supervision/authority/denials"
    assert supervision_authority_denial_receipts["authority_route"] == "/lens/host/supervision/authority"
    assert supervision_authority_denial_receipts["total"] == 0
    assert supervision_authority_denial_receipts["latest"] is None
    assert supervision_authority_denial_receipts["items"] == []
    assert supervision_authority_denial_receipts["governance"]["gate"] == (
        "lens_host_supervision_authority_denial_receipts_readback"
    )
    assert supervision_authority_denial_receipts["governance"]["read_only_contract"] is True
    assert supervision_authority_denial_receipts["governance"]["denial_receipt_write_authority"] is False
    assert supervision_authority_denial_receipts["governance"]["execution_authority"] is False
    assert supervision_authority_denial_receipts["governance"]["approval_decision_authority"] is False
    assert supervision_authority_denial_receipts["governance"]["process_supervision_authority"] is False
    assert supervision_authority_denial_receipts["governance"]["service_control_authority"] is False
    assert supervision_authority_denial_receipts["governance"]["memory_write"] is False
    assert resident_host["supervision_authority_grant_receipts_route"] == "/lens/host/supervision/authority/grants"
    supervision_authority_grant_receipts = resident_host["supervision_authority_grant_receipts"]
    assert supervision_authority_grant_receipts["kind"] == "lens.host.supervision_authority.grant_receipts"
    assert supervision_authority_grant_receipts["status"] == "empty"
    assert supervision_authority_grant_receipts["route"] == "/lens/host/supervision/authority/grants"
    assert supervision_authority_grant_receipts["authority_route"] == "/lens/host/supervision/authority"
    assert supervision_authority_grant_receipts["total"] == 0
    assert supervision_authority_grant_receipts["latest"] is None
    assert supervision_authority_grant_receipts["active_latest"] is None
    assert supervision_authority_grant_receipts["authority_granted"] is False
    assert supervision_authority_grant_receipts["items"] == []
    assert supervision_authority_grant_receipts["governance"]["gate"] == (
        "lens_host_supervision_authority_grant_receipts_readback"
    )
    assert supervision_authority_grant_receipts["governance"]["read_only_contract"] is True
    assert supervision_authority_grant_receipts["governance"]["execution_authority"] is False
    assert supervision_authority_grant_receipts["governance"]["approval_decision_authority"] is False
    assert supervision_authority_grant_receipts["governance"]["process_supervision_authority"] is False
    assert supervision_authority_grant_receipts["governance"]["service_control_authority"] is False
    assert supervision_authority_grant_receipts["governance"]["memory_write"] is False
    assert resident_host["supervision_authority_readiness_route"] == "/lens/host/supervision/authority/readiness"
    supervision_authority_readiness = resident_host["supervision_authority_readiness"]
    assert supervision_authority_readiness["kind"] == "lens.host.supervision_authority.readiness_audit"
    assert supervision_authority_readiness["status"] == "blocked"
    assert supervision_authority_readiness["audit_status"] == "complete"
    assert supervision_authority_readiness["route"] == "/lens/host/supervision/authority/readiness"
    assert supervision_authority_readiness["authority_route"] == "/lens/host/supervision/authority"
    assert supervision_authority_readiness["denials_route"] == "/lens/host/supervision/authority/denials"
    assert supervision_authority_readiness["grants_route"] == "/lens/host/supervision/authority/grants"
    assert supervision_authority_readiness["ready"] is False
    assert supervision_authority_readiness["preflight_ready"] is True
    assert supervision_authority_readiness["authority_ready"] is False
    assert supervision_authority_readiness["supervision_ready"] is False
    assert supervision_authority_readiness["resident_claim_allowed"] is False
    assert supervision_authority_readiness["boundary_observed"] is True
    assert supervision_authority_readiness["denial_receipt_readback_ready"] is True
    assert supervision_authority_readiness["grant_receipt_readback_ready"] is True
    assert supervision_authority_readiness["receipt_count"] == 0
    assert supervision_authority_readiness["latest_receipt_id"] == ""
    assert supervision_authority_readiness["grant_receipt_count"] == 0
    assert supervision_authority_readiness["latest_grant_receipt_id"] == ""
    assert supervision_authority_readiness["active_grant_receipt_id"] == ""
    assert supervision_authority_readiness["requirements_total"] >= 11
    assert supervision_authority_readiness["requirements_blocked_total"] >= 6
    supervision_authority_readiness_requirements = {
        item["id"]: item for item in supervision_authority_readiness["requirements"]
    }
    assert supervision_authority_readiness_requirements["host_supervision_authority_preflight"]["ready"] is True
    assert supervision_authority_readiness_requirements["host_supervision_authority_denial_boundary"]["ready"] is True
    assert supervision_authority_readiness_requirements["host_supervision_authority_denial_receipts"]["ready"] is True
    assert supervision_authority_readiness_requirements["host_supervision_authority_grant_receipts"]["ready"] is True
    assert supervision_authority_readiness_requirements["authority_grant_implementation"]["ready"] is True
    assert "actor_scope" in supervision_authority_readiness["blocked_requirements"]
    assert "process_supervision_authority" in supervision_authority_readiness["blocked_requirements"]
    assert "service_control_authority" in supervision_authority_readiness["blocked_requirements"]
    assert "resident_claim_authority" in supervision_authority_readiness["blocked_requirements"]
    assert "authority_grant_implementation" not in supervision_authority_readiness["blocked_requirements"]
    assert "system_write_scope_not_ready" in supervision_authority_readiness["blockers"]
    assert "host_supervision_authority_grant_not_implemented" not in supervision_authority_readiness["blockers"]
    assert "process_supervision_authority_not_granted" in supervision_authority_readiness["blockers"]
    assert supervision_authority_readiness["governance"]["gate"] == "lens_host_supervision_authority_readiness_audit"
    assert supervision_authority_readiness["governance"]["read_only_contract"] is True
    assert supervision_authority_readiness["governance"]["audit_only"] is True
    assert supervision_authority_readiness["governance"]["preflight_only"] is True
    assert supervision_authority_readiness["governance"]["authority_grant_boundary"] is True
    assert supervision_authority_readiness["governance"]["execution_authority"] is False
    assert supervision_authority_readiness["governance"]["approval_decision_authority"] is False
    assert supervision_authority_readiness["governance"]["local_process_launch_authority"] is False
    assert supervision_authority_readiness["governance"]["process_supervision_authority"] is False
    assert supervision_authority_readiness["governance"]["process_restart_authority"] is False
    assert supervision_authority_readiness["governance"]["service_install_authority"] is False
    assert supervision_authority_readiness["governance"]["service_control_authority"] is False
    assert supervision_authority_readiness["governance"]["memory_write"] is False
    assert supervision_authority_readiness["governance"]["denial_receipt_write_authority"] is False
    assert supervision_authority_readiness["governance"]["resident_claim_authority"] is False
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
    expected_supervisor_readback = {
        "status": "missing",
        "readback_ready": True,
        "runtime_state_path": "data/runtime/lens-host-supervisor/status.json",
        "state_exists": False,
        "state_status": "",
        "mode": "",
        "observed_pid": 0,
        "observed_state": "",
        "updated_at": "",
        "state_age_seconds": None,
        "freshness_window_seconds": 900,
        "freshness_status": "missing",
        "state_stale": False,
        "fresh_readback": False,
        "bounded_supervisor_observed": False,
        "observation_completed": False,
        "supervised_session_completed": False,
        "fresh_bounded_supervisor_observed": False,
        "fresh_supervised_session_completed": False,
        "restarted_process": False,
        "managed_service": False,
        "resident_supervised_runtime": False,
        "resident_claim_allowed": False,
        "process_supervision_authority": False,
        "process_restart_authority": False,
        "service_control_authority": False,
        "blocked_reason": "resident_host_supervisor_state_missing",
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
    assert resident_host["supervisor_readback"] == expected_supervisor_readback
    assert resident_host["supervisor_readback_ready"] is True
    assert resident_host["supervisor_freshness_status"] == "missing"
    assert resident_host["supervisor_state_age_seconds"] is None
    assert resident_host["supervisor_state_stale"] is False
    assert resident_host["fresh_supervisor_readback"] is False
    assert resident_host["bounded_supervisor_observed"] is False
    assert resident_host["supervised_session_completed"] is False
    assert resident_host["fresh_bounded_supervisor_observed"] is False
    assert resident_host["fresh_supervised_session_completed"] is False
    assert resident_host["resident_supervised_runtime"] is False
    expected_supervision_readiness = {
        "status": "blocked",
        "ready": False,
        "mode": "windows_service",
        "service_manager": "scripts/service-install.ps1",
        "service_manager_exists": True,
        "process_supervision_enabled": False,
        "persistent_supervision_enabled": False,
        "process_supervision_authority": False,
        "process_restart_authority": False,
        "service_install_authority": False,
        "service_control_authority": False,
        "receipt_write_authority": False,
        "resident_claim_authority": False,
        "authority_grant_active": False,
        "authority_grant_route": "/lens/host/supervision/authority",
        "authority_grants_route": "/lens/host/supervision/authority/grants",
        "authority_grant": {},
        "resident_claim_allowed": False,
        "next_allowed_transition": "foreground_status_session_only",
        "blocked_by": [
            "process_supervision_enabled",
            "persistent_supervision_enabled",
            "process_restart_authority",
            "service_install_authority",
            "service_control_authority",
            "receipt_write_authority",
            "resident_claim_authority",
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
                "id": "persistent_supervision_enabled",
                "label": "Persistent supervision enabled",
                "ready": False,
                "status": "blocked",
                "reason": "persistent_supervision_disabled",
            },
            {
                "id": "process_restart_authority",
                "label": "Process restart authority",
                "ready": False,
                "status": "blocked",
                "reason": "process_restart_authority_false",
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
            {
                "id": "receipt_write_authority",
                "label": "Resident supervision receipt authority",
                "ready": False,
                "status": "blocked",
                "reason": "receipt_write_authority_false",
            },
            {
                "id": "resident_claim_authority",
                "label": "Resident claim authority",
                "ready": False,
                "status": "blocked",
                "reason": "resident_claim_authority_false",
            },
        ],
    }
    assert resident_host["supervision_readiness"] == expected_supervision_readiness
    assert resident_host["supervision_gate_route"] == "/lens/host/supervision"
    supervision_gate = resident_host["supervision_gate"]
    assert supervision_gate["kind"] == "lens.host.supervision_enablement_gate"
    assert supervision_gate["status"] == "blocked"
    assert supervision_gate["route"] == "/lens/host/supervision"
    assert supervision_gate["host_route"] == "/lens/host"
    assert supervision_gate["manifest_route"] == "/lens/host/manifest"
    assert supervision_gate["ready"] is False
    assert supervision_gate["supervision_ready"] is False
    assert supervision_gate["resident_claim_allowed"] is False
    assert supervision_gate["resident_host_process"] is False
    assert supervision_gate["foreground_process_observed"] is False
    assert supervision_gate["resident_host_process_state"] == "missing"
    assert supervision_gate["resident_host_process_blocker"] == "resident_host_process_missing"
    assert supervision_gate["supervisor_readback_ready"] is True
    assert supervision_gate["supervisor_freshness_status"] == "missing"
    assert supervision_gate["supervisor_state_age_seconds"] is None
    assert supervision_gate["supervisor_state_stale"] is False
    assert supervision_gate["fresh_supervisor_readback"] is False
    assert supervision_gate["bounded_supervisor_observed"] is False
    assert supervision_gate["supervised_session_completed"] is False
    assert supervision_gate["fresh_bounded_supervisor_observed"] is False
    assert supervision_gate["fresh_supervised_session_completed"] is False
    assert supervision_gate["resident_supervised_runtime"] is False
    assert supervision_gate["resident_host_supervised"] is False
    assert supervision_gate["service_installed"] is False
    assert supervision_gate["service_managed"] is False
    assert supervision_gate["process_supervision_enabled"] is False
    assert supervision_gate["persistent_supervision_enabled"] is False
    assert supervision_gate["process_restart_authority"] is False
    assert supervision_gate["process_restart_supported"] is False
    assert supervision_gate["service_plan_ready"] is False
    assert supervision_gate["would_install_service"] is False
    assert supervision_gate["would_start_service"] is False
    assert supervision_gate["would_supervise_process"] is False
    assert supervision_gate["would_restart_process"] is False
    assert supervision_gate["next_allowed_transition"] == "foreground_status_session_only"
    assert "resident_host_process_missing" in supervision_gate["blockers"]
    assert "process_supervision_enabled" in supervision_gate["blockers"]
    assert "persistent_supervision_enabled" in supervision_gate["blockers"]
    assert "process_restart_authority" in supervision_gate["blockers"]
    assert "service_install_authority" in supervision_gate["blockers"]
    assert "service_control_authority" in supervision_gate["blockers"]
    assert "receipt_write_authority" in supervision_gate["blockers"]
    assert "resident_claim_authority" in supervision_gate["blockers"]
    assert "process_restart_authority_false" in supervision_gate["blockers"]
    assert "service_install_authority_false" in supervision_gate["blockers"]
    assert "service_control_authority_false" in supervision_gate["blockers"]
    assert "receipt_write_authority_false" in supervision_gate["blockers"]
    assert "resident_claim_authority_false" in supervision_gate["blockers"]
    assert "lens_host_runtime_not_implemented" in supervision_gate["blockers"]
    assert supervision_gate["prerequisites"] == expected_supervision_readiness["prerequisites"]
    assert supervision_gate["process_readback"] == resident_host["process_readback"]
    assert supervision_gate["supervisor_readback"] == expected_supervisor_readback
    assert supervision_gate["service_readback"] == resident_host["service_readback"]
    assert supervision_gate["service_plan"] == expected_service_plan
    assert supervision_gate["supervision_readiness"] == expected_supervision_readiness
    assert supervision_gate["governance"] == {
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
    }
    assert resident_host["supervision_authority_preflight_route"] == "/lens/host/supervision/authority"
    supervision_authority = resident_host["supervision_authority_preflight"]
    assert supervision_authority["kind"] == "lens.host.supervision_authority.preflight"
    assert supervision_authority["status"] == "blocked"
    assert supervision_authority["route"] == "/lens/host/supervision/authority"
    assert supervision_authority["host_route"] == "/lens/host"
    assert supervision_authority["supervision_route"] == "/lens/host/supervision"
    assert supervision_authority["manifest_route"] == "/lens/host/manifest"
    assert supervision_authority["ready"] is False
    assert supervision_authority["preflight_ready"] is True
    assert supervision_authority["authority_ready"] is False
    assert supervision_authority["supervision_ready"] is False
    assert supervision_authority["resident_claim_allowed"] is False
    assert supervision_authority["would_supervise_process"] is False
    assert supervision_authority["would_restart_process"] is False
    assert supervision_authority["would_install_service"] is False
    assert supervision_authority["would_start_service"] is False
    assert supervision_authority["requirements_total"] >= 10
    assert supervision_authority["requirements_blocked_total"] >= 5
    assert "process_supervision_authority" in supervision_authority["blocked_requirements"]
    assert "process_restart_authority" in supervision_authority["blocked_requirements"]
    assert "service_install_authority" in supervision_authority["blocked_requirements"]
    assert "service_control_authority" in supervision_authority["blocked_requirements"]
    assert "resident_claim_authority" in supervision_authority["blocked_requirements"]
    assert "receipt_write_authority" in supervision_authority["blocked_requirements"]
    assert "resident_host_supervision_authority_not_granted" in supervision_authority["blockers"]
    assert "process_supervision_authority_not_granted" in supervision_authority["blockers"]
    assert "receipt_write_authority_not_granted" in supervision_authority["blockers"]
    assert supervision_authority["governance"] == {
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
    }
    assert resident_host["supervision_authority_denial_route"] == "/lens/host/supervision/authority"
    supervision_authority_denial = resident_host["supervision_authority_denial"]
    assert supervision_authority_denial["kind"] == "lens.host.supervision_authority.denial"
    assert supervision_authority_denial["status"] == "blocked"
    assert supervision_authority_denial["route"] == "/lens/host/supervision/authority"
    assert supervision_authority_denial["method"] == "POST"
    assert supervision_authority_denial["preflight_route"] == "/lens/host/supervision/authority"
    assert supervision_authority_denial["boundary_ready"] is True
    assert supervision_authority_denial["ready"] is False
    assert supervision_authority_denial["applied"] is False
    assert supervision_authority_denial["executed"] is False
    assert supervision_authority_denial["authority_granted"] is False
    assert supervision_authority_denial["supervision_ready"] is False
    assert supervision_authority_denial["authority_ready"] is False
    assert supervision_authority_denial["resident_claim_allowed"] is False
    assert supervision_authority_denial["permission"]["ready"] is False
    assert "system_write_scope_not_ready" in supervision_authority_denial["blockers"]
    assert "host_supervision_authority_grant_not_implemented" not in supervision_authority_denial["blockers"]
    assert "process_supervision_authority_not_granted" in supervision_authority_denial["blockers"]
    assert supervision_authority_denial["denial"] == {
        "reason": "host_supervision_authority_not_ready",
        "message": (
            "Lens resident host process supervision authority is denied until an exact approved "
            "host supervision authority request and system.write actor scope are present."
        ),
        "would_grant_process_supervision_authority": False,
        "would_grant_process_restart_authority": False,
        "would_grant_service_install_authority": False,
        "would_grant_service_control_authority": False,
        "would_grant_local_process_launch_authority": False,
        "would_supervise_process": False,
        "would_restart_process": False,
        "would_install_service": False,
        "would_start_service": False,
        "would_claim_resident": False,
        "would_write_receipt": False,
        "would_write_memory": False,
        "denial_receipt_written": False,
    }
    assert supervision_authority_denial["receipt_written"] is False
    assert supervision_authority_denial["receipt_route"] == "/lens/host/supervision/authority/denials"
    assert supervision_authority_denial["receipt"] == {}
    assert supervision_authority_denial["governance"]["gate"] == "lens_host_supervision_authority_denial_boundary"
    assert supervision_authority_denial["governance"]["authority_grant_boundary"] is True
    assert supervision_authority_denial["governance"]["denial_boundary"] is True
    assert supervision_authority_denial["governance"]["process_supervision_authority"] is False
    assert supervision_authority_denial["governance"]["process_restart_authority"] is False
    assert supervision_authority_denial["governance"]["service_install_authority"] is False
    assert supervision_authority_denial["governance"]["service_control_authority"] is False
    assert supervision_authority_denial["governance"]["receipt_write_authority"] is False
    assert supervision_authority_denial["governance"]["denial_receipt_write_authority"] is False
    assert supervision_authority_denial["governance"]["resident_claim_authority"] is False
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
        "host_supervisor_readback",
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
    assert launch_manifest["supervisor_readback"] == expected_supervisor_readback
    assert launch_manifest["supervision_readiness"] == expected_supervision_readiness
    assert launch_manifest["foreground_session"] == resident_host["foreground_session"]
    assert [item["id"] for item in launch_manifest["required_bindings"]] == [
        "api_status",
        "host_status_runner",
        "host_service_config",
        "host_service_readback",
        "host_service_plan",
        "host_process_readback",
        "host_supervisor_readback",
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
    host_preflight_groups = preflight_surfaces["host"]["blocker_groups"]
    assert "lens_host_runtime_not_implemented" in host_preflight_groups["runtime"]
    assert "resident_host_process_missing" in host_preflight_groups["process_readback"]
    assert "service_control_authority_false" in host_preflight_groups["service_plan"]
    assert "service_control_authority_false" in host_preflight_groups["authority"]
    assert "tray_host_missing" in host_preflight_groups["surface_dependencies"]
    assert preflight_surfaces["summon"]["kind"] == "lens.summon.api_preflight"
    assert preflight_surfaces["summon"]["status"] == "blocked"
    assert preflight_surfaces["summon"]["global_hotkey"] == "Ctrl+Alt+Space"
    assert preflight_surfaces["summon"]["config_exists"] is True
    assert preflight_surfaces["summon"]["acceptance_criterion"] == "summon_anywhere"
    assert preflight_surfaces["summon"]["next_smallest_truthful_gap"] == "summon_anywhere_blockers"
    assert preflight_surfaces["summon"]["required_before_enable"] == [
        "resident_host_process",
        "tray_presence",
        "overlay_window",
        "global_hotkey_binding",
        "summon_binding",
    ]
    assert "global_hotkey_binding_disabled" in preflight_surfaces["summon"]["blockers"]
    assert "summon_authority_not_granted" in preflight_surfaces["summon"]["blockers"]
    summon_preflight_groups = preflight_surfaces["summon"]["blocker_groups"]
    assert summon_preflight_groups["global_hotkey_binding"] == [
        "global_hotkey_binding_disabled",
        "global_hotkey_registration_disabled",
        "hotkey_registration_authority_not_granted",
    ]
    assert summon_preflight_groups["summon_binding"] == [
        "lens_summon_binding_not_implemented",
        "summon_authority_not_granted",
    ]
    assert summon_preflight_groups["surface_dependencies"] == [
        "tray_host_missing",
        "overlay_window_missing",
    ]
    assert preflight_surfaces["tray"]["kind"] == "lens.tray.api_preflight"
    assert preflight_surfaces["tray"]["status"] == "blocked"
    assert preflight_surfaces["tray"]["config_exists"] is True
    assert preflight_surfaces["tray"]["required_before_enable"] == [
        "resident_host_process",
        "tray_icon",
        "user_session_presence",
        "global_hotkey_binding",
        "overlay_window",
        "summon_binding",
    ]
    assert "tray_host_disabled" in preflight_surfaces["tray"]["blockers"]
    assert "tray_registration_authority_not_granted" in preflight_surfaces["tray"]["blockers"]
    assert preflight_surfaces["overlay"]["kind"] == "lens.overlay.api_preflight"
    assert preflight_surfaces["overlay"]["status"] == "blocked"
    assert preflight_surfaces["overlay"]["config_exists"] is True
    assert preflight_surfaces["overlay"]["required_before_enable"] == [
        "resident_host_process",
        "tray_presence",
        "overlay_window",
        "always_on_top_policy",
        "global_hotkey_binding",
        "summon_binding",
    ]
    assert "overlay_window_disabled" in preflight_surfaces["overlay"]["blockers"]
    assert "overlay_control_authority_not_granted" in preflight_surfaces["overlay"]["blockers"]
    summon_enablement_gate = body["summon_enablement_gate"]
    assert summon_enablement_gate["kind"] == "lens.summon.enablement_gate"
    assert summon_enablement_gate["status"] == "blocked"
    assert summon_enablement_gate["route"] == "/lens/summon"
    assert summon_enablement_gate["preflight_route"] == "/lens/preflight"
    assert summon_enablement_gate["status_route"] == "/lens/status"
    assert summon_enablement_gate["host_route"] == "/lens/host"
    assert summon_enablement_gate["ready"] is False
    assert summon_enablement_gate["summon_anywhere"] is False
    assert summon_enablement_gate["acceptance_criterion"] == "summon_anywhere"
    assert summon_enablement_gate["next_smallest_truthful_gap"] == "summon_anywhere_blockers"
    assert summon_enablement_gate["summon_binding_ready"] is False
    assert summon_enablement_gate["resident_host_ready"] is False
    assert summon_enablement_gate["tray_ready"] is False
    assert summon_enablement_gate["overlay_ready"] is False
    assert summon_enablement_gate["global_hotkey"] == "Ctrl+Alt+Space"
    assert summon_enablement_gate["binding_scope"] == "global"
    assert summon_enablement_gate["palette_route"] == "/lens/status"
    assert summon_enablement_gate["required_before_enable"] == [
        "resident_host_process",
        "tray_presence",
        "overlay_window",
        "global_hotkey_binding",
        "summon_binding",
    ]
    assert "global_hotkey_binding_disabled" in summon_enablement_gate["blockers"]
    assert "global_hotkey_binding_missing" in summon_enablement_gate["blockers"]
    assert "summon_authority_not_granted" in summon_enablement_gate["blockers"]
    assert "summon_binding_missing" in summon_enablement_gate["blockers"]
    assert "resident_host_process_missing" in summon_enablement_gate["blockers"]
    summon_gate_groups = summon_enablement_gate["blocker_groups"]
    assert "resident_host_process_missing" in summon_gate_groups["resident_host"]
    assert "tray_host_missing" in summon_gate_groups["tray_presence"]
    assert "overlay_window_missing" in summon_gate_groups["overlay_window"]
    assert "global_hotkey_binding_missing" in summon_gate_groups["global_hotkey_binding"]
    assert "summon_binding_missing" in summon_gate_groups["summon_binding"]
    assert summon_enablement_gate["summon_preflight"] == preflight_surfaces["summon"]
    assert summon_enablement_gate["surface_dependencies"]["host"]["ready"] is False
    assert summon_enablement_gate["surface_dependencies"]["tray"]["status"] == "blocked"
    assert summon_enablement_gate["surface_dependencies"]["overlay"]["status"] == "blocked"
    assert summon_enablement_gate["governance"] == {
        "read_only_contract": True,
        "execution_authority": False,
        "approval_decision_authority": False,
        "memory_write": False,
        "overlay_control_authority": False,
        "summon_authority": False,
        "capture_authority": False,
        "new_sensing_authority": False,
        "local_process_launch_authority": False,
        "mutation_authority_granted": False,
        "hotkey_registration_authority": False,
        "tray_registration_authority": False,
    }
    tray_enablement_gate = body["tray_enablement_gate"]
    assert tray_enablement_gate["kind"] == "lens.tray.enablement_gate"
    assert tray_enablement_gate["status"] == "blocked"
    assert tray_enablement_gate["route"] == "/lens/tray"
    assert tray_enablement_gate["preflight_route"] == "/lens/preflight"
    assert tray_enablement_gate["status_route"] == "/lens/status"
    assert tray_enablement_gate["host_route"] == "/lens/host"
    assert tray_enablement_gate["ready"] is False
    assert tray_enablement_gate["tray_presence"] is False
    assert tray_enablement_gate["tray_preflight_ready"] is False
    assert tray_enablement_gate["resident_host_ready"] is False
    assert tray_enablement_gate["summon_binding_ready"] is False
    assert tray_enablement_gate["overlay_ready"] is False
    assert tray_enablement_gate["tray_host_enabled"] is False
    assert tray_enablement_gate["tray_icon_enabled"] is False
    assert tray_enablement_gate["notification_supported"] is False
    assert tray_enablement_gate["presence_name"] == "Francis Lens Tray Presence"
    assert tray_enablement_gate["tray_scope"] == "user_session"
    assert tray_enablement_gate["required_before_enable"] == [
        "resident_host_process",
        "tray_icon",
        "user_session_presence",
        "global_hotkey_binding",
        "overlay_window",
        "summon_binding",
    ]
    assert "tray_host_disabled" in tray_enablement_gate["blockers"]
    assert "tray_icon_disabled" in tray_enablement_gate["blockers"]
    assert "tray_registration_authority_not_granted" in tray_enablement_gate["blockers"]
    assert "tray_icon_authority_not_granted" in tray_enablement_gate["blockers"]
    assert "notification_authority_not_granted" in tray_enablement_gate["blockers"]
    assert "resident_host_process_missing" in tray_enablement_gate["blockers"]
    assert tray_enablement_gate["tray_preflight"] == preflight_surfaces["tray"]
    assert tray_enablement_gate["surface_dependencies"]["host"]["ready"] is False
    assert tray_enablement_gate["surface_dependencies"]["summon"]["status"] == "blocked"
    assert tray_enablement_gate["surface_dependencies"]["overlay"]["status"] == "blocked"
    assert tray_enablement_gate["governance"] == {
        "read_only_contract": True,
        "execution_authority": False,
        "approval_decision_authority": False,
        "memory_write": False,
        "overlay_control_authority": False,
        "summon_authority": False,
        "capture_authority": False,
        "new_sensing_authority": False,
        "local_process_launch_authority": False,
        "mutation_authority_granted": False,
        "service_control_authority": False,
        "tray_registration_authority": False,
        "tray_icon_authority": False,
        "notification_authority": False,
        "hotkey_registration_authority": False,
    }
    overlay_enablement_gate = body["overlay_enablement_gate"]
    assert overlay_enablement_gate["kind"] == "lens.overlay.enablement_gate"
    assert overlay_enablement_gate["status"] == "blocked"
    assert overlay_enablement_gate["route"] == "/lens/overlay"
    assert overlay_enablement_gate["preflight_route"] == "/lens/preflight"
    assert overlay_enablement_gate["status_route"] == "/lens/status"
    assert overlay_enablement_gate["host_route"] == "/lens/host"
    assert overlay_enablement_gate["ready"] is False
    assert overlay_enablement_gate["overlay_window"] is False
    assert overlay_enablement_gate["overlay_preflight_ready"] is False
    assert overlay_enablement_gate["resident_host_ready"] is False
    assert overlay_enablement_gate["summon_binding_ready"] is False
    assert overlay_enablement_gate["tray_presence_ready"] is False
    assert overlay_enablement_gate["overlay_enabled"] is False
    assert overlay_enablement_gate["window_enabled"] is False
    assert overlay_enablement_gate["always_on_top"] is False
    assert overlay_enablement_gate["dock_supported"] is False
    assert overlay_enablement_gate["focus_supported"] is False
    assert overlay_enablement_gate["click_through_supported"] is False
    assert overlay_enablement_gate["capture_supported"] is False
    assert overlay_enablement_gate["overlay_name"] == "Francis Lens Overlay"
    assert overlay_enablement_gate["overlay_scope"] == "user_session"
    assert overlay_enablement_gate["required_before_enable"] == [
        "resident_host_process",
        "tray_presence",
        "overlay_window",
        "always_on_top_policy",
        "global_hotkey_binding",
        "summon_binding",
    ]
    assert "overlay_window_disabled" in overlay_enablement_gate["blockers"]
    assert "always_on_top_disabled" in overlay_enablement_gate["blockers"]
    assert "overlay_control_authority_not_granted" in overlay_enablement_gate["blockers"]
    assert "window_management_authority_not_granted" in overlay_enablement_gate["blockers"]
    assert "capture_authority_not_granted" in overlay_enablement_gate["blockers"]
    assert "resident_host_process_missing" in overlay_enablement_gate["blockers"]
    assert overlay_enablement_gate["overlay_preflight"] == preflight_surfaces["overlay"]
    assert overlay_enablement_gate["surface_dependencies"]["host"]["ready"] is False
    assert overlay_enablement_gate["surface_dependencies"]["summon"]["status"] == "blocked"
    assert overlay_enablement_gate["surface_dependencies"]["tray"]["status"] == "blocked"
    assert overlay_enablement_gate["governance"] == {
        "read_only_contract": True,
        "execution_authority": False,
        "approval_decision_authority": False,
        "memory_write": False,
        "overlay_control_authority": False,
        "summon_authority": False,
        "capture_authority": False,
        "new_sensing_authority": False,
        "local_process_launch_authority": False,
        "mutation_authority_granted": False,
        "window_management_authority": False,
        "service_control_authority": False,
        "tray_registration_authority": False,
        "hotkey_registration_authority": False,
    }
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
    resident_runtime_authority_request_command = next(
        item
        for item in body["command_palette"]["commands"]
        if item["id"] == "lens.resident_runtime.execution_authority.request"
    )
    assert resident_runtime_authority_request_command["route"] == "/lens/resident-runtime/authority-grant/request"
    assert resident_runtime_authority_request_command["method"] == "POST"
    assert resident_runtime_authority_request_command["mutates"] is True
    assert resident_runtime_authority_request_command["execution_authority"] is False
    assert resident_runtime_authority_request_command["approval_decision_authority"] is False
    pilot_mode = next(item for item in body["command_palette"]["commands"] if item["id"] == "mode.pilot")
    assert pilot_mode["route"] == "/system/operator_mode"
    assert pilot_mode["target_mode"] == "pilot"
    assert pilot_mode["write_guard"] == "system.write plus operator posture"
    assert body["mode_selector"]["status"] == "readback_ready"
    assert body["pilot_indicator"]["status"] == "standby"
    assert body["receipts"]["lens_resident_surface_route"] == "/lens/resident-surface"
    assert body["receipts"]["lens_resident_surface_activation_route"] == "/lens/resident-surface/activation"
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
    runtime_preflight_criterion = _criterion(body, "resident_runtime_authority_grant_preflight")
    assert runtime_preflight_criterion["status"] == "blocked"
    assert runtime_preflight_criterion["ready"] is False
    assert runtime_preflight_criterion["grant_ready"] is False
    assert runtime_preflight_criterion["authority_grant_ready"] is False
    assert runtime_preflight_criterion["runtime_ready"] is False
    assert runtime_preflight_criterion["resident_claim_allowed"] is False
    assert runtime_preflight_criterion["evidence"] == [
        "/lens/resident-runtime/preflight",
        "/lens/host/activation/preflight",
        "/lens/status",
    ]
    assert "approval_id_required" in runtime_preflight_criterion["blockers"]
    assert "resident_runtime_authority_grant_not_implemented" not in runtime_preflight_criterion["blockers"]
    assert "resident_runtime_execution_authority_not_granted" in runtime_preflight_criterion["blockers"]
    assert "process_supervision_authority_not_granted" in runtime_preflight_criterion["blockers"]
    assert runtime_preflight_criterion["execution_authority"] is False
    assert runtime_preflight_criterion["approval_decision_authority"] is False
    assert runtime_preflight_criterion["local_process_launch_authority"] is False
    assert runtime_preflight_criterion["process_supervision_authority"] is False
    assert runtime_preflight_criterion["process_restart_authority"] is False
    assert runtime_preflight_criterion["service_install_authority"] is False
    assert runtime_preflight_criterion["service_control_authority"] is False
    assert runtime_preflight_criterion["tray_registration_authority"] is False
    assert runtime_preflight_criterion["hotkey_registration_authority"] is False
    assert runtime_preflight_criterion["overlay_control_authority"] is False
    assert runtime_preflight_criterion["memory_write"] is False
    assert runtime_preflight_criterion["receipt_write_authority"] is False
    assert runtime_preflight_criterion["resident_claim_authority"] is False
    runtime_policy_criterion = _criterion(body, "resident_runtime_execution_policy_contract")
    assert runtime_policy_criterion["status"] == "readback_ready"
    assert runtime_policy_criterion["ready"] is True
    assert runtime_policy_criterion["policy_contract_ready"] is True
    assert runtime_policy_criterion["execution_policy_ready"] is True
    assert runtime_policy_criterion["grant_ready"] is False
    assert runtime_policy_criterion["runtime_ready"] is False
    assert runtime_policy_criterion["resident_claim_allowed"] is False
    assert runtime_policy_criterion["evidence"] == [
        "/lens/resident-runtime/policy",
        "/lens/resident-runtime/preflight",
        "/lens/resident-runtime/authority-grant",
        "/lens/status",
    ]
    assert "resident_runtime_execution_authority_not_granted" in runtime_policy_criterion["blockers"]
    assert "resident_runtime_authority_grant_not_implemented" not in runtime_policy_criterion["blockers"]
    assert runtime_policy_criterion["execution_authority"] is False
    assert runtime_policy_criterion["approval_decision_authority"] is False
    assert runtime_policy_criterion["local_process_launch_authority"] is False
    assert runtime_policy_criterion["process_supervision_authority"] is False
    assert runtime_policy_criterion["process_restart_authority"] is False
    assert runtime_policy_criterion["service_install_authority"] is False
    assert runtime_policy_criterion["service_control_authority"] is False
    assert runtime_policy_criterion["tray_registration_authority"] is False
    assert runtime_policy_criterion["hotkey_registration_authority"] is False
    assert runtime_policy_criterion["overlay_control_authority"] is False
    assert runtime_policy_criterion["memory_write"] is False
    assert runtime_policy_criterion["receipt_write_authority"] is False
    assert runtime_policy_criterion["resident_claim_authority"] is False
    runtime_authority_request_criterion = _criterion(body, "resident_runtime_execution_authority_request_readback")
    assert runtime_authority_request_criterion["status"] == "none"
    assert runtime_authority_request_criterion["evidence"] == [
        "/lens/resident-runtime/authority-grant/requests",
        "/lens/resident-runtime/authority-grant/request",
        "/lens/status",
    ]
    assert runtime_authority_request_criterion["pending_count"] == 0
    assert runtime_authority_request_criterion["approved_count"] == 0
    assert runtime_authority_request_criterion["receipt_count"] == 0
    assert runtime_authority_request_criterion["latest_approval_id"] == ""
    assert runtime_authority_request_criterion["authority_granted"] is False
    assert runtime_authority_request_criterion["resident_claim_allowed"] is False
    assert runtime_authority_request_criterion["execution_authority"] is False
    assert runtime_authority_request_criterion["approval_decision_authority"] is False
    assert runtime_authority_request_criterion["process_supervision_authority"] is False
    assert runtime_authority_request_criterion["service_control_authority"] is False
    assert runtime_authority_request_criterion["memory_write"] is False
    assert runtime_authority_request_criterion["resident_claim_authority"] is False
    runtime_authority_grant_criterion = _criterion(body, "resident_runtime_execution_authority_grant_boundary")
    assert runtime_authority_grant_criterion["status"] == "blocked"
    assert runtime_authority_grant_criterion["boundary_ready"] is True
    assert runtime_authority_grant_criterion["applied"] is False
    assert runtime_authority_grant_criterion["executed"] is False
    assert runtime_authority_grant_criterion["authority_granted"] is False
    assert runtime_authority_grant_criterion["grant_ready"] is False
    assert runtime_authority_grant_criterion["authority_grant_ready"] is False
    assert runtime_authority_grant_criterion["runtime_ready"] is False
    assert runtime_authority_grant_criterion["resident_claim_allowed"] is False
    assert runtime_authority_grant_criterion["evidence"] == [
        "/lens/resident-runtime/authority-grant",
        "/lens/resident-runtime/authority-grant/grants",
        "/lens/resident-runtime/policy",
        "/lens/status",
    ]
    assert "approval_id_required" in runtime_authority_grant_criterion["blockers"]
    assert "resident_runtime_authority_grant_not_implemented" not in runtime_authority_grant_criterion["blockers"]
    assert "resident_runtime_execution_authority_not_granted" not in runtime_authority_grant_criterion["blockers"]
    assert runtime_authority_grant_criterion["execution_authority"] is False
    assert runtime_authority_grant_criterion["approval_decision_authority"] is False
    assert runtime_authority_grant_criterion["local_process_launch_authority"] is False
    assert runtime_authority_grant_criterion["process_supervision_authority"] is False
    assert runtime_authority_grant_criterion["process_restart_authority"] is False
    assert runtime_authority_grant_criterion["service_install_authority"] is False
    assert runtime_authority_grant_criterion["service_control_authority"] is False
    assert runtime_authority_grant_criterion["tray_registration_authority"] is False
    assert runtime_authority_grant_criterion["hotkey_registration_authority"] is False
    assert runtime_authority_grant_criterion["overlay_control_authority"] is False
    assert runtime_authority_grant_criterion["memory_write"] is False
    assert runtime_authority_grant_criterion["receipt_write_authority"] is False
    assert runtime_authority_grant_criterion["resident_claim_authority"] is False
    runtime_authority_grant_receipts_criterion = _criterion(body, "resident_runtime_authority_grant_receipt_readback")
    assert runtime_authority_grant_receipts_criterion["status"] == "empty"
    assert runtime_authority_grant_receipts_criterion["evidence"] == [
        "/lens/resident-runtime/authority-grant/grants",
        "/lens/resident-runtime/authority-grant",
        "/lens/status",
    ]
    assert runtime_authority_grant_receipts_criterion["receipt_count"] == 0
    assert runtime_authority_grant_receipts_criterion["latest_receipt_id"] == ""
    assert runtime_authority_grant_receipts_criterion["active_receipt_id"] == ""
    assert runtime_authority_grant_receipts_criterion["authority_granted"] is False
    assert runtime_authority_grant_receipts_criterion["resident_runtime_execution_authority"] is False
    assert runtime_authority_grant_receipts_criterion["execution_authority"] is False
    assert runtime_authority_grant_receipts_criterion["approval_decision_authority"] is False
    assert runtime_authority_grant_receipts_criterion["process_supervision_authority"] is False
    assert runtime_authority_grant_receipts_criterion["service_control_authority"] is False
    assert runtime_authority_grant_receipts_criterion["memory_write"] is False
    assert runtime_authority_grant_receipts_criterion["receipt_write_authority"] is False
    runtime_authority_grant_denials_criterion = _criterion(
        body, "resident_runtime_authority_grant_denial_receipt_readback"
    )
    assert runtime_authority_grant_denials_criterion["status"] == "empty"
    assert runtime_authority_grant_denials_criterion["evidence"] == [
        "/lens/resident-runtime/authority-grant/denials",
        "/lens/resident-runtime/authority-grant",
        "/lens/status",
    ]
    assert runtime_authority_grant_denials_criterion["receipt_count"] == 0
    assert runtime_authority_grant_denials_criterion["latest_receipt_id"] == ""
    assert runtime_authority_grant_denials_criterion["execution_authority"] is False
    assert runtime_authority_grant_denials_criterion["approval_decision_authority"] is False
    assert runtime_authority_grant_denials_criterion["process_supervision_authority"] is False
    assert runtime_authority_grant_denials_criterion["service_control_authority"] is False
    assert runtime_authority_grant_denials_criterion["memory_write"] is False
    assert runtime_authority_grant_denials_criterion["denial_receipt_write_authority"] is False
    assert runtime_authority_grant_denials_criterion["receipt_write_authority"] is False
    runtime_authority_grant_readiness_criterion = _criterion(body, "resident_runtime_authority_grant_readiness_audit")
    assert runtime_authority_grant_readiness_criterion["status"] == "blocked"
    assert runtime_authority_grant_readiness_criterion["audit_status"] == "complete"
    assert runtime_authority_grant_readiness_criterion["ready"] is False
    assert runtime_authority_grant_readiness_criterion["grant_ready"] is False
    assert runtime_authority_grant_readiness_criterion["runtime_ready"] is False
    assert runtime_authority_grant_readiness_criterion["resident_claim_allowed"] is False
    assert runtime_authority_grant_readiness_criterion["boundary_observed"] is True
    assert runtime_authority_grant_readiness_criterion["grant_receipt_readback_ready"] is True
    assert runtime_authority_grant_readiness_criterion["denial_receipt_readback_ready"] is True
    assert runtime_authority_grant_readiness_criterion["evidence"] == [
        "/lens/resident-runtime/authority-grant/readiness",
        "/lens/resident-runtime/authority-grant/grants",
        "/lens/resident-runtime/authority-grant/denials",
        "/lens/resident-runtime/authority-grant",
        "/lens/resident-runtime/policy",
        "/lens/resident-runtime/plan",
        "/lens/status",
    ]
    assert runtime_authority_grant_readiness_criterion["requirements_total"] >= 10
    assert runtime_authority_grant_readiness_criterion["requirements_blocked_total"] >= 5
    assert (
        "exact_resident_runtime_execution_authority_approval"
        in runtime_authority_grant_readiness_criterion["blocked_requirements"]
    )
    assert "resident_runtime_execution_authority" in runtime_authority_grant_readiness_criterion["blocked_requirements"]
    assert "authority_grant_implementation" not in runtime_authority_grant_readiness_criterion["blocked_requirements"]
    assert (
        "resident_runtime_authority_grant_not_implemented"
        not in runtime_authority_grant_readiness_criterion["blockers"]
    )
    assert runtime_authority_grant_readiness_criterion["execution_authority"] is False
    assert runtime_authority_grant_readiness_criterion["approval_decision_authority"] is False
    assert runtime_authority_grant_readiness_criterion["process_supervision_authority"] is False
    assert runtime_authority_grant_readiness_criterion["service_control_authority"] is False
    assert runtime_authority_grant_readiness_criterion["memory_write"] is False
    assert runtime_authority_grant_readiness_criterion["receipt_write_authority"] is False
    host_supervision_authority_criterion = _criterion(body, "resident_host_supervision_authority_preflight")
    assert host_supervision_authority_criterion["status"] == "blocked"
    assert host_supervision_authority_criterion["evidence"] == [
        "/lens/host/supervision/authority",
        "/lens/host/supervision",
        "/lens/host/manifest",
        "/lens/status",
    ]
    assert host_supervision_authority_criterion["ready"] is False
    assert host_supervision_authority_criterion["preflight_ready"] is True
    assert host_supervision_authority_criterion["authority_ready"] is False
    assert host_supervision_authority_criterion["resident_claim_allowed"] is False
    assert host_supervision_authority_criterion["requirements_total"] >= 10
    assert host_supervision_authority_criterion["requirements_blocked_total"] >= 5
    assert "process_supervision_authority" in host_supervision_authority_criterion["blocked_requirements"]
    assert "service_control_authority" in host_supervision_authority_criterion["blocked_requirements"]
    assert "resident_host_supervision_authority_not_granted" in host_supervision_authority_criterion["blockers"]
    assert host_supervision_authority_criterion["execution_authority"] is False
    assert host_supervision_authority_criterion["approval_decision_authority"] is False
    assert host_supervision_authority_criterion["local_process_launch_authority"] is False
    assert host_supervision_authority_criterion["process_supervision_authority"] is False
    assert host_supervision_authority_criterion["process_restart_authority"] is False
    assert host_supervision_authority_criterion["service_install_authority"] is False
    assert host_supervision_authority_criterion["service_control_authority"] is False
    assert host_supervision_authority_criterion["memory_write"] is False
    assert host_supervision_authority_criterion["receipt_write_authority"] is False
    host_supervision_denial_criterion = _criterion(body, "resident_host_supervision_authority_denial_boundary")
    assert host_supervision_denial_criterion["status"] == "blocked"
    assert host_supervision_denial_criterion["evidence"] == [
        "/lens/host/supervision/authority",
        "/lens/host/supervision",
        "/lens/host/manifest",
        "/lens/status",
    ]
    assert host_supervision_denial_criterion["boundary_ready"] is True
    assert host_supervision_denial_criterion["applied"] is False
    assert host_supervision_denial_criterion["executed"] is False
    assert host_supervision_denial_criterion["authority_granted"] is False
    assert host_supervision_denial_criterion["ready"] is False
    assert host_supervision_denial_criterion["authority_ready"] is False
    assert host_supervision_denial_criterion["resident_claim_allowed"] is False
    assert "host_supervision_authority_grant_not_implemented" not in host_supervision_denial_criterion["blockers"]
    assert "process_supervision_authority_not_granted" in host_supervision_denial_criterion["blockers"]
    assert host_supervision_denial_criterion["execution_authority"] is False
    assert host_supervision_denial_criterion["approval_decision_authority"] is False
    assert host_supervision_denial_criterion["local_process_launch_authority"] is False
    assert host_supervision_denial_criterion["process_supervision_authority"] is False
    assert host_supervision_denial_criterion["process_restart_authority"] is False
    assert host_supervision_denial_criterion["service_install_authority"] is False
    assert host_supervision_denial_criterion["service_control_authority"] is False
    assert host_supervision_denial_criterion["memory_write"] is False
    assert host_supervision_denial_criterion["receipt_write_authority"] is False
    assert host_supervision_denial_criterion["denial_receipt_write_authority"] is False
    host_supervision_denial_receipts_criterion = _criterion(
        body, "resident_host_supervision_authority_denial_receipt_readback"
    )
    assert host_supervision_denial_receipts_criterion["status"] == "empty"
    assert host_supervision_denial_receipts_criterion["evidence"] == [
        "/lens/host/supervision/authority/denials",
        "/lens/host/supervision/authority",
        "/lens/status",
    ]
    assert host_supervision_denial_receipts_criterion["receipt_count"] == 0
    assert host_supervision_denial_receipts_criterion["latest_receipt_id"] == ""
    assert host_supervision_denial_receipts_criterion["execution_authority"] is False
    assert host_supervision_denial_receipts_criterion["approval_decision_authority"] is False
    assert host_supervision_denial_receipts_criterion["local_process_launch_authority"] is False
    assert host_supervision_denial_receipts_criterion["process_supervision_authority"] is False
    assert host_supervision_denial_receipts_criterion["process_restart_authority"] is False
    assert host_supervision_denial_receipts_criterion["service_install_authority"] is False
    assert host_supervision_denial_receipts_criterion["service_control_authority"] is False
    assert host_supervision_denial_receipts_criterion["memory_write"] is False
    assert host_supervision_denial_receipts_criterion["denial_receipt_write_authority"] is False
    assert host_supervision_denial_receipts_criterion["receipt_write_authority"] is False
    host_supervision_grant_receipts_criterion = _criterion(
        body, "resident_host_supervision_authority_grant_receipt_readback"
    )
    assert host_supervision_grant_receipts_criterion["status"] == "empty"
    assert host_supervision_grant_receipts_criterion["evidence"] == [
        "/lens/host/supervision/authority/grants",
        "/lens/host/supervision/authority",
        "/lens/status",
    ]
    assert host_supervision_grant_receipts_criterion["receipt_count"] == 0
    assert host_supervision_grant_receipts_criterion["latest_receipt_id"] == ""
    assert host_supervision_grant_receipts_criterion["active_receipt_id"] == ""
    assert host_supervision_grant_receipts_criterion["authority_granted"] is False
    assert host_supervision_grant_receipts_criterion["execution_authority"] is False
    assert host_supervision_grant_receipts_criterion["approval_decision_authority"] is False
    assert host_supervision_grant_receipts_criterion["local_process_launch_authority"] is False
    assert host_supervision_grant_receipts_criterion["process_supervision_authority"] is False
    assert host_supervision_grant_receipts_criterion["service_control_authority"] is False
    assert host_supervision_grant_receipts_criterion["memory_write"] is False
    assert host_supervision_grant_receipts_criterion["denial_receipt_write_authority"] is False
    assert host_supervision_grant_receipts_criterion["receipt_write_authority"] is False
    host_supervision_readiness_criterion = _criterion(body, "resident_host_supervision_authority_readiness_audit")
    assert host_supervision_readiness_criterion["status"] == "blocked"
    assert host_supervision_readiness_criterion["audit_status"] == "complete"
    assert host_supervision_readiness_criterion["evidence"] == [
        "/lens/host/supervision/authority/readiness",
        "/lens/host/supervision/authority/grants",
        "/lens/host/supervision/authority/denials",
        "/lens/host/supervision/authority",
        "/lens/host/supervision",
        "/lens/host/manifest",
        "/lens/status",
    ]
    assert host_supervision_readiness_criterion["ready"] is False
    assert host_supervision_readiness_criterion["preflight_ready"] is True
    assert host_supervision_readiness_criterion["authority_ready"] is False
    assert host_supervision_readiness_criterion["supervision_ready"] is False
    assert host_supervision_readiness_criterion["resident_claim_allowed"] is False
    assert host_supervision_readiness_criterion["boundary_observed"] is True
    assert host_supervision_readiness_criterion["denial_receipt_readback_ready"] is True
    assert host_supervision_readiness_criterion["grant_receipt_readback_ready"] is True
    assert host_supervision_readiness_criterion["receipt_count"] == 0
    assert host_supervision_readiness_criterion["latest_receipt_id"] == ""
    assert host_supervision_readiness_criterion["grant_receipt_count"] == 0
    assert host_supervision_readiness_criterion["latest_grant_receipt_id"] == ""
    assert host_supervision_readiness_criterion["active_grant_receipt_id"] == ""
    assert host_supervision_readiness_criterion["requirements_total"] >= 11
    assert host_supervision_readiness_criterion["requirements_blocked_total"] >= 6
    assert "authority_grant_implementation" not in host_supervision_readiness_criterion["blocked_requirements"]
    assert "process_supervision_authority" in host_supervision_readiness_criterion["blocked_requirements"]
    assert "service_control_authority" in host_supervision_readiness_criterion["blocked_requirements"]
    assert "host_supervision_authority_grant_not_implemented" not in host_supervision_readiness_criterion["blockers"]
    assert host_supervision_readiness_criterion["execution_authority"] is False
    assert host_supervision_readiness_criterion["approval_decision_authority"] is False
    assert host_supervision_readiness_criterion["local_process_launch_authority"] is False
    assert host_supervision_readiness_criterion["process_supervision_authority"] is False
    assert host_supervision_readiness_criterion["process_restart_authority"] is False
    assert host_supervision_readiness_criterion["service_install_authority"] is False
    assert host_supervision_readiness_criterion["service_control_authority"] is False
    assert host_supervision_readiness_criterion["memory_write"] is False
    assert host_supervision_readiness_criterion["receipt_write_authority"] is False
    assert host_supervision_readiness_criterion["denial_receipt_write_authority"] is False
    runtime_plan_criterion = _criterion(body, "resident_runtime_activation_plan")
    assert runtime_plan_criterion["status"] == "blocked"
    assert runtime_plan_criterion["plan_available"] is True
    assert runtime_plan_criterion["runtime_ready"] is False
    assert runtime_plan_criterion["resident_claim_allowed"] is False
    assert runtime_plan_criterion["evidence"] == [
        "/lens/resident-runtime/plan",
        "/lens/host/supervision",
        "/lens/summon",
        "/lens/tray",
        "/lens/overlay",
        "/lens/status",
    ]
    assert "resident_runtime_execution_authority_not_granted" in runtime_plan_criterion["blockers"]
    assert "process_supervision_authority_not_granted" in runtime_plan_criterion["blockers"]
    assert "tray_registration_authority_not_granted" in runtime_plan_criterion["blockers"]
    assert "hotkey_registration_authority_not_granted" in runtime_plan_criterion["blockers"]
    assert "overlay_control_authority_not_granted" in runtime_plan_criterion["blockers"]
    assert runtime_plan_criterion["execution_authority"] is False
    assert runtime_plan_criterion["approval_decision_authority"] is False
    assert runtime_plan_criterion["local_process_launch_authority"] is False
    assert runtime_plan_criterion["process_supervision_authority"] is False
    assert runtime_plan_criterion["service_install_authority"] is False
    assert runtime_plan_criterion["service_control_authority"] is False
    assert runtime_plan_criterion["tray_registration_authority"] is False
    assert runtime_plan_criterion["hotkey_registration_authority"] is False
    assert runtime_plan_criterion["overlay_control_authority"] is False
    assert runtime_plan_criterion["memory_write"] is False
    runtime_boundary_criterion = _criterion(body, "resident_runtime_authority_boundary")
    assert runtime_boundary_criterion["status"] == "blocked"
    assert runtime_boundary_criterion["applied"] is False
    assert runtime_boundary_criterion["executed"] is False
    assert runtime_boundary_criterion["evidence"] == [
        "/lens/resident-runtime/execute",
        "/lens/resident-runtime/plan",
        "/lens/status",
    ]
    assert "approval_id_required" in runtime_boundary_criterion["blockers"]
    assert "resident_runtime_execution_authority_not_granted" in runtime_boundary_criterion["blockers"]
    assert "process_supervision_authority_not_granted" in runtime_boundary_criterion["blockers"]
    assert "service_control_authority_not_granted" in runtime_boundary_criterion["blockers"]
    assert "tray_registration_authority_not_granted" in runtime_boundary_criterion["blockers"]
    assert "hotkey_registration_authority_not_granted" in runtime_boundary_criterion["blockers"]
    assert "overlay_control_authority_not_granted" in runtime_boundary_criterion["blockers"]
    assert runtime_boundary_criterion["execution_authority"] is False
    assert runtime_boundary_criterion["approval_decision_authority"] is False
    assert runtime_boundary_criterion["local_process_launch_authority"] is False
    assert runtime_boundary_criterion["process_supervision_authority"] is False
    assert runtime_boundary_criterion["service_control_authority"] is False
    assert runtime_boundary_criterion["tray_registration_authority"] is False
    assert runtime_boundary_criterion["hotkey_registration_authority"] is False
    assert runtime_boundary_criterion["overlay_control_authority"] is False
    assert runtime_boundary_criterion["memory_write"] is False
    assert runtime_boundary_criterion["receipt_write_authority"] is False
    assert runtime_boundary_criterion["resident_claim_authority"] is False
    runtime_denial_receipts_criterion = _criterion(body, "resident_runtime_activation_denial_receipt_readback")
    assert runtime_denial_receipts_criterion["status"] == "empty"
    assert runtime_denial_receipts_criterion["evidence"] == [
        "/lens/resident-runtime/denials",
        "/lens/resident-runtime/execute",
        "/lens/status",
    ]
    assert runtime_denial_receipts_criterion["receipt_count"] == 0
    assert runtime_denial_receipts_criterion["latest_receipt_id"] == ""
    assert runtime_denial_receipts_criterion["execution_authority"] is False
    assert runtime_denial_receipts_criterion["approval_decision_authority"] is False
    assert runtime_denial_receipts_criterion["process_supervision_authority"] is False
    assert runtime_denial_receipts_criterion["service_control_authority"] is False
    assert runtime_denial_receipts_criterion["memory_write"] is False
    assert runtime_denial_receipts_criterion["denial_receipt_write_authority"] is False
    assert runtime_denial_receipts_criterion["receipt_write_authority"] is False
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
    denial_receipt_criterion = _criterion(body, "host_activation_denial_receipt_readback")
    assert denial_receipt_criterion == {
        "id": "host_activation_denial_receipt_readback",
        "status": "empty",
        "evidence": ["/lens/host/activation/denials", "/lens/host/activation/execute", "/lens/status"],
        "receipt_count": 0,
        "latest_receipt_id": "",
        "execution_authority": False,
        "approval_decision_authority": False,
        "local_process_launch_authority": False,
        "memory_write": False,
    }
    resident_surface_activation = body["resident_surface_activation"]
    assert resident_surface_activation["kind"] == "lens.resident_surface.activation_boundary"
    assert resident_surface_activation["status"] == "blocked"
    assert resident_surface_activation["route"] == "/lens/resident-surface/activation"
    assert resident_surface_activation["boundary_ready"] is True
    assert resident_surface_activation["activation_ready"] is False
    assert resident_surface_activation["resident_surface_ready"] is False
    assert resident_surface_activation["resident_claim_allowed"] is False
    assert resident_surface_activation["execution"]["runtime_preflight_route"] == "/lens/resident-runtime/preflight"
    assert resident_surface_activation["execution"]["runtime_preflight_status"] == "blocked"
    assert resident_surface_activation["execution"]["runtime_policy_route"] == "/lens/resident-runtime/policy"
    assert resident_surface_activation["execution"]["runtime_policy_status"] == "readback_ready"
    assert (
        resident_surface_activation["execution"]["runtime_authority_grant_route"]
        == "/lens/resident-runtime/authority-grant"
    )
    assert resident_surface_activation["execution"]["runtime_authority_grant_status"] == "blocked"
    assert resident_surface_activation["execution"]["runtime_execute_route"] == "/lens/resident-runtime/execute"
    assert resident_surface_activation["execution"]["runtime_denial_status"] == "blocked"
    assert resident_surface_activation["execution"]["would_launch_process"] is False
    assert resident_surface_activation["execution"]["would_open_overlay"] is False
    assert resident_surface_activation["execution"]["would_register_hotkey"] is False
    assert resident_surface_activation["execution"]["would_register_tray"] is False
    assert resident_surface_activation["execution"]["would_supervise_process"] is False
    assert resident_surface_activation["execution"]["would_restart_process"] is False
    assert resident_surface_activation["execution"]["would_capture_screen"] is False
    assert resident_surface_activation["execution"]["would_write_memory"] is False
    assert resident_surface_activation["execution"]["would_write_receipt"] is False
    assert resident_surface_activation["execution"]["would_claim_resident"] is False
    assert (
        resident_surface_activation["execution"]["runtime_denial_reason"]
        == "resident_runtime_execution_authority_not_granted"
    )
    assert resident_surface_activation["surface"]["status"] == "blocked"
    assert resident_surface_activation["surface"]["summon_status"] == "blocked"
    assert resident_surface_activation["surface"]["tray_status"] == "blocked"
    assert resident_surface_activation["surface"]["overlay_status"] == "blocked"
    assert "resident_surface_runtime_missing" in resident_surface_activation["blockers"]
    assert "resident_surface_missing" not in resident_surface_activation["blockers"]
    assert "local_process_launch_authority_not_granted" in resident_surface_activation["blockers"]
    assert "resident_runtime_execution_authority_not_granted" in resident_surface_activation["blockers"]
    assert resident_surface_activation["resident_runtime_plan"]["kind"] == "lens.resident_runtime.activation_plan"
    assert resident_surface_activation["resident_runtime_plan"]["runtime_ready"] is False
    assert (
        resident_surface_activation["resident_runtime_preflight"]["kind"]
        == "lens.resident_runtime.activation_preflight"
    )
    assert resident_surface_activation["resident_runtime_preflight"]["grant_ready"] is False
    assert (
        resident_surface_activation["resident_runtime_policy"]["kind"]
        == "lens.resident_runtime.execution_policy_contract"
    )
    assert resident_surface_activation["resident_runtime_policy"]["policy_contract_ready"] is True
    assert resident_surface_activation["resident_runtime_policy"]["grant_ready"] is False
    assert (
        resident_surface_activation["resident_runtime_authority_grant"]["kind"]
        == "lens.resident_runtime.execution_authority_grant.denial"
    )
    assert resident_surface_activation["resident_runtime_authority_grant"]["boundary_ready"] is True
    assert resident_surface_activation["resident_runtime_authority_grant"]["authority_granted"] is False
    assert (
        resident_surface_activation["resident_runtime_denial"]["kind"]
        == "lens.resident_runtime.activation.execution_denial"
    )
    assert resident_surface_activation["resident_runtime_denial"]["executed"] is False
    assert (
        resident_surface_activation["next_smallest_truthful_gap"]
        == "approve_resident_runtime_execution_authority_grant_receipt"
    )
    assert resident_surface_activation["governance"]["gate"] == "lens_resident_surface_activation_boundary"
    assert resident_surface_activation["governance"]["boundary_only"] is True
    assert resident_surface_activation["governance"]["execution_authority"] is False
    assert resident_surface_activation["governance"]["approval_decision_authority"] is False
    assert resident_surface_activation["governance"]["local_process_launch_authority"] is False
    assert resident_surface_activation["governance"]["overlay_control_authority"] is False
    assert resident_surface_activation["governance"]["summon_authority"] is False
    assert resident_surface_activation["governance"]["memory_write"] is False
    surface_activation_criterion = _criterion(body, "resident_surface_activation_boundary")
    assert surface_activation_criterion == {
        "id": "resident_surface_activation_boundary",
        "status": "blocked_readback_ready",
        "evidence": [
            "/lens/resident-surface/activation",
            "/lens/resident-runtime/preflight",
            "/lens/resident-runtime/policy",
            "/lens/resident-runtime/authority-grant",
            "/lens/resident-runtime/plan",
            "/lens/host/activation/plan",
            "/lens/preflight",
            "/lens/status",
        ],
        "activation_ready": False,
        "resident_surface_ready": False,
        "resident_claim_allowed": False,
        "execution_authority": False,
        "approval_decision_authority": False,
        "local_process_launch_authority": False,
        "overlay_control_authority": False,
        "summon_authority": False,
        "memory_write": False,
    }
    supervision_gate_criterion = _criterion(body, "resident_supervision_enablement_gate")
    assert supervision_gate_criterion["status"] == "blocked"
    assert supervision_gate_criterion["ready"] is False
    assert supervision_gate_criterion["resident_claim_allowed"] is False
    assert supervision_gate_criterion["evidence"] == [
        "/lens/host/supervision",
        "/lens/host/manifest",
        "/lens/status",
    ]
    assert supervision_gate_criterion["process_supervision_authority"] is False
    assert supervision_gate_criterion["process_restart_authority"] is False
    assert supervision_gate_criterion["service_install_authority"] is False
    assert supervision_gate_criterion["service_control_authority"] is False
    assert supervision_gate_criterion["receipt_write_authority"] is False
    assert supervision_gate_criterion["resident_claim_authority"] is False
    assert "process_supervision_enabled" in supervision_gate_criterion["blockers"]
    assert "persistent_supervision_enabled" in supervision_gate_criterion["blockers"]
    assert "receipt_write_authority_false" in supervision_gate_criterion["blockers"]
    assert "resident_claim_authority_false" in supervision_gate_criterion["blockers"]
    assert "service_install_authority_false" in supervision_gate_criterion["blockers"]
    assert _criterion(body, "summon_anywhere")["status"] == "not_implemented"
    assert _criterion(body, "summon_anywhere")["evidence"] == [
        "/lens/summon",
        "/lens/host",
        "/lens/preflight",
        "/lens/status",
    ]
    assert "summon_binding_missing" in _criterion(body, "summon_anywhere")["blockers"]
    summon_gate_criterion = _criterion(body, "summon_enablement_gate")
    assert summon_gate_criterion["status"] == "blocked"
    assert summon_gate_criterion["ready"] is False
    assert summon_gate_criterion["summon_anywhere"] is False
    assert summon_gate_criterion["evidence"] == ["/lens/summon", "/lens/preflight", "/lens/status"]
    assert summon_gate_criterion["global_hotkey"] == "Ctrl+Alt+Space"
    assert summon_gate_criterion["next_smallest_truthful_gap"] == "summon_anywhere_blockers"
    assert "summon_authority_not_granted" in summon_gate_criterion["blockers"]
    assert summon_gate_criterion["execution_authority"] is False
    assert summon_gate_criterion["approval_decision_authority"] is False
    assert summon_gate_criterion["local_process_launch_authority"] is False
    assert summon_gate_criterion["hotkey_registration_authority"] is False
    assert summon_gate_criterion["summon_authority"] is False
    assert summon_gate_criterion["overlay_control_authority"] is False
    tray_gate_criterion = _criterion(body, "tray_enablement_gate")
    assert tray_gate_criterion["status"] == "blocked"
    assert tray_gate_criterion["ready"] is False
    assert tray_gate_criterion["tray_presence"] is False
    assert tray_gate_criterion["evidence"] == ["/lens/tray", "/lens/preflight", "/lens/status"]
    assert tray_gate_criterion["presence_name"] == "Francis Lens Tray Presence"
    assert "tray_registration_authority_not_granted" in tray_gate_criterion["blockers"]
    assert tray_gate_criterion["execution_authority"] is False
    assert tray_gate_criterion["approval_decision_authority"] is False
    assert tray_gate_criterion["local_process_launch_authority"] is False
    assert tray_gate_criterion["service_control_authority"] is False
    assert tray_gate_criterion["tray_registration_authority"] is False
    assert tray_gate_criterion["tray_icon_authority"] is False
    assert tray_gate_criterion["notification_authority"] is False
    overlay_gate_criterion = _criterion(body, "overlay_enablement_gate")
    assert overlay_gate_criterion["status"] == "blocked"
    assert overlay_gate_criterion["ready"] is False
    assert overlay_gate_criterion["overlay_window"] is False
    assert overlay_gate_criterion["evidence"] == ["/lens/overlay", "/lens/preflight", "/lens/status"]
    assert overlay_gate_criterion["overlay_name"] == "Francis Lens Overlay"
    assert "overlay_control_authority_not_granted" in overlay_gate_criterion["blockers"]
    assert overlay_gate_criterion["execution_authority"] is False
    assert overlay_gate_criterion["approval_decision_authority"] is False
    assert overlay_gate_criterion["local_process_launch_authority"] is False
    assert overlay_gate_criterion["service_control_authority"] is False
    assert overlay_gate_criterion["window_management_authority"] is False
    assert overlay_gate_criterion["overlay_control_authority"] is False
    assert overlay_gate_criterion["capture_authority"] is False
    assert overlay_gate_criterion["hotkey_registration_authority"] is False
    assert overlay_gate_criterion["tray_registration_authority"] is False
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
    supervision_response = client.get("/lens/host/supervision")
    assert supervision_response.status_code == 200
    assert supervision_response.json() == supervision_gate
    supervision_authority_response = client.get("/lens/host/supervision/authority")
    assert supervision_authority_response.status_code == 200
    assert supervision_authority_response.json() == supervision_authority
    supervision_authority_request = client.post(
        "/lens/host/supervision/authority/request",
        json={
            "actor": "test.system.write",
            "reason": "operator wants to review host supervision authority",
        },
    )
    assert supervision_authority_request.status_code == 200
    supervision_authority_approval_id = str(supervision_authority_request.json()["approval_id"])
    assert supervision_authority_approval_id
    supervision_authority_decision = client.post(
        "/approvals/decision",
        json={
            "id": supervision_authority_approval_id,
            "action": "approve",
            "actor": "test.approvals.decision",
            "comment": "approved only as a host supervision authority review decision",
        },
    )
    assert supervision_authority_decision.status_code == 200
    assert supervision_authority_decision.json()["status"] == "approved"
    supervision_authority_denial_response = client.post(
        "/lens/host/supervision/authority",
        json={
            "approval_id": supervision_authority_approval_id,
            "actor": "test.system.write",
            "reason": "operator asked to prove host supervision authority stays denied",
        },
    )
    assert supervision_authority_denial_response.status_code == 200
    supervision_authority_denial_body = supervision_authority_denial_response.json()
    assert supervision_authority_denial_body["kind"] == "lens.host.supervision_authority.grant"
    assert supervision_authority_denial_body["status"] == "authority_granted"
    assert supervision_authority_denial_body["route"] == "/lens/host/supervision/authority"
    assert supervision_authority_denial_body["method"] == "POST"
    assert supervision_authority_denial_body["approval_id"] == supervision_authority_approval_id
    assert supervision_authority_denial_body["approval"]["found"] is True
    assert supervision_authority_denial_body["approval"]["status"] == "approved"
    assert supervision_authority_denial_body["approval"]["approved"] is True
    assert supervision_authority_denial_body["actor"] == "test.system.write"
    assert supervision_authority_denial_body["permission"]["ready"] is True
    assert supervision_authority_denial_body["boundary_ready"] is True
    assert supervision_authority_denial_body["applied"] is True
    assert supervision_authority_denial_body["executed"] is False
    assert supervision_authority_denial_body["authority_granted"] is True
    assert supervision_authority_denial_body["ready"] is True
    assert supervision_authority_denial_body["authority_ready"] is True
    assert supervision_authority_denial_body["resident_claim_allowed"] is False
    assert "system_write_scope_not_ready" not in supervision_authority_denial_body["blockers"]
    assert "host_supervision_authority_grant_not_implemented" not in supervision_authority_denial_body["blockers"]
    assert "process_supervision_authority_not_granted" not in supervision_authority_denial_body["blockers"]
    assert supervision_authority_denial_body["grant"]["would_grant_process_supervision_authority"] is True
    assert supervision_authority_denial_body["grant"]["would_grant_process_restart_authority"] is True
    assert supervision_authority_denial_body["grant"]["would_grant_service_install_authority"] is True
    assert supervision_authority_denial_body["grant"]["would_grant_service_control_authority"] is True
    assert supervision_authority_denial_body["grant"]["would_supervise_process"] is False
    assert supervision_authority_denial_body["grant"]["would_restart_process"] is False
    assert supervision_authority_denial_body["grant"]["would_install_service"] is False
    assert supervision_authority_denial_body["grant"]["would_start_service"] is False
    assert supervision_authority_denial_body["grant"]["would_write_receipt"] is False
    assert supervision_authority_denial_body["grant"]["would_write_memory"] is False
    assert supervision_authority_denial_body["grant"]["grant_receipt_written"] is True
    assert supervision_authority_denial_body["receipt_written"] is True
    assert supervision_authority_denial_body["receipt_route"] == "/lens/host/supervision/authority/grants"
    supervision_authority_denial_receipt = supervision_authority_denial_body["receipt"]
    assert supervision_authority_denial_receipt["kind"] == "lens.host.supervision_authority.grant.receipt"
    assert supervision_authority_denial_receipt["status"] == "authority_granted"
    assert supervision_authority_denial_receipt["route"] == "/lens/host/supervision/authority"
    assert supervision_authority_denial_receipt["source_kind"] == "lens.host.supervision_authority.grant"
    assert supervision_authority_denial_receipt["approval_id"] == supervision_authority_approval_id
    assert supervision_authority_denial_receipt["approval"]["approved"] is True
    assert supervision_authority_denial_receipt["actor"] == "test.system.write"
    assert supervision_authority_denial_receipt["permission"]["ready"] is True
    assert supervision_authority_denial_receipt["preflight"]["preflight_ready"] is True
    assert supervision_authority_denial_receipt["lease"]["active"] is True
    assert supervision_authority_denial_receipt["authority_boundary"]["applied"] is True
    assert supervision_authority_denial_receipt["authority_boundary"]["executed"] is False
    assert supervision_authority_denial_receipt["authority_boundary"]["authority_granted"] is True
    assert supervision_authority_denial_receipt["authorities"]["process_supervision_authority"] is True
    assert supervision_authority_denial_receipt["authorities"]["service_control_authority"] is True
    assert supervision_authority_denial_receipt["grant"]["would_grant_process_supervision_authority"] is True
    assert supervision_authority_denial_receipt["governance"]["gate"] == (
        "lens_host_supervision_authority_grant_receipt"
    )
    assert supervision_authority_denial_receipt["governance"]["denial_receipt_write_authority"] is False
    assert supervision_authority_denial_receipt["governance"]["execution_authority"] is False
    assert supervision_authority_denial_receipt["governance"]["approval_decision_authority"] is False
    assert supervision_authority_denial_receipt["governance"]["process_supervision_authority"] is True
    assert supervision_authority_denial_receipt["governance"]["service_control_authority"] is True
    assert supervision_authority_denial_receipt["governance"]["memory_write"] is False
    supervision_authority_denial_receipt_path = (
        data_root
        / "lens"
        / "host_supervision_authority_grants"
        / f"{supervision_authority_denial_receipt['receipt_id']}.json"
    )
    assert supervision_authority_denial_receipt_path.exists()
    assert supervision_authority_denial_body["governance"]["authority_grant_boundary"] is True
    assert supervision_authority_denial_body["governance"]["denial_boundary"] is False
    assert supervision_authority_denial_body["governance"]["process_supervision_authority"] is True
    assert supervision_authority_denial_body["governance"]["process_restart_authority"] is True
    assert supervision_authority_denial_body["governance"]["service_install_authority"] is True
    assert supervision_authority_denial_body["governance"]["service_control_authority"] is True
    assert supervision_authority_denial_body["governance"]["receipt_write_authority"] is True
    assert supervision_authority_denial_body["governance"]["denial_receipt_write_authority"] is False
    supervision_authority_denials_response = client.get(
        "/lens/host/supervision/authority/grants"
        f"?limit=10&approval_id={supervision_authority_approval_id}&status=authority_granted"
    )
    assert supervision_authority_denials_response.status_code == 200
    supervision_authority_denials_body = supervision_authority_denials_response.json()
    assert supervision_authority_denials_body["kind"] == "lens.host.supervision_authority.grant_receipts"
    assert supervision_authority_denials_body["status"] == "readback_ready"
    assert supervision_authority_denials_body["route"] == "/lens/host/supervision/authority/grants"
    assert supervision_authority_denials_body["authority_route"] == "/lens/host/supervision/authority"
    assert supervision_authority_denials_body["approval_id"] == supervision_authority_approval_id
    assert supervision_authority_denials_body["filter_status"] == "authority_granted"
    assert supervision_authority_denials_body["total"] == 1
    assert (
        supervision_authority_denials_body["latest"]["receipt_id"]
        == (supervision_authority_denial_receipt["receipt_id"])
    )
    assert supervision_authority_denials_body["items"][0]["authority_boundary"]["authority_granted"] is True
    assert supervision_authority_denials_body["items"][0]["governance"]["execution_authority"] is False
    assert supervision_authority_denials_body["governance"]["gate"] == (
        "lens_host_supervision_authority_grant_receipts_readback"
    )
    assert supervision_authority_denials_body["governance"]["read_only_contract"] is True
    assert supervision_authority_denials_body["governance"]["denial_receipt_write_authority"] is False
    assert supervision_authority_denials_body["governance"]["execution_authority"] is False
    assert supervision_authority_denials_body["governance"]["approval_decision_authority"] is False
    assert supervision_authority_denials_body["governance"]["process_supervision_authority"] is False
    assert supervision_authority_denials_body["governance"]["service_control_authority"] is False
    assert supervision_authority_denials_body["governance"]["memory_write"] is False
    supervision_authority_readiness_response = client.get(
        "/lens/host/supervision/authority/readiness"
        f"?limit=10&approval_id={supervision_authority_approval_id}&actor=test.system.write"
    )
    assert supervision_authority_readiness_response.status_code == 200
    supervision_authority_readiness_body = supervision_authority_readiness_response.json()
    assert supervision_authority_readiness_body["kind"] == "lens.host.supervision_authority.readiness_audit"
    assert supervision_authority_readiness_body["status"] == "blocked"
    assert supervision_authority_readiness_body["audit_status"] == "complete"
    assert supervision_authority_readiness_body["route"] == "/lens/host/supervision/authority/readiness"
    assert supervision_authority_readiness_body["authority_route"] == "/lens/host/supervision/authority"
    assert supervision_authority_readiness_body["denials_route"] == "/lens/host/supervision/authority/denials"
    assert supervision_authority_readiness_body["grants_route"] == "/lens/host/supervision/authority/grants"
    assert supervision_authority_readiness_body["approval_id"] == supervision_authority_approval_id
    assert supervision_authority_readiness_body["ready"] is False
    assert supervision_authority_readiness_body["preflight_ready"] is True
    assert supervision_authority_readiness_body["authority_ready"] is True
    assert supervision_authority_readiness_body["supervision_ready"] is False
    assert supervision_authority_readiness_body["resident_claim_allowed"] is False
    assert supervision_authority_readiness_body["boundary_observed"] is True
    assert supervision_authority_readiness_body["denial_receipt_readback_ready"] is True
    assert supervision_authority_readiness_body["grant_receipt_readback_ready"] is True
    assert supervision_authority_readiness_body["receipt_count"] == 0
    assert supervision_authority_readiness_body["latest_receipt_id"] == ""
    assert supervision_authority_readiness_body["grant_receipt_count"] == 1
    assert (
        supervision_authority_readiness_body["latest_grant_receipt_id"]
        == supervision_authority_denial_receipt["receipt_id"]
    )
    assert (
        supervision_authority_readiness_body["active_grant_receipt_id"]
        == supervision_authority_denial_receipt["receipt_id"]
    )
    direct_readiness_requirements = {item["id"]: item for item in supervision_authority_readiness_body["requirements"]}
    assert direct_readiness_requirements["exact_supervision_authority_approval"]["ready"] is True
    assert direct_readiness_requirements["actor_scope"]["ready"] is True
    assert direct_readiness_requirements["host_supervision_authority_preflight"]["ready"] is True
    assert direct_readiness_requirements["host_supervision_authority_denial_boundary"]["ready"] is True
    assert direct_readiness_requirements["host_supervision_authority_denial_receipts"]["ready"] is True
    assert direct_readiness_requirements["host_supervision_authority_grant_receipts"]["ready"] is True
    assert direct_readiness_requirements["authority_grant_implementation"]["ready"] is True
    assert direct_readiness_requirements["process_supervision_authority"]["ready"] is True
    assert direct_readiness_requirements["process_restart_authority"]["ready"] is True
    assert direct_readiness_requirements["service_install_authority"]["ready"] is True
    assert direct_readiness_requirements["service_control_authority"]["ready"] is True
    assert direct_readiness_requirements["resident_claim_authority"]["ready"] is True
    assert "actor_scope" not in supervision_authority_readiness_body["blocked_requirements"]
    assert "exact_supervision_authority_approval" not in supervision_authority_readiness_body["blocked_requirements"]
    assert "process_supervision_authority" not in supervision_authority_readiness_body["blocked_requirements"]
    assert "service_control_authority" not in supervision_authority_readiness_body["blocked_requirements"]
    assert "resident_claim_authority" not in supervision_authority_readiness_body["blocked_requirements"]
    assert "authority_grant_implementation" not in supervision_authority_readiness_body["blocked_requirements"]
    assert "system_write_scope_not_ready" not in supervision_authority_readiness_body["blockers"]
    assert "host_supervision_authority_grant_not_implemented" not in supervision_authority_readiness_body["blockers"]
    assert supervision_authority_readiness_body["governance"]["audit_only"] is True
    assert supervision_authority_readiness_body["governance"]["execution_authority"] is False
    assert supervision_authority_readiness_body["governance"]["approval_decision_authority"] is False
    assert supervision_authority_readiness_body["governance"]["process_supervision_authority"] is True
    assert supervision_authority_readiness_body["governance"]["service_control_authority"] is True
    assert supervision_authority_readiness_body["governance"]["memory_write"] is False
    preflight_response = client.get("/lens/preflight")
    assert preflight_response.status_code == 200
    assert preflight_response.json()["kind"] == "lens.preflight"
    assert preflight_response.json()["surfaces"]["summon"] == preflight_surfaces["summon"]
    summon_response = client.get("/lens/summon")
    assert summon_response.status_code == 200
    assert summon_response.json() == summon_enablement_gate
    tray_response = client.get("/lens/tray")
    assert tray_response.status_code == 200
    assert tray_response.json() == tray_enablement_gate
    overlay_response = client.get("/lens/overlay")
    assert overlay_response.status_code == 200
    assert overlay_response.json() == overlay_enablement_gate
    surface_activation_response = client.get("/lens/resident-surface/activation")
    assert surface_activation_response.status_code == 200
    assert surface_activation_response.json()["kind"] == "lens.resident_surface.activation_boundary"
    assert surface_activation_response.json()["resident_surface_ready"] is False
    surface_response = client.get("/lens/resident-surface?limit=3")
    assert surface_response.status_code == 200
    surface_body = surface_response.json()
    assert surface_body["kind"] == "lens.resident_surface.readback"
    assert surface_body["status"] == "blocked"
    assert surface_body["contract_status"] == "readback_ready"
    assert surface_body["route"] == "/lens/resident-surface"
    assert surface_body["activation_route"] == "/lens/resident-surface/activation"
    assert surface_body["content_contract_ready"] is True
    assert surface_body["resident_surface_ready"] is False
    assert surface_body["resident_overlay_runtime"] is False
    assert surface_body["summon_anywhere"] is False
    assert surface_body["tray_presence"] is False
    assert "resident_surface_runtime_missing" in surface_body["blockers"]
    assert "resident_surface_missing" not in surface_body["blockers"]
    assert surface_body["governance"]["read_only_contract"] is True
    assert surface_body["governance"]["execution_authority"] is False
    assert surface_body["governance"]["approval_decision_authority"] is False
    assert surface_body["governance"]["memory_write"] is False
    assert surface_body["governance"]["overlay_control_authority"] is False
    runtime_preflight_response = client.get("/lens/resident-runtime/preflight?actor=test.system.write")
    assert runtime_preflight_response.status_code == 200
    runtime_preflight_body = runtime_preflight_response.json()
    assert runtime_preflight_body["kind"] == "lens.resident_runtime.activation_preflight"
    assert runtime_preflight_body["route"] == "/lens/resident-runtime/preflight"
    assert runtime_preflight_body["plan_route"] == "/lens/resident-runtime/plan"
    assert runtime_preflight_body["execute_route"] == "/lens/resident-runtime/execute"
    assert runtime_preflight_body["status"] == "blocked"
    assert runtime_preflight_body["grant_ready"] is False
    assert runtime_preflight_body["authority_grant_ready"] is False
    assert runtime_preflight_body["runtime_ready"] is False
    assert runtime_preflight_body["resident_claim_allowed"] is False
    assert runtime_preflight_body["permission"]["ready"] is True
    assert "approval_id_required" in runtime_preflight_body["blockers"]
    assert "system_write_scope_not_ready" not in runtime_preflight_body["blockers"]
    assert "resident_runtime_authority_grant_not_implemented" not in runtime_preflight_body["blockers"]
    assert "resident_runtime_execution_authority_not_granted" in runtime_preflight_body["blockers"]
    assert runtime_preflight_body["governance"]["gate"] == "lens_resident_runtime_activation_preflight"
    assert runtime_preflight_body["governance"]["preflight_only"] is True
    assert runtime_preflight_body["governance"]["authority_grant_preflight"] is True
    assert runtime_preflight_body["governance"]["execution_authority"] is False
    assert runtime_preflight_body["governance"]["approval_decision_authority"] is False
    assert runtime_preflight_body["governance"]["process_supervision_authority"] is False
    assert runtime_preflight_body["governance"]["service_control_authority"] is False
    assert runtime_preflight_body["governance"]["resident_claim_authority"] is False
    assert runtime_preflight_body["governance"]["memory_write"] is False
    runtime_policy_response = client.get("/lens/resident-runtime/policy?actor=test.system.write")
    assert runtime_policy_response.status_code == 200
    runtime_policy_body = runtime_policy_response.json()
    assert runtime_policy_body["kind"] == "lens.resident_runtime.execution_policy_contract"
    assert runtime_policy_body["route"] == "/lens/resident-runtime/policy"
    assert runtime_policy_body["preflight_route"] == "/lens/resident-runtime/preflight"
    assert runtime_policy_body["authority_grant_route"] == "/lens/resident-runtime/authority-grant"
    assert runtime_policy_body["plan_route"] == "/lens/resident-runtime/plan"
    assert runtime_policy_body["execute_route"] == "/lens/resident-runtime/execute"
    assert runtime_policy_body["status"] == "readback_ready"
    assert runtime_policy_body["policy_contract_ready"] is True
    assert runtime_policy_body["execution_policy_ready"] is True
    assert runtime_policy_body["grant_ready"] is False
    assert runtime_policy_body["runtime_ready"] is False
    assert runtime_policy_body["resident_claim_allowed"] is False
    assert runtime_policy_body["permission"]["ready"] is True
    assert runtime_policy_body["policy"]["default_effect"] == "deny"
    assert runtime_policy_body["policy"]["required_actor_scope"] == "system.write"
    assert "launch_process" in runtime_policy_body["policy"]["must_not_execute_until_granted"]
    assert "resident_runtime_execution_authority_not_granted" in runtime_policy_body["blockers"]
    assert "resident_runtime_authority_grant_not_implemented" not in runtime_policy_body["blockers"]
    assert runtime_policy_body["governance"]["gate"] == "lens_resident_runtime_execution_policy_contract"
    assert runtime_policy_body["governance"]["policy_contract"] is True
    assert runtime_policy_body["governance"]["execution_authority"] is False
    assert runtime_policy_body["governance"]["approval_decision_authority"] is False
    assert runtime_policy_body["governance"]["process_supervision_authority"] is False
    assert runtime_policy_body["governance"]["service_control_authority"] is False
    assert runtime_policy_body["governance"]["resident_claim_authority"] is False
    assert runtime_policy_body["governance"]["memory_write"] is False
    runtime_authority_requests_response = client.get("/lens/resident-runtime/authority-grant/requests")
    assert runtime_authority_requests_response.status_code == 200
    runtime_authority_requests_body = runtime_authority_requests_response.json()
    assert runtime_authority_requests_body["kind"] == "lens.resident_runtime.execution_authority.request_readback"
    assert runtime_authority_requests_body["status"] == "none"
    assert runtime_authority_requests_body["route"] == "/lens/resident-runtime/authority-grant/requests"
    assert runtime_authority_requests_body["request_route"] == "/lens/resident-runtime/authority-grant/request"
    assert runtime_authority_requests_body["grant_route"] == "/lens/resident-runtime/authority-grant"
    assert runtime_authority_requests_body["total_count"] == 0
    assert runtime_authority_requests_body["authority_granted"] is False
    assert runtime_authority_requests_body["resident_claim_allowed"] is False
    assert runtime_authority_requests_body["execution_authority"] is False
    assert runtime_authority_requests_body["governance"]["read_only_contract"] is True
    assert runtime_authority_requests_body["governance"]["approval_request_write"] is False
    assert runtime_authority_requests_body["governance"]["execution_authority"] is False
    assert runtime_authority_requests_body["governance"]["resident_claim_authority"] is False
    runtime_authority_request_response = client.post(
        "/lens/resident-runtime/authority-grant/request",
        json={
            "actor": "test.system.write",
            "reason": "operator asks to review resident runtime execution authority",
        },
    )
    assert runtime_authority_request_response.status_code == 200
    runtime_authority_request_body = runtime_authority_request_response.json()
    assert runtime_authority_request_body["status"] == "approval_requested"
    assert runtime_authority_request_body["approval_requested"] is True
    assert runtime_authority_request_body["applied"] is False
    assert runtime_authority_request_body["executed"] is False
    assert runtime_authority_request_body["action"] == "lens.resident_runtime.execution_authority"
    assert runtime_authority_request_body["authority_granted"] is False
    assert runtime_authority_request_body["resident_claim_allowed"] is False
    assert runtime_authority_request_body["execution_authority"] is False
    assert runtime_authority_request_body["process_supervision_authority"] is False
    assert runtime_authority_request_body["service_control_authority"] is False
    assert runtime_authority_request_body["memory_write"] is False
    assert runtime_authority_request_body["governance"]["approval_request_write"] is True
    assert runtime_authority_request_body["governance"]["execution_authority"] is False
    assert runtime_authority_request_body["governance"]["resident_claim_authority"] is False
    runtime_authority_request_payload = runtime_authority_request_body["resident_runtime_execution_authority"]
    assert runtime_authority_request_payload["request_kind"] == "lens.resident_runtime.execution_authority.request"
    assert runtime_authority_request_payload["route"] == "/lens/resident-runtime/authority-grant/request"
    assert runtime_authority_request_payload["grant_route"] == "/lens/resident-runtime/authority-grant"
    assert runtime_authority_request_payload["grant_boundary"]["boundary_ready"] is True
    assert runtime_authority_request_payload["grant_boundary"]["authority_granted"] is False
    assert runtime_authority_request_payload["grant_boundary"]["resident_claim_allowed"] is False
    assert runtime_authority_request_payload["readiness"]["boundary_observed"] is True
    assert "resident_runtime_authority_grant_not_implemented" not in runtime_authority_request_payload["blockers"]
    assert "resident_runtime_execution_authority_not_granted" in runtime_authority_request_payload["blockers"]
    runtime_authority_requests_response = client.get("/lens/resident-runtime/authority-grant/requests")
    assert runtime_authority_requests_response.status_code == 200
    runtime_authority_requests_body = runtime_authority_requests_response.json()
    assert runtime_authority_requests_body["status"] == "pending_review"
    assert runtime_authority_requests_body["pending_count"] == 1
    assert runtime_authority_requests_body["total_count"] == 1
    assert runtime_authority_requests_body["latest"]["id"] == runtime_authority_request_body["approval_id"]
    assert runtime_authority_requests_body["items"][0]["id"] == runtime_authority_request_body["approval_id"]
    assert runtime_authority_requests_body["authority_granted"] is False
    runtime_authority_grant_response = client.post(
        "/lens/resident-runtime/authority-grant",
        json={
            "actor": "test.system.write",
            "reason": "operator asked to prove resident runtime authority stays blocked",
        },
    )
    assert runtime_authority_grant_response.status_code == 200
    runtime_authority_grant_body = runtime_authority_grant_response.json()
    assert runtime_authority_grant_body["kind"] == "lens.resident_runtime.execution_authority_grant.denial"
    assert runtime_authority_grant_body["status"] == "blocked"
    assert runtime_authority_grant_body["route"] == "/lens/resident-runtime/authority-grant"
    assert runtime_authority_grant_body["preflight_route"] == "/lens/resident-runtime/preflight"
    assert runtime_authority_grant_body["policy_route"] == "/lens/resident-runtime/policy"
    assert runtime_authority_grant_body["applied"] is False
    assert runtime_authority_grant_body["executed"] is False
    assert runtime_authority_grant_body["authority_granted"] is False
    assert runtime_authority_grant_body["boundary_ready"] is True
    assert runtime_authority_grant_body["permission"]["ready"] is True
    assert runtime_authority_grant_body["grant_denial"]["reason"] == "resident_runtime_execution_authority_not_ready"
    assert runtime_authority_grant_body["grant_denial"]["would_grant_execution_authority"] is False
    assert runtime_authority_grant_body["grant_denial"]["would_grant_resident_runtime_execution_authority"] is False
    assert runtime_authority_grant_body["grant_denial"]["would_grant_process_supervision_authority"] is False
    assert runtime_authority_grant_body["grant_denial"]["would_grant_service_control_authority"] is False
    assert runtime_authority_grant_body["grant_denial"]["would_grant_tray_registration_authority"] is False
    assert runtime_authority_grant_body["grant_denial"]["would_grant_hotkey_registration_authority"] is False
    assert runtime_authority_grant_body["grant_denial"]["would_grant_overlay_control_authority"] is False
    assert runtime_authority_grant_body["grant_denial"]["would_grant_memory_write"] is False
    assert runtime_authority_grant_body["grant_denial"]["would_grant_resident_claim"] is False
    assert runtime_authority_grant_body["receipt_written"] is False
    assert runtime_authority_grant_body["receipt"] == {}
    assert "approval_id_required" in runtime_authority_grant_body["blockers"]
    assert "system_write_scope_not_ready" not in runtime_authority_grant_body["blockers"]
    assert "resident_runtime_authority_grant_not_implemented" not in runtime_authority_grant_body["blockers"]
    assert "resident_runtime_execution_authority_not_granted" not in runtime_authority_grant_body["blockers"]
    assert runtime_authority_grant_body["governance"]["gate"] == (
        "lens_resident_runtime_execution_authority_grant_denial_boundary"
    )
    assert runtime_authority_grant_body["governance"]["authority_grant_boundary"] is True
    assert runtime_authority_grant_body["governance"]["denial_boundary"] is True
    assert runtime_authority_grant_body["governance"]["execution_authority"] is False
    assert runtime_authority_grant_body["governance"]["approval_decision_authority"] is False
    assert runtime_authority_grant_body["governance"]["process_supervision_authority"] is False
    assert runtime_authority_grant_body["governance"]["service_control_authority"] is False
    assert runtime_authority_grant_body["governance"]["resident_claim_authority"] is False
    assert runtime_authority_grant_body["governance"]["memory_write"] is False
    runtime_authority_grant_denials_response = client.get("/lens/resident-runtime/authority-grant/denials")
    assert runtime_authority_grant_denials_response.status_code == 200
    runtime_authority_grant_denials_body = runtime_authority_grant_denials_response.json()
    assert runtime_authority_grant_denials_body["kind"] == (
        "lens.resident_runtime.execution_authority_grant.denial_receipts"
    )
    assert runtime_authority_grant_denials_body["status"] == "empty"
    assert runtime_authority_grant_denials_body["route"] == "/lens/resident-runtime/authority-grant/denials"
    assert runtime_authority_grant_denials_body["authority_grant_route"] == "/lens/resident-runtime/authority-grant"
    assert runtime_authority_grant_denials_body["total"] == 0
    assert runtime_authority_grant_denials_body["items"] == []
    assert runtime_authority_grant_denials_body["governance"]["gate"] == (
        "lens_resident_runtime_execution_authority_grant_denial_receipts_readback"
    )
    assert runtime_authority_grant_denials_body["governance"]["execution_authority"] is False
    assert runtime_authority_grant_denials_body["governance"]["denial_receipt_write_authority"] is False
    assert runtime_authority_grant_denials_body["governance"]["memory_write"] is False
    runtime_authority_grant_grants_response = client.get("/lens/resident-runtime/authority-grant/grants")
    assert runtime_authority_grant_grants_response.status_code == 200
    runtime_authority_grant_grants_body = runtime_authority_grant_grants_response.json()
    assert runtime_authority_grant_grants_body["kind"] == (
        "lens.resident_runtime.execution_authority_grant.grant_receipts"
    )
    assert runtime_authority_grant_grants_body["status"] == "empty"
    assert runtime_authority_grant_grants_body["route"] == "/lens/resident-runtime/authority-grant/grants"
    assert runtime_authority_grant_grants_body["authority_grant_route"] == "/lens/resident-runtime/authority-grant"
    assert runtime_authority_grant_grants_body["total"] == 0
    assert runtime_authority_grant_grants_body["items"] == []
    assert runtime_authority_grant_grants_body["authority_granted"] is False
    assert runtime_authority_grant_grants_body["governance"]["gate"] == (
        "lens_resident_runtime_execution_authority_grant_receipts_readback"
    )
    assert runtime_authority_grant_grants_body["governance"]["execution_authority"] is False
    assert runtime_authority_grant_grants_body["governance"]["receipt_write_authority"] is False
    assert runtime_authority_grant_grants_body["governance"]["memory_write"] is False
    runtime_authority_grant_readiness_response = client.get(
        "/lens/resident-runtime/authority-grant/readiness?actor=test.system.write"
    )
    assert runtime_authority_grant_readiness_response.status_code == 200
    runtime_authority_grant_readiness_body = runtime_authority_grant_readiness_response.json()
    assert runtime_authority_grant_readiness_body["kind"] == (
        "lens.resident_runtime.execution_authority_grant.readiness_audit"
    )
    assert runtime_authority_grant_readiness_body["status"] == "blocked"
    assert runtime_authority_grant_readiness_body["audit_status"] == "complete"
    assert runtime_authority_grant_readiness_body["route"] == "/lens/resident-runtime/authority-grant/readiness"
    assert runtime_authority_grant_readiness_body["ready"] is False
    assert runtime_authority_grant_readiness_body["grant_ready"] is False
    assert runtime_authority_grant_readiness_body["runtime_ready"] is False
    assert runtime_authority_grant_readiness_body["resident_claim_allowed"] is False
    assert runtime_authority_grant_readiness_body["boundary_observed"] is True
    assert runtime_authority_grant_readiness_body["grant_receipt_readback_ready"] is True
    assert runtime_authority_grant_readiness_body["denial_receipt_readback_ready"] is True
    assert runtime_authority_grant_readiness_body["receipt_count"] == 0
    readiness_requirements = {item["id"]: item for item in runtime_authority_grant_readiness_body["requirements"]}
    assert readiness_requirements["actor_scope"]["ready"] is True
    assert readiness_requirements["execution_policy_contract"]["ready"] is True
    assert readiness_requirements["authority_grant_boundary"]["ready"] is True
    assert readiness_requirements["authority_grant_receipts"]["ready"] is True
    assert readiness_requirements["authority_grant_denial_receipts"]["ready"] is True
    assert readiness_requirements["resident_runtime_execution_authority"]["ready"] is False
    assert (
        "exact_resident_runtime_execution_authority_approval"
        in runtime_authority_grant_readiness_body["blocked_requirements"]
    )
    assert "resident_runtime_execution_authority" in runtime_authority_grant_readiness_body["blocked_requirements"]
    assert "authority_grant_implementation" not in runtime_authority_grant_readiness_body["blocked_requirements"]
    assert "resident_runtime_authority_grant_not_implemented" not in runtime_authority_grant_readiness_body["blockers"]
    assert runtime_authority_grant_readiness_body["governance"]["audit_only"] is True
    assert runtime_authority_grant_readiness_body["governance"]["execution_authority"] is False
    assert runtime_authority_grant_readiness_body["governance"]["approval_decision_authority"] is False
    assert runtime_authority_grant_readiness_body["governance"]["process_supervision_authority"] is False
    assert runtime_authority_grant_readiness_body["governance"]["service_control_authority"] is False
    assert runtime_authority_grant_readiness_body["governance"]["memory_write"] is False
    runtime_plan_response = client.get("/lens/resident-runtime/plan")
    assert runtime_plan_response.status_code == 200
    runtime_plan_body = runtime_plan_response.json()
    assert runtime_plan_body["kind"] == "lens.resident_runtime.activation_plan"
    assert runtime_plan_body["route"] == "/lens/resident-runtime/plan"
    assert runtime_plan_body["policy_route"] == "/lens/resident-runtime/policy"
    assert runtime_plan_body["authority_grant_route"] == "/lens/resident-runtime/authority-grant"
    assert runtime_plan_body["execute_route"] == "/lens/resident-runtime/execute"
    assert runtime_plan_body["status"] == "blocked"
    assert runtime_plan_body["runtime_ready"] is False
    assert runtime_plan_body["plan"]["would_launch_process"] is False
    assert runtime_plan_body["plan"]["would_supervise_process"] is False
    assert runtime_plan_body["plan"]["would_register_tray"] is False
    assert runtime_plan_body["plan"]["would_register_hotkey"] is False
    assert runtime_plan_body["plan"]["would_open_overlay"] is False
    assert runtime_plan_body["plan"]["would_write_memory"] is False
    assert runtime_plan_body["governance"]["gate"] == "lens_resident_runtime_activation_plan"
    assert runtime_plan_body["governance"]["plan_readback_only"] is True
    assert runtime_plan_body["governance"]["execution_authority"] is False
    assert runtime_plan_body["governance"]["process_supervision_authority"] is False
    assert runtime_plan_body["governance"]["service_install_authority"] is False
    assert runtime_plan_body["governance"]["service_control_authority"] is False
    assert runtime_plan_body["governance"]["tray_registration_authority"] is False
    assert runtime_plan_body["governance"]["hotkey_registration_authority"] is False
    assert runtime_plan_body["governance"]["overlay_control_authority"] is False
    assert runtime_plan_body["governance"]["memory_write"] is False
    runtime_execute_response = client.post(
        "/lens/resident-runtime/execute",
        json={
            "actor": "test.system.write",
            "reason": "operator asked to prove resident runtime stays blocked",
        },
    )
    assert runtime_execute_response.status_code == 200
    runtime_execute_body = runtime_execute_response.json()
    assert runtime_execute_body["kind"] == "lens.resident_runtime.activation.execution_denial"
    assert runtime_execute_body["status"] == "blocked"
    assert runtime_execute_body["route"] == "/lens/resident-runtime/execute"
    assert runtime_execute_body["plan_route"] == "/lens/resident-runtime/plan"
    assert runtime_execute_body["applied"] is False
    assert runtime_execute_body["executed"] is False
    assert runtime_execute_body["permission"]["ready"] is True
    assert runtime_execute_body["denial"]["reason"] == "resident_runtime_execution_authority_not_granted"
    assert runtime_execute_body["denial"]["would_launch_process"] is False
    assert runtime_execute_body["denial"]["would_supervise_process"] is False
    assert runtime_execute_body["denial"]["would_restart_process"] is False
    assert runtime_execute_body["denial"]["would_install_service"] is False
    assert runtime_execute_body["denial"]["would_start_service"] is False
    assert runtime_execute_body["denial"]["would_register_tray"] is False
    assert runtime_execute_body["denial"]["would_register_hotkey"] is False
    assert runtime_execute_body["denial"]["would_open_overlay"] is False
    assert runtime_execute_body["denial"]["would_write_memory"] is False
    assert runtime_execute_body["denial"]["would_write_receipt"] is False
    assert runtime_execute_body["denial"]["would_claim_resident"] is False
    assert runtime_execute_body["receipt_written"] is False
    assert runtime_execute_body["receipt"] == {}
    assert "approval_id_required" in runtime_execute_body["blockers"]
    assert "system_write_scope_not_ready" not in runtime_execute_body["blockers"]
    assert "resident_runtime_execution_authority_not_granted" in runtime_execute_body["blockers"]
    assert runtime_execute_body["governance"]["gate"] == "lens_resident_runtime_activation_execution_denial"
    assert runtime_execute_body["governance"]["execution_boundary"] is True
    assert runtime_execute_body["governance"]["resident_runtime_boundary"] is True
    assert runtime_execute_body["governance"]["execution_authority"] is False
    assert runtime_execute_body["governance"]["process_supervision_authority"] is False
    assert runtime_execute_body["governance"]["service_control_authority"] is False
    assert runtime_execute_body["governance"]["hotkey_registration_authority"] is False
    assert runtime_execute_body["governance"]["overlay_control_authority"] is False
    assert runtime_execute_body["governance"]["memory_write"] is False
    assert runtime_execute_body["governance"]["receipt_write_authority"] is False
    assert runtime_execute_body["governance"]["resident_claim_authority"] is False


def test_lens_persistent_supervision_plan_readback_blocks_without_authority(monkeypatch, tmp_path: Path) -> None:
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
    response = client.get("/lens/host/persistent-supervision")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["kind"] == "lens.host.persistent_supervision_plan"
    assert body["status"] == "blocked"
    assert body["route"] == "/lens/host/persistent-supervision"
    assert body["host_route"] == "/lens/host"
    assert body["manifest_route"] == "/lens/host/manifest"
    assert body["supervision_route"] == "/lens/host/supervision"
    assert body["authority_route"] == "/lens/host/supervision/authority"
    assert body["service_name"] == "Francis-LensHost"
    assert body["service_manager"] == "scripts/service-install.ps1"
    assert body["service_manager_present"] is True
    assert body["service_config_present"] is True
    assert body["host_entrypoint_present"] is True
    assert body["plan_available"] is True
    assert body["ready"] is False
    assert body["persistent_supervision_ready"] is False
    assert body["resident_claim_allowed"] is False
    assert body["requirements_total"] == 10
    assert body["requirements_ready_total"] == 3
    assert body["requirements_blocked_total"] == 7
    assert body["blocked_requirements"] == [
        "process_supervision_enabled",
        "persistent_supervision_enabled",
        "process_restart_authority",
        "service_install_authority",
        "service_control_authority",
        "receipt_write_authority",
        "resident_claim_authority",
    ]
    assert "process_supervision_disabled" in body["blockers"]
    assert "persistent_supervision_disabled" in body["blockers"]
    assert "process_restart_authority_not_granted" in body["blockers"]
    assert "service_install_authority_not_granted" in body["blockers"]
    assert "service_control_authority_not_granted" in body["blockers"]
    assert "receipt_write_authority_not_granted" in body["blockers"]
    assert "resident_claim_authority_not_granted" in body["blockers"]
    assert body["plan"] == {
        "mode": "persistent_supervised_resident_host",
        "service_name": "Francis-LensHost",
        "would_install_service": False,
        "would_update_service": False,
        "would_start_service": False,
        "would_supervise_process": False,
        "would_restart_process": False,
        "would_write_receipt": False,
        "would_write_memory": False,
        "would_claim_resident": False,
    }
    assert body["next_smallest_truthful_gap"] == "persistent_supervision_authority_not_granted"
    assert body["governance"] == {
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
    }

    enablement = client.get("/lens/host/persistent-supervision/enablement")
    assert enablement.status_code == 200
    enablement_body = enablement.json()
    assert enablement_body["kind"] == "lens.host.persistent_supervision_enablement.preflight"
    assert enablement_body["status"] == "blocked"
    assert enablement_body["route"] == "/lens/host/persistent-supervision/enablement"
    assert enablement_body["plan_route"] == "/lens/host/persistent-supervision"
    assert enablement_body["authority_route"] == "/lens/host/supervision/authority"
    assert enablement_body["preflight_ready"] is True
    assert enablement_body["ready"] is False
    assert enablement_body["enablement_ready"] is False
    assert enablement_body["persistent_supervision_ready"] is False
    assert enablement_body["resident_claim_allowed"] is False
    assert enablement_body["authority_grant_active"] is False
    assert enablement_body["active_grant_receipt_id"] == ""
    assert enablement_body["blocked_requirements"] == [
        "active_host_supervision_authority_grant",
        "process_supervision_enabled",
        "persistent_supervision_enabled",
    ]
    assert "host_supervision_authority_grant_not_active" in enablement_body["blockers"]
    assert "process_supervision_disabled" in enablement_body["blockers"]
    assert "persistent_supervision_disabled" in enablement_body["blockers"]
    assert enablement_body["next_smallest_truthful_gap"] == "persistent_supervision_authority_not_granted"
    assert enablement_body["plan"] == {
        "mode": "persistent_supervision_enablement_preflight",
        "service_name": "Francis-LensHost",
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
    }
    assert enablement_body["governance"] == {
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
    }

    enablement_denial = client.post(
        "/lens/host/persistent-supervision/enablement",
        json={
            "actor": "test.system.write",
            "reason": "prove persistent supervision enablement stays denied without authority",
        },
    )
    assert enablement_denial.status_code == 200
    enablement_denial_body = enablement_denial.json()
    assert enablement_denial_body["kind"] == "lens.host.persistent_supervision_enablement.denial"
    assert enablement_denial_body["status"] == "blocked"
    assert enablement_denial_body["route"] == "/lens/host/persistent-supervision/enablement"
    assert enablement_denial_body["preflight_route"] == "/lens/host/persistent-supervision/enablement"
    assert enablement_denial_body["plan_route"] == "/lens/host/persistent-supervision"
    assert enablement_denial_body["authority_route"] == "/lens/host/supervision/authority"
    assert enablement_denial_body["applied"] is False
    assert enablement_denial_body["executed"] is False
    assert enablement_denial_body["boundary_ready"] is True
    assert enablement_denial_body["ready"] is False
    assert enablement_denial_body["enablement_ready"] is False
    assert enablement_denial_body["authority_grant_active"] is False
    assert enablement_denial_body["active_grant_receipt_id"] == ""
    assert enablement_denial_body["service_config_updated"] is False
    assert "host_supervision_authority_grant_not_active" in enablement_denial_body["blockers"]
    assert "persistent_supervision_enablement_authority_not_granted" in enablement_denial_body["blockers"]
    assert "service_config_write_authority_not_granted" in enablement_denial_body["blockers"]
    assert "persistent_supervision_execution_authority_not_granted" in enablement_denial_body["blockers"]
    assert "system_write_scope_not_ready" not in enablement_denial_body["blockers"]
    assert enablement_denial_body["denial"]["reason"] == "host_supervision_authority_grant_not_active"
    assert enablement_denial_body["denial"]["would_update_service_config"] is False
    assert enablement_denial_body["denial"]["would_enable_process_supervision"] is False
    assert enablement_denial_body["denial"]["would_enable_persistent_supervision"] is False
    assert enablement_denial_body["denial"]["would_install_service"] is False
    assert enablement_denial_body["denial"]["would_start_service"] is False
    assert enablement_denial_body["denial"]["would_supervise_process"] is False
    assert enablement_denial_body["denial"]["would_restart_process"] is False
    assert enablement_denial_body["denial"]["would_write_memory"] is False
    assert enablement_denial_body["denial"]["would_claim_resident"] is False
    assert enablement_denial_body["governance"]["gate"] == (
        "lens_host_persistent_supervision_enablement_denial_boundary"
    )
    assert enablement_denial_body["governance"]["denial_boundary"] is True
    assert enablement_denial_body["governance"]["execution_authority"] is False
    assert enablement_denial_body["governance"]["approval_decision_authority"] is False
    assert enablement_denial_body["governance"]["process_supervision_authority"] is False
    assert enablement_denial_body["governance"]["service_config_write_authority"] is False
    assert enablement_denial_body["governance"]["memory_write"] is False
    assert enablement_denial_body["governance"]["resident_claim_authority"] is False
    assert enablement_denial_body["governance"]["mutation_authority_granted"] is False

    status = client.get("/lens/status")
    assert status.status_code == 200
    status_body = status.json()
    resident_host = status_body["resident_host"]
    assert resident_host["persistent_supervision_plan_route"] == "/lens/host/persistent-supervision"
    assert resident_host["persistent_supervision_plan"]["next_smallest_truthful_gap"] == (
        "persistent_supervision_authority_not_granted"
    )
    assert resident_host["persistent_supervision_plan"]["plan"]["would_supervise_process"] is False
    assert resident_host["persistent_supervision_enablement_route"] == ("/lens/host/persistent-supervision/enablement")
    assert resident_host["persistent_supervision_enablement"]["next_smallest_truthful_gap"] == (
        "persistent_supervision_authority_not_granted"
    )
    assert resident_host["persistent_supervision_enablement"]["plan"]["would_update_service_config"] is False
    assert resident_host["persistent_supervision_enablement_denial_route"] == (
        "/lens/host/persistent-supervision/enablement"
    )
    assert resident_host["persistent_supervision_enablement_denial"]["boundary_ready"] is True
    persistent_denial_criterion = _criterion(status_body, "persistent_supervision_enablement_denial_boundary")
    assert persistent_denial_criterion["status"] == "blocked"
    assert persistent_denial_criterion["boundary_ready"] is True
    assert persistent_denial_criterion["applied"] is False
    assert persistent_denial_criterion["executed"] is False
    assert persistent_denial_criterion["service_config_updated"] is False
    assert persistent_denial_criterion["execution_authority"] is False
    assert persistent_denial_criterion["service_config_write_authority"] is False
    assert persistent_denial_criterion["memory_write"] is False


def test_lens_persistent_supervision_enablement_authority_request_requires_system_write_without_grant(
    monkeypatch,
    tmp_path: Path,
) -> None:
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
        "/lens/host/persistent-supervision/enablement/authority/request",
        json={
            "actor": "test.lens.no_scope",
            "reason": "try to request persistent supervision enablement authority without scope",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["status"] == "denied"
    assert body["approval_requested"] is False
    assert body["applied"] is False
    assert body["error"] == "api_permission_denied"
    assert body["authority_granted"] is False
    assert body["persistent_supervision_enablement_allowed"] is False
    assert body["governance"]["gate"] == "permission_gate"
    assert body["governance"]["required_scope"] == "system.write"
    assert body["governance"]["reason"] == "missing_scopes"
    assert body["governance"]["service_config_write_authority"] is False
    assert body["governance"]["persistent_supervision_execution_authority"] is False
    assert body["governance"]["process_supervision_authority"] is False
    assert body["governance"]["service_control_authority"] is False
    assert body["governance"]["receipt_write_authority"] is False
    assert body["governance"]["memory_write"] is False
    assert body["governance"]["resident_claim_authority"] is False
    assert client.get("/approvals/list?status=pending").json()["items"] == []
    assert not (data_root / "runtime" / "lens-host-supervisor" / "status.json").exists()
    assert not (data_root / "runtime" / "lens-host" / "status.json").exists()
    assert not (data_root / "runtime" / "lens-host" / "lens-host.pid").exists()


def test_lens_persistent_supervision_enablement_authority_request_creates_approval_only_readback(
    monkeypatch,
    tmp_path: Path,
) -> None:
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
        "/lens/host/persistent-supervision/enablement/authority/request",
        json={
            "actor": "test.system.write",
            "reason": "prove governed persistent supervision enablement authority request",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["status"] == "approval_requested"
    assert body["approval_requested"] is True
    assert body["applied"] is False
    assert body["authority_granted"] is False
    assert body["service_config_write_authority"] is False
    assert body["persistent_supervision_execution_authority"] is False
    assert body["persistent_supervision_enablement_allowed"] is False
    assert body["resident_claim_allowed"] is False
    assert body["action"] == "lens.host.persistent_supervision_enablement_authority"
    assert body["governance"]["approval_request_write"] is True
    assert body["governance"]["approval_action"] == "lens.host.persistent_supervision_enablement_authority"
    assert body["governance"]["service_config_write_authority"] is False
    assert body["governance"]["persistent_supervision_execution_authority"] is False
    assert body["governance"]["process_supervision_authority"] is False
    assert body["governance"]["service_control_authority"] is False
    assert body["governance"]["receipt_write_authority"] is False
    assert body["governance"]["memory_write"] is False
    assert body["governance"]["resident_claim_authority"] is False
    assert body["governance"]["authority_granted"] is False
    approval_id = str(body["approval_id"])
    assert approval_id

    pending_path = data_root / "approvals" / "pending" / f"{approval_id}.json"
    pending_payload = json.loads(pending_path.read_text(encoding="utf-8"))
    assert pending_payload["action"] == "lens.host.persistent_supervision_enablement_authority"
    assert pending_payload["reason"] == "prove governed persistent supervision enablement authority request"
    requested = pending_payload["payload"]
    assert requested["request_kind"] == "lens.host.persistent_supervision_enablement_authority.request"
    assert requested["route"] == "/lens/host/persistent-supervision/enablement/authority/request"
    assert requested["enablement_route"] == "/lens/host/persistent-supervision/enablement"
    assert requested["readback_route"] == "/lens/host/persistent-supervision/enablement/authority/requests"
    assert requested["readiness_route"] == "/lens/host/persistent-supervision/enablement/authority/readiness"
    assert requested["preflight"]["preflight_ready"] is True
    assert requested["preflight"]["authority_grant_active"] is False
    assert requested["preflight"]["enablement_ready"] is False
    assert "active_host_supervision_authority_grant" in requested["preflight"]["blocked_requirements"]
    assert "host_supervision_authority_grant_not_active" in requested["preflight"]["blockers"]
    assert requested["denial_boundary"]["boundary_ready"] is True
    assert requested["denial_boundary"]["applied"] is False
    assert requested["denial_boundary"]["executed"] is False
    assert requested["denial_boundary"]["service_config_updated"] is False
    assert "persistent_supervision_enablement_authority_not_granted" in requested["denial_boundary"]["blockers"]
    assert requested["governance"]["approval_request_write"] is True
    assert requested["governance"]["service_config_write_authority"] is False
    assert requested["governance"]["persistent_supervision_execution_authority"] is False
    assert requested["governance"]["resident_claim_authority"] is False

    readback = client.get("/lens/host/persistent-supervision/enablement/authority/requests?limit=10")
    assert readback.status_code == 200
    readback_body = readback.json()
    assert readback_body["kind"] == "lens.host.persistent_supervision_enablement_authority.request_readback"
    assert readback_body["status"] == "pending_review"
    assert readback_body["route"] == "/lens/host/persistent-supervision/enablement/authority/requests"
    assert readback_body["request_route"] == "/lens/host/persistent-supervision/enablement/authority/request"
    assert readback_body["readiness_route"] == "/lens/host/persistent-supervision/enablement/authority/readiness"
    assert readback_body["pending_count"] == 1
    assert readback_body["approved_count"] == 0
    assert readback_body["total_count"] == 1
    assert readback_body["latest"]["id"] == approval_id
    assert readback_body["latest"]["action"] == "lens.host.persistent_supervision_enablement_authority"
    assert readback_body["authority_granted"] is False
    assert readback_body["service_config_write_authority"] is False
    assert readback_body["persistent_supervision_execution_authority"] is False
    assert readback_body["persistent_supervision_enablement_allowed"] is False
    assert readback_body["resident_claim_allowed"] is False
    assert readback_body["governance"]["read_only_contract"] is True
    assert readback_body["governance"]["approval_request_write"] is False
    assert readback_body["governance"]["service_config_write_authority"] is False
    assert readback_body["governance"]["persistent_supervision_execution_authority"] is False
    assert readback_body["governance"]["memory_write"] is False
    assert readback_body["governance"]["authority_granted"] is False

    pending_readiness = client.get(
        "/lens/host/persistent-supervision/enablement/authority/readiness"
        f"?limit=10&approval_id={approval_id}&actor=test.system.write"
    )
    assert pending_readiness.status_code == 200
    pending_readiness_body = pending_readiness.json()
    assert pending_readiness_body["kind"] == ("lens.host.persistent_supervision_enablement_authority.readiness_audit")
    assert pending_readiness_body["status"] == "blocked"
    assert pending_readiness_body["approval_id"] == approval_id
    assert pending_readiness_body["approval_ready"] is False
    assert pending_readiness_body["request_readback_ready"] is True
    assert pending_readiness_body["boundary_observed"] is True
    assert pending_readiness_body["authority_grant_active"] is False
    assert pending_readiness_body["service_config_write_authority"] is False
    assert pending_readiness_body["persistent_supervision_execution_authority"] is False
    assert pending_readiness_body["governance"]["execution_authority"] is False
    assert pending_readiness_body["governance"]["approval_decision_authority"] is False
    assert pending_readiness_body["governance"]["service_config_write_authority"] is False
    assert pending_readiness_body["governance"]["memory_write"] is False
    assert "persistent_supervision_enablement_authority_approval_not_approved" in pending_readiness_body["blockers"]
    assert "service_config_write_authority" in pending_readiness_body["blocked_requirements"]

    decided = client.post(
        "/approvals/decision",
        json={
            "id": approval_id,
            "action": "approve",
            "actor": "test.approvals.decision",
            "comment": "approved only as a persistent supervision enablement authority review decision",
        },
    )
    assert decided.status_code == 200
    assert decided.json()["status"] == "approved"

    approved_readback = client.get("/lens/host/persistent-supervision/enablement/authority/requests?limit=10")
    assert approved_readback.status_code == 200
    approved_readback_body = approved_readback.json()
    assert approved_readback_body["status"] == "approved_no_authority"
    assert approved_readback_body["pending_count"] == 0
    assert approved_readback_body["approved_count"] == 1
    assert approved_readback_body["authority_granted"] is False

    approved_readiness = client.get(
        "/lens/host/persistent-supervision/enablement/authority/readiness"
        f"?limit=10&approval_id={approval_id}&actor=test.system.write"
    )
    assert approved_readiness.status_code == 200
    approved_readiness_body = approved_readiness.json()
    assert approved_readiness_body["approval_ready"] is True
    assert approved_readiness_body["ready"] is False
    assert approved_readiness_body["authority_granted"] is False
    assert approved_readiness_body["service_config_updated"] is False
    assert approved_readiness_body["persistent_supervision_enablement_allowed"] is False
    assert (
        "persistent_supervision_enablement_authority_approval_not_approved" not in (approved_readiness_body["blockers"])
    )
    assert "persistent_supervision_enablement_authority_not_granted" in approved_readiness_body["blockers"]
    assert "service_config_write_authority_not_granted" in approved_readiness_body["blockers"]
    assert "persistent_supervision_execution_authority_not_granted" in approved_readiness_body["blockers"]
    approved_requirements = {item["id"]: item for item in approved_readiness_body["requirements"]}
    assert approved_requirements["exact_persistent_supervision_enablement_authority_approval"]["ready"] is True
    assert approved_requirements["persistent_supervision_enablement_authority_request_readback"]["ready"] is True
    assert approved_requirements["service_config_write_authority"]["ready"] is False
    assert approved_requirements["persistent_supervision_execution_authority"]["ready"] is False
    assert approved_readiness_body["governance"]["service_config_write_authority"] is False
    assert approved_readiness_body["governance"]["persistent_supervision_execution_authority"] is False
    assert approved_readiness_body["governance"]["receipt_write_authority"] is False
    assert approved_readiness_body["governance"]["resident_claim_authority"] is False

    lens_status = client.get("/lens/status?limit=10")
    assert lens_status.status_code == 200
    status_body = lens_status.json()
    resident_host = status_body["resident_host"]
    assert resident_host["persistent_supervision_enablement_authority_request_route"] == (
        "/lens/host/persistent-supervision/enablement/authority/request"
    )
    assert resident_host["persistent_supervision_enablement_authority_requests"]["approved_count"] == 1
    assert resident_host["persistent_supervision_enablement_authority_readiness"]["request_readback_ready"] is True
    criterion = _criterion(status_body, "persistent_supervision_enablement_authority_readiness_audit")
    assert criterion["status"] == "blocked"
    assert criterion["request_readback_ready"] is True
    assert criterion["boundary_observed"] is True
    assert criterion["service_config_write_authority"] is False
    assert criterion["persistent_supervision_execution_authority"] is False
    command = next(
        item
        for item in status_body["command_palette"]["commands"]
        if item["id"] == "lens.host.persistent_supervision_enablement_authority.request"
    )
    assert command["route"] == "/lens/host/persistent-supervision/enablement/authority/request"
    assert command["method"] == "POST"
    assert command["mutates"] is True
    assert command["write_guard"] == "system.write approval request; no service config or execution authority"
    assert command["execution_authority"] is False
    assert command["approval_decision_authority"] is False
    assert not (data_root / "runtime" / "lens-host-supervisor" / "status.json").exists()
    assert not (data_root / "runtime" / "lens-host" / "status.json").exists()
    assert not (data_root / "runtime" / "lens-host" / "lens-host.pid").exists()


def test_lens_persistent_supervision_enablement_authority_grant_requires_approved_request_and_host_grant(
    monkeypatch,
    tmp_path: Path,
) -> None:
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

    missing_approval = client.post(
        "/lens/host/persistent-supervision/enablement/authority",
        json={
            "actor": "test.system.write",
            "reason": "try persistent supervision enablement authority without exact approval",
        },
    )
    assert missing_approval.status_code == 200
    missing_body = missing_approval.json()
    assert missing_body["status"] == "blocked"
    assert missing_body["approval_id"] == ""
    assert missing_body["approval"]["required"] is True
    assert missing_body["approval"]["found"] is False
    assert missing_body["authority_granted"] is False
    assert missing_body["receipt_written"] is False
    assert "approval_id_required" in missing_body["blockers"]
    assert "host_supervision_authority_grant_not_active" in missing_body["blockers"]
    assert missing_body["governance"]["grant_receipt_write_blocker"] == (
        "persistent_supervision_enablement_authority_not_ready"
    )

    host_request = client.post(
        "/lens/host/supervision/authority/request",
        json={
            "actor": "test.system.write",
            "reason": "operator wants host supervision authority reviewed first",
        },
    )
    assert host_request.status_code == 200
    host_approval_id = str(host_request.json()["approval_id"])
    assert host_approval_id
    host_decision = client.post(
        "/approvals/decision",
        json={
            "id": host_approval_id,
            "action": "approve",
            "actor": "test.approvals.decision",
            "comment": "approved only as host supervision authority prerequisite",
        },
    )
    assert host_decision.status_code == 200
    assert host_decision.json()["status"] == "approved"
    host_grant = client.post(
        "/lens/host/supervision/authority",
        json={
            "approval_id": host_approval_id,
            "actor": "test.system.write",
            "reason": "grant host supervision authority prerequisite",
        },
    )
    assert host_grant.status_code == 200
    host_grant_body = host_grant.json()
    assert host_grant_body["status"] == "authority_granted"
    host_grant_receipt_id = host_grant_body["receipt"]["receipt_id"]

    requested = client.post(
        "/lens/host/persistent-supervision/enablement/authority/request",
        json={
            "actor": "test.system.write",
            "reason": "operator wants persistent supervision enablement authority reviewed",
        },
    )
    assert requested.status_code == 200
    approval_id = str(requested.json()["approval_id"])
    assert approval_id

    pending_attempt = client.post(
        "/lens/host/persistent-supervision/enablement/authority",
        json={
            "approval_id": approval_id,
            "actor": "test.system.write",
            "reason": "try persistent supervision enablement authority before approval decision",
        },
    )
    assert pending_attempt.status_code == 200
    pending_body = pending_attempt.json()
    assert pending_body["status"] == "blocked"
    assert pending_body["approval_id"] == approval_id
    assert pending_body["approval"]["status"] == "pending"
    assert pending_body["approval"]["approved"] is False
    assert pending_body["host_supervision_authority"]["active"] is True
    assert pending_body["host_supervision_authority"]["receipt_id"] == host_grant_receipt_id
    assert "persistent_supervision_enablement_authority_approval_not_approved" in pending_body["blockers"]
    assert pending_body["receipt_written"] is False

    decided = client.post(
        "/approvals/decision",
        json={
            "id": approval_id,
            "action": "approve",
            "actor": "test.approvals.decision",
            "comment": "approved only as a persistent supervision enablement authority review decision",
        },
    )
    assert decided.status_code == 200
    assert decided.json()["status"] == "approved"

    approved_attempt = client.post(
        "/lens/host/persistent-supervision/enablement/authority",
        json={
            "approval_id": approval_id,
            "actor": "test.system.write",
            "reason": "prove bounded persistent supervision enablement authority grant without config mutation",
        },
    )
    assert approved_attempt.status_code == 200
    approved_body = approved_attempt.json()
    assert approved_body["kind"] == "lens.host.persistent_supervision_enablement_authority.grant"
    assert approved_body["status"] == "authority_granted"
    assert approved_body["approval_id"] == approval_id
    assert approved_body["approval"]["found"] is True
    assert approved_body["approval"]["status"] == "approved"
    assert approved_body["approval"]["approved"] is True
    assert "persistent_supervision_enablement_authority_approval_not_approved" not in approved_body["blockers"]
    assert "persistent_supervision_enablement_authority_not_granted" not in approved_body["blockers"]
    assert "service_config_write_authority_not_granted" not in approved_body["blockers"]
    assert approved_body["authority_granted"] is True
    assert approved_body["grant_ready"] is True
    assert approved_body["ready"] is True
    assert approved_body["applied"] is True
    assert approved_body["executed"] is False
    assert approved_body["persistent_supervision_enablement_allowed"] is False
    assert approved_body["service_config_updated"] is False
    assert approved_body["service_config_write_authority"] is False
    assert approved_body["persistent_supervision_execution_authority"] is False
    assert approved_body["resident_claim_allowed"] is False
    assert approved_body["receipt_route"] == "/lens/host/persistent-supervision/enablement/authority/grants"
    assert approved_body["receipt_written"] is True
    receipt = approved_body["receipt"]
    assert receipt["kind"] == "lens.host.persistent_supervision_enablement_authority.grant.receipt"
    assert receipt["status"] == "authority_granted"
    assert receipt["approval_id"] == approval_id
    assert receipt["approval"]["approved"] is True
    assert receipt["host_supervision_authority"]["active"] is True
    assert receipt["host_supervision_authority"]["receipt_id"] == host_grant_receipt_id
    assert receipt["lease"]["active"] is True
    assert receipt["authority_boundary"]["applied"] is True
    assert receipt["authority_boundary"]["executed"] is False
    assert receipt["authority_boundary"]["authority_granted"] is True
    assert receipt["authority_boundary"]["service_config_updated"] is False
    assert receipt["authorities"]["persistent_supervision_enablement_authority"] is True
    assert receipt["authorities"]["service_config_write_authority"] is False
    assert receipt["authorities"]["persistent_supervision_execution_authority"] is False
    assert receipt["authorities"]["receipt_write_authority"] is True
    assert receipt["authorities"]["resident_claim_authority"] is False
    assert receipt["governance"]["execution_authority"] is False
    assert receipt["governance"]["approval_decision_authority"] is False
    assert receipt["governance"]["service_config_write_authority"] is False
    assert receipt["governance"]["persistent_supervision_execution_authority"] is False
    assert receipt["governance"]["memory_write"] is False

    grants = client.get(
        f"/lens/host/persistent-supervision/enablement/authority/grants?limit=10&approval_id={approval_id}"
    )
    assert grants.status_code == 200
    grants_body = grants.json()
    assert grants_body["kind"] == "lens.host.persistent_supervision_enablement_authority.grant_receipts"
    assert grants_body["approval_id"] == approval_id
    assert grants_body["total"] == 1
    assert grants_body["items"][0]["approval_id"] == approval_id
    assert grants_body["active_latest"]["receipt_id"] == receipt["receipt_id"]
    assert grants_body["authority_granted"] is True
    assert grants_body["service_config_write_authority"] is False
    assert grants_body["persistent_supervision_execution_authority"] is False

    readiness = client.get(
        "/lens/host/persistent-supervision/enablement/authority/readiness"
        f"?limit=10&approval_id={approval_id}&actor=test.system.write"
    )
    assert readiness.status_code == 200
    readiness_body = readiness.json()
    assert readiness_body["approval_ready"] is True
    assert readiness_body["authority_granted"] is True
    assert readiness_body["enablement_authority_granted"] is True
    assert readiness_body["active_enablement_authority_grant_receipt_id"] == receipt["receipt_id"]
    assert readiness_body["grant_receipt_count"] == 1
    assert readiness_body["grant_receipt_readback_ready"] is True
    assert readiness_body["service_config_write_authority"] is False
    assert readiness_body["persistent_supervision_execution_authority"] is False
    assert "persistent_supervision_enablement_authority_not_granted" not in readiness_body["blockers"]
    assert "service_config_write_authority_not_granted" in readiness_body["blockers"]
    assert "persistent_supervision_execution_authority_not_granted" in readiness_body["blockers"]
    readiness_requirements = {item["id"]: item for item in readiness_body["requirements"]}
    assert readiness_requirements["persistent_supervision_enablement_authority_grant_boundary"]["ready"] is True
    assert readiness_requirements["persistent_supervision_enablement_authority_grant_receipts"]["ready"] is True
    assert readiness_requirements["persistent_supervision_enablement_authority"]["ready"] is True
    assert readiness_requirements["service_config_write_authority"]["ready"] is False
    assert readiness_requirements["persistent_supervision_execution_authority"]["ready"] is False
    assert readiness_body["governance"]["persistent_supervision_enablement_authority"] is True
    assert readiness_body["governance"]["service_config_write_authority"] is False
    assert readiness_body["governance"]["persistent_supervision_execution_authority"] is False
    assert readiness_body["governance"]["memory_write"] is False

    enablement_denial = client.post(
        "/lens/host/persistent-supervision/enablement",
        json={
            "actor": "test.system.write",
            "reason": "prove enablement still denies config mutation after enablement authority grant",
        },
    )
    assert enablement_denial.status_code == 200
    enablement_denial_body = enablement_denial.json()
    assert enablement_denial_body["status"] == "denied_no_service_config_write_authority"
    assert enablement_denial_body["applied"] is False
    assert enablement_denial_body["executed"] is False
    assert enablement_denial_body["service_config_updated"] is False
    assert enablement_denial_body["authority_grant_active"] is True
    assert enablement_denial_body["active_grant_receipt_id"] == host_grant_receipt_id
    assert enablement_denial_body["persistent_supervision_enablement_authority_granted"] is True
    assert enablement_denial_body["active_enablement_authority_grant_receipt_id"] == receipt["receipt_id"]
    assert "host_supervision_authority_grant_not_active" not in enablement_denial_body["blockers"]
    assert "persistent_supervision_enablement_authority_not_granted" not in enablement_denial_body["blockers"]
    assert "service_config_write_authority_not_granted" in enablement_denial_body["blockers"]
    assert "persistent_supervision_execution_authority_not_granted" in enablement_denial_body["blockers"]
    assert enablement_denial_body["denial"]["would_update_service_config"] is False
    assert enablement_denial_body["denial"]["would_enable_process_supervision"] is False
    assert enablement_denial_body["denial"]["would_enable_persistent_supervision"] is False
    assert enablement_denial_body["denial"]["would_start_service"] is False
    assert enablement_denial_body["denial"]["would_write_memory"] is False
    assert enablement_denial_body["governance"]["persistent_supervision_enablement_authority"] is True
    assert enablement_denial_body["governance"]["service_config_write_authority"] is False
    assert enablement_denial_body["governance"]["persistent_supervision_execution_authority"] is False

    lens_status = client.get("/lens/status?limit=10")
    assert lens_status.status_code == 200
    status_body = lens_status.json()
    resident_host = status_body["resident_host"]
    assert resident_host["persistent_supervision_enablement_authority_grant_route"] == (
        "/lens/host/persistent-supervision/enablement/authority"
    )
    assert resident_host["persistent_supervision_enablement_authority_grants"]["authority_granted"] is True
    criterion = _criterion(status_body, "persistent_supervision_enablement_authority_readiness_audit")
    assert criterion["grant_receipt_readback_ready"] is True
    assert criterion["enablement_authority_granted"] is True
    assert criterion["active_enablement_authority_grant_receipt_id"] == receipt["receipt_id"]
    assert criterion["service_config_write_authority"] is False
    assert criterion["persistent_supervision_execution_authority"] is False
    grant_readback_criterion = _criterion(
        status_body,
        "persistent_supervision_enablement_authority_grant_receipt_readback",
    )
    assert grant_readback_criterion["receipt_count"] == 1
    assert grant_readback_criterion["active_receipt_id"] == receipt["receipt_id"]
    assert grant_readback_criterion["authority_granted"] is True
    assert grant_readback_criterion["service_config_write_authority"] is False
    assert grant_readback_criterion["persistent_supervision_execution_authority"] is False
    assert not (data_root / "runtime" / "lens-host-supervisor" / "status.json").exists()
    assert not (data_root / "runtime" / "lens-host" / "status.json").exists()
    assert not (data_root / "runtime" / "lens-host" / "lens-host.pid").exists()


def test_lens_persistent_supervision_enablement_execution_request_requires_enablement_authority_grant(
    monkeypatch,
    tmp_path: Path,
) -> None:
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
    no_scope = client.post(
        "/lens/host/persistent-supervision/enablement/execution/request",
        json={
            "actor": "test.lens.no_scope",
            "reason": "try to request persistent supervision execution authority without scope",
        },
    )
    assert no_scope.status_code == 200
    no_scope_body = no_scope.json()
    assert no_scope_body["status"] == "denied"
    assert no_scope_body["approval_requested"] is False
    assert no_scope_body["governance"]["gate"] == "permission_gate"
    assert no_scope_body["governance"]["service_config_write_authority"] is False
    assert no_scope_body["governance"]["persistent_supervision_execution_authority"] is False
    assert client.get("/approvals/list?status=pending").json()["items"] == []

    missing_enablement_grant = client.post(
        "/lens/host/persistent-supervision/enablement/execution/request",
        json={
            "actor": "test.system.write",
            "reason": "try to request persistent supervision execution before enablement authority grant",
        },
    )
    assert missing_enablement_grant.status_code == 200
    missing_body = missing_enablement_grant.json()
    assert missing_body["status"] == "blocked"
    assert missing_body["approval_requested"] is False
    assert missing_body["authority_granted"] is False
    assert missing_body["service_config_write_authority"] is False
    assert missing_body["persistent_supervision_execution_authority"] is False
    assert missing_body["persistent_supervision_enablement_authority_granted"] is False
    assert "persistent_supervision_enablement_authority_not_granted" in missing_body["blockers"]
    assert client.get("/approvals/list?status=pending").json()["items"] == []

    host_request = client.post(
        "/lens/host/supervision/authority/request",
        json={
            "actor": "test.system.write",
            "reason": "operator wants host supervision authority reviewed first",
        },
    )
    assert host_request.status_code == 200
    host_approval_id = str(host_request.json()["approval_id"])
    assert host_approval_id
    host_decision = client.post(
        "/approvals/decision",
        json={
            "id": host_approval_id,
            "action": "approve",
            "actor": "test.approvals.decision",
            "comment": "approved only as host supervision authority prerequisite",
        },
    )
    assert host_decision.status_code == 200
    assert host_decision.json()["status"] == "approved"
    host_grant = client.post(
        "/lens/host/supervision/authority",
        json={
            "approval_id": host_approval_id,
            "actor": "test.system.write",
            "reason": "grant host supervision authority prerequisite",
        },
    )
    assert host_grant.status_code == 200
    assert host_grant.json()["status"] == "authority_granted"

    enablement_request = client.post(
        "/lens/host/persistent-supervision/enablement/authority/request",
        json={
            "actor": "test.system.write",
            "reason": "operator wants persistent supervision enablement authority reviewed",
        },
    )
    assert enablement_request.status_code == 200
    enablement_approval_id = str(enablement_request.json()["approval_id"])
    assert enablement_approval_id
    enablement_decision = client.post(
        "/approvals/decision",
        json={
            "id": enablement_approval_id,
            "action": "approve",
            "actor": "test.approvals.decision",
            "comment": "approved only as persistent supervision enablement authority prerequisite",
        },
    )
    assert enablement_decision.status_code == 200
    assert enablement_decision.json()["status"] == "approved"
    enablement_grant = client.post(
        "/lens/host/persistent-supervision/enablement/authority",
        json={
            "approval_id": enablement_approval_id,
            "actor": "test.system.write",
            "reason": "grant persistent supervision enablement authority prerequisite",
        },
    )
    assert enablement_grant.status_code == 200
    enablement_grant_body = enablement_grant.json()
    assert enablement_grant_body["status"] == "authority_granted"
    enablement_receipt_id = enablement_grant_body["receipt"]["receipt_id"]

    requested = client.post(
        "/lens/host/persistent-supervision/enablement/execution/request",
        json={
            "actor": "test.system.write",
            "reason": "prove governed persistent supervision execution authority request",
        },
    )
    assert requested.status_code == 200
    body = requested.json()
    assert body["status"] == "approval_requested"
    assert body["approval_requested"] is True
    assert body["applied"] is False
    assert body["executed"] is False
    assert body["authority_granted"] is False
    assert body["persistent_supervision_enablement_authority_granted"] is True
    assert body["active_enablement_authority_grant_receipt_id"] == enablement_receipt_id
    assert body["service_config_write_authority"] is False
    assert body["persistent_supervision_execution_authority"] is False
    assert body["action"] == "lens.host.persistent_supervision_enablement_execution_authority"
    assert body["governance"]["approval_request_write"] is True
    assert body["governance"]["persistent_supervision_enablement_authority"] is True
    assert body["governance"]["service_config_write_authority"] is False
    assert body["governance"]["persistent_supervision_execution_authority"] is False
    approval_id = str(body["approval_id"])
    assert approval_id

    pending_path = data_root / "approvals" / "pending" / f"{approval_id}.json"
    pending_payload = json.loads(pending_path.read_text(encoding="utf-8"))
    assert pending_payload["action"] == "lens.host.persistent_supervision_enablement_execution_authority"
    assert pending_payload["reason"] == "prove governed persistent supervision execution authority request"
    payload = pending_payload["payload"]
    assert payload["request_kind"] == "lens.host.persistent_supervision_enablement_execution_authority.request"
    assert payload["route"] == "/lens/host/persistent-supervision/enablement/execution/request"
    assert payload["readback_route"] == "/lens/host/persistent-supervision/enablement/execution/requests"
    assert payload["readiness_route"] == "/lens/host/persistent-supervision/enablement/execution/readiness"
    assert payload["active_enablement_authority_grant_receipt_id"] == enablement_receipt_id
    assert payload["denial_boundary"]["boundary_ready"] is True
    assert payload["denial_boundary"]["applied"] is False
    assert payload["denial_boundary"]["executed"] is False
    assert payload["denial_boundary"]["service_config_updated"] is False
    assert payload["denial_boundary"]["persistent_supervision_enablement_authority_granted"] is True
    assert payload["readiness"]["enablement_authority_granted"] is True
    assert payload["readiness"]["service_config_write_authority"] is False
    assert payload["readiness"]["persistent_supervision_execution_authority"] is False
    assert "service_config_write_authority_not_granted" in payload["blockers"]
    assert "persistent_supervision_execution_authority_not_granted" in payload["blockers"]
    assert payload["governance"]["approval_request_write"] is True
    assert payload["governance"]["service_config_write_authority"] is False
    assert payload["governance"]["persistent_supervision_execution_authority"] is False

    readback = client.get("/lens/host/persistent-supervision/enablement/execution/requests?limit=10")
    assert readback.status_code == 200
    readback_body = readback.json()
    assert readback_body["kind"] == "lens.host.persistent_supervision_enablement_execution.request_readback"
    assert readback_body["status"] == "pending_review"
    assert readback_body["pending_count"] == 1
    assert readback_body["approved_count"] == 0
    assert readback_body["latest"]["id"] == approval_id
    assert readback_body["active_enablement_authority_grant_receipt_id"] == enablement_receipt_id
    assert readback_body["authority_granted"] is False
    assert readback_body["service_config_write_authority"] is False
    assert readback_body["persistent_supervision_execution_authority"] is False

    pending_readiness = client.get(
        "/lens/host/persistent-supervision/enablement/execution/readiness"
        f"?limit=10&approval_id={approval_id}&actor=test.system.write"
    )
    assert pending_readiness.status_code == 200
    pending_readiness_body = pending_readiness.json()
    assert pending_readiness_body["kind"] == "lens.host.persistent_supervision_enablement_execution.readiness_audit"
    assert pending_readiness_body["status"] == "blocked"
    assert pending_readiness_body["approval_id"] == approval_id
    assert pending_readiness_body["approval_ready"] is False
    assert pending_readiness_body["request_readback_ready"] is True
    assert pending_readiness_body["boundary_observed"] is True
    assert pending_readiness_body["enablement_authority_granted"] is True
    assert pending_readiness_body["active_enablement_authority_grant_receipt_id"] == enablement_receipt_id
    assert "persistent_supervision_enablement_execution_approval_not_approved" in pending_readiness_body["blockers"]
    assert pending_readiness_body["service_config_write_authority"] is False
    assert pending_readiness_body["persistent_supervision_execution_authority"] is False

    pending_denial = client.post(
        "/lens/host/persistent-supervision/enablement/execution",
        json={
            "approval_id": approval_id,
            "actor": "test.system.write",
            "reason": "attempt persistent supervision execution before approval decision",
        },
    )
    assert pending_denial.status_code == 200
    pending_denial_body = pending_denial.json()
    assert pending_denial_body["kind"] == "lens.host.persistent_supervision_enablement_execution.denial"
    assert pending_denial_body["status"] == "blocked"
    assert pending_denial_body["approval_id"] == approval_id
    assert pending_denial_body["approval"]["ready"] is False
    assert pending_denial_body["persistent_supervision_enablement_authority_granted"] is True
    assert pending_denial_body["active_enablement_authority_grant_receipt_id"] == enablement_receipt_id
    assert pending_denial_body["applied"] is False
    assert pending_denial_body["executed"] is False
    assert pending_denial_body["service_config_updated"] is False
    assert pending_denial_body["service_config_write_authority"] is False
    assert pending_denial_body["persistent_supervision_execution_authority"] is False
    assert "persistent_supervision_enablement_execution_approval_not_approved" in pending_denial_body["blockers"]

    decided = client.post(
        "/approvals/decision",
        json={
            "id": approval_id,
            "action": "approve",
            "actor": "test.approvals.decision",
            "comment": "approved only as a persistent supervision execution authority review decision",
        },
    )
    assert decided.status_code == 200
    assert decided.json()["status"] == "approved"

    approved_denial = client.post(
        "/lens/host/persistent-supervision/enablement/execution",
        json={
            "approval_id": approval_id,
            "actor": "test.system.write",
            "reason": "attempt persistent supervision execution after approval decision",
        },
    )
    assert approved_denial.status_code == 200
    approved_denial_body = approved_denial.json()
    assert approved_denial_body["kind"] == "lens.host.persistent_supervision_enablement_execution.denial"
    assert approved_denial_body["status"] == "denied_no_service_config_write_authority"
    assert approved_denial_body["approval_id"] == approval_id
    assert approved_denial_body["approval"]["ready"] is True
    assert approved_denial_body["approval"]["status"] == "approved"
    assert approved_denial_body["persistent_supervision_enablement_authority_granted"] is True
    assert approved_denial_body["active_enablement_authority_grant_receipt_id"] == enablement_receipt_id
    assert approved_denial_body["boundary_ready"] is True
    assert approved_denial_body["applied"] is False
    assert approved_denial_body["executed"] is False
    assert approved_denial_body["service_config_updated"] is False
    assert approved_denial_body["persistent_supervision_enablement_allowed"] is False
    assert approved_denial_body["resident_claim_allowed"] is False
    assert approved_denial_body["service_config_write_authority"] is False
    assert approved_denial_body["persistent_supervision_execution_authority"] is False
    assert approved_denial_body["receipt_write_authority"] is False
    assert "persistent_supervision_enablement_execution_approval_not_approved" not in (approved_denial_body["blockers"])
    assert "service_config_write_authority_not_granted" in approved_denial_body["blockers"]
    assert "persistent_supervision_execution_authority_not_granted" in approved_denial_body["blockers"]
    assert approved_denial_body["denial"]["would_update_service_config"] is False
    assert approved_denial_body["denial"]["would_enable_persistent_supervision"] is False
    assert approved_denial_body["denial"]["would_start_service"] is False
    assert approved_denial_body["denial"]["would_write_receipt"] is False
    assert approved_denial_body["denial"]["would_write_memory"] is False
    assert approved_denial_body["denial"]["would_claim_resident"] is False
    assert approved_denial_body["governance"]["denial_boundary"] is True
    assert approved_denial_body["governance"]["approval_request_write"] is False
    assert approved_denial_body["governance"]["service_config_write_authority"] is False
    assert approved_denial_body["governance"]["persistent_supervision_execution_authority"] is False

    approved_readiness = client.get(
        "/lens/host/persistent-supervision/enablement/execution/readiness"
        f"?limit=10&approval_id={approval_id}&actor=test.system.write"
    )
    assert approved_readiness.status_code == 200
    approved_readiness_body = approved_readiness.json()
    assert approved_readiness_body["approval_ready"] is True
    assert approved_readiness_body["ready"] is False
    assert approved_readiness_body["authority_granted"] is False
    assert approved_readiness_body["service_config_write_authority"] is False
    assert approved_readiness_body["persistent_supervision_execution_authority"] is False
    assert (
        "persistent_supervision_enablement_execution_approval_not_approved" not in (approved_readiness_body["blockers"])
    )
    assert "service_config_write_authority_not_granted" in approved_readiness_body["blockers"]
    assert "persistent_supervision_execution_authority_not_granted" in approved_readiness_body["blockers"]
    requirements = {item["id"]: item for item in approved_readiness_body["requirements"]}
    assert requirements["exact_persistent_supervision_enablement_execution_approval"]["ready"] is True
    assert requirements["active_persistent_supervision_enablement_authority_grant"]["ready"] is True
    assert requirements["persistent_supervision_enablement_execution_request_readback"]["ready"] is True
    assert requirements["persistent_supervision_enablement_execution_denial_boundary"]["ready"] is True
    assert requirements["service_config_write_authority"]["ready"] is False
    assert requirements["persistent_supervision_execution_authority"]["ready"] is False

    approved_readback = client.get("/lens/host/persistent-supervision/enablement/execution/requests?limit=10")
    assert approved_readback.status_code == 200
    approved_readback_body = approved_readback.json()
    assert approved_readback_body["status"] == "approved_no_authority"
    assert approved_readback_body["pending_count"] == 0
    assert approved_readback_body["approved_count"] == 1
    assert approved_readback_body["authority_granted"] is False

    execution_grant = client.post(
        "/lens/host/persistent-supervision/enablement/execution/authority",
        json={
            "approval_id": approval_id,
            "actor": "test.system.write",
            "reason": "grant bounded persistent supervision execution authority without runtime mutation",
        },
    )
    assert execution_grant.status_code == 200
    execution_grant_body = execution_grant.json()
    assert execution_grant_body["kind"] == "lens.host.persistent_supervision_enablement_execution_authority.grant"
    assert execution_grant_body["status"] == "authority_granted"
    assert execution_grant_body["approval_id"] == approval_id
    assert execution_grant_body["approval"]["found"] is True
    assert execution_grant_body["approval"]["status"] == "approved"
    assert execution_grant_body["approval"]["approved"] is True
    assert execution_grant_body["enablement_authority"]["active"] is True
    assert execution_grant_body["enablement_authority"]["receipt_id"] == enablement_receipt_id
    assert execution_grant_body["authority_granted"] is True
    assert execution_grant_body["grant_ready"] is True
    assert execution_grant_body["ready"] is True
    assert execution_grant_body["applied"] is True
    assert execution_grant_body["executed"] is False
    assert execution_grant_body["service_config_write_authority"] is True
    assert execution_grant_body["persistent_supervision_execution_authority"] is True
    assert execution_grant_body["receipt_write_authority"] is True
    assert execution_grant_body["persistent_supervision_enablement_allowed"] is False
    assert execution_grant_body["service_config_updated"] is False
    assert execution_grant_body["resident_claim_allowed"] is False
    assert execution_grant_body["receipt_route"] == (
        "/lens/host/persistent-supervision/enablement/execution/authority/grants"
    )
    assert execution_grant_body["receipt_written"] is True
    assert execution_grant_body["blockers"] == []
    assert execution_grant_body["grant"]["would_update_service_config"] is False
    assert execution_grant_body["grant"]["would_enable_persistent_supervision"] is False
    assert execution_grant_body["grant"]["would_start_service"] is False
    assert execution_grant_body["grant"]["would_write_memory"] is False
    assert execution_grant_body["grant"]["would_claim_resident"] is False
    assert execution_grant_body["governance"]["execution_authority"] is False
    assert execution_grant_body["governance"]["approval_decision_authority"] is False
    assert execution_grant_body["governance"]["service_config_write_authority"] is True
    assert execution_grant_body["governance"]["persistent_supervision_execution_authority"] is True
    assert execution_grant_body["governance"]["receipt_write_authority"] is True
    assert execution_grant_body["governance"]["memory_write"] is False
    assert execution_grant_body["governance"]["resident_claim_authority"] is False
    execution_receipt = execution_grant_body["receipt"]
    execution_receipt_id = execution_receipt["receipt_id"]
    assert execution_receipt["kind"] == (
        "lens.host.persistent_supervision_enablement_execution_authority.grant.receipt"
    )
    assert execution_receipt["approval_id"] == approval_id
    assert execution_receipt["enablement_authority"]["active"] is True
    assert execution_receipt["enablement_authority"]["receipt_id"] == enablement_receipt_id
    assert execution_receipt["authority_boundary"]["applied"] is True
    assert execution_receipt["authority_boundary"]["executed"] is False
    assert execution_receipt["authority_boundary"]["service_config_write_authority"] is True
    assert execution_receipt["authority_boundary"]["persistent_supervision_execution_authority"] is True
    assert execution_receipt["authority_boundary"]["service_config_updated"] is False
    assert execution_receipt["authorities"]["service_config_write_authority"] is True
    assert execution_receipt["authorities"]["persistent_supervision_execution_authority"] is True
    assert execution_receipt["authorities"]["receipt_write_authority"] is True
    assert execution_receipt["authorities"]["resident_claim_authority"] is False
    assert execution_receipt["governance"]["execution_authority"] is False
    assert execution_receipt["governance"]["service_config_write_authority"] is True
    assert execution_receipt["governance"]["persistent_supervision_execution_authority"] is True
    assert execution_receipt["governance"]["memory_write"] is False
    assert execution_receipt["governance"]["resident_claim_authority"] is False

    execution_grants = client.get(
        f"/lens/host/persistent-supervision/enablement/execution/authority/grants?limit=10&approval_id={approval_id}"
    )
    assert execution_grants.status_code == 200
    execution_grants_body = execution_grants.json()
    assert execution_grants_body["kind"] == (
        "lens.host.persistent_supervision_enablement_execution_authority.grant_receipts"
    )
    assert execution_grants_body["approval_id"] == approval_id
    assert execution_grants_body["total"] == 1
    assert execution_grants_body["active_latest"]["receipt_id"] == execution_receipt_id
    assert execution_grants_body["authority_granted"] is True
    assert execution_grants_body["service_config_write_authority"] is True
    assert execution_grants_body["persistent_supervision_execution_authority"] is True

    granted_readback = client.get("/lens/host/persistent-supervision/enablement/execution/requests?limit=10")
    assert granted_readback.status_code == 200
    granted_readback_body = granted_readback.json()
    assert granted_readback_body["status"] == "authority_granted"
    assert granted_readback_body["active_enablement_authority_grant_receipt_id"] == enablement_receipt_id
    assert granted_readback_body["active_execution_authority_grant_receipt_id"] == execution_receipt_id
    assert granted_readback_body["authority_granted"] is True
    assert granted_readback_body["service_config_write_authority"] is True
    assert granted_readback_body["persistent_supervision_execution_authority"] is True
    assert granted_readback_body["persistent_supervision_enablement_allowed"] is False
    assert granted_readback_body["resident_claim_allowed"] is False

    granted_readiness = client.get(
        "/lens/host/persistent-supervision/enablement/execution/readiness"
        f"?limit=10&approval_id={approval_id}&actor=test.system.write"
    )
    assert granted_readiness.status_code == 200
    granted_readiness_body = granted_readiness.json()
    assert granted_readiness_body["approval_ready"] is True
    assert granted_readiness_body["ready"] is False
    assert granted_readiness_body["authority_granted"] is True
    assert granted_readiness_body["execution_authority_granted"] is True
    assert granted_readiness_body["active_execution_authority_grant_receipt_id"] == execution_receipt_id
    assert granted_readiness_body["service_config_write_authority"] is True
    assert granted_readiness_body["persistent_supervision_execution_authority"] is True
    assert granted_readiness_body["receipt_write_authority"] is True
    assert granted_readiness_body["resident_claim_allowed"] is False
    assert "service_config_write_authority_not_granted" not in granted_readiness_body["blockers"]
    assert "persistent_supervision_execution_authority_not_granted" not in granted_readiness_body["blockers"]
    assert "receipt_write_authority_not_granted" not in granted_readiness_body["blockers"]
    assert "resident_claim_authority_not_granted" in granted_readiness_body["blockers"]
    granted_requirements = {item["id"]: item for item in granted_readiness_body["requirements"]}
    assert granted_requirements["service_config_write_authority"]["ready"] is True
    assert granted_requirements["persistent_supervision_execution_authority"]["ready"] is True
    assert granted_requirements["receipt_write_authority"]["ready"] is True
    assert granted_requirements["resident_claim_authority"]["ready"] is False

    granted_denial = client.post(
        "/lens/host/persistent-supervision/enablement/execution",
        json={
            "approval_id": approval_id,
            "actor": "test.system.write",
            "reason": "prove execution authority still stops before resident claim",
        },
    )
    assert granted_denial.status_code == 200
    granted_denial_body = granted_denial.json()
    assert granted_denial_body["status"] == "denied_no_resident_claim_authority"
    assert granted_denial_body["authority_granted"] is True
    assert granted_denial_body["active_execution_authority_grant_receipt_id"] == execution_receipt_id
    assert granted_denial_body["service_config_write_authority"] is True
    assert granted_denial_body["persistent_supervision_execution_authority"] is True
    assert granted_denial_body["receipt_write_authority"] is True
    assert granted_denial_body["applied"] is False
    assert granted_denial_body["executed"] is False
    assert granted_denial_body["service_config_updated"] is False
    assert granted_denial_body["persistent_supervision_enablement_allowed"] is False
    assert granted_denial_body["resident_claim_allowed"] is False
    assert "service_config_write_authority_not_granted" not in granted_denial_body["blockers"]
    assert "persistent_supervision_execution_authority_not_granted" not in granted_denial_body["blockers"]
    assert "receipt_write_authority_not_granted" not in granted_denial_body["blockers"]
    assert "resident_claim_authority_not_granted" in granted_denial_body["blockers"]
    assert granted_denial_body["denial"]["would_update_service_config"] is False
    assert granted_denial_body["denial"]["would_enable_persistent_supervision"] is False
    assert granted_denial_body["denial"]["would_start_service"] is False
    assert granted_denial_body["denial"]["would_write_memory"] is False
    assert granted_denial_body["denial"]["would_claim_resident"] is False

    status = client.get("/lens/status?limit=10")
    assert status.status_code == 200
    status_body = status.json()
    resident_host = status_body["resident_host"]
    assert resident_host["persistent_supervision_enablement_execution_route"] == (
        "/lens/host/persistent-supervision/enablement/execution"
    )
    assert resident_host["persistent_supervision_enablement_execution_request_route"] == (
        "/lens/host/persistent-supervision/enablement/execution/request"
    )
    assert resident_host["persistent_supervision_enablement_execution_requests"]["approved_count"] == 1
    assert resident_host["persistent_supervision_enablement_execution_requests"]["authority_granted"] is True
    assert (
        resident_host["persistent_supervision_enablement_execution_requests"][
            "active_execution_authority_grant_receipt_id"
        ]
        == execution_receipt_id
    )
    assert resident_host["persistent_supervision_enablement_execution_denial_route"] == (
        "/lens/host/persistent-supervision/enablement/execution"
    )
    assert resident_host["persistent_supervision_enablement_execution_denial"]["boundary_ready"] is True
    assert resident_host["persistent_supervision_enablement_execution_denial"]["applied"] is False
    assert resident_host["persistent_supervision_enablement_execution_denial"]["executed"] is False
    assert resident_host["persistent_supervision_enablement_execution_denial"]["service_config_updated"] is False
    assert resident_host["persistent_supervision_enablement_execution_authority_grant_route"] == (
        "/lens/host/persistent-supervision/enablement/execution/authority"
    )
    assert resident_host["persistent_supervision_enablement_execution_authority_grants_route"] == (
        "/lens/host/persistent-supervision/enablement/execution/authority/grants"
    )
    assert resident_host["persistent_supervision_enablement_execution_authority_grants"]["authority_granted"] is True
    assert (
        resident_host["persistent_supervision_enablement_execution_authority_grants"]["active_latest"]["receipt_id"]
        == execution_receipt_id
    )
    assert resident_host["persistent_supervision_enablement_execution_readiness"]["request_readback_ready"] is True
    criterion = _criterion(status_body, "persistent_supervision_enablement_execution_readiness_audit")
    assert criterion["status"] == "blocked"
    assert criterion["request_readback_ready"] is True
    assert criterion["boundary_observed"] is True
    assert criterion["enablement_authority_granted"] is True
    assert criterion["active_enablement_authority_grant_receipt_id"] == enablement_receipt_id
    assert criterion["execution_authority_granted"] is True
    assert criterion["active_execution_authority_grant_receipt_id"] == execution_receipt_id
    assert criterion["service_config_write_authority"] is True
    assert criterion["persistent_supervision_execution_authority"] is True
    grant_receipt_criterion = _criterion(
        status_body,
        "persistent_supervision_enablement_execution_authority_grant_receipt_readback",
    )
    assert grant_receipt_criterion["receipt_count"] == 1
    assert grant_receipt_criterion["active_receipt_id"] == execution_receipt_id
    assert grant_receipt_criterion["authority_granted"] is True
    assert grant_receipt_criterion["service_config_write_authority"] is True
    assert grant_receipt_criterion["persistent_supervision_execution_authority"] is True
    denial_criterion = _criterion(status_body, "persistent_supervision_enablement_execution_denial_boundary")
    assert denial_criterion["status"] == "blocked"
    assert denial_criterion["boundary_ready"] is True
    assert denial_criterion["applied"] is False
    assert denial_criterion["executed"] is False
    assert denial_criterion["service_config_updated"] is False
    assert denial_criterion["authority_granted"] is True
    assert denial_criterion["active_execution_authority_grant_receipt_id"] == execution_receipt_id
    assert denial_criterion["service_config_write_authority"] is True
    assert denial_criterion["persistent_supervision_execution_authority"] is True
    command = next(
        item
        for item in status_body["command_palette"]["commands"]
        if item["id"] == "lens.host.persistent_supervision_enablement_execution_authority.request"
    )
    assert command["route"] == "/lens/host/persistent-supervision/enablement/execution/request"
    assert command["method"] == "POST"
    assert command["mutates"] is True
    assert command["write_guard"] == (
        "system.write approval request; requires enablement authority; no service config mutation"
    )
    assert command["execution_authority"] is False
    assert command["approval_decision_authority"] is False
    grant_command = next(
        item
        for item in status_body["command_palette"]["commands"]
        if item["id"] == "lens.host.persistent_supervision_enablement_execution_authority.grant"
    )
    assert grant_command["route"] == "/lens/host/persistent-supervision/enablement/execution/authority"
    assert grant_command["method"] == "POST"
    assert grant_command["mutates"] is True
    assert grant_command["write_guard"] == (
        "system.write plus exact approved execution authority request and active enablement grant; "
        "writes authority receipt only"
    )
    assert grant_command["execution_authority"] is False
    assert grant_command["approval_decision_authority"] is False
    assert not (data_root / "runtime" / "lens-host-supervisor" / "status.json").exists()
    assert not (data_root / "runtime" / "lens-host" / "status.json").exists()
    assert not (data_root / "runtime" / "lens-host" / "lens-host.pid").exists()


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
    resident_surface = body["resident_surface"]
    resident_surface_runtime = resident_surface["resident_surface_runtime"]
    assert resident_surface["foreground_runtime_observed"] is True
    assert resident_surface["resident_surface_ready"] is False
    assert resident_surface["resident_claim_allowed"] is False
    assert resident_surface_runtime["status"] == "foreground_runtime_observed"
    assert resident_surface_runtime["runtime_state_status"] == "foreground_running"
    assert resident_surface_runtime["pid"] == os.getpid()
    assert resident_surface_runtime["process_alive"] is True
    assert resident_surface_runtime["foreground_runtime_observed"] is True
    assert resident_surface_runtime["foreground_session_only"] is True
    assert resident_surface_runtime["runtime_ready"] is False
    assert resident_surface_runtime["resident_claim_allowed"] is False
    assert "resident_surface_runtime_missing" not in resident_surface["blockers"]
    assert "resident_surface_runtime_not_supervised" in resident_surface["blockers"]
    assert "resident_surface_not_resident" in resident_surface["blockers"]
    assert resident_surface_runtime["blockers"] == [
        "resident_surface_runtime_not_supervised",
        "resident_surface_not_resident",
    ]
    for runtime_contract in (
        body["resident_runtime_preflight"],
        body["resident_runtime_policy"],
        body["resident_runtime_plan"],
        body["resident_runtime_denial"],
        body["resident_surface_activation"],
    ):
        assert "resident_surface_runtime_missing" not in runtime_contract["blockers"]
        assert "resident_surface_runtime_not_supervised" in runtime_contract["blockers"]
        assert "resident_surface_not_resident" in runtime_contract["blockers"]
    assert body["resident_runtime_authority_grant"]["status"] == "blocked"
    assert "approval_id_required" in body["resident_runtime_authority_grant"]["blockers"]
    assert resident_surface_runtime["governance"]["execution_authority"] is False
    assert resident_surface_runtime["governance"]["process_supervision_authority"] is False
    assert resident_surface_runtime["governance"]["resident_claim_authority"] is False
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
        "persistent_supervision_enabled",
        "process_restart_authority",
        "service_install_authority",
        "service_control_authority",
        "receipt_write_authority",
        "resident_claim_authority",
    ]
    assert resident_host["supervision_readiness"]["prerequisites"][3]["id"] == "foreground_process_readback"
    assert resident_host["supervision_readiness"]["prerequisites"][3]["status"] == "process_observed"
    supervision_gate = resident_host["supervision_gate"]
    assert supervision_gate["resident_host_process"] is True
    assert supervision_gate["foreground_process_observed"] is True
    assert supervision_gate["resident_host_process_state"] == "foreground_observed_not_supervised"
    assert supervision_gate["resident_host_process_blocker"] == "resident_host_process_not_supervised"
    assert "resident_host_process_missing" not in supervision_gate["blockers"]
    assert "resident_host_process_not_supervised" in supervision_gate["blockers"]
    assert "resident_host_process_missing" not in resident_host["blockers"]
    assert "lens_host_runtime_not_implemented" in resident_host["blockers"]
    assert resident_host["governance"]["service_control_authority"] is False
    assert resident_host["governance"]["local_process_launch_authority"] is False
    activation_response = client.get("/lens/resident-surface/activation?limit=1")
    assert activation_response.status_code == 200
    activation_body = activation_response.json()
    assert "resident_surface_runtime_missing" not in activation_body["blockers"]
    assert "resident_surface_runtime_not_supervised" in activation_body["blockers"]
    assert "resident_surface_not_resident" in activation_body["blockers"]
    assert activation_body["governance"]["execution_authority"] is False

    manifest = client.get("/lens/host/manifest")
    assert manifest.status_code == 200
    manifest_body = manifest.json()
    assert manifest_body["process_readback"] == process_readback
    assert manifest_body["service_plan"] == resident_host["service_plan"]
    assert manifest_body["governance"]["local_process_launch_authority"] is False


def test_lens_api_surfaces_host_supervisor_readback_without_authority(monkeypatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    data_root = repo_root / "data"
    _write_dev_environment(repo_root)
    _write_lens_host_status_runner(repo_root)
    _write_service_manager(repo_root)
    _write_lens_preflight_scripts(repo_root)
    _write_lens_runtime_configs(repo_root)
    _write_lens_host_service_config(repo_root)
    _write_lens_host_supervisor_state(data_root, observed_pid=9876, updated_at="2026-05-01T00:00:00Z")
    monkeypatch.setenv("FRANCIS_ROOT", str(repo_root))
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_ENV_PROFILE", "dev")
    monkeypatch.setenv("FRANCIS_RUN_MODE", "api")

    from fastapi.testclient import TestClient

    from francis.api.app import create_app
    from francis.lens import host_manifest as host_manifest_module

    fixed_now = datetime(2026, 5, 1, 0, 0, 5, tzinfo=UTC).timestamp()
    monkeypatch.setattr(host_manifest_module.time, "time", lambda: fixed_now)

    client = TestClient(create_app())
    response = client.get("/lens/status?limit=1")

    assert response.status_code == 200
    body = response.json()
    resident_host = body["resident_host"]
    supervisor_readback = resident_host["supervisor_readback"]
    assert supervisor_readback["status"] == "supervised_session_completed"
    assert supervisor_readback["readback_ready"] is True
    assert supervisor_readback["runtime_state_path"] == "data/runtime/lens-host-supervisor/status.json"
    assert supervisor_readback["state_exists"] is True
    assert supervisor_readback["state_status"] == "supervised_session_completed"
    assert supervisor_readback["mode"] == "supervise_once"
    assert supervisor_readback["observed_pid"] == 9876
    assert supervisor_readback["observed_state"] == "foreground_stopped"
    assert supervisor_readback["state_age_seconds"] is not None
    assert 0 <= supervisor_readback["state_age_seconds"] <= supervisor_readback["freshness_window_seconds"]
    assert supervisor_readback["freshness_window_seconds"] == 900
    assert supervisor_readback["freshness_status"] == "fresh"
    assert supervisor_readback["state_stale"] is False
    assert supervisor_readback["fresh_readback"] is True
    assert supervisor_readback["bounded_supervisor_observed"] is True
    assert supervisor_readback["supervised_session_completed"] is True
    assert supervisor_readback["fresh_bounded_supervisor_observed"] is True
    assert supervisor_readback["fresh_supervised_session_completed"] is True
    assert supervisor_readback["resident_supervised_runtime"] is False
    assert supervisor_readback["resident_claim_allowed"] is False
    assert supervisor_readback["process_supervision_authority"] is False
    assert supervisor_readback["service_control_authority"] is False
    assert supervisor_readback["blocked_reason"] == "resident_supervision_not_persistent"
    assert supervisor_readback["governance"] == {
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
    }
    assert resident_host["supervisor_readback_ready"] is True
    assert resident_host["supervisor_freshness_status"] == "fresh"
    assert resident_host["supervisor_state_age_seconds"] == supervisor_readback["state_age_seconds"]
    assert resident_host["supervisor_state_stale"] is False
    assert resident_host["fresh_supervisor_readback"] is True
    assert resident_host["bounded_supervisor_observed"] is True
    assert resident_host["supervised_session_completed"] is True
    assert resident_host["fresh_bounded_supervisor_observed"] is True
    assert resident_host["fresh_supervised_session_completed"] is True
    assert resident_host["resident_supervised_runtime"] is False
    components = {item["id"]: item for item in resident_host["components"]}
    assert components["host_supervisor_readback"] == {
        "id": "host_supervisor_readback",
        "label": "Host supervisor readback",
        "status": "supervised_session_completed",
        "freshness_status": "fresh",
        "state_age_seconds": supervisor_readback["state_age_seconds"],
        "state_stale": False,
        "required_for": ["startup_supervision", "resident_presence"],
    }

    supervision_gate = resident_host["supervision_gate"]
    assert supervision_gate["supervisor_readback_ready"] is True
    assert supervision_gate["supervisor_freshness_status"] == "fresh"
    assert supervision_gate["supervisor_state_age_seconds"] == supervisor_readback["state_age_seconds"]
    assert supervision_gate["supervisor_state_stale"] is False
    assert supervision_gate["fresh_supervisor_readback"] is True
    assert supervision_gate["bounded_supervisor_observed"] is True
    assert supervision_gate["supervised_session_completed"] is True
    assert supervision_gate["fresh_bounded_supervisor_observed"] is True
    assert supervision_gate["fresh_supervised_session_completed"] is True
    assert supervision_gate["resident_supervised_runtime"] is False
    assert supervision_gate["resident_host_supervised"] is False
    assert supervision_gate["resident_claim_allowed"] is False
    assert supervision_gate["supervisor_readback"] == supervisor_readback
    assert supervision_gate["governance"]["execution_authority"] is False
    assert supervision_gate["governance"]["process_supervision_authority"] is False
    assert supervision_gate["governance"]["resident_claim_authority"] is False

    resident_surface_runtime = body["resident_surface"]["resident_surface_runtime"]
    assert resident_surface_runtime["supervisor_readback_status"] == "supervised_session_completed"
    assert resident_surface_runtime["supervisor_freshness_status"] == "fresh"
    assert resident_surface_runtime["supervisor_state_age_seconds"] == supervisor_readback["state_age_seconds"]
    assert resident_surface_runtime["supervisor_state_stale"] is False
    assert resident_surface_runtime["fresh_supervisor_readback"] is True
    assert resident_surface_runtime["bounded_supervisor_observed"] is True
    assert resident_surface_runtime["supervised_session_completed"] is True
    assert resident_surface_runtime["fresh_bounded_supervisor_observed"] is True
    assert resident_surface_runtime["fresh_supervised_session_completed"] is True
    assert resident_surface_runtime["resident_supervised_runtime"] is False
    assert resident_surface_runtime["runtime_ready"] is False
    assert resident_surface_runtime["resident_claim_allowed"] is False
    assert "resident_surface_runtime_missing" in resident_surface_runtime["blockers"]

    manifest = client.get("/lens/host/manifest")
    assert manifest.status_code == 200
    manifest_body = manifest.json()
    assert manifest_body["supervisor_readback"] == supervisor_readback
    required_bindings = {item["id"]: item for item in manifest_body["required_bindings"]}
    assert required_bindings["host_supervisor_readback"] == {
        "id": "host_supervisor_readback",
        "path": "data/runtime/lens-host-supervisor/status.json",
        "status": "supervised_session_completed",
        "freshness_status": "fresh",
        "state_age_seconds": supervisor_readback["state_age_seconds"],
        "state_stale": False,
    }
    assert manifest_body["governance"]["execution_authority"] is False
    assert manifest_body["governance"]["service_control_authority"] is False
    assert manifest_body["governance"]["mutation_authority_granted"] is False


def test_lens_api_marks_stale_host_supervisor_readback_without_authority(monkeypatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    data_root = repo_root / "data"
    _write_dev_environment(repo_root)
    _write_lens_host_status_runner(repo_root)
    _write_service_manager(repo_root)
    _write_lens_preflight_scripts(repo_root)
    _write_lens_runtime_configs(repo_root)
    _write_lens_host_service_config(repo_root)
    _write_lens_host_supervisor_state(
        data_root,
        observed_pid=2468,
        updated_at="2026-04-28T21:31:00Z",
    )
    monkeypatch.setenv("FRANCIS_ROOT", str(repo_root))
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_ENV_PROFILE", "dev")
    monkeypatch.setenv("FRANCIS_RUN_MODE", "api")

    from fastapi.testclient import TestClient

    from francis.api.app import create_app
    from francis.lens import host_manifest as host_manifest_module

    fixed_now = datetime(2026, 5, 1, 0, 0, 5, tzinfo=UTC).timestamp()
    monkeypatch.setattr(host_manifest_module.time, "time", lambda: fixed_now)

    client = TestClient(create_app())
    response = client.get("/lens/status?limit=1")

    assert response.status_code == 200
    body = response.json()
    resident_host = body["resident_host"]
    supervisor_readback = resident_host["supervisor_readback"]
    assert supervisor_readback["status"] == "supervised_session_completed"
    assert supervisor_readback["freshness_window_seconds"] == 900
    assert supervisor_readback["state_age_seconds"] > supervisor_readback["freshness_window_seconds"]
    assert supervisor_readback["freshness_status"] == "stale"
    assert supervisor_readback["state_stale"] is True
    assert supervisor_readback["fresh_readback"] is False
    assert supervisor_readback["bounded_supervisor_observed"] is True
    assert supervisor_readback["supervised_session_completed"] is True
    assert supervisor_readback["fresh_bounded_supervisor_observed"] is False
    assert supervisor_readback["fresh_supervised_session_completed"] is False
    assert supervisor_readback["resident_supervised_runtime"] is False
    assert supervisor_readback["governance"]["execution_authority"] is False
    assert supervisor_readback["governance"]["resident_claim_authority"] is False

    assert resident_host["supervisor_freshness_status"] == "stale"
    assert resident_host["supervisor_state_age_seconds"] == supervisor_readback["state_age_seconds"]
    assert resident_host["supervisor_state_stale"] is True
    assert resident_host["fresh_supervisor_readback"] is False
    assert resident_host["fresh_bounded_supervisor_observed"] is False
    assert resident_host["fresh_supervised_session_completed"] is False
    components = {item["id"]: item for item in resident_host["components"]}
    assert components["host_supervisor_readback"] == {
        "id": "host_supervisor_readback",
        "label": "Host supervisor readback",
        "status": "supervised_session_completed",
        "freshness_status": "stale",
        "state_age_seconds": supervisor_readback["state_age_seconds"],
        "state_stale": True,
        "required_for": ["startup_supervision", "resident_presence"],
    }

    supervision_gate = resident_host["supervision_gate"]
    assert supervision_gate["supervisor_freshness_status"] == "stale"
    assert supervision_gate["supervisor_state_stale"] is True
    assert supervision_gate["fresh_supervisor_readback"] is False
    assert supervision_gate["fresh_bounded_supervisor_observed"] is False
    assert supervision_gate["fresh_supervised_session_completed"] is False
    assert "host_supervisor_readback_stale" in supervision_gate["blockers"]
    assert supervision_gate["governance"]["execution_authority"] is False
    assert supervision_gate["governance"]["process_supervision_authority"] is False
    assert supervision_gate["governance"]["resident_claim_authority"] is False

    resident_surface_runtime = body["resident_surface"]["resident_surface_runtime"]
    assert resident_surface_runtime["supervisor_freshness_status"] == "stale"
    assert resident_surface_runtime["supervisor_state_stale"] is True
    assert resident_surface_runtime["fresh_supervisor_readback"] is False
    assert resident_surface_runtime["fresh_bounded_supervisor_observed"] is False
    assert resident_surface_runtime["fresh_supervised_session_completed"] is False
    assert resident_surface_runtime["resident_claim_allowed"] is False

    manifest = client.get("/lens/host/manifest")
    assert manifest.status_code == 200
    manifest_body = manifest.json()
    required_bindings = {item["id"]: item for item in manifest_body["required_bindings"]}
    assert required_bindings["host_supervisor_readback"] == {
        "id": "host_supervisor_readback",
        "path": "data/runtime/lens-host-supervisor/status.json",
        "status": "supervised_session_completed",
        "freshness_status": "stale",
        "state_age_seconds": supervisor_readback["state_age_seconds"],
        "state_stale": True,
    }
    assert manifest_body["governance"]["execution_authority"] is False
    assert manifest_body["governance"]["service_control_authority"] is False
    assert manifest_body["governance"]["mutation_authority_granted"] is False


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


def test_lens_host_supervision_authority_request_requires_system_write_without_grant(
    monkeypatch,
    tmp_path: Path,
) -> None:
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
        "/lens/host/supervision/authority/request",
        json={
            "actor": "test.lens.no_scope",
            "reason": "try to request host supervision without scope",
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
    assert body["governance"]["process_supervision_authority"] is False
    assert body["governance"]["process_restart_authority"] is False
    assert body["governance"]["service_install_authority"] is False
    assert body["governance"]["service_control_authority"] is False
    assert body["governance"]["resident_claim_authority"] is False
    assert client.get("/approvals/list?status=pending").json()["items"] == []
    assert not (data_root / "runtime" / "lens-host-supervisor" / "status.json").exists()
    assert not (data_root / "runtime" / "lens-host" / "status.json").exists()
    assert not (data_root / "runtime" / "lens-host" / "lens-host.pid").exists()


def test_lens_host_supervision_authority_request_creates_approval_only_receipt(
    monkeypatch,
    tmp_path: Path,
) -> None:
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
        "/lens/host/supervision/authority/request",
        json={
            "actor": "test.system.write",
            "reason": "prove governed host supervision authority request",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["status"] == "approval_requested"
    assert body["approval_requested"] is True
    assert body["applied"] is False
    assert body["authority_granted"] is False
    assert body["resident_claim_allowed"] is False
    assert body["action"] == "lens.host.supervision_authority"
    assert body["governance"]["approval_request_write"] is True
    assert body["governance"]["approval_action"] == "lens.host.supervision_authority"
    assert body["governance"]["process_supervision_authority"] is False
    assert body["governance"]["process_restart_authority"] is False
    assert body["governance"]["service_install_authority"] is False
    assert body["governance"]["service_control_authority"] is False
    assert body["governance"]["resident_claim_authority"] is False
    assert body["governance"]["authority_granted"] is False
    approval_id = str(body["approval_id"])
    assert approval_id

    pending_path = data_root / "approvals" / "pending" / f"{approval_id}.json"
    pending_payload = json.loads(pending_path.read_text(encoding="utf-8"))
    assert pending_payload["action"] == "lens.host.supervision_authority"
    assert pending_payload["reason"] == "prove governed host supervision authority request"
    requested = pending_payload["payload"]
    assert requested["request_kind"] == "lens.host.supervision_authority.request"
    assert requested["route"] == "/lens/host/supervision/authority/request"
    assert requested["supervision_route"] == "/lens/host/supervision"
    assert requested["grant_route"] == "/lens/host/supervision/authority"
    assert requested["readback_route"] == "/lens/host/supervision/authority/requests"
    assert requested["supervision_gate"]["ready"] is False
    assert requested["supervision_gate"]["resident_host_supervised"] is False
    assert requested["preflight"]["preflight_ready"] is True
    assert requested["preflight"]["authority_ready"] is False
    assert "process_supervision_authority" in requested["preflight"]["blocked_requirements"]
    assert "process_supervision_authority_not_granted" in requested["preflight"]["blockers"]
    assert requested["governance"]["approval_request_write"] is True
    assert requested["governance"]["process_supervision_authority"] is False
    assert requested["governance"]["service_control_authority"] is False
    assert requested["governance"]["resident_claim_authority"] is False

    readback = client.get("/lens/host/supervision/authority/requests?limit=10")
    assert readback.status_code == 200
    readback_body = readback.json()
    assert readback_body["kind"] == "lens.host.supervision_authority.request_readback"
    assert readback_body["status"] == "pending_review"
    assert readback_body["route"] == "/lens/host/supervision/authority/requests"
    assert readback_body["request_route"] == "/lens/host/supervision/authority/request"
    assert readback_body["grant_route"] == "/lens/host/supervision/authority"
    assert readback_body["pending_count"] == 1
    assert readback_body["approved_count"] == 0
    assert readback_body["total_count"] == 1
    assert readback_body["latest"]["id"] == approval_id
    assert readback_body["latest"]["action"] == "lens.host.supervision_authority"
    assert readback_body["authority_granted"] is False
    assert readback_body["resident_claim_allowed"] is False
    assert readback_body["governance"]["read_only_contract"] is True
    assert readback_body["governance"]["approval_request_write"] is False
    assert readback_body["governance"]["process_supervision_authority"] is False
    assert readback_body["governance"]["service_control_authority"] is False
    assert readback_body["governance"]["authority_granted"] is False

    lens_status = client.get("/lens/status")
    assert lens_status.status_code == 200
    status_body = lens_status.json()
    assert status_body["approvals_view"]["pending_count"] == 1
    assert status_body["resident_host"]["supervision_authority_request_route"] == (
        "/lens/host/supervision/authority/request"
    )
    assert status_body["resident_host"]["supervision_authority_requests"]["pending_count"] == 1
    command = next(
        item
        for item in status_body["command_palette"]["commands"]
        if item["id"] == "lens.host.supervision_authority.request"
    )
    assert command["route"] == "/lens/host/supervision/authority/request"
    assert command["method"] == "POST"
    assert command["mutates"] is True
    assert command["write_guard"] == "system.write approval request; no supervision authority"
    assert command["execution_authority"] is False
    assert command["approval_decision_authority"] is False
    assert not (data_root / "runtime" / "lens-host-supervisor" / "status.json").exists()
    assert not (data_root / "runtime" / "lens-host" / "status.json").exists()
    assert not (data_root / "runtime" / "lens-host" / "lens-host.pid").exists()


def test_lens_host_supervision_authority_grant_requires_approved_request_before_grant_receipt(
    monkeypatch,
    tmp_path: Path,
) -> None:
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
    missing_approval = client.post(
        "/lens/host/supervision/authority",
        json={
            "actor": "test.system.write",
            "reason": "try host supervision authority without exact approval",
        },
    )
    assert missing_approval.status_code == 200
    missing_body = missing_approval.json()
    assert missing_body["status"] == "blocked"
    assert missing_body["approval_id"] == ""
    assert missing_body["approval"]["required"] is True
    assert missing_body["approval"]["found"] is False
    assert missing_body["approval"]["approved"] is False
    assert "approval_id_required" in missing_body["blockers"]
    assert missing_body["receipt_written"] is False
    assert missing_body["governance"]["denial_receipt_write_authority"] is False
    assert missing_body["governance"]["denial_receipt_write_blocker"] == "host_supervision_authority_not_ready"

    requested = client.post(
        "/lens/host/supervision/authority/request",
        json={
            "actor": "test.system.write",
            "reason": "operator wants host supervision authority reviewed",
        },
    )
    assert requested.status_code == 200
    approval_id = str(requested.json()["approval_id"])
    assert approval_id

    pending_attempt = client.post(
        "/lens/host/supervision/authority",
        json={
            "approval_id": approval_id,
            "actor": "test.system.write",
            "reason": "try host supervision authority before approval decision",
        },
    )
    assert pending_attempt.status_code == 200
    pending_body = pending_attempt.json()
    assert pending_body["status"] == "blocked"
    assert pending_body["approval_id"] == approval_id
    assert pending_body["approval"]["status"] == "pending"
    assert pending_body["approval"]["approved"] is False
    assert "supervision_authority_approval_not_approved" in pending_body["blockers"]
    assert pending_body["receipt_written"] is False

    decided = client.post(
        "/approvals/decision",
        json={
            "id": approval_id,
            "action": "approve",
            "actor": "test.approvals.decision",
            "comment": "approved only as a host supervision authority review decision",
        },
    )
    assert decided.status_code == 200
    assert decided.json()["status"] == "approved"

    approved_attempt = client.post(
        "/lens/host/supervision/authority",
        json={
            "approval_id": approval_id,
            "actor": "test.system.write",
            "reason": "prove approved host supervision authority grants bounded lease without execution",
        },
    )
    assert approved_attempt.status_code == 200
    approved_body = approved_attempt.json()
    assert approved_body["kind"] == "lens.host.supervision_authority.grant"
    assert approved_body["status"] == "authority_granted"
    assert approved_body["approval_id"] == approval_id
    assert approved_body["approval"]["found"] is True
    assert approved_body["approval"]["status"] == "approved"
    assert approved_body["approval"]["approved"] is True
    assert "approval_id_required" not in approved_body["blockers"]
    assert "supervision_authority_approval_not_approved" not in approved_body["blockers"]
    assert "host_supervision_authority_grant_not_implemented" not in approved_body["blockers"]
    assert "process_supervision_authority_not_granted" not in approved_body["blockers"]
    assert approved_body["authority_granted"] is True
    assert approved_body["grant_ready"] is True
    assert approved_body["ready"] is True
    assert approved_body["authority_ready"] is True
    assert approved_body["supervision_ready"] is False
    assert approved_body["resident_claim_allowed"] is False
    assert approved_body["applied"] is True
    assert approved_body["executed"] is False
    assert approved_body["receipt_route"] == "/lens/host/supervision/authority/grants"
    assert approved_body["receipt_written"] is True
    receipt = approved_body["receipt"]
    assert receipt["kind"] == "lens.host.supervision_authority.grant.receipt"
    assert receipt["status"] == "authority_granted"
    assert receipt["approval_id"] == approval_id
    assert receipt["approval"]["approved"] is True
    assert receipt["lease"]["active"] is True
    assert receipt["lease"]["lease_seconds"] == 3600
    assert receipt["authority_boundary"]["applied"] is True
    assert receipt["authority_boundary"]["executed"] is False
    assert receipt["authority_boundary"]["authority_granted"] is True
    assert receipt["authorities"]["process_supervision_authority"] is True
    assert receipt["authorities"]["process_restart_authority"] is True
    assert receipt["authorities"]["service_install_authority"] is True
    assert receipt["authorities"]["service_control_authority"] is True
    assert receipt["authorities"]["receipt_write_authority"] is True
    assert receipt["authorities"]["resident_claim_authority"] is True
    assert receipt["governance"]["execution_authority"] is False
    assert receipt["governance"]["approval_decision_authority"] is False
    assert receipt["governance"]["memory_write"] is False

    denials = client.get(f"/lens/host/supervision/authority/denials?limit=10&approval_id={approval_id}")
    assert denials.status_code == 200
    denials_body = denials.json()
    assert denials_body["approval_id"] == approval_id
    assert denials_body["total"] == 0
    assert denials_body["items"] == []

    grants = client.get(f"/lens/host/supervision/authority/grants?limit=10&approval_id={approval_id}")
    assert grants.status_code == 200
    grants_body = grants.json()
    assert grants_body["approval_id"] == approval_id
    assert grants_body["total"] == 1
    assert grants_body["items"][0]["approval_id"] == approval_id
    assert grants_body["items"][0]["approval"]["approved"] is True
    assert grants_body["active_latest"]["receipt_id"] == receipt["receipt_id"]
    assert grants_body["authority_granted"] is True

    readiness = client.get(
        f"/lens/host/supervision/authority/readiness?limit=10&approval_id={approval_id}&actor=test.system.write"
    )
    assert readiness.status_code == 200
    readiness_body = readiness.json()
    assert readiness_body["approval_id"] == approval_id
    requirements = {item["id"]: item for item in readiness_body["requirements"]}
    assert requirements["exact_supervision_authority_approval"]["ready"] is True
    assert "exact_supervision_authority_approval" not in readiness_body["blocked_requirements"]
    assert requirements["host_supervision_authority_grant_receipts"]["ready"] is True
    assert requirements["authority_grant_implementation"]["ready"] is True
    assert requirements["process_supervision_authority"]["ready"] is True
    assert requirements["process_restart_authority"]["ready"] is True
    assert requirements["service_install_authority"]["ready"] is True
    assert requirements["service_control_authority"]["ready"] is True
    assert requirements["resident_claim_authority"]["ready"] is True
    assert "host_supervision_authority_grant_not_implemented" not in readiness_body["blockers"]
    assert "process_supervision_authority_not_granted" not in readiness_body["blockers"]
    assert readiness_body["receipt_count"] == 0
    assert readiness_body["grant_receipt_count"] == 1
    assert readiness_body["active_grant_receipt_id"] == receipt["receipt_id"]

    persistent_plan = client.get("/lens/host/persistent-supervision")
    assert persistent_plan.status_code == 200
    persistent_body = persistent_plan.json()
    persistent_requirements = {item["id"]: item for item in persistent_body["requirements"]}
    assert persistent_body["status"] == "blocked"
    assert persistent_body["next_smallest_truthful_gap"] == "persistent_supervision_enablement_disabled"
    assert persistent_requirements["process_supervision_enabled"]["ready"] is False
    assert persistent_requirements["persistent_supervision_enabled"]["ready"] is False
    assert persistent_requirements["process_restart_authority"]["ready"] is True
    assert persistent_requirements["service_install_authority"]["ready"] is True
    assert persistent_requirements["service_control_authority"]["ready"] is True
    assert persistent_requirements["receipt_write_authority"]["ready"] is True
    assert persistent_requirements["resident_claim_authority"]["ready"] is True

    enablement = client.get("/lens/host/persistent-supervision/enablement")
    assert enablement.status_code == 200
    enablement_body = enablement.json()
    assert enablement_body["kind"] == "lens.host.persistent_supervision_enablement.preflight"
    assert enablement_body["status"] == "blocked"
    assert enablement_body["ready"] is False
    assert enablement_body["enablement_ready"] is False
    assert enablement_body["persistent_supervision_ready"] is False
    assert enablement_body["resident_claim_allowed"] is False
    assert enablement_body["authority_grant_active"] is True
    assert enablement_body["active_grant_receipt_id"] == receipt["receipt_id"]
    assert enablement_body["next_smallest_truthful_gap"] == "persistent_supervision_enablement_disabled"
    assert enablement_body["blocked_requirements"] == [
        "process_supervision_enabled",
        "persistent_supervision_enabled",
    ]
    enablement_requirements = {item["id"]: item for item in enablement_body["requirements"]}
    assert enablement_requirements["active_host_supervision_authority_grant"]["ready"] is True
    assert enablement_requirements["process_supervision_enabled"]["ready"] is False
    assert enablement_requirements["persistent_supervision_enabled"]["ready"] is False
    assert "host_supervision_authority_grant_not_active" not in enablement_body["blockers"]
    assert "process_supervision_disabled" in enablement_body["blockers"]
    assert "persistent_supervision_disabled" in enablement_body["blockers"]
    assert enablement_body["plan"]["would_update_service_config"] is False
    assert enablement_body["plan"]["would_enable_process_supervision"] is False
    assert enablement_body["plan"]["would_enable_persistent_supervision"] is False
    assert enablement_body["plan"]["would_install_service"] is False
    assert enablement_body["plan"]["would_start_service"] is False
    assert enablement_body["plan"]["would_supervise_process"] is False
    assert enablement_body["plan"]["would_restart_process"] is False
    assert enablement_body["plan"]["would_write_memory"] is False
    assert enablement_body["plan"]["would_claim_resident"] is False
    assert enablement_body["governance"]["execution_authority"] is False
    assert enablement_body["governance"]["approval_decision_authority"] is False
    assert enablement_body["governance"]["service_config_write_authority"] is False
    assert enablement_body["governance"]["memory_write"] is False
    assert enablement_body["governance"]["mutation_authority_granted"] is False

    enablement_denial = client.post(
        "/lens/host/persistent-supervision/enablement",
        json={
            "actor": "test.system.write",
            "reason": "prove persistent supervision enablement denies config mutation after authority lease",
        },
    )
    assert enablement_denial.status_code == 200
    enablement_denial_body = enablement_denial.json()
    assert enablement_denial_body["kind"] == "lens.host.persistent_supervision_enablement.denial"
    assert enablement_denial_body["status"] == "denied_no_service_config_write_authority"
    assert enablement_denial_body["applied"] is False
    assert enablement_denial_body["executed"] is False
    assert enablement_denial_body["boundary_ready"] is True
    assert enablement_denial_body["authority_grant_active"] is True
    assert enablement_denial_body["active_grant_receipt_id"] == receipt["receipt_id"]
    assert enablement_denial_body["service_config_updated"] is False
    assert "host_supervision_authority_grant_not_active" not in enablement_denial_body["blockers"]
    assert "process_supervision_disabled" in enablement_denial_body["blockers"]
    assert "persistent_supervision_disabled" in enablement_denial_body["blockers"]
    assert "persistent_supervision_enablement_authority_not_granted" in enablement_denial_body["blockers"]
    assert "service_config_write_authority_not_granted" in enablement_denial_body["blockers"]
    assert "persistent_supervision_execution_authority_not_granted" in enablement_denial_body["blockers"]
    assert "system_write_scope_not_ready" not in enablement_denial_body["blockers"]
    assert enablement_denial_body["denial"]["reason"] == "service_config_write_authority_not_granted"
    assert enablement_denial_body["denial"]["would_update_service_config"] is False
    assert enablement_denial_body["denial"]["would_enable_process_supervision"] is False
    assert enablement_denial_body["denial"]["would_enable_persistent_supervision"] is False
    assert enablement_denial_body["denial"]["would_install_service"] is False
    assert enablement_denial_body["denial"]["would_start_service"] is False
    assert enablement_denial_body["denial"]["would_supervise_process"] is False
    assert enablement_denial_body["denial"]["would_restart_process"] is False
    assert enablement_denial_body["denial"]["would_write_memory"] is False
    assert enablement_denial_body["denial"]["would_claim_resident"] is False
    assert enablement_denial_body["governance"]["denial_boundary"] is True
    assert enablement_denial_body["governance"]["execution_authority"] is False
    assert enablement_denial_body["governance"]["approval_decision_authority"] is False
    assert enablement_denial_body["governance"]["process_supervision_authority"] is False
    assert enablement_denial_body["governance"]["service_config_write_authority"] is False
    assert enablement_denial_body["governance"]["memory_write"] is False
    assert enablement_denial_body["governance"]["resident_claim_authority"] is False

    status = client.get("/lens/status?limit=10")
    assert status.status_code == 200
    status_body = status.json()
    resident_host = status_body["resident_host"]
    assert resident_host["persistent_supervision_enablement_route"] == ("/lens/host/persistent-supervision/enablement")
    assert resident_host["persistent_supervision_enablement"]["active_grant_receipt_id"] == receipt["receipt_id"]
    assert resident_host["persistent_supervision_enablement"]["next_smallest_truthful_gap"] == (
        "persistent_supervision_enablement_disabled"
    )
    assert resident_host["persistent_supervision_enablement_denial_route"] == (
        "/lens/host/persistent-supervision/enablement"
    )
    assert resident_host["persistent_supervision_enablement_denial"]["boundary_ready"] is True
    assert resident_host["persistent_supervision_enablement_denial"]["authority_grant_active"] is True
    assert resident_host["persistent_supervision_enablement_denial"]["active_grant_receipt_id"] == receipt["receipt_id"]
    persistent_denial_criterion = _criterion(status_body, "persistent_supervision_enablement_denial_boundary")
    assert persistent_denial_criterion["boundary_ready"] is True
    assert persistent_denial_criterion["applied"] is False
    assert persistent_denial_criterion["executed"] is False
    assert persistent_denial_criterion["authority_grant_active"] is True
    assert persistent_denial_criterion["service_config_updated"] is False
    assert persistent_denial_criterion["execution_authority"] is False
    assert persistent_denial_criterion["service_config_write_authority"] is False
    assert persistent_denial_criterion["memory_write"] is False
    assert not (data_root / "runtime" / "lens-host-supervisor" / "status.json").exists()
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

    resident_runtime_preflight = client.get(
        f"/lens/resident-runtime/preflight?approval_id={approval_id}&actor=test.system.write"
    )
    assert resident_runtime_preflight.status_code == 200
    resident_runtime_preflight_body = resident_runtime_preflight.json()
    assert resident_runtime_preflight_body["kind"] == "lens.resident_runtime.activation_preflight"
    assert resident_runtime_preflight_body["status"] == "blocked"
    assert resident_runtime_preflight_body["approval_id"] == approval_id
    assert resident_runtime_preflight_body["approval"]["status"] == "approved"
    assert resident_runtime_preflight_body["approval"]["approved"] is True
    assert resident_runtime_preflight_body["permission"]["ready"] is True
    assert resident_runtime_preflight_body["operator_posture"]["ready"] is True
    assert resident_runtime_preflight_body["grant_ready"] is False
    assert resident_runtime_preflight_body["authority_grant_ready"] is False
    assert resident_runtime_preflight_body["runtime_ready"] is False
    assert resident_runtime_preflight_body["resident_claim_allowed"] is False
    assert "activation_approval_not_approved" not in resident_runtime_preflight_body["blockers"]
    assert "system_write_scope_not_ready" not in resident_runtime_preflight_body["blockers"]
    assert "resident_runtime_authority_grant_not_implemented" not in resident_runtime_preflight_body["blockers"]
    assert "resident_runtime_execution_authority_not_granted" in resident_runtime_preflight_body["blockers"]
    assert "process_supervision_authority_not_granted" in resident_runtime_preflight_body["blockers"]
    assert "tray_registration_authority_not_granted" in resident_runtime_preflight_body["blockers"]
    assert "overlay_control_authority_not_granted" in resident_runtime_preflight_body["blockers"]
    assert resident_runtime_preflight_body["governance"]["gate"] == "lens_resident_runtime_activation_preflight"
    assert resident_runtime_preflight_body["governance"]["preflight_only"] is True
    assert resident_runtime_preflight_body["governance"]["execution_authority"] is False
    assert resident_runtime_preflight_body["governance"]["process_supervision_authority"] is False
    assert resident_runtime_preflight_body["governance"]["service_control_authority"] is False
    assert resident_runtime_preflight_body["governance"]["resident_claim_authority"] is False
    assert resident_runtime_preflight_body["governance"]["memory_write"] is False

    resident_runtime_policy = client.get(
        f"/lens/resident-runtime/policy?approval_id={approval_id}&actor=test.system.write"
    )
    assert resident_runtime_policy.status_code == 200
    resident_runtime_policy_body = resident_runtime_policy.json()
    assert resident_runtime_policy_body["kind"] == "lens.resident_runtime.execution_policy_contract"
    assert resident_runtime_policy_body["status"] == "readback_ready"
    assert resident_runtime_policy_body["approval_id"] == approval_id
    assert resident_runtime_policy_body["approval"]["status"] == "approved"
    assert resident_runtime_policy_body["approval"]["approved"] is True
    assert resident_runtime_policy_body["permission"]["ready"] is True
    assert resident_runtime_policy_body["operator_posture"]["ready"] is True
    assert resident_runtime_policy_body["policy_contract_ready"] is True
    assert resident_runtime_policy_body["execution_policy_ready"] is True
    assert resident_runtime_policy_body["grant_ready"] is False
    assert resident_runtime_policy_body["runtime_ready"] is False
    assert resident_runtime_policy_body["resident_claim_allowed"] is False
    assert "activation_approval_not_approved" not in resident_runtime_policy_body["blockers"]
    assert "system_write_scope_not_ready" not in resident_runtime_policy_body["blockers"]
    assert "resident_runtime_execution_authority_not_granted" in resident_runtime_policy_body["blockers"]
    assert "resident_runtime_authority_grant_not_implemented" not in resident_runtime_policy_body["blockers"]
    policy_requirements = {step["id"]: step for step in resident_runtime_policy_body["requirements"]}
    assert policy_requirements["verify_exact_approval"]["status"] == "ready"
    assert policy_requirements["verify_actor_scope"]["status"] == "ready"
    assert policy_requirements["verify_operator_posture"]["status"] == "ready"
    assert policy_requirements["define_future_authority_grant_boundary"]["status"] == "blocked"
    assert (
        policy_requirements["define_future_authority_grant_boundary"]["source"]
        == "/lens/resident-runtime/authority-grant/grants"
    )
    assert resident_runtime_policy_body["governance"]["gate"] == "lens_resident_runtime_execution_policy_contract"
    assert resident_runtime_policy_body["governance"]["policy_contract"] is True
    assert resident_runtime_policy_body["governance"]["execution_authority"] is False
    assert resident_runtime_policy_body["governance"]["process_supervision_authority"] is False
    assert resident_runtime_policy_body["governance"]["service_control_authority"] is False
    assert resident_runtime_policy_body["governance"]["resident_claim_authority"] is False
    assert resident_runtime_policy_body["governance"]["memory_write"] is False

    runtime_authority_request = client.post(
        "/lens/resident-runtime/authority-grant/request",
        json={
            "actor": "test.system.write",
            "reason": "operator asked to review resident runtime execution authority",
        },
    )
    assert runtime_authority_request.status_code == 200
    runtime_authority_request_body = runtime_authority_request.json()
    assert runtime_authority_request_body["status"] == "approval_requested"
    assert runtime_authority_request_body["approval_requested"] is True
    assert runtime_authority_request_body["applied"] is False
    assert runtime_authority_request_body["executed"] is False
    assert runtime_authority_request_body["action"] == "lens.resident_runtime.execution_authority"
    assert runtime_authority_request_body["authority_granted"] is False
    assert runtime_authority_request_body["resident_claim_allowed"] is False
    assert runtime_authority_request_body["execution_authority"] is False
    assert runtime_authority_request_body["process_supervision_authority"] is False
    assert runtime_authority_request_body["service_control_authority"] is False
    assert runtime_authority_request_body["memory_write"] is False
    assert runtime_authority_request_body["governance"]["approval_request_write"] is True
    assert runtime_authority_request_body["governance"]["execution_authority"] is False
    assert runtime_authority_request_body["governance"]["resident_claim_authority"] is False
    runtime_authority_request_readback = client.get("/lens/resident-runtime/authority-grant/requests")
    assert runtime_authority_request_readback.status_code == 200
    runtime_authority_request_readback_body = runtime_authority_request_readback.json()
    assert runtime_authority_request_readback_body["status"] == "pending_review"
    assert runtime_authority_request_readback_body["pending_count"] == 1
    assert runtime_authority_request_readback_body["total_count"] == 1
    assert runtime_authority_request_readback_body["latest"]["id"] == runtime_authority_request_body["approval_id"]
    runtime_authority_approval_id = str(runtime_authority_request_body["approval_id"])
    runtime_authority_decision = client.post(
        "/approvals/decision",
        json={
            "id": runtime_authority_approval_id,
            "action": "approve",
            "actor": "test.approvals.decision",
            "comment": "approved only as a resident runtime authority review decision",
        },
    )
    assert runtime_authority_decision.status_code == 200
    assert runtime_authority_decision.json()["status"] == "approved"

    resident_runtime_authority_grant = client.post(
        "/lens/resident-runtime/authority-grant",
        json={
            "approval_id": runtime_authority_approval_id,
            "actor": "test.system.write",
            "reason": "operator approved resident runtime execution authority receipt",
        },
    )
    assert resident_runtime_authority_grant.status_code == 200
    resident_runtime_authority_grant_body = resident_runtime_authority_grant.json()
    assert resident_runtime_authority_grant_body["kind"] == "lens.resident_runtime.execution_authority_grant.grant"
    assert resident_runtime_authority_grant_body["status"] == "authority_granted"
    assert resident_runtime_authority_grant_body["route"] == "/lens/resident-runtime/authority-grant"
    assert resident_runtime_authority_grant_body["approval_id"] == runtime_authority_approval_id
    assert resident_runtime_authority_grant_body["authority_granted"] is True
    assert resident_runtime_authority_grant_body["resident_runtime_execution_authority"] is True
    assert resident_runtime_authority_grant_body["applied"] is True
    assert resident_runtime_authority_grant_body["executed"] is False
    assert resident_runtime_authority_grant_body["boundary_ready"] is True
    assert resident_runtime_authority_grant_body["permission"]["ready"] is True
    assert resident_runtime_authority_grant_body["approval"]["approved"] is True
    assert resident_runtime_authority_grant_body["grant_denial"] == {}
    assert resident_runtime_authority_grant_body["grant"]["would_grant_resident_runtime_execution_authority"] is True
    assert resident_runtime_authority_grant_body["grant"]["would_grant_execution_authority"] is False
    assert resident_runtime_authority_grant_body["grant"]["would_grant_local_process_launch_authority"] is False
    assert resident_runtime_authority_grant_body["grant"]["would_grant_process_supervision_authority"] is False
    assert resident_runtime_authority_grant_body["grant"]["would_grant_process_restart_authority"] is False
    assert resident_runtime_authority_grant_body["grant"]["would_grant_service_install_authority"] is False
    assert resident_runtime_authority_grant_body["grant"]["would_grant_service_control_authority"] is False
    assert resident_runtime_authority_grant_body["grant"]["would_grant_tray_registration_authority"] is False
    assert resident_runtime_authority_grant_body["grant"]["would_grant_hotkey_registration_authority"] is False
    assert resident_runtime_authority_grant_body["grant"]["would_grant_overlay_control_authority"] is False
    assert resident_runtime_authority_grant_body["grant"]["would_grant_receipt_write_authority"] is True
    assert resident_runtime_authority_grant_body["grant"]["would_grant_memory_write"] is False
    assert resident_runtime_authority_grant_body["grant"]["would_grant_resident_claim"] is False
    assert resident_runtime_authority_grant_body["grant"]["grant_receipt_written"] is True
    assert resident_runtime_authority_grant_body["receipt_written"] is True
    assert resident_runtime_authority_grant_body["receipt_route"] == "/lens/resident-runtime/authority-grant/grants"
    authority_grant_receipt = resident_runtime_authority_grant_body["receipt"]
    assert authority_grant_receipt["kind"] == ("lens.resident_runtime.execution_authority_grant.grant.receipt")
    assert authority_grant_receipt["status"] == "authority_granted"
    assert authority_grant_receipt["route"] == "/lens/resident-runtime/authority-grant"
    assert authority_grant_receipt["source_kind"] == ("lens.resident_runtime.execution_authority_grant.grant")
    assert authority_grant_receipt["approval_id"] == runtime_authority_approval_id
    assert authority_grant_receipt["actor"] == "test.system.write"
    assert authority_grant_receipt["approval"]["approved"] is True
    assert authority_grant_receipt["permission"]["ready"] is True
    assert authority_grant_receipt["authority_grant"]["applied"] is False
    assert authority_grant_receipt["authority_grant"]["executed"] is False
    assert authority_grant_receipt["authority_grant"]["authority_granted"] is True
    assert authority_grant_receipt["authority_grant"]["resident_runtime_execution_authority"] is True
    assert authority_grant_receipt["grant"]["would_grant_resident_runtime_execution_authority"] is True
    assert authority_grant_receipt["grant"]["would_grant_execution_authority"] is False
    assert authority_grant_receipt["governance"]["gate"] == ("lens_resident_runtime_execution_authority_grant_receipt")
    assert authority_grant_receipt["governance"]["denial_receipt_write_authority"] is False
    assert authority_grant_receipt["governance"]["execution_authority"] is False
    assert authority_grant_receipt["governance"]["resident_runtime_execution_authority"] is True
    assert authority_grant_receipt["governance"]["approval_decision_authority"] is False
    assert authority_grant_receipt["governance"]["process_supervision_authority"] is False
    assert authority_grant_receipt["governance"]["memory_write"] is False
    authority_grant_receipt_path = (
        data_root / "lens" / "resident_runtime_authority_grants" / f"{authority_grant_receipt['receipt_id']}.json"
    )
    assert authority_grant_receipt_path.exists()
    assert "system_write_scope_not_ready" not in resident_runtime_authority_grant_body["blockers"]
    assert "resident_runtime_authority_grant_not_implemented" not in resident_runtime_authority_grant_body["blockers"]
    assert "resident_runtime_execution_authority_not_granted" not in resident_runtime_authority_grant_body["blockers"]
    assert resident_runtime_authority_grant_body["governance"]["authority_grant_boundary"] is True
    assert resident_runtime_authority_grant_body["governance"]["execution_authority"] is False
    assert resident_runtime_authority_grant_body["governance"]["resident_runtime_execution_authority"] is True
    assert resident_runtime_authority_grant_body["governance"]["approval_decision_authority"] is False
    assert resident_runtime_authority_grant_body["governance"]["process_supervision_authority"] is False
    assert resident_runtime_authority_grant_body["governance"]["service_control_authority"] is False
    assert resident_runtime_authority_grant_body["governance"]["receipt_write_authority"] is True
    assert resident_runtime_authority_grant_body["governance"]["denial_receipt_write_authority"] is False
    assert resident_runtime_authority_grant_body["governance"]["resident_claim_authority"] is False
    assert resident_runtime_authority_grant_body["governance"]["memory_write"] is False

    authority_grant_grants = client.get(
        "/lens/resident-runtime/authority-grant/grants"
        f"?limit=10&approval_id={runtime_authority_approval_id}&status=authority_granted"
    )
    assert authority_grant_grants.status_code == 200
    authority_grant_grants_body = authority_grant_grants.json()
    assert authority_grant_grants_body["kind"] == ("lens.resident_runtime.execution_authority_grant.grant_receipts")
    assert authority_grant_grants_body["status"] == "readback_ready"
    assert authority_grant_grants_body["route"] == "/lens/resident-runtime/authority-grant/grants"
    assert authority_grant_grants_body["authority_grant_route"] == "/lens/resident-runtime/authority-grant"
    assert authority_grant_grants_body["approval_id"] == runtime_authority_approval_id
    assert authority_grant_grants_body["filter_status"] == "authority_granted"
    assert authority_grant_grants_body["total"] == 1
    assert authority_grant_grants_body["latest"]["receipt_id"] == authority_grant_receipt["receipt_id"]
    assert authority_grant_grants_body["active_latest"]["receipt_id"] == authority_grant_receipt["receipt_id"]
    assert authority_grant_grants_body["items"][0]["approval_id"] == runtime_authority_approval_id
    assert authority_grant_grants_body["items"][0]["authority_grant"]["authority_granted"] is True
    assert authority_grant_grants_body["items"][0]["governance"]["execution_authority"] is False
    assert authority_grant_grants_body["items"][0]["governance"]["resident_runtime_execution_authority"] is True
    assert authority_grant_grants_body["governance"]["gate"] == (
        "lens_resident_runtime_execution_authority_grant_receipts_readback"
    )
    assert authority_grant_grants_body["governance"]["read_only_contract"] is True
    assert authority_grant_grants_body["governance"]["denial_receipt_write_authority"] is False
    assert authority_grant_grants_body["governance"]["execution_authority"] is False
    assert authority_grant_grants_body["governance"]["approval_decision_authority"] is False
    assert authority_grant_grants_body["governance"]["memory_write"] is False

    authority_grant_denials = client.get(
        f"/lens/resident-runtime/authority-grant/denials?limit=10&approval_id={runtime_authority_approval_id}"
    )
    assert authority_grant_denials.status_code == 200
    assert authority_grant_denials.json()["total"] == 0

    authority_grant_readiness = client.get(
        "/lens/resident-runtime/authority-grant/readiness"
        f"?limit=10&approval_id={runtime_authority_approval_id}&actor=test.system.write"
    )
    assert authority_grant_readiness.status_code == 200
    authority_grant_readiness_body = authority_grant_readiness.json()
    assert authority_grant_readiness_body["kind"] == ("lens.resident_runtime.execution_authority_grant.readiness_audit")
    assert authority_grant_readiness_body["status"] == "blocked"
    assert authority_grant_readiness_body["audit_status"] == "complete"
    assert authority_grant_readiness_body["route"] == "/lens/resident-runtime/authority-grant/readiness"
    assert authority_grant_readiness_body["approval_id"] == runtime_authority_approval_id
    assert authority_grant_readiness_body["ready"] is False
    assert authority_grant_readiness_body["grant_ready"] is False
    assert authority_grant_readiness_body["authority_grant_ready"] is False
    assert authority_grant_readiness_body["runtime_ready"] is False
    assert authority_grant_readiness_body["resident_claim_allowed"] is False
    assert authority_grant_readiness_body["boundary_observed"] is True
    assert authority_grant_readiness_body["authority_granted"] is True
    assert authority_grant_readiness_body["resident_runtime_execution_authority"] is True
    assert authority_grant_readiness_body["grant_receipt_readback_ready"] is True
    assert authority_grant_readiness_body["denial_receipt_readback_ready"] is True
    assert authority_grant_readiness_body["receipt_count"] == 1
    assert authority_grant_readiness_body["latest_receipt_id"] == authority_grant_receipt["receipt_id"]
    readiness_requirements = {item["id"]: item for item in authority_grant_readiness_body["requirements"]}
    assert readiness_requirements["exact_resident_runtime_execution_authority_approval"]["ready"] is True
    assert readiness_requirements["actor_scope"]["ready"] is True
    assert readiness_requirements["operator_posture"]["ready"] is True
    assert readiness_requirements["execution_policy_contract"]["ready"] is True
    assert readiness_requirements["authority_grant_boundary"]["ready"] is True
    assert readiness_requirements["authority_grant_receipts"]["ready"] is True
    assert readiness_requirements["authority_grant_denial_receipts"]["ready"] is True
    assert readiness_requirements["resident_supervision_gate"]["ready"] is False
    assert readiness_requirements["summon_gate"]["ready"] is False
    assert readiness_requirements["tray_gate"]["ready"] is False
    assert readiness_requirements["overlay_gate"]["ready"] is False
    assert readiness_requirements["runtime_activation_plan"]["ready"] is False
    assert readiness_requirements["resident_runtime_execution_authority"]["ready"] is True
    assert "authority_grant_implementation" not in authority_grant_readiness_body["blocked_requirements"]
    assert "resident_runtime_execution_authority" not in authority_grant_readiness_body["blocked_requirements"]
    assert "resident_runtime_authority_grant_not_implemented" not in authority_grant_readiness_body["blockers"]
    assert "resident_runtime_execution_authority_not_granted" not in authority_grant_readiness_body["blockers"]
    assert "process_supervision_authority_not_granted" in authority_grant_readiness_body["blockers"]
    assert "tray_registration_authority_not_granted" in authority_grant_readiness_body["blockers"]
    assert authority_grant_readiness_body["governance"]["gate"] == (
        "lens_resident_runtime_execution_authority_grant_readiness_audit"
    )
    assert authority_grant_readiness_body["governance"]["read_only_contract"] is True
    assert authority_grant_readiness_body["governance"]["audit_only"] is True
    assert authority_grant_readiness_body["governance"]["execution_authority"] is False
    assert authority_grant_readiness_body["governance"]["resident_runtime_execution_authority"] is True
    assert authority_grant_readiness_body["governance"]["approval_decision_authority"] is False
    assert authority_grant_readiness_body["governance"]["process_supervision_authority"] is False
    assert authority_grant_readiness_body["governance"]["service_control_authority"] is False
    assert authority_grant_readiness_body["governance"]["tray_registration_authority"] is False
    assert authority_grant_readiness_body["governance"]["hotkey_registration_authority"] is False
    assert authority_grant_readiness_body["governance"]["overlay_control_authority"] is False
    assert authority_grant_readiness_body["governance"]["receipt_write_authority"] is False
    assert authority_grant_readiness_body["governance"]["resident_claim_authority"] is False
    assert authority_grant_readiness_body["governance"]["memory_write"] is False

    resident_runtime_plan = client.get(f"/lens/resident-runtime/plan?approval_id={approval_id}&actor=test.system.write")
    assert resident_runtime_plan.status_code == 200
    resident_runtime_plan_body = resident_runtime_plan.json()
    assert resident_runtime_plan_body["kind"] == "lens.resident_runtime.activation_plan"
    assert resident_runtime_plan_body["status"] == "blocked"
    assert resident_runtime_plan_body["execute_route"] == "/lens/resident-runtime/execute"
    assert resident_runtime_plan_body["approval_id"] == approval_id
    assert resident_runtime_plan_body["approval"]["selected_status"] == "approved"
    assert resident_runtime_plan_body["approval"]["selected_approved"] is True
    assert resident_runtime_plan_body["plan_available"] is True
    assert resident_runtime_plan_body["runtime_ready"] is False
    assert resident_runtime_plan_body["resident_claim_allowed"] is False
    runtime_steps = {step["id"]: step for step in resident_runtime_plan_body["plan"]["steps"]}
    assert runtime_steps["verify_exact_host_activation_plan"]["status"] == "ready"
    assert runtime_steps["verify_supervision_gate"]["status"] == "blocked"
    assert runtime_steps["verify_summon_gate"]["status"] == "blocked"
    assert runtime_steps["verify_tray_gate"]["status"] == "blocked"
    assert runtime_steps["verify_overlay_gate"]["status"] == "blocked"
    assert runtime_steps["activate_supervised_resident_host"]["status"] == "blocked"
    assert runtime_steps["activate_supervised_resident_host"]["authority_granted"] is False
    assert runtime_steps["register_tray_hotkey_overlay"]["authority_granted"] is False
    assert runtime_steps["record_resident_runtime_receipt"]["authority_granted"] is True
    assert resident_runtime_plan_body["plan"]["would_launch_process"] is False
    assert resident_runtime_plan_body["plan"]["would_supervise_process"] is False
    assert resident_runtime_plan_body["plan"]["would_register_tray"] is False
    assert resident_runtime_plan_body["plan"]["would_register_hotkey"] is False
    assert resident_runtime_plan_body["plan"]["would_open_overlay"] is False
    assert resident_runtime_plan_body["plan"]["would_write_receipt"] is False
    assert "activation_approval_not_approved" not in resident_runtime_plan_body["blockers"]
    assert "system_write_scope_not_ready" not in resident_runtime_plan_body["blockers"]
    assert "resident_runtime_execution_authority_not_granted" not in resident_runtime_plan_body["blockers"]
    assert "process_supervision_authority_not_granted" in resident_runtime_plan_body["blockers"]
    assert "tray_registration_authority_not_granted" in resident_runtime_plan_body["blockers"]
    assert "overlay_control_authority_not_granted" in resident_runtime_plan_body["blockers"]
    assert resident_runtime_plan_body["governance"]["gate"] == "lens_resident_runtime_activation_plan"
    assert resident_runtime_plan_body["governance"]["read_only_contract"] is True
    assert resident_runtime_plan_body["governance"]["plan_readback_only"] is True
    assert resident_runtime_plan_body["governance"]["execution_authority"] is False
    assert resident_runtime_plan_body["governance"]["resident_runtime_execution_authority"] is True
    assert resident_runtime_plan_body["governance"]["approval_decision_authority"] is False
    assert resident_runtime_plan_body["governance"]["process_supervision_authority"] is False
    assert resident_runtime_plan_body["governance"]["service_control_authority"] is False
    assert resident_runtime_plan_body["governance"]["resident_claim_authority"] is False
    assert resident_runtime_plan_body["governance"]["receipt_write_authority"] is False

    resident_surface_activation = client.get(
        f"/lens/resident-surface/activation?approval_id={approval_id}&actor=test.system.write"
    )
    assert resident_surface_activation.status_code == 200
    resident_surface_activation_body = resident_surface_activation.json()
    assert resident_surface_activation_body["kind"] == "lens.resident_surface.activation_boundary"
    assert resident_surface_activation_body["status"] == "blocked"
    assert resident_surface_activation_body["approval_id"] == approval_id
    assert resident_surface_activation_body["approval"]["selected_status"] == "approved"
    assert resident_surface_activation_body["approval"]["selected_approved"] is True
    assert resident_surface_activation_body["boundary_ready"] is True
    assert resident_surface_activation_body["activation_ready"] is False
    assert resident_surface_activation_body["resident_surface_ready"] is False
    assert resident_surface_activation_body["resident_claim_allowed"] is False
    assert resident_surface_activation_body["execution_ready"] is False
    assert resident_surface_activation_body["executed"] is False
    assert resident_surface_activation_body["applied"] is False
    assert resident_surface_activation_body["execution"]["preflight_status"] == "blocked"
    assert resident_surface_activation_body["execution"]["plan_status"] == "blocked"
    assert resident_surface_activation_body["execution"]["runtime_preflight_status"] == "blocked"
    assert resident_surface_activation_body["execution"]["runtime_policy_status"] == "readback_ready"
    assert resident_surface_activation_body["execution"]["runtime_authority_grant_status"] == "authority_granted"
    assert resident_surface_activation_body["execution"]["runtime_plan_status"] == "blocked"
    assert resident_surface_activation_body["execution"]["runtime_denial_status"] == (
        "denied_no_resident_runtime_execution_boundary"
    )
    assert resident_surface_activation_body["execution"]["denial_status"] == "denied_no_execution_authority"
    assert resident_surface_activation_body["execution"]["would_launch_process"] is False
    assert resident_surface_activation_body["execution"]["would_install_service"] is False
    assert resident_surface_activation_body["execution"]["would_start_service"] is False
    assert resident_surface_activation_body["execution"]["would_supervise_process"] is False
    assert resident_surface_activation_body["execution"]["would_restart_process"] is False
    assert resident_surface_activation_body["execution"]["would_register_tray"] is False
    assert resident_surface_activation_body["execution"]["would_register_hotkey"] is False
    assert resident_surface_activation_body["execution"]["would_open_overlay"] is False
    assert resident_surface_activation_body["execution"]["would_capture_screen"] is False
    assert resident_surface_activation_body["execution"]["would_write_memory"] is False
    assert resident_surface_activation_body["execution"]["would_write_receipt"] is False
    assert resident_surface_activation_body["execution"]["would_decide_approval"] is False
    assert resident_surface_activation_body["execution"]["would_claim_resident"] is False
    assert (
        resident_surface_activation_body["execution"]["runtime_denial_reason"]
        == "local_process_launch_authority_not_granted"
    )
    assert resident_surface_activation_body["surface"]["summon_status"] == "blocked"
    assert resident_surface_activation_body["surface"]["tray_status"] == "blocked"
    assert resident_surface_activation_body["surface"]["overlay_status"] == "blocked"
    surface_components = {item["id"]: item for item in resident_surface_activation_body["components"]}
    assert surface_components["resident_runtime_preflight"]["status"] == "blocked"
    assert surface_components["resident_runtime_preflight"]["ready"] is False
    assert surface_components["resident_runtime_policy"]["status"] == "readback_ready"
    assert surface_components["resident_runtime_policy"]["ready"] is True
    assert surface_components["resident_runtime_authority_grant"]["status"] == "authority_granted"
    assert surface_components["resident_runtime_authority_grant"]["ready"] is True
    assert surface_components["resident_runtime_plan"]["status"] == "blocked"
    assert surface_components["resident_runtime_activation_denial"]["status"] == (
        "denied_no_resident_runtime_execution_boundary"
    )
    assert surface_components["host_activation_denial"]["status"] == "denied_no_execution_authority"
    assert surface_components["summon_preflight"]["status"] == "blocked"
    assert surface_components["tray_preflight"]["status"] == "blocked"
    assert surface_components["overlay_preflight"]["status"] == "blocked"
    assert "activation_approval_not_approved" not in resident_surface_activation_body["blockers"]
    assert "system_write_scope_not_ready" not in resident_surface_activation_body["blockers"]
    assert "local_process_launch_authority_not_granted" in resident_surface_activation_body["blockers"]
    assert "resident_runtime_execution_authority_not_granted" not in resident_surface_activation_body["blockers"]
    assert "process_supervision_authority_not_granted" in resident_surface_activation_body["blockers"]
    assert "resident_surface_runtime_missing" in resident_surface_activation_body["blockers"]
    assert "resident_surface_missing" not in resident_surface_activation_body["blockers"]
    assert resident_surface_activation_body["governance"]["boundary_only"] is True
    assert resident_surface_activation_body["governance"]["activation_authority"] is False
    assert resident_surface_activation_body["governance"]["execution_authority"] is False
    assert resident_surface_activation_body["governance"]["approval_decision_authority"] is False
    assert resident_surface_activation_body["governance"]["local_process_launch_authority"] is False
    assert resident_surface_activation_body["governance"]["service_install_authority"] is False
    assert resident_surface_activation_body["governance"]["service_control_authority"] is False
    assert resident_surface_activation_body["governance"]["hotkey_registration_authority"] is False
    assert resident_surface_activation_body["governance"]["overlay_control_authority"] is False
    assert resident_surface_activation_body["governance"]["summon_authority"] is False
    assert resident_surface_activation_body["governance"]["memory_write"] is False

    denied_runtime_execution = client.post(
        "/lens/resident-runtime/execute",
        json={
            "approval_id": approval_id,
            "actor": "test.system.write",
            "reason": "operator asked to prove resident runtime stays blocked",
        },
    )
    assert denied_runtime_execution.status_code == 200
    denied_runtime_execution_body = denied_runtime_execution.json()
    assert denied_runtime_execution_body["kind"] == "lens.resident_runtime.activation.execution_denial"
    assert denied_runtime_execution_body["status"] == "denied_no_resident_runtime_execution_boundary"
    assert denied_runtime_execution_body["route"] == "/lens/resident-runtime/execute"
    assert denied_runtime_execution_body["approval_id"] == approval_id
    assert denied_runtime_execution_body["applied"] is False
    assert denied_runtime_execution_body["executed"] is False
    assert denied_runtime_execution_body["permission"]["ready"] is True
    assert denied_runtime_execution_body["resident_runtime_execution_authority"] is True
    assert denied_runtime_execution_body["plan"]["approval"]["selected_status"] == "approved"
    assert denied_runtime_execution_body["plan"]["approval"]["selected_approved"] is True
    assert denied_runtime_execution_body["plan"]["runtime_ready"] is False
    assert denied_runtime_execution_body["denial"]["reason"] == "local_process_launch_authority_not_granted"
    assert denied_runtime_execution_body["denial"]["would_launch_process"] is False
    assert denied_runtime_execution_body["denial"]["would_supervise_process"] is False
    assert denied_runtime_execution_body["denial"]["would_restart_process"] is False
    assert denied_runtime_execution_body["denial"]["would_install_service"] is False
    assert denied_runtime_execution_body["denial"]["would_start_service"] is False
    assert denied_runtime_execution_body["denial"]["would_register_tray"] is False
    assert denied_runtime_execution_body["denial"]["would_register_hotkey"] is False
    assert denied_runtime_execution_body["denial"]["would_open_overlay"] is False
    assert denied_runtime_execution_body["denial"]["would_write_memory"] is False
    assert denied_runtime_execution_body["denial"]["would_write_receipt"] is False
    assert denied_runtime_execution_body["denial"]["would_claim_resident"] is False
    assert denied_runtime_execution_body["denial"]["denial_receipt_written"] is True
    assert denied_runtime_execution_body["receipt_written"] is True
    assert denied_runtime_execution_body["receipt_route"] == "/lens/resident-runtime/denials"
    runtime_denial_receipt = denied_runtime_execution_body["receipt"]
    assert runtime_denial_receipt["kind"] == "lens.resident_runtime.activation.denial.receipt"
    assert runtime_denial_receipt["status"] == "denied_no_resident_runtime_execution_boundary"
    assert runtime_denial_receipt["route"] == "/lens/resident-runtime/execute"
    assert runtime_denial_receipt["source_kind"] == "lens.resident_runtime.activation.execution_denial"
    assert runtime_denial_receipt["approval_id"] == approval_id
    assert runtime_denial_receipt["actor"] == "test.system.write"
    assert runtime_denial_receipt["approval"]["approved"] is True
    assert runtime_denial_receipt["permission"]["ready"] is True
    assert runtime_denial_receipt["runtime"]["runtime_ready"] is False
    assert runtime_denial_receipt["runtime"]["resident_claim_allowed"] is False
    assert runtime_denial_receipt["execution"]["applied"] is False
    assert runtime_denial_receipt["execution"]["executed"] is False
    assert runtime_denial_receipt["execution"]["would_launch_process"] is False
    assert runtime_denial_receipt["execution"]["would_supervise_process"] is False
    assert runtime_denial_receipt["execution"]["would_register_tray"] is False
    assert runtime_denial_receipt["execution"]["would_open_overlay"] is False
    assert runtime_denial_receipt["execution"]["would_write_memory"] is False
    assert runtime_denial_receipt["execution"]["would_write_receipt"] is False
    assert runtime_denial_receipt["governance"]["gate"] == "lens_resident_runtime_activation_denial_receipt"
    assert runtime_denial_receipt["governance"]["denial_receipt_write_authority"] is True
    assert runtime_denial_receipt["governance"]["execution_authority"] is False
    assert runtime_denial_receipt["governance"]["approval_decision_authority"] is False
    assert runtime_denial_receipt["governance"]["process_supervision_authority"] is False
    assert runtime_denial_receipt["governance"]["service_control_authority"] is False
    assert runtime_denial_receipt["governance"]["memory_write"] is False
    runtime_denial_receipt_path = (
        data_root / "lens" / "resident_runtime_activation_denials" / f"{runtime_denial_receipt['receipt_id']}.json"
    )
    assert runtime_denial_receipt_path.exists()
    assert "activation_approval_not_approved" not in denied_runtime_execution_body["blockers"]
    assert "system_write_scope_not_ready" not in denied_runtime_execution_body["blockers"]
    assert "resident_runtime_execution_authority_not_granted" not in denied_runtime_execution_body["blockers"]
    assert "process_supervision_authority_not_granted" in denied_runtime_execution_body["blockers"]
    assert "service_control_authority_not_granted" in denied_runtime_execution_body["blockers"]
    assert "tray_registration_authority_not_granted" in denied_runtime_execution_body["blockers"]
    assert "hotkey_registration_authority_not_granted" in denied_runtime_execution_body["blockers"]
    assert "overlay_control_authority_not_granted" in denied_runtime_execution_body["blockers"]
    assert denied_runtime_execution_body["governance"]["gate"] == "lens_resident_runtime_activation_execution_denial"
    assert denied_runtime_execution_body["governance"]["execution_boundary"] is True
    assert denied_runtime_execution_body["governance"]["denial_boundary"] is True
    assert denied_runtime_execution_body["governance"]["resident_runtime_boundary"] is True
    assert denied_runtime_execution_body["governance"]["execution_authority"] is False
    assert denied_runtime_execution_body["governance"]["resident_runtime_execution_authority"] is True
    assert denied_runtime_execution_body["governance"]["approval_decision_authority"] is False
    assert denied_runtime_execution_body["governance"]["local_process_launch_authority"] is False
    assert denied_runtime_execution_body["governance"]["process_supervision_authority"] is False
    assert denied_runtime_execution_body["governance"]["service_control_authority"] is False
    assert denied_runtime_execution_body["governance"]["hotkey_registration_authority"] is False
    assert denied_runtime_execution_body["governance"]["overlay_control_authority"] is False
    assert denied_runtime_execution_body["governance"]["memory_write"] is False
    assert denied_runtime_execution_body["governance"]["receipt_write_authority"] is False
    assert denied_runtime_execution_body["governance"]["denial_receipt_write_authority"] is True
    assert denied_runtime_execution_body["governance"]["resident_claim_authority"] is False
    runtime_denial_receipts = client.get(f"/lens/resident-runtime/denials?limit=10&approval_id={approval_id}")
    assert runtime_denial_receipts.status_code == 200
    runtime_denial_receipts_body = runtime_denial_receipts.json()
    assert runtime_denial_receipts_body["kind"] == "lens.resident_runtime.activation.denial_receipts"
    assert runtime_denial_receipts_body["status"] == "readback_ready"
    assert runtime_denial_receipts_body["route"] == "/lens/resident-runtime/denials"
    assert runtime_denial_receipts_body["execute_route"] == "/lens/resident-runtime/execute"
    assert runtime_denial_receipts_body["plan_route"] == "/lens/resident-runtime/plan"
    assert runtime_denial_receipts_body["approval_id"] == approval_id
    assert runtime_denial_receipts_body["total"] == 1
    assert runtime_denial_receipts_body["latest"]["receipt_id"] == runtime_denial_receipt["receipt_id"]
    assert runtime_denial_receipts_body["items"][0]["approval_id"] == approval_id
    assert runtime_denial_receipts_body["items"][0]["execution"]["would_supervise_process"] is False
    assert runtime_denial_receipts_body["items"][0]["governance"]["execution_authority"] is False
    assert runtime_denial_receipts_body["governance"]["gate"] == (
        "lens_resident_runtime_activation_denial_receipts_readback"
    )
    assert runtime_denial_receipts_body["governance"]["read_only_contract"] is True
    assert runtime_denial_receipts_body["governance"]["denial_receipt_write_authority"] is False
    assert runtime_denial_receipts_body["governance"]["execution_authority"] is False
    assert runtime_denial_receipts_body["governance"]["approval_decision_authority"] is False
    assert runtime_denial_receipts_body["governance"]["process_supervision_authority"] is False
    assert runtime_denial_receipts_body["governance"]["service_control_authority"] is False
    assert runtime_denial_receipts_body["governance"]["memory_write"] is False

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
    assert denied_execution_body["denial"]["denial_receipt_written"] is True
    assert denied_execution_body["receipt_written"] is True
    assert denied_execution_body["receipt_route"] == "/lens/host/activation/denials"
    denial_receipt = denied_execution_body["receipt"]
    assert denial_receipt["kind"] == "lens.host.activation.denial.receipt"
    assert denial_receipt["status"] == "denied_no_execution_authority"
    assert denial_receipt["route"] == "/lens/host/activation/execute"
    assert denial_receipt["source_kind"] == "lens.host.activation.execution_denial"
    assert denial_receipt["approval_id"] == approval_id
    assert denial_receipt["actor"] == "test.system.write"
    assert denial_receipt["approval"]["approved"] is True
    assert denial_receipt["permission"]["ready"] is True
    assert denial_receipt["execution"]["applied"] is False
    assert denial_receipt["execution"]["executed"] is False
    assert denial_receipt["execution"]["would_launch_process"] is False
    assert denial_receipt["execution"]["would_write_memory"] is False
    assert denial_receipt["governance"]["gate"] == "lens_host_activation_denial_receipt"
    assert denial_receipt["governance"]["denial_receipt_write_authority"] is True
    assert denial_receipt["governance"]["execution_authority"] is False
    assert denial_receipt["governance"]["approval_decision_authority"] is False
    assert denial_receipt["governance"]["local_process_launch_authority"] is False
    assert denial_receipt["governance"]["memory_write"] is False
    denial_receipt_path = data_root / "lens" / "host_activation_denials" / f"{denial_receipt['receipt_id']}.json"
    assert denial_receipt_path.exists()
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
    assert denied_execution_body["governance"]["denial_receipt_write_authority"] is True
    denial_receipts = client.get(f"/lens/host/activation/denials?limit=10&approval_id={approval_id}")
    assert denial_receipts.status_code == 200
    denial_receipts_body = denial_receipts.json()
    assert denial_receipts_body["kind"] == "lens.host.activation.denial_receipts"
    assert denial_receipts_body["status"] == "readback_ready"
    assert denial_receipts_body["route"] == "/lens/host/activation/denials"
    assert denial_receipts_body["execute_route"] == "/lens/host/activation/execute"
    assert denial_receipts_body["approval_id"] == approval_id
    assert denial_receipts_body["total"] == 1
    assert denial_receipts_body["latest"]["receipt_id"] == denial_receipt["receipt_id"]
    assert denial_receipts_body["items"][0]["approval_id"] == approval_id
    assert denial_receipts_body["items"][0]["execution"]["would_launch_process"] is False
    assert denial_receipts_body["items"][0]["governance"]["execution_authority"] is False
    assert denial_receipts_body["governance"]["gate"] == "lens_host_activation_denial_receipts_readback"
    assert denial_receipts_body["governance"]["read_only_contract"] is True
    assert denial_receipts_body["governance"]["denial_receipt_write_authority"] is False
    assert denial_receipts_body["governance"]["execution_authority"] is False
    assert denial_receipts_body["governance"]["approval_decision_authority"] is False
    assert denial_receipts_body["governance"]["memory_write"] is False
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
    status_denial_receipts = status_body["resident_host"]["activation_denial_receipts"]
    assert status_denial_receipts["status"] == "readback_ready"
    assert status_denial_receipts["total"] == 1
    assert status_denial_receipts["latest"]["receipt_id"] == denial_receipt["receipt_id"]
    status_denial_receipt_criterion = _criterion(status_body, "host_activation_denial_receipt_readback")
    assert status_denial_receipt_criterion["status"] == "readback_ready"
    assert status_denial_receipt_criterion["receipt_count"] == 1
    assert status_denial_receipt_criterion["latest_receipt_id"] == denial_receipt["receipt_id"]
    assert status_denial_receipt_criterion["execution_authority"] is False
    assert status_denial_receipt_criterion["approval_decision_authority"] is False
    assert status_denial_receipt_criterion["local_process_launch_authority"] is False
    assert status_denial_receipt_criterion["memory_write"] is False
    status_authority_requests = status_body["resident_host"]["resident_runtime_authority_requests"]
    assert status_authority_requests["status"] == "authority_granted"
    assert status_authority_requests["pending_count"] == 0
    assert status_authority_requests["approved_count"] == 1
    assert status_authority_requests["total_count"] == 1
    assert status_authority_requests["latest"]["id"] == runtime_authority_request_body["approval_id"]
    assert status_authority_requests["active_grant_receipt_id"] == authority_grant_receipt["receipt_id"]
    assert status_authority_requests["authority_granted"] is True
    assert status_authority_requests["resident_runtime_execution_authority"] is True
    status_authority_request_criterion = _criterion(
        status_body, "resident_runtime_execution_authority_request_readback"
    )
    assert status_authority_request_criterion["status"] == "authority_granted"
    assert status_authority_request_criterion["pending_count"] == 0
    assert status_authority_request_criterion["approved_count"] == 1
    assert status_authority_request_criterion["receipt_count"] == 1
    assert status_authority_request_criterion["latest_approval_id"] == runtime_authority_request_body["approval_id"]
    assert status_authority_request_criterion["authority_granted"] is True
    assert status_authority_request_criterion["resident_claim_allowed"] is False
    assert status_authority_request_criterion["execution_authority"] is False
    assert status_authority_request_criterion["approval_decision_authority"] is False
    assert status_authority_request_criterion["process_supervision_authority"] is False
    assert status_authority_request_criterion["service_control_authority"] is False
    assert status_authority_request_criterion["memory_write"] is False
    assert status_authority_request_criterion["resident_claim_authority"] is False
    status_authority_grant_receipts = status_body["resident_host"]["resident_runtime_authority_grant_receipts"]
    assert status_authority_grant_receipts["status"] == "readback_ready"
    assert status_authority_grant_receipts["total"] == 1
    assert status_authority_grant_receipts["latest"]["receipt_id"] == authority_grant_receipt["receipt_id"]
    assert status_authority_grant_receipts["active_latest"]["receipt_id"] == authority_grant_receipt["receipt_id"]
    assert status_authority_grant_receipts["authority_granted"] is True
    status_authority_grant_receipts_criterion = _criterion(
        status_body, "resident_runtime_authority_grant_receipt_readback"
    )
    assert status_authority_grant_receipts_criterion["status"] == "readback_ready"
    assert status_authority_grant_receipts_criterion["receipt_count"] == 1
    assert status_authority_grant_receipts_criterion["latest_receipt_id"] == authority_grant_receipt["receipt_id"]
    assert status_authority_grant_receipts_criterion["active_receipt_id"] == authority_grant_receipt["receipt_id"]
    assert status_authority_grant_receipts_criterion["authority_granted"] is True
    assert status_authority_grant_receipts_criterion["resident_runtime_execution_authority"] is True
    assert status_authority_grant_receipts_criterion["execution_authority"] is False
    assert status_authority_grant_receipts_criterion["approval_decision_authority"] is False
    assert status_authority_grant_receipts_criterion["process_supervision_authority"] is False
    assert status_authority_grant_receipts_criterion["service_control_authority"] is False
    assert status_authority_grant_receipts_criterion["memory_write"] is False
    status_authority_grant_denials = status_body["resident_host"]["resident_runtime_authority_grant_denial_receipts"]
    assert status_authority_grant_denials["status"] == "empty"
    assert status_authority_grant_denials["total"] == 0
    assert status_authority_grant_denials["latest"] is None
    status_authority_grant_denials_criterion = _criterion(
        status_body, "resident_runtime_authority_grant_denial_receipt_readback"
    )
    assert status_authority_grant_denials_criterion["status"] == "empty"
    assert status_authority_grant_denials_criterion["receipt_count"] == 0
    assert status_authority_grant_denials_criterion["latest_receipt_id"] == ""
    assert status_authority_grant_denials_criterion["execution_authority"] is False
    assert status_authority_grant_denials_criterion["approval_decision_authority"] is False
    assert status_authority_grant_denials_criterion["process_supervision_authority"] is False
    assert status_authority_grant_denials_criterion["service_control_authority"] is False
    assert status_authority_grant_denials_criterion["memory_write"] is False
    assert status_authority_grant_denials_criterion["denial_receipt_write_authority"] is False
    status_authority_grant_readiness = status_body["resident_host"]["resident_runtime_authority_grant_readiness"]
    assert status_authority_grant_readiness["status"] == "blocked"
    assert status_authority_grant_readiness["audit_status"] == "complete"
    assert status_authority_grant_readiness["receipt_count"] == 1
    assert status_authority_grant_readiness["latest_receipt_id"] == authority_grant_receipt["receipt_id"]
    assert status_authority_grant_readiness["denial_receipt_count"] == 0
    assert status_authority_grant_readiness["latest_denial_receipt_id"] == ""
    assert status_authority_grant_readiness["authority_granted"] is True
    assert status_authority_grant_readiness["resident_runtime_execution_authority"] is True
    assert status_authority_grant_readiness["governance"]["execution_authority"] is False
    status_authority_grant_readiness_criterion = _criterion(
        status_body, "resident_runtime_authority_grant_readiness_audit"
    )
    assert status_authority_grant_readiness_criterion["status"] == "blocked"
    assert status_authority_grant_readiness_criterion["audit_status"] == "complete"
    assert status_authority_grant_readiness_criterion["ready"] is False
    assert status_authority_grant_readiness_criterion["boundary_observed"] is True
    assert status_authority_grant_readiness_criterion["authority_granted"] is True
    assert status_authority_grant_readiness_criterion["resident_runtime_execution_authority"] is True
    assert status_authority_grant_readiness_criterion["grant_receipt_readback_ready"] is True
    assert status_authority_grant_readiness_criterion["denial_receipt_readback_ready"] is True
    assert "authority_grant_implementation" not in status_authority_grant_readiness_criterion["blocked_requirements"]
    assert (
        "resident_runtime_execution_authority" not in status_authority_grant_readiness_criterion["blocked_requirements"]
    )
    assert (
        "resident_runtime_authority_grant_not_implemented" not in status_authority_grant_readiness_criterion["blockers"]
    )
    assert (
        "resident_runtime_execution_authority_not_granted" not in status_authority_grant_readiness_criterion["blockers"]
    )
    assert status_authority_grant_readiness_criterion["execution_authority"] is False
    assert status_authority_grant_readiness_criterion["approval_decision_authority"] is False
    assert status_authority_grant_readiness_criterion["process_supervision_authority"] is False
    assert status_authority_grant_readiness_criterion["service_control_authority"] is False
    assert status_authority_grant_readiness_criterion["memory_write"] is False
    status_runtime_denials = status_body["resident_host"]["resident_runtime_denial_receipts"]
    assert status_runtime_denials["status"] == "readback_ready"
    assert status_runtime_denials["total"] == 1
    assert status_runtime_denials["latest"]["receipt_id"] == runtime_denial_receipt["receipt_id"]
    assert (
        status_body["resident_runtime_denial_receipts"]["latest"]["receipt_id"] == runtime_denial_receipt["receipt_id"]
    )
    status_runtime_denials_criterion = _criterion(status_body, "resident_runtime_activation_denial_receipt_readback")
    assert status_runtime_denials_criterion["status"] == "readback_ready"
    assert status_runtime_denials_criterion["receipt_count"] == 1
    assert status_runtime_denials_criterion["latest_receipt_id"] == runtime_denial_receipt["receipt_id"]
    assert status_runtime_denials_criterion["execution_authority"] is False
    assert status_runtime_denials_criterion["approval_decision_authority"] is False
    assert status_runtime_denials_criterion["process_supervision_authority"] is False
    assert status_runtime_denials_criterion["service_control_authority"] is False
    assert status_runtime_denials_criterion["memory_write"] is False
    assert status_runtime_denials_criterion["denial_receipt_write_authority"] is False
    runtime_authority_criterion = _criterion(status_body, "resident_runtime_authority_boundary")
    assert runtime_authority_criterion["status"] == "blocked"
    assert runtime_authority_criterion["applied"] is False
    assert runtime_authority_criterion["executed"] is False
    assert runtime_authority_criterion["execution_authority"] is False
    assert runtime_authority_criterion["process_supervision_authority"] is False
    assert runtime_authority_criterion["service_control_authority"] is False
    assert runtime_authority_criterion["hotkey_registration_authority"] is False
    assert runtime_authority_criterion["overlay_control_authority"] is False
    assert runtime_authority_criterion["memory_write"] is False
    assert runtime_authority_criterion["resident_claim_authority"] is False
    assert not (data_root / "runtime" / "lens-host" / "status.json").exists()
    assert not (data_root / "runtime" / "lens-host" / "lens-host.pid").exists()
