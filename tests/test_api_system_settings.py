from __future__ import annotations

from pathlib import Path


def test_system_info_and_status(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_ENV_PROFILE", "test")
    monkeypatch.setenv("FRANCIS_RUN_MODE", "api-test")

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    info = client.get("/system/info")
    assert info.status_code == 200
    info_body = info.json()
    assert info_body["ok"] is True
    assert info_body["info"]["service"] == "francis-api"
    assert info_body["info"]["env_profile"] == "test"
    assert info_body["info"]["run_mode"] == "api-test"

    status = client.get("/system/status")
    assert status.status_code == 200
    status_body = status.json()
    assert status_body["ok"] is True
    assert status_body["status"] == "ready"


def test_system_world_state_reports_nested_task_records(monkeypatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    data_root = repo_root / "data"
    task_dir = data_root / "tasks" / "tsk_nested"
    (data_root / "approvals" / "pending").mkdir(parents=True, exist_ok=True)
    task_dir.mkdir(parents=True, exist_ok=True)
    (
        data_root / "approvals" / "pending" / "appr.json"
    ).write_text(
        '{"id":"appr","action":"plugin.run","reason":"integration_test","status":"pending","ts":10}',
        encoding="utf-8",
    )
    (
        task_dir / "record.json"
    ).write_text(
        '{"task_id":"tsk_nested","status":"running","capability":"plugin.run","objective":"Test nested task","created_at":"2026-04-11T10:00:00+00:00","updated_at":"2026-04-11T10:05:00+00:00"}',
        encoding="utf-8",
    )

    monkeypatch.setenv("FRANCIS_ROOT", str(repo_root))
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    response = client.get("/system/world_state")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["subsystem"] == "world_state"
    assert body["counts"]["tasks"] == 1
    assert body["paths"]["tasks"]["path"] == str(data_root / "tasks")
    assert body["overview"]["task_status_counts"]["running"] == 1
    assert body["overview"]["recent_tasks"][0]["id"] == "tsk_nested"
    assert body["overview"]["pending_approvals"][0]["id"] == "appr"


def test_system_flags_set_and_list(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    set_res = client.post(
        "/system/flags/set",
        json={
            "key": "ui.experimental_mode",
            "enabled": True,
            "reason": "integration_test",
            "description": "Enable UI experiment",
        },
    )
    assert set_res.status_code == 200
    set_body = set_res.json()
    assert set_body["ok"] is True
    assert set_body["item"]["key"] == "ui.experimental_mode"
    assert set_body["item"]["enabled"] is True

    by_key = client.post(
        "/system/flags/ui.experimental_mode",
        json={"enabled": False, "reason": "turn_off"},
    )
    assert by_key.status_code == 200
    by_key_body = by_key.json()
    assert by_key_body["ok"] is True
    assert by_key_body["item"]["enabled"] is False

    listed = client.get("/system/flags")
    assert listed.status_code == 200
    listed_body = listed.json()
    assert isinstance(listed_body.get("items"), list)
    target = [item for item in listed_body["items"] if item.get("key") == "ui.experimental_mode"]
    assert target
    assert target[0]["enabled"] is False


def test_system_config_mutate_reflects_in_effective_snapshot(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    set_mutation = client.post(
        "/system/config/mutate",
        json={
            "op": "set",
            "path": "ui.preferences.theme",
            "value": "light",
            "reason": "test_set",
        },
    )
    assert set_mutation.status_code == 200
    set_body = set_mutation.json()
    assert set_body["ok"] is True
    assert set_body["applied"] is True
    assert set_body["resulting_value"] == "light"

    merge_mutation = client.post(
        "/system/config/mutate",
        json={
            "op": "merge",
            "path": "ui.preferences",
            "value": {"density": "compact"},
            "reason": "test_merge",
        },
    )
    assert merge_mutation.status_code == 200
    merge_body = merge_mutation.json()
    assert merge_body["ok"] is True
    assert merge_body["resulting_value"]["density"] == "compact"

    effective = client.get("/system/config/effective")
    assert effective.status_code == 200
    effective_body = effective.json()
    cfg = effective_body["config"]
    assert cfg["ui"]["preferences"]["theme"] == "light"
    assert cfg["ui"]["preferences"]["density"] == "compact"
