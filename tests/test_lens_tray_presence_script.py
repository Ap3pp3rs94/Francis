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


def _run_tray_presence(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            _powershell(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(_repo_root() / "scripts" / "lens-tray-presence.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
    )


def test_lens_tray_presence_status_reports_missing_runtime(tmp_path: Path) -> None:
    proc = _run_tray_presence("-Mode", "Status", "-DataDir", str(tmp_path / "data"))

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.tray.presence.runtime"
    assert payload["status"] == "missing"
    assert payload["ready"] is False
    assert payload["tray_presence"] is False
    assert payload["tray_runtime"]["requirement_state"] == "missing"
    assert payload["tray_runtime"]["blocker"] == "tray_presence_runtime_missing"
    assert payload["governance"]["read_only_contract"] is True
    assert payload["governance"]["tray_registration_authority"] is False
    assert payload["governance"]["tray_icon_authority"] is False


def test_lens_tray_presence_projects_and_requires_isolated_runtime_identity(tmp_path: Path) -> None:
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
                "presence_name": "Francis Lens Tray Presence [CPJ-001]",
                "tray_text": "Francis Lens [CPJ-001]",
                "runtime_identity": "CPJ-001",
            }
        ),
        encoding="utf-8",
    )

    proc = _run_tray_presence("-Mode", "Status", "-DataDir", str(data_dir), "-RuntimeIdentity", "CPJ-001")

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["ready"] is True
    assert payload["runtime_identity"] == "CPJ-001"
    assert payload["presence_name"] == "Francis Lens Tray Presence [CPJ-001]"
    assert payload["tray_text"] == "Francis Lens [CPJ-001]"
    assert payload["tray_runtime"]["runtime_identity_matches_expected"] is True

    mismatch = _run_tray_presence("-Mode", "Status", "-DataDir", str(data_dir), "-RuntimeIdentity", "CPJ-002")
    assert mismatch.returncode == 0, mismatch.stderr
    mismatch_payload = json.loads(mismatch.stdout)
    assert mismatch_payload["ready"] is False
    assert mismatch_payload["tray_runtime"]["runtime_identity_matches_expected"] is False


def test_lens_tray_presence_status_reports_live_runtime_readback(tmp_path: Path) -> None:
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

    proc = _run_tray_presence("-Mode", "Status", "-DataDir", str(data_dir))

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.tray.presence.runtime"
    assert payload["status"] == "running"
    assert payload["ready"] is True
    assert payload["tray_presence"] is True
    assert payload["tray_runtime"]["process_alive"] is True
    assert payload["tray_runtime"]["tray_icon_visible"] is True
    assert payload["tray_runtime"]["requirement_state"] == "running"
    assert payload["tray_runtime"]["blocker"] == ""


def test_lens_tray_presence_run_uses_hidden_message_loop_form() -> None:
    script = (_repo_root() / "scripts" / "lens-tray-presence.ps1").read_text(encoding="utf-8")

    assert "New-Object System.Windows.Forms.Form" in script
    assert "$MainForm.ShowInTaskbar = $false" in script
    assert "$MainForm.Add_Shown({" in script
    assert "$MainForm.Hide()" in script
    assert "$MainForm.Close()" in script
    assert "[System.Windows.Forms.Application]::Run($MainForm)" in script
    assert "$MainForm.Dispose()" in script
    assert "'-RuntimeIdentity'" in script
