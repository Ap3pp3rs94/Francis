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


def test_chat_send_sanitizes_handler_exceptions(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app
    from francis.api.routes import chat

    def fail_handle(*_args, **_kwargs):
        raise RuntimeError("chat handler traceback token=chat-secret")

    monkeypatch.setattr(chat, "handle", fail_handle)

    client = TestClient(create_app())
    response = client.post("/chat/send", json={"message": "hello", "use_llm": False})

    assert response.status_code == 200
    body = response.json()
    assert body["error"] == "internal_api_error"
    assert "chat-secret" not in json.dumps(body, sort_keys=True)
    assert "traceback" not in json.dumps(body, sort_keys=True).lower()


def test_operation_run_sanitizes_runtime_exceptions(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    actor = "test.operations.security"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", json.dumps({actor: ["operations.run"]}))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app
    from francis.api.routes import operations

    def allow_posture(_action: str) -> str:
        return ""

    def fail_run(*_args, **_kwargs):
        raise RuntimeError("operation runtime traceback token=operation-secret")

    monkeypatch.setattr(operations, "_execution_posture_guard", allow_posture)
    monkeypatch.setattr(operations.operations_runtime, "run_operation", fail_run)

    client = TestClient(create_app())
    response = client.post(
        "/operations/op_security/run",
        json={"actor": actor, "worker_id": "test.operations.security"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["error"] == "internal_api_error"
    assert "operation-secret" not in json.dumps(body, sort_keys=True)
    assert "traceback" not in json.dumps(body, sort_keys=True).lower()


def test_lens_status_sanitizes_helper_exception_readbacks(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app
    from francis.lens import status as lens_status

    def fail_list_requests(*_args, **_kwargs):
        raise RuntimeError("lens status traceback token=lens-status-secret")

    monkeypatch.setattr(lens_status, "list_requests", fail_list_requests)

    client = TestClient(create_app())
    response = client.get("/lens/status?limit=1")

    assert response.status_code == 200
    body = response.json()
    assert body["approvals_view"]["status"] == "unavailable"
    assert body["approvals_view"]["error"] == "internal_api_error"
    assert "lens-status-secret" not in json.dumps(body, sort_keys=True)
    assert "traceback" not in json.dumps(body, sort_keys=True).lower()


def test_lens_preflight_config_read_errors_do_not_expose_exception_text(monkeypatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    config_path = repo_root / "config" / "lens" / "host.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("FRANCIS_ROOT", str(repo_root))

    from francis.lens import preflight

    def fail_read_text(self: Path, *_args, **_kwargs) -> str:
        if self == config_path:
            raise OSError("lens config traceback token=lens-config-secret")
        return "{}"

    monkeypatch.setattr(Path, "read_text", fail_read_text)

    payload, exists, error = preflight._read_config("config/lens/host.json")

    assert payload == {}
    assert exists is True
    assert error == "lens_config_read_error"
    assert "lens-config-secret" not in json.dumps({"error": error}, sort_keys=True)
    assert "traceback" not in error.lower()


def test_lens_runner_os_errors_do_not_expose_exception_text(monkeypatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    scripts_dir = repo_root / "scripts"
    scripts_dir.mkdir(parents=True)
    (scripts_dir / "lens-host.ps1").write_text("# fixture\n", encoding="utf-8")
    data_root = tmp_path / "francis_data"

    from francis.lens import activation

    def fail_run(*_args, **_kwargs):
        raise OSError("lens runner traceback token=lens-runner-secret")

    monkeypatch.setattr(activation, "repo_root", lambda: repo_root)
    monkeypatch.setattr(activation, "data_dir", lambda: data_root)
    monkeypatch.setattr(activation, "_powershell_path", lambda: "pwsh")
    monkeypatch.setattr(activation.subprocess, "run", fail_run)

    body = activation._run_bounded_lens_host_activation(run_seconds=1)

    assert body["ok"] is False
    assert body["status"] == "launch_failed"
    assert body["error"] == "internal_api_error"
    assert "lens-runner-secret" not in json.dumps(body, sort_keys=True)
    assert "traceback" not in json.dumps(body, sort_keys=True).lower()


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
