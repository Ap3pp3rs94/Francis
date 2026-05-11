from __future__ import annotations

import json
import os
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


def _run_script(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
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
        env=env,
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


def _write_execution_readiness(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "kind": "lens.os_binding.command_palette_binding.execution_readiness",
                "status": "blocked",
                "route": "/lens/os-binding/execution/readiness",
                "execute_route": "/lens/os-binding/execute",
                "denials_route": "/lens/os-binding/denials",
                "ready": False,
                "execution_ready": False,
                "os_level_command_palette": False,
                "summon_anywhere": False,
                "denial_boundary_observed": True,
                "denial_receipt_readback_ready": True,
                "blocked_requirements": [
                    "global_hotkey_binding",
                    "summon_binding",
                    "resident_host",
                    "tray_presence",
                    "overlay_window",
                ],
                "blockers": [
                    "os_binding_execution_boundary_not_implemented",
                    "global_hotkey_binding_missing",
                    "summon_binding_missing",
                ],
                "next_smallest_truthful_gap": "os_binding_command_palette_execution_boundary",
                "governance": {
                    "read_only_contract": True,
                    "execution_authority": False,
                    "approval_decision_authority": False,
                    "memory_write": False,
                    "hotkey_registration_authority": False,
                    "summon_authority": False,
                },
            }
        ),
        encoding="utf-8",
    )


def test_lens_command_palette_os_binding_proof_composes_blocked_readbacks(
    tmp_path: Path,
) -> None:
    status_path = tmp_path / "lens-status.json"
    execution_readiness_path = tmp_path / "execution-readiness.json"
    _write_lens_status(status_path)
    _write_execution_readiness(execution_readiness_path)

    result = _run_script(
        "-Mode",
        "Status",
        "-StatusPath",
        str(status_path),
        "-ExecutionReadinessPath",
        str(execution_readiness_path),
    )

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
    assert payload["os_binding_candidate_observed"] is True
    assert payload["os_binding_execution_readiness_observed"] is True
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

    os_binding_candidate = payload["os_binding_candidate"]
    assert os_binding_candidate["kind"] == "lens.command_palette.os_binding_candidate"
    assert os_binding_candidate["status"] == "blocked"
    assert os_binding_candidate["candidate"] == "global_hotkey_to_lens_command_palette_bridge"
    assert os_binding_candidate["trigger"] == "Ctrl+Alt+Space"
    assert os_binding_candidate["binding_scope"] == "global"
    assert os_binding_candidate["route"] == "/lens/status"
    assert os_binding_candidate["local_surface"] == "chat_ui.command_palette"
    assert os_binding_candidate["bridge_script"] == "scripts/lens-command-palette.ps1"
    assert os_binding_candidate["proof_script"] == "scripts/lens-command-palette-os-binding-proof.ps1"
    assert os_binding_candidate["requires_approval_kind"] == ("lens.os_binding.command_palette_binding_authority")
    assert os_binding_candidate["required_authority"] == [
        "lens.os_binding.command_palette_binding_authority",
        "hotkey_registration_authority",
        "summon_authority",
        "local_process_launch_authority",
    ]
    assert os_binding_candidate["required_preflight_families"] == [
        "palette_binding",
        "global_hotkey_binding",
        "summon_binding",
        "authority",
    ]
    assert os_binding_candidate["blocked_by"] == [
        "os_level_command_palette_missing",
        "summon_anywhere_missing",
        "global_hotkey_binding_missing",
        "global_hotkey_binding_disabled",
        "global_hotkey_registration_disabled",
        "hotkey_registration_authority_not_granted",
        "lens_summon_binding_not_implemented",
        "summon_authority_not_granted",
        "local_process_launch_authority_not_granted",
    ]
    assert os_binding_candidate["current_authorized_effect"] == "readback_only_status"
    assert os_binding_candidate["candidate_effect_if_authorized"] == (
        "open_lens_command_palette_from_governed_os_binding"
    )
    assert os_binding_candidate["open_mode_authorized"] is False
    assert os_binding_candidate["open_mode_refusal"] == "lens_command_palette_open_not_authorized"
    assert os_binding_candidate["would_register_hotkey_now"] is False
    assert os_binding_candidate["would_open_palette_now"] is False
    assert os_binding_candidate["would_summon_anywhere_now"] is False
    assert os_binding_candidate["would_launch_process_now"] is False
    assert os_binding_candidate["would_write_memory_now"] is False
    assert os_binding_candidate["next_smallest_truthful_gap"] == "os_level_command_palette_binding"

    execution_readiness = payload["execution_readiness"]
    assert execution_readiness["status"] == "blocked"
    assert execution_readiness["source"] == "path"
    assert execution_readiness["evidence"] == str(execution_readiness_path)
    assert execution_readiness["route"] == "/lens/os-binding/execution/readiness"
    assert execution_readiness["execute_route"] == "/lens/os-binding/execute"
    assert execution_readiness["denials_route"] == "/lens/os-binding/denials"
    assert execution_readiness["ready"] is False
    assert execution_readiness["execution_ready"] is False
    assert execution_readiness["denial_boundary_observed"] is True
    assert execution_readiness["denial_receipt_readback_ready"] is True
    assert execution_readiness["blocked_requirements"] == [
        "global_hotkey_binding",
        "summon_binding",
        "resident_host",
        "tray_presence",
        "overlay_window",
    ]
    assert execution_readiness["blockers"] == [
        "os_binding_execution_boundary_not_implemented",
        "global_hotkey_binding_missing",
        "summon_binding_missing",
    ]
    assert execution_readiness["next_smallest_truthful_gap"] == ("os_binding_command_palette_execution_boundary")

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
    assert checks["os_binding_candidate_boundary"]["passed"] is True
    assert checks["os_binding_candidate_boundary"]["status"] == "candidate_blocked_readback_ready"
    assert checks["os_binding_execution_readiness"]["passed"] is True
    assert checks["os_binding_execution_readiness"]["status"] == "blocked_readback_ready"
    assert checks["os_binding_side_effects_denied"]["passed"] is True
    assert checks["os_binding_side_effects_denied"]["status"] == "diagnostic_bounded"

    assert payload["governance"] == {
        "diagnostic_only": True,
        "wraps_command_palette_shell_bridge": True,
        "wraps_summon_preflight": True,
        "wraps_tray_preflight": True,
        "wraps_overlay_preflight": True,
        "os_binding_candidate_boundary_readback": True,
        "wraps_os_binding_execution_readiness": True,
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


def test_lens_command_palette_os_binding_proof_uses_repo_readback_without_api(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["FRANCIS_ROOT"] = str(REPO_ROOT)
    env["FRANCIS_DATA_DIR"] = str(tmp_path / "data")

    result = _run_script(
        "-Mode",
        "Status",
        "-ApiBaseUrl",
        "http://127.0.0.1:1",
        "-TimeoutSeconds",
        "1",
        env=env,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout)
    assert payload["kind"] == "lens.command_palette.os_binding_blockers.proof"
    assert payload["status"] == "proof_passed"
    assert payload["ok"] is True
    assert payload["os_level_command_palette_binding_observed"] is True
    assert payload["os_binding_candidate_observed"] is True
    assert payload["os_binding_execution_readiness_observed"] is True
    assert payload["side_effects_denied"] is True
    assert payload["command_palette"]["status"] == "blocked"
    assert payload["command_palette"]["availability"] == "chat_ui_only"
    assert payload["command_palette"]["command_total"] > 0
    assert payload["os_binding_candidate"]["local_surface"] == "chat_ui.command_palette"
    execution_readiness = payload["execution_readiness"]
    assert execution_readiness["source"] == "python"
    assert (
        execution_readiness["evidence"] == "francis.lens.os_binding_authority.lens_os_binding_execution_readiness_audit"
    )
    assert execution_readiness["status"] == "blocked"
    assert execution_readiness["route"] == "/lens/os-binding/execution/readiness"
    assert execution_readiness["ready"] is False
    assert execution_readiness["execution_ready"] is False
    assert "os_binding_execution_boundary_not_implemented" in execution_readiness["blockers"]
    assert "global_hotkey_binding" in execution_readiness["blocked_requirements"]
    assert "summon_binding" in execution_readiness["blocked_requirements"]
    assert payload["governance"]["read_only_contract"] is True
    assert payload["governance"]["opens_palette"] is False
    assert payload["governance"]["execution_authority"] is False
    assert payload["governance"]["hotkey_registration_authority"] is False
