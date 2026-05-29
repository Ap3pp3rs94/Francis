from __future__ import annotations

import json
from pathlib import Path


def test_api_boundary_returns_stable_error_code_without_exception_text(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app
    from francis.api.routes import approvals

    def fail_request(*_args, **_kwargs):
        raise RuntimeError("sensitive traceback token=raw-stack-secret")

    monkeypatch.setattr(approvals, "create_request", fail_request)

    client = TestClient(create_app())
    response = client.post(
        "/approvals/request",
        json={"action": "test.secret", "reason": "test", "payload": {}},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["error"] == "internal_api_error"
    assert "raw-stack-secret" not in json.dumps(body, sort_keys=True)
    assert "traceback" not in json.dumps(body, sort_keys=True).lower()


def test_operator_posture_guard_sanitizes_snapshot_errors(monkeypatch) -> None:
    from francis.api.routes import _operator_posture

    def fail_snapshot() -> dict[str, object]:
        raise RuntimeError("operator posture traceback token=posture-secret")

    monkeypatch.setattr(_operator_posture, "operator_mode_snapshot", fail_snapshot)

    reason = _operator_posture.posture_write_guard("writing test state")

    assert reason == "Writes are blocked until operator posture can be verified: internal_api_error"
    assert "posture-secret" not in reason
    assert "traceback" not in reason.lower()


def test_plugin_runtime_paths_reject_registry_traversal(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    registry_path = data_root / "plugins" / "_registry.json"
    registry_path.parent.mkdir(parents=True)
    registry_path.write_text(
        json.dumps(
            {
                "plugins": {
                    "evil.path": {
                        "id": "evil.path",
                        "name": "Traversal",
                        "status": "enabled",
                        "enabled": True,
                        "generated_dir": str(tmp_path / "outside_generated"),
                        "artifact_zip": str(tmp_path / "outside.zip"),
                        "capabilities": [{"id": "evil.path.run", "kind": "tool", "action": "run"}],
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())
    response = client.get("/plugins/get", params={"id": "evil.path"})

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    runtime = body["item"]["runtime"]
    assert runtime["artifact_exists"] is False
    assert runtime["spec_exists"] is False

    from francis.api.routes import plugins

    plugin_root = data_root / "plugins"
    assert plugins._resolve_under(plugin_root, "../outside") is None
    assert plugins._resolve_under(plugin_root, str(tmp_path / "outside")) is None
    assert plugins._resolve_under(plugin_root, "bad\x00path") is None
