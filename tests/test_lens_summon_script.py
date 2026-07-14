from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
import time
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


def _write_native_runtime(data_root: Path) -> tuple[Path, Path, dict[str, object]]:
    overlay_root = data_root / "runtime" / "lens-overlay"
    hotkey_root = data_root / "runtime" / "lens-hotkey"
    overlay_root.mkdir(parents=True)
    hotkey_root.mkdir(parents=True)
    pid = os.getpid()
    overlay_status_path = overlay_root / "status.json"
    overlay_status: dict[str, object] = {
        "kind": "lens.overlay.runtime_state",
        "status": "overlay_running",
        "pid": pid,
        "overlay_window_visible": True,
        "always_on_top": True,
        "orb_controls": {
            "right_click_panel_supported": True,
            "panel_visible": False,
            "latest_status": "not_opened",
            "latest_request_id": "",
            "last_receipt_path": "",
        },
    }
    overlay_status_path.write_text(json.dumps(overlay_status), encoding="utf-8")
    (overlay_root / "lens-overlay.pid").write_text(str(pid), encoding="utf-8")
    (hotkey_root / "status.json").write_text(
        json.dumps(
            {
                "kind": "lens.hotkey.runtime_state",
                "status": "hotkey_bound",
                "pid": pid,
                "hotkey_bound": True,
                "launch_on_hotkey": True,
                "global_hotkey": "Ctrl+Alt+F",
                "press_count": 1,
            }
        ),
        encoding="utf-8",
    )
    (hotkey_root / "lens-hotkey.pid").write_text(str(pid), encoding="utf-8")
    return overlay_root, overlay_status_path, overlay_status


def _write_summon_override(path: Path, *, overlay_control_authority: bool = True) -> None:
    path.write_text(
        json.dumps(
            {
                "kind": "lens.summon.config",
                "global_hotkey": "Ctrl+Alt+F",
                "binding_scope": "global",
                "binding_enabled": True,
                "register_hotkey": True,
                "startup_register": False,
                "summon_runner": "scripts/lens-summon.ps1",
                "summon_authority": True,
                "hotkey_registration_authority": True,
                "overlay_control_authority": overlay_control_authority,
                "local_process_launch_authority": True,
                "blocked_reason": "",
            }
        ),
        encoding="utf-8",
    )


def test_lens_summon_status_reports_local_binding_without_os_authority(tmp_path: Path) -> None:
    status_path = tmp_path / "lens-status.json"
    _write_status(status_path)

    proc = _run_summon("-Mode", "Status", "-DataDir", str(tmp_path / "data"), "-StatusPath", str(status_path))

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
    assert checks["native_orb_surface_target"]["status"] == "unavailable"
    assert checks["web_surface_fallback"]["status"] == "available"
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
        "-DataDir",
        str(tmp_path / "data"),
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
    assert payload["governance"]["opens_palette"] is False
    assert payload["governance"]["local_process_launch_authority"] is False
    assert payload["governance"]["summon_authority"] is False


def test_lens_summon_refuses_native_request_without_overlay_control_authority(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    overlay_root, _, _ = _write_native_runtime(data_root)
    config_path = tmp_path / "summon-override.json"
    _write_summon_override(config_path, overlay_control_authority=False)

    proc = _run_summon(
        "-Mode",
        "LocalOpen",
        "-DataDir",
        str(data_root),
        "-ConfigOverridePath",
        str(config_path),
        "-Trigger",
        "global_hotkey",
    )

    assert proc.returncode == 1, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["status"] == "blocked_by_authority"
    assert payload["ok"] is False
    assert payload["opened"] is False
    assert payload["execution_authority_ready"] is False
    assert payload["summon_anywhere"] is False
    assert "overlay_control_authority_not_granted" in payload["blockers"]
    assert not (overlay_root / "summon-request.json").exists()
    assert "receipt_path" not in payload


def test_lens_summon_opens_canonical_orb_panel_through_correlated_request(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    overlay_root, overlay_status_path, overlay_status = _write_native_runtime(data_root)

    config_path = tmp_path / "summon-override.json"
    _write_summon_override(config_path)
    command_palette_status = tmp_path / "lens-status.json"
    _write_status(command_palette_status)

    observed_request: dict[str, object] = {}

    def consume_request() -> None:
        request_path = overlay_root / "summon-request.json"
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and not request_path.is_file():
            time.sleep(0.05)
        if not request_path.is_file():
            return
        request: dict[str, object] | None = None
        while time.monotonic() < deadline:
            try:
                request = json.loads(request_path.read_text(encoding="utf-8-sig"))
                break
            except PermissionError:
                time.sleep(0.05)
        if request is None:
            return
        observed_request.update(request)
        request_id = str(request["request_id"])
        receipt_relative = f"data/runtime/lens-overlay/orb-controls/orb-control-{request_id}.json"
        receipt_path = overlay_root / "orb-controls" / f"orb-control-{request_id}.json"
        receipt_path.parent.mkdir(parents=True)
        receipt_path.write_text(
            json.dumps({"kind": "lens.overlay.orb_control.receipt", "action": "panel_open", "request_id": request_id}),
            encoding="utf-8",
        )
        updated = dict(overlay_status)
        updated["orb_controls"] = {
            **overlay_status["orb_controls"],
            "panel_visible": True,
            "latest_status": "panel_open",
            "latest_request_id": request_id,
            "last_receipt_path": receipt_relative,
        }
        overlay_status_path.write_text(json.dumps(updated), encoding="utf-8")
        request_path.unlink()

    consumer = threading.Thread(target=consume_request, daemon=True)
    consumer.start()
    proc = _run_summon(
        "-Mode",
        "LocalOpen",
        "-DataDir",
        str(data_root),
        "-ConfigOverridePath",
        str(config_path),
        "-StatusPath",
        str(command_palette_status),
        "-TimeoutSeconds",
        "10",
        "-Trigger",
        "global_hotkey",
    )
    consumer.join(timeout=2)

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["status"] == "native_surface_opened"
    assert payload["launch_target"] == "lens.overlay.orb_panel"
    assert payload["native_surface"] == "lens.overlay.orb.right_click_panel"
    assert payload["opened"] is True
    assert payload["browser_opened"] is False
    assert payload["native_request_consumed"] is True
    assert payload["native_request"]["request_id"] == observed_request["request_id"]
    assert observed_request["kind"] == "lens.overlay.summon_request"
    assert observed_request["action"] == "open_orb_panel"
    assert observed_request["authority_scope"] == "runtime_overlay_panel_only"
    assert observed_request["source"] == "lens.hotkey.global"
    assert observed_request["trigger"] == "global_hotkey"
    assert payload["os_level_summon"] is True
    assert payload["summon_anywhere"] is True
    assert payload["controls_user_os_cursor"] is False
    assert payload["physical_input_performed"] is False
    assert payload["governance"]["overlay_control_authority"] is True
    assert payload["governance"]["local_process_launch_authority"] is False
    assert Path(payload["receipt_path"]).is_file()
    assert payload["trigger"] == "global_hotkey"
    assert payload["palette_launcher"]["status"] == "not_invoked_native_primary"
    receipt = json.loads(Path(payload["receipt_path"]).read_text(encoding="utf-8-sig"))
    assert receipt["trigger"] == "global_hotkey"
    assert receipt["browser_opened"] is False
    persisted = json.loads((data_root / "runtime" / "lens-summon" / "status.json").read_text(encoding="utf-8-sig"))
    assert persisted["native_request"]["request_id"] == observed_request["request_id"]
    assert persisted["native_request_consumed"] is True
