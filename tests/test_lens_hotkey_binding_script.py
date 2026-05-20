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


def test_lens_hotkey_binding_start_timeout_stops_started_child_process() -> None:
    source = (_repo_root() / "scripts" / "lens-hotkey-binding.ps1").read_text(encoding="utf-8")

    assert "-PassThru" in source
    assert "Stop-Process -Id $StartedProcess.Id -Force" in source
    assert "started_process_stopped" in source


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
    assert payload["hotkey_runtime"]["global_hotkey"] == "Ctrl+Alt+Space"
    assert payload["hotkey_runtime"]["binding_scope"] == "global"
    assert payload["governance"]["read_only_contract"] is True
    assert payload["governance"]["hotkey_registration_authority"] is False
    assert payload["governance"]["summon_authority"] is False
    assert payload["governance"]["local_process_launch_authority"] is False


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
                "global_hotkey": "Ctrl+Alt+Space",
                "binding_scope": "global",
                "hotkey_bound": True,
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
                "global_hotkey": "Ctrl+Alt+Space",
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


def test_lens_hotkey_binding_start_refuses_default_blocked_config(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
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
    assert "hotkey_registration_authority_not_granted" in payload["blockers"]
    assert payload["required_authorities"] == ["hotkey_registration_authority"]
    assert payload["missing_authorities"] == ["hotkey_registration_authority_not_granted"]
    assert payload["would_register_hotkey"] is False
    assert payload["would_launch_process"] is False
    assert payload["governance"]["hotkey_registration_authority"] is False
    assert payload["governance"]["local_process_launch_authority"] is False
    assert payload["governance"]["mutation_authority_granted"] is False
    assert not (data_dir / "runtime" / "lens-hotkey" / "lens-hotkey.pid").exists()


def test_lens_hotkey_binding_run_refuses_default_blocked_config(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    proc = _run_hotkey_binding(
        "-Mode",
        "Run",
        "-DataDir",
        str(data_dir),
        "-RunSeconds",
        "1",
        "-NoLaunch",
    )

    assert proc.returncode == 2, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["status"] == "blocked_by_config"
    assert payload["error"] == "lens_hotkey_binding_run_blocked_by_config"
    assert payload["global_hotkey_binding"] is False
    assert "hotkey_registration_authority_not_granted" in payload["blockers"]
    assert payload["would_register_hotkey"] is False
    assert payload["would_launch_process"] is False
    assert payload["governance"]["hotkey_registration_authority"] is False
    assert payload["governance"]["mutation_authority_granted"] is False
    assert not (data_dir / "runtime" / "lens-hotkey" / "lens-hotkey.pid").exists()
