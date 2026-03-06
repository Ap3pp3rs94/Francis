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


def test_trace_header_propagates_through_missions_and_runs_trace() -> None:
    c = TestClient(app)
    original_mode = _get_mode(c)
    original_scope = _get_scope(c)
    trace_id = f"trace-{uuid4()}"
    headers = {"x-trace-id": trace_id}
    try:
        _set_mode(c, "pilot", kill_switch=False)
        _set_scope(c, _enable_apps(original_scope, ["missions", "receipts"]))

        created = c.post(
            "/missions",
            headers=headers,
            json={
                "title": f"TraceMission-{uuid4()}",
                "objective": "trace propagation",
                "steps": ["step-1", "step-2"],
            },
        )
        assert created.status_code == 200
        created_payload = created.json()
        mission_id = created_payload["mission"]["id"]
        assert created_payload["trace_id"] == trace_id

        tick = c.post(f"/missions/{mission_id}/tick", headers=headers)
        assert tick.status_code == 200
        assert tick.json()["trace_id"] == trace_id

        trace = c.get(f"/runs/trace/{trace_id}", params={"limit": 100})
        assert trace.status_code == 200
        payload = trace.json()
        assert payload["trace_id"] == trace_id

        mission_history = payload.get("receipts", {}).get("mission_history", [])
        assert any(
            str(row.get("mission_id", "")) == mission_id and str(row.get("trace_id", "")) == trace_id
            for row in mission_history
        )
        assert any(str(row.get("event", "")) == "mission.tick" for row in mission_history)
    finally:
        _set_scope(c, original_scope)
        _set_mode(c, str(original_mode.get("mode", "pilot")), bool(original_mode.get("kill_switch", False)))


def test_trace_header_propagates_through_tools_and_worker_cycle() -> None:
    c = TestClient(app)
    original_mode = _get_mode(c)
    original_scope = _get_scope(c)
    trace_id = f"trace-{uuid4()}"
    headers = {"x-trace-id": trace_id}
    try:
        _set_mode(c, "pilot", kill_switch=False)
        _set_scope(c, _enable_apps(original_scope, ["tools", "worker", "receipts"]))

        tool_run = c.post("/tools/run", headers=headers, json={"skill": "repo.status", "args": {}})
        assert tool_run.status_code == 200
        assert tool_run.json()["trace_id"] == trace_id

        cycle = c.post(
            "/worker/cycle",
            headers=headers,
            json={"max_jobs": 5, "max_runtime_seconds": 10, "action_allowlist": ["mission.tick"]},
        )
        assert cycle.status_code == 200
        assert cycle.json()["trace_id"] == trace_id

        trace = c.get(f"/runs/trace/{trace_id}", params={"limit": 100})
        assert trace.status_code == 200
        payload = trace.json()
        assert payload["trace_id"] == trace_id

        logs = payload.get("receipts", {}).get("logs", [])
        decisions = payload.get("receipts", {}).get("decisions", [])
        assert any(str(row.get("kind", "")) == "tool.run" and str(row.get("trace_id", "")) == trace_id for row in logs)
        assert any(
            str(row.get("kind", "")).startswith("worker.cycle") and str(row.get("trace_id", "")) == trace_id
            for row in decisions
        )
    finally:
        _set_scope(c, original_scope)
        _set_mode(c, str(original_mode.get("mode", "pilot")), bool(original_mode.get("kill_switch", False)))
