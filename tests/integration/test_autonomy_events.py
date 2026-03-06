from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from apps.api.main import app


def _workspace_root() -> Path:
    return Path(__file__).resolve().parents[2] / "workspace"


def _events_file() -> Path:
    return _workspace_root() / "autonomy" / "events.jsonl"


def _deadletter_file() -> Path:
    return _workspace_root() / "autonomy" / "deadletter.jsonl"


def _worker_deadletter_file() -> Path:
    return _workspace_root() / "queue" / "deadletter.jsonl"


def _last_dispatch_file() -> Path:
    return _workspace_root() / "autonomy" / "last_dispatch.json"


def _dispatch_history_file() -> Path:
    return _workspace_root() / "autonomy" / "dispatch_history.jsonl"


def _last_tick_file() -> Path:
    return _workspace_root() / "autonomy" / "last_tick.json"


def _tick_history_file() -> Path:
    return _workspace_root() / "autonomy" / "tick_history.jsonl"


def _guardrail_file() -> Path:
    return _workspace_root() / "autonomy" / "reactor_guardrail_state.json"


def _guardrail_history_file() -> Path:
    return _workspace_root() / "autonomy" / "reactor_guardrail_history.jsonl"


def _incidents_file() -> Path:
    return _workspace_root() / "incidents" / "incidents.jsonl"


def _approvals_file() -> Path:
    return _workspace_root() / "approvals" / "requests.jsonl"


def _decisions_file() -> Path:
    return _workspace_root() / "journals" / "decisions.jsonl"


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


def _stash(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _restore(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_autonomy_event_enqueue_and_queue_status() -> None:
    c = TestClient(app)
    original_mode = _get_mode(c)
    original_scope = _get_scope(c)
    test_scope = _scope_with_app(original_scope, "autonomy")
    events_before = _stash(_events_file())
    deadletter_before = _stash(_deadletter_file())
    last_dispatch_before = _stash(_last_dispatch_file())

    try:
        _set_scope(c, test_scope)
        _set_mode(c, "pilot", kill_switch=False)
        _restore(_events_file(), "")
        _restore(_deadletter_file(), "")
        _restore(_last_dispatch_file(), "{}")

        enqueue = c.post(
            "/autonomy/events",
            json={
                "event_type": "telemetry.errors_present",
                "source": "telemetry",
                "priority": "high",
                "payload": {"count": 4},
                "dedupe_key": "telemetry-errors-1",
            },
        )
        assert enqueue.status_code == 200
        payload = enqueue.json()
        assert payload["status"] == "ok"
        assert payload["event"]["status"] == "queued"
        event_id = payload["event"]["id"]

        queue = c.get("/autonomy/events/queue")
        assert queue.status_code == 200
        q = queue.json()["queue"]
        assert q["queued_count"] >= 1
        assert any(str(item.get("id", "")) == event_id for item in q.get("queued", []))
    finally:
        _restore(_events_file(), events_before)
        _restore(_deadletter_file(), deadletter_before)
        _restore(_last_dispatch_file(), last_dispatch_before)
        _set_scope(c, original_scope)
        _set_mode(c, str(original_mode.get("mode", "pilot")), bool(original_mode.get("kill_switch", False)))


def test_autonomy_event_dispatch_processes_due_event() -> None:
    c = TestClient(app)
    original_mode = _get_mode(c)
    original_scope = _get_scope(c)
    test_scope = _scope_with_app(original_scope, "autonomy")
    events_before = _stash(_events_file())
    deadletter_before = _stash(_deadletter_file())
    last_dispatch_before = _stash(_last_dispatch_file())

    try:
        _set_scope(c, test_scope)
        _set_mode(c, "pilot", kill_switch=False)
        _restore(_events_file(), "")
        _restore(_deadletter_file(), "")
        _restore(_last_dispatch_file(), "{}")

        enqueue = c.post(
            "/autonomy/events",
            json={
                "event_type": "manual.dispatch_test",
                "source": "pytest",
                "priority": "normal",
                "payload": {"test": True},
            },
        )
        assert enqueue.status_code == 200

        dispatch = c.post(
            "/autonomy/events/dispatch",
            json={
                "max_events": 1,
                "max_actions": 0,
                "max_runtime_seconds": 5,
                "allow_medium": False,
                "allow_high": False,
                "stop_on_critical": False,
            },
        )
        assert dispatch.status_code == 200
        payload = dispatch.json()
        assert payload["status"] == "ok"
        assert payload["leased_count"] >= 1
        assert payload["processed_count"] >= 1
        assert payload["failed_count"] == 0
        verification = payload.get("verification", {})
        assert verification.get("verification_status") in {"verified", "partial", "uncertain"}
        assert verification.get("confidence") in {"confirmed", "likely", "uncertain"}
        assert isinstance(verification.get("can_claim_done"), bool)
        assert payload.get("completion_state") in {"done", "incomplete"}
        assert payload.get("trust_badge") in {"Confirmed", "Likely", "Uncertain"}

        queue = c.get("/autonomy/events/queue")
        assert queue.status_code == 200
        q = queue.json()["queue"]
        assert q["dispatched_count"] >= 1
        assert queue.json()["last_dispatch"].get("run_id") == payload.get("run_id")
    finally:
        _restore(_events_file(), events_before)
        _restore(_deadletter_file(), deadletter_before)
        _restore(_last_dispatch_file(), last_dispatch_before)
        _set_scope(c, original_scope)
        _set_mode(c, str(original_mode.get("mode", "pilot")), bool(original_mode.get("kill_switch", False)))


def test_autonomy_event_queue_rbac_and_control_enforced() -> None:
    c = TestClient(app)
    original_mode = _get_mode(c)
    original_scope = _get_scope(c)
    test_scope = _scope_with_app(original_scope, "autonomy")
    events_before = _stash(_events_file())
    deadletter_before = _stash(_deadletter_file())
    last_dispatch_before = _stash(_last_dispatch_file())

    try:
        _set_scope(c, test_scope)
        _set_mode(c, "pilot", kill_switch=False)
        _restore(_events_file(), "")
        _restore(_deadletter_file(), "")
        _restore(_last_dispatch_file(), "{}")

        observer_read = c.get("/autonomy/events/queue", headers={"x-francis-role": "observer"})
        assert observer_read.status_code == 200

        observer_write = c.post(
            "/autonomy/events",
            json={"event_type": "observer.denied"},
            headers={"x-francis-role": "observer"},
        )
        assert observer_write.status_code == 403
        assert "RBAC denied" in observer_write.json().get("detail", "")

        restricted_scope = {
            "repos": test_scope.get("repos", []),
            "workspaces": test_scope.get("workspaces", []),
            "apps": [name for name in test_scope.get("apps", []) if str(name).strip().lower() != "autonomy"],
        }
        _set_scope(c, restricted_scope)
        blocked = c.get("/autonomy/events/queue")
        assert blocked.status_code == 403
        assert "Control denied" in blocked.json().get("detail", "")
    finally:
        _restore(_events_file(), events_before)
        _restore(_deadletter_file(), deadletter_before)
        _restore(_last_dispatch_file(), last_dispatch_before)
        _set_scope(c, original_scope)
        _set_mode(c, str(original_mode.get("mode", "pilot")), bool(original_mode.get("kill_switch", False)))


def test_autonomy_dispatch_high_risk_requires_approval() -> None:
    c = TestClient(app)
    original_mode = _get_mode(c)
    original_scope = _get_scope(c)
    with_autonomy = _scope_with_app(original_scope, "autonomy")
    test_scope = _scope_with_app(with_autonomy, "approvals")
    events_before = _stash(_events_file())
    deadletter_before = _stash(_deadletter_file())
    last_dispatch_before = _stash(_last_dispatch_file())
    approvals_before = _stash(_approvals_file())
    decisions_before = _stash(_decisions_file())

    try:
        _set_scope(c, test_scope)
        _set_mode(c, "pilot", kill_switch=False)
        _restore(_events_file(), "")
        _restore(_deadletter_file(), "")
        _restore(_last_dispatch_file(), "{}")
        _restore(_approvals_file(), "")
        _restore(_decisions_file(), "")

        enqueue = c.post(
            "/autonomy/events",
            json={
                "event_type": "telemetry.critical_present",
                "source": "telemetry",
                "priority": "critical",
                "payload": {"count": 1},
            },
        )
        assert enqueue.status_code == 200
        assert enqueue.json()["event"]["risk_tier"] in {"high", "critical"}

        blocked = c.post(
            "/autonomy/events/dispatch",
            json={
                "max_events": 1,
                "max_actions": 0,
                "max_runtime_seconds": 5,
                "allow_medium": False,
                "allow_high": False,
                "stop_on_critical": False,
            },
        )
        assert blocked.status_code == 403
        detail = blocked.json().get("detail", {})
        assert isinstance(detail, dict)
        assert detail.get("action") == "autonomy.dispatch.high_risk"
        approval_id = str(detail.get("approval_request_id", ""))
        assert approval_id

        decided = c.post(
            f"/approvals/{approval_id}/decision",
            json={"decision": "approved", "note": "allow high-risk autonomy dispatch"},
        )
        assert decided.status_code == 200

        dispatched = c.post(
            "/autonomy/events/dispatch",
            headers={"x-approval-id": approval_id},
            json={
                "max_events": 1,
                "max_actions": 0,
                "max_runtime_seconds": 5,
                "allow_medium": False,
                "allow_high": False,
                "stop_on_critical": False,
            },
        )
        assert dispatched.status_code == 200
        payload = dispatched.json()
        assert payload["status"] == "ok"
        assert payload["processed_count"] >= 1
        assert payload.get("approval_id") == approval_id
    finally:
        _restore(_events_file(), events_before)
        _restore(_deadletter_file(), deadletter_before)
        _restore(_last_dispatch_file(), last_dispatch_before)
        _restore(_approvals_file(), approvals_before)
        _restore(_decisions_file(), decisions_before)
        _set_scope(c, original_scope)
        _set_mode(c, str(original_mode.get("mode", "pilot")), bool(original_mode.get("kill_switch", False)))


def test_autonomy_collect_events_enqueues_filtered_reactor_signals() -> None:
    c = TestClient(app)
    original_mode = _get_mode(c)
    original_scope = _get_scope(c)
    test_scope = _scope_with_app(original_scope, "autonomy")
    events_before = _stash(_events_file())
    incidents_before = _stash(_incidents_file())

    try:
        _set_scope(c, test_scope)
        _set_mode(c, "pilot", kill_switch=False)
        _restore(_events_file(), "")
        _restore(
            _incidents_file(),
            (
                '{"id":"inc-1","ts":"2026-01-01T00:00:00+00:00","run_id":"r-1",'
                '"severity":"critical","kind":"incident.test","message":"collect test","status":"open"}\n'
            ),
        )

        collected = c.post(
            "/autonomy/events/collect",
            json={"max_events": 10, "include_types": ["incident.critical_open"]},
        )
        assert collected.status_code == 200
        payload = collected.json()
        assert payload["status"] == "ok"
        assert payload["seen_count"] >= 1
        assert payload["queued_count"] >= 1
        assert any(str(item.get("event_type", "")) == "incident.critical_open" for item in payload.get("queued", []))

        collected_again = c.post(
            "/autonomy/events/collect",
            json={"max_events": 10, "include_types": ["incident.critical_open"]},
        )
        assert collected_again.status_code == 200
        second_payload = collected_again.json()
        assert second_payload["duplicate_count"] >= 1
    finally:
        _restore(_events_file(), events_before)
        _restore(_incidents_file(), incidents_before)
        _set_scope(c, original_scope)
        _set_mode(c, str(original_mode.get("mode", "pilot")), bool(original_mode.get("kill_switch", False)))


def test_autonomy_recover_requeues_expired_leases() -> None:
    c = TestClient(app)
    original_mode = _get_mode(c)
    original_scope = _get_scope(c)
    test_scope = _scope_with_app(original_scope, "autonomy")
    events_before = _stash(_events_file())

    try:
        _set_scope(c, test_scope)
        _set_mode(c, "pilot", kill_switch=False)
        _restore(
            _events_file(),
            (
                '{"id":"evt-1","ts":"2026-01-01T00:00:00+00:00","run_id":"r-1","kind":"autonomy.event",'
                '"event_type":"manual.recover","source":"pytest","priority":"high","risk_tier":"medium",'
                '"payload":{"x":1},"status":"leased","attempts":1,"next_run_after":"2026-01-01T00:00:00+00:00",'
                '"dedupe_key":"recover-test","lease_id":"lease-1","lease_owner":"worker-x",'
                '"leased_at":"2020-01-01T00:00:00+00:00","lease_expires_at":"2020-01-01T00:05:00+00:00",'
                '"completed_at":null,"dispatch_run_id":null,"error":null}\n'
            ),
        )

        recovered = c.post("/autonomy/events/recover", json={"max_recover": 10, "lease_ttl_seconds": 60})
        assert recovered.status_code == 200
        payload = recovered.json()
        assert payload["status"] == "ok"
        recovery = payload.get("recovery", {})
        assert int(recovery.get("recovered_count", 0)) >= 1
        queue = payload.get("queue", {})
        assert int(queue.get("queued_count", 0)) >= 1
        assert int(queue.get("leased_count", 0)) == 0
    finally:
        _restore(_events_file(), events_before)
        _set_scope(c, original_scope)
        _set_mode(c, str(original_mode.get("mode", "pilot")), bool(original_mode.get("kill_switch", False)))


def test_autonomy_dispatch_history_endpoint_returns_receipts() -> None:
    c = TestClient(app)
    original_mode = _get_mode(c)
    original_scope = _get_scope(c)
    test_scope = _scope_with_app(original_scope, "autonomy")
    events_before = _stash(_events_file())
    deadletter_before = _stash(_deadletter_file())
    last_dispatch_before = _stash(_last_dispatch_file())
    history_before = _stash(_dispatch_history_file())

    try:
        _set_scope(c, test_scope)
        _set_mode(c, "pilot", kill_switch=False)
        _restore(_events_file(), "")
        _restore(_deadletter_file(), "")
        _restore(_last_dispatch_file(), "{}")
        _restore(_dispatch_history_file(), "")

        enqueue = c.post(
            "/autonomy/events",
            json={
                "event_type": "manual.history_test",
                "source": "pytest",
                "priority": "normal",
                "payload": {"test": True},
            },
        )
        assert enqueue.status_code == 200

        dispatch = c.post(
            "/autonomy/events/dispatch",
            json={
                "max_events": 1,
                "max_actions": 0,
                "max_runtime_seconds": 5,
                "allow_medium": False,
                "allow_high": False,
                "stop_on_critical": False,
            },
        )
        assert dispatch.status_code == 200
        dispatch_payload = dispatch.json()
        assert dispatch_payload["status"] == "ok"
        run_id = dispatch_payload["run_id"]

        history = c.get("/autonomy/events/history", params={"limit": 10})
        assert history.status_code == 200
        payload = history.json()
        assert payload["status"] == "ok"
        assert payload["count"] >= 1
        rows = payload.get("history", [])
        assert any(str(item.get("run_id", "")) == run_id for item in rows)
    finally:
        _restore(_events_file(), events_before)
        _restore(_deadletter_file(), deadletter_before)
        _restore(_last_dispatch_file(), last_dispatch_before)
        _restore(_dispatch_history_file(), history_before)
        _set_scope(c, original_scope)
        _set_mode(c, str(original_mode.get("mode", "pilot")), bool(original_mode.get("kill_switch", False)))


def test_autonomy_dispatch_halts_when_critical_incident_open() -> None:
    c = TestClient(app)
    original_mode = _get_mode(c)
    original_scope = _get_scope(c)
    test_scope = _scope_with_app(original_scope, "autonomy")
    events_before = _stash(_events_file())
    deadletter_before = _stash(_deadletter_file())
    last_dispatch_before = _stash(_last_dispatch_file())
    incidents_before = _stash(_incidents_file())

    try:
        _set_scope(c, test_scope)
        _set_mode(c, "pilot", kill_switch=False)
        _restore(_events_file(), "")
        _restore(_deadletter_file(), "")
        _restore(_last_dispatch_file(), "{}")
        _restore(
            _incidents_file(),
            (
                '{"id":"inc-critical","ts":"2026-01-01T00:00:00+00:00","run_id":"r-critical",'
                '"severity":"critical","kind":"incident.critical","message":"critical open",'
                '"status":"open"}\n'
            ),
        )

        enqueue = c.post(
            "/autonomy/events",
            json={
                "event_type": "manual.critical_halt_test",
                "source": "pytest",
                "priority": "normal",
            },
        )
        assert enqueue.status_code == 200

        dispatch = c.post(
            "/autonomy/events/dispatch",
            json={
                "max_events": 1,
                "max_actions": 1,
                "max_runtime_seconds": 5,
                "stop_on_critical": True,
            },
        )
        assert dispatch.status_code == 200
        payload = dispatch.json()
        assert payload["status"] == "ok"
        assert payload["halted_reason"] == "critical_incident_present"
        assert payload["leased_count"] == 0
        assert payload["processed_count"] == 0
        assert payload["failed_count"] == 0
        assert int(payload.get("critical_incident_count", 0)) >= 1
        verification = payload.get("verification", {})
        assert verification.get("verification_status") == "blocked"
        assert verification.get("confidence") == "uncertain"
        assert verification.get("can_claim_done") is False
        assert payload.get("completion_state") == "incomplete"
        assert payload.get("trust_badge") == "Uncertain"

        queue = payload.get("queue", {})
        assert int(queue.get("queued_count", 0)) >= 1
    finally:
        _restore(_events_file(), events_before)
        _restore(_deadletter_file(), deadletter_before)
        _restore(_last_dispatch_file(), last_dispatch_before)
        _restore(_incidents_file(), incidents_before)
        _set_scope(c, original_scope)
        _set_mode(c, str(original_mode.get("mode", "pilot")), bool(original_mode.get("kill_switch", False)))


def test_autonomy_dispatch_action_budget_requeues_remaining_events() -> None:
    c = TestClient(app)
    original_mode = _get_mode(c)
    original_scope = _get_scope(c)
    test_scope = _scope_with_app(original_scope, "autonomy")
    events_before = _stash(_events_file())
    deadletter_before = _stash(_deadletter_file())
    worker_deadletter_before = _stash(_worker_deadletter_file())
    last_dispatch_before = _stash(_last_dispatch_file())

    try:
        _set_scope(c, test_scope)
        _set_mode(c, "pilot", kill_switch=False)
        _restore(_events_file(), "")
        _restore(_deadletter_file(), "")
        _restore(_last_dispatch_file(), "{}")
        _restore(
            _worker_deadletter_file(),
            (
                '{"id":"queue-dl-1","ts":"2026-01-01T00:00:00+00:00","run_id":"r-dl",'
                '"kind":"job.deadletter","action":"mission.tick","error":"forced test deadletter"}\n'
            ),
        )

        enqueue_one = c.post(
            "/autonomy/events",
            json={
                "event_type": "manual.dispatch_budget_test.1",
                "source": "pytest",
                "priority": "normal",
            },
        )
        assert enqueue_one.status_code == 200

        enqueue_two = c.post(
            "/autonomy/events",
            json={
                "event_type": "manual.dispatch_budget_test.2",
                "source": "pytest",
                "priority": "normal",
            },
        )
        assert enqueue_two.status_code == 200

        dispatch = c.post(
            "/autonomy/events/dispatch",
            json={
                "max_events": 2,
                "max_actions": 1,
                "max_runtime_seconds": 10,
                "max_dispatch_actions": 0,
                "max_dispatch_runtime_seconds": 30,
                "allow_medium": False,
                "allow_high": False,
                "stop_on_critical": False,
            },
        )
        assert dispatch.status_code == 200
        payload = dispatch.json()
        assert payload["status"] == "ok"
        assert payload["leased_count"] == 2
        assert payload["processed_count"] == 0
        assert payload["failed_count"] == 0
        assert payload["released_count"] == 2
        assert payload["halted_reason"] == "dispatch_action_budget_exceeded"
        assert int(payload.get("dispatch_executed_actions", 0)) == 0

        queue = c.get("/autonomy/events/queue")
        assert queue.status_code == 200
        q = queue.json().get("queue", {})
        assert int(q.get("queued_count", 0)) >= 2
        assert int(q.get("dispatched_count", 0)) == 0
    finally:
        _restore(_events_file(), events_before)
        _restore(_deadletter_file(), deadletter_before)
        _restore(_worker_deadletter_file(), worker_deadletter_before)
        _restore(_last_dispatch_file(), last_dispatch_before)
        _set_scope(c, original_scope)
        _set_mode(c, str(original_mode.get("mode", "pilot")), bool(original_mode.get("kill_switch", False)))


def test_autonomy_dispatch_runtime_budget_requeues_remaining_events() -> None:
    c = TestClient(app)
    original_mode = _get_mode(c)
    original_scope = _get_scope(c)
    test_scope = _scope_with_app(original_scope, "autonomy")
    events_before = _stash(_events_file())
    deadletter_before = _stash(_deadletter_file())
    last_dispatch_before = _stash(_last_dispatch_file())

    try:
        _set_scope(c, test_scope)
        _set_mode(c, "pilot", kill_switch=False)
        _restore(_events_file(), "")
        _restore(_deadletter_file(), "")
        _restore(_last_dispatch_file(), "{}")

        enqueue_one = c.post(
            "/autonomy/events",
            json={
                "event_type": "manual.dispatch_runtime_test.1",
                "source": "pytest",
                "priority": "normal",
            },
        )
        assert enqueue_one.status_code == 200

        enqueue_two = c.post(
            "/autonomy/events",
            json={
                "event_type": "manual.dispatch_runtime_test.2",
                "source": "pytest",
                "priority": "normal",
            },
        )
        assert enqueue_two.status_code == 200

        monotonic_tick = {"value": 0}

        def _fake_monotonic() -> float:
            monotonic_tick["value"] += 1
            return float(monotonic_tick["value"] * 100)

        with patch(
            "services.orchestrator.app.routes.autonomy.time.monotonic",
            side_effect=_fake_monotonic,
        ):
            dispatch = c.post(
                "/autonomy/events/dispatch",
                json={
                    "max_events": 2,
                    "max_actions": 1,
                    "max_runtime_seconds": 10,
                    "max_dispatch_actions": 10,
                    "max_dispatch_runtime_seconds": 30,
                    "allow_medium": False,
                    "allow_high": False,
                    "stop_on_critical": False,
                },
            )

        assert dispatch.status_code == 200
        payload = dispatch.json()
        assert payload["status"] == "ok"
        assert payload["leased_count"] == 2
        assert payload["processed_count"] == 0
        assert payload["failed_count"] == 0
        assert payload["released_count"] == 2
        assert payload["halted_reason"] == "dispatch_runtime_budget_exceeded"

        queue = c.get("/autonomy/events/queue")
        assert queue.status_code == 200
        q = queue.json().get("queue", {})
        assert int(q.get("queued_count", 0)) >= 2
        assert int(q.get("dispatched_count", 0)) == 0
    finally:
        _restore(_events_file(), events_before)
        _restore(_deadletter_file(), deadletter_before)
        _restore(_last_dispatch_file(), last_dispatch_before)
        _set_scope(c, original_scope)
        _set_mode(c, str(original_mode.get("mode", "pilot")), bool(original_mode.get("kill_switch", False)))


def test_autonomy_dispatch_failure_retries_with_backoff() -> None:
    c = TestClient(app)
    original_mode = _get_mode(c)
    original_scope = _get_scope(c)
    test_scope = _scope_with_app(original_scope, "autonomy")
    events_before = _stash(_events_file())
    deadletter_before = _stash(_deadletter_file())
    last_dispatch_before = _stash(_last_dispatch_file())

    try:
        _set_scope(c, test_scope)
        _set_mode(c, "pilot", kill_switch=False)
        _restore(_events_file(), "")
        _restore(_deadletter_file(), "")
        _restore(_last_dispatch_file(), "{}")

        enqueue = c.post(
            "/autonomy/events",
            json={
                "event_type": "manual.retry_test",
                "source": "pytest",
                "priority": "normal",
            },
        )
        assert enqueue.status_code == 200

        with patch("services.orchestrator.app.routes.autonomy.run_cycle", side_effect=RuntimeError("dispatch boom")):
            dispatch = c.post(
                "/autonomy/events/dispatch",
                json={
                    "max_events": 1,
                    "max_actions": 1,
                    "max_runtime_seconds": 5,
                    "max_attempts": 2,
                    "retry_backoff_seconds": 120,
                    "allow_medium": False,
                    "allow_high": False,
                    "stop_on_critical": False,
                },
            )
        assert dispatch.status_code == 200
        payload = dispatch.json()
        assert payload["status"] == "ok"
        assert payload["processed_count"] == 0
        assert payload["failed_count"] == 0
        assert payload["retried_count"] == 1
        queue = payload.get("queue", {})
        assert int(queue.get("queued_count", 0)) >= 1
        assert int(queue.get("deadletter_count", 0)) == 0
        queued_rows = queue.get("queued", [])
        assert queued_rows
        retry_row = queued_rows[-1]
        assert int(retry_row.get("retry_backoff_seconds", 0)) == 120
        next_run_after = str(retry_row.get("next_run_after", ""))
        parsed = datetime.fromisoformat(next_run_after.replace("Z", "+00:00"))
        assert parsed > datetime.now(timezone.utc)
    finally:
        _restore(_events_file(), events_before)
        _restore(_deadletter_file(), deadletter_before)
        _restore(_last_dispatch_file(), last_dispatch_before)
        _set_scope(c, original_scope)
        _set_mode(c, str(original_mode.get("mode", "pilot")), bool(original_mode.get("kill_switch", False)))


def test_autonomy_dispatch_failure_exhausts_attempts_to_deadletter() -> None:
    c = TestClient(app)
    original_mode = _get_mode(c)
    original_scope = _get_scope(c)
    test_scope = _scope_with_app(original_scope, "autonomy")
    events_before = _stash(_events_file())
    deadletter_before = _stash(_deadletter_file())
    last_dispatch_before = _stash(_last_dispatch_file())

    try:
        _set_scope(c, test_scope)
        _set_mode(c, "pilot", kill_switch=False)
        _restore(_events_file(), "")
        _restore(_deadletter_file(), "")
        _restore(_last_dispatch_file(), "{}")

        enqueue = c.post(
            "/autonomy/events",
            json={
                "event_type": "manual.retry_exhausted_test",
                "source": "pytest",
                "priority": "normal",
            },
        )
        assert enqueue.status_code == 200

        with patch("services.orchestrator.app.routes.autonomy.run_cycle", side_effect=RuntimeError("dispatch boom")):
            dispatch = c.post(
                "/autonomy/events/dispatch",
                json={
                    "max_events": 1,
                    "max_actions": 1,
                    "max_runtime_seconds": 5,
                    "max_attempts": 1,
                    "retry_backoff_seconds": 60,
                    "allow_medium": False,
                    "allow_high": False,
                    "stop_on_critical": False,
                },
            )
        assert dispatch.status_code == 200
        payload = dispatch.json()
        assert payload["status"] == "ok"
        assert payload["processed_count"] == 0
        assert payload["failed_count"] == 1
        assert payload["retried_count"] == 0
        queue = payload.get("queue", {})
        assert int(queue.get("failed_count", 0)) >= 1
        assert int(queue.get("deadletter_count", 0)) >= 1
    finally:
        _restore(_events_file(), events_before)
        _restore(_deadletter_file(), deadletter_before)
        _restore(_last_dispatch_file(), last_dispatch_before)
        _set_scope(c, original_scope)
        _set_mode(c, str(original_mode.get("mode", "pilot")), bool(original_mode.get("kill_switch", False)))


def test_autonomy_reactor_tick_collects_then_dispatches() -> None:
    c = TestClient(app)
    original_mode = _get_mode(c)
    original_scope = _get_scope(c)
    test_scope = _scope_with_app(original_scope, "autonomy")
    events_before = _stash(_events_file())
    deadletter_before = _stash(_deadletter_file())
    worker_deadletter_before = _stash(_worker_deadletter_file())
    last_dispatch_before = _stash(_last_dispatch_file())
    last_tick_before = _stash(_last_tick_file())
    tick_history_before = _stash(_tick_history_file())

    try:
        _set_scope(c, test_scope)
        _set_mode(c, "pilot", kill_switch=False)
        _restore(_events_file(), "")
        _restore(_deadletter_file(), "")
        _restore(_last_dispatch_file(), "{}")
        _restore(_last_tick_file(), "{}")
        _restore(_tick_history_file(), "")
        _restore(
            _worker_deadletter_file(),
            (
                '{"id":"queue-dl-reactor","ts":"2026-01-01T00:00:00+00:00","run_id":"r-reactor",'
                '"kind":"job.deadletter","action":"mission.tick","error":"reactor signal"}\n'
            ),
        )

        tick = c.post(
            "/autonomy/reactor/tick",
            json={
                "max_collect_events": 10,
                "include_types": ["queue.deadletter_present"],
                "max_events": 5,
                "max_actions": 0,
                "max_runtime_seconds": 5,
                "allow_medium": True,
                "allow_high": False,
                "stop_on_critical": False,
            },
        )
        assert tick.status_code == 200
        payload = tick.json()
        assert payload["status"] == "ok"
        collect = payload.get("collect", {})
        dispatch = payload.get("dispatch", {})
        verification = payload.get("verification", {})
        assert collect.get("status") == "ok"
        assert int(collect.get("queued_count", 0)) >= 1
        assert dispatch.get("status") == "ok"
        assert int(dispatch.get("leased_count", 0)) >= 1
        assert int(dispatch.get("processed_count", 0)) >= 1
        assert verification.get("verification_status") in {"verified", "partial", "uncertain"}
        assert verification.get("confidence") in {"confirmed", "likely", "uncertain"}
        assert payload.get("completion_state") in {"done", "incomplete"}
        assert payload.get("trust_badge") in {"Confirmed", "Likely", "Uncertain"}

        tick_summary = payload.get("tick", {})
        assert tick_summary.get("kind") == "autonomy.reactor.tick"
        assert tick_summary.get("run_id") == payload.get("run_id")
        tick_verification = tick_summary.get("verification", {})
        assert tick_verification.get("verification_status") in {"verified", "partial", "uncertain", "blocked"}
        assert tick_verification.get("confidence") in {"confirmed", "likely", "uncertain"}
        assert tick_summary.get("completion_state") in {"done", "incomplete"}
        assert tick_summary.get("trust_badge") in {"Confirmed", "Likely", "Uncertain"}

        last = c.get("/autonomy/reactor/last")
        assert last.status_code == 200
        last_tick = last.json().get("last_tick", {})
        assert last_tick.get("run_id") == payload.get("run_id")
        assert last_tick.get("kind") == "autonomy.reactor.tick"

        history = c.get("/autonomy/reactor/history", params={"limit": 10})
        assert history.status_code == 200
        history_payload = history.json()
        assert history_payload.get("status") == "ok"
        assert int(history_payload.get("count", 0)) >= 1
        rows = history_payload.get("history", [])
        assert any(str(item.get("run_id", "")) == str(payload.get("run_id")) for item in rows)
    finally:
        _restore(_events_file(), events_before)
        _restore(_deadletter_file(), deadletter_before)
        _restore(_worker_deadletter_file(), worker_deadletter_before)
        _restore(_last_dispatch_file(), last_dispatch_before)
        _restore(_last_tick_file(), last_tick_before)
        _restore(_tick_history_file(), tick_history_before)
        _set_scope(c, original_scope)
        _set_mode(c, str(original_mode.get("mode", "pilot")), bool(original_mode.get("kill_switch", False)))


def test_autonomy_reactor_guardrail_cooldown_on_retry_pressure() -> None:
    c = TestClient(app)
    original_mode = _get_mode(c)
    original_scope = _get_scope(c)
    test_scope = _scope_with_app(original_scope, "autonomy")
    events_before = _stash(_events_file())
    deadletter_before = _stash(_deadletter_file())
    last_dispatch_before = _stash(_last_dispatch_file())
    last_tick_before = _stash(_last_tick_file())
    tick_history_before = _stash(_tick_history_file())
    guardrail_before = _stash(_guardrail_file())
    guardrail_history_before = _stash(_guardrail_history_file())

    try:
        _set_scope(c, test_scope)
        _set_mode(c, "pilot", kill_switch=False)
        _restore(
            _events_file(),
            (
                '{"id":"evt-retry-1","ts":"2026-01-01T00:00:00+00:00","run_id":"r-retry","kind":"autonomy.event",'
                '"event_type":"manual.retry_pressure","source":"pytest","priority":"normal","risk_tier":"low",'
                '"payload":{},"status":"queued","attempts":2,"next_run_after":"2020-01-01T00:00:00+00:00",'
                '"dedupe_key":"retry-pressure","lease_id":null,"lease_owner":null,"leased_at":null,'
                '"completed_at":null,"dispatch_run_id":null,"error":"retry pending","last_error":"retry pending",'
                '"last_failed_at":"2026-01-01T00:00:00+00:00","retry_backoff_seconds":120,"max_attempts":3}\n'
            ),
        )
        _restore(_deadletter_file(), "")
        _restore(_last_dispatch_file(), "{}")
        _restore(_last_tick_file(), "{}")
        _restore(_tick_history_file(), "")
        _restore(_guardrail_file(), "{}")
        _restore(_guardrail_history_file(), "")

        tick1 = c.post(
            "/autonomy/reactor/tick",
            json={
                "max_collect_events": 1,
                "include_types": ["observer.scan_due"],
                "max_events": 1,
                "max_actions": 0,
                "max_dispatch_actions": 0,
                "stop_on_critical": False,
                "retry_pressure_threshold": 1,
                "retry_pressure_consecutive_ticks": 2,
                "retry_pressure_cooldown_ticks": 2,
            },
        )
        assert tick1.status_code == 200
        payload1 = tick1.json()
        guardrail1 = payload1.get("guardrail", {})
        assert guardrail1.get("cooldown_active") is False
        assert int(guardrail1.get("state_after", {}).get("consecutive_retry_pressure_ticks", 0)) == 1

        tick2 = c.post(
            "/autonomy/reactor/tick",
            json={
                "max_collect_events": 1,
                "include_types": ["observer.scan_due"],
                "max_events": 1,
                "max_actions": 0,
                "max_dispatch_actions": 0,
                "stop_on_critical": False,
                "retry_pressure_threshold": 1,
                "retry_pressure_consecutive_ticks": 2,
                "retry_pressure_cooldown_ticks": 2,
            },
        )
        assert tick2.status_code == 200
        payload2 = tick2.json()
        guardrail2 = payload2.get("guardrail", {})
        assert guardrail2.get("cooldown_active") is True
        assert guardrail2.get("escalated") is True
        assert payload2.get("dispatch", {}).get("halted_reason") == "retry_pressure_cooldown"

        tick3 = c.post(
            "/autonomy/reactor/tick",
            json={
                "max_collect_events": 1,
                "include_types": ["observer.scan_due"],
                "max_events": 1,
                "max_actions": 0,
                "max_dispatch_actions": 0,
                "stop_on_critical": False,
                "retry_pressure_threshold": 1,
                "retry_pressure_consecutive_ticks": 2,
                "retry_pressure_cooldown_ticks": 2,
            },
        )
        assert tick3.status_code == 200
        payload3 = tick3.json()
        guardrail3 = payload3.get("guardrail", {})
        assert guardrail3.get("cooldown_active") is True
        assert payload3.get("dispatch", {}).get("halted_reason") == "retry_pressure_cooldown"

        guardrail_read = c.get("/autonomy/reactor/guardrail")
        assert guardrail_read.status_code == 200
        g = guardrail_read.json().get("guardrail", {})
        assert int(g.get("escalations_count", 0)) >= 1
        assert int(g.get("tick_count", 0)) >= 3

        guardrail_history = c.get("/autonomy/reactor/guardrail/history", params={"limit": 20})
        assert guardrail_history.status_code == 200
        history_payload = guardrail_history.json()
        assert history_payload.get("status") == "ok"
        rows = history_payload.get("history", [])
        assert len(rows) >= 3
        assert any(str(item.get("kind", "")) == "autonomy.reactor.guardrail.tick" for item in rows)
    finally:
        _restore(_events_file(), events_before)
        _restore(_deadletter_file(), deadletter_before)
        _restore(_last_dispatch_file(), last_dispatch_before)
        _restore(_last_tick_file(), last_tick_before)
        _restore(_tick_history_file(), tick_history_before)
        _restore(_guardrail_file(), guardrail_before)
        _restore(_guardrail_history_file(), guardrail_history_before)
        _set_scope(c, original_scope)
        _set_mode(c, str(original_mode.get("mode", "pilot")), bool(original_mode.get("kill_switch", False)))


def test_autonomy_reactor_guardrail_reset_requires_pilot_and_updates_receipts() -> None:
    c = TestClient(app)
    original_mode = _get_mode(c)
    original_scope = _get_scope(c)
    test_scope = _scope_with_app(original_scope, "autonomy")
    guardrail_before = _stash(_guardrail_file())
    guardrail_history_before = _stash(_guardrail_history_file())

    try:
        _set_scope(c, test_scope)
        _set_mode(c, "pilot", kill_switch=False)
        _restore(
            _guardrail_file(),
            (
                '{'
                '"tick_count":12,'
                '"consecutive_retry_pressure_ticks":0,'
                '"cooldown_remaining_ticks":2,'
                '"escalations_count":4,'
                '"last_retry_pressure_count":3,'
                '"last_reason":"retry_pressure_cooldown"'
                '}'
            ),
        )
        _restore(_guardrail_history_file(), "")

        denied = c.post(
            "/autonomy/reactor/guardrail/reset",
            headers={"x-francis-role": "observer"},
            json={"reason": "observer denied"},
        )
        assert denied.status_code == 403
        assert "RBAC denied" in str(denied.json().get("detail", ""))

        away_mode = c.put("/control/mode", json={"mode": "away", "kill_switch": False})
        assert away_mode.status_code == 200
        blocked = c.post("/autonomy/reactor/guardrail/reset", json={"reason": "away denied"})
        assert blocked.status_code == 403
        assert "Control denied" in str(blocked.json().get("detail", ""))

        _set_mode(c, "pilot", kill_switch=False)
        reset = c.post("/autonomy/reactor/guardrail/reset", json={"reason": "manual recovery"})
        assert reset.status_code == 200
        payload = reset.json()
        receipt = payload.get("receipt", {})
        assert receipt.get("kind") == "autonomy.reactor.guardrail.reset"
        assert receipt.get("reason") == "manual recovery"
        after = receipt.get("after", {})
        assert int(after.get("cooldown_remaining_ticks", 0)) == 0
        assert int(after.get("consecutive_retry_pressure_ticks", 0)) == 0
        assert int(after.get("escalations_count", 0)) == 4

        history = c.get("/autonomy/reactor/guardrail/history", params={"limit": 10})
        assert history.status_code == 200
        rows = history.json().get("history", [])
        assert any(str(item.get("kind", "")) == "autonomy.reactor.guardrail.reset" for item in rows)
    finally:
        _restore(_guardrail_file(), guardrail_before)
        _restore(_guardrail_history_file(), guardrail_history_before)
        _set_scope(c, original_scope)
        _set_mode(c, str(original_mode.get("mode", "pilot")), bool(original_mode.get("kill_switch", False)))


def test_receipts_trust_latest_filters_by_run_and_trace() -> None:
    c = TestClient(app)
    original_mode = _get_mode(c)
    original_scope = _get_scope(c)
    test_scope = _scope_with_app(original_scope, "autonomy")
    events_before = _stash(_events_file())
    deadletter_before = _stash(_deadletter_file())
    last_dispatch_before = _stash(_last_dispatch_file())
    dispatch_history_before = _stash(_dispatch_history_file())
    last_tick_before = _stash(_last_tick_file())
    tick_history_before = _stash(_tick_history_file())

    try:
        _set_scope(c, test_scope)
        _set_mode(c, "pilot", kill_switch=False)
        _restore(_events_file(), "")
        _restore(_deadletter_file(), "")
        _restore(_last_dispatch_file(), "{}")
        _restore(_dispatch_history_file(), "")
        _restore(_last_tick_file(), "{}")
        _restore(_tick_history_file(), "")

        enqueue = c.post(
            "/autonomy/events",
            json={
                "event_type": "manual.trust_receipt_test",
                "source": "pytest",
                "priority": "normal",
                "payload": {"test": True},
            },
        )
        assert enqueue.status_code == 200

        dispatch = c.post(
            "/autonomy/events/dispatch",
            json={
                "max_events": 1,
                "max_actions": 0,
                "max_runtime_seconds": 5,
                "allow_medium": False,
                "allow_high": False,
                "stop_on_critical": False,
            },
        )
        assert dispatch.status_code == 200
        dispatch_payload = dispatch.json()
        dispatch_run_id = str(dispatch_payload.get("run_id", ""))
        assert dispatch_run_id
        assert str(dispatch_payload.get("trace_id", "")) == dispatch_run_id

        all_rows = c.get("/receipts/trust/latest", params={"limit": 50})
        assert all_rows.status_code == 200
        all_payload = all_rows.json()
        assert all_payload["status"] == "ok"
        rows = all_payload.get("trust_receipts", [])
        assert any(str(item.get("run_id", "")) == dispatch_run_id for item in rows)

        by_run = c.get("/receipts/trust/latest", params={"run_id": dispatch_run_id, "limit": 50})
        assert by_run.status_code == 200
        by_run_rows = by_run.json().get("trust_receipts", [])
        assert by_run_rows
        assert all(
            str(item.get("run_id", "")) == dispatch_run_id or str(item.get("trace_id", "")) == dispatch_run_id
            for item in by_run_rows
        )

        by_trace = c.get("/receipts/trust/latest", params={"trace_id": dispatch_run_id, "limit": 50})
        assert by_trace.status_code == 200
        by_trace_rows = by_trace.json().get("trust_receipts", [])
        assert by_trace_rows
        assert all(str(item.get("trace_id", "")) == dispatch_run_id for item in by_trace_rows)
        assert all("verification_status" in item and "confidence" in item for item in by_trace_rows)
    finally:
        _restore(_events_file(), events_before)
        _restore(_deadletter_file(), deadletter_before)
        _restore(_last_dispatch_file(), last_dispatch_before)
        _restore(_dispatch_history_file(), dispatch_history_before)
        _restore(_last_tick_file(), last_tick_before)
        _restore(_tick_history_file(), tick_history_before)
        _set_scope(c, original_scope)
        _set_mode(c, str(original_mode.get("mode", "pilot")), bool(original_mode.get("kill_switch", False)))
