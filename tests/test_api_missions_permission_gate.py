from __future__ import annotations

from pathlib import Path

_MISSION_ACTOR = "test.missions.write"


def _create_permission_gate_mission(client) -> str:
    created = client.post(
        "/missions/create",
        json={
            "objective": "Exercise mission execution permission gate",
            "summary": "Mission execution should require a scoped actor.",
            "next_step": "Advance only after permission scope is verified.",
            "requester_id": "test.missions.permission_gate",
        },
    )
    assert created.status_code == 200
    body = created.json()
    assert body["ok"] is True
    return str(body["mission_id"])


def test_mission_advance_denies_missing_actor_before_mutation(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())
    mission_id = _create_permission_gate_mission(client)

    denied = client.post(f"/missions/{mission_id}/advance", json={"note": "missing actor should not advance"})

    assert denied.status_code == 200
    body = denied.json()
    assert body["ok"] is False
    assert body["applied"] is False
    assert body["status"] == "denied"
    assert body["error"] == "api_permission_denied"
    assert body["governance"]["gate"] == "permission_gate"
    assert body["governance"]["reason"] == "missing_actor"
    assert body["governance"]["evidence"]["required_scope_count"] == 1

    fetched = client.get(f"/missions/{mission_id}")
    assert fetched.status_code == 200
    assert fetched.json()["mission"]["linked_task_ids"] == []


def test_mission_run_once_denies_unscoped_actor_before_mutation(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", "{}")

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())
    mission_id = _create_permission_gate_mission(client)

    denied = client.post("/missions/run_once", json={"actor": _MISSION_ACTOR, "limit": 10})

    assert denied.status_code == 200
    body = denied.json()
    assert body["ok"] is False
    assert body["status"] == "denied"
    assert body["error"] == "api_permission_denied"
    assert body["governance"]["gate"] == "permission_gate"
    assert body["governance"]["reason"] == "missing_scopes"
    assert body["governance"]["evidence"]["required_scope_count"] == 1
    assert body["advanced"] == 0
    assert body["results"] == []
    assert body["errors"][0]["governance"]["reason"] == "missing_scopes"

    fetched = client.get(f"/missions/{mission_id}")
    assert fetched.status_code == 200
    assert fetched.json()["mission"]["linked_task_ids"] == []


def test_mission_lifecycle_mutations_deny_unscoped_actor_before_mutation(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", "{}")

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())
    mission_id = _create_permission_gate_mission(client)

    patched = client.patch(
        f"/missions/{mission_id}",
        json={
            "status": "active",
            "summary": "unscoped patch should not apply",
            "next_step": "deny before update",
            "actor": _MISSION_ACTOR,
        },
    )
    ticked = client.post(f"/missions/{mission_id}/tick", json={"actor": _MISSION_ACTOR})
    deadlettered = client.post(
        f"/missions/{mission_id}/deadletter",
        json={"reason": "unscoped_deadletter", "actor": _MISSION_ACTOR},
    )
    replaced = client.post(
        f"/missions/{mission_id}/replace",
        json={
            "objective": "Unscoped replacement",
            "summary": "Replacement should not be declared.",
            "actor": _MISSION_ACTOR,
        },
    )
    tick_all = client.post("/missions/tick", json={"actor": _MISSION_ACTOR, "limit": 10})

    for response in (patched, ticked, deadlettered, replaced, tick_all):
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is False
        assert body["status"] == "denied"
        assert body["error"] == "api_permission_denied"
        assert body["governance"]["gate"] == "permission_gate"
        assert body["governance"]["reason"] == "missing_scopes"
        assert body["governance"]["evidence"]["required_scope_count"] == 1

    assert ticked.json()["applied"] is False
    assert tick_all.json()["applied"] == 0
    assert tick_all.json()["errors"][0]["governance"]["reason"] == "missing_scopes"

    fetched = client.get(f"/missions/{mission_id}")
    assert fetched.status_code == 200
    mission = fetched.json()["mission"]
    assert mission["status"] == "queued"
    assert mission["summary"] == "Mission execution should require a scoped actor."
    assert mission["next_step"] == "Advance only after permission scope is verified."
    assert mission["deadletter_reason"] is None

    listed = client.get("/missions/list")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()["items"]] == [mission_id]


def test_mission_advance_allows_scoped_actor(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())
    mission_id = _create_permission_gate_mission(client)

    advanced = client.post(
        f"/missions/{mission_id}/advance",
        json={"actor": _MISSION_ACTOR, "note": "scoped actor may create first operation"},
    )

    assert advanced.status_code == 200
    body = advanced.json()
    assert body["ok"] is True
    assert body["applied"] is True
    assert body["action"] == "create_first_operation"
    assert body["operation_id"].startswith("tsk_")
    assert body["operation"]["name"] == "plan.create"
    assert body["operation"]["status"] == "queued"
    assert body["mission"]["linked_task_ids"] == [body["operation_id"]]
