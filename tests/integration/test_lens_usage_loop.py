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


def _restore_text(path: Path, content: str, existed: bool) -> None:
    if existed:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    elif path.exists():
        path.unlink()


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
                assert "repo.tests.request_approval" in chip_kinds

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
        _restore_text(signal_path, signal_before, signal_before_exists)


def test_lens_actions_carry_repo_tests_approval_into_action_chip() -> None:
    workspace = Path(__file__).resolve().parents[2] / "workspace"
    repo_root = workspace.parent
    telemetry_path = workspace / "telemetry" / "events.jsonl"
    signal_path = repo_root / "usage-loop-signal.txt"
    approvals_path = workspace / "approvals" / "requests.jsonl"
    decisions_path = workspace / "journals" / "decisions.jsonl"
    telemetry_before = _read_text(telemetry_path)
    signal_before_exists = signal_path.exists()
    signal_before = _read_text(signal_path)
    approvals_before_exists = approvals_path.exists()
    approvals_before = _read_text(approvals_path)
    decisions_before_exists = decisions_path.exists()
    decisions_before = _read_text(decisions_path)

    try:
        signal_path.write_text("usage signal\n", encoding="utf-8")
        _write_jsonl(
            telemetry_path,
            [
                {
                    "id": "usage-loop-telemetry-3",
                    "ts": "2026-03-11T01:10:00+00:00",
                    "ingested_at": "2026-03-11T01:10:01+00:00",
                    "run_id": "usage-loop-run-3",
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
        approvals_path.parent.mkdir(parents=True, exist_ok=True)
        approvals_path.write_text("", encoding="utf-8")
        decisions_path.parent.mkdir(parents=True, exist_ok=True)
        decisions_path.write_text("", encoding="utf-8")

        with TestClient(app) as client:
            original_mode = _get_mode(client)
            original_scope = _get_scope(client)
            try:
                _set_mode(client, "assist", kill_switch=False)
                _set_scope(client, _enable_apps(original_scope, ["tools", "lens", "telemetry", "approvals", "control"]))

                request_approval = client.post("/lens/actions/execute", json={"kind": "repo.tests.request_approval"})
                assert request_approval.status_code == 200
                approval_id = str(request_approval.json()["result"]["approval"]["id"]).strip()
                assert approval_id

                pending_actions = client.get("/lens/actions")
                assert pending_actions.status_code == 200
                pending_chips = pending_actions.json()["action_chips"]
                pending_repo_tests = next(
                    chip for chip in pending_chips if str(chip.get("kind", "")).strip() == "repo.tests"
                )
                assert pending_repo_tests["enabled"] is False
                assert "pending" in str(pending_repo_tests.get("policy_reason", "")).lower()

                approve = client.post(
                    "/lens/actions/execute",
                    json={
                        "kind": "control.remote.approval.approve",
                        "args": {"approval_id": approval_id, "note": "lens usage approval"},
                    },
                )
                assert approve.status_code == 200

                approved_actions = client.get("/lens/actions")
                assert approved_actions.status_code == 200
                approved_chips = approved_actions.json()["action_chips"]
                approved_repo_tests = next(
                    chip for chip in approved_chips if str(chip.get("kind", "")).strip() == "repo.tests"
                )
                assert approved_repo_tests["enabled"] is True
                execute_args = approved_repo_tests.get("execute_via", {}).get("payload", {}).get("args", {})
                assert execute_args.get("approval_id") == approval_id
                assert execute_args.get("lane") == "fast"
            finally:
                _set_scope(client, original_scope)
                _set_mode(
                    client,
                    str(original_mode.get("mode", "pilot")),
                    bool(original_mode.get("kill_switch", False)),
                )
    finally:
        telemetry_path.write_text(telemetry_before, encoding="utf-8")
        _restore_text(signal_path, signal_before, signal_before_exists)
        _restore_text(approvals_path, approvals_before, approvals_before_exists)
        _restore_text(decisions_path, decisions_before, decisions_before_exists)


def test_lens_execute_repo_tests_with_approved_request() -> None:
    workspace = Path(__file__).resolve().parents[2] / "workspace"
    approvals_path = workspace / "approvals" / "requests.jsonl"
    decisions_path = workspace / "journals" / "decisions.jsonl"
    approvals_before_exists = approvals_path.exists()
    approvals_before = _read_text(approvals_path)
    decisions_before_exists = decisions_path.exists()
    decisions_before = _read_text(decisions_path)

    try:
        approvals_path.parent.mkdir(parents=True, exist_ok=True)
        approvals_path.write_text("", encoding="utf-8")
        decisions_path.parent.mkdir(parents=True, exist_ok=True)
        decisions_path.write_text("", encoding="utf-8")

        with TestClient(app) as client:
            original_mode = _get_mode(client)
            original_scope = _get_scope(client)
            try:
                _set_mode(client, "assist", kill_switch=False)
                _set_scope(client, _enable_apps(original_scope, ["tools", "lens", "approvals", "control"]))

                request_approval = client.post(
                    "/lens/actions/execute",
                    json={
                        "kind": "repo.tests.request_approval",
                        "args": {"target": "tests/unit/test_usage_loop.py"},
                    },
                )
                assert request_approval.status_code == 200
                approval_id = str(request_approval.json()["result"]["approval"]["id"]).strip()
                assert approval_id

                approve = client.post(
                    "/lens/actions/execute",
                    json={
                        "kind": "control.remote.approval.approve",
                        "args": {"approval_id": approval_id, "note": "approve direct repo tests"},
                    },
                )
                assert approve.status_code == 200

                repo_tests = client.post(
                    "/lens/actions/execute",
                    json={
                        "kind": "repo.tests",
                        "args": {"target": "tests/unit/test_usage_loop.py", "approval_id": approval_id},
                    },
                )
            finally:
                _set_scope(client, original_scope)
                _set_mode(
                    client,
                    str(original_mode.get("mode", "pilot")),
                    bool(original_mode.get("kill_switch", False)),
                )

        assert repo_tests.status_code == 200
        result_payload = repo_tests.json()
        assert result_payload["result"]["kind"] == "repo.tests"
        assert result_payload["result"]["tool"]["skill"] == "repo.tests"
        assert result_payload["result"]["tool"]["approval_id"] == approval_id
    finally:
        _restore_text(approvals_path, approvals_before, approvals_before_exists)
        _restore_text(decisions_path, decisions_before, decisions_before_exists)
