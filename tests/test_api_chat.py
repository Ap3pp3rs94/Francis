from __future__ import annotations

from pathlib import Path


def test_chat_mission_command_declares_queued_mission_with_loop_context(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    sent = client.post(
        "/chat/send",
        json={"message": "/mission Prepare deploy token=chatmissionsecret123", "use_llm": True},
    )
    assert sent.status_code == 200
    body = sent.json()
    mission_id = str(body["mission_id"])

    assert body["ok"] is True
    assert body["mode"] == "mission_ingress"
    assert body["status"] == "queued"
    assert mission_id.startswith("msn_")
    assert mission_id in body["reply"]
    assert body["mission"]["id"] == mission_id
    assert body["mission"]["objective"] == "Prepare deploy token=[REDACTED:secret]"
    assert body["mission"]["requester_id"] == "chat.send"
    assert body["mission"]["meta"]["source"] == "chat.send"
    assert body["mission"]["meta"]["ingress_plane"] == "P1_INTERFACE"
    assert body["queue_item"]["recommended_action"] == "create_first_operation"
    assert body["loop_state"]["active_stage"] == "plan"
    assert body["loop_state"]["handoff"]["action"] == "link_operation"
    assert body["loop_state"]["interface"]["status"] == "available"
    assert body["current_task"]["source"] == "mission_handoff"
    assert body["current_task"]["handoff_action"] == "link_operation"

    fetched = client.get(f"/missions/{mission_id}")
    assert fetched.status_code == 200
    fetched_body = fetched.json()
    assert fetched_body["mission"]["id"] == mission_id
    assert fetched_body["loop_state"]["active_stage"] == "plan"

    record_text = (data_root / "missions" / mission_id / "record.json").read_text(encoding="utf-8")
    history_text = (data_root / "missions" / mission_id / "history.jsonl").read_text(encoding="utf-8")
    ledger_text = (data_root / "conversations" / "ledger" / "ledger.jsonl").read_text(encoding="utf-8")
    assert "chatmissionsecret123" not in record_text
    assert "chatmissionsecret123" not in history_text
    assert "chatmissionsecret123" not in ledger_text
    assert "[REDACTED:secret]" in ledger_text


def test_chat_mission_command_respects_observe_mode(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app
    from francis.world_state.operator_mode import set_control_mode

    client = TestClient(create_app())
    set_control_mode("observe", reason="test_chat_mission_observe", actor="tests")

    sent = client.post(
        "/chat/send",
        json={"message": "/mission This should stay read-only", "use_llm": True},
    )
    assert sent.status_code == 200
    body = sent.json()

    assert body["ok"] is False
    assert body["mode"] == "mission_ingress"
    assert body["status"] == "blocked"
    assert "Observe mode keeps Francis read-only." in body["error"]
    assert "Mission declaration blocked:" in body["reply"]

    mission_root = data_root / "missions"
    assert not mission_root.exists() or not any(mission_root.iterdir())
