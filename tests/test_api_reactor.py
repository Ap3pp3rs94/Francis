from __future__ import annotations

import json
from pathlib import Path

_REACTOR_ACTOR = "test.reactor.write"
_APPROVAL_ACTOR = "test.reactor.approvals.decide"


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
    verification = attempt_body["event"]["latest_verification_receipt"]
    assert verification["kind"] == "reactor.verification.receipt"
    assert verification["verification_status"] == "not_available"
    assert verification["verification_outcome"] == "dispatch_engine_not_implemented"
    assert verification["source_receipt_kind"] == "reactor.dispatch_attempt.receipt"
    assert verification["verified"] is False
    assert verification["completion_claimed"] is False
    assert verification["completion_claim_allowed"] is False
    assert verification["governance"]["execution_authority"] is False
    stable_return = attempt_body["event"]["latest_stable_return"]
    assert stable_return["kind"] == "reactor.stable_return.receipt"
    assert stable_return["status"] == "settled"
    assert stable_return["route"] == "dispatch_engine"
    assert stable_return["source_receipt_kind"] == "reactor.dispatch_attempt.receipt"
    assert stable_return["returned_to_stable_state"] is True
    assert stable_return["execution_started"] is False
    assert stable_return["dispatch_applied"] is False
    assert stable_return["governance"]["execution_authority"] is False
    assert stable_return["verification_receipt_id"] == verification["receipt_id"]
    assert stable_return["verification_status"] == "not_available"
    assert stable_return["verification_outcome"] == "dispatch_engine_not_implemented"
    assert attempt_body["event"]["latest_receipt"]["receipt_id"] == stable_return["receipt_id"]

    verification_list = client.get(
        "/reactor/events/list",
        params={"receipt_kind": "reactor.verification.receipt"},
    )
    assert verification_list.status_code == 200
    assert {item["event_id"] for item in verification_list.json()["items"]} == {event_id}

    stable_return_list = client.get(
        "/reactor/events/list",
        params={"receipt_kind": "reactor.stable_return.receipt"},
    )
    assert stable_return_list.status_code == 200
    assert {item["event_id"] for item in stable_return_list.json()["items"]} == {event_id}

    status = client.get("/reactor/status")
    assert status.status_code == 200
    assert status.json()["total"] == 1
    assert status.json()["trigger_source_counts"] == {"mission_queue": 1}
    assert status.json()["status_counts"] == {"dispatch_deferred": 1}
    assert status.json()["verification_counts"] == {"not_available": 1}
    assert status.json()["verification_outcome_counts"] == {"dispatch_engine_not_implemented": 1}
    assert status.json()["stable_return_counts"] == {"settled": 1}


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


def test_reactor_review_queue_route_projects_readonly_items(monkeypatch, tmp_path: Path) -> None:
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
            "approval_id": "appr_reactor_review_queue",
        },
    ).json()
    approval_id = str(approval["event_id"])
    client.post(
        "/reactor/events/dispatch_attempt",
        json={"event_id": approval_id, "actor": _REACTOR_ACTOR},
    )

    retry = client.post(
        "/reactor/events/enqueue",
        json={
            "trigger_source": "mission_queue",
            "summary": "Retry candidate needs scheduler review",
            "actor": _REACTOR_ACTOR,
            "action_class": "mission_tick",
            "max_actions": 1,
            "max_retries": 2,
        },
    ).json()
    retry_id = str(retry["event_id"])
    client.post(
        "/reactor/events/dispatch_attempt",
        json={"event_id": retry_id, "actor": _REACTOR_ACTOR},
    )

    queue = client.get("/reactor/review_queue")

    assert queue.status_code == 200
    body = queue.json()
    assert body["ok"] is True
    assert body["available_total"] == 2
    assert body["route_counts"] == {"approval_queue": 1, "retry_backoff": 1}
    assert body["governance"]["execution_authority"] is False
    assert body["governance"]["approval_authority"] is False
    assert body["governance"]["dispatch_authority"] is False

    by_id = {item["event_id"]: item for item in body["items"]}
    assert by_id[approval_id]["review"]["route"] == "approval_queue"
    assert by_id[approval_id]["review"]["gate"] == "approval_required"
    assert by_id[approval_id]["trigger"]["approval_id"] == "appr_reactor_review_queue"
    assert by_id[retry_id]["review"]["route"] == "retry_backoff"
    assert by_id[retry_id]["review"]["receipt_kind"] == "reactor.retry.schedule.receipt"

    retry_only = client.get("/reactor/review_queue", params={"route": "retry_backoff"})
    assert retry_only.status_code == 200
    assert retry_only.json()["available_total"] == 1
    assert retry_only.json()["items"][0]["event_id"] == retry_id


def test_reactor_retry_schedule_readback_routes(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", json.dumps({_REACTOR_ACTOR: ["reactor.write"]}))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    queued = client.post(
        "/reactor/events/enqueue",
        json={
            "trigger_source": "mission_queue",
            "summary": "Deferred Reactor dispatch needs a durable retry schedule",
            "actor": _REACTOR_ACTOR,
            "action_class": "mission_tick",
            "max_actions": 1,
            "max_retries": 2,
            "backoff_seconds": 45,
        },
    )
    assert queued.status_code == 200
    event_id = str(queued.json()["event_id"])

    attempted = client.post(
        "/reactor/events/dispatch_attempt",
        json={
            "event_id": event_id,
            "actor": _REACTOR_ACTOR,
            "reason": "schedule retry without starting retry execution",
        },
    )
    assert attempted.status_code == 200
    event = attempted.json()["event"]
    retry_candidate = event["dispatch"]["retry_candidate"]
    retry_schedule = event["dispatch"]["retry_schedule"]
    retry_schedule_receipt = event["dispatch"]["retry_schedule_receipt"]
    retry_schedule_id = retry_schedule["retry_schedule_id"]
    assert retry_candidate["retry_scheduled"] is True
    assert retry_schedule["kind"] == "reactor.retry_schedule.item"
    assert retry_schedule["candidate_id"] == retry_candidate["candidate_id"]
    assert retry_schedule["status"] == "scheduled"
    assert retry_schedule["due_after_ts"] == retry_candidate["next_retry_after_ts"]
    assert retry_schedule["retry_started"] is False
    assert retry_schedule["execution_started"] is False
    assert retry_schedule["governance"]["retry_execution_authority"] is False
    assert retry_schedule_receipt["kind"] == "reactor.retry.schedule.receipt"
    assert retry_schedule_receipt["retry_schedule_id"] == retry_schedule_id
    assert retry_schedule_receipt["retry_scheduled"] is True
    assert event["latest_verification_receipt"]["verification_outcome"] == "retry_scheduled"
    assert event["latest_stable_return"]["source_receipt_kind"] == "reactor.retry.schedule.receipt"
    assert event["latest_stable_return"]["retry_scheduled"] is True

    listed = client.get("/reactor/retries/list")
    assert listed.status_code == 200
    listed_body = listed.json()
    assert listed_body["ok"] is True
    assert listed_body["total"] == 1
    assert listed_body["items"][0]["retry_schedule_id"] == retry_schedule_id
    assert listed_body["items"][0]["event_id"] == event_id
    assert listed_body["governance"]["retry_execution_authority"] is False

    scheduled_only = client.get("/reactor/retries/list", params={"status": "scheduled"})
    assert scheduled_only.status_code == 200
    assert {item["retry_schedule_id"] for item in scheduled_only.json()["items"]} == {retry_schedule_id}

    fetched = client.get("/reactor/retries/get", params={"id": retry_schedule_id})
    assert fetched.status_code == 200
    fetched_body = fetched.json()
    assert fetched_body["ok"] is True
    assert fetched_body["item"]["retry_schedule_id"] == retry_schedule_id
    assert fetched_body["item"]["retry_started"] is False
    assert fetched_body["item"]["execution_started"] is False

    schedule_receipts = client.get(
        "/reactor/events/list",
        params={"receipt_kind": "reactor.retry.schedule.receipt"},
    )
    assert schedule_receipts.status_code == 200
    assert {item["event_id"] for item in schedule_receipts.json()["items"]} == {event_id}

    status = client.get("/reactor/status")
    assert status.status_code == 200
    assert status.json()["retry_schedule_counts"] == {"scheduled": 1}
    assert status.json()["retry_schedule_total"] == 1


def test_reactor_deadletter_queue_readback_routes(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", json.dumps({_REACTOR_ACTOR: ["reactor.write"]}))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    queued = client.post(
        "/reactor/events/enqueue",
        json={
            "trigger_source": "mission_queue",
            "summary": "Budget-exhausted Reactor event needs real deadletter queueing",
            "actor": _REACTOR_ACTOR,
            "action_class": "mission_tick",
            "max_actions": 0,
            "max_retries": 1,
        },
    )
    assert queued.status_code == 200
    event_id = str(queued.json()["event_id"])

    attempted = client.post(
        "/reactor/events/dispatch_attempt",
        json={"event_id": event_id, "actor": _REACTOR_ACTOR},
    )
    assert attempted.status_code == 200
    event = attempted.json()["event"]
    deadletter_item = event["dispatch"]["deadletter_item"]
    deadletter_id = deadletter_item["deadletter_id"]
    assert deadletter_item["kind"] == "reactor.deadletter.item"
    assert deadletter_item["event_id"] == event_id
    assert event["dispatch"]["deadletter_enqueue"]["status"] == "queued"
    assert event["dispatch"]["deadletter_candidate"]["deadletter_enqueued"] is True
    assert event["governance"]["deadletter_resolution_authority"] is False

    listed = client.get("/reactor/deadletters/list")
    assert listed.status_code == 200
    listed_body = listed.json()
    assert listed_body["ok"] is True
    assert listed_body["total"] == 1
    assert listed_body["items"][0]["deadletter_id"] == deadletter_id
    assert listed_body["items"][0]["source_receipt_kind"] == "reactor.deadletter_candidate.receipt"
    assert listed_body["governance"]["deadletter_resolution_authority"] is False

    fetched = client.get("/reactor/deadletters/get", params={"id": deadletter_id})
    assert fetched.status_code == 200
    fetched_body = fetched.json()
    assert fetched_body["ok"] is True
    assert fetched_body["item"]["deadletter_id"] == deadletter_id
    assert fetched_body["item"]["execution_started"] is False
    assert fetched_body["item"]["retry_started"] is False
    assert fetched_body["item"]["escalation_started"] is False

    status = client.get("/reactor/status")
    assert status.status_code == 200
    assert status.json()["deadletter_queue_counts"] == {"queued": 1}
    assert status.json()["deadletter_total"] == 1


def test_reactor_dispatch_attempt_routes_missing_approval_into_pending_queue(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", json.dumps({_REACTOR_ACTOR: ["reactor.write"]}))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    queued = client.post(
        "/reactor/events/enqueue",
        json={
            "trigger_source": "user_request",
            "summary": "Approval-required Reactor work needs a real queue item",
            "actor": _REACTOR_ACTOR,
            "risk_tier": "critical",
            "action_class": "mutate",
            "approval_required": True,
            "mission_id": "msn_reactor_api_approval",
            "operation_id": "tsk_reactor_api_approval",
        },
    )
    assert queued.status_code == 200
    event_id = str(queued.json()["event_id"])

    attempted = client.post(
        "/reactor/events/dispatch_attempt",
        json={
            "event_id": event_id,
            "actor": _REACTOR_ACTOR,
            "reason": "queue missing approval for Reactor dispatch",
        },
    )

    assert attempted.status_code == 200
    body = attempted.json()
    assert body["ok"] is True
    event = body["event"]
    approval_id = event["trigger"]["approval_id"]
    assert approval_id
    assert event["dispatch"]["approval_request"]["approval_id"] == approval_id
    assert event["dispatch"]["approval_request"]["approval_queued"] is True
    assert event["governance"]["approval_authority"] is False
    assert event["governance"]["approval_request_queued"] is True

    approvals = client.get("/approvals/list", params={"status": "pending", "limit": 20})
    assert approvals.status_code == 200
    pending = next(item for item in approvals.json()["items"] if item["id"] == approval_id)
    assert pending["action"] == "reactor.dispatch"
    assert pending["status"] == "pending"
    assert pending["payload"]["event_id"] == event_id
    assert pending["payload"]["route"] == "approval_queue"
    assert pending["payload"]["gate"] == "approval_required"
    assert pending["payload"]["execution_started"] is False
    assert pending["payload"]["dispatch_applied"] is False

    status = client.get("/reactor/status")
    assert status.status_code == 200
    assert status.json()["approval_request_counts"] == {"pending": 1}

    review_queue = client.get("/reactor/review_queue", params={"route": "approval_queue"})
    assert review_queue.status_code == 200
    review_item = review_queue.json()["items"][0]
    assert review_item["trigger"]["approval_id"] == approval_id
    assert review_item["review"]["receipt_kind"] == "reactor.approval_request.receipt"
    assert review_item["review"]["receipt_ref"] == approval_id


def test_reactor_dispatch_attempt_reconciles_approved_decision(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv(
        "FRANCIS_API_ACTOR_SCOPES",
        json.dumps({_REACTOR_ACTOR: ["reactor.write"], _APPROVAL_ACTOR: ["approvals.decide"]}),
    )

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    queued = client.post(
        "/reactor/events/enqueue",
        json={
            "trigger_source": "user_request",
            "summary": "Approved Reactor work should resume only to deferred dispatch",
            "actor": _REACTOR_ACTOR,
            "risk_tier": "critical",
            "action_class": "mutate",
            "approval_required": True,
        },
    )
    assert queued.status_code == 200
    event_id = str(queued.json()["event_id"])

    first_attempt = client.post(
        "/reactor/events/dispatch_attempt",
        json={
            "event_id": event_id,
            "actor": _REACTOR_ACTOR,
            "reason": "queue missing approval for Reactor dispatch",
        },
    )
    assert first_attempt.status_code == 200
    approval_id = first_attempt.json()["event"]["trigger"]["approval_id"]
    assert approval_id

    approved = client.post(
        "/approvals/decision",
        json={
            "id": approval_id,
            "action": "approve",
            "actor": _APPROVAL_ACTOR,
            "comment": "approved for Reactor resume proof",
        },
    )
    assert approved.status_code == 200
    assert approved.json()["ok"] is True
    assert approved.json()["status"] == "approved"

    resumed = client.post(
        "/reactor/events/dispatch_attempt",
        json={
            "event_id": event_id,
            "actor": _REACTOR_ACTOR,
            "reason": "resume after approval decision",
        },
    )

    assert resumed.status_code == 200
    body = resumed.json()
    assert body["ok"] is True
    event = body["event"]
    assert event["status"] == "dispatch_deferred"
    assert event["stable_state"] == "awaiting_dispatch_engine"
    assert event["dispatch"]["allowed"] is True
    assert event["dispatch"]["applied"] is False
    assert event["dispatch"]["engine"] == "not_implemented"
    assert "blocker" not in event["dispatch"]
    approval_decision = event["dispatch"]["approval_decision"]
    assert approval_decision["kind"] == "reactor.approval_decision.receipt"
    assert approval_decision["approval_id"] == approval_id
    assert approval_decision["status"] == "approved"
    assert approval_decision["approval_allows_dispatch"] is True
    assert approval_decision["execution_started"] is False
    assert event["governance"]["approval_authority"] is False
    assert event["governance"]["dispatch_authority"] is False
    assert event["governance"]["execution_authority"] is False

    status = client.get("/reactor/status")
    assert status.status_code == 200
    assert status.json()["status_counts"] == {"dispatch_deferred": 1}
    assert status.json()["approval_decision_counts"] == {"approved": 1}

    review_queue = client.get("/reactor/review_queue", params={"route": "approval_queue"})
    assert review_queue.status_code == 200
    assert review_queue.json()["available_total"] == 0


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
