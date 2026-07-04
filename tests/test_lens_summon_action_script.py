from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest


def _powershell() -> str:
    exe = shutil.which("powershell") or shutil.which("pwsh")
    if not exe:
        pytest.skip("PowerShell is not available")
    return exe


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _run_action(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            _powershell(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(_repo_root() / "scripts" / "lens-summon-action.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
        timeout=30,
    )


def _write_ready_summon_config(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "kind": "francis.lens.summon.config",
                "version": 1,
                "summon_name": "Francis Lens Summon",
                "enabled": True,
                "global_hotkey": "Ctrl+Alt+F",
                "binding_scope": "global",
                "binding_enabled": True,
                "register_hotkey": True,
                "startup_register": False,
                "palette_route": "/lens/status",
                "host_preflight": "scripts/lens-host-preflight.ps1",
                "host_status_runner": "scripts/lens-host.ps1",
                "summon_runner": "scripts/lens-summon.ps1",
                "local_palette_launcher": "scripts/lens-command-palette.ps1 -Mode LocalOpen",
                "overlay_required": False,
                "tray_required": False,
                "requires_explicit_enable": True,
                "summon_authority": True,
                "hotkey_registration_authority": True,
                "overlay_control_authority": True,
                "local_process_launch_authority": True,
                "blocked_reason": "",
                "required_before_enable": [
                    "resident_host_process",
                    "tray_presence",
                    "overlay_window",
                    "global_hotkey_binding",
                    "summon_binding",
                ],
            }
        ),
        encoding="utf-8",
    )


def _write_ready_runtime_readbacks(data_dir: Path) -> None:
    pid = os.getpid()
    host_dir = data_dir / "runtime" / "lens-host"
    host_dir.mkdir(parents=True)
    (host_dir / "lens-host.pid").write_text(str(pid), encoding="utf-8")
    (host_dir / "status.json").write_text(
        json.dumps(
            {
                "kind": "lens.host.runtime_state",
                "status": "resident_running",
                "pid": pid,
            }
        ),
        encoding="utf-8",
    )

    hotkey_dir = data_dir / "runtime" / "lens-hotkey"
    hotkey_dir.mkdir(parents=True)
    (hotkey_dir / "lens-hotkey.pid").write_text(str(pid), encoding="utf-8")
    (hotkey_dir / "status.json").write_text(
        json.dumps(
            {
                "kind": "lens.hotkey.runtime_state",
                "status": "hotkey_bound",
                "pid": pid,
                "global_hotkey": "Ctrl+Alt+F",
                "binding_scope": "global",
                "hotkey_bound": True,
                "launch_on_hotkey": False,
                "summon_runner": "scripts/lens-summon.ps1",
                "press_count": 0,
            }
        ),
        encoding="utf-8",
    )


def _write_lens_status(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "kind": "lens.status",
                "command_palette": {
                    "status": "readback_ready",
                    "availability": "chat_ui_only",
                    "summon_anywhere": False,
                    "url_entrypoint_ready": True,
                    "url_entrypoint": {
                        "kind": "lens.command_palette.url_entrypoint",
                        "status": "ready",
                        "route": "/?francis_lens=command_palette",
                        "local_surface": "chat_ui.command_palette",
                        "opens_palette_in_chat_ui": True,
                        "requires_running_chat_ui": True,
                        "os_level_command_palette": False,
                        "summon_anywhere": False,
                        "global_hotkey": False,
                    },
                    "route": "/lens/status",
                    "local_surface": "chat_ui.command_palette",
                    "command_total": 1,
                    "commands": [{"id": "nav.orb", "label": "Open ORB", "group": "Navigation"}],
                },
            }
        ),
        encoding="utf-8",
    )


def test_lens_summon_action_status_consumes_preflight_without_execution(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    proc = _run_action("-Mode", "Status", "-DataDir", str(data_dir))

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.summon.action"
    assert payload["status"] == "blocked"
    assert payload["mode"] == "status"
    assert payload["preflight"]["kind"] == "lens.summon.preflight"
    assert payload["preflight_ready"] is False
    assert payload["execution_attempted"] is False
    assert payload["handoff_attempted"] is False
    assert payload["hotkey_binding_attempted"] is False
    assert payload["launch_attempted"] is False
    assert payload["bounded_handoff"]["status"] == "not_requested"
    assert payload["governance"]["read_only_contract"] is True
    assert payload["governance"]["execution_authority"] is False
    assert payload["governance"]["mutation_authority_granted"] is False


def test_lens_summon_action_ready_launch_uses_bounded_no_launch_handoff(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    config_path = tmp_path / "summon-ready.json"
    status_path = tmp_path / "lens-status.json"
    _write_ready_summon_config(config_path)
    _write_ready_runtime_readbacks(data_dir)
    _write_lens_status(status_path)

    proc = _run_action(
        "-Mode",
        "Launch",
        "-DataDir",
        str(data_dir),
        "-ConfigOverridePath",
        str(config_path),
        "-StatusPath",
        str(status_path),
    )

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.summon.action"
    assert payload["status"] == "handoff_completed"
    assert payload["mode"] == "launch"
    assert payload["preflight_ready"] is True
    assert payload["preflight"]["status"] == "ready_for_execution"
    assert payload["preflight"]["ready"] is True
    assert payload["preflight"]["config_path"] == str(config_path)
    assert payload["preflight"]["blockers"] == []
    assert payload["preflight"]["required_before_enable_ready"] is True
    assert payload["action_gate"]["status"] == "ready_for_execution"
    assert payload["action_gate"]["would_summon"] is True
    assert payload["execution_attempted"] is True
    assert payload["handoff_attempted"] is True
    assert payload["hotkey_binding_attempted"] is False
    assert payload["launch_attempted"] is True
    assert payload["allow_launch"] is False
    assert payload["bounded_handoff"]["status"] == "local_open_ready"
    assert payload["bounded_handoff"]["exit_code"] == 0
    assert payload["bounded_handoff"]["json_parsed"] is True
    handoff_payload = payload["bounded_handoff"]["payload"]
    assert handoff_payload["kind"] == "lens.summon.local_launcher"
    assert handoff_payload["status"] == "local_open_ready"
    assert handoff_payload["config_path"] == str(config_path)
    assert handoff_payload["opened"] is False
    assert handoff_payload["no_launch"] is True
    assert handoff_payload["governance"]["local_process_launch_authority"] is False
    assert payload["governance"]["action_request_gated"] is True
    assert payload["governance"]["execution_authority"] is True
    assert payload["governance"]["summon_authority"] is True
    assert payload["governance"]["local_process_launch_authority"] is False
    assert payload["governance"]["mutation_authority_granted"] is False


@pytest.mark.parametrize(
    ("mode", "expected_error", "attempt_field"),
    [
        ("Bind", "lens_summon_action_blocked_by_preflight", "hotkey_binding_attempted"),
        ("Launch", "lens_summon_action_blocked_by_preflight", "launch_attempted"),
    ],
)
def test_lens_summon_action_refuses_blocked_handoff_without_side_effects(
    tmp_path: Path,
    mode: str,
    expected_error: str,
    attempt_field: str,
) -> None:
    data_dir = tmp_path / "data"
    proc = _run_action("-Mode", mode, "-DataDir", str(data_dir))

    assert proc.returncode == 2
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.summon.action"
    assert payload["status"] == "blocked_by_preflight"
    assert payload["mode"] == mode.lower()
    assert payload["error"] == expected_error
    assert payload["preflight_exit_code"] == 2
    assert payload["preflight_ready"] is False
    assert payload["preflight"]["kind"] == "lens.summon.preflight"
    assert payload["action_gate"]["action"] == mode.lower()
    assert payload["action_gate"]["status"] == "blocked"
    assert payload["action_gate"]["execution_handoff"] == f"scripts/lens-summon-action.ps1 -Mode {mode}"
    assert payload["execution_attempted"] is False
    assert payload["handoff_attempted"] is False
    assert payload["hotkey_binding_attempted"] is False
    assert payload["launch_attempted"] is False
    assert payload[attempt_field] is False
    assert payload["bounded_handoff"]["status"] == "not_requested"
    assert payload["bounded_handoff"]["payload"] is None
    assert payload["governance"]["action_request_gated"] is True
    assert payload["governance"]["execution_authority"] is False
    assert payload["governance"]["approval_decision_authority"] is False
    assert payload["governance"]["memory_write"] is False
    assert payload["governance"]["hotkey_registration_authority"] is False
    assert payload["governance"]["summon_authority"] is False
    assert payload["governance"]["mutation_authority_granted"] is False
    assert not (data_dir / "runtime" / "lens-hotkey" / "status.json").exists()
