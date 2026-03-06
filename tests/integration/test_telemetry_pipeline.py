from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from apps.api.main import app


def _workspace_root() -> Path:
    return Path(__file__).resolve().parents[2] / "workspace"


def _autonomy_events_file() -> Path:
    return _workspace_root() / "autonomy" / "events.jsonl"


def _stash(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _restore(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
        except Exception:
            continue
        if isinstance(parsed, dict):
            rows.append(parsed)
    return rows


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


def _scope_with_app(scope: dict, app_name: str) -> dict:
    current_apps = scope.get("apps", []) if isinstance(scope, dict) else []
    apps = sorted({str(item).strip().lower() for item in current_apps if str(item).strip()}.union({app_name.lower()}))
    return {
        "repos": scope.get("repos", []),
        "workspaces": scope.get("workspaces", []),
        "apps": apps,
    }


def _get_telemetry_config(client: TestClient) -> dict:
    response = client.get("/telemetry/config")
    assert response.status_code == 200
    return response.json()["config"]


def _set_telemetry_config(client: TestClient, payload: dict) -> dict:
    response = client.put("/telemetry/config", json=payload)
    assert response.status_code == 200
    return response.json()["config"]


def test_telemetry_disabled_ingest_is_ignored() -> None:
    c = TestClient(app)
    original_mode = _get_mode(c)
    original_scope = _get_scope(c)
    test_scope = _scope_with_app(original_scope, "telemetry")
    _set_scope(c, test_scope)
    original_config = _get_telemetry_config(c)

    try:
        _set_mode(c, "pilot", kill_switch=False)
        _set_telemetry_config(c, {"enabled": False})
        before = c.get("/telemetry/status").json()["telemetry"]["event_count_total"]

        post = c.post(
            "/telemetry/events",
            json={
                "stream": "terminal",
                "source": "pytest",
                "severity": "info",
                "text": "token=abc password=123",
            },
        )
        assert post.status_code == 200
        payload = post.json()
        assert payload["status"] == "ignored"
        assert payload["reason"] == "telemetry disabled"

        after = c.get("/telemetry/status").json()["telemetry"]["event_count_total"]
        assert after == before
    finally:
        _set_scope(c, test_scope)
        _set_telemetry_config(c, original_config)
        _set_scope(c, original_scope)
        _set_mode(c, str(original_mode.get("mode", "pilot")), bool(original_mode.get("kill_switch", False)))


def test_telemetry_ingest_redacts_and_surfaces_in_lens_state() -> None:
    c = TestClient(app)
    original_mode = _get_mode(c)
    original_scope = _get_scope(c)
    test_scope = _scope_with_app(original_scope, "telemetry")
    _set_scope(c, test_scope)
    original_config = _get_telemetry_config(c)

    try:
        _set_mode(c, "pilot", kill_switch=False)
        _set_telemetry_config(
            c,
            {
                "enabled": True,
                "allowed_streams": ["terminal"],
                "max_text_chars": 256,
            },
        )
        before = c.get("/telemetry/status").json()["telemetry"]["event_count_total"]

        post = c.post(
            "/telemetry/events",
            json={
                "stream": "terminal",
                "source": "pytest",
                "severity": "error",
                "text": "build failed; token=abc password=123",
                "fields": {
                    "stderr": "password leaked",
                    "nested": {"auth": "token-xyz"},
                },
            },
        )
        assert post.status_code == 200
        payload = post.json()
        assert payload["status"] == "ok"
        event = payload["event"]
        assert event["stream"] == "terminal"
        assert "[REDACTED]" in event["text"]
        assert "token" not in event["text"].lower()
        assert "password" not in event["text"].lower()
        assert "[REDACTED]" in str(event.get("fields", {}))

        telemetry = c.get("/telemetry/status")
        assert telemetry.status_code == 200
        telemetry_payload = telemetry.json()["telemetry"]
        assert telemetry_payload["enabled"] is True
        assert telemetry_payload["event_count_total"] >= before + 1
        assert "terminal" in telemetry_payload.get("active_streams_horizon", [])

        lens = c.get("/lens/state")
        assert lens.status_code == 200
        lens_payload = lens.json()
        telemetry_chip = lens_payload.get("telemetry", {})
        assert telemetry_chip.get("enabled") is True
        assert "terminal" in telemetry_chip.get("active_streams_horizon", [])
        assert telemetry_chip.get("event_count_horizon", 0) >= 1
    finally:
        _set_scope(c, test_scope)
        _set_telemetry_config(c, original_config)
        _set_scope(c, original_scope)
        _set_mode(c, str(original_mode.get("mode", "pilot")), bool(original_mode.get("kill_switch", False)))


def test_telemetry_scope_and_rbac_enforcement() -> None:
    c = TestClient(app)
    original_mode = _get_mode(c)
    original_scope = _get_scope(c)
    test_scope = _scope_with_app(original_scope, "telemetry")
    _set_scope(c, test_scope)
    original_config = _get_telemetry_config(c)

    try:
        _set_mode(c, "pilot", kill_switch=False)

        restricted_scope = {
            "repos": test_scope.get("repos", []),
            "workspaces": test_scope.get("workspaces", []),
            "apps": [
                app_name
                for app_name in test_scope.get("apps", [])
                if str(app_name).strip().lower() != "telemetry"
            ],
        }
        _set_scope(c, restricted_scope)
        denied = c.get("/telemetry/status")
        assert denied.status_code == 403
        assert "Control denied" in denied.json().get("detail", "")

        _set_scope(c, test_scope)

        read_with_observer = c.get("/telemetry/status", headers={"x-francis-role": "observer"})
        assert read_with_observer.status_code == 200

        write_with_observer = c.put(
            "/telemetry/config",
            json={"enabled": True},
            headers={"x-francis-role": "observer"},
        )
        assert write_with_observer.status_code == 403
        assert "RBAC denied" in write_with_observer.json().get("detail", "")
    finally:
        _set_scope(c, test_scope)
        _set_telemetry_config(c, original_config)
        _set_scope(c, original_scope)
        _set_mode(c, str(original_mode.get("mode", "pilot")), bool(original_mode.get("kill_switch", False)))


def test_telemetry_connectors_normalize_payloads() -> None:
    c = TestClient(app)
    original_mode = _get_mode(c)
    original_scope = _get_scope(c)
    test_scope = _scope_with_app(original_scope, "telemetry")
    _set_scope(c, test_scope)
    original_config = _get_telemetry_config(c)

    try:
        _set_mode(c, "pilot", kill_switch=False)
        _set_telemetry_config(
            c,
            {
                "enabled": True,
                "allowed_streams": ["terminal", "git", "dev_server"],
                "max_text_chars": 4000,
            },
        )

        terminal = c.post(
            "/telemetry/connectors/terminal",
            json={
                "source": "pytest",
                "command": "npm run build",
                "cwd": "D:/francis",
                "exit_code": 1,
                "stderr": "password=123 token=abc",
                "duration_ms": 2150,
            },
        )
        assert terminal.status_code == 200
        terminal_payload = terminal.json()
        assert terminal_payload["status"] == "ok"
        assert terminal_payload["event"]["stream"] == "terminal"
        assert terminal_payload["event"]["severity"] == "error"
        assert "[REDACTED]" in terminal_payload["event"]["text"]

        git = c.post(
            "/telemetry/connectors/git",
            json={
                "action": "merge_conflict",
                "repo": "francis",
                "branch": "main",
                "summary": "conflict in worker.py",
                "files": ["worker.py"],
            },
        )
        assert git.status_code == 200
        git_payload = git.json()
        assert git_payload["status"] == "ok"
        assert git_payload["event"]["stream"] == "git"
        assert git_payload["event"]["severity"] == "error"

        dev_server = c.post(
            "/telemetry/connectors/dev-server",
            json={
                "service": "api",
                "level": "warning",
                "message": "slow request",
                "port": 8000,
            },
        )
        assert dev_server.status_code == 200
        dev_payload = dev_server.json()
        assert dev_payload["status"] == "ok"
        assert dev_payload["event"]["stream"] == "dev_server"
        assert dev_payload["event"]["severity"] == "warn"

        status = c.get("/telemetry/status")
        assert status.status_code == 200
        streams = status.json()["telemetry"].get("active_streams_horizon", [])
        assert "terminal" in streams
        assert "git" in streams
        assert "dev_server" in streams
    finally:
        _set_scope(c, test_scope)
        _set_telemetry_config(c, original_config)
        _set_scope(c, original_scope)
        _set_mode(c, str(original_mode.get("mode", "pilot")), bool(original_mode.get("kill_switch", False)))


def test_telemetry_retention_enforced() -> None:
    c = TestClient(app)
    original_mode = _get_mode(c)
    original_scope = _get_scope(c)
    test_scope = _scope_with_app(original_scope, "telemetry")
    _set_scope(c, test_scope)
    original_config = _get_telemetry_config(c)

    try:
        _set_mode(c, "pilot", kill_switch=False)
        _set_telemetry_config(
            c,
            {
                "enabled": True,
                "allowed_streams": ["terminal"],
                "retention_max_events": 2,
                "retention_max_age_hours": 1,
            },
        )

        old = c.post(
            "/telemetry/events",
            json={
                "stream": "terminal",
                "source": "pytest",
                "severity": "info",
                "text": "very old event",
                "ts": "2000-01-01T00:00:00+00:00",
            },
        )
        assert old.status_code == 200
        assert old.json()["status"] == "ok"
        assert old.json()["retention"]["dropped_by_age"] >= 1

        for index in range(3):
            resp = c.post(
                "/telemetry/events",
                json={
                    "stream": "terminal",
                    "source": "pytest",
                    "severity": "info",
                    "text": f"retention event {index}",
                },
            )
            assert resp.status_code == 200
            assert resp.json()["status"] == "ok"

        status = c.get("/telemetry/status")
        assert status.status_code == 200
        telemetry = status.json()["telemetry"]
        assert telemetry["retention_max_events"] == 2
        assert telemetry["retention_max_age_hours"] == 1
        assert telemetry["event_count_total"] <= 2
    finally:
        _set_scope(c, test_scope)
        _set_telemetry_config(c, original_config)
        _set_scope(c, original_scope)
        _set_mode(c, str(original_mode.get("mode", "pilot")), bool(original_mode.get("kill_switch", False)))


def test_telemetry_auto_enqueues_autonomy_signal_on_critical() -> None:
    c = TestClient(app)
    original_mode = _get_mode(c)
    original_scope = _get_scope(c)
    with_telemetry = _scope_with_app(original_scope, "telemetry")
    test_scope = _scope_with_app(with_telemetry, "autonomy")
    _set_scope(c, test_scope)
    original_config = _get_telemetry_config(c)
    events_before = _stash(_autonomy_events_file())

    try:
        _set_mode(c, "pilot", kill_switch=False)
        _restore(_autonomy_events_file(), "")
        _set_telemetry_config(
            c,
            {
                "enabled": True,
                "allowed_streams": ["dev_server"],
            },
        )

        post = c.post(
            "/telemetry/connectors/dev-server",
            json={
                "source": "pytest",
                "service": "api",
                "level": "critical",
                "message": "service crashed",
                "port": 8000,
            },
        )
        assert post.status_code == 200
        payload = post.json()
        assert payload["status"] == "ok"
        auto = payload.get("autonomy_signal")
        assert isinstance(auto, dict)
        assert auto.get("status") in {"ok", "duplicate"}

        events = _read_jsonl(_autonomy_events_file())
        assert any(str(row.get("event_type", "")) == "telemetry.critical_present" for row in events)
    finally:
        _restore(_autonomy_events_file(), events_before)
        _set_scope(c, test_scope)
        _set_telemetry_config(c, original_config)
        _set_scope(c, original_scope)
        _set_mode(c, str(original_mode.get("mode", "pilot")), bool(original_mode.get("kill_switch", False)))
