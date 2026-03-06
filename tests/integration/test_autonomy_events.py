from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from apps.api.main import app


def _workspace_root() -> Path:
    return Path(__file__).resolve().parents[2] / "workspace"


def _events_file() -> Path:
    return _workspace_root() / "autonomy" / "events.jsonl"


def _deadletter_file() -> Path:
    return _workspace_root() / "autonomy" / "deadletter.jsonl"


def _last_dispatch_file() -> Path:
    return _workspace_root() / "autonomy" / "last_dispatch.json"


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
