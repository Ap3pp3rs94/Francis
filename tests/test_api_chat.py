from __future__ import annotations

import json
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
    operation_id = str(body["operation_id"])
    assert operation_id.startswith("tsk_")
    assert operation_id in body["reply"]
    assert body["advance"]["ok"] is True
    assert body["advance"]["applied"] is True
    assert body["advance"]["action"] == "create_first_operation"
    assert body["advance"]["operation_id"] == operation_id
    assert body["operation"]["id"] == operation_id
    assert body["operation"]["name"] == "plan.create"
    assert body["operation"]["status"] == "queued"
    assert body["mission"]["id"] == mission_id
    assert body["mission"]["objective"] == "Prepare deploy token=[REDACTED:secret]"
    assert body["mission"]["requester_id"] == "chat.send"
    assert body["mission"]["meta"]["source"] == "chat.send"
    assert body["mission"]["meta"]["ingress_plane"] == "P1_INTERFACE"
    assert body["mission"]["linked_task_ids"] == [operation_id]
    assert body["mission"]["meta"]["last_advance_action"] == "create_first_operation"
    assert body["mission"]["meta"]["last_advance_operation_id"] == operation_id
    assert body["mission"]["meta"]["last_advance_operation_name"] == "plan.create"
    assert body["queue_item"]["recommended_action"] == "run_linked_operation"
    assert body["queue_item"]["action_target_id"] == operation_id
    assert body["queue_item"]["advance"]["eligible"] is True
    assert body["queue_item"]["advance"]["action"] == "run_linked_operation"
    assert body["loop_state"]["active_stage"] == "execute"
    assert body["loop_state"]["handoff"]["action"] == "run_linked_operation"
    assert body["loop_state"]["handoff"]["operation_id"] == operation_id
    assert body["loop_state"]["interface"]["status"] == "available"
    assert body["loop_state"]["interface"]["operation_id"] == operation_id
    assert body["current_task"]["source"] == "mission_meta"
    assert body["current_task"]["operation_id"] == operation_id
    assert body["current_task"]["operation_name"] == "plan.create"
    assert body["current_task"]["operation_plane"] == "P7_EXECUTION"
    assert body["current_task"]["advance_action"] == "create_first_operation"
    assert body["current_task"]["handoff_action"] == "run_linked_operation"

    fetched = client.get(f"/missions/{mission_id}")
    assert fetched.status_code == 200
    fetched_body = fetched.json()
    assert fetched_body["mission"]["id"] == mission_id
    assert fetched_body["mission"]["linked_task_ids"] == [operation_id]
    assert fetched_body["loop_state"]["active_stage"] == "execute"
    assert fetched_body["current_task"]["operation_id"] == operation_id

    record_text = (data_root / "missions" / mission_id / "record.json").read_text(encoding="utf-8")
    history_text = (data_root / "missions" / mission_id / "history.jsonl").read_text(encoding="utf-8")
    task_text = (data_root / "tasks" / operation_id / "record.json").read_text(encoding="utf-8")
    ledger_text = (data_root / "conversations" / "ledger" / "ledger.jsonl").read_text(encoding="utf-8")
    assert "chatmissionsecret123" not in record_text
    assert "chatmissionsecret123" not in history_text
    assert "chatmissionsecret123" not in task_text
    assert "chatmissionsecret123" not in ledger_text
    assert "[REDACTED:secret]" in ledger_text
    ledger_entries = [json.loads(line) for line in ledger_text.splitlines()]
    assistant_entry = next(
        item
        for item in reversed(ledger_entries)
        if item["role"] == "assistant" and item["meta"]["mode"] == "mission_ingress"
    )
    assistant_meta = assistant_entry["meta"]
    assert assistant_meta["mission_id"] == mission_id
    assert assistant_meta["ingress_plane"] == "P1_INTERFACE"
    assert assistant_meta["active_stage"] == "execute"
    assert assistant_meta["handoff_stage"] == "execute"
    assert assistant_meta["handoff_action"] == "run_linked_operation"
    assert assistant_meta["handoff_operation_id"] == operation_id
    assert assistant_meta["handoff_next_step"] == body["loop_state"]["handoff"]["next_step"]
    assert assistant_meta["current_task_source"] == "mission_meta"
    assert assistant_meta["current_task_operation_id"] == operation_id
    assert assistant_meta["current_task_operation_name"] == "plan.create"
    assert assistant_meta["current_task_operation_plane"] == "P7_EXECUTION"
    assert assistant_meta["current_task_advance_action"] == "create_first_operation"
    assert assistant_meta["current_task_next_step"] == body["current_task"]["next_step"]
    assert assistant_meta["linked_operation_count"] == 1
    assert assistant_meta["run_ledger_count"] == 1
    assert assistant_meta["memory_receipt_count"] == 0


def test_chat_mission_ingress_compact_meta_preserves_handoff_trace_handles() -> None:
    from francis.api.routes.chat import _compact_mission_ingress_meta
    from francis.missions.store import MissionRecord, MissionStatus

    record = MissionRecord(
        mission_id="msn_trace_handles",
        created_at="2026-04-26T00:00:00+00:00",
        updated_at="2026-04-26T00:00:01+00:00",
        status=MissionStatus.COMPLETED,
        objective="Preserve trace handles",
        requester_id="chat.send",
    )

    meta = _compact_mission_ingress_meta(
        record=record,
        loop_state={
            "active_stage": "interface",
            "handoff": {
                "stage": "interface",
                "action": "review_result",
                "gate": "operator_review",
                "approval_id": "apr_trace_handles",
                "approval_status": "approved",
                "operation_id": "tsk_trace_handles",
                "trace_id": "trace_handles",
                "run_id": "run_handles",
                "artifact_dir": "D:/francis/data/artifacts/trace-handles",
                "next_step": "review_completed_mission",
            },
        },
        current_task={
            "source": "terminal_operation_receipt",
            "approval_id": "apr_trace_handles",
            "approval_status": "approved",
            "previous_approval_id": "apr_previous_trace_handles",
            "previous_approval_status": "approved",
            "operation_id": "tsk_trace_handles",
            "operation_name": "plan.create",
            "operation_plane": "P9_OBSERVABILITY",
            "gate": "operator_review",
            "trace_id": "trace_handles",
            "run_id": "run_handles",
            "artifact_dir": "D:/francis/data/artifacts/trace-handles",
            "advance_action": "run_linked_operation",
            "next_step": "review_completed_mission",
        },
        receipt_summary={
            "linked_operation_count": 1,
            "run_ledger_count": 2,
            "memory_receipt_count": 1,
        },
    )

    assert meta["active_stage"] == "interface"
    assert meta["handoff_approval_status"] == "approved"
    assert meta["handoff_trace_id"] == "trace_handles"
    assert meta["handoff_run_id"] == "run_handles"
    assert meta["handoff_artifact_dir"] == "D:/francis/data/artifacts/trace-handles"
    assert meta["current_task_approval_id"] == "apr_trace_handles"
    assert meta["current_task_approval_status"] == "approved"
    assert meta["current_task_previous_approval_id"] == "apr_previous_trace_handles"
    assert meta["current_task_previous_approval_status"] == "approved"
    assert meta["current_task_operation_id"] == "tsk_trace_handles"
    assert meta["current_task_operation_name"] == "plan.create"
    assert meta["current_task_operation_plane"] == "P9_OBSERVABILITY"
    assert meta["current_task_trace_id"] == "trace_handles"
    assert meta["current_task_run_id"] == "run_handles"
    assert meta["current_task_artifact_dir"] == "D:/francis/data/artifacts/trace-handles"
    assert meta["current_task_advance_action"] == "run_linked_operation"
    assert meta["memory_receipt_count"] == 1


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
    assert body["governance"]["gate"] == "operator_posture"
    assert body["governance"]["reason"] == "observe_mode"
    assert body["governance"]["next_step"] == "switch_operator_posture_before_declaring_chat_missions"

    ledger_text = (data_root / "conversations" / "ledger" / "ledger.jsonl").read_text(encoding="utf-8")
    ledger_entries = [json.loads(line) for line in ledger_text.splitlines()]
    assistant_entry = next(
        item
        for item in reversed(ledger_entries)
        if item["role"] == "assistant" and item["meta"]["mode"] == "mission_ingress"
    )
    assistant_meta = assistant_entry["meta"]
    assert assistant_meta["status"] == "blocked"
    assert assistant_meta["error"] == body["error"]
    assert assistant_meta["ingress_plane"] == "P1_INTERFACE"
    assert assistant_meta["active_stage"] == "gate"
    assert assistant_meta["handoff_stage"] == "gate"
    assert assistant_meta["handoff_action"] == "switch_operator_posture"
    assert assistant_meta["handoff_gate"] == "operator_posture"
    assert assistant_meta["handoff_next_step"] == "switch_operator_posture_before_declaring_chat_missions"
    assert assistant_meta["governance_gate"] == "operator_posture"
    assert assistant_meta["governance_reason"] == "observe_mode"
    assert assistant_meta["governance_next_step"] == "switch_operator_posture_before_declaring_chat_missions"

    mission_root = data_root / "missions"
    assert not mission_root.exists() or not any(mission_root.iterdir())


def test_chat_mission_command_denies_unscoped_actor_before_mutation(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", "{}")

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    sent = client.post(
        "/chat/send",
        json={"message": "/mission Permission gate should stop this before mission state", "use_llm": True},
    )
    assert sent.status_code == 200
    body = sent.json()

    assert body["ok"] is False
    assert body["mode"] == "mission_ingress"
    assert body["status"] == "denied"
    assert body["error"] == "api_permission_denied"
    assert body["reply"] == "Mission declaration denied by permission gate."
    assert body["governance"]["gate"] == "permission_gate"
    assert body["governance"]["reason"] == "missing_scopes"
    assert body["governance"]["next_step"] == "configure_actor_scope_before_declaring_chat_missions"
    assert body["governance"]["evidence"]["actor_present"] is True
    assert body["governance"]["evidence"]["required_scope_count"] == 1

    ledger_text = (data_root / "conversations" / "ledger" / "ledger.jsonl").read_text(encoding="utf-8")
    ledger_entries = [json.loads(line) for line in ledger_text.splitlines()]
    assistant_entry = next(
        item
        for item in reversed(ledger_entries)
        if item["role"] == "assistant" and item["meta"]["mode"] == "mission_ingress"
    )
    assistant_meta = assistant_entry["meta"]
    assert assistant_meta["status"] == "denied"
    assert assistant_meta["error"] == "api_permission_denied"
    assert assistant_meta["ingress_plane"] == "P1_INTERFACE"
    assert assistant_meta["active_stage"] == "gate"
    assert assistant_meta["handoff_stage"] == "gate"
    assert assistant_meta["handoff_action"] == "configure_actor_scope"
    assert assistant_meta["handoff_gate"] == "permission_gate"
    assert assistant_meta["handoff_next_step"] == "configure_actor_scope_before_declaring_chat_missions"
    assert assistant_meta["governance_gate"] == "permission_gate"
    assert assistant_meta["governance_reason"] == "missing_scopes"
    assert assistant_meta["governance_next_step"] == "configure_actor_scope_before_declaring_chat_missions"
    assert assistant_meta["governance_evidence"]["actor_present"] is True
    assert assistant_meta["governance_evidence"]["required_scope_count"] == 1

    mission_root = data_root / "missions"
    task_root = data_root / "tasks"
    assert not mission_root.exists() or not any(mission_root.iterdir())
    assert not task_root.exists() or not any(task_root.iterdir())


def test_chat_websocket_structured_message_declares_mission(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())
    with client.websocket_connect("/chat/ws") as websocket:
        websocket.send_text(
            json.dumps(
                {
                    "type": "message",
                    "message": {
                        "role": "user",
                        "content": "mission: Preserve websocket mission token=chatwssecret123",
                        "ts": 1777160000,
                    },
                }
            )
        )
        event = json.loads(websocket.receive_text())

    assert event["type"] == "message"
    assert event["message"]["role"] == "assistant"
    assert "Mission " in event["message"]["content"]
    meta = event["message"]["meta"]
    mission_id = str(meta["mission_id"])
    assert meta["ok"] is True
    assert meta["mode"] == "mission_ingress"
    assert meta["status"] == "queued"
    assert meta["mission"]["id"] == mission_id
    assert meta["mission"]["objective"] == "Preserve websocket mission token=[REDACTED:secret]"
    operation_id = str(meta["operation_id"])
    assert operation_id.startswith("tsk_")
    assert meta["advance"]["action"] == "create_first_operation"
    assert meta["advance"]["operation_id"] == operation_id
    assert meta["operation"]["id"] == operation_id
    assert meta["queue_item"]["recommended_action"] == "run_linked_operation"
    assert meta["queue_item"]["action_target_id"] == operation_id
    assert meta["loop_state"]["active_stage"] == "execute"
    assert meta["loop_state"]["handoff"]["operation_id"] == operation_id
    assert meta["loop_state"]["interface"]["status"] == "available"
    assert meta["loop_state"]["interface"]["operation_id"] == operation_id
    assert meta["current_task"]["operation_id"] == operation_id
    assert meta["current_task"]["handoff_action"] == "run_linked_operation"

    record_text = (data_root / "missions" / mission_id / "record.json").read_text(encoding="utf-8")
    task_text = (data_root / "tasks" / operation_id / "record.json").read_text(encoding="utf-8")
    ledger_text = (data_root / "conversations" / "ledger" / "ledger.jsonl").read_text(encoding="utf-8")
    assert "chatwssecret123" not in record_text
    assert "chatwssecret123" not in task_text
    assert "chatwssecret123" not in ledger_text
