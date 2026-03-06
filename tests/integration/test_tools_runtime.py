from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from apps.api.main import app


def _get_mode(client: TestClient) -> dict:
    response = client.get("/control/mode")
    assert response.status_code == 200
    return response.json()


def _set_mode(client: TestClient, mode: str, kill_switch: bool | None = None) -> None:
    payload: dict[str, object] = {"mode": mode}
    if kill_switch is not None:
        payload["kill_switch"] = kill_switch
    response = client.put("/control/mode", json=payload)
    assert response.status_code == 200


def _get_scope(client: TestClient) -> dict:
    response = client.get("/control/scope")
    assert response.status_code == 200
    return response.json()["scope"]


def _set_scope(client: TestClient, scope: dict) -> None:
    response = client.put("/control/scope", json=scope)
    assert response.status_code == 200


def _enable_tools_app(scope: dict) -> dict:
    apps = [str(item) for item in scope.get("apps", []) if isinstance(item, str)]
    if "tools" not in [item.lower() for item in apps]:
        apps.append("tools")
    return {
        "repos": scope.get("repos", []),
        "workspaces": scope.get("workspaces", []),
        "apps": apps,
    }


def _approve(client: TestClient, approval_id: str) -> None:
    decision = client.post(
        f"/approvals/{approval_id}/decision",
        json={"decision": "approved", "note": "integration test approval"},
    )
    assert decision.status_code == 200


def test_tools_catalog_and_workspace_execution_with_receipts() -> None:
    c = TestClient(app)
    original_mode = _get_mode(c)
    original_scope = _get_scope(c)

    try:
        _set_mode(c, "pilot", kill_switch=False)
        _set_scope(c, _enable_tools_app(original_scope))

        tools = c.get("/tools")
        assert tools.status_code == 200
        payload = tools.json()
        assert payload["status"] == "ok"
        names = [item.get("name") for item in payload.get("tools", [])]
        assert "workspace.read" in names
        assert "workspace.search" in names
        assert "workspace.write" in names

        rel_path = f"brain/tools_runtime_{uuid4()}.txt"
        write_requires_approval = c.post(
            "/tools/run",
            json={"skill": "workspace.write", "args": {"path": rel_path, "content": "alpha beta gamma"}},
        )
        assert write_requires_approval.status_code == 403
        detail = write_requires_approval.json().get("detail", {})
        assert isinstance(detail, dict)
        approval_id = str(detail.get("approval_request_id", ""))
        assert approval_id
        _approve(c, approval_id)

        write = c.post(
            "/tools/run",
            headers={"x-approval-id": approval_id},
            json={"skill": "workspace.write", "args": {"path": rel_path, "content": "alpha beta gamma"}},
        )
        assert write.status_code == 200
        assert write.json()["result"]["ok"] is True

        read = c.post("/tools/run", json={"skill": "workspace.read", "args": {"path": rel_path}})
        assert read.status_code == 200
        assert "alpha beta gamma" in read.json()["result"]["output"]["content"]

        search = c.post("/tools/run", json={"skill": "workspace.search", "args": {"query": "beta", "path": "brain"}})
        assert search.status_code == 200
        assert search.json()["result"]["ok"] is True
        assert search.json()["result"]["output"]["count"] >= 1

        tests_requires_approval = c.post("/tools/run", json={"skill": "repo.tests", "args": {"target": "tests/unit/test_registry.py"}})
        assert tests_requires_approval.status_code == 403
        tests_detail = tests_requires_approval.json().get("detail", {})
        assert isinstance(tests_detail, dict)
        tests_approval_id = str(tests_detail.get("approval_request_id", ""))
        assert tests_approval_id
        _approve(c, tests_approval_id)
        tests_run = c.post(
            "/tools/run",
            headers={"x-approval-id": tests_approval_id},
            json={"skill": "repo.tests", "args": {"target": "tests/unit/test_registry.py"}},
        )
        assert tests_run.status_code == 200
        assert tests_run.json()["result"]["ok"] is True

        receipts = c.get("/receipts/latest", params={"limit": 200})
        assert receipts.status_code == 200
        ledger_rows = receipts.json()["receipts"]["ledger"]
        assert any(
            row.get("kind") == "tool.run" and row.get("summary", {}).get("skill") == "workspace.write"
            for row in ledger_rows
        )
        assert any(
            row.get("kind") == "tool.run" and row.get("summary", {}).get("skill") == "repo.tests" for row in ledger_rows
        )
    finally:
        _set_scope(c, original_scope)
        _set_mode(c, str(original_mode.get("mode", "pilot")), bool(original_mode.get("kill_switch", False)))


def test_tools_mutating_action_blocked_in_observe_mode() -> None:
    c = TestClient(app)
    original_mode = _get_mode(c)
    original_scope = _get_scope(c)
    try:
        _set_scope(c, _enable_tools_app(original_scope))
        _set_mode(c, "observe", kill_switch=False)

        blocked = c.post(
            "/tools/run",
            json={"skill": "workspace.write", "args": {"path": f"brain/blocked_{uuid4()}.txt", "content": "deny"}},
        )
        assert blocked.status_code == 403
        assert "Control denied" in blocked.json().get("detail", "")

        read_only = c.post("/tools/run", json={"skill": "repo.status", "args": {}})
        assert read_only.status_code == 200
    finally:
        _set_scope(c, original_scope)
        _set_mode(c, str(original_mode.get("mode", "pilot")), bool(original_mode.get("kill_switch", False)))


def test_tools_rbac_denies_observer_execution() -> None:
    c = TestClient(app)
    original_mode = _get_mode(c)
    original_scope = _get_scope(c)
    try:
        _set_mode(c, "pilot", kill_switch=False)
        _set_scope(c, _enable_tools_app(original_scope))

        denied = c.post(
            "/tools/run",
            headers={"x-francis-role": "observer"},
            json={"skill": "workspace.read", "args": {"path": "missions/missions.json"}},
        )
        assert denied.status_code == 403
        assert "RBAC denied" in denied.json().get("detail", "")
    finally:
        _set_scope(c, original_scope)
        _set_mode(c, str(original_mode.get("mode", "pilot")), bool(original_mode.get("kill_switch", False)))
