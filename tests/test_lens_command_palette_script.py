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


def _run_palette(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            _powershell(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(_repo_root() / "scripts" / "lens-command-palette.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
        timeout=30,
        env=env,
    )


def test_lens_command_palette_shell_bridge_reads_status_without_os_binding(tmp_path: Path) -> None:
    status_path = tmp_path / "lens-status.json"
    status_path.write_text(
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
                    "command_total": 2,
                    "commands": [
                        {
                            "id": "nav.approvals",
                            "label": "Open Approvals",
                            "group": "Navigation",
                            "route": "/approvals/list?status=pending",
                            "action": "open_surface",
                            "mutates": False,
                            "execution_authority": False,
                            "approval_decision_authority": False,
                            "memory_write": False,
                        },
                        {
                            "id": "mode.pilot",
                            "label": "Switch to Pilot",
                            "group": "Control",
                            "route": "/system/operator_mode",
                            "action": "declare_control_mode",
                            "mutates": True,
                            "write_guard": "system.write plus operator posture",
                            "execution_authority": False,
                            "approval_decision_authority": False,
                            "memory_write": False,
                        },
                    ],
                },
            }
        ),
        encoding="utf-8",
    )

    proc = _run_palette("-Mode", "Status", "-StatusPath", str(status_path))

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.command_palette.shell_bridge"
    assert payload["status"] == "blocked"
    assert payload["ok"] is True
    assert payload["backend_source"] == "status_path"
    assert payload["readback_ready"] is True
    assert payload["os_level_command_palette"] is False
    assert payload["summon_anywhere"] is False
    assert payload["url_entrypoint_ready"] is True
    assert payload["url_entrypoint"]["route"] == "/?francis_lens=command_palette"
    assert payload["url_entrypoint"]["opens_palette_in_chat_ui"] is True
    assert payload["url_entrypoint"]["os_level_command_palette"] is False
    assert payload["availability"] == "chat_ui_only"
    assert payload["route"] == "/lens/status"
    assert payload["local_surface"] == "chat_ui.command_palette"
    assert payload["command_total"] == 2
    assert [item["id"] for item in payload["commands"]] == ["nav.approvals", "mode.pilot"]
    assert payload["commands"][1]["mutates"] is True
    assert payload["commands"][1]["write_guard"] == "system.write plus operator posture"
    assert payload["commands"][1]["execution_authority"] is False
    assert "os_level_command_palette_missing" in payload["blockers"]
    assert "summon_anywhere_missing" in payload["blockers"]
    assert "global_hotkey_binding_missing" in payload["blockers"]
    assert payload["next_smallest_truthful_gap"] == "os_level_command_palette_binding"
    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["lens_status_readback"]["status"] == "available"
    assert checks["command_palette_readback"]["status"] == "readback_ready"
    assert checks["os_level_palette_binding"]["status"] == "blocked"
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


def test_lens_command_palette_shell_bridge_uses_python_readback_without_api(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["FRANCIS_ROOT"] = str(_repo_root())
    env["FRANCIS_DATA_DIR"] = str(tmp_path / "data")

    proc = _run_palette(
        "-Mode",
        "Status",
        "-ApiBaseUrl",
        "http://127.0.0.1:1",
        "-TimeoutSeconds",
        "1",
        env=env,
    )

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.command_palette.shell_bridge"
    assert payload["status"] == "blocked"
    assert payload["ok"] is True
    assert payload["backend_source"] == "python"
    assert payload["backend_evidence"] == "francis.lens.status.lens_status"
    assert payload["readback_ready"] is True
    assert payload["availability"] == "chat_ui_only"
    assert payload["command_total"] > 0
    assert payload["url_entrypoint_ready"] is True
    assert payload["url_entrypoint"]["route"] == "/?francis_lens=command_palette"
    assert payload["os_level_command_palette"] is False
    assert payload["summon_anywhere"] is False
    assert "os_level_command_palette_missing" in payload["blockers"]
    assert payload["governance"]["opens_palette"] is False
    assert payload["governance"]["execution_authority"] is False
    assert payload["governance"]["hotkey_registration_authority"] is False


def test_lens_command_palette_shell_bridge_local_open_dry_run_uses_chat_ui_entrypoint(
    tmp_path: Path,
) -> None:
    status_path = tmp_path / "lens-status.json"
    status_path.write_text(
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

    proc = _run_palette(
        "-Mode",
        "LocalOpen",
        "-StatusPath",
        str(status_path),
        "-ChatUiBaseUrl",
        "http://127.0.0.1:5173",
        "-NoLaunch",
    )

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.command_palette.shell_bridge"
    assert payload["status"] == "local_open_ready"
    assert payload["ok"] is True
    assert payload["readback_ready"] is True
    assert payload["local_open_mode"] == "LocalOpen"
    assert payload["local_open_available"] is True
    assert payload["local_open_target_url"] == "http://127.0.0.1:5173/?francis_lens=command_palette"
    assert payload["chat_ui_base_url"] == "http://127.0.0.1:5173"
    assert payload["would_open_palette"] is True
    assert payload["opened"] is False
    assert payload["no_launch"] is True
    assert payload["os_level_command_palette"] is False
    assert payload["summon_anywhere"] is False
    assert "os_level_command_palette_missing" in payload["blockers"]
    assert payload["governance"]["read_only_contract"] is False
    assert payload["governance"]["opens_palette"] is True
    assert payload["governance"]["execution_authority"] is False
    assert payload["governance"]["approval_decision_authority"] is False
    assert payload["governance"]["memory_write"] is False
    assert payload["governance"]["hotkey_registration_authority"] is False
    assert payload["governance"]["tray_registration_authority"] is False
    assert payload["governance"]["overlay_control_authority"] is False
    assert payload["governance"]["summon_authority"] is False
    assert payload["governance"]["local_process_launch_authority"] is False
    assert payload["governance"]["mutation_authority_granted"] is False


def test_lens_command_palette_shell_bridge_refuses_open_mode(tmp_path: Path) -> None:
    status_path = tmp_path / "lens-status.json"
    execution_readiness_path = tmp_path / "execution-readiness.json"
    status_path.write_text(
        json.dumps(
            {
                "kind": "lens.status",
                "command_palette": {
                    "status": "readback_ready",
                    "availability": "chat_ui_only",
                    "summon_anywhere": False,
                    "commands": [{"id": "nav.orb", "label": "Open ORB", "group": "Navigation"}],
                },
            }
        ),
        encoding="utf-8",
    )
    execution_readiness_path.write_text(
        json.dumps(
            {
                "kind": "lens.os_binding.command_palette_binding.execution_readiness",
                "status": "blocked",
                "route": "/lens/os-binding/execution/readiness",
                "execute_route": "/lens/os-binding/execute",
                "ready": False,
                "execution_ready": False,
                "authority_granted": True,
                "os_level_command_palette_binding_authority": True,
                "denial_boundary_observed": True,
                "denial_receipt_readback_ready": True,
                "execution_prerequisites_ready": False,
                "required_before_execution_boundary": [
                    "system_write_permission",
                    "os_binding_readiness_readback",
                    "os_binding_implementation_plan",
                    "os_binding_authority_grant",
                    "os_binding_execution_denial_boundary",
                    "os_binding_denial_receipts",
                    "global_hotkey_binding",
                    "summon_binding",
                    "resident_host",
                    "tray_presence",
                    "overlay_window",
                ],
                "blocked_requirements": [
                    "global_hotkey_binding",
                    "summon_binding",
                    "resident_host",
                ],
                "blocked_execution_prerequisites": [
                    "global_hotkey_binding",
                    "summon_binding",
                    "resident_host",
                ],
                "blockers": [
                    "global_hotkey_binding_missing",
                    "summon_binding_missing",
                    "resident_host_process_missing",
                    "os_binding_execution_boundary_not_implemented",
                ],
                "next_smallest_truthful_gap": "os_binding_execution_prerequisites",
                "execution_boundary_handoff": {
                    "status": "blocked_by_prerequisites",
                    "route": "/lens/os-binding/execute",
                    "readiness_route": "/lens/os-binding/execution/readiness",
                    "next_step": "resolve_os_binding_execution_prerequisites_before_execution_boundary",
                    "next_smallest_truthful_gap": "os_binding_execution_prerequisites",
                    "required_before_execution_boundary": [
                        "system_write_permission",
                        "os_binding_readiness_readback",
                        "os_binding_implementation_plan",
                        "os_binding_authority_grant",
                        "os_binding_execution_denial_boundary",
                        "os_binding_denial_receipts",
                        "global_hotkey_binding",
                        "summon_binding",
                        "resident_host",
                        "tray_presence",
                        "overlay_window",
                    ],
                    "blocked_requirements": [
                        "global_hotkey_binding",
                        "summon_binding",
                        "resident_host",
                    ],
                    "blocked_surface_prerequisites": [
                        "global_hotkey_binding",
                        "summon_binding",
                        "resident_host",
                    ],
                    "read_only_contract": True,
                    "would_execute": False,
                    "would_open_palette": False,
                    "would_register_hotkey": False,
                    "would_summon": False,
                    "would_control_overlay": False,
                    "would_launch_process": False,
                    "would_write_memory": False,
                },
                "governance": {
                    "read_only_contract": True,
                    "execution_authority": False,
                    "approval_decision_authority": False,
                    "memory_write": False,
                    "summon_authority": False,
                    "hotkey_registration_authority": False,
                    "mutation_authority_granted": False,
                },
            }
        ),
        encoding="utf-8",
    )

    proc = _run_palette(
        "-Mode",
        "Open",
        "-StatusPath",
        str(status_path),
        "-ExecutionReadinessPath",
        str(execution_readiness_path),
    )

    assert proc.returncode == 2
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.command_palette.shell_bridge"
    assert payload["status"] == "refused"
    assert payload["ok"] is False
    assert payload["error"] == "lens_command_palette_open_not_authorized"
    execution_readiness = payload["execution_readiness"]
    assert execution_readiness["source"] == "execution_readiness_path"
    assert execution_readiness["status"] == "blocked"
    assert execution_readiness["route"] == "/lens/os-binding/execution/readiness"
    assert execution_readiness["execute_route"] == "/lens/os-binding/execute"
    assert execution_readiness["ready"] is False
    assert execution_readiness["execution_ready"] is False
    assert execution_readiness["authority_granted"] is True
    assert execution_readiness["os_level_command_palette_binding_authority"] is True
    assert execution_readiness["denial_boundary_observed"] is True
    assert execution_readiness["denial_receipt_readback_ready"] is True
    assert execution_readiness["execution_prerequisites_ready"] is False
    assert execution_readiness["blocked_requirements"] == [
        "global_hotkey_binding",
        "summon_binding",
        "resident_host",
    ]
    assert execution_readiness["blocked_execution_prerequisites"] == [
        "global_hotkey_binding",
        "summon_binding",
        "resident_host",
    ]
    assert "os_binding_execution_boundary_not_implemented" in execution_readiness["blockers"]
    assert execution_readiness["next_smallest_truthful_gap"] == "os_binding_execution_prerequisites"
    handoff = execution_readiness["execution_boundary_handoff"]
    assert handoff["status"] == "blocked_by_prerequisites"
    assert handoff["next_step"] == "resolve_os_binding_execution_prerequisites_before_execution_boundary"
    assert handoff["next_smallest_truthful_gap"] == "os_binding_execution_prerequisites"
    assert handoff["blocked_requirements"] == execution_readiness["blocked_execution_prerequisites"]
    assert handoff["read_only_contract"] is True
    assert handoff["would_execute"] is False
    assert handoff["would_open_palette"] is False
    assert handoff["would_register_hotkey"] is False
    assert handoff["would_summon"] is False
    assert handoff["would_control_overlay"] is False
    assert handoff["would_launch_process"] is False
    assert handoff["would_write_memory"] is False
    assert payload["refusal_blockers"] == execution_readiness["blockers"]
    assert payload["governance"]["execution_readiness_readback"] is True
    assert payload["governance"]["execution_readiness_route"] == "/lens/os-binding/execution/readiness"
    assert payload["governance"]["opens_palette"] is False
    assert payload["governance"]["hotkey_registration_authority"] is False
    assert payload["governance"]["execution_authority"] is False
