from __future__ import annotations

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
    assert launch_manifest["service_readback"] == resident_host["service_readback"]
    assert launch_manifest["process_readback"] == resident_host["process_readback"]
    assert launch_manifest["foreground_session"] == resident_host["foreground_session"]
    assert [item["id"] for item in launch_manifest["required_bindings"]] == [
        "api_status",
        "host_status_runner",
        "host_service_config",
        "host_service_readback",
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
    assert _criterion(body, "summon_anywhere")["status"] == "not_implemented"
    assert "summon_binding_missing" in _criterion(body, "summon_anywhere")["blockers"]

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
    assert manifest_body["service_readback"]["status"] == "not_checked_by_api"
    assert manifest_body["service_readback"]["service_control_authority"] is False
    assert manifest_body["process_readback"]["status"] == "missing"
    assert manifest_body["status_command"]["executable"] is True
    assert manifest_body["candidate_command"]["executable"] is True
    assert manifest_body["governance"]["local_process_launch_authority"] is False
    assert manifest_body["governance"]["service_install_authority"] is False


def test_lens_status_surfaces_pending_approval_without_decision_authority(monkeypatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    data_root = repo_root / "data"
    _write_dev_environment(repo_root)
    _write_lens_host_status_runner(repo_root)
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
