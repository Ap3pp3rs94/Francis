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
    assert body["mcp_tools"]["ingress"] == "francis.chatgpt_voice.ingress"
    assert body["mcp_tools"]["server_ingress"] == "francis_chatgpt_voice_ingress"
    assert body["receipt_contract"]["direct_http_transport"] == "http_api"
    assert body["receipt_contract"]["mcp_gateway_transport"] == "mcp_gateway_tool"
    assert body["receipt_contract"]["mcp_gateway_tool"] == "francis.chatgpt_voice.ingress"
    assert body["receipt_contract"]["mcp_server_tool"] == "francis_chatgpt_voice_ingress"
    assert body["orb_voice_contract"]["mcp_transcript_updates_voice_turn_readback"] is True
    assert body["orb_voice_contract"]["voice_turn_state_path"] == "data/runtime/lens-overlay/voice-turn-status.json"
    assert body["orb_voice_contract"]["virtual_voice_turn"] is True
    assert body["orb_voice_contract"]["microphone_capture_claimed"] is False
    assert body["orb_voice_contract"]["raw_audio_stream_accepted"] is False
    assert body["orb_voice_contract"]["client_speaks_top_level_reply"] is True
    assert body["input_contract"]["audio_stream_accepted"] is False
    assert body["client_speech_contract"]["call_ingress_for_every_voice_turn"] is True
    assert body["client_speech_contract"]["speak_only_top_level_reply"] is True
    assert body["client_speech_contract"]["transcript_unavailable_must_be_forwarded"] is True
    assert body["client_speech_contract"]["local_fallback_answer_allowed"] is False
    assert "Do not answer locally" in body["client_speech_contract"]["description"]
    assert body["chatgpt_app_boundary"]["native_phone_localhost_access_claimed"] is False
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
    assert body["chat_forward"]["requested"] is False
    assert body["receipt"]["transcript"] == "Francis can you hear me"
    assert body["receipt"]["turn_id"] == "voice-turn-1"
    assert body["receipt"]["ingress_transport"] == "http_api"
    assert body["receipt"]["mcp_gateway_tool"] == ""
    assert body["receipt"]["mcp_server_tool"] == ""
    assert body["receipt"]["reply_source"] == "bridge.recorded_only"
    assert isinstance(body["receipt"]["created_ts"], float)
    assert body["receipt"]["created_at"].endswith("Z")
    receipt_path = Path(body["receipt"]["receipt_path"])
    assert receipt_path.exists()
    persisted = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert persisted["created_ts"] == body["receipt"]["created_ts"]
    assert persisted["created_at"] == body["receipt"]["created_at"]
    orb_voice = body["orb_voice_bridge"]
    assert orb_voice["status"] == "chatgpt_voice_transcript_recorded"
    assert orb_voice["virtual_voice_turn"] is True
    assert orb_voice["mcp_ingress"] is False
    assert orb_voice["transcript_source"] == "chatgpt_voice_http_transcript"
    assert orb_voice["microphone_recognition_claimed"] is False
    assert orb_voice["raw_audio"] is False
    assert body["receipt"]["orb_voice_bridge"]["status"] == "chatgpt_voice_transcript_recorded"
    voice_state = data_root / "runtime" / "lens-overlay" / "voice-turn-status.json"
    assert voice_state.exists()
    state = json.loads(voice_state.read_text(encoding="utf-8"))
    assert state["turn_id"] == "voice-turn-1"
    assert state["virtual_voice_turn"] is True
    assert state["transcript_source"] == "chatgpt_voice_http_transcript"
    assert state["local_overlay_speech_started"] is False
    assert body["governance"]["writes_receipt"] is True
    assert body["governance"]["writes_lens_voice_turn"] is True
    assert body["governance"]["forwards_to_chat"] is False
    assert body["governance"]["raw_audio"] is False
    assert body["governance"]["grants_execution_authority"] is False
    assert not (data_root / "conversations" / "ledger" / "ledger.jsonl").exists()


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
    assert orb_voice["client_origin"] == "mcp_client_unspecified"
    assert orb_voice["mcp_ingress"] is True
    assert orb_voice["transcript_source"] == "chatgpt_voice_mcp_transcript"
    assert orb_voice["chat_bridge_status"] == "forwarded"
    assert orb_voice["chat_forwarded"] is True
    assert orb_voice["client_speaks_top_level_reply"] is True
    assert orb_voice["local_overlay_speech_started"] is False
    assert orb_voice["microphone_recognition_claimed"] is False
    assert orb_voice["raw_audio"] is False
    assert body["receipt"]["orb_voice_bridge"]["mcp_ingress"] is True
    assert body["receipt"]["client_origin"] == "mcp_client_unspecified"
    assert body["receipt"]["mcp_server_tool"] == "francis_chatgpt_voice_ingress"

    voice_state = data_root / "runtime" / "lens-overlay" / "voice-turn-status.json"
    assert voice_state.exists()
    state = json.loads(voice_state.read_text(encoding="utf-8"))
    assert state["kind"] == "lens.overlay.voice.turn_state"
    assert state["status"] == "chatgpt_voice_reply_ready"
    assert state["active_turn_id"] == "chatgpt-mcp-voice-turn"
    assert state["virtual_voice_turn"] is True
    assert state["mcp_ingress"] is True
    assert state["mcp_server_tool"] == "francis_chatgpt_voice_ingress"
    assert state["client_origin"] == "mcp_client_unspecified"
    assert state["microphone_speech"] is False
    assert state["microphone_recognition_claimed"] is False
    assert state["raw_audio"] is False
    assert state["chat_route_writes_conversation_ledger"] is True
    assert state["speech_output_owner"] == "chatgpt_voice_client"
    assert state["local_overlay_speech_started"] is False
    assert "can you hear me" not in json.dumps(state)

    voice_receipt = data_root / "runtime" / "lens-overlay" / "voice-turns" / "chatgpt-mcp-voice-turn.json"
    assert voice_receipt.exists()


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
    assert "voice-turn-memory-2" in body["receipt"]["turn_id"]


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
    assert "francis.chatgpt_voice.receipts" in names
    tool_by_name = {tool["name"]: tool for tool in list_tools()}
    ingress_description = tool_by_name["francis.chatgpt_voice.ingress"]["description"]
    assert "speak only the returned top-level `reply`" in ingress_description
    assert "Transcript Unavailable" in ingress_description
    assert "Do not answer locally" in ingress_description

    contract = run_tool("francis.chatgpt_voice.contract", {"actor": _ACTOR})
    assert contract["ok"] is True
    assert contract["governance"]["read_only"] is True

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
    assert ingress["data"]["receipt"]["client_origin"] == "chatgpt_app_voice"
    assert ingress["data"]["orb_voice_bridge"]["virtual_voice_turn"] is True
    assert ingress["data"]["orb_voice_bridge"]["mcp_ingress"] is True
    assert ingress["data"]["orb_voice_bridge"]["client_origin"] == "chatgpt_app_voice"
    assert ingress["data"]["orb_voice_bridge"]["local_overlay_speech_started"] is False

    receipts = run_tool("francis.chatgpt_voice.receipts", {"actor": _ACTOR, "limit": 5})
    assert receipts["ok"] is True
    assert receipts["data"]["count"] == 1
