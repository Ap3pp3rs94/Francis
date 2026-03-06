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


def _enable_apps(scope: dict, required_apps: list[str]) -> dict:
    apps = [str(item) for item in scope.get("apps", []) if isinstance(item, str)]
    lowered = [item.lower() for item in apps]
    for app_name in required_apps:
        if app_name.lower() not in lowered:
            apps.append(app_name)
            lowered.append(app_name.lower())
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


def test_tools_chain_mission_context_and_rollback_receipts() -> None:
    c = TestClient(app)
    original_mode = _get_mode(c)
    original_scope = _get_scope(c)

    try:
        _set_mode(c, "pilot", kill_switch=False)
        _set_scope(c, _enable_apps(original_scope, ["tools", "missions", "receipts"]))

        mission = c.post(
            "/missions",
            json={
                "title": f"ChainMission-{uuid4()}",
                "objective": "validate chain behavior",
                "steps": ["write", "verify"],
            },
        )
        assert mission.status_code == 200
        mission_id = mission.json()["mission"]["id"]

        request = c.post(
            "/approvals/request",
            json={"action": "tools.workspace.write", "reason": "chain write step"},
        )
        assert request.status_code == 200
        approval_id = request.json()["approval"]["id"]
        _approve(c, approval_id)

        rel_path = f"brain/chain_{uuid4()}.txt"
        chain = c.post(
            "/tools/chain",
            json={
                "mission_id": mission_id,
                "goal": "write then fail to trigger rollback",
                "rollback_on_failure": True,
                "steps": [
                    {
                        "skill": "workspace.write",
                        "approval_id": approval_id,
                        "args": {"path": rel_path, "content": "temporary content"},
                    },
                    {
                        "skill": "unknown.tool",
                        "args": {},
                    },
                ],
            },
        )
        assert chain.status_code == 200
        payload = chain.json()
        assert payload["status"] == "failed"
        assert payload["mission"]["id"] == mission_id
        assert payload["rollback"]["count"] >= 1
        assert payload["failed"]["skill"] == "unknown.tool"

        read_back = c.post("/tools/run", json={"skill": "workspace.read", "args": {"path": rel_path}})
        assert read_back.status_code == 200
        assert "temporary content" not in read_back.json()["result"]["output"]["content"]

        receipts = c.get("/receipts/latest", params={"limit": 200})
        assert receipts.status_code == 200
        history = receipts.json()["receipts"]["mission_history"]
        assert any(
            row.get("event") == "mission.tool_chain" and row.get("mission_id") == mission_id for row in history
        )
    finally:
        _set_scope(c, original_scope)
        _set_mode(c, str(original_mode.get("mode", "pilot")), bool(original_mode.get("kill_switch", False)))


def test_forge_promoted_tool_pack_auto_registers_and_runs() -> None:
    c = TestClient(app)
    original_mode = _get_mode(c)
    original_scope = _get_scope(c)

    try:
        _set_mode(c, "pilot", kill_switch=False)
        _set_scope(c, _enable_apps(original_scope, ["tools", "forge", "approvals"]))

        stage = c.post(
            "/forge/stage",
            json={
                "name": f"Pack-{uuid4()}",
                "description": "Tool-pack auto registration integration test.",
                "rationale": "verify promoted packs appear in /tools",
                "tags": ["pack", "integration"],
                "risk_tier": "low",
            },
        )
        assert stage.status_code == 200
        stage_id = stage.json()["stage_id"]

        promote_needs_approval = c.post(f"/forge/promote/{stage_id}")
        assert promote_needs_approval.status_code == 403
        detail = promote_needs_approval.json().get("detail", {})
        assert isinstance(detail, dict)
        approval_id = str(detail.get("approval_request_id", ""))
        assert approval_id
        _approve(c, approval_id)

        promote = c.post(f"/forge/promote/{stage_id}", headers={"x-approval-id": approval_id})
        assert promote.status_code == 200
        promote_payload = promote.json()
        assert promote_payload["tool_pack_registered"] is True
        skill_name = str(promote_payload.get("tool_pack_skill", ""))
        assert skill_name

        tools = c.get("/tools")
        assert tools.status_code == 200
        names = [item.get("name") for item in tools.json().get("tools", [])]
        assert skill_name in names

        run = c.post(
            "/tools/run",
            json={"skill": skill_name, "args": {"payload": {"hello": "world"}}},
        )
        assert run.status_code == 200
        run_payload = run.json()
        assert run_payload["result"]["ok"] is True
        assert run_payload["result"]["output"]["tool_pack"] == skill_name
        assert run_payload["skill"]["source"] == "forge"
    finally:
        _set_scope(c, original_scope)
        _set_mode(c, str(original_mode.get("mode", "pilot")), bool(original_mode.get("kill_switch", False)))
