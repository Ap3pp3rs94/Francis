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
