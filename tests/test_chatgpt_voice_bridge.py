from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from francis.api.app import create_app
from francis.mcp_gateway.tools import list_tools, run_tool

_ACTOR = "chatgpt.voice"


def _scopes(*scopes: str, actor: str = _ACTOR) -> str:
    return json.dumps({actor: list(scopes)})


def test_chatgpt_voice_contract_is_permission_gated(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", _scopes("chatgpt.voice.bridge.read"))

    client = TestClient(create_app())

    denied = client.get("/chatgpt-voice/contract", params={"actor": "missing.scope"})
    assert denied.json()["error"] == "api_permission_denied"

    allowed = client.get("/chatgpt-voice/contract", params={"actor": _ACTOR})
    body = allowed.json()
    assert body["ok"] is True
    assert body["kind"] == "francis.chatgpt_voice.bridge.contract"
    assert body["routes"]["ingress"] == "/chatgpt-voice/ingress"
    assert body["routes"]["mcp_proof"] == "/chatgpt-voice/mcp-proof"
    assert body["mcp_tools"]["ingress"] == "francis.chatgpt_voice.ingress"
    assert body["mcp_tools"]["server_ingress"] == "francis_chatgpt_voice_ingress"
    assert body["mcp_tools"]["mcp_probe"] == "francis.chatgpt_voice.mcp_probe"
    assert body["mcp_tools"]["server_mcp_probe"] == "francis_chatgpt_voice_mcp_probe"
    assert body["receipt_contract"]["direct_http_transport"] == "http_api"
    assert body["receipt_contract"]["mcp_gateway_transport"] == "mcp_gateway_tool"
    assert body["receipt_contract"]["mcp_gateway_tool"] == "francis.chatgpt_voice.ingress"
    assert body["receipt_contract"]["mcp_server_tool"] == "francis_chatgpt_voice_ingress"
    assert body["receipt_contract"]["mcp_connection_proof_gateway_tool"] == "francis.chatgpt_voice.mcp_probe"
    assert body["receipt_contract"]["mcp_connection_proof_server_tool"] == "francis_chatgpt_voice_mcp_probe"
    assert body["receipt_contract"]["bridge_receipt_root"] == "data/integrations/chatgpt_voice/receipts"
    assert body["receipt_contract"]["metadata_secrets_redacted_field"] == "metadata_secrets_redacted"
    assert body["receipt_contract"]["redacted_metadata_fields_field"] == "redacted_metadata_fields"
    assert body["receipt_contract"]["receipt_readback_redacts_secret_patterns"] is True
    assert body["receipt_contract"]["voice_substrate_proof_field"] == "voice_substrate_proof"
    assert body["receipt_contract"]["voice_output_provider_field"] == "voice_output_provider"
    assert body["receipt_contract"]["voice_output_provider_status_field"] == "voice_output_provider_status"
    assert body["receipt_contract"]["voice_provider_state_field"] == "voice_provider_state"
    assert body["receipt_contract"]["voice_provider_receipt_field"] == "voice_provider_receipt"
    assert body["receipt_contract"]["voice_provider_receipt_mode_field"] == "voice_provider_receipt_mode"
    assert body["receipt_contract"]["voice_provider_state_taxonomy"] == [
        "client_text_reply_no_provider_call",
        "live_provider_receipt",
        "mock_provider_receipt",
        "fixture_provider_receipt",
        "replay_provider_receipt",
        "provider_unavailable",
        "provider_unconfigured",
    ]
    assert body["receipt_contract"]["voice_provider_receipt_mode_taxonomy"] == [
        "client_text_reply_no_provider_call",
        "live_provider_receipt",
        "mock_provider_receipt",
        "fixture_provider_receipt",
        "replay_provider_receipt",
        "provider_unavailable",
        "provider_unconfigured",
    ]
    assert body["receipt_contract"]["voice_provider_receipt_modes_are_mutually_exclusive"] is True
    assert body["orb_voice_contract"]["francis_identity"] == "Francis"
    assert body["orb_voice_contract"]["francis_surfaces"] == ["voice", "lens", "orb"]
    assert body["orb_voice_contract"]["orb_role"] == "embodiment"
    assert body["orb_voice_contract"]["orb_is_embodiment"] is True
    assert body["orb_voice_contract"]["voice_lens_orb_are_separate_identities"] is False
    assert body["orb_voice_contract"]["voice_lens_orb_are_francis_surfaces"] is True
    assert body["orb_voice_contract"]["mcp_transcript_updates_voice_turn_readback"] is True
    assert body["orb_voice_contract"]["voice_turn_state_path"] == "data/runtime/lens-overlay/voice-turn-status.json"
    assert body["orb_voice_contract"]["virtual_voice_turn"] is True
    assert body["orb_voice_contract"]["microphone_capture_claimed"] is False
    assert body["orb_voice_contract"]["raw_audio_stream_accepted"] is False
    assert body["orb_voice_contract"]["client_speaks_top_level_reply"] is True
    assert body["orb_voice_contract"]["orb_position_command_accepts_francis_identity_reference"] is True
    substrate_boundary = body["orb_voice_contract"]["orb_position_command_substrate_boundary"]
    assert substrate_boundary["voice_controls_orb_directly"] is False
    assert substrate_boundary["overlay_runtime_owns_position_mutation"] is True
    assert substrate_boundary["applied_state_requires_overlay_receipt"] is True
    assert substrate_boundary["orb_applied_state_claimed_by_bridge"] is False
    assert substrate_boundary["orb_visual_lock_preserved"] is True
    assert substrate_boundary["substrate_governance_bypass"] is False
    assert "go" in body["orb_voice_contract"]["orb_position_command_move_verbs"]
    assert "slide" in body["orb_voice_contract"]["orb_position_command_move_verbs"]
    assert body["input_contract"]["audio_stream_accepted"] is False
    assert body["client_speech_contract"]["call_ingress_for_every_voice_turn"] is True
    assert body["client_speech_contract"]["call_mcp_probe_to_validate_connector"] is True
    assert body["client_speech_contract"]["speak_only_top_level_reply"] is True
    assert body["client_speech_contract"]["voice_output_provider"] == "chatgpt_voice_client"
    assert body["client_speech_contract"]["voice_output_mode"] == "client_text_reply"
    assert body["client_speech_contract"]["voice_output_provider_status"] == "client_speaks_top_level_reply"
    assert body["client_speech_contract"]["transcript_unavailable_must_be_forwarded"] is True
    assert body["client_speech_contract"]["local_fallback_answer_allowed"] is False
    assert "Do not answer locally" in body["client_speech_contract"]["description"]
    assert body["chatgpt_app_boundary"]["native_phone_localhost_access_claimed"] is False
    provider_boundary = body["output_provider_boundary"]
    assert provider_boundary["voice_output_provider"] == "chatgpt_voice_client"
    assert provider_boundary["voice_output_mode"] == "client_text_reply"
    assert provider_boundary["voice_provider_state"] == "client_text_reply_no_provider_call"
    assert provider_boundary["voice_provider_receipt_mode"] == "client_text_reply_no_provider_call"
    assert provider_boundary["voice_provider_receipt_mode_is_provider_call"] is False
    substrate_proof = provider_boundary["voice_substrate_proof"]
    assert substrate_proof["provider_receipt_mode"] == "client_text_reply_no_provider_call"
    assert substrate_proof["provider_taxonomy_enforced"] is True
    assert substrate_proof["output_provider_call_claimed"] is False
    assert substrate_proof["elevenlabs_live_use_requires_provider_receipt"] is True
    assert substrate_proof["voice_controls_orb_directly"] is False
    assert substrate_proof["substrate_governance_bypass"] is False
    assert provider_boundary["live_voice_provider_call"] is False
    assert provider_boundary["mock_voice_provider_call"] is False
    assert provider_boundary["fixture_voice_provider_call"] is False
    assert provider_boundary["replay_voice_provider_call"] is False
    assert provider_boundary["voice_provider_unavailable"] is False
    assert provider_boundary["voice_provider_unconfigured"] is False
    assert provider_boundary["elevenlabs_provider_invoked"] is False
    assert provider_boundary["elevenlabs_audio_claimed"] is False
    provider_receipt = provider_boundary["voice_provider_receipt"]
    assert provider_receipt["state"] == "client_text_reply_no_provider_call"
    assert provider_receipt["receipt_mode"] == "client_text_reply_no_provider_call"
    assert provider_receipt["receipt_mode_is_provider_call"] is False
    assert provider_receipt["client_text_reply"] is True
    assert provider_receipt["provider_unavailable_and_unconfigured_distinct"] is True
    assert provider_receipt["live_mock_fixture_replay_are_mutually_exclusive"] is True
    assert provider_receipt["elevenlabs"]["operator_preferred_provider"] is True
    assert provider_receipt["elevenlabs"]["configuration_driven"] is True
    assert provider_receipt["elevenlabs"]["bridge_invokes_provider"] is False
    assert provider_receipt["elevenlabs"]["live_use_requires_provider_receipt"] is True
    assert provider_boundary["provider_boundary"]["elevenlabs_live_use_requires_provider_receipt"] is True
    assert provider_boundary["provider_boundary"]["provider_unavailable_and_unconfigured_distinct"] is True
    assert (
        provider_boundary["provider_boundary"]["bridge_provider_receipt_mode"] == "client_text_reply_no_provider_call"
    )
    assert provider_boundary["provider_boundary"]["bridge_provider_receipt_mode_is_provider_call"] is False
    assert body["governance"]["read_only"] is True
    assert body["governance"]["grants_execution_authority"] is False
    assert body["governance"]["grants_mutation_authority"] is False


def test_chatgpt_voice_ingress_records_without_chat_forward(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", _scopes("chatgpt.voice.bridge.write"))

    client = TestClient(create_app())

    body = client.post(
        "/chatgpt-voice/ingress",
        json={
            "actor": _ACTOR,
            "transcript": "Francis can you hear me",
            "turn_id": "voice-turn-1",
            "forward_to_chat": False,
        },
    ).json()

    assert body["ok"] is True
    assert body["status"] == "recorded"
    assert body["reply"] == "I recorded the transcript for Francis. Chat forwarding was not requested."
    assert body["voice_response"]["source"] == "bridge.recorded_only"
    assert body["voice_response"]["speakable"] is True
    assert body["voice_response"]["voice_output_provider"] == "chatgpt_voice_client"
    assert body["voice_response"]["voice_output_mode"] == "client_text_reply"
    assert body["voice_response"]["voice_provider_state"] == "client_text_reply_no_provider_call"
    assert body["voice_response"]["voice_provider_receipt_mode"] == "client_text_reply_no_provider_call"
    assert body["voice_response"]["voice_provider_receipt_mode_is_provider_call"] is False
    assert body["voice_response"]["voice_substrate_proof"]["output_provider_call_claimed"] is False
    assert body["voice_response"]["live_voice_provider_call"] is False
    assert body["voice_response"]["mock_voice_provider_call"] is False
    assert body["voice_response"]["fixture_voice_provider_call"] is False
    assert body["voice_response"]["replay_voice_provider_call"] is False
    assert body["voice_response"]["voice_provider_unavailable"] is False
    assert body["voice_response"]["voice_provider_unconfigured"] is False
    assert body["voice_response"]["elevenlabs_provider_invoked"] is False
    assert body["voice_response"]["voice_provider_receipt"]["state"] == "client_text_reply_no_provider_call"
    assert body["voice_response"]["voice_provider_receipt"]["receipt_mode"] == "client_text_reply_no_provider_call"
    assert body["voice_response"]["voice_provider_receipt"]["provider_status_observed"] is False
    assert body["chat_forward"]["requested"] is False
    assert body["receipt"]["transcript"] == "Francis can you hear me"
    assert body["receipt"]["turn_id"] == "voice-turn-1"
    assert body["receipt"]["ingress_transport"] == "http_api"
    assert body["receipt"]["mcp_gateway_tool"] == ""
    assert body["receipt"]["mcp_server_tool"] == ""
    assert body["receipt"]["mcp_server_transport"] == ""
    assert body["receipt"]["voice_output_provider"] == "chatgpt_voice_client"
    assert body["receipt"]["voice_output_mode"] == "client_text_reply"
    assert body["receipt"]["voice_output_provider_status"] == "client_speaks_top_level_reply"
    assert body["receipt"]["voice_provider_state"] == "client_text_reply_no_provider_call"
    assert body["receipt"]["voice_provider_receipt_mode"] == "client_text_reply_no_provider_call"
    assert body["receipt"]["voice_provider_receipt_mode_is_provider_call"] is False
    assert body["receipt"]["live_voice_provider_call"] is False
    assert body["receipt"]["mock_voice_provider_call"] is False
    assert body["receipt"]["fixture_voice_provider_call"] is False
    assert body["receipt"]["replay_voice_provider_call"] is False
    assert body["receipt"]["voice_provider_unavailable"] is False
    assert body["receipt"]["voice_provider_unconfigured"] is False
    assert body["receipt"]["elevenlabs_provider_invoked"] is False
    assert body["receipt"]["elevenlabs_audio_claimed"] is False
    assert body["receipt"]["voice_provider_receipt"]["state"] == "client_text_reply_no_provider_call"
    assert body["receipt"]["voice_provider_receipt"]["receipt_mode"] == "client_text_reply_no_provider_call"
    assert body["receipt"]["voice_provider_receipt"]["receipt_mode_is_provider_call"] is False
    receipt_proof = body["receipt"]["voice_substrate_proof"]
    assert receipt_proof["kind"] == "francis.voice.substrate_proof.v1"
    assert receipt_proof["bridge_receipt_id"] == body["receipt"]["id"]
    assert receipt_proof["bridge_receipt_path"].endswith(f"{body['receipt']['id']}.json")
    assert receipt_proof["voice_turn_receipt_path"] == "data/runtime/lens-overlay/voice-turns/voice-turn-1.json"
    assert receipt_proof["transcript_state"] == "redacted_transcript_recorded"
    assert receipt_proof["structured_receipts"]["bridge_ingress_receipt"] is True
    assert receipt_proof["structured_receipts"]["virtual_voice_turn_receipt"] is True
    assert receipt_proof["structured_receipts"]["provider_boundary_receipt"] is True
    assert receipt_proof["structured_receipts"]["orb_position_command_request_receipt"] is False
    assert receipt_proof["provider_receipt_mode"] == "client_text_reply_no_provider_call"
    assert receipt_proof["output_provider_call_claimed"] is False
    assert receipt_proof["voice_controls_orb_directly"] is False
    assert body["receipt"]["voice_provider_receipt"]["provider_status_observed"] is False
    assert body["receipt"]["voice_provider_receipt"]["provider_unavailable_and_unconfigured_distinct"] is True
    assert body["receipt"]["voice_provider_receipt"]["elevenlabs"]["bridge_invokes_provider"] is False
    assert body["receipt"]["voice_provider_receipt"]["elevenlabs"]["direct_orb_control"] is False
    assert body["receipt"]["provider_boundary"]["elevenlabs_called_by_bridge"] is False
    assert body["receipt"]["reply_source"] == "bridge.recorded_only"
    assert isinstance(body["receipt"]["created_ts"], float)
    assert body["receipt"]["created_at"].endswith("Z")
    receipt_path = Path(body["receipt"]["receipt_path"])
    assert receipt_path.exists()
    persisted = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert persisted["created_ts"] == body["receipt"]["created_ts"]
    assert persisted["created_at"] == body["receipt"]["created_at"]
    assert persisted["voice_substrate_proof"]["bridge_receipt_id"] == body["receipt"]["id"]
    orb_voice = body["orb_voice_bridge"]
    assert orb_voice["status"] == "chatgpt_voice_transcript_recorded"
    assert orb_voice["virtual_voice_turn"] is True
    assert orb_voice["francis_identity"] == "Francis"
    assert orb_voice["francis_surfaces"] == ["voice", "lens", "orb"]
    assert orb_voice["orb_role"] == "embodiment"
    assert orb_voice["orb_is_embodiment"] is True
    assert orb_voice["voice_lens_orb_are_separate_identities"] is False
    assert orb_voice["voice_lens_orb_are_francis_surfaces"] is True
    assert orb_voice["mcp_ingress"] is False
    assert orb_voice["transcript_source"] == "chatgpt_voice_http_transcript"
    assert orb_voice["microphone_recognition_claimed"] is False
    assert orb_voice["raw_audio"] is False
    assert body["receipt"]["orb_voice_bridge"]["status"] == "chatgpt_voice_transcript_recorded"
    assert body["receipt"]["orb_voice_bridge"]["francis_identity"] == "Francis"
    voice_state = data_root / "runtime" / "lens-overlay" / "voice-turn-status.json"
    assert voice_state.exists()
    state = json.loads(voice_state.read_text(encoding="utf-8"))
    assert state["turn_id"] == "voice-turn-1"
    assert state["virtual_voice_turn"] is True
    assert state["francis_identity"] == "Francis"
    assert state["orb_is_embodiment"] is True
    assert state["transcript_source"] == "chatgpt_voice_http_transcript"
    assert state["voice_output_provider"] == "chatgpt_voice_client"
    assert state["voice_output_mode"] == "client_text_reply"
    assert state["voice_output_provider_status"] == "client_speaks_top_level_reply"
    assert state["voice_provider_state"] == "client_text_reply_no_provider_call"
    assert state["voice_provider_receipt_mode"] == "client_text_reply_no_provider_call"
    assert state["voice_provider_receipt_mode_is_provider_call"] is False
    assert state["voice_substrate_proof"]["voice_turn_receipt_path"] == (
        "data/runtime/lens-overlay/voice-turns/voice-turn-1.json"
    )
    assert state["voice_substrate_proof"]["structured_receipts"]["virtual_voice_turn_receipt"] is True
    assert state["voice_substrate_proof"]["structured_receipts"]["bridge_ingress_receipt"] is False
    assert state["live_voice_provider_call"] is False
    assert state["mock_voice_provider_call"] is False
    assert state["fixture_voice_provider_call"] is False
    assert state["replay_voice_provider_call"] is False
    assert state["voice_provider_unavailable"] is False
    assert state["voice_provider_unconfigured"] is False
    assert state["elevenlabs_provider_invoked"] is False
    assert state["elevenlabs_audio_claimed"] is False
    assert state["voice_provider_receipt"]["state"] == "client_text_reply_no_provider_call"
    assert state["voice_provider_receipt"]["receipt_mode"] == "client_text_reply_no_provider_call"
    assert state["voice_provider_receipt"]["elevenlabs"]["configuration_driven"] is True
    assert state["voice_provider_receipt"]["elevenlabs"]["direct_orb_control"] is False
    assert state["local_overlay_speech_started"] is False
    assert body["governance"]["writes_receipt"] is True
    assert body["governance"]["writes_lens_voice_turn"] is True
    assert body["governance"]["forwards_to_chat"] is False
    assert body["governance"]["raw_audio"] is False
    assert body["governance"]["grants_execution_authority"] is False
    assert not (data_root / "conversations" / "ledger" / "ledger.jsonl").exists()


def test_chatgpt_voice_ingress_redacts_secret_metadata_in_receipts(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv(
        "FRANCIS_API_ACTOR_SCOPES",
        _scopes("chatgpt.voice.bridge.read", "chatgpt.voice.bridge.write"),
    )
    secret = "sk-" + ("a" * 24)

    client = TestClient(create_app())

    body = client.post(
        "/chatgpt-voice/ingress",
        json={
            "actor": _ACTOR,
            "source": f"chatgpt.voice token={secret}",
            "client_origin": f"chatgpt_app_voice token={secret}",
            "conversation_id": f"conversation-{secret}",
            "turn_id": f"turn-{secret}",
            "locale": f"en-US token={secret}",
            "transcript": f"Francis record api_key={secret}",
            "forward_to_chat": False,
        },
    ).json()

    assert body["ok"] is True
    assert body["status"] == "recorded"
    serialized = json.dumps(body)
    assert secret not in serialized
    assert "[REDACTED:secret]" in serialized
    receipt = body["receipt"]
    assert receipt["secrets_redacted"] is True
    assert receipt["metadata_secrets_redacted"] is True
    assert set(receipt["redacted_metadata_fields"]) >= {
        "client_origin",
        "conversation_id",
        "locale",
        "source",
        "turn_id",
    }

    receipt_path = Path(receipt["receipt_path"])
    persisted_text = receipt_path.read_text(encoding="utf-8")
    assert secret not in persisted_text
    assert "[REDACTED:secret]" in persisted_text

    voice_state = data_root / "runtime" / "lens-overlay" / "voice-turn-status.json"
    state_text = voice_state.read_text(encoding="utf-8")
    assert secret not in state_text
    assert "[REDACTED:secret]" in state_text

    readback = client.get("/chatgpt-voice/receipts", params={"actor": _ACTOR, "limit": 5}).json()
    assert readback["ok"] is True
    assert secret not in json.dumps(readback)


def test_chatgpt_voice_mcp_proof_records_connection_without_transcript_or_voice_turn(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", _scopes("chatgpt.voice.bridge.write"))

    client = TestClient(create_app())

    body = client.post(
        "/chatgpt-voice/mcp-proof",
        json={"actor": _ACTOR, "reason": "connector proof from ChatGPT"},
    ).json()

    assert body["ok"] is True
    assert body["status"] == "recorded"
    assert body["reply"] == "Francis MCP voice bridge is reachable. No transcript was recorded."
    assert body["voice_response"]["source"] == "bridge.mcp_connection_proof"
    assert body["voice_response"]["voice_output_provider"] == "chatgpt_voice_client"
    assert body["voice_response"]["voice_provider_state"] == "client_text_reply_no_provider_call"
    assert body["voice_response"]["voice_provider_receipt_mode"] == "client_text_reply_no_provider_call"
    assert body["voice_response"]["voice_provider_receipt_mode_is_provider_call"] is False
    assert body["voice_response"]["live_voice_provider_call"] is False
    assert body["voice_response"]["replay_voice_provider_call"] is False
    assert body["voice_response"]["elevenlabs_provider_invoked"] is False
    assert body["chat_forward"]["requested"] is False
    assert body["chat_forward"]["forwarded"] is False
    assert body["orb_voice_bridge"]["status"] == "mcp_connection_proof_recorded"
    assert body["orb_voice_bridge"]["virtual_voice_turn"] is False
    assert body["orb_voice_bridge"]["orb_is_embodiment"] is True
    assert body["orb_voice_bridge"]["client_origin"] == "chatgpt_app_voice"
    assert body["receipt"]["proof_kind"] == "mcp_connection"
    assert body["receipt"]["actor"] == _ACTOR
    assert body["receipt"]["source"] == "chatgpt.voice"
    assert body["receipt"]["client_origin"] == "chatgpt_app_voice"
    assert body["receipt"]["mcp_gateway_tool"] == "francis.chatgpt_voice.mcp_probe"
    assert body["receipt"]["mcp_server_tool"] == "francis_chatgpt_voice_mcp_probe"
    assert body["receipt"]["mcp_server_transport"] == ""
    assert body["receipt"]["voice_output_provider"] == "chatgpt_voice_client"
    assert body["receipt"]["voice_output_mode"] == "client_text_reply"
    assert body["receipt"]["voice_provider_state"] == "client_text_reply_no_provider_call"
    assert body["receipt"]["voice_provider_receipt_mode"] == "client_text_reply_no_provider_call"
    assert body["receipt"]["voice_provider_receipt_mode_is_provider_call"] is False
    assert body["receipt"]["live_voice_provider_call"] is False
    assert body["receipt"]["mock_voice_provider_call"] is False
    assert body["receipt"]["fixture_voice_provider_call"] is False
    assert body["receipt"]["replay_voice_provider_call"] is False
    assert body["receipt"]["voice_provider_unavailable"] is False
    assert body["receipt"]["voice_provider_unconfigured"] is False
    assert body["receipt"]["elevenlabs_provider_invoked"] is False
    assert body["receipt"]["elevenlabs_audio_claimed"] is False
    assert body["receipt"]["voice_provider_receipt"]["provider_status_observed"] is False
    assert body["receipt"]["voice_provider_receipt"]["receipt_mode"] == "client_text_reply_no_provider_call"
    assert body["receipt"]["voice_provider_receipt"]["receipt_mode_is_provider_call"] is False
    assert body["receipt"]["voice_provider_receipt"]["elevenlabs"]["bridge_invokes_provider"] is False
    assert body["orb_voice_bridge"]["mcp_server_transport"] == ""
    assert body["orb_voice_bridge"]["mcp_server_transport_verified"] is False
    assert body["orb_voice_bridge"]["public_mcp_connector_transport"] is False
    assert body["receipt"]["transcript"] == ""
    assert body["receipt"]["transcript_char_count"] == 0
    assert body["receipt"]["governance"]["writes_receipt"] is True
    assert body["receipt"]["governance"]["forwards_to_chat"] is False
    assert Path(body["receipt"]["receipt_path"]).exists()
    assert not (data_root / "runtime" / "lens-overlay" / "voice-turn-status.json").exists()
    assert not (data_root / "conversations" / "ledger" / "ledger.jsonl").exists()


def test_chatgpt_voice_mcp_probe_redacts_secret_metadata_in_receipts(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", _scopes("chatgpt.voice.bridge.read", "chatgpt.voice.bridge.write"))
    secret = "sk-" + ("b" * 24)

    proof = run_tool(
        "francis.chatgpt_voice.mcp_probe",
        {
            "actor": _ACTOR,
            "source": f"chatgpt.voice token={secret}",
            "client_origin": f"chatgpt_app_voice token={secret}",
            "reason": f"connector proof api_key={secret}",
            "mcp_server_transport": f"streamable-http token={secret}",
        },
    )

    assert proof["ok"] is True
    assert secret not in json.dumps(proof)
    receipt = proof["data"]["receipt"]
    assert receipt["secrets_redacted"] is True
    assert receipt["metadata_secrets_redacted"] is True
    assert set(receipt["redacted_metadata_fields"]) >= {
        "client_origin",
        "mcp_server_transport",
        "reason",
        "source",
    }
    receipt_path = Path(receipt["receipt_path"])
    assert secret not in receipt_path.read_text(encoding="utf-8")

    receipts = run_tool("francis.chatgpt_voice.receipts", {"actor": _ACTOR, "limit": 5})
    assert receipts["ok"] is True
    assert secret not in json.dumps(receipts)


def test_chatgpt_voice_http_ingress_preserves_browser_voice_client_origin(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv(
        "FRANCIS_API_ACTOR_SCOPES",
        json.dumps({"chat_ui.voice": ["chatgpt.voice.bridge.write", "chat.write"]}),
    )

    client = TestClient(create_app())

    body = client.post(
        "/chatgpt-voice/ingress",
        json={
            "actor": "chat_ui.voice",
            "source": "chat_ui.voice",
            "client_origin": "francis_chat_ui_browser_voice",
            "transcript": "there is a sound near the desk",
            "turn_id": "browser-voice-passive",
            "forward_to_chat": False,
        },
    ).json()

    assert body["ok"] is True
    assert body["status"] == "recorded"
    assert body["receipt"]["actor"] == "chat_ui.voice"
    assert body["receipt"]["source"] == "chat_ui.voice"
    assert body["receipt"]["client_origin"] == "francis_chat_ui_browser_voice"
    assert body["orb_voice_bridge"]["client_origin"] == "francis_chat_ui_browser_voice"
    assert body["chat_forward"]["requested"] is False
    assert not (data_root / "conversations" / "ledger" / "ledger.jsonl").exists()


def test_chatgpt_voice_browser_ingress_queues_orb_position_command_without_chat_forward(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv(
        "FRANCIS_API_ACTOR_SCOPES",
        json.dumps({"chat_ui.voice": ["chatgpt.voice.bridge.write", "chat.write"]}),
    )

    client = TestClient(create_app())

    body = client.post(
        "/chatgpt-voice/ingress",
        json={
            "actor": "chat_ui.voice",
            "source": "chat_ui.voice",
            "client_origin": "francis_chat_ui_browser_voice",
            "transcript": "Francis move the orb to the left side please",
            "turn_id": "browser-orb-left-command",
            "forward_to_chat": True,
        },
    ).json()

    assert body["ok"] is True
    assert body["status"] == "orb_position_command_queued"
    assert body["reply"] == "I queued the orb move to the left side."
    assert body["voice_response"]["source"] == "bridge.orb_position_command_queued"
    assert body["chat_forward"]["requested"] is True
    assert body["chat_forward"]["forwarded"] is False
    assert body["chat_forward"]["status"] == "suppressed_orb_position_command"
    command = body["orb_position_command"]
    assert command["status"] == "queued"
    assert command["request_id"] == "browser-orb-left-command"
    assert command["command"] == "move_orb_left_side"
    assert command["reference_type"] == "orb"
    assert command["target_side"] == "left"
    assert command["target_anchor"] == "voice_command_left_side"
    assert command["conversation_forwarding_suppressed"] is True
    assert command["overlay_runtime_owns_execution"] is True
    assert command["authority_scope"] == "runtime_overlay_position_only"
    assert command["substrate_boundary"]["voice_controls_orb_directly"] is False
    assert command["substrate_boundary"]["bridge_writes_overlay_command_request"] is True
    assert command["substrate_boundary"]["overlay_runtime_owns_position_mutation"] is True
    assert command["substrate_boundary"]["applied_state_requires_overlay_receipt"] is True
    assert command["substrate_boundary"]["orb_applied_state_claimed_by_bridge"] is False
    assert command["substrate_boundary"]["orb_visual_lock_preserved"] is True
    assert command["substrate_boundary"]["substrate_governance_bypass"] is False
    assert command["grants_execution_authority"] is False
    assert command["grants_mutation_authority"] is False

    request_path = data_root / "runtime" / "lens-overlay" / "orb-position-command-request.json"
    assert request_path.exists()
    request = json.loads(request_path.read_text(encoding="utf-8"))
    assert request["kind"] == "lens.overlay.orb_position_command.request"
    assert request["status"] == "queued"
    assert request["command"] == "move_orb_left_side"
    assert request["reference_type"] == "orb"
    assert request["target_side"] == "left"
    assert request["stores_transcript"] is False
    assert request["chat_forward_requested_before_command"] is True
    assert request["substrate_boundary"]["voice_controls_orb_directly"] is False
    assert request["substrate_boundary"]["overlay_runtime_owns_position_mutation"] is True
    assert request["substrate_boundary"]["applied_state_requires_overlay_receipt"] is True
    assert request["substrate_boundary"]["orb_applied_state_claimed_by_bridge"] is False
    assert request["substrate_boundary"]["orb_visual_lock_preserved"] is True
    assert request["governance"]["substrate_governance_bypass"] is False
    assert "Francis move the orb" not in json.dumps(request)

    command_receipt = data_root / "runtime" / "lens-overlay" / "orb-position-commands" / "browser-orb-left-command.json"
    assert command_receipt.exists()
    assert body["receipt"]["chat_forward_status"] == "suppressed_orb_position_command"
    assert body["receipt"]["orb_position_command_request"]["command"] == "move_orb_left_side"
    assert body["receipt"]["orb_position_command_request"]["substrate_boundary"]["voice_controls_orb_directly"] is False
    assert (
        body["receipt"]["orb_position_command_request"]["substrate_boundary"]["applied_state_requires_overlay_receipt"]
        is True
    )
    command_proof = body["receipt"]["voice_substrate_proof"]
    assert command_proof["structured_receipts"]["orb_position_command_request_receipt"] is True
    assert command_proof["orb_position_command_receipt_path"] == (
        "data/runtime/lens-overlay/orb-position-commands/browser-orb-left-command.json"
    )
    assert command_proof["bridge_queues_overlay_request"] is True
    assert command_proof["overlay_receipt_required_for_applied_state"] is True
    assert command_proof["orb_applied_state_claimed_by_bridge"] is False
    assert command_proof["voice_controls_orb_directly"] is False
    assert body["receipt"]["governance"]["forwards_to_chat"] is False
    assert body["receipt"]["governance"]["writes_overlay_position_command_request"] is True
    assert body["receipt"]["governance"]["mutation_authority_scope"] == "runtime_overlay_position_only"
    assert body["receipt"]["governance"]["grants_execution_authority"] is False
    assert body["receipt"]["governance"]["grants_mutation_authority"] is False
    assert body["orb_voice_bridge"]["orb_position_command_detected"] is True
    assert body["orb_voice_bridge"]["orb_position_command"] == "move_orb_left_side"
    assert body["orb_voice_bridge"]["orb_position_command_overlay_runtime_owns_execution"] is True
    assert not (data_root / "conversations" / "ledger" / "ledger.jsonl").exists()


def test_chatgpt_voice_browser_ingress_queues_francis_identity_orb_move(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv(
        "FRANCIS_API_ACTOR_SCOPES",
        json.dumps({"chat_ui.voice": ["chatgpt.voice.bridge.write", "chat.write"]}),
    )

    client = TestClient(create_app())

    body = client.post(
        "/chatgpt-voice/ingress",
        json={
            "actor": "chat_ui.voice",
            "source": "chat_ui.voice",
            "client_origin": "francis_chat_ui_browser_voice",
            "transcript": "Francis move left",
            "turn_id": "browser-francis-left-command",
            "forward_to_chat": True,
        },
    ).json()

    assert body["ok"] is True
    assert body["status"] == "orb_position_command_queued"
    assert body["chat_forward"]["status"] == "suppressed_orb_position_command"
    command = body["orb_position_command"]
    assert command["command"] == "move_orb_left_side"
    assert command["reference_type"] == "francis_identity"
    assert command["target_side"] == "left"
    request_path = data_root / "runtime" / "lens-overlay" / "orb-position-command-request.json"
    request = json.loads(request_path.read_text(encoding="utf-8"))
    assert request["command"] == "move_orb_left_side"
    assert request["reference_type"] == "francis_identity"
    assert request["stores_transcript"] is False
    assert "Francis move left" not in json.dumps(request)


def test_chatgpt_voice_browser_ingress_queues_natural_francis_identity_orb_move(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv(
        "FRANCIS_API_ACTOR_SCOPES",
        json.dumps({"chat_ui.voice": ["chatgpt.voice.bridge.write", "chat.write"]}),
    )

    client = TestClient(create_app())

    body = client.post(
        "/chatgpt-voice/ingress",
        json={
            "actor": "chat_ui.voice",
            "source": "chat_ui.voice",
            "client_origin": "francis_chat_ui_browser_voice",
            "transcript": "Francis go right",
            "turn_id": "browser-francis-natural-right-command",
            "forward_to_chat": True,
        },
    ).json()

    assert body["ok"] is True
    assert body["status"] == "orb_position_command_queued"
    assert body["chat_forward"]["status"] == "suppressed_orb_position_command"
    command = body["orb_position_command"]
    assert command["command"] == "move_orb_right_side"
    assert command["reference_type"] == "francis_identity"
    assert command["target_side"] == "right"
    request_path = data_root / "runtime" / "lens-overlay" / "orb-position-command-request.json"
    request = json.loads(request_path.read_text(encoding="utf-8"))
    assert request["command"] == "move_orb_right_side"
    assert request["reference_type"] == "francis_identity"
    assert request["stores_transcript"] is False
    assert "Francis go right" not in json.dumps(request)


def test_chatgpt_voice_browser_ingress_does_not_queue_bare_move_left(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv(
        "FRANCIS_API_ACTOR_SCOPES",
        json.dumps({"chat_ui.voice": ["chatgpt.voice.bridge.write", "chat.write"]}),
    )

    client = TestClient(create_app())

    body = client.post(
        "/chatgpt-voice/ingress",
        json={
            "actor": "chat_ui.voice",
            "source": "chat_ui.voice",
            "client_origin": "francis_chat_ui_browser_voice",
            "transcript": "move left",
            "turn_id": "browser-bare-left-command",
            "forward_to_chat": False,
        },
    ).json()

    assert body["ok"] is True
    assert body["status"] == "recorded"
    assert not (data_root / "runtime" / "lens-overlay" / "orb-position-command-request.json").exists()


def test_chatgpt_voice_forward_requires_existing_chat_write_gate(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", _scopes("chatgpt.voice.bridge.write"))

    client = TestClient(create_app())

    body = client.post(
        "/chatgpt-voice/ingress",
        json={"actor": _ACTOR, "transcript": "can you hear me", "turn_id": "voice-turn-denied"},
    ).json()

    assert body["ok"] is False
    assert body["status"] == "recorded_not_forwarded"
    assert body["reply"] == "I recorded the transcript, but the Francis chat write gate did not accept forwarding."
    assert body["voice_response"]["source"] == "bridge.forward_denied"
    assert body["chat_forward"]["requested"] is True
    assert body["chat_forward"]["forwarded"] is False
    assert body["chat_forward"]["error"] == "api_permission_denied"
    assert body["receipt"]["chat_forward_status"] == "denied"
    assert body["receipt"]["reply_source"] == "bridge.forward_denied"
    assert Path(body["receipt"]["receipt_path"]).exists()
    assert not (data_root / "conversations" / "ledger" / "ledger.jsonl").exists()


def test_chatgpt_voice_forward_reaches_chat_when_scoped(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv(
        "FRANCIS_API_ACTOR_SCOPES",
        _scopes("chatgpt.voice.bridge.write", "chat.write"),
    )

    client = TestClient(create_app())

    body = client.post(
        "/chatgpt-voice/ingress",
        json={"actor": _ACTOR, "transcript": "can you hear me", "turn_id": "voice-turn-forwarded"},
    ).json()

    assert body["ok"] is True
    assert body["status"] == "forwarded"
    assert body["reply"] == "I can hear you. Voice input is reaching Francis."
    assert body["voice_response"]["source"] == "chat_forward.response"
    assert body["voice_response"]["speakable"] is True
    assert body["chat_forward"]["forwarded"] is True
    assert body["chat_forward"]["response"]["reply"] == "I can hear you. Voice input is reaching Francis."
    assert body["receipt"]["chat_forward_status"] == "forwarded"
    assert body["receipt"]["chat_response_status"] == ""
    assert body["receipt"]["reply"] == "I can hear you. Voice input is reaching Francis."
    assert body["orb_voice_bridge"]["status"] == "chatgpt_voice_reply_ready"
    assert body["orb_voice_bridge"]["chat_bridge_status"] == "forwarded"
    assert body["orb_voice_bridge"]["chat_forwarded"] is True
    assert body["orb_voice_bridge"]["client_speaks_top_level_reply"] is True
    assert body["orb_voice_bridge"]["local_overlay_speech_started"] is False
    assert body["governance"]["calls_model"] is False
    assert body["governance"]["grants_execution_authority"] is False

    ledger = data_root / "conversations" / "ledger" / "ledger.jsonl"
    assert ledger.exists()
    ledger_text = ledger.read_text(encoding="utf-8")
    assert "can you hear me" in ledger_text
    assert "voice-turn-forwarded" in ledger_text


def test_chatgpt_voice_mcp_ingress_updates_orb_virtual_voice_turn(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv(
        "FRANCIS_API_ACTOR_SCOPES",
        _scopes("chatgpt.voice.bridge.write", "chat.write"),
    )

    result = run_tool(
        "francis.chatgpt_voice.ingress",
        {
            "actor": _ACTOR,
            "source": "chatgpt.voice",
            "transcript": "can you hear me",
            "turn_id": "chatgpt-mcp-voice-turn",
            "ingress_transport": "mcp_gateway_tool",
            "mcp_gateway_tool": "francis.chatgpt_voice.ingress",
            "mcp_server_tool": "francis_chatgpt_voice_ingress",
        },
    )

    assert result["ok"] is True
    assert result["status"] == "forwarded"
    body = result["data"]
    assert body["ok"] is True
    assert body["status"] == "forwarded"
    assert body["reply"] == "I can hear you. Voice input is reaching Francis."
    orb_voice = body["orb_voice_bridge"]
    assert orb_voice["status"] == "chatgpt_voice_reply_ready"
    assert orb_voice["turn_id"] == "chatgpt-mcp-voice-turn"
    assert orb_voice["virtual_voice_turn"] is True
    assert orb_voice["client_origin"] == "chatgpt_app_voice"
    assert orb_voice["mcp_ingress"] is True
    assert orb_voice["transcript_source"] == "chatgpt_voice_mcp_transcript"
    assert orb_voice["chat_bridge_status"] == "forwarded"
    assert orb_voice["chat_forwarded"] is True
    assert orb_voice["client_speaks_top_level_reply"] is True
    assert orb_voice["local_overlay_speech_started"] is False
    assert orb_voice["microphone_recognition_claimed"] is False
    assert orb_voice["raw_audio"] is False
    assert body["receipt"]["orb_voice_bridge"]["mcp_ingress"] is True
    assert body["receipt"]["client_origin"] == "chatgpt_app_voice"
    assert body["receipt"]["mcp_server_tool"] == "francis_chatgpt_voice_ingress"
    assert body["receipt"]["mcp_server_transport"] == ""

    voice_state = data_root / "runtime" / "lens-overlay" / "voice-turn-status.json"
    assert voice_state.exists()
    state = json.loads(voice_state.read_text(encoding="utf-8"))
    assert state["kind"] == "lens.overlay.voice.turn_state"
    assert state["status"] == "chatgpt_voice_reply_ready"
    assert state["active_turn_id"] == "chatgpt-mcp-voice-turn"
    assert state["virtual_voice_turn"] is True
    assert state["mcp_ingress"] is True
    assert state["mcp_server_tool"] == "francis_chatgpt_voice_ingress"
    assert state["mcp_server_transport"] == ""
    assert state["client_origin"] == "chatgpt_app_voice"
    assert state["microphone_speech"] is False
    assert state["microphone_recognition_claimed"] is False
    assert state["raw_audio"] is False
    assert state["chat_route_writes_conversation_ledger"] is True
    assert state["speech_output_owner"] == "chatgpt_voice_client"
    assert state["voice_output_provider"] == "chatgpt_voice_client"
    assert state["voice_output_mode"] == "client_text_reply"
    assert state["live_voice_provider_call"] is False
    assert state["mock_voice_provider_call"] is False
    assert state["fixture_voice_provider_call"] is False
    assert state["replay_voice_provider_call"] is False
    assert state["voice_provider_unavailable"] is False
    assert state["voice_provider_unconfigured"] is False
    assert state["elevenlabs_provider_invoked"] is False
    assert state["local_overlay_speech_started"] is False
    assert "can you hear me" not in json.dumps(state)

    voice_receipt = data_root / "runtime" / "lens-overlay" / "voice-turns" / "chatgpt-mcp-voice-turn.json"
    assert voice_receipt.exists()


def test_chatgpt_voice_mcp_ingress_keeps_local_selftest_origin_unspecified(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv(
        "FRANCIS_API_ACTOR_SCOPES",
        _scopes("chatgpt.voice.bridge.write", "chat.write"),
    )

    result = run_tool(
        "francis.chatgpt_voice.ingress",
        {
            "actor": _ACTOR,
            "source": "local.mcp.selftest",
            "transcript": "can you hear me",
            "turn_id": "local-mcp-selftest-turn",
            "ingress_transport": "mcp_gateway_tool",
            "mcp_gateway_tool": "francis.chatgpt_voice.ingress",
            "mcp_server_tool": "francis_chatgpt_voice_ingress",
        },
    )

    assert result["ok"] is True
    body = result["data"]
    assert body["receipt"]["source"] == "local.mcp.selftest"
    assert body["receipt"]["client_origin"] == "mcp_client_unspecified"
    assert body["orb_voice_bridge"]["client_origin"] == "mcp_client_unspecified"


def test_chatgpt_voice_forward_uses_continuity_context_for_llm(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv(
        "FRANCIS_API_ACTOR_SCOPES",
        _scopes("chatgpt.voice.bridge.write", "chat.write"),
    )

    from francis.chat import router as chat_router

    captured_prompts: list[str] = []

    def fake_generate(prompt: str) -> str:
        captured_prompts.append(prompt)
        return "Your orb codename is Solstice."

    monkeypatch.setattr(chat_router, "generate", fake_generate)

    client = TestClient(create_app())
    first = client.post(
        "/chatgpt-voice/ingress",
        json={
            "actor": _ACTOR,
            "transcript": "Remember my orb codename is Solstice.",
            "turn_id": "voice-turn-memory-1",
        },
    ).json()
    assert first["ok"] is True
    assert first["status"] == "forwarded"

    body = client.post(
        "/chatgpt-voice/ingress",
        json={
            "actor": _ACTOR,
            "transcript": "What is my orb codename?",
            "turn_id": "voice-turn-memory-2",
            "use_llm": True,
        },
    ).json()

    assert body["ok"] is True
    assert body["status"] == "forwarded"
    assert body["reply"] == "Your orb codename is Solstice."
    assert body["voice_response"]["source"] == "chat_forward.response"
    assert body["chat_forward"]["forwarded"] is True
    chat_response = body["chat_forward"]["response"]
    continuity = chat_response["telemetry_context"]["continuity_prompt_context"]
    assert continuity["status"] == "applied"
    assert continuity["source_id"] == "conversation_ledger"
    assert continuity["line_count"] >= 1
    assert continuity["matched_entry_count"] >= 1
    assert continuity["reads_memory"] is True
    assert continuity["writes_memory"] is False
    assert continuity["grants_execution_authority"] is False
    assert continuity["grants_mutation_authority"] is False
    assert captured_prompts
    assert "continuity.ledger.relevant[user]: Remember my orb codename is Solstice." in captured_prompts[0]
    assert "francis.identity: You are Francis; voice, lens, and orb are three Francis surfaces" in captured_prompts[0]
    assert "francis.orb_embodiment: The Orb is Francis's embodiment" in captured_prompts[0]
    identity = chat_response["telemetry_context"]["francis_identity_context"]
    assert identity["status"] == "applied"
    assert identity["identity"] == "Francis"
    assert identity["surfaces"] == ["voice", "lens", "orb"]
    assert identity["surface_route"] == "chatgpt_voice_bridge"
    assert identity["orb_role"] == "embodiment"
    assert identity["voice_lens_orb_are_separate_identities"] is False
    assert identity["voice_lens_orb_are_francis_surfaces"] is True
    assert identity["grants_execution_authority"] is False
    assert identity["grants_mutation_authority"] is False
    trace = chat_response["execution_trace"]
    assert trace["francis_identity_context_applied"] is True
    assert trace["francis_identity"] == "Francis"
    assert trace["orb_is_embodiment"] is True
    assert "voice-turn-memory-2" in body["receipt"]["turn_id"]


def test_chatgpt_voice_forward_sentence_bounds_long_model_reply(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv(
        "FRANCIS_API_ACTOR_SCOPES",
        _scopes("chatgpt.voice.bridge.write", "chat.write"),
    )

    from francis.chat import router as chat_router

    first_sentence = (
        "Francis received the voice turn and is keeping the answer short for spoken playback while preserving "
        "the operator-facing receipt and bridge state with no extra execution authority."
    )
    long_tail = " This extra material should stay in the chat response object but not in the top-level voice reply" * 20

    def fake_generate(prompt: str) -> str:
        assert "francis.identity: You are Francis; voice, lens, and orb are three Francis surfaces" in prompt
        return f"{first_sentence}.{long_tail}"

    monkeypatch.setattr(chat_router, "generate", fake_generate)

    client = TestClient(create_app())
    body = client.post(
        "/chatgpt-voice/ingress",
        json={
            "actor": _ACTOR,
            "transcript": "Francis explain the bridge state",
            "turn_id": "voice-turn-long-reply",
            "use_llm": True,
        },
    ).json()

    assert body["ok"] is True
    assert body["status"] == "forwarded"
    assert body["reply"] == f"{first_sentence}."
    assert len(body["reply"]) <= 420
    assert body["voice_response"]["text"] == body["reply"]
    assert body["voice_response"]["text_truncated"] is True
    assert body["voice_response"]["sentence_aware_limit"] is True
    assert body["receipt"]["chat_reply_max_speakable_chars"] == 420
    assert body["receipt"]["chat_reply_truncated_for_voice"] is True
    assert body["receipt"]["chat_reply_sentence_aware_limit"] is True
    assert body["chat_forward"]["response"]["reply"].startswith(first_sentence)
    assert "This extra material" in body["chat_forward"]["response"]["reply"]
    assert "This extra material" not in body["reply"]

    voice_state = data_root / "runtime" / "lens-overlay" / "voice-turn-status.json"
    state = json.loads(voice_state.read_text(encoding="utf-8"))
    assert state["chat_reply_max_speakable_chars"] == 420
    assert state["chat_reply_truncated_for_voice"] is True
    assert state["chat_reply_sentence_aware_limit"] is True
    assert state["chat_reply_length"] == len(body["reply"])
    assert state["client_speaks_top_level_reply"] is True
    assert state["grants_execution_authority"] is False


def test_chatgpt_voice_ingress_rejects_unavailable_transcript_with_reply(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", _scopes("chatgpt.voice.bridge.write", "chat.write"))

    client = TestClient(create_app())

    body = client.post(
        "/chatgpt-voice/ingress",
        json={"actor": _ACTOR, "transcript": "Transcript Unavailable", "turn_id": "voice-turn-empty"},
    ).json()

    assert body["ok"] is False
    assert body["status"] == "rejected"
    assert body["error"] == "transcript_unavailable"
    assert body["reply"] == (
        "ChatGPT reported that the transcript was unavailable, so I did not forward that as your message. "
        "Please repeat the request or send the text."
    )
    assert body["voice_response"]["source"] == "bridge.transcript_guard"
    assert body["voice_response"]["requires_transcript"] is True
    assert body["voice_response"]["grants_execution_authority"] is False
    assert body["receipt"]["reason"] == "transcript_unavailable"
    assert body["receipt"]["chat_forward_requested"] is True
    unavailable_proof = body["receipt"]["voice_substrate_proof"]
    assert unavailable_proof["transcript_state"] == "transcript_unavailable_rejected"
    assert unavailable_proof["structured_receipts"]["bridge_ingress_receipt"] is True
    assert unavailable_proof["structured_receipts"]["virtual_voice_turn_receipt"] is True
    assert unavailable_proof["provider_receipt_mode"] == "client_text_reply_no_provider_call"
    assert unavailable_proof["output_provider_call_claimed"] is False
    assert unavailable_proof["voice_provider_unavailable"] is False
    assert unavailable_proof["voice_provider_unconfigured"] is False
    assert unavailable_proof["voice_controls_orb_directly"] is False
    assert body["receipt"]["orb_voice_bridge"]["status"] == "chatgpt_voice_transcript_rejected"
    assert body["orb_voice_bridge"]["status"] == "chatgpt_voice_transcript_rejected"
    assert body["orb_voice_bridge"]["virtual_voice_turn"] is True
    assert body["orb_voice_bridge"]["mcp_ingress"] is False
    assert body["orb_voice_bridge"]["microphone_recognition_claimed"] is False
    assert body["orb_voice_bridge"]["raw_audio"] is False
    assert isinstance(body["receipt"]["created_ts"], float)
    assert body["receipt"]["created_at"].endswith("Z")
    assert body["receipt"]["governance"]["forwards_to_chat"] is False
    assert Path(body["receipt"]["receipt_path"]).exists()
    assert not (data_root / "conversations" / "ledger" / "ledger.jsonl").exists()


def test_chatgpt_voice_ingress_rejects_transcript_unavailable_prefix_with_filler(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", _scopes("chatgpt.voice.bridge.write", "chat.write"))

    client = TestClient(create_app())

    body = client.post(
        "/chatgpt-voice/ingress",
        json={
            "actor": _ACTOR,
            "transcript": "Transcript Unavailable\n\nAll right, I'm awaiting the next actionable step.",
            "turn_id": "voice-turn-unavailable-prefix",
        },
    ).json()

    assert body["ok"] is False
    assert body["status"] == "rejected"
    assert body["error"] == "transcript_unavailable"
    assert body["voice_response"]["source"] == "bridge.transcript_guard"
    assert body["voice_response"]["requires_transcript"] is True
    assert body["chat_forward"]["requested"] is True
    assert body["chat_forward"]["forwarded"] is False
    assert body["receipt"]["reason"] == "transcript_unavailable"
    assert body["receipt"]["chat_forward_requested"] is True
    assert body["receipt"]["governance"]["forwards_to_chat"] is False
    assert Path(body["receipt"]["receipt_path"]).exists()
    assert not (data_root / "conversations" / "ledger" / "ledger.jsonl").exists()


def test_chatgpt_voice_mcp_tools_expose_bounded_bridge(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", _scopes("chatgpt.voice.bridge.read", "chatgpt.voice.bridge.write"))

    names = {tool["name"] for tool in list_tools()}
    assert "francis.chatgpt_voice.contract" in names
    assert "francis.chatgpt_voice.ingress" in names
    assert "francis.chatgpt_voice.mcp_probe" in names
    assert "francis.chatgpt_voice.receipts" in names
    tool_by_name = {tool["name"]: tool for tool in list_tools()}
    ingress_description = tool_by_name["francis.chatgpt_voice.ingress"]["description"]
    assert "required bridge for every ChatGPT voice turn directed at Francis" in ingress_description
    assert "speak only the returned top-level `reply`" in ingress_description
    assert "sentence-aware and bounded for spoken playback" in ingress_description
    assert "Transcript Unavailable" in ingress_description
    assert "Do not answer locally" in ingress_description

    contract = run_tool("francis.chatgpt_voice.contract", {"actor": _ACTOR})
    assert contract["ok"] is True
    assert contract["governance"]["read_only"] is True
    speech_contract = contract["data"]["client_speech_contract"]
    assert speech_contract["mcp_server_default_client_origin"] == "chatgpt_app_voice"
    assert speech_contract["max_reply_chars"] == 420
    assert speech_contract["sentence_aware_reply_limit"] is True

    proof = run_tool("francis.chatgpt_voice.mcp_probe", {"actor": _ACTOR, "source": "chatgpt.voice"})
    assert proof["ok"] is True
    assert proof["status"] == "recorded"
    assert proof["governance"]["raw_audio"] is False
    assert proof["governance"]["grants_execution_authority"] is False
    assert proof["data"]["receipt"]["proof_kind"] == "mcp_connection"
    assert proof["data"]["receipt"]["mcp_gateway_tool"] == "francis.chatgpt_voice.mcp_probe"
    assert proof["data"]["receipt"]["mcp_server_tool"] == "francis_chatgpt_voice_mcp_probe"
    assert proof["data"]["receipt"]["mcp_server_transport"] == ""
    assert proof["data"]["receipt"]["client_origin"] == "chatgpt_app_voice"
    assert proof["data"]["receipt"]["transcript"] == ""
    assert proof["data"]["orb_voice_bridge"]["virtual_voice_turn"] is False

    ingress = run_tool(
        "francis.chatgpt_voice.ingress",
        {
            "actor": _ACTOR,
            "transcript": "hello Francis",
            "forward_to_chat": False,
            "client_origin": "chatgpt_app_voice",
        },
    )
    assert ingress["ok"] is True
    assert ingress["status"] == "recorded"
    assert ingress["governance"]["raw_shell"] is False
    assert ingress["governance"]["raw_audio"] is False
    assert ingress["data"]["receipt"]["ingress_transport"] == "mcp_gateway_tool"
    assert ingress["data"]["receipt"]["mcp_gateway_tool"] == "francis.chatgpt_voice.ingress"
    assert ingress["data"]["receipt"]["mcp_server_tool"] == ""
    assert ingress["data"]["receipt"]["mcp_server_transport"] == ""
    assert ingress["data"]["receipt"]["client_origin"] == "chatgpt_app_voice"
    assert ingress["data"]["orb_voice_bridge"]["virtual_voice_turn"] is True
    assert ingress["data"]["orb_voice_bridge"]["mcp_ingress"] is True
    assert ingress["data"]["orb_voice_bridge"]["client_origin"] == "chatgpt_app_voice"
    assert ingress["data"]["orb_voice_bridge"]["local_overlay_speech_started"] is False

    receipts = run_tool("francis.chatgpt_voice.receipts", {"actor": _ACTOR, "limit": 5})
    assert receipts["ok"] is True
    assert receipts["data"]["count"] == 2
