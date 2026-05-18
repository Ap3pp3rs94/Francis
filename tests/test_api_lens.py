from __future__ import annotations

import json
import os
import shutil
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
    script.write_text(
        """
[CmdletBinding()]
param(
  [ValidateSet('Status', 'Foreground', 'Launch', 'Resident')]
  [string]$Mode = 'Status',
  [int]$RunSeconds = 0
)

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$DataRoot = if (-not [string]::IsNullOrWhiteSpace([string]$env:FRANCIS_DATA_DIR)) {
  [string]$env:FRANCIS_DATA_DIR
} else {
  Join-Path $RepoRoot 'data'
}
$RuntimeDir = Join-Path (Join-Path $DataRoot 'runtime') 'lens-host'
$StatePath = Join-Path $RuntimeDir 'status.json'
$PidPath = Join-Path $RuntimeDir 'lens-host.pid'

function Write-JsonFile {
  param([string]$Path, [object]$Payload)
  New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Path) | Out-Null
  $Payload | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $Path -Encoding UTF8
}

$StateExists = Test-Path -LiteralPath $StatePath -PathType Leaf
$PidPresent = Test-Path -LiteralPath $PidPath -PathType Leaf
$Now = (Get-Date).ToUniversalTime().ToString('o')
$Payload = [ordered]@{
  ok = $true
  kind = 'lens.host.status_runner'
  status = 'status_only'
  mode = $Mode.ToLowerInvariant()
  process_readback = [ordered]@{
    status = if ($StateExists -or $PidPresent) { 'state_present_process_not_running' } else { 'missing' }
    readback_ready = $true
    runtime_state_path = 'data/runtime/lens-host/status.json'
    state_exists = $StateExists
    state_status = ''
    state_updated_at = ''
    heartbeat_count = 0
    last_heartbeat_at = ''
    pid_path = 'data/runtime/lens-host/lens-host.pid'
    pid_present = $PidPresent
    pid = 0
    process_alive = $false
    supervision_enabled = $false
    blocked_reason = 'resident_host_process_missing'
  }
  foreground_supported = $true
  foreground_session = $false
  resident_supported = $true
  resident_session = $false
  foreground_run_seconds = $RunSeconds
  blockers = @(
    'lens_host_runtime_not_implemented',
    'resident_host_process_missing',
    'tray_host_missing',
    'global_hotkey_binding_missing',
    'overlay_window_missing',
    'summon_binding_missing'
  )
  governance = [ordered]@{
    execution_authority = $false
    local_process_launch_authority = $false
    foreground_session_authority = $false
    resident_claim_authority = $false
    service_install_authority = $false
    service_control_authority = $false
    memory_write = $false
  }
}

if ($Mode -eq 'Launch') {
  New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null
  Set-Content -LiteralPath $PidPath -Value ([string]$PID) -Encoding ASCII
  $RunningState = [ordered]@{
    kind = 'lens.host.runtime_state'
    status = 'foreground_running'
    mode = 'foreground'
    pid = $PID
    process_alive = $true
    resident = $false
    service_managed = $false
    tray_presence = $false
    global_hotkey = $false
    overlay_window = $false
    summon_anywhere = $false
    started_at = $Now
    updated_at = $Now
    heartbeat_count = 1
    last_heartbeat_at = $Now
    bounded_run_seconds = $RunSeconds
    governance = [ordered]@{
      execution_authority = $false
      local_process_launch_authority = $false
      foreground_session_authority = $true
      resident_claim_authority = $false
      service_install_authority = $false
      service_control_authority = $false
      memory_write = $false
    }
  }
  Write-JsonFile -Path $StatePath -Payload $RunningState
  $Payload.status = 'launch_started'
  $Payload.mode = 'launch'
  $Payload.foreground_session = $true
  $Payload.launch_supported = $true
  $Payload.process_readback.status = 'process_observed'
  $Payload.process_readback.state_exists = $true
  $Payload.process_readback.state_status = 'foreground_running'
  $Payload.process_readback.state_updated_at = $Now
  $Payload.process_readback.heartbeat_count = 1
  $Payload.process_readback.last_heartbeat_at = $Now
  $Payload.process_readback.pid_present = $true
  $Payload.process_readback.pid = $PID
  $Payload.process_readback.process_alive = $true
  $Payload.process_readback.blocked_reason = 'resident_host_not_supervised'
  $Payload.launch = [ordered]@{
    status = 'started_observed'
    launcher_pid = $PID
    observed_pid = $PID
    run_seconds = $RunSeconds
    runtime_state_path = 'data/runtime/lens-host/status.json'
    pid_path = 'data/runtime/lens-host/lens-host.pid'
    observed_at = $Now
    stop_mode = 'bounded_self_stop'
  }
  $Payload.governance['bounded_process_launch'] = $true
  $Payload.governance['temporary_runtime_state_write'] = $true
  $Payload.governance['foreground_session_authority'] = $true
}

$Payload | ConvertTo-Json -Depth 8
exit 0
""".strip(),
        encoding="utf-8",
    )


def _write_service_manager(repo_root: Path) -> None:
    script = repo_root / "scripts" / "service-install.ps1"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text("# Service manager fixture\n", encoding="utf-8")


def _write_lens_preflight_scripts(repo_root: Path) -> None:
    script_dir = repo_root / "scripts"
    script_dir.mkdir(parents=True, exist_ok=True)
    for name in (
        "lens-host-preflight.ps1",
        "lens-summon.ps1",
        "lens-summon-preflight.ps1",
        "lens-command-palette.ps1",
        "lens-tray-preflight.ps1",
        "lens-overlay-preflight.ps1",
        "lens-overlay-window.ps1",
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
  "summon_runner": "scripts/lens-summon.ps1",
  "local_palette_launcher": "scripts/lens-command-palette.ps1 -Mode LocalOpen",
  "overlay_required": true,
  "tray_required": true,
  "requires_explicit_enable": true,
  "summon_authority": false,
  "hotkey_registration_authority": false,
  "overlay_control_authority": false,
  "local_process_launch_authority": false,
  "blocked_reason": "lens_summon_binding_disabled_pending_authority",
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
  "blocked_reason": "lens_tray_presence_disabled_pending_authority",
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
  "overlay_runner": "scripts/lens-overlay-window.ps1",
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
    "Resident"
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
  "resident_mode": "Resident",
  "resident_session_enabled": true,
  "resident_session_default_seconds": 0,
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
  "blocked_reason": "lens_host_runtime_not_implemented",
  "required_before_enable": [
    "resident_host_process",
    "tray_presence",
    "global_hotkey_binding",
    "overlay_window",
    "summon_binding"
  ]
}
""".strip(),
        encoding="utf-8",
    )


def _write_lens_host_runtime_state(
    data_root: Path,
    *,
    pid: int,
    status: str = "foreground_running",
    mode: str = "foreground",
) -> None:
    runtime_root = data_root / "runtime" / "lens-host"
    runtime_root.mkdir(parents=True, exist_ok=True)
    (runtime_root / "lens-host.pid").write_text(str(pid), encoding="ascii")
    (runtime_root / "status.json").write_text(
        json.dumps(
            {
                "kind": "lens.host.runtime_state",
                "status": status,
                "mode": mode,
                "pid": pid,
                "process_alive": status in {"foreground_running", "resident_running"},
                "resident": mode == "resident",
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


def _write_lens_tray_runtime_state(data_root: Path, *, pid: int) -> None:
    runtime_root = data_root / "runtime" / "lens-tray"
    runtime_root.mkdir(parents=True, exist_ok=True)
    (runtime_root / "lens-tray.pid").write_text(str(pid), encoding="ascii")
    (runtime_root / "status.json").write_text(
        json.dumps(
            {
                "kind": "lens.tray.runtime_state",
                "status": "tray_running",
                "pid": pid,
                "tray_icon_visible": True,
                "updated_at": "2026-05-01T00:00:00Z",
                "message": "Francis Lens tray presence is running.",
            }
        ),
        encoding="utf-8",
    )


def _write_lens_hotkey_runtime_state(data_root: Path, *, pid: int) -> None:
    runtime_root = data_root / "runtime" / "lens-hotkey"
    runtime_root.mkdir(parents=True, exist_ok=True)
    (runtime_root / "lens-hotkey.pid").write_text(str(pid), encoding="ascii")
    (runtime_root / "status.json").write_text(
        json.dumps(
            {
                "kind": "lens.hotkey.runtime_state",
                "status": "hotkey_bound",
                "pid": pid,
                "global_hotkey": "Ctrl+Alt+Space",
                "binding_scope": "global",
                "hotkey_bound": True,
                "launch_on_hotkey": False,
                "summon_runner": "scripts/lens-summon.ps1",
                "press_count": 0,
                "updated_at": "2026-05-12T22:30:00Z",
                "message": "Francis Lens global hotkey binding is running.",
            }
        ),
        encoding="utf-8",
    )


def _write_lens_overlay_runtime_state(data_root: Path, *, pid: int) -> None:
    runtime_root = data_root / "runtime" / "lens-overlay"
    runtime_root.mkdir(parents=True, exist_ok=True)
    (runtime_root / "lens-overlay.pid").write_text(str(pid), encoding="ascii")
    (runtime_root / "status.json").write_text(
        json.dumps(
            {
                "kind": "lens.overlay.runtime_state",
                "status": "overlay_running",
                "pid": pid,
                "overlay_name": "Francis Lens Overlay",
                "overlay_scope": "user_session",
                "overlay_window_visible": True,
                "always_on_top": True,
                "updated_at": "2026-05-13T02:00:00Z",
                "message": "Francis Lens overlay window is running.",
            }
        ),
        encoding="utf-8",
    )


def _write_lens_host_supervisor_state(
    data_root: Path,
    *,
    observed_pid: int,
    status: str = "supervised_session_completed",
    mode: str = "supervise_once",
    host_mode: str = "",
    observed_state: str = "foreground_stopped",
    updated_at: str | None = None,
    resident_supervised_runtime: bool = False,
    process_supervision_authority: bool = False,
    process_restart_authority: bool = False,
    service_control_authority: bool = False,
) -> None:
    runtime_root = data_root / "runtime" / "lens-host-supervisor"
    runtime_root.mkdir(parents=True, exist_ok=True)
    observed_at = updated_at or datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    (runtime_root / "status.json").write_text(
        json.dumps(
            {
                "kind": "lens.host.supervisor_state",
                "status": status,
                "mode": mode,
                "host_mode": host_mode,
                "observed_pid": observed_pid,
                "observed_state": observed_state,
                "restarted_process": False,
                "managed_service": False,
                "resident_supervised_runtime": resident_supervised_runtime,
                "resident_claim_allowed": False,
                "process_supervision_authority": process_supervision_authority,
                "process_restart_authority": process_restart_authority,
                "service_control_authority": service_control_authority,
                "updated_at": observed_at,
                "governance": {
                    "memory_write": False,
                    "service_control_authority": service_control_authority,
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


def test_lens_os_binding_readiness_groups_blockers_without_authority(
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
    response = client.get("/lens/os-binding/readiness")

    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "lens.os_binding.readiness"
    assert body["status"] == "blocked"
    assert body["audit_status"] == "complete"
    assert body["route"] == "/lens/os-binding/readiness"
    assert body["plan_route"] == "/lens/os-binding/plan"
    assert body["status_route"] == "/lens/status"
    assert body["preflight_route"] == "/lens/preflight"
    assert body["authority_route"] == "/lens/os-binding/authority"
    assert body["authority_request_route"] == "/lens/os-binding/authority/request"
    assert body["authority_requests_route"] == "/lens/os-binding/authority/requests"
    assert body["summon_route"] == "/lens/summon"
    assert body["ready"] is False
    assert body["os_binding_ready"] is False
    assert body["os_level_command_palette"] is False
    assert body["summon_anywhere"] is False
    assert body["acceptance_criterion"] == "summon_anywhere"
    assert body["next_smallest_truthful_gap"] == "os_level_command_palette_binding"
    assert body["first_blocker_family"] == "palette_binding"
    assert body["required_before_enable"] == [
        "resident_host_process",
        "tray_presence",
        "overlay_window",
        "global_hotkey_binding",
        "summon_binding",
    ]
    assert body["requirements_total"] == 8
    assert body["requirements_ready_total"] == 1
    assert body["requirements_blocked_total"] == 7
    assert body["blocked_requirements"] == [
        "os_level_command_palette",
        "global_hotkey_binding",
        "summon_binding",
        "resident_host",
        "tray_presence",
        "overlay_window",
        "authority_boundary",
    ]
    requirements = {item["id"]: item for item in body["requirements"]}
    assert requirements["authority_request_readback"]["route"] == "/lens/os-binding/authority/requests"
    assert requirements["authority_request_readback"]["ready"] is True
    assert requirements["os_level_command_palette"]["route"] == "/lens/os-binding/plan"
    assert requirements["os_level_command_palette"]["ready"] is False
    assert requirements["os_level_command_palette"]["readback_ready"] is True
    assert requirements["os_level_command_palette"]["source"] == "lens.command_palette.shell_bridge"
    assert requirements["os_level_command_palette"]["bridge_script"] == "scripts/lens-command-palette.ps1"
    assert requirements["global_hotkey_binding"]["route"] == "/lens/summon"
    assert requirements["summon_binding"]["route"] == "/lens/summon"
    assert requirements["resident_host"]["route"] == "/lens/host"
    assert requirements["tray_presence"]["route"] == "/lens/tray"
    assert requirements["overlay_window"]["route"] == "/lens/overlay"
    blocker_groups = body["blocker_groups"]
    assert "os_level_command_palette_missing" in blocker_groups["palette_binding"]
    assert "summon_anywhere_missing" in blocker_groups["palette_binding"]
    assert "global_hotkey_binding_disabled" in blocker_groups["global_hotkey_binding"]
    assert "global_hotkey_registration_disabled" in blocker_groups["global_hotkey_binding"]
    assert "lens_summon_binding_disabled_pending_authority" in blocker_groups["summon_binding"]
    assert "resident_host_process_missing" in blocker_groups["resident_host"]
    assert "lens_tray_presence_disabled_pending_authority" in blocker_groups["tray_presence"]
    assert "lens_overlay_window_not_implemented" in blocker_groups["overlay_window"]
    assert "summon_authority_not_granted" in blocker_groups["authority"]
    authority_readback = body["authority_request_readback"]
    assert authority_readback["kind"] == "lens.os_binding.command_palette_binding_authority.request_readback"
    assert authority_readback["status"] == "none"
    assert authority_readback["readback_ready"] is True
    assert authority_readback["route"] == "/lens/os-binding/authority/requests"
    assert authority_readback["authority_route"] == "/lens/os-binding/authority"
    assert authority_readback["request_route"] == "/lens/os-binding/authority/request"
    assert authority_readback["pending_count"] == 0
    assert authority_readback["approved_count"] == 0
    assert authority_readback["total_count"] == 0
    assert authority_readback["latest_approval_id"] == ""
    assert authority_readback["authority_granted"] is False
    assert authority_readback["os_level_command_palette_binding_authority"] is False
    assert authority_readback["opens_palette"] is False
    assert authority_readback["registers_hotkey"] is False
    assert authority_readback["launches_process"] is False
    assert authority_readback["controls_overlay"] is False
    assert authority_readback["governance"]["read_only_contract"] is True
    assert authority_readback["governance"]["approval_request_write"] is False
    assert authority_readback["governance"]["memory_write"] is False
    command_palette_contract = body["command_palette_contract"]
    assert command_palette_contract["kind"] == "lens.os_binding.command_palette_contract"
    assert command_palette_contract["status"] == "blocked"
    assert command_palette_contract["readback_ready"] is True
    assert command_palette_contract["route"] == "/lens/status"
    assert command_palette_contract["source"] == "lens.command_palette.shell_bridge"
    assert command_palette_contract["bridge_script"] == "scripts/lens-command-palette.ps1"
    assert command_palette_contract["proof_script"] == "scripts/lens-command-palette-os-binding-proof.ps1"
    assert command_palette_contract["availability"] == "chat_ui_only"
    assert command_palette_contract["url_entrypoint_ready"] is True
    assert command_palette_contract["url_entrypoint_route"] == "/?francis_lens=command_palette"
    assert command_palette_contract["authority_granted"] is False
    assert command_palette_contract["os_level_command_palette"] is False
    assert command_palette_contract["would_open_palette"] is False
    assert command_palette_contract["would_register_hotkey"] is False
    assert command_palette_contract["governance"]["read_only_contract"] is True
    assert command_palette_contract["governance"]["execution_authority"] is False
    summon_enablement_gate = body["summon_enablement_gate"]
    assert summon_enablement_gate["route"] == "/lens/summon"
    assert summon_enablement_gate["status"] == "blocked"
    assert summon_enablement_gate["ready"] is False
    assert summon_enablement_gate["summon_anywhere"] is False
    assert summon_enablement_gate["next_smallest_truthful_gap"] == "summon_anywhere_blockers"
    assert summon_enablement_gate["first_blocker_family"] == "resident_host"
    assert summon_enablement_gate["blocked_families"] == [
        "resident_host",
        "tray_presence",
        "overlay_window",
        "global_hotkey_binding",
        "summon_binding",
        "authority",
    ]
    assert summon_enablement_gate["global_hotkey_runtime_ready"] is False
    assert summon_enablement_gate["hotkey_runtime_readback"]["requirement_state"] == "missing"
    assert summon_enablement_gate["overlay_runtime_ready"] is False
    assert summon_enablement_gate["overlay_runtime_readback"]["requirement_state"] == "missing"
    implementation_plan = body["implementation_plan"]
    assert implementation_plan["kind"] == "lens.os_binding.implementation_plan"
    assert implementation_plan["route"] == "/lens/os-binding/plan"
    assert implementation_plan["status"] == "blocked"
    assert implementation_plan["plan_available"] is True
    assert implementation_plan["implementation_ready"] is False
    assert implementation_plan["next_smallest_truthful_gap"] == "os_level_command_palette_binding"
    assert implementation_plan["blocked_requirements"] == [
        "os_level_command_palette_contract",
        "global_hotkey_binding_contract",
        "summon_binding_contract",
        "resident_host_dependency",
        "tray_presence_dependency",
        "overlay_window_dependency",
        "authority_boundary",
    ]
    assert implementation_plan["governance"]["read_only_contract"] is True
    assert implementation_plan["governance"]["execution_authority"] is False
    assert implementation_plan["governance"]["hotkey_registration_authority"] is False
    assert implementation_plan["command_palette_contract"]["readback_ready"] is True
    assert implementation_plan["command_palette_contract"]["route"] == "/lens/status"
    governance = body["governance"]
    assert governance["read_only_contract"] is True
    assert governance["execution_authority"] is False
    assert governance["approval_decision_authority"] is False
    assert governance["memory_write"] is False
    assert governance["summon_authority"] is False
    assert governance["hotkey_registration_authority"] is False
    assert governance["tray_registration_authority"] is False
    assert governance["overlay_control_authority"] is False
    assert governance["process_supervision_authority"] is False
    assert governance["resident_claim_authority"] is False


def test_lens_os_binding_readiness_consumes_live_hotkey_runtime_without_authority(
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
    _write_lens_hotkey_runtime_state(data_root, pid=os.getpid())
    monkeypatch.setenv("FRANCIS_ROOT", str(repo_root))
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_ENV_PROFILE", "dev")
    monkeypatch.setenv("FRANCIS_RUN_MODE", "api")

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())
    response = client.get("/lens/os-binding/readiness")

    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "lens.os_binding.readiness"
    assert body["status"] == "blocked"
    assert body["ready"] is False
    assert body["summon_anywhere"] is False
    requirements = {item["id"]: item for item in body["requirements"]}
    hotkey_requirement = requirements["global_hotkey_binding"]
    assert hotkey_requirement["ready"] is False
    assert hotkey_requirement["runtime_ready"] is True
    assert hotkey_requirement["runtime_requirement_state"] == "bound"
    assert hotkey_requirement["runtime_blocker"] == ""
    assert hotkey_requirement["hotkey_runtime_readback"]["process_alive"] is True
    assert hotkey_requirement["hotkey_runtime_readback"]["hotkey_bound"] is True
    assert "global_hotkey_binding_disabled" in hotkey_requirement["blockers"]
    assert "hotkey_registration_authority_not_granted" in hotkey_requirement["blockers"]
    assert body["blocker_groups"]["global_hotkey_binding"] == [
        "global_hotkey_binding_disabled",
        "global_hotkey_registration_disabled",
        "hotkey_registration_authority_not_granted",
    ]
    summon_preflight = body["implementation_plan"]["command_palette_contract"]
    assert summon_preflight["would_register_hotkey"] is False
    gate = body["summon_enablement_gate"]
    assert gate["summon_anywhere"] is False
    assert body["governance"]["hotkey_registration_authority"] is False
    assert body["governance"]["execution_authority"] is False


def test_lens_os_binding_readiness_consumes_live_overlay_runtime_without_authority(
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
    _write_lens_overlay_runtime_state(data_root, pid=os.getpid())
    monkeypatch.setenv("FRANCIS_ROOT", str(repo_root))
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_ENV_PROFILE", "dev")
    monkeypatch.setenv("FRANCIS_RUN_MODE", "api")

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())
    response = client.get("/lens/os-binding/readiness")

    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "lens.os_binding.readiness"
    assert body["status"] == "blocked"
    assert body["ready"] is False
    requirements = {item["id"]: item for item in body["requirements"]}
    overlay_requirement = requirements["overlay_window"]
    assert overlay_requirement["ready"] is False
    assert overlay_requirement["runtime_ready"] is True
    assert overlay_requirement["runtime_requirement_state"] == "visible"
    assert overlay_requirement["runtime_blocker"] == ""
    assert overlay_requirement["overlay_runtime_readback"]["process_alive"] is True
    assert overlay_requirement["overlay_runtime_readback"]["overlay_window_visible"] is True
    assert overlay_requirement["overlay_runtime_readback"]["always_on_top"] is True
    assert "lens_overlay_window_not_implemented" not in overlay_requirement["blockers"]
    assert "overlay_window_missing" not in overlay_requirement["blockers"]
    assert "overlay_window_disabled" in overlay_requirement["blockers"]
    assert "overlay_control_authority_not_granted" in overlay_requirement["blockers"]
    assert body["blocker_groups"]["overlay_window"] == [
        "overlay_window_disabled",
        "overlay_control_authority_not_granted",
    ]
    gate = body["summon_enablement_gate"]
    assert gate["overlay_runtime_ready"] is True
    assert gate["overlay_runtime_readback"]["ready"] is True
    assert body["summon_anywhere"] is False
    assert body["governance"]["overlay_control_authority"] is False
    assert body["governance"]["execution_authority"] is False


def test_lens_os_binding_plan_blocks_os_palette_without_authority(
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
    response = client.get("/lens/os-binding/plan")

    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "lens.os_binding.implementation_plan"
    assert body["status"] == "blocked"
    assert body["route"] == "/lens/os-binding/plan"
    assert body["readiness_route"] == "/lens/os-binding/readiness"
    assert body["plan_available"] is True
    assert body["implementation_ready"] is False
    assert body["execution_ready"] is False
    assert body["os_binding_ready"] is False
    assert body["os_level_command_palette"] is False
    assert body["summon_anywhere"] is False
    assert body["acceptance_criterion"] == "summon_anywhere"
    assert body["next_smallest_truthful_gap"] == "os_level_command_palette_binding"
    assert body["requirements_total"] == 7
    assert body["requirements_ready_total"] == 0
    assert body["requirements_blocked_total"] == 7
    assert body["blocked_requirements"] == [
        "os_level_command_palette_contract",
        "global_hotkey_binding_contract",
        "summon_binding_contract",
        "resident_host_dependency",
        "tray_presence_dependency",
        "overlay_window_dependency",
        "authority_boundary",
    ]
    assert "os_level_command_palette_missing" in body["blocker_groups"]["palette_binding"]
    assert "global_hotkey_binding_disabled" in body["blocker_groups"]["global_hotkey_binding"]
    assert "lens_summon_binding_disabled_pending_authority" in body["blocker_groups"]["summon_binding"]
    assert "resident_host_process_missing" in body["blocker_groups"]["resident_host"]
    command_palette_contract = body["command_palette_contract"]
    assert command_palette_contract["readback_ready"] is True
    assert command_palette_contract["source_route"] == "/lens/status"
    assert command_palette_contract["local_surface"] == "chat_ui.command_palette"
    assert command_palette_contract["authority_required"] == "os_level_command_palette_binding_authority"
    assert command_palette_contract["governance"]["execution_authority"] is False
    steps = {item["id"]: item for item in body["plan"]["steps"]}
    assert steps["os_level_command_palette_contract"]["route"] == "/lens/status"
    assert steps["os_level_command_palette_contract"]["authority_required"] == (
        "os_level_command_palette_binding_authority"
    )
    assert steps["os_level_command_palette_contract"]["readback_ready"] is True
    assert steps["os_level_command_palette_contract"]["bridge_script"] == "scripts/lens-command-palette.ps1"
    assert body["source_readbacks"]["command_palette_contract_readback_ready"] is True
    assert body["source_readbacks"]["command_palette_contract_bridge_script"] == ("scripts/lens-command-palette.ps1")
    assert steps["global_hotkey_binding_contract"]["route"] == "/lens/summon"
    assert steps["global_hotkey_binding_contract"]["authority_required"] == "hotkey_registration_authority"
    assert steps["summon_binding_contract"]["authority_required"] == "summon_authority"
    assert body["plan"]["would_open_palette"] is False
    assert body["plan"]["would_register_hotkey"] is False
    assert body["plan"]["would_summon"] is False
    assert body["plan"]["would_launch_process"] is False
    assert body["plan"]["would_register_tray"] is False
    assert body["plan"]["would_open_overlay"] is False
    assert body["plan"]["would_write_memory"] is False
    assert body["plan"]["would_decide_approval"] is False
    governance = body["governance"]
    assert governance["read_only_contract"] is True
    assert governance["execution_authority"] is False
    assert governance["approval_decision_authority"] is False
    assert governance["memory_write"] is False
    assert governance["summon_authority"] is False
    assert governance["hotkey_registration_authority"] is False
    assert governance["tray_registration_authority"] is False
    assert governance["overlay_control_authority"] is False
    assert governance["local_process_launch_authority"] is False
    assert governance["resident_claim_authority"] is False


def test_lens_os_binding_authority_request_requires_system_write_without_binding(
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
        "/lens/os-binding/authority/request",
        json={
            "actor": "test.lens.no_scope",
            "reason": "try to request OS binding authority without scope",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["status"] == "denied"
    assert body["approval_requested"] is False
    assert body["applied"] is False
    assert body["executed"] is False
    assert body["error"] == "api_permission_denied"
    assert body["action"] == "lens.os_binding.command_palette_binding_authority"
    assert body["authority_granted"] is False
    assert body["os_level_command_palette_binding_authority"] is False
    assert body["opens_palette"] is False
    assert body["registers_hotkey"] is False
    assert body["launches_process"] is False
    assert body["controls_overlay"] is False
    assert body["governance"]["gate"] == "permission_gate"
    assert body["governance"]["required_scope"] == "system.write"
    assert body["governance"]["reason"] == "missing_scopes"
    assert body["governance"]["approval_request_write"] is False
    assert body["governance"]["os_level_command_palette_binding_authority"] is False
    assert body["governance"]["hotkey_registration_authority"] is False
    assert body["governance"]["summon_authority"] is False
    assert body["governance"]["overlay_control_authority"] is False
    assert body["governance"]["memory_write"] is False
    assert body["governance"]["resident_claim_authority"] is False
    assert client.get("/approvals/list?status=pending").json()["items"] == []
    assert not (data_root / "runtime" / "lens-host" / "status.json").exists()
    assert not (data_root / "runtime" / "lens-host" / "lens-host.pid").exists()


def test_lens_os_binding_authority_request_creates_approval_only_readback(
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
    contract = client.get("/lens/os-binding/authority")
    assert contract.status_code == 200
    contract_body = contract.json()
    assert contract_body["kind"] == "lens.os_binding.command_palette_binding_authority.contract"
    assert contract_body["status"] == "approval_request_ready"
    assert contract_body["route"] == "/lens/os-binding/authority"
    assert contract_body["request_route"] == "/lens/os-binding/authority/request"
    assert contract_body["readback_route"] == "/lens/os-binding/authority/requests"
    assert contract_body["readiness_route"] == "/lens/os-binding/readiness"
    assert contract_body["plan_route"] == "/lens/os-binding/plan"
    assert contract_body["execution_readiness_route"] == "/lens/os-binding/execution/readiness"
    assert contract_body["creates_approval_request"] is True
    assert contract_body["grants_authority"] is False
    assert contract_body["opens_palette"] is False
    assert contract_body["registers_hotkey"] is False
    assert contract_body["summons"] is False
    assert contract_body["launches_process"] is False
    assert contract_body["controls_overlay"] is False
    assert contract_body["writes_memory"] is False
    assert contract_body["decides_approval"] is False
    assert contract_body["claims_resident"] is False
    assert contract_body["governance"]["read_only_contract"] is True
    assert contract_body["governance"]["approval_request_write"] is True
    assert contract_body["governance"]["os_level_command_palette_binding_authority"] is False

    response = client.post(
        "/lens/os-binding/authority/request",
        json={
            "actor": "test.system.write",
            "reason": "prove governed OS binding authority request",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["status"] == "approval_requested"
    assert body["approval_requested"] is True
    assert body["applied"] is False
    assert body["executed"] is False
    assert body["action"] == "lens.os_binding.command_palette_binding_authority"
    assert body["authority_granted"] is False
    assert body["os_level_command_palette_binding_authority"] is False
    assert body["os_level_command_palette"] is False
    assert body["summon_anywhere"] is False
    assert body["opens_palette"] is False
    assert body["registers_hotkey"] is False
    assert body["launches_process"] is False
    assert body["controls_overlay"] is False
    assert body["governance"]["approval_request_write"] is True
    assert body["governance"]["approval_action"] == "lens.os_binding.command_palette_binding_authority"
    assert body["governance"]["os_level_command_palette_binding_authority"] is False
    assert body["governance"]["execution_authority"] is False
    assert body["governance"]["approval_decision_authority"] is False
    assert body["governance"]["hotkey_registration_authority"] is False
    assert body["governance"]["summon_authority"] is False
    assert body["governance"]["overlay_control_authority"] is False
    assert body["governance"]["memory_write"] is False
    assert body["governance"]["resident_claim_authority"] is False
    approval_id = str(body["approval_id"])
    assert approval_id

    pending_path = data_root / "approvals" / "pending" / f"{approval_id}.json"
    pending_payload = json.loads(pending_path.read_text(encoding="utf-8"))
    assert pending_payload["action"] == "lens.os_binding.command_palette_binding_authority"
    assert pending_payload["reason"] == "prove governed OS binding authority request"
    requested = pending_payload["payload"]
    assert requested["request_kind"] == "lens.os_binding.command_palette_binding_authority.request"
    assert requested["route"] == "/lens/os-binding/authority/request"
    assert requested["authority_route"] == "/lens/os-binding/authority"
    assert requested["readback_route"] == "/lens/os-binding/authority/requests"
    assert requested["readiness_route"] == "/lens/os-binding/readiness"
    assert requested["plan_route"] == "/lens/os-binding/plan"
    assert requested["readiness"]["ready"] is False
    assert requested["readiness"]["os_level_command_palette"] is False
    assert "os_level_command_palette" in requested["readiness"]["blocked_requirements"]
    assert "os_level_command_palette_missing" in requested["readiness"]["blockers"]
    assert requested["implementation_plan"]["plan_available"] is True
    assert requested["implementation_plan"]["implementation_ready"] is False
    assert "os_level_command_palette_contract" in requested["implementation_plan"]["blocked_requirements"]
    assert requested["authority_boundary"]["authority_ready"] is False
    assert requested["authority_boundary"]["authority_granted"] is False
    assert requested["authority_boundary"]["os_level_command_palette_binding_authority"] is False
    assert requested["authority_boundary"]["opens_palette"] is False
    assert requested["authority_boundary"]["registers_hotkey"] is False
    assert requested["authority_boundary"]["launches_process"] is False
    assert "os_level_command_palette_binding_authority_not_granted" in requested["authority_boundary"]["blockers"]
    assert requested["governance"]["approval_request_write"] is True
    assert requested["governance"]["os_level_command_palette_binding_authority"] is False
    assert requested["governance"]["would_open_palette"] is False
    assert requested["governance"]["would_register_hotkey"] is False
    assert requested["governance"]["would_launch_process"] is False
    assert requested["governance"]["would_open_overlay"] is False
    assert requested["governance"]["would_write_memory"] is False

    readback = client.get("/lens/os-binding/authority/requests?limit=10")
    assert readback.status_code == 200
    readback_body = readback.json()
    assert readback_body["kind"] == "lens.os_binding.command_palette_binding_authority.request_readback"
    assert readback_body["status"] == "pending_review"
    assert readback_body["route"] == "/lens/os-binding/authority/requests"
    assert readback_body["authority_route"] == "/lens/os-binding/authority"
    assert readback_body["request_route"] == "/lens/os-binding/authority/request"
    assert readback_body["pending_count"] == 1
    assert readback_body["approved_count"] == 0
    assert readback_body["total_count"] == 1
    assert readback_body["latest"]["id"] == approval_id
    assert readback_body["latest"]["action"] == "lens.os_binding.command_palette_binding_authority"
    assert readback_body["authority_required"] == "os_level_command_palette_binding_authority"
    assert readback_body["authority_granted"] is False
    assert readback_body["os_level_command_palette_binding_authority"] is False
    assert readback_body["os_level_command_palette"] is False
    assert readback_body["summon_anywhere"] is False
    assert readback_body["opens_palette"] is False
    assert readback_body["registers_hotkey"] is False
    assert readback_body["launches_process"] is False
    assert readback_body["controls_overlay"] is False
    assert readback_body["governance"]["read_only_contract"] is True
    assert readback_body["governance"]["approval_request_write"] is False
    assert readback_body["governance"]["os_level_command_palette_binding_authority"] is False
    assert readback_body["governance"]["hotkey_registration_authority"] is False
    assert readback_body["governance"]["summon_authority"] is False
    assert readback_body["governance"]["overlay_control_authority"] is False
    assert readback_body["governance"]["memory_write"] is False
    assert readback_body["governance"]["resident_claim_authority"] is False
    readiness_response = client.get("/lens/os-binding/readiness")
    assert readiness_response.status_code == 200
    readiness_body = readiness_response.json()
    readiness_authority = readiness_body["authority_request_readback"]
    assert readiness_authority["status"] == "pending_review"
    assert readiness_authority["readback_ready"] is True
    assert readiness_authority["pending_count"] == 1
    assert readiness_authority["approved_count"] == 0
    assert readiness_authority["authority_required"] == "os_level_command_palette_binding_authority"
    assert readiness_authority["total_count"] == 1
    assert readiness_authority["latest_approval_id"] == approval_id
    assert readiness_authority["authority_granted"] is False
    assert readiness_authority["os_level_command_palette_binding_authority"] is False
    assert readiness_body["requirements_ready_total"] == 1
    status_response = client.get("/lens/status?limit=10")
    assert status_response.status_code == 200
    status_body = status_response.json()
    assert status_body["os_binding_authority_requests"]["pending_count"] == 1
    assert status_body["os_binding_authority_requests"]["latest"]["id"] == approval_id
    assert status_body["os_binding_readiness"]["authority_request_readback"]["latest_approval_id"] == approval_id
    os_binding_criterion = _criterion(status_body, "os_binding_readiness")
    assert os_binding_criterion["authority_request_readback_status"] == "pending_review"
    assert os_binding_criterion["authority_request_pending_count"] == 1
    assert os_binding_criterion["authority_request_total_count"] == 1
    assert os_binding_criterion["authority_request_latest_approval_id"] == approval_id
    assert os_binding_criterion["authority_granted"] is False
    assert os_binding_criterion["os_level_command_palette_binding_authority"] is False
    assert not (data_root / "runtime" / "lens-host" / "status.json").exists()
    assert not (data_root / "runtime" / "lens-host" / "lens-host.pid").exists()


def test_lens_os_binding_execute_binds_governed_hotkey_lease(
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

    import francis.lens.os_binding_authority as os_binding_module
    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    pid = os.getpid()

    def fake_hotkey_action(*, mode: str, run_seconds: int) -> dict[str, Any]:
        if mode == "stop":
            runtime_root = data_root / "runtime" / "lens-hotkey"
            runtime_root.mkdir(parents=True, exist_ok=True)
            (runtime_root / "lens-hotkey.pid").unlink(missing_ok=True)
            (runtime_root / "status.json").write_text(
                json.dumps(
                    {
                        "kind": "lens.hotkey.runtime_state",
                        "status": "hotkey_stopped",
                        "pid": pid,
                        "global_hotkey": "Ctrl+Alt+Space",
                        "binding_scope": "global",
                        "hotkey_bound": False,
                        "launch_on_hotkey": False,
                        "updated_at": "2026-05-14T00:00:00Z",
                    }
                ),
                encoding="utf-8",
            )
            return {
                "ok": True,
                "status": "stopped",
                "returncode": 0,
                "script_mode": "Stop",
                "script": "scripts/lens-hotkey-binding.ps1",
                "runner": {"ok": True, "status": "stopped", "ready": False},
                "blockers": ["global_hotkey_binding_runtime_missing"],
            }

        _write_lens_hotkey_runtime_state(data_root, pid=pid)
        return {
            "ok": True,
            "status": "started",
            "returncode": 0,
            "script_mode": "Start",
            "script": "scripts/lens-hotkey-binding.ps1",
            "runner": {
                "ok": True,
                "status": "started",
                "ready": True,
                "global_hotkey_binding": True,
                "run_seconds": run_seconds,
                "hotkey_runtime": {
                    "ready": True,
                    "hotkey_bound": True,
                    "pid": pid,
                    "launch_on_hotkey": False,
                },
                "governance": {
                    "execution_authority": False,
                    "hotkey_registration_authority": True,
                    "local_process_launch_authority": True,
                    "summon_authority": False,
                    "overlay_control_authority": False,
                    "memory_write": False,
                },
            },
            "blockers": [],
        }

    monkeypatch.setattr(
        os_binding_module,
        "_run_lens_os_binding_hotkey_action",
        fake_hotkey_action,
    )

    client = TestClient(create_app())
    requested = client.post(
        "/lens/os-binding/authority/request",
        json={
            "actor": "test.system.write",
            "reason": "operator wants OS binding command palette authority",
        },
    )
    assert requested.status_code == 200
    approval_id = str(requested.json()["approval_id"])

    decided = client.post(
        "/approvals/decision",
        json={
            "id": approval_id,
            "action": "approve",
            "actor": "test.approvals.decision",
            "comment": "approved OS binding command palette authority",
        },
    )
    assert decided.status_code == 200
    assert decided.json()["status"] == "approved"

    grant = client.post(
        "/lens/os-binding/authority",
        json={
            "approval_id": approval_id,
            "actor": "test.system.write",
            "reason": "operator grants bounded OS binding authority",
            "lease_seconds": 600,
        },
    )
    assert grant.status_code == 200
    grant_body = grant.json()
    assert grant_body["status"] == "authority_granted"
    assert grant_body["os_level_command_palette_binding_authority"] is True
    assert grant_body["hotkey_registration_authority"] is True
    assert grant_body["local_process_launch_authority"] is True
    assert grant_body["receipt_written"] is True
    assert grant_body["governance"]["hotkey_registration_authority"] is True
    assert grant_body["governance"]["local_process_launch_authority"] is True
    assert grant_body["governance"]["summon_authority"] is False
    assert grant_body["governance"]["overlay_control_authority"] is False
    assert grant_body["governance"]["memory_write"] is False

    started = client.post(
        "/lens/os-binding/execute",
        json={
            "approval_id": approval_id,
            "actor": "test.system.write",
            "reason": "bind governed Lens global hotkey",
            "mode": "bind",
            "run_seconds": 60,
        },
    )
    assert started.status_code == 200
    started_body = started.json()
    assert started_body["kind"] == "lens.os_binding.command_palette_binding.execution"
    assert started_body["status"] == "global_hotkey_bound"
    assert started_body["executed"] is True
    assert started_body["mode"] == "bind"
    assert started_body["global_hotkey_binding"] is True
    assert started_body["hotkey_runtime_ready"] is True
    assert started_body["hotkey_bound"] is True
    assert started_body["hotkey_runtime_pid"] == pid
    assert started_body["launch_on_hotkey"] is False
    assert started_body["stop_command"] == "scripts/lens-hotkey-binding.ps1 -Mode Stop"
    assert started_body["next_smallest_truthful_gap"] == "summon_binding"
    assert started_body["governance"]["execution_authority"] is True
    assert started_body["governance"]["hotkey_registration_authority"] is True
    assert started_body["governance"]["local_process_launch_authority"] is True
    assert started_body["governance"]["summon_authority"] is False
    assert started_body["governance"]["overlay_control_authority"] is False
    assert started_body["governance"]["memory_write"] is False
    assert started_body["governance"]["resident_claim_authority"] is False
    assert started_body["receipt_written"] is True
    receipt = started_body["receipt"]
    assert receipt["kind"] == "lens.os_binding.command_palette_binding.execution_receipt"
    assert receipt["execution"]["mode"] == "bind"
    assert receipt["execution"]["global_hotkey_binding"] is True
    assert receipt["execution"]["hotkey_runtime_ready"] is True
    assert receipt["execution"]["launch_on_hotkey"] is False

    executions = client.get("/lens/os-binding/executions?limit=10")
    assert executions.status_code == 200
    executions_body = executions.json()
    assert executions_body["kind"] == "lens.os_binding.command_palette_binding.execution_receipts"
    assert executions_body["status"] == "readback_ready"
    assert executions_body["total"] == 1
    assert executions_body["latest_global_hotkey_binding"] is True
    assert executions_body["latest_next_smallest_truthful_gap"] == "summon_binding"

    readiness = client.get("/lens/os-binding/execution/readiness", params={"actor": "test.system.write"})
    assert readiness.status_code == 200
    readiness_body = readiness.json()
    assert readiness_body["kind"] == "lens.os_binding.command_palette_binding.execution_readiness"
    assert readiness_body["authority_granted"] is True
    assert readiness_body["os_level_command_palette"] is True
    assert "global_hotkey_binding" not in readiness_body["blocked_requirements"]
    assert readiness_body["governance"]["hotkey_registration_authority"] is True
    assert readiness_body["governance"]["local_process_launch_authority"] is True
    assert readiness_body["governance"]["memory_write"] is False


def test_lens_os_binding_execute_requires_active_grant(
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
        "/lens/os-binding/execute",
        json={
            "approval_id": "missing-grant",
            "actor": "test.system.write",
            "reason": "try to bind without an active grant",
            "mode": "bind",
            "run_seconds": 60,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "lens.os_binding.command_palette_binding.execution_denial"
    assert body["status"] == "blocked"
    assert body["executed"] is False
    assert body["receipt_written"] is False
    assert "os_binding_authority_grant_not_active" in body["blockers"]
    assert "hotkey_registration_authority_not_granted" in body["blockers"]
    assert body["governance"]["execution_authority"] is False
    assert body["governance"]["hotkey_registration_authority"] is False
    assert body["governance"]["local_process_launch_authority"] is False
    assert body["governance"]["memory_write"] is False
    assert not (data_root / "runtime" / "lens-hotkey" / "status.json").exists()


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
    assert body["os_binding_authority_requests"]["route"] == "/lens/os-binding/authority/requests"
    assert body["os_binding_authority_requests"]["request_route"] == "/lens/os-binding/authority/request"
    assert body["os_binding_authority_requests"]["authority_route"] == "/lens/os-binding/authority"
    assert body["os_binding_authority_requests"]["execute_route"] == "/lens/os-binding/execute"
    assert body["os_binding_authority_requests"]["authority_granted"] is False
    assert body["os_binding_execution_receipts"]["route"] == "/lens/os-binding/executions"
    assert body["os_binding_execution_receipts"]["execute_route"] == "/lens/os-binding/execute"
    assert body["os_binding_execution_receipts"]["total"] == 0
    assert body["tray_authority_requests"]["route"] == "/lens/tray/authority/requests"
    assert body["tray_authority_requests"]["request_route"] == "/lens/tray/authority/request"
    assert body["tray_authority_requests"]["authority_route"] == "/lens/tray/authority"
    assert body["tray_authority_requests"]["execute_route"] == "/lens/tray/execute"
    assert body["tray_authority_requests"]["authority_granted"] is False
    assert body["tray_execution_receipts"]["route"] == "/lens/tray/executions"
    assert body["tray_execution_receipts"]["execute_route"] == "/lens/tray/execute"
    assert body["tray_execution_receipts"]["total"] == 0
    assert body["overlay_authority_requests"]["route"] == "/lens/overlay/authority/requests"
    assert body["overlay_authority_requests"]["request_route"] == "/lens/overlay/authority/request"
    assert body["overlay_authority_requests"]["authority_route"] == "/lens/overlay/authority"
    assert body["overlay_authority_requests"]["execute_route"] == "/lens/overlay/execute"
    assert body["overlay_authority_requests"]["authority_granted"] is False
    assert body["overlay_execution_receipts"]["route"] == "/lens/overlay/executions"
    assert body["overlay_execution_receipts"]["execute_route"] == "/lens/overlay/execute"
    assert body["overlay_execution_receipts"]["total"] == 0
    assert body["summon_authority_requests"]["route"] == "/lens/summon/authority/requests"
    assert body["summon_authority_requests"]["request_route"] == "/lens/summon/authority/request"
    assert body["summon_authority_requests"]["authority_route"] == "/lens/summon/authority"
    assert body["summon_authority_requests"]["execute_route"] == "/lens/summon/execute"
    assert body["summon_authority_requests"]["authority_granted"] is False
    assert body["summon_execution_receipts"]["route"] == "/lens/summon/executions"
    assert body["summon_execution_receipts"]["execute_route"] == "/lens/summon/execute"
    assert body["summon_execution_receipts"]["total"] == 0
    assert body["receipts"]["lens_tray_authority_request_route"] == "/lens/tray/authority/request"
    assert body["receipts"]["lens_tray_execute_route"] == "/lens/tray/execute"
    assert body["receipts"]["lens_overlay_authority_request_route"] == "/lens/overlay/authority/request"
    assert body["receipts"]["lens_overlay_execute_route"] == "/lens/overlay/execute"
    assert body["receipts"]["lens_summon_authority_request_route"] == "/lens/summon/authority/request"
    assert body["receipts"]["lens_summon_execute_route"] == "/lens/summon/execute"
    stage6_readiness = body["stage6_readiness"]
    assert stage6_readiness["stage"] == "Stage 6 / Lens MVP"
    assert stage6_readiness["stage_state"] == "active"
    assert stage6_readiness["status"] == "blocked"
    assert stage6_readiness["ready_to_close"] is False
    assert stage6_readiness["criteria_total"] == 5
    assert stage6_readiness["ready_total"] == 2
    assert stage6_readiness["blocked_total"] == 3
    assert stage6_readiness["ready_criteria"] == ["mode_visibility", "pilot_visibility_groundwork"]
    assert stage6_readiness["blocked_criteria"] == [
        "summon_anywhere",
        "helpful_not_noisy",
        "system_resident_presence",
    ]
    assert stage6_readiness["next_smallest_truthful_gap"] == "summon_anywhere_blockers"
    next_handoff = stage6_readiness["next_handoff"]
    assert next_handoff["kind"] == "lens.stage6.next_handoff.readback"
    assert next_handoff["status"] == "readback_ready"
    assert next_handoff["stage_next_smallest_truthful_gap"] == "summon_anywhere_blockers"
    assert next_handoff["next_smallest_truthful_gap"] == "resident_host_process_not_supervised"
    assert next_handoff["recommended_next_slice"] == (
        "resolve_resident_host_process_before_persistent_supervision_enablement"
    )
    assert next_handoff["recommended_handoff_source"] == "persistent_supervision_first_missing_requirement_handoff"
    assert next_handoff["recommended_proof_script"] == (
        "scripts/lens-resident-host-runtime-boundary-proof.ps1 -Mode Status"
    )
    assert next_handoff["recommended_route"] == "/lens/host"
    assert next_handoff["recommended_readiness_route"] == "/lens/host/runtime-loop/readiness"
    assert next_handoff["recommended_request_route"] == "/lens/resident-runtime/authority-grant/request"
    assert next_handoff["recommended_grant_route"] == "/lens/resident-runtime/authority-grant"
    assert next_handoff["recommended_execution_readiness_route"] == "/lens/resident-runtime/plan"
    assert next_handoff["authority_required"] == ("resident_host_process_tray_hotkey_overlay_and_summon_prerequisites")
    assert next_handoff["authority_granted"] is False
    assert next_handoff["recommended_prerequisites_handoff_source"] == (
        "persistent_supervision_required_prerequisites_handoff"
    )
    assert next_handoff["recommended_prerequisites_next_slice"] == (
        "resolve_persistent_supervision_required_prerequisites_before_enablement"
    )
    assert next_handoff["recommended_prerequisites_proof_script"] == (
        "scripts/lens-persistent-supervision-prerequisites-proof.ps1 -Mode Status"
    )
    assert next_handoff["recommended_prerequisites_route"] == "/lens/host/persistent-supervision"
    assert next_handoff["recommended_prerequisites_readiness_route"] == "/lens/host/persistent-supervision/enablement"
    assert next_handoff["recommended_prerequisites_authority_required"] == (
        "resident_host_process_tray_hotkey_overlay_and_summon_prerequisites"
    )
    assert next_handoff["recommended_prerequisites_authority_granted"] is False
    assert next_handoff["recommended_first_missing_handoff_source"] == (
        "persistent_supervision_first_missing_requirement_handoff"
    )
    assert next_handoff["recommended_first_missing_next_slice"] == (
        "resolve_resident_host_process_before_persistent_supervision_enablement"
    )
    assert next_handoff["recommended_first_missing_proof_script"] == (
        "scripts/lens-resident-host-runtime-boundary-proof.ps1 -Mode Status"
    )
    assert next_handoff["recommended_first_missing_route"] == "/lens/host"
    assert next_handoff["recommended_first_missing_readiness_route"] == "/lens/host/runtime-loop/readiness"
    assert next_handoff["recommended_first_missing_authority_required"] == "process_supervision_authority"
    assert next_handoff["recommended_first_missing_authority_granted"] is False
    assert next_handoff["first_blocked_criterion"] == "summon_anywhere"
    assert next_handoff["persistent_supervision_required_prerequisites_observed"] is True
    assert next_handoff["persistent_supervision_missing_required_before_enable"] == [
        "resident_host_process",
        "tray_presence",
        "global_hotkey_binding",
        "overlay_window",
        "summon_binding",
    ]
    assert next_handoff["persistent_supervision_first_missing_required_before_enable"] == "resident_host_process"
    assert next_handoff["persistent_supervision_first_missing_requirement_handoff"]["id"] == "resident_host_process"
    assert (
        next_handoff["persistent_supervision_first_missing_requirement_handoff"]["authority_route"]
        == "/lens/host/activation/authority"
    )
    assert (
        next_handoff["persistent_supervision_first_missing_requirement_handoff"]["authority_request_route"]
        == "/lens/host/activation/request"
    )
    assert (
        next_handoff["persistent_supervision_first_missing_requirement_handoff"]["approval_action"]
        == "lens.host.foreground_activation"
    )
    assert (
        next_handoff["persistent_supervision_first_missing_requirement_handoff"]["resident_runtime_approval_action"]
        == "lens.resident_runtime.execution_authority"
    )
    assert (
        next_handoff["persistent_supervision_first_missing_requirement_handoff"][
            "resident_runtime_authority_request_route"
        ]
        == "/lens/resident-runtime/authority-grant/request"
    )
    assert (
        next_handoff["persistent_supervision_first_missing_requirement_handoff"]["resident_runtime_authority_route"]
        == "/lens/resident-runtime/authority-grant"
    )
    assert (
        next_handoff["persistent_supervision_first_missing_requirement_handoff"]["resident_runtime_plan_route"]
        == "/lens/resident-runtime/plan"
    )
    assert (
        next_handoff["persistent_supervision_first_missing_requirement_handoff"]["resident_runtime_execute_route"]
        == "/lens/resident-runtime/execute"
    )
    assert next_handoff["persistent_supervision_first_missing_requirement_handoff"]["read_only_contract"] is True
    assert next_handoff["persistent_supervision_first_missing_requirement_handoff"]["diagnostic_only"] is True
    assert next_handoff["persistent_supervision_first_missing_requirement_handoff"]["would_execute"] is False
    assert next_handoff["persistent_supervision_first_missing_requirement_handoff"]["would_mutate"] is False
    assert next_handoff["persistent_supervision_first_missing_requirement_handoff"]["authority_granted"] is False
    assert (
        next_handoff["persistent_supervision_required_prerequisites_handoff"]["id"]
        == "persistent_supervision_required_prerequisites"
    )
    assert next_handoff["persistent_supervision_required_prerequisites_handoff"]["status"] == "blocked"
    assert (
        next_handoff["persistent_supervision_required_prerequisites_handoff"]["next_smallest_truthful_gap"]
        == "persistent_supervision_required_prerequisites_missing"
    )
    assert next_handoff["persistent_supervision_required_prerequisites_handoff"]["blockers"] == [
        "resident_host_process",
        "tray_presence",
        "global_hotkey_binding",
        "overlay_window",
        "summon_binding",
    ]
    assert next_handoff["persistent_supervision_required_prerequisites_handoff"]["authority_granted"] is False
    assert next_handoff["persistent_supervision_enablement_authority_handoff_observed"] is False
    assert next_handoff["persistent_supervision_enablement_authority_handoff"] == {}
    assert next_handoff["resident_runtime_candidate_handoff_observed"] is False
    assert next_handoff["resident_runtime_candidate_handoff"] == {}
    assert next_handoff["governance"]["execution_authority"] is False
    assert next_handoff["governance"]["process_supervision_authority"] is False
    assert next_handoff["governance"]["resident_claim_authority"] is False
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
    assert closure["next_smallest_truthful_gap"] == "summon_anywhere_blockers"
    closure_criteria = {item["id"]: item for item in closure["criteria"]}
    assert closure_criteria["summon_anywhere"]["ready"] is False
    assert closure_criteria["summon_anywhere"]["next_smallest_truthful_gap"] == "summon_anywhere_blockers"
    expected_first_stage6_summon_handoff = {
        "id": "resident_host",
        "label": "Resident host",
        "status": "blocked",
        "blockers": [
            "resident_host_process_missing",
            "lens_host_runtime_not_implemented",
            "local_process_launch_authority_not_granted",
        ],
        "proof_script": "scripts/lens-summon-resident-host-blocker-proof.ps1 -Mode Status",
        "route": "/lens/host",
        "readiness_route": "/lens/host/runtime-loop/readiness",
        "next_step": "run_resident_host_blocker_proof",
        "next_smallest_truthful_gap": "resident_host_runtime_blocker_boundary",
        "authority_required": "resident_runtime_execution_authority",
        "authority_granted": False,
        "read_only_contract": True,
        "diagnostic_only": True,
        "would_execute": False,
        "would_mutate": False,
    }
    assert closure_criteria["summon_anywhere"]["handoff"] == {
        "next_step": "resolve_summon_anywhere_blockers_before_stage6_closure",
        "readiness_route": "/lens/summon/readiness",
        "summon_route": "/lens/summon",
        "preflight_route": "/lens/preflight",
        "status_route": "/lens/status",
        "proof_script": "scripts/lens-summon-preflight.ps1 -Mode Status",
        "first_blocker_family": "resident_host",
        "first_blocker_family_handoff": expected_first_stage6_summon_handoff,
        "first_blocker_family_next_smallest_truthful_gap": "resident_host_runtime_blocker_boundary",
        "first_blocker_family_completion_audit_handoff": {
            "next_step": "consume_resident_host_process_supervision_handoff_before_stage6_closure",
            "proof_script": (
                "scripts/lens-summon-resident-host-blocker-proof.ps1 -Mode Status -ConsumeProcessSupervisionHandoff"
            ),
            "previous_next_smallest_truthful_gap": "resident_host_process_not_supervised",
            "next_smallest_truthful_gap": "stage6_lens_completion_audit",
            "authority_required": "process_supervision_authority",
            "authority_granted": False,
            "read_only_contract": True,
            "diagnostic_only": True,
            "would_execute": False,
            "would_mutate": False,
        },
        "summon_anywhere_family_chain_completion_audit_handoff": {
            "next_step": "consume_summon_anywhere_family_chain_proof_before_stage6_closure",
            "proof_script": "scripts/lens-summon-anywhere-family-chain-proof.ps1 -Mode Status",
            "previous_next_smallest_truthful_gap": "summon_anywhere_blockers",
            "next_smallest_truthful_gap": "stage6_lens_completion_audit",
            "blocked_families": [
                "resident_host",
                "tray_presence",
                "overlay_window",
                "global_hotkey_binding",
                "summon_binding",
                "authority",
            ],
            "authority_required": "resident_runtime_execution_authority",
            "authority_granted": False,
            "read_only_contract": True,
            "diagnostic_only": True,
            "would_execute": False,
            "would_mutate": False,
        },
        "authority_required": "resident_runtime_execution_authority",
        "authority_granted": False,
        "next_smallest_truthful_gap": "summon_anywhere_blockers",
        "read_only_contract": True,
    }
    assert closure_criteria["summon_anywhere"]["evidence"] == [
        "/lens/os-binding/readiness",
        "/lens/summon",
        "/lens/status",
    ]
    assert "summon_anywhere_missing" in closure_criteria["summon_anywhere"]["blockers"]
    assert "os_level_command_palette_missing" in closure_criteria["summon_anywhere"]["blockers"]
    assert closure_criteria["helpful_not_noisy"]["ready"] is False
    assert closure_criteria["helpful_not_noisy"]["next_smallest_truthful_gap"] == (
        "approve_resident_runtime_execution_authority_grant_receipt"
    )
    assert closure_criteria["helpful_not_noisy"]["handoff"] == {
        "next_step": "prove_resident_surface_operator_experience_before_helpful_not_noisy_claim",
        "readiness_route": "/lens/resident-surface/activation",
        "surface_route": "/lens/resident-surface",
        "host_route": "/lens/host",
        "runtime_loop_readiness_route": "/lens/host/runtime-loop/readiness",
        "proof_script": "scripts/lens-resident-surface-proof.ps1 -Mode Status",
        "checkpoint_proof_handoff": {
            "next_step": "consume_resident_surface_foreground_runtime_proof_before_helpful_not_noisy_claim",
            "proof_script": "scripts/lens-stage6-checkpoint.ps1 -Mode Status",
            "child_proof_script": "scripts/lens-resident-surface-proof.ps1 -Mode Status",
            "previous_next_smallest_truthful_gap": "resident_surface_runtime_missing",
            "next_smallest_truthful_gap": "resident_surface_runtime_not_supervised",
            "authority_required": "process_supervision_authority",
            "authority_granted": False,
            "read_only_contract": True,
            "diagnostic_only": True,
            "would_execute": False,
            "would_mutate": False,
        },
        "authority_required": "resident_runtime_execution_authority",
        "authority_granted": False,
        "resident_runtime_authority_grant_readiness_route": "/lens/resident-runtime/authority-grant/readiness",
        "resident_runtime_authority_grant_next_smallest_truthful_gap": (
            "approve_resident_runtime_execution_authority_grant_receipt"
        ),
        "resident_runtime_authority_grant_first_blocked_requirement": (
            "exact_resident_runtime_execution_authority_approval"
        ),
        "resident_runtime_authority_grant_first_blocked_requirement_handoff": {
            "id": "exact_resident_runtime_execution_authority_approval",
            "label": "Exact approved resident runtime execution authority request",
            "status": "blocked",
            "route": "/lens/resident-runtime/authority-grant/requests",
            "readiness_route": "/lens/resident-runtime/authority-grant/readiness",
            "request_route": "/lens/resident-runtime/authority-grant/request",
            "requests_route": "/lens/resident-runtime/authority-grant/requests",
            "grant_route": "/lens/resident-runtime/authority-grant",
            "grants_route": "/lens/resident-runtime/authority-grant/grants",
            "denials_route": "/lens/resident-runtime/authority-grant/denials",
            "approval_action": "lens.resident_runtime.execution_authority",
            "next_step": "create_or_select_exact_approved_resident_runtime_execution_authority_request",
            "authority_required": "operator_approval",
            "authority_granted": False,
            "blockers": ["approval_id_required"],
            "would_execute": False,
            "would_mutate": False,
        },
        "resident_runtime_authority_grant_blocked_requirements": [
            "exact_resident_runtime_execution_authority_approval",
            "actor_scope",
            "resident_supervision_gate",
            "resident_host_supervision_authority_preflight",
            "summon_gate",
            "tray_gate",
            "overlay_gate",
            "runtime_activation_plan",
            "resident_runtime_execution_authority",
        ],
        "resident_runtime_authority_grant_requirements_total": 16,
        "resident_runtime_authority_grant_requirements_ready_total": 7,
        "resident_runtime_authority_grant_requirements_blocked_total": 9,
        "resident_runtime_authority_grant_ready": False,
        "resident_runtime_execution_authority": False,
        "resident_claim_allowed": False,
        "next_smallest_truthful_gap": "approve_resident_runtime_execution_authority_grant_receipt",
        "read_only_contract": True,
        "diagnostic_only": True,
        "would_execute": False,
        "would_mutate": False,
    }
    assert closure_criteria["mode_visibility"]["ready"] is True
    assert closure_criteria["pilot_visibility_groundwork"]["ready"] is True
    assert closure_criteria["system_resident_presence"]["ready"] is False
    assert closure_criteria["system_resident_presence"]["next_smallest_truthful_gap"] == (
        "resident_host_supervision_authority_readiness_blockers"
    )
    assert closure_criteria["system_resident_presence"]["handoff"] == {
        "next_step": "resolve_resident_host_runtime_loop_before_system_resident_claim",
        "runtime_loop_readiness_route": "/lens/host/runtime-loop/readiness",
        "runtime_loop_route": "/lens/host/runtime-loop",
        "host_route": "/lens/host",
        "supervision_authority_readiness_route": "/lens/host/supervision/authority/readiness",
        "persistent_supervision_route": "/lens/host/persistent-supervision",
        "resident_runtime_plan_route": "/lens/resident-runtime/plan",
        "tray_route": "/lens/tray",
        "overlay_route": "/lens/overlay",
        "authority_required": "resident_runtime_execution_authority",
        "authority_granted": False,
        "supervision_authority_next_smallest_truthful_gap": "host_supervision_authority_exact_approval_request",
        "supervision_authority_first_blocked_requirement": "exact_supervision_authority_approval",
        "supervision_authority_first_blocked_requirement_handoff": {
            "id": "exact_supervision_authority_approval",
            "label": "Exact approved host supervision authority request",
            "status": "blocked",
            "route": "/lens/host/supervision/authority/requests",
            "readiness_route": "/lens/host/supervision/authority/readiness",
            "request_route": "/lens/host/supervision/authority/request",
            "requests_route": "/lens/host/supervision/authority/requests",
            "grant_route": "/lens/host/supervision/authority",
            "grants_route": "/lens/host/supervision/authority/grants",
            "denials_route": "/lens/host/supervision/authority/denials",
            "approval_action": "lens.host.supervision_authority",
            "next_step": "create_or_select_exact_approved_host_supervision_authority_request",
            "authority_required": "operator_approval",
            "authority_granted": False,
            "blockers": ["approval_id_required"],
            "would_execute": False,
            "would_mutate": False,
        },
        "supervision_authority_blocked_requirements": [
            "exact_supervision_authority_approval",
            "actor_scope",
            "resident_supervision_gate",
            "process_supervision_authority",
            "process_restart_authority",
            "service_install_authority",
            "service_control_authority",
            "resident_claim_authority",
        ],
        "supervision_authority_requirements_total": 14,
        "supervision_authority_requirements_ready_total": 6,
        "supervision_authority_requirements_blocked_total": 8,
        "supervision_authority_ready": False,
        "supervision_authority_granted": False,
        "process_supervision_authority": False,
        "service_control_authority": False,
        "resident_claim_authority": False,
        "next_smallest_truthful_gap": "resident_host_supervision_authority_readiness_blockers",
        "read_only_contract": True,
        "diagnostic_only": True,
        "would_execute": False,
        "would_mutate": False,
    }
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
    os_binding_authority_requests = body["os_binding_authority_requests"]
    assert os_binding_authority_requests["kind"] == "lens.os_binding.command_palette_binding_authority.request_readback"
    assert os_binding_authority_requests["status"] == "none"
    assert os_binding_authority_requests["route"] == "/lens/os-binding/authority/requests"
    assert os_binding_authority_requests["authority_route"] == "/lens/os-binding/authority"
    assert os_binding_authority_requests["request_route"] == "/lens/os-binding/authority/request"
    assert os_binding_authority_requests["pending_count"] == 0
    assert os_binding_authority_requests["approved_count"] == 0
    assert os_binding_authority_requests["total_count"] == 0
    assert os_binding_authority_requests["authority_required"] == "os_level_command_palette_binding_authority"
    assert os_binding_authority_requests["authority_granted"] is False
    assert os_binding_authority_requests["os_level_command_palette_binding_authority"] is False
    assert body["command_palette"]["status"] == "readback_ready"
    assert body["command_palette"]["summon_anywhere"] is False
    assert body["command_palette"]["availability"] == "chat_ui_only"
    assert body["command_palette"]["url_entrypoint_ready"] is True
    assert body["command_palette"]["url_entrypoint"]["route"] == "/?francis_lens=command_palette"
    assert body["command_palette"]["url_entrypoint"]["opens_palette_in_chat_ui"] is True
    assert body["command_palette"]["url_entrypoint"]["os_level_command_palette"] is False
    assert body["command_palette"]["url_entrypoint"]["summon_anywhere"] is False
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
    os_binding_response = client.get("/lens/os-binding/readiness")
    assert os_binding_response.status_code == 200
    assert body["os_binding_readiness"] == os_binding_response.json()
    os_binding = body["os_binding_readiness"]
    assert os_binding["kind"] == "lens.os_binding.readiness"
    assert os_binding["status"] == "blocked"
    assert os_binding["route"] == "/lens/os-binding/readiness"
    assert os_binding["plan_route"] == "/lens/os-binding/plan"
    assert os_binding["ready"] is False
    assert os_binding["os_binding_ready"] is False
    assert os_binding["os_level_command_palette"] is False
    assert os_binding["summon_anywhere"] is False
    assert os_binding["first_blocker_family"] == "palette_binding"
    assert os_binding["next_smallest_truthful_gap"] == "os_level_command_palette_binding"
    assert os_binding["requirements_total"] == 8
    assert os_binding["requirements_ready_total"] == 1
    assert os_binding["requirements_blocked_total"] == 7
    assert os_binding["blocked_requirements"] == [
        "os_level_command_palette",
        "global_hotkey_binding",
        "summon_binding",
        "resident_host",
        "tray_presence",
        "overlay_window",
        "authority_boundary",
    ]
    assert os_binding["authority_request_readback"]["status"] == "none"
    assert os_binding["authority_request_readback"]["readback_ready"] is True
    assert os_binding["authority_request_readback"]["pending_count"] == 0
    assert os_binding["authority_request_readback"]["total_count"] == 0
    assert (
        os_binding["authority_request_readback"]["authority_required"] == "os_level_command_palette_binding_authority"
    )
    assert os_binding["authority_request_readback"]["authority_granted"] is False
    os_binding_requirements = {item["id"]: item for item in os_binding["requirements"]}
    assert os_binding_requirements["authority_request_readback"]["ready"] is True
    assert os_binding_requirements["authority_request_readback"]["route"] == "/lens/os-binding/authority/requests"
    assert os_binding_requirements["authority_request_readback"]["authority_required"] == (
        "os_level_command_palette_binding_authority"
    )
    assert os_binding_requirements["os_level_command_palette"]["readback_ready"] is True
    assert os_binding_requirements["os_level_command_palette"]["source_route"] == "/lens/status"
    assert os_binding["command_palette_contract"]["readback_ready"] is True
    assert os_binding["command_palette_contract"]["bridge_script"] == "scripts/lens-command-palette.ps1"
    assert "os_level_command_palette_missing" in os_binding["blocker_groups"]["palette_binding"]
    assert "global_hotkey_binding_missing" in os_binding["blocker_groups"]["global_hotkey_binding"]
    assert "summon_binding_missing" in os_binding["blocker_groups"]["summon_binding"]
    assert os_binding["governance"]["execution_authority"] is False
    assert os_binding["governance"]["approval_decision_authority"] is False
    assert os_binding["governance"]["memory_write"] is False
    assert os_binding["governance"]["hotkey_registration_authority"] is False
    assert os_binding["governance"]["tray_registration_authority"] is False
    assert os_binding["governance"]["overlay_control_authority"] is False
    assert os_binding["implementation_plan"]["route"] == "/lens/os-binding/plan"
    assert os_binding["implementation_plan"]["plan_available"] is True
    assert os_binding["implementation_plan"]["implementation_ready"] is False
    assert os_binding["implementation_plan"]["command_palette_contract"]["readback_ready"] is True
    os_binding_execution_response = client.get("/lens/os-binding/execution/readiness")
    assert os_binding_execution_response.status_code == 200
    os_binding_execution = body["os_binding_execution_readiness"]
    direct_os_binding_execution = os_binding_execution_response.json()
    assert os_binding_execution["kind"] == direct_os_binding_execution["kind"]
    assert os_binding_execution["route"] == direct_os_binding_execution["route"]
    assert os_binding_execution["execute_route"] == direct_os_binding_execution["execute_route"]
    assert os_binding_execution["denials_route"] == direct_os_binding_execution["denials_route"]
    assert os_binding_execution["kind"] == "lens.os_binding.command_palette_binding.execution_readiness"
    assert os_binding_execution["status"] == "blocked"
    assert os_binding_execution["route"] == "/lens/os-binding/execution/readiness"
    assert os_binding_execution["ready"] is False
    assert os_binding_execution["execution_ready"] is False
    assert os_binding_execution["denial_boundary_observed"] is True
    assert os_binding_execution["denial_status"] == "blocked"
    assert os_binding_execution["denial_receipt_readback_ready"] is True
    assert os_binding_execution["denial_receipt_total"] == 0
    assert "os_binding_execution_boundary_not_implemented" in os_binding_execution["blockers"]
    assert "system_write_permission" in os_binding_execution["blocked_requirements"]
    assert os_binding_execution["governance"]["execution_authority"] is False
    assert os_binding_execution["governance"]["approval_decision_authority"] is False
    assert os_binding_execution["governance"]["memory_write"] is False
    assert os_binding_execution["governance"]["denial_receipt_write_authority"] is False
    assert body["receipts"]["lens_os_binding_readiness_route"] == "/lens/os-binding/readiness"
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
        "authority_route": "/lens/host/activation/authority",
        "authority_grants_route": "/lens/host/activation/authority/grants",
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
            "authority_route": "/lens/host/activation/authority",
            "authority_grants_route": "/lens/host/activation/authority/grants",
            "read_only_contract": False,
            "activation_authority": False,
            "execution_authority": False,
            "approval_decision_authority": False,
            "memory_write": False,
            "local_process_launch_authority": False,
            "receipt_write_authority": False,
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
    assert resident_host["resident_runtime_execution_receipts_route"] == "/lens/resident-runtime/executions"
    resident_runtime_execution_receipts = resident_host["resident_runtime_execution_receipts"]
    assert resident_runtime_execution_receipts["kind"] == "lens.resident_runtime.activation.execution_receipts"
    assert resident_runtime_execution_receipts["status"] == "empty"
    assert resident_runtime_execution_receipts["route"] == "/lens/resident-runtime/executions"
    assert resident_runtime_execution_receipts["execute_route"] == "/lens/resident-runtime/execute"
    assert resident_runtime_execution_receipts["host_supervision_executions_route"] == (
        "/lens/host/supervision/executions"
    )
    assert resident_runtime_execution_receipts["total"] == 0
    assert resident_runtime_execution_receipts["latest"] is None
    assert resident_runtime_execution_receipts["items"] == []
    assert resident_runtime_execution_receipts["resident_supervised_runtime_receipt_observed"] is False
    assert resident_runtime_execution_receipts["resident_claim_allowed"] is False
    assert resident_runtime_execution_receipts["governance"]["gate"] == (
        "lens_resident_runtime_activation_execution_receipts_readback"
    )
    assert resident_runtime_execution_receipts["governance"]["read_only_contract"] is True
    assert resident_runtime_execution_receipts["governance"]["host_supervision_receipt_projection"] is True
    assert resident_runtime_execution_receipts["governance"]["execution_authority"] is False
    assert resident_runtime_execution_receipts["governance"]["approval_decision_authority"] is False
    assert resident_runtime_execution_receipts["governance"]["process_supervision_authority"] is False
    assert resident_runtime_execution_receipts["governance"]["service_control_authority"] is False
    assert resident_runtime_execution_receipts["governance"]["memory_write"] is False
    assert resident_runtime_execution_receipts["governance"]["resident_claim_authority"] is False
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
    assert supervision_authority_readiness["operator_surface_readback_ready"] is True
    assert supervision_authority_readiness["first_blocked_requirement"] == "exact_supervision_authority_approval"
    assert [item["id"] for item in supervision_authority_readiness["blocked_requirement_handoffs"]] == (
        supervision_authority_readiness["blocked_requirements"]
    )
    assert supervision_authority_readiness["first_blocked_requirement_handoff"] == {
        "id": "exact_supervision_authority_approval",
        "label": "Exact approved host supervision authority request",
        "status": "blocked",
        "route": "/lens/host/supervision/authority/requests",
        "readiness_route": "/lens/host/supervision/authority/readiness",
        "request_route": "/lens/host/supervision/authority/request",
        "requests_route": "/lens/host/supervision/authority/requests",
        "grant_route": "/lens/host/supervision/authority",
        "grants_route": "/lens/host/supervision/authority/grants",
        "denials_route": "/lens/host/supervision/authority/denials",
        "approval_action": "lens.host.supervision_authority",
        "next_step": "create_or_select_exact_approved_host_supervision_authority_request",
        "authority_required": "operator_approval",
        "authority_granted": False,
        "blockers": ["approval_id_required"],
        "would_execute": False,
        "would_mutate": False,
    }
    assert (
        supervision_authority_readiness["next_smallest_truthful_gap"]
        == "host_supervision_authority_exact_approval_request"
    )
    assert supervision_authority_readiness["ready"] is False
    assert supervision_authority_readiness["preflight_ready"] is True
    assert supervision_authority_readiness["authority_ready"] is False
    assert supervision_authority_readiness["supervision_ready"] is False
    assert supervision_authority_readiness["resident_claim_allowed"] is False
    assert supervision_authority_readiness["boundary_observed"] is True
    assert supervision_authority_readiness["request_readback_ready"] is True
    assert supervision_authority_readiness["request_pending_count"] == 0
    assert supervision_authority_readiness["request_approved_count"] == 0
    assert supervision_authority_readiness["request_total_count"] == 0
    assert supervision_authority_readiness["latest_request_approval_id"] == ""
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
    assert supervision_authority_readiness_requirements["host_supervision_authority_request_readback"]["ready"] is True
    assert supervision_authority_readiness_requirements["host_supervision_authority_denial_boundary"]["ready"] is True
    assert supervision_authority_readiness_requirements["host_supervision_authority_denial_receipts"]["ready"] is True
    assert supervision_authority_readiness_requirements["host_supervision_authority_grant_receipts"]["ready"] is True
    assert supervision_authority_readiness_requirements["authority_grant_implementation"]["ready"] is True
    assert "actor_scope" in supervision_authority_readiness["blocked_requirements"]
    assert "host_supervision_authority_request_readback" not in supervision_authority_readiness["blocked_requirements"]
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
    service_readback = resident_host["service_readback"]
    assert service_readback["readback_ready"] is True
    assert service_readback["service_name"] == "Francis-LensHost"
    assert service_readback["windows_service"] is True
    assert service_readback["service_status_readback"] is True
    assert service_readback["host_query"] == "windows_service_status"
    if os.name == "nt":
        assert service_readback["status"] in {
            "not_installed",
            "running",
            "stopped",
            "paused",
            "start_pending",
            "stop_pending",
            "continue_pending",
            "pause_pending",
            "unknown",
            "unavailable",
        }
        assert service_readback["platform_supported"] is True
    else:
        assert service_readback["status"] == "unsupported_platform"
        assert service_readback["platform_supported"] is False
    assert isinstance(service_readback["installed"], bool)
    assert service_readback["install_supported"] is False
    assert service_readback["start_supported"] is False
    assert service_readback["stop_supported"] is False
    assert service_readback["restart_supported"] is False
    assert service_readback["install_authority"] is False
    assert service_readback["service_install_authority"] is False
    assert service_readback["service_control_authority"] is False
    assert service_readback["blocked_reason"] in {
        "lens_host_service_not_installed",
        "service_control_authority_not_granted",
        "windows_service_readback_unavailable",
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
            "Resident",
        ],
        "planned_command": "pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/lens-host.ps1 -Mode Resident",
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
        "state_kind": "",
        "state_status": "",
        "state_pid": 0,
        "state_pid_matches_pid_file": False,
        "state_updated_at": "",
        "pid_path": "data/runtime/lens-host/lens-host.pid",
        "pid_present": False,
        "pid": 0,
        "process_alive": False,
        "process_alive_check": "not_attempted_no_pid_file",
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
        "host_mode": "",
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
        "resident_runtime_candidate_supervised": False,
        "fresh_bounded_supervisor_observed": False,
        "fresh_supervised_session_completed": False,
        "fresh_resident_runtime_candidate_supervised": False,
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
    assert launch_manifest["runtime_boundary_route"] == "/lens/host/runtime-boundary"
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
    assert launch_manifest["resident_command"] == {
        "shell": "pwsh",
        "args": [
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "scripts/lens-host.ps1",
            "-Mode",
            "Resident",
        ],
        "working_directory": ".",
        "executable": True,
        "authority_granted": False,
        "resident_claim_allowed": False,
        "reason": (
            "Manual resident runtime candidate is available; service supervision, tray, summon, "
            "overlay, and resident claim remain blocked."
        ),
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
    assert launch_manifest["activation_execution_readback"] == {
        "status": "empty",
        "readback_ready": True,
        "route": "/lens/host/activation/executions",
        "execute_route": "/lens/host/activation/execute",
        "receipt_root": "data/lens/host_activation_executions",
        "receipt_count": 0,
        "latest_receipt_id": "",
        "latest_status": "",
        "latest_created_ts": 0.0,
        "latest_runner_status": "",
        "latest_observed_process": False,
        "latest_observed_pid": 0,
        "latest_runtime_state_path": "",
        "bounded_activation_execution_observed": False,
        "resident_host_process_claimed": False,
        "resident_claim_allowed": False,
        "resident_claim_authority": False,
        "evidence_only": True,
        "does_not_satisfy_resident_host_process": True,
    }
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
        "host_activation_execution_receipts",
        "host_supervision_execution_receipts",
        "host_supervisor_readback",
        "host_readiness",
        "tray_presence",
        "global_hotkey",
        "overlay_window",
        "summon_binding",
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
        "lens_summon_binding_disabled_pending_authority",
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
    assert summon_enablement_gate["first_blocker_family"] == "resident_host"
    expected_summon_blocked_families = [
        "resident_host",
        "tray_presence",
        "overlay_window",
        "global_hotkey_binding",
        "summon_binding",
        "authority",
    ]
    assert summon_enablement_gate["blocked_families"] == expected_summon_blocked_families
    assert summon_enablement_gate["operator_surface_readback_ready"] is True
    assert summon_enablement_gate["first_blocker_family_handoff_observed"] is True
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
    blocker_family_readback = {item["id"]: item for item in summon_enablement_gate["blocker_family_readback"]}
    assert list(blocker_family_readback) == expected_summon_blocked_families
    assert blocker_family_readback["resident_host"]["route"] == "/lens/host"
    assert blocker_family_readback["resident_host"]["status"] == "blocked"
    assert blocker_family_readback["resident_host"]["ready"] is False
    assert blocker_family_readback["resident_host"]["authority_required"] == "resident_runtime_execution_authority"
    assert "resident_host_process_missing" in blocker_family_readback["resident_host"]["blockers"]
    assert blocker_family_readback["tray_presence"]["route"] == "/lens/tray"
    assert blocker_family_readback["overlay_window"]["route"] == "/lens/overlay"
    assert blocker_family_readback["global_hotkey_binding"]["route"] == "/lens/summon"
    assert blocker_family_readback["summon_binding"]["route"] == "/lens/summon"
    assert blocker_family_readback["authority"]["route"] == "/lens/preflight"
    expected_first_summon_handoff = {
        "id": "resident_host",
        "label": "Resident host",
        "status": "blocked",
        "blockers": [
            "resident_host_process_missing",
            "lens_host_runtime_not_implemented",
            "local_process_launch_authority_not_granted",
        ],
        "proof_script": "scripts/lens-summon-resident-host-blocker-proof.ps1 -Mode Status",
        "route": "/lens/host",
        "readiness_route": "/lens/host/runtime-loop/readiness",
        "next_step": "run_resident_host_blocker_proof",
        "next_smallest_truthful_gap": "resident_host_runtime_blocker_boundary",
        "authority_required": "resident_runtime_execution_authority",
        "authority_granted": False,
        "read_only_contract": True,
        "diagnostic_only": True,
        "would_execute": False,
        "would_mutate": False,
    }
    assert summon_enablement_gate["first_blocker_family_handoff"] == expected_first_summon_handoff
    assert [handoff["id"] for handoff in summon_enablement_gate["blocked_family_handoffs"]] == (
        expected_summon_blocked_families
    )
    assert [handoff["proof_script"] for handoff in summon_enablement_gate["blocked_family_handoffs"]] == [
        "scripts/lens-summon-resident-host-blocker-proof.ps1 -Mode Status",
        "scripts/lens-summon-tray-presence-blocker-proof.ps1 -Mode Status",
        "scripts/lens-summon-overlay-window-blocker-proof.ps1 -Mode Status",
        "scripts/lens-summon-global-hotkey-binding-blocker-proof.ps1 -Mode Status",
        "scripts/lens-summon-binding-blocker-proof.ps1 -Mode Status",
        "scripts/lens-summon-authority-blocker-proof.ps1 -Mode Status",
    ]
    assert [handoff["next_smallest_truthful_gap"] for handoff in summon_enablement_gate["blocked_family_handoffs"]] == [
        "resident_host_runtime_blocker_boundary",
        "summon_overlay_window_blocker_boundary",
        "summon_global_hotkey_binding_blocker_boundary",
        "summon_binding_blocker_boundary",
        "summon_authority_blocker_boundary",
        "stage6_lens_completion_audit",
    ]
    assert all(handoff["read_only_contract"] is True for handoff in summon_enablement_gate["blocked_family_handoffs"])
    assert all(handoff["diagnostic_only"] is True for handoff in summon_enablement_gate["blocked_family_handoffs"])
    assert all(handoff["authority_granted"] is False for handoff in summon_enablement_gate["blocked_family_handoffs"])
    assert all(handoff["would_execute"] is False for handoff in summon_enablement_gate["blocked_family_handoffs"])
    assert all(handoff["would_mutate"] is False for handoff in summon_enablement_gate["blocked_family_handoffs"])
    assert summon_enablement_gate["summon_anywhere_family_chain_completion_audit_handoff_observed"] is True
    assert summon_enablement_gate["summon_anywhere_family_chain_completion_audit_handoff"] == {
        "next_step": "consume_summon_anywhere_family_chain_proof_before_stage6_closure",
        "proof_script": "scripts/lens-summon-anywhere-family-chain-proof.ps1 -Mode Status",
        "previous_next_smallest_truthful_gap": "summon_anywhere_blockers",
        "next_smallest_truthful_gap": "stage6_lens_completion_audit",
        "blocked_families": expected_summon_blocked_families,
        "authority_required": "resident_runtime_execution_authority",
        "authority_granted": False,
        "read_only_contract": True,
        "diagnostic_only": True,
        "would_execute": False,
        "would_mutate": False,
    }
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
        "first_blocker_family_handoff_readback": True,
        "summon_anywhere_family_chain_completion_audit_handoff_readback": True,
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
    assert body["receipts"]["lens_os_binding_authority_route"] == "/lens/os-binding/authority"
    assert body["receipts"]["lens_os_binding_authority_request_route"] == "/lens/os-binding/authority/request"
    assert body["receipts"]["lens_os_binding_authority_requests_route"] == "/lens/os-binding/authority/requests"
    assert body["receipts"]["lens_os_binding_execution_readiness_route"] == "/lens/os-binding/execution/readiness"
    assert body["receipts"]["lens_resident_surface_route"] == "/lens/resident-surface"
    assert body["receipts"]["lens_resident_surface_activation_route"] == "/lens/resident-surface/activation"
    assert body["receipts"]["lens_resident_runtime_executions_route"] == "/lens/resident-runtime/executions"
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
    assert _criterion(body, "command_palette_commands")["url_entrypoint_ready"] is True
    assert _criterion(body, "command_palette_commands")["url_entrypoint"]["route"] == "/?francis_lens=command_palette"
    os_binding_criterion = _criterion(body, "os_binding_readiness")
    assert os_binding_criterion["status"] == "blocked"
    assert os_binding_criterion["audit_status"] == "complete"
    assert os_binding_criterion["evidence"] == [
        "/lens/os-binding/readiness",
        "/lens/os-binding/execution/readiness",
        "/lens/os-binding/authority/requests",
        "/lens/os-binding/authority/request",
        "/lens/os-binding/denials",
        "/lens/summon",
        "/lens/status",
    ]
    assert os_binding_criterion["ready"] is False
    assert os_binding_criterion["os_binding_ready"] is False
    assert os_binding_criterion["os_level_command_palette"] is False
    assert os_binding_criterion["summon_anywhere"] is False
    assert os_binding_criterion["execution_readiness_status"] == "blocked"
    assert os_binding_criterion["execution_readiness_ready"] is False
    assert os_binding_criterion["execution_boundary_observed"] is True
    assert os_binding_criterion["execution_denial_status"] == "blocked"
    assert os_binding_criterion["execution_denial_receipt_readback_ready"] is True
    assert os_binding_criterion["execution_denial_receipt_total"] == 0
    assert os_binding_criterion["latest_execution_denial_receipt_id"] == ""
    assert "system_write_permission" in os_binding_criterion["execution_blocked_requirements"]
    assert os_binding_criterion["execution_next_smallest_truthful_gap"] == "os_binding_execution_prerequisites"
    assert os_binding_criterion["execution_denial"]["kind"] == (
        "lens.os_binding.command_palette_binding.execution_denial"
    )
    assert os_binding_criterion["execution_denial"]["executed"] is False
    assert os_binding_criterion["authority_request_readback_status"] == "none"
    assert os_binding_criterion["authority_request_readback_ready"] is True
    assert os_binding_criterion["authority_route"] == "/lens/os-binding/authority"
    assert os_binding_criterion["authority_request_route"] == "/lens/os-binding/authority/request"
    assert os_binding_criterion["authority_requests_route"] == "/lens/os-binding/authority/requests"
    assert os_binding_criterion["authority_request_pending_count"] == 0
    assert os_binding_criterion["authority_request_approved_count"] == 0
    assert os_binding_criterion["authority_request_total_count"] == 0
    assert os_binding_criterion["authority_request_latest_approval_id"] == ""
    assert os_binding_criterion["authority_granted"] is False
    assert os_binding_criterion["os_level_command_palette_binding_authority"] is False
    assert os_binding_criterion["first_blocker_family"] == "palette_binding"
    assert os_binding_criterion["next_smallest_truthful_gap"] == "os_level_command_palette_binding"
    assert os_binding_criterion["requirements_total"] == 8
    assert os_binding_criterion["requirements_ready_total"] == 1
    assert os_binding_criterion["requirements_blocked_total"] == 7
    assert "os_level_command_palette" in os_binding_criterion["blocked_requirements"]
    assert "os_level_command_palette_missing" in os_binding_criterion["blockers"]
    assert "os_level_command_palette_missing" in os_binding_criterion["blocker_groups"]["palette_binding"]
    assert os_binding_criterion["execution_authority"] is False
    assert os_binding_criterion["approval_decision_authority"] is False
    assert os_binding_criterion["local_process_launch_authority"] is False
    assert os_binding_criterion["process_supervision_authority"] is False
    assert os_binding_criterion["service_control_authority"] is False
    assert os_binding_criterion["hotkey_registration_authority"] is False
    assert os_binding_criterion["tray_registration_authority"] is False
    assert os_binding_criterion["overlay_control_authority"] is False
    assert os_binding_criterion["summon_authority"] is False
    assert os_binding_criterion["memory_write"] is False
    assert os_binding_criterion["resident_claim_authority"] is False
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
        "/lens/host/supervision/authority/requests",
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
    assert host_supervision_readiness_criterion["request_readback_ready"] is True
    assert host_supervision_readiness_criterion["request_pending_count"] == 0
    assert host_supervision_readiness_criterion["request_approved_count"] == 0
    assert host_supervision_readiness_criterion["request_total_count"] == 0
    assert host_supervision_readiness_criterion["latest_request_approval_id"] == ""
    assert host_supervision_readiness_criterion["denial_receipt_readback_ready"] is True
    assert host_supervision_readiness_criterion["grant_receipt_readback_ready"] is True
    assert host_supervision_readiness_criterion["receipt_count"] == 0
    assert host_supervision_readiness_criterion["latest_receipt_id"] == ""
    assert host_supervision_readiness_criterion["grant_receipt_count"] == 0
    assert host_supervision_readiness_criterion["latest_grant_receipt_id"] == ""
    assert host_supervision_readiness_criterion["active_grant_receipt_id"] == ""
    assert host_supervision_readiness_criterion["requirements_total"] >= 11
    assert host_supervision_readiness_criterion["requirements_blocked_total"] >= 6
    assert (
        "host_supervision_authority_request_readback"
        not in host_supervision_readiness_criterion["blocked_requirements"]
    )
    assert "authority_grant_implementation" not in host_supervision_readiness_criterion["blocked_requirements"]
    assert host_supervision_readiness_criterion["operator_surface_readback_ready"] is True
    assert host_supervision_readiness_criterion["first_blocked_requirement"] == "exact_supervision_authority_approval"
    assert [item["id"] for item in host_supervision_readiness_criterion["blocked_requirement_handoffs"]] == (
        host_supervision_readiness_criterion["blocked_requirements"]
    )
    assert host_supervision_readiness_criterion["first_blocked_requirement_handoff"] == {
        "id": "exact_supervision_authority_approval",
        "label": "Exact approved host supervision authority request",
        "status": "blocked",
        "route": "/lens/host/supervision/authority/requests",
        "readiness_route": "/lens/host/supervision/authority/readiness",
        "request_route": "/lens/host/supervision/authority/request",
        "requests_route": "/lens/host/supervision/authority/requests",
        "grant_route": "/lens/host/supervision/authority",
        "grants_route": "/lens/host/supervision/authority/grants",
        "denials_route": "/lens/host/supervision/authority/denials",
        "approval_action": "lens.host.supervision_authority",
        "next_step": "create_or_select_exact_approved_host_supervision_authority_request",
        "authority_required": "operator_approval",
        "authority_granted": False,
        "blockers": ["approval_id_required"],
        "would_execute": False,
        "would_mutate": False,
    }
    assert (
        host_supervision_readiness_criterion["next_smallest_truthful_gap"]
        == "host_supervision_authority_exact_approval_request"
    )
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
    runtime_execution_receipts_criterion = _criterion(body, "resident_runtime_execution_receipt_readback")
    assert runtime_execution_receipts_criterion["status"] == "empty"
    assert runtime_execution_receipts_criterion["evidence"] == [
        "/lens/resident-runtime/executions",
        "/lens/resident-runtime/execute",
        "/lens/host/supervision/executions",
        "/lens/status",
    ]
    assert runtime_execution_receipts_criterion["receipt_count"] == 0
    assert runtime_execution_receipts_criterion["latest_receipt_id"] == ""
    assert runtime_execution_receipts_criterion["latest_supervision_mode"] == ""
    assert runtime_execution_receipts_criterion["latest_resident_host_process"] is False
    assert runtime_execution_receipts_criterion["latest_resident_supervised_runtime"] is False
    assert runtime_execution_receipts_criterion["resident_supervised_runtime_receipt_observed"] is False
    assert runtime_execution_receipts_criterion["resident_claim_allowed"] is False
    assert runtime_execution_receipts_criterion["execution_authority"] is False
    assert runtime_execution_receipts_criterion["approval_decision_authority"] is False
    assert runtime_execution_receipts_criterion["process_supervision_authority"] is False
    assert runtime_execution_receipts_criterion["service_control_authority"] is False
    assert runtime_execution_receipts_criterion["memory_write"] is False
    assert runtime_execution_receipts_criterion["resident_claim_authority"] is False
    assert runtime_execution_receipts_criterion["receipt_write_authority"] is False
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
    assert (
        resident_surface_activation["execution"]["runtime_authority_grant_readiness_route"]
        == "/lens/resident-runtime/authority-grant/readiness"
    )
    assert resident_surface_activation["execution"]["runtime_authority_grant_readiness_status"] == "blocked"
    assert (
        resident_surface_activation["execution"]["runtime_authority_grant_request_route"]
        == "/lens/resident-runtime/authority-grant/request"
    )
    assert (
        resident_surface_activation["execution"]["runtime_authority_grant_requests_route"]
        == "/lens/resident-runtime/authority-grant/requests"
    )
    assert (
        resident_surface_activation["execution"]["runtime_authority_grants_route"]
        == "/lens/resident-runtime/authority-grant/grants"
    )
    assert (
        resident_surface_activation["execution"]["runtime_authority_grant_denials_route"]
        == "/lens/resident-runtime/authority-grant/denials"
    )
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
    resident_runtime_authority_grant_readiness = resident_surface_activation[
        "resident_runtime_authority_grant_readiness"
    ]
    assert resident_runtime_authority_grant_readiness["kind"] == (
        "lens.resident_runtime.execution_authority_grant.readiness_audit"
    )
    assert resident_runtime_authority_grant_readiness["status"] == "blocked"
    assert resident_runtime_authority_grant_readiness["operator_surface_readback_ready"] is True
    assert (
        resident_runtime_authority_grant_readiness["first_blocked_requirement"]
        == "exact_resident_runtime_execution_authority_approval"
    )
    assert (
        resident_runtime_authority_grant_readiness["next_smallest_truthful_gap"]
        == "approve_resident_runtime_execution_authority_grant_receipt"
    )
    assert resident_surface_activation["resident_runtime_authority_grant_handoff_observed"] is True
    assert resident_surface_activation["resident_runtime_authority_grant_handoff"] == {
        "id": "exact_resident_runtime_execution_authority_approval",
        "label": "Exact approved resident runtime execution authority request",
        "status": "blocked",
        "route": "/lens/resident-runtime/authority-grant/requests",
        "readiness_route": "/lens/resident-runtime/authority-grant/readiness",
        "request_route": "/lens/resident-runtime/authority-grant/request",
        "requests_route": "/lens/resident-runtime/authority-grant/requests",
        "grant_route": "/lens/resident-runtime/authority-grant",
        "grants_route": "/lens/resident-runtime/authority-grant/grants",
        "denials_route": "/lens/resident-runtime/authority-grant/denials",
        "approval_action": "lens.resident_runtime.execution_authority",
        "next_step": "create_or_select_exact_approved_resident_runtime_execution_authority_request",
        "authority_required": "operator_approval",
        "authority_granted": False,
        "blockers": ["approval_id_required"],
        "would_execute": False,
        "would_mutate": False,
    }
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
    assert resident_surface_activation["governance"]["resident_runtime_authority_grant_readiness_readback"] is True
    assert resident_surface_activation["governance"]["resident_runtime_authority_grant_handoff_readback"] is True
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
    assert summon_gate_criterion["first_blocker_family"] == "resident_host"
    assert summon_gate_criterion["blocked_families"] == expected_summon_blocked_families
    assert summon_gate_criterion["operator_surface_readback_ready"] is True
    assert summon_gate_criterion["first_blocker_family_handoff_observed"] is True
    assert summon_gate_criterion["first_blocker_family_handoff"] == expected_first_summon_handoff
    assert [handoff["id"] for handoff in summon_gate_criterion["blocked_family_handoffs"]] == (
        expected_summon_blocked_families
    )
    status_family_readback = {item["id"]: item for item in summon_gate_criterion["blocker_family_readback"]}
    assert status_family_readback["resident_host"]["route"] == "/lens/host"
    assert status_family_readback["resident_host"]["status"] == "blocked"
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
    if os.name == "nt":
        assert manifest_body["service_readback"]["status"] in {
            "not_installed",
            "running",
            "stopped",
            "paused",
            "start_pending",
            "stop_pending",
            "continue_pending",
            "pause_pending",
            "unknown",
            "unavailable",
        }
    else:
        assert manifest_body["service_readback"]["status"] == "unsupported_platform"
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
    supervision_authority_request_body = supervision_authority_request.json()
    supervision_authority_approval_id = str(supervision_authority_request_body["approval_id"])
    assert supervision_authority_approval_id
    supervision_authority_request_payload = supervision_authority_request_body["supervision_authority"]
    assert supervision_authority_request_payload["request_kind"] == "lens.host.supervision_authority.request"
    supervision_authority_request_readiness = supervision_authority_request_payload["readiness"]
    assert supervision_authority_request_readiness["kind"] == "lens.host.supervision_authority.readiness_audit"
    assert supervision_authority_request_readiness["status"] == "blocked"
    assert supervision_authority_request_readiness["audit_status"] == "complete"
    assert supervision_authority_request_readiness["route"] == "/lens/host/supervision/authority/readiness"
    assert supervision_authority_request_readiness["ready"] is False
    assert supervision_authority_request_readiness["preflight_ready"] is True
    assert supervision_authority_request_readiness["authority_ready"] is False
    assert supervision_authority_request_readiness["supervision_ready"] is False
    assert supervision_authority_request_readiness["resident_claim_allowed"] is False
    assert supervision_authority_request_readiness["operator_surface_readback_ready"] is True
    assert (
        supervision_authority_request_readiness["first_blocked_requirement"] == "exact_supervision_authority_approval"
    )
    assert (
        supervision_authority_request_readiness["first_blocked_requirement_handoff"]["request_route"]
        == "/lens/host/supervision/authority/request"
    )
    assert supervision_authority_request_readiness["first_blocked_requirement_handoff"]["would_execute"] is False
    assert supervision_authority_request_readiness["first_blocked_requirement_handoff"]["would_mutate"] is False
    assert "exact_supervision_authority_approval" in supervision_authority_request_readiness["blocked_requirements"]
    assert supervision_authority_request_readiness["grant_receipt_count"] == 0
    assert (
        supervision_authority_request_readiness["next_smallest_truthful_gap"]
        == "host_supervision_authority_exact_approval_request"
    )
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
    assert supervision_authority_readiness_body["operator_surface_readback_ready"] is True
    assert [item["id"] for item in supervision_authority_readiness_body["blocked_requirement_handoffs"]] == (
        supervision_authority_readiness_body["blocked_requirements"]
    )
    assert (
        supervision_authority_readiness_body["first_blocked_requirement"]
        == (supervision_authority_readiness_body["blocked_requirements"][0])
    )
    direct_first_blocker_handoff = supervision_authority_readiness_body["first_blocked_requirement_handoff"]
    assert direct_first_blocker_handoff["id"] == supervision_authority_readiness_body["first_blocked_requirement"]
    assert direct_first_blocker_handoff["readiness_route"] == "/lens/host/supervision/authority/readiness"
    assert direct_first_blocker_handoff["would_execute"] is False
    assert direct_first_blocker_handoff["would_mutate"] is False
    assert supervision_authority_readiness_body["ready"] is False
    assert supervision_authority_readiness_body["preflight_ready"] is True
    assert supervision_authority_readiness_body["authority_ready"] is True
    assert supervision_authority_readiness_body["supervision_ready"] is False
    assert supervision_authority_readiness_body["resident_claim_allowed"] is False
    assert supervision_authority_readiness_body["boundary_observed"] is True
    assert supervision_authority_readiness_body["request_readback_ready"] is True
    assert supervision_authority_readiness_body["request_pending_count"] == 0
    assert supervision_authority_readiness_body["request_approved_count"] == 1
    assert supervision_authority_readiness_body["request_total_count"] == 1
    assert supervision_authority_readiness_body["latest_request_approval_id"] == supervision_authority_approval_id
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
    assert direct_readiness_requirements["host_supervision_authority_request_readback"]["ready"] is True
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
    assert (
        "host_supervision_authority_request_readback"
        not in supervision_authority_readiness_body["blocked_requirements"]
    )
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
    summon_readiness_response = client.get("/lens/summon/readiness")
    assert summon_readiness_response.status_code == 200
    assert summon_readiness_response.json() == summon_enablement_gate
    tray_response = client.get("/lens/tray")
    assert tray_response.status_code == 200
    assert tray_response.json() == tray_enablement_gate
    tray_readiness_response = client.get("/lens/tray/readiness")
    assert tray_readiness_response.status_code == 200
    assert tray_readiness_response.json() == tray_enablement_gate
    overlay_response = client.get("/lens/overlay")
    assert overlay_response.status_code == 200
    assert overlay_response.json() == overlay_enablement_gate
    overlay_readiness_response = client.get("/lens/overlay/readiness")
    assert overlay_readiness_response.status_code == 200
    assert overlay_readiness_response.json() == overlay_enablement_gate
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
    assert runtime_authority_grant_readiness_body["operator_surface_readback_ready"] is True
    assert (
        runtime_authority_grant_readiness_body["first_blocked_requirement"]
        == "exact_resident_runtime_execution_authority_approval"
    )
    assert (
        runtime_authority_grant_readiness_body["next_smallest_truthful_gap"]
        == "approve_resident_runtime_execution_authority_grant_receipt"
    )
    assert runtime_authority_grant_readiness_body["first_blocked_requirement_handoff"] == {
        "id": "exact_resident_runtime_execution_authority_approval",
        "label": "Exact approved resident runtime execution authority request",
        "status": "blocked",
        "route": "/lens/resident-runtime/authority-grant/requests",
        "readiness_route": "/lens/resident-runtime/authority-grant/readiness",
        "request_route": "/lens/resident-runtime/authority-grant/request",
        "requests_route": "/lens/resident-runtime/authority-grant/requests",
        "grant_route": "/lens/resident-runtime/authority-grant",
        "grants_route": "/lens/resident-runtime/authority-grant/grants",
        "denials_route": "/lens/resident-runtime/authority-grant/denials",
        "approval_action": "lens.resident_runtime.execution_authority",
        "next_step": "create_or_select_exact_approved_resident_runtime_execution_authority_request",
        "authority_required": "operator_approval",
        "authority_granted": False,
        "blockers": ["approval_id_required"],
        "would_execute": False,
        "would_mutate": False,
    }
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


def test_stage6_next_handoff_promotes_audited_enablement_authority_denial() -> None:
    from francis.lens.status import _stage6_next_handoff_readback

    closure_readback = {
        "ready_to_close": False,
        "next_smallest_truthful_gap": "summon_anywhere_blockers",
        "blocked_criteria": ["summon_anywhere"],
        "criteria": [
            {
                "id": "summon_anywhere",
                "next_smallest_truthful_gap": "summon_anywhere_blockers",
                "handoff": {
                    "next_step": "resolve_summon_anywhere_blockers_before_stage6_closure",
                    "proof_script": "scripts/lens-summon-preflight.ps1 -Mode Status",
                    "status_route": "/lens/status",
                    "readiness_route": "/lens/summon/readiness",
                    "authority_required": "resident_runtime_execution_authority",
                },
            }
        ],
    }
    first_missing_handoff = {
        "id": "resident_host_process",
        "blocker": "resident_host_process_missing",
        "requirement_state": "missing",
        "next_smallest_truthful_gap": "resident_host_process_not_supervised",
        "next_step": "resolve_resident_host_process_before_persistent_supervision_enablement",
        "proof_script": "scripts/lens-resident-host-runtime-boundary-proof.ps1 -Mode Status",
        "route": "/lens/host",
        "readiness_route": "/lens/host/runtime-loop/readiness",
        "authority_required": "resident_host_process_tray_hotkey_overlay_and_summon_prerequisites",
        "read_only_contract": True,
        "diagnostic_only": True,
        "would_execute": False,
        "would_mutate": False,
    }
    resident_host = {
        "persistent_supervision_plan": {
            "required_before_enable_ready": False,
            "missing_required_before_enable": ["resident_host_process"],
            "first_missing_required_before_enable": "resident_host_process",
            "first_missing_requirement_handoff": first_missing_handoff,
        },
        "persistent_supervision_enablement": {
            "required_before_enable_ready": False,
            "missing_required_before_enable": ["resident_host_process"],
            "first_missing_required_before_enable": "resident_host_process",
            "first_missing_requirement_handoff": first_missing_handoff,
        },
        "persistent_supervision_enablement_authority_readiness": {
            "kind": "lens.host.persistent_supervision_enablement_authority.readiness_audit",
            "status": "blocked",
            "route": "/lens/host/persistent-supervision/enablement/authority/readiness",
            "request_route": "/lens/host/persistent-supervision/enablement/authority/request",
            "authority_route": "/lens/host/persistent-supervision/enablement/authority",
            "grants_route": "/lens/host/persistent-supervision/enablement/authority/grants",
            "enablement_route": "/lens/host/persistent-supervision/enablement",
            "boundary_observed": True,
            "grant_boundary_observed": True,
            "grant_receipt_readback_ready": True,
            "enablement_authority_granted": False,
            "service_config_write_authority": False,
            "service_config_updated": False,
            "blockers": [
                "persistent_supervision_enablement_authority_not_granted",
                "service_config_write_authority_not_granted",
            ],
        },
        "persistent_supervision_enablement_execution_readiness": {
            "kind": "lens.host.persistent_supervision_enablement.execution_readiness_audit",
            "status": "blocked",
            "route": "/lens/host/persistent-supervision/enablement/execution/readiness",
            "boundary_observed": True,
            "persistent_supervision_execution_authority": False,
            "receipt_write_authority": False,
            "resident_claim_authority": False,
            "resident_claim_allowed": False,
            "executed": False,
            "blockers": [
                "persistent_supervision_execution_authority_not_granted",
                "resident_claim_authority_not_granted",
            ],
        },
    }

    next_handoff = _stage6_next_handoff_readback(
        closure_readback=closure_readback,
        resident_host=resident_host,
    )

    assert next_handoff["next_smallest_truthful_gap"] == ("persistent_supervision_enablement_authority_not_granted")
    assert next_handoff["recommended_next_slice"] == (
        "prove_persistent_supervision_enablement_authority_after_candidate_handoff"
    )
    assert next_handoff["recommended_handoff_source"] == ("persistent_supervision_enablement_authority_denial_handoff")
    assert next_handoff["recommended_proof_script"] == (
        "scripts/lens-persistent-supervision-enablement-authority-proof.ps1 -Mode Status"
    )
    assert next_handoff["recommended_route"] == "/lens/host/persistent-supervision/enablement"
    assert next_handoff["recommended_readiness_route"] == (
        "/lens/host/persistent-supervision/enablement/authority/readiness"
    )
    assert next_handoff["recommended_request_route"] == (
        "/lens/host/persistent-supervision/enablement/authority/request"
    )
    assert next_handoff["recommended_grant_route"] == "/lens/host/persistent-supervision/enablement/authority"
    assert next_handoff["recommended_grants_route"] == ("/lens/host/persistent-supervision/enablement/authority/grants")
    assert next_handoff["recommended_execution_readiness_route"] == (
        "/lens/host/persistent-supervision/enablement/execution/readiness"
    )
    assert next_handoff["authority_required"] == "persistent_supervision_enablement_authority"
    assert next_handoff["recommended_prerequisites_handoff_source"] == (
        "persistent_supervision_required_prerequisites_handoff"
    )
    assert next_handoff["recommended_prerequisites_next_slice"] == (
        "resolve_persistent_supervision_required_prerequisites_before_enablement"
    )
    assert next_handoff["recommended_prerequisites_proof_script"] == (
        "scripts/lens-persistent-supervision-prerequisites-proof.ps1 -Mode Status"
    )
    assert (
        next_handoff["persistent_supervision_required_prerequisites_handoff"]["id"]
        == "persistent_supervision_required_prerequisites"
    )
    assert next_handoff["persistent_supervision_required_prerequisites_handoff"]["status"] == "blocked"
    assert next_handoff["persistent_supervision_required_prerequisites_handoff"]["blockers"] == [
        "resident_host_process"
    ]
    assert next_handoff["recommended_first_missing_handoff_source"] == (
        "persistent_supervision_first_missing_requirement_handoff"
    )
    assert next_handoff["recommended_first_missing_next_slice"] == (
        "resolve_resident_host_process_before_persistent_supervision_enablement"
    )
    assert next_handoff["recommended_first_missing_proof_script"] == (
        "scripts/lens-resident-host-runtime-boundary-proof.ps1 -Mode Status"
    )
    assert next_handoff["recommended_first_missing_authority_required"] == "process_supervision_authority"
    assert next_handoff["persistent_supervision_enablement_authority_handoff_observed"] is True
    enablement_handoff = next_handoff["persistent_supervision_enablement_authority_handoff"]
    assert enablement_handoff["id"] == "persistent_supervision_enablement_authority"
    assert enablement_handoff["next_smallest_truthful_gap"] == (
        "persistent_supervision_enablement_authority_not_granted"
    )
    assert enablement_handoff["proof_script"] == (
        "scripts/lens-persistent-supervision-enablement-authority-proof.ps1 -Mode Status"
    )
    assert enablement_handoff["request_route"] == "/lens/host/persistent-supervision/enablement/authority/request"
    assert enablement_handoff["grant_route"] == "/lens/host/persistent-supervision/enablement/authority"
    assert enablement_handoff["grants_route"] == "/lens/host/persistent-supervision/enablement/authority/grants"
    assert enablement_handoff["readiness_route"] == ("/lens/host/persistent-supervision/enablement/authority/readiness")
    assert enablement_handoff["execution_readiness_route"] == (
        "/lens/host/persistent-supervision/enablement/execution/readiness"
    )
    assert enablement_handoff["acceptance_criterion"] == "system_resident_presence"
    assert enablement_handoff["authority_required"] == "persistent_supervision_enablement_authority"
    assert enablement_handoff["authority_granted"] is False
    assert enablement_handoff["enablement_denial_observed"] is True
    assert enablement_handoff["execution_denial_observed"] is True
    assert enablement_handoff["persistent_supervision_enablement_authority"] is False
    assert enablement_handoff["service_config_write_authority"] is False
    assert enablement_handoff["persistent_supervision_execution_authority"] is False
    assert enablement_handoff["resident_claim_authority"] is False
    assert enablement_handoff["resident_claim_allowed"] is False
    assert enablement_handoff["service_config_updated"] is False
    assert enablement_handoff["applied"] is False
    assert enablement_handoff["executed"] is False
    assert enablement_handoff["read_only_contract"] is True
    assert enablement_handoff["diagnostic_only"] is True
    assert enablement_handoff["would_execute"] is False
    assert enablement_handoff["would_mutate"] is False
    assert "persistent_supervision_enablement_authority_not_granted" in enablement_handoff["blockers"]
    assert "persistent_supervision_execution_authority_not_granted" in enablement_handoff["blockers"]

    first_missing_handoff["blocker"] = "resident_host_process_not_supervised"
    first_missing_handoff["requirement_state"] = "foreground_observed_not_supervised"
    live_process_handoff = _stage6_next_handoff_readback(
        closure_readback=closure_readback,
        resident_host=resident_host,
    )
    assert live_process_handoff["next_smallest_truthful_gap"] == "resident_host_process_not_supervised"
    assert live_process_handoff["persistent_supervision_enablement_authority_handoff_observed"] is False
    assert live_process_handoff["persistent_supervision_enablement_authority_handoff"] == {}


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
    expected_enablement_prerequisites = [
        "resident_host_process",
        "tray_presence",
        "global_hotkey_binding",
        "overlay_window",
        "summon_binding",
    ]
    assert body["required_before_enable"] == expected_enablement_prerequisites
    assert body["missing_required_before_enable"] == expected_enablement_prerequisites
    assert body["first_missing_required_before_enable"] == "resident_host_process"
    plan_first_missing_handoff = body["first_missing_requirement_handoff"]
    assert plan_first_missing_handoff["id"] == "resident_host_process"
    assert plan_first_missing_handoff["route"] == "/lens/host"
    assert plan_first_missing_handoff["readiness_route"] == "/lens/host/runtime-loop/readiness"
    assert plan_first_missing_handoff["proof_script"] == (
        "scripts/lens-resident-host-runtime-boundary-proof.ps1 -Mode Status"
    )
    assert plan_first_missing_handoff["next_step"] == (
        "resolve_resident_host_process_before_persistent_supervision_enablement"
    )
    assert plan_first_missing_handoff["next_smallest_truthful_gap"] == "resident_host_process_not_supervised"
    assert plan_first_missing_handoff["read_only_contract"] is True
    assert plan_first_missing_handoff["would_execute"] is False
    assert plan_first_missing_handoff["would_mutate"] is False
    assert plan_first_missing_handoff["authority_granted"] is False
    assert plan_first_missing_handoff["resident_runtime_authority_request_route"] == (
        "/lens/resident-runtime/authority-grant/request"
    )
    assert plan_first_missing_handoff["resident_runtime_authority_route"] == "/lens/resident-runtime/authority-grant"
    assert plan_first_missing_handoff["resident_runtime_plan_route"] == "/lens/resident-runtime/plan"
    assert plan_first_missing_handoff["resident_runtime_execute_route"] == "/lens/resident-runtime/execute"
    assert plan_first_missing_handoff["request_route"] == "/lens/resident-runtime/authority-grant/request"
    assert plan_first_missing_handoff["grant_route"] == "/lens/resident-runtime/authority-grant"
    assert plan_first_missing_handoff["execution_readiness_route"] == "/lens/resident-runtime/plan"
    assert plan_first_missing_handoff["execution_route"] == "/lens/resident-runtime/execute"
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
    assert enablement_body["required_before_enable"] == expected_enablement_prerequisites
    assert enablement_body["missing_required_before_enable"] == expected_enablement_prerequisites
    assert enablement_body["first_missing_required_before_enable"] == "resident_host_process"
    enablement_first_missing_handoff = enablement_body["first_missing_requirement_handoff"]
    assert enablement_first_missing_handoff["id"] == "resident_host_process"
    assert enablement_first_missing_handoff["route"] == "/lens/host"
    assert enablement_first_missing_handoff["readiness_route"] == "/lens/host/runtime-loop/readiness"
    assert enablement_first_missing_handoff["next_smallest_truthful_gap"] == "resident_host_process_not_supervised"
    assert enablement_first_missing_handoff["read_only_contract"] is True
    assert enablement_first_missing_handoff["would_execute"] is False
    assert enablement_first_missing_handoff["would_mutate"] is False
    assert enablement_first_missing_handoff["authority_granted"] is False
    assert enablement_first_missing_handoff["resident_runtime_authority_request_route"] == (
        "/lens/resident-runtime/authority-grant/request"
    )
    assert enablement_first_missing_handoff["resident_runtime_authority_route"] == (
        "/lens/resident-runtime/authority-grant"
    )
    assert enablement_first_missing_handoff["resident_runtime_plan_route"] == "/lens/resident-runtime/plan"
    assert enablement_first_missing_handoff["resident_runtime_execute_route"] == "/lens/resident-runtime/execute"
    dependency_readback = enablement_body["enablement_dependency_readback"]
    assert [item["id"] for item in dependency_readback] == expected_enablement_prerequisites
    dependencies_by_id = {item["id"]: item for item in dependency_readback}
    assert dependencies_by_id["resident_host_process"]["family"] == "resident_host"
    assert dependencies_by_id["resident_host_process"]["route"] == "/lens/host"
    assert dependencies_by_id["resident_host_process"]["status"] == "blocked"
    assert dependencies_by_id["resident_host_process"]["blocker"] == "resident_host_process_missing"
    assert dependencies_by_id["tray_presence"]["route"] == "/lens/tray"
    assert dependencies_by_id["tray_presence"]["blocker"] == "tray_host_missing"
    assert dependencies_by_id["global_hotkey_binding"]["route"] == "/lens/summon"
    assert dependencies_by_id["global_hotkey_binding"]["blocker"] == "global_hotkey_binding_missing"
    assert dependencies_by_id["overlay_window"]["route"] == "/lens/overlay"
    assert dependencies_by_id["overlay_window"]["blocker"] == "overlay_window_missing"
    assert dependencies_by_id["summon_binding"]["route"] == "/lens/summon"
    assert dependencies_by_id["summon_binding"]["blocker"] == "summon_binding_missing"
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
    assert enablement_denial_body["preflight"]["required_before_enable"] == expected_enablement_prerequisites
    assert enablement_denial_body["preflight"]["missing_required_before_enable"] == expected_enablement_prerequisites
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
    assert resident_host["persistent_supervision_plan"]["current_truthful_gap"] == (
        "persistent_supervision_required_prerequisites_missing"
    )
    assert resident_host["persistent_supervision_plan"]["current_truthful_gap_basis"] == (
        "missing_required_before_enable"
    )
    assert resident_host["persistent_supervision_plan"]["current_first_missing_requirement"] == (
        "resident_host_process"
    )
    assert resident_host["persistent_supervision_plan"]["current_first_missing_truthful_gap"] == (
        "resident_host_process_not_supervised"
    )
    assert resident_host["persistent_supervision_plan"]["raw_persistent_supervision_next_smallest_truthful_gap"] == (
        "persistent_supervision_authority_not_granted"
    )
    assert resident_host["persistent_supervision_plan"]["plan"]["would_supervise_process"] is False
    assert resident_host["persistent_supervision_enablement_route"] == ("/lens/host/persistent-supervision/enablement")
    assert resident_host["persistent_supervision_enablement"]["next_smallest_truthful_gap"] == (
        "persistent_supervision_authority_not_granted"
    )
    assert resident_host["persistent_supervision_enablement"]["current_truthful_gap"] == (
        "persistent_supervision_required_prerequisites_missing"
    )
    assert resident_host["persistent_supervision_enablement"]["current_truthful_gap_basis"] == (
        "missing_required_before_enable"
    )
    assert resident_host["persistent_supervision_enablement"]["current_first_missing_requirement"] == (
        "resident_host_process"
    )
    assert resident_host["persistent_supervision_enablement"]["current_first_missing_truthful_gap"] == (
        "resident_host_process_not_supervised"
    )
    assert resident_host["persistent_supervision_enablement"][
        "raw_persistent_supervision_next_smallest_truthful_gap"
    ] == ("persistent_supervision_authority_not_granted")
    assert resident_host["persistent_supervision_enablement"]["required_before_enable"] == (
        expected_enablement_prerequisites
    )
    assert resident_host["persistent_supervision_enablement"]["missing_required_before_enable"] == (
        expected_enablement_prerequisites
    )
    assert resident_host["persistent_supervision_enablement"]["plan"]["would_update_service_config"] is False
    assert resident_host["persistent_supervision_enablement_denial_route"] == (
        "/lens/host/persistent-supervision/enablement"
    )
    prerequisite_bringup = status_body["stage6_readiness"]["prerequisite_bringup"]
    assert prerequisite_bringup["kind"] == "lens.stage6.prerequisite_bringup.plan"
    assert prerequisite_bringup["status"] == "blocked"
    assert prerequisite_bringup["mode"] == "status"
    assert prerequisite_bringup["current_truthful_gap"] == ("persistent_supervision_required_prerequisites_missing")
    assert prerequisite_bringup["current_truthful_gap_basis"] == "missing_required_before_enable"
    assert prerequisite_bringup["current_first_missing_requirement"] == "resident_host_process"
    assert prerequisite_bringup["current_first_missing_truthful_gap"] == "resident_host_process_not_supervised"
    assert prerequisite_bringup["raw_persistent_supervision_next_smallest_truthful_gap"] == (
        "persistent_supervision_authority_not_granted"
    )
    assert prerequisite_bringup["required_before_enable"] == expected_enablement_prerequisites
    assert prerequisite_bringup["missing_required_before_enable"] == expected_enablement_prerequisites
    assert prerequisite_bringup["next_operator_action_requirement"] == "resident_host_process"
    assert prerequisite_bringup["next_operator_action"]["id"] == ("request_resident_runtime_execution_authority")
    assert prerequisite_bringup["next_operator_action"]["route"] == ("/lens/resident-runtime/authority-grant/request")
    assert prerequisite_bringup["next_operator_action"]["live_effect"] == "approval request receipt only"
    assert prerequisite_bringup["next_operator_action"]["script_would_execute"] is False
    assert prerequisite_bringup["next_operator_action"]["script_would_mutate"] is False
    assert prerequisite_bringup["next_operator_command"]["mode"] == "RequestNext"
    assert prerequisite_bringup["next_operator_command"]["requires_confirmation"] is True
    assert prerequisite_bringup["next_operator_command"]["requires_approval_id"] is False
    assert prerequisite_bringup["next_operator_command"]["requires_operator_approval_decision"] is False
    assert "RequestNext" in prerequisite_bringup["next_operator_command"]["command"]
    resident_step = prerequisite_bringup["ordered_prerequisite_steps"][0]
    assert resident_step["id"] == "resident_host_process"
    assert resident_step["status"] == "blocked"
    assert resident_step["next_operator_action"]["id"] == "request_resident_runtime_execution_authority"
    assert resident_step["authority_state"]["resident_runtime"]["authority_granted"] is False
    assert resident_step["authority_state"]["host_supervision"]["authority_granted"] is False
    assert prerequisite_bringup["operator_sequence"][0]["id"] == "request_resident_runtime_execution_authority"
    first_operator_command = prerequisite_bringup["operator_sequence"][0]["operator_command"]
    assert first_operator_command["command"] == (
        ".\\scripts\\lens-stage6-prerequisite-bringup-plan.ps1 -Mode RequestNext -Actor <actor> -ConfirmRequest"
    )
    assert first_operator_command["mode"] == "RequestNext"
    assert first_operator_command["requires_confirmation"] is True
    assert first_operator_command["requires_approval_id"] is False
    assert first_operator_command["requires_operator_approval_decision"] is False
    assert first_operator_command["available_now"] is True
    assert first_operator_command["preview_only"] is False
    assert first_operator_command["availability_reason"] == "current_next_operator_action"
    assert all("operator_command" in item for item in prerequisite_bringup["operator_sequence"])
    assert all(
        item["operator_command"]["available_now"] is False for item in prerequisite_bringup["operator_sequence"][1:]
    )
    assert all(
        item["operator_command"]["preview_only"] is True for item in prerequisite_bringup["operator_sequence"][1:]
    )
    assert prerequisite_bringup["operator_sequence_command_availability"] == {
        "available_now_count": 1,
        "preview_only_count": len(prerequisite_bringup["operator_sequence"]) - 1,
        "sequence_length": len(prerequisite_bringup["operator_sequence"]),
        "truthful": True,
    }
    checks = {item["id"]: item for item in prerequisite_bringup["checks"]}
    assert checks["operator_sequence_command_availability"]["status"] == "truthful"
    assert checks["operator_sequence_command_availability"]["passed"] is True
    assert prerequisite_bringup["governance"]["read_only_contract"] is True
    assert prerequisite_bringup["governance"]["uses_lens_status_readback"] is True
    assert prerequisite_bringup["governance"]["approval_request_write"] is False
    assert prerequisite_bringup["governance"]["authority_grant_receipt_write"] is False
    assert prerequisite_bringup["governance"]["execution_receipt_write"] is False
    assert prerequisite_bringup["governance"]["mutation_authority_granted"] is False
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


def test_stage6_prerequisite_bringup_selects_persistent_enablement_next_actions() -> None:
    from francis.lens.status import (
        _stage6_next_persistent_supervision_enablement_action,
        _stage6_persistent_supervision_enablement_steps,
    )

    actions = _stage6_persistent_supervision_enablement_steps({})

    def select_next(
        *,
        enablement_requests: dict[str, Any] | None = None,
        enablement_grants: dict[str, Any] | None = None,
        execution_requests: dict[str, Any] | None = None,
        execution_grants: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return _stage6_next_persistent_supervision_enablement_action(
            actions=actions,
            status_readbacks={
                "persistent_supervision_enablement_authority_requests": enablement_requests or {},
                "persistent_supervision_enablement_authority_grants": enablement_grants or {},
                "persistent_supervision_enablement_execution_requests": execution_requests or {},
                "persistent_supervision_enablement_execution_authority_grants": execution_grants or {},
            },
        )

    request_action = select_next()
    assert request_action["id"] == "request_persistent_supervision_enablement_authority"
    assert request_action["route"] == "/lens/host/persistent-supervision/enablement/authority/request"

    grant_action = select_next(
        enablement_requests={
            "approved_count": 1,
            "latest": {"status": "approved", "id": "approval-enable-1"},
        }
    )
    assert grant_action["id"] == "grant_persistent_supervision_enablement_authority"
    assert grant_action["approved_approval_id"] == "approval-enable-1"

    execution_request_action = select_next(
        enablement_grants={
            "authority_granted": True,
            "active_latest": {"approval_id": "approval-enable-1"},
        }
    )
    assert execution_request_action["id"] == "request_persistent_supervision_execution_authority"

    execution_grant_action = select_next(
        enablement_grants={
            "authority_granted": True,
            "active_latest": {"approval_id": "approval-enable-1"},
        },
        execution_requests={
            "approved_count": 1,
            "latest": {"status": "approved", "id": "approval-execute-1"},
        },
    )
    assert execution_grant_action["id"] == "grant_persistent_supervision_execution_authority"
    assert execution_grant_action["approved_approval_id"] == "approval-execute-1"

    apply_action = select_next(
        enablement_grants={
            "authority_granted": True,
            "active_latest": {"approval_id": "approval-enable-1"},
        },
        execution_grants={
            "authority_granted": True,
            "active_latest": {"approval_id": "approval-execute-1"},
        },
    )
    assert apply_action["id"] == "apply_persistent_supervision_enablement"
    assert apply_action["active_approval_id"] == "approval-execute-1"
    assert apply_action["enablement_active_approval_id"] == "approval-enable-1"


def test_stage6_prerequisite_bringup_surface_execute_action_uses_active_authority_grant() -> None:
    from francis.lens.status import (
        _stage6_authority_state,
        _stage6_next_prerequisite_action,
        _stage6_prerequisite_operator_command,
        _stage6_surface_prerequisite_actions,
    )

    readback = {
        "authority_granted": True,
        "active_authority_grant": {
            "approval_id": "approval-hotkey-1",
            "receipt_id": "grant-hotkey-1",
        },
        "request_route": "/lens/os-binding/authority/request",
        "authority_route": "/lens/os-binding/authority",
        "execute_route": "/lens/os-binding/execute",
        "action": "lens.os_binding.command_palette_binding_authority",
    }
    actions = _stage6_surface_prerequisite_actions("global_hotkey_binding", readback)
    action = _stage6_next_prerequisite_action(
        "global_hotkey_binding",
        actions=actions,
        status_readbacks={"os_binding_authority_requests": readback},
    )

    assert action["id"] == "execute_global_hotkey_binding"
    assert action["active_approval_id"] == "approval-hotkey-1"
    assert _stage6_authority_state(readback)["active_grant_receipt_id"] == "grant-hotkey-1"
    assert _stage6_authority_state(readback)["active_approval_id"] == "approval-hotkey-1"
    assert _stage6_prerequisite_operator_command(action)["command"] == (
        ".\\scripts\\lens-stage6-prerequisite-bringup-plan.ps1 "
        "-Mode ExecuteNext -Actor <actor> -ApprovalId approval-hotkey-1 -RunSeconds 2 -ConfirmExecute"
    )


def test_stage6_prerequisite_bringup_labels_enablement_requirement_when_prerequisites_ready() -> None:
    from francis.lens.status import _stage6_prerequisite_bringup_readback

    required = [
        "resident_host_process",
        "tray_presence",
        "global_hotkey_binding",
        "overlay_window",
        "summon_binding",
    ]
    dependencies = [
        {
            "id": requirement,
            "family": requirement,
            "route": f"/lens/test/{requirement}",
            "readiness_route": f"/lens/test/{requirement}/readiness",
            "ready": True,
            "requirement_state": "ready",
            "blocker": "",
            "blocked_reason": "",
        }
        for requirement in required
    ]

    payload = _stage6_prerequisite_bringup_readback(
        closure_readback={
            "ready_to_close": False,
            "next_smallest_truthful_gap": "persistent_supervision_required_prerequisites_missing",
        },
        resident_host={
            "persistent_supervision_plan": {
                "next_smallest_truthful_gap": "persistent_supervision_authority_not_granted",
                "required_before_enable": required,
                "missing_required_before_enable": [],
                "required_before_enable_ready": True,
                "first_missing_required_before_enable": "",
                "enablement_dependency_readback": dependencies,
            },
            "persistent_supervision_enablement": {},
            "resident_runtime_authority_requests": {},
            "resident_runtime_authority_grant_receipts": {},
            "supervision_authority_requests": {},
            "supervision_authority_grant_receipts": {},
            "persistent_supervision_enablement_authority_requests": {},
            "persistent_supervision_enablement_authority_grants": {},
            "persistent_supervision_enablement_execution_requests": {},
            "persistent_supervision_enablement_execution_authority_grants": {},
        },
        os_binding_authority_requests={},
        tray_authority_requests={},
        overlay_authority_requests={},
        summon_authority_requests={},
    )

    assert payload["status"] == "ready"
    assert payload["current_truthful_gap"] == "persistent_supervision_authority_not_granted"
    assert payload["current_truthful_gap_basis"] == "persistent_supervision_plan.next_smallest_truthful_gap"
    assert payload["current_first_missing_requirement"] == ""
    assert payload["missing_required_before_enable"] == []
    assert payload["required_before_enable_ready"] is True
    assert payload["next_operator_action_requirement"] == "persistent_supervision_enablement"
    assert payload["next_operator_action"]["id"] == "request_persistent_supervision_enablement_authority"
    assert payload["next_operator_action"]["route"] == (
        "/lens/host/persistent-supervision/enablement/authority/request"
    )
    assert payload["next_operator_command"]["mode"] == "RequestNext"
    assert payload["operator_sequence"][0]["id"] == "request_persistent_supervision_enablement_authority"
    assert payload["operator_sequence"][0]["operator_command"]["available_now"] is True
    assert payload["operator_sequence_command_availability"] == {
        "available_now_count": 1,
        "preview_only_count": 0,
        "sequence_length": 1,
        "truthful": True,
    }
    assert all(item["ready"] is True for item in payload["ordered_prerequisite_steps"])


def test_lens_persistent_supervision_enablement_blocks_until_required_surfaces_exist(
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
    service_config_path = repo_root / "config" / "runtime" / "services" / "lens-host.json"
    service_config = json.loads(service_config_path.read_text(encoding="utf-8"))
    service_config["process_supervision_enabled"] = True
    service_config["persistent_supervision_enabled"] = True
    service_config_path.write_text(json.dumps(service_config, indent=2), encoding="utf-8")
    monkeypatch.setenv("FRANCIS_ROOT", str(repo_root))
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_ENV_PROFILE", "dev")
    monkeypatch.setenv("FRANCIS_RUN_MODE", "api")

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())
    host_request = client.post(
        "/lens/host/supervision/authority/request",
        json={
            "actor": "test.system.write",
            "reason": "operator wants host supervision authority reviewed before persistent enablement",
        },
    )
    assert host_request.status_code == 200
    host_approval_id = str(host_request.json()["approval_id"])
    host_decision = client.post(
        "/approvals/decision",
        json={
            "id": host_approval_id,
            "action": "approve",
            "actor": "test.approvals.decision",
            "comment": "approved only to prove required surfaces still gate persistent supervision",
        },
    )
    assert host_decision.status_code == 200
    assert host_decision.json()["status"] == "approved"
    host_grant = client.post(
        "/lens/host/supervision/authority",
        json={
            "approval_id": host_approval_id,
            "actor": "test.system.write",
            "reason": "grant host supervision authority without resident surfaces",
        },
    )
    assert host_grant.status_code == 200
    assert host_grant.json()["status"] == "authority_granted"

    expected_enablement_prerequisites = [
        "resident_host_process",
        "tray_presence",
        "global_hotkey_binding",
        "overlay_window",
        "summon_binding",
    ]
    persistent_plan = client.get("/lens/host/persistent-supervision")
    assert persistent_plan.status_code == 200
    persistent_body = persistent_plan.json()
    assert persistent_body["status"] == "blocked"
    assert persistent_body["ready"] is False
    assert persistent_body["persistent_supervision_ready"] is False
    assert persistent_body["required_before_enable_ready"] is False
    assert persistent_body["required_before_enable"] == expected_enablement_prerequisites
    assert persistent_body["missing_required_before_enable"] == expected_enablement_prerequisites
    assert persistent_body["requirements_total"] == 11
    assert persistent_body["requirements_ready_total"] == 10
    assert persistent_body["requirements_blocked_total"] == 1
    assert persistent_body["blocked_requirements"] == ["required_before_enable"]
    assert persistent_body["blockers"] == ["persistent_supervision_required_prerequisites_missing"]
    assert persistent_body["next_smallest_truthful_gap"] == "persistent_supervision_required_prerequisites_missing"
    requirements = {item["id"]: item for item in persistent_body["requirements"]}
    assert requirements["process_supervision_enabled"]["ready"] is True
    assert requirements["persistent_supervision_enabled"]["ready"] is True
    assert requirements["process_restart_authority"]["ready"] is True
    assert requirements["service_install_authority"]["ready"] is True
    assert requirements["service_control_authority"]["ready"] is True
    assert requirements["receipt_write_authority"]["ready"] is True
    assert requirements["resident_claim_authority"]["ready"] is True
    assert requirements["required_before_enable"]["ready"] is False
    assert requirements["required_before_enable"]["missing_required_before_enable"] == (
        expected_enablement_prerequisites
    )

    enablement = client.get("/lens/host/persistent-supervision/enablement")
    assert enablement.status_code == 200
    enablement_body = enablement.json()
    assert enablement_body["status"] == "blocked"
    assert enablement_body["ready"] is False
    assert enablement_body["enablement_ready"] is False
    assert enablement_body["required_before_enable_ready"] is False
    assert enablement_body["authority_grant_active"] is True
    assert enablement_body["process_supervision_enabled"] is True
    assert enablement_body["persistent_supervision_enabled"] is True
    assert enablement_body["requirements_total"] == 5
    assert enablement_body["requirements_ready_total"] == 4
    assert enablement_body["requirements_blocked_total"] == 1
    assert enablement_body["blocked_requirements"] == ["required_before_enable"]
    assert enablement_body["blockers"] == ["persistent_supervision_required_prerequisites_missing"]
    assert enablement_body["next_smallest_truthful_gap"] == "persistent_supervision_required_prerequisites_missing"
    enablement_requirements = {item["id"]: item for item in enablement_body["requirements"]}
    assert enablement_requirements["active_host_supervision_authority_grant"]["ready"] is True
    assert enablement_requirements["process_supervision_enabled"]["ready"] is True
    assert enablement_requirements["persistent_supervision_enabled"]["ready"] is True
    assert enablement_requirements["required_before_enable"]["ready"] is False
    assert enablement_requirements["required_before_enable"]["missing_required_before_enable"] == (
        expected_enablement_prerequisites
    )
    assert not (data_root / "runtime" / "lens-host-supervisor" / "status.json").exists()
    assert not (data_root / "runtime" / "lens-host" / "status.json").exists()
    assert not (data_root / "runtime" / "lens-host" / "lens-host.pid").exists()


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
    assert pending_readiness_body["operator_surface_readback_ready"] is True
    assert pending_readiness_body["first_blocked_requirement"] == (
        "exact_persistent_supervision_enablement_authority_approval"
    )
    assert (
        pending_readiness_body["next_smallest_truthful_gap"]
        == "persistent_supervision_enablement_authority_exact_approval_request"
    )
    pending_handoff = pending_readiness_body["first_blocked_requirement_handoff"]
    assert pending_handoff["request_route"] == "/lens/host/persistent-supervision/enablement/authority/request"
    assert pending_handoff["approval_action"] == "lens.host.persistent_supervision_enablement_authority"

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
    assert approved_readiness_body["first_blocked_requirement"] == "active_host_supervision_authority_grant"
    approved_handoff = approved_readiness_body["first_blocked_requirement_handoff"]
    assert approved_handoff["host_supervision_authority_readiness_route"] == (
        "/lens/host/supervision/authority/readiness"
    )
    assert approved_readiness_body["next_smallest_truthful_gap"] == (
        "grant_active_host_supervision_authority_before_persistent_supervision_enablement_authority"
    )
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
    assert criterion["operator_surface_readback_ready"] is True
    assert criterion["request_pending_count"] == 0
    assert criterion["request_approved_count"] == 1
    assert criterion["request_total_count"] == 1
    assert criterion["latest_request_approval_id"] == approval_id
    assert criterion["first_blocked_requirement"] == "exact_persistent_supervision_enablement_authority_approval"
    assert criterion["first_blocked_requirement_handoff"]["request_route"] == (
        "/lens/host/persistent-supervision/enablement/authority/request"
    )
    assert criterion["next_smallest_truthful_gap"] == (
        "persistent_supervision_enablement_authority_exact_approval_request"
    )
    next_handoff = status_body["stage6_readiness"]["next_handoff"]
    assert next_handoff["next_smallest_truthful_gap"] == "resident_host_process_not_supervised"
    assert next_handoff["persistent_supervision_enablement_authority_handoff_observed"] is False
    assert next_handoff["persistent_supervision_enablement_authority_handoff"] == {}
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
    assert readiness_body["operator_surface_readback_ready"] is True
    assert readiness_body["first_blocked_requirement"] == "service_config_write_authority"
    assert readiness_body["first_blocked_requirement_handoff"]["execution_readiness_route"] == (
        "/lens/host/persistent-supervision/enablement/execution/readiness"
    )
    assert readiness_body["next_smallest_truthful_gap"] == (
        "grant_persistent_supervision_execution_authority_before_service_config_write"
    )
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
    assert criterion["request_pending_count"] == 0
    assert criterion["request_approved_count"] == 1
    assert criterion["request_total_count"] == 1
    assert criterion["latest_request_approval_id"] == approval_id
    assert criterion["first_blocked_requirement"] == "exact_persistent_supervision_enablement_authority_approval"
    assert criterion["first_blocked_requirement_handoff"]["request_route"] == (
        "/lens/host/persistent-supervision/enablement/authority/request"
    )
    assert criterion["next_smallest_truthful_gap"] == (
        "persistent_supervision_enablement_authority_exact_approval_request"
    )
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
    assert pending_readiness_body["operator_surface_readback_ready"] is True
    assert pending_readiness_body["first_blocked_requirement"] == (
        "exact_persistent_supervision_enablement_execution_approval"
    )
    assert pending_readiness_body["next_smallest_truthful_gap"] == (
        "persistent_supervision_enablement_execution_exact_approval_request"
    )
    pending_execution_handoff = pending_readiness_body["first_blocked_requirement_handoff"]
    assert pending_execution_handoff["request_route"] == (
        "/lens/host/persistent-supervision/enablement/execution/request"
    )
    assert pending_execution_handoff["approval_action"] == (
        "lens.host.persistent_supervision_enablement_execution_authority"
    )

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
    assert approved_readiness_body["first_blocked_requirement"] == "service_config_write_authority"
    assert approved_readiness_body["first_blocked_requirement_handoff"]["grant_route"] == (
        "/lens/host/persistent-supervision/enablement/execution/authority"
    )
    assert approved_readiness_body["next_smallest_truthful_gap"] == (
        "grant_exact_approved_persistent_supervision_execution_authority_request"
    )

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
    assert granted_readiness_body["first_blocked_requirement"] == "resident_claim_authority"
    assert granted_readiness_body["first_blocked_requirement_handoff"]["execution_apply_route"] == (
        "/lens/host/persistent-supervision/enablement/execution/apply"
    )
    assert granted_readiness_body["next_smallest_truthful_gap"] == (
        "review_resident_claim_boundary_before_persistent_supervision_claim"
    )

    granted_denial = client.post(
        "/lens/host/persistent-supervision/enablement/execution",
        json={
            "approval_id": approval_id,
            "actor": "test.system.write",
            "reason": "prove execution boundary remains read-only after explicit authority",
        },
    )
    assert granted_denial.status_code == 200
    granted_denial_body = granted_denial.json()
    assert granted_denial_body["kind"] == "lens.host.persistent_supervision_enablement_execution.denial"
    assert granted_denial_body["status"] == "denied_no_resident_claim_authority"
    assert granted_denial_body["route"] == "/lens/host/persistent-supervision/enablement/execution"
    assert granted_denial_body["apply_route"] == "/lens/host/persistent-supervision/enablement/execution/apply"
    assert granted_denial_body["authority_granted"] is True
    assert granted_denial_body["service_config_write_authority"] is True
    assert granted_denial_body["persistent_supervision_execution_authority"] is True
    assert granted_denial_body["applied"] is False
    assert granted_denial_body["executed"] is False
    assert granted_denial_body["service_config_updated"] is False
    assert granted_denial_body["denial"]["would_update_service_config"] is False
    assert granted_denial_body["denial"]["would_write_receipt"] is False
    assert not (data_root / "lens" / "pse_executions").exists()
    denied_service_config = json.loads(
        (repo_root / "config" / "runtime" / "services" / "lens-host.json").read_text(encoding="utf-8")
    )
    assert denied_service_config["process_supervision_enabled"] is False
    assert denied_service_config["persistent_supervision_enabled"] is False

    execution = client.post(
        "/lens/host/persistent-supervision/enablement/execution/apply",
        json={
            "approval_id": approval_id,
            "actor": "test.system.write",
            "reason": "apply bounded persistent supervision service config after explicit authority",
        },
    )
    assert execution.status_code == 200
    execution_body = execution.json()
    assert execution_body["kind"] == "lens.host.persistent_supervision_enablement_execution.execution"
    assert execution_body["status"] == "service_config_updated"
    assert execution_body["route"] == "/lens/host/persistent-supervision/enablement/execution/apply"
    assert execution_body["denial_route"] == "/lens/host/persistent-supervision/enablement/execution"
    assert execution_body["apply_route"] == "/lens/host/persistent-supervision/enablement/execution/apply"
    assert execution_body["authority_granted"] is True
    assert execution_body["active_execution_authority_grant_receipt_id"] == execution_receipt_id
    assert execution_body["service_config_write_authority"] is True
    assert execution_body["persistent_supervision_execution_authority"] is True
    assert execution_body["receipt_write_authority"] is True
    assert execution_body["applied"] is True
    assert execution_body["executed"] is True
    assert execution_body["service_config_updated"] is True
    assert execution_body["persistent_supervision_enablement_allowed"] is True
    assert execution_body["persistent_supervision_ready"] is False
    assert execution_body["resident_claim_allowed"] is False
    assert execution_body["receipt_written"] is True
    assert "service_config_write_authority_not_granted" not in execution_body["blockers"]
    assert "persistent_supervision_execution_authority_not_granted" not in execution_body["blockers"]
    assert "receipt_write_authority_not_granted" not in execution_body["blockers"]
    assert "resident_claim_authority_not_granted" in execution_body["blockers"]
    assert "persistent_supervision_required_prerequisites_missing" in execution_body["blockers"]
    assert execution_body["service_config"]["updated"] is True
    assert "process_supervision_enabled" in execution_body["service_config"]["changed_fields"]
    assert "persistent_supervision_enabled" in execution_body["service_config"]["changed_fields"]
    assert execution_body["governance"]["execution_authority"] is False
    assert execution_body["governance"]["service_config_write_authority"] is True
    assert execution_body["governance"]["persistent_supervision_execution_authority"] is True
    assert execution_body["governance"]["service_config_mutation_authority"] is True
    assert execution_body["governance"]["mutation_authority_granted"] is True
    assert execution_body["governance"]["service_install_authority"] is False
    assert execution_body["governance"]["service_control_authority"] is False
    assert execution_body["governance"]["local_process_launch_authority"] is False
    assert execution_body["governance"]["memory_write"] is False
    assert execution_body["governance"]["resident_claim_authority"] is False
    execution_service_config = json.loads(
        (repo_root / "config" / "runtime" / "services" / "lens-host.json").read_text(encoding="utf-8")
    )
    assert execution_service_config["process_supervision_enabled"] is True
    assert execution_service_config["persistent_supervision_enabled"] is True
    assert execution_service_config["supervision_ready"] is False
    assert execution_service_config["supervision_blocked_reason"] == "resident_supervision_prerequisites_pending"
    assert execution_service_config["blocked_reason"] == "lens_host_persistent_supervision_prerequisites_pending"
    assert execution_service_config["installable"] is False
    assert execution_service_config["service_control_authority"] is False
    assert execution_service_config["resident_claim_authority"] is False
    execution_receipt = execution_body["receipt"]
    service_config_execution_receipt_id = execution_receipt["receipt_id"]
    assert execution_receipt["kind"] == "lens.host.persistent_supervision_enablement_execution.receipt"
    assert execution_receipt["approval_id"] == approval_id
    assert execution_receipt["service_config"]["updated"] is True
    assert execution_receipt["result"]["service_config_updated"] is True
    assert execution_receipt["result"]["persistent_supervision_enablement_allowed"] is True
    assert execution_receipt["result"]["resident_claim_allowed"] is False
    assert execution_receipt["governance"]["service_config_write_authority"] is True
    assert execution_receipt["governance"]["persistent_supervision_execution_authority"] is True
    assert execution_receipt["governance"]["service_config_mutation_authority"] is True
    assert execution_receipt["governance"]["memory_write"] is False
    assert execution_receipt["governance"]["resident_claim_authority"] is False

    executions = client.get(
        f"/lens/host/persistent-supervision/enablement/executions?limit=10&approval_id={approval_id}"
    )
    assert executions.status_code == 200
    executions_body = executions.json()
    assert executions_body["kind"] == "lens.host.persistent_supervision_enablement_execution.receipts"
    assert executions_body["total"] == 1
    assert executions_body["latest"]["receipt_id"] == service_config_execution_receipt_id
    assert executions_body["service_config_updated"] is True
    assert executions_body["persistent_supervision_enablement_allowed"] is True
    assert executions_body["persistent_supervision_ready"] is False
    assert executions_body["resident_claim_allowed"] is False

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
    assert resident_host["persistent_supervision_enablement_execution_apply_route"] == (
        "/lens/host/persistent-supervision/enablement/execution/apply"
    )
    assert resident_host["persistent_supervision_enablement_execution_receipts_route"] == (
        "/lens/host/persistent-supervision/enablement/executions"
    )
    assert resident_host["persistent_supervision_enablement_execution_receipts"]["total"] == 1
    assert resident_host["persistent_supervision_enablement_execution_receipts"]["latest"]["receipt_id"] == (
        service_config_execution_receipt_id
    )
    assert resident_host["persistent_supervision_enablement_execution_receipts"]["service_config_updated"] is True
    assert (
        resident_host["persistent_supervision_enablement_execution_receipts"][
            "persistent_supervision_enablement_allowed"
        ]
        is True
    )
    assert resident_host["persistent_supervision_enablement_execution_receipts"]["resident_claim_allowed"] is False
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
    assert criterion["service_config_updated"] is True
    assert criterion["service_config_write_authority"] is True
    assert criterion["persistent_supervision_execution_authority"] is True
    assert criterion["operator_surface_readback_ready"] is True
    assert criterion["request_pending_count"] == 0
    assert criterion["request_approved_count"] == 1
    assert criterion["request_total_count"] == 1
    assert criterion["latest_request_approval_id"] == approval_id
    assert criterion["first_blocked_requirement"] == "exact_persistent_supervision_enablement_execution_approval"
    assert criterion["first_blocked_requirement_handoff"]["request_route"] == (
        "/lens/host/persistent-supervision/enablement/execution/request"
    )
    assert criterion["next_smallest_truthful_gap"] == (
        "persistent_supervision_enablement_execution_exact_approval_request"
    )
    resident_claim_handoff = next(
        item for item in criterion["blocked_requirement_handoffs"] if item["id"] == "resident_claim_authority"
    )
    assert resident_claim_handoff["execution_apply_route"] == (
        "/lens/host/persistent-supervision/enablement/execution/apply"
    )
    execution_receipt_criterion = _criterion(
        status_body,
        "persistent_supervision_enablement_execution_receipt_readback",
    )
    assert execution_receipt_criterion["receipt_count"] == 1
    assert execution_receipt_criterion["latest_receipt_id"] == service_config_execution_receipt_id
    assert execution_receipt_criterion["service_config_updated"] is True
    assert execution_receipt_criterion["persistent_supervision_enablement_allowed"] is True
    assert execution_receipt_criterion["persistent_supervision_ready"] is False
    assert execution_receipt_criterion["resident_claim_allowed"] is False
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


def test_lens_host_runtime_boundary_distinguishes_diagnostic_runner_from_resident_runtime(
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
    response = client.get("/lens/host/runtime-boundary")

    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "lens.host.runtime_boundary"
    assert body["status"] == "blocked"
    assert body["route"] == "/lens/host/runtime-boundary"
    assert body["host_route"] == "/lens/host"
    assert body["manifest_route"] == "/lens/host/manifest"
    assert body["ready"] is False
    assert body["runtime_ready"] is False
    assert body["resident_runtime"] is False
    assert body["diagnostic_status_runner_ready"] is True
    assert body["bounded_foreground_session_available"] is True
    assert body["bounded_launch_available"] is True
    assert body["resident_runtime_candidate_available"] is True
    assert body["runtime_state_write_configured"] is True
    assert body["foreground_process_observed"] is False
    assert body["resident_host_process_state"] == "missing"
    assert body["resident_host_process_blocker"] == "resident_host_process_missing"
    assert body["runtime_blockers"] == ["lens_host_runtime_not_implemented"]
    assert body["surface_dependency_blockers"] == [
        "tray_host_missing",
        "global_hotkey_binding_missing",
        "overlay_window_missing",
        "summon_binding_missing",
    ]
    assert body["blockers"] == [
        "lens_host_runtime_not_implemented",
        "resident_host_process_missing",
    ]
    assert body["blocker_groups"]["runtime"] == ["lens_host_runtime_not_implemented"]
    assert body["blocker_groups"]["process_readback"] == ["resident_host_process_missing"]
    assert body["boundaries"]["diagnostic_status_runner"]["ready"] is True
    assert body["boundaries"]["diagnostic_status_runner"]["resident_runtime"] is False
    assert body["boundaries"]["bounded_foreground_session"]["ready"] is True
    assert body["boundaries"]["bounded_foreground_session"]["resident_runtime"] is False
    assert body["boundaries"]["resident_runtime_candidate"] == {
        "status": "available",
        "ready": True,
        "scope": "manual_process_runtime_candidate_only",
        "host_script": "scripts/lens-host.ps1 -Mode Resident",
        "resident_runtime": False,
        "service_managed": False,
        "process_supervision": False,
        "would_launch_from_api": False,
        "would_install_service": False,
        "authority_granted": False,
        "resident_claim_allowed": False,
    }
    assert body["boundaries"]["resident_runtime"] == {
        "status": "blocked",
        "ready": False,
        "resident": False,
        "service_managed": False,
        "process_supervision": False,
        "blockers": ["lens_host_runtime_not_implemented"],
    }
    assert body["governance"]["read_only_contract"] is True
    assert body["governance"]["execution_authority"] is False
    assert body["governance"]["local_process_launch_authority"] is False
    assert body["governance"]["diagnostic_launch_authority"] is False
    assert body["governance"]["process_supervision_authority"] is False
    assert body["governance"]["service_control_authority"] is False
    assert body["governance"]["resident_claim_authority"] is False
    assert body["next_smallest_truthful_gap"] == "resident_host_runtime_implementation_plan"

    manifest = client.get("/lens/host/manifest")
    assert manifest.status_code == 200
    assert manifest.json()["runtime_boundary_route"] == "/lens/host/runtime-boundary"


def test_lens_host_runtime_implementation_plan_stays_readback_only(
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
    response = client.get("/lens/host/runtime-plan")

    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "lens.host.runtime_implementation_plan"
    assert body["status"] == "blocked"
    assert body["route"] == "/lens/host/runtime-plan"
    assert body["manifest_route"] == "/lens/host/manifest"
    assert body["runtime_boundary_route"] == "/lens/host/runtime-boundary"
    assert body["plan_available"] is True
    assert body["implementation_ready"] is False
    assert body["execution_ready"] is False
    assert body["resident_runtime_ready"] is False
    assert body["resident_claim_allowed"] is False
    assert body["foreground_process_observed"] is False
    assert body["resident_host_process_state"] == "missing"
    assert body["resident_host_process_blocker"] == "resident_host_process_missing"
    assert body["requirements_total"] == 11
    assert body["requirements_ready_total"] == 4
    assert body["blocked_requirements"] == [
        "resident_runtime_loop_contract",
        "process_supervision_contract",
        "service_management_contract",
        "tray_presence_contract",
        "hotkey_summon_contract",
        "overlay_window_contract",
        "resident_claim_contract",
    ]
    assert body["blocker_groups"]["runtime"] == ["lens_host_runtime_not_implemented"]
    assert body["blocker_groups"]["process_readback"] == ["resident_host_process_missing"]
    assert body["blocker_groups"]["surface_dependencies"] == [
        "tray_host_missing",
        "global_hotkey_binding_missing",
        "overlay_window_missing",
        "summon_binding_missing",
    ]
    assert "resident_runtime_execution_authority_not_granted" in body["blocker_groups"]["authority"]
    assert "resident_host_process_missing" in body["blockers"]
    assert "process_supervision_authority_not_granted" in body["blockers"]
    assert "service_control_authority_not_granted" in body["blockers"]
    assert "hotkey_registration_authority_not_granted" in body["blockers"]
    assert "resident_claim_authority_not_granted" in body["blockers"]

    plan = body["plan"]
    assert plan["would_launch_process"] is False
    assert plan["would_supervise_process"] is False
    assert plan["would_restart_process"] is False
    assert plan["would_install_service"] is False
    assert plan["would_start_service"] is False
    assert plan["would_register_tray"] is False
    assert plan["would_register_hotkey"] is False
    assert plan["would_open_overlay"] is False
    assert plan["would_claim_resident"] is False
    assert plan["would_write_memory"] is False
    assert plan["would_write_receipt"] is False
    assert plan["would_decide_approval"] is False
    plan_steps = {step["id"]: step for step in plan["steps"]}
    assert plan_steps["host_entrypoint_contract"]["status"] == "ready"
    assert plan_steps["diagnostic_status_boundary"]["status"] == "ready"
    assert plan_steps["bounded_foreground_session_boundary"]["status"] == "ready"
    assert plan_steps["runtime_state_readback_contract"]["status"] == "ready"
    assert plan_steps["resident_runtime_loop_contract"]["status"] == "blocked"
    assert plan_steps["resident_runtime_loop_contract"]["route"] == "/lens/host/runtime-loop"
    assert plan_steps["resident_runtime_loop_contract"]["authority_granted"] is False
    assert plan_steps["process_supervision_contract"]["status"] == "blocked"
    assert plan_steps["process_supervision_contract"]["authority_granted"] is False
    assert "resident_host_process_missing" in plan_steps["process_supervision_contract"]["blockers"]
    assert plan_steps["service_management_contract"]["status"] == "blocked"
    assert plan_steps["service_management_contract"]["authority_granted"] is False
    assert plan_steps["tray_presence_contract"]["status"] == "blocked"
    assert plan_steps["hotkey_summon_contract"]["status"] == "blocked"
    assert plan_steps["overlay_window_contract"]["status"] == "blocked"
    assert plan_steps["resident_claim_contract"]["status"] == "blocked"

    runtime_boundary = body["runtime_boundary"]
    assert runtime_boundary["kind"] == "lens.host.runtime_boundary"
    assert runtime_boundary["resident_runtime"] is False
    assert runtime_boundary["process_supervision"] is False
    assert runtime_boundary["governance"]["execution_authority"] is False
    assert runtime_boundary["governance"]["resident_claim_authority"] is False

    governance = body["governance"]
    assert governance["gate"] == "lens_host_runtime_implementation_plan"
    assert governance["read_only_contract"] is True
    assert governance["plan_readback_only"] is True
    for key in [
        "execution_authority",
        "resident_runtime_execution_authority",
        "approval_decision_authority",
        "memory_write",
        "local_process_launch_authority",
        "diagnostic_launch_authority",
        "process_supervision_authority",
        "process_restart_authority",
        "service_install_authority",
        "service_control_authority",
        "receipt_write_authority",
        "resident_claim_authority",
        "overlay_control_authority",
        "summon_authority",
        "hotkey_registration_authority",
        "tray_registration_authority",
        "mutation_authority_granted",
    ]:
        assert governance[key] is False
    assert body["next_smallest_truthful_gap"] == "resident_host_runtime_loop_readiness_audit"
    assert "/lens/host/runtime-loop" in body["evidence"]
    assert "/lens/host/runtime-loop/denials" in body["evidence"]
    assert not (data_root / "runtime" / "lens-host" / "status.json").exists()
    assert not (data_root / "runtime" / "lens-host" / "lens-host.pid").exists()


def test_lens_host_runtime_loop_contract_stays_readback_only(
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
    response = client.get("/lens/host/runtime-loop")

    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "lens.host.runtime_loop_contract"
    assert body["status"] == "blocked"
    assert body["route"] == "/lens/host/runtime-loop"
    assert body["runtime_plan_route"] == "/lens/host/runtime-plan"
    assert body["runtime_boundary_route"] == "/lens/host/runtime-boundary"
    assert body["supervision_route"] == "/lens/host/supervision"
    assert body["resident_runtime_execute_route"] == "/lens/resident-runtime/execute"
    assert body["execution_denial_route"] == "/lens/host/runtime-loop/execute"
    assert body["denial_receipts_route"] == "/lens/host/runtime-loop/denials"
    assert body["contract_available"] is True
    assert body["loop_readback_ready"] is True
    assert body["loop_ready"] is False
    assert body["execution_ready"] is False
    assert body["resident_runtime_loop"] is False
    assert body["resident_runtime_ready"] is False
    assert body["resident_claim_allowed"] is False
    assert body["foreground_process_observed"] is False
    assert body["foreground_session_available"] is True
    assert body["resident_host_process_state"] == "missing"
    assert body["resident_host_process_blocker"] == "resident_host_process_missing"
    assert body["requirements_total"] == 8
    assert body["requirements_ready_total"] == 3
    assert body["blocked_requirements"] == [
        "resident_loop_process_supervision",
        "resident_loop_service_lifecycle",
        "resident_loop_surface_presence",
        "resident_loop_receipt_emission",
        "resident_loop_claim_checkpoint",
    ]
    assert body["blocker_groups"]["runtime"] == ["lens_host_runtime_not_implemented"]
    assert body["blocker_groups"]["process_readback"] == ["resident_host_process_missing"]
    assert body["blocker_groups"]["surface_dependencies"] == [
        "tray_host_missing",
        "global_hotkey_binding_missing",
        "overlay_window_missing",
        "summon_binding_missing",
    ]
    assert "resident_runtime_loop_not_implemented" in body["blocker_groups"]["loop"]
    assert "resident_runtime_execution_authority_not_granted" in body["blocker_groups"]["authority"]
    assert "resident_host_process_missing" in body["blockers"]
    assert "resident_runtime_loop_not_supervised" in body["blockers"]
    assert "receipt_write_authority_not_granted" in body["blockers"]

    loop_contract = body["loop_contract"]
    assert loop_contract["readback_ready"] is True
    assert loop_contract["would_start_loop"] is False
    assert loop_contract["would_launch_process"] is False
    assert loop_contract["would_supervise_process"] is False
    assert loop_contract["would_restart_process"] is False
    assert loop_contract["would_install_service"] is False
    assert loop_contract["would_start_service"] is False
    assert loop_contract["would_register_tray"] is False
    assert loop_contract["would_register_hotkey"] is False
    assert loop_contract["would_open_overlay"] is False
    assert loop_contract["would_claim_resident"] is False
    assert loop_contract["would_write_receipt"] is False
    assert loop_contract["would_write_memory"] is False
    assert loop_contract["would_decide_approval"] is False
    requirements = {item["id"]: item for item in loop_contract["requirements"]}
    assert requirements["diagnostic_status_tick"]["status"] == "ready"
    assert requirements["bounded_foreground_tick"]["status"] == "ready"
    assert requirements["runtime_state_heartbeat_readback"]["status"] == "ready"
    assert requirements["resident_loop_process_supervision"]["status"] == "blocked"
    assert requirements["resident_loop_process_supervision"]["authority_granted"] is False
    assert "resident_host_process_missing" in requirements["resident_loop_process_supervision"]["blockers"]
    assert requirements["resident_loop_service_lifecycle"]["status"] == "blocked"
    assert requirements["resident_loop_surface_presence"]["status"] == "blocked"
    assert requirements["resident_loop_receipt_emission"]["status"] == "blocked"
    assert requirements["resident_loop_claim_checkpoint"]["status"] == "blocked"

    runtime_plan = body["runtime_plan"]
    assert runtime_plan["kind"] == "lens.host.runtime_implementation_plan"
    assert runtime_plan["plan"]["would_launch_process"] is False
    assert runtime_plan["plan"]["would_supervise_process"] is False
    assert runtime_plan["governance"]["execution_authority"] is False

    governance = body["governance"]
    assert governance["gate"] == "lens_host_runtime_loop_contract"
    assert governance["read_only_contract"] is True
    assert governance["loop_contract_readback_only"] is True
    for key in [
        "execution_authority",
        "resident_runtime_execution_authority",
        "approval_decision_authority",
        "memory_write",
        "local_process_launch_authority",
        "diagnostic_launch_authority",
        "process_supervision_authority",
        "process_restart_authority",
        "service_install_authority",
        "service_control_authority",
        "receipt_write_authority",
        "resident_claim_authority",
        "overlay_control_authority",
        "summon_authority",
        "hotkey_registration_authority",
        "tray_registration_authority",
        "mutation_authority_granted",
    ]:
        assert governance[key] is False
    assert body["next_smallest_truthful_gap"] == "resident_host_runtime_loop_readiness_audit"
    assert "/lens/host/runtime-loop/denials" in body["evidence"]

    status_response = client.get("/lens/status?limit=1")
    assert status_response.status_code == 200
    resident_host = status_response.json()["resident_host"]
    assert resident_host["runtime_implementation_plan_route"] == "/lens/host/runtime-plan"
    assert resident_host["runtime_loop_contract_route"] == "/lens/host/runtime-loop"
    assert resident_host["runtime_loop_contract"]["kind"] == "lens.host.runtime_loop_contract"
    assert resident_host["runtime_loop_contract"]["loop_ready"] is False
    assert resident_host["runtime_loop_execution_denial_route"] == "/lens/host/runtime-loop/execute"
    runtime_loop_denial = resident_host["runtime_loop_execution_denial"]
    assert runtime_loop_denial["kind"] == "lens.host.runtime_loop.execution_denial"
    assert runtime_loop_denial["status"] == "denied_no_approval"
    assert runtime_loop_denial["applied"] is False
    assert runtime_loop_denial["executed"] is False
    assert runtime_loop_denial["loop_started"] is False
    assert runtime_loop_denial["receipt_written"] is False
    assert runtime_loop_denial["denial"]["would_start_loop"] is False
    assert runtime_loop_denial["denial"]["would_write_receipt"] is False
    assert runtime_loop_denial["receipt_route"] == "/lens/host/runtime-loop/denials"
    assert runtime_loop_denial["governance"]["gate"] == "lens_host_runtime_loop_execution_denial_boundary"
    assert runtime_loop_denial["governance"]["execution_authority"] is False
    assert runtime_loop_denial["governance"]["receipt_write_authority"] is False
    assert runtime_loop_denial["governance"]["denial_receipt_write_authority"] is False
    assert resident_host["runtime_loop_denial_receipts_route"] == "/lens/host/runtime-loop/denials"
    runtime_loop_denial_receipts = resident_host["runtime_loop_denial_receipts"]
    assert runtime_loop_denial_receipts["kind"] == "lens.host.runtime_loop.denial_receipts"
    assert runtime_loop_denial_receipts["status"] == "empty"
    assert runtime_loop_denial_receipts["route"] == "/lens/host/runtime-loop/denials"
    assert runtime_loop_denial_receipts["execute_route"] == "/lens/host/runtime-loop/execute"
    assert runtime_loop_denial_receipts["runtime_loop_route"] == "/lens/host/runtime-loop"
    assert runtime_loop_denial_receipts["total"] == 0
    assert runtime_loop_denial_receipts["latest"] is None
    assert runtime_loop_denial_receipts["items"] == []
    assert runtime_loop_denial_receipts["governance"]["gate"] == ("lens_host_runtime_loop_denial_receipts_readback")
    assert runtime_loop_denial_receipts["governance"]["read_only_contract"] is True
    assert runtime_loop_denial_receipts["governance"]["execution_authority"] is False
    assert runtime_loop_denial_receipts["governance"]["denial_receipt_write_authority"] is False
    assert runtime_loop_denial_receipts["governance"]["receipt_write_authority"] is False
    assert not (data_root / "runtime" / "lens-host" / "status.json").exists()
    assert not (data_root / "runtime" / "lens-host" / "lens-host.pid").exists()


def test_lens_host_runtime_loop_execution_denial_stays_non_mutating(
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
        "/lens/host/runtime-loop/execute",
        json={
            "actor": "test.system.write",
            "approval_id": "approval-runtime-loop",
            "reason": "prove the runtime loop execution boundary",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "lens.host.runtime_loop.execution_denial"
    assert body["status"] == "denied_no_resident_runtime_authority"
    assert body["route"] == "/lens/host/runtime-loop/execute"
    assert body["method"] == "POST"
    assert body["runtime_loop_route"] == "/lens/host/runtime-loop"
    assert body["runtime_plan_route"] == "/lens/host/runtime-plan"
    assert body["runtime_boundary_route"] == "/lens/host/runtime-boundary"
    assert body["approval_id"] == "approval-runtime-loop"
    assert body["actor"] == "test.system.write"
    assert body["reason"] == "prove the runtime loop execution boundary"
    assert body["applied"] is False
    assert body["executed"] is False
    assert body["loop_started"] is False
    assert body["resident_runtime_loop"] is False
    assert body["resident_runtime_ready"] is False
    assert body["resident_claim_allowed"] is False
    assert body["foreground_process_observed"] is False
    assert body["resident_host_process_state"] == "missing"
    assert body["resident_host_process_blocker"] == "resident_host_process_missing"
    assert "approval_id_required" not in body["blockers"]
    assert "resident_runtime_execution_authority_not_granted" in body["blockers"]
    assert "resident_runtime_loop_not_implemented" in body["blockers"]
    assert "resident_runtime_loop_not_supervised" in body["blockers"]
    assert "resident_runtime_loop_execution_not_authorized" in body["blockers"]
    assert "resident_runtime_loop_execution_boundary_not_implemented" in body["blockers"]
    assert "resident_host_process_missing" in body["blockers"]
    assert "receipt_write_authority_not_granted" in body["blockers"]

    denial = body["denial"]
    assert denial["reason"] == "denied_no_resident_runtime_authority"
    assert denial["next_step"] == "grant_resident_runtime_execution_authority_before_loop_start"
    assert denial["would_start_loop"] is False
    assert denial["would_launch_process"] is False
    assert denial["would_supervise_process"] is False
    assert denial["would_restart_process"] is False
    assert denial["would_install_service"] is False
    assert denial["would_start_service"] is False
    assert denial["would_register_tray"] is False
    assert denial["would_register_hotkey"] is False
    assert denial["would_open_overlay"] is False
    assert denial["would_claim_resident"] is False
    assert denial["would_write_receipt"] is False
    assert denial["would_write_memory"] is False
    assert denial["would_decide_approval"] is False
    assert denial["denial_receipt_written"] is True

    proof = body["proof"]
    assert proof["loop_readback_ready"] is True
    assert proof["loop_ready"] is False
    assert proof["execution_ready"] is False
    assert proof["resident_runtime_loop"] is False
    assert proof["resident_runtime_ready"] is False
    assert proof["resident_claim_allowed"] is False
    assert proof["requirements_total"] == 8
    assert "resident_loop_process_supervision" in proof["blocked_requirements"]
    assert body["runtime_loop_contract"]["kind"] == "lens.host.runtime_loop_contract"
    assert body["runtime_loop_contract"]["loop_contract"]["would_start_loop"] is False
    assert body["receipt_written"] is True
    assert body["receipt_route"] == "/lens/host/runtime-loop/denials"
    receipt = body["receipt"]
    assert receipt["kind"] == "lens.host.runtime_loop.denial.receipt"
    assert receipt["status"] == "denied_no_resident_runtime_authority"
    assert receipt["route"] == "/lens/host/runtime-loop/execute"
    assert receipt["source_kind"] == "lens.host.runtime_loop.execution_denial"
    assert receipt["approval_id"] == "approval-runtime-loop"
    assert receipt["actor"] == "test.system.write"
    assert receipt["execution"]["loop_started"] is False
    assert receipt["execution"]["would_start_loop"] is False
    assert receipt["execution"]["would_supervise_process"] is False
    assert receipt["execution"]["would_write_memory"] is False
    assert receipt["governance"]["gate"] == "lens_host_runtime_loop_denial_receipt"
    assert receipt["governance"]["denial_receipt_write_authority"] is True
    assert receipt["governance"]["execution_authority"] is False
    assert receipt["governance"]["resident_runtime_execution_authority"] is False
    assert receipt["governance"]["memory_write"] is False
    receipt_path = data_root / "lens" / "host_runtime_loop_denials" / f"{receipt['receipt_id']}.json"
    assert receipt_path.exists()

    governance = body["governance"]
    assert governance["gate"] == "lens_host_runtime_loop_execution_denial_boundary"
    assert governance["execution_boundary"] is True
    assert governance["denial_boundary"] is True
    assert governance["read_only_contract"] is True
    assert governance["denial_receipt_write_authority"] is True
    for key in [
        "execution_authority",
        "resident_runtime_execution_authority",
        "approval_decision_authority",
        "memory_write",
        "local_process_launch_authority",
        "diagnostic_launch_authority",
        "process_supervision_authority",
        "process_restart_authority",
        "service_install_authority",
        "service_control_authority",
        "receipt_write_authority",
        "resident_claim_authority",
        "overlay_control_authority",
        "summon_authority",
        "hotkey_registration_authority",
        "tray_registration_authority",
        "mutation_authority_granted",
    ]:
        assert governance[key] is False
    assert body["next_smallest_truthful_gap"] == "resident_host_runtime_loop_readiness_audit"

    denials_response = client.get(
        "/lens/host/runtime-loop/denials",
        params={"limit": 10, "approval_id": "approval-runtime-loop", "status": body["status"]},
    )
    assert denials_response.status_code == 200
    denials = denials_response.json()
    assert denials["kind"] == "lens.host.runtime_loop.denial_receipts"
    assert denials["status"] == "readback_ready"
    assert denials["route"] == "/lens/host/runtime-loop/denials"
    assert denials["execute_route"] == "/lens/host/runtime-loop/execute"
    assert denials["runtime_loop_route"] == "/lens/host/runtime-loop"
    assert denials["runtime_plan_route"] == "/lens/host/runtime-plan"
    assert denials["runtime_boundary_route"] == "/lens/host/runtime-boundary"
    assert denials["limit"] == 10
    assert denials["approval_id"] == "approval-runtime-loop"
    assert denials["filter_status"] == "denied_no_resident_runtime_authority"
    assert denials["total"] == 1
    assert denials["latest"]["receipt_id"] == receipt["receipt_id"]
    assert denials["items"] == [receipt]
    assert denials["receipt_readback_ready"] is True
    assert denials["denial_receipt_readback_ready"] is True
    assert denials["next_smallest_truthful_gap"] == "resident_host_runtime_loop_readiness_audit"
    assert denials["governance"]["gate"] == "lens_host_runtime_loop_denial_receipts_readback"
    assert denials["governance"]["read_only_contract"] is True
    for key in [
        "execution_authority",
        "resident_runtime_execution_authority",
        "approval_decision_authority",
        "memory_write",
        "local_process_launch_authority",
        "diagnostic_launch_authority",
        "process_supervision_authority",
        "process_restart_authority",
        "service_install_authority",
        "service_control_authority",
        "receipt_write_authority",
        "denial_receipt_write_authority",
        "resident_claim_authority",
        "overlay_control_authority",
        "summon_authority",
        "hotkey_registration_authority",
        "tray_registration_authority",
        "mutation_authority_granted",
    ]:
        assert denials["governance"][key] is False

    status_response = client.get("/lens/status?limit=1")
    assert status_response.status_code == 200
    status_body = status_response.json()
    resident_host = status_body["resident_host"]
    assert resident_host["runtime_loop_execution_denial_route"] == "/lens/host/runtime-loop/execute"
    assert resident_host["runtime_loop_execution_denial"]["kind"] == "lens.host.runtime_loop.execution_denial"
    assert resident_host["runtime_loop_execution_denial"]["loop_started"] is False
    assert resident_host["runtime_loop_execution_denial"]["governance"]["receipt_write_authority"] is False
    assert resident_host["runtime_loop_denial_receipts_route"] == "/lens/host/runtime-loop/denials"
    assert resident_host["runtime_loop_denial_receipts"]["kind"] == "lens.host.runtime_loop.denial_receipts"
    assert resident_host["runtime_loop_denial_receipts"]["status"] == "readback_ready"
    assert resident_host["runtime_loop_denial_receipts"]["total"] == 1
    assert resident_host["runtime_loop_denial_receipts"]["latest"]["receipt_id"] == receipt["receipt_id"]
    assert status_body["runtime_loop_denial_receipts"]["route"] == "/lens/host/runtime-loop/denials"
    assert status_body["runtime_loop_denial_receipts"]["latest"]["receipt_id"] == receipt["receipt_id"]
    assert status_body["receipts"]["lens_host_runtime_loop_denials_route"] == "/lens/host/runtime-loop/denials"
    criterion = _criterion(status_body, "resident_host_runtime_loop_denial_receipt_readback")
    assert criterion["status"] == "readback_ready"
    assert criterion["receipt_count"] == 1
    assert criterion["latest_receipt_id"] == receipt["receipt_id"]
    assert criterion["evidence"] == [
        "/lens/host/runtime-loop/denials",
        "/lens/host/runtime-loop/execute",
        "/lens/status",
    ]
    assert criterion["execution_authority"] is False
    assert criterion["resident_runtime_execution_authority"] is False
    assert criterion["approval_decision_authority"] is False
    assert criterion["memory_write"] is False
    assert criterion["receipt_write_authority"] is False
    assert criterion["denial_receipt_write_authority"] is False
    assert not (data_root / "runtime" / "lens-host" / "status.json").exists()
    assert not (data_root / "runtime" / "lens-host" / "lens-host.pid").exists()


def test_lens_host_runtime_loop_readiness_audit_stays_readback_only(
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
    response = client.get(
        "/lens/host/runtime-loop/readiness",
        params={"limit": 10, "approval_id": "approval-runtime-loop", "actor": "test.system.write"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "lens.host.runtime_loop.readiness_audit"
    assert body["status"] == "blocked"
    assert body["audit_status"] == "complete"
    assert body["route"] == "/lens/host/runtime-loop/readiness"
    assert body["runtime_plan_route"] == "/lens/host/runtime-plan"
    assert body["runtime_loop_route"] == "/lens/host/runtime-loop"
    assert body["execute_route"] == "/lens/host/runtime-loop/execute"
    assert body["denials_route"] == "/lens/host/runtime-loop/denials"
    assert body["approval_id"] == "approval-runtime-loop"
    assert body["actor"] == "test.system.write"
    assert body["limit"] == 10
    assert body["ready"] is False
    assert body["loop_ready"] is False
    assert body["execution_ready"] is False
    assert body["resident_runtime_loop"] is False
    assert body["resident_runtime_ready"] is False
    assert body["resident_claim_allowed"] is False
    assert body["runtime_plan_available"] is True
    assert body["loop_contract_readback_ready"] is True
    assert body["execution_denial_boundary_observed"] is True
    assert body["denial_receipt_readback_ready"] is True
    assert body["receipt_count"] == 0
    assert body["latest_receipt_id"] == ""
    assert body["requirements_total"] == 12
    assert body["requirements_ready_total"] == 7
    assert body["requirements_blocked_total"] == 5
    assert body["blocked_requirements"] == [
        "resident_loop_process_supervision",
        "resident_loop_service_lifecycle",
        "resident_loop_surface_presence",
        "resident_loop_receipt_emission",
        "resident_loop_claim_checkpoint",
    ]
    assert body["operator_surface_readback_ready"] is True
    assert body["first_blocked_requirement"] == "resident_loop_process_supervision"
    assert [item["id"] for item in body["blocked_requirement_handoffs"]] == body["blocked_requirements"]
    assert body["first_blocked_requirement_handoff"] == {
        "id": "resident_loop_process_supervision",
        "label": "Resident loop process supervision",
        "status": "blocked",
        "route": "/lens/host/supervision",
        "readiness_route": "/lens/host/supervision/authority/readiness",
        "request_route": "/lens/host/supervision/authority/request",
        "requests_route": "/lens/host/supervision/authority/requests",
        "grant_route": "/lens/host/supervision/authority",
        "grants_route": "/lens/host/supervision/authority/grants",
        "denials_route": "/lens/host/supervision/authority/denials",
        "next_step": "resolve_host_supervision_authority_readiness_blockers_before_implementation",
        "proof_script": "scripts/lens-host-runtime-loop-readiness-proof.ps1 -Mode Status",
        "authority_required": "process_supervision_authority",
        "authority_granted": False,
        "blockers": [
            "resident_host_process_missing",
            "process_supervision_authority_not_granted",
            "process_restart_authority_not_granted",
        ],
        "would_execute": False,
        "would_mutate": False,
    }
    assert body["recommended_handoff_source"] == "runtime_loop_first_blocked_requirement_handoff"
    assert (
        body["recommended_next_slice"] == "resolve_host_supervision_authority_readiness_blockers_before_implementation"
    )
    assert body["recommended_proof_script"] == "scripts/lens-host-runtime-loop-readiness-proof.ps1 -Mode Status"
    assert body["recommended_route"] == "/lens/host/supervision"
    assert body["recommended_readiness_route"] == "/lens/host/supervision/authority/readiness"
    assert body["authority_required"] == "process_supervision_authority"
    assert body["recommended_handoff"] == body["first_blocked_requirement_handoff"]
    requirements = {item["id"]: item for item in body["requirements"]}
    assert requirements["runtime_implementation_plan"]["ready"] is True
    assert requirements["runtime_loop_contract"]["ready"] is True
    assert requirements["runtime_loop_execution_denial_boundary"]["ready"] is True
    assert requirements["runtime_loop_execution_denial_boundary"]["status"] == "denied_no_resident_runtime_authority"
    assert requirements["runtime_loop_denial_receipts"]["ready"] is True
    assert requirements["diagnostic_status_tick"]["ready"] is True
    assert requirements["bounded_foreground_tick"]["ready"] is True
    assert requirements["runtime_state_heartbeat_readback"]["ready"] is True
    assert requirements["resident_loop_process_supervision"]["ready"] is False
    assert requirements["resident_loop_service_lifecycle"]["ready"] is False
    assert requirements["resident_loop_surface_presence"]["ready"] is False
    assert requirements["resident_loop_receipt_emission"]["ready"] is False
    assert requirements["resident_loop_claim_checkpoint"]["ready"] is False
    assert "resident_runtime_execution_authority_not_granted" in body["blockers"]
    assert "resident_host_process_missing" in body["blockers"]
    assert "resident_runtime_loop_not_implemented" in body["blockers"]
    assert "resident_runtime_loop_not_supervised" in body["blockers"]
    assert "receipt_write_authority_not_granted" in body["blockers"]
    assert "resident_claim_authority_not_granted" in body["blockers"]
    assert body["source_readbacks"] == {
        "runtime_plan_status": "blocked",
        "runtime_loop_status": "blocked",
        "execution_denial_status": "denied_no_resident_runtime_authority",
        "denial_receipts_status": "empty",
        "authority_grant_active": False,
        "active_supervision_authority_grant_receipt_id": "",
    }
    assert body["next_smallest_truthful_gap"] == "resident_host_supervision_authority_readiness_blockers"

    governance = body["governance"]
    assert governance["gate"] == "lens_host_runtime_loop_readiness_audit"
    assert governance["read_only_contract"] is True
    assert governance["audit_only"] is True
    assert governance["execution_boundary"] is True
    assert governance["denial_boundary"] is True
    for key in [
        "execution_authority",
        "resident_runtime_execution_authority",
        "approval_decision_authority",
        "memory_write",
        "local_process_launch_authority",
        "diagnostic_launch_authority",
        "process_supervision_authority",
        "process_restart_authority",
        "service_install_authority",
        "service_control_authority",
        "receipt_write_authority",
        "denial_receipt_write_authority",
        "resident_claim_authority",
        "overlay_control_authority",
        "summon_authority",
        "hotkey_registration_authority",
        "tray_registration_authority",
        "mutation_authority_granted",
    ]:
        assert governance[key] is False

    status_response = client.get("/lens/status?limit=1")
    assert status_response.status_code == 200
    status_body = status_response.json()
    resident_host = status_body["resident_host"]
    assert resident_host["runtime_loop_readiness_route"] == "/lens/host/runtime-loop/readiness"
    assert resident_host["runtime_loop_readiness"]["kind"] == "lens.host.runtime_loop.readiness_audit"
    assert resident_host["runtime_loop_readiness"]["status"] == "blocked"
    assert resident_host["runtime_loop_readiness"]["ready"] is False
    assert resident_host["runtime_loop_readiness"]["recommended_handoff"] == body["first_blocked_requirement_handoff"]
    assert (
        resident_host["runtime_loop_readiness"]["recommended_next_slice"]
        == "resolve_host_supervision_authority_readiness_blockers_before_implementation"
    )
    assert status_body["runtime_loop_readiness"]["route"] == "/lens/host/runtime-loop/readiness"
    assert status_body["receipts"]["lens_host_runtime_loop_readiness_route"] == "/lens/host/runtime-loop/readiness"
    criterion = _criterion(status_body, "resident_host_runtime_loop_readiness_audit")
    assert criterion["status"] == "blocked"
    assert criterion["audit_status"] == "complete"
    assert criterion["ready"] is False
    assert criterion["loop_contract_readback_ready"] is True
    assert criterion["execution_denial_boundary_observed"] is True
    assert criterion["denial_receipt_readback_ready"] is True
    assert criterion["requirements_total"] == 12
    assert criterion["requirements_ready_total"] == 7
    assert criterion["requirements_blocked_total"] == 5
    assert criterion["blocked_requirements"] == [
        "resident_loop_process_supervision",
        "resident_loop_service_lifecycle",
        "resident_loop_surface_presence",
        "resident_loop_receipt_emission",
        "resident_loop_claim_checkpoint",
    ]
    assert criterion["operator_surface_readback_ready"] is True
    assert criterion["next_smallest_truthful_gap"] == "resident_host_supervision_authority_readiness_blockers"
    assert criterion["first_blocked_requirement"] == "resident_loop_process_supervision"
    assert criterion["first_blocked_requirement_handoff"] == body["first_blocked_requirement_handoff"]
    assert [item["id"] for item in criterion["blocked_requirement_handoffs"]] == criterion["blocked_requirements"]
    assert len(criterion["requirement_readback"]) == 12
    blocked_requirement_readback = criterion["blocked_requirement_readback"]
    assert [item["id"] for item in blocked_requirement_readback] == criterion["blocked_requirements"]
    assert blocked_requirement_readback[0] == {
        "id": "resident_loop_process_supervision",
        "label": "Resident loop process supervision",
        "status": "blocked",
        "route": "/lens/host/supervision",
        "ready": False,
        "authority_required": "process_supervision_authority",
        "authority_granted": False,
        "blockers": [
            "resident_host_process_missing",
            "process_supervision_authority_not_granted",
            "process_restart_authority_not_granted",
        ],
    }
    assert criterion["execution_authority"] is False
    assert criterion["resident_runtime_execution_authority"] is False
    assert criterion["process_supervision_authority"] is False
    assert criterion["service_control_authority"] is False
    assert criterion["memory_write"] is False
    assert criterion["receipt_write_authority"] is False
    assert criterion["resident_claim_authority"] is False
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

    runtime_boundary_response = client.get("/lens/host/runtime-boundary")
    assert runtime_boundary_response.status_code == 200
    runtime_boundary = runtime_boundary_response.json()
    assert runtime_boundary["foreground_process_observed"] is True
    assert runtime_boundary["resident_host_process_state"] == "foreground_observed_not_supervised"
    assert runtime_boundary["resident_host_process_blocker"] == "resident_host_process_not_supervised"
    assert "resident_host_process_missing" not in runtime_boundary["blockers"]
    assert "resident_host_process_not_supervised" in runtime_boundary["blockers"]
    assert "lens_host_runtime_not_implemented" in runtime_boundary["runtime_blockers"]
    assert runtime_boundary["resident_runtime"] is False
    assert runtime_boundary["process_supervision"] is False
    assert runtime_boundary["governance"]["execution_authority"] is False
    assert runtime_boundary["governance"]["local_process_launch_authority"] is False
    assert runtime_boundary["governance"]["resident_claim_authority"] is False

    runtime_plan_response = client.get("/lens/host/runtime-plan")
    assert runtime_plan_response.status_code == 200
    runtime_plan = runtime_plan_response.json()
    assert runtime_plan["kind"] == "lens.host.runtime_implementation_plan"
    assert runtime_plan["foreground_process_observed"] is True
    assert runtime_plan["resident_host_process_state"] == "foreground_observed_not_supervised"
    assert runtime_plan["resident_host_process_blocker"] == "resident_host_process_not_supervised"
    assert runtime_plan["implementation_ready"] is False
    assert runtime_plan["execution_ready"] is False
    assert runtime_plan["resident_runtime_ready"] is False
    assert "resident_host_process_missing" not in runtime_plan["blockers"]
    assert "resident_host_process_not_supervised" in runtime_plan["blockers"]
    assert "lens_host_runtime_not_implemented" in runtime_plan["blockers"]
    runtime_plan_steps = {step["id"]: step for step in runtime_plan["plan"]["steps"]}
    process_supervision_step = runtime_plan_steps["process_supervision_contract"]
    assert runtime_plan_steps["resident_runtime_loop_contract"]["route"] == "/lens/host/runtime-loop"
    assert "resident_host_process_not_supervised" in process_supervision_step["blockers"]
    assert "resident_host_process_missing" not in process_supervision_step["blockers"]
    assert runtime_plan["plan"]["would_launch_process"] is False
    assert runtime_plan["plan"]["would_supervise_process"] is False
    assert runtime_plan["governance"]["execution_authority"] is False
    assert runtime_plan["governance"]["local_process_launch_authority"] is False
    assert runtime_plan["governance"]["process_supervision_authority"] is False
    assert runtime_plan["governance"]["resident_claim_authority"] is False

    runtime_loop_response = client.get("/lens/host/runtime-loop")
    assert runtime_loop_response.status_code == 200
    runtime_loop = runtime_loop_response.json()
    assert runtime_loop["kind"] == "lens.host.runtime_loop_contract"
    assert runtime_loop["foreground_process_observed"] is True
    assert runtime_loop["resident_host_process_state"] == "foreground_observed_not_supervised"
    assert runtime_loop["resident_host_process_blocker"] == "resident_host_process_not_supervised"
    assert runtime_loop["loop_ready"] is False
    assert runtime_loop["resident_runtime_loop"] is False
    assert "resident_host_process_missing" not in runtime_loop["blockers"]
    assert "resident_host_process_not_supervised" in runtime_loop["blockers"]
    assert "resident_runtime_loop_not_supervised" in runtime_loop["blockers"]
    runtime_loop_requirements = {item["id"]: item for item in runtime_loop["loop_contract"]["requirements"]}
    assert (
        "resident_host_process_not_supervised"
        in runtime_loop_requirements["resident_loop_process_supervision"]["blockers"]
    )
    assert (
        "resident_host_process_missing"
        not in runtime_loop_requirements["resident_loop_process_supervision"]["blockers"]
    )
    assert runtime_loop["loop_contract"]["would_start_loop"] is False
    assert runtime_loop["loop_contract"]["would_supervise_process"] is False
    assert runtime_loop["loop_contract"]["would_write_receipt"] is False
    assert runtime_loop["governance"]["execution_authority"] is False
    assert runtime_loop["governance"]["process_supervision_authority"] is False
    assert runtime_loop["governance"]["receipt_write_authority"] is False
    assert runtime_loop["governance"]["resident_claim_authority"] is False

    runtime_loop_execution_response = client.post(
        "/lens/host/runtime-loop/execute",
        json={
            "actor": "test.system.write",
            "approval_id": "approval-live-runtime-loop",
            "reason": "prove foreground runtime is still non-resident",
        },
    )
    assert runtime_loop_execution_response.status_code == 200
    runtime_loop_execution = runtime_loop_execution_response.json()
    assert runtime_loop_execution["kind"] == "lens.host.runtime_loop.execution_denial"
    assert runtime_loop_execution["status"] == "denied_no_resident_runtime_authority"
    assert runtime_loop_execution["foreground_process_observed"] is True
    assert runtime_loop_execution["resident_host_process_state"] == "foreground_observed_not_supervised"
    assert runtime_loop_execution["resident_host_process_blocker"] == "resident_host_process_not_supervised"
    assert "resident_host_process_missing" not in runtime_loop_execution["blockers"]
    assert "resident_host_process_not_supervised" in runtime_loop_execution["blockers"]
    assert "resident_runtime_loop_not_supervised" in runtime_loop_execution["blockers"]
    assert runtime_loop_execution["applied"] is False
    assert runtime_loop_execution["executed"] is False
    assert runtime_loop_execution["loop_started"] is False
    assert runtime_loop_execution["denial"]["would_start_loop"] is False
    assert runtime_loop_execution["denial"]["would_supervise_process"] is False
    assert runtime_loop_execution["denial"]["would_write_receipt"] is False
    assert runtime_loop_execution["denial"]["denial_receipt_written"] is True
    assert runtime_loop_execution["receipt_written"] is True
    runtime_loop_receipt = runtime_loop_execution["receipt"]
    assert runtime_loop_receipt["kind"] == "lens.host.runtime_loop.denial.receipt"
    assert runtime_loop_receipt["approval_id"] == "approval-live-runtime-loop"
    assert runtime_loop_receipt["execution"]["foreground_process_observed"] is True
    assert runtime_loop_receipt["execution"]["would_supervise_process"] is False
    assert runtime_loop_execution["governance"]["execution_authority"] is False
    assert runtime_loop_execution["governance"]["process_supervision_authority"] is False
    assert runtime_loop_execution["governance"]["receipt_write_authority"] is False
    assert runtime_loop_execution["governance"]["denial_receipt_write_authority"] is True
    assert runtime_loop_execution["governance"]["resident_claim_authority"] is False

    runtime_loop_denials_response = client.get(
        "/lens/host/runtime-loop/denials",
        params={"limit": 10, "approval_id": "approval-live-runtime-loop"},
    )
    assert runtime_loop_denials_response.status_code == 200
    runtime_loop_denials = runtime_loop_denials_response.json()
    assert runtime_loop_denials["status"] == "readback_ready"
    assert runtime_loop_denials["total"] == 1
    assert runtime_loop_denials["latest"]["receipt_id"] == runtime_loop_receipt["receipt_id"]
    assert runtime_loop_denials["latest"]["execution"]["would_supervise_process"] is False
    assert runtime_loop_denials["latest"]["governance"]["execution_authority"] is False
    assert runtime_loop_denials["latest"]["governance"]["denial_receipt_write_authority"] is True


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
    assert supervisor_readback["host_mode"] == ""
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
    assert supervisor_readback["resident_runtime_candidate_supervised"] is False
    assert supervisor_readback["fresh_bounded_supervisor_observed"] is True
    assert supervisor_readback["fresh_supervised_session_completed"] is True
    assert supervisor_readback["fresh_resident_runtime_candidate_supervised"] is False
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
    assert resident_host["resident_runtime_candidate_supervised"] is False
    assert resident_host["fresh_bounded_supervisor_observed"] is True
    assert resident_host["fresh_supervised_session_completed"] is True
    assert resident_host["fresh_resident_runtime_candidate_supervised"] is False
    assert resident_host["resident_supervised_runtime"] is False
    components = {item["id"]: item for item in resident_host["components"]}
    assert components["host_supervisor_readback"] == {
        "id": "host_supervisor_readback",
        "label": "Host supervisor readback",
        "status": "supervised_session_completed",
        "host_mode": "",
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
    assert supervision_gate["resident_runtime_candidate_supervised"] is False
    assert supervision_gate["fresh_bounded_supervisor_observed"] is True
    assert supervision_gate["fresh_supervised_session_completed"] is True
    assert supervision_gate["fresh_resident_runtime_candidate_supervised"] is False
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
    assert resident_surface_runtime["resident_runtime_candidate_supervised"] is False
    assert resident_surface_runtime["fresh_bounded_supervisor_observed"] is True
    assert resident_surface_runtime["fresh_supervised_session_completed"] is True
    assert resident_surface_runtime["fresh_resident_runtime_candidate_supervised"] is False
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
        "host_mode": "",
        "freshness_status": "fresh",
        "state_age_seconds": supervisor_readback["state_age_seconds"],
        "state_stale": False,
    }
    assert manifest_body["governance"]["execution_authority"] is False
    assert manifest_body["governance"]["service_control_authority"] is False
    assert manifest_body["governance"]["mutation_authority_granted"] is False


def test_lens_api_surfaces_bounded_resident_candidate_supervisor_readback(monkeypatch, tmp_path: Path) -> None:
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
        observed_pid=4321,
        mode="supervise_resident_once",
        host_mode="resident",
        observed_state="resident_stopped",
        updated_at="2026-05-01T00:00:00Z",
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
    assert supervisor_readback["mode"] == "supervise_resident_once"
    assert supervisor_readback["host_mode"] == "resident"
    assert supervisor_readback["observed_pid"] == 4321
    assert supervisor_readback["observed_state"] == "resident_stopped"
    assert supervisor_readback["freshness_status"] == "fresh"
    assert supervisor_readback["resident_runtime_candidate_supervised"] is True
    assert supervisor_readback["fresh_resident_runtime_candidate_supervised"] is True
    assert supervisor_readback["resident_supervised_runtime"] is False
    assert supervisor_readback["resident_claim_allowed"] is False
    assert supervisor_readback["blocked_reason"] == "resident_runtime_candidate_not_persistent"
    assert supervisor_readback["governance"]["execution_authority"] is False
    assert supervisor_readback["governance"]["resident_claim_authority"] is False

    assert resident_host["resident_runtime_candidate_supervised"] is True
    assert resident_host["fresh_resident_runtime_candidate_supervised"] is True
    assert resident_host["resident_supervised_runtime"] is False
    next_handoff = body["stage6_readiness"]["next_handoff"]
    assert next_handoff["next_smallest_truthful_gap"] == "resident_supervision_not_persistent"
    assert next_handoff["recommended_next_slice"] == (
        "resolve_resident_supervision_persistence_before_persistent_supervision_enablement"
    )
    assert next_handoff["recommended_handoff_source"] == "resident_runtime_candidate_handoff"
    assert next_handoff["recommended_proof_script"] == (
        "scripts/lens-resident-supervision-persistence-boundary-proof.ps1 -Mode Status"
    )
    assert next_handoff["authority_required"] == "persistent_process_supervision_authority"
    assert next_handoff["resident_runtime_candidate_handoff_observed"] is True
    assert next_handoff["resident_runtime_candidate_handoff"]["status"] == "observed_not_persistent"
    assert next_handoff["resident_runtime_candidate_handoff"]["proof_script"] == (
        "scripts/lens-resident-supervision-persistence-boundary-proof.ps1 -Mode Status"
    )
    assert next_handoff["resident_runtime_candidate_handoff"]["authority_required"] == (
        "persistent_process_supervision_authority"
    )
    assert next_handoff["resident_runtime_candidate_handoff"]["authority_granted"] is False
    assert (
        next_handoff["resident_runtime_candidate_handoff"]["next_smallest_truthful_gap"]
        == "resident_supervision_not_persistent"
    )
    assert next_handoff["governance"]["execution_authority"] is False
    assert next_handoff["governance"]["process_supervision_authority"] is False
    assert next_handoff["governance"]["resident_claim_authority"] is False

    persistent_plan = resident_host["persistent_supervision_plan"]
    plan_dependencies = {item["id"]: item for item in persistent_plan["enablement_dependency_readback"]}
    resident_process_dependency = plan_dependencies["resident_host_process"]
    assert resident_process_dependency["requirement_state"] == "resident_candidate_observed_not_persistent"
    assert resident_process_dependency["blocked_reason"] == "resident_supervision_not_persistent"
    assert resident_process_dependency["blocker"] == "resident_supervision_not_persistent"
    assert resident_process_dependency["resident_runtime_candidate_supervised"] is True
    assert resident_process_dependency["fresh_resident_runtime_candidate_supervised"] is True
    assert resident_process_dependency["resident_supervised_runtime"] is False
    plan_handoff = persistent_plan["first_missing_requirement_handoff"]
    assert plan_handoff["id"] == "resident_host_process"
    assert plan_handoff["requirement_state"] == "resident_candidate_observed_not_persistent"
    assert plan_handoff["blocker"] == "resident_supervision_not_persistent"
    assert plan_handoff["next_step"] == (
        "resolve_resident_supervision_persistence_before_persistent_supervision_enablement"
    )
    assert plan_handoff["next_smallest_truthful_gap"] == "resident_supervision_not_persistent"
    assert plan_handoff["authority_required"] == "persistent_process_supervision_authority"
    assert plan_handoff["authority_route"] == "/lens/host/supervision/authority"
    assert plan_handoff["authority_request_route"] == "/lens/host/supervision/authority/request"
    assert plan_handoff["authority_requests_route"] == "/lens/host/supervision/authority/requests"
    assert plan_handoff["authority_readiness_route"] == "/lens/host/supervision/authority/readiness"
    assert plan_handoff["authority_grants_route"] == "/lens/host/supervision/authority/grants"
    assert plan_handoff["authority_denials_route"] == "/lens/host/supervision/authority/denials"
    assert plan_handoff["approval_action"] == "lens.host.supervision_authority"
    assert plan_handoff["persistent_supervision_route"] == "/lens/host/persistent-supervision"
    assert plan_handoff["persistent_supervision_enablement_route"] == "/lens/host/persistent-supervision/enablement"
    assert plan_handoff["persistent_supervision_enablement_authority_route"] == (
        "/lens/host/persistent-supervision/enablement/authority"
    )
    assert plan_handoff["persistent_supervision_enablement_authority_request_route"] == (
        "/lens/host/persistent-supervision/enablement/authority/request"
    )
    assert plan_handoff["persistent_supervision_enablement_authority_requests_route"] == (
        "/lens/host/persistent-supervision/enablement/authority/requests"
    )
    assert plan_handoff["persistent_supervision_enablement_authority_readiness_route"] == (
        "/lens/host/persistent-supervision/enablement/authority/readiness"
    )
    assert plan_handoff["persistent_supervision_enablement_authority_grants_route"] == (
        "/lens/host/persistent-supervision/enablement/authority/grants"
    )
    assert plan_handoff["persistent_supervision_enablement_execution_route"] == (
        "/lens/host/persistent-supervision/enablement/execution"
    )
    assert plan_handoff["persistent_supervision_enablement_execution_request_route"] == (
        "/lens/host/persistent-supervision/enablement/execution/request"
    )
    assert plan_handoff["persistent_supervision_enablement_execution_requests_route"] == (
        "/lens/host/persistent-supervision/enablement/execution/requests"
    )
    assert plan_handoff["persistent_supervision_enablement_execution_readiness_route"] == (
        "/lens/host/persistent-supervision/enablement/execution/readiness"
    )
    assert plan_handoff["persistent_supervision_enablement_execution_authority_route"] == (
        "/lens/host/persistent-supervision/enablement/execution/authority"
    )
    assert plan_handoff["persistent_supervision_enablement_execution_authority_grants_route"] == (
        "/lens/host/persistent-supervision/enablement/execution/authority/grants"
    )
    assert plan_handoff["persistent_supervision_enablement_executions_route"] == (
        "/lens/host/persistent-supervision/enablement/executions"
    )
    assert plan_handoff["persistent_supervision_next_smallest_truthful_gap"] == (
        "persistent_supervision_authority_not_granted"
    )
    assert plan_handoff["persistent_supervision_enablement_authority_action"] == (
        "lens.host.persistent_supervision_enablement_authority"
    )
    assert plan_handoff["persistent_supervision_enablement_execution_action"] == (
        "lens.host.persistent_supervision_enablement_execution_authority"
    )
    assert plan_handoff["persistent_supervision_authority_scope"] == "system.write"
    assert plan_handoff["read_only_contract"] is True
    assert plan_handoff["would_execute"] is False
    assert plan_handoff["would_mutate"] is False

    persistent_enablement = resident_host["persistent_supervision_enablement"]
    enablement_dependencies = {item["id"]: item for item in persistent_enablement["enablement_dependency_readback"]}
    assert enablement_dependencies["resident_host_process"]["blocker"] == "resident_supervision_not_persistent"
    enablement_handoff = persistent_enablement["first_missing_requirement_handoff"]
    assert enablement_handoff["next_smallest_truthful_gap"] == "resident_supervision_not_persistent"
    assert enablement_handoff["authority_required"] == "persistent_process_supervision_authority"
    assert enablement_handoff["authority_request_route"] == "/lens/host/supervision/authority/request"
    assert enablement_handoff["approval_action"] == "lens.host.supervision_authority"
    assert enablement_handoff["persistent_supervision_next_smallest_truthful_gap"] == (
        "persistent_supervision_authority_not_granted"
    )
    assert enablement_handoff["persistent_supervision_enablement_authority_readiness_route"] == (
        "/lens/host/persistent-supervision/enablement/authority/readiness"
    )
    assert enablement_handoff["persistent_supervision_enablement_execution_readiness_route"] == (
        "/lens/host/persistent-supervision/enablement/execution/readiness"
    )
    assert persistent_enablement["governance"]["process_supervision_authority"] is False
    assert persistent_enablement["governance"]["service_config_write_authority"] is False

    components = {item["id"]: item for item in resident_host["components"]}
    assert components["host_supervisor_readback"]["host_mode"] == "resident"
    supervision_gate = resident_host["supervision_gate"]
    assert supervision_gate["resident_runtime_candidate_supervised"] is True
    assert supervision_gate["fresh_resident_runtime_candidate_supervised"] is True
    assert supervision_gate["resident_supervised_runtime"] is False
    assert supervision_gate["resident_claim_allowed"] is False
    assert supervision_gate["governance"]["execution_authority"] is False

    resident_surface_runtime = body["resident_surface"]["resident_surface_runtime"]
    assert resident_surface_runtime["resident_runtime_candidate_supervised"] is True
    assert resident_surface_runtime["fresh_resident_runtime_candidate_supervised"] is True
    assert resident_surface_runtime["resident_supervised_runtime"] is False
    assert resident_surface_runtime["resident_claim_allowed"] is False

    manifest = client.get("/lens/host/manifest")
    assert manifest.status_code == 200
    manifest_body = manifest.json()
    assert manifest_body["supervisor_readback"] == supervisor_readback
    required_bindings = {item["id"]: item for item in manifest_body["required_bindings"]}
    assert required_bindings["host_supervisor_readback"]["host_mode"] == "resident"
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
    assert supervisor_readback["resident_runtime_candidate_supervised"] is False
    assert supervisor_readback["fresh_bounded_supervisor_observed"] is False
    assert supervisor_readback["fresh_supervised_session_completed"] is False
    assert supervisor_readback["fresh_resident_runtime_candidate_supervised"] is False
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
        "host_mode": "",
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
        "host_mode": "",
        "freshness_status": "stale",
        "state_age_seconds": supervisor_readback["state_age_seconds"],
        "state_stale": True,
    }
    assert manifest_body["governance"]["execution_authority"] is False
    assert manifest_body["governance"]["service_control_authority"] is False
    assert manifest_body["governance"]["mutation_authority_granted"] is False


def test_lens_status_promotes_live_supervised_resident_host_before_tray(monkeypatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    data_root = repo_root / "data"
    _write_dev_environment(repo_root)
    _write_lens_host_status_runner(repo_root)
    _write_service_manager(repo_root)
    _write_lens_preflight_scripts(repo_root)
    _write_lens_runtime_configs(repo_root)
    _write_lens_host_service_config(repo_root)
    service_config_path = repo_root / "config" / "runtime" / "services" / "lens-host.json"
    service_config = json.loads(service_config_path.read_text(encoding="utf-8"))
    service_config["process_supervision_enabled"] = True
    service_config["persistent_supervision_enabled"] = True
    service_config["supervision_blocked_reason"] = "resident_supervision_prerequisites_pending"
    service_config["blocked_reason"] = "lens_host_persistent_supervision_prerequisites_pending"
    service_config_path.write_text(json.dumps(service_config, indent=2), encoding="utf-8")
    _write_lens_host_runtime_state(
        data_root,
        pid=6789,
        status="resident_running",
        mode="resident",
    )
    _write_lens_host_supervisor_state(
        data_root,
        observed_pid=6789,
        status="resident_supervising",
        mode="supervise_resident",
        host_mode="resident",
        observed_state="resident_running",
        updated_at="2026-05-01T00:00:00Z",
        resident_supervised_runtime=True,
        process_supervision_authority=True,
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
    monkeypatch.setattr(host_manifest_module, "_process_alive_readback", lambda pid: (pid == 6789, "test"))

    client = TestClient(create_app())
    response = client.get("/lens/status?limit=1")

    assert response.status_code == 200
    body = response.json()
    resident_host = body["resident_host"]
    supervisor_readback = resident_host["supervisor_readback"]
    assert supervisor_readback["status"] == "resident_supervising"
    assert supervisor_readback["freshness_status"] == "fresh"
    assert supervisor_readback["resident_supervised_runtime"] is True
    assert supervisor_readback["process_supervision_authority"] is True
    assert supervisor_readback["service_control_authority"] is False
    assert resident_host["process_readback"]["process_alive"] is True
    assert resident_host["process_readback"]["state_status"] == "resident_running"

    persistent_plan = resident_host["persistent_supervision_plan"]
    assert persistent_plan["missing_required_before_enable"] == [
        "tray_presence",
        "global_hotkey_binding",
        "overlay_window",
        "summon_binding",
    ]
    plan_dependencies = {item["id"]: item for item in persistent_plan["enablement_dependency_readback"]}
    resident_process_dependency = plan_dependencies["resident_host_process"]
    assert resident_process_dependency["ready"] is True
    assert resident_process_dependency["requirement_state"] == "ready"
    assert resident_process_dependency["resident_supervised_runtime"] is True
    assert resident_process_dependency["process_alive"] is True

    supervision_gate = resident_host["supervision_gate"]
    assert supervision_gate["resident_host_process"] is True
    assert supervision_gate["resident_supervised_runtime"] is True
    assert supervision_gate["resident_host_supervised"] is True
    assert supervision_gate["resident_host_process_state"] == "resident_supervised"
    assert supervision_gate["resident_host_process_blocker"] == ""
    assert "resident_host_process_not_supervised" not in supervision_gate["blockers"]
    assert "resident_host_process_missing" not in supervision_gate["blockers"]

    tray_dependency = plan_dependencies["tray_presence"]
    assert tray_dependency["ready"] is False
    assert tray_dependency["blocker"] == "tray_host_missing"
    handoff = persistent_plan["first_missing_requirement_handoff"]
    assert handoff["id"] == "tray_presence"
    assert handoff["next_smallest_truthful_gap"] == "summon_tray_presence_blocker_boundary"
    assert handoff["route"] == "/lens/tray"
    assert handoff["read_only_contract"] is True
    assert handoff["would_execute"] is False
    assert handoff["would_mutate"] is False
    assert persistent_plan["governance"]["execution_authority"] is False
    assert persistent_plan["governance"]["resident_claim_authority"] is False


def test_lens_status_promotes_live_tray_runtime_before_hotkey(monkeypatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    data_root = repo_root / "data"
    _write_dev_environment(repo_root)
    _write_lens_host_status_runner(repo_root)
    _write_service_manager(repo_root)
    _write_lens_preflight_scripts(repo_root)
    _write_lens_runtime_configs(repo_root)
    _write_lens_host_service_config(repo_root)
    service_config_path = repo_root / "config" / "runtime" / "services" / "lens-host.json"
    service_config = json.loads(service_config_path.read_text(encoding="utf-8"))
    service_config["process_supervision_enabled"] = True
    service_config["persistent_supervision_enabled"] = True
    service_config["supervision_blocked_reason"] = "resident_supervision_prerequisites_pending"
    service_config["blocked_reason"] = "lens_host_persistent_supervision_prerequisites_pending"
    service_config_path.write_text(json.dumps(service_config, indent=2), encoding="utf-8")
    _write_lens_host_runtime_state(
        data_root,
        pid=6789,
        status="resident_running",
        mode="resident",
    )
    _write_lens_host_supervisor_state(
        data_root,
        observed_pid=6789,
        status="resident_supervising",
        mode="supervise_resident",
        host_mode="resident",
        observed_state="resident_running",
        updated_at="2026-05-01T00:00:00Z",
        resident_supervised_runtime=True,
        process_supervision_authority=True,
    )
    _write_lens_tray_runtime_state(data_root, pid=4321)
    monkeypatch.setenv("FRANCIS_ROOT", str(repo_root))
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_ENV_PROFILE", "dev")
    monkeypatch.setenv("FRANCIS_RUN_MODE", "api")

    from fastapi.testclient import TestClient

    from francis.api.app import create_app
    from francis.lens import host_manifest as host_manifest_module

    fixed_now = datetime(2026, 5, 1, 0, 0, 5, tzinfo=UTC).timestamp()
    monkeypatch.setattr(host_manifest_module.time, "time", lambda: fixed_now)
    monkeypatch.setattr(host_manifest_module, "_process_alive_readback", lambda pid: (pid in {4321, 6789}, "test"))

    client = TestClient(create_app())
    response = client.get("/lens/status?limit=1")

    assert response.status_code == 200
    body = response.json()
    resident_host = body["resident_host"]
    assert resident_host["tray_runtime_readback"]["ready"] is True
    assert resident_host["tray_runtime_readback"]["process_alive"] is True
    assert resident_host["tray_runtime_readback"]["tray_icon_visible"] is True

    persistent_plan = resident_host["persistent_supervision_plan"]
    assert persistent_plan["missing_required_before_enable"] == [
        "global_hotkey_binding",
        "overlay_window",
        "summon_binding",
    ]
    plan_dependencies = {item["id"]: item for item in persistent_plan["enablement_dependency_readback"]}
    tray_dependency = plan_dependencies["tray_presence"]
    assert tray_dependency["ready"] is True
    assert tray_dependency["blocker"] == ""
    assert tray_dependency["requirement_state"] == "ready"
    assert tray_dependency["blocked_reason"] == ""
    assert tray_dependency["tray_presence_source"] == "live_runtime_readback"
    assert tray_dependency["tray_runtime_ready"] is True
    assert tray_dependency["tray_runtime_process_alive"] is True
    assert tray_dependency["tray_runtime_icon_visible"] is True
    assert tray_dependency["tray_runtime_pid"] == 4321

    handoff = persistent_plan["first_missing_requirement_handoff"]
    assert handoff["id"] == "global_hotkey_binding"
    assert handoff["next_smallest_truthful_gap"] == "os_level_command_palette_binding"
    assert handoff["route"] == "/lens/summon"
    assert handoff["read_only_contract"] is True
    assert handoff["would_execute"] is False
    assert handoff["would_mutate"] is False
    assert persistent_plan["governance"]["execution_authority"] is False
    assert persistent_plan["governance"]["resident_claim_authority"] is False


def test_lens_status_promotes_coordinated_surface_runtime_before_summon_binding(
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
    service_config_path = repo_root / "config" / "runtime" / "services" / "lens-host.json"
    service_config = json.loads(service_config_path.read_text(encoding="utf-8"))
    service_config["process_supervision_enabled"] = True
    service_config["persistent_supervision_enabled"] = True
    service_config["supervision_blocked_reason"] = "resident_supervision_prerequisites_pending"
    service_config["blocked_reason"] = "lens_host_persistent_supervision_prerequisites_pending"
    service_config_path.write_text(json.dumps(service_config, indent=2), encoding="utf-8")
    _write_lens_host_runtime_state(
        data_root,
        pid=6789,
        status="resident_running",
        mode="resident",
    )
    _write_lens_host_supervisor_state(
        data_root,
        observed_pid=6789,
        status="resident_supervising",
        mode="supervise_resident",
        host_mode="resident",
        observed_state="resident_running",
        updated_at="2026-05-01T00:00:00Z",
        resident_supervised_runtime=True,
        process_supervision_authority=True,
    )
    surface_pid = os.getpid()
    _write_lens_tray_runtime_state(data_root, pid=surface_pid)
    _write_lens_hotkey_runtime_state(data_root, pid=surface_pid)
    _write_lens_overlay_runtime_state(data_root, pid=surface_pid)
    monkeypatch.setenv("FRANCIS_ROOT", str(repo_root))
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_ENV_PROFILE", "dev")
    monkeypatch.setenv("FRANCIS_RUN_MODE", "api")

    from fastapi.testclient import TestClient

    from francis.api.app import create_app
    from francis.lens import host_manifest as host_manifest_module

    fixed_now = datetime(2026, 5, 1, 0, 0, 5, tzinfo=UTC).timestamp()
    monkeypatch.setattr(host_manifest_module.time, "time", lambda: fixed_now)
    monkeypatch.setattr(
        host_manifest_module,
        "_process_alive_readback",
        lambda pid: (pid in {surface_pid, 6789}, "test"),
    )

    client = TestClient(create_app())
    response = client.get("/lens/status?limit=1")

    assert response.status_code == 200
    body = response.json()
    resident_host = body["resident_host"]
    assert resident_host["tray_runtime_readback"]["ready"] is True
    assert resident_host["hotkey_runtime_readback"]["ready"] is True
    assert resident_host["hotkey_runtime_readback"]["hotkey_bound"] is True
    assert resident_host["overlay_runtime_readback"]["ready"] is True
    assert resident_host["overlay_runtime_readback"]["overlay_window_visible"] is True

    persistent_plan = resident_host["persistent_supervision_plan"]
    assert persistent_plan["missing_required_before_enable"] == ["summon_binding"]
    plan_dependencies = {item["id"]: item for item in persistent_plan["enablement_dependency_readback"]}
    for dependency_id in [
        "resident_host_process",
        "tray_presence",
        "global_hotkey_binding",
        "overlay_window",
    ]:
        assert plan_dependencies[dependency_id]["ready"] is True
        assert plan_dependencies[dependency_id]["blocker"] == ""
        assert plan_dependencies[dependency_id]["requirement_state"] == "ready"

    hotkey_dependency = plan_dependencies["global_hotkey_binding"]
    assert hotkey_dependency["hotkey_presence_source"] == "live_runtime_readback"
    assert hotkey_dependency["hotkey_runtime_ready"] is True
    assert hotkey_dependency["hotkey_runtime_process_alive"] is True
    assert hotkey_dependency["hotkey_runtime_bound"] is True
    assert hotkey_dependency["hotkey_runtime_pid"] == surface_pid

    overlay_dependency = plan_dependencies["overlay_window"]
    assert overlay_dependency["overlay_presence_source"] == "live_runtime_readback"
    assert overlay_dependency["overlay_runtime_ready"] is True
    assert overlay_dependency["overlay_runtime_process_alive"] is True
    assert overlay_dependency["overlay_runtime_window_visible"] is True
    assert overlay_dependency["overlay_runtime_always_on_top"] is True
    assert overlay_dependency["overlay_runtime_pid"] == surface_pid

    handoff = persistent_plan["first_missing_requirement_handoff"]
    assert handoff["id"] == "summon_binding"
    assert handoff["next_smallest_truthful_gap"] == "summon_anywhere_blockers"
    assert handoff["route"] == "/lens/summon"
    assert handoff["read_only_contract"] is True
    assert handoff["would_execute"] is False
    assert handoff["would_mutate"] is False
    assert persistent_plan["governance"]["execution_authority"] is False
    assert persistent_plan["governance"]["resident_claim_authority"] is False


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


def test_lens_host_activation_authority_grant_executes_bounded_launch(monkeypatch, tmp_path: Path) -> None:
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
            "reason": "operator wants bounded host activation authority",
            "mode": "foreground_status_session",
        },
    )
    assert requested.status_code == 200
    approval_id = str(requested.json()["approval_id"])

    decided = client.post(
        "/approvals/decision",
        json={
            "id": approval_id,
            "action": "approve",
            "actor": "test.approvals.decision",
            "comment": "approved host activation authority review",
        },
    )
    assert decided.status_code == 200
    assert decided.json()["status"] == "approved"

    empty_grants = client.get("/lens/host/activation/authority/grants")
    assert empty_grants.status_code == 200
    assert empty_grants.json()["status"] == "empty"
    assert empty_grants.json()["authority_granted"] is False

    grant = client.post(
        "/lens/host/activation/authority",
        json={
            "approval_id": approval_id,
            "actor": "test.system.write",
            "reason": "operator grants bounded host activation authority",
            "lease_seconds": 600,
        },
    )
    assert grant.status_code == 200
    grant_body = grant.json()
    assert grant_body["kind"] == "lens.host.activation_authority.grant"
    assert grant_body["status"] == "authority_granted"
    assert grant_body["approval_id"] == approval_id
    assert grant_body["authority_granted"] is True
    assert grant_body["activation_authority"] is True
    assert grant_body["local_process_launch_authority"] is True
    assert grant_body["launches_process"] is False
    assert grant_body["grant"]["would_grant_local_process_launch_authority"] is True
    assert grant_body["grant"]["would_launch_process"] is False
    assert grant_body["receipt_written"] is True
    grant_receipt = grant_body["receipt"]
    assert grant_receipt["kind"] == "lens.host.activation_authority.grant.receipt"
    assert grant_receipt["approval_id"] == approval_id
    assert grant_receipt["authorities"]["local_process_launch_authority"] is True
    assert grant_receipt["governance"]["local_process_launch_authority"] is True
    grant_receipt_path = data_root / "lens" / "host_activation_authority_grants" / f"{grant_receipt['receipt_id']}.json"
    assert grant_receipt_path.exists()

    grants = client.get(f"/lens/host/activation/authority/grants?limit=10&approval_id={approval_id}")
    assert grants.status_code == 200
    grants_body = grants.json()
    assert grants_body["kind"] == "lens.host.activation_authority.grant_receipts"
    assert grants_body["status"] == "readback_ready"
    assert grants_body["total"] == 1
    assert grants_body["active_latest"]["receipt_id"] == grant_receipt["receipt_id"]
    assert grants_body["authority_granted"] is True
    assert grants_body["local_process_launch_authority"] is True
    assert grants_body["governance"]["execution_authority"] is False

    readback = client.get("/lens/host/activation?limit=10")
    assert readback.status_code == 200
    readback_body = readback.json()
    assert readback_body["status"] == "authority_granted"
    assert readback_body["active_grant_receipt_id"] == grant_receipt["receipt_id"]
    assert readback_body["latest_execution_receipt_id"] == ""
    assert readback_body["latest_execution_status"] == ""
    assert readback_body["latest_execution_bounded_process_launch"] is False
    assert readback_body["latest_execution_observed_process"] is False
    assert readback_body["latest_execution_handoff_observed"] is False
    assert readback_body["latest_execution_handoff"] == {}
    assert readback_body["activation_authority"] is True
    assert readback_body["local_process_launch_authority"] is True
    assert readback_body["governance"]["local_process_launch_authority"] is True
    assert readback_body["governance"]["latest_execution_handoff_readback"] is False

    preflight = client.get(f"/lens/host/activation/preflight?approval_id={approval_id}&actor=test.system.write")
    assert preflight.status_code == 200
    preflight_body = preflight.json()
    assert preflight_body["status"] == "bounded_prerequisite_ready"
    assert preflight_body["ready"] is False
    assert preflight_body["bounded_prerequisite_launch_ready"] is True
    assert preflight_body["bounded_prerequisite_launch_blockers"] == []
    assert preflight_body["authority"]["active_grant_receipt_id"] == grant_receipt["receipt_id"]
    assert preflight_body["authority"]["local_process_launch_authority"] is True
    assert "local_process_launch_authority_not_granted" not in preflight_body["blockers"]
    assert "lens_preflight_blocked" in preflight_body["blockers"]
    assert preflight_body["governance"]["local_process_launch_authority"] is True
    assert preflight_body["governance"]["execution_authority"] is False

    plan = client.get(f"/lens/host/activation/plan?approval_id={approval_id}&actor=test.system.write")
    assert plan.status_code == 200
    plan_body = plan.json()
    assert plan_body["status"] == "bounded_prerequisite_ready"
    assert plan_body["execution_ready"] is True
    assert plan_body["full_activation_ready"] is False
    assert plan_body["bounded_prerequisite_launch_ready"] is True
    plan_steps = {step["id"]: step for step in plan_body["plan"]["steps"]}
    assert plan_steps["launch_foreground_status_session"]["authority_granted"] is True
    assert plan_steps["launch_foreground_status_session"]["status"] == "ready"
    assert plan_steps["record_activation_receipt"]["status"] == "ready"
    assert plan_body["plan"]["would_launch_process"] is True
    assert plan_body["plan"]["would_launch_bounded_foreground_process"] is True
    assert "local_process_launch_authority_not_granted" not in plan_body["blockers"]
    assert plan_body["governance"]["local_process_launch_authority"] is True
    assert plan_body["governance"]["execution_authority"] is False

    executed = client.post(
        "/lens/host/activation/execute",
        json={
            "approval_id": approval_id,
            "actor": "test.system.write",
            "reason": "prove bounded host activation launch remains governed",
            "run_seconds": 1,
        },
    )
    assert executed.status_code == 200
    executed_body = executed.json()
    powershell_available = bool(shutil.which("pwsh") or shutil.which("powershell"))
    expects_observed_foreground_launch = powershell_available and os.name == "nt"
    launch_observed = executed_body["status"] == "bounded_foreground_launch_observed"
    assert executed_body["kind"] == "lens.host.activation.execution"
    assert executed_body["approval_id"] == approval_id
    assert executed_body["run_seconds"] == 1
    assert "local_process_launch_authority_not_granted" not in executed_body["blockers"]
    assert executed_body["governance"]["local_process_launch_authority"] is True
    assert executed_body["governance"]["execution_authority"] is True
    assert executed_body["governance"]["resident_claim_authority"] is False
    assert executed_body["governance"]["service_install_authority"] is False
    assert executed_body["governance"]["service_control_authority"] is False
    assert executed_body["governance"]["memory_write"] is False
    assert executed_body["receipt_written"] is True
    assert executed_body["receipt"]["kind"] == "lens.host.activation.execution.receipt"
    assert executed_body["receipt"]["approval_id"] == approval_id
    assert executed_body["receipt"]["resident_claim"]["resident_host_process_claimed"] is False
    if expects_observed_foreground_launch:
        assert launch_observed is True
    if launch_observed:
        assert executed_body["status"] == "bounded_foreground_launch_observed"
        assert executed_body["executed"] is True
        assert executed_body["launch"]["ok"] is True
        assert executed_body["launch"]["runner"]["status"] == "launch_started"
        assert executed_body["receipt"]["execution"]["bounded_process_launch"] is True
        assert executed_body["receipt"]["execution"]["observed_process"] is True
        assert (data_root / "runtime" / "lens-host" / "status.json").exists()
        assert (data_root / "runtime" / "lens-host" / "lens-host.pid").exists()
    else:
        assert executed_body["status"] == "bounded_foreground_launch_failed"
        assert executed_body["executed"] is False
        assert executed_body["launch"]["ok"] is False
        if powershell_available:
            assert executed_body["launch"]["status"] in {"launch_timeout", "launch_failed"}
        else:
            assert executed_body["launch"]["status"] == "powershell_runtime_missing"
            assert "powershell_runtime_missing" in executed_body["blockers"]
        assert executed_body["receipt"]["execution"]["bounded_process_launch"] is False
        assert executed_body["receipt"]["execution"]["observed_process"] is False
        assert not (data_root / "runtime" / "lens-host" / "status.json").exists()
        assert not (data_root / "runtime" / "lens-host" / "lens-host.pid").exists()

    executions = client.get(f"/lens/host/activation/executions?limit=10&approval_id={approval_id}")
    assert executions.status_code == 200
    executions_body = executions.json()
    assert executions_body["kind"] == "lens.host.activation.execution_receipts"
    assert executions_body["status"] == "readback_ready"
    assert executions_body["total"] == 1
    assert executions_body["latest"]["receipt_id"] == executed_body["receipt"]["receipt_id"]
    if launch_observed:
        assert executions_body["latest_bounded_process_launch"] is True
        assert executions_body["latest_observed_process"] is True
        assert executions_body["latest_execution_handoff_observed"] is True
        execution_handoff = executions_body["latest_execution_handoff"]
        assert execution_handoff["id"] == "resident_host_process"
        assert execution_handoff["status"] == "bounded_foreground_activation_observed_not_resident"
        assert execution_handoff["source"] == "/lens/host/activation/executions"
        assert execution_handoff["receipt_id"] == executed_body["receipt"]["receipt_id"]
        assert execution_handoff["activation_execution_status"] == "bounded_foreground_launch_observed"
        assert execution_handoff["activation_execution_evidence_only"] is True
        assert execution_handoff["does_not_satisfy_resident_host_process"] is True
        assert execution_handoff["previous_next_smallest_truthful_gap"] == "resident_host_process_not_supervised"
        assert execution_handoff["next_smallest_truthful_gap"] == "resident_host_process_not_supervised"
        assert execution_handoff["next_step"] == (
            "consume_resident_host_process_supervision_handoff_before_stage6_closure"
        )
        assert execution_handoff["proof_script"] == (
            "scripts/lens-resident-host-process-supervision-blocker-proof.ps1 -Mode Status"
        )
        assert execution_handoff["route"] == "/lens/host"
        assert execution_handoff["readiness_route"] == "/lens/host/runtime-loop/readiness"
        assert execution_handoff["authority_required"] == "process_supervision_authority"
        assert execution_handoff["authority_granted"] is False
        assert execution_handoff["read_only_contract"] is True
        assert execution_handoff["diagnostic_only"] is True
        assert execution_handoff["would_execute"] is False
        assert execution_handoff["would_mutate"] is False
        assert executions_body["governance"]["latest_execution_handoff_readback"] is True

        readback_after_execution = client.get("/lens/host/activation?limit=10")
        assert readback_after_execution.status_code == 200
        readback_after_execution_body = readback_after_execution.json()
        assert readback_after_execution_body["latest_execution_receipt_id"] == executed_body["receipt"]["receipt_id"]
        assert readback_after_execution_body["latest_execution_status"] == "bounded_foreground_launch_observed"
        assert readback_after_execution_body["latest_execution_bounded_process_launch"] is True
        assert readback_after_execution_body["latest_execution_observed_process"] is True
        assert readback_after_execution_body["latest_execution_handoff_observed"] is True
        assert readback_after_execution_body["latest_execution_handoff"] == execution_handoff
        assert readback_after_execution_body["governance"]["latest_execution_handoff_readback"] is True
    else:
        assert executions_body["latest_bounded_process_launch"] is False
        assert executions_body["latest_observed_process"] is False
        assert executions_body["latest_execution_handoff_observed"] is False
        assert executions_body["latest_execution_handoff"] == {}
        assert executions_body["governance"]["latest_execution_handoff_readback"] is False


def test_lens_host_supervision_execute_writes_bounded_resident_candidate_receipt(
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
    service_config_path = repo_root / "config" / "runtime" / "services" / "lens-host.json"
    service_config = json.loads(service_config_path.read_text(encoding="utf-8"))
    service_config["process_supervision_enabled"] = True
    service_config["persistent_supervision_enabled"] = True
    service_config["supervision_blocked_reason"] = "resident_supervision_prerequisites_pending"
    service_config["blocked_reason"] = "lens_host_persistent_supervision_prerequisites_pending"
    service_config_path.write_text(json.dumps(service_config, indent=2), encoding="utf-8")
    monkeypatch.setenv("FRANCIS_ROOT", str(repo_root))
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_ENV_PROFILE", "dev")
    monkeypatch.setenv("FRANCIS_RUN_MODE", "api")

    import francis.lens.activation as activation_module
    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    def fake_supervise_once(*, run_seconds: int) -> dict[str, Any]:
        _write_lens_host_supervisor_state(
            data_root,
            observed_pid=4321,
            mode="supervise_resident_once",
            host_mode="resident",
            observed_state="resident_stopped",
        )
        return {
            "ok": True,
            "status": "supervised_session_completed",
            "returncode": 0,
            "run_seconds": run_seconds,
            "script": "scripts/lens-host-supervisor.ps1",
            "runner": {
                "ok": True,
                "status": "supervised_session_completed",
                "bounded_supervised_session": True,
                "temporary_host_process_observed": True,
                "resident_runtime_candidate_supervised": True,
                "next_smallest_truthful_gap": "resident_supervision_not_persistent",
            },
            "blockers": [
                "resident_runtime_candidate_not_persistent",
                "resident_supervision_not_persistent",
                "tray_host_missing",
                "global_hotkey_binding_missing",
                "overlay_window_missing",
                "summon_binding_missing",
            ],
        }

    monkeypatch.setattr(activation_module, "_run_bounded_lens_host_supervision_once", fake_supervise_once)

    client = TestClient(create_app())
    requested = client.post(
        "/lens/host/supervision/authority/request",
        json={
            "actor": "test.system.write",
            "reason": "operator wants bounded host supervision authority",
        },
    )
    assert requested.status_code == 200
    approval_id = str(requested.json()["approval_id"])

    decided = client.post(
        "/approvals/decision",
        json={
            "id": approval_id,
            "action": "approve",
            "actor": "test.approvals.decision",
            "comment": "approved host supervision execution boundary review",
        },
    )
    assert decided.status_code == 200
    assert decided.json()["status"] == "approved"

    grant = client.post(
        "/lens/host/supervision/authority",
        json={
            "approval_id": approval_id,
            "actor": "test.system.write",
            "reason": "operator grants host supervision authority for bounded execution",
            "lease_seconds": 600,
        },
    )
    assert grant.status_code == 200
    grant_body = grant.json()
    assert grant_body["status"] == "authority_granted"
    grant_receipt_id = grant_body["receipt"]["receipt_id"]

    executed = client.post(
        "/lens/host/supervision/execute",
        json={
            "approval_id": approval_id,
            "actor": "test.system.write",
            "reason": "prove bounded resident host supervision remains governed",
            "run_seconds": 1,
        },
    )
    assert executed.status_code == 200
    executed_body = executed.json()
    assert executed_body["kind"] == "lens.host.supervision.execution"
    assert executed_body["status"] == "resident_candidate_supervised_not_persistent"
    assert executed_body["approval_id"] == approval_id
    assert executed_body["active_grant"]["receipt_id"] == grant_receipt_id
    assert executed_body["executed"] is True
    assert executed_body["bounded_supervised_session"] is True
    assert executed_body["temporary_host_process_observed"] is True
    assert executed_body["resident_runtime_candidate_supervised"] is True
    assert executed_body["resident_supervised_runtime"] is False
    assert executed_body["resident_claim_allowed"] is False
    assert executed_body["next_smallest_truthful_gap"] == "resident_supervision_not_persistent"
    assert executed_body["governance"]["execution_authority"] is True
    assert executed_body["governance"]["process_supervision_authority"] is True
    assert executed_body["governance"]["process_restart_authority"] is True
    assert executed_body["governance"]["local_process_launch_authority"] is False
    assert executed_body["governance"]["service_install_authority"] is False
    assert executed_body["governance"]["service_control_authority"] is False
    assert executed_body["governance"]["tray_registration_authority"] is False
    assert executed_body["governance"]["hotkey_registration_authority"] is False
    assert executed_body["governance"]["overlay_control_authority"] is False
    assert executed_body["governance"]["summon_authority"] is False
    assert executed_body["governance"]["memory_write"] is False
    assert executed_body["governance"]["resident_claim_authority"] is False
    assert executed_body["receipt_written"] is True
    receipt = executed_body["receipt"]
    assert receipt["kind"] == "lens.host.supervision.execution.receipt"
    assert receipt["approval_id"] == approval_id
    assert receipt["execution"]["resident_runtime_candidate_supervised"] is True
    assert receipt["execution"]["resident_supervised_runtime"] is False
    assert receipt["resident_claim"]["resident_host_process_claimed"] is False
    receipt_path = data_root / "lens" / "host_supervision_executions" / f"{receipt['receipt_id']}.json"
    assert receipt_path.exists()

    executions = client.get(f"/lens/host/supervision/executions?limit=10&approval_id={approval_id}")
    assert executions.status_code == 200
    executions_body = executions.json()
    assert executions_body["kind"] == "lens.host.supervision.execution_receipts"
    assert executions_body["total"] == 1
    assert executions_body["latest"]["receipt_id"] == receipt["receipt_id"]
    assert executions_body["latest_bounded_supervised_session"] is True
    assert executions_body["latest_resident_runtime_candidate_supervised"] is True
    assert executions_body["latest_next_smallest_truthful_gap"] == "resident_supervision_not_persistent"

    status = client.get("/lens/status?limit=1")
    assert status.status_code == 200
    status_body = status.json()
    next_handoff = status_body["stage6_readiness"]["next_handoff"]
    assert next_handoff["next_smallest_truthful_gap"] == "resident_supervision_not_persistent"
    assert next_handoff["recommended_handoff_source"] == "resident_runtime_candidate_handoff"
    assert next_handoff["resident_runtime_candidate_handoff_observed"] is True
    persistent_plan = status_body["resident_host"]["persistent_supervision_plan"]
    dependencies = {item["id"]: item for item in persistent_plan["enablement_dependency_readback"]}
    assert dependencies["resident_host_process"]["requirement_state"] == ("resident_candidate_observed_not_persistent")
    assert dependencies["resident_host_process"]["blocker"] == "resident_supervision_not_persistent"


def test_lens_host_supervision_execute_starts_and_stops_resident_supervision_lease(
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
    service_config_path = repo_root / "config" / "runtime" / "services" / "lens-host.json"
    service_config = json.loads(service_config_path.read_text(encoding="utf-8"))
    service_config["process_supervision_enabled"] = True
    service_config["persistent_supervision_enabled"] = True
    service_config["supervision_blocked_reason"] = "resident_supervision_prerequisites_pending"
    service_config["blocked_reason"] = "lens_host_persistent_supervision_prerequisites_pending"
    service_config_path.write_text(json.dumps(service_config, indent=2), encoding="utf-8")
    monkeypatch.setenv("FRANCIS_ROOT", str(repo_root))
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_ENV_PROFILE", "dev")
    monkeypatch.setenv("FRANCIS_RUN_MODE", "api")

    import francis.lens.activation as activation_module
    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    pid = os.getpid()

    def fake_resident_supervision_action(*, mode: str) -> dict[str, Any]:
        if mode == "resident_stop":
            host_root = data_root / "runtime" / "lens-host"
            host_root.mkdir(parents=True, exist_ok=True)
            (host_root / "lens-host.pid").unlink(missing_ok=True)
            (host_root / "status.json").write_text(
                json.dumps(
                    {
                        "kind": "lens.host.runtime_state",
                        "status": "resident_stopped",
                        "mode": "resident",
                        "pid": pid,
                        "process_alive": False,
                        "resident": False,
                        "resident_claim_allowed": False,
                        "service_managed": False,
                        "tray_presence": False,
                        "global_hotkey": False,
                        "overlay_window": False,
                        "summon_anywhere": False,
                        "updated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                    }
                ),
                encoding="utf-8",
            )
            _write_lens_host_supervisor_state(
                data_root,
                observed_pid=pid,
                status="resident_supervision_stopped",
                mode="stop_resident",
                host_mode="resident",
                observed_state="resident_stopped",
                resident_supervised_runtime=False,
                process_supervision_authority=True,
                process_restart_authority=False,
                service_control_authority=False,
            )
            return {
                "ok": True,
                "status": "resident_supervision_stopped",
                "returncode": 0,
                "script_mode": "StopResident",
                "script": "scripts/lens-host-supervisor.ps1",
                "runner": {
                    "ok": True,
                    "status": "resident_supervision_stopped",
                    "resident_host_process": False,
                    "resident_supervised_runtime": False,
                    "resident_runtime_candidate_supervised": False,
                    "resident_claim_allowed": False,
                    "next_smallest_truthful_gap": "resident_host_process_missing",
                },
                "blockers": ["resident_host_process_missing", "tray_host_missing"],
            }

        _write_lens_host_runtime_state(data_root, pid=pid, status="resident_running", mode="resident")
        _write_lens_host_supervisor_state(
            data_root,
            observed_pid=pid,
            status="resident_supervising",
            mode="supervise_resident",
            host_mode="resident",
            observed_state="resident_running",
            resident_supervised_runtime=True,
            process_supervision_authority=True,
            process_restart_authority=False,
            service_control_authority=False,
        )
        return {
            "ok": True,
            "status": "resident_supervision_started",
            "returncode": 0,
            "script_mode": "StartResident",
            "script": "scripts/lens-host-supervisor.ps1",
            "runner": {
                "ok": True,
                "status": "resident_supervision_started",
                "bounded_supervised_session": False,
                "temporary_host_process_observed": True,
                "resident_host_process": True,
                "resident_supervised_runtime": True,
                "resident_runtime_candidate_supervised": True,
                "resident_claim_allowed": False,
                "service_managed": False,
                "tray_presence": False,
                "global_hotkey": False,
                "overlay_window": False,
                "summon_anywhere": False,
                "next_smallest_truthful_gap": "summon_tray_presence_blocker_boundary",
            },
            "blockers": [
                "tray_host_missing",
                "global_hotkey_binding_missing",
                "overlay_window_missing",
                "summon_binding_missing",
            ],
        }

    monkeypatch.setattr(
        activation_module,
        "_run_lens_host_resident_supervision_action",
        fake_resident_supervision_action,
    )

    client = TestClient(create_app())
    requested = client.post(
        "/lens/host/supervision/authority/request",
        json={
            "actor": "test.system.write",
            "reason": "operator wants resident host supervision authority",
        },
    )
    assert requested.status_code == 200
    approval_id = str(requested.json()["approval_id"])

    decided = client.post(
        "/approvals/decision",
        json={
            "id": approval_id,
            "action": "approve",
            "actor": "test.approvals.decision",
            "comment": "approved host supervision lease boundary review",
        },
    )
    assert decided.status_code == 200
    assert decided.json()["status"] == "approved"

    grant = client.post(
        "/lens/host/supervision/authority",
        json={
            "approval_id": approval_id,
            "actor": "test.system.write",
            "reason": "operator grants host supervision authority for resident lease",
            "lease_seconds": 600,
        },
    )
    assert grant.status_code == 200
    grant_body = grant.json()
    assert grant_body["status"] == "authority_granted"

    started = client.post(
        "/lens/host/supervision/execute",
        json={
            "approval_id": approval_id,
            "actor": "test.system.write",
            "reason": "start governed live resident host supervision",
            "mode": "resident_start",
        },
    )
    assert started.status_code == 200
    started_body = started.json()
    assert started_body["kind"] == "lens.host.supervision.execution"
    assert started_body["status"] == "resident_supervision_started"
    assert started_body["supervision_mode"] == "resident_start"
    assert started_body["executed"] is True
    assert started_body["resident_host_process"] is True
    assert started_body["resident_supervised_runtime"] is True
    assert started_body["resident_runtime_candidate_supervised"] is True
    assert started_body["resident_claim_allowed"] is False
    assert started_body["stop_command"] == "scripts/lens-host-supervisor.ps1 -Mode StopResident"
    assert started_body["next_smallest_truthful_gap"] == "summon_tray_presence_blocker_boundary"
    assert started_body["governance"]["resident_supervision_lease_execution"] is True
    assert started_body["governance"]["local_process_launch_authority"] is True
    assert started_body["governance"]["service_control_authority"] is False
    assert started_body["governance"]["resident_claim_authority"] is False
    assert started_body["receipt_written"] is True
    start_receipt = started_body["receipt"]
    assert start_receipt["execution"]["supervision_mode"] == "resident_start"
    assert start_receipt["execution"]["resident_host_process"] is True
    assert start_receipt["execution"]["resident_supervised_runtime"] is True
    assert start_receipt["resident_claim"]["resident_host_process_claimed"] is False

    status = client.get("/lens/status?limit=1")
    assert status.status_code == 200
    status_body = status.json()
    persistent_plan = status_body["resident_host"]["persistent_supervision_plan"]
    dependencies = {item["id"]: item for item in persistent_plan["enablement_dependency_readback"]}
    assert dependencies["resident_host_process"]["ready"] is True
    assert dependencies["resident_host_process"]["resident_supervised_runtime"] is True
    assert dependencies["resident_host_process"]["supervision_execution_supervised_runtime_receipt_observed"] is True
    assert persistent_plan["first_missing_required_before_enable"] == "tray_presence"
    next_handoff = status_body["stage6_readiness"]["next_handoff"]
    assert next_handoff["next_smallest_truthful_gap"] == "summon_tray_presence_blocker_boundary"

    stopped = client.post(
        "/lens/host/supervision/execute",
        json={
            "approval_id": approval_id,
            "actor": "test.system.write",
            "reason": "stop governed live resident host supervision",
            "mode": "resident_stop",
        },
    )
    assert stopped.status_code == 200
    stopped_body = stopped.json()
    assert stopped_body["status"] == "resident_supervision_stopped"
    assert stopped_body["supervision_mode"] == "resident_stop"
    assert stopped_body["resident_host_process"] is False
    assert stopped_body["resident_supervised_runtime"] is False
    assert stopped_body["resident_claim_allowed"] is False
    assert stopped_body["governance"]["resident_supervision_lease_execution"] is True
    assert stopped_body["governance"]["service_control_authority"] is False
    assert stopped_body["governance"]["resident_claim_authority"] is False


def test_lens_tray_presence_execute_starts_and_stops_governed_tray_lease(
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
    service_config_path = repo_root / "config" / "runtime" / "services" / "lens-host.json"
    service_config = json.loads(service_config_path.read_text(encoding="utf-8"))
    service_config["process_supervision_enabled"] = True
    service_config["persistent_supervision_enabled"] = True
    service_config["supervision_blocked_reason"] = "resident_supervision_prerequisites_pending"
    service_config["blocked_reason"] = "lens_host_persistent_supervision_prerequisites_pending"
    service_config_path.write_text(json.dumps(service_config, indent=2), encoding="utf-8")
    monkeypatch.setenv("FRANCIS_ROOT", str(repo_root))
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_ENV_PROFILE", "dev")
    monkeypatch.setenv("FRANCIS_RUN_MODE", "api")

    import francis.lens.tray_authority as tray_authority_module
    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    pid = os.getpid()
    _write_lens_host_runtime_state(data_root, pid=pid, status="resident_running", mode="resident")
    _write_lens_host_supervisor_state(
        data_root,
        observed_pid=pid,
        status="resident_supervising",
        mode="supervise_resident",
        host_mode="resident",
        observed_state="resident_running",
        resident_supervised_runtime=True,
        process_supervision_authority=True,
        process_restart_authority=False,
        service_control_authority=False,
    )

    def fake_tray_presence_action(*, mode: str, run_seconds: int) -> dict[str, Any]:
        if mode == "stop":
            runtime_root = data_root / "runtime" / "lens-tray"
            runtime_root.mkdir(parents=True, exist_ok=True)
            (runtime_root / "lens-tray.pid").unlink(missing_ok=True)
            (runtime_root / "status.json").write_text(
                json.dumps(
                    {
                        "kind": "lens.tray.runtime_state",
                        "status": "tray_stopped",
                        "pid": pid,
                        "tray_icon_visible": False,
                        "updated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                        "message": "Francis Lens tray presence stopped by operator command.",
                    }
                ),
                encoding="utf-8",
            )
            return {
                "ok": True,
                "status": "stopped",
                "returncode": 0,
                "script_mode": "Stop",
                "script": "scripts/lens-tray-presence.ps1",
                "runner": {
                    "ok": True,
                    "status": "stopped",
                    "ready": False,
                    "tray_presence": False,
                    "run_seconds": run_seconds,
                },
                "blockers": ["tray_presence_runtime_missing"],
            }

        _write_lens_tray_runtime_state(data_root, pid=pid)
        return {
            "ok": True,
            "status": "started",
            "returncode": 0,
            "script_mode": "Start",
            "script": "scripts/lens-tray-presence.ps1",
            "runner": {
                "ok": True,
                "status": "started",
                "ready": True,
                "tray_presence": True,
                "run_seconds": run_seconds,
                "tray_runtime": {
                    "ready": True,
                    "process_alive": True,
                    "tray_icon_visible": True,
                    "pid": pid,
                },
                "governance": {
                    "execution_authority": False,
                    "tray_registration_authority": True,
                    "tray_icon_authority": True,
                    "local_process_launch_authority": True,
                    "memory_write": False,
                },
            },
            "blockers": [],
        }

    monkeypatch.setattr(
        tray_authority_module,
        "_run_lens_tray_presence_action",
        fake_tray_presence_action,
    )

    client = TestClient(create_app())
    requested = client.post(
        "/lens/tray/authority/request",
        json={
            "actor": "test.system.write",
            "reason": "operator wants tray presence authority",
        },
    )
    assert requested.status_code == 200
    approval_id = str(requested.json()["approval_id"])

    decided = client.post(
        "/approvals/decision",
        json={
            "id": approval_id,
            "action": "approve",
            "actor": "test.approvals.decision",
            "comment": "approved tray presence lease boundary review",
        },
    )
    assert decided.status_code == 200
    assert decided.json()["status"] == "approved"

    grant = client.post(
        "/lens/tray/authority",
        json={
            "approval_id": approval_id,
            "actor": "test.system.write",
            "reason": "operator grants tray presence authority",
            "lease_seconds": 600,
        },
    )
    assert grant.status_code == 200
    grant_body = grant.json()
    assert grant_body["status"] == "authority_granted"
    assert grant_body["tray_presence_authority"] is True
    assert grant_body["receipt_written"] is True
    assert grant_body["governance"]["tray_registration_authority"] is True
    assert grant_body["governance"]["hotkey_registration_authority"] is False
    assert grant_body["governance"]["summon_authority"] is False
    assert grant_body["governance"]["overlay_control_authority"] is False
    assert grant_body["governance"]["memory_write"] is False
    assert grant_body["governance"]["resident_claim_authority"] is False

    started = client.post(
        "/lens/tray/execute",
        json={
            "approval_id": approval_id,
            "actor": "test.system.write",
            "reason": "start governed Lens tray presence",
            "mode": "start",
            "run_seconds": 60,
        },
    )
    assert started.status_code == 200
    started_body = started.json()
    assert started_body["kind"] == "lens.tray.presence.execution"
    assert started_body["status"] == "tray_presence_started"
    assert started_body["executed"] is True
    assert started_body["mode"] == "start"
    assert started_body["tray_presence"] is True
    assert started_body["tray_runtime_ready"] is True
    assert started_body["tray_icon_visible"] is True
    assert started_body["tray_runtime_pid"] == pid
    assert started_body["resident_host_readiness"]["ready"] is True
    assert started_body["resident_host_readiness"]["resident_supervised_runtime"] is True
    assert started_body["stop_command"] == "scripts/lens-tray-presence.ps1 -Mode Stop"
    assert started_body["next_smallest_truthful_gap"] == "os_level_command_palette_binding"
    assert started_body["governance"]["execution_authority"] is True
    assert started_body["governance"]["local_process_launch_authority"] is True
    assert started_body["governance"]["tray_registration_authority"] is True
    assert started_body["governance"]["tray_icon_authority"] is True
    assert started_body["governance"]["hotkey_registration_authority"] is False
    assert started_body["governance"]["summon_authority"] is False
    assert started_body["governance"]["overlay_control_authority"] is False
    assert started_body["governance"]["service_control_authority"] is False
    assert started_body["governance"]["memory_write"] is False
    assert started_body["governance"]["resident_claim_authority"] is False
    assert started_body["receipt_written"] is True
    start_receipt = started_body["receipt"]
    assert start_receipt["execution"]["mode"] == "start"
    assert start_receipt["execution"]["tray_presence"] is True
    assert start_receipt["execution"]["tray_runtime_ready"] is True
    assert start_receipt["resident_claim"]["resident_host_process_claimed"] is False

    status = client.get("/lens/status?limit=1")
    assert status.status_code == 200
    status_body = status.json()
    persistent_plan = status_body["resident_host"]["persistent_supervision_plan"]
    dependencies = {item["id"]: item for item in persistent_plan["enablement_dependency_readback"]}
    assert dependencies["resident_host_process"]["ready"] is True
    assert dependencies["tray_presence"]["ready"] is True
    assert dependencies["tray_presence"]["tray_presence_source"] == "live_runtime_readback"
    assert persistent_plan["missing_required_before_enable"] == [
        "global_hotkey_binding",
        "overlay_window",
        "summon_binding",
    ]
    next_handoff = persistent_plan["first_missing_requirement_handoff"]
    assert next_handoff["id"] == "global_hotkey_binding"
    assert next_handoff["next_smallest_truthful_gap"] == "os_level_command_palette_binding"

    stopped = client.post(
        "/lens/tray/execute",
        json={
            "approval_id": approval_id,
            "actor": "test.system.write",
            "reason": "stop governed Lens tray presence",
            "mode": "stop",
        },
    )
    assert stopped.status_code == 200
    stopped_body = stopped.json()
    assert stopped_body["status"] == "tray_presence_stopped"
    assert stopped_body["mode"] == "stop"
    assert stopped_body["executed"] is True
    assert stopped_body["tray_presence"] is False
    assert stopped_body["tray_runtime_ready"] is False
    assert stopped_body["governance"]["execution_authority"] is True
    assert stopped_body["governance"]["local_process_launch_authority"] is False
    assert stopped_body["governance"]["service_control_authority"] is False
    assert stopped_body["governance"]["hotkey_registration_authority"] is False
    assert stopped_body["governance"]["summon_authority"] is False
    assert stopped_body["governance"]["overlay_control_authority"] is False
    assert stopped_body["governance"]["memory_write"] is False
    assert stopped_body["governance"]["resident_claim_authority"] is False
    assert stopped_body["receipt_written"] is True


def test_lens_overlay_execute_starts_and_stops_governed_overlay_lease(
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
    service_config_path = repo_root / "config" / "runtime" / "services" / "lens-host.json"
    service_config = json.loads(service_config_path.read_text(encoding="utf-8"))
    service_config["process_supervision_enabled"] = True
    service_config["persistent_supervision_enabled"] = True
    service_config["supervision_blocked_reason"] = "resident_supervision_prerequisites_pending"
    service_config["blocked_reason"] = "lens_host_persistent_supervision_prerequisites_pending"
    service_config_path.write_text(json.dumps(service_config, indent=2), encoding="utf-8")
    monkeypatch.setenv("FRANCIS_ROOT", str(repo_root))
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_ENV_PROFILE", "dev")
    monkeypatch.setenv("FRANCIS_RUN_MODE", "api")

    import francis.lens.overlay_authority as overlay_authority_module
    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    pid = os.getpid()
    _write_lens_host_runtime_state(data_root, pid=pid, status="resident_running", mode="resident")
    _write_lens_host_supervisor_state(
        data_root,
        observed_pid=pid,
        status="resident_supervising",
        mode="supervise_resident",
        host_mode="resident",
        observed_state="resident_running",
        resident_supervised_runtime=True,
        process_supervision_authority=True,
    )
    _write_lens_tray_runtime_state(data_root, pid=pid)
    _write_lens_hotkey_runtime_state(data_root, pid=pid)

    def fake_overlay_action(*, mode: str, run_seconds: int) -> dict[str, Any]:
        assert run_seconds == 1
        runtime_root = data_root / "runtime" / "lens-overlay"
        runtime_root.mkdir(parents=True, exist_ok=True)
        if mode == "stop":
            (runtime_root / "lens-overlay.pid").unlink(missing_ok=True)
            (runtime_root / "status.json").write_text(
                json.dumps(
                    {
                        "kind": "lens.overlay.runtime_state",
                        "status": "overlay_stopped",
                        "pid": pid,
                        "overlay_name": "Francis Lens Overlay",
                        "overlay_scope": "user_session",
                        "overlay_window_visible": False,
                        "always_on_top": False,
                        "updated_at": "2026-05-17T21:00:00Z",
                    }
                ),
                encoding="utf-8",
            )
            return {
                "ok": True,
                "status": "stopped",
                "returncode": 0,
                "script_mode": "Stop",
                "script": "scripts/lens-overlay-window.ps1",
                "runner": {
                    "ok": True,
                    "status": "stopped",
                    "ready": False,
                    "overlay_window": False,
                },
                "blockers": ["overlay_window_runtime_missing"],
            }
        _write_lens_overlay_runtime_state(data_root, pid=pid)
        return {
            "ok": True,
            "status": "started",
            "returncode": 0,
            "script_mode": "Start",
            "script": "scripts/lens-overlay-window.ps1",
            "runner": {
                "ok": True,
                "status": "started",
                "ready": True,
                "overlay_window": True,
                "next_smallest_truthful_gap": "overlay_authority_and_config",
            },
            "blockers": [],
        }

    monkeypatch.setattr(
        overlay_authority_module,
        "_run_lens_overlay_window_action",
        fake_overlay_action,
    )

    client = TestClient(create_app())
    requested = client.post(
        "/lens/overlay/authority/request",
        json={
            "actor": "test.system.write",
            "reason": "operator wants overlay window authority",
        },
    )
    assert requested.status_code == 200
    approval_id = str(requested.json()["approval_id"])
    decided = client.post(
        "/approvals/decision",
        json={
            "id": approval_id,
            "action": "approve",
            "actor": "test.approvals.decision",
            "comment": "approved overlay window authority",
        },
    )
    assert decided.status_code == 200
    assert decided.json()["status"] == "approved"
    grant = client.post(
        "/lens/overlay/authority",
        json={
            "approval_id": approval_id,
            "actor": "test.system.write",
            "reason": "operator grants bounded overlay window authority",
            "lease_seconds": 600,
        },
    )
    assert grant.status_code == 200
    grant_body = grant.json()
    assert grant_body["status"] == "authority_granted"
    assert grant_body["overlay_window_authority"] is True
    assert grant_body["receipt_written"] is True
    assert grant_body["governance"]["overlay_window_execution_authority"] is True
    assert grant_body["governance"]["overlay_control_authority"] is True
    assert grant_body["governance"]["window_management_authority"] is True
    assert grant_body["governance"]["local_process_launch_authority"] is True
    assert grant_body["governance"]["summon_authority"] is False
    assert grant_body["governance"]["memory_write"] is False

    started = client.post(
        "/lens/overlay/execute",
        json={
            "approval_id": approval_id,
            "actor": "test.system.write",
            "reason": "start governed Lens overlay window",
            "mode": "start",
            "run_seconds": 1,
        },
    )
    assert started.status_code == 200
    started_body = started.json()
    assert started_body["kind"] == "lens.overlay.window.execution"
    assert started_body["status"] == "overlay_window_started"
    assert started_body["executed"] is True
    assert started_body["mode"] == "start"
    assert started_body["overlay_window"] is True
    assert started_body["overlay_runtime_ready"] is True
    assert started_body["overlay_window_visible"] is True
    assert started_body["always_on_top"] is True
    assert started_body["overlay_runtime_pid"] == pid
    assert started_body["resident_claim_allowed"] is False
    assert started_body["stop_command"] == "scripts/lens-overlay-window.ps1 -Mode Stop"
    assert started_body["next_smallest_truthful_gap"] == "summon_anywhere_blockers"
    assert started_body["governance"]["execution_authority"] is True
    assert started_body["governance"]["overlay_window_execution_authority"] is True
    assert started_body["governance"]["overlay_control_authority"] is True
    assert started_body["governance"]["window_management_authority"] is True
    assert started_body["governance"]["local_process_launch_authority"] is True
    assert started_body["governance"]["hotkey_registration_authority"] is False
    assert started_body["governance"]["tray_registration_authority"] is False
    assert started_body["governance"]["summon_authority"] is False
    assert started_body["governance"]["capture_authority"] is False
    assert started_body["governance"]["new_sensing_authority"] is False
    assert started_body["governance"]["memory_write"] is False
    assert started_body["governance"]["resident_claim_authority"] is False
    assert started_body["receipt_written"] is True
    receipt = started_body["receipt"]
    assert receipt["kind"] == "lens.overlay.window.execution_receipt"
    assert receipt["execution"]["mode"] == "start"
    assert receipt["execution"]["overlay_window"] is True
    assert receipt["execution"]["overlay_runtime_ready"] is True
    assert receipt["execution"]["overlay_window_visible"] is True
    assert receipt["execution"]["always_on_top"] is True
    assert receipt["resident_claim"]["resident_host_process_claimed"] is False

    executions = client.get("/lens/overlay/executions?limit=10")
    assert executions.status_code == 200
    executions_body = executions.json()
    assert executions_body["kind"] == "lens.overlay.window.execution_receipts"
    assert executions_body["status"] == "readback_ready"
    assert executions_body["total"] == 1
    assert executions_body["latest_overlay_window"] is True
    assert executions_body["latest_next_smallest_truthful_gap"] == "summon_anywhere_blockers"

    status = client.get("/lens/status?limit=1")
    assert status.status_code == 200
    persistent_plan = status.json()["resident_host"]["persistent_supervision_plan"]
    assert persistent_plan["missing_required_before_enable"] == ["summon_binding"]
    handoff = persistent_plan["first_missing_requirement_handoff"]
    assert handoff["id"] == "summon_binding"
    assert handoff["next_smallest_truthful_gap"] == "summon_anywhere_blockers"

    stopped = client.post(
        "/lens/overlay/execute",
        json={
            "approval_id": approval_id,
            "actor": "test.system.write",
            "reason": "stop governed Lens overlay window",
            "mode": "stop",
            "run_seconds": 1,
        },
    )
    assert stopped.status_code == 200
    stopped_body = stopped.json()
    assert stopped_body["status"] == "overlay_window_stopped"
    assert stopped_body["mode"] == "stop"
    assert stopped_body["executed"] is True
    assert stopped_body["overlay_window"] is False
    assert stopped_body["overlay_runtime_ready"] is False
    assert stopped_body["governance"]["execution_authority"] is True
    assert stopped_body["governance"]["local_process_launch_authority"] is False
    assert stopped_body["governance"]["overlay_control_authority"] is True
    assert stopped_body["governance"]["window_management_authority"] is True
    assert stopped_body["governance"]["memory_write"] is False
    assert stopped_body["receipt_written"] is True


def test_lens_summon_execute_records_bounded_handoff_without_summon_anywhere_claim(
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
    service_config_path = repo_root / "config" / "runtime" / "services" / "lens-host.json"
    service_config = json.loads(service_config_path.read_text(encoding="utf-8"))
    service_config["process_supervision_enabled"] = True
    service_config["persistent_supervision_enabled"] = True
    service_config["supervision_blocked_reason"] = "resident_supervision_prerequisites_pending"
    service_config["blocked_reason"] = "lens_host_persistent_supervision_prerequisites_pending"
    service_config_path.write_text(json.dumps(service_config, indent=2), encoding="utf-8")
    monkeypatch.setenv("FRANCIS_ROOT", str(repo_root))
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_ENV_PROFILE", "dev")
    monkeypatch.setenv("FRANCIS_RUN_MODE", "api")

    import francis.lens.summon_authority as summon_authority_module
    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    pid = os.getpid()
    _write_lens_host_runtime_state(data_root, pid=pid, status="resident_running", mode="resident")
    _write_lens_host_supervisor_state(
        data_root,
        observed_pid=pid,
        status="resident_supervising",
        mode="supervise_resident",
        host_mode="resident",
        observed_state="resident_running",
        resident_supervised_runtime=True,
        process_supervision_authority=True,
    )
    _write_lens_tray_runtime_state(data_root, pid=pid)
    _write_lens_hotkey_runtime_state(data_root, pid=pid)
    _write_lens_overlay_runtime_state(data_root, pid=pid)

    def fake_summon_action(*, mode: str, run_seconds: int, allow_launch: bool) -> dict[str, Any]:
        assert mode == "launch"
        assert run_seconds == 1
        assert allow_launch is False
        return {
            "ok": True,
            "status": "handoff_completed",
            "returncode": 0,
            "script_mode": "Launch",
            "script": "scripts/lens-summon-action.ps1",
            "runner": {
                "ok": True,
                "kind": "lens.summon.action",
                "status": "handoff_completed",
                "mode": "launch",
                "preflight_ready": True,
                "execution_attempted": True,
                "handoff_attempted": True,
                "launch_attempted": True,
                "allow_launch": False,
                "bounded_handoff": {
                    "status": "local_open_ready",
                    "exit_code": 0,
                    "json_parsed": True,
                    "payload": {
                        "kind": "lens.summon.local_launcher",
                        "status": "local_open_ready",
                        "local_binding_ready": True,
                        "summon_binding_target_ready": True,
                        "local_summon_available": True,
                        "os_level_summon": False,
                        "summon_anywhere": False,
                        "global_hotkey": "Ctrl+Alt+Space",
                        "binding_scope": "global",
                        "local_open_target_url": "http://127.0.0.1:5173/?lens=command-palette",
                        "opened": False,
                        "no_launch": True,
                    },
                },
                "next_smallest_truthful_gap": "summon_anywhere_runtime_readback",
                "governance": {
                    "execution_authority": True,
                    "approval_decision_authority": False,
                    "memory_write": False,
                    "summon_authority": True,
                    "hotkey_registration_authority": False,
                    "local_process_launch_authority": False,
                    "mutation_authority_granted": False,
                },
            },
            "blockers": [],
        }

    monkeypatch.setattr(
        summon_authority_module,
        "_run_lens_summon_action",
        fake_summon_action,
    )

    client = TestClient(create_app())
    requested = client.post(
        "/lens/summon/authority/request",
        json={
            "actor": "test.system.write",
            "reason": "operator wants bounded summon action authority",
        },
    )
    assert requested.status_code == 200
    approval_id = str(requested.json()["approval_id"])
    decided = client.post(
        "/approvals/decision",
        json={
            "id": approval_id,
            "action": "approve",
            "actor": "test.approvals.decision",
            "comment": "approved summon action authority",
        },
    )
    assert decided.status_code == 200
    assert decided.json()["status"] == "approved"
    grant = client.post(
        "/lens/summon/authority",
        json={
            "approval_id": approval_id,
            "actor": "test.system.write",
            "reason": "operator grants bounded summon action authority",
            "lease_seconds": 600,
        },
    )
    assert grant.status_code == 200
    grant_body = grant.json()
    assert grant_body["status"] == "authority_granted"
    assert grant_body["summon_action_authority"] is True
    assert grant_body["receipt_written"] is True
    assert grant_body["governance"]["summon_execution_authority"] is True
    assert grant_body["governance"]["bounded_local_open_handoff_authority"] is True
    assert grant_body["governance"]["summon_authority"] is True
    assert grant_body["governance"]["summon_anywhere_authority"] is False
    assert grant_body["governance"]["os_level_summon_authority"] is False
    assert grant_body["governance"]["memory_write"] is False

    executed = client.post(
        "/lens/summon/execute",
        json={
            "approval_id": approval_id,
            "actor": "test.system.write",
            "reason": "record bounded summon local-open handoff",
            "mode": "launch",
            "run_seconds": 1,
            "allow_launch": False,
        },
    )
    assert executed.status_code == 200
    executed_body = executed.json()
    assert executed_body["kind"] == "lens.summon.action.execution"
    assert executed_body["status"] == "summon_binding_observed"
    assert executed_body["executed"] is True
    assert executed_body["summon_binding"] is True
    assert executed_body["summon_runtime_ready"] is True
    assert executed_body["bounded_handoff_ready"] is True
    assert executed_body["local_open_ready"] is True
    assert executed_body["opened"] is False
    assert executed_body["no_launch"] is True
    assert executed_body["allow_launch"] is False
    assert executed_body["summon_anywhere"] is False
    assert executed_body["os_level_summon"] is False
    assert executed_body["next_smallest_truthful_gap"] == "summon_anywhere_runtime_readback"
    assert executed_body["governance"]["execution_authority"] is True
    assert executed_body["governance"]["summon_execution_authority"] is True
    assert executed_body["governance"]["bounded_local_open_handoff_authority"] is True
    assert executed_body["governance"]["summon_authority"] is True
    assert executed_body["governance"]["summon_anywhere_authority"] is False
    assert executed_body["governance"]["os_level_summon_authority"] is False
    assert executed_body["governance"]["local_process_launch_authority"] is False
    assert executed_body["governance"]["hotkey_registration_authority"] is False
    assert executed_body["governance"]["overlay_control_authority"] is False
    assert executed_body["governance"]["memory_write"] is False
    assert executed_body["governance"]["resident_claim_authority"] is False
    assert executed_body["receipt_written"] is True
    receipt = executed_body["receipt"]
    assert receipt["kind"] == "lens.summon.action.execution_receipt"
    assert receipt["execution"]["summon_binding"] is True
    assert receipt["execution"]["bounded_handoff_ready"] is True
    assert receipt["execution"]["summon_anywhere"] is False
    assert receipt["execution"]["os_level_summon"] is False

    runtime_state_path = data_root / "runtime" / "lens-summon" / "status.json"
    runtime_state = json.loads(runtime_state_path.read_text(encoding="utf-8"))
    assert runtime_state["kind"] == "lens.summon.runtime_state"
    assert runtime_state["status"] == "summon_binding_observed"
    assert runtime_state["bounded_handoff_ready"] is True
    assert runtime_state["local_open_ready"] is True
    assert runtime_state["opened"] is False
    assert runtime_state["no_launch"] is True
    assert runtime_state["summon_anywhere"] is False

    executions = client.get("/lens/summon/executions?limit=10")
    assert executions.status_code == 200
    executions_body = executions.json()
    assert executions_body["kind"] == "lens.summon.action.execution_receipts"
    assert executions_body["status"] == "readback_ready"
    assert executions_body["total"] == 1
    assert executions_body["latest_summon_binding"] is True
    assert executions_body["latest_summon_anywhere"] is False
    assert executions_body["latest_next_smallest_truthful_gap"] == "summon_anywhere_runtime_readback"

    summon_readiness = client.get("/lens/summon/readiness")
    assert summon_readiness.status_code == 200
    summon_readiness_body = summon_readiness.json()
    assert summon_readiness_body["ready"] is False
    assert summon_readiness_body["summon_binding_ready"] is True
    assert summon_readiness_body["summon_runtime_ready"] is True
    assert summon_readiness_body["summon_runtime_bounded_handoff_ready"] is True
    assert summon_readiness_body["summon_anywhere"] is False
    assert summon_readiness_body["blocker_groups"]["summon_binding"] == []
    assert "summon_anywhere_runtime_readback" in summon_readiness_body["blocker_groups"]["summon_anywhere"]

    status = client.get("/lens/status?limit=1")
    assert status.status_code == 200
    persistent_plan = status.json()["resident_host"]["persistent_supervision_plan"]
    assert persistent_plan["missing_required_before_enable"] == []
    assert persistent_plan["required_before_enable_ready"] is True
    dependencies = {item["id"]: item for item in persistent_plan["enablement_dependency_readback"]}
    assert dependencies["summon_binding"]["ready"] is True
    assert dependencies["summon_binding"]["summon_runtime_ready"] is True
    assert dependencies["summon_binding"]["summon_presence_source"] == "live_runtime_readback"
    assert dependencies["summon_binding"]["summon_runtime_bounded_handoff_ready"] is True


def test_lens_resident_runtime_execute_starts_supervised_resident_host_lease(
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
    service_config_path = repo_root / "config" / "runtime" / "services" / "lens-host.json"
    service_config = json.loads(service_config_path.read_text(encoding="utf-8"))
    service_config["process_supervision_enabled"] = True
    service_config["persistent_supervision_enabled"] = True
    service_config["supervision_blocked_reason"] = "resident_supervision_prerequisites_pending"
    service_config["blocked_reason"] = "lens_host_persistent_supervision_prerequisites_pending"
    service_config_path.write_text(json.dumps(service_config, indent=2), encoding="utf-8")
    monkeypatch.setenv("FRANCIS_ROOT", str(repo_root))
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_ENV_PROFILE", "dev")
    monkeypatch.setenv("FRANCIS_RUN_MODE", "api")

    import francis.lens.activation as activation_module
    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    pid = os.getpid()

    def fake_resident_supervision_action(*, mode: str) -> dict[str, Any]:
        assert mode == "resident_start"
        _write_lens_host_runtime_state(data_root, pid=pid, status="resident_running", mode="resident")
        _write_lens_host_supervisor_state(
            data_root,
            observed_pid=pid,
            status="resident_supervising",
            mode="supervise_resident",
            host_mode="resident",
            observed_state="resident_running",
            resident_supervised_runtime=True,
            process_supervision_authority=True,
            process_restart_authority=False,
            service_control_authority=False,
        )
        return {
            "ok": True,
            "status": "resident_supervision_started",
            "returncode": 0,
            "script_mode": "StartResident",
            "script": "scripts/lens-host-supervisor.ps1",
            "runner": {
                "ok": True,
                "status": "resident_supervision_started",
                "bounded_supervised_session": False,
                "temporary_host_process_observed": True,
                "resident_host_process": True,
                "resident_supervised_runtime": True,
                "resident_runtime_candidate_supervised": True,
                "resident_claim_allowed": False,
                "next_smallest_truthful_gap": "summon_tray_presence_blocker_boundary",
            },
            "blockers": [
                "tray_host_missing",
                "global_hotkey_binding_missing",
                "overlay_window_missing",
                "summon_binding_missing",
            ],
        }

    monkeypatch.setattr(
        activation_module,
        "_run_lens_host_resident_supervision_action",
        fake_resident_supervision_action,
    )

    client = TestClient(create_app())
    host_requested = client.post(
        "/lens/host/supervision/authority/request",
        json={
            "actor": "test.system.write",
            "reason": "operator wants bounded host supervision authority",
        },
    )
    assert host_requested.status_code == 200
    host_approval_id = str(host_requested.json()["approval_id"])
    host_decided = client.post(
        "/approvals/decision",
        json={
            "id": host_approval_id,
            "action": "approve",
            "actor": "test.approvals.decision",
            "comment": "approved host supervision execution boundary review",
        },
    )
    assert host_decided.status_code == 200
    assert host_decided.json()["status"] == "approved"
    host_grant = client.post(
        "/lens/host/supervision/authority",
        json={
            "approval_id": host_approval_id,
            "actor": "test.system.write",
            "reason": "operator grants host supervision authority for bounded execution",
            "lease_seconds": 600,
        },
    )
    assert host_grant.status_code == 200
    assert host_grant.json()["status"] == "authority_granted"

    runtime_requested = client.post(
        "/lens/resident-runtime/authority-grant/request",
        json={
            "actor": "test.system.write",
            "reason": "operator wants resident runtime execution authority",
        },
    )
    assert runtime_requested.status_code == 200
    runtime_approval_id = str(runtime_requested.json()["approval_id"])
    runtime_decided = client.post(
        "/approvals/decision",
        json={
            "id": runtime_approval_id,
            "action": "approve",
            "actor": "test.approvals.decision",
            "comment": "approved resident runtime execution boundary review",
        },
    )
    assert runtime_decided.status_code == 200
    assert runtime_decided.json()["status"] == "approved"
    runtime_grant = client.post(
        "/lens/resident-runtime/authority-grant",
        json={
            "approval_id": runtime_approval_id,
            "actor": "test.system.write",
            "reason": "operator grants resident runtime execution authority",
            "lease_seconds": 600,
        },
    )
    assert runtime_grant.status_code == 200
    assert runtime_grant.json()["status"] == "authority_granted"

    plan = client.get(f"/lens/resident-runtime/plan?approval_id={runtime_approval_id}&actor=test.system.write")
    assert plan.status_code == 200
    plan_body = plan.json()
    assert plan_body["bounded_resident_candidate_ready"] is True
    assert plan_body["host_supervision_authority"] is True
    assert plan_body["process_supervision_authority"] is True
    assert plan_body["process_restart_authority"] is True
    assert plan_body["runtime_ready"] is False
    assert plan_body["resident_claim_allowed"] is False
    plan_steps = {step["id"]: step for step in plan_body["plan"]["steps"]}
    assert plan_steps["activate_supervised_resident_host"]["status"] == "ready"
    assert plan_body["plan"]["would_launch_process"] is True
    assert plan_body["plan"]["would_supervise_process"] is True
    assert plan_body["plan"]["would_register_tray"] is False
    assert plan_body["plan"]["would_register_hotkey"] is False
    assert plan_body["plan"]["would_open_overlay"] is False
    assert plan_body["plan"]["would_claim_resident"] is False

    executed = client.post(
        "/lens/resident-runtime/execute",
        json={
            "approval_id": runtime_approval_id,
            "actor": "test.system.write",
            "reason": "prove resident runtime starts supervised resident host lease",
            "run_seconds": 1,
        },
    )
    assert executed.status_code == 200
    executed_body = executed.json()
    assert executed_body["kind"] == "lens.resident_runtime.activation.execution"
    assert executed_body["status"] == "resident_supervision_started"
    assert executed_body["approval_id"] == runtime_approval_id
    assert executed_body["host_supervision_approval_id"] == host_approval_id
    assert executed_body["executed"] is True
    assert executed_body["bounded_resident_candidate_ready"] is True
    assert executed_body["supervised_resident_host_ready"] is True
    assert executed_body["resident_supervision_lease_started"] is True
    assert executed_body["resident_host_process"] is True
    assert executed_body["stop_command"] == "scripts/lens-host-supervisor.ps1 -Mode StopResident"
    assert executed_body["bounded_supervised_session"] is False
    assert executed_body["temporary_host_process_observed"] is True
    assert executed_body["resident_runtime_candidate_supervised"] is True
    assert executed_body["resident_supervised_runtime"] is True
    assert executed_body["resident_claim_allowed"] is False
    assert executed_body["next_smallest_truthful_gap"] == "summon_tray_presence_blocker_boundary"
    assert executed_body["host_supervision_authority"]["process_supervision_authority"] is True
    assert executed_body["host_supervision_authority"]["process_restart_authority"] is True
    assert executed_body["governance"]["gate"] == "lens_resident_runtime_activation_execution"
    assert executed_body["governance"]["execution_authority"] is True
    assert executed_body["governance"]["resident_runtime_execution_authority"] is True
    assert executed_body["governance"]["resident_supervision_lease_execution"] is True
    assert executed_body["governance"]["local_process_launch_authority"] is True
    assert executed_body["governance"]["bounded_supervision_process_launch_authority"] is False
    assert executed_body["governance"]["process_supervision_authority"] is True
    assert executed_body["governance"]["process_restart_authority"] is False
    assert executed_body["governance"]["service_install_authority"] is False
    assert executed_body["governance"]["service_control_authority"] is False
    assert executed_body["governance"]["tray_registration_authority"] is False
    assert executed_body["governance"]["hotkey_registration_authority"] is False
    assert executed_body["governance"]["overlay_control_authority"] is False
    assert executed_body["governance"]["summon_authority"] is False
    assert executed_body["governance"]["memory_write"] is False
    assert executed_body["governance"]["resident_claim_authority"] is False
    assert executed_body["receipt_written"] is True
    receipt = executed_body["receipt"]
    assert receipt["kind"] == "lens.host.supervision.execution.receipt"
    assert receipt["route"] == "/lens/resident-runtime/execute"
    assert receipt["approval_id"] == host_approval_id
    assert receipt["execution"]["supervision_mode"] == "resident_start"
    assert receipt["execution"]["resident_runtime_candidate_supervised"] is True
    assert receipt["execution"]["resident_supervised_runtime"] is True
    assert receipt["execution"]["resident_host_process"] is True
    assert receipt["resident_claim"]["resident_host_process_claimed"] is False
    receipt_path = data_root / "lens" / "host_supervision_executions" / f"{receipt['receipt_id']}.json"
    assert receipt_path.exists()

    executions = client.get("/lens/resident-runtime/executions?limit=10")
    assert executions.status_code == 200
    executions_body = executions.json()
    assert executions_body["kind"] == "lens.resident_runtime.activation.execution_receipts"
    assert executions_body["status"] == "readback_ready"
    assert executions_body["route"] == "/lens/resident-runtime/executions"
    assert executions_body["execute_route"] == "/lens/resident-runtime/execute"
    assert executions_body["host_supervision_executions_route"] == "/lens/host/supervision/executions"
    assert executions_body["total"] == 1
    assert executions_body["latest_receipt_id"] == receipt["receipt_id"]
    assert executions_body["latest_supervision_mode"] == "resident_start"
    assert executions_body["latest_resident_host_process"] is True
    assert executions_body["latest_resident_supervised_runtime"] is True
    assert executions_body["latest_stop_command"] == "scripts/lens-host-supervisor.ps1 -Mode StopResident"
    assert executions_body["latest_next_smallest_truthful_gap"] == "summon_tray_presence_blocker_boundary"
    assert executions_body["resident_supervised_runtime_receipt_observed"] is True
    assert executions_body["resident_claim_allowed"] is False
    assert executions_body["governance"]["read_only_contract"] is True
    assert executions_body["governance"]["resident_runtime_execution_readback"] is True
    assert executions_body["governance"]["host_supervision_receipt_projection"] is True
    assert executions_body["governance"]["execution_authority"] is False
    assert executions_body["governance"]["resident_claim_authority"] is False
    assert executions_body["governance"]["memory_write"] is False

    status = client.get("/lens/status?limit=1")
    assert status.status_code == 200
    status_body = status.json()
    status_executions = status_body["resident_host"]["resident_runtime_execution_receipts"]
    assert status_executions["status"] == "readback_ready"
    assert status_executions["total"] == 1
    assert status_executions["latest_receipt_id"] == receipt["receipt_id"]
    assert status_executions["latest_supervision_mode"] == "resident_start"
    assert status_executions["resident_supervised_runtime_receipt_observed"] is True
    assert status_body["resident_runtime_execution_receipts"]["latest_receipt_id"] == receipt["receipt_id"]
    status_execution_receipts_criterion = _criterion(status_body, "resident_runtime_execution_receipt_readback")
    assert status_execution_receipts_criterion["status"] == "readback_ready"
    assert status_execution_receipts_criterion["receipt_count"] == 1
    assert status_execution_receipts_criterion["latest_receipt_id"] == receipt["receipt_id"]
    assert status_execution_receipts_criterion["latest_supervision_mode"] == "resident_start"
    assert status_execution_receipts_criterion["latest_resident_host_process"] is True
    assert status_execution_receipts_criterion["latest_resident_supervised_runtime"] is True
    assert status_execution_receipts_criterion["resident_supervised_runtime_receipt_observed"] is True
    assert status_execution_receipts_criterion["resident_claim_allowed"] is False
    assert status_execution_receipts_criterion["execution_authority"] is False
    assert status_execution_receipts_criterion["approval_decision_authority"] is False
    assert status_execution_receipts_criterion["process_supervision_authority"] is False
    assert status_execution_receipts_criterion["service_control_authority"] is False
    assert status_execution_receipts_criterion["memory_write"] is False
    assert status_execution_receipts_criterion["resident_claim_authority"] is False
    next_handoff = status_body["stage6_readiness"]["next_handoff"]
    assert next_handoff["next_smallest_truthful_gap"] == "summon_tray_presence_blocker_boundary"
    assert next_handoff["persistent_supervision_first_missing_required_before_enable"] == "tray_presence"


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
    assert authority_grant_readiness_body["operator_surface_readback_ready"] is True
    assert authority_grant_readiness_body["first_blocked_requirement"] == "resident_supervision_gate"
    readiness_handoff = authority_grant_readiness_body["first_blocked_requirement_handoff"]
    assert readiness_handoff["id"] == "resident_supervision_gate"
    assert readiness_handoff["route"] == "/lens/host/supervision"
    assert readiness_handoff["host_route"] == "/lens/host"
    assert readiness_handoff["manifest_route"] == "/lens/host/manifest"
    assert readiness_handoff["supervision_route"] == "/lens/host/supervision"
    assert readiness_handoff["readiness_route"] == "/lens/resident-runtime/authority-grant/readiness"
    assert (
        readiness_handoff["next_step"] == "resolve_resident_host_supervision_gate_blockers_before_runtime_authority_use"
    )
    assert readiness_handoff["authority_required"] == "process_supervision_and_service_control"
    assert readiness_handoff["authority_granted"] is False
    assert readiness_handoff["would_execute"] is False
    assert readiness_handoff["would_mutate"] is False
    assert "resident_host_process_missing" in readiness_handoff["blockers"]
    assert "summon_binding_missing" in readiness_handoff["blockers"]
    assert (
        authority_grant_readiness_body["next_smallest_truthful_gap"]
        == "resolve_resident_host_supervision_gate_blockers_before_runtime_authority_use"
    )
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
    assert (
        resident_surface_activation_body["execution"]["runtime_authority_grant_readiness_route"]
        == "/lens/resident-runtime/authority-grant/readiness"
    )
    assert resident_surface_activation_body["execution"]["runtime_authority_grant_readiness_status"] == "blocked"
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
    surface_authority_readiness = resident_surface_activation_body["resident_runtime_authority_grant_readiness"]
    assert surface_authority_readiness["status"] == "blocked"
    assert surface_authority_readiness["operator_surface_readback_ready"] is True
    assert surface_authority_readiness["authority_granted"] is True
    assert surface_authority_readiness["first_blocked_requirement"] == "resident_supervision_gate"
    assert resident_surface_activation_body["resident_runtime_authority_grant_handoff_observed"] is True
    assert (
        resident_surface_activation_body["resident_runtime_authority_grant_handoff"]["next_step"]
        == "resolve_resident_host_supervision_gate_blockers_before_runtime_authority_use"
    )
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
    assert resident_surface_activation_body["governance"]["resident_runtime_authority_grant_readiness_readback"] is True
    assert resident_surface_activation_body["governance"]["resident_runtime_authority_grant_handoff_readback"] is True

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
