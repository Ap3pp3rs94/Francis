from __future__ import annotations

from pathlib import Path


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

    fetched = client.get(f"/operations/{operation_id}")
    assert fetched.status_code == 200
    fetched_body = fetched.json()
    assert str(fetched_body["operation"]["id"]) == operation_id
    assert fetched_body["operation"]["status"] in {"succeeded", "failed"}


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
