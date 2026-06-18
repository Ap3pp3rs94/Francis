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


def _run_preflight(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            _powershell(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(_repo_root() / "scripts" / "lens-overlay-preflight.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
    )


def test_lens_overlay_preflight_reports_disabled_window_without_authority(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    proc = _run_preflight("-Mode", "Status", "-DataDir", str(data_dir))

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.overlay.preflight"
    assert payload["status"] == "blocked"
    assert payload["ready"] is False
    assert Path(payload["data_root"]) == data_dir
    assert payload["overlay_name"] == "Francis Lens Overlay"
    assert payload["required_before_enable"] == [
        "resident_host_process",
        "tray_presence",
        "overlay_window",
        "always_on_top_policy",
        "global_hotkey_binding",
        "summon_binding",
    ]
    assert payload["overlay"]["window_enabled"] is False
    assert payload["overlay"]["always_on_top"] is False
    assert payload["resident_host_process"]["process_alive"] is False
    assert payload["resident_host_process"]["requirement_state"] == "missing"
    assert payload["resident_host_process"]["blocker"] == "resident_host_process_missing"
    assert payload["overlay"]["overlay_runner"] == "scripts/lens-overlay-window.ps1"
    assert payload["overlay_runtime"]["ready"] is False
    assert payload["overlay_runtime"]["requirement_state"] == "missing"
    assert payload["overlay_runtime"]["blocker"] == "overlay_window_runtime_missing"
    assert "overlay_window_disabled" in payload["blockers"]
    assert "resident_host_process_missing" in payload["blockers"]
    assert "overlay_control_authority_not_granted" in payload["blockers"]
    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["overlay_config"]["status"] == "present_disabled"
    assert checks["window_enabled"]["status"] == "disabled"
    assert checks["always_on_top"]["status"] == "disabled"
    assert checks["host_preflight"]["status"] == "present"
    assert checks["tray_preflight"]["status"] == "present"
    assert checks["overlay_runner"]["status"] == "present"
    assert checks["runtime_state"]["status"] == "missing"
    assert checks["overlay_runtime"]["status"] == "missing"
    assert checks["overlay_control_authority"]["status"] == "blocked"
    assert payload["governance"] == {
        "read_only_contract": True,
        "execution_authority": False,
        "approval_decision_authority": False,
        "memory_write": False,
        "overlay_control_authority": False,
        "window_management_authority": False,
        "summon_authority": False,
        "capture_authority": False,
        "new_sensing_authority": False,
        "local_process_launch_authority": False,
        "tray_registration_authority": False,
        "mutation_authority_granted": False,
    }


def test_lens_overlay_preflight_rejects_stale_runtime_pid(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    runtime_dir = data_dir / "runtime" / "lens-host"
    runtime_dir.mkdir(parents=True)
    (runtime_dir / "status.json").write_text(
        json.dumps(
            {
                "kind": "lens.host.runtime_state",
                "status": "resident_running",
                "pid": 999999,
            }
        ),
        encoding="utf-8",
    )
    (runtime_dir / "lens-host.pid").write_text("1", encoding="utf-8")

    proc = _run_preflight("-Mode", "Status", "-DataDir", str(data_dir))

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    process = payload["resident_host_process"]
    assert process["process_alive"] is False
    assert process["runtime_state_exists"] is True
    assert process["runtime_status_kind"] == "lens.host.runtime_state"
    assert process["runtime_status"] == "resident_running"
    assert process["runtime_status_pid"] == 999999
    assert process["pid"] == 1
    assert process["runtime_status_pid_matches_pid_file"] is False
    assert process["requirement_state"] == "stale_or_unverified"
    assert process["blocker"] == "resident_host_process_missing"
    assert "resident_host_process_missing" in payload["blockers"]
    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["runtime_state"]["status"] == "stale_or_unverified"


def test_lens_overlay_preflight_surfaces_live_voice_input_blocker(tmp_path: Path) -> None:
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
                "overlay_voice": {
                    "kind": "lens.overlay.voice.runtime",
                    "status": "listening",
                    "ok": True,
                    "microphone_capture": True,
                    "wake_listening": True,
                    "microphone_signal_status": "no_signal",
                    "microphone_input_effective": False,
                    "needs_operator_audio_input_check": True,
                    "audio_signal_problem": "NoSignal",
                    "audio_level": 0,
                    "transcript_redacted": True,
                },
            }
        ),
        encoding="utf-8",
    )

    proc = _run_preflight("-Mode", "Status", "-DataDir", str(data_dir))

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    overlay_runtime = payload["overlay_runtime"]
    assert overlay_runtime["ready"] is True
    assert overlay_runtime["voice_input_ready"] is False
    assert overlay_runtime["voice_input_status"] == "blocked"
    assert overlay_runtime["voice_input_blocker"] == "microphone_no_signal"
    assert overlay_runtime["next_voice_input_step"] == "select_or_unmute_default_windows_microphone"
    assert overlay_runtime["voice_input_readiness"]["needs_operator_audio_input_check"] is True
    assert overlay_runtime["voice_input_readiness"]["audio_capture_endpoints"]["read_only"] is True
    assert overlay_runtime["voice_input_readiness"]["audio_capture_endpoints"]["source"] == "windows_pnp_audio_endpoint"
    assert overlay_runtime["voice_input_readiness"]["default_capture_endpoint"]["read_only"] is True
    assert (
        overlay_runtime["voice_input_readiness"]["default_capture_endpoint"]["source"]
        == "windows_coreaudio_default_capture_endpoint"
    )
    assert overlay_runtime["voice_input_readiness"]["default_capture_endpoint"]["endpoint_id_redacted"] is True
    assert "default_capture_endpoint_resolved" in overlay_runtime["voice_input_readiness"]
    assert "default_capture_endpoint_muted" in overlay_runtime["voice_input_readiness"]
    assert "default_capture_endpoint_volume_scalar" in overlay_runtime["voice_input_readiness"]
    assert overlay_runtime["voice_input_readiness"]["explicit_endpoint_selection_supported"] is False
    assert overlay_runtime["voice_input_readiness"]["speech_audio_input_tokens"]["read_only"] is True
    assert (
        overlay_runtime["voice_input_readiness"]["speech_audio_input_tokens"]["source"]
        == "windows_sapi_audio_input_registry"
    )
    assert overlay_runtime["voice_input_readiness"]["speech_audio_input_tokens"]["token_device_ids_redacted"] is True
    assert overlay_runtime["voice_input_readiness"]["transcript_redacted"] is True
    assert "microphone_no_signal" in payload["blockers"]
    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["voice_input"]["status"] == "blocked"


def test_lens_overlay_preflight_refuses_open_actions() -> None:
    proc = _run_preflight("-Mode", "Open")

    assert proc.returncode == 2
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.overlay.preflight"
    assert payload["status"] == "refused"
    assert payload["ok"] is False
    assert payload["error"] == "lens_overlay_action_not_authorized"
    assert payload["governance"]["overlay_control_authority"] is False
    assert payload["governance"]["local_process_launch_authority"] is False
