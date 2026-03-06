from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from apps.api.main import app


def test_runs_endpoint_returns_recent_history() -> None:
    c = TestClient(app)
    mode = c.put("/control/mode", json={"mode": "pilot", "kill_switch": False})
    assert mode.status_code == 200

    created = c.post(
        "/missions",
        json={"title": f"RunHistory-{uuid4()}", "objective": "Generate run ledger", "steps": ["s1"]},
    )
    assert created.status_code == 200
    run_id = created.json()["run_id"]

    runs = c.get("/runs")
    assert runs.status_code == 200
    payload = runs.json()
    assert payload["status"] == "ok"
    assert isinstance(payload.get("runs"), list)

    matched = [row for row in payload["runs"] if row.get("run_id") == run_id]
    assert matched
    assert int(matched[0].get("event_count", 0)) >= 1
    assert isinstance(matched[0].get("kinds"), list)


def test_runs_limit_applies() -> None:
    c = TestClient(app)
    runs = c.get("/runs", params={"limit": 1})
    assert runs.status_code == 200
    payload = runs.json()
    assert payload["status"] == "ok"
    assert len(payload.get("runs", [])) <= 1
