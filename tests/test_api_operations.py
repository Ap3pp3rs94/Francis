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

    approved = client.post("/approvals/decision", json={"id": approval_id, "action": "approve"})
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
