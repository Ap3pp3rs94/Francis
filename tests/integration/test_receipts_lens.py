from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

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


def _get_takeover(client: TestClient) -> dict:
    response = client.get("/control/takeover")
    assert response.status_code == 200
    return response.json()["takeover"]


def _ensure_takeover_idle(client: TestClient) -> None:
    current = _get_takeover(client)
    status = str(current.get("status", "idle")).strip().lower()
    if status == "requested":
        client.post("/control/takeover/confirm", json={"confirm": True, "mode": "pilot", "reason": "test reset"})
        status = "active"
    if status == "active":
        client.post(
            "/control/takeover/handback",
            json={"summary": "test reset", "verification": {}, "pending_approvals": 0, "mode": "assist"},
        )


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


def test_receipts_and_run_lookup() -> None:
    c = TestClient(app)

    mode = c.put("/control/mode", json={"mode": "pilot", "kill_switch": False})
    assert mode.status_code == 200

    create = c.post(
        "/missions",
        json={"title": f"Receipt-{uuid4()}", "objective": "Receipts", "steps": ["s1"]},
    )
    assert create.status_code == 200
    run_id = create.json()["run_id"]

    latest = c.get("/receipts/latest")
    assert latest.status_code == 200
    latest_payload = latest.json()
    assert latest_payload["status"] == "ok"
    receipts = latest_payload["receipts"]
    assert "ledger" in receipts
    assert "decisions" in receipts
    assert "logs" in receipts

    run = c.get(f"/runs/{run_id}")
    assert run.status_code == 200
    run_payload = run.json()
    assert run_payload["status"] == "ok"
    assert run_payload["run_id"] == run_id
    assert run_payload["count"] >= 1


def test_receipts_trust_latest_endpoint_available() -> None:
    c = TestClient(app)
    mode = c.put("/control/mode", json={"mode": "pilot", "kill_switch": False})
    assert mode.status_code == 200

    trust = c.get("/receipts/trust/latest", params={"limit": 10})
    assert trust.status_code == 200
    payload = trust.json()
    assert payload["status"] == "ok"
    assert "trust_receipts" in payload
    assert "filters" in payload


def test_lens_state_and_actions() -> None:
    c = TestClient(app)
    mode = c.put("/control/mode", json={"mode": "pilot", "kill_switch": False})
    assert mode.status_code == 200

    state = c.get("/lens/state")
    assert state.status_code == 200
    state_payload = state.json()
    assert state_payload["status"] == "ok"
    assert "mode" in state_payload
    assert "scope" in state_payload
    assert "intent_state" in state_payload
    assert "event_state" in state_payload
    assert "control_surface" in state_payload
    control_surface = state_payload["control_surface"]
    assert control_surface.get("pilot_mode_on") is True
    pilot_indicator = control_surface.get("pilot_indicator", {})
    assert pilot_indicator.get("visible") is True
    assert pilot_indicator.get("status") == "on"

    actions = c.get("/lens/actions")
    assert actions.status_code == 200
    actions_payload = actions.json()
    assert actions_payload["status"] == "ok"
    assert isinstance(actions_payload.get("action_chips"), list)
    assert "selected_actions" in actions_payload
    assert "blocked_actions" in actions_payload
    assert any(chip.get("kind") == "control.panic" for chip in actions_payload.get("action_chips", []))


def test_lens_execute_control_panic_resume_and_indicator() -> None:
    c = TestClient(app)
    original_mode = _get_mode(c)
    original_scope = _get_scope(c)
    try:
        _set_mode(c, "pilot", kill_switch=False)
        _set_scope(c, _enable_apps(original_scope, ["lens", "control", "missions", "receipts"]))

        dry_run = c.post(
            "/lens/actions/execute",
            json={"kind": "control.panic", "dry_run": True, "args": {"reason": "dry run"}},
        )
        assert dry_run.status_code == 200
        assert dry_run.json()["status"] == "dry_run"
        assert _get_mode(c).get("kill_switch") is False

        panic = c.post(
            "/lens/actions/execute",
            json={"kind": "control.panic", "args": {"reason": "lens panic"}},
        )
        assert panic.status_code == 200
        panic_payload = panic.json()
        assert panic_payload["status"] == "ok"
        assert panic_payload["result"]["after"]["kill_switch"] is True

        state_after_panic = c.get("/lens/state")
        assert state_after_panic.status_code == 200
        indicator = state_after_panic.json().get("control_surface", {}).get("pilot_indicator", {})
        assert indicator.get("status") == "paused"

        blocked = c.post(
            "/missions",
            json={"title": f"LensPanic-{uuid4()}", "objective": "blocked", "steps": ["s1"]},
        )
        assert blocked.status_code == 403

        resume = c.post(
            "/lens/actions/execute",
            json={"kind": "control.resume", "args": {"mode": "pilot", "reason": "lens resume"}},
        )
        assert resume.status_code == 200
        resume_payload = resume.json()
        assert resume_payload["status"] == "ok"
        assert resume_payload["result"]["after"]["kill_switch"] is False

        state_after_resume = c.get("/lens/state")
        assert state_after_resume.status_code == 200
        indicator_after_resume = state_after_resume.json().get("control_surface", {}).get("pilot_indicator", {})
        assert indicator_after_resume.get("status") == "on"
    finally:
        _set_scope(c, original_scope)
        _set_mode(c, str(original_mode.get("mode", "pilot")), bool(original_mode.get("kill_switch", False)))


def test_lens_execute_worker_cycle_dry_run_records_trace_receipt() -> None:
    c = TestClient(app)
    original_mode = _get_mode(c)
    original_scope = _get_scope(c)
    trace_id = f"lens-exec-{uuid4()}"
    headers = {"x-trace-id": trace_id}
    try:
        _set_mode(c, "pilot", kill_switch=False)
        _set_scope(c, _enable_apps(original_scope, ["lens", "worker", "receipts"]))

        execute = c.post(
            "/lens/actions/execute",
            headers=headers,
            json={
                "kind": "worker.cycle",
                "dry_run": True,
                "args": {"max_jobs": 3, "max_runtime_seconds": 10, "action_allowlist": ["mission.tick"]},
            },
        )
        assert execute.status_code == 200
        payload = execute.json()
        assert payload["status"] == "dry_run"
        assert payload["trace_id"] == trace_id
        assert payload["result"]["kind"] == "worker.cycle"

        trace = c.get(f"/runs/trace/{trace_id}", params={"limit": 100})
        assert trace.status_code == 200
        decisions = trace.json().get("receipts", {}).get("decisions", [])
        assert any(
            str(row.get("kind", "")) == "lens.action.execute"
            and str(row.get("action_kind", "")) == "worker.cycle"
            and bool(row.get("dry_run", False))
            for row in decisions
        )
    finally:
        _set_scope(c, original_scope)
        _set_mode(c, str(original_mode.get("mode", "pilot")), bool(original_mode.get("kill_switch", False)))


def test_lens_execute_autonomy_dispatch_dry_run_supported() -> None:
    c = TestClient(app)
    original_mode = _get_mode(c)
    original_scope = _get_scope(c)
    try:
        _set_mode(c, "pilot", kill_switch=False)
        _set_scope(c, _enable_apps(original_scope, ["lens", "autonomy", "receipts"]))

        execute = c.post(
            "/lens/actions/execute",
            json={
                "kind": "autonomy.dispatch",
                "dry_run": True,
                "args": {
                    "max_events": 2,
                    "max_actions": 1,
                    "max_runtime_seconds": 5,
                    "max_dispatch_actions": 2,
                    "max_dispatch_runtime_seconds": 10,
                },
            },
        )
        assert execute.status_code == 200
        payload = execute.json()
        assert payload["status"] == "dry_run"
        assert payload["result"]["kind"] == "autonomy.dispatch"
        assert payload["result"]["execution_args"]["max_events"] == 2
    finally:
        _set_scope(c, original_scope)
        _set_mode(c, str(original_mode.get("mode", "pilot")), bool(original_mode.get("kill_switch", False)))


def test_lens_execute_autonomy_reactor_tick_dry_run_supported() -> None:
    c = TestClient(app)
    original_mode = _get_mode(c)
    original_scope = _get_scope(c)
    try:
        _set_mode(c, "pilot", kill_switch=False)
        _set_scope(c, _enable_apps(original_scope, ["lens", "autonomy", "receipts"]))

        execute = c.post(
            "/lens/actions/execute",
            json={
                "kind": "autonomy.reactor.tick",
                "dry_run": True,
                "args": {
                    "max_collect_events": 4,
                    "max_events": 2,
                    "max_actions": 1,
                    "max_runtime_seconds": 5,
                    "max_dispatch_actions": 2,
                    "max_dispatch_runtime_seconds": 10,
                },
            },
        )
        assert execute.status_code == 200
        payload = execute.json()
        assert payload["status"] == "dry_run"
        assert payload["result"]["kind"] == "autonomy.reactor.tick"
        assert payload["result"]["execution_args"]["max_collect_events"] == 4
    finally:
        _set_scope(c, original_scope)
        _set_mode(c, str(original_mode.get("mode", "pilot")), bool(original_mode.get("kill_switch", False)))


def test_lens_execute_forge_propose_supported() -> None:
    c = TestClient(app)
    original_mode = _get_mode(c)
    original_scope = _get_scope(c)
    try:
        _set_mode(c, "pilot", kill_switch=False)
        _set_scope(c, _enable_apps(original_scope, ["lens", "forge", "receipts"]))

        execute = c.post(
            "/lens/actions/execute",
            json={"kind": "forge.propose"},
        )
        assert execute.status_code == 200
        payload = execute.json()
        assert payload["status"] == "ok"
        assert payload["result"]["kind"] == "forge.propose"
        summary = payload["result"]["summary"]
        assert summary["status"] == "ok"
        assert isinstance(summary.get("proposals", []), list)
        assert "context" in summary
    finally:
        _set_scope(c, original_scope)
        _set_mode(c, str(original_mode.get("mode", "pilot")), bool(original_mode.get("kill_switch", False)))


def test_lens_state_surfaces_takeover_status() -> None:
    c = TestClient(app)
    original_mode = _get_mode(c)
    original_scope = _get_scope(c)
    try:
        _set_mode(c, "assist", kill_switch=False)
        _set_scope(c, _enable_apps(original_scope, ["lens", "control", "receipts", "approvals"]))
        _ensure_takeover_idle(c)

        requested = c.post(
            "/control/takeover/request",
            json={"objective": f"Lens takeover state {uuid4()}", "reason": "lens state test"},
        )
        assert requested.status_code == 200
        requested_objective = requested.json()["takeover"]["objective"]
        requested_session_id = str(requested.json()["takeover"].get("session_id", "")).strip()
        assert requested_session_id

        state_requested = c.get("/lens/state")
        assert state_requested.status_code == 200
        takeover_requested = state_requested.json().get("control_surface", {}).get("takeover", {})
        assert takeover_requested.get("status") == "requested"
        assert takeover_requested.get("pending_confirmation") is True
        assert takeover_requested.get("objective") == requested_objective
        assert str(takeover_requested.get("session_id", "")).strip() == requested_session_id
        assert int(takeover_requested.get("session_count", 0)) >= 1
        assert isinstance(takeover_requested.get("recent_sessions", []), list)
        assert any(
            str(row.get("kind", "")) == "control.takeover.requested"
            for row in takeover_requested.get("recent_activity", [])
        )

        confirmed = c.post("/control/takeover/confirm", json={"confirm": True, "reason": "lens confirm"})
        assert confirmed.status_code == 200

        state_active = c.get("/lens/state")
        assert state_active.status_code == 200
        takeover_active = state_active.json().get("control_surface", {}).get("takeover", {})
        assert takeover_active.get("status") == "active"
        assert takeover_active.get("active") is True
        assert str(takeover_active.get("session_id", "")).strip() == requested_session_id
        assert int(takeover_active.get("session_count", 0)) >= 1
        assert any(
            str(row.get("kind", "")) == "control.takeover.confirmed"
            for row in takeover_active.get("recent_activity", [])
        )
    finally:
        _ensure_takeover_idle(c)
        _set_scope(c, original_scope)
        _set_mode(c, str(original_mode.get("mode", "pilot")), bool(original_mode.get("kill_switch", False)))


def test_lens_execute_takeover_flow_supported() -> None:
    c = TestClient(app)
    original_mode = _get_mode(c)
    original_scope = _get_scope(c)
    trace_id = f"lens-takeover-{uuid4()}"
    headers = {"x-trace-id": trace_id}
    try:
        _set_mode(c, "assist", kill_switch=False)
        _set_scope(c, _enable_apps(original_scope, ["lens", "control", "receipts"]))
        _ensure_takeover_idle(c)

        dry_request = c.post(
            "/lens/actions/execute",
            headers=headers,
            json={
                "kind": "control.takeover.request",
                "dry_run": True,
                "args": {"objective": "Dry run objective", "reason": "preview"},
            },
        )
        assert dry_request.status_code == 200
        assert dry_request.json()["status"] == "dry_run"

        requested = c.post(
            "/lens/actions/execute",
            headers=headers,
            json={
                "kind": "control.takeover.request",
                "args": {"objective": f"Execute takeover {uuid4()}", "reason": "lens execute"},
            },
        )
        assert requested.status_code == 200
        requested_payload = requested.json()
        assert requested_payload["status"] == "ok"
        assert requested_payload["result"]["summary"]["takeover"]["status"] == "requested"

        confirmed = c.post(
            "/lens/actions/execute",
            headers=headers,
            json={"kind": "control.takeover.confirm", "args": {"confirm": True, "mode": "pilot", "reason": "go"}},
        )
        assert confirmed.status_code == 200
        confirmed_payload = confirmed.json()
        assert confirmed_payload["result"]["summary"]["takeover"]["status"] == "active"

        handed_back = c.post(
            "/lens/actions/execute",
            headers=headers,
            json={
                "kind": "control.takeover.handback",
                "args": {
                    "summary": "Lens handback",
                    "verification": {"tests": "pass"},
                    "pending_approvals": 0,
                    "mode": "assist",
                },
            },
        )
        assert handed_back.status_code == 200
        handback_payload = handed_back.json()
        assert handback_payload["result"]["summary"]["takeover"]["status"] == "idle"

        trace = c.get(f"/runs/trace/{trace_id}", params={"limit": 100})
        assert trace.status_code == 200
        decisions = trace.json().get("receipts", {}).get("decisions", [])
        assert any(
            str(row.get("kind", "")) == "lens.action.execute"
            and str(row.get("action_kind", "")) == "control.takeover.request"
            for row in decisions
        )
        assert any(
            str(row.get("kind", "")) == "lens.action.execute"
            and str(row.get("action_kind", "")) == "control.takeover.handback"
            for row in decisions
        )
    finally:
        _ensure_takeover_idle(c)
        _set_scope(c, original_scope)
        _set_mode(c, str(original_mode.get("mode", "pilot")), bool(original_mode.get("kill_switch", False)))


def test_lens_execute_appends_takeover_activity_and_handback_package() -> None:
    c = TestClient(app)
    original_mode = _get_mode(c)
    original_scope = _get_scope(c)
    try:
        _set_mode(c, "assist", kill_switch=False)
        _set_scope(c, _enable_apps(original_scope, ["lens", "control", "receipts"]))
        _ensure_takeover_idle(c)

        requested = c.post(
            "/control/takeover/request",
            json={"objective": f"Activity takeover {uuid4()}", "reason": "activity test"},
        )
        assert requested.status_code == 200
        session_id = str(requested.json()["takeover"].get("session_id", "")).strip()
        assert session_id

        confirmed = c.post(
            "/control/takeover/confirm",
            json={"confirm": True, "reason": "activity confirm", "mode": "pilot"},
        )
        assert confirmed.status_code == 200

        execute = c.post(
            "/lens/actions/execute",
            json={"kind": "control.resume", "dry_run": True, "args": {"mode": "pilot", "reason": "activity dry run"}},
        )
        assert execute.status_code == 200
        assert execute.json()["status"] == "dry_run"
        state_active = c.get("/lens/state")
        assert state_active.status_code == 200
        takeover_active = state_active.json().get("control_surface", {}).get("takeover", {})
        assert str(takeover_active.get("session_id", "")).strip() == session_id
        assert any(
            str(row.get("kind", "")) == "lens.action.execute"
            and str(row.get("detail", {}).get("action_kind", "")) == "control.resume"
            for row in takeover_active.get("recent_activity", [])
        )

        activity = c.get("/control/takeover/activity", params={"session_id": session_id, "limit": 100})
        assert activity.status_code == 200
        rows = activity.json().get("activity", [])
        lens_rows = [row for row in rows if str(row.get("kind", "")) == "lens.action.execute"]
        assert lens_rows
        assert any(
            str(row.get("detail", {}).get("action_kind", "")) == "control.resume"
            and bool(row.get("detail", {}).get("dry_run", False))
            for row in lens_rows
        )

        handed_back = c.post(
            "/control/takeover/handback",
            json={"summary": "Activity handback", "verification": {"tests": "pass"}, "pending_approvals": 0},
        )
        assert handed_back.status_code == 200
        state_handed_back = c.get("/lens/state")
        assert state_handed_back.status_code == 200
        takeover_handed_back = state_handed_back.json().get("control_surface", {}).get("takeover", {})
        assert takeover_handed_back.get("status") == "idle"
        assert str(takeover_handed_back.get("last_session_id", "")).strip() == session_id
        assert takeover_handed_back.get("handback_package_available") is True
        assert isinstance(takeover_handed_back.get("handback_package_summary"), dict)

        package = c.get("/control/takeover/handback/package", params={"session_id": session_id, "limit": 120})
        assert package.status_code == 200
        payload = package.json()
        package_activity = payload.get("timeline", {}).get("activity", [])
        assert any(str(row.get("kind", "")) == "lens.action.execute" for row in package_activity)
        decisions = payload.get("receipts", {}).get("decisions", [])
        assert any(
            str(row.get("kind", "")) == "lens.action.execute"
            and str(row.get("session_id", "")).strip() == session_id
            for row in decisions
        )
    finally:
        _ensure_takeover_idle(c)
        _set_scope(c, original_scope)
        _set_mode(c, str(original_mode.get("mode", "pilot")), bool(original_mode.get("kill_switch", False)))


def test_lens_execute_takeover_activity_and_package_reads_supported() -> None:
    c = TestClient(app)
    original_mode = _get_mode(c)
    original_scope = _get_scope(c)
    try:
        _set_mode(c, "assist", kill_switch=False)
        _set_scope(c, _enable_apps(original_scope, ["lens", "control", "receipts"]))
        _ensure_takeover_idle(c)

        requested = c.post(
            "/control/takeover/request",
            json={"objective": f"Read session {uuid4()}", "reason": "lens read actions"},
        )
        assert requested.status_code == 200
        session_id = str(requested.json()["takeover"].get("session_id", "")).strip()
        assert session_id

        confirmed = c.post(
            "/control/takeover/confirm",
            json={"confirm": True, "reason": "lens read confirm", "mode": "pilot"},
        )
        assert confirmed.status_code == 200

        approval_request = c.post(
            "/approvals/request",
            json={"action": "forge.promote", "reason": "lens remote approve test", "metadata": {"source": "pytest"}},
        )
        assert approval_request.status_code == 200
        approval_id = str(approval_request.json().get("approval", {}).get("id", "")).strip()
        assert approval_id

        approval_request_two = c.post(
            "/approvals/request",
            json={"action": "tools.run", "reason": "lens remote reject test", "metadata": {"source": "pytest"}},
        )
        assert approval_request_two.status_code == 200
        approval_id_two = str(approval_request_two.json().get("approval", {}).get("id", "")).strip()
        assert approval_id_two

        actions_active = c.get("/lens/actions")
        assert actions_active.status_code == 200
        chips_active = actions_active.json().get("action_chips", [])
        assert any(str(chip.get("kind", "")) == "control.remote.state" for chip in chips_active)
        assert any(str(chip.get("kind", "")) == "control.remote.approvals" for chip in chips_active)
        assert any(str(chip.get("kind", "")) == "control.remote.feed" for chip in chips_active)
        assert any(str(chip.get("kind", "")) == "control.remote.approval.approve" for chip in chips_active)
        assert any(str(chip.get("kind", "")) == "control.remote.approval.reject" for chip in chips_active)
        assert any(str(chip.get("kind", "")) == "control.remote.panic" for chip in chips_active)
        assert any(str(chip.get("kind", "")) == "control.remote.takeover.handback" for chip in chips_active)
        assert any(str(chip.get("kind", "")) == "control.takeover.sessions" for chip in chips_active)
        assert any(str(chip.get("kind", "")) == "control.takeover.session" for chip in chips_active)
        assert any(str(chip.get("kind", "")) == "control.takeover.activity" for chip in chips_active)

        remote_state = c.post("/lens/actions/execute", json={"kind": "control.remote.state"})
        assert remote_state.status_code == 200
        remote_state_payload = remote_state.json()
        assert remote_state_payload["status"] == "ok"
        assert remote_state_payload["result"]["summary"]["status"] == "ok"
        assert int(remote_state_payload["result"]["summary"]["approvals"]["pending_count"]) >= 1

        remote_pending = c.post(
            "/lens/actions/execute",
            json={"kind": "control.remote.approvals", "args": {"status": "pending", "limit": 20}},
        )
        assert remote_pending.status_code == 200
        remote_pending_payload = remote_pending.json()
        assert remote_pending_payload["status"] == "ok"
        remote_pending_rows = remote_pending_payload["result"]["summary"]["approvals"]
        assert any(str(row.get("id", "")).strip() == approval_id for row in remote_pending_rows)

        remote_feed = c.post(
            "/lens/actions/execute",
            json={"kind": "control.remote.feed", "args": {"limit": 100}},
        )
        assert remote_feed.status_code == 200
        remote_feed_payload = remote_feed.json()
        assert remote_feed_payload["status"] == "ok"
        remote_feed_summary = remote_feed_payload["result"]["summary"]
        assert remote_feed_summary["status"] == "ok"
        assert int(remote_feed_summary.get("count", 0)) >= 1

        remote_approve = c.post(
            "/lens/actions/execute",
            json={"kind": "control.remote.approval.approve", "args": {"approval_id": approval_id, "note": "lens approve"}},
        )
        assert remote_approve.status_code == 200
        remote_approve_payload = remote_approve.json()
        assert remote_approve_payload["status"] == "ok"
        assert remote_approve_payload["result"]["summary"]["approval"]["status"] == "approved"

        approval_after = c.get(f"/approvals/{approval_id}")
        assert approval_after.status_code == 200
        assert approval_after.json().get("approval", {}).get("status") == "approved"

        remote_reject = c.post(
            "/lens/actions/execute",
            json={"kind": "control.remote.approval.reject", "args": {"approval_id": approval_id_two, "note": "lens reject"}},
        )
        assert remote_reject.status_code == 200
        remote_reject_payload = remote_reject.json()
        assert remote_reject_payload["status"] == "ok"
        assert remote_reject_payload["result"]["summary"]["approval"]["status"] == "rejected"

        approval_after_reject = c.get(f"/approvals/{approval_id_two}")
        assert approval_after_reject.status_code == 200
        assert approval_after_reject.json().get("approval", {}).get("status") == "rejected"

        read_sessions = c.post(
            "/lens/actions/execute",
            json={"kind": "control.takeover.sessions", "args": {"limit": 20}},
        )
        assert read_sessions.status_code == 200
        sessions_payload = read_sessions.json()
        assert sessions_payload["status"] == "ok"
        sessions_summary = sessions_payload["result"]["summary"]
        assert sessions_summary["status"] == "ok"
        assert int(sessions_summary.get("count", 0)) >= 1
        assert any(str(row.get("session_id", "")).strip() == session_id for row in sessions_summary.get("sessions", []))

        read_session = c.post(
            "/lens/actions/execute",
            json={"kind": "control.takeover.session", "args": {"session_id": session_id, "limit": 120}},
        )
        assert read_session.status_code == 200
        read_session_payload = read_session.json()
        assert read_session_payload["status"] == "ok"
        session_summary = read_session_payload["result"]["summary"]
        assert session_summary["status"] == "ok"
        assert session_summary.get("session", {}).get("session_id") == session_id

        read_activity = c.post(
            "/lens/actions/execute",
            json={"kind": "control.takeover.activity", "args": {"session_id": session_id, "limit": 40}},
        )
        assert read_activity.status_code == 200
        read_activity_payload = read_activity.json()
        assert read_activity_payload["status"] == "ok"
        summary = read_activity_payload["result"]["summary"]
        assert summary["status"] == "ok"
        assert summary["session_id"] == session_id
        assert summary["count"] >= 1

        handback = c.post(
            "/control/takeover/handback",
            json={"summary": "Read handback", "verification": {"tests": "pass"}, "pending_approvals": 0},
        )
        assert handback.status_code == 200

        actions_idle = c.get("/lens/actions")
        assert actions_idle.status_code == 200
        chips_idle = actions_idle.json().get("action_chips", [])
        assert any(str(chip.get("kind", "")) == "control.remote.takeover.request" for chip in chips_idle)
        assert any(str(chip.get("kind", "")) == "control.takeover.sessions" for chip in chips_idle)
        assert any(str(chip.get("kind", "")) == "control.takeover.session" for chip in chips_idle)
        assert any(str(chip.get("kind", "")) == "control.takeover.handback.package" for chip in chips_idle)
        assert any(str(chip.get("kind", "")) == "control.takeover.handback.export" for chip in chips_idle)

        read_package = c.post(
            "/lens/actions/execute",
            json={"kind": "control.takeover.handback.package", "args": {"session_id": session_id, "limit": 80}},
        )
        assert read_package.status_code == 200
        read_package_payload = read_package.json()
        assert read_package_payload["status"] == "ok"
        package_summary = read_package_payload["result"]["summary"]
        assert package_summary["status"] == "ok"
        assert package_summary["session_id"] == session_id
        assert int(package_summary.get("summary", {}).get("counts", {}).get("transitions", 0)) >= 3

        export_package = c.post(
            "/lens/actions/execute",
            json={"kind": "control.takeover.handback.export", "args": {"session_id": session_id, "limit": 80}},
        )
        assert export_package.status_code == 200
        export_payload = export_package.json()
        assert export_payload["status"] == "ok"
        export_summary = export_payload["result"]["summary"]
        assert export_summary["status"] == "ok"
        assert export_summary["session_id"] == session_id
        assert str(export_summary.get("export", {}).get("path", "")).startswith("control/handback_exports/")
    finally:
        _ensure_takeover_idle(c)
        _set_scope(c, original_scope)
        _set_mode(c, str(original_mode.get("mode", "pilot")), bool(original_mode.get("kill_switch", False)))


def test_lens_execute_remote_command_wrappers_supported() -> None:
    c = TestClient(app)
    original_mode = _get_mode(c)
    original_scope = _get_scope(c)
    trace_id = f"lens-remote-command-{uuid4()}"
    headers = {"x-trace-id": trace_id}
    try:
        _set_mode(c, "assist", kill_switch=False)
        _set_scope(c, _enable_apps(original_scope, ["lens", "control", "receipts"]))
        _ensure_takeover_idle(c)

        remote_request = c.post(
            "/lens/actions/execute",
            headers=headers,
            json={
                "kind": "control.remote.takeover.request",
                "args": {"objective": f"Lens remote takeover {uuid4()}", "reason": "lens remote request"},
            },
        )
        assert remote_request.status_code == 200
        remote_request_payload = remote_request.json()
        assert remote_request_payload["status"] == "ok"
        remote_request_summary = remote_request_payload["result"]["summary"]
        assert remote_request_summary["status"] == "ok"
        assert remote_request_summary["command"] == "control.takeover.request"
        session_id = str(remote_request_summary.get("session_id", "")).strip()
        assert session_id

        remote_confirm = c.post(
            "/lens/actions/execute",
            headers=headers,
            json={
                "kind": "control.remote.takeover.confirm",
                "args": {"confirm": True, "mode": "pilot", "reason": "lens remote confirm", "session_id": session_id},
            },
        )
        assert remote_confirm.status_code == 200
        remote_confirm_payload = remote_confirm.json()
        assert remote_confirm_payload["status"] == "ok"
        remote_confirm_summary = remote_confirm_payload["result"]["summary"]
        assert remote_confirm_summary["status"] == "ok"
        assert remote_confirm_summary["command"] == "control.takeover.confirm"
        assert remote_confirm_summary["summary"]["takeover"]["status"] == "active"

        actions_active = c.get("/lens/actions")
        assert actions_active.status_code == 200
        chips_active = actions_active.json().get("action_chips", [])
        assert any(str(chip.get("kind", "")) == "control.remote.panic" for chip in chips_active)
        assert any(str(chip.get("kind", "")) == "control.remote.takeover.handback" for chip in chips_active)

        remote_panic = c.post(
            "/lens/actions/execute",
            headers=headers,
            json={"kind": "control.remote.panic", "args": {"reason": "lens remote panic", "session_id": session_id}},
        )
        assert remote_panic.status_code == 200
        remote_panic_payload = remote_panic.json()
        assert remote_panic_payload["status"] == "ok"
        remote_panic_summary = remote_panic_payload["result"]["summary"]
        assert remote_panic_summary["status"] == "ok"
        assert remote_panic_summary["command"] == "control.panic"
        assert remote_panic_summary["summary"]["kill_switch"] is True

        remote_feed_filtered = c.post(
            "/lens/actions/execute",
            headers=headers,
            json={
                "kind": "control.remote.feed",
                "args": {
                    "session_id": session_id,
                    "kind": "control.remote.panic",
                    "risk_tier": "high",
                    "limit": 100,
                },
            },
        )
        assert remote_feed_filtered.status_code == 200
        remote_feed_filtered_payload = remote_feed_filtered.json()
        assert remote_feed_filtered_payload["status"] == "ok"
        feed_summary = remote_feed_filtered_payload["result"]["summary"]
        assert feed_summary["status"] == "ok"
        assert feed_summary.get("filters", {}).get("kind") == "control.remote.panic"
        assert feed_summary.get("filters", {}).get("risk_tier") == "high"
        assert int(feed_summary.get("count", 0)) >= 1
        assert all(str(row.get("kind", "")) == "control.remote.panic" for row in feed_summary.get("feed", []))
        assert all(str(row.get("risk_tier", "")) == "high" for row in feed_summary.get("feed", []))

        remote_feed_decisions = c.post(
            "/lens/actions/execute",
            headers=headers,
            json={
                "kind": "control.remote.feed",
                "args": {
                    "session_id": session_id,
                    "source": "journals.decisions",
                    "limit": 100,
                },
            },
        )
        assert remote_feed_decisions.status_code == 200
        remote_feed_decisions_payload = remote_feed_decisions.json()
        assert remote_feed_decisions_payload["status"] == "ok"
        decisions_summary = remote_feed_decisions_payload["result"]["summary"]
        assert decisions_summary["status"] == "ok"
        assert decisions_summary.get("filters", {}).get("source") == "journals.decisions"
        assert int(decisions_summary.get("count", 0)) >= 1
        assert all(str(row.get("source", "")) == "journals.decisions" for row in decisions_summary.get("feed", []))

        actions_paused = c.get("/lens/actions")
        assert actions_paused.status_code == 200
        chips_paused = actions_paused.json().get("action_chips", [])
        assert any(str(chip.get("kind", "")) == "control.remote.resume" for chip in chips_paused)

        remote_resume = c.post(
            "/lens/actions/execute",
            headers=headers,
            json={
                "kind": "control.remote.resume",
                "args": {"reason": "lens remote resume", "mode": "pilot", "session_id": session_id},
            },
        )
        assert remote_resume.status_code == 200
        remote_resume_payload = remote_resume.json()
        assert remote_resume_payload["status"] == "ok"
        remote_resume_summary = remote_resume_payload["result"]["summary"]
        assert remote_resume_summary["status"] == "ok"
        assert remote_resume_summary["command"] == "control.resume"
        assert remote_resume_summary["summary"]["kill_switch"] is False

        remote_handback = c.post(
            "/lens/actions/execute",
            headers=headers,
            json={
                "kind": "control.remote.takeover.handback",
                "args": {
                    "summary": "lens remote handback",
                    "verification": {"tests": "pass"},
                    "pending_approvals": 0,
                    "mode": "assist",
                    "reason": "lens remote done",
                    "session_id": session_id,
                },
            },
        )
        assert remote_handback.status_code == 200
        remote_handback_payload = remote_handback.json()
        assert remote_handback_payload["status"] == "ok"
        remote_handback_summary = remote_handback_payload["result"]["summary"]
        assert remote_handback_summary["status"] == "ok"
        assert remote_handback_summary["command"] == "control.takeover.handback"
        assert remote_handback_summary["summary"]["takeover"]["status"] == "idle"

        trace = c.get(f"/runs/trace/{trace_id}", params={"limit": 300})
        assert trace.status_code == 200
        decision_rows = trace.json().get("receipts", {}).get("decisions", [])
        assert any(
            str(row.get("kind", "")) == "lens.action.execute"
            and str(row.get("action_kind", "")) == "control.remote.takeover.request"
            for row in decision_rows
        )
        assert any(str(row.get("kind", "")) == "control.remote.takeover.request" for row in decision_rows)
        assert any(str(row.get("kind", "")) == "control.remote.takeover.confirm" for row in decision_rows)
        assert any(str(row.get("kind", "")) == "control.remote.panic" for row in decision_rows)
        assert any(str(row.get("kind", "")) == "control.remote.resume" for row in decision_rows)
        assert any(str(row.get("kind", "")) == "control.remote.takeover.handback" for row in decision_rows)
    finally:
        _ensure_takeover_idle(c)
        _set_scope(c, original_scope)
        _set_mode(c, str(original_mode.get("mode", "pilot")), bool(original_mode.get("kill_switch", False)))


def test_lens_remote_chips_and_execute_respect_observer_rbac() -> None:
    c = TestClient(app)
    original_mode = _get_mode(c)
    original_scope = _get_scope(c)
    observer_headers = {"x-francis-role": "observer"}
    try:
        _set_mode(c, "assist", kill_switch=False)
        _set_scope(c, _enable_apps(original_scope, ["lens", "control", "receipts", "approvals"]))
        _ensure_takeover_idle(c)

        actions = c.get("/lens/actions", headers=observer_headers)
        assert actions.status_code == 200
        chips = actions.json().get("action_chips", [])
        chip_by_kind = {str(chip.get("kind", "")): chip for chip in chips}

        assert chip_by_kind.get("control.remote.state", {}).get("enabled") is True
        assert chip_by_kind.get("control.remote.panic", {}).get("enabled") is False
        assert "rbac denied" in str(chip_by_kind.get("control.remote.panic", {}).get("policy_reason", "")).lower()
        assert chip_by_kind.get("control.remote.takeover.request", {}).get("enabled") is False
        assert "rbac denied" in str(
            chip_by_kind.get("control.remote.takeover.request", {}).get("policy_reason", "")
        ).lower()

        execute_read = c.post(
            "/lens/actions/execute",
            headers=observer_headers,
            json={"kind": "control.remote.state"},
        )
        assert execute_read.status_code == 200
        assert execute_read.json().get("result", {}).get("summary", {}).get("status") == "ok"

        execute_write = c.post(
            "/lens/actions/execute",
            headers=observer_headers,
            json={"kind": "control.remote.panic", "args": {"reason": "observer should fail"}},
        )
        assert execute_write.status_code == 403
        assert "rbac denied" in str(execute_write.json().get("detail", "")).lower()
    finally:
        _ensure_takeover_idle(c)
        _set_scope(c, original_scope)
        _set_mode(c, str(original_mode.get("mode", "pilot")), bool(original_mode.get("kill_switch", False)))


def test_lens_state_degrades_when_remote_read_denied() -> None:
    c = TestClient(app)
    original_mode = _get_mode(c)
    original_scope = _get_scope(c)
    worker_headers = {"x-francis-role": "worker"}
    try:
        _set_mode(c, "assist", kill_switch=False)
        _set_scope(c, _enable_apps(original_scope, ["lens", "control", "receipts", "approvals"]))

        state = c.get("/lens/state", headers=worker_headers)
        assert state.status_code == 200
        payload = state.json()
        remote = payload.get("remote", {})
        assert remote.get("status") == "unavailable"
        assert "control.remote.read" in str(remote.get("policy_reason", ""))
    finally:
        _set_scope(c, original_scope)
        _set_mode(c, str(original_mode.get("mode", "pilot")), bool(original_mode.get("kill_switch", False)))


def test_lens_surfaces_worker_queue_signals() -> None:
    workspace = Path(__file__).resolve().parents[2] / "workspace"
    jobs_path = workspace / "queue" / "jobs.jsonl"
    existing = jobs_path.read_text(encoding="utf-8") if jobs_path.exists() else ""
    try:
        jobs_path.parent.mkdir(parents=True, exist_ok=True)
        queued = {
            "id": str(uuid4()),
            "ts": "2026-01-01T00:00:00+00:00",
            "run_id": str(uuid4()),
            "action": "forge.propose",
            "status": "queued",
            "priority": "high",
            "attempts": 0,
        }
        jobs_path.write_text(json.dumps(queued, ensure_ascii=False) + "\n", encoding="utf-8")

        c = TestClient(app)
        mode = c.put("/control/mode", json={"mode": "pilot", "kill_switch": False})
        assert mode.status_code == 200

        state = c.get("/lens/state")
        assert state.status_code == 200
        payload = state.json()
        blockers = payload.get("blockers", {})
        assert int(blockers.get("worker_queue_due", 0)) >= 1

        actions = c.get("/lens/actions")
        assert actions.status_code == 200
        action_chips = actions.json().get("action_chips", [])
        assert any(chip.get("kind") == "worker.cycle" for chip in action_chips)
    finally:
        jobs_path.write_text(existing, encoding="utf-8")


def test_lens_surfaces_worker_lease_pressure() -> None:
    workspace = Path(__file__).resolve().parents[2] / "workspace"
    jobs_path = workspace / "queue" / "jobs.jsonl"
    existing = jobs_path.read_text(encoding="utf-8") if jobs_path.exists() else ""
    try:
        jobs_path.parent.mkdir(parents=True, exist_ok=True)
        leased = {
            "id": str(uuid4()),
            "ts": "2026-01-01T00:00:00+00:00",
            "run_id": str(uuid4()),
            "action": "forge.propose",
            "status": "leased",
            "lease_owner": "worker-a",
            "lease_key": str(uuid4()),
            "lease_expires_at": "2020-01-01T00:00:00+00:00",
            "attempts": 0,
        }
        jobs_path.write_text(json.dumps(leased, ensure_ascii=False) + "\n", encoding="utf-8")

        c = TestClient(app)
        mode = c.put("/control/mode", json={"mode": "pilot", "kill_switch": False})
        assert mode.status_code == 200

        state = c.get("/lens/state")
        assert state.status_code == 200
        blockers = state.json().get("blockers", {})
        assert int(blockers.get("worker_leased", 0)) >= 1
        assert int(blockers.get("worker_leased_expired", 0)) >= 1

        actions = c.get("/lens/actions")
        assert actions.status_code == 200
        actions_payload = actions.json()
        selected = actions_payload.get("selected_actions", [])
        blocked = actions_payload.get("blocked_actions", [])
        all_kinds = [item.get("kind") for item in selected] + [item.get("kind") for item in blocked]
        assert "worker.cycle" in all_kinds
    finally:
        jobs_path.write_text(existing, encoding="utf-8")


def test_lens_actions_reflect_action_budget_blocks() -> None:
    workspace = Path(__file__).resolve().parents[2] / "workspace"
    jobs_path = workspace / "queue" / "jobs.jsonl"
    budget_path = workspace / "autonomy" / "action_budget_state.json"
    jobs_before = jobs_path.read_text(encoding="utf-8") if jobs_path.exists() else ""
    budget_before = budget_path.read_text(encoding="utf-8") if budget_path.exists() else ""
    try:
        jobs_path.parent.mkdir(parents=True, exist_ok=True)
        budget_path.parent.mkdir(parents=True, exist_ok=True)
        jobs_path.write_text(
            json.dumps(
                {
                    "id": str(uuid4()),
                    "ts": "2026-01-01T00:00:00+00:00",
                    "run_id": str(uuid4()),
                    "action": "forge.propose",
                    "status": "queued",
                    "priority": "high",
                    "attempts": 0,
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        budget_path.write_text(
            json.dumps(
                {
                    "date": datetime.now(timezone.utc).date().isoformat(),
                    "counts": {"worker.cycle": 500},
                    "last_executed_at": {},
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        c = TestClient(app)
        mode = c.put("/control/mode", json={"mode": "pilot", "kill_switch": False})
        assert mode.status_code == 200
        actions = c.get("/lens/actions")
        assert actions.status_code == 200
        chips = actions.json().get("action_chips", [])
        worker_chip = [chip for chip in chips if chip.get("kind") == "worker.cycle"]
        assert worker_chip
        assert worker_chip[0].get("enabled") is False
        assert "daily cap reached" in str(worker_chip[0].get("policy_reason", ""))
    finally:
        jobs_path.write_text(jobs_before, encoding="utf-8")
        budget_path.write_text(budget_before, encoding="utf-8")


def test_lens_worker_chip_includes_lease_telemetry() -> None:
    workspace = Path(__file__).resolve().parents[2] / "workspace"
    jobs_path = workspace / "queue" / "jobs.jsonl"
    last_worker_run_path = workspace / "runs" / "last_worker_run.json"
    jobs_before = jobs_path.read_text(encoding="utf-8") if jobs_path.exists() else ""
    last_before = last_worker_run_path.read_text(encoding="utf-8") if last_worker_run_path.exists() else ""
    try:
        jobs_path.parent.mkdir(parents=True, exist_ok=True)
        last_worker_run_path.parent.mkdir(parents=True, exist_ok=True)
        jobs_path.write_text(
            json.dumps(
                {
                    "id": str(uuid4()),
                    "ts": "2026-01-01T00:00:00+00:00",
                    "run_id": str(uuid4()),
                    "action": "forge.propose",
                    "status": "queued",
                    "priority": "high",
                    "attempts": 0,
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        last_worker_run_path.write_text(
            json.dumps(
                {
                    "lease_renewed_count": 3,
                    "lease_lost_count": 1,
                    "lease_finalize_conflict_count": 2,
                    "reclaimed_leases_count": 4,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        c = TestClient(app)
        mode = c.put("/control/mode", json={"mode": "pilot", "kill_switch": False})
        assert mode.status_code == 200

        actions = c.get("/lens/actions")
        assert actions.status_code == 200
        chips = actions.json().get("action_chips", [])
        worker_chip = [chip for chip in chips if chip.get("kind") == "worker.cycle"]
        assert worker_chip
        telemetry = worker_chip[0].get("lease_telemetry", {})
        assert int(telemetry.get("renewed_last_cycle", 0)) == 3
        assert int(telemetry.get("lost_last_cycle", 0)) == 1
        assert int(telemetry.get("conflicts_last_cycle", 0)) == 2
        assert int(telemetry.get("recovered_last_cycle", 0)) == 4
    finally:
        jobs_path.write_text(jobs_before, encoding="utf-8")
        last_worker_run_path.write_text(last_before, encoding="utf-8")


def test_lens_surfaces_autonomy_event_queue_and_dispatch_chip() -> None:
    workspace = Path(__file__).resolve().parents[2] / "workspace"
    autonomy_events_path = workspace / "autonomy" / "events.jsonl"
    events_before = autonomy_events_path.read_text(encoding="utf-8") if autonomy_events_path.exists() else ""
    try:
        autonomy_events_path.parent.mkdir(parents=True, exist_ok=True)
        queued_event = {
            "id": str(uuid4()),
            "ts": "2026-01-01T00:00:00+00:00",
            "run_id": str(uuid4()),
            "kind": "autonomy.event",
            "event_type": "telemetry.critical_present",
            "source": "telemetry:dev_server",
            "priority": "critical",
            "risk_tier": "high",
            "payload": {"count": 1},
            "status": "queued",
            "attempts": 0,
            "next_run_after": "2020-01-01T00:00:00+00:00",
            "dedupe_key": "test-autonomy-high-risk",
            "lease_id": None,
            "lease_owner": None,
            "leased_at": None,
            "completed_at": None,
            "dispatch_run_id": None,
            "error": None,
        }
        autonomy_events_path.write_text(json.dumps(queued_event, ensure_ascii=False) + "\n", encoding="utf-8")

        c = TestClient(app)
        mode = c.put("/control/mode", json={"mode": "pilot", "kill_switch": False})
        assert mode.status_code == 200

        state = c.get("/lens/state")
        assert state.status_code == 200
        payload = state.json()
        autonomy_queue = payload.get("autonomy_queue", {})
        assert int(autonomy_queue.get("queued_count", 0)) >= 1
        assert int(autonomy_queue.get("high_risk_due_count", 0)) >= 1
        blockers = payload.get("blockers", {})
        assert int(blockers.get("autonomy_queue_due", 0)) >= 1
        assert int(blockers.get("autonomy_queue_high_risk_due", 0)) >= 1

        actions = c.get("/lens/actions")
        assert actions.status_code == 200
        chips = actions.json().get("action_chips", [])
        dispatch_chip = [chip for chip in chips if chip.get("kind") == "autonomy.dispatch"]
        assert dispatch_chip
        assert dispatch_chip[0].get("enabled") is True
        telemetry = dispatch_chip[0].get("queue_telemetry", {})
        assert int(telemetry.get("queued_count", 0)) >= 1
        assert int(telemetry.get("high_risk_due_count", 0)) >= 1
        assert "approval required" in str(dispatch_chip[0].get("policy_reason", "")).lower()
    finally:
        autonomy_events_path.write_text(events_before, encoding="utf-8")


def test_lens_surfaces_autonomy_stale_lease_recovery_chip() -> None:
    workspace = Path(__file__).resolve().parents[2] / "workspace"
    autonomy_events_path = workspace / "autonomy" / "events.jsonl"
    events_before = autonomy_events_path.read_text(encoding="utf-8") if autonomy_events_path.exists() else ""
    try:
        autonomy_events_path.parent.mkdir(parents=True, exist_ok=True)
        leased_expired_event = {
            "id": str(uuid4()),
            "ts": "2026-01-01T00:00:00+00:00",
            "run_id": str(uuid4()),
            "kind": "autonomy.event",
            "event_type": "manual.recover_test",
            "source": "pytest",
            "priority": "high",
            "risk_tier": "medium",
            "payload": {"x": 1},
            "status": "leased",
            "attempts": 1,
            "next_run_after": "2026-01-01T00:00:00+00:00",
            "dedupe_key": "lens-recover-test",
            "lease_id": str(uuid4()),
            "lease_owner": "worker-x",
            "leased_at": "2020-01-01T00:00:00+00:00",
            "lease_expires_at": "2020-01-01T00:05:00+00:00",
            "completed_at": None,
            "dispatch_run_id": None,
            "error": None,
        }
        autonomy_events_path.write_text(json.dumps(leased_expired_event, ensure_ascii=False) + "\n", encoding="utf-8")

        c = TestClient(app)
        mode = c.put("/control/mode", json={"mode": "pilot", "kill_switch": False})
        assert mode.status_code == 200

        state = c.get("/lens/state")
        assert state.status_code == 200
        payload = state.json()
        autonomy_queue = payload.get("autonomy_queue", {})
        assert int(autonomy_queue.get("leased_expired_count", 0)) >= 1
        blockers = payload.get("blockers", {})
        assert int(blockers.get("autonomy_queue_leased_expired", 0)) >= 1

        actions = c.get("/lens/actions")
        assert actions.status_code == 200
        chips = actions.json().get("action_chips", [])
        recover_chip = [chip for chip in chips if chip.get("kind") == "autonomy.recover"]
        assert recover_chip
        assert recover_chip[0].get("enabled") is True
        telemetry = recover_chip[0].get("queue_telemetry", {})
        assert int(telemetry.get("leased_expired_count", 0)) >= 1
    finally:
        autonomy_events_path.write_text(events_before, encoding="utf-8")


def test_lens_surfaces_autonomy_dispatch_halt_and_budget_telemetry() -> None:
    workspace = Path(__file__).resolve().parents[2] / "workspace"
    autonomy_events_path = workspace / "autonomy" / "events.jsonl"
    last_dispatch_path = workspace / "autonomy" / "last_dispatch.json"
    events_before = autonomy_events_path.read_text(encoding="utf-8") if autonomy_events_path.exists() else ""
    last_before = last_dispatch_path.read_text(encoding="utf-8") if last_dispatch_path.exists() else ""
    try:
        autonomy_events_path.parent.mkdir(parents=True, exist_ok=True)
        queued_event = {
            "id": str(uuid4()),
            "ts": "2026-01-01T00:00:00+00:00",
            "run_id": str(uuid4()),
            "kind": "autonomy.event",
            "event_type": "manual.lens_dispatch_halt",
            "source": "pytest",
            "priority": "normal",
            "risk_tier": "low",
            "payload": {},
            "status": "queued",
            "attempts": 0,
            "next_run_after": "2020-01-01T00:00:00+00:00",
            "dedupe_key": "lens-dispatch-halt",
            "lease_id": None,
            "lease_owner": None,
            "leased_at": None,
            "completed_at": None,
            "dispatch_run_id": None,
            "error": None,
        }
        autonomy_events_path.write_text(json.dumps(queued_event, ensure_ascii=False) + "\n", encoding="utf-8")
        last_dispatch_path.write_text(
            json.dumps(
                {
                    "run_id": str(uuid4()),
                    "halted_reason": "dispatch_action_budget_exceeded",
                    "processed_count": 0,
                    "failed_count": 0,
                    "retried_count": 1,
                    "released_count": 2,
                    "dispatch_executed_actions": 0,
                    "config": {
                        "max_dispatch_actions": 2,
                        "max_dispatch_runtime_seconds": 45,
                        "max_attempts": 3,
                        "retry_backoff_seconds": 120,
                    },
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        c = TestClient(app)
        mode = c.put("/control/mode", json={"mode": "pilot", "kill_switch": False})
        assert mode.status_code == 200

        state = c.get("/lens/state")
        assert state.status_code == 200
        payload = state.json()
        dispatch = payload.get("autonomy_dispatch", {})
        assert dispatch.get("halted") is True
        assert dispatch.get("halted_reason") == "dispatch_action_budget_exceeded"
        assert int(dispatch.get("max_dispatch_actions", 0)) == 2
        assert int(dispatch.get("max_dispatch_runtime_seconds", 0)) == 45
        assert int(dispatch.get("max_attempts", 0)) == 3
        assert int(dispatch.get("retry_backoff_seconds", 0)) == 120
        assert "verification_status" in dispatch
        assert "confidence" in dispatch
        assert "can_claim_done" in dispatch
        assert dispatch.get("completion_state") in {"done", "incomplete", None}
        assert dispatch.get("trust_badge") in {"Confirmed", "Likely", "Uncertain"}
        blockers = payload.get("blockers", {})
        assert blockers.get("autonomy_dispatch_halted") is True
        assert blockers.get("autonomy_dispatch_budget_halt") is True
        assert blockers.get("autonomy_dispatch_critical_halt") is False

        actions = c.get("/lens/actions")
        assert actions.status_code == 200
        chips = actions.json().get("action_chips", [])
        dispatch_chip = [chip for chip in chips if chip.get("kind") == "autonomy.dispatch"]
        assert dispatch_chip
        assert dispatch_chip[0].get("trust_badge") in {"Confirmed", "Likely", "Uncertain"}
        queue_telemetry = dispatch_chip[0].get("queue_telemetry", {})
        assert queue_telemetry.get("last_halted_reason") == "dispatch_action_budget_exceeded"
        assert int(queue_telemetry.get("last_max_dispatch_actions", 0)) == 2
        assert int(queue_telemetry.get("last_max_dispatch_runtime_seconds", 0)) == 45
        assert "last_verification_status" in queue_telemetry
        assert "last_confidence" in queue_telemetry
        assert "last_can_claim_done" in queue_telemetry
        assert "last_completion_state" in queue_telemetry
    finally:
        autonomy_events_path.write_text(events_before, encoding="utf-8")
        last_dispatch_path.write_text(last_before, encoding="utf-8")


def test_lens_surfaces_autonomy_reactor_state_and_health_chip() -> None:
    workspace = Path(__file__).resolve().parents[2] / "workspace"
    autonomy_events_path = workspace / "autonomy" / "events.jsonl"
    last_tick_path = workspace / "autonomy" / "last_tick.json"
    guardrail_path = workspace / "autonomy" / "reactor_guardrail_state.json"
    events_before = autonomy_events_path.read_text(encoding="utf-8") if autonomy_events_path.exists() else ""
    tick_before = last_tick_path.read_text(encoding="utf-8") if last_tick_path.exists() else ""
    guardrail_before = guardrail_path.read_text(encoding="utf-8") if guardrail_path.exists() else ""
    try:
        autonomy_events_path.parent.mkdir(parents=True, exist_ok=True)
        queued_retry_event = {
            "id": str(uuid4()),
            "ts": "2026-01-01T00:00:00+00:00",
            "run_id": str(uuid4()),
            "kind": "autonomy.event",
            "event_type": "manual.retry_pressure",
            "source": "pytest",
            "priority": "normal",
            "risk_tier": "low",
            "payload": {},
            "status": "queued",
            "attempts": 2,
            "next_run_after": "2020-01-01T00:00:00+00:00",
            "dedupe_key": "lens-reactor-retry",
            "lease_id": None,
            "lease_owner": None,
            "leased_at": None,
            "completed_at": None,
            "dispatch_run_id": None,
            "error": "retry pending",
            "last_error": "retry pending",
            "last_failed_at": "2026-01-01T00:00:00+00:00",
            "retry_backoff_seconds": 120,
            "max_attempts": 3,
        }
        autonomy_events_path.write_text(json.dumps(queued_retry_event, ensure_ascii=False) + "\n", encoding="utf-8")
        last_tick_path.write_text(
            json.dumps(
                {
                    "id": str(uuid4()),
                    "ts": "2026-01-01T01:00:00+00:00",
                    "run_id": str(uuid4()),
                    "kind": "autonomy.reactor.tick",
                    "collect": {"seen_count": 5, "queued_count": 2, "duplicate_count": 1},
                    "dispatch": {
                        "leased_count": 2,
                        "processed_count": 0,
                        "failed_count": 1,
                        "retried_count": 1,
                        "released_count": 1,
                        "halted_reason": "dispatch_runtime_budget_exceeded",
                    },
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        guardrail_path.write_text(
            json.dumps(
                {
                    "tick_count": 9,
                    "consecutive_retry_pressure_ticks": 0,
                    "cooldown_remaining_ticks": 2,
                    "escalations_count": 3,
                    "last_retry_pressure_count": 1,
                    "last_reason": "retry_pressure_cooldown",
                    "updated_at": "2026-01-01T01:00:00+00:00",
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        c = TestClient(app)
        mode = c.put("/control/mode", json={"mode": "pilot", "kill_switch": False})
        assert mode.status_code == 200

        state = c.get("/lens/state")
        assert state.status_code == 200
        payload = state.json()
        autonomy_queue = payload.get("autonomy_queue", {})
        assert int(autonomy_queue.get("queued_retry_count", 0)) >= 1
        reactor = payload.get("autonomy_reactor", {})
        assert reactor.get("halted") is True
        assert reactor.get("halted_reason") == "dispatch_runtime_budget_exceeded"
        assert int(reactor.get("collect_seen_count", 0)) == 5
        assert int(reactor.get("dispatch_retried_count", 0)) == 1
        assert "verification_status" in reactor
        assert "confidence" in reactor
        assert "can_claim_done" in reactor
        assert reactor.get("completion_state") in {"done", "incomplete", None}
        assert reactor.get("trust_badge") in {"Confirmed", "Likely", "Uncertain"}
        guardrail = reactor.get("guardrail", {})
        assert int(guardrail.get("cooldown_remaining_ticks", 0)) == 2
        assert int(guardrail.get("escalations_count", 0)) == 3
        assert guardrail.get("last_reason") == "retry_pressure_cooldown"
        assert guardrail.get("manual_reset_available") is True
        blockers = payload.get("blockers", {})
        assert int(blockers.get("autonomy_queue_retry_pressure", 0)) >= 1
        assert blockers.get("autonomy_reactor_halted") is True
        assert blockers.get("autonomy_reactor_halted_reason") == "dispatch_runtime_budget_exceeded"
        assert blockers.get("autonomy_reactor_cooldown_active") is True

        actions = c.get("/lens/actions")
        assert actions.status_code == 200
        chips = actions.json().get("action_chips", [])
        reactor_chip = [chip for chip in chips if chip.get("kind") == "autonomy.reactor.tick"]
        assert reactor_chip
        assert reactor_chip[0].get("enabled") is True
        assert reactor_chip[0].get("trust_badge") in {"Confirmed", "Likely", "Uncertain"}
        telemetry = reactor_chip[0].get("queue_telemetry", {})
        assert int(telemetry.get("queued_retry_count", 0)) >= 1
        assert telemetry.get("last_tick_halted_reason") == "dispatch_runtime_budget_exceeded"
        assert "last_tick_verification_status" in telemetry
        assert "last_tick_confidence" in telemetry
        assert "last_tick_can_claim_done" in telemetry
        assert "last_tick_completion_state" in telemetry
        assert int(telemetry.get("last_tick_retried_count", 0)) == 1
        assert telemetry.get("guardrail_cooldown_active") is True
        assert int(telemetry.get("guardrail_cooldown_remaining_ticks", 0)) == 2
        assert int(telemetry.get("guardrail_escalations_count", 0)) == 3
        assert "guardrail cooldown active" in str(reactor_chip[0].get("policy_reason", "")).lower()
        reset_chip = [chip for chip in chips if chip.get("kind") == "autonomy.reactor.guardrail.reset"]
        assert reset_chip
        assert reset_chip[0].get("enabled") is True
        assert reset_chip[0].get("trust_badge") in {"Confirmed", "Likely", "Uncertain"}
        reset_telemetry = reset_chip[0].get("queue_telemetry", {})
        assert reset_telemetry.get("guardrail_cooldown_active") is True
        assert int(reset_telemetry.get("guardrail_cooldown_remaining_ticks", 0)) == 2
    finally:
        autonomy_events_path.write_text(events_before, encoding="utf-8")
        last_tick_path.write_text(tick_before, encoding="utf-8")
        guardrail_path.write_text(guardrail_before, encoding="utf-8")
