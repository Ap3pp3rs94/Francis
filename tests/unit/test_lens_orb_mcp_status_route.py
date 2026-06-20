from __future__ import annotations

import json
from pathlib import Path


def test_lens_mcp_status_route_exposes_read_only_body_state(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())
    response = client.get("/lens/mcp/status?actor=test.lens.mcp.status&receipt_limit=3")

    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "francis.lens_orb.mcp_status_bridge"
    assert body["status"] in {"ready", "degraded"}
    assert body["mcp"]["tool_count"] >= 18
    assert "missing_tools" in body["mcp"]
    assert "missing_required_tools" in body["mcp"]
    assert body["resident"] is False
    assert body["routes"]["mcp_observe"] == "/lens/mcp/observe"
    assert body["governance"]["read_only"] is True
    assert body["governance"]["raw_input"] is False
    assert body["governance"]["screenshots"] is False
    assert body["governance"]["ocr"] is False
    assert "traceback" not in json.dumps(body, sort_keys=True).lower()


def test_lens_orb_mcp_status_alias_route_is_available(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())
    response = client.get("/lens/orb/mcp-status?actor=test.lens.orb")

    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "francis.lens_orb.mcp_status_bridge"
    assert body["routes"]["mcp_status"] == "/lens/mcp/status"
    assert body["routes"]["mcp_observe"] == "/lens/mcp/observe"


def test_lens_command_palette_monitor_route_projects_voice_bridge_proof(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    status_path = data_root / "runtime" / "lens-command-palette-monitor" / "status.json"
    status_path.parent.mkdir(parents=True)
    status_path.write_text(
        json.dumps(
            {
                "ok": True,
                "kind": "lens.command_palette.monitor",
                "status": "healthy",
                "mode": "run",
                "monitor_pid": 1234,
                "monitor_process_alive": True,
                "anomaly_count": 0,
                "anomalies": [],
                "checks": [
                    {
                        "id": "voice_overlay_readback",
                        "passed": True,
                        "status": "readback_ready",
                        "evidence": "scripts/lens-overlay-window.ps1 -Mode Status",
                    }
                ],
                "bridge": {
                    "ok": True,
                    "readback_ready": True,
                    "local_open_available": True,
                    "route": "/?francis_lens=command_palette",
                    "local_surface": "chat_ui.command_palette",
                    "command_total": 2,
                },
                "voice_monitor": {
                    "enabled": True,
                    "ok": True,
                    "selected_provider": "ElevenLabs",
                    "selected_voice": "Emma",
                    "voice_label": "Emma",
                    "voice_identity_ok": True,
                    "overlay_ready": True,
                    "overlay_voice_status": "listening",
                    "voice_status": "listening",
                    "wake_listening": True,
                    "wake_phrase": "hey francis",
                    "passive_listen_contract": "passive_transcript_awareness_only_until_wake_phrase",
                    "continuous_voice_chat": True,
                    "continuous_voice_chat_mode": "enabled_no_wake_phrase_required",
                    "continuous_voice_chat_self_trigger_guard": (
                        "suppress_all_except_francis_stop_while_owned_speech_process_active"
                    ),
                    "microphone_gate_while_speaking": "francis_stop_only",
                    "conversation_forwarding_while_speaking": False,
                    "interrupt_phrase": "francis stop",
                    "voice_input_ready": False,
                    "voice_input_status": "waiting_for_audio_signal",
                    "voice_input_blocker": "audio_signal_not_confirmed",
                    "next_voice_input_step": "say_hey_francis_to_confirm_default_microphone_signal",
                    "orb_position_command_ready": False,
                    "orb_position_command_targets": ["left", "right"],
                    "orb_position_command_requires_orb_reference": True,
                    "orb_position_command_accepts_francis_identity_reference": True,
                    "orb_position_command_accepts_wake_phrase_reference": True,
                    "orb_position_command_requires_direction": True,
                    "orb_position_command_conversation_forwarding_suppressed": True,
                    "orb_position_command_authority_scope": "runtime_overlay_position_only",
                    "overlay_position_anchor": "voice_command_left_side",
                    "overlay_left": 48,
                    "overlay_top": 644,
                    "voice_position_command_active": True,
                    "latest_orb_position_command": "move_orb_left_side",
                    "latest_orb_position_command_status": "orb_voice_command_applied",
                    "latest_orb_position_command_applied": True,
                    "recent_receipt_count": 1,
                    "manual_acoustic_orb_position_proof": {
                        "status": "fresh_acoustic_orb_position_command_observed",
                        "proof_observed": True,
                        "proof_blocker": "none",
                        "first_failed_requirement": "none",
                        "failed_requirements": ["transcript"],
                        "requirement_checks": {
                            "voice_input_ready": True,
                            "wake_listener_ready": True,
                            "microphone_signal_observed": True,
                            "local_overlay_speech_command_observed": True,
                            "voice_command_microphone_origin": True,
                            "voice_command_wake_phrase_observed": True,
                            "orb_receipt_observed": True,
                            "orb_receipt_applied": True,
                            "orb_receipt_microphone_origin": True,
                            "orb_receipt_wake_phrase_observed": True,
                            "orb_receipt_command_matches_voice": True,
                            "orb_receipt_request_matches_voice": True,
                            "orb_receipt_fresh": True,
                            "api_injected_text_rejected": True,
                            "transcript_redacted": True,
                            "stores_transcript": False,
                            "transcript": True,
                        },
                        "freshness_window_seconds": 300,
                        "voice_input_ready": True,
                        "wake_listening": True,
                        "microphone_signal_observed": True,
                        "required_phrase": "hey francis move left or hey francis move right",
                        "requires_local_overlay_speech_recognition": True,
                        "api_injected_text_counts_as_proof": False,
                        "transcript_redacted_from_summary": True,
                        "diagnostic_paths": {
                            "overlay_status": "data/runtime/lens-overlay/status.json",
                            "overlay_voice_status": "data/runtime/lens-overlay/voice-status.json",
                            "orb_position_receipt_root": "data/runtime/lens-overlay/orb-position-commands",
                            "latest_orb_receipt": (
                                "data/runtime/lens-overlay/orb-position-commands/local-orb-left-proof.json"
                            ),
                            "transcript": "do not expose this acoustic transcript",
                        },
                        "latest_voice_status": "orb_voice_command_applied",
                        "latest_voice_command": "move_orb_left_side",
                        "latest_voice_command_request_id": "local-orb-left-proof",
                        "latest_voice_command_source": "local_overlay_speech_recognition",
                        "latest_voice_transcript_source": "microphone_wake_listener",
                        "latest_voice_microphone_recognition_claimed": True,
                        "latest_voice_wake_phrase_detected": True,
                        "latest_voice_command_counts_as_acoustic_proof": True,
                        "latest_orb_receipt_id": "local-orb-left-proof",
                        "latest_orb_receipt_command": "move_orb_left_side",
                        "latest_orb_receipt_request_id": "local-orb-left-proof",
                        "latest_orb_receipt_command_source": "local_overlay_speech_recognition",
                        "latest_orb_receipt_transcript_source": "microphone_wake_listener",
                        "latest_orb_receipt_microphone_recognition_claimed": True,
                        "latest_orb_receipt_wake_phrase_detected": True,
                        "latest_orb_receipt_applied": True,
                        "latest_orb_receipt_age_seconds": 2,
                        "latest_orb_receipt_fresh": True,
                        "latest_orb_receipt_matches_latest_voice_command": True,
                        "latest_orb_receipt_matches_latest_voice_request": True,
                        "latest_orb_receipt_counts_as_acoustic_proof": True,
                        "next_operator_step": "keep_monitoring_or_repeat_for_next_acoustic_orb_move",
                        "grants_execution_authority": False,
                        "grants_mutation_authority": False,
                        "transcript": "do not expose this acoustic transcript",
                    },
                    "latest_receipt_id": "chatgpt-voice-recorded-ui",
                    "latest_receipt_actor": "chat_ui.voice",
                    "latest_receipt_source": "chat_ui.voice",
                    "latest_receipt_client_origin": "francis_chat_ui_browser_voice",
                    "latest_receipt_ingress_transport": "http_api",
                    "latest_receipt_counts_as_chatgpt_mcp_proof": False,
                    "latest_receipt_proof_rejection_reason": "latest_receipt_not_chatgpt_voice_origin",
                    "transcript": "do not expose this transcript",
                    "chatgpt_mcp_proof": {
                        "status": "fresh_mcp_connection_proof_observed",
                        "proof_observed": False,
                        "mcp_connection_proof_observed": True,
                        "mcp_connection_proof_status": "fresh_observed",
                        "chatgpt_source_receipt_count": 0,
                        "any_mcp_server_receipt_count": 1,
                        "fresh_any_mcp_server_receipt_count": 1,
                        "latest_any_mcp_server_receipt_id": "chatgpt-voice-recorded-selftest",
                        "latest_any_mcp_server_receipt_source": "local.mcp.selftest",
                        "latest_any_mcp_server_receipt_client_origin": "codex_live_mcp_selftest",
                        "any_mcp_probe_receipt_count": 1,
                        "fresh_any_mcp_probe_receipt_count": 1,
                        "latest_any_mcp_probe_receipt_id": "chatgpt-voice-recorded-probe",
                        "latest_any_mcp_probe_receipt_source": "chatgpt.voice",
                        "latest_any_mcp_probe_receipt_client_origin": "chatgpt_app_voice",
                        "mcp_server_receipt_count": 0,
                        "mcp_probe_receipt_count": 1,
                        "fresh_mcp_probe_receipt_count": 1,
                        "mcp_connection_proof_receipt_count": 1,
                        "fresh_mcp_connection_proof_receipt_count": 1,
                        "latest_mcp_probe_receipt_id": "chatgpt-voice-recorded-probe",
                        "latest_mcp_connection_proof_receipt_id": "chatgpt-voice-recorded-probe",
                        "latest_mcp_connection_proof_tool": "francis_chatgpt_voice_mcp_probe",
                        "latest_fresh_usable_mcp_server_receipt_id": "",
                        "next_operator_step": "call_francis_chatgpt_voice_mcp_probe_from_chatgpt_connector",
                        "transcript": "do not expose this proof transcript",
                    },
                },
                "chatgpt_connector_monitor": {
                    "enabled": True,
                    "ok": True,
                    "status": "ready_for_chatgpt_connector",
                    "connector_url_present": True,
                    "connector_url_host": "francis-voice-178175.loca.lt",
                    "connector_url_source": "localtunnel",
                    "connector_shape_valid": True,
                    "connector_usable_for_chatgpt": True,
                    "expected_tool_present": True,
                    "known_localtunnel": True,
                    "persistent_candidate": False,
                    "persistent_ingress_status": "localtunnel_fallback_replace_needed",
                    "blockers": ["localtunnel_url_is_not_persistent_ingress"],
                },
                "chatgpt_persistent_ingress_plan_monitor": {
                    "enabled": True,
                    "ok": True,
                    "status": "localtunnel_fallback_replace_needed",
                    "blockers": ["localtunnel_url_is_not_persistent_ingress"],
                    "recommended_provider_order": ["cloudflared_token_tunnel", "cloudflared_named_tunnel"],
                    "next_operator_steps": ["choose_or_install_a_persistent_https_ingress_provider"],
                    "operator_handoff": {
                        "kind": "francis.chatgpt_voice.persistent_ingress_operator_handoff",
                        "safe_to_display": True,
                        "read_only_plan": True,
                        "installs_provider": False,
                        "opens_tunnel": False,
                        "writes_state": False,
                        "requires_operator_provider_account_or_hostname": True,
                        "preferred_provider": "cloudflared_named_tunnel",
                        "local_endpoint": "http://127.0.0.1:8787/mcp",
                        "stable_url_placeholder": "https://YOUR-STABLE-HOST/mcp",
                        "install_commands": {
                            "cloudflared_winget": (
                                "winget install --id Cloudflare.cloudflared --exact "
                                "--accept-source-agreements --accept-package-agreements"
                            ),
                        },
                        "governed_handoff_commands": {
                            "record_url": (
                                ".\\scripts\\chatgpt-voice-connector.ps1 -Mode RecordUrl "
                                '-ConnectorUrl "https://YOUR-STABLE-HOST/mcp" -Json'
                            ),
                            "start_persistent_mcp": (
                                ".\\scripts\\chatgpt-voice-connector.ps1 -Mode StartPersistent "
                                '-ConnectorUrl "https://YOUR-STABLE-HOST/mcp" -VerifyConnector -Json'
                            ),
                            "start_cloudflared_token": (
                                ".\\scripts\\chatgpt-voice-connector.ps1 -Mode StartCloudflaredToken "
                                '-CloudflaredTokenFile "data\\runtime\\chatgpt-voice-connector\\cloudflared-token.txt" '
                                '-CloudflaredHostname "YOUR-STABLE-HOST" -ExposePublicTunnel -VerifyConnector -Json'
                            ),
                        },
                    },
                    "governance_safe": True,
                    "providers": {
                        "cloudflared_named_tunnel_available": True,
                        "cloudflared_named_tunnel_path": "C:\\Program Files (x86)\\cloudflared\\cloudflared.exe",
                        "cloudflared_named_tunnel_origin_cert_present": False,
                        "cloudflared_named_tunnel_origin_cert_content_read": False,
                        "cloudflared_named_tunnel_login_required": True,
                        "cloudflared_named_tunnel_requested": True,
                        "cloudflared_named_tunnel_requested_name": "francis",
                        "cloudflared_named_tunnel_requested_hostname": "francis.example.test",
                        "cloudflared_named_tunnel_exists": False,
                        "cloudflared_named_tunnel_preflight_checked": False,
                        "cloudflared_named_tunnel_preflight_exists": False,
                        "cloudflared_named_tunnel_preflight_output_discarded": True,
                        "cloudflared_named_tunnel_operator_provider_setup_commands": [
                            "cloudflared tunnel create francis",
                            "cloudflared tunnel route dns francis francis.example.test",
                        ],
                        "cloudflared_named_tunnel_next_operator_step": "run_cloudflared_tunnel_login",
                        "cloudflared_token_tunnel_available": True,
                        "cloudflared_token_tunnel_path": "C:\\Program Files (x86)\\cloudflared\\cloudflared.exe",
                        "cloudflared_token_tunnel_token_file_requested": True,
                        "cloudflared_token_tunnel_token_file_present": False,
                        "cloudflared_token_tunnel_token_file_content_read": False,
                        "cloudflared_token_tunnel_requested_hostname": "francis.example.test",
                        "cloudflared_token_tunnel_hostname_requested": True,
                        "cloudflared_token_tunnel_next_operator_step": "create_cloudflared_dashboard_token_file",
                        "cloudflared_login_status": "cloudflared_login_started",
                        "cloudflared_login_process_id": 201620,
                        "cloudflared_login_process_alive": True,
                        "cloudflared_login_provider_started": True,
                        "cloudflared_login_browser_may_open": True,
                        "cloudflared_login_writes_origin_cert": True,
                        "cloudflared_login_origin_cert_present": False,
                        "cloudflared_login_origin_cert_content_read": False,
                        "cloudflared_login_public_tunnel_started": False,
                        "cloudflared_login_connector_url_recorded": False,
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())
    response = client.get("/lens/command-palette/monitor")

    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "francis.lens.command_palette.monitor_readback"
    assert body["status"] == "healthy"
    assert body["monitor_process_alive"] is True
    assert body["bridge"]["route"] == "/?francis_lens=command_palette"
    assert body["voice_monitor"]["selected_voice"] == "Emma"
    assert body["voice_monitor"]["wake_listening"] is True
    assert body["voice_monitor"]["wake_phrase"] == "hey francis"
    assert body["voice_monitor"]["passive_listen_contract"] == "passive_transcript_awareness_only_until_wake_phrase"
    assert body["voice_monitor"]["microphone_gate_while_speaking"] == "francis_stop_only"
    assert body["voice_monitor"]["conversation_forwarding_while_speaking"] is False
    assert body["voice_monitor"]["interrupt_phrase"] == "francis stop"
    assert body["voice_monitor"]["voice_input_status"] == "waiting_for_audio_signal"
    assert body["voice_monitor"]["voice_input_blocker"] == "audio_signal_not_confirmed"
    assert body["voice_monitor"]["orb_position_command_targets"] == ["left", "right"]
    assert body["voice_monitor"]["orb_position_command_requires_orb_reference"] is True
    assert body["voice_monitor"]["orb_position_command_accepts_francis_identity_reference"] is True
    assert body["voice_monitor"]["orb_position_command_accepts_wake_phrase_reference"] is True
    assert body["voice_monitor"]["orb_position_command_requires_direction"] is True
    assert body["voice_monitor"]["orb_position_command_conversation_forwarding_suppressed"] is True
    assert body["voice_monitor"]["orb_position_command_authority_scope"] == "runtime_overlay_position_only"
    assert body["voice_monitor"]["voice_position_command_active"] is True
    assert body["voice_monitor"]["overlay_position_anchor"] == "voice_command_left_side"
    assert body["voice_monitor"]["latest_orb_position_command"] == "move_orb_left_side"
    assert body["voice_monitor"]["latest_orb_position_command_status"] == "orb_voice_command_applied"
    assert body["voice_monitor"]["latest_orb_position_command_applied"] is True
    acoustic_proof = body["voice_monitor"]["manual_acoustic_orb_position_proof"]
    assert acoustic_proof["status"] == "fresh_acoustic_orb_position_command_observed"
    assert acoustic_proof["proof_observed"] is True
    assert acoustic_proof["proof_blocker"] == "none"
    assert acoustic_proof["first_failed_requirement"] == "none"
    assert acoustic_proof["failed_requirements"] == []
    requirement_checks = acoustic_proof["requirement_checks"]
    assert requirement_checks["voice_input_ready"] is True
    assert requirement_checks["wake_listener_ready"] is True
    assert requirement_checks["microphone_signal_observed"] is True
    assert requirement_checks["local_overlay_speech_command_observed"] is True
    assert requirement_checks["voice_command_microphone_origin"] is True
    assert requirement_checks["voice_command_wake_phrase_observed"] is True
    assert requirement_checks["orb_receipt_observed"] is True
    assert requirement_checks["orb_receipt_applied"] is True
    assert requirement_checks["orb_receipt_microphone_origin"] is True
    assert requirement_checks["orb_receipt_wake_phrase_observed"] is True
    assert requirement_checks["orb_receipt_command_matches_voice"] is True
    assert requirement_checks["orb_receipt_request_matches_voice"] is True
    assert requirement_checks["orb_receipt_fresh"] is True
    assert requirement_checks["api_injected_text_rejected"] is True
    assert requirement_checks["transcript_redacted"] is True
    assert requirement_checks["stores_transcript"] is False
    assert "transcript" not in requirement_checks
    assert acoustic_proof["latest_voice_command"] == "move_orb_left_side"
    assert acoustic_proof["latest_voice_command_source"] == "local_overlay_speech_recognition"
    assert acoustic_proof["latest_voice_transcript_source"] == "microphone_wake_listener"
    assert acoustic_proof["latest_voice_microphone_recognition_claimed"] is True
    assert acoustic_proof["latest_voice_command_counts_as_acoustic_proof"] is True
    assert acoustic_proof["latest_orb_receipt_id"] == "local-orb-left-proof"
    assert acoustic_proof["diagnostic_paths"] == {
        "overlay_status": "data/runtime/lens-overlay/status.json",
        "overlay_voice_status": "data/runtime/lens-overlay/voice-status.json",
        "orb_position_receipt_root": "data/runtime/lens-overlay/orb-position-commands",
        "latest_orb_receipt": "data/runtime/lens-overlay/orb-position-commands/local-orb-left-proof.json",
    }
    assert "transcript" not in acoustic_proof["diagnostic_paths"]
    assert acoustic_proof["latest_orb_receipt_microphone_recognition_claimed"] is True
    assert acoustic_proof["latest_orb_receipt_fresh"] is True
    assert acoustic_proof["latest_orb_receipt_matches_latest_voice_command"] is True
    assert acoustic_proof["latest_orb_receipt_matches_latest_voice_request"] is True
    assert acoustic_proof["latest_orb_receipt_counts_as_acoustic_proof"] is True
    assert acoustic_proof["api_injected_text_counts_as_proof"] is False
    assert acoustic_proof["grants_execution_authority"] is False
    assert acoustic_proof["grants_mutation_authority"] is False
    assert body["voice_monitor"]["latest_receipt_actor"] == "chat_ui.voice"
    assert body["voice_monitor"]["latest_receipt_ingress_transport"] == "http_api"
    assert body["voice_monitor"]["latest_receipt_counts_as_chatgpt_mcp_proof"] is False
    assert body["voice_monitor"]["chatgpt_mcp_proof"]["status"] == "fresh_mcp_connection_proof_observed"
    assert body["voice_monitor"]["chatgpt_mcp_proof"]["proof_observed"] is False
    assert body["voice_monitor"]["chatgpt_mcp_proof"]["mcp_connection_proof_observed"] is True
    assert body["voice_monitor"]["chatgpt_mcp_proof"]["mcp_connection_proof_status"] == "fresh_observed"
    assert body["voice_monitor"]["chatgpt_mcp_proof"]["any_mcp_server_receipt_count"] == 1
    assert body["voice_monitor"]["chatgpt_mcp_proof"]["fresh_any_mcp_server_receipt_count"] == 1
    assert (
        body["voice_monitor"]["chatgpt_mcp_proof"]["latest_any_mcp_server_receipt_id"]
        == "chatgpt-voice-recorded-selftest"
    )
    assert body["voice_monitor"]["chatgpt_mcp_proof"]["latest_any_mcp_server_receipt_source"] == "local.mcp.selftest"
    assert body["voice_monitor"]["chatgpt_mcp_proof"]["mcp_probe_receipt_count"] == 1
    assert body["voice_monitor"]["chatgpt_mcp_proof"]["fresh_mcp_probe_receipt_count"] == 1
    assert (
        body["voice_monitor"]["chatgpt_mcp_proof"]["latest_mcp_connection_proof_receipt_id"]
        == "chatgpt-voice-recorded-probe"
    )
    assert (
        body["voice_monitor"]["chatgpt_mcp_proof"]["latest_mcp_connection_proof_tool"]
        == "francis_chatgpt_voice_mcp_probe"
    )
    assert body["chatgpt_connector_monitor"]["known_localtunnel"] is True
    assert body["chatgpt_persistent_ingress_plan_monitor"]["governance_safe"] is True
    providers = body["chatgpt_persistent_ingress_plan_monitor"]["providers"]
    assert providers["cloudflared_named_tunnel_available"] is True
    assert providers["cloudflared_named_tunnel_login_required"] is True
    assert providers["cloudflared_named_tunnel_requested"] is True
    assert providers["cloudflared_named_tunnel_requested_name"] == "francis"
    assert providers["cloudflared_named_tunnel_requested_hostname"] == "francis.example.test"
    assert providers["cloudflared_named_tunnel_exists"] is False
    assert providers["cloudflared_named_tunnel_preflight_checked"] is False
    assert providers["cloudflared_named_tunnel_preflight_exists"] is False
    assert providers["cloudflared_named_tunnel_preflight_output_discarded"] is True
    assert providers["cloudflared_named_tunnel_operator_provider_setup_commands"] == [
        "cloudflared tunnel create francis",
        "cloudflared tunnel route dns francis francis.example.test",
    ]
    assert providers["cloudflared_named_tunnel_next_operator_step"] == "run_cloudflared_tunnel_login"
    assert providers["cloudflared_named_tunnel_origin_cert_content_read"] is False
    assert providers["cloudflared_token_tunnel_available"] is True
    assert providers["cloudflared_token_tunnel_token_file_requested"] is True
    assert providers["cloudflared_token_tunnel_token_file_present"] is False
    assert providers["cloudflared_token_tunnel_token_file_content_read"] is False
    assert providers["cloudflared_token_tunnel_requested_hostname"] == "francis.example.test"
    assert providers["cloudflared_token_tunnel_hostname_requested"] is True
    assert providers["cloudflared_token_tunnel_next_operator_step"] == "create_cloudflared_dashboard_token_file"
    assert providers["cloudflared_login_status"] == "cloudflared_login_started"
    assert providers["cloudflared_login_process_id"] == 201620
    assert providers["cloudflared_login_process_alive"] is True
    assert providers["cloudflared_login_provider_started"] is True
    assert providers["cloudflared_login_browser_may_open"] is True
    assert providers["cloudflared_login_writes_origin_cert"] is True
    assert providers["cloudflared_login_origin_cert_present"] is False
    assert providers["cloudflared_login_origin_cert_content_read"] is False
    assert providers["cloudflared_login_public_tunnel_started"] is False
    assert providers["cloudflared_login_connector_url_recorded"] is False
    handoff = body["chatgpt_persistent_ingress_plan_monitor"]["operator_handoff"]
    assert handoff["preferred_provider"] == "cloudflared_named_tunnel"
    assert handoff["read_only_plan"] is True
    assert handoff["installs_provider"] is False
    assert handoff["opens_tunnel"] is False
    assert handoff["writes_state"] is False
    assert handoff["stable_url_placeholder"] == "https://YOUR-STABLE-HOST/mcp"
    assert handoff["install_commands"]["cloudflared_winget"].endswith(
        "--accept-source-agreements --accept-package-agreements",
    )
    assert "RecordUrl" in handoff["governed_handoff_commands"]["record_url"]
    assert "StartCloudflaredToken" in handoff["governed_handoff_commands"]["start_cloudflared_token"]
    assert body["governance"]["execution_authority"] is False
    assert body["governance"]["captures_audio"] is False
    assert "do not expose this transcript" not in json.dumps(body, sort_keys=True)
    assert "do not expose this acoustic transcript" not in json.dumps(body, sort_keys=True)


def test_lens_command_palette_monitor_route_reports_missing_state(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())
    response = client.get("/lens/command-palette/monitor")

    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "francis.lens.command_palette.monitor_readback"
    assert body["ok"] is False
    assert body["status"] == "missing"
    assert body["monitor_process_alive"] is False
    assert body["voice_monitor"]["chatgpt_mcp_proof"]["proof_observed"] is False
    assert body["governance"]["execution_authority"] is False
