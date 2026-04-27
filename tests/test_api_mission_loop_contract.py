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
    assert memory_receipt["current_task_operation_name"] == "plan.create"
    assert memory_receipt["current_task_operation_plane"] == "P9_OBSERVABILITY"
    assert memory_receipt["current_task_advance_action"] == "run_linked_operation"
    expected_plan_receipt = {
        "plan_status": "in_progress",
        "plan_current_step_id": "understand",
        "plan_current_step_title": "Understand goal + constraints",
        "plan_step_count": 4,
        "plan_checkpoint_count": 3,
    }
    for key, value in expected_plan_receipt.items():
        assert memory_receipt[key] == value

    fetched = client.get(f"/missions/{mission_id}")
    assert fetched.status_code == 200
    fetched_body = fetched.json()
    assert fetched_body["mission"]["status"] == "completed"
    assert fetched_body["loop_state"]["active_stage"] == "interface"
    assert fetched_body["loop_state"]["handoff"]["stage"] == "interface"
    assert fetched_body["loop_state"]["handoff"]["action"] == "review_result"
    assert fetched_body["loop_state"]["handoff"]["operation_id"] == operation_id
    assert fetched_body["loop_state"]["handoff"]["next_step"] == "review_completed_mission"
    assert fetched_body["loop_state"]["memory"]["memory_receipt_count"] == 1
    assert fetched_body["loop_state"]["interface"]["status"] == "available"
    assert fetched_body["loop_state"]["interface"]["operation_id"] == operation_id
    assert fetched_body["receipt_summary"]["memory_receipt_count"] == 1
    assert fetched_body["latest_memory_receipt"]["operation_id"] == operation_id
    assert fetched_body["latest_memory_receipt"]["current_task_operation_name"] == "plan.create"
    assert fetched_body["latest_memory_receipt"]["current_task_operation_plane"] == "P9_OBSERVABILITY"
    assert fetched_body["latest_memory_receipt"]["current_task_advance_action"] == "run_linked_operation"
    for key, value in expected_plan_receipt.items():
        assert fetched_body["current_task"][key] == value
        assert fetched_body["loop_state"]["interface"][key] == value
        assert fetched_body["latest_memory_receipt"][key] == value

    operation_detail = client.get(f"/operations/{operation_id}")
    assert operation_detail.status_code == 200
    operation_body = operation_detail.json()
    assert operation_body["latest_memory_receipt"]["operation_id"] == operation_id
    for key, value in expected_plan_receipt.items():
        assert operation_body["latest_memory_receipt"][key] == value
        assert operation_body["operation"]["meta"]["latest_memory_receipt"][key] == value

    operation_many = client.post("/operations/get_many", json={"ids": [operation_id]})
    assert operation_many.status_code == 200
    operation_many_item = operation_many.json()["items"][0]
    assert operation_many_item["latest_memory_receipt"]["operation_id"] == operation_id
    for key, value in expected_plan_receipt.items():
        assert operation_many_item["latest_memory_receipt"][key] == value

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
    assert ingress_receipt["loop"]["current_task_operation_id"] == operation_id
    assert ingress_receipt["loop"]["current_task_operation_name"] == "plan.create"
    assert ingress_receipt["loop"]["current_task_operation_plane"] == "P7_EXECUTION"
    assert ingress_receipt["loop"]["current_task_advance_action"] == "create_first_operation"
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
    assert terminal_receipt["loop"]["active_stage"] == "interface"
    assert terminal_receipt["loop"]["handoff_stage"] == "interface"
    assert terminal_receipt["loop"]["handoff_action"] == "review_result"
    assert terminal_receipt["loop"]["handoff_operation_id"] == operation_id
    assert terminal_receipt["loop"]["handoff_trace_id"] == trace_id
    assert terminal_receipt["loop"]["handoff_run_id"] == run_id
    assert terminal_receipt["loop"]["handoff_next_step"] == "review_completed_mission"
    assert terminal_receipt["loop"]["current_task_source"] == "terminal_operation_receipt"
    assert terminal_receipt["loop"]["current_task_operation_id"] == operation_id
    assert terminal_receipt["loop"]["current_task_operation_name"] == "plan.create"
    assert terminal_receipt["loop"]["current_task_operation_plane"] == "P9_OBSERVABILITY"
    assert terminal_receipt["loop"]["current_task_advance_action"] == "run_linked_operation"
    assert terminal_receipt["loop"]["current_task_run_id"] == run_id
    assert terminal_receipt["loop"]["current_task_next_step"] == "review_completed_mission"
    assert terminal_receipt["loop"]["run_id"] == run_id
    assert terminal_receipt["loop"]["memory_receipt_count"] == 1
    for key, value in expected_plan_receipt.items():
        assert terminal_receipt["loop"][key] == value
    assert terminal_receipt["payload"]["meta"]["subsystem"] == "operations.runtime"
    assert terminal_receipt["payload"]["meta"]["operation_status"] == "succeeded"

    timeline_text = json.dumps(timeline_body, sort_keys=True)
    assert secret_token not in timeline_text


def test_mission_loop_gate_handoff_preserves_trace_handle(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    mission = client.post(
        "/missions/create",
        json={
            "objective": "Keep gated mission trace handles visible",
            "summary": "The gate stage must not drop known trace handles.",
            "requester_id": "test.missions.advance",
        },
    )
    assert mission.status_code == 200
    mission_id = str(mission.json()["mission_id"])

    installed = client.post(
        "/plugins/install",
        json={
            "source_kind": "registry",
            "source_ref": "acme/gated-trace",
            "actor": "test.plugins.write",
            "capabilities": [
                {
                    "id": "acme.gated_trace",
                    "kind": "tool",
                    "name": "deploy",
                    "action": "deploy",
                    "description": "Critical gated deployment action.",
                    "meta": {"risk_tier": "critical", "required_trust": 5},
                }
            ],
        },
    )
    assert installed.status_code == 200
    plugin_id = str(installed.json()["plugin_id"])

    seed_trace_id = "trace_mission_gate_meta"
    seed_run_id = "run_mission_gate_meta"
    artifact_dir = str(data_root / "artifacts" / "mission_gate_meta")
    created = client.post(
        "/operations/create",
        json={
            "action": "plugin.run",
            "reason": "gated operation with existing trace handle",
            "mission_id": mission_id,
            "input": {"id": plugin_id, "action": "deploy", "input": {"target": "prod"}},
            "meta": {"trace_id": seed_trace_id, "run_id": seed_run_id, "artifact_dir": artifact_dir},
        },
    )
    assert created.status_code == 200
    operation_id = str(created.json()["operation_id"])

    blocked = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.missions.advance"})
    assert blocked.status_code == 200
    blocked_body = blocked.json()
    assert blocked_body["status"] == "blocked"
    operation = blocked_body["operation"]
    trace_id = str(operation["trace_id"])
    run_id = str(operation["run_id"])
    artifact_dir = str(operation["artifact_dir"])
    assert trace_id.startswith("trace_")
    assert run_id.startswith("run_")

    fetched = client.get(f"/missions/{mission_id}")
    assert fetched.status_code == 200
    body = fetched.json()

    assert body["loop_state"]["active_stage"] == "gate"
    assert body["current_task"]["trace_id"] == trace_id
    assert body["current_task"]["run_id"] == run_id
    assert body["current_task"]["artifact_dir"] == artifact_dir
    assert body["loop_state"]["handoff"]["trace_id"] == trace_id
    assert body["loop_state"]["handoff"]["run_id"] == run_id
    assert body["loop_state"]["handoff"]["artifact_dir"] == artifact_dir
    assert body["loop_state"]["gate"]["trace_id"] == trace_id
    assert body["loop_state"]["gate"]["run_id"] == run_id
    assert body["loop_state"]["gate"]["artifact_dir"] == artifact_dir
    assert body["loop_state"]["execute"]["trace_id"] == trace_id
    assert body["loop_state"]["execute"]["run_id"] == run_id
    assert body["loop_state"]["execute"]["artifact_dir"] == artifact_dir
