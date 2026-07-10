from __future__ import annotations

import json
import os
import shutil
import subprocess
import re
from pathlib import Path

import pytest


def _powershell() -> str:
    exe = shutil.which("powershell") or shutil.which("pwsh")
    if not exe:
        pytest.skip("PowerShell is not available")
    return exe


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _normalized_contains(source: str, snippet: str) -> bool:
    return re.sub(r"\s+", " ", source).find(re.sub(r"\s+", " ", snippet)) >= 0


def _write_hotkey_config_override(tmp_path: Path, *, command_hotkeys: list[dict[str, object]]) -> Path:
    config = json.loads((_repo_root() / "config" / "runtime" / "lens" / "summon.json").read_text(encoding="utf-8"))
    config["command_hotkeys"] = command_hotkeys
    path = tmp_path / "summon.override.json"
    path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    return path


def test_lens_hotkey_binding_start_timeout_stops_started_child_process() -> None:
    source = (_repo_root() / "scripts" / "lens-hotkey-binding.ps1").read_text(encoding="utf-8")

    assert "-PassThru" in source
    assert "Stop-Process -Id $StartedProcess.Id -Force" in source
    assert "started_process_stopped" in source


def test_lens_hotkey_binding_start_reports_terminal_child_failure() -> None:
    source = (_repo_root() / "scripts" / "lens-hotkey-binding.ps1").read_text(encoding="utf-8")

    assert "@('failed', 'unsupported', 'hotkey_already_owned') -contains [string]$Readback.runtime_status" in source
    assert "$Payload.error = if ($ChildRuntimeStatus -eq 'unsupported')" in source
    assert "$Payload.child_runtime_status = $ChildRuntimeStatus" in source
    assert "$Payload.child_runtime_status_message = [string]$Readback.runtime_status_message" in source
    assert "$Payload.hotkey_already_owned = $HotkeyAlreadyOwned" in source
    assert "$Payload.registration_failure = $Readback.registration_failure" in source


def test_lens_hotkey_binding_registerhotkey_failure_writes_owned_blocked_receipt() -> None:
    source = (_repo_root() / "scripts" / "lens-hotkey-binding.ps1").read_text(encoding="utf-8")

    assert "RegisterHotKey failed for global hotkey" in source
    assert "RegisterHotKey failed for command hotkey" in source
    assert "-Status 'hotkey_already_owned'" in source
    assert "-Error 'hotkey_already_owned' -Blocker 'hotkey_already_owned'" in source
    assert "win32_error = $Win32Error" in source
    assert "registration_failure = if (-not [string]::IsNullOrWhiteSpace($Error))" in source


def test_lens_hotkey_binding_run_uses_hidden_message_loop_form() -> None:
    source = (_repo_root() / "scripts" / "lens-hotkey-binding.ps1").read_text(encoding="utf-8")

    assert "New-Object System.Windows.Forms.Form" in source
    assert "$MainForm.ShowInTaskbar = $false" in source
    assert "$MainForm.Add_Shown({" in source
    assert "$MainForm.Hide()" in source
    assert "$MainForm.Close()" in source
    assert "[System.Windows.Forms.Application]::Run($MainForm)" in source
    assert "$MainForm.Dispose()" in source
    assert "[System.Windows.Forms.Application]::Run()" not in source


def test_lens_hotkey_binding_registers_configured_global_hotkey() -> None:
    source = (_repo_root() / "scripts" / "lens-hotkey-binding.ps1").read_text(encoding="utf-8")

    assert "function Resolve-HotkeyRegistration" in source
    assert "function Resolve-HotkeyKeyCode" in source
    assert "F([1-9]|1[0-9]|2[0-4])" in source
    assert "Resolve-HotkeyRegistration -GlobalHotkey ([string]$ConfigForAction.global_hotkey)" in source
    assert "[uint32]$HotkeyRegistration.modifiers" in source
    assert "[uint32]$HotkeyRegistration.virtual_key" in source
    assert "RegisterHotKey($Window.Handle, 1, 0x0003, 0x20)" not in source


def test_lens_hotkey_binding_launches_canonical_summon_with_runtime_identity() -> None:
    source = (_repo_root() / "scripts" / "lens-hotkey-binding.ps1").read_text(encoding="utf-8")

    assert "'-DataDir'" in source
    assert "$script:DataRoot" in source
    assert "'-Trigger'" in source
    assert "'global_hotkey'" in source


def test_lens_hotkey_binding_registers_ctrl_m_orb_move_command_trigger() -> None:
    source = (_repo_root() / "scripts" / "lens-hotkey-binding.ps1").read_text(encoding="utf-8")
    config = (_repo_root() / "config" / "runtime" / "lens" / "summon.json").read_text(encoding="utf-8")

    assert '"command_id": "orb.move"' in config
    assert '"global_hotkey": "Ctrl+M"' in config
    assert '"authority_scope": "runtime_overlay_position_only"' in config
    assert '"capture_mode": "one_shot_click"' in config
    assert '"trigger_carries_authority": false' in config
    assert "function Get-CommandHotkeyConfigs" in source
    assert "function Get-EnabledCommandHotkeyConfigs" in source
    assert "Test-PrimaryHotkeyRegistrationEnabled -Config $ConfigForAction" in source
    assert "command_hotkeys = Get-CommandHotkeyConfigs -Payload $Config" in source
    assert "Resolve-HotkeyRegistration -GlobalHotkey ([string]$CommandHotkey.global_hotkey)" in source
    assert "RegisterHotKey($Window.Handle, $NextHotkeyId" in source
    assert "if ($PrimaryHotkeyRegistrationEnabled)" in source
    assert "$Modifiers = $Modifiers -bor [uint32]0x0002" in source
    assert "Write-HotkeyCommandRequest -Root $script:DataRoot -Trigger $CommandTrigger" in source
    assert "command_id = 'orb.move'" in source
    assert "status = 'command_request_already_pending'" in source
    assert "status = 'command_hotkey_debounced'" not in source
    assert "trigger_carries_authority = $false" in source
    assert "controls_user_os_cursor = $false" in source


def _run_hotkey_binding(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            _powershell(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(_repo_root() / "scripts" / "lens-hotkey-binding.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
        timeout=60,
    )


def test_lens_hotkey_binding_status_reports_missing_runtime(tmp_path: Path) -> None:
    proc = _run_hotkey_binding("-Mode", "Status", "-DataDir", str(tmp_path / "data"))

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.hotkey.binding.runtime"
    assert payload["status"] == "missing"
    assert payload["ready"] is False
    assert payload["global_hotkey_binding"] is False
    assert payload["summon_anywhere"] is False
    assert payload["next_smallest_truthful_gap"] == "global_hotkey_binding"
    assert payload["hotkey_runtime"]["requirement_state"] == "missing"
    assert payload["hotkey_runtime"]["blocker"] == "global_hotkey_binding_runtime_missing"
    assert payload["hotkey_runtime"]["global_hotkey"] == "Ctrl+Alt+F"
    assert payload["hotkey_runtime"]["binding_scope"] == "global"
    assert payload["governance"]["read_only_contract"] is True
    assert payload["governance"]["hotkey_registration_authority"] is False
    assert payload["governance"]["summon_authority"] is False
    assert payload["governance"]["local_process_launch_authority"] is False


def test_lens_hotkey_binding_status_surfaces_owned_hotkey_blocked_receipt(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    runtime_dir = data_dir / "runtime" / "lens-hotkey"
    runtime_dir.mkdir(parents=True)
    (runtime_dir / "status.json").write_text(
        json.dumps(
            {
                "kind": "lens.hotkey.runtime_state",
                "status": "hotkey_already_owned",
                "pid": 999999,
                "global_hotkey": "Ctrl+Alt+F",
                "binding_scope": "global",
                "hotkey_bound": False,
                "error": "hotkey_already_owned",
                "blocker": "hotkey_already_owned",
                "win32_error": 1409,
                "registration_failure": {
                    "error": "hotkey_already_owned",
                    "blocker": "hotkey_already_owned",
                    "global_hotkey": "Ctrl+Alt+F",
                    "win32_error": 1409,
                },
                "message": "RegisterHotKey failed for global hotkey 'Ctrl+Alt+F' with Win32 error 1409.",
            }
        ),
        encoding="utf-8",
    )

    proc = _run_hotkey_binding("-Mode", "Status", "-DataDir", str(data_dir))

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.hotkey.binding.runtime"
    assert payload["status"] == "blocked"
    assert payload["ready"] is False
    assert payload["blocked"] is True
    assert payload["blocker"] == "hotkey_already_owned"
    assert payload["blockers"] == ["hotkey_already_owned"]
    assert payload["next_smallest_truthful_gap"] == "choose_unclaimed_global_hotkey"
    assert payload["hotkey_runtime"]["requirement_state"] == "blocked"
    assert payload["hotkey_runtime"]["blocker"] == "hotkey_already_owned"
    assert payload["hotkey_runtime"]["runtime_status"] == "hotkey_already_owned"
    assert payload["hotkey_runtime"]["runtime_status_error"] == "hotkey_already_owned"
    assert payload["hotkey_runtime"]["win32_error"] == 1409
    assert payload["hotkey_runtime"]["registration_failure"]["global_hotkey"] == "Ctrl+Alt+F"


def test_lens_hotkey_binding_status_reports_live_runtime_readback(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    runtime_dir = data_dir / "runtime" / "lens-hotkey"
    runtime_dir.mkdir(parents=True)
    pid = os.getpid()
    (runtime_dir / "lens-hotkey.pid").write_text(str(pid), encoding="utf-8")
    (runtime_dir / "status.json").write_text(
        json.dumps(
            {
                "kind": "lens.hotkey.runtime_state",
                "status": "hotkey_bound",
                "pid": pid,
                "global_hotkey": "Ctrl+Alt+F",
                "binding_scope": "global",
                "hotkey_bound": True,
                "primary_hotkey_bound": True,
                "launch_on_hotkey": False,
                "summon_runner": "scripts/lens-summon.ps1",
                "press_count": 0,
            }
        ),
        encoding="utf-8",
    )

    proc = _run_hotkey_binding("-Mode", "Status", "-DataDir", str(data_dir))

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.hotkey.binding.runtime"
    assert payload["status"] == "bound"
    assert payload["ready"] is True
    assert payload["global_hotkey_binding"] is True
    assert payload["summon_anywhere"] is False
    assert payload["os_level_summon"] is False
    assert payload["next_smallest_truthful_gap"] == "summon_binding"
    assert payload["hotkey_runtime"]["process_alive"] is True
    assert payload["hotkey_runtime"]["hotkey_bound"] is True
    assert payload["hotkey_runtime"]["requirement_state"] == "bound"
    assert payload["hotkey_runtime"]["blocker"] == ""
    assert payload["hotkey_runtime"]["runtime_status_pid_matches_pid_file"] is True
    assert payload["governance"]["read_only_contract"] is True
    assert payload["governance"]["hotkey_registration_authority"] is False
    assert payload["governance"]["local_process_launch_authority"] is False


def test_lens_hotkey_binding_status_reports_launch_on_hotkey_runtime(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    runtime_dir = data_dir / "runtime" / "lens-hotkey"
    runtime_dir.mkdir(parents=True)
    pid = os.getpid()
    (runtime_dir / "lens-hotkey.pid").write_text(str(pid), encoding="utf-8")
    (runtime_dir / "status.json").write_text(
        json.dumps(
            {
                "kind": "lens.hotkey.runtime_state",
                "status": "hotkey_bound",
                "pid": pid,
                "global_hotkey": "Ctrl+Alt+F",
                "binding_scope": "global",
                "hotkey_bound": True,
                "launch_on_hotkey": True,
                "summon_runner": "scripts/lens-summon.ps1",
                "press_count": 0,
            }
        ),
        encoding="utf-8",
    )

    proc = _run_hotkey_binding("-Mode", "Status", "-DataDir", str(data_dir))

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["status"] == "bound"
    assert payload["ready"] is True
    assert payload["global_hotkey_binding"] is True
    assert payload["summon_anywhere"] is True
    assert payload["os_level_summon"] is True
    assert payload["hotkey_runtime"]["launch_on_hotkey"] is True


def test_lens_hotkey_binding_status_reports_command_hotkey_runtime_readback(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    runtime_dir = data_dir / "runtime" / "lens-hotkey"
    runtime_dir.mkdir(parents=True)
    pid = os.getpid()
    command_hotkey = {
        "id": "hotkey.ctrl_m",
        "command_id": "orb.move",
        "global_hotkey": "Ctrl+M",
        "binding_scope": "global",
        "enabled": True,
        "authority_scope": "runtime_overlay_position_only",
        "capture_mode": "one_shot_click",
        "handler": "lens.overlay.place_mode",
        "receipt_kind": "overlay_position",
        "trigger_carries_authority": False,
    }
    (runtime_dir / "lens-hotkey.pid").write_text(str(pid), encoding="utf-8")
    (runtime_dir / "status.json").write_text(
        json.dumps(
            {
                "kind": "lens.hotkey.runtime_state",
                "status": "hotkey_bound",
                "pid": pid,
                "global_hotkey": "Ctrl+Alt+F",
                "binding_scope": "global",
                "hotkey_bound": True,
                "primary_hotkey_bound": False,
                "launch_on_hotkey": False,
                "summon_runner": "scripts/lens-summon.ps1",
                "registered_command_hotkey_count": 1,
                "registered_command_hotkeys": [command_hotkey],
                "press_count": 0,
            }
        ),
        encoding="utf-8",
    )

    proc = _run_hotkey_binding("-Mode", "Status", "-DataDir", str(data_dir))

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["status"] == "bound"
    assert payload["ready"] is True
    assert payload["global_hotkey_binding"] is True
    assert payload["primary_hotkey_binding"] is False
    assert payload["command_hotkey_binding"] is True
    assert payload["summon_anywhere"] is False
    assert payload["hotkey_runtime"]["command_hotkey_binding"] is True
    assert payload["hotkey_runtime"]["registered_command_hotkey_count"] == 1
    assert payload["hotkey_runtime"]["runtime_command_hotkeys"][0]["command_id"] == "orb.move"


def test_lens_hotkey_binding_start_refuses_config_without_primary_or_command_hotkeys(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    config_path = _write_hotkey_config_override(tmp_path, command_hotkeys=[])
    proc = _run_hotkey_binding(
        "-Mode",
        "Start",
        "-DataDir",
        str(data_dir),
        "-StartupTimeoutSeconds",
        "1",
        "-RunSeconds",
        "1",
        "-NoLaunch",
        "-ConfigOverridePath",
        str(config_path),
    )

    assert proc.returncode == 2, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.hotkey.binding.runtime"
    assert payload["status"] == "blocked_by_config"
    assert payload["ok"] is False
    assert payload["ready"] is False
    assert payload["global_hotkey_binding"] is False
    assert payload["error"] == "lens_hotkey_binding_start_blocked_by_config"
    assert "lens_summon_binding_disabled_pending_authority" in payload["blockers"]
    assert "global_hotkey_binding_disabled" in payload["blockers"]
    assert "global_hotkey_registration_disabled" in payload["blockers"]
    assert "command_hotkey_registration_disabled" in payload["blockers"]
    assert payload["required_authorities"] == ["hotkey_registration_authority"]
    assert payload["missing_authorities"] == []
    assert payload["would_register_hotkey"] is False
    assert payload["would_launch_process"] is False
    assert payload["governance"]["hotkey_registration_authority"] is False
    assert payload["governance"]["local_process_launch_authority"] is False
    assert payload["governance"]["mutation_authority_granted"] is False
    assert not (data_dir / "runtime" / "lens-hotkey" / "lens-hotkey.pid").exists()


def test_lens_hotkey_binding_start_clears_stale_bound_runtime_before_rebind() -> None:
    source = (_repo_root() / "scripts" / "lens-hotkey-binding.ps1").read_text(encoding="utf-8")

    assert _normalized_contains(
        source,
        "if (-not [bool]$Existing.ready -and -not [bool]$Existing.process_alive -and [string]$Existing.runtime_status)",
    )
    assert "$RuntimeRoot = Join-Path $DataRoot 'runtime\\lens-hotkey'" in source
    assert "Remove-Item -LiteralPath (Join-Path $RuntimeRoot 'status.json')" in source
    assert "Remove-Item -LiteralPath (Join-Path $RuntimeRoot 'lens-hotkey.pid')" in source
    assert "Get-HotkeyRuntimeReadback -Root $DataRoot" in source


def test_lens_hotkey_binding_run_refuses_config_without_primary_or_command_hotkeys(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    config_path = _write_hotkey_config_override(tmp_path, command_hotkeys=[])
    proc = _run_hotkey_binding(
        "-Mode",
        "Run",
        "-DataDir",
        str(data_dir),
        "-RunSeconds",
        "1",
        "-NoLaunch",
        "-ConfigOverridePath",
        str(config_path),
    )

    assert proc.returncode == 2, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["status"] == "blocked_by_config"
    assert payload["error"] == "lens_hotkey_binding_run_blocked_by_config"
    assert payload["global_hotkey_binding"] is False
    assert "global_hotkey_registration_disabled" in payload["blockers"]
    assert "command_hotkey_registration_disabled" in payload["blockers"]
    assert payload["missing_authorities"] == []
    assert payload["would_register_hotkey"] is False
    assert payload["would_launch_process"] is False
    assert payload["governance"]["hotkey_registration_authority"] is False
    assert payload["governance"]["mutation_authority_granted"] is False
    assert not (data_dir / "runtime" / "lens-hotkey" / "lens-hotkey.pid").exists()
