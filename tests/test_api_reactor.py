from __future__ import annotations

import json
from pathlib import Path

_REACTOR_ACTOR = "test.reactor.write"


def test_reactor_event_routes_enqueue_and_readback(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", json.dumps({_REACTOR_ACTOR: ["reactor.write"]}))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    empty_status = client.get("/reactor/status")
    assert empty_status.status_code == 200
    assert empty_status.json()["ok"] is True
    assert empty_status.json()["total"] == 0
    assert empty_status.json()["dispatch_engine"] == "not_implemented"

    queued = client.post(
        "/reactor/events/enqueue",
        json={
            "trigger_source": "mission_queue",
            "trigger_type": "mission_tick",
            "summary": "Mission queue has a ready item",
            "actor": _REACTOR_ACTOR,
            "mode": "pilot",
            "mission_id": "msn_reactor_ready",
            "operation_id": "tsk_reactor_ready",
            "risk_tier": "normal",
            "action_class": "mission_tick",
            "max_actions": 2,
            "max_runtime_seconds": 90,
            "stop_conditions": ["advanced_once", "approval_required", "budget_exhausted"],
            "metadata": {"queue": "mission"},
        },
    )
    assert queued.status_code == 200
    queued_body = queued.json()
    assert queued_body["ok"] is True
    assert queued_body["applied"] is True
    event = queued_body["event"]
    event_id = str(queued_body["event_id"])
    assert event["trigger"]["source"] == "mission_queue"
    assert event["classification"]["mode"] == "pilot"
    assert event["classification"]["stable_state"] == "awaiting_dispatch"
    assert event["bounds"]["max_actions"] == 2
    assert event["dispatch"]["applied"] is False
    assert event["governance"]["dispatch_authority"] is False

    listed = client.get("/reactor/events/list", params={"trigger_source": "mission_queue"})
    assert listed.status_code == 200
    listed_body = listed.json()
    assert listed_body["total"] == 1
    assert listed_body["items"][0]["event_id"] == event_id

    fetched = client.get("/reactor/events/get", params={"id": event_id})
    assert fetched.status_code == 200
    assert fetched.json()["ok"] is True
    assert fetched.json()["item"]["event_id"] == event_id

    dispatch_attempt = client.post(
        "/reactor/events/dispatch_attempt",
        json={
            "event_id": event_id,
            "actor": _REACTOR_ACTOR,
            "reason": "record a bounded dispatch attempt before execution exists",
        },
    )
    assert dispatch_attempt.status_code == 200
    attempt_body = dispatch_attempt.json()
    assert attempt_body["ok"] is True
    assert attempt_body["applied"] is True
    assert attempt_body["receipt"]["kind"] == "reactor.dispatch_attempt.receipt"
    assert attempt_body["receipt"]["execution_started"] is False
    assert attempt_body["event"]["status"] == "dispatch_deferred"
    assert attempt_body["event"]["dispatch"]["engine"] == "not_implemented"
    assert attempt_body["event"]["governance"]["execution_authority"] is False

    status = client.get("/reactor/status")
    assert status.status_code == 200
    assert status.json()["total"] == 1
    assert status.json()["trigger_source_counts"] == {"mission_queue": 1}
    assert status.json()["status_counts"] == {"dispatch_deferred": 1}


def test_reactor_event_routes_filter_review_readbacks(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", json.dumps({_REACTOR_ACTOR: ["reactor.write"]}))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    approval = client.post(
        "/reactor/events/enqueue",
        json={
            "trigger_source": "user_request",
            "summary": "Approval-gated mutation needs review",
            "actor": _REACTOR_ACTOR,
            "risk_tier": "critical",
            "action_class": "mutate",
            "approval_required": True,
            "approval_id": "appr_reactor_filter",
        },
    ).json()
    approval_id = str(approval["event_id"])
    client.post(
        "/reactor/events/dispatch_attempt",
        json={"event_id": approval_id, "actor": _REACTOR_ACTOR},
    )

    budget = client.post(
        "/reactor/events/enqueue",
        json={
            "trigger_source": "mission_queue",
            "summary": "Budget-exhausted event needs deadletter review",
            "actor": _REACTOR_ACTOR,
            "action_class": "mission_tick",
            "max_actions": 0,
        },
    ).json()
    budget_id = str(budget["event_id"])
    client.post(
        "/reactor/events/dispatch_attempt",
        json={"event_id": budget_id, "actor": _REACTOR_ACTOR},
    )

    retry = client.post(
        "/reactor/events/enqueue",
        json={
            "trigger_source": "mission_queue",
            "summary": "Retry-exhausted event needs review",
            "actor": _REACTOR_ACTOR,
            "action_class": "mission_tick",
            "max_actions": 1,
            "max_retries": 1,
        },
    ).json()
    retry_id = str(retry["event_id"])
    client.post(
        "/reactor/events/dispatch_attempt",
        json={"event_id": retry_id, "actor": _REACTOR_ACTOR},
    )
    client.post(
        "/reactor/events/dispatch_attempt",
        json={"event_id": retry_id, "actor": _REACTOR_ACTOR},
    )

    approval_list = client.get("/reactor/events/list", params={"review_route": "approval_queue"})
    assert approval_list.status_code == 200
    assert {item["event_id"] for item in approval_list.json()["items"]} == {approval_id}

    deadletter_blockers = client.get("/reactor/events/list", params={"blocker_route": "deadletter_candidate"})
    assert deadletter_blockers.status_code == 200
    assert {item["event_id"] for item in deadletter_blockers.json()["items"]} == {budget_id}

    deadletter_review = client.get("/reactor/events/list", params={"review_route": "deadletter_candidate"})
    assert deadletter_review.status_code == 200
    assert {item["event_id"] for item in deadletter_review.json()["items"]} == {budget_id, retry_id}

    exhausted_state = client.get("/reactor/events/list", params={"stable_state": "retry_budget_exhausted"})
    assert exhausted_state.status_code == 200
    assert {item["event_id"] for item in exhausted_state.json()["items"]} == {retry_id}

    exhausted_receipt = client.get(
        "/reactor/events/list",
        params={"receipt_kind": "reactor.retry_exhausted.receipt"},
    )
    assert exhausted_receipt.status_code == 200
    assert {item["event_id"] for item in exhausted_receipt.json()["items"]} == {retry_id}


def test_reactor_event_routes_require_scope_and_valid_trigger(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", "{}")

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    denied = client.post(
        "/reactor/events/enqueue",
        json={
            "trigger_source": "user_request",
            "summary": "operator asked to continue",
            "actor": _REACTOR_ACTOR,
        },
    )
    assert denied.status_code == 200
    assert denied.json()["ok"] is False
    assert denied.json()["error"] == "api_permission_denied"
    assert denied.json()["governance"]["scope"] == "reactor.write"

    denied_attempt = client.post(
        "/reactor/events/dispatch_attempt",
        json={
            "event_id": "reactor_evt_missing",
            "actor": _REACTOR_ACTOR,
        },
    )
    assert denied_attempt.status_code == 200
    assert denied_attempt.json()["ok"] is False
    assert denied_attempt.json()["error"] == "api_permission_denied"

    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", json.dumps({_REACTOR_ACTOR: ["reactor.write"]}))
    client = TestClient(create_app())
    invalid = client.post(
        "/reactor/events/enqueue",
        json={
            "trigger_source": "self_loop",
            "summary": "keep doing things without a trigger",
            "actor": _REACTOR_ACTOR,
        },
    )
    assert invalid.status_code == 200
    assert invalid.json()["ok"] is False
    assert invalid.json()["error"] == "invalid_trigger_source"
    assert not (data_root / "reactor" / "events").exists()
