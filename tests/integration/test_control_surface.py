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


def test_control_mode_blocks_mission_create_in_observe() -> None:
    c = TestClient(app)
    original_mode = _get_mode(c)

    try:
        _set_mode(c, "observe", kill_switch=False)
        create = c.post(
            "/missions",
            json={"title": f"Denied-{uuid4()}", "objective": "Should be blocked", "steps": ["s1"]},
        )
        assert create.status_code == 403
        assert "Control denied" in create.json().get("detail", "")
    finally:
        _set_mode(c, str(original_mode.get("mode", "pilot")), bool(original_mode.get("kill_switch", False)))


def test_control_scope_blocks_forge_when_app_removed() -> None:
    c = TestClient(app)
    original_scope = _get_scope(c)
    original_mode = _get_mode(c)

    try:
        _set_mode(c, "pilot", kill_switch=False)
        restricted_scope = {
            "repos": original_scope.get("repos", []),
            "workspaces": original_scope.get("workspaces", []),
            "apps": ["missions", "control", "receipts", "lens"],
        }
        _set_scope(c, restricted_scope)
        forge = c.get("/forge")
        assert forge.status_code == 403
        assert "Control denied" in forge.json().get("detail", "")
    finally:
        _set_scope(c, original_scope)
        _set_mode(c, str(original_mode.get("mode", "pilot")), bool(original_mode.get("kill_switch", False)))


def test_control_panic_blocks_mutations_until_resume() -> None:
    c = TestClient(app)
    original_mode = _get_mode(c)
    original_scope = _get_scope(c)
    try:
        _set_mode(c, "pilot", kill_switch=False)
        _set_scope(
            c,
            {
                "repos": original_scope.get("repos", []),
                "workspaces": original_scope.get("workspaces", []),
                "apps": ["missions", "control", "receipts", "lens"],
            },
        )

        panic = c.post("/control/panic", json={"reason": "integration panic"})
        assert panic.status_code == 200
        panic_payload = panic.json()
        assert panic_payload["status"] == "ok"
        assert panic_payload["kill_switch"] is True

        blocked = c.post(
            "/missions",
            json={"title": f"PanicBlocked-{uuid4()}", "objective": "blocked", "steps": ["s1"]},
        )
        assert blocked.status_code == 403
        assert "kill switch active" in str(blocked.json().get("detail", "")).lower()

        resume = c.post("/control/resume", json={"reason": "integration resume", "mode": "pilot"})
        assert resume.status_code == 200
        resume_payload = resume.json()
        assert resume_payload["status"] == "ok"
        assert resume_payload["kill_switch"] is False
        assert resume_payload["mode"] == "pilot"

        create = c.post(
            "/missions",
            json={"title": f"PanicResume-{uuid4()}", "objective": "allowed", "steps": ["s1"]},
        )
        assert create.status_code == 200
    finally:
        _set_scope(c, original_scope)
        _set_mode(c, str(original_mode.get("mode", "pilot")), bool(original_mode.get("kill_switch", False)))


def test_control_receipts_are_traceable_via_runs_trace() -> None:
    c = TestClient(app)
    original_mode = _get_mode(c)
    trace_id = f"control-{uuid4()}"
    headers = {"x-trace-id": trace_id}
    try:
        _set_mode(c, "pilot", kill_switch=False)

        mode_change = c.put("/control/mode", headers=headers, json={"mode": "away", "kill_switch": False, "reason": "night"})
        assert mode_change.status_code == 200
        assert mode_change.json()["trace_id"] == trace_id

        panic = c.post("/control/panic", headers=headers, json={"reason": "traceable panic"})
        assert panic.status_code == 200
        assert panic.json()["trace_id"] == trace_id

        trace = c.get(f"/runs/trace/{trace_id}", params={"limit": 100})
        assert trace.status_code == 200
        payload = trace.json()
        decisions = payload.get("receipts", {}).get("decisions", [])
        logs = payload.get("receipts", {}).get("logs", [])
        assert any(str(row.get("kind", "")) == "control.mode" for row in decisions)
        assert any(str(row.get("kind", "")) == "control.panic" for row in decisions)
        assert any(str(row.get("kind", "")) == "control.panic" for row in logs)
    finally:
        _set_mode(c, str(original_mode.get("mode", "pilot")), bool(original_mode.get("kill_switch", False)))
