from __future__ import annotations

from pathlib import Path


def test_missions_create_list_get_update(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    created = client.post(
        "/missions/create",
        json={
            "objective": "Carry Stage 3 continuity work",
            "summary": "Mission declared for the first real Stage 3 slice.",
            "next_step": "Link an operation and advance the mission state.",
            "requester_id": "test.missions",
            "risk_tier": "high",
        },
    )
    assert created.status_code == 200
    created_body = created.json()
    assert created_body["ok"] is True
    mission_id = str(created_body["mission_id"])

    listed = client.get("/missions/list")
    assert listed.status_code == 200
    listed_body = listed.json()
    assert any(str(item.get("id")) == mission_id for item in listed_body["items"])

    operation = client.post(
        "/operations/create",
        json={
            "action": "plan.create",
            "reason": "mission linkage test",
            "input": {"goal": "Create a linked run-ledger entry"},
        },
    )
    assert operation.status_code == 200
    operation_body = operation.json()
    assert operation_body["ok"] is True
    operation_id = str(operation_body["operation_id"])

    patched = client.patch(
        f"/missions/{mission_id}",
        json={
            "status": "active",
            "next_step": "Review the linked operation and capture follow-up work.",
            "add_task_ids": [operation_id],
            "actor": "test.missions",
            "note": "Mission picked up for execution.",
            "meta": {"source": "integration_test"},
        },
    )
    assert patched.status_code == 200
    patched_body = patched.json()
    assert patched_body["ok"] is True
    assert patched_body["mission"]["status"] == "active"
    assert patched_body["mission"]["linked_task_ids"] == [operation_id]
    assert patched_body["mission"]["linked_task_count"] == 1
    assert patched_body["mission"]["meta"]["source"] == "integration_test"
    history_events = [str(item.get("event")) for item in patched_body["history"]]
    assert "status_changed" in history_events
    assert "task_links_updated" in history_events
    assert "continuity_updated" in history_events

    deadlettered = client.patch(
        f"/missions/{mission_id}",
        json={
            "status": "deadlettered",
            "deadletter_reason": "approval_timeout",
            "actor": "test.missions",
            "note": "Operator did not clear the required gate in time.",
        },
    )
    assert deadlettered.status_code == 200
    deadlettered_body = deadlettered.json()
    assert deadlettered_body["ok"] is True
    assert deadlettered_body["mission"]["status"] == "deadlettered"
    assert deadlettered_body["mission"]["deadletter_reason"] == "approval_timeout"

    fetched = client.get(f"/missions/{mission_id}")
    assert fetched.status_code == 200
    fetched_body = fetched.json()
    assert fetched_body["ok"] is True
    assert fetched_body["mission"]["id"] == mission_id
    assert fetched_body["mission"]["linked_task_ids"] == [operation_id]
    assert fetched_body["mission"]["deadletter_reason"] == "approval_timeout"
    fetched_events = [str(item.get("event")) for item in fetched_body["history"]]
    assert fetched_events.count("status_changed") >= 2


def test_mission_linked_operation_run_updates_history_and_status(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    mission = client.post(
        "/missions/create",
        json={
            "objective": "Carry a linked operation to completion",
            "summary": "Mission should reflect the linked run lifecycle.",
            "next_step": "Queue the first linked operation.",
            "requester_id": "test.missions.linked",
        },
    )
    assert mission.status_code == 200
    mission_id = str(mission.json()["mission_id"])

    created = client.post(
        "/operations/create",
        json={
            "action": "plan.create",
            "reason": "mission linked operation",
            "mission_id": mission_id,
            "input": {"goal": "Create a linked plan"},
        },
    )
    assert created.status_code == 200
    created_body = created.json()
    assert created_body["ok"] is True
    assert created_body["mission_id"] == mission_id
    assert created_body["mission_linked"] is True
    assert created_body["operation"]["meta"]["mission_id"] == mission_id
    operation_id = str(created_body["operation_id"])

    queued_mission = client.get(f"/missions/{mission_id}")
    assert queued_mission.status_code == 200
    queued_body = queued_mission.json()
    assert queued_body["mission"]["linked_task_ids"] == [operation_id]
    assert queued_body["mission"]["status"] == "queued"

    executed = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.missions.linked"})
    assert executed.status_code == 200
    executed_body = executed.json()
    assert executed_body["ok"] is True
    assert executed_body["status"] == "succeeded"

    fetched = client.get(f"/missions/{mission_id}")
    assert fetched.status_code == 200
    fetched_body = fetched.json()
    assert fetched_body["ok"] is True
    assert fetched_body["mission"]["status"] == "completed"
    assert fetched_body["mission"]["meta"]["last_task_id"] == operation_id
    assert fetched_body["mission"]["meta"]["last_task_status"] == "completed"
    history_events = [str(item.get("event")) for item in fetched_body["history"]]
    assert "linked_task_transition" in history_events
    transition_events = [item for item in fetched_body["history"] if item.get("event") == "linked_task_transition"]
    assert any(item.get("details", {}).get("task_status") == "running" for item in transition_events)
    assert any(item.get("details", {}).get("task_status") == "completed" for item in transition_events)


def test_mission_linked_governance_hold_updates_blocked_state(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    mission = client.post(
        "/missions/create",
        json={
            "objective": "Carry governed deploy continuity",
            "summary": "Mission should surface governance holds from linked operations.",
            "requester_id": "test.missions.governance",
        },
    )
    assert mission.status_code == 200
    mission_id = str(mission.json()["mission_id"])

    installed = client.post(
        "/plugins/install",
        json={
            "source_kind": "registry",
            "source_ref": "acme/risky",
            "capabilities": [
                {
                    "id": "acme.deploy",
                    "kind": "tool",
                    "name": "deploy",
                    "action": "deploy",
                    "description": "Critical deployment action.",
                    "meta": {"risk_tier": "critical", "required_trust": 5},
                }
            ],
        },
    )
    assert installed.status_code == 200
    plugin_id = str(installed.json()["plugin_id"])

    created = client.post(
        "/operations/create",
        json={
            "action": "plugin.run",
            "reason": "governed deploy",
            "mission_id": mission_id,
            "input": {"id": plugin_id, "action": "deploy", "input": {"target": "prod"}},
        },
    )
    assert created.status_code == 200
    created_body = created.json()
    assert created_body["ok"] is True
    operation_id = str(created_body["operation_id"])

    blocked = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.missions.governance"})
    assert blocked.status_code == 200
    blocked_body = blocked.json()
    assert blocked_body["ok"] is True
    assert blocked_body["status"] == "blocked"

    fetched = client.get(f"/missions/{mission_id}")
    assert fetched.status_code == 200
    fetched_body = fetched.json()
    assert fetched_body["ok"] is True
    assert fetched_body["mission"]["status"] == "blocked"
    assert fetched_body["mission"]["meta"]["last_task_id"] == operation_id
    assert fetched_body["mission"]["meta"]["last_task_status"] == "accepted"
    assert fetched_body["mission"]["meta"]["last_task_result_status"] == "blocked"
    assert fetched_body["mission"]["meta"]["last_task_gate"] == "trust_gate"
    assert fetched_body["mission"]["meta"]["last_task_next_step"] == "raise_trust_or_reduce_risk"
    transition_events = [item for item in fetched_body["history"] if item.get("event") == "linked_task_transition"]
    assert transition_events
    assert transition_events[-1]["details"]["gate"] == "trust_gate"
    assert transition_events[-1]["details"]["mission_status_after"] == "blocked"
