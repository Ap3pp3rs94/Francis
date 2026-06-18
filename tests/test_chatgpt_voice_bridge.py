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
    assert body["input_contract"]["audio_stream_accepted"] is False
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
    assert body["chat_forward"]["requested"] is False
    assert body["receipt"]["transcript"] == "Francis can you hear me"
    assert body["receipt"]["turn_id"] == "voice-turn-1"
    assert Path(body["receipt"]["receipt_path"]).exists()
    assert body["governance"]["writes_receipt"] is True
    assert body["governance"]["forwards_to_chat"] is False
    assert body["governance"]["raw_audio"] is False
    assert body["governance"]["grants_execution_authority"] is False
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
    assert body["chat_forward"]["requested"] is True
    assert body["chat_forward"]["forwarded"] is False
    assert body["chat_forward"]["error"] == "api_permission_denied"
    assert body["receipt"]["chat_forward_status"] == "denied"
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
    assert body["chat_forward"]["forwarded"] is True
    assert body["chat_forward"]["response"]["reply"] == "I can hear you. Voice input is reaching Francis."
    assert body["receipt"]["chat_forward_status"] == "forwarded"
    assert body["receipt"]["chat_response_status"] == ""
    assert body["governance"]["calls_model"] is False
    assert body["governance"]["grants_execution_authority"] is False

    ledger = data_root / "conversations" / "ledger" / "ledger.jsonl"
    assert ledger.exists()
    ledger_text = ledger.read_text(encoding="utf-8")
    assert "can you hear me" in ledger_text
    assert "voice-turn-forwarded" in ledger_text


def test_chatgpt_voice_mcp_tools_expose_bounded_bridge(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", _scopes("chatgpt.voice.bridge.read", "chatgpt.voice.bridge.write"))

    names = {tool["name"] for tool in list_tools()}
    assert "francis.chatgpt_voice.contract" in names
    assert "francis.chatgpt_voice.ingress" in names
    assert "francis.chatgpt_voice.receipts" in names

    contract = run_tool("francis.chatgpt_voice.contract", {"actor": _ACTOR})
    assert contract["ok"] is True
    assert contract["governance"]["read_only"] is True

    ingress = run_tool(
        "francis.chatgpt_voice.ingress",
        {"actor": _ACTOR, "transcript": "hello Francis", "forward_to_chat": False},
    )
    assert ingress["ok"] is True
    assert ingress["status"] == "recorded"
    assert ingress["governance"]["raw_shell"] is False
    assert ingress["governance"]["raw_audio"] is False

    receipts = run_tool("francis.chatgpt_voice.receipts", {"actor": _ACTOR, "limit": 5})
    assert receipts["ok"] is True
    assert receipts["data"]["count"] == 1
