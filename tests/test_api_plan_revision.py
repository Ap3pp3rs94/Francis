from __future__ import annotations

import csv
import io


def test_plan_revise_result_carries_bounded_plan_summary(monkeypatch, tmp_path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    created_plan = client.post(
        "/operations/create",
        json={
            "action": "plan.create",
            "reason": "seed revision plan",
            "input": {"goal": "produce a plan that can be revised"},
        },
    )
    assert created_plan.status_code == 200
    plan_operation_id = str(created_plan.json()["operation_id"])

    plan_run = client.post(f"/operations/{plan_operation_id}/run", json={"worker_id": "test.plan_revision"})
    assert plan_run.status_code == 200
    plan_output = plan_run.json()["operation"]["output"]
    assert plan_output["kind"] == "plan.create.result"
    assert plan_output["plan_status"] == "in_progress"

    revised_plan = client.post(
        "/operations/create",
        json={
            "action": "plan.revise",
            "reason": "bounded revision summary",
            "input": {
                "plan": plan_output["plan"],
                "reason": "verification failed",
            },
        },
    )
    assert revised_plan.status_code == 200
    revision_operation_id = str(revised_plan.json()["operation_id"])

    revision_run = client.post(f"/operations/{revision_operation_id}/run", json={"worker_id": "test.plan_revision"})
    assert revision_run.status_code == 200
    revision_body = revision_run.json()
    assert revision_body["status"] == "succeeded"
    output = revision_body["operation"]["output"]
    assert output["kind"] == "plan.revise.result"
    assert output["ok"] is True
    assert output["plan_status"] == "revised"
    assert output["plan_current_step_id"] == "understand"
    assert output["plan_current_step_title"] == "Understand goal + constraints"
    assert output["plan_step_count"] == 7
    assert output["plan_checkpoint_count"] == 3
    assert output["plan"]["status"] == "revised"
    assert len(output["plan"]["revisions"]) == 1
    assert str(output.get("trace_id") or "").startswith("trace_")
    assert str(output.get("run_id") or "").startswith("run_")

    fetched = client.get(f"/operations/{revision_operation_id}")
    assert fetched.status_code == 200
    fetched_output = fetched.json()["operation"]["output"]
    assert fetched_output["plan_status"] == "revised"
    assert fetched_output["plan_step_count"] == 7

    exported = client.get("/operations/export", params={"format": "csv", "run_id": output["run_id"]})
    assert exported.status_code == 200
    rows = list(csv.DictReader(io.StringIO(exported.text)))
    assert len(rows) == 1
    assert rows[0]["id"] == revision_operation_id
    assert rows[0]["plan_status"] == "revised"
    assert rows[0]["plan_current_step_id"] == "understand"
    assert rows[0]["plan_current_step_title"] == "Understand goal + constraints"
    assert rows[0]["plan_step_count"] == "7"
    assert rows[0]["plan_checkpoint_count"] == "3"
