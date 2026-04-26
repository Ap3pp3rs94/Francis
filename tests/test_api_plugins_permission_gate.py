from __future__ import annotations

from pathlib import Path

_PLUGIN_ACTOR = "test.plugins.write"


def test_plugin_lifecycle_mutations_deny_without_actor_scope(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    denied_install = client.post(
        "/plugins/install",
        json={"source_kind": "registry", "source_ref": "acme/denied", "reason": "missing actor"},
    )
    assert denied_install.status_code == 200
    denied_install_body = denied_install.json()
    assert denied_install_body["ok"] is False
    assert denied_install_body["applied"] is False
    assert denied_install_body["status"] == "denied"
    assert denied_install_body["error"] == "api_permission_denied"
    assert denied_install_body["governance"]["gate"] == "permission_gate"
    assert denied_install_body["governance"]["reason"] == "missing_actor"
    assert denied_install_body["governance"]["evidence"]["required_scope_count"] == 1
    assert not (data_root / "plugins" / "_registry.json").exists()

    denied_build = client.post(
        "/plugins/build",
        json={"name": "Denied Plugin", "description": "missing actor"},
    )
    assert denied_build.status_code == 200
    denied_build_body = denied_build.json()
    assert denied_build_body["ok"] is False
    assert denied_build_body["status"] == "denied"
    assert denied_build_body["governance"]["reason"] == "missing_actor"

    denied_reload = client.post("/plugins/reload")
    assert denied_reload.status_code == 200
    denied_reload_body = denied_reload.json()
    assert denied_reload_body["ok"] is False
    assert denied_reload_body["status"] == "denied"
    assert denied_reload_body["governance"]["reason"] == "missing_actor"
    assert not (data_root / "plugins" / "_registry.json").exists()


def test_plugin_lifecycle_mutations_allow_scoped_actor(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    installed = client.post(
        "/plugins/install",
        json={
            "source_kind": "registry",
            "source_ref": "acme/scoped",
            "reason": "scoped actor",
            "actor": _PLUGIN_ACTOR,
        },
    )
    assert installed.status_code == 200
    installed_body = installed.json()
    assert installed_body["ok"] is True
    plugin_id = str(installed_body["plugin_id"])
    assert (data_root / "plugins" / "_registry.json").exists()

    disabled = client.post("/plugins/disable", json={"id": plugin_id, "reason": "scoped actor", "actor": _PLUGIN_ACTOR})
    assert disabled.status_code == 200
    assert disabled.json()["ok"] is True
    assert disabled.json()["status"] == "disabled"

    enabled = client.post("/plugins/enable", json={"id": plugin_id, "reason": "scoped actor", "actor": _PLUGIN_ACTOR})
    assert enabled.status_code == 200
    assert enabled.json()["ok"] is True
    assert enabled.json()["status"] == "enabled"

    reloaded = client.post("/plugins/reload", json={"reason": "scoped actor", "actor": _PLUGIN_ACTOR})
    assert reloaded.status_code == 200
    assert reloaded.json()["ok"] is True

    uninstalled = client.post(
        "/plugins/uninstall", json={"id": plugin_id, "reason": "scoped actor", "actor": _PLUGIN_ACTOR}
    )
    assert uninstalled.status_code == 200
    assert uninstalled.json()["ok"] is True
    assert uninstalled.json()["status"] == "uninstalled"
