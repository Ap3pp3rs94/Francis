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
    env = os.environ.copy()
    for name in (
        "FRANCIS_ELEVENLABS_API_KEY",
        "ELEVENLABS_API_KEY",
        "FRANCIS_ELEVENLABS_VOICE_ID",
        "ELEVENLABS_VOICE_ID",
        "FRANCIS_ELEVENLABS_VOICE_NAME",
        "FRANCIS_ELEVENLABS_VOICE_LABEL",
        "ELEVENLABS_VOICE_NAME",
    ):
        env.pop(name, None)

    proc = _run_overlay_window(
        "-Mode",
        "Status",
        "-VoiceEnvironmentScope",
        "ProcessOnly",
        "-DataDir",
        str(tmp_path / "data"),
        env=env,
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
    assert payload["orb_visual"]["right_corner_locked"] is True
    assert payload["orb_visual"]["default_anchor"] == "bottom_right"
    assert payload["orb_visual"]["motion_clock"] == "anchored_static"
    assert payload["orb_visual"]["motion_profile"] == "right_corner_locked"
    assert payload["orb_visual"]["manual_drag_supported"] is False
    assert payload["orb_visual"]["desktop_roam_supported"] is False
    assert payload["orb_visual"]["desktop_roam_bounds"] == "virtual_screen"
    assert payload["orb_visual"]["render_profile"]["source"] == "wpf_render_capability"
    assert payload["orb_visual"]["render_profile"]["motion_integrator"] == "elapsed_time_delta_clamped"
    ring_color_contract = payload["orb_visual"]["ring_color_contract"]
    assert ring_color_contract["kind"] == "lens.overlay.orb_ring_color_contract"
    assert ring_color_contract["source"] == "docs/operations/ORB_VISUAL_LOCK.md"
    assert ring_color_contract["render_source"] == "native/orb/native_orb_renderer.cpp"
    assert ring_color_contract["visual_contract"] == "native_cpp_orb.liquid_streamer_identity"
    assert ring_color_contract["renderer"] == "native_cpp_orb_renderer"
    assert ring_color_contract["state_driven_render_object"] is True
    assert ring_color_contract["ring_family"]["main_streamer_ring_count"] == 15
    assert ring_color_contract["ring_family"]["single_identity_ring_count"] == 20
    assert ring_color_contract["glow_family"]["outer_glow_primary"] == "#DAEEFF"
    assert payload["overlay_position"]["status"] == "window_unavailable"
    assert payload["overlay_position"]["right_corner_locked"] is True
    assert payload["overlay_position"]["default_anchor"] == "bottom_right"
    assert payload["overlay_position"]["desktop_roam_supported"] is False
    assert payload["overlay_position"]["desktop_roam_bounds"] == "work_area"
    assert payload["overlay_position"]["manual_drag_supported"] is False
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


def test_lens_overlay_window_status_labels_configured_elevenlabs_voice_as_emma(tmp_path: Path) -> None:
    env = os.environ.copy()
    env.pop("FRANCIS_ELEVENLABS_API_KEY", None)
    env.pop("ELEVENLABS_API_KEY", None)
    env["FRANCIS_ELEVENLABS_VOICE_ID"] = "56bWURjYFHyYyVf490Dp"
    env["FRANCIS_ELEVENLABS_VOICE_NAME"] = "Emma"

    proc = _run_overlay_window(
        "-Mode",
        "Status",
        "-VoiceEnvironmentScope",
        "ProcessOnly",
        "-VoiceProvider",
        "ElevenLabs",
        "-DataDir",
        str(tmp_path / "data"),
        env=env,
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["overlay_voice"]["voice_provider"] == "ElevenLabs"
    assert payload["overlay_voice"]["selected_voice"] == "Emma"
    assert payload["overlay_voice"]["voice_lens_orb_identity"] == "Francis"
    assert payload["overlay_voice"]["voice_lens_orb_are_francis_surfaces"] is True
    assert payload["overlay_voice"]["voice_lens_orb_are_separate_identities"] is False
    readiness = payload["voice_provider_readiness"]
    assert readiness["selected_provider"] == "ElevenLabs"
    assert readiness["elevenlabs"]["voice_id_present"] is True
    assert readiness["elevenlabs"]["voice_label"] == "Emma"
    assert readiness["elevenlabs"]["voice_label_source"] == "Process:FRANCIS_ELEVENLABS_VOICE_NAME"
    assert readiness["elevenlabs"]["credential_values_redacted"] is True
    assert readiness["stores_secret"] is False


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


def test_lens_overlay_window_status_reports_native_renderer_missing_for_synthetic_runtime(
    tmp_path: Path,
) -> None:
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
                    "top": 452.0,
                    "width": 220.0,
                    "height": 220.0,
                    "right_corner_locked": True,
                    "default_anchor": "bottom_right",
                    "desktop_roam_supported": False,
                    "desktop_roam_bounds": "work_area",
                    "manual_drag_supported": False,
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
    assert payload["status"] == "missing"
    assert payload["ready"] is False
    assert payload["overlay_window"] is False
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
    assert payload["next_smallest_truthful_gap"] == "overlay_window_runtime"
    assert payload["overlay_runtime"]["process_alive"] is True
    assert payload["overlay_runtime"]["runtime_process_alive"] is False
    assert payload["overlay_runtime"]["overlay_window_visible"] is True
    assert payload["overlay_runtime"]["always_on_top"] is True
    assert payload["overlay_position"]["status"] == "visible_position_observed"
    assert payload["overlay_position"]["left"] == 800.0
    assert payload["overlay_position"]["right_corner_locked"] is True
    assert payload["overlay_position"]["default_anchor"] == "bottom_right"
    assert payload["overlay_position"]["desktop_roam_supported"] is False
    assert payload["overlay_position"]["desktop_roam_bounds"] == "work_area"
    assert payload["overlay_position"]["manual_drag_supported"] is False
    assert payload["overlay_runtime"]["overlay_position"]["roam_right"] == 1280.0
    assert payload["overlay_runtime"]["requirement_state"] == "native_renderer_missing"
    assert payload["overlay_runtime"]["blocker"] == "native_cpp_orb_renderer_not_active"
    assert payload["overlay_runtime"]["native_renderer"]["active_renderer"] is False
    assert payload["overlay_runtime"]["native_renderer"]["process_alive"] is False
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


def test_lens_overlay_window_status_clears_stale_voice_suppression_readback(tmp_path: Path) -> None:
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
                    "voice_provider": "ElevenLabs",
                    "selected_voice": "Emma",
                    "microphone_capture": True,
                    "wake_listening": True,
                    "wake_phrase": "hey francis",
                    "microphone_signal_status": "observed",
                    "microphone_input_effective": True,
                    "needs_operator_audio_input_check": False,
                },
            }
        ),
        encoding="utf-8",
    )
    (runtime_dir / "voice-status.json").write_text(
        json.dumps(
            {
                "kind": "lens.overlay.voice.runtime",
                "status": "voice_input_suppressed_while_speaking",
                "ok": True,
                "voice_provider": "ElevenLabs",
                "selected_voice": "Emma",
                "microphone_capture": True,
                "wake_listening": True,
                "wake_phrase": "hey francis",
                "continuous_voice_chat_blocker": "owned_speech_process_active",
                "microphone_gate_while_speaking": "francis_stop_only",
                "conversation_forwarding_while_speaking": False,
            }
        ),
        encoding="utf-8",
    )

    proc = _run_overlay_window("-Mode", "Status", "-DataDir", str(data_dir))

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["status"] == "missing"
    assert payload["ready"] is False
    assert payload["overlay_runtime"]["requirement_state"] == "native_renderer_missing"
    assert payload["overlay_runtime"]["blocker"] == "native_cpp_orb_renderer_not_active"
    assert payload["voice"]["status"] == "listening"
    assert payload["voice"]["selected_voice"] == "Emma"
    assert payload["voice"]["previous_voice_status"] == "voice_input_suppressed_while_speaking"
    assert payload["voice"]["previous_voice_status_stale"] is True
    assert payload["voice"]["stale_suppression_cleared"] is True
    assert payload["voice"]["microphone_gate_while_speaking"] == "francis_stop_only"
    assert payload["voice"]["conversation_forwarding_while_speaking"] is False


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


def test_lens_overlay_window_status_prefers_voice_turn_status_file_over_runtime_snapshot(tmp_path: Path) -> None:
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
                "voice_turn": {
                    "kind": "lens.overlay.voice.turn_state",
                    "status": "chatgpt_voice_reply_ready",
                    "active_turn_id": "stale-runtime-turn",
                    "virtual_voice_turn": True,
                    "mcp_ingress": True,
                    "updated_at": "2026-06-18T00:00:00Z",
                },
            }
        ),
        encoding="utf-8",
    )
    (runtime_dir / "voice-turn-status.json").write_text(
        json.dumps(
            {
                "kind": "lens.overlay.voice.turn_state",
                "status": "chatgpt_voice_reply_ready",
                "active_turn_id": "fresh-voice-turn-file",
                "virtual_voice_turn": True,
                "mcp_ingress": True,
                "transcript_source": "chatgpt_voice_mcp_transcript",
                "updated_at": "2026-06-18T00:00:10Z",
            }
        ),
        encoding="utf-8",
    )

    proc = _run_overlay_window("-Mode", "Status", "-DataDir", str(data_dir))

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["voice_turn"]["active_turn_id"] == "fresh-voice-turn-file"
    assert payload["voice_turn"]["transcript_source"] == "chatgpt_voice_mcp_transcript"
    assert payload["overlay_runtime"]["voice_turn"]["active_turn_id"] == "fresh-voice-turn-file"


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


def test_lens_overlay_window_start_launcher_allows_visible_overlay_child() -> None:
    script = (_repo_root() / "scripts" / "lens-overlay-window.ps1").read_text(encoding="utf-8")

    assert "Start-Process -FilePath $PowerShell.Source -ArgumentList $ArgumentText -WindowStyle Normal" in script
    assert (
        "Start-Process -FilePath $PowerShell.Source -ArgumentList $ArgumentText -WindowStyle Hidden | Out-Null"
        not in script
    )
    assert (
        "Start-Process -FilePath $PowerShell.Source -ArgumentList $ArgumentText -WindowStyle Hidden -PassThru" in script
    )


def test_lens_overlay_voice_orb_position_command_is_local_and_bounded() -> None:
    script = (_repo_root() / "scripts" / "lens-overlay-window.ps1").read_text(encoding="utf-8")

    assert "function Resolve-OverlayVoiceOrbCommand" in script
    assert "function Get-OverlayOrbPositionCommandRequestPath" in script
    assert "orb-position-command-request.json" in script
    assert "function Invoke-OverlayQueuedOrbPositionCommand" in script
    assert "chatgpt_voice_bridge_file_request" in script
    assert "$HasOrbReference = $Words -contains 'orb' -or $Words -contains 'orbs'" in script
    assert "$HasFrancisReference = $Words -contains 'francis' -or $Words -contains 'frances'" in script
    assert "$HasEmbodimentReference = $HasOrbReference -or $HasFrancisReference -or [bool]$WakePhraseDetected" in script
    assert "$HasMoveVerb = $Words -contains 'move'" in script
    assert "$Words -contains 'go'" in script
    assert "$Words -contains 'slide'" in script
    assert "$MoveTop = $Words -contains 'top' -or $Words -contains 'upper'" in script
    assert "$MoveBottom = $Words -contains 'bottom' -or $Words -contains 'lower'" in script
    assert "$HasHorizontalDirection = ($MoveLeft -or $MoveRight) -and ($MoveLeft -ne $MoveRight)" in script
    assert "$HasVerticalDirection = ($MoveTop -or $MoveBottom) -and ($MoveTop -ne $MoveBottom)" in script
    assert (
        "$TargetCorner = if (-not [string]::IsNullOrWhiteSpace($TargetSide) -and -not [string]::IsNullOrWhiteSpace($TargetVertical))"
        in script
    )
    assert "$Result.command = 'move_orb_{0}_{1}' -f $TargetToken, $TargetKind" in script
    assert "$Result.target_vertical = $TargetVertical" in script
    assert "$Result.target_corner = $TargetCorner" in script
    assert "$Result.reference_type = $ReferenceType" in script
    assert "function Set-OrbWindowSidePosition" in script
    assert "function Get-OrbCommandTargetCoordinate" in script
    assert "$HasVerticalTarget = $TargetVertical -in @('top', 'bottom')" in script
    assert "[double]$WorkArea.Top + $Margin" in script
    assert "[double]$WorkArea.Right - $Margin" in script
    assert "Clamp-OverlayDouble -Value ($MinimumLeft + $Margin)" in script
    assert "Clamp-OverlayDouble -Value ($MaximumLeft - $Margin)" in script
    assert "function Invoke-OverlayVoiceOrbCommand" in script
    assert "$Payload.status = 'orb_voice_command_applied'" in script
    assert "$Payload.status = 'orb_voice_command_travel_started'" in script
    assert "$Payload.overlay_position_command_source = $CommandSource" in script
    assert (
        "$Payload.orb_command_reference_type = Get-StringProperty -Payload $Command -Name 'reference_type' -Default ''"
        in script
    )
    assert "$Payload.overlay_position_command_request_id = $EffectiveCommandRequestId" in script
    assert "$Payload.target_vertical = $TargetVertical" in script
    assert "$Payload.target_corner = $TargetCorner" in script
    assert "$Payload.direct_francis_address_detected = [bool]$IsDirectFrancisAddressCommand" in script
    assert "microphone_direct_francis_address" in script
    assert "$Payload.microphone_speech = (-not [bool]$IsBridgeFileCommand)" in script
    assert "$Payload.microphone_recognition_claimed = (-not [bool]$IsBridgeFileCommand)" in script
    assert "$Payload.synthetic_transcript = [bool]$IsBridgeFileCommand" in script
    assert "$Payload.chat_bridge_status = 'not_called'" in script
    assert "$Payload.chat_route_writes_conversation_ledger = $false" in script
    assert "$Payload.conversation_forwarding_suppressed = $true" in script
    assert "$Payload.speech_output_suppressed = $true" in script
    assert "$Payload.bounded_overlay_position_mutation = $true" in script
    assert "$Payload.mutation_authority_scope = 'runtime_overlay_position_only'" in script
    assert "$Payload.grants_execution_authority = $false" in script
    assert "$Payload.grants_mutation_authority = $false" in script
    assert "Start-OrbWindowCoordinateTravel `" in script
    assert "-Request $CommandReceiptRequest" in script
    assert "target_vertical = $TargetVertical" in script
    assert "target_corner = $TargetCorner" in script
    assert "$script:LensOverlayOperatorPositionAnchor = $TargetAnchor" in script
    assert "Reset-OrbAutonomousMotionAnchor -Window $Window -MotionState $MotionState" in script
    assert "Write-OverlayPositionState -Root $Root -Window $Window -MotionState $MotionState" in script
    assert (
        "$OrbCommand = Resolve-OverlayVoiceOrbCommand -Text $CommandText -WakePhraseDetected:$CommandWakePhraseDetected"
        in script
    )
    assert (
        "$DirectFrancisAddressDetected = Test-OverlayDirectFrancisAddressRecognized -RecognizedText $RecognizedText"
        in script
    )
    assert (
        "$CommandWakePhraseDetected = (-not [string]::IsNullOrWhiteSpace($UtteranceText) -or $WakePhraseOnly -or $DirectFrancisAddressDetected)"
        in script
    )
    assert "local_overlay_direct_francis_address" in script
    assert "-and -not $DirectFrancisAddressDetected" in script
    assert "$AddressedUtteranceText = if (-not [string]::IsNullOrWhiteSpace($UtteranceText))" in script
    assert "Invoke-OverlayVoiceOrbCommand -Root $script:LensOverlayWakeRoot" in script
    assert "$ReferenceType = Get-StringProperty -Payload $Request -Name 'reference_type' -Default ''" in script
    assert "reference_type = $ReferenceType" in script
    assert "command_source = $CommandSource" in script
    assert (
        "microphone_recognition_claimed = Get-BoolProperty -Payload $Result -Name 'microphone_recognition_claimed'"
        in script
    )
    assert (
        "$ReceiptClientOrigin = if ($IsBridgeFileCommand) { 'chatgpt_voice_bridge_file_request' } else { 'local_overlay_speech_recognition' }"
        in script
    )
    assert "Write-OverlayOrbPositionCommandReceipt -Root $Root -RequestId $RequestId" in script
    assert "Remove-OverlayOrbPositionCommandRequest -Root $Root -Path $RequestPath" in script
    assert "$CommandTimer = New-Object System.Windows.Threading.DispatcherTimer" in script
    assert "Invoke-OverlayQueuedOrbPositionCommand -Root $script:LensOverlayDataRoot" in script
    assert "voice_position_command_active" in script


def test_lens_overlay_orb_move_place_mode_is_one_shot_bounded_and_receipted() -> None:
    script = (_repo_root() / "scripts" / "lens-overlay-window.ps1").read_text(encoding="utf-8")

    assert "[int]$OrbMovePlaceTimeoutSeconds = 12" in script
    assert "function Invoke-OverlayOrbMovePlaceMode" in script
    assert "$AuthorityScope -ne 'runtime_overlay_position_only'" in script
    assert "$CommandId -eq 'orb.move' -and $CaptureMode -eq 'one_shot_click'" in script
    assert "Remove-OverlayOrbPositionCommandRequest -Root $Root -Path $RequestPath" in script
    assert "$CaptureWindow = New-Object System.Windows.Window" in script
    assert "LensOverlayOrbMoveCaptureWindow" in script
    assert "status = 'orb_move_place_already_armed'" in script
    assert "$CaptureWindow.AllowsTransparency = $true" in script
    assert "$CaptureWindow.TopMost = $true" in script
    assert "$CaptureWindow.Owner = $Window" in script
    assert "$CaptureWindow.Cursor = [System.Windows.Input.Cursors]::Cross" in script
    assert "$TimeoutTimer = New-Object System.Windows.Threading.DispatcherTimer" in script
    assert "cancel_reason = 'timeout'" in script
    assert "$CaptureWindow.Add_KeyDown" in script
    assert "[System.Windows.Input.Key]::Escape" in script
    assert "cancel_reason = 'escape'" in script
    assert "$CaptureRoot.Add_MouseRightButtonDown" in script
    assert "cancel_reason = 'right_click'" in script
    assert "$CaptureRoot.Add_MouseLeftButtonDown" in script
    assert "$script:LensOverlayOrbMovePlaceModeHandled = $true" in script
    assert "function Dismiss-OverlayOrbMoveCaptureWindow" in script
    assert "$script:LensOverlayOrbMoveCaptureWindow.Hide()" in script
    assert "Dismiss-OverlayOrbMoveCaptureWindow" in script
    assert "$script:LensOverlayOrbMoveCaptureTimeoutTimer.Dispose()" not in script
    assert "$ActiveTimer.Dispose()" not in script
    assert "function Start-OrbWindowCoordinateTravel" in script
    assert "[System.Windows.Media.CompositionTarget]::add_Rendering($Handler)" in script
    assert "[System.Windows.Media.CompositionTarget]::remove_Rendering($RenderingHandler)" in script
    assert "$Ease = ($Progress * $Progress * $Progress)" in script
    assert "320 + ($Distance * 0.95)" in script
    assert "travel_timing_source = 'composition_rendering'" in script
    assert "travel_easing = 'smootherstep'" in script
    assert "Get-Variable -Name LensOverlayOperatorPositionAnchor -Scope Script" in script
    assert "if (-not [string]::IsNullOrWhiteSpace($OperatorAnchor))" in script
    assert (
        "Start-OrbWindowCoordinateTravel -Window $Context['window'] -WorkArea $Context['work_area'] -X $TargetX -Y $TargetY"
        in script
    )
    assert "overlay_position_anchor = $ContextTargetAnchor" in script
    assert "status = 'orb_move_place_travel_started'" in script
    assert "status = 'orb_move_place_applied'" in script
    assert "travelled_to_target = $true" in script
    assert "travel_started = Get-BoolProperty -Payload $Travel -Name 'ok' -Default $false" in script
    assert (
        "Write-OverlayOrbPositionCommandReceipt -Root ([string]$Context['root']) -RequestId ([string]$Context['request_id']) -Request $Context['request'] -Result $Result"
        in script
    )
    assert (
        "receipt_kind = Get-StringProperty -Payload $Request -Name 'receipt_kind' -Default 'overlay_position'" in script
    )
    assert "authority_scope = $AuthorityScope" in script
    assert "trigger_carries_authority = Get-BoolProperty -Payload $Request -Name 'trigger_carries_authority'" in script
    assert "controls_user_os_cursor = $false" in script
    assert "physical_input_performed = $false" in script
    assert "desktop_effect_performed = $false" in script
    assert "grants_execution_authority = $false" in script
    assert "grants_mutation_authority = $false" in script
    assert "[void]$CaptureWindow.Show()" in script
    assert "$CaptureWindow.Add_Closed({" in script
    assert "param($Sender, $EventArgs)" in script
    assert "status = 'orb_move_place_armed'" in script
    assert "[void]$CaptureWindow.ShowDialog()" not in script
    assert "$Application.ShutdownMode = [System.Windows.ShutdownMode]::OnExplicitShutdown" in script
    assert "$Application.MainWindow = $Form" in script
    assert "$Form.Add_Closed({" in script
    assert "$script:LensOverlayApplication.Shutdown()" in script
    assert "$Form.Width = [double]$Screen.Width" in script
    assert "$Form.Height = [double]$Screen.Height" in script
    assert "$OverlayRoot = New-Object System.Windows.Controls.Canvas" in script
    assert "New-NativeOrbControlSurface -Size $OrbSize -HitBoxSize $OrbHitBoxSize" in script
    assert "Start-NativeOrbRenderer -Root $DataRoot" in script
    assert "function Register-OverlayOrbHitTestHook" in script
    assert "$OrbClickTarget.Add_MouseRightButtonDown({" in script
    assert "$script:LensOverlayWindow.DragMove()" not in script
    assert "full_screen_overlay_orb_offset" in script
    assert "click_hit_box_scope = 'orb_core_only'" in script
    assert "hit_test_passthrough_outside_click_box_enabled = $HitTestPassthroughEnabled" in script


@pytest.mark.skipif(os.name != "nt", reason="WPF travel probe requires Windows")
def test_lens_overlay_orb_coordinate_travel_moves_over_render_frames() -> None:
    powershell = shutil.which("powershell")
    if powershell is None:
        pytest.skip("Windows PowerShell is not available")

    overlay_script = _repo_root() / "scripts" / "lens-overlay-window.ps1"
    probe = f"""
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName PresentationFramework
Add-Type -AssemblyName PresentationCore
Add-Type -AssemblyName WindowsBase
$scriptPath = @'
{overlay_script}
'@
$tokens = $null
$errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($scriptPath, [ref]$tokens, [ref]$errors)
if ($errors.Count -gt 0) {{ throw ($errors[0].ToString()) }}
$wanted = @(
  'Clamp-OverlayDouble',
  'Get-OrbHitBoxSize',
  'Test-OrbFullScreenOverlayPlane',
  'Get-OrbInWindowOffsetX',
  'Get-OrbInWindowOffsetY',
  'Set-OrbInWindowOffset',
  'Get-OrbWindowPlacementForTarget',
  'Reset-OrbAutonomousMotionAnchor',
  'Start-OrbWindowCoordinateTravel'
)
$functionAsts = $ast.FindAll({{ param($Node) $Node -is [System.Management.Automation.Language.FunctionDefinitionAst] }}, $true)
foreach ($name in $wanted) {{
  $functionAst = @($functionAsts | Where-Object {{ $_.Name -eq $name }} | Select-Object -First 1)
  if ($functionAst.Count -eq 0) {{ throw "Missing function $name" }}
  Invoke-Expression $functionAst[0].Extent.Text
}}
$script:LensOverlayOrbMoveTravelRenderingHandler = $null
$script:LensOverlayOrbMoveTravelContext = $null
$script:LensOverlayOrbMovePlaceModeResult = $null
$window = New-Object System.Windows.Window
$window.Width = 80
$window.Height = 80
$window.Left = 10
$window.Top = 20
$window.ShowInTaskbar = $false
$window.WindowStyle = [System.Windows.WindowStyle]::None
$window.Opacity = 0.05
$workArea = [pscustomobject]@{{ Left = 0.0; Top = 0.0; Right = 800.0; Bottom = 600.0; Width = 800.0; Height = 600.0 }}
$motion = [ordered]@{{ anchor_left = 10.0; anchor_top = 20.0; phase = 0.0; last_frame_seconds = -1.0 }}
try {{
  $window.Show()
  $result = Start-OrbWindowCoordinateTravel -Window $window -WorkArea $workArea -X 520 -Y 420 -MotionState $motion -TargetAnchor 'probe' -Root '' -RequestId 'probe' -DurationMilliseconds 520
  $postStartLeft = [double]$window.Left
  $postStartTop = [double]$window.Top
  $frames = [System.Collections.ArrayList]::new()
  for ($i = 0; $i -lt 100; $i++) {{
    $frame = New-Object System.Windows.Threading.DispatcherFrame
    $timer = New-Object System.Windows.Threading.DispatcherTimer
    $timer.Interval = [TimeSpan]::FromMilliseconds(16)
    $timer.Add_Tick({{ param($Sender, $EventArgs) $Sender.Stop(); $frame.Continue = $false }})
    $timer.Start()
    [System.Windows.Threading.Dispatcher]::PushFrame($frame)
    [void]$frames.Add([pscustomobject]@{{ left = [double]$window.Left; top = [double]$window.Top; active = ($null -ne $script:LensOverlayOrbMoveTravelRenderingHandler) }})
    if ($null -eq $script:LensOverlayOrbMoveTravelRenderingHandler) {{ break }}
  }}
  $final = $script:LensOverlayOrbMovePlaceModeResult
  $expectedLeft = 480.0
  $expectedTop = 380.0
  $intermediate = @($frames | Where-Object {{ $_.left -gt 10.5 -and $_.left -lt ($expectedLeft - 0.5) -and $_.top -gt 20.5 -and $_.top -lt ($expectedTop - 0.5) }})
  if (-not [bool]$result.ok) {{ throw 'travel did not start' }}
  if ([Math]::Abs($postStartLeft - $expectedLeft) -le 0.75 -and [Math]::Abs($postStartTop - $expectedTop) -le 0.75) {{ throw 'travel landed immediately' }}
  if ($intermediate.Count -lt 1) {{
    $lastFrame = @($frames | Select-Object -Last 1)
    $lastLeft = if ($lastFrame.Count -gt 0) {{ [double]$lastFrame[0].left }} else {{ -1.0 }}
    $lastTop = if ($lastFrame.Count -gt 0) {{ [double]$lastFrame[0].top }} else {{ -1.0 }}
    $lastActive = if ($lastFrame.Count -gt 0) {{ [bool]$lastFrame[0].active }} else {{ $false }}
    $finalStatus = if ($null -ne $final) {{ [string]$final.status }} else {{ 'missing' }}
    throw ('no intermediate travel frame observed; frames={{0}} last_left={{1}} last_top={{2}} last_active={{3}} final={{4}}' -f $frames.Count, $lastLeft, $lastTop, $lastActive, $finalStatus)
  }}
  if ($null -eq $final -or -not [bool]$final.ok) {{ throw 'final travel result missing' }}
  if ([Math]::Abs(([double]$final.overlay_left) - $expectedLeft) -gt 0.75 -or [Math]::Abs(([double]$final.overlay_top) - $expectedTop) -gt 0.75) {{ throw 'final travel position mismatch' }}
  [pscustomobject]@{{
    started_status = $result.status
    post_start_at_final = ([Math]::Abs($postStartLeft - $expectedLeft) -le 0.75 -and [Math]::Abs($postStartTop - $expectedTop) -le 0.75)
    frame_count = $frames.Count
    intermediate_count = $intermediate.Count
    final_status = $final.status
    final_left = [double]$final.overlay_left
    final_top = [double]$final.overlay_top
    timing_source = $final.travel_timing_source
    easing = $final.travel_easing
  }} | ConvertTo-Json -Depth 4
}} finally {{
  if ($null -ne $window) {{ $window.Close() }}
}}
"""
    proc = subprocess.run(
        [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Sta", "-Command", probe],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
        timeout=30,
    )

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["started_status"] == "orb_move_place_travel_started"
    assert payload["post_start_at_final"] is False
    assert payload["frame_count"] >= 2
    assert payload["intermediate_count"] >= 1
    assert payload["final_status"] == "orb_move_place_applied"
    assert payload["final_left"] == pytest.approx(480.0, abs=0.75)
    assert payload["final_top"] == pytest.approx(380.0, abs=0.75)
    assert payload["timing_source"] == "composition_rendering"
    assert payload["easing"] == "smootherstep"


@pytest.mark.skipif(os.name != "nt", reason="WPF coordinate probe requires Windows")
def test_lens_overlay_orb_edge_reach_uses_in_window_offset() -> None:
    powershell = shutil.which("powershell")
    if powershell is None:
        pytest.skip("Windows PowerShell is not available")

    overlay_script = _repo_root() / "scripts" / "lens-overlay-window.ps1"
    probe = f"""
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName PresentationFramework
Add-Type -AssemblyName PresentationCore
Add-Type -AssemblyName WindowsBase
$scriptPath = @'
{overlay_script}
'@
$tokens = $null
$errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($scriptPath, [ref]$tokens, [ref]$errors)
if ($errors.Count -gt 0) {{ throw ($errors[0].ToString()) }}
$wanted = @(
  'Clamp-OverlayDouble',
  'Get-OrbHitBoxSize',
  'Test-OrbFullScreenOverlayPlane',
  'Get-OrbInWindowOffsetX',
  'Get-OrbInWindowOffsetY',
  'Set-OrbInWindowOffset',
  'Get-OrbWindowPlacementForTarget',
  'Reset-OrbAutonomousMotionAnchor',
  'Set-OrbWindowCoordinatePosition'
)
$functionAsts = $ast.FindAll({{ param($Node) $Node -is [System.Management.Automation.Language.FunctionDefinitionAst] }}, $true)
foreach ($name in $wanted) {{
  $functionAst = @($functionAsts | Where-Object {{ $_.Name -eq $name }} | Select-Object -First 1)
  if ($functionAst.Count -eq 0) {{ throw "Missing function $name" }}
  Invoke-Expression $functionAst[0].Extent.Text
}}
$script:LensOverlayEnergyRoot = $null
$script:LensOverlayOrbWindowOffsetTransform = $null
$script:LensOverlayOrbInWindowOffsetX = 0.0
$script:LensOverlayOrbInWindowOffsetY = 0.0
$script:LensOverlayOrbHitBoxSize = 72.0
$window = New-Object System.Windows.Window
$window.Width = 800
$window.Height = 600
$window.Left = 0
$window.Top = 0
$workArea = [pscustomobject]@{{ Left = 0.0; Top = 0.0; Right = 800.0; Bottom = 600.0; Width = 800.0; Height = 600.0 }}
$motion = [ordered]@{{ anchor_left = 400.0; anchor_top = 300.0; phase = 0.0; last_frame_seconds = -1.0; full_screen_overlay_plane = $true }}
$result = Set-OrbWindowCoordinatePosition -Window $window -WorkArea $workArea -X 0 -Y 0 -MotionState $motion -TargetAnchor 'edge_probe' -Root ''
[pscustomobject]@{{
  applied = [bool]$result.applied
  left = [double]$result.left
  top = [double]$result.top
  orb_center_x = [double]$result.orb_center_x
  orb_center_y = [double]$result.orb_center_y
  offset_x = [double]$result.orb_in_window_offset_x
  offset_y = [double]$result.orb_in_window_offset_y
  offset_applied = [bool]$result.in_window_offset_applied
  target_reachable = [bool]$result.target_reachable_by_orb_center
  window_clamped = [bool]$result.window_clamped
  full_screen_overlay_plane = [bool]$result.full_screen_overlay_plane
  overlay_window_stationary = [bool]$result.overlay_window_stationary
  click_hit_box_size = [double]$result.click_hit_box_size
  click_hit_box_scope = [string]$result.click_hit_box_scope
  reach_mode = [string]$result.reach_mode
}} | ConvertTo-Json -Depth 4
"""
    proc = subprocess.run(
        [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Sta", "-Command", probe],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
        timeout=30,
    )

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["applied"] is True
    assert payload["left"] == pytest.approx(0.0, abs=0.75)
    assert payload["top"] == pytest.approx(0.0, abs=0.75)
    assert payload["orb_center_x"] == pytest.approx(0.0, abs=0.75)
    assert payload["orb_center_y"] == pytest.approx(0.0, abs=0.75)
    assert payload["offset_x"] == pytest.approx(-400.0, abs=0.75)
    assert payload["offset_y"] == pytest.approx(-300.0, abs=0.75)
    assert payload["offset_applied"] is True
    assert payload["target_reachable"] is True
    assert payload["window_clamped"] is False
    assert payload["full_screen_overlay_plane"] is True
    assert payload["overlay_window_stationary"] is True
    assert payload["click_hit_box_size"] == pytest.approx(72.0, abs=0.1)
    assert payload["click_hit_box_scope"] == "orb_core_only"
    assert payload["reach_mode"] == "full_screen_overlay_orb_offset"


def test_lens_overlay_orb_right_click_panel_controls_and_chat_are_receipted() -> None:
    script = (_repo_root() / "scripts" / "lens-overlay-window.ps1").read_text(encoding="utf-8")

    assert "function New-OverlayOrbRightClickPanel" in script
    assert "function Show-OverlayOrbRightClickPanel" in script
    assert "function Set-OverlayOrbFeatureToggle" in script
    assert "function Invoke-OverlayOrbPanelChatSubmit" in script
    assert "$OrbClickTarget.Add_MouseRightButtonDown({" in script
    assert "[void](Show-OverlayOrbRightClickPanel -PlacementTarget $Sender)" in script
    assert "$Popup = New-Object System.Windows.Controls.Primitives.Popup" in script
    assert "$Popup.Placement = [System.Windows.Controls.Primitives.PlacementMode]::MousePoint" in script
    assert "$Popup.StaysOpen = $false" in script
    assert "$Border.Width = 292" in script
    assert "$Border.MaxHeight = 268" in script
    assert "$Input.MaxLength = 600" in script
    assert "Francis Orb" in script
    assert "Listen" in script
    assert "PTT" in script
    assert "LLM" in script
    assert "Drift" in script
    assert "Receipted Orb chat. Hold Ctrl+V for push-to-talk." in script
    assert "conversation_surface = 'lens.overlay.orb.right_click_chat'" in script
    assert "chat_bridge_route = '/chat/send'" in script
    assert "chat_bridge_actor = 'lens.overlay.voice'" in script
    assert "voice_reply_requested = $true" in script
    assert "orb-controls" in script
    assert "kind = 'lens.overlay.orb_control.receipt'" in script
    assert "-Action 'panel_open'" in script
    assert "[string]$Trigger = 'right_click'" in script
    assert "trigger = $Trigger" in script
    assert "-Action 'feature_toggle'" in script
    assert "wake_listen" in script
    assert "continuous_voice_chat" in script
    assert "voice_llm" in script
    assert "ambient_motion" in script
    assert "Start-OverlayWakeListener -Root $script:LensOverlayDataRoot" in script
    assert "RecognizeAsyncCancel()" in script
    assert "Start-OrbFrameSyncedMotion -Window $script:LensOverlayWindow" in script
    assert "Stop-OrbFrameSyncedMotion -Subscription $MotionSubscription" in script
    assert "SyntheticVoiceTurn" in script
    assert "New-OverlayVoiceTextFile -Root $script:LensOverlayDataRoot -Text $BoundedText" in script
    assert "Remove-OverlayVoiceTextFile -Root $DataRoot -TextPath $VoiceTextPath" in script
    assert "chat_input_hash = Get-OverlayTextDigest -Text $BoundedText" in script
    assert "chat_text_redacted = $true" in script
    assert "overlay_stores_transcript = $false" in script
    assert "synthetic_voice_turn = $true" in script
    assert "speech_output_owner = 'lens.overlay'" in script
    assert "text_file_retention = 'transient_deleted_by_synthetic_voice_turn'" in script
    assert "orb_controls = Get-OverlayOrbControlReadback" in script
    assert "grants_execution_authority = $false" in script
    assert "grants_mutation_authority = $false" in script
    assert "controls_user_os_cursor = $false" in script
    assert "physical_input_performed = $false" in script
    assert "desktop_effect_performed = $false" in script
    assert "ShowDialog()" not in script


def test_lens_overlay_consumes_correlated_canonical_summon_requests() -> None:
    script = (_repo_root() / "scripts" / "lens-overlay-window.ps1").read_text(encoding="utf-8")

    assert "function Get-OverlaySummonRequestPath" in script
    assert "function Invoke-OverlayQueuedSummonRequest" in script
    assert "'summon-request.json'" in script
    assert "'lens.overlay.summon_request'" in script
    assert "'open_orb_panel'" in script
    assert "'runtime_overlay_panel_only'" in script
    assert "@('global_hotkey', 'local_open') -notcontains $Trigger" in script
    assert "Show-OverlayOrbRightClickPanel -PlacementTarget $PlacementTarget -Trigger $Trigger" in script
    assert "Invoke-OverlayQueuedSummonRequest -Root $script:LensOverlayDataRoot" in script
    assert "latest_request_id" in script
    assert "Publish-OverlayOrbControlRuntimeState" in script
    assert (
        "$script:LensOverlayOrbPanelPopup.Placement = [System.Windows.Controls.Primitives.PlacementMode]::Right"
        in script
    )
    assert "$script:LensOverlayOrbPanelPopup.HorizontalOffset = 12" in script


def test_lens_overlay_voice_chat_falls_back_when_llm_bridge_is_slow() -> None:
    script = (_repo_root() / "scripts" / "lens-overlay-window.ps1").read_text(encoding="utf-8")

    assert "function Invoke-OverlayVoiceChatBridgeRequest" in script
    assert "function Get-OverlayContinuousVoiceTurnGuard" in script
    assert "MaxPendingSeconds = 90" in script
    assert "$Status -in @('chat_pending', 'speaking')" in script
    assert "voice_input_suppressed_pending_turn" in script
    assert "pending_voice_turn_guard = $true" in script
    assert "conversation_forwarding_suppressed = $true" in script
    assert "$PrimaryTimeoutSeconds = if ($UseLlm) { 0 } else { 20 }" in script
    assert "$FallbackTimeoutSeconds = 45" in script
    assert "llm_deferred_for_voice_bridge_availability" in script
    assert "local_llm_voice_turn_not_called_without_abort_or_quality_guard" in script
    assert "-UseLlm $false" in script
    assert "$ChatBridgeFallbackUsed = $true" in script
    assert "chat_bridge_primary_status = $ChatBridgePrimaryStatus" in script
    assert "chat_bridge_primary_error = $ChatBridgePrimaryError" in script
    assert "chat_bridge_fallback_used = $ChatBridgeFallbackUsed" in script
    assert "chat_bridge_effective_use_llm = $ChatBridgeEffectiveUseLlm" in script
    assert "llm_fallback_used = $ChatBridgeFallbackUsed" in script
    assert "grants_execution_authority = $false" in script
    assert "grants_mutation_authority = $false" in script


def test_lens_overlay_window_script_uses_atomic_state_and_owned_process_stop() -> None:
    script = (_repo_root() / "scripts" / "lens-overlay-window.ps1").read_text(encoding="utf-8")

    assert "function Test-OverlayRuntimeProcess" in script
    assert "function Stop-OverlayRuntimeProcess" in script
    assert "function New-McpBodyStateProjection" in script
    assert "function Read-McpBodyStateForOverlay" in script
    assert "function Format-McpBodyStateLabel" in script
    assert "function New-NativeOrbControlSurface" in script
    assert "function Initialize-NativeOrbRendererInterop" in script
    assert "function Set-NativeOrbRendererPosition" in script
    assert "function Start-NativeOrbRenderer" in script
    assert "function Stop-NativeOrbRenderer" in script
    assert "$ExistingRenderer = Get-NativeOrbRendererReadback -Root $Root" in script
    assert "LensOverlayNativeRendererReused" in script
    assert "return $ExistingRenderer" in script
    assert "if (-not $script:LensOverlayNativeRendererReused)" in script
    assert "FindRendererWindow" in script
    assert "PostMessage" in script
    assert "MoveCenterMessage" in script
    assert "function New-OrbEnergySurface" not in script
    assert "function New-OrbTorusMesh" not in script
    assert "function Add-Orb3DEnergyRing" not in script
    assert "function New-OrbAutonomousMotionState" in script
    assert "function Update-OrbAutonomousMotion" in script
    assert "function Get-OverlayWpfRenderProfile" in script
    assert "function Set-OverlayHardwareRenderMode" in script
    assert "function New-OrbVisualProjection" in script
    assert "function Start-OrbFrameSyncedMotion" in script
    assert "function Stop-OrbFrameSyncedMotion" in script
    assert "[switch]$EnableAutonomousMotion" in script
    assert "[int]$McpBodyStateTimeoutSeconds = 1" in script
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
    assert "function Get-ElevenLabsVoiceLabel" in script
    assert "function Get-OverlaySelectedVoiceName" in script
    assert "function Start-OverlayWakeListener" in script
    assert "function Get-OverlayVoiceReadback" in script
    assert "function Move-OverlayRuntimeStateFile" in script
    assert "function Join-OverlayProcessArguments" in script
    assert "function Update-OverlayMcpBodyStateLabel" in script
    assert "function Update-OverlayMcpBodyStateLabelSafely" in script
    assert "Invoke-RestMethod -Uri $Uri -Method Get" in script
    assert "read_timeout_seconds" in script
    assert "Invoke-RestMethod -Uri $Uri -Method Get -TimeoutSec $TimeoutSeconds" in script
    assert "Read-McpBodyStateForOverlay -McpStatusRoute $Config.mcp_status_route" in script
    assert "-TimeoutSeconds $McpBodyStateTimeoutSeconds" in script
    assert "live_status' -Value 'refresh_failed'" in script
    assert "Overlay runtime stayed visible after MCP body-state refresh failed." in script
    assert "francis_lens=orb_overlay" in script
    assert "native_cpp_orb.liquid_streamer_identity" in script
    assert "native_cpp_orb_renderer" in script
    assert "bounded_desktop_roam" in script
    assert "composition_target_rendering" in script
    assert "elapsed_time_delta_clamped" in script
    assert "native_renderer_size = Get-NativeOrbRendererSize" in script
    assert "Set-NativeOrbRendererPosition -Root $Root" in script
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
    assert "FRANCIS_ELEVENLABS_VOICE_NAME" in script
    assert "56bWURjYFHyYyVf490Dp" in script
    assert "known_voice_id:Emma" in script
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
    assert "explicit_wake_phrase_or_direct_francis_address" in script
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
    assert "function Get-OverlayOwnedSpeechGuardState" in script
    assert "external_voice_speech_active" in script
    assert "speech_output_owner' -Default ''" in script
    assert "chatgpt_voice_client" in script
    assert "external_voice_transport_speaking" in script
    assert "suppress_external_voice_transport_echo_on_francis_stop_only" in script
    assert "single_voice_owner_guard = 'owned_or_external_client_voice'" in script
    assert "Get-OverlayOwnedSpeechGuardState -Root $script:LensOverlayWakeRoot -CooldownSeconds 12" in script
    assert "function Start-OverlayVoiceSpeechProcess" in script
    assert "function New-OverlayWakeAliasList" in script
    assert "function Get-OverlayWakePrefixedUtterance" in script
    assert "function Test-OverlayDirectFrancisAddressRecognized" in script
    assert "function Get-OverlayDirectFrancisAddressedUtterance" in script
    assert "function Test-OverlayWakePhraseRecognized" in script
    assert "function Test-OverlayStopPhraseRecognized" in script
    assert "function Invoke-OverlayVoiceStopPhrase" in script
    assert "function Get-OverlayTextDigest" in script
    assert "function Initialize-OverlayKeyboardInterop" in script
    assert "FrancisLensOverlayKeyboardNative" in script
    assert "GetAsyncKeyState" in script
    assert "function Test-OverlayContinuousVoiceChatPushToTalkActive" in script
    assert "function Get-OverlayContinuousVoiceChatMode" in script
    assert "function Set-OverlayContinuousVoiceChatGateReadback" in script
    assert "push_to_talk_ctrl_v_required" in script
    assert "continuous_voice_chat_push_to_talk_chord = 'Ctrl+V'" in script
    assert "continuous_voice_chat_free_run = $false" in script
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
    assert "message = $Message" in script
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
    assert "Set-OverlayContinuousVoiceChatGateReadback -Payload $Payload" in script
    assert "voice_input_suppressed_push_to_talk_inactive" in script
    assert "push_to_talk_chord_not_held" in script
    assert "No-wake continuous voice chat is push-to-talk gated; hold Ctrl+V while speaking" in script
    assert (
        "$ContinuousVoiceCommandAllowed = ([bool]$script:LensOverlayContinuousVoiceChat -and [bool]$ContinuousVoicePushToTalkAllowed)"
        in script
    )
    assert "voice_input_suppressed_while_speaking" in script
    assert "francis_stop_listening_restored" in script
    assert "interrupted_by_francis_stop_phrase" in script
    assert "context_scrub_scope = 'interrupted_voice_turn_reply_context'" in script
    assert "conversation_forwarding_suppressed = $true" in script
    assert "required_interrupt_phrase = 'francis_stop'" in script
    assert "Stop-OverlayVoiceSpeechProcess -Root $Root -Reason 'francis_stop_phrase_interrupted_owned_speech'" in script
    assert "owned_speech_recently_completed" in script
    assert (
        "self_trigger_guard_window_seconds = Get-IntegerProperty -Payload $SpeechGuard -Name 'self_trigger_guard_window_seconds' -Default 12"
        in script
    )
    assert "Get-OverlayOwnedSpeechGuardState -Root $script:LensOverlayWakeRoot -CooldownSeconds 12" in script
    assert "Test-OverlayVoiceSpeechProcess -ProcessId $SpeechProcessId" in script
    assert "-ContinuousVoiceChat $script:LensOverlayRequestedContinuousVoiceChat" in script
    assert "wake_listener_start_failed" in script
    assert "the Orb remains visible without claiming microphone capture" in script
    assert (
        "Write-OverlayVoiceState -Root $script:LensOverlayDataRoot -Payload $script:LensOverlayRuntimeVoice" in script
    )
    assert "Update-OverlayMcpBodyStateLabelSafely -Label $script:LensOverlayLabel" in script
    assert "$ArgumentList += '-EnableContinuousVoiceChat'" in script
    assert "I received the test text, but the local chat bridge is not available right now." in script
    assert "-SyntheticTranscript $true" in script
    assert "chat_reply_redacted = $true" in script
    assert "Limit-OverlayVoiceReplyText -Text $SpokenText -MaxLength 900" in script
    assert "$SentenceBoundary = $Candidate.LastIndexOfAny([char[]]@('.', '!', '?'))" in script
    assert "speech_script_redacted = $true" in script
    assert "speech_script_max_length = 900" in script
    assert "speech_script_sentence_aware_limit = $true" in script
    assert "speech_script_truncated = ($ChatReply.Length -gt $SpokenText.Length)" in script
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
    assert "wake_listener_released_before_speech_completion = $false" in script
    assert "simultaneous_listen_while_speaking_supported = $false" in script
    assert "stop_phrase_listen_while_speaking_supported = [bool]$SpeechProcess.ok" in script
    assert "microphone_gate_while_speaking = 'francis_stop_only'" in script
    assert "conversation_forwarding_while_speaking = $false" in script
    assert "simultaneous_work_while_speaking_supported = $false" in script
    assert "barge_in_supported = [bool]$SpeechProcess.ok" in script
    assert "barge_in_scope = 'cancel_owned_speech_process_on_francis_stop_only'" in script
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
    assert "System.Windows.Controls.Viewport3D" not in script
    assert "System.Windows.Media.Media3D.PerspectiveCamera" not in script
    assert "System.Windows.Media.Media3D.GeometryModel3D" not in script
    assert "System.Windows.Media.Animation.DoubleAnimation" not in script
    assert "MCP body-state" in script
    assert "Tools: {0}/{1}" in script
    assert "Takeover: {0} | Input: {1} | Blockers: {2}" in script
    assert "$Form.WindowStyle = [System.Windows.WindowStyle]::None" in script
    assert "$Form.AllowsTransparency = $true" in script
    assert "$Form.Background = [System.Windows.Media.Brushes]::Transparent" in script
    assert "$Form.ShowInTaskbar = $true" in script
    assert "$Form.TopMost = $true" in script
    assert "function Get-OverlayVirtualScreenBounds" in script
    assert "VirtualScreenHeight" in script
    assert "function Set-OverlayWindowTopMostPinned" in script
    assert "FrancisLensOverlayNativeWindow" in script
    assert "SetWindowPos" in script
    assert "[switch]$EnableManualOrbDrag" in script
    assert "$Form.Left = [double]$Screen.Left" in script
    assert "$Form.Width = [double]$Screen.Width" in script
    assert "$Screen = Get-OverlayVirtualScreenBounds" in script
    assert "$OrbClickTarget.Cursor = if ($ManualOrbDragEnabled)" in script
    assert "$script:LensOverlayHitTestPassthroughEnabled = $true" in script
    assert "$script:LensOverlayTopMostPinApplied = [bool]$Pinned" in script
    assert "topmost_pin_applied = $TopMostPinApplied" in script
    assert "overlay_includes_taskbar = $OverlayIncludesTaskbar" in script
    assert "if ($ManualOrbDragEnabled) {" in script
    assert "$OrbClickTarget.Add_MouseLeftButtonDown" in script
    assert "$OrbClickTarget.Add_MouseMove" in script
    assert "$script:LensOverlayOrbDragActive = $true" in script
    assert "Set-OrbWindowCoordinatePosition -Window $script:LensOverlayWindow" in script
    assert "native_renderer_move_attempted" in script
    assert "native_renderer_move_applied" in script
    assert "native_renderer_move_status" in script
    assert "$script:LensOverlayWindow.DragMove()" not in script
    assert "Reset-OrbAutonomousMotionAnchor" in script
    assert "bounded_desktop_roam" in script
    assert "right_corner_locked" in script
    assert "default_anchor = if ($AutonomousMotion) { 'bounded_work_area' }" in script
    assert "$AutonomousMotionEnabled = [bool]$EnableAutonomousMotion -and -not [bool]$DisableAutonomousMotion" in script
    assert "desktop_roam_supported = $AutonomousMotion" in script
    assert "manual_drag_supported = $ManualDrag" in script
    assert "desktop_roam_bounds = 'virtual_screen'" in script
    assert "roam_left = $MinimumLeft" in script
    assert "roam_right = if ($FullScreenOverlayPlane) { [double]$WorkArea.Right } else { $MaximumLeft }" in script
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
    assert "[int]$McpBodyStateTimeoutSeconds = 1" in script
    assert "[int]$McpRefreshIntervalSeconds = 0" in script
    assert "refresh_deferred_for_animation" in script
    assert "Publish-DeferredOverlayMcpBodyState -Label $script:LensOverlayLabel" in script
    assert "if ($McpRefreshIntervalSeconds -gt 0) {" in script
    assert "$RefreshTimer.Interval = [TimeSpan]::FromSeconds($McpRefreshIntervalSeconds)" in script
    assert "LensOverlayLastOrbVirtualPointerWriteTicks" in script
    assert "$PointerItem.LastWriteTimeUtc.Ticks" in script
    assert "'-McpRefreshIntervalSeconds'" in script
    assert "mcp_body_state = $McpBodyState" in script
    assert "orb_semantic_state" in script
    assert "semantic_state" in script
    assert "semantic_source" in script
    assert "function New-OrbRingColorContract" in script
    assert "ring_color_contract = New-OrbRingColorContract" in script
    assert "Add-OrbVisualRingColorContract -OrbVisual $OrbVisual" in script
    assert "orb_visual = $OrbVisual" in script
    assert "status.{0}.tmp" in script
    assert "Move-OverlayRuntimeStateFile -TempPath $TempPath -DestinationPath $StatusPath" in script
    assert "[System.IO.File]::Replace($TempPath, $DestinationPath, $BackupPath)" in script
    assert "runtime_process_alive = $RuntimeProcessAlive" in script
    assert "Stop-OverlayRuntimeProcess -ProcessId ([int]$TimedOut.pid)" in script
