from __future__ import annotations

import csv
import io
import json
import subprocess
from pathlib import Path


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )


def test_operations_create_list_get_cancel(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    created = client.post(
        "/operations/create",
        json={
            "action": "plan.create",
            "reason": "api_operations_test",
            "input": {"goal": "verify operations API"},
        },
    )
    assert created.status_code == 200
    created_body = created.json()
    assert created_body["ok"] is True
    operation_id = str(created_body["operation_id"])

    listed = client.get("/operations/list")
    assert listed.status_code == 200
    listed_body = listed.json()
    assert isinstance(listed_body.get("items"), list)
    assert any(str(item.get("id")) == operation_id for item in listed_body["items"])

    fetched = client.get(f"/operations/{operation_id}")
    assert fetched.status_code == 200
    fetched_body = fetched.json()
    assert str(fetched_body["operation"]["id"]) == operation_id

    cancelled = client.post(f"/operations/{operation_id}/cancel", json={"reason": "test_cancel"})
    assert cancelled.status_code == 200
    cancelled_body = cancelled.json()
    assert "status" in cancelled_body
    assert cancelled_body["status"] in {"queued", "running", "failed", "canceled", "succeeded", "unknown"}


def test_operations_operator_surfaces_redact_secret_text(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    created = client.post(
        "/operations/create",
        json={
            "action": "plan.create",
            "reason": "operator reason password=operationreasonsecret123",
            "input": {"goal": "draft plan token=operationinputsecret123"},
            "meta": {"ticket": "OPS-1", "operator_note": "secret=operationmetasecret123"},
        },
    )
    assert created.status_code == 200
    created_body = created.json()
    assert created_body["ok"] is True
    operation_id = str(created_body["operation_id"])
    assert created_body["operation"]["meta"]["objective"] == "operator reason password=[REDACTED:secret]"
    assert created_body["operation"]["input"]["goal"] == "draft plan token=[REDACTED:secret]"
    assert created_body["operation"]["input"]["meta"]["operator_note"] == "secret=[REDACTED:secret]"
    assert created_body["operation"]["input"]["meta"]["ticket"] == "OPS-1"

    patched = client.patch(
        f"/operations/{operation_id}",
        json={
            "note": "patch note token=operationpatchnotesecret123",
            "meta": {"operator_note": "password=operationpatchmetasecret123"},
        },
    )
    assert patched.status_code == 200
    patched_body = patched.json()
    assert patched_body["ok"] is True

    fetched = client.get(f"/operations/{operation_id}")
    listed = client.get("/operations/list")
    many = client.post("/operations/get_many", json={"ids": [operation_id]})
    exported = client.get("/operations/export?format=json")
    assert fetched.status_code == 200
    assert listed.status_code == 200
    assert many.status_code == 200
    assert exported.status_code == 200

    fetched_body = fetched.json()
    assert fetched_body["meta"]["task"]["objective"] == "operator reason password=[REDACTED:secret]"
    assert fetched_body["meta"]["task"]["inputs"]["goal"] == "draft plan token=[REDACTED:secret]"
    assert fetched_body["meta"]["task"]["meta"]["note"] == "patch note token=[REDACTED:secret]"
    assert fetched_body["meta"]["task"]["meta"]["operator_note"] == "password=[REDACTED:secret]"

    cancelled = client.post(
        f"/operations/{operation_id}/cancel",
        json={"reason": "cancel reason secret=operationcancelsecret123"},
    )
    assert cancelled.status_code == 200

    combined_response_text = "\n".join(
        [
            json.dumps(created_body, sort_keys=True),
            json.dumps(patched_body, sort_keys=True),
            json.dumps(fetched_body, sort_keys=True),
            json.dumps(listed.json(), sort_keys=True),
            json.dumps(many.json(), sort_keys=True),
            exported.text,
            json.dumps(cancelled.json(), sort_keys=True),
        ]
    )
    for raw in (
        "operationreasonsecret123",
        "operationinputsecret123",
        "operationmetasecret123",
        "operationpatchnotesecret123",
        "operationpatchmetasecret123",
        "operationcancelsecret123",
    ):
        assert raw not in combined_response_text

    record_text = (data_root / "tasks" / operation_id / "record.json").read_text(encoding="utf-8")
    audit_text = (data_root / "tasks" / operation_id / "audit.log").read_text(encoding="utf-8")
    assert "operationreasonsecret123" not in record_text
    assert "operationmetasecret123" not in record_text
    assert "operationpatchnotesecret123" not in record_text
    assert "operationpatchmetasecret123" not in record_text
    assert "operationcancelsecret123" not in record_text
    assert "operationcancelsecret123" not in audit_text
    assert "operationinputsecret123" in record_text


def test_operations_run_executes_plan_create(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    created = client.post(
        "/operations/create",
        json={"action": "plan.create", "reason": "run_now", "input": {"goal": "run immediately"}},
    )
    assert created.status_code == 200
    operation_id = str(created.json()["operation_id"])

    run_now = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.operations"})
    assert run_now.status_code == 200
    run_body = run_now.json()
    assert run_body["status"] in {"succeeded", "failed"}
    output = run_body["operation"]["output"]
    assert isinstance(output, dict)
    assert output["kind"] == "plan.create.result"
    assert output["plan_status"] == "in_progress"
    assert output["plan_current_step_id"] == "understand"
    assert output["plan_current_step_title"] == "Understand goal + constraints"
    assert output["plan_step_count"] == 4
    assert output["plan_checkpoint_count"] == 3
    assert output["plan"]["status"] == "in_progress"
    trace_id = str(output.get("trace_id") or "")
    run_id = str(output.get("run_id") or "")
    assert trace_id.startswith("trace_")
    assert run_id.startswith("run_")
    assert run_body["operation"]["trace_id"] == trace_id
    assert run_body["operation"]["run_id"] == run_id

    fetched = client.get(f"/operations/{operation_id}")
    assert fetched.status_code == 200
    fetched_body = fetched.json()
    assert str(fetched_body["operation"]["id"]) == operation_id
    assert fetched_body["operation"]["status"] in {"succeeded", "failed"}
    assert fetched_body["operation"]["trace_id"] == trace_id
    assert fetched_body["operation"]["run_id"] == run_id
    final_status_log = next(
        item
        for item in fetched_body["logs"]
        if item["kind"] == "audit_event" and item["name"] == "status_updated" and item["status"] == "succeeded"
    )
    assert final_status_log["trace_id"] == trace_id
    assert final_status_log["run_id"] == run_id
    assert final_status_log["output"]["trace_id"] == trace_id
    assert final_status_log["output"]["run_id"] == run_id

    listed_by_trace = client.get("/operations/list", params={"trace_id": trace_id})
    assert listed_by_trace.status_code == 200
    assert [item["id"] for item in listed_by_trace.json()["items"]] == [operation_id]


def test_operations_create_is_blocked_in_observe_mode(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app
    from francis.world_state.operator_mode import set_control_mode

    client = TestClient(create_app())

    set_control_mode("observe", reason="test_observe_create_block", actor="tests")

    created = client.post(
        "/operations/create",
        json={"action": "plan.create", "reason": "observe_block", "input": {"goal": "should not queue"}},
    )
    assert created.status_code == 200
    created_body = created.json()
    assert created_body["ok"] is False
    assert created_body["status"] == "blocked"
    assert "Observe mode keeps Francis read-only." in created_body["error"]

    listed = client.get("/operations/list")
    assert listed.status_code == 200
    listed_body = listed.json()
    assert listed_body["items"] == []


def test_operations_run_is_blocked_in_observe_mode(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app
    from francis.world_state.operator_mode import set_control_mode

    client = TestClient(create_app())

    created = client.post(
        "/operations/create",
        json={"action": "plan.create", "reason": "observe_block", "input": {"goal": "stay queued in observe"}},
    )
    assert created.status_code == 200
    operation_id = str(created.json()["operation_id"])

    set_control_mode("observe", reason="test_observe_block", actor="tests")

    run_now = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.operations"})
    assert run_now.status_code == 200
    run_body = run_now.json()
    assert run_body["ok"] is False
    assert run_body["status"] == "queued"
    assert "Observe mode keeps execution read-only." in run_body["message"]

    fetched = client.get(f"/operations/{operation_id}")
    assert fetched.status_code == 200
    fetched_body = fetched.json()
    assert fetched_body["operation"]["status"] == "queued"


def test_operations_run_once_worker_route_completes_cleanly(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    run_once = client.post(
        "/operations/run-once",
        json={
            "queue": "default",
            "kind": "default",
            "concurrency": 1,
            "heartbeat_s": 0.1,
            "profile": "dev",
            "run_mode": "api",
            "log_level": "INFO",
        },
    )
    assert run_once.status_code == 200
    body = run_once.json()
    assert body["ok"] is True
    assert body["exit_code"] == 0


def test_operations_run_once_worker_route_is_blocked_in_observe_mode(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app
    from francis.world_state.operator_mode import set_control_mode

    set_control_mode("observe", reason="test_observe_worker_block", actor="tests")

    client = TestClient(create_app())

    run_once = client.post(
        "/operations/run-once",
        json={
            "queue": "default",
            "kind": "default",
            "concurrency": 1,
            "heartbeat_s": 0.1,
            "profile": "dev",
            "run_mode": "api",
            "log_level": "INFO",
        },
    )
    assert run_once.status_code == 200
    body = run_once.json()
    assert body["ok"] is False
    assert body["exit_code"] == 1
    assert body["status"] == "blocked"
    assert "Observe mode keeps execution read-only." in body["error"]


def test_operations_export_jsonl_contains_task(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    created = client.post(
        "/operations/create",
        json={"action": "plan.create", "reason": "export_test", "input": {"goal": "export"}},
    )
    assert created.status_code == 200
    operation_id = str(created.json()["operation_id"])

    exported = client.get("/operations/export?format=jsonl")
    assert exported.status_code == 200
    assert operation_id in exported.text


def test_operations_plugin_run_action_executes(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    built = client.post("/plugins/build", json={"name": "Ops Plugin", "description": "operation plugin action"})
    assert built.status_code == 200
    plugin_id = str(built.json()["plugin_id"])

    status = client.get("/operations/status")
    assert status.status_code == 200
    capabilities = status.json().get("capabilities") or []
    assert "plugin.run" in capabilities

    created = client.post(
        "/operations/create",
        json={
            "action": "plugin.run",
            "reason": "queue plugin run",
            "input": {"id": plugin_id, "action": "run", "input": "hello from operation"},
        },
    )
    assert created.status_code == 200
    created_body = created.json()
    assert created_body["ok"] is True
    operation_id = str(created_body["operation_id"])

    run_now = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.operations.plugin"})
    assert run_now.status_code == 200
    run_body = run_now.json()
    assert run_body["status"] == "succeeded"
    output = run_body["operation"]["output"]
    assert isinstance(output, dict)
    assert output["ok"] is True
    assert str(output["output"]) == "Plugin response: hello from operation"
    trace_id = str(output["receipt"].get("trace_id") or "")
    run_id = str(output["receipt"].get("run_id") or "")
    assert trace_id.startswith("trace_")
    assert run_id.startswith("run_")
    assert run_body["operation"]["trace_id"] == trace_id
    assert run_body["operation"]["run_id"] == run_id
    assert run_body["operation"]["meta"]["trace_id"] == trace_id
    assert run_body["operation"]["meta"]["run_id"] == run_id

    fetched = client.get(f"/operations/{operation_id}")
    assert fetched.status_code == 200
    fetched_body = fetched.json()
    assert fetched_body["operation"]["trace_id"] == trace_id
    assert fetched_body["operation"]["run_id"] == run_id
    assert fetched_body["operation"]["meta"]["trace_id"] == trace_id
    assert fetched_body["operation"]["meta"]["run_id"] == run_id

    listed = client.get("/operations/list")
    assert listed.status_code == 200
    listed_operation = next(item for item in listed.json()["items"] if item["id"] == operation_id)
    assert listed_operation["trace_id"] == trace_id
    assert listed_operation["run_id"] == run_id

    listed_by_trace = client.get("/operations/list", params={"trace_id": trace_id})
    assert listed_by_trace.status_code == 200
    assert [item["id"] for item in listed_by_trace.json()["items"]] == [operation_id]

    listed_by_run = client.get("/operations/list", params={"run_id": run_id})
    assert listed_by_run.status_code == 200
    assert [item["id"] for item in listed_by_run.json()["items"]] == [operation_id]

    exported_json = client.get("/operations/export", params={"format": "json", "run_id": run_id})
    assert exported_json.status_code == 200
    assert [item["id"] for item in exported_json.json()["items"]] == [operation_id]

    exported_csv = client.get("/operations/export", params={"format": "csv", "trace_id": trace_id})
    assert exported_csv.status_code == 200
    rows = list(csv.DictReader(io.StringIO(exported_csv.text)))
    assert [row["id"] for row in rows] == [operation_id]
    assert rows[0]["trace_id"] == trace_id
    assert rows[0]["run_id"] == run_id
    assert "artifact_dir" in rows[0]


def test_operations_list_and_export_filter_artifact_receipts(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    task_id = "tsk_artifact_filter"
    artifact_dir = str(data_root / "artifacts" / "supervised_exec" / "run_filter")
    task_dir = data_root / "tasks" / task_id
    task_dir.mkdir(parents=True)
    (task_dir / "record.json").write_text(
        json.dumps(
            {
                "task_id": task_id,
                "status": "completed",
                "capability": "codex.supervised_exec",
                "requester_id": "test.operations.artifact_filter",
                "created_at": "2024-03-09T16:00:00+00:00",
                "updated_at": "2024-03-09T16:00:01+00:00",
                "inputs": {},
                "result": {
                    "data": {
                        "ok": True,
                        "receipt": {
                            "trace_id": "trace_artifact_filter",
                            "run_id": "run_artifact_filter",
                            "artifact_dir": artifact_dir,
                        },
                    }
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    listed = client.get("/operations/list", params={"artifact_dir": artifact_dir})
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()["items"]] == [task_id]

    exported = client.get("/operations/export", params={"format": "csv", "artifact_dir": artifact_dir})
    assert exported.status_code == 200
    rows = list(csv.DictReader(io.StringIO(exported.text)))
    assert [row["id"] for row in rows] == [task_id]
    assert rows[0]["trace_id"] == "trace_artifact_filter"
    assert rows[0]["run_id"] == "run_artifact_filter"
    assert rows[0]["artifact_dir"] == artifact_dir


def test_operations_run_surfaces_completed_mission_memory_receipt(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    mission = client.post(
        "/missions/create",
        json={
            "objective": "Expose direct operation memory receipt",
            "summary": "Completed mission-linked operation run should return the memory receipt handoff.",
            "requester_id": "test.operations.memory_receipt",
        },
    )
    assert mission.status_code == 200
    mission_id = str(mission.json()["mission_id"])

    built = client.post(
        "/plugins/build",
        json={"name": "Ops Memory Receipt Plugin", "description": "operation memory receipt"},
    )
    assert built.status_code == 200
    plugin_id = str(built.json()["plugin_id"])

    created = client.post(
        "/operations/create",
        json={
            "action": "plugin.run",
            "reason": "direct operation memory receipt",
            "mission_id": mission_id,
            "input": {"id": plugin_id, "action": "run", "input": "operation memory receipt"},
        },
    )
    assert created.status_code == 200
    operation_id = str(created.json()["operation_id"])

    run_now = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.operations.memory_receipt"})
    assert run_now.status_code == 200
    run_body = run_now.json()
    assert run_body["status"] == "succeeded"
    trace_id = str(run_body["operation"]["trace_id"])
    run_id = str(run_body["operation"]["run_id"])
    artifact_dir = str(run_body["operation"].get("artifact_dir") or "")

    receipt = run_body["memory_receipt"]
    assert receipt["source"] == "continuity.ledger"
    assert receipt["kind"] == "ledger_append"
    assert receipt["role"] == "system"
    assert receipt["scope"] == "mission.loop"
    assert receipt["operation_status"] == "succeeded"
    assert receipt["subsystem"] == "operations.runtime"
    expected_references = {
        "mission_id": mission_id,
        "operation_id": operation_id,
        "trace_id": trace_id,
        "run_id": run_id,
    }
    if artifact_dir:
        expected_references["artifact_dir"] = artifact_dir
    assert receipt["references"] == expected_references

    listed = client.get("/memory/timeline/list", params={"run_id": run_id})
    assert listed.status_code == 200
    assert any(item.get("references", {}).get("operation_id") == operation_id for item in listed.json()["items"])


def test_operations_run_surfaces_failed_mission_memory_receipt(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    mission = client.post(
        "/missions/create",
        json={
            "objective": "Expose failed operation memory receipt",
            "summary": "Failed mission-linked operation run should return the memory receipt handoff.",
            "requester_id": "test.operations.failed_memory_receipt",
        },
    )
    assert mission.status_code == 200
    mission_id = str(mission.json()["mission_id"])

    created = client.post(
        "/operations/create",
        json={
            "action": "plugin.run",
            "reason": "direct failed operation memory receipt",
            "mission_id": mission_id,
            "input": {"action": "run", "input": "missing plugin id"},
        },
    )
    assert created.status_code == 200
    operation_id = str(created.json()["operation_id"])

    run_now = client.post(
        f"/operations/{operation_id}/run", json={"worker_id": "test.operations.failed_memory_receipt"}
    )
    assert run_now.status_code == 200
    run_body = run_now.json()
    assert run_body["ok"] is False
    assert run_body["status"] == "failed"
    assert run_body["operation"]["error"] == "plugin_id_required"

    receipt = run_body["memory_receipt"]
    assert receipt["source"] == "continuity.ledger"
    assert receipt["kind"] == "ledger_append"
    assert receipt["role"] == "system"
    assert receipt["scope"] == "mission.loop"
    assert receipt["operation_status"] == "failed"
    assert receipt["subsystem"] == "operations.runtime"
    assert "Mission operation failed" in receipt["message"]
    assert receipt["references"]["mission_id"] == mission_id
    assert receipt["references"]["operation_id"] == operation_id
    assert str(receipt["references"]["trace_id"]).startswith("trace_")
    assert str(receipt["references"]["run_id"]).startswith("run_")

    listed = client.get(
        "/memory/timeline/list",
        params={"mission_id": mission_id, "operation_id": operation_id, "include_payload": 1},
    )
    assert listed.status_code == 200
    receipts = [
        item
        for item in listed.json()["items"]
        if item.get("kind") == "ledger_append"
        and item.get("references", {}).get("mission_id") == mission_id
        and item.get("references", {}).get("operation_id") == operation_id
    ]
    assert receipts
    assert receipts[0]["payload"]["meta"]["operation_status"] == "failed"


def test_operations_tool_run_action_executes(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    built = client.post("/plugins/build", json={"name": "Ops Tool Plugin", "description": "operation tool action"})
    assert built.status_code == 200
    plugin_id = str(built.json()["plugin_id"])

    tools = client.get(f"/plugins/tools/list?plugin_id={plugin_id}")
    assert tools.status_code == 200
    tools_body = tools.json()
    assert isinstance(tools_body.get("items"), list)
    assert tools_body["items"]
    tool_id = str(tools_body["items"][0]["id"])

    status = client.get("/operations/status")
    assert status.status_code == 200
    capabilities = status.json().get("capabilities") or []
    assert "plugin.tool.run" in capabilities

    created = client.post(
        "/operations/create",
        json={
            "action": "tool.run",
            "reason": "queue tool run",
            "input": {"id": tool_id, "input": "hello from tool operation"},
        },
    )
    assert created.status_code == 200
    created_body = created.json()
    assert created_body["ok"] is True
    operation_id = str(created_body["operation_id"])

    run_now = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.operations.tool"})
    assert run_now.status_code == 200
    run_body = run_now.json()
    assert run_body["status"] == "succeeded"
    output = run_body["operation"]["output"]
    assert isinstance(output, dict)
    assert output["ok"] is True
    assert output["tool_id"] == tool_id
    assert str(output["output"]) == "Plugin response: hello from tool operation"


def test_operations_governance_holds_are_visible_and_rerunnable(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

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
    installed_body = installed.json()
    assert installed_body["ok"] is True
    plugin_id = str(installed_body["plugin_id"])

    created = client.post(
        "/operations/create",
        json={
            "action": "plugin.run",
            "reason": "governed deploy",
            "input": {"id": plugin_id, "action": "deploy", "input": {"target": "prod"}},
        },
    )
    assert created.status_code == 200
    created_body = created.json()
    assert created_body["ok"] is True
    operation_id = str(created_body["operation_id"])

    blocked = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.operations.governance"})
    assert blocked.status_code == 200
    blocked_body = blocked.json()
    assert blocked_body["ok"] is True
    assert blocked_body["status"] == "blocked"
    blocked_meta = blocked_body["operation"]["meta"]
    assert blocked_meta["orb_plane"] == "P3_GOVERNANCE"
    assert blocked_meta["governance"]["gate"] == "trust_gate"
    assert blocked_meta["governance"]["next_step"] == "raise_trust_or_reduce_risk"

    raised = client.post("/trust/set", json={"level": 6, "reason": "operations-governance-test"})
    assert raised.status_code == 200
    assert raised.json()["ok"] is True

    pending = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.operations.governance"})
    assert pending.status_code == 200
    pending_body = pending.json()
    assert pending_body["ok"] is True
    assert pending_body["status"] == "queued"
    pending_meta = pending_body["operation"]["meta"]
    assert pending_meta["orb_plane"] == "P3_GOVERNANCE"
    assert pending_meta["governance"]["gate"] == "approvals_gate"
    approval_id = str(pending_meta["approval_id"])
    assert approval_id

    detail_pending = client.get(f"/operations/{operation_id}")
    assert detail_pending.status_code == 200
    detail_pending_body = detail_pending.json()
    task_inputs = detail_pending_body["meta"]["task"]["inputs"]
    assert task_inputs["approval_id"] == approval_id
    assert task_inputs["meta"]["approval_id"] == approval_id
    log_names = [str(item.get("name")) for item in detail_pending_body["logs"]]
    assert "status_updated" in log_names
    assert "governance_hold" in log_names

    approved = client.post(
        "/approvals/decision", json={"id": approval_id, "action": "approve", "actor": "test.approvals.decision"}
    )
    assert approved.status_code == 200
    assert approved.json()["ok"] is True

    executed = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.operations.governance"})
    assert executed.status_code == 200
    executed_body = executed.json()
    assert executed_body["ok"] is True
    assert executed_body["status"] == "succeeded"
    output = executed_body["operation"]["output"]
    assert isinstance(output, dict)
    assert output["status"] == "ok"

    detail_executed = client.get(f"/operations/{operation_id}")
    assert detail_executed.status_code == 200
    detail_executed_body = detail_executed.json()
    governance_holds = [item for item in detail_executed_body["logs"] if item.get("name") == "governance_hold"]
    assert len(governance_holds) >= 2


def test_operations_approved_mission_run_receipt_preserves_approval_posture(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    mission = client.post(
        "/missions/create",
        json={
            "objective": "Preserve approved operation posture",
            "summary": "Approved mission-linked execution should keep approval posture in receipts.",
            "requester_id": "test.operations.approved_mission_receipt",
        },
    )
    assert mission.status_code == 200
    mission_id = str(mission.json()["mission_id"])

    installed = client.post(
        "/plugins/install",
        json={
            "source_kind": "registry",
            "source_ref": "acme/ops-approved-mission",
            "capabilities": [
                {
                    "id": "acme.deploy",
                    "kind": "tool",
                    "name": "deploy",
                    "action": "deploy",
                    "description": "Deploy to a target environment.",
                    "meta": {"risk_tier": "critical", "required_trust": 5},
                }
            ],
        },
    )
    assert installed.status_code == 200
    assert installed.json()["ok"] is True
    plugin_id = str(installed.json()["plugin_id"])

    raised = client.post("/trust/set", json={"level": 6, "reason": "operations-approved-mission-receipt"})
    assert raised.status_code == 200
    assert raised.json()["ok"] is True

    created = client.post(
        "/operations/create",
        json={
            "action": "plugin.run",
            "reason": "approved mission operation",
            "mission_id": mission_id,
            "input": {"id": plugin_id, "action": "deploy", "input": {"target": "prod"}},
        },
    )
    assert created.status_code == 200
    assert created.json()["ok"] is True
    operation_id = str(created.json()["operation_id"])

    pending = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.operations.approved"})
    assert pending.status_code == 200
    pending_body = pending.json()
    assert pending_body["status"] == "queued"
    approval_id = str(pending_body["operation"]["meta"]["approval_id"])
    assert approval_id

    approved = client.post(
        "/approvals/decision", json={"id": approval_id, "action": "approve", "actor": "test.approvals.decision"}
    )
    assert approved.status_code == 200
    assert approved.json()["ok"] is True

    executed = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.operations.approved"})
    assert executed.status_code == 200
    executed_body = executed.json()
    assert executed_body["ok"] is True
    assert executed_body["status"] == "succeeded"
    assert executed_body["operation"]["meta"]["approval_id"] == approval_id

    receipt = executed_body["memory_receipt"]
    assert receipt["operation_status"] == "succeeded"
    assert receipt["approval_status"] == "approved"
    assert receipt["references"]["mission_id"] == mission_id
    assert receipt["references"]["operation_id"] == operation_id
    assert receipt["references"]["approval_id"] == approval_id

    detail = client.get(f"/operations/{operation_id}")
    assert detail.status_code == 200
    assert detail.json()["operation"]["meta"]["approval_id"] == approval_id

    listed = client.get(
        "/memory/timeline/list",
        params={"mission_id": mission_id, "operation_id": operation_id, "include_payload": 1},
    )
    assert listed.status_code == 200
    receipts = [
        item for item in listed.json()["items"] if item.get("references", {}).get("operation_id") == operation_id
    ]
    assert receipts
    assert receipts[0]["loop"]["handoff_approval_id"] == approval_id
    assert receipts[0]["loop"]["handoff_approval_status"] == "approved"


def test_operations_plugin_run_refreshes_exact_action_approval(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    installed = client.post(
        "/plugins/install",
        json={
            "source_kind": "registry",
            "source_ref": "acme/ops-governed",
            "capabilities": [
                {
                    "id": "acme.deploy",
                    "kind": "tool",
                    "name": "deploy",
                    "action": "deploy",
                    "description": "Deploy to a target environment.",
                    "meta": {"risk_tier": "critical", "required_trust": 5},
                }
            ],
        },
    )
    assert installed.status_code == 200
    installed_body = installed.json()
    assert installed_body["ok"] is True
    plugin_id = str(installed_body["plugin_id"])

    raised = client.post("/trust/set", json={"level": 6, "reason": "operations-plugin-refresh-test"})
    assert raised.status_code == 200
    assert raised.json()["ok"] is True

    created = client.post(
        "/operations/create",
        json={
            "action": "plugin.run",
            "reason": "governed deploy refresh",
            "input": {"id": plugin_id, "action": "deploy", "input": {"target": "prod"}},
        },
    )
    assert created.status_code == 200
    created_body = created.json()
    assert created_body["ok"] is True
    operation_id = str(created_body["operation_id"])

    pending = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.operations.plugin_refresh"})
    assert pending.status_code == 200
    pending_body = pending.json()
    assert pending_body["ok"] is True
    assert pending_body["status"] == "queued"
    pending_meta = pending_body["operation"]["meta"]
    assert pending_meta["orb_plane"] == "P3_GOVERNANCE"
    assert pending_meta["governance"]["gate"] == "approvals_gate"
    approval_id = str(pending_meta["approval_id"])
    assert approval_id

    approved = client.post(
        "/approvals/decision", json={"id": approval_id, "action": "approve", "actor": "test.approvals.decision"}
    )
    assert approved.status_code == 200
    assert approved.json()["ok"] is True

    record_path = data_root / "tasks" / operation_id / "record.json"
    record = json.loads(record_path.read_text(encoding="utf-8"))
    record["inputs"]["input"] = {"target": "staging"}
    record_path.write_text(json.dumps(record, indent=2), encoding="utf-8")

    mismatched = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.operations.plugin_refresh"})
    assert mismatched.status_code == 200
    mismatched_body = mismatched.json()
    assert mismatched_body["ok"] is True
    assert mismatched_body["status"] == "queued"
    mismatch_output = mismatched_body["operation"]["output"]
    assert isinstance(mismatch_output, dict)
    assert mismatch_output["status"] == "needs_approval"
    assert mismatch_output["error"] == "approval_payload_mismatch"
    refreshed_approval_id = str(mismatch_output["approval_id"])
    assert refreshed_approval_id
    assert refreshed_approval_id != approval_id
    assert mismatch_output["previous_approval_id"] == approval_id
    mismatch_meta = mismatched_body["operation"]["meta"]
    assert mismatch_meta["orb_plane"] == "P3_GOVERNANCE"
    assert mismatch_meta["governance"]["gate"] == "approvals_gate"
    assert mismatch_meta["approval_id"] == refreshed_approval_id

    art = Path(str(mismatch_output["artifact_dir"]))
    assert (art / "request.json").exists()
    assert (art / "mismatch.json").exists()

    detail_pending = client.get(f"/operations/{operation_id}")
    assert detail_pending.status_code == 200
    detail_pending_body = detail_pending.json()
    task_inputs = detail_pending_body["meta"]["task"]["inputs"]
    assert task_inputs["approval_id"] == refreshed_approval_id
    assert task_inputs["meta"]["approval_id"] == refreshed_approval_id
    assert task_inputs["input"]["target"] == "staging"
    governance_holds = [item for item in detail_pending_body["logs"] if item.get("name") == "governance_hold"]
    assert governance_holds
    last_hold = governance_holds[-1]["output"]
    assert last_hold["approval_id"] == refreshed_approval_id

    approved_refreshed = client.post(
        "/approvals/decision",
        json={"id": refreshed_approval_id, "action": "approve", "actor": "test.approvals.decision"},
    )
    assert approved_refreshed.status_code == 200
    assert approved_refreshed.json()["ok"] is True

    executed = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.operations.plugin_refresh"})
    assert executed.status_code == 200
    executed_body = executed.json()
    assert executed_body["ok"] is True
    assert executed_body["status"] == "succeeded"
    output = executed_body["operation"]["output"]
    assert isinstance(output, dict)
    assert output["status"] == "ok"
    assert output["meta"]["action"] == "deploy"


def test_operations_git_push_requires_approval_and_pushes_branch(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    repo_root = tmp_path / "repo"
    remote_root = tmp_path / "remote.git"
    repo_root.mkdir()

    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_ROOT", str(repo_root))

    _git(repo_root, "init")
    _git(repo_root, "config", "user.name", "Francis Tests")
    _git(repo_root, "config", "user.email", "francis-tests@example.com")
    _git(repo_root, "checkout", "-b", "main")
    (repo_root / "README.md").write_text("initial\n", encoding="utf-8")
    _git(repo_root, "add", "README.md")
    _git(repo_root, "commit", "-m", "Initial commit")
    _git(repo_root, "init", "--bare", str(remote_root))
    _git(repo_root, "remote", "add", "origin", str(remote_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    status = client.get("/operations/status")
    assert status.status_code == 200
    capabilities = status.json().get("capabilities") or []
    assert "git.push" in capabilities

    created = client.post(
        "/operations/create",
        json={
            "action": "git.push",
            "reason": "push current branch",
            "input": {"cwd": str(repo_root), "remote": "origin"},
        },
    )
    assert created.status_code == 200
    created_body = created.json()
    assert created_body["ok"] is True
    operation_id = str(created_body["operation_id"])

    pending = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.operations.git_push"})
    assert pending.status_code == 200
    pending_body = pending.json()
    assert pending_body["ok"] is True
    assert pending_body["status"] == "queued"
    pending_meta = pending_body["operation"]["meta"]
    assert pending_meta["orb_plane"] == "P3_GOVERNANCE"
    assert pending_meta["governance"]["gate"] == "approvals_gate"
    approval_id = str(pending_meta["approval_id"])
    assert approval_id

    detail_pending = client.get(f"/operations/{operation_id}")
    assert detail_pending.status_code == 200
    detail_pending_body = detail_pending.json()
    pending_inputs = detail_pending_body["meta"]["task"]["inputs"]
    assert pending_inputs["approval_id"] == approval_id
    assert pending_inputs["meta"]["approval_id"] == approval_id
    log_names = [str(item.get("name")) for item in detail_pending_body["logs"]]
    assert "governance_hold" in log_names

    approved = client.post(
        "/approvals/decision", json={"id": approval_id, "action": "approve", "actor": "test.approvals.decision"}
    )
    assert approved.status_code == 200
    assert approved.json()["ok"] is True

    executed = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.operations.git_push"})
    assert executed.status_code == 200
    executed_body = executed.json()
    assert executed_body["ok"] is True
    assert executed_body["status"] == "succeeded"
    output = executed_body["operation"]["output"]
    assert isinstance(output, dict)
    assert output["status"] == "success"
    assert output["branch"] == "main"
    assert output["remote"] == "origin"
    assert output["exit_code"] == 0

    remote_branch = subprocess.run(
        ["git", "--git-dir", str(remote_root), "rev-parse", "refs/heads/main"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    assert remote_branch.returncode == 0
    assert remote_branch.stdout.strip()


def test_operations_git_push_refreshes_approval_when_remote_changes(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    repo_root = tmp_path / "repo"
    origin_root = tmp_path / "origin.git"
    mirror_root = tmp_path / "mirror.git"
    repo_root.mkdir()

    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_ROOT", str(repo_root))

    _git(repo_root, "init")
    _git(repo_root, "config", "user.name", "Francis Tests")
    _git(repo_root, "config", "user.email", "francis-tests@example.com")
    _git(repo_root, "checkout", "-b", "main")
    (repo_root / "README.md").write_text("initial\n", encoding="utf-8")
    _git(repo_root, "add", "README.md")
    _git(repo_root, "commit", "-m", "Initial commit")
    _git(repo_root, "init", "--bare", str(origin_root))
    _git(repo_root, "init", "--bare", str(mirror_root))
    _git(repo_root, "remote", "add", "origin", str(origin_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    created = client.post(
        "/operations/create",
        json={
            "action": "git.push",
            "reason": "push current branch",
            "input": {"cwd": str(repo_root), "remote": "origin"},
        },
    )
    assert created.status_code == 200
    operation_id = str(created.json()["operation_id"])

    pending = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.operations.git_push"})
    assert pending.status_code == 200
    pending_body = pending.json()
    first_approval_id = str(pending_body["operation"]["meta"]["approval_id"])
    assert first_approval_id

    approved = client.post(
        "/approvals/decision", json={"id": first_approval_id, "action": "approve", "actor": "test.approvals.decision"}
    )
    assert approved.status_code == 200
    assert approved.json()["ok"] is True

    _git(repo_root, "remote", "set-url", "origin", str(mirror_root))

    mismatched = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.operations.git_push"})
    assert mismatched.status_code == 200
    mismatched_body = mismatched.json()
    assert mismatched_body["ok"] is True
    assert mismatched_body["status"] == "queued"
    mismatch_output = mismatched_body["operation"]["output"]
    assert isinstance(mismatch_output, dict)
    assert mismatch_output["status"] == "needs_approval"
    assert mismatch_output["error"] == "approval_payload_mismatch"
    refreshed_approval_id = str(mismatch_output["approval_id"])
    assert refreshed_approval_id
    assert refreshed_approval_id != first_approval_id
    assert mismatch_output["previous_approval_id"] == first_approval_id
    mismatch_meta = mismatched_body["operation"]["meta"]
    assert mismatch_meta["orb_plane"] == "P3_GOVERNANCE"
    assert mismatch_meta["governance"]["gate"] == "approvals_gate"
    assert mismatch_meta["approval_id"] == refreshed_approval_id

    art = Path(str(mismatch_output["artifact_dir"]))
    assert (art / "request.json").exists()
    assert (art / "mismatch.json").exists()
    assert not (art / "result.json").exists()

    mirror_branch_before = subprocess.run(
        ["git", "--git-dir", str(mirror_root), "rev-parse", "refs/heads/main"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    assert mirror_branch_before.returncode != 0

    approved_refreshed = client.post(
        "/approvals/decision",
        json={"id": refreshed_approval_id, "action": "approve", "actor": "test.approvals.decision"},
    )
    assert approved_refreshed.status_code == 200
    assert approved_refreshed.json()["ok"] is True

    executed = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.operations.git_push"})
    assert executed.status_code == 200
    executed_body = executed.json()
    assert executed_body["ok"] is True
    assert executed_body["status"] == "succeeded"
    output = executed_body["operation"]["output"]
    assert isinstance(output, dict)
    assert output["status"] == "success"
    assert output["approval_id"] == refreshed_approval_id
    assert output["run_id"] == refreshed_approval_id
    assert executed_body["operation"]["run_id"] == refreshed_approval_id
    assert executed_body["operation"]["artifact_dir"] == output["artifact_dir"]
    assert executed_body["operation"]["meta"]["run_id"] == refreshed_approval_id
    assert executed_body["operation"]["meta"]["artifact_dir"] == output["artifact_dir"]
    assert output["remote_url"] == str(mirror_root)

    mirror_branch_after = subprocess.run(
        ["git", "--git-dir", str(mirror_root), "rev-parse", "refs/heads/main"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    assert mirror_branch_after.returncode == 0
    assert mirror_branch_after.stdout.strip()


def test_operations_git_push_seals_secret_remote_url_and_redacts_artifacts(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    repo_root = tmp_path / "repo"
    origin_secret = "gitpushoriginsecret123"
    mirror_secret = "gitpushmirrorsecret123"
    origin_root = tmp_path / f"password={origin_secret}.git"
    mirror_root = tmp_path / f"password={mirror_secret}.git"
    repo_root.mkdir()

    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_ROOT", str(repo_root))

    _git(repo_root, "init")
    _git(repo_root, "config", "user.name", "Francis Tests")
    _git(repo_root, "config", "user.email", "francis-tests@example.com")
    _git(repo_root, "checkout", "-b", "main")
    (repo_root / "README.md").write_text("initial\n", encoding="utf-8")
    _git(repo_root, "add", "README.md")
    _git(repo_root, "commit", "-m", "Initial commit")
    _git(repo_root, "init", "--bare", str(origin_root))
    _git(repo_root, "init", "--bare", str(mirror_root))
    _git(repo_root, "remote", "add", "origin", str(origin_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    created = client.post(
        "/operations/create",
        json={
            "action": "git.push",
            "reason": "push credential-bearing remote",
            "input": {"cwd": str(repo_root), "remote": "origin"},
        },
    )
    assert created.status_code == 200
    operation_id = str(created.json()["operation_id"])

    pending = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.operations.git_push_secret"})
    assert pending.status_code == 200
    pending_body = pending.json()
    assert pending_body["status"] == "queued"
    first_approval_id = str(pending_body["operation"]["meta"]["approval_id"])
    assert first_approval_id

    approval_path = data_root / "approvals" / "pending" / f"{first_approval_id}.json"
    approval_text = approval_path.read_text(encoding="utf-8")
    assert origin_secret not in approval_text
    approval_payload = json.loads(approval_text)
    sealed_remote = approval_payload["payload"]["remote_url"]
    assert sealed_remote["kind"] == "sealed_secret"
    assert sealed_remote["redacted"].endswith("password=[REDACTED:secret]")
    assert str(sealed_remote["digest"]).startswith("hmac-sha256:")

    request_artifact = data_root / "artifacts" / "git_push" / first_approval_id / "request.json"
    request_artifact_text = request_artifact.read_text(encoding="utf-8")
    assert origin_secret not in request_artifact_text
    assert "hmac-sha256:" not in request_artifact_text

    approved = client.post(
        "/approvals/decision", json={"id": first_approval_id, "action": "approve", "actor": "test.approvals.decision"}
    )
    assert approved.status_code == 200
    assert approved.json()["ok"] is True

    _git(repo_root, "remote", "set-url", "origin", str(mirror_root))

    mismatched = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.operations.git_push_secret"})
    assert mismatched.status_code == 200
    mismatched_body = mismatched.json()
    assert mismatched_body["status"] == "queued"
    mismatch_output = mismatched_body["operation"]["output"]
    assert isinstance(mismatch_output, dict)
    assert mismatch_output["error"] == "approval_payload_mismatch"
    refreshed_approval_id = str(mismatch_output["approval_id"])
    assert refreshed_approval_id != first_approval_id

    refreshed_art = Path(str(mismatch_output["artifact_dir"]))
    mismatch_artifact_text = (refreshed_art / "mismatch.json").read_text(encoding="utf-8")
    assert origin_secret not in mismatch_artifact_text
    assert mirror_secret not in mismatch_artifact_text
    assert "hmac-sha256:" not in mismatch_artifact_text
    refreshed_approval_text = (data_root / "approvals" / "pending" / f"{refreshed_approval_id}.json").read_text(
        encoding="utf-8"
    )
    assert mirror_secret not in refreshed_approval_text

    approved_refreshed = client.post(
        "/approvals/decision",
        json={"id": refreshed_approval_id, "action": "approve", "actor": "test.approvals.decision"},
    )
    assert approved_refreshed.status_code == 200
    assert approved_refreshed.json()["ok"] is True

    executed = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.operations.git_push_secret"})
    assert executed.status_code == 200
    executed_body = executed.json()
    assert executed_body["status"] in {"succeeded", "failed"}
    executed_text = json.dumps(executed_body, sort_keys=True)
    assert origin_secret not in executed_text
    assert mirror_secret not in executed_text
    output = executed_body["operation"]["output"]
    assert isinstance(output, dict)
    assert output["status"] in {"success", "error"}
    assert isinstance(output["exit_code"], int)

    art = Path(str(output["artifact_dir"]))
    for artifact_name in ("plan.json", "result.json", "stdout.txt", "stderr.txt"):
        artifact_text = (art / artifact_name).read_text(encoding="utf-8")
        assert origin_secret not in artifact_text
        assert mirror_secret not in artifact_text
        assert "hmac-sha256:" not in artifact_text

    if output["status"] == "success":
        mirror_branch_after = subprocess.run(
            ["git", "--git-dir", str(mirror_root), "rev-parse", "refs/heads/main"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        assert mirror_branch_after.returncode == 0
        assert mirror_branch_after.stdout.strip()


def test_operations_git_push_seals_https_userinfo_remote_and_redacts_projection(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_ROOT", str(repo_root))

    _git(repo_root, "init")
    _git(repo_root, "config", "user.name", "Francis Tests")
    _git(repo_root, "config", "user.email", "francis-tests@example.com")
    _git(repo_root, "checkout", "-b", "main")
    (repo_root / "README.md").write_text("initial\n", encoding="utf-8")
    _git(repo_root, "add", "README.md")
    _git(repo_root, "commit", "-m", "Initial commit")

    raw_userinfo = "francis-userinfo-secret123"
    redacted_remote = "https://[REDACTED:secret]@example.invalid/owner/repo.git"
    _git(repo_root, "remote", "add", "origin", f"https://{raw_userinfo}@example.invalid/owner/repo.git")

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    created = client.post(
        "/operations/create",
        json={
            "action": "git.push",
            "reason": "push userinfo credential remote",
            "input": {"cwd": str(repo_root), "remote": "origin"},
        },
    )
    assert created.status_code == 200
    operation_id = str(created.json()["operation_id"])

    pending = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.operations.git_push_userinfo"})
    assert pending.status_code == 200
    pending_body = pending.json()
    assert pending_body["status"] == "queued"
    pending_text = json.dumps(pending_body, sort_keys=True)
    assert raw_userinfo not in pending_text

    approval_id = str(pending_body["operation"]["meta"]["approval_id"])
    assert approval_id

    approval_path = data_root / "approvals" / "pending" / f"{approval_id}.json"
    approval_text = approval_path.read_text(encoding="utf-8")
    assert raw_userinfo not in approval_text
    approval_payload = json.loads(approval_text)
    sealed_remote = approval_payload["payload"]["remote_url"]
    assert sealed_remote["kind"] == "sealed_secret"
    assert sealed_remote["redacted"] == redacted_remote
    assert str(sealed_remote["digest"]).startswith("hmac-sha256:")

    request_artifact = data_root / "artifacts" / "git_push" / approval_id / "request.json"
    request_artifact_text = request_artifact.read_text(encoding="utf-8")
    assert raw_userinfo not in request_artifact_text
    assert "hmac-sha256:" not in request_artifact_text
    assert redacted_remote in request_artifact_text

    listed = client.get("/approvals/list?status=pending&limit=20")
    assert listed.status_code == 200
    listed_item = next(item for item in listed.json()["items"] if item["id"] == approval_id)
    listed_text = json.dumps(listed_item, sort_keys=True)
    assert raw_userinfo not in listed_text
    assert "hmac-sha256:" not in listed_text
    assert listed_item["payload"]["remote_url"] == redacted_remote


def test_operations_supervised_exec_seals_secret_command_and_redacts_artifacts(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    raw_secret = "supervisedexecsecret123"
    command = f"echo password={raw_secret}"
    created = client.post(
        "/operations/create",
        json={
            "action": "supervised_exec",
            "reason": "run approved secret-bearing command",
            "input": {"user_command": command, "cwd": str(tmp_path)},
        },
    )
    assert created.status_code == 200
    operation_id = str(created.json()["operation_id"])

    pending = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.operations.supervised_secret"})
    assert pending.status_code == 200
    pending_body = pending.json()
    assert pending_body["status"] == "queued"
    assert pending_body["operation"]["input"]["user_command"] == "echo password=[REDACTED:secret]"
    approval_id = str(pending_body["operation"]["meta"]["approval_id"])
    assert approval_id

    approval_path = data_root / "approvals" / "pending" / f"{approval_id}.json"
    approval_text = approval_path.read_text(encoding="utf-8")
    assert raw_secret not in approval_text
    approval_payload = json.loads(approval_text)
    sealed_command = approval_payload["payload"]["user_command"]
    assert sealed_command["kind"] == "sealed_secret"
    assert sealed_command["redacted"] == "echo password=[REDACTED:secret]"
    assert str(sealed_command["digest"]).startswith("hmac-sha256:")

    request_artifact = data_root / "artifacts" / "supervised_exec" / approval_id / "request.json"
    request_artifact_text = request_artifact.read_text(encoding="utf-8")
    assert raw_secret not in request_artifact_text
    assert "hmac-sha256:" not in request_artifact_text

    approved = client.post(
        "/approvals/decision", json={"id": approval_id, "action": "approve", "actor": "test.approvals.decision"}
    )
    assert approved.status_code == 200
    assert approved.json()["ok"] is True

    executed = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.operations.supervised_secret"})
    assert executed.status_code == 200
    executed_body = executed.json()
    assert executed_body["ok"] is True
    assert executed_body["status"] == "succeeded"
    output = executed_body["operation"]["output"]
    assert isinstance(output, dict)
    assert output["status"] == "success"
    art = Path(str(output["artifact_dir"]))
    assert raw_secret not in (art / "stdout.txt").read_text(encoding="utf-8")
    assert "password=[REDACTED:secret]" in (art / "stdout.txt").read_text(encoding="utf-8")
    plan_text = (art / "plan.json").read_text(encoding="utf-8")
    result_text = (art / "result.json").read_text(encoding="utf-8")
    assert raw_secret not in plan_text
    assert raw_secret not in result_text
    assert "hmac-sha256:" not in plan_text
    assert "hmac-sha256:" not in result_text

    mismatch_secret = "supervisedmismatchsecret123"
    different_secret = "superviseddifferentsecret123"
    mismatch_created = client.post(
        "/operations/create",
        json={
            "action": "supervised_exec",
            "reason": "verify sealed mismatch",
            "input": {"user_command": f"echo password={mismatch_secret}", "cwd": str(tmp_path)},
        },
    )
    assert mismatch_created.status_code == 200
    mismatch_operation_id = str(mismatch_created.json()["operation_id"])

    mismatch_pending = client.post(
        f"/operations/{mismatch_operation_id}/run",
        json={"worker_id": "test.operations.supervised_mismatch"},
    )
    assert mismatch_pending.status_code == 200
    first_approval_id = str(mismatch_pending.json()["operation"]["meta"]["approval_id"])
    assert first_approval_id

    first_approval = client.post(
        "/approvals/decision", json={"id": first_approval_id, "action": "approve", "actor": "test.approvals.decision"}
    )
    assert first_approval.status_code == 200
    assert first_approval.json()["ok"] is True

    record_path = data_root / "tasks" / mismatch_operation_id / "record.json"
    record = json.loads(record_path.read_text(encoding="utf-8"))
    record["inputs"]["user_command"] = f"echo password={different_secret}"
    record_path.write_text(json.dumps(record, indent=2), encoding="utf-8")

    mismatched = client.post(
        f"/operations/{mismatch_operation_id}/run",
        json={"worker_id": "test.operations.supervised_mismatch"},
    )
    assert mismatched.status_code == 200
    mismatched_body = mismatched.json()
    assert mismatched_body["status"] == "queued"
    mismatch_output = mismatched_body["operation"]["output"]
    assert isinstance(mismatch_output, dict)
    assert mismatch_output["error"] == "approval_payload_mismatch"
    refreshed_approval_id = str(mismatch_output["approval_id"])
    assert refreshed_approval_id != first_approval_id

    refreshed_art = Path(str(mismatch_output["artifact_dir"]))
    mismatch_artifact_text = (refreshed_art / "mismatch.json").read_text(encoding="utf-8")
    assert mismatch_secret not in mismatch_artifact_text
    assert different_secret not in mismatch_artifact_text
    assert "hmac-sha256:" not in mismatch_artifact_text
    refreshed_approval_text = (data_root / "approvals" / "pending" / f"{refreshed_approval_id}.json").read_text(
        encoding="utf-8"
    )
    assert different_secret not in refreshed_approval_text


def test_operations_supervised_exec_refreshes_stale_approval(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    created = client.post(
        "/operations/create",
        json={
            "action": "supervised_exec",
            "reason": "run approved command",
            "input": {"user_command": "echo approved", "cwd": str(tmp_path)},
        },
    )
    assert created.status_code == 200
    created_body = created.json()
    assert created_body["ok"] is True
    operation_id = str(created_body["operation_id"])

    pending = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.operations.supervised_exec"})
    assert pending.status_code == 200
    pending_body = pending.json()
    assert pending_body["ok"] is True
    assert pending_body["status"] == "queued"
    pending_meta = pending_body["operation"]["meta"]
    assert pending_meta["orb_plane"] == "P3_GOVERNANCE"
    assert pending_meta["governance"]["gate"] == "approvals_gate"
    approval_id = str(pending_meta["approval_id"])
    assert approval_id

    approved = client.post(
        "/approvals/decision", json={"id": approval_id, "action": "approve", "actor": "test.approvals.decision"}
    )
    assert approved.status_code == 200
    assert approved.json()["ok"] is True

    record_path = data_root / "tasks" / operation_id / "record.json"
    record = json.loads(record_path.read_text(encoding="utf-8"))
    record["inputs"]["user_command"] = "echo refreshed"
    record_path.write_text(json.dumps(record, indent=2), encoding="utf-8")

    mismatched = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.operations.supervised_exec"})
    assert mismatched.status_code == 200
    mismatched_body = mismatched.json()
    assert mismatched_body["ok"] is True
    assert mismatched_body["status"] == "queued"
    mismatch_output = mismatched_body["operation"]["output"]
    assert isinstance(mismatch_output, dict)
    assert mismatch_output["status"] == "needs_approval"
    assert mismatch_output["error"] == "approval_payload_mismatch"
    refreshed_approval_id = str(mismatch_output["approval_id"])
    assert refreshed_approval_id
    assert refreshed_approval_id != approval_id
    assert mismatch_output["previous_approval_id"] == approval_id
    mismatch_meta = mismatched_body["operation"]["meta"]
    assert mismatch_meta["orb_plane"] == "P3_GOVERNANCE"
    assert mismatch_meta["governance"]["gate"] == "approvals_gate"
    assert mismatch_meta["approval_id"] == refreshed_approval_id

    detail_pending = client.get(f"/operations/{operation_id}")
    assert detail_pending.status_code == 200
    detail_pending_body = detail_pending.json()
    task_inputs = detail_pending_body["meta"]["task"]["inputs"]
    assert task_inputs["approval_id"] == refreshed_approval_id
    assert task_inputs["meta"]["approval_id"] == refreshed_approval_id
    assert task_inputs["user_command"] == "echo refreshed"
    governance_holds = [item for item in detail_pending_body["logs"] if item.get("name") == "governance_hold"]
    assert governance_holds
    last_hold = governance_holds[-1]["output"]
    assert last_hold["approval_id"] == refreshed_approval_id
    assert last_hold["gate"] == "approvals_gate"

    refreshed_art = Path(str(mismatch_output["artifact_dir"]))
    assert (refreshed_art / "request.json").exists()
    assert (refreshed_art / "mismatch.json").exists()
    assert not (refreshed_art / "result.json").exists()

    approved_refreshed = client.post(
        "/approvals/decision",
        json={"id": refreshed_approval_id, "action": "approve", "actor": "test.approvals.decision"},
    )
    assert approved_refreshed.status_code == 200
    assert approved_refreshed.json()["ok"] is True

    executed = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.operations.supervised_exec"})
    assert executed.status_code == 200
    executed_body = executed.json()
    assert executed_body["ok"] is True
    assert executed_body["status"] == "succeeded"
    output = executed_body["operation"]["output"]
    assert isinstance(output, dict)
    assert output["status"] == "success"
    assert output["approval_id"] == refreshed_approval_id
