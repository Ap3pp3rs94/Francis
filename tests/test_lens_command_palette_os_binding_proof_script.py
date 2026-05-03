from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "lens-command-palette-os-binding-proof.ps1"


def _powershell() -> str:
    exe = shutil.which("powershell") or shutil.which("pwsh")
    if exe is None:
        pytest.skip("PowerShell is not available")
    return exe


def _run_script(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            _powershell(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(SCRIPT),
            *args,
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def _write_lens_status(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "command_palette": {
                    "status": "readback_ready",
                    "availability": "chat_ui_only",
                    "summon_anywhere": False,
                    "route": "/lens/status",
                    "local_surface": "chat_ui.command_palette",
                    "command_total": 2,
                    "commands": [
                        {
                            "id": "go-pilot",
                            "label": "Pilot",
                            "authority": {"execution": False},
                        },
                        {
                            "id": "open-approvals",
                            "label": "Approvals",
                            "authority": {"approval_decision": False},
                        },
                    ],
                }
            }
        ),
        encoding="utf-8",
    )


def test_lens_command_palette_os_binding_proof_composes_blocked_readbacks(
    tmp_path: Path,
) -> None:
    status_path = tmp_path / "lens-status.json"
    _write_lens_status(status_path)

    result = _run_script("-Mode", "Status", "-StatusPath", str(status_path))

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)

    assert payload["kind"] == "lens.command_palette.os_binding_blockers.proof"
    assert payload["status"] == "proof_passed"
    assert payload["ok"] is True
    assert payload["stage"] == "Stage 6 / Lens MVP"
    assert payload["stage_state"] == "active"
    assert payload["acceptance_criterion"] == "summon_anywhere"
    assert payload["os_level_command_palette_binding_observed"] is True
    assert payload["summon_preflight_observed"] is True
    assert payload["tray_preflight_observed"] is True
    assert payload["overlay_preflight_observed"] is True
    assert payload["side_effects_denied"] is True
    assert payload["blocked_families"] == [
        "palette_binding",
        "global_hotkey_binding",
        "summon_binding",
        "tray_presence",
        "overlay_window",
        "authority",
    ]
    assert payload["first_blocker_family"] == "palette_binding"
    assert payload["next_smallest_truthful_gap"] == "os_level_command_palette_binding"

    blocker_groups = payload["blocker_groups"]
    assert blocker_groups["palette_binding"] == [
        "os_level_command_palette_missing",
        "summon_anywhere_missing",
        "global_hotkey_binding_missing",
    ]
    assert blocker_groups["global_hotkey_binding"] == [
        "global_hotkey_binding_disabled",
        "global_hotkey_registration_disabled",
        "hotkey_registration_authority_not_granted",
    ]
    assert blocker_groups["summon_binding"] == [
        "lens_summon_binding_not_implemented",
        "summon_authority_not_granted",
    ]
    assert blocker_groups["tray_presence"] == [
        "tray_host_disabled",
        "tray_icon_disabled",
        "tray_registration_authority_not_granted",
    ]
    assert blocker_groups["overlay_window"] == [
        "overlay_window_disabled",
        "always_on_top_disabled",
        "overlay_control_authority_not_granted",
    ]
    assert blocker_groups["authority"] == [
        "summon_authority_not_granted",
        "hotkey_registration_authority_not_granted",
        "local_process_launch_authority_not_granted",
        "tray_registration_authority_not_granted",
        "overlay_control_authority_not_granted",
    ]

    command_palette = payload["command_palette"]
    assert command_palette["status"] == "blocked"
    assert command_palette["availability"] == "chat_ui_only"
    assert command_palette["os_level_command_palette"] is False
    assert command_palette["summon_anywhere"] is False
    assert command_palette["command_total"] == 2
    assert command_palette["route"] == "/lens/status"
    assert command_palette["local_surface"] == "chat_ui.command_palette"

    summon_preflight = payload["summon_preflight"]
    assert summon_preflight["status"] == "blocked"
    assert summon_preflight["ready"] is False
    assert summon_preflight["global_hotkey"] == "Ctrl+Alt+Space"
    assert summon_preflight["binding_scope"] == "global"
    assert summon_preflight["palette_route"] == "/lens/status"

    assert payload["tray_preflight"]["status"] == "blocked"
    assert payload["tray_preflight"]["ready"] is False
    assert payload["overlay_preflight"]["status"] == "blocked"
    assert payload["overlay_preflight"]["ready"] is False

    checks = {check["name"]: check for check in payload["checks"]}
    assert checks["command_palette_shell_bridge"]["passed"] is True
    assert checks["command_palette_shell_bridge"]["status"] == "blocked_readback_ready"
    assert checks["summon_preflight"]["passed"] is True
    assert checks["summon_preflight"]["status"] == "blocked_readback_ready"
    assert checks["tray_preflight"]["passed"] is True
    assert checks["tray_preflight"]["status"] == "blocked_readback_ready"
    assert checks["overlay_preflight"]["passed"] is True
    assert checks["overlay_preflight"]["status"] == "blocked_readback_ready"
    assert checks["os_binding_side_effects_denied"]["passed"] is True
    assert checks["os_binding_side_effects_denied"]["status"] == "diagnostic_bounded"

    assert payload["governance"] == {
        "diagnostic_only": True,
        "wraps_command_palette_shell_bridge": True,
        "wraps_summon_preflight": True,
        "wraps_tray_preflight": True,
        "wraps_overlay_preflight": True,
        "read_only_contract": True,
        "opens_palette": False,
        "execution_authority": False,
        "approval_decision_authority": False,
        "memory_write": False,
        "overlay_control_authority": False,
        "window_management_authority": False,
        "summon_authority": False,
        "hotkey_registration_authority": False,
        "tray_registration_authority": False,
        "local_process_launch_authority": False,
        "service_control_authority": False,
        "capture_authority": False,
        "new_sensing_authority": False,
        "mutation_authority_granted": False,
    }
