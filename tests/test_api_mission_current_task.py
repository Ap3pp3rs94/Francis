from __future__ import annotations

from pathlib import Path


def test_mission_current_task_preserves_previous_approval_lineage(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app
    from francis.missions.store import MissionCreateRequest, MissionStatus, create_mission

    operation_id = "tsk_current_task_previous_approval"
    mission, err = create_mission(
        MissionCreateRequest(
            objective="Surface previous approval lineage in current task readback",
            summary="Current-task readbacks should keep approval replacement lineage visible.",
            requester_id="test.missions.current_task",
            status=MissionStatus.BLOCKED,
            linked_task_ids=[operation_id],
            meta={
                "last_task_id": operation_id,
                "last_task_status": "accepted",
                "last_task_result_status": "needs_approval",
                "last_task_gate": "approvals_gate",
                "last_task_next_step": "review_pending_approval",
                "last_task_approval_id": "apr_current_lineage",
                "last_task_previous_approval_id": "apr_previous_lineage",
                "last_task_previous_approval_status": "missing",
                "last_task_approval_status": "pending",
            },
        )
    )
    assert err is None
    assert mission is not None

    client = TestClient(create_app())

    fetched = client.get(f"/missions/{mission.mission_id}")
    assert fetched.status_code == 200
    fetched_body = fetched.json()
    assert fetched_body["current_task"]["approval_id"] == "apr_current_lineage"
    assert fetched_body["current_task"]["approval_status"] == "pending"
    assert fetched_body["current_task"]["previous_approval_id"] == "apr_previous_lineage"
    assert fetched_body["current_task"]["previous_approval_status"] == "missing"

    queued = client.get("/missions/queue")
    assert queued.status_code == 200
    queue_item = next(item for item in queued.json()["items"] if item["id"] == mission.mission_id)
    assert queue_item["current_task"]["previous_approval_id"] == "apr_previous_lineage"
    assert queue_item["current_task"]["previous_approval_status"] == "missing"
