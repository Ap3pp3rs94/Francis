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


def _run_overlay_window(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            _powershell(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(_repo_root() / "scripts" / "lens-overlay-window.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
        timeout=60,
    )


def test_lens_overlay_window_status_reports_missing_runtime(tmp_path: Path) -> None:
    proc = _run_overlay_window("-Mode", "Status", "-DataDir", str(tmp_path / "data"))

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.overlay.window.runtime"
    assert payload["status"] == "missing"
    assert payload["ready"] is False
    assert payload["overlay_window"] is False
    assert payload["next_smallest_truthful_gap"] == "overlay_window_runtime"
    assert payload["overlay_runtime"]["requirement_state"] == "missing"
    assert payload["overlay_runtime"]["blocker"] == "overlay_window_runtime_missing"
    assert payload["overlay_runtime"]["expected_overlay_name"] == "Francis Lens Overlay"
    assert payload["overlay_runtime"]["expected_overlay_scope"] == "user_session"
    assert payload["governance"]["read_only_contract"] is True
    assert payload["governance"]["overlay_control_authority"] is False
    assert payload["governance"]["window_management_authority"] is False
    assert payload["governance"]["local_process_launch_authority"] is False


def test_lens_overlay_window_stop_handles_corrupt_runtime_status(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    runtime_dir = data_dir / "runtime" / "lens-overlay"
    runtime_dir.mkdir(parents=True)
    (runtime_dir / "lens-overlay.pid").write_text("999999", encoding="utf-8")
    (runtime_dir / "status.json").write_text("", encoding="utf-8")

    proc = _run_overlay_window("-Mode", "Stop", "-DataDir", str(data_dir))

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.overlay.window.runtime"
    assert payload["status"] == "stopped"
    assert payload["ready"] is False
    assert payload["overlay_window"] is False
    assert payload["overlay_runtime"]["runtime_state_exists"] is True
    assert payload["overlay_runtime"]["pid_present"] is False
    assert payload["overlay_runtime"]["runtime_status"] == "overlay_stopped"
    assert payload["overlay_runtime"]["runtime_process_alive"] is False


def test_lens_overlay_window_status_reports_live_runtime_readback(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    runtime_dir = data_dir / "runtime" / "lens-overlay"
    runtime_dir.mkdir(parents=True)
    pid = os.getpid()
    (runtime_dir / "lens-overlay.pid").write_text(str(pid), encoding="utf-8")
    (runtime_dir / "status.json").write_text(
        json.dumps(
            {
                "kind": "lens.overlay.runtime_state",
                "status": "overlay_running",
                "pid": pid,
                "overlay_name": "Francis Lens Overlay",
                "overlay_scope": "user_session",
                "overlay_window_visible": True,
                "always_on_top": True,
            }
        ),
        encoding="utf-8",
    )

    proc = _run_overlay_window("-Mode", "Status", "-DataDir", str(data_dir))

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.overlay.window.runtime"
    assert payload["status"] == "visible"
    assert payload["ready"] is True
    assert payload["overlay_window"] is True
    assert payload["next_smallest_truthful_gap"] == "overlay_authority_and_config"
    assert payload["overlay_runtime"]["process_alive"] is True
    assert payload["overlay_runtime"]["runtime_process_alive"] is False
    assert payload["overlay_runtime"]["overlay_window_visible"] is True
    assert payload["overlay_runtime"]["always_on_top"] is True
    assert payload["overlay_runtime"]["requirement_state"] == "visible"
    assert payload["overlay_runtime"]["blocker"] == ""
    assert payload["overlay_runtime"]["runtime_status_pid_matches_pid_file"] is True
    assert payload["governance"]["read_only_contract"] is True
    assert payload["governance"]["overlay_control_authority"] is False
    assert payload["governance"]["local_process_launch_authority"] is False


def test_lens_overlay_window_script_uses_atomic_state_and_owned_process_stop() -> None:
    script = (_repo_root() / "scripts" / "lens-overlay-window.ps1").read_text(encoding="utf-8")

    assert "function Test-OverlayRuntimeProcess" in script
    assert "function Stop-OverlayRuntimeProcess" in script
    assert "status.{0}.tmp" in script
    assert "Move-Item -LiteralPath $TempPath -Destination $StatusPath -Force" in script
    assert "runtime_process_alive = $RuntimeProcessAlive" in script
    assert "Stop-OverlayRuntimeProcess -ProcessId ([int]$TimedOut.pid)" in script
