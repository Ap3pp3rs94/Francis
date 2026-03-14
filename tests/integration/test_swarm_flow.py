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


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    raw = _read_text(path)
    rows: list[dict[str, object]] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        parsed = json.loads(stripped)
        if isinstance(parsed, dict):
            rows.append(parsed)
    return rows


def _restore_text(path: Path, content: str, existed: bool) -> None:
    if existed:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    elif path.exists():
        path.unlink()


def test_swarm_state_initializes_unit_registry() -> None:
    workspace = Path(__file__).resolve().parents[2] / "workspace"
    units_path = workspace / "swarm" / "units.json"
    units_before_exists = units_path.exists()
    units_before = _read_text(units_path)

    try:
        if units_path.exists():
            units_path.unlink()

        with TestClient(app) as client:
            original_scope = _get_scope(client)
            try:
                _set_scope(client, _enable_apps(original_scope, ["swarm"]))
                response = client.get("/swarm/state")
            finally:
                _set_scope(client, original_scope)

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "ok"
        assert payload["counts"]["units"] >= 5
        assert any(str(row.get("unit_id", "")) == "coordinator" for row in payload["units"])
        assert "unit(s) advertised" in payload["summary"]
    finally:
        _restore_text(units_path, units_before, units_before_exists)


def test_swarm_delegate_retry_complete_and_deadletter_flow() -> None:
    workspace = Path(__file__).resolve().parents[2] / "workspace"
    units_path = workspace / "swarm" / "units.json"
    delegations_path = workspace / "swarm" / "delegations.jsonl"
    deadletter_path = workspace / "swarm" / "deadletter.jsonl"
    run_ledger_path = workspace / "runs" / "run_ledger.jsonl"
    log_path = workspace / "logs" / "francis.log.jsonl"
    decisions_path = workspace / "journals" / "decisions.jsonl"

    units_before_exists = units_path.exists()
    units_before = _read_text(units_path)
    delegations_before_exists = delegations_path.exists()
    delegations_before = _read_text(delegations_path)
    deadletter_before_exists = deadletter_path.exists()
    deadletter_before = _read_text(deadletter_path)
    run_ledger_before_exists = run_ledger_path.exists()
    run_ledger_before = _read_text(run_ledger_path)
    log_before_exists = log_path.exists()
    log_before = _read_text(log_path)
    decisions_before_exists = decisions_path.exists()
    decisions_before = _read_text(decisions_path)

    try:
        with TestClient(app) as client:
            original_mode = _get_mode(client)
            original_scope = _get_scope(client)
            try:
                _set_mode(client, "pilot", kill_switch=False)
                _set_scope(client, _enable_apps(original_scope, ["swarm", "control", "receipts", "lens", "tools"]))

                delegated = client.post(
                    "/swarm/delegate",
                    json={
                        "target_unit_id": "repo_operator",
                        "action_kind": "repo.tests",
                        "summary": "Run the fast HUD contract checks.",
                        "max_attempts": 2,
                    },
                )
                assert delegated.status_code == 200
                delegated_payload = delegated.json()
                delegation_id = str(delegated_payload["delegation"]["id"]).strip()
                trace_id = str(delegated_payload["trace_id"]).strip()
                assert delegation_id
                assert trace_id
                assert delegated_payload["delegation"]["status"] == "queued"

                leased = client.post(
                    f"/swarm/delegations/{delegation_id}/lease",
                    json={"unit_id": "repo_operator"},
                )
                assert leased.status_code == 200
                assert leased.json()["delegation"]["status"] == "leased"

                retried = client.post(
                    f"/swarm/delegations/{delegation_id}/fail",
                    json={
                        "unit_id": "repo_operator",
                        "error": "Tests need one more retry window.",
                        "retryable": True,
                        "retry_backoff_seconds": 0,
                    },
                )
                assert retried.status_code == 200
                assert retried.json()["delegation"]["status"] == "queued"
                assert int(retried.json()["delegation"]["attempts"]) == 1

                leased_again = client.post(
                    f"/swarm/delegations/{delegation_id}/lease",
                    json={"unit_id": "repo_operator"},
                )
                assert leased_again.status_code == 200
                assert leased_again.json()["delegation"]["status"] == "leased"

                completed = client.post(
                    f"/swarm/delegations/{delegation_id}/complete",
                    json={
                        "unit_id": "repo_operator",
                        "result_summary": "Fast checks completed and handed back cleanly.",
                    },
                )
                assert completed.status_code == 200
                assert completed.json()["delegation"]["status"] == "completed"

                second = client.post(
                    "/swarm/delegate",
                    json={
                        "target_unit_id": "verifier",
                        "action_kind": "verify.receipts",
                        "summary": "Verify the latest receipt chain.",
                        "max_attempts": 1,
                    },
                )
                assert second.status_code == 200
                second_id = str(second.json()["delegation"]["id"]).strip()

                second_lease = client.post(
                    f"/swarm/delegations/{second_id}/lease",
                    json={"unit_id": "verifier"},
                )
                assert second_lease.status_code == 200
                assert second_lease.json()["delegation"]["status"] == "leased"

                deadlettered = client.post(
                    f"/swarm/delegations/{second_id}/fail",
                    json={
                        "unit_id": "verifier",
                        "error": "Receipt chain is inconsistent and requires operator review.",
                        "retryable": False,
                    },
                )
                assert deadlettered.status_code == 200
                deadletter_payload = deadlettered.json()
                assert deadletter_payload["delegation"]["status"] == "deadlettered"
                assert deadletter_payload["swarm"]["counts"]["deadletter"] >= 1
            finally:
                _set_scope(client, original_scope)
                _set_mode(
                    client,
                    str(original_mode.get("mode", "pilot")),
                    bool(original_mode.get("kill_switch", False)),
                )

        ledger_rows = _read_jsonl(run_ledger_path)
        created_summary = next(
            row.get("summary", {})
            for row in reversed(ledger_rows)
            if str(row.get("kind", "")).strip() == "swarm.delegation.created"
            and isinstance(row.get("summary"), dict)
            and str(row["summary"].get("delegation_id", "")).strip() == delegation_id
        )
        leased_summary = next(
            row.get("summary", {})
            for row in reversed(ledger_rows)
            if str(row.get("kind", "")).strip() == "swarm.delegation.leased"
            and isinstance(row.get("summary"), dict)
            and str(row["summary"].get("delegation_id", "")).strip() == delegation_id
        )
        retried_summary = next(
            row.get("summary", {})
            for row in reversed(ledger_rows)
            if str(row.get("kind", "")).strip() == "swarm.delegation.retried"
            and isinstance(row.get("summary"), dict)
            and str(row["summary"].get("delegation_id", "")).strip() == delegation_id
        )
        completed_summary = next(
            row.get("summary", {})
            for row in reversed(ledger_rows)
            if str(row.get("kind", "")).strip() == "swarm.delegation.completed"
            and isinstance(row.get("summary"), dict)
            and str(row["summary"].get("delegation_id", "")).strip() == delegation_id
        )
        deadletter_summary = next(
            row.get("summary", {})
            for row in reversed(ledger_rows)
            if str(row.get("kind", "")).strip() == "swarm.delegation.deadlettered"
            and isinstance(row.get("summary"), dict)
            and str(row["summary"].get("delegation_id", "")).strip() == second_id
        )
        assert created_summary["action_kind"] == "repo.tests"
        assert leased_summary["target_unit_id"] in {"repo_operator", "verifier"}
        assert retried_summary["status"] == "queued"
        assert completed_summary["result_summary"] == "Fast checks completed and handed back cleanly."
        assert deadletter_summary["status"] == "deadlettered"

        delegations = _read_jsonl(delegations_path)
        assert any(str(row.get("status", "")) == "completed" for row in delegations)
        assert any(str(row.get("status", "")) == "deadlettered" for row in delegations)

        deadletters = _read_jsonl(deadletter_path)
        assert deadletters
        assert any(str(row.get("target_unit_id", "")) == "verifier" for row in deadletters)
    finally:
        _restore_text(units_path, units_before, units_before_exists)
        _restore_text(delegations_path, delegations_before, delegations_before_exists)
        _restore_text(deadletter_path, deadletter_before, deadletter_before_exists)
        _restore_text(run_ledger_path, run_ledger_before, run_ledger_before_exists)
        _restore_text(log_path, log_before, log_before_exists)
        _restore_text(decisions_path, decisions_before, decisions_before_exists)


def test_swarm_execute_supported_delegation_and_record_receipts() -> None:
    workspace = Path(__file__).resolve().parents[2] / "workspace"
    units_path = workspace / "swarm" / "units.json"
    delegations_path = workspace / "swarm" / "delegations.jsonl"
    deadletter_path = workspace / "swarm" / "deadletter.jsonl"
    run_ledger_path = workspace / "runs" / "run_ledger.jsonl"
    log_path = workspace / "logs" / "francis.log.jsonl"
    decisions_path = workspace / "journals" / "decisions.jsonl"

    units_before_exists = units_path.exists()
    units_before = _read_text(units_path)
    delegations_before_exists = delegations_path.exists()
    delegations_before = _read_text(delegations_path)
    deadletter_before_exists = deadletter_path.exists()
    deadletter_before = _read_text(deadletter_path)
    run_ledger_before_exists = run_ledger_path.exists()
    run_ledger_before = _read_text(run_ledger_path)
    log_before_exists = log_path.exists()
    log_before = _read_text(log_path)
    decisions_before_exists = decisions_path.exists()
    decisions_before = _read_text(decisions_path)

    try:
        with TestClient(app) as client:
            original_mode = _get_mode(client)
            original_scope = _get_scope(client)
            try:
                _set_mode(client, "pilot", kill_switch=False)
                _set_scope(client, _enable_apps(original_scope, ["swarm", "control", "receipts", "lens", "tools"]))

                delegated = client.post(
                    "/swarm/delegate",
                    json={
                        "target_unit_id": "repo_operator",
                        "action_kind": "repo.status",
                        "summary": "Inspect the repo surface through Swarm.",
                    },
                )
                assert delegated.status_code == 200
                delegation_id = str(delegated.json()["delegation"]["id"]).strip()
                assert delegation_id

                executed = client.post(f"/swarm/delegations/{delegation_id}/execute")
                assert executed.status_code == 200
                payload = executed.json()
                assert payload["status"] == "ok"
                assert payload["delegation"]["status"] == "completed"
                assert str(payload["delegation"]["result_summary"]).strip()
                assert payload["execution"]["executor"] == "lens"
                assert str(payload["execution"]["execution_run_id"]).strip()
            finally:
                _set_scope(client, original_scope)
                _set_mode(
                    client,
                    str(original_mode.get("mode", "pilot")),
                    bool(original_mode.get("kill_switch", False)),
                )

        ledger_rows = _read_jsonl(run_ledger_path)
        executed_summary = next(
            row.get("summary", {})
            for row in reversed(ledger_rows)
            if str(row.get("kind", "")).strip() == "swarm.delegation.executed"
            and isinstance(row.get("summary"), dict)
            and str(row["summary"].get("delegation_id", "")).strip() == delegation_id
        )
        completed_summary = next(
            row.get("summary", {})
            for row in reversed(ledger_rows)
            if str(row.get("kind", "")).strip() == "swarm.delegation.completed"
            and isinstance(row.get("summary"), dict)
            and str(row["summary"].get("delegation_id", "")).strip() == delegation_id
        )
        assert executed_summary["executor"] == "lens"
        assert str(executed_summary["result_summary"]).strip()
        assert str(completed_summary["result_summary"]).strip()
    finally:
        _restore_text(units_path, units_before, units_before_exists)
        _restore_text(delegations_path, delegations_before, delegations_before_exists)
        _restore_text(deadletter_path, deadletter_before, deadletter_before_exists)
        _restore_text(run_ledger_path, run_ledger_before, run_ledger_before_exists)
        _restore_text(log_path, log_before, log_before_exists)
        _restore_text(decisions_path, decisions_before, decisions_before_exists)


def test_swarm_execute_unsupported_delegation_deadletters_cleanly() -> None:
    workspace = Path(__file__).resolve().parents[2] / "workspace"
    units_path = workspace / "swarm" / "units.json"
    delegations_path = workspace / "swarm" / "delegations.jsonl"
    deadletter_path = workspace / "swarm" / "deadletter.jsonl"
    run_ledger_path = workspace / "runs" / "run_ledger.jsonl"
    log_path = workspace / "logs" / "francis.log.jsonl"
    decisions_path = workspace / "journals" / "decisions.jsonl"

    units_before_exists = units_path.exists()
    units_before = _read_text(units_path)
    delegations_before_exists = delegations_path.exists()
    delegations_before = _read_text(delegations_path)
    deadletter_before_exists = deadletter_path.exists()
    deadletter_before = _read_text(deadletter_path)
    run_ledger_before_exists = run_ledger_path.exists()
    run_ledger_before = _read_text(run_ledger_path)
    log_before_exists = log_path.exists()
    log_before = _read_text(log_path)
    decisions_before_exists = decisions_path.exists()
    decisions_before = _read_text(decisions_path)

    try:
        with TestClient(app) as client:
            original_mode = _get_mode(client)
            original_scope = _get_scope(client)
            try:
                _set_mode(client, "pilot", kill_switch=False)
                _set_scope(client, _enable_apps(original_scope, ["swarm", "control", "receipts", "lens"]))

                delegated = client.post(
                    "/swarm/delegate",
                    json={
                        "target_unit_id": "planner",
                        "action_kind": "mission.plan",
                        "summary": "Try an unsupported planner action.",
                        "max_attempts": 1,
                    },
                )
                assert delegated.status_code == 200
                delegation_id = str(delegated.json()["delegation"]["id"]).strip()
                assert delegation_id

                executed = client.post(f"/swarm/delegations/{delegation_id}/execute")
                assert executed.status_code == 200
                payload = executed.json()
                assert payload["status"] == "error"
                assert payload["delegation"]["status"] == "deadlettered"
                assert "not supported" in str(payload["delegation"]["last_error"]).lower()
            finally:
                _set_scope(client, original_scope)
                _set_mode(
                    client,
                    str(original_mode.get("mode", "pilot")),
                    bool(original_mode.get("kill_switch", False)),
                )

        ledger_rows = _read_jsonl(run_ledger_path)
        failure_summary = next(
            row.get("summary", {})
            for row in reversed(ledger_rows)
            if str(row.get("kind", "")).strip() == "swarm.delegation.execution_failed"
            and isinstance(row.get("summary"), dict)
            and str(row["summary"].get("delegation_id", "")).strip() == delegation_id
        )
        deadletter_summary = next(
            row.get("summary", {})
            for row in reversed(ledger_rows)
            if str(row.get("kind", "")).strip() == "swarm.delegation.deadlettered"
            and isinstance(row.get("summary"), dict)
            and str(row["summary"].get("delegation_id", "")).strip() == delegation_id
        )
        assert "not supported" in str(failure_summary["error"]).lower()
        assert deadletter_summary["status"] == "deadlettered"
    finally:
        _restore_text(units_path, units_before, units_before_exists)
        _restore_text(delegations_path, delegations_before, delegations_before_exists)
        _restore_text(deadletter_path, deadletter_before, deadletter_before_exists)
        _restore_text(run_ledger_path, run_ledger_before, run_ledger_before_exists)
        _restore_text(log_path, log_before, log_before_exists)
        _restore_text(decisions_path, decisions_before, decisions_before_exists)
