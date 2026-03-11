from __future__ import annotations

import json
from pathlib import Path

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


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def test_lens_state_surfaces_current_work_and_next_best_action() -> None:
    workspace = Path(__file__).resolve().parents[2] / "workspace"
    repo_root = workspace.parent
    telemetry_path = workspace / "telemetry" / "events.jsonl"
    signal_path = repo_root / "usage-loop-signal.txt"
    telemetry_before = _read_text(telemetry_path)
    signal_before_exists = signal_path.exists()
    signal_before = _read_text(signal_path)

    try:
        signal_path.write_text("usage signal\n", encoding="utf-8")
        _write_jsonl(
            telemetry_path,
            [
                {
                    "id": "usage-loop-telemetry-1",
                    "ts": "2026-03-11T01:00:00+00:00",
                    "ingested_at": "2026-03-11T01:00:01+00:00",
                    "run_id": "usage-loop-run",
                    "kind": "telemetry.event",
                    "stream": "terminal",
                    "source": "terminal",
                    "severity": "error",
                    "text": "terminal: pytest -q tests/integration/test_lens_usage_loop.py (exit=1)",
                    "fields": {
                        "command": "pytest -q tests/integration/test_lens_usage_loop.py",
                        "cwd": str(repo_root),
                        "exit_code": 1,
                        "stdout": "",
                        "stderr": "1 failed",
                    },
                }
            ],
        )

        with TestClient(app) as client:
            state = client.get("/lens/state")

        assert state.status_code == 200
        payload = state.json()
        assert payload["current_work"]["repo"]["available"] is True
        assert payload["current_work"]["repo"]["dirty"] is True
        assert payload["current_work"]["attention"]["kind"] == "terminal_failure"
        assert payload["next_best_action"]["kind"] == "repo.tests"
        assert payload["next_best_action"]["enabled"] is False
    finally:
        telemetry_path.write_text(telemetry_before, encoding="utf-8")
        if signal_before_exists:
            signal_path.write_text(signal_before, encoding="utf-8")
        elif signal_path.exists():
            signal_path.unlink()


def test_lens_actions_include_repo_usage_chips_and_repo_status_executes() -> None:
    workspace = Path(__file__).resolve().parents[2] / "workspace"
    repo_root = workspace.parent
    telemetry_path = workspace / "telemetry" / "events.jsonl"
    signal_path = repo_root / "usage-loop-signal.txt"
    telemetry_before = _read_text(telemetry_path)
    signal_before_exists = signal_path.exists()
    signal_before = _read_text(signal_path)

    try:
        signal_path.write_text("usage signal\n", encoding="utf-8")
        _write_jsonl(
            telemetry_path,
            [
                {
                    "id": "usage-loop-telemetry-2",
                    "ts": "2026-03-11T01:05:00+00:00",
                    "ingested_at": "2026-03-11T01:05:01+00:00",
                    "run_id": "usage-loop-run-2",
                    "kind": "telemetry.event",
                    "stream": "terminal",
                    "source": "terminal",
                    "severity": "error",
                    "text": "terminal: pytest -q tests/integration/test_lens_usage_loop.py (exit=1)",
                    "fields": {
                        "command": "pytest -q tests/integration/test_lens_usage_loop.py",
                        "cwd": str(repo_root),
                        "exit_code": 1,
                        "stdout": "",
                        "stderr": "1 failed",
                    },
                }
            ],
        )

        with TestClient(app) as client:
            original_mode = _get_mode(client)
            original_scope = _get_scope(client)
            try:
                _set_mode(client, "assist", kill_switch=False)
                _set_scope(client, _enable_apps(original_scope, ["tools", "lens", "telemetry"]))
                actions = client.get("/lens/actions")
                assert actions.status_code == 200
                actions_payload = actions.json()
                chip_kinds = [chip.get("kind") for chip in actions_payload.get("action_chips", [])]
                assert "repo.status" in chip_kinds
                assert "repo.diff" in chip_kinds
                assert "repo.lint" in chip_kinds
                assert "repo.tests" in chip_kinds

                repo_status = client.post("/lens/actions/execute", json={"kind": "repo.status"})
            finally:
                _set_scope(client, original_scope)
                _set_mode(
                    client,
                    str(original_mode.get("mode", "pilot")),
                    bool(original_mode.get("kill_switch", False)),
                )

        assert repo_status.status_code == 200
        result_payload = repo_status.json()
        assert result_payload["result"]["kind"] == "repo.status"
        assert result_payload["result"]["tool"]["skill"] == "repo.status"
        assert "usage-loop-signal.txt" in result_payload["result"]["summary"]
    finally:
        telemetry_path.write_text(telemetry_before, encoding="utf-8")
        if signal_before_exists:
            signal_path.write_text(signal_before, encoding="utf-8")
        elif signal_path.exists():
            signal_path.unlink()
