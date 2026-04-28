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
            str(_repo_root() / "scripts" / "lens-summon-preflight.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
    )


def test_lens_summon_preflight_reports_disabled_hotkey_without_authority() -> None:
    proc = _run_preflight("-Mode", "Status")

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.summon.preflight"
    assert payload["status"] == "blocked"
    assert payload["ready"] is False
    assert payload["global_hotkey"] == "Ctrl+Alt+Space"
    assert payload["binding"]["binding_enabled"] is False
    assert "global_hotkey_binding_disabled" in payload["blockers"]
    assert "summon_authority_not_granted" in payload["blockers"]
    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["summon_config"]["status"] == "present_disabled"
    assert checks["hotkey_declared"]["status"] == "declared"
    assert checks["binding_enabled"]["status"] == "disabled"
    assert checks["register_hotkey"]["status"] == "disabled"
    assert checks["host_preflight"]["status"] == "present"
    assert checks["hotkey_registration_authority"]["status"] == "blocked"
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
        "hotkey_registration_authority": False,
        "mutation_authority_granted": False,
    }


def test_lens_summon_preflight_refuses_bind_actions() -> None:
    proc = _run_preflight("-Mode", "Bind")

    assert proc.returncode == 2
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.summon.preflight"
    assert payload["status"] == "refused"
    assert payload["ok"] is False
    assert payload["error"] == "lens_summon_action_not_authorized"
    assert payload["governance"]["hotkey_registration_authority"] is False
    assert payload["governance"]["summon_authority"] is False
