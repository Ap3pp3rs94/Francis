from __future__ import annotations

import json
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


def _run_preflight(*args: str) -> subprocess.CompletedProcess[str]:
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
    assert payload["tray"]["tray_host_enabled"] is False
    assert payload["tray"]["tray_icon_enabled"] is False
    assert "tray_host_disabled" in payload["blockers"]
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
