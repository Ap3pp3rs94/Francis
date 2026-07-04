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


def _run_summon(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            _powershell(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(_repo_root() / "scripts" / "lens-summon.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
        timeout=30,
    )


def _write_status(path: Path) -> None:
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


def test_lens_summon_status_reports_local_binding_without_os_authority(tmp_path: Path) -> None:
    status_path = tmp_path / "lens-status.json"
    _write_status(status_path)

    proc = _run_summon("-Mode", "Status", "-StatusPath", str(status_path))

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.summon.local_launcher"
    assert payload["status"] == "local_binding_ready"
    assert payload["ok"] is True
    assert payload["local_binding_ready"] is True
    assert payload["summon_binding_target_ready"] is True
    assert payload["local_summon_available"] is True
    assert payload["os_level_summon"] is False
    assert payload["summon_anywhere"] is False
    assert payload["global_hotkey"] == "Ctrl+Alt+F"
    assert payload["binding_scope"] == "global"
    assert payload["binding_enabled"] is False
    assert payload["register_hotkey"] is False
    assert payload["summon_runner"] == "scripts/lens-summon.ps1"
    assert payload["local_open_target_url"] == "http://127.0.0.1:5173/?francis_lens=command_palette"
    assert payload["next_smallest_truthful_gap"] == "global_hotkey_binding"
    assert "lens_summon_binding_disabled_pending_authority" in payload["blockers"]
    assert "global_hotkey_binding_disabled" in payload["blockers"]
    assert "global_hotkey_registration_disabled" in payload["blockers"]
    assert "summon_authority_not_granted" not in payload["blockers"]
    palette = payload["palette_launcher"]
    assert palette["script"] == "scripts/lens-command-palette.ps1"
    assert palette["status"] == "local_open_ready"
    assert palette["local_open_available"] is True
    assert palette["readback_ready"] is True
    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["command_palette_local_open"]["status"] == "local_open_ready"
    assert checks["global_hotkey_binding"]["status"] == "disabled"
    assert checks["summon_authority"]["status"] == "allowed"
    assert payload["governance"] == {
        "read_only_contract": True,
        "opens_palette": False,
        "execution_authority": False,
        "approval_decision_authority": False,
        "memory_write": False,
        "overlay_control_authority": False,
        "summon_authority": False,
        "hotkey_registration_authority": False,
        "tray_registration_authority": False,
        "local_process_launch_authority": False,
        "mutation_authority_granted": False,
    }


def test_lens_summon_local_open_dry_run_uses_command_palette_bridge(tmp_path: Path) -> None:
    status_path = tmp_path / "lens-status.json"
    _write_status(status_path)

    proc = _run_summon(
        "-Mode",
        "LocalOpen",
        "-StatusPath",
        str(status_path),
        "-NoLaunch",
    )

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["status"] == "local_open_ready"
    assert payload["would_open_palette"] is True
    assert payload["opened"] is False
    assert payload["no_launch"] is True
    assert payload["local_binding_ready"] is True
    assert payload["summon_anywhere"] is False
    assert payload["governance"]["read_only_contract"] is False
    assert payload["governance"]["opens_palette"] is True
    assert payload["governance"]["local_process_launch_authority"] is False
    assert payload["governance"]["summon_authority"] is False
