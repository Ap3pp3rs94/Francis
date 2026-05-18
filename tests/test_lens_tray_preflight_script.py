from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest


def _powershell() -> str:
    exe = shutil.which("powershell") or shutil.which("pwsh")
    if not exe:
        pytest.skip("PowerShell is not available")
    return exe


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _run_preflight(*args: str) -> subprocess.CompletedProcess[str]:
    command_args = list(args)
    if "-DataDir" not in command_args:
        with tempfile.TemporaryDirectory() as raw_data_parent:
            command_args.extend(["-DataDir", str(Path(raw_data_parent) / "data")])
            return _run_preflight_with_args(command_args)
    return _run_preflight_with_args(command_args)


def _run_preflight_with_args(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            _powershell(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(_repo_root() / "scripts" / "lens-tray-preflight.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
    )


def test_lens_tray_preflight_reports_disabled_presence_without_authority() -> None:
    proc = _run_preflight("-Mode", "Status")

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.tray.preflight"
    assert payload["status"] == "blocked"
    assert payload["ready"] is False
    assert payload["presence_name"] == "Francis Lens Tray Presence"
    assert payload["required_before_enable"] == [
        "resident_host_process",
        "tray_icon",
        "user_session_presence",
        "global_hotkey_binding",
        "overlay_window",
        "summon_binding",
    ]
    assert payload["tray"]["tray_host_enabled"] is False
    assert payload["tray"]["tray_icon_enabled"] is False
    assert payload["resident_host_process"]["process_alive"] is False
    assert "tray_host_disabled" in payload["blockers"]
    assert "resident_host_process_missing" in payload["blockers"]
    assert "tray_registration_authority_not_granted" in payload["blockers"]
    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["tray_config"]["status"] == "present_disabled"
    assert checks["tray_host_enabled"]["status"] == "disabled"
    assert checks["tray_icon_enabled"]["status"] == "disabled"
    assert checks["host_preflight"]["status"] == "present"
    assert checks["summon_preflight"]["status"] == "present"
    assert checks["tray_registration_authority"]["status"] == "blocked"
    assert payload["governance"] == {
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
        "tray_registration_authority": False,
        "tray_icon_authority": False,
        "notification_authority": False,
        "mutation_authority_granted": False,
    }


def test_lens_tray_preflight_rejects_stale_runtime_pid(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    runtime_dir = data_dir / "runtime" / "lens-host"
    runtime_dir.mkdir(parents=True)
    pid_file_pid = 999999
    status_pid = 999998
    (runtime_dir / "lens-host.pid").write_text(str(pid_file_pid), encoding="utf-8")
    (runtime_dir / "status.json").write_text(
        json.dumps(
            {
                "kind": "lens.host.runtime_state",
                "status": "resident_running",
                "pid": status_pid,
            }
        ),
        encoding="utf-8",
    )

    proc = _run_preflight("-Mode", "Status", "-DataDir", str(data_dir))

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.tray.preflight"
    assert payload["status"] == "blocked"
    assert payload["ready"] is False
    assert payload["data_root"] == str(data_dir)
    process = payload["resident_host_process"]
    assert process["pid"] == pid_file_pid
    assert process["pid_present"] is True
    assert process["runtime_state_exists"] is True
    assert process["runtime_status_kind"] == "lens.host.runtime_state"
    assert process["runtime_status"] == "resident_running"
    assert process["runtime_status_pid"] == status_pid
    assert process["runtime_status_pid_matches_pid_file"] is False
    assert process["process_alive"] is False
    assert process["requirement_state"] == "stale_or_unverified"
    assert process["blocker"] == "resident_host_process_missing"
    assert "resident_host_process_missing" in payload["blockers"]
    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["runtime_state"]["status"] == "stale_or_unverified"


def test_lens_tray_preflight_reports_live_tray_runtime_readback(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    runtime_dir = data_dir / "runtime" / "lens-tray"
    runtime_dir.mkdir(parents=True)
    pid = os.getpid()
    (runtime_dir / "lens-tray.pid").write_text(str(pid), encoding="utf-8")
    (runtime_dir / "status.json").write_text(
        json.dumps(
            {
                "kind": "lens.tray.runtime_state",
                "status": "tray_running",
                "pid": pid,
                "tray_icon_visible": True,
            }
        ),
        encoding="utf-8",
    )

    proc = _run_preflight("-Mode", "Status", "-DataDir", str(data_dir))

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.tray.preflight"
    assert payload["status"] == "blocked"
    assert payload["ready"] is False
    assert payload["tray"]["tray_runner"] == "scripts/lens-tray-presence.ps1"
    tray_runtime = payload["tray_runtime"]
    assert tray_runtime["ready"] is True
    assert tray_runtime["process_alive"] is True
    assert tray_runtime["tray_icon_visible"] is True
    assert tray_runtime["requirement_state"] == "running"
    assert tray_runtime["blocker"] == ""
    assert "tray_presence_runtime_missing" not in payload["blockers"]
    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["tray_runner"]["status"] == "present"
    assert checks["tray_runtime"]["status"] == "running"


def test_lens_tray_preflight_refuses_register_actions() -> None:
    proc = _run_preflight("-Mode", "Register")

    assert proc.returncode == 2
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.tray.preflight"
    assert payload["status"] == "refused"
    assert payload["ok"] is False
    assert payload["error"] == "lens_tray_action_not_authorized"
    assert payload["governance"]["tray_registration_authority"] is False
    assert payload["governance"]["local_process_launch_authority"] is False
