from __future__ import annotations

import json
from pathlib import Path


def test_chat_ingress_advances_to_terminal_memory_receipt(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    secret_token = "missionloopsecret123"
    declared = client.post(
        "/chat/send",
        json={
            "message": f"/mission Prove mission loop memory contract token={secret_token}",
            "use_llm": False,
        },
    )
    assert declared.status_code == 200
    declared_body = declared.json()
    assert declared_body["ok"] is True
    assert declared_body["mode"] == "mission_ingress"
    mission_id = str(declared_body["mission_id"])
    operation_id = str(declared_body["operation_id"])

    ingress_loop = declared_body["loop_state"]
    assert ingress_loop["active_stage"] == "execute"
    assert ingress_loop["handoff"]["action"] == "run_linked_operation"
    assert ingress_loop["handoff"]["operation_id"] == operation_id
    assert declared_body["current_task"]["operation_id"] == operation_id
    assert declared_body["receipt_summary"]["memory_receipt_count"] == 0

    advanced = client.post(
        f"/missions/{mission_id}/advance",
        json={"actor": "test.missions.advance", "worker_id": "test.missions.advance"},
    )
    assert advanced.status_code == 200
    advanced_body = advanced.json()
    assert advanced_body["ok"] is True
    assert advanced_body["applied"] is True
    assert advanced_body["action"] == "run_linked_operation"
    assert advanced_body["status"] == "succeeded"
    assert advanced_body["operation_id"] == operation_id
    trace_id = str(advanced_body["trace_id"])
    run_id = str(advanced_body["run_id"])
    assert trace_id.startswith("trace_")
    assert run_id.startswith("run_")
    memory_receipt = advanced_body["memory_receipt"]
    assert memory_receipt["source"] == "continuity.ledger"
    assert memory_receipt["references"]["mission_id"] == mission_id
    assert memory_receipt["references"]["operation_id"] == operation_id
    assert memory_receipt["references"]["trace_id"] == trace_id
    assert memory_receipt["references"]["run_id"] == run_id

    fetched = client.get(f"/missions/{mission_id}")
    assert fetched.status_code == 200
    fetched_body = fetched.json()
    assert fetched_body["mission"]["status"] == "completed"
    assert fetched_body["loop_state"]["active_stage"] == "memory"
    assert fetched_body["loop_state"]["memory"]["memory_receipt_count"] == 1
    assert fetched_body["receipt_summary"]["memory_receipt_count"] == 1
    assert fetched_body["latest_memory_receipt"]["operation_id"] == operation_id

    listed = client.get(
        "/memory/timeline/list",
        params={"mission_id": mission_id, "include_payload": "1"},
    )
    assert listed.status_code == 200
    timeline_body = listed.json()
    assert timeline_body["total"] == 2
    items = timeline_body["items"]

    ingress_items = [
        item
        for item in items
        if item.get("loop", {}).get("ingress_plane") == "P1_INTERFACE"
        and item.get("loop", {}).get("handoff_operation_id") == operation_id
    ]
    assert len(ingress_items) == 1
    ingress_receipt = ingress_items[0]
    assert ingress_receipt["kind"] == "ledger_append"
    assert ingress_receipt["provenance"]["source"] == "continuity.ledger"
    assert ingress_receipt["references"]["mission_id"] == mission_id
    assert ingress_receipt["loop"]["active_stage"] == "execute"
    assert ingress_receipt["loop"]["handoff_action"] == "run_linked_operation"
    assert ingress_receipt["loop"]["linked_operation_count"] == 1
    assert ingress_receipt["loop"]["memory_receipt_count"] == 0

    terminal_items = [
        item
        for item in items
        if item.get("operation_status") == "succeeded"
        and item.get("references", {}).get("trace_id") == trace_id
        and item.get("references", {}).get("run_id") == run_id
    ]
    assert len(terminal_items) == 1
    terminal_receipt = terminal_items[0]
    assert terminal_receipt["kind"] == "ledger_append"
    assert "Mission operation completed" in terminal_receipt["message"]
    assert terminal_receipt["provenance"]["source"] == "continuity.ledger"
    assert terminal_receipt["provenance"]["domain"] == "operations"
    assert terminal_receipt["provenance"]["scope"] == "mission.loop"
    assert terminal_receipt["references"]["mission_id"] == mission_id
    assert terminal_receipt["references"]["operation_id"] == operation_id
    assert terminal_receipt["loop"]["run_id"] == run_id
    assert terminal_receipt["loop"]["plan_status"] == "in_progress"
    assert terminal_receipt["loop"]["plan_current_step_id"] == "understand"
    assert terminal_receipt["loop"]["plan_step_count"] == 4
    assert terminal_receipt["loop"]["plan_checkpoint_count"] == 3
    assert terminal_receipt["payload"]["meta"]["subsystem"] == "operations.runtime"
    assert terminal_receipt["payload"]["meta"]["operation_status"] == "succeeded"

    timeline_text = json.dumps(timeline_body, sort_keys=True)
    assert secret_token not in timeline_text
