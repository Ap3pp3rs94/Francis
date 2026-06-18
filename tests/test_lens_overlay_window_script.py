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


def _run_overlay_window(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
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
        env=env,
        timeout=60,
    )


def test_lens_overlay_window_status_reports_missing_runtime(tmp_path: Path) -> None:
    proc = _run_overlay_window(
        "-Mode",
        "Status",
        "-VoiceEnvironmentScope",
        "ProcessOnly",
        "-DataDir",
        str(tmp_path / "data"),
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.overlay.window.runtime"
    assert payload["status"] == "missing"
    assert payload["ready"] is False
    assert payload["overlay_window"] is False
    assert payload["mcp_status_route"] == "/lens/mcp/status"
    assert payload["orb_mcp_status_route"] == "/lens/orb/mcp-status"
    assert payload["mcp_body_state_route"] == "/lens/mcp/status"
    assert payload["mcp_body_state"]["status"] == "linked"
    assert payload["mcp_body_state"]["read_only"] is True
    assert payload["mcp_body_state"]["grants_execution_authority"] is False
    assert payload["mcp_body_state"]["grants_mutation_authority"] is False
    assert payload["mcp_body_state"]["live_status"] == "not_requested"
    assert payload["mcp_body_state"]["semantic_state"] == "unknown"
    assert payload["mcp_body_state"]["semantic_source"] == "not_requested"
    assert payload["next_smallest_truthful_gap"] == "overlay_window_runtime"
    assert payload["overlay_runtime"]["requirement_state"] == "missing"
    assert payload["overlay_runtime"]["blocker"] == "overlay_window_runtime_missing"
    assert payload["overlay_runtime"]["expected_overlay_name"] == "Francis Lens Overlay"
    assert payload["overlay_runtime"]["expected_overlay_scope"] == "user_session"
    assert payload["overlay_runtime"]["mcp_status_route"] == "/lens/mcp/status"
    assert payload["overlay_runtime"]["orb_mcp_status_route"] == "/lens/orb/mcp-status"
    assert payload["orb_visual"]["autonomous_motion"] is False
    assert payload["orb_visual"]["motion_clock"] == "manual_drag_only"
    assert payload["orb_visual"]["motion_profile"] == "manual_drag_only"
    assert payload["orb_visual"]["desktop_roam_supported"] is True
    assert payload["orb_visual"]["desktop_roam_bounds"] == "work_area"
    assert payload["orb_visual"]["render_profile"]["source"] == "wpf_render_capability"
    assert payload["orb_visual"]["render_profile"]["motion_integrator"] == "elapsed_time_delta_clamped"
    assert payload["overlay_position"]["status"] == "window_unavailable"
    assert payload["overlay_position"]["desktop_roam_supported"] is True
    assert payload["overlay_position"]["desktop_roam_bounds"] == "work_area"
    readiness = payload["voice_provider_readiness"]
    assert readiness["kind"] == "lens.overlay.voice.provider_readiness"
    assert readiness["selected_provider"] == "WindowsSapi"
    assert readiness["environment_scope"] == "ProcessOnly"
    assert readiness["windows_sapi"]["credential_required"] is False
    assert readiness["elevenlabs"]["configured"] is False
    assert readiness["elevenlabs"]["api_key_present"] is False
    assert readiness["elevenlabs"]["voice_id_present"] is False
    assert set(readiness["elevenlabs"]["missing_configuration"]) == {"api_key", "voice_id"}
    assert readiness["elevenlabs"]["speed"] == 0.89
    assert readiness["elevenlabs"]["stability"] == 0.58
    assert readiness["elevenlabs"]["similarity_boost"] == 0.78
    assert readiness["elevenlabs"]["style"] == 0.0
    assert readiness["elevenlabs"]["credential_values_redacted"] is True
    assert readiness["stores_secret"] is False
    assert readiness["logs_text_payload"] is False
    assert payload["overlay_runtime"]["mcp_body_state"]["route"] == "/lens/mcp/status"
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
    assert payload["mcp_body_state_route"] == "/lens/mcp/status"
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
                "mcp_status_route": "/lens/mcp/status",
                "orb_mcp_status_route": "/lens/orb/mcp-status",
                "mcp_body_state": {
                    "status": "linked",
                    "source": "lens_orb_mcp_status_bridge",
                    "route": "/lens/mcp/status",
                    "read_only": True,
                    "grants_execution_authority": False,
                    "grants_mutation_authority": False,
                    "live_status": "ready",
                    "body_status": "ready",
                    "embodied_posture": "takeover_ready",
                    "semantic_state": "blocked",
                    "semantic_source": "francis.operator_mode.backlog_and_mission_continuity",
                    "orb_semantic_state": {
                        "ok": True,
                        "status": "blocked",
                        "semantic_state": "blocked",
                        "source": "francis.operator_mode.backlog_and_mission_continuity",
                        "truth_source": "mission_operation_readback",
                        "read_only": True,
                        "private_ui_state": False,
                        "visual_change": False,
                    },
                    "tool_count": 18,
                    "expected_tool_count": 18,
                    "resident": False,
                    "blockers_count": 0,
                },
                "voice": {
                    "kind": "lens.overlay.voice.runtime",
                    "status": "spoken",
                    "voice_provider": "ElevenLabs",
                    "microphone_capture": False,
                    "wake_listening": False,
                    "text_redacted": True,
                },
                "overlay_voice": {
                    "kind": "lens.overlay.voice.runtime",
                    "status": "listening",
                    "ok": True,
                    "voice_provider": "ElevenLabs",
                    "microphone_capture": True,
                    "wake_listening": True,
                    "wake_phrase": "hey francis",
                    "wake_confidence_threshold": 0.35,
                    "wake_alias_count": 6,
                    "transcript_redacted": True,
                    "persistent_overlay_readback": True,
                    "last_speech_receipt": False,
                    "audio_observed": True,
                    "microphone_signal_status": "no_signal",
                    "microphone_input_effective": False,
                    "needs_operator_audio_input_check": True,
                    "audio_signal_problem": "NoSignal",
                    "audio_level": 0,
                },
                "voice_provider_readiness": {
                    "kind": "lens.overlay.voice.provider_readiness",
                    "selected_provider": "ElevenLabs",
                    "environment_scope": "All",
                    "windows_sapi": {
                        "configured": True,
                        "credential_required": False,
                        "sends_text_to_remote_provider": False,
                    },
                    "elevenlabs": {
                        "configured": True,
                        "api_key_present": True,
                        "voice_id_present": True,
                        "missing_configuration": [],
                        "credential_values_redacted": True,
                    },
                    "active_provider_configured": True,
                    "remote_provider_requires_explicit_selection": True,
                    "stores_secret": False,
                    "logs_text_payload": False,
                },
                "overlay_window_visible": True,
                "always_on_top": True,
                "overlay_position": {
                    "status": "visible_position_observed",
                    "left": 800.0,
                    "top": 84.0,
                    "width": 220.0,
                    "height": 220.0,
                    "desktop_roam_supported": True,
                    "desktop_roam_bounds": "work_area",
                    "manual_drag_supported": True,
                    "anchor_left": 640.0,
                    "anchor_top": 360.0,
                    "range_x": 640.0,
                    "range_y": 360.0,
                    "roam_left": 0.0,
                    "roam_top": 0.0,
                    "roam_right": 1280.0,
                    "roam_bottom": 720.0,
                    "startup_left": 1012.0,
                    "startup_top": 84.0,
                    "grants_execution_authority": False,
                    "grants_mutation_authority": False,
                },
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
    assert payload["mcp_status_route"] == "/lens/mcp/status"
    assert payload["mcp_body_state"]["route"] == "/lens/mcp/status"
    assert payload["mcp_body_state"]["read_only"] is True
    assert payload["mcp_body_state"]["live_status"] == "ready"
    assert payload["mcp_body_state"]["tool_count"] == 18
    assert payload["mcp_body_state"]["expected_tool_count"] == 18
    assert payload["mcp_body_state"]["embodied_posture"] == "takeover_ready"
    assert payload["mcp_body_state"]["semantic_state"] == "blocked"
    assert payload["mcp_body_state"]["semantic_source"] == "francis.operator_mode.backlog_and_mission_continuity"
    assert payload["mcp_body_state"]["orb_semantic_state"]["semantic_state"] == "blocked"
    assert payload["mcp_body_state"]["orb_semantic_state"]["read_only"] is True
    assert payload["mcp_body_state"]["orb_semantic_state"]["private_ui_state"] is False
    assert payload["mcp_body_state"]["orb_semantic_state"]["visual_change"] is False
    assert payload["next_smallest_truthful_gap"] == "lens_voice_default_microphone_signal"
    assert payload["overlay_runtime"]["process_alive"] is True
    assert payload["overlay_runtime"]["runtime_process_alive"] is False
    assert payload["overlay_runtime"]["overlay_window_visible"] is True
    assert payload["overlay_runtime"]["always_on_top"] is True
    assert payload["overlay_position"]["status"] == "visible_position_observed"
    assert payload["overlay_position"]["left"] == 800.0
    assert payload["overlay_position"]["desktop_roam_supported"] is True
    assert payload["overlay_position"]["desktop_roam_bounds"] == "work_area"
    assert payload["overlay_runtime"]["overlay_position"]["roam_right"] == 1280.0
    assert payload["overlay_runtime"]["requirement_state"] == "visible"
    assert payload["overlay_runtime"]["blocker"] == ""
    assert payload["overlay_runtime"]["runtime_status_pid_matches_pid_file"] is True
    assert payload["overlay_runtime"]["mcp_body_state_route"] == "/lens/mcp/status"
    assert payload["voice"]["status"] == "spoken"
    assert payload["voice"]["wake_listening"] is False
    assert payload["voice_turn"] is None
    assert payload["overlay_voice"]["status"] == "listening"
    assert payload["overlay_voice"]["wake_listening"] is True
    assert payload["overlay_voice"]["wake_confidence_threshold"] == 0.35
    assert payload["overlay_voice"]["wake_alias_count"] == 6
    assert payload["overlay_voice"]["transcript_redacted"] is True
    assert payload["voice_input_ready"] is False
    assert payload["voice_input_status"] == "blocked"
    assert payload["voice_input_blocker"] == "microphone_no_signal"
    assert payload["next_voice_input_step"] == "select_or_unmute_default_windows_microphone"
    assert payload["voice_input_readiness"]["microphone_signal_status"] == "no_signal"
    assert payload["voice_input_readiness"]["needs_operator_audio_input_check"] is True
    assert payload["voice_input_readiness"]["audio_capture_endpoints"]["read_only"] is True
    assert payload["voice_input_readiness"]["audio_capture_endpoints"]["source"] == "windows_pnp_audio_endpoint"
    assert payload["voice_input_readiness"]["audio_capture_endpoints"]["endpoint_instance_ids_redacted"] is True
    assert payload["voice_input_readiness"]["default_capture_endpoint"]["read_only"] is True
    assert (
        payload["voice_input_readiness"]["default_capture_endpoint"]["source"]
        == "windows_coreaudio_default_capture_endpoint"
    )
    assert payload["voice_input_readiness"]["default_capture_endpoint"]["endpoint_id_redacted"] is True
    assert "default_capture_endpoint_resolved" in payload["voice_input_readiness"]
    assert "default_capture_endpoint_muted" in payload["voice_input_readiness"]
    assert "default_capture_endpoint_volume_scalar" in payload["voice_input_readiness"]
    assert payload["voice_input_readiness"]["explicit_endpoint_selection_supported"] is False
    assert payload["voice_input_readiness"]["speech_audio_input_tokens"]["read_only"] is True
    assert (
        payload["voice_input_readiness"]["speech_audio_input_tokens"]["source"] == "windows_sapi_audio_input_registry"
    )
    assert payload["voice_input_readiness"]["speech_audio_input_tokens"]["token_device_ids_redacted"] is True
    assert payload["voice_input_readiness"]["transcript_redacted"] is True
    assert payload["voice_input_readiness"]["grants_execution_authority"] is False
    assert payload["overlay_runtime"]["voice_input_blocker"] == "microphone_no_signal"
    assert payload["overlay_runtime"]["voice_input_ready"] is False
    assert payload["voice_provider_readiness"]["selected_provider"] == "ElevenLabs"
    assert payload["voice_provider_readiness"]["elevenlabs"]["credential_values_redacted"] is True
    assert payload["overlay_runtime"]["overlay_voice"]["persistent_overlay_readback"] is True
    assert payload["governance"]["read_only_contract"] is True
    assert payload["governance"]["overlay_control_authority"] is False
    assert payload["governance"]["local_process_launch_authority"] is False
    assert payload["governance"]["microphone_capture_active"] is True


def test_lens_overlay_window_status_projects_completed_voice_turn_handback(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    runtime_dir = data_dir / "runtime" / "lens-overlay"
    runtime_dir.mkdir(parents=True)
    pid = os.getpid()
    speech_pid = 999999
    turn_id = "voice_turn_test_handback"
    (runtime_dir / "lens-overlay.pid").write_text(str(pid), encoding="utf-8")
    (runtime_dir / "voice-playback-status.json").write_text(
        json.dumps(
            {
                "kind": "lens.overlay.voice.runtime",
                "status": "spoken",
                "ok": True,
                "playback_state_only": True,
                "speech_process_pid": speech_pid,
                "temp_audio_deleted": True,
                "updated_at": "2026-06-18T00:00:00Z",
            }
        ),
        encoding="utf-8",
    )
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
                "voice_turn": {
                    "kind": "lens.overlay.voice.turn_state",
                    "status": "speaking",
                    "active_turn_id": turn_id,
                    "turn_id": turn_id,
                    "speech_process_pid": speech_pid,
                    "speech_playback_status_path": "data/runtime/lens-overlay/voice-playback-status.json",
                    "speech_playback_async": True,
                },
            }
        ),
        encoding="utf-8",
    )

    proc = _run_overlay_window("-Mode", "Status", "-DataDir", str(data_dir))

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    voice_turn = payload["voice_turn"]
    assert voice_turn["status"] == "spoken"
    assert voice_turn["voice_turn_completed"] is True
    assert voice_turn["handback_ready"] is True
    assert voice_turn["handback_state"] == "speech_playback_spoken"
    assert voice_turn["playback_status"] == "spoken"
    assert voice_turn["playback_receipt_observed"] is True
    assert voice_turn["speech_process_alive"] is False
    assert voice_turn["completed_at"] == "2026-06-18T00:00:00Z"
    assert payload["overlay_runtime"]["voice_turn"]["status"] == "spoken"


def test_lens_overlay_voice_speak_requires_explicit_bounded_text(tmp_path: Path) -> None:
    proc = _run_overlay_window("-Mode", "Speak", "-DataDir", str(tmp_path / "data"), "-VoiceText", "")

    assert proc.returncode == 2, proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.overlay.voice.runtime"
    assert payload["status"] == "refused"
    assert payload["ok"] is False
    assert payload["error"] == "voice_text_required"
    assert payload["speech_output"] is True
    assert payload["microphone_capture"] is False
    assert payload["voice_input"] == "disabled_requires_explicit_microphone_authority"
    assert payload["wake_listening"] is False
    assert payload["selected_voice"] == "Microsoft Zira Desktop"
    assert payload["stores_transcript"] is False
    assert payload["requires_explicit_speak_command"] is True

    voice_status = tmp_path / "data" / "runtime" / "lens-overlay" / "voice-status.json"
    assert voice_status.is_file()
    receipt = json.loads(voice_status.read_text(encoding="utf-8-sig"))
    assert receipt["status"] == "refused"
    assert receipt["error"] == "voice_text_required"


def test_lens_overlay_synthetic_voice_turn_requires_explicit_bounded_text(tmp_path: Path) -> None:
    proc = _run_overlay_window(
        "-Mode",
        "SyntheticVoiceTurn",
        "-DataDir",
        str(tmp_path / "data"),
        "-VoiceText",
        "",
    )

    assert proc.returncode == 2, proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.overlay.voice.runtime"
    assert payload["status"] == "synthetic_voice_turn_refused"
    assert payload["ok"] is False
    assert payload["error"] == "synthetic_voice_turn_text_required"
    assert payload["voice_turn"] is True
    assert payload["synthetic_transcript"] is True
    assert payload["synthetic_voice_turn"] is True
    assert payload["synthetic_voice_turn_command"] is True
    assert payload["transcript_source"] == "operator_explicit_synthetic_voice_turn"
    assert payload["explicit_operator_text"] is True
    assert payload["microphone_speech"] is False
    assert payload["microphone_recognition_claimed"] is False
    assert payload["voice_recognition"] == "not_used_explicit_synthetic_transcript"
    assert payload["wake_phrase_detected"] is False
    assert payload["chat_bridge_status"] == "not_called"
    assert payload["speech_started"] is False
    assert payload["transcript_redacted"] is True
    assert payload["overlay_stores_transcript"] is False

    voice_status = tmp_path / "data" / "runtime" / "lens-overlay" / "voice-status.json"
    assert voice_status.is_file()
    receipt = json.loads(voice_status.read_text(encoding="utf-8-sig"))
    assert receipt["status"] == "synthetic_voice_turn_refused"
    assert receipt["synthetic_transcript"] is True
    assert receipt["wake_phrase_detected"] is False


def test_lens_overlay_elevenlabs_speak_requires_explicit_remote_config(tmp_path: Path) -> None:
    env = os.environ.copy()
    env.pop("FRANCIS_ELEVENLABS_API_KEY", None)
    env.pop("ELEVENLABS_API_KEY", None)
    env.pop("FRANCIS_ELEVENLABS_VOICE_ID", None)
    env.pop("ELEVENLABS_VOICE_ID", None)

    proc = _run_overlay_window(
        "-Mode",
        "Speak",
        "-DataDir",
        str(tmp_path / "data"),
        "-VoiceProvider",
        "ElevenLabs",
        "-VoiceEnvironmentScope",
        "ProcessOnly",
        "-VoiceText",
        "Francis voice check.",
        env=env,
    )

    assert proc.returncode == 2, proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.overlay.voice.runtime"
    assert payload["status"] == "refused"
    assert payload["ok"] is False
    assert payload["error"] == "elevenlabs_configuration_required"
    assert payload["voice_provider"] == "ElevenLabs"
    assert payload["source"] == "elevenlabs_text_to_speech"
    assert payload["remote_processing"] is True
    assert payload["sends_text_to_remote_provider"] is True
    assert payload["stores_transcript"] is False
    assert payload["stores_audio"] is False
    assert payload["audio_retention"] == "transient_deleted_after_playback"
    assert set(payload["missing_configuration"]) == {"api_key", "voice_id"}
    assert payload["text_redacted"] is True

    voice_status = tmp_path / "data" / "runtime" / "lens-overlay" / "voice-status.json"
    assert voice_status.is_file()
    receipt = json.loads(voice_status.read_text(encoding="utf-8-sig"))
    assert receipt["error"] == "elevenlabs_configuration_required"


def test_lens_audio_config_declares_elevenlabs_remote_tts_disabled_by_default() -> None:
    config = (_repo_root() / "config" / "models" / "specialized" / "audio.yaml").read_text(encoding="utf-8")

    assert "remote_providers:" in config
    assert 'id: "elevenlabs"' in config
    assert "enabled: false" in config
    assert "Hosted expressive TTS; requires network egress + credentials." in config


def test_lens_overlay_window_script_uses_atomic_state_and_owned_process_stop() -> None:
    script = (_repo_root() / "scripts" / "lens-overlay-window.ps1").read_text(encoding="utf-8")

    assert "function Test-OverlayRuntimeProcess" in script
    assert "function Stop-OverlayRuntimeProcess" in script
    assert "function New-McpBodyStateProjection" in script
    assert "function Read-McpBodyStateForOverlay" in script
    assert "function Format-McpBodyStateLabel" in script
    assert "function New-OrbEnergySurface" in script
    assert "function New-OrbTorusMesh" in script
    assert "function Add-Orb3DEnergyRing" in script
    assert "function New-OrbAutonomousMotionState" in script
    assert "function Update-OrbAutonomousMotion" in script
    assert "function Get-OverlayWpfRenderProfile" in script
    assert "function Set-OverlayHardwareRenderMode" in script
    assert "function New-OrbVisualProjection" in script
    assert "function Start-OrbFrameSyncedMotion" in script
    assert "function Stop-OrbFrameSyncedMotion" in script
    assert "[switch]$EnableAutonomousMotion" in script
    assert "function Invoke-OverlayVoiceSpeech" in script
    assert "function Invoke-OverlayElevenLabsVoiceSpeech" in script
    assert "function Invoke-OverlayAudioFilePlayback" in script
    assert "function Get-ScopedEnvironmentValue" in script
    assert "function Get-ScopedEnvironmentSource" in script
    assert "function New-OverlayVoiceProviderReadiness" in script
    assert "function New-OverlayRuntimeVoiceProjection" in script
    assert "function Get-VoiceEnvironmentTargets" in script
    assert "function Get-VoiceEnvironmentScopeNames" in script
    assert "function Get-ElevenLabsApiKey" in script
    assert "function Get-ElevenLabsVoiceId" in script
    assert "function Get-ElevenLabsApiKeySource" in script
    assert "function Get-ElevenLabsVoiceIdSource" in script
    assert "function Start-OverlayWakeListener" in script
    assert "function Get-OverlayVoiceReadback" in script
    assert "function Move-OverlayRuntimeStateFile" in script
    assert "function Join-OverlayProcessArguments" in script
    assert "function Update-OverlayMcpBodyStateLabel" in script
    assert "Invoke-RestMethod -Uri $Uri -Method Get" in script
    assert "francis_lens=orb_overlay" in script
    assert "chat_ui.orbGlyph.energy_reference" in script
    assert "wpf_3d_animated_energy_orb" in script
    assert "bounded_desktop_roam" in script
    assert "composition_target_rendering" in script
    assert "elapsed_time_delta_clamped" in script
    assert "render_profile = Get-OverlayWpfRenderProfile" in script
    assert "[System.Windows.Media.CompositionTarget]::add_Rendering" in script
    assert "[System.Windows.Media.CompositionTarget]::remove_Rendering" in script
    assert "Set-OverlayHardwareRenderMode" in script
    assert "$DeltaSeconds = [Math]::Min(0.05, $DeltaSeconds)" in script
    assert "$DriftY = ([Math]::Sin($Phase * 0.61)" in script
    assert "windows_sapi_speech_synthesis" in script
    assert "elevenlabs_text_to_speech" in script
    assert "https://api.elevenlabs.io/v1/text-to-speech/{0}?output_format={1}" in script
    assert "[double]$ElevenLabsSpeed = 0.89" in script
    assert "[double]$ElevenLabsStability = 0.58" in script
    assert "[double]$ElevenLabsSimilarityBoost = 0.78" in script
    assert "[double]$ElevenLabsStyle = 0.0" in script
    assert "[int]$VoiceVolume = 64" in script
    assert "speed = $Speed" in script
    assert "stability = $Stability" in script
    assert "similarity_boost = $SimilarityBoost" in script
    assert "style = $Style" in script
    assert "$Payload.speed = $Speed" in script
    assert "FRANCIS_ELEVENLABS_API_KEY" in script
    assert "FRANCIS_ELEVENLABS_VOICE_ID" in script
    assert "[System.EnvironmentVariableTarget]::User" in script
    assert "[System.EnvironmentVariableTarget]::Machine" in script
    assert "voice_provider_readiness = New-OverlayVoiceProviderReadiness" in script
    assert "overlay_voice = $OverlayVoice" in script
    assert "elevenlabs_configuration_required" in script
    assert "credential_values_redacted = $true" in script
    assert "logs_text_payload = $false" in script
    assert "transient_deleted_after_playback" in script
    assert "remote_text_sent = $true" in script
    assert "temp_audio_deleted" in script
    assert "explicit_wake_phrase_or_wake_prefixed_utterance" in script
    assert "disabled_requires_explicit_microphone_authority" in script
    assert "function Get-OverlayApiBaseUrl" in script
    assert "function Get-OverlayVoiceUseLlm" in script
    assert "function Get-OverlayVoiceSpeechPidPath" in script
    assert "function Get-OverlayVoicePlaybackStatusPath" in script
    assert "function Test-OverlayVoiceRecentSpeechPlayback" in script
    assert "function New-OverlayVoiceTextFile" in script
    assert "function Read-OverlayVoiceTextInput" in script
    assert "function Remove-OverlayVoiceTextFile" in script
    assert "function Test-OverlayPathWithinRoot" in script
    assert "function Test-OverlayVoiceSpeechProcess" in script
    assert "Get-ProcessAlive -ProcessId $ProcessId" in script
    assert "Get-Command -Name Get-CimInstance -ErrorAction SilentlyContinue" in script
    assert "function Stop-OverlayVoiceSpeechProcess" in script
    assert "function Start-OverlayVoiceSpeechProcess" in script
    assert "function New-OverlayWakeAliasList" in script
    assert "function Get-OverlayWakePrefixedUtterance" in script
    assert "function Test-OverlayWakePhraseRecognized" in script
    assert "function Get-OverlayTextDigest" in script
    assert "function Get-OverlayVoiceTurnStatusPath" in script
    assert "function Get-OverlayVoiceTurnReceiptPath" in script
    assert "function Get-OverlayVoiceTurnReadback" in script
    assert "function Start-OverlayVoiceTurn" in script
    assert "function Test-OverlayVoiceTurnCurrent" in script
    assert "function Update-OverlayVoiceTurnReceipt" in script
    assert "function Invoke-OverlayVoiceChatTurn" in script
    assert "SyntheticVoiceTurn" in script
    assert "EnableContinuousVoiceChat" in script
    assert "EnableVoiceLlm" in script
    assert "$UtteranceBuilder.AppendWildcard()" in script
    assert "Invoke-RestMethod -Uri $ChatUri -Method Post" in script
    assert "message = $BoundedUtterance" in script
    assert "actor = $ConversationActor" in script
    assert "voice_turn_id = $VoiceTurnId" in script
    assert "supersedes_voice_turn_id = $SupersedesVoiceTurnId" in script
    assert "$ConversationActor = 'lens.overlay.voice'" in script
    assert "$ChatRoute = '/chat/send'" in script
    assert "$UseLlm = Get-OverlayVoiceUseLlm" in script
    assert "FRANCIS_LENS_VOICE_USE_LLM" in script
    assert "voice_llm_enabled = [bool]$EnableVoiceLlm" in script
    assert (
        "voice_llm_request_source = if ($EnableVoiceLlm) { 'EnableVoiceLlm' } else { 'FRANCIS_LENS_VOICE_USE_LLM' }"
        in script
    )
    assert "$ArgumentList += '-EnableVoiceLlm'" in script
    assert "transcript_hash = Get-OverlayTextDigest -Text $BoundedUtterance" in script
    assert "overlay_stores_transcript = $false" in script
    assert "synthetic_voice_turn_text_required" in script
    assert "synthetic_transcript = [bool]$SyntheticTranscript" in script
    assert "synthetic_voice_turn_command = [bool]$SyntheticTranscript" in script
    assert "operator_explicit_synthetic_voice_turn" in script
    assert "microphone_continuous_dictation" in script
    assert "microphone_speech = (-not [bool]$SyntheticTranscript)" in script
    assert "microphone_recognition_claimed = (-not [bool]$SyntheticTranscript)" in script
    assert "not_used_explicit_synthetic_transcript" in script
    assert "system_speech_continuous_dictation" in script
    assert "wake_phrase_detected = [bool]$EffectiveWakePhraseDetected" in script
    assert "continuous_voice_chat = [bool]$ContinuousVoiceChat" in script
    assert (
        "continuous_voice_chat_mode = if ($ContinuousVoiceChat) { 'enabled_no_wake_phrase_required' } else { 'disabled_wake_phrase_required' }"
        in script
    )
    assert (
        "continuous_voice_chat_self_trigger_guard = 'suppress_no_wake_turns_while_owned_speech_process_active'"
        in script
    )
    assert "continuous_voice_suppressed_while_speaking" in script
    assert "owned_speech_recently_completed" in script
    assert "self_trigger_guard_window_seconds = 4" in script
    assert "Test-OverlayVoiceRecentSpeechPlayback -Root $script:LensOverlayWakeRoot -CooldownSeconds 4" in script
    assert "Test-OverlayVoiceSpeechProcess -ProcessId $SpeechProcessId" in script
    assert "-ContinuousVoiceChat $script:LensOverlayRequestedContinuousVoiceChat" in script
    assert "$ArgumentList += '-EnableContinuousVoiceChat'" in script
    assert "I received the test text, but the local chat bridge is not available right now." in script
    assert "-SyntheticTranscript $true" in script
    assert "chat_reply_redacted = $true" in script
    assert "speech_script_redacted = $true" in script
    assert "speech_script_transport = 'transient_local_file'" in script
    assert "speech_script_command_line_redacted = $true" in script
    assert "speech_script_retention = 'transient_deleted_after_playback'" in script
    assert "'-PlaybackStateOnly'" in script
    assert "'-VoiceTextPath'" in script
    assert "voice-playback-status.json" in script
    assert "lens-overlay-speech.pid" in script
    assert (
        "Start-Process -FilePath $PowerShell.Source -ArgumentList $ArgumentText -WindowStyle Hidden -PassThru" in script
    )
    assert "Stop-OverlayVoiceSpeechProcess -Root $Root -Reason 'barge_in_replaced_owned_speech_process'" in script
    assert "Remove-OverlayVoiceTextFile -Root $DataRoot -TextPath $VoiceTextPath" in script
    assert "voice-turn-status.json" in script
    assert "voice_turn_completed = $true" in script
    assert "handback_ready = $true" in script
    assert (
        "handback_state = if ($PlaybackStatus -eq 'spoken') { 'speech_playback_spoken' } else { 'speech_playback_not_spoken' }"
        in script
    )
    assert "playback_receipt_observed = $true" in script
    assert "Get-UtcTimestampStringProperty -Payload $Playback -Name 'updated_at' -Default ''" in script
    assert "voice_turn = Get-OverlayVoiceTurnReadback -Root $Root" in script
    assert "voice-turns" in script
    assert "Start-OverlayVoiceTurn -Root $Root -UtteranceText $BoundedUtterance" in script
    assert "Stop-OverlayVoiceSpeechProcess -Root $Root -Reason 'voice_turn_superseded_before_chat_reply'" in script
    assert "superseded_by_new_voice_turn" in script
    assert "superseded_by_turn_id = $TurnId" in script
    assert "speech_cancelled_at_supersession = [bool]$PriorSpeech.stopped" in script
    assert "thought_relevance_status = 'superseded_pending_result'" in script
    assert "thought_retention_policy = 'drop_superseded_reply_unless_operator_reasks'" in script
    assert "model_call_abort_requested = $false" in script
    assert "model_call_abort_observed = $false" in script
    assert "Test-OverlayVoiceTurnCurrent -Root $Root -TurnId $VoiceTurnId" in script
    assert "voice_chat_reply_superseded" in script
    assert "newer_voice_turn_active" in script
    assert "superseded_by_turn_id = $SupersededByTurnId" in script
    assert "chat_reply_suppressed = $true" in script
    assert "chat_trace_voice_turn_id = $VoiceTurnId" in script
    assert "chat_trace_supersedes_voice_turn_id = $SupersedesVoiceTurnId" in script
    assert "chat_trace_voice_turn_correlation = $ChatTraceVoiceTurnCorrelation" in script
    assert "chat_trace_stale_reply_suppression_supported = $ChatTraceStaleReplySuppressionSupported" in script
    assert "chat_trace_voice_turn_relevance_policy = $ChatTraceVoiceTurnRelevancePolicy" in script
    assert "chat_trace_stale_reply_suppression_owner = $ChatTraceStaleReplySuppressionOwner" in script
    assert "chat_trace_stale_reply_suppression_boundary = $ChatTraceStaleReplySuppressionBoundary" in script
    assert "chat_trace_model_call_abort_boundary = $ChatTraceModelCallAbortBoundary" in script
    assert "chat_trace_model_call_cancellation_supported = $ChatTraceModelCallCancellationSupported" in script
    assert (
        "chat_trace_backend_current_voice_turn_lookup_supported = $ChatTraceBackendCurrentVoiceTurnLookupSupported"
    ) in script
    assert "chat_trace_backend_stale_reply_drop_supported = $ChatTraceBackendStaleReplyDropSupported" in script
    assert "chat_trace_thought_relevance_pruning_supported = $ChatTraceThoughtRelevancePruningSupported" in script
    assert "chat_trace_thought_relevance_pruning_boundary = $ChatTraceThoughtRelevancePruningBoundary" in script
    assert "model_call_completed_after_superseded = $ChatModelResponseObserved" in script
    assert "thought_relevance_status = 'stale_reply_dropped'" in script
    assert "thought_retention_policy = 'drop_superseded_reply_keep_trace_metadata'" in script
    assert "thought_relevance_pruning_supported = $ChatTraceThoughtRelevancePruningSupported" in script
    assert "stale_reply_suppression_owner = 'lens.overlay'" in script
    assert "stale_reply_suppression_boundary = 'overlay_voice_turn_current_check'" in script
    assert "backend_stale_reply_drop_supported = $ChatTraceBackendStaleReplyDropSupported" in script
    assert "Update-OverlayVoiceTurnReceipt -Root $Root -TurnId $VoiceTurnId -Status 'speaking'" in script
    assert "speech_playback_async = [bool]$SpeechProcess.ok" in script
    assert "speech_playback_blocking = $false" in script
    assert "speech_process_pid = [int]$SpeechProcess.process_id" in script
    assert "wake_listener_released_before_speech_completion = [bool]$SpeechProcess.ok" in script
    assert "simultaneous_listen_while_speaking_supported = [bool]$SpeechProcess.ok" in script
    assert "simultaneous_work_while_speaking_supported = $false" in script
    assert "barge_in_supported = [bool]$SpeechProcess.ok" in script
    assert "barge_in_scope = 'cancel_owned_speech_process_on_next_wake_prefixed_utterance'" in script
    assert "latest_voice_turn_wins = $true" in script
    assert "stale_reply_suppression_supported = $true" in script
    assert "chat_reply_suppressed = $false" in script
    assert "thought_relevance_status = 'current_reply_spoken'" in script
    assert "thought_retention_policy = 'current_turn_active'" in script
    assert "model_call_cancellation_supported = $false" in script
    assert "arbitrary_audio_control = $false" in script
    assert "thought_cancellation_supported = $false" in script
    assert "lens_voice_model_call_abort_and_thought_relevance" in script
    assert "System.Speech.Synthesis.SpeechSynthesizer" in script
    assert "System.Speech.Recognition.SpeechRecognitionEngine" in script
    assert "System.Speech.Recognition.DictationGrammar" in script
    assert "Francis Lens wake-prefixed dictation fallback" in script
    assert "RecognizeAsync([System.Speech.Recognition.RecognizeMode]::Multiple)" in script
    assert "[double]$WakeConfidenceThreshold = 0.35" in script
    assert "'hey frances'" in script
    assert "'hi francis'" in script
    assert "'ok francis'" in script
    assert "recognition_threshold = $ConfidenceThreshold" in script
    assert "wake_rejected_low_confidence" in script
    assert "Wake phrase candidate was heard below confidence threshold" in script
    assert "Test-OverlayWakePhraseRecognized -RecognizedText $RecognizedText" in script
    assert "wake_rejected_no_wake_phrase" in script
    assert "Speech was recognized without the Francis wake phrase; no response was emitted." in script
    assert "speech_output_suppressed = $true" in script
    assert "dictation_fallback_enabled = $true" in script
    assert "wake_confidence_threshold = $ConfidenceThreshold" in script
    assert "wake_alias_count = $WakeAliasCount" in script
    assert "Add_AudioLevelUpdated" in script
    assert "audio_observed = $true" in script
    assert "audio_event_count = $script:LensOverlayWakeAudioEventCount" in script
    assert "has_observed_microphone_signal = $true" in script
    assert "microphone_signal_status = 'signal_observed'" in script
    assert "microphone_input_effective = $true" in script
    assert "Add_AudioSignalProblemOccurred" in script
    assert "audio_signal_problem" in script
    assert "microphone_signal_status = 'silence_after_signal'" in script
    assert "last_no_signal_after_signal_at" in script
    assert "microphone_signal_status = 'unknown_until_audio_signal'" in script
    assert "last_no_signal_before_signal_at" in script
    assert "needs_operator_audio_input_check = $false" in script
    assert "Add_SpeechDetected" in script
    assert "speech_detected = $true" in script
    assert "speech_detected_count = $script:LensOverlayWakeSpeechDetectedCount" in script
    assert "Add_SpeechHypothesized" in script
    assert "speech_hypothesis_count = $script:LensOverlayWakeSpeechHypothesisCount" in script
    assert "Add_SpeechRecognitionRejected" in script
    assert "speech_rejected_count = $script:LensOverlayWakeSpeechRejectedCount" in script
    assert "speech_recognition_diagnostics = 'redacted_counts_only'" in script
    assert "wake_acknowledged" in script
    assert "Microsoft Zira Desktop" in script
    assert "System.Windows.Controls.Viewport3D" in script
    assert "System.Windows.Media.Media3D.PerspectiveCamera" in script
    assert "System.Windows.Media.Media3D.GeometryModel3D" in script
    assert "System.Windows.Media.Animation.DoubleAnimation" in script
    assert "MCP body-state" in script
    assert "Tools: {0}/{1}" in script
    assert "Takeover: {0} | Input: {1} | Blockers: {2}" in script
    assert "$Form.WindowStyle = [System.Windows.WindowStyle]::None" in script
    assert "$Form.AllowsTransparency = $true" in script
    assert "$Form.Background = [System.Windows.Media.Brushes]::Transparent" in script
    assert "$Form.ShowInTaskbar = $true" in script
    assert "$Form.TopMost = $true" in script
    assert "$EnergyRoot.Add_MouseLeftButtonDown" in script
    assert "$script:LensOverlayWindow.DragMove()" in script
    assert "Reset-OrbAutonomousMotionAnchor" in script
    assert "bounded_desktop_roam" in script
    assert "$AutonomousMotionEnabled = [bool]$EnableAutonomousMotion -and -not [bool]$DisableAutonomousMotion" in script
    assert "desktop_roam_supported = $true" in script
    assert "desktop_roam_bounds = 'work_area'" in script
    assert "roam_left = $MinimumLeft" in script
    assert "roam_right = $MaximumLeft" in script
    assert "overlay_position = New-OverlayWindowPositionProjection" in script
    assert "overlay_position = $Readback.overlay_position" in script
    assert "function Write-OverlayPositionState" in script
    assert "function Write-OrbAutonomousMotionPositionReceipt" in script
    assert "LensOverlayLastPositionReceiptSeconds" in script
    assert "(($FrameSeconds - $LastReceiptSeconds) -lt 1.0)" in script
    assert "Write-OrbAutonomousMotionPositionReceipt -Window $script:LensOverlayWindow" in script
    assert "$MotionSubscription = Start-OrbFrameSyncedMotion" in script
    assert "if ($AutonomousMotionEnabled) {" in script
    assert "autonomous_motion = $AutonomousMotion" in script
    assert "voice = Get-OverlayVoiceReadback -Root $Root" in script
    assert "overlay_voice = $Readback.overlay_voice" in script
    assert "voice_input_readiness = $Readback.voice_input_readiness" in script
    assert "voice_input_blocker = $VoiceInputBlocker" in script
    assert "microphone_capture = $WakeListening" in script
    assert "function Get-OverlayVoiceInputReadiness" in script
    assert "function Get-OverlayAudioCaptureEndpointReadback" in script
    assert "function Get-OverlayDefaultCaptureEndpointReadback" in script
    assert "Get-PnpDevice -Class AudioEndpoint" in script
    assert "windows_coreaudio_default_capture_endpoint" in script
    assert "LensOverlayCoreAudioProbe" in script
    assert "GetDefaultAudioEndpoint(EDataFlow.eCapture, ERole.eCommunications" in script
    assert "endpoint_instance_ids_redacted = $true" in script
    assert "current_overlay_uses_system_speech_default_audio_device" in script
    assert "function Get-OverlaySpeechAudioInputTokenReadback" in script
    assert "windows_sapi_audio_input_registry" in script
    assert "HKCU:\\Software\\Microsoft\\Speech\\AudioInput\\TokenEnums\\MMAudioIn" in script
    assert "token_device_ids_redacted = $true" in script
    assert "microphone_no_signal" in script
    assert "select_or_unmute_default_windows_microphone" in script
    assert (
        "microphone_capture_active = (Get-BoolProperty -Payload $Readback.overlay_voice -Name 'microphone_capture' -Default $false)"
        in script
    )
    assert "$script:LensOverlayWakeRecognizer = Start-OverlayWakeListener" in script
    assert "-Provider $script:LensOverlayRequestedVoiceProvider" in script
    assert "$ArgumentList += '-EnableWakeListen'" in script
    assert "$ArgumentList += '-ElevenLabsUseSpeakerBoost'" in script
    assert "'-VoiceProvider'" in script
    assert "'-ElevenLabsVoiceId'" in script
    assert "'-ElevenLabsSpeed'" in script
    assert "'-VoiceEnvironmentScope'" in script
    assert "'-WakeConfidenceThreshold'" in script
    assert "-RemoteSpeed $script:LensOverlayRequestedElevenLabsSpeed" in script
    assert "$ArgumentText = Join-OverlayProcessArguments -Arguments $ArgumentList" in script
    assert "Start-Process -FilePath $PowerShell.Source -ArgumentList $ArgumentText" in script
    assert "stores_transcript = $false" in script
    assert "function Paint-OverlayOrb" not in script
    assert "TransparencyKey" not in script
    assert "BackgroundImage" not in script
    assert "headless_browser_alpha_screenshot" not in script
    assert "playwright screenshot" not in script
    assert "$RefreshTimer.Interval = [TimeSpan]::FromSeconds(5)" in script
    assert "mcp_body_state = $McpBodyState" in script
    assert "orb_semantic_state" in script
    assert "semantic_state" in script
    assert "semantic_source" in script
    assert "orb_visual = $OrbVisual" in script
    assert "status.{0}.tmp" in script
    assert "Move-OverlayRuntimeStateFile -TempPath $TempPath -DestinationPath $StatusPath" in script
    assert "[System.IO.File]::Replace($TempPath, $DestinationPath, $BackupPath)" in script
    assert "runtime_process_alive = $RuntimeProcessAlive" in script
    assert "Stop-OverlayRuntimeProcess -ProcessId ([int]$TimedOut.pid)" in script
