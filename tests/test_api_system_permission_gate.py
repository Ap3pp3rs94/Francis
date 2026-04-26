from __future__ import annotations

from pathlib import Path

_SYSTEM_ACTOR = "test.system.write"


def test_system_runtime_mutations_deny_without_actor_scope(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    denied_config = client.post(
        "/system/config/mutate",
        json={"op": "set", "path": "ui.preferences.theme", "value": "dark", "reason": "missing actor"},
    )
    assert denied_config.status_code == 200
    denied_config_body = denied_config.json()
    assert denied_config_body["ok"] is False
    assert denied_config_body["applied"] is False
    assert denied_config_body["status"] == "denied"
    assert denied_config_body["error"] == "api_permission_denied"
    assert denied_config_body["governance"]["gate"] == "permission_gate"
    assert denied_config_body["governance"]["reason"] == "missing_actor"
    assert denied_config_body["governance"]["evidence"]["required_scope_count"] == 1
    assert not (data_root / "runtime" / "system_settings.json").exists()

    denied_flag = client.post(
        "/system/flags/set",
        json={"key": "ui.denied", "enabled": True, "reason": "missing actor"},
    )
    assert denied_flag.status_code == 200
    denied_flag_body = denied_flag.json()
    assert denied_flag_body["ok"] is False
    assert denied_flag_body["applied"] is False
    assert denied_flag_body["status"] == "denied"
    assert denied_flag_body["error"] == "api_permission_denied"
    assert denied_flag_body["governance"]["gate"] == "permission_gate"
    assert denied_flag_body["governance"]["reason"] == "missing_actor"
    assert not (data_root / "runtime" / "feature_flags.json").exists()

    denied_mode = client.post(
        "/system/operator_mode",
        json={"mode": "away", "reason": "missing actor"},
    )
    assert denied_mode.status_code == 200
    denied_mode_body = denied_mode.json()
    assert denied_mode_body["ok"] is False
    assert denied_mode_body["applied"] is False
    assert denied_mode_body["status"] == "denied"
    assert denied_mode_body["error"] == "api_permission_denied"
    assert denied_mode_body["governance"]["gate"] == "permission_gate"
    assert denied_mode_body["governance"]["reason"] == "missing_actor"
    assert not (data_root / "runtime" / "control_mode.json").exists()

    denied_service = client.post(
        "/system/services/action",
        json={"action": "restart", "services": ["daemon"], "reason": "missing actor"},
    )
    assert denied_service.status_code == 200
    denied_service_body = denied_service.json()
    assert denied_service_body["ok"] is False
    assert denied_service_body["applied"] is False
    assert denied_service_body["status"] == "denied"
    assert denied_service_body["error"] == "api_permission_denied"
    assert denied_service_body["governance"]["gate"] == "permission_gate"
    assert denied_service_body["governance"]["reason"] == "missing_actor"
    assert not (data_root / "logs" / "audit" / "audit.jsonl").exists()


def test_system_runtime_mutations_allow_scoped_actor(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    config = client.post(
        "/system/config/mutate",
        json={
            "op": "set",
            "path": "ui.preferences.theme",
            "value": "dark",
            "reason": "scoped actor",
            "actor": _SYSTEM_ACTOR,
        },
    )
    assert config.status_code == 200
    config_body = config.json()
    assert config_body["ok"] is True
    assert config_body["applied"] is True
    assert config_body["resulting_value"] == "dark"
    assert config_body["meta"]["actor"] == _SYSTEM_ACTOR

    flag = client.post(
        "/system/flags/set",
        json={"key": "ui.allowed", "enabled": True, "reason": "scoped actor", "actor": _SYSTEM_ACTOR},
    )
    assert flag.status_code == 200
    flag_body = flag.json()
    assert flag_body["ok"] is True
    assert flag_body["applied"] is True
    assert flag_body["item"]["enabled"] is True
    assert flag_body["item"]["meta"]["actor"] == _SYSTEM_ACTOR

    mode = client.post(
        "/system/operator_mode",
        json={"mode": "away", "reason": "scoped actor", "actor": _SYSTEM_ACTOR},
    )
    assert mode.status_code == 200
    mode_body = mode.json()
    assert mode_body["ok"] is True
    assert mode_body["applied"] is True
    assert mode_body["control_mode"]["id"] == "away"
    assert mode_body["control_mode"]["changed_by"] == _SYSTEM_ACTOR

    service = client.post(
        "/system/services/action",
        json={"action": "probe", "services": ["api"], "reason": "scoped actor", "actor": _SYSTEM_ACTOR},
    )
    assert service.status_code == 200
    service_body = service.json()
    assert service_body["ok"] is True
    assert service_body["status"] == "accepted"
